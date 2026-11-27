"""Automated deterministic tests for Part VI (Ch22-Ch25) runtimes, schemas, and figures."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
for sub in ("examples/ch22", "examples/ch23", "examples/ch24", "examples/ch25"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import async_runtime as ch22  # noqa: E402
import session_replay as ch23  # noqa: E402
import stream_interrupt_demo as ch24  # noqa: E402
import multimodal_coordinator as ch25  # noqa: E402


def test_ch22_plugin_context_reversible_cleanup():
    ctx = ch22.PluginContext()
    disposed = []
    ctx.provide("plug.mock", "tool_executor", object(), on_dispose=lambda: disposed.append("cleaned"))
    assert ctx.require("tool_executor") is not None
    ctx.unload("plug.mock")
    assert disposed == ["cleaned"]
    try:
        ctx.require("tool_executor")
        assert False, "expected KeyError after unload"
    except KeyError:
        pass


def test_ch22_bounded_runtime_enforces_caps_and_releases_resources(tmp_path):
    cfg = yaml.safe_load((ROOT / "examples/ch22/runtime_config.yaml").read_text(encoding="utf-8"))
    assert cfg["scheduler"]["global_max_workers"] == 6
    assert cfg["scheduler"]["control_plane_priority_lane"] is True

    # Run bounded & unbounded on a fast time scale
    workload = ch22.build_workload_50()
    assert len(workload) == 50
    adapter = ch22.DeterministicToolAdapter(time_scale=0.0002)
    rt = ch22.AsyncAgentRuntime(
        ch22.RuntimeConfig(
            mode="bounded_concurrency",
            global_max_workers=6,
            global_queue_capacity=40,
            tenant_max_in_flight=3,
            tenant_max_queue_depth=18,
            control_plane_priority_lane=True,
            time_scale=0.0002,
        ),
        adapter,
    )
    res = asyncio.run(rt.run_workload(workload))
    assert res["peak_in_flight"] <= 6
    assert res["peak_queued"] <= 40
    assert adapter.active_handles == 0
    assert res["total_reclaims"] >= 1


def test_ch23_session_fsm_and_20_reconnect_variants(tmp_path):
    fsm = yaml.safe_load((ROOT / "examples/ch23/session_state_machine.yaml").read_text(encoding="utf-8"))
    assert len(fsm["states"]) == 6
    schema = json.loads((ROOT / "examples/ch23/event_schema.json").read_text(encoding="utf-8"))
    for req in ("session_id", "turn_id", "event_id", "sequence", "schema_version"):
        assert req in schema["required"]

    summary = ch23.run_20_variants_experiment(tmp_path)
    assert summary["total_variants"] == 20
    assert summary["events_plus_snapshots"]["terminal_consistent_count"] == 20
    assert summary["events_plus_snapshots"]["duplicate_side_effects"] == 0
    assert summary["chat_text_only_baseline"]["duplicate_side_effects"] > 0
    # Verify forbidden transition was explicitly blocked in V23-15
    v15 = next(v for v in summary["variants"] if v["variant_id"] == "V23-15")
    assert v15["forbidden_transition_blocked"] is True


def test_ch24_40_interruption_cases_zero_leak_and_latency_bound(tmp_path):
    summary = ch24.run_experiment(tmp_path)
    assert summary["total_cases_per_strategy"] == 40
    full = summary["strategies"]["cancel_plus_gen_and_flush"]
    ui = summary["strategies"]["ui_only_stop"]
    prop = summary["strategies"]["cancel_propagation_only"]

    assert full["passed_cases"] == 40
    assert full["late_tool_leaks"] == 0
    assert full["visible_stop_p95_ms"] <= 60.0
    assert full["committed_effects_preserved"] == 5
    assert ui["late_tool_leaks"] == 14
    assert prop["late_tool_leaks"] == 14
    assert full["visible_stop_p95_ms"] < prop["visible_stop_p95_ms"] < ui["visible_stop_p95_ms"]


def test_ch25_multimodal_dual_clock_and_degradation(tmp_path):
    schema = json.loads((ROOT / "examples/ch25/multimodal_event_schema.json").read_text(encoding="utf-8"))
    assert set(schema["properties"]["modality"]["enum"]) == {"text", "audio", "vision", "file", "sensor"}
    assert "event_time_ms" in schema["required"] and "receive_time_ms" in schema["required"]

    summary = ch25.run_experiment(tmp_path)
    assert summary["total_cases"] == 20
    fusion = summary["strategies"]["turn_ref_time_fusion"]
    naive = summary["strategies"]["arrival_order_fusion"]

    assert fusion["object_binding_correct"] == 20
    assert fusion["turn_misjudgment_count"] == 0
    assert fusion["degradation_success_count"] == fusion["degradation_required_total"] == 5
    assert naive["object_binding_correct"] < fusion["object_binding_correct"]
    assert fusion["mean_sync_error_ms"] < naive["mean_sync_error_ms"]


def test_part6_all_svg_figures_exist_and_referenced():
    expected_svgs = [
        "docs/images/ch22/fig-22-01-runtime-fault-domains.svg",
        "docs/images/ch22/fig-22-02-dag-queue-worker-timeline.svg",
        "docs/images/ch23/fig-23-01-session-fsm.svg",
        "docs/images/ch23/fig-23-02-snapshot-replay-reconnect.svg",
        "docs/images/ch24/fig-24-01-streaming-pipeline-buffers.svg",
        "docs/images/ch24/fig-24-02-interrupt-propagation-timeline.svg",
        "docs/images/ch24/fig-24-03-interrupt-tail-latency.svg",
        "docs/images/ch25/fig-25-01-multimodal-shared-timeline.svg",
        "docs/images/ch25/fig-25-02-multimodal-turn-fsm.svg",
    ]
    for rel in expected_svgs:
        p = ROOT / rel
        assert p.exists() and p.stat().st_size > 1000, f"missing or tiny SVG: {rel}"
