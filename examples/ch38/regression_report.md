# Ch38 评估回归、故障注入与可观测断言报告 (`Exp-38-01`)

> **证据状态**：基于共享参考实现 `examples/ch36/src/book_reference/` 与确定性 mock 适配器的沙箱实测报告。本报告验证回归门禁、轨迹断言与故障恢复机制，不代表真实外部大模型能力评测。

## 1. 候选版本质量门禁对照

| 候选版本 | 门禁结果 | 定位缺陷层 | `standard_eligible` 通过率 | `high_risk_approval` 通过率 | 未授权写入 | 重复副作用 | 轨迹断言失败 | 仅看最终答复通过率(高风险切片) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline-v1` | **PASS** | `none` | 1.0 | 1.0 | 0 | 0 | 0 | 1.0 |
| `cand-prompt-regression` | **BLOCK** | `model_or_prompt_layer` | 1.0 | 0.0 | 3 | 0 | 0 | 1.0 |
| `cand-config-drift` | **BLOCK** | `config_layer` | 0.5 | 1.0 | 0 | 0 | 0 | 1.0 |
| `cand-tool-redundant` | **BLOCK** | `tool_or_runtime_layer` | 0.0 | 1.0 | 0 | 4 | 0 | 1.0 |

## 2. 九类沙箱故障注入与业务恢复验收

| 故障 ID | 故障类别 | 防护触发 | 外部工单数 | 恢复验收 |
| --- | --- | --- | ---: | --- |
| `FI-01` | `model_timeout` | `True` | 0 | `PASS` |
| `FI-02` | `tool_lookup_timeout` | `True` | 0 | `PASS` |
| `FI-03` | `tool_write_timeout` | `True` | 0 | `PASS` |
| `FI-04` | `after_commit_crash` | `True` | 1 | `PASS` |
| `FI-05` | `response_lost` | `True` | 1 | `PASS` |
| `FI-06` | `cancel_after_commit` | `True` | 1 | `PASS` |
| `FI-07` | `rate_limit_429` | `True` | 1 | `PASS` |
| `FI-08` | `policy_config_drift` | `True` | 0 | `PASS` |
| `FI-09` | `trace_field_missing` | `True` | 0 | `PASS` |

## 3. 交付给 Ch39 的发布输入结论

- `baseline-v1` 全部 12 项黄金切片任务、OpenTelemetry 风格轨迹断言（TA-01—TA-05）及 9 类沙箱故障注入均通过，允许进入 Ch39 预发布演练。
- 三类受控变更（`cand-prompt-regression`、`cand-config-drift`、`cand-tool-redundant`）均被回归门禁阻断并精准定位到模型/提示层、配置层或工具/运行时层；其中 `cand-prompt-regression` 在仅看最终答复的评估下呈现 1.0 虚假高分，证明必须启用风险切片与独立数据库/轨迹断言。
