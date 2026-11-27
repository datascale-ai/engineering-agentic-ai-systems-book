# Ch39 预发布部署、故障注入与回滚演练报告 (`Exp-39-01`)

> **证据状态**：在本地隔离临时目录运行，复用 `examples/ch36/src/book_reference/` 与 `examples/ch38/regression_runner/`。本演练仅证明所声明配置与沙箱边界下的发布门禁、五要素回滚与幂等恢复机制，不宣称为真实生产集群容灾或真实 IAM 治理验收。

## 1. 四项演练结果汇总

| 演练编号 | 演练内容 | 关键观察 | 验收结论 |
| --- | --- | --- | --- |
| `DRILL-01` | 受控发布 (`release-v1.0.0`) | CD 回归门禁通过；合规探针 `completed`(1 工单)，高风险探针 `rejected(needs_approval)`，TA-01—TA-05 通过 | **PASS** |
| `DRILL-02` | 配置错配 + 权限缓存残留 + 密钥防泄对照 | 完整门禁阻断坏候选（定位 `config_layer, model_or_prompt_layer`）；若跳过门禁且仅回滚代码，缓存残留导致 420 元高风险任务越权 `completed`；审计日志零密钥泄露 | **PASS** |
| `DRILL-03` | 五要素完整回滚与恢复验收 | 暂停入口 → 恢复代码/配置 → 清空 1 条旧权限缓存(epoch=2)；回滚后高风险任务重新被拒(`needs_approval`)，既有合法工单完好保留 | **PASS** |
| `DRILL-04` | PRJ-3 端到端综合实践演练 | 注入 `after_commit` 崩溃后重连恢复，终态 `completed`、唯一工单数 `1`、轨迹断言 `True` | **PASS** |

## 2. 事故与恢复运行时间线（摘录）

| 虚拟时刻 (ms) | 当前版本 | 事件 | 关键字段 |
| ---: | --- | --- | --- |
| 10 | `release-v1.0.0` | `cd_gate_start` | `{"candidate": "release-v1.0.0"}` |
| 20 | `release-v1.0.0` | `cd_gate_passed` | `{"candidate": "release-v1.0.0", "slices_passed": 3}` |
| 30 | `release-v1.0.0` | `staging_smoke_verified` | `{"eligible_status": "completed", "highrisk_status": "rejected", "tickets_total": 1}` |
| 40 | `release-v1.0.0` | `fault_injected_candidate` | `{"candidate": "release-v1.1.0-bad-config", "injected_secret_sample": "[REDACTED_SECRET]"}` |
| 50 | `release-v1.0.0` | `cd_gate_blocked_bad_candidate` | `{"candidate": "release-v1.1.0-bad-config", "detected_layers": ["config_layer", "model_or_prompt_layer"]}` |
| 60 | `release-v1.0.0` | `incomplete_rollback_detected` | `{"note": "code/config reverted but permission cache still stale"}` |
| 70 | `release-v1.0.0` | `rollback_step1_intake_paused` | `{"intake_enabled": false}` |
| 80 | `release-v1.0.0` | `rollback_step2_3_code_config_restored` | `{"config_digest": "a9e8573067b0"}` |
| 90 | `release-v1.0.0` | `rollback_step4_permission_cache_purged` | `{"cleared_entries": 1, "new_epoch": 2}` |
| 100 | `release-v1.0.0` | `rollback_step5_intake_resumed` | `{"intake_enabled": true}` |
| 110 | `release-v1.0.0` | `rollback_business_verified` | `{"post_highrisk_status": "rejected", "post_eligible_status": "completed", "legit_preserved": true}` |
| 120 | `release-v1.0.0` | `capstone_prj3_verified` | `{"crashed": true, "status": "completed", "tickets": 1, "trace_ok": true}` |

## 3. 生产适用边界与未覆盖项

1. 本演练在单机 SQLite 与内存权限缓存上验证五要素回滚逻辑，未覆盖多副本分布式 Redis 缓存一致性、Kubernetes 滚动更新连接排空或跨区数据库模式降级。
2. 审计日志脱敏检验了正则特征拦截，生产环境仍需结合外部 Secret Manager（如 Vault / KMS）与短期动态凭据。
