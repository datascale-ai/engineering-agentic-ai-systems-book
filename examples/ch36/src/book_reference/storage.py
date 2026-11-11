"""Two independent local SQLite stores expose the client/service commit gap."""
import json
import sqlite3
from .contracts import Rejected, canonical, digest


class TicketService:
    """A local service substitute, with atomic effect and idempotency record."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
              ticket_id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, operation_id TEXT NOT NULL,
              payload_digest TEXT NOT NULL, payload_json TEXT NOT NULL,
              approved_digest TEXT NOT NULL, created_at_ms INTEGER NOT NULL,
              UNIQUE(tenant, operation_id));
            CREATE TABLE IF NOT EXISTS service_events (
              sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, details_json TEXT NOT NULL);
        """)
        self.db.commit()

    def _event(self, kind, details):
        self.db.execute("INSERT INTO service_events(kind,details_json) VALUES (?,?)", (kind, canonical(details)))

    def lookup(self, tenant, operation_id, payload):
        # Caller identity is supplied by this trusted in-process boundary, not model text.
        row = self.db.execute("SELECT ticket_id,payload_digest FROM tickets WHERE tenant=? AND operation_id=?", (tenant, operation_id)).fetchone()
        if row and row[1] != digest(payload):
            raise Rejected("idempotency_conflict")
        return row[0] if row else None

    def create(self, tenant, operation_id, payload, approval, now_ms):
        # BEGIN IMMEDIATE serializes local writers. It does not make the client store atomic.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.lookup(tenant, operation_id, payload)
            if existing is not None:
                self._event("replayed", {"tenant": tenant, "operation_id": operation_id})
                self.db.commit()
                return existing
            if approval is None or not approval.permitted:
                raise Rejected("approval_missing")
            if approval.tenant != tenant:
                raise Rejected("approval_tenant")
            if approval.payload_digest != digest(payload):
                raise Rejected("approval_scope")
            if now_ms >= approval.expires_at_ms:
                raise Rejected("approval_expired")
            cursor = self.db.execute("INSERT INTO tickets(tenant,operation_id,payload_digest,payload_json,approved_digest,created_at_ms) VALUES (?,?,?,?,?,?)",
                                     (tenant, operation_id, digest(payload), canonical(payload), approval.payload_digest, now_ms))
            self._event("created", {"tenant": tenant, "operation_id": operation_id, "ticket_id": cursor.lastrowid})
            self.db.commit()
            return cursor.lastrowid
        except Exception:
            self.db.rollback()
            raise

    def verify(self, tenant, ticket_id, expected_payload):
        row = self.db.execute("SELECT payload_json,approved_digest FROM tickets WHERE tenant=? AND ticket_id=?", (tenant, ticket_id)).fetchone()
        return bool(row and json.loads(row[0]) == expected_payload and row[1] == digest(expected_payload))

    def close(self):
        self.db.close()


class SessionStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
              tenant TEXT, task_id TEXT, task_digest TEXT NOT NULL,
              status TEXT NOT NULL, reason TEXT, operation_id TEXT, payload_json TEXT,
              attempts INTEGER NOT NULL DEFAULT 0, ticket_id INTEGER,
              PRIMARY KEY(tenant, task_id));
            CREATE TABLE IF NOT EXISTS events (
              sequence INTEGER PRIMARY KEY, tenant TEXT, task_id TEXT,
              kind TEXT NOT NULL, details_json TEXT NOT NULL);
        """)
        self.db.commit()

    def event(self, task, kind, **details):
        self.db.execute("INSERT INTO events(tenant,task_id,kind,details_json) VALUES (?,?,?,?)",
                        (task["tenant"], task["task_id"], kind, canonical(details)))

    def get(self, task):
        row = self.db.execute("SELECT * FROM sessions WHERE tenant=? AND task_id=?", (task["tenant"], task["task_id"])).fetchone()
        return dict(row) if row else None

    def ensure(self, task):
        row = self.get(task)
        if row:
            if row["task_digest"] != digest(task):
                raise Rejected("session_task_conflict")
            return row
        with self.db:
            self.db.execute("INSERT INTO sessions(tenant,task_id,task_digest,status) VALUES (?,?,?,?)",
                            (task["tenant"], task["task_id"], digest(task), "new"))
            self.event(task, "session_created")
        return self.get(task)

    def transition(self, task, status, kind, **fields):
        if set(fields) - {"reason", "operation_id", "payload_json", "ticket_id", "attempts"}:
            raise ValueError("unknown_session_field")
        old = self.get(task)
        allowed = {"new": {"new", "pending", "rejected", "cancelled"},
                   "pending": {"pending", "completed", "rejected", "cancelled"},
                   "completed": {"completed"}, "rejected": {"rejected"},
                   "cancelled": {"cancelled"}}
        if old is None or status not in allowed[old["status"]]:
            raise Rejected("terminal_session" if old and old["status"] in {"completed", "rejected", "cancelled"} else "state_transition")
        names = ["status", *fields]
        with self.db:
            self.db.execute("UPDATE sessions SET " + ",".join(k+"=?" for k in names) + " WHERE tenant=? AND task_id=?",
                            (status, *fields.values(), task["tenant"], task["task_id"]))
            self.event(task, kind, **fields)
        return self.get(task)

    def cancel(self, task):
        self.ensure(task)
        if self.get(task)["status"] in {"completed", "rejected"}:
            raise Rejected("terminal_session")
        return self.transition(task, "cancelled", "cancelled", reason="user_cancelled")

    def close(self):
        self.db.close()
