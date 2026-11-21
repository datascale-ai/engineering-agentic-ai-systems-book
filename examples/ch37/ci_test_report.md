# 本地测试报告

日期：2026-11-11。这是本地执行报告和 CI 接入说明，远程 CI 尚未实跑，F 尚未独立审阅。

环境：Windows、CPython 3.12.14、SQLite 3.53.1、pytest 8.3.5、uv 0.12.8。源码身份由 `../ch36/asset_inventory.json` 记录，包含本次尚未提交的新实现；Git HEAD 不能单独代表全部交付内容。

| 验证 | 实际结果 | 证据 |
| --- | --- | --- |
| 固定夹具 | 30 个唯一 ID，六组各五 | `fixtures/cases.jsonl`、`test_matrix.yaml` |
| 行为套件 | 69 passed，包括 27 组三步枚举 | `reports/clean-copy-junit.xml`（同机新目录/新环境） |
| 根测试 | 77 passed，含既有 8 个结构检查 | `reports/junit.xml` |
| 本地三切片 | 3 个切片通过；PRJ-3 两进程 42→0 | Ch36 `reports/clean_copy.json`、`reports/reproduction.json` |
| 缺陷对照 | 2 工单、2 created；自报通过，独立验收 false，exit1 | `reports/regression_buggy.json` |
| 修复对照 | 1 工单、1 created；独立验收 true，exit0 | `reports/regression_fixed.json` |
| 文档 | MkDocs strict 构建通过；两章图和脚注链接检查通过 | 章节自检记录 |

根 pytest 的 `testpaths` 已纳入 `examples/ch37/tests`；既有工作流直接运行 pytest，可收集新增测试。JUnit 耗时含测试安排与释放，不作为业务延迟。示例执行无真实模型和网络；无 Hypothesis、覆盖率百分比、并发压测或跨机器结论。干净副本是同机复制当前交付文件，使用缓存离线重建，不是已发布 Git 树或其他学生独立复现。

重复命令和预期退出见 `README.md`。测试失败按正文 Tab-37-02 分类；没有把关键失败静默改为跳过。原始 SQLite 可通过命令重建；报告不含凭证或真实业务资料。

## 2026-11-20 补充验证

`tests/test_student_e_studies.py` 新增21个展开测试项：持久回执、冲突重复、精确到期、旧代次/核验、并发领取、跨重启预算、消息模式、20故障脚本、规则/人工答案、证据缺口、字节预算、两环境200试次、延迟查询/幂等、退役门禁和独立进程PRJ-2。根入口98项通过，原77项均保留。报告见 [新增JUnit](reports/student-e-20261120-junit.xml) 和 [项目及实验报告](../ch36/experiment_report.md)。旧报告仅代表其原日期；本轮没有声明真实模型、生产部署、远程CI或其他学生已完成复现。
