# 工程证据索引

版本 `local-2026-11-20`。本索引连接正文主张、唯一源码、独立预期及实际记录；主张仅限本地教学边界。

| 证据 ID | 正文与主张 | 唯一源码/预期 | 实际记录 |
| --- | --- | --- | --- |
| E-P2-01 | 第五篇/Ch36：三角色按持久消息交接并独立核验 | `project2.py`、原Engine；`project_expected.json` | `reports/study_20261120/project2/` |
| E-P2-02 | 首项提交后进程中断不重复创建 | 独立只读服务状态、阶段代次；回归测试 | 同上report中的crash/recover和工单/created数量 |
| E19-01 | 20故障任务的生效、拒绝和有界退出 | `coordination.py`、`coordination_study.py`；故障表与预期草稿 | `reports/study_20261120/ch19/` |
| E20-01 | 同一脚本的聚合、证据与预算流程可回查 | `debate_study.py`；20道人工答案独立于模型 | `reports/study_20261120/ch20/` |
| E21-01 | 两环境有版本/时效保护及闭环对照 | `environment_study.py`；外部状态与动作前置快照评分 | `reports/study_20261120/ch21/` |
| ED-01 | 四阶段配置生命周期与有限tenant检查 | `deployment_study.py`、profiles；独立业务快照 | `reports/study_20261120/deploy/` |

源码均在 `src/book_reference/`，输入在 `fixtures/study/`。模式只有一份 `message_schema.json`，资产身份由 `asset_inventory.json` 核对，根报告给清单摘要。作者同机运行和新目录复现不能代替非作者独立运行；F审阅和公共消费者确认仍待完成。
