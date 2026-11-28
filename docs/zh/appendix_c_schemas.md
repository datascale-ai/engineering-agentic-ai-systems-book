---
title: "附录C：接口、模式与事件轨迹"
owner: "F"
status: zh-draft
version: zh-draft-0.2
updated: 2026-11-27
---

# 附录C：接口、模式与事件轨迹

**Interfaces, Schemas, and Event Traces**

**摘要**　本附录集中维护全书各篇共享的核心接口登记表、JSON Schema / YAML 模式版本、事件轨迹字段与完整填写样例，确保正文章节与代码仓库中的权威模式保持同一版本而不失同步。附录覆盖 [Ch03](part1/ch03_agent_architecture.md) 六类基础对象、[Ch09](part3/ch09_task_decomposition_planning.md) 计划图、[Ch19](part5/ch19_multi_agent_communication.md) 多智能体协调消息、[Ch22](part6/ch22_orchestration_runtime.md) 运行时配置、[Ch23](part6/ch23_sessions_events_state.md) 会话状态机与事件模式（`event-v2`）、[Ch24](part6/ch24_streaming_interrupts.md) 流式打断时间线、[Ch25](part6/ch25_multimodal_realtime.md) 五模态事件模式（`mm-event-v1`）以及 [Ch38](part9/ch38_regression_fault_injection.md)—[Ch39](part9/ch39_deployment_continuous_delivery.md) 的 OpenTelemetry GenAI 风格轨迹断言与发布清单。每项接口均给出可验证的仓库源路径、完整样例及跨章回链。

**关键词**　公共接口（shared interfaces）；JSON Schema；事件轨迹（event trace）；模式版本与迁移（schema versioning and upcasting）；会话状态机（session state machine）；流式打断（streaming interruption）；多模态事件（multimodal event）；OpenTelemetry GenAI。

**维护信息**　主责学生：F；供稿与协同：A 核对象语义、C 供计划/工具模式、D 供状态/知识卡片、E 供多智能体与参考实现契约。预期篇幅约 8 个等效出版页；全部模式文件采用仓库 MIT 许可。本附录不承担正文尚未解释的方法论述，仅作权威契约索引与完整样例对照。

---

## C.1 全书公共接口总登记表

下表严格遵循全书公共合稿字段协议（`schema_id | 字段/事件 | 生产章 | 消费章 | 版本 | 兼容性说明 | 验证命令 | 维护人`），正文章节仅引用 `schema_id` 与对应仓库路径，避免多处手工复制导致字段漂移。

| `schema_id` | 核心字段 / 事件摘要 | 生产章 | 消费章 | 版本 | 兼容性说明 | 验证命令 | 维护人 |
| --- | --- | --- | --- | --- | --- | --- | :---: |
| `SCH-CORE-01` | `Goal` / `AgentState` / `ModelRequest` / `ToolCall` / `ToolResult` / `Event` | [Ch03](part1/ch03_agent_architecture.md) | 全书各章 | `demo-1` / `core-0.2` | 核心必填字段变更须升主版本；允许新增非破坏扩展字段 | `python -m pytest examples/ch37/tests/test_behaviour.py -q` | A / F |
| `SCH-PLAN-01` | `plan_id`、`subtasks`、`depends_on`、`preconditions`、`budget`、`acceptance` | [Ch09](part3/ch09_task_decomposition_planning.md) | Ch10 / Ch11 / Ch22 | `plan-1.0` | 依赖 DAG 必须无环；工具名需存在于 Ch11 注册目录 | `python -m pytest tests/ch09/test_planning.py -q` | C |
| `SCH-COORD-01` | `task_id`、`message_id`、`task_revision`、`assignment_epoch`、`lease_id`、`payload_digest` | [Ch19](part5/ch19_multi_agent_communication.md) | Ch20 / Ch22 / Ch36 | `coordination-draft-0.1` | 同一 `message_id` 载荷不得篡改；旧代次提交一律拒绝 | `python -m pytest examples/ch37/tests/test_student_e_studies.py -q` | E |
| `SCH-RT-22` | `global_max_workers`、`global_queue_capacity`、`tenants`、`lease_ttl_ms`、`control_plane_priority_lane` | [Ch22](part6/ch22_orchestration_runtime.md) | Ch27 / Ch30 / Ch36 | `runtime-config-1.0` | 所有队列必须显式声明容量与溢出策略；插件注册须可逆清理 | `python examples/ch22/async_runtime.py` | F |
| `SCH-EVT-23` | `session_id`、`turn_id`、`event_id`、`sequence`、`schema_version`、`command_id`、`occurred_at_ms`、`payload` | [Ch23](part6/ch23_sessions_events_state.md) | Ch19 / Ch22 / Ch24 / Ch36 / Ch38 | `event-v2`（兼容 `event-v1`） | 历史 `event-v1` 经读时 `upcast_event` 无损升为 `event-v2`；原始日志不可变 | `python examples/ch23/session_replay.py` | F |
| `SCH-FSM-23` | `created`/`running`/`paused`/`completed`/`cancelled`/`failed` 及禁止迁移表 | [Ch23](part6/ch23_sessions_events_state.md) | Ch22 / Ch24 / Ch36 | `session-fsm-1.0` | 终态不可逆；禁止跳过执行直接 `completed` | `python -m pytest tests/ch22_25/test_part6_runtime.py -q` | F |
| `SCH-STR-24` | `turn_id`、`generation_id`、`channel`、`t0..t4`、`late_tool_leaked`、`tool_already_committed` | [Ch24](part6/ch24_streaming_interrupts.md) | Ch25 / Ch27 / Ch34 | `stream-interrupt-1.0` | `generation_id` 单调递增；旧代次回调零混入；已提交副作用如实保留 | `python examples/ch24/stream_interrupt_demo.py` | F |
| `SCH-MM-25` | `modality`（5 类）、`event_time_ms`、`receive_time_ms`、`chunk_id`、`revision`、`ref_target_id`、`state_version` | [Ch25](part6/ch25_multimodal_realtime.md) | Ch27 / Ch29 / Ch35 | `mm-event-v1` | 对齐与指代消解仅认 `event_time_ms`；同 `chunk_id` 高 `revision` 覆盖低版本 | `python examples/ch25/multimodal_coordinator.py` | F |
| `SCH-TRACE-38` | `gen_ai.operation.name`、`agent.tenant`、`agent.policy_version`、`TA-01`—`TA-05` 稳定/波动字段划分 | [Ch38](part9/ch38_regression_fault_injection.md) | Ch30 / Ch39 | `trace-assertions-1.0` | 与 OpenTelemetry GenAI 语义规范对齐；严禁日志/span 含明文密钥 | `python examples/ch38/regression_runner/runner.py` | F |
| `SCH-CD-39` | `profiles`（local/test/staging）、`S1`—`S7` 门禁、五要素回滚序列与审计时间线 | [Ch39](part9/ch39_deployment_continuous_delivery.md) | 附录 D / Ch30 | `cd-pipeline-1.0` | 与附录 D 档位语义一致；回滚必须覆盖代码、配置、数据、权限与缓存 | `python examples/ch39/drill_runner.py` | F / E |

