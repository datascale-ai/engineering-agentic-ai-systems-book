"""Ch09 proposal-only validator. Pure, bounded, deterministic; no remote actions.

VALID_UNDER_MODEL means every enumerated serial topological order is valid in
the supplied trusted model. It does not assert real-world completion.
"""
from collections import deque
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / 'proposals/plan_schema.json').read_text(encoding='utf-8'))


def shape_errors(value, schema, path='$'):
    """Validate exactly the JSON Schema keyword subset used by this proposal.

    This is not a general JSON Schema implementation. Schema is trusted/local.
    """
    if '$ref' in schema:
        target = SCHEMA
        for token in schema['$ref'].split('/')[1:]:
            target = target[token]
        return shape_errors(value, target, path)
    types = schema.get('type', [])
    types = [types] if isinstance(types, str) else types
    checks = {'object': lambda x: isinstance(x, dict),
              'array': lambda x: isinstance(x, list),
              'string': lambda x: isinstance(x, str),
              'integer': lambda x: type(x) is int,
              'null': lambda x: x is None}
    if types and not any(checks[t](value) for t in types):
        return [f'{path}: type {types}']
    errors = []
    if 'const' in schema and value != schema['const']:
        errors.append(f'{path}: const')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        for name in schema.get('required', []):
            if name not in value:
                errors.append(f'{path}.{name}: required')
        if schema.get('additionalProperties') is False:
            errors += [f'{path}.{k}: additional property' for k in sorted(value.keys() - props.keys())]
        for k in value.keys() & props.keys():
            errors += shape_errors(value[k], props[k], f'{path}.{k}')
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            errors.append(f'{path}: minItems')
        if schema.get('uniqueItems') and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append(f'{path}: uniqueItems')
        for i, v in enumerate(value):
            errors += shape_errors(v, schema.get('items', {}), f'{path}[{i}]')
    if isinstance(value, str) and len(value) < schema.get('minLength', 0):
        errors.append(f'{path}: minLength')
    if type(value) is int and value < schema.get('minimum', value):
        errors.append(f'{path}: minimum')
    return sorted(errors)


def graph_order(tasks):
    """Kahn ordering; dangling references are checked by validate first."""
    deps = {t['id']: set(t['depends_on']) for t in tasks}
    order = []
    while deps:
        ready = sorted(k for k, parents in deps.items() if not parents)
        if not ready:
            return None
        for key in ready:
            order.append(key)
            del deps[key]
        for parents in deps.values():
            parents.difference_update(ready)
    return order


def inconsistent(state, conflicts):
    return any(set(pair) <= state for pair in conflicts)


