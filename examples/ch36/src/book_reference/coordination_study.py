"""Twenty deterministic fault scripts, three rotating workers, paired baselines."""
import json

from .coordination import Board
from .project2 import DATA, load, save


def exercise(board, case):
    task_id, actor, base, fault = case["task_id"], case["worker"], case["start"], case["fault"]
    takeover = "W" + str(int(actor[-1]) % 3 + 1)
    board.add(task_id, task_id, "draft", {"expected_draft_version": 1}, deadline=base + 16)
    trace = []

    def claim(who, tick, protocol_only=False):
        grant = board.claim(task_id, who, base + tick)
        trace.append({"op": "claim", "tick": tick, "actor": who, "protocol_only": protocol_only})
        return grant

    def submit(grant, tick, suffix="main", version=1, dropped=False, protocol_only=False, existing=None):
        message = existing or board.envelope(grant, {"draft_version": version, "policy": "P20-A@2.0"}, task_id + ":" + suffix, base + tick)
        trace.append({"op": "submit", "tick": tick, "message": message, "dropped": dropped, "protocol_only": protocol_only})
        if not dropped:
            board.submit(message, grant["owner"], base + tick)
        else:
            board.event(base + tick, task_id, "transport_drop", message=message)
        return message

    def close(message, tick, passed=True):
        board.close_candidate(task_id, message["candidate_id"], base + tick, passed)
        trace.append({"op": "close", "tick": tick, "candidate_id": message["candidate_id"], "passed": passed})

    first = claim(actor, 0)
    if fault == "partition":
        board.event(base + 1, task_id, "partition_started", owner=actor)
        claim(takeover, 16, True)
    elif fault == "cancel":
        board.cancel(task_id, base + 2)
        trace.append({"op": "cancel", "tick": 2})
        close(submit(first, 3), 4)
    elif fault in {"late_old", "late_renew"}:
        current = claim(takeover, 7)
        if fault == "late_renew":
            board.renew(task_id, actor, first["epoch"], base + 8)
            trace.append({"op": "renew", "tick": 8, "actor": actor})
        close(submit(current, 9, "new"), 10)
        close(submit(first, 12, "old", version=0), 13)
    elif fault == "old_verification":
        old = submit(first, 2, "old", version=0)
        close(old, 3, False)
        current = claim(actor, 4)
        close(submit(current, 6, "new"), 7)
        close(old, 8)
    elif fault in {"at_expiry", "after_expiry"}:
        submit(first, 6 if fault == "at_expiry" else 7, "expired", version=0)
        current = claim(takeover, 8)
        close(submit(current, 10, "new"), 11)
    elif fault == "worker_exit":
        board.event(base + 2, task_id, "worker_exited", actor=actor)
        close(submit(claim(takeover, 7), 9), 10)
    elif fault == "lost_grant_ack":
        board.event(base, task_id, "grant_ack_lost")
        current = claim(actor, 2, True)
        close(submit(current, 3), 4)
    elif fault == "lost_submit":
        message = submit(first, 3, dropped=True)
        submit(first, 4, protocol_only=True, existing=message)
        close(message, 5)
    else:
        tick = 5 if fault == "before_expiry" else 3
        message = submit(first, tick)
        if fault in {"duplicate", "duplicate_many", "lost_submit_ack"}:
            if fault == "lost_submit_ack":
                board.event(base + tick, task_id, "submit_ack_lost", message_id=message["message_id"])
            count = 3 if fault == "duplicate_many" else 1
            for i in range(count):
                submit(first, 4 + i, existing=message, protocol_only=fault == "lost_submit_ack")
        if fault == "exit_after_submit":
            board.event(base + 4, task_id, "worker_exited", actor=actor)
        close(message, 8 if fault == "exit_after_submit" else max(tick + 1, 7 if fault == "duplicate_many" else 4))
        if fault == "duplicate_after_close":
            submit(first, 9, existing=message)
    return trace


