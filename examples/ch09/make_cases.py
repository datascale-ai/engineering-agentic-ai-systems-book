"""Original synthetic data, MIT under the repository license; no shared assets."""
from copy import deepcopy
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent


def base_case(number):
    def tool(pre, post, credit, approval=False, is_approval=False):
        return dict(version='mock-1', available=True, preconditions=pre, postconditions=post,
                    delete_effects=[], resources=dict(credit=credit, duration_ms=10),
                    requires_approval=approval, is_approval=is_approval)
    tools = {
        'read_policy': tool(['request'], ['policy'], 1),
        'qualify': tool(['policy'], ['eligible'], 1),
        'draft': tool(['request'], ['drafted'], 1),
        'approve': tool(['eligible', 'drafted'], ['approved'], 1, is_approval=True),
        'submit': tool(['eligible', 'drafted', 'approved'], ['submitted'], 2, approval=True),
        'verify': tool(['submitted'], ['verified'], 1),
    }
    goal_ref = f'CH09-SYN-{number:02d}'
    env = dict(snapshot_id='ch09-mock-snapshot-1', goal_ref=goal_ref, initial_state=['request'],
               goal_conditions=['verified'], conflicts=[['verified', 'denied']],
               tools=tools, budget=dict(credit=10, duration_ms=100))
    deps = {'read_policy': [], 'qualify': ['read_policy'], 'draft': [],
            'approve': ['qualify', 'draft'], 'submit': ['approve'], 'verify': ['submit']}
    tasks = [dict(id=k, depends_on=deps[k], tool=k, tool_version=t['version'],
                  preconditions=t['preconditions'][:], postconditions=t['postconditions'][:],
                  delete_effects=[], resources=t['resources'].copy(), acceptance=t['postconditions'][:])
             for k, t in tools.items()]
    plan = dict(schema_version='ch09-proposal-0.1', plan_id=f'plan-{number:02d}', version=1,
                previous_version=None, goal_ref=goal_ref, snapshot_id=env['snapshot_id'],
                goal_conditions=env['goal_conditions'][:], constraints=deepcopy(env['conflicts']),
                budget=env['budget'].copy(), tasks=tasks)
    return dict(case_id=goal_ref, goal_text='查核政策和资格，准备材料，取得人工审批后提交，并核验状态。',
                environment=env, candidate_plan=plan, expected_goal_feasible=True,
                annotation='完整计划；两分支汇合', runtime_fault=None)


def make_cases():
    cases = [base_case(i) for i in range(1, 21)]
    # Different task slices; not twenty independent domains.
    for i, name in enumerate(['差旅申请', '培训申请', '设备申请', '访问申请', '采购申请']):
        cases[i]['goal_text'] = name + '：' + cases[i]['goal_text']
    def remove(case, target):
        case['candidate_plan']['tasks'] = [t for t in case['candidate_plan']['tasks'] if t['id'] != target]
        for task in case['candidate_plan']['tasks']:
            if target in task['depends_on']:
                task['depends_on'].remove(target)
    remove(cases[5], 'approve')
    cases[5]['annotation'] = '计划遗漏审批；目标仍可行'
    remove(cases[6], 'qualify')
    cases[6]['annotation'] = '计划遗漏资格核验；目标仍可行'
    cases[7]['candidate_plan']['tasks'][0]['depends_on'] = ['verify']
    cases[7]['annotation'] = '候选依赖成环；目标仍可行'
    cases[8]['candidate_plan']['tasks'][3]['depends_on'] = ['draft']
    cases[8]['annotation'] = '审批遗漏资格依赖；一种拓扑序成功并不足够'
    cases[9]['candidate_plan']['tasks'][4]['resources']['credit'] = 0
    cases[9]['annotation'] = '计划低报写入成本；环境仍有足够预算'
    for idx, goal, count, label in [(10, 'policy', 1, '仅查询政策'),
                                    (11, 'eligible', 2, '仅核验资格'),
                                    (12, 'submitted', 5, '审批后提交，目标不要求状态验证')]:
        c = cases[idx]
        c['goal_text'] = label
        c['environment']['goal_conditions'] = [goal]
        c['candidate_plan']['goal_conditions'] = [goal]
        c['candidate_plan']['tasks'] = c['candidate_plan']['tasks'][:count]
        c['annotation'] = label
    cases[13]['runtime_fault'] = 'tool_offline_after_snapshot'
    cases[13]['annotation'] = '静态快照有效，执行前submit下线'
    cases[14]['runtime_fault'] = 'http_200_without_business_effect'
    cases[14]['annotation'] = 'submit返回200，但没有持久业务效果和证据'
    cases[15]['environment']['tools']['approve']['available'] = False
    cases[15]['annotation'] = '无可信审批能力；当前模型不可行'
    cases[16]['environment']['tools']['submit']['available'] = False
    cases[16]['annotation'] = '提交工具已下线；当前模型不可行'
    for container in [cases[17]['environment'], cases[17]['candidate_plan']]:
        container['budget']['credit'] = 6
    cases[17]['annotation'] = '最小完整链消耗7 credit，预算只有6'
    cases[18]['environment']['goal_conditions'] = ['verified', 'denied']
    cases[18]['candidate_plan']['goal_conditions'] = ['verified', 'denied']
    cases[18]['annotation'] = '目标谓词互斥'
    cases[19]['environment']['goal_conditions'] = ['archived']
    cases[19]['candidate_plan']['goal_conditions'] = ['archived']
    cases[19]['annotation'] = '环境无任何动作产生archived'
    for c in cases[15:]:
        c['expected_goal_feasible'] = False
    for c in cases:
        # Free text arm: only a tool-name bullet list. The adapter supplies a
        # sequential order from the listing; it does NOT recover missing edges.
        c['free_text_plan'] = '\n'.join(f"- 使用 {t['tool']}。" for t in c['candidate_plan']['tasks'])
    return cases


if __name__ == '__main__':
    (HERE / 'plan_cases.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False, sort_keys=True) + '\n' for c in make_cases()), encoding='utf-8')
    print('wrote 20 original synthetic cases (15 model-feasible, 5 model-infeasible)')
