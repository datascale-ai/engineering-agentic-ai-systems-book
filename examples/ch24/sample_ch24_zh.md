# Ch24 样章运行说明与验收索引 (`sample_ch24_zh.md`)

本文件为 Springer 提案指定样章 [Ch24 流式流水线、流量控制与用户打断](../../docs/zh/part6/ch24_streaming_interrupts.md) 的配套运行入口说明。

## 1. 可复现命令

从仓库根目录运行：

```powershell
# 1. 离线必跑：40 项确定性离散事件模拟（Exp-24-01）与本地回环 HTTP SSE 墙钟实测（Exp-24-02）
python examples/ch24/stream_interrupt_demo.py
python examples/ch24/realtime_sse_benchmark.py
python -m pytest tests/ch22_25/test_part6_runtime.py -q

# 2. 可选在线实测：连接真实 OpenAI 兼容 HTTPS SSE 端点（Exp-24-03，需自行配置环境变量）
# $env:OPENAI_API_KEY="..."; $env:OPENAI_BASE_URL="https://.../v1"; $env:OPENAI_MODEL="gpt-6.2-astra"
# python examples/ch24/live_api_sse_benchmark.py
```

## 2. 产出文件清单

- `examples/ch24/stream_interrupt_demo.py`：`Exp-24-01`，40 个确定性取消时序用例与三组对照（`ui_only_stop`、`cancel_propagation_only`、`cancel_plus_gen_and_flush`）的离散事件模拟脚本。
- `examples/ch24/interrupt_timeline.jsonl` & `results/ch24_summary.json`：`Exp-24-01` 全部 120 条（40 用例 × 3 对照）离散事件原始日志与分位数汇总。
- `examples/ch24/realtime_sse_benchmark.py` & `results/realtime_sse_wallclock.json`：`Exp-24-02`，本机 `127.0.0.1` 真实 HTTP/1.1 SSE + `asyncio.Queue` 墙钟实测（36 次，零密钥离线可复现）。
- `examples/ch24/live_api_sse_benchmark.py` & `results/live_llm_sse_wallclock.json`：`Exp-24-03`，真实在线大模型（`gpt-6.2-astra`）HTTPS/TLS SSE 墙钟实测脚本与脱敏汇总（不含任何密钥或私有主机地址；CI 默认跳过）。
- `docs/images/ch24/fig-24-03-interrupt-tail-latency.svg`：由 `interrupt_timeline.jsonl` 离散事件模拟日志直接生成的打断尾延迟分布图。

## 3. 样章独立验收边界

1. **可见停止（Visible Stop）**：以用户动作 `t0_user_stop_ms` 为起点、最后一条旧片段渲染 `t4_last_stale_rendered_ms` 为终点测量，不以取消函数返回时间替代。
2. **生产停止（Producer Stop）**：独立统计上游生产者退出时刻 `t3_producer_stopped_ms` 与句柄释放状态。
3. **旧内容清理（Stale Cleanup）**：验证旧 `generation_id` 的迟到工具回调与缓冲音频块不得混入新轮次。
4. **不可逆边界**：已播放至声卡 DMA 的片段以及 `tool_already_committed=true` 的远端副作用明确声明无法通过流取消撤回，必须交由 Ch12/Ch13 补偿或核对流程处置。
