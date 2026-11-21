"""Research/execution/verification in separate local worker processes."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from .adapters import ControlledClock, FixedModel
from .contracts import Approval, Rejected, SimulatedCrash, digest, payload_for, policy_decision
from .coordination import Board
from .engine import Engine
from .storage import SessionStore, TicketService

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "fixtures/study"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def inspect_task(output, task, decision):
    """Fresh read-only connections, rather than an engine's success string."""
    uri = (output / "service.sqlite").resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        rows = db.execute("SELECT payload_json,approved_digest FROM tickets WHERE tenant=? AND operation_id=?",
                          (task["tenant"], f'{task["task_id"]}:{task["revision"]}:create')).fetchall()
        events = [json.loads(r[0]) for r in db.execute("SELECT details_json FROM service_events WHERE kind='created'")]
    uri = (output / "session.sqlite").resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        state = db.execute("SELECT status,reason FROM sessions WHERE tenant=? AND task_id=?", (task["tenant"], task["task_id"])).fetchone()
    eligible = decision == "eligible"
    payload = payload_for(task)
    count = sum(e["tenant"] == task["tenant"] and e["operation_id"] == f'{task["task_id"]}:{task["revision"]}:create' for e in events)
    checks = {"state": bool(state and state[0] == ("completed" if eligible else "rejected")),
              "ticket_count": len(rows) == int(eligible), "created_count": count == int(eligible),
              "payload": all(json.loads(r[0]) == payload and r[1] == digest(payload) for r in rows),
              "rejection_reason": bool(state and (eligible or state[1] == decision))}
    return {"task_id": task["task_id"], "decision": decision, "status": state[0] if state else None,
            "ticket_count": len(rows), "created_count": count, "checks": checks, "passed": all(checks.values())}


def worker(output, job_id, actor, now, crash_after_commit=False):
    policy = load(ROOT / "fixtures/policy.json")
    board = Board(output / "coordination.sqlite")
    try:
        job = board.get(job_id)
        expected_role = {"research": "researcher", "execute": "executor", "verify": "verifier"}
        if not job or expected_role.get(job["stage"]) != actor:
            raise Rejected("worker_role")
        grant = board.claim(job_id, actor, now)
        if not grant:
            raise Rejected("worker_not_granted")
        task = json.loads(job["input_json"])
        if actor == "researcher":
            result = {"decision": policy_decision(task, policy),
                      "evidence": [policy["version"] + "#1", policy["version"] + "#2"],
                      "task_digest": digest(task), "policy_digest": digest(policy)}
        elif actor == "executor":
            research = board.get(task["task_id"] + ":research")
            if not research or research["state"] != "closed":
                raise Rejected("research_not_closed")
            proposal = json.loads(research["result_json"])
            if proposal["task_digest"] != digest(task) or proposal["policy_digest"] != digest(policy):
                raise Rejected("research_binding")
            model = FixedModel({"decision": proposal["decision"], "evidence": proposal["evidence"]})
            store, service = SessionStore(output / "session.sqlite"), TicketService(output / "service.sqlite")
            try:
                approval = Approval(task["tenant"], digest(payload_for(task)), 4000) if proposal["decision"] == "eligible" else None
                engine = Engine(store, service, model, ControlledClock(1000), policy)
                try:
                    state = engine.run(task, approval, fault="after_commit" if crash_after_commit else None)
                except SimulatedCrash:
                    return 42
                result = {"status": state["status"], "operation_id": state["operation_id"], "reason": state["reason"]}
            finally:
                store.close()
                service.close()
        else:
            execution = board.get(task["task_id"] + ":execute")
            if not execution or execution["state"] != "closed":
                raise Rejected("execution_not_closed")
            # The worker does not read the teacher's expected-answer file.
            if task["amount"] > 500 or not task["domestic"] or not task["receipt_valid"]:
                decision = "ineligible"
            else:
                decision = "needs_approval" if task["amount"] > 300 else "eligible"
            result = inspect_task(output, task, decision)
            if not result["passed"]:
                raise Rejected("verification_failed")
        message = board.envelope(grant, result, f'{job_id}:{grant["epoch"]}', now + 1)
        response = board.submit(message, actor, now + 1)
        if not response["accepted"]:
            raise Rejected("worker_submit:" + str(response["reason"]))
        return 0
    finally:
        board.close()


def run_project(output):
    output.mkdir(parents=True, exist_ok=False)
    tasks = load(DATA / "project_tasks.json")
    board = Board(output / "coordination.sqlite")
    commands = []
    now = 0
    try:
        for task in tasks:
            for stage, actor in (("research", "researcher"), ("execute", "executor"), ("verify", "verifier")):
                job_id = task["task_id"] + ":" + stage
                board.add(job_id, task["task_id"], stage, task, tenant=task["tenant"])
                command = [sys.executable, str(ROOT / "run_study.py"), "worker", "--output", str(output),
                           "--job", job_id, "--actor", actor, "--tick", str(now)]
                crash = stage == "execute" and task["task_id"] == tasks[0]["task_id"]
                result = subprocess.run(command + (["--crash-after-commit"] if crash else []), capture_output=True, text=True, encoding="utf-8")
                commands.append({"job": job_id, "actor": actor, "phase": "crash" if crash else "run",
                                 "exit_code": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()})
                if crash and result.returncode == 42:
                    now += 7
                    command[-1] = str(now)
                    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                    commands.append({"job": job_id, "actor": actor, "phase": "recover", "exit_code": result.returncode,
                                     "stdout": result.stdout.strip(), "stderr": result.stderr.strip()})
                if result.returncode:
                    raise Rejected("worker_failed:" + job_id + ":" + result.stderr.strip())
                job = board.get(job_id)
                if not board.close_candidate(job_id, job["candidate_id"], now + 2):
                    raise Rejected("coordinator_close")
                now += 10
        expected = load(DATA / "project_expected.json")
        results = [inspect_task(output, t, expected[t["task_id"]]["decision"]) for t in tasks]
        events = board.events()
        budget = dict(board.db.execute("SELECT used,cap FROM root_budget WHERE id=1").fetchone())
        report = {"project": "PRJ-2-local-1", "evidence": "local_sqlite_and_separate_processes",
                  "scope": "8 original tasks, 2 original clauses, trusted local identities; team integration pending",
                  "tasks": results, "roles": ["researcher", "executor", "verifier"],
                  "closed_jobs": board.db.execute("SELECT count(*) FROM jobs WHERE state='closed'").fetchone()[0],
                  "ticket_count": sum(r["ticket_count"] for r in results), "budget": budget,
                  "commands": commands, "independent_student_reproduction": "pending"}
        report["passed"] = all(r["passed"] for r in results) and report["closed_jobs"] == 24 and report["ticket_count"] == 3
        save(output / "report.json", report)
        save(output / "events.json", events)
        return report
    finally:
        board.close()