def validate(plan, env, max_orders=1000):
    """env is a trusted snapshot, separate from untrusted candidate plan."""
    errors = [{'code': 'SHAPE', 'detail': e} for e in shape_errors(plan, SCHEMA)]
    def fail(code, detail):
        errors.append({'code': code, 'detail': detail})
    def report(status, checked=0, witness=None):
        return dict(status=status, errors=sorted(errors, key=lambda e: (e['code'], e['detail'])),
                    checked_orders=checked, witness=witness,
                    snapshot_id=env['snapshot_id'], schema_version='ch09-proposal-0.1')
    if errors:
        return report('INVALID')
    tasks = plan['tasks']
    ids = [t['id'] for t in tasks]
    if len(ids) != len(set(ids)):
        fail('DUPLICATE_ID', 'task ids must be unique')
    if plan['goal_ref'] != env['goal_ref'] or set(plan['goal_conditions']) != set(env['goal_conditions']):
        fail('GOAL_MISMATCH', 'candidate cannot redefine trusted goal')
    if plan['snapshot_id'] != env['snapshot_id']:
        fail('SNAPSHOT_MISMATCH', 'tool/state snapshot changed')
    if plan['previous_version'] is not None and plan['previous_version'] >= plan['version']:
        fail('VERSION_ORDER', 'previous_version must precede version')
    if plan['constraints'] != env['conflicts']:
        fail('CONSTRAINT_MISMATCH', 'candidate cannot remove invariants')
    if inconsistent(set(env['goal_conditions']), env['conflicts']):
        fail('GOAL_CONFLICT', 'mutually exclusive goal predicates')
    totals = {'credit': 0, 'duration_ms': 0}
    for task in tasks:
        for parent in task['depends_on']:
            if parent not in ids:
                fail('MISSING_DEPENDENCY', f"{task['id']} -> {parent}")
        tool = env['tools'].get(task['tool'])
        if tool is None:
            fail('TOOL_MISSING', task['tool'])
            continue
        if not tool['available']:
            fail('TOOL_UNAVAILABLE', task['tool'])
        if task['tool_version'] != tool['version']:
            fail('TOOL_VERSION', task['id'])
        for field in ('preconditions', 'postconditions', 'delete_effects'):
            if set(task[field]) != set(tool[field]):
                fail('ACTION_MODEL_MISMATCH', f"{task['id']}.{field}")
        if task['resources'] != tool['resources']:
            fail('RESOURCE_ESTIMATE_MISMATCH', task['id'])
        if not set(task['acceptance']) <= set(tool['postconditions']):
            fail('ACCEPTANCE_UNSUPPORTED', task['id'])
        for unit in totals:
            totals[unit] += tool['resources'][unit]
        if tool['requires_approval']:
            ancestors = set()
            stack = list(task['depends_on'])
            lookup = {t['id']: t for t in tasks}
            while stack:
                parent = stack.pop()
                if parent in ancestors or parent not in lookup:
                    continue
                ancestors.add(parent)
                stack.extend(lookup[parent]['depends_on'])
            # Approval comes from the trusted registry, never a model's label.
            if not any(env['tools'].get(lookup[a]['tool'], {}).get('is_approval', False) for a in ancestors):
                fail('APPROVAL_DEPENDENCY_MISSING', task['id'])
    for unit, amount in totals.items():
        if amount > min(plan['budget'][unit], env['budget'][unit]):
            fail('BUDGET_EXCEEDED', f'{unit}: {amount}')
    if not errors and graph_order(tasks) is None:
        fail('CYCLE', 'no complete topological order')
    if errors:
        return report('INVALID')
    lookup = {t['id']: t for t in tasks}
    checked = 0
    # Explore all serial topological orders. A single failing order means the
    # graph is insufficient for a scheduler that may choose any ready task.
    stack = [(set(), set(env['initial_state']), [])]
    while stack:
        done, state, order = stack.pop()
        if len(done) == len(tasks):
            checked += 1
            if not set(env['goal_conditions']) <= state:
                fail('GOAL_UNREACHED', ','.join(sorted(set(env['goal_conditions']) - state)))
                return report('INVALID', checked, order)
            if checked > max_orders:
                fail('ORDER_LIMIT', str(max_orders))
                return report('UNKNOWN', checked, order)
            continue
        ready = sorted(k for k, t in lookup.items() if k not in done and set(t['depends_on']) <= done)
        for key in reversed(ready):
            tool = env['tools'][lookup[key]['tool']]
            if not set(tool['preconditions']) <= state:
                fail('PRECONDITION_UNSUPPORTED', key)
                return report('INVALID', checked, order + [key])
            next_state = (state - set(tool['delete_effects'])) | set(tool['postconditions'])
            if inconsistent(next_state, env['conflicts']):
                fail('STATE_CONFLICT', key)
                return report('INVALID', checked, order + [key])
            stack.append((done | {key}, next_state, order + [key]))
    return report('VALID_UNDER_MODEL', checked)


def search_feasibility(env, max_states=10000):
    """Independent bounded state-space search, not candidate validation.

    Exhaustion proves UNSAT only in this finite, deterministic trusted model.
    A found sequence proves existence, not safety of every DAG ordering.
    """
    if inconsistent(set(env['goal_conditions']), env['conflicts']):
        return {'status': 'UNSAT_MODEL', 'expanded': 0, 'witness': None}
    queue = deque([(frozenset(env['initial_state']), 0, 0, [])])
    seen = set()
    while queue:
        state, credit, duration, order = queue.popleft()
        marker = (state, credit, duration)
        if marker in seen:
            continue
        seen.add(marker)
        if len(seen) > max_states:
            return {'status': 'UNKNOWN', 'expanded': len(seen), 'witness': None}
        if set(env['goal_conditions']) <= state:
            return {'status': 'SAT_MODEL', 'expanded': len(seen), 'witness': order}
        for key, tool in sorted(env['tools'].items()):
            if not tool['available'] or not set(tool['preconditions']) <= state:
                continue
            if tool['requires_approval'] and 'approved' not in state:
                continue
            c = credit + tool['resources']['credit']
            d = duration + tool['resources']['duration_ms']
            if c > env['budget']['credit'] or d > env['budget']['duration_ms']:
                continue
            new_state = (state - set(tool['delete_effects'])) | set(tool['postconditions'])
            if new_state != state and not inconsistent(new_state, env['conflicts']):
                queue.append((frozenset(new_state), c, d, order + [key]))
    return {'status': 'UNSAT_MODEL', 'expanded': len(seen), 'witness': None}
