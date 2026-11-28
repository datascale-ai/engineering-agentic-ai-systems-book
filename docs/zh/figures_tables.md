---
title: "图表目录"
owner: "F"
status: zh-draft
version: zh-draft-0.2
updated: 2026-11-27
---

# 图表目录

**List of Figures and Tables**

本目录由学生 F 按全书公共合稿格式（`fig/tab_id | 标题 | 类型 | 数据/来源 | 许可 | 源文件 | 首次引用章`）统一维护，登记当前已完成中文稿章节的图源与核心表格资产。未完成正式稿的篇章待各主责学生提交 G1 稿后持续合入。

---

## 一、全书总览与已完成篇章图目录（Figures）

| `fig_id` | 标题 | 类型 | 数据 / 来源 | 许可 | 可编辑 / 导出源文件路径 | 首次引用章 |
| --- | --- | --- | --- | --- | --- | --- |
| `Fig-00-01` | 全书九篇架构总图 | 架构图 | 本书原创 | MIT | `docs/images/book-structure-zh.png` | [全书导览](index.md) |
| `Fig-01-01` | 智能体与工作流关系图 | 概念图 | 本书原创 | MIT | `docs/images/part1/fig_01_01_system_types-ZH.png` | [Ch01](part1/ch01_agentic_ai_overview.md) |
| `Fig-01-02` | 九篇生命周期能力地图 | 路线图 | 本书原创 | MIT | `docs/images/part1/fig_01_02_book_map-ZH.png` | [Ch01](part1/ch01_agentic_ai_overview.md) |
| `Fig-02-01` | 单轮模型与受控反馈循环对照 | 架构图 | 本书原创 | MIT | `docs/images/part1/fig_02_01_single_turn_vs_loop-ZH.png` | [Ch02](part1/ch02_from_llms_to_agents.md) |
| `Fig-02-02` | 六阶段智能体工程演进路线 | 演进图 | 本书原创 | MIT | `docs/images/part1/fig_02_02_engineering_evolution-ZH.png` | [Ch02](part1/ch02_from_llms_to_agents.md) |
| `Fig-03-01` | 智能体参考架构与信任边界 | 架构图 | 本书原创 | MIT | `docs/images/part1/fig_03_01_reference_architecture-ZH.png` | [Ch03](part1/ch03_agent_architecture.md) |
| `Fig-03-02` | 四种控制结构对照 | 流程图 | 本书原创 | MIT | `docs/images/part1/fig_03_02_control_structures-ZH.png` | [Ch03](part1/ch03_agent_architecture.md) |
| `Fig-04-01` | 五阶段生命周期与退回路径 | 流程图 | 本书原创 | MIT | `docs/images/part1/fig_04_01_lifecycle_gates-ZH.png` | [Ch04](part1/ch04_system_lifecycle_design.md) |
| `Fig-04-02` | 循环控制与预算消耗出口 | 控制图 | 本书原创 | MIT | `docs/images/part1/fig_04_02_loop_budget-ZH.png` | [Ch04](part1/ch04_system_lifecycle_design.md) |
| `Fig-09-02` | 规划、静态检查与执行器接口图 | 架构图 | 本书原创 | MIT | `docs/images/ch09/Fig-09-02.png` | [Ch09](part3/ch09_task_decomposition_planning.md) |
| `Fig-10-02` | 新旧任务图差异与失效依赖 | 差异图 | 本书原创 | MIT | `docs/images/ch10/Fig-10-02.png` | [Ch10](part3/ch10_iterative_reasoning_revision.md) |
| `Fig-18-01` | 多智能体四类组织结构 | 拓扑图 | 本书原创 SVG | MIT | `docs/images/ch18/fig-18-01-organization-topologies.svg` | [Ch18](part5/ch18_multi_agent_roles.md) |
| `Fig-18-02` | 委派链中的责任与预算传递 | 时序图 | 本书原创 SVG | MIT | `docs/images/ch18/fig-18-02-delegation-budget-chain.svg` | [Ch18](part5/ch18_multi_agent_roles.md) |
| `Fig-19-01` | 任务领取、执行与提交时序 | 时序图 | 本书原创 SVG | MIT | `docs/images/ch19/fig-19-01-task-sequence.svg` | [Ch19](part5/ch19_multi_agent_communication.md) |
| `Fig-19-02` | 冲突解决与重新分配状态机 | 状态机 | 本书原创 SVG | MIT | `docs/images/ch19/fig-19-02-reassignment-state-machine.svg` | [Ch19](part5/ch19_multi_agent_communication.md) |
| `Fig-20-01` | 独立生成到证据裁决流程 | 流程图 | 本书原创 SVG | MIT | `docs/images/ch20/fig-20-01-evidence-decision-flow.svg` | [Ch20](part5/ch20_collective_reasoning.md) |
| `Fig-20-02` | 少数意见在聚合中的保留路径 | 流程图 | 本书原创 SVG | MIT | `docs/images/ch20/fig-20-02-minority-retention.svg` | [Ch20](part5/ch20_collective_reasoning.md) |
| `Fig-21-01` | 感知、环境估计、行动与反馈闭环 | 闭环图 | 本书原创 SVG | MIT | `docs/images/ch21/fig-21-01-observe-act-loop.svg` | [Ch21](part5/ch21_perception_environment.md) |
| `Fig-21-02` | 数字、仿真与物理环境适配层 | 架构图 | 本书原创 SVG | MIT | `docs/images/ch21/fig-21-02-environment-adapter-layers.svg` | [Ch21](part5/ch21_perception_environment.md) |
| `Fig-22-01` | 智能体编排运行时组件与故障域划分 | 架构图 | 本书原创 SVG（映射 `async_runtime.py`） | MIT | `docs/images/ch22/fig-22-01-runtime-fault-domains.svg` | [Ch22](part6/ch22_orchestration_runtime.md) |
| `Fig-22-02` | DAG 到有界队列与 Worker 的调度、接管及取消时序 | 时序图 | 本书原创 SVG（`Exp-22-01`） | MIT | `docs/images/ch22/fig-22-02-dag-queue-worker-timeline.svg` | [Ch22](part6/ch22_orchestration_runtime.md) |
| `Fig-23-01` | 显式会话状态机与禁止转换规则 | 状态机 | 本书原创 SVG（`session_state_machine.yaml`） | MIT | `docs/images/ch23/fig-23-01-session-fsm.svg` | [Ch23](part6/ch23_sessions_events_state.md) |
| `Fig-23-02` | 快照加增量事件回放的重连协调时序 | 时序图 | 本书原创 SVG（`session_replay.py`） | MIT | `docs/images/ch23/fig-23-02-snapshot-replay-reconnect.svg` | [Ch23](part6/ch23_sessions_events_state.md) |
| `Fig-24-01` | 模型到界面/播放端的流式流水线、水位线缓冲与带外打断总线 | 架构图 | 本书原创 SVG（指定样章） | MIT | `docs/images/ch24/fig-24-01-streaming-pipeline-buffers.svg` | [Ch24](part6/ch24_streaming_interrupts.md) |
| `Fig-24-02` | 用户打断传播五时间点分解与迟到结果隔离 | 时序图 | 本书原创 SVG（指定样章） | MIT | `docs/images/ch24/fig-24-02-interrupt-propagation-timeline.svg` | [Ch24](part6/ch24_streaming_interrupts.md) |
| `Fig-24-03` | 三组对照下的端到端可见打断延迟分布 | 数据柱状图 | 真实实验日志 `examples/ch24/interrupt_timeline.jsonl` | MIT | `docs/images/ch24/fig-24-03-interrupt-tail-latency.svg` | [Ch24](part6/ch24_streaming_interrupts.md) |
| `Fig-25-01` | 语音、视觉、文件与传感器共享双时钟时间线 | 时序图 | 本书原创 SVG（`media_sync_cases.jsonl`） | MIT | `docs/images/ch25/fig-25-01-multimodal-shared-timeline.svg` | [Ch25](part6/ch25_multimodal_realtime.md) |
| `Fig-25-02` | 多模态轮次状态机（含重叠判定与优雅降级） | 状态机 | 本书原创 SVG（`degradation_matrix.md`） | MIT | `docs/images/ch25/fig-25-02-multimodal-turn-fsm.svg` | [Ch25](part6/ch25_multimodal_realtime.md) |
| `Fig-26-01` | 从目标理解到用户结果的分层评估框架 | 架构图 | 本书原创 | MIT | `docs/images/part7/fig_26_01_evaluation_layers-ZH.png` | [Ch26](part7/ch26_evaluation_methods.md) |
| `Fig-26-02` | 数据集到回归门禁的评测流水线 | 流程图 | 本书原创 | MIT | `docs/images/part7/fig_26_02_evaluation_pipeline-ZH.png` | [Ch26](part7/ch26_evaluation_methods.md) |
| `Fig-27-01` | 端到端调用瀑布图 | 瀑布图 | 本书原创 | MIT | `docs/images/part7/fig_27_01_end_to_end_waterfall-ZH.png` | [Ch27](part7/ch27_benchmarking_capacity.md) |
| `Fig-27-02` | 负载、吞吐、P95 与错误率曲线 | 曲线图 | 本书原创 | MIT | `docs/images/part7/fig_27_02_load_capacity_curve-ZH.png` | [Ch27](part7/ch27_benchmarking_capacity.md) |
| `Fig-36-01` | 共享参考实现的模块依赖与独立测试边界 | 依赖图 | 本书原创 SVG | MIT | `docs/images/ch36/fig-36-01-module-dependencies.svg` | [Ch36](part9/ch36_reference_implementation.md) |
| `Fig-36-02` | 代码、配置、数据与结果的版本谱系 | 谱系图 | 本书原创 SVG | MIT | `docs/images/ch36/fig-36-02-version-lineage.svg` | [Ch36](part9/ch36_reference_implementation.md) |
| `Fig-36-03` | 配置覆盖与基线变更审查流程 | 流程图 | 本书原创 SVG | MIT | `docs/images/ch36/fig-36-03-configuration-review.svg` | [Ch36](part9/ch36_reference_implementation.md) |
| `Fig-37-01` | 智能体测试金字塔与测试责任 | 金字塔图 | 本书原创 SVG | MIT | `docs/images/ch37/fig-37-01-test-responsibilities.svg` | [Ch37](part9/ch37_agent_testing.md) |
| `Fig-37-02` | 模型、工具、时钟与网络的确定性 mock 边界 | 边界图 | 本书原创 SVG | MIT | `docs/images/ch37/fig-37-02-test-double-boundaries.svg` | [Ch37](part9/ch37_agent_testing.md) |
| `Fig-37-03` | 端到端场景的事件断言链 | 断言图 | 本书原创 SVG | MIT | `docs/images/ch37/fig-37-03-event-assertion-chain.svg` | [Ch37](part9/ch37_agent_testing.md) |
| `Fig-38-01` | 评估回归、故障注入与可观测断言到发布门禁的流水线 | 流程图 | 本书原创 SVG（`regression_runner/`） | MIT | `docs/images/ch38/fig-38-01-regression-to-gate-pipeline.svg` | [Ch38](part9/ch38_regression_fault_injection.md) |
| `Fig-38-02` | 基线与候选运行的轨迹差异视图 | 差异图 | 沙箱回归日志 `ch38_regression_results.json` | MIT | `docs/images/ch38/fig-38-02-trajectory-diff-view.svg` | [Ch38](part9/ch38_regression_fault_injection.md) |
| `Fig-38-03` | OpenTelemetry GenAI 轨迹断言（TA-01—TA-05）在事件链中的位置 | 断言图 | 本书原创 SVG（`trace_assertions.yaml`） | MIT | `docs/images/ch38/fig-38-03-trace-assertions-event-chain.svg` | [Ch38](part9/ch38_regression_fault_injection.md) |
| `Fig-39-01` | 从提交到预发布的持续交付流水线与发布门禁（S1—S7） | 流水线图 | 本书原创 SVG（`cd_pipeline.yaml`） | MIT | `docs/images/ch39/fig-39-01-cd-pipeline-gates.svg` | [Ch39](part9/ch39_deployment_continuous_delivery.md) |
| `Fig-39-02` | Local、Test 与 Staging 三档部署拓扑及身份/数据/网络边界 | 拓扑图 | 本书原创 SVG（`profiles.yaml`） | MIT | `docs/images/ch39/fig-39-02-deployment-topology-boundaries.svg` | [Ch39](part9/ch39_deployment_continuous_delivery.md) |
| `Fig-39-03` | 故障注入、不完全回滚反例与五要素回滚恢复验收时间线 | 数据时间线 | 真实演练日志 `examples/ch39/results/ch39_drill_results.json` | MIT | `docs/images/ch39/fig-39-03-fault-to-recovery-timeline.svg` | [Ch39](part9/ch39_deployment_continuous_delivery.md) |