def simplified(trace, case):
    """An intentionally limited last-result-wins application with no durable ACKs."""
    state, candidate, closing, accepted, stale, sent = "ready", None, 0, 0, 0, 0
    for entry in trace:
        if entry.get("protocol_only"):
            continue
        sent += 1
        if entry["op"] == "claim" and state == "ready":
            state = "leased"
        elif entry["op"] == "submit" and not entry["dropped"]:
            if case["fault"] == "lost_grant_ack":
                continue  # this baseline has no retry/query after the lost grant receipt
            candidate = entry["message"]["payload"]
            accepted += 1
            stale += int(candidate["draft_version"] != 1)
            state = "submitted"
        elif entry["op"] == "cancel":
            state = "cancelled"
        elif entry["op"] == "close" and candidate is not None:
            if entry["passed"]:
                state, closing = "closed", closing + 1
            else:
                state = "ready"
    cancelled = case["fault"] == "cancel"
    duplicate_effects = max(0, accepted - (2 if case["fault"] == "old_verification" else 1))
    valid = bool(state == "closed" and candidate and candidate["draft_version"] == 1 and closing == 1
                 and not cancelled and not stale and not duplicate_effects)
    return {"task_id": case["task_id"], "state": state, "qualified_completion": valid,
            "duplicate_effects": duplicate_effects,
            "stale_acceptances": stale, "close_count": closing, "cancel_reactivated": cancelled and state != "cancelled",
            "unaccounted": state not in {"closed", "cancelled", "escalated"}, "request_attempts": sent}


def run_coordination(output):
    output.mkdir(parents=True, exist_ok=False)
    board = Board(output / "coordination.sqlite")
    rows, baseline = [], []
    try:
        for case in load(DATA / "coordination_faults.json"):
            trace = exercise(board, case)
            baseline.append(simplified(trace, case))
            job = board.get(case["task_id"])
            events = [e for e in board.events() if e["job_id"] == case["task_id"]]
            expected = "cancelled" if case["fault"] == "cancel" else "escalated" if case["fault"] == "partition" else "closed"
            closes = sum(e["kind"] == "closed" for e in events)
            result = json.loads(job["result_json"]) if job["result_json"] else None
            passed = job["state"] == expected and closes == int(expected == "closed") and (expected != "closed" or result["draft_version"] == 1)
            fault_time = next((e["tick"] for e in events if e["kind"] in {"transport_drop", "worker_exited", "grant_ack_lost", "partition_started", "message_rejected"}), None)
            rows.append({"task_id": case["task_id"], "fault": case["fault"], "state": job["state"],
                         "qualified_completion": passed and expected == "closed", "acceptance_passed": passed,
                         "close_count": closes, "grants": job["attempts"],
                         "rejected_messages": sum(e["kind"] in {"message_rejected", "verification_rejected", "renew_rejected"} for e in events),
                         "terminal_tick": job["closed_at"], "fault_tick": fault_time,
                         "recovery_ticks": job["closed_at"] - fault_time if fault_time is not None and expected == "closed" else None,
                         "communication": {"request_attempts": len(trace),
                                           "reply_attempts": len(trace) - sum(e.get("dropped", False) for e in trace),
                                           "lost_requests": sum(e.get("dropped", False) for e in trace),
                                           "lost_replies": int(case["fault"] in {"lost_grant_ack", "lost_submit_ack"})},
                         "trace": trace})
        budget = dict(board.db.execute("SELECT used,cap FROM root_budget").fetchone())
        report = {"experiment": "Exp-19-01", "evidence": "deterministic_discrete_events_and_sqlite",
                  "workers": ["W1", "W2", "W3"], "scheduling": "20-tick serial task slots; no throughput claim",
                  "budget_unit": "authoritative RPC requests; transport attempts and replies reported separately",
                  "task_count": 20, "protocol": rows, "simplified": baseline, "budget": budget,
                  "protocol_qualified": sum(r["qualified_completion"] for r in rows),
                  "simplified_qualified": sum(r["qualified_completion"] for r in baseline),
                  "simplified_unaccounted": sum(r["unaccounted"] for r in baseline),
                  "passed": all(r["acceptance_passed"] for r in rows)}
        save(output / "report.json", report)
        save(output / "events.json", board.events())
        return report
    finally:
        board.close()
