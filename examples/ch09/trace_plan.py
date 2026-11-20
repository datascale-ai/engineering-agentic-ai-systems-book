"""Print/save worked traces from existing Ch09 cases; deterministic mock only."""
from pathlib import Path
import argparse
import hashlib
import json

from plan_validator import search_feasibility, validate
from run_experiment import execute_mock

HERE = Path(__file__).resolve().parent


def trace_cases(output):
    raw = (HERE / 'plan_cases.jsonl').read_bytes()
    cases = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    selected = {1, 6, 8, 9, 14, 15, 16, 18, 19, 20}
    traces = []
    for case in cases:
        if int(case['case_id'].rsplit('-', 1)[1]) not in selected:
            continue
        plan, env = case['candidate_plan'], case['environment']
        report = validate(plan, env)
        direct = execute_mock(plan, env, case['runtime_fault'])
        traces.append(dict(case_id=case['case_id'], annotation=case['annotation'],
                           evidence_level='deterministic_mock',
                           static_report=report, feasibility=search_feasibility(env),
                           direct_mock=direct,
                           gated_dispatch=report['status'] == 'VALID_UNDER_MODEL'))
    result = dict(evidence_level='deterministic_mock', model_calls=0,
                  input_sha256=hashlib.sha256(raw).hexdigest(),
                  source_sha256={name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                 for name in ('trace_plan.py', 'plan_validator.py', 'run_experiment.py')},
                  traces=traces)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    for record in traces:
        print(record['case_id'], record['static_report']['status'],
              record['feasibility']['status'], record['direct_mock']['reason'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=HERE / 'results/worked_traces.json')
    trace_cases(parser.parse_args().output)