---

## 二、第六篇与第九篇（F 主责章节）核心表目录（Tables）

| `tab_id` | 标题 | 类型 | 数据 / 来源 | 许可 | 对应源文件 / 报告 | 首次引用章 |
| --- | --- | --- | --- | --- | --- | --- |
| `Tab-22-01` | 运行时五维资源控制项与过载处置契约 | 契约表 | `examples/ch22/runtime_config.yaml` | MIT | `docs/zh/part6/ch22_orchestration_runtime.md` | [Ch22](part6/ch22_orchestration_runtime.md) |
| `Tab-22-02` | Worker 生命周期、租约超时与崩溃接管规则 | 规则表 | `examples/ch22/async_runtime.py` | MIT | `docs/zh/part6/ch22_orchestration_runtime.md` | [Ch22](part6/ch22_orchestration_runtime.md) |
| `Tab-22-03` | `Exp-22-01` 三种调度模式在 50 任务双租户负载下的模拟实验对照 | 实验表 | `examples/ch22/results/runtime_metrics.json` | MIT | `examples/ch22/runtime_load_report.md` | [Ch22](part6/ch22_orchestration_runtime.md) |
| `Tab-23-01` | Ch23 公共事件字段规范（`event-v2`） | 契约表 | `examples/ch23/event_schema.json` | MIT | `docs/zh/part6/ch23_sessions_events_state.md` | [Ch23](part6/ch23_sessions_events_state.md) |
| `Tab-23-02` | 重连与投递异常协调判定矩阵 | 决策表 | `examples/ch23/session_replay.py` | MIT | `docs/zh/part6/ch23_sessions_events_state.md` | [Ch23](part6/ch23_sessions_events_state.md) |
| `Tab-23-03` | `Exp-23-01` 20 种中断、重连与投递变体沙箱重放汇总 | 实验表 | `examples/ch23/results/replay_report.json` | MIT | `docs/zh/part6/ch23_sessions_events_state.md` | [Ch23](part6/ch23_sessions_events_state.md) |
| `Tab-24-01` | 流式流水线各层缓冲治理契约 | 治理表 | `examples/ch24/stream_interrupt_demo.py` | MIT | `docs/zh/part6/ch24_streaming_interrupts.md` | [Ch24](part6/ch24_streaming_interrupts.md) |
| `Tab-24-02` | 流式打断高频竞态矩阵与确定性处置规则 | 竞态表 | `examples/ch24/stream_interrupt_demo.py` | MIT | `docs/zh/part6/ch24_streaming_interrupts.md` | [Ch24](part6/ch24_streaming_interrupts.md) |
| `Tab-24-03` | 样章验收对照表（40 个确定性时序用例离散事件模拟） | 验收表 | `examples/ch24/results/ch24_summary.json` | MIT | `examples/ch24/interrupt_timeline.jsonl` | [Ch24](part6/ch24_streaming_interrupts.md) |
| `Tab-24-04` | 真实异步流式墙钟实测汇总（本地回环 SSE 与在线 `gpt-6.2-astra`） | 实测表 | `examples/ch24/results/realtime_sse_wallclock.json` / `live_llm_sse_wallclock.json` | MIT | `examples/ch24/live_api_sse_benchmark.py` | [Ch24](part6/ch24_streaming_interrupts.md) |
| `Tab-25-01` | 多模态事件公共模式核心字段（`mm-event-v1`） | 契约表 | `examples/ch25/multimodal_event_schema.json` | MIT | `docs/zh/part6/ch25_multimodal_realtime.md` | [Ch25](part6/ch25_multimodal_realtime.md) |
| `Tab-25-02` | 多模态失模态优雅降级与恢复矩阵 | 降级表 | `examples/ch25/degradation_matrix.md` | MIT | `docs/zh/part6/ch25_multimodal_realtime.md` | [Ch25](part6/ch25_multimodal_realtime.md) |
| `Tab-25-03` | `Exp-25-01` 20 项多模态同步与错位交互离散事件模拟对照 | 实验表 | `examples/ch25/results/ch25_report.json` | MIT | `examples/ch25/media_sync_cases.jsonl` | [Ch25](part6/ch25_multimodal_realtime.md) |
| `Tab-38-01` | 九类沙箱故障注入矩阵与沙箱恢复验收 | 故障表 | `examples/ch38/fault_injection_matrix.yaml` | MIT | `examples/ch38/regression_report.md` | [Ch38](part9/ch38_regression_fault_injection.md) |
| `Tab-38-02` | 基线与三类受控变更候选的沙箱质量门禁报告 | 回归表 | `examples/ch38/results/ch38_regression_results.json` | MIT | `examples/ch38/regression_report.md` | [Ch38](part9/ch38_regression_fault_injection.md) |
| `Tab-39-01` | 发布就绪检查表（含 `release-v1.0.0` 已填写样例） | 检查表 | `examples/ch39/release_checklist.md` | MIT | `docs/zh/part9/ch39_deployment_continuous_delivery.md` | [Ch39](part9/ch39_deployment_continuous_delivery.md) |
| `Tab-39-02` | 智能体五要素回滚序列与恢复验收判据 | 手册表 | `examples/ch39/rollback_runbook.md` | MIT | `docs/zh/part9/ch39_deployment_continuous_delivery.md` | [Ch39](part9/ch39_deployment_continuous_delivery.md) |
| `Tab-39-03` | `Exp-39-01` 四项预发布与回滚沙箱演练结果 | 演练表 | `examples/ch39/results/ch39_drill_results.json` | MIT | `examples/ch39/release_report.md` | [Ch39](part9/ch39_deployment_continuous_delivery.md) |

> **说明**：其余章节（Ch05—Ch08、Ch11—Ch17、Ch28—Ch35）的图表条目将在各章进入 G1 正式中文稿后按同一字段格式汇总入本表。
