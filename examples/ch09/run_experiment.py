"""Exp-09-01 deterministic teaching experiment, no LLM or remote services."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sys
import time

from plan_validator import graph_order, search_feasibility, validate

HERE = Path(__file__).resolve().parent


def text_adapter(text, template, env):
    """Exact six-phrase parser, NOT a general free-text planner/parser."""
    tasks = []
    for line in text.splitlines():
        if not line.startswith('- 使用 ') or not line.endswith('。'):
            raise ValueError('unsupported phrase')
        name = line[5:-1]
        if name not in env['tools'] or any(t['id'] == name for t in tasks):
            raise ValueError('unknown or duplicate tool')
        tool = env['tools'][name]
        tasks.append(dict(id=name, tool=name, tool_version=tool['version'],
                          depends_on=[tasks[-1]['id']] if tasks else [],
                          preconditions=tool['preconditions'][:], postconditions=tool['postconditions'][:],
                          delete_effects=tool['delete_effects'][:], resources=tool['resources'].copy(),
                          acceptance=tool['postconditions'][:]))
    plan = deepcopy(template)
    plan['tasks'] = tasks
    return plan


def execute_mock(plan, env, fault=None):
    """Independent runtime checks trusted preconditions, costs and observed facts.

    Does not call validate. Checks one deterministic serial order, returns
    simulated evidence only; all actual services and human approvals are absent.
    """
    order = graph_order(plan['tasks'])
    if order is None:
        return dict(success=False, reason='cycle', events=[], evidence=[], spent_credit=0)
    tasks = {t['id']: t for t in plan['tasks']}
    state = set(env['initial_state'])
    events, evidence = [], []
    spent = {'credit': 0, 'duration_ms': 0}
    for key in order:
        task = tasks[key]
        tool = env['tools'].get(task['tool'])
        reason = None
        if not tool or not tool['available'] or (task['tool'] == 'submit' and fault == 'tool_offline_after_snapshot'):
            reason = 'tool_unavailable'
        elif not set(tool['preconditions']) <= state:
            reason = 'precondition_missing'
        elif tool['requires_approval'] and 'approved' not in state:
            reason = 'approval_missing'
        elif any(spent[u] + tool['resources'][u] > min(plan['budget'][u], env['budget'][u]) for u in spent):
            reason = 'budget_exceeded'
        if reason:
            events.append(dict(task_id=key, status='blocked', reason=reason))
            return dict(success=False, reason=reason, events=events, evidence=evidence, spent_credit=spent['credit'])
        for unit in spent:
            spent[unit] += tool['resources'][unit]
        no_effect = task['tool'] == 'submit' and fault == 'http_200_without_business_effect'
        events.append(dict(task_id=key, tool=task['tool'], state_before=sorted(state),
                           requires_approval=tool['requires_approval'],
                           status='http_200' if no_effect else 'mock_effect_applied'))
        if not no_effect:
            state.difference_update(tool['delete_effects'])
            state.update(tool['postconditions'])
            evidence.extend(dict(task_id=key, predicate=p, producer='independent_mock_observer', level='deterministic_mock')
                            for p in tool['postconditions'])
        if not set(task['acceptance']) <= {e['predicate'] for e in evidence if e['task_id'] == key}:
            return dict(success=False, reason='acceptance_evidence_missing', events=events, evidence=evidence, spent_credit=spent['credit'])
        if any(set(pair) <= state for pair in env['conflicts']):
            return dict(success=False, reason='state_conflict', events=events, evidence=evidence, spent_credit=spent['credit'])
    success = set(env['goal_conditions']) <= state
    return dict(success=success, reason='accepted_mock' if success else 'goal_unreached', events=events,
                evidence=evidence, spent_credit=spent['credit'])


def run(out):
    raw = (HERE / 'plan_cases.jsonl').read_bytes()
    cases = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    records = []
    for case in cases:
        env = case['environment']
        for arm in ('free_text', 'structured', 'structured_validated'):
            start = time.perf_counter_ns()
            candidate = deepcopy(case['candidate_plan'])
            payload = case['free_text_plan'] if arm == 'free_text' else json.dumps(candidate, ensure_ascii=False, sort_keys=True)
            if arm == 'free_text':
                candidate = text_adapter(payload, candidate, env)
            report = validate(candidate, env)  # offline evaluator for all arms
            # Only arm 3 uses the report to gate dispatch. No repair is performed.
            admitted = arm != 'structured_validated' or report['status'] == 'VALID_UNDER_MODEL'
            feasibility = search_feasibility(env) if arm == 'structured_validated' else {'status': 'SAT_MODEL', 'expanded': 0, 'witness': None}
            elapsed = time.perf_counter_ns() - start
            outcome = execute_mock(candidate, env, case['runtime_fault']) if admitted else dict(
                success=False, reason='static_rejected', events=[], evidence=[], spent_credit=0)
            records.append(dict(case_id=case['case_id'], arm=arm, expected_goal_feasible=case['expected_goal_feasible'],
                                annotation=case['annotation'], static_report=report, admitted=admitted,
                                feasibility_diagnosis=feasibility, outcome=outcome, payload_bytes=len(payload.encode('utf-8')),
                                local_processing_ns=elapsed, model_calls=0, model_tokens=None, paid_cost=0))
    summary = {}
    for arm in ('free_text', 'structured', 'structured_validated'):
        rows = [r for r in records if r['arm'] == arm]
        infeasible = [r for r in rows if not r['expected_goal_feasible']]
        feasible = [r for r in rows if r['expected_goal_feasible']]
        admitted = [r for r in rows if r['admitted']]
        summary[arm] = dict(
            n=len(rows), structurally_acyclic=sum(not any(e['code'] in ('CYCLE','MISSING_DEPENDENCY','DUPLICATE_ID','SHAPE') for e in r['static_report']['errors']) for r in rows),
            static_valid=sum(r['static_report']['status'] == 'VALID_UNDER_MODEL' for r in rows),
            goal_feasibility_correct=sum((r['feasibility_diagnosis']['status'] == 'SAT_MODEL') == r['expected_goal_feasible'] for r in rows if r['feasibility_diagnosis']['status'] != 'UNKNOWN'),
            feasibility_unknown=sum(r['feasibility_diagnosis']['status'] == 'UNKNOWN' for r in rows),
            infeasible_correctly_diagnosed=sum(r['feasibility_diagnosis']['status'] == 'UNSAT_MODEL' for r in infeasible),
            infeasible_n=len(infeasible), infeasible_blocked=sum(not r['admitted'] for r in infeasible),
            feasible_candidates_blocked=sum(not r['admitted'] for r in feasible),
            admitted=len(admitted), executed_success=sum(r['outcome']['success'] for r in rows),
            feasible_executed_success=sum(r['outcome']['success'] for r in feasible), feasible_n=len(feasible),
            unsafe_submit_events=sum(e.get('requires_approval', False) and 'approved' not in e.get('state_before', [])
                                     for r in rows for e in r['outcome']['events'] if e['status'] != 'blocked'),
            payload_bytes=sum(r['payload_bytes'] for r in rows),
            local_processing_ns=sum(r['local_processing_ns'] for r in rows),
            model_calls=0, model_tokens=None, paid_cost=0,
            mock_execution_credit=sum(r['outcome']['spent_credit'] for r in rows),
            feasibility_search_expanded=sum(r['feasibility_diagnosis']['expanded'] for r in rows))
    out.mkdir(parents=True, exist_ok=True)
    (out / 'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in records), encoding='utf-8')
    manifest = dict(experiment='Exp-09-01', evidence_level='deterministic_mock', date=datetime.now(timezone.utc).date().isoformat(),
                    recorded_at_utc=datetime.now(timezone.utc).isoformat(),
                    python=sys.version, platform=platform.platform(), repeats=1, seed='none; deterministic',
                    input_sha256=hashlib.sha256(raw).hexdigest(),
                    code_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'plan_validator.py', HERE/'run_experiment.py', HERE/'proposals/plan_schema.json']},
                    summary=summary)
    (out / 'summary.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=HERE/'results/exp09-01')
    run(parser.parse_args().output_dir)
