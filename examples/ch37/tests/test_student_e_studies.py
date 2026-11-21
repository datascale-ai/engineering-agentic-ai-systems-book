"""Behavioural checks for persistent coordination and the new bounded studies."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sqlite3

import pytest

from book_reference.contracts import Rejected
from book_reference.coordination import Board, validate_message
from book_reference.coordination_study import run_coordination
from book_reference.debate_study import ScriptModel, evidence_check, rule_check, run_debate
from book_reference.deployment_study import admission, validate_release
from book_reference.environment_study import EnvironmentAdapter, TARGET, run_environments
from book_reference.project2 import DATA, ROOT, load, run_project
from book_reference.contracts import digest


def new_message(board):
    board.add("job", "task", "research", {"amount": 250}, deadline=30)
    grant = board.claim("job", "W1", 0)
    return board.envelope(grant, {"answer": "draft"}, "m1", 3)


def test_receipt_survives_restart_and_conflicting_duplicate_is_rejected(tmp_path):
    path = tmp_path / "board.sqlite"
    first = Board(path)
    message = new_message(first)
    response = first.submit(message, "W1", 3)
    first.close()
    second = Board(path)
    try:
        assert second.submit(message, "W1", 8) == response
        altered = deepcopy(message)
        altered["payload"] = {"answer": "altered"}
        assert second.submit(altered, "W1", 9)["reason"] == "duplicate_conflict"
        assert sum(e["kind"] == "candidate_accepted" for e in second.events()) == 1
        assert json.loads(second.get("job")["result_json"]) == {"answer": "draft"}
    finally:
        second.close()


@pytest.mark.parametrize("tick", [6, 7])
def test_exact_expiry_and_old_assignment_are_rejected(tick, tmp_path):
    board = Board(tmp_path / "board.sqlite")
    try:
        old = new_message(board)
        assert board.submit(old, "W1", tick)["reason"] == "expired_or_clock"
        current = board.claim("job", "W2", 8)
        assert current["epoch"] == 2
        changed_id = {**old, "message_id": "late-old", "candidate_id": "late-candidate"}
        assert not board.submit(changed_id, "W1", 9)["accepted"]
        assert board.get("job")["owner"] == "W2"
        assert not board.renew("job", "W1", 1, 9)
    finally:
        board.close()


def test_verification_is_bound_to_candidate_and_deadline_has_accountable_exit(tmp_path):
    board = Board(tmp_path / "board.sqlite")
    try:
        message = new_message(board)
        board.submit(message, "W1", 3)
        assert not board.close_candidate("job", "different-candidate", 4)
        assert board.get("job")["state"] == "submitted"
        assert not board.close_candidate("job", message["candidate_id"], 30)
        assert board.claim("job", "W2", 30) is None
        assert board.get("job")["state"] == "escalated"
    finally:
        board.close()


def test_concurrent_claims_have_one_distinct_owner(tmp_path):
    path = tmp_path / "board.sqlite"
    board = Board(path)
    board.add("job", "task", "research", {}, deadline=30)
    board.close()
    def claim(actor):
        local = Board(path)
        try:
            return local.claim("job", actor, 0)
        finally:
            local.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, ["W1", "W2"]))
    assert sum(item is not None for item in outcomes) == 1


def test_root_budget_persists_and_role_cannot_impersonate(tmp_path):
    path = tmp_path / "board.sqlite"
    board = Board(path, message_cap=3)
    message = new_message(board)
    assert not board.submit(message, "W2", 3)["accepted"]
    assert board.submit(message, "W1", 3)["accepted"]
    board.close()
    board = Board(path, message_cap=3)
    try:
        with pytest.raises(Rejected, match="root_message_budget"):
            board.submit(message, "W1", 4)
    finally:
        board.close()


@pytest.mark.parametrize("field,value", [("epoch", True), ("revision", 0), ("sent_at", 1.5),
                                        ("schema_version", "unknown"), ("recipient", "executor"), ("payload", [])])
def test_schema_rejects_invalid_control_messages(field, value, tmp_path):
    board = Board(tmp_path / "board.sqlite")
    try:
        message = new_message(board)
        message[field] = value
        with pytest.raises(Rejected):
            validate_message(message)
    finally:
        board.close()


def test_twenty_faults_have_18_completions_and_two_explicit_exits(tmp_path):
    report = run_coordination(tmp_path / "coordination")
    assert report["passed"]
    assert report["protocol_qualified"] == 18
    assert [r["state"] for r in report["protocol"][-2:]] == ["cancelled", "escalated"]
    assert report["budget"]["used"] <= report["budget"]["cap"]
    assert report["simplified_unaccounted"] > 0


def test_question_solver_matches_independently_frozen_answers():
    answers = load(DATA / "question_expected.json")
    assert len(answers) == 20
    for question in load(DATA / "questions.json"):
        assert rule_check(question) == answers[question["task_id"]]


def test_correct_label_with_incomplete_policy_evidence_is_not_qualified():
    question = load(DATA / "questions.json")[13]
    assert question["task_id"] == "Q14"
    response = {"label": "insufficient_evidence", "case_digest": digest(question),
                "evidence": ["P20-A@2.0#eligibility", "P20-A@2.0#approval"]}
    assert not evidence_check(question, response)
    response["evidence"] += ["P20-A@1.0#eligibility", "P20-A@1.0#approval"]
    assert evidence_check(question, response)


def test_script_model_accounts_for_every_request_and_cannot_silently_overrun():
    model = ScriptModel(cap=500, reserve=100, max_calls=1)
    with pytest.raises(Rejected, match="debate_budget"):
        model.propose(load(DATA / "questions.json")[0], 11, "member-0")
    assert model.calls == model.used == 0


def test_three_methods_keep_all_300_trials_and_never_claim_real_tokens(tmp_path):
    report = run_debate(tmp_path / "debate")
    assert report["passed"] and report["trials"] == 300
    assert all(g["trials"] == 100 for g in report["groups"].values())
    rows = [json.loads(line) for line in (tmp_path / "debate/trials.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(r["actual_tokens"] is None and r["money_cost"] is None and r["budget_within_cap"] for r in rows)
    assert all(len(r["messages"]) == r["calls"] for r in rows)


def test_delayed_save_is_queried_and_replayed_without_a_second_effect():
    limits = load(DATA / "study_manifest.json")["environment"]
    env = EnvironmentAdapter({"task_id": "dev-delay", "environment": "form", "fault": "save_delayed"}, 11, limits)
    obs = env.observe()
    fill = {"episode": obs["episode"], "action_id": "fill", "action": "fill", "fields": TARGET,
            "basis": obs["version"], "captured_ms": obs["captured_ms"]}
    env.act(fill)
    obs = env.observe()
    request = {"episode": obs["episode"], "action_id": "save", "action": "save", "x": obs["save_x"],
               "basis": obs["version"], "captured_ms": obs["captured_ms"]}
    assert env.act(request)["status"] == "pending"
    for _ in range(8):
        answer = env.query("save")
    assert answer["status"] == "done"
    assert env.act(request)["status"] == "done"
    assert sum(e["kind"] == "action_committed" and e["details"]["request"]["action"] == "save" for e in env.events) == 1


def test_all_environment_trials_preserve_safety_and_count_stops_separately(tmp_path):
    report = run_environments(tmp_path / "environment")
    assert report["passed"] and report["trials"] == 200
    rows = [json.loads(line) for line in (tmp_path / "environment/trials.jsonl").read_text(encoding="utf-8").splitlines()]
    special = [r for r in rows if r["task_id"] in {"A07", "A10", "B09", "B10"}]
    assert all(r["constraint_handling_passed"] and not r["business_success"] for r in special)
    assert all(r["actions"] <= 12 and r["observations"] <= 20 and r["queries"] <= 20 for r in rows)
    assert all(r["business_success"] for r in rows if r["task_id"] in {"A01", "B01"})
    lost_receipt = [r for r in rows if r["task_id"] == "A06" and r["method"] == "O"]
    assert all(r["oracle"]["postcondition"] and not r["business_success"] for r in lost_receipt)


def test_retirement_actually_blocks_new_admission_and_config_mismatch_is_rejected(tmp_path):
    config = {"release_id": "dev", "source_inventory": digest(load(ROOT / "asset_inventory.json")),
              "policy_version": "P20-A@2.0", "workers": 3, "identity_mode": "trusted_local_fixture"}
    with sqlite3.connect(tmp_path / "control.sqlite") as db:
        db.execute("CREATE TABLE control(id INTEGER, intake INTEGER, grants INTEGER, active TEXT, canary TEXT)")
        db.execute("INSERT INTO control VALUES(1,1,1,'dev',NULL)")
        admission(db, config)
        with pytest.raises(Rejected, match="release_not_routed"):
            admission(db, {**config, "release_id": "removed-canary"})
        with pytest.raises(Rejected, match="release_contract_mismatch"):
            validate_release({**config, "policy_version": "wrong"}, "P20-A@2.0")
        db.execute("UPDATE control SET intake=0,grants=0")
        with pytest.raises(Rejected, match="release_retired"):
            admission(db, config)


def test_project2_roles_use_processes_and_recover_one_external_effect(tmp_path):
    report = run_project(tmp_path / "project")
    assert report["passed"] and len(report["tasks"]) == 8
    assert report["closed_jobs"] == 24 and report["ticket_count"] == 3
    assert [r["exit_code"] for r in report["commands"] if r["phase"] in {"crash", "recover"}] == [42, 0]
    with sqlite3.connect(tmp_path / "project/service.sqlite") as db:
        assert db.execute("SELECT count(*) FROM tickets").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM service_events WHERE kind='created'").fetchone()[0] == 3
