"""Behavioral checks for the Ch09 teaching proposal, not a public contract suite."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'examples/ch09'


def module(name):
    isolated_name = f'_ch09_test_asset_{name}'
    spec = importlib.util.spec_from_file_location(isolated_name, ASSETS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[isolated_name] = mod
    spec.loader.exec_module(mod)
    return mod


validator = module('plan_validator')
_prior_validator = sys.modules.get('plan_validator')
sys.modules['plan_validator'] = validator
try:
    runner = module('run_experiment')
finally:
    if _prior_validator is None:
        sys.modules.pop('plan_validator', None)
    else:
        sys.modules['plan_validator'] = _prior_validator
factory = module('make_cases')


@pytest.fixture
def case():
    return factory.base_case(1)


def codes(report):
    return {e['code'] for e in report['errors']}


def test_good_dag_accepts_all_orders_and_mock_evidence(case):
    report = validator.validate(case['candidate_plan'], case['environment'])
    assert report['status'] == 'VALID_UNDER_MODEL'
    assert report['checked_orders'] == 3
    result = runner.execute_mock(case['candidate_plan'], case['environment'])
    assert result['success']
    assert any(e['predicate'] == 'verified' and e['producer'] == 'independent_mock_observer' for e in result['evidence'])


@pytest.mark.parametrize('mutate', [
    lambda p: p['tasks'][0].update(resources={'credit': -1, 'duration_ms': 10}),
    lambda p: p['tasks'][0].update(resources={'credit': True, 'duration_ms': 10}),
    lambda p: p['tasks'][0].update(acceptance=[]),
    lambda p: p['tasks'][0].update(preconditions='request'),
    lambda p: p.update(unknown_field='ignored?'),
    lambda p: p.update(tasks=[]),
])
def test_malformed_input_rejected_without_crash(case, mutate):
    mutate(case['candidate_plan'])
    assert 'SHAPE' in codes(validator.validate(case['candidate_plan'], case['environment']))


@pytest.mark.parametrize('change,expected', [
    (lambda p: p['tasks'][0]['depends_on'].append('missing'), 'MISSING_DEPENDENCY'),
    (lambda p: p['tasks'][0]['depends_on'].append('verify'), 'CYCLE'),
    (lambda p: p['tasks'][0].update(id='qualify'), 'DUPLICATE_ID'),
    (lambda p: p.update(goal_conditions=['request']), 'GOAL_MISMATCH'),
    (lambda p: p.update(constraints=[]), 'CONSTRAINT_MISMATCH'),
    (lambda p: p.update(snapshot_id='stale'), 'SNAPSHOT_MISMATCH'),
    (lambda p: p.update(previous_version=1), 'VERSION_ORDER'),
    (lambda p: p['tasks'][4].update(preconditions=[]), 'ACTION_MODEL_MISMATCH'),
    (lambda p: p['tasks'][4]['resources'].update(credit=0), 'RESOURCE_ESTIMATE_MISMATCH'),
])
def test_untrusted_plan_cannot_redefine_model(case, change, expected):
    change(case['candidate_plan'])
    assert expected in codes(validator.validate(case['candidate_plan'], case['environment']))


def test_missing_approval_rejected_and_runtime_blocks_it():
    c = factory.make_cases()[5]
    assert 'APPROVAL_DEPENDENCY_MISSING' in codes(validator.validate(c['candidate_plan'], c['environment']))
    result = runner.execute_mock(c['candidate_plan'], c['environment'])
    assert not result['success']
    assert not any(e.get('tool') == 'submit' for e in result['events'])


def test_one_good_order_does_not_make_dag_safe():
    c = factory.make_cases()[8]
    report = validator.validate(c['candidate_plan'], c['environment'])
    assert report['status'] == 'INVALID'
    assert 'PRECONDITION_UNSUPPORTED' in codes(report)


def test_delete_effect_threat_requires_ordering(case):
    p, env = case['candidate_plan'], case['environment']
    env['tools']['revoke'] = dict(version='mock-1', available=True, preconditions=['approved'],
        postconditions=['revoked'], delete_effects=['approved'], resources={'credit': 0, 'duration_ms': 0},
        requires_approval=False, is_approval=False)
    t = env['tools']['revoke']
    p['tasks'].append(dict(id='revoke', tool='revoke', tool_version='mock-1', depends_on=['approve'],
        preconditions=t['preconditions'][:], postconditions=t['postconditions'][:],
        delete_effects=t['delete_effects'][:], resources=t['resources'].copy(), acceptance=['revoked']))
    assert validator.validate(p, env)['status'] == 'INVALID'
    p['tasks'][-1]['depends_on'] = ['submit']
    assert validator.validate(p, env)['status'] == 'VALID_UNDER_MODEL'


def test_proof_budget_exhaustion_is_unknown(case):
    assert validator.validate(case['candidate_plan'], case['environment'], max_orders=0)['status'] == 'UNKNOWN'
    assert validator.search_feasibility(case['environment'], max_states=0)['status'] == 'UNKNOWN'


@pytest.mark.parametrize('fault,reason', [
    ('tool_offline_after_snapshot', 'tool_unavailable'),
    ('http_200_without_business_effect', 'acceptance_evidence_missing'),
])
def test_static_valid_can_fail_runtime(case, fault, reason):
    assert validator.validate(case['candidate_plan'], case['environment'])['status'] == 'VALID_UNDER_MODEL'
    result = runner.execute_mock(case['candidate_plan'], case['environment'], fault)
    assert not result['success'] and result['reason'] == reason
    assert not any(e['predicate'] == 'verified' for e in result['evidence'])


def test_twenty_cases_and_five_infeasible_have_independent_witnesses():
    cases = [json.loads(line) for line in (ASSETS/'plan_cases.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(cases) == len({c['case_id'] for c in cases}) == 20
    assert sum(not c['expected_goal_feasible'] for c in cases) == 5
    for c in cases:
        found = validator.search_feasibility(c['environment'])
        assert (found['status'] == 'SAT_MODEL') == c['expected_goal_feasible']
        if c['expected_goal_feasible']:
            assert found['witness'] is not None
        else:
            assert found['status'] == 'UNSAT_MODEL' and found['witness'] is None


def test_data_generator_is_reproducible():
    stored = [json.loads(line) for line in (ASSETS/'plan_cases.jsonl').read_text(encoding='utf-8').splitlines()]
    assert factory.make_cases() == stored


def test_free_text_adapter_has_declared_limits(case):
    with pytest.raises(ValueError, match='unsupported phrase'):
        runner.text_adapter('请酌情办理', case['candidate_plan'], case['environment'])


def test_experiment_rejects_without_faking_completion(tmp_path):
    runner.run(tmp_path)
    rows = [json.loads(line) for line in (tmp_path/'results.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 60
    for r in rows:
        if not r['admitted']:
            assert r['outcome']['events'] == r['outcome']['evidence'] == []
            assert not r['outcome']['success']
        for e in r['outcome']['events']:
            if e.get('requires_approval'):
                assert 'approved' in e['state_before']
