"""Behavioral contracts for D's shared reference implementation."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from ch15.memory import Memory, MemoryStore
from ch17.run_adaptation import accepted, decide, fixtures, validate
from ch33.run_adoption import Directory, business_case
from d_shared.projects import Project, ProjectError, load_assets
from d_shared.retrieval import bm25, permitted, evidence_answer


def memory(**kwargs):
    values = dict(
        memory_id="m1",
        tenant_id="t1",
        owner_id="u1",
        key="departure",
        value="morning",
        kind="semantic",
        scope="user",
        session_id=None,
        valid_from=0,
        valid_until=10,
        revision=1,
        source_ref="confirmed:1",
    )
    values.update(kwargs)
    return Memory(**values)


def test_temporary_override_exits_and_owner_isolates():
    store = MemoryStore()
    store.put(memory(), "t1", "u1")
    store.put(
        memory(memory_id="temp", value="noon", scope="session", session_id="s1"),
        "t1",
        "u1",
    )
    assert store.recall("t1", "u1", "departure", "s1", 1).value == "noon"
    assert store.recall("t1", "u1", "departure", "s2", 1).value == "morning"
    assert store.recall("t1", "u2", "departure", "s1", 1) is None
    assert store.recall("t2", "u1", "departure", "s1", 1) is None
    assert store.recall("t1", "u1", "departure", "s1", 10) is None


def test_delete_invalidates_cached_result_and_restore():
    store = MemoryStore()
    store.put(memory(), "t1", "u1")
    store.snapshot()
    assert store.recall("t1", "u1", "departure", "s1", 1)
    with pytest.raises(PermissionError):
        store.delete("m1", "t1", "u2")
    report = store.delete("m1", "t1", "u1")
    assert report["backup"] == "retained_until_expiry"
    store.restore()
    assert store.recall("t1", "u1", "departure", "s1", 1) is None
    with pytest.raises(ValueError):
        store.put(memory(revision=2), "t1", "u1")


def test_memory_revision_and_untrusted_owner():
    store = MemoryStore()
    store.put(memory(), "t1", "u1")
    with pytest.raises(ValueError):
        store.put(memory(), "t1", "u1")
    with pytest.raises(PermissionError):
        store.put(memory(owner_id="u2"), "t1", "u1")


def test_rag_filters_old_restricted_and_unknown():
    docs, _ = load_assets()
    allowed = [d for d in docs if permitted(d, "B", "2026-11-09")]
    assert len(allowed) == 20
    assert all(d["version"] == 2 and d["classification"] == "internal" for d in allowed)
    assert (
        evidence_answer("差旅住宿上限", bm25("差旅住宿", allowed)[:3])["evidence"]
        == "P01@2#1"
    )
    assert (
        evidence_answer("差旅住宿家属海外商业保险", bm25("差旅住宿", allowed)[:3])[
            "evidence"
        ]
        is None
    )
    assert (
        evidence_answer("差旅住宿专项例外", bm25("差旅住宿", allowed)[:3])["evidence"]
        is None
    )


def test_holdout_rejects_overfit_despite_repair_success():
    kind, repair, holdout, patch = fixtures(0)
    assert validate(patch, repair) and not validate(patch, holdout)
    assert not accepted(
        {"scope": kind, "revision": 2},
        {"scope": kind, "revision": 1},
        {"repair_pass": True, "holdout_pass": False},
    )[0]
    assert validate("correct", repair) and validate("correct", holdout)


@pytest.fixture
def project(tmp_path):
    docs, tasks = load_assets()
    return Project(tmp_path / "p.db", docs), docs, tasks[1]


def test_concurrent_ticket_commit_once(project):
    p, _, task = project
    p.open(task)
    candidate = p.research(task["task_id"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: p.commit(task["task_id"], candidate), range(8))
        )
    assert all(r == results[0] for r in results)
    assert p.ticket_count(task["task_id"]) == 1
    assert sum(e["kind"] == "accepted" for e in p.events(task["task_id"])) == 1
    assert p.query_ticket(task["task_id"])["ticket_id"] == "ticket:" + task["task_id"]


@pytest.mark.parametrize(
    "fault", ["cancel", "late_output", "wrong_release", "missing_evidence"]
)
def test_rejected_work_never_creates_ticket(project, fault):
    p, _, task = project
    with pytest.raises(ProjectError):
        p.run(task, fault=fault)
    assert p.ticket_count(task["task_id"]) == 0


def test_restart_and_stream_cancellation(project):
    p, docs, task = project
    stream = p.stream(task)
    assert next(stream)["kind"] == "evidence_ready"
    restored = Project(p.database, docs)
    assert list(restored.stream(task))[-1]["result"]["decision"] == "create"
    assert restored.ticket_count(task["task_id"]) == 1
    other = dict(task, task_id="cancel-stream")
    stream = restored.stream(other)
    next(stream)
    restored.cancel(other["task_id"])
    with pytest.raises(ProjectError):
        next(stream)
    assert restored.ticket_count(other["task_id"]) == 0


def test_task_identity_and_release_rollback(project):
    p, docs, task = project
    p.open(task)
    with pytest.raises(ProjectError):
        p.open(dict(task, amount_yuan=1))
    with pytest.raises(ProjectError):
        Project(p.database, docs, "bad-release").run(task)
    assert Project(p.database, docs).run(task)["decision"] == "create"


def test_evidence_quote_tampering_and_budget(project):
    p, _, task = project
    p.open(task)
    candidate = p.research(task["task_id"])
    candidate["evidence"]["quote"] = "invented"
    with pytest.raises(ProjectError):
        p.commit(task["task_id"], candidate)
    candidate = p.research(task["task_id"])
    candidate["remaining_steps"] = 0
    with pytest.raises(ProjectError):
        p.commit(task["task_id"], candidate)


def test_revoked_identity_does_not_reuse_cache():
    d = Directory()
    assert d.read("alice", "A")
    d.revoke("alice")
    assert not d.read("alice", "A")
    assert not d.read("bob", "A")


def test_cost_model_includes_review_and_fixed_cost():
    assert business_case(2, 200)["action_net_yuan"] < 0
    assert business_case(2, 1000)["action_net_yuan"] > 0
    assert business_case(10, 1000)["action_net_yuan"] < 0


@pytest.mark.parametrize(
    "amount,approved,expected",
    [
        (499, True, "create"),
        (500, True, "create"),
        (501, True, "hold"),
        (499, False, "hold"),
    ],
)
def test_amount_boundary_and_approval_are_independent(
    project, amount, approved, expected
):
    p, _, task = project
    task = dict(task, amount_yuan=amount, approved=approved)
    assert p.run(task)["decision"] == expected
    assert p.ticket_count(task["task_id"]) == int(expected == "create")


def test_cancel_after_completion_keeps_business_truth(project):
    p, _, task = project
    p.run(task)
    response = p.cancel(task["task_id"])
    assert not response["cancelled"] and p.get(task["task_id"])["stage"] == "completed"
    assert p.ticket_count(task["task_id"]) == 1


def test_foreign_tenant_evidence_is_rejected(project):
    p, docs, task = project
    p.open(task)
    candidate = p.research(task["task_id"])
    foreign = dict(
        next(d for d in docs if d["chunk_id"] == "P01@2#1"),
        chunk_id="foreign#1",
        tenant_id="other",
    )
    p.documents.append(foreign)
    candidate["evidence"]["evidence"] = "foreign#1"
    with pytest.raises(ProjectError, match="evidence_not_permitted"):
        p.commit(task["task_id"], candidate)
    assert p.ticket_count(task["task_id"]) == 0


def test_review_backlog_exposes_capacity_limit():
    from ch33.run_adoption import simulate_flow

    normal = simulate_flow("assist", 2)
    overloaded = simulate_flow("assist", 6)
    assert normal["mean_wait_minutes"] == 0
    assert overloaded["mean_wait_minutes"] == 29.5 and overloaded["peak_waiting"] == 10


def test_role_handoffs_spend_one_shared_budget(project):
    p, _, task = project
    p.run(task, mode="PRJ-2")
    handoffs = [e for e in p.events(task["task_id"]) if e["kind"] == "handoff"]
    assert [e["payload"]["remaining_steps"] for e in handoffs] == [2, 1]
    assert p.ticket_count(task["task_id"]) == 1
