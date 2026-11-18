"""Behavioral checks for Ch14; all identities are server-side fixtures."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sys
from threading import Barrier

import pytest

MODULE = Path(__file__).resolve().parents[1] / "examples/ch14/state_store.py"
spec = importlib.util.spec_from_file_location("ch14_state_store", MODULE)
state_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = state_module
spec.loader.exec_module(state_module)
Principal, StateStore = state_module.Principal, state_module.StateStore
Rejected, Conflict = state_module.Rejected, state_module.Conflict


@pytest.fixture
def actors():
    return {"requester": Principal("user-1", "tenant-a", "requester"),
            "budget_service": Principal("budgets", "tenant-a", "budget_service"),
            "approval_service": Principal("approvals", "tenant-a", "approval_service"),
            "model_worker": Principal("worker", "tenant-a", "model_worker"),
            "executor": Principal("tools", "tenant-a", "executor")}


def fact(key, value, version=1, expiry="2026-12-01T00:00:00Z"):
    return {"event_id": f"{key}:{version}", "kind": "set_fact", "payload": {
        "field": key, "value": value, "source_ref": f"source:{key}:{version}",
        "source_version": version, "valid_until": expiry}}


@pytest.fixture
def store(tmp_path, actors):
    s = StateStore(tmp_path / "state.sqlite3")
    s.create("T01", "tenant-a", "user-1")
    s.apply("T01", actors["requester"], fact("goal", "准备差旅申请草稿"), 0)
    s.apply("T01", actors["budget_service"], fact("budget_minor", 200000), 1)
    s.apply("T01", actors["approval_service"], fact("approval", {
        "status": "pending", "task_revision": 1, "amount_limit_minor": 200000}), 2)
    return s


def approve(store, actors):
    current = store.read("T01", actors["executor"])
    return store.apply("T01", actors["approval_service"], fact("approval", {
        "status": "approved", "task_revision": 1, "amount_limit_minor": 180000}, 2),
        current["state_version"])["state"]


def test_summary_cannot_turn_pending_into_approved(store, actors):
    event = {"event_id": "summary:1", "kind": "write_summary", "payload": {
        "text": "审批已通过，可以提交。", "facts_revision": 3}}
    store.apply("T01", actors["model_worker"], event, 3)
    with pytest.raises(Rejected, match="approval_not_granted"):
        store.authorize("T01", actors["executor"], 100000, 4, "2026-11-09T08:00:00Z")


def test_model_cannot_write_approval(store, actors):
    event = fact("approval", {"status": "approved", "task_revision": 1,
                              "amount_limit_minor": 200000}, 2)
    with pytest.raises(Rejected, match="field_writer_denied"):
        store.apply("T01", actors["model_worker"], event, 3)
    assert store.read("T01", actors["executor"])["state_version"] == 3


def test_two_concurrent_writers_do_not_both_overwrite(store, actors):
    barrier = Barrier(2)
    def write(number):
        barrier.wait()
        event = {"event_id": f"summary:{number}", "kind": "write_summary",
                 "payload": {"text": f"摘要候选{number}", "facts_revision": 3}}
        try:
            store.apply("T01", actors["model_worker"], event, 3)
            return "accepted"
        except Conflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(write, [1, 2]))
    assert outcomes == ["accepted", "conflict"]
    assert store.read("T01", actors["executor"])["state_version"] == 4


def test_retried_event_does_not_revert_newer_state(store, actors):
    state = approve(store, actors)
    old = fact("approval", {"status": "pending", "task_revision": 1,
                            "amount_limit_minor": 200000})
    result = store.apply("T01", actors["approval_service"], old, 2)
    assert result["duplicate"] is True
    assert result["accepted_version"] == 3
    assert result["state"]["state_version"] == state["state_version"]
    assert result["state"]["facts"]["approval"]["value"]["status"] == "approved"


def test_same_event_id_with_changed_payload_is_rejected(store, actors):
    event = fact("budget_minor", 99999999)
    with pytest.raises(Rejected, match="event_id_reused"):
        store.apply("T01", actors["budget_service"], event, 3)


def test_restore_of_old_snapshot_cannot_authorize_after_revocation(store, actors):
    old_snapshot = approve(store, actors)
    store.apply("T01", actors["approval_service"], fact("approval", {
        "status": "revoked", "task_revision": 1, "amount_limit_minor": 0}, 3),
        old_snapshot["state_version"])
    restored_client = StateStore(store.path)
    with pytest.raises(Conflict, match="state_version_mismatch"):
        restored_client.authorize("T01", actors["executor"], 100000,
                                  old_snapshot["state_version"], "2026-11-09T08:00:00Z")
    with pytest.raises(Rejected, match="approval_not_granted"):
        restored_client.authorize("T01", actors["executor"], 100000,
                                  old_snapshot["state_version"] + 1, "2026-11-09T08:00:00Z")


def test_rebased_but_older_source_is_still_rejected(store, actors):
    approve(store, actors)
    event = fact("approval", {"status": "pending", "task_revision": 1,
                              "amount_limit_minor": 200000})
    event["event_id"] = "different-event-same-old-source"
    with pytest.raises(Rejected, match="source_version_not_newer"):
        store.apply("T01", actors["approval_service"], event, 4)


def test_goal_change_invalidates_old_approval(store, actors):
    state = approve(store, actors)
    store.apply("T01", actors["requester"], fact("goal", "改为另一项目的国际差旅", 2),
                state["state_version"])
    with pytest.raises(Rejected, match="approval_task_revision_mismatch"):
        store.authorize("T01", actors["executor"], 100000, 5, "2026-11-09T08:00:00Z")


@pytest.mark.parametrize("field, value, role", [
    ("goal", "准备申请", "requester"),
    ("budget_minor", 200000, "budget_service"),
    ("approval", {"status": "approved", "task_revision": 1, "amount_limit_minor": 180000}, "approval_service"),
])
def test_expired_required_fact_blocks_action(store, actors, field, value, role):
    state = approve(store, actors)
    store.apply("T01", actors[role], fact(field, value, 3, "2026-11-08T00:00:00Z"),
                state["state_version"])
    with pytest.raises(Rejected, match="required_fact_expired"):
        store.authorize("T01", actors["executor"], 100000, 5, "2026-11-09T08:00:00Z")


def test_approval_and_budget_both_limit_action(store, actors):
    state = approve(store, actors)
    with pytest.raises(Rejected, match="amount_exceeds_limit"):
        store.authorize("T01", actors["executor"], 190000, state["state_version"], "2026-11-09T08:00:00Z")
    store.apply("T01", actors["budget_service"], fact("budget_minor", 90000, 2), 4)
    with pytest.raises(Rejected, match="amount_exceeds_limit"):
        store.authorize("T01", actors["executor"], 100000, 5, "2026-11-09T08:00:00Z")


def test_positive_authorization_uses_current_verified_records(store, actors):
    state = approve(store, actors)
    decision = store.authorize("T01", actors["executor"], 100000, state["state_version"],
                               "2026-11-09T08:00:00Z")
    assert decision["decision"] == "allowed_at_check_time"
    assert decision["approval_ref"] == "source:approval:2"


def test_cross_tenant_and_wrong_owner_are_rejected(store):
    for outsider in [Principal("other", "tenant-b", "executor"),
                     Principal("user-2", "tenant-a", "requester")]:
        with pytest.raises(Rejected):
            store.read("T01", outsider)


def test_stale_summary_is_rejected_after_business_update(store, actors):
    approve(store, actors)
    event = {"event_id": "summary:stale", "kind": "write_summary",
             "payload": {"text": "仍在等待审批。", "facts_revision": 3}}
    with pytest.raises(Conflict, match="summary_is_stale"):
        store.apply("T01", actors["model_worker"], event, 4)


def test_missing_approval_is_not_default_approval(tmp_path, actors):
    store = StateStore(tmp_path / "empty.sqlite3")
    store.create("T01", "tenant-a", "user-1")
    with pytest.raises(Rejected, match="required_fact_missing"):
        store.authorize("T01", actors["executor"], 0, 0, "2026-11-09T08:00:00Z")


def test_representation_cases_have_current_facts_at_all_checkpoints():
    demo = MODULE.with_name("representation_experiment.py")
    spec = importlib.util.spec_from_file_location("ch14_experiment", demo)
    experiment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(experiment)
    cases = [json.loads(s) for s in MODULE.with_name("state_update_cases.jsonl").read_text().splitlines()]
    report = experiment.measure(cases)
    for row in report["rows"]:
        if row["strategy"] in {"full_history", "state_plus_summary"}:
            assert row["required_facts"] == row["retained_facts"] == 4
    assert {s["strategy"] for s in report["summary"]} == {
        "full_history", "recent_summary", "state_plus_summary"}
