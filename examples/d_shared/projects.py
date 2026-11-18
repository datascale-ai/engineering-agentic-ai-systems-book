"""Shared, deterministic reference project kernel with durable events.

PRJ-1: evidence -> decision -> two sandbox business tools.
PRJ-2: researcher/executor/verifier logical handoffs and acceptance.
PRJ-3: persisted stages, generations, cancellation and release check.
No LLM, external enterprise system, or network service is impersonated.
"""

import json
from pathlib import Path
import sqlite3
import uuid

from .retrieval import bm25, permitted, evidence_answer


class ProjectError(Exception):
    pass


class Project:
    def __init__(self, database, documents, release="teaching-0.1"):
        self.database = str(database)
        self.documents = documents
        self.release = release
        with self.connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, payload TEXT NOT NULL, stage TEXT NOT NULL,
                generation INTEGER NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0,
                release TEXT NOT NULL, result TEXT);
              CREATE TABLE IF NOT EXISTS tickets (
                task_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, payload TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                generation INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
            """)

    def connect(self):
        return sqlite3.connect(self.database, timeout=5)

    @staticmethod
    def event(db, tid, generation, kind, payload):
        db.execute(
            "INSERT INTO events(task_id,generation,kind,payload) VALUES(?,?,?,?)",
            (tid, generation, kind, json.dumps(payload, ensure_ascii=False)),
        )

    def open(self, task):
        text = json.dumps(task, ensure_ascii=False, sort_keys=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM tasks WHERE task_id=?", (task["task_id"],)
            ).fetchone()
            if row and row[0] != text:
                raise ProjectError("task_id_payload_mismatch")
            if not row:
                db.execute(
                    "INSERT INTO tasks VALUES(?,?,?,1,0,?,NULL)",
                    (task["task_id"], text, "ready", self.release),
                )
                self.event(
                    db, task["task_id"], 1, "task_opened", {"release": self.release}
                )

    def get(self, tid):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload,stage,generation,cancelled,release,result FROM tasks WHERE task_id=?",
                (tid,),
            ).fetchone()
        if not row:
            raise ProjectError("unknown_task")
        return {
            "task": json.loads(row[0]),
            "stage": row[1],
            "generation": row[2],
            "cancelled": bool(row[3]),
            "release": row[4],
            "result": json.loads(row[5]) if row[5] else None,
        }

    def cancel(self, tid):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT generation,stage FROM tasks WHERE task_id=?", (tid,)
            ).fetchone()
            if not row:
                raise ProjectError("unknown_task")
            if row[1] == "completed":
                self.event(db, tid, row[0], "cancel_after_completion", {})
                return {"cancelled": False, "reason": "already_completed"}
            if row[1] == "cancelled":
                return {"cancelled": True, "reason": "already_cancelled"}
            db.execute(
                "UPDATE tasks SET cancelled=1,generation=generation+1,stage='cancelled' WHERE task_id=?",
                (tid,),
            )
            self.event(db, tid, row[0] + 1, "cancelled", {})
            return {"cancelled": True, "reason": "cancelled_before_commit"}

    def research(self, tid):
        state = self.get(tid)
        task = state["task"]
        eligible = [
            d
            for d in self.documents
            if d["tenant_id"] == task["tenant_id"]
            and permitted(d, task["department"], "2026-11-09")
        ]
        # The request form supplies an explicit expense category. This is a
        # structured field, not a category inferred from the gold evidence ID.
        eligible = [
            d
            for d in eligible
            if d["topic"] == task["topic"] and d["classification"] == "internal"
        ]
        evidence = evidence_answer(
            task["query"],
            bm25(task["topic"] + " " + task["query"], eligible)[:3],
            task["department"],
        )
        return {
            "task_id": tid,
            "generation": state["generation"],
            "researcher": "research",
            "schema_version": "1.0",
            "message_id": str(uuid.uuid4()),
            "parent_task_id": None,
            "sender": "research",
            "receiver": "verify",
            "remaining_steps": 2,  # Research spent the first of three steps.
            "evidence": evidence,
            "release": self.release,
        }

    def verify(self, tid, candidate):
        state = self.get(tid)
        task = state["task"]
        answer = candidate["evidence"]
        if (
            candidate.get("schema_version") != "1.0"
            or candidate.get("receiver") != "verify"
        ):
            raise ProjectError("message_contract")
        if candidate.get("remaining_steps", 0) < 1:
            raise ProjectError("budget_exhausted")
        if (
            candidate["task_id"] != tid
            or candidate["generation"] != state["generation"]
        ):
            raise ProjectError("late_generation")
        if state["cancelled"]:
            raise ProjectError("cancelled")
        if candidate["release"] != state["release"] or self.release != state["release"]:
            raise ProjectError("release_mismatch")
        doc = next(
            (d for d in self.documents if d["chunk_id"] == answer.get("evidence")), None
        )
        if (
            not doc
            or doc["topic"] != task["topic"]
            or doc["classification"] != "internal"
        ):
            raise ProjectError("missing_or_wrong_evidence")
        if doc["tenant_id"] != task["tenant_id"] or not permitted(
            doc, task["department"], "2026-11-09"
        ):
            raise ProjectError("evidence_not_permitted")
        if (
            answer.get("quote") != doc["text"]
            or answer.get("limit_yuan") != doc["limit_yuan"]
        ):
            raise ProjectError("evidence_content_mismatch")
        return {
            "decision": "create"
            if task["approved"] and task["amount_yuan"] <= doc["limit_yuan"]
            else "hold",
            "evidence": doc["chunk_id"],
            "limit_yuan": doc["limit_yuan"],
        }

    def commit(self, tid, candidate):
        result = self.verify(tid, candidate)
        existing = self.query_ticket(tid)
        if existing and existing["payload"] != result:
            raise ProjectError("existing_ticket_conflict")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT generation,cancelled,release FROM tasks WHERE task_id=?", (tid,)
            ).fetchone()
            if row[1] or row[0] != candidate["generation"]:
                raise ProjectError("cancelled_or_late_generation")
            if row[2] != self.release:
                raise ProjectError("release_mismatch")
            if result["decision"] == "create":
                db.execute(
                    "INSERT OR IGNORE INTO tickets VALUES(?,?,?)",
                    (tid, "ticket:" + tid, json.dumps(result)),
                )
            previous = db.execute(
                "SELECT stage FROM tasks WHERE task_id=?", (tid,)
            ).fetchone()[0]
            db.execute(
                "UPDATE tasks SET stage='completed',result=? WHERE task_id=?",
                (json.dumps(result), tid),
            )
            if previous != "completed":
                self.event(db, tid, row[0], "accepted", result)
        return result

    def query_ticket(self, tid):
        with self.connect() as db:
            row = db.execute(
                "SELECT ticket_id,payload FROM tickets WHERE task_id=?", (tid,)
            ).fetchone()
        return {"ticket_id": row[0], "payload": json.loads(row[1])} if row else None

    def events(self, tid, after=0):
        with self.connect() as db:
            rows = db.execute(
                "SELECT sequence,generation,kind,payload FROM events WHERE task_id=? AND sequence>? ORDER BY sequence",
                (tid, after),
            ).fetchall()
        return [
            {
                "sequence": r[0],
                "generation": r[1],
                "kind": r[2],
                "payload": json.loads(r[3]),
            }
            for r in rows
        ]

    def checkpoint(self, tid, candidate):
        self.verify(tid, candidate)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT generation,cancelled FROM tasks WHERE task_id=?", (tid,)
            ).fetchone()
            if row[1] or row[0] != candidate["generation"]:
                raise ProjectError("late_generation")
            db.execute(
                "UPDATE tasks SET stage='researched',result=? WHERE task_id=?",
                (json.dumps(candidate), tid),
            )
            self.event(
                db,
                tid,
                row[0],
                "checkpoint",
                {"evidence": candidate["evidence"]["evidence"]},
            )

    def stream(self, task):
        """Pull event stream: closing/cancelling before next() prevents commit."""
        self.open(task)
        tid = task["task_id"]
        state = self.get(tid)
        if state["stage"] == "completed":
            yield {"kind": "completed", "result": state["result"]}
            return
        candidate = (
            state["result"] if state["stage"] == "researched" else self.research(tid)
        )
        if state["stage"] != "researched":
            self.checkpoint(tid, candidate)
        yield {
            "kind": "evidence_ready",
            "generation": candidate["generation"],
            "evidence": candidate["evidence"]["evidence"],
        }
        result = self.commit(tid, candidate)
        yield {"kind": "completed", "result": result}

    def run(self, task, mode="PRJ-1", fault=None):
        self.open(task)
        tid = task["task_id"]
        state = self.get(tid)
        if state["release"] != self.release:
            raise ProjectError("release_mismatch")
        if state["cancelled"]:
            raise ProjectError("cancelled")
        if state["stage"] == "completed":
            return state["result"]
        candidate = self.research(tid)
        if mode in {"PRJ-2", "PRJ-3"}:
            with self.connect() as db:
                self.event(
                    db,
                    tid,
                    state["generation"],
                    "handoff",
                    {
                        "from": "research",
                        "to": "verify",
                        "evidence": candidate["evidence"]["evidence"],
                        "remaining_steps": candidate["remaining_steps"],
                    },
                )
        if fault == "missing_evidence":
            candidate["evidence"]["evidence"] = None
        if fault == "worker_lost":
            raise ProjectError("worker_lost_before_commit")
        if fault == "cancel":
            self.cancel(tid)
        if fault == "late_output":
            candidate["generation"] -= 1
        if fault == "wrong_release":
            candidate["release"] = "wrong-release"
        if mode == "PRJ-2":
            checked = self.verify(tid, candidate)
            candidate["remaining_steps"] -= 1
            with self.connect() as db:
                self.event(
                    db,
                    tid,
                    state["generation"],
                    "handoff",
                    {
                        "from": "verify",
                        "to": "execute",
                        "decision": checked["decision"],
                        "remaining_steps": candidate["remaining_steps"],
                    },
                )
        result = self.commit(tid, candidate)
        if fault == "duplicate":
            self.commit(tid, candidate)
        return result

    def ticket_count(self, tid):
        with self.connect() as db:
            return db.execute(
                "SELECT count(*) FROM tickets WHERE task_id=?", (tid,)
            ).fetchone()[0]


def load_assets():
    root = Path(__file__).resolve().parent / "data"
    return (
        [json.loads(s) for s in (root / "policies.jsonl").read_text().splitlines()],
        [json.loads(s) for s in (root / "tasks.jsonl").read_text().splitlines()],
    )
