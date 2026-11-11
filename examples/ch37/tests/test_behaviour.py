"""Thirty fixed scenarios, checked against persistent business facts."""
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3

import pytest

from book_reference.adapters import ControlledClock, FixedModel
from book_reference.contracts import Approval, Rejected, ReplyGate, SimulatedCrash, validate_task
from book_reference.engine import Engine
from book_reference.storage import SessionStore, TicketService

BASE = Path(__file__).resolve().parents[2] / "ch36" / "fixtures"
CASES = [json.loads(line) for line in (Path(__file__).parents[1] / "fixtures/cases.jsonl").read_text(encoding="utf-8").splitlines()]


def expected_payload(task):
    # The oracle explicitly lists business fields; it does not call payload_for().
    return {"task_id": task["task_id"], "revision": task["revision"], "amount": task["amount"],
            "domestic": task["domestic"], "receipt_valid": task["receipt_valid"], "policy_version": task["policy_version"]}


def expected_digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def assert_business_facts(path, count, payload=None):
    # Separate connection; a forged success response cannot satisfy this assertion.
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT tenant,operation_id,payload_json,approved_digest FROM tickets").fetchall()
        created = db.execute("SELECT count(*) FROM service_events WHERE kind='created'").fetchone()[0]
    assert len(rows) == count
    assert created == count
    assert len({(row[0], row[1]) for row in rows}) == count
    if payload is not None:
        assert all(json.loads(row[2]) == payload for row in rows)
        assert all(row[3] == expected_digest(payload) for row in rows)
    return rows


class Harness:
    def __init__(self, path, task_patch=None, model_decision="eligible", now_ms=1000):
        self.path = path
        self.task = json.loads((BASE / "task.json").read_text(encoding="utf-8"))
        self.task.update(task_patch or {})
        self.policy = json.loads((BASE / "policy.json").read_text(encoding="utf-8"))
        self.model = FixedModel({"decision": model_decision, "evidence": ["P20-A@2.0#1", "P20-A@2.0#2"]})
        self.clock = ControlledClock(now_ms)
        self.payload = expected_payload(self.task)
        self.grant = Approval(self.task["tenant"], expected_digest(self.payload), 4000)
        self.open()

    def open(self):
        self.store = SessionStore(self.path / "session.sqlite")
        self.service = TicketService(self.path / "service.sqlite")
        self.engine = Engine(self.store, self.service, self.model, self.clock, self.policy)

    def close(self):
        self.store.close()
        self.service.close()

    def reopen(self):
        self.close()
        self.open()

    def run(self, **kwargs):
        return self.engine.run(self.task, self.grant, **kwargs)

    def events(self):
        with sqlite3.connect(self.path / "session.sqlite") as db:
            return [row[0] for row in db.execute("SELECT kind FROM events ORDER BY sequence")]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_fixed_case(case, tmp_path, monkeypatch):
    scenario = case["scenario"]
    if case["id"].startswith("SC"):
        task = json.loads((BASE / "task.json").read_text(encoding="utf-8"))
        task.update(case.get("task_patch", {}))
        task.pop(case.get("remove", "__absent__"), None)
        if case["expected"] == "accepted":
            assert validate_task(task) == task
        else:
            with pytest.raises(Rejected, match=case["expected"]):
                validate_task(task)
        return
    h = Harness(tmp_path, case.get("task_patch"), case.get("model_decision", "eligible"), case.get("clock_ms", 1000))
    try:
        if scenario in {"wrong_revision", "old_epoch", "duplicate_message", "altered_duplicate"}:
            reply = h.model.propose(h.task)
            gate = ReplyGate()
            if scenario == "duplicate_message":
                assert [gate.accept(h.task, reply), gate.accept(h.task, reply)] == case["expected_acceptance"]
            else:
                if scenario == "altered_duplicate":
                    assert gate.accept(h.task, reply)
                reply.update(case["reply_patch"])
                with pytest.raises(Rejected, match=case["expected_reason"]):
                    gate.accept(h.task, reply)
            assert_business_facts(tmp_path / "service.sqlite", 0)
            return
        if scenario in {"same_key_replay", "key_conflict", "tenant_isolation"}:
            key = "fixed-operation"
            first = h.service.create(h.task["tenant"], key, h.payload, h.grant, 1000)
            if scenario == "same_key_replay":
                assert h.service.create(h.task["tenant"], key, h.payload, None, 9999) == first
                assert h.service.db.execute("SELECT count(*) FROM service_events WHERE kind='replayed'").fetchone()[0] == case["expected_replays"]
            elif scenario == "key_conflict":
                changed = dict(h.payload, amount=case["changed_amount"])
                with pytest.raises(Rejected, match=case["expected_reason"]):
                    h.service.create(h.task["tenant"], key, changed, h.grant, 1000)
            else:
                tenant = case["second_tenant"]
                h.service.create(tenant, key, h.payload, Approval(tenant, expected_digest(h.payload), 4000), 1000)
            assert_business_facts(tmp_path / "service.sqlite", case["expected_tickets"], h.payload)
            return
        if case.get("grant") == "missing":
            h.grant = None
        elif case.get("grant") == "other_tenant":
            h.grant = Approval("another-tenant", expected_digest(h.payload), 4000)
        elif case.get("grant") == "wrong_digest":
            h.grant = Approval(h.task["tenant"], "0" * 64, 4000)
        elif case.get("grant") == "expired":
            h.grant = Approval(h.task["tenant"], expected_digest(h.payload), 1000)
        if scenario == "unverified_effect":
            monkeypatch.setattr(h.service, "verify", lambda *args: False)
        if scenario == "commit_timeout_resume":
            original = h.service.create
            calls = []

            def commit_then_timeout(*args):
                calls.append(args[1])
                original(*args)
                raise TimeoutError("controlled response loss after commit")

            monkeypatch.setattr(h.service, "create", commit_then_timeout)
            assert h.run()["status"] == "pending"
            result = h.run()
            assert len(calls) == 1
            assert result["attempts"] == case["expected_attempts"]
        elif scenario in {"recover_before_send", "recover_after_commit", "project_3_resume"}:
            with pytest.raises(SimulatedCrash):
                h.run(project=case.get("project", "PRJ-3"), fault=case["fault"])
            assert_business_facts(tmp_path / "service.sqlite", 0 if case["fault"] == "before_send" else 1)
            h.reopen()
            result = h.run(project=case.get("project", "PRJ-3"))
        elif scenario == "completed_replay":
            h.run()
            result = h.run()
            assert h.model.calls == case["expected_model_calls"]
        elif scenario == "cancel_before_send":
            h.store.cancel(h.task)
            result = h.run()
            assert "action_requested" not in h.events()
        else:
            result = h.run(project=case.get("project", "PRJ-1"), fault=case.get("fault"))
        assert result["status"] == case["expected_status"]
        if "expected_reason" in case:
            assert result["reason"] == case["expected_reason"]
        assert_business_facts(tmp_path / "service.sqlite", case["expected_tickets"], h.payload)
        events = h.events()
        if result["status"] == "completed":
            assert events.index("intent_saved") < events.index("action_requested") < events.index("postcondition_verified") < events.index("completed")
        if "required_event" in case:
            assert case["required_event"] in events
        if scenario == "cancel_after_commit":
            assert result["ticket_id"] is not None
            assert "completed" not in events
    finally:
        h.close()