---

## C.2 会话事件与状态机规范及完整填写样例（`SCH-EVT-23` / `SCH-FSM-23`）

权威 JSON Schema 源文件位于 `examples/ch23/event_schema.json`（Draft 2020-12），状态机定义位于 `examples/ch23/session_state_machine.yaml`。下面给出一组完整填写的跨版本重连事件轨迹样例（展示 `event-v1` 历史事件升级与 `event-v2` 新事件同流回放）：

```json
[
  {
    "schema_version": "event-v1",
    "session_id": "S23-03-schema-upgrade-V23-12",
    "turn_id": "t1",
    "event_id": "S23-03-schema-upgrade-V23-12:ev:3",
    "sequence": 3,
    "event_type": "tool_effect_committed",
    "occurred_at_ms": 300,
    "producer": "session-authority",
    "payload": {
      "operation_id": "op-s3-1",
      "tool": "create_ticket",
      "payload_digest": "sha256:ccc3",
      "ticket_ref": "TK-1001"
    }
  },
  {
    "schema_version": "event-v2",
    "session_id": "S23-03-schema-upgrade-V23-12",
    "turn_id": "t1",
    "event_id": "S23-03-schema-upgrade-V23-12:ev:5",
    "sequence": 5,
    "event_type": "session_completed",
    "occurred_at_ms": 500,
    "producer": "session-authority",
    "command_id": "cmd-5",
    "correlation_id": "S23-03-schema-upgrade-V23-12",
    "causation_id": "S23-03-schema-upgrade-V23-12:ev:4",
    "payload": {
      "verified": true
    }
  }
]
```

**版本迁移核验规则**：读取 `sequence=3` 时，`upcast_event()` 将 `payload.ticket_ref` 无损映射为 `payload.ticket_id` 并补齐 `command_id: null`、`correlation_id` 与 `causation_id`，原始持久化日志保持逐字节不变；回放至 `sequence=5` 时，状态机校验 `running → completed` 合法迁移且绝不重新调用外部工单创建接口。详见 [Ch23 第 23.3 节](part6/ch23_sessions_events_state.md)。

---

## C.3 流式打断五时间点记录样例（`SCH-STR-24`）

权威生成器与完整 120 条实测记录位于 `examples/ch24/stream_interrupt_demo.py` 与 `examples/ch24/interrupt_timeline.jsonl`。以下为“工具已提交后用户打断 + 迟到回调拦截”用例（`C24-31`）在完整机制（`cancel_plus_gen_and_flush`）下的真实填写样例：

