"""Ch14: persistent task state with conditional updates (Python 3.11+).

No model or external business service is invoked. Principal must be supplied
by the host application's authentication layer, never by model output.
Amounts are integer minor currency units. This module issues decisions;
atomic execution of an external action belongs to the tool boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


class StateError(Exception):
    pass


class Conflict(StateError):
    pass


class Rejected(StateError):
    pass


@dataclass(frozen=True)
class Principal:
    name: str
    tenant_id: str
    role: str


WRITERS = {
    "goal": {"requester"},
    "preference": {"requester"},
    "budget_minor": {"budget_service"},
    "approval": {"approval_service"},
}


def utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise Rejected("timestamp_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise Rejected("timestamp_invalid") from error
    if parsed.tzinfo is None:
        raise Rejected("timezone_required")
    return parsed.astimezone(timezone.utc)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class StateStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS states (
                  task_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                  state_version INTEGER NOT NULL, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS accepted_events (
                  task_id TEXT NOT NULL, principal TEXT NOT NULL,
                  event_id TEXT NOT NULL, payload TEXT NOT NULL,
                  accepted_version INTEGER NOT NULL,
                  PRIMARY KEY (task_id, principal, event_id));
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def create(self, task_id: str, tenant_id: str, owner_id: str) -> dict:
        state = {
            "schema_version": "agent-state-draft-0.1",
            "task_id": task_id, "tenant_id": tenant_id, "owner_id": owner_id,
            "state_version": 0, "task_revision": 0, "facts_revision": 0,
            "facts": {}, "summary": None,
        }
        with self.connect() as db:
            db.execute("INSERT INTO states VALUES (?, ?, 0, ?)",
                       (task_id, tenant_id, canonical(state)))
        return state

    @staticmethod
    def check_scope(state: dict, principal: Principal):
        if principal.tenant_id != state["tenant_id"]:
            raise Rejected("tenant_mismatch")
        if principal.role == "requester" and principal.name != state["owner_id"]:
            raise Rejected("owner_mismatch")
        if principal.role not in {"requester", "budget_service", "approval_service",
                                  "model_worker", "executor"}:
            raise Rejected("role_unknown")

    def read(self, task_id: str, principal: Principal) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT document FROM states WHERE task_id=?",
                             (task_id,)).fetchone()
        if row is None:
            raise Rejected("task_unknown")
        state = json.loads(row[0])
        self.check_scope(state, principal)
        return state

    def apply(self, task_id: str, principal: Principal, event: dict,
              expected_version: int) -> dict:
        """One transaction commits both the state update and event receipt.

        A duplicate returns its original acceptance version and current state.
        It does not recreate a historical state or overwrite newer facts.
        """
        required = {"event_id", "kind", "payload"}
        if (not isinstance(event, dict) or set(event) != required
                or not isinstance(event["event_id"], str) or not event["event_id"]
                or not isinstance(event["payload"], dict)):
            raise Rejected("event_shape")
        encoded = canonical(event)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT document FROM states WHERE task_id=?",
                             (task_id,)).fetchone()
            if row is None:
                raise Rejected("task_unknown")
            state = json.loads(row[0])
            self.check_scope(state, principal)
            old = db.execute("""SELECT payload, accepted_version FROM accepted_events
                                WHERE task_id=? AND principal=? AND event_id=?""",
                             (task_id, principal.name, event["event_id"])).fetchone()
            if old:
                if old[0] != encoded:
                    raise Rejected("event_id_reused_with_different_payload")
                return {"duplicate": True, "accepted_version": old[1], "state": state}
            if state["state_version"] != expected_version:
                raise Conflict("state_version_mismatch")
            if event["kind"] == "set_fact":
                self.set_fact(state, principal, event["payload"])
            elif event["kind"] == "write_summary":
                p = event["payload"]
                if principal.role != "model_worker" or set(p) != {"text", "facts_revision"}:
                    raise Rejected("summary_writer_or_shape")
                if not isinstance(p["text"], str) or len(p["text"]) > 1000:
                    raise Rejected("summary_text")
                if p["facts_revision"] != state["facts_revision"]:
                    raise Conflict("summary_is_stale")
                state["summary"] = {**p, "based_on_state_version": expected_version}
            else:
                raise Rejected("event_kind_unknown")
            state["state_version"] += 1
            version = state["state_version"]
            changed = db.execute("""UPDATE states SET state_version=?, document=?
                                    WHERE task_id=? AND state_version=?""",
                                 (version, canonical(state), task_id, expected_version))
            if changed.rowcount != 1:
                raise Conflict("state_version_mismatch")
            db.execute("INSERT INTO accepted_events VALUES (?, ?, ?, ?, ?)",
                       (task_id, principal.name, event["event_id"], encoded, version))
            return {"duplicate": False, "accepted_version": version, "state": state}

    @staticmethod
    def set_fact(state: dict, principal: Principal, p: dict):
        fields = {"field", "value", "source_ref", "source_version", "valid_until"}
        if set(p) != fields or p["field"] not in WRITERS:
            raise Rejected("fact_shape")
        field = p["field"]
        if principal.role not in WRITERS[field]:
            raise Rejected("field_writer_denied")
        if not isinstance(p["source_ref"], str) or not p["source_ref"]:
            raise Rejected("source_ref_required")
        if type(p["source_version"]) is not int or p["source_version"] < 1:
            raise Rejected("source_version_invalid")
        utc(p["valid_until"])
        previous = state["facts"].get(field)
        if previous and p["source_version"] <= previous["source_version"]:
            raise Rejected("source_version_not_newer")
        value = p["value"]
        if field in {"goal", "preference"} and (not isinstance(value, str) or not value):
            raise Rejected("text_value_required")
        if field == "budget_minor" and (type(value) is not int or value < 0):
            raise Rejected("budget_invalid")
        if field == "approval":
            if not isinstance(value, dict) or set(value) != {"status", "task_revision", "amount_limit_minor"}:
                raise Rejected("approval_shape")
            if value["status"] not in {"pending", "approved", "revoked"}:
                raise Rejected("approval_status_invalid")
            if (type(value["task_revision"]) is not int
                    or value["task_revision"] != state["task_revision"]):
                raise Rejected("approval_task_revision_mismatch")
            if type(value["amount_limit_minor"]) is not int or value["amount_limit_minor"] < 0:
                raise Rejected("approval_amount_invalid")
        if field == "goal":
            state["task_revision"] += 1
        state["facts"][field] = {
            "value": value, "source_ref": p["source_ref"],
            "source_version": p["source_version"], "valid_until": p["valid_until"],
            "writer": principal.name, "status": "verified",
        }
        state["facts_revision"] += 1

    def authorize(self, task_id: str, principal: Principal, amount_minor: int,
                  expected_version: int, now: str) -> dict:
        state = self.read(task_id, principal)
        if principal.role != "executor":
            raise Rejected("executor_required")
        if type(amount_minor) is not int or amount_minor < 0:
            raise Rejected("amount_invalid")
        if state["state_version"] != expected_version:
            raise Conflict("state_version_mismatch")
        for field in ("goal", "budget_minor", "approval"):
            fact = state["facts"].get(field)
            if fact is None or fact["status"] != "verified":
                raise Rejected("required_fact_missing")
            if utc(now) >= utc(fact["valid_until"]):
                raise Rejected("required_fact_expired")
        approval = state["facts"]["approval"]["value"]
        if approval["status"] != "approved":
            raise Rejected("approval_not_granted")
        if approval["task_revision"] != state["task_revision"]:
            raise Rejected("approval_task_revision_mismatch")
        if amount_minor > min(state["facts"]["budget_minor"]["value"],
                              approval["amount_limit_minor"]):
            raise Rejected("amount_exceeds_limit")
        return {"task_id": task_id, "state_version": state["state_version"],
                "approval_ref": state["facts"]["approval"]["source_ref"],
                "decision": "allowed_at_check_time"}
