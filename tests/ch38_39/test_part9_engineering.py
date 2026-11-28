"""Automated deterministic tests for Part IX (Ch38-Ch39), Appendix C, and Figures index."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
for sub in ("examples/ch36/src", "examples/ch38", "examples/ch39"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from regression_runner import runner as ch38  # noqa: E402
import drill_runner as ch39  # noqa: E402


def test_ch38_regression_gates_and_9_fault_injections(tmp_path):
    # Copy YAML configs into tmp_path so test never mutates repo artifacts
    for fname in ("golden_slices.yaml", "fault_injection_matrix.yaml", "trace_assertions.yaml"):
        src = ROOT / "examples/ch38" / fname
        (tmp_path / fname).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    res = ch38.run_all(tmp_path)
    cands = res["candidates"]
    assert cands["baseline-v1"]["gate_passed"] is True
    assert cands["cand-prompt-regression"]["gate_passed"] is False
    assert "model_or_prompt_layer" in cands["cand-prompt-regression"]["detected_fault_layers"]
    assert cands["cand-config-drift"]["gate_passed"] is False
    assert "config_layer" in cands["cand-config-drift"]["detected_fault_layers"]
    assert cands["cand-tool-redundant"]["gate_passed"] is False
    assert "tool_or_runtime_layer" in cands["cand-tool-redundant"]["detected_fault_layers"]

    # Naive final-answer-only check fails to catch prompt regression on high-risk slice
    hi_slice = cands["cand-prompt-regression"]["slices"]["high_risk_approval_required"]
    assert hi_slice["pass_rate"] == 0.0
    assert hi_slice["unauthorized_writes"] == 3
    assert hi_slice["naive_answer_only_pass_rate"] == 1.0

    # All 9 fault injections must recover cleanly
    assert len(res["fault_injections"]) == 9
    assert all(f["recovered"] for f in res["fault_injections"])


def test_ch39_four_staging_drills_and_five_element_rollback(tmp_path):
    profiles = yaml.safe_load((ROOT / "examples/ch39/deploy/profiles.yaml").read_text(encoding="utf-8"))
    assert set(profiles["profiles"]) == {"local", "test", "staging"}
    pipeline = yaml.safe_load((ROOT / "examples/ch39/ci/cd_pipeline.yaml").read_text(encoding="utf-8"))
    assert len(pipeline["stages"]) == 7

    res = ch39.run_drills(tmp_path)
    assert res["all_drills_passed"] is True
    d2 = res["drills"]["DRILL-02_fault_and_incomplete_rollback_contrast"]
    assert d2["full_cd_gate_blocked"] is True
    assert d2["incomplete_rollback_exposed_stale_cache_bug"] is True
    assert d2["secret_leaked_in_audit_log"] is False
    d3 = res["drills"]["DRILL-03_full_five_element_rollback"]
    assert d3["cleared_cache_entries"] == 1
    assert d3["post_rollback_highrisk_probe"]["status"] == "rejected"
    assert d3["legitimate_ticket_preserved"] is True


def test_part9_figures_and_f_markdown_links_resolve():
    f_docs = [
        ROOT / "docs/zh/part6/index.md",
        ROOT / "docs/zh/part6/ch22_orchestration_runtime.md",
        ROOT / "docs/zh/part6/ch23_sessions_events_state.md",
        ROOT / "docs/zh/part6/ch24_streaming_interrupts.md",
        ROOT / "docs/zh/part6/ch25_multimodal_realtime.md",
        ROOT / "docs/zh/part9/index.md",
        ROOT / "docs/zh/part9/ch38_regression_fault_injection.md",
        ROOT / "docs/zh/part9/ch39_deployment_continuous_delivery.md",
        ROOT / "docs/zh/appendix_c_schemas.md",
        ROOT / "docs/zh/figures_tables.md",
    ]
    link_re = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    for doc in f_docs:
        text = doc.read_text(encoding="utf-8")
        assert "写作占位页" not in text
        assert "占位页，等待正式材料" not in text
        for target in link_re.findall(text):
            if target.startswith(("http://", "https://", "#")):
                continue
            resolved = (doc.parent / target.split("#")[0]).resolve()
            assert resolved.exists(), f"Broken relative link in {doc.name}: {target} -> {resolved}"