```json
{
  "case_id": "C24-31",
  "scenario": "cancel_after_tool_commit",
  "strategy": "cancel_plus_gen_and_flush",
  "turn_id": "turn-31",
  "generation_id": 4,
  "t0_user_stop_ms": 238.0,
  "t1_stop_perceived_ms": 244.0,
  "t2_cancel_propagated_ms": 248.0,
  "t3_producer_stopped_ms": 254.0,
  "t4_last_stale_rendered_ms": 254.0,
  "propagation_latency_ms": 10.0,
  "producer_stop_latency_ms": 16.0,
  "visible_stop_latency_ms": 16.0,
  "backpressure_active": false,
  "already_played_before_t0_chunks": 9,
  "stale_chunks_rendered": 1,
  "stale_chunks_dropped": 6,
  "late_tool_leaked": false,
  "tool_already_committed": true,
  "resources_released": true,
  "valid_output_lost": 0,
  "expected_outcome": "zero_next_turn_leak_and_stop_within_60ms",
  "passed": true,
  "failure_reasons": []
}
```

该样例同时示范了 [Ch24](part6/ch24_streaming_interrupts.md) 的三条核心验收口径：以 $t_0$ 为起点测得可见停止延迟 16.0 ms（<= 60 ms）；迟到工具回调被 `generation_id=4` 围栏拦截（`late_tool_leaked=false`）；同时诚实保留 `tool_already_committed=true`，不宣称流取消撤销了远端提交。

---

## C.4 多模态双时钟事件完整样例（`SCH-MM-25`）

权威 JSON Schema 位于 `examples/ch25/multimodal_event_schema.json`，完整 20 项合成片段位于 `examples/ch25/media_sync_cases.jsonl`。以下为覆盖视觉延迟帧与语音指代消解的完整填写样例：

```json
{
  "schema_version": "mm-event-v1",
  "session_id": "S25-receipt-check-01",
  "event_id": "v2",
  "modality": "vision",
  "source_id": "cam-mobile-0",
  "event_time_ms": 1380,
  "receive_time_ms": 1510,
  "turn_id": "t2",
  "generation_id": 2,
  "chunk_id": "frame-v2",
  "revision": 2,
  "is_final": true,
  "state_version": 4,
  "ref_target_id": "item-new-right",
  "privacy_class": "confidential",
  "payload": {
    "frame_id": "frame-v2",
    "extracted_amount": 480,
    "capture_notice": "synthetic_teaching_fixture"
  }
}
```

尽管该视觉帧在网络层 `receive_time_ms = 1510` 晚于语音到达（`1440`），但其物理采集时刻 `event_time_ms = 1380` 与语音 `event_time_ms = 1400` 同属 `turn_id = t2`，协调器据此准确绑定 `item-new-right` 而非旧画面。详见 [Ch25 第 25.2 节](part6/ch25_multimodal_realtime.md)。

---

## C.5 OpenTelemetry GenAI 风格轨迹与发布审计样例（`SCH-TRACE-38` / `SCH-CD-39`）

权威断言规则位于 `examples/ch38/trace_assertions.yaml`，持续交付与五要素回滚配置位于 `examples/ch39/ci/cd_pipeline.yaml` 与 `examples/ch39/deploy/profiles.yaml`。以下为一次通过 `TA-01`—`TA-05` 全部断言的标准轨迹片段（稳定字段与允许波动字段严格分离）：

```json
{
  "trace_id": "tr-G38-02",
  "spans": [
    {
      "name": "invoke_agent",
      "op": "invoke_agent",
      "attributes": {
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.request.model": "mock:baseline",
        "agent.tenant": "tenant-alpha",
        "agent.task_id": "G38-02",
        "agent.policy_version": "P20-A@2.0",
        "agent.status": "completed",
        "agent.reason": null,
        "agent.ticket_count": 1
      }
    },
    {
      "name": "policy_evaluate",
      "op": "policy_evaluate",
      "attributes": { "agent.policy_version": "P20-A@2.0" }
    },
    {
      "name": "execute_tool create_ticket",
      "op": "execute_tool",
      "attributes": { "gen_ai.tool.name": "create_ticket", "agent.operation_id": "G38-02:1:create" }
    },
    {
      "name": "verify_postcondition",
      "op": "verify_postcondition",
      "attributes": { "agent.ticket_count": 1 }
    }
  ]
}
```

---

## C.6 公共模式变更与同步协议

1. **单一真相源（Single Source of Truth）**：所有 JSON Schema 与 YAML 契约均以仓库 `examples/` 下对应文件为唯一机器校验真相源；本附录仅同步摘录关键字段与填写样例，严禁手工派生互不兼容的第二份定义。
2. **破坏性变更流程**：任何字段删除、枚举收缩或语义变更，必须由维护人提出变更说明、同步升级 `schema_version`、补齐读时 `upcaster` 或兼容策略，并经由全部消费章负责人确认及重跑 `pytest` 全部契约测试后方可合入。
3. **跨章回链检查**：本附录接口已分别回链至 [Ch03](part1/ch03_agent_architecture.md)、[Ch09](part3/ch09_task_decomposition_planning.md)、[Ch19](part5/ch19_multi_agent_communication.md)、[Ch22—Ch25](part6/index.md)、[Ch36—Ch39](part9/index.md) 及 [附录 D](appendix_d_deployment.md)。