def test_fixture_ids_are_unique_and_classified():
    assert len(CASES) == len({case["id"] for case in CASES}) == 30
    assert {case["id"][:2] for case in CASES} == {"SC", "PA", "TO", "SE", "CO", "EE"}


@pytest.mark.parametrize("sequence", itertools.product(("run", "recover", "cancel"), repeat=3), ids=lambda s: "-".join(s))
def test_bounded_state_sequences(sequence, tmp_path):
    """27 explicit sequences, not a claim of exhaustive or Hypothesis testing."""
    h = Harness(tmp_path)
    try:
        cancelled = False
        for operation in sequence:
            if operation == "recover":
                h.reopen()
            elif operation == "cancel":
                state = h.store.ensure(h.task)
                if state["status"] not in {"completed", "rejected"}:
                    h.store.cancel(h.task)
                    cancelled = True
            else:
                h.run()
            state = h.store.ensure(h.task)
            rows = assert_business_facts(tmp_path / "service.sqlite", 1 if state["ticket_id"] is not None else 0, h.payload)
            assert len(rows) <= 1
            if cancelled:
                assert state["status"] == "cancelled"
    finally:
        h.close()


def test_regression_new_key_on_retry_is_detected(tmp_path):
    """The deliberately defective client is confined to this test."""
    h = Harness(tmp_path)
    try:
        for attempt in (1, 2):
            h.service.create(h.task["tenant"], f"buggy-attempt-{attempt}", h.payload, h.grant, 1000)
        assert {"status": "completed"}["status"] == "completed"  # old presentation-only check passes
        with pytest.raises(AssertionError):
            assert_business_facts(tmp_path / "service.sqlite", 1, h.payload)
        # The shipped recovery path uses the stable operation ID (SE-02 / TO-05).
        assert_business_facts(tmp_path / "service.sqlite", 2, h.payload)
    finally:
        h.close()


def test_unknown_query_never_resends(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    try:
        def timeout(*args):
            raise TimeoutError("controlled query failure")
        monkeypatch.setattr(h.service, "lookup", timeout)
        result = h.run()
        assert result["status"] == "pending"
        assert result["reason"] == "lookup_timeout"
        assert result["attempts"] == 0
        assert_business_facts(tmp_path / "service.sqlite", 0)
    finally:
        h.close()


def test_task_cannot_change_under_recovery_identity(tmp_path):
    h = Harness(tmp_path)
    try:
        with pytest.raises(SimulatedCrash):
            h.run(fault="before_send")
        h.task["amount"] += 1
        with pytest.raises(Rejected, match="session_task_conflict"):
            h.run()
        assert_business_facts(tmp_path / "service.sqlite", 0)
    finally:
        h.close()


def test_terminal_cancel_cannot_become_completed(tmp_path):
    h = Harness(tmp_path)
    try:
        h.store.cancel(h.task)
        with pytest.raises(Rejected, match="terminal_session"):
            h.store.transition(h.task, "completed", "forged_completion")
        assert_business_facts(tmp_path / "service.sqlite", 0)
    finally:
        h.close()
