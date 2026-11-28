# Ch39 发布就绪检查表 (`release_checklist.md`)

> 任何候选版本进入预发布档位前，须逐项核验并填入可追溯证据路径；缺失高风险门禁证据或跳过权限/缓存核查不得放行。

| 检查项 ID | 核查维度 | 必须验证的客观条件 | 对应证据入口 | 当前基线 (`release-v1.0.0`) 状态 |
| --- | --- | --- | --- | --- |
| `RC-01` | 制品与配置绑定 | 代码、模型配置、提示版本、政策版本、Schema 版本绑定同一发布清单摘要 | `examples/ch39/results/ch39_drill_results.json` | 已通过（摘要一致） |
| `RC-02` | 分层行为测试 | Ch37 单元/集成/E2E 行为断言全部通过，无跳过的高风险回归用例 | `examples/ch37/tests/test_behaviour.py` | 已通过 |
| `RC-03` | 切片回归门禁 | Ch38 全部黄金切片通过，高风险审批切片零越权写入、零重复副作用 | `examples/ch38/regression_report.md` | 已通过（12/12） |
| `RC-04` | 可观测与密钥防泄 | TA-01—TA-05 轨迹断言通过；日志、指标与 trace 不含明文密钥 | `examples/ch38/trace_assertions.yaml` | 已通过（零泄露） |
| `RC-05` | 权限缓存隔离 | 候选配置变更后权限缓存版本号递增，旧权限条目不会跨版本残留 | `examples/ch39/drill_runner.py` | 已通过（缓存版本匹配） |
| `RC-06` | 回滚预案可演练 | 回滚目标版本、快照检查点、清缓存步骤与业务复验命令已在沙箱演练 | `examples/ch39/rollback_runbook.md` | 已通过（DRILL-03 验证） |
| `RC-07` | 适用边界声明 | 明确区分本地/预发布演练与真实生产容量、真实 IAM/网络隔离 | `examples/ch39/release_report.md` | 已声明 |
