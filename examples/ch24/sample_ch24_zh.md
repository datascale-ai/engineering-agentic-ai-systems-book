# Ch24 样章运行说明与验收索引 (`sample_ch24_zh.md`)

本文件为 Springer 提案指定样章 [Ch24 流式流水线、流量控制与用户打断](../../docs/zh/part6/ch24_streaming_interrupts.md) 的配套运行入口说明。

## 1. 可复现命令

从仓库根目录运行：

```powershell
python examples/ch24/stream_interrupt_demo.py
python -m pytest tests/ch22_25/test_part6_runtime.py -q
```

## 2. 产出文件清单

- `examples/ch24/stream_interrupt_demo.py`：40 个确定性取消时序用例与三组对照（`ui_only_stop`、`cancel_propagation_only`、`cancel_plus_gen_and_flush`）的实现与评测脚本。
- `examples/ch24/interrupt_timeline.jsonl`：全部 120 条（40 用例 × 3 对照）含五时间点（`t0`—`t4`）、旧片段统计、迟到回调泄露标记与验收判定原因的原始事件日志。
- `examples/ch24/results/ch24_summary.json`：三组对照的 P50/P95/P99/Max 打断延迟、旧输出残留、资源释放率与通过数汇总。
- `docs/images/ch24/fig-24-03-interrupt-tail-latency.svg`：由 `interrupt_timeline.jsonl` 真实实验日志直接生成的打断尾延迟分布图。

## 3. 样章独立验收边界

1. **可见停止（Visible Stop）**：以用户动作 `t0_user_stop_ms` 为起点、最后一条旧片段渲染 `t4_last_stale_rendered_ms` 为终点测量，不以取消函数返回时间替代。
2. **生产停止（Producer Stop）**：独立统计上游生产者退出时刻 `t3_producer_stopped_ms` 与句柄释放状态。
3. **旧内容清理（Stale Cleanup）**：验证旧 `generation_id` 的迟到工具回调与缓冲音频块不得混入新轮次。
4. **不可逆边界**：已播放至声卡 DMA 的片段以及 `tool_already_committed=true` 的远端副作用明确声明无法通过流取消撤回，必须交由 Ch12/Ch13 补偿或核对流程处置。
