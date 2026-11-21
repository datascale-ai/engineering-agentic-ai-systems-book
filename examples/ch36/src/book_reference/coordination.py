"""Local durable coordination; trusted process identities, not network authentication."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from .contracts import Rejected, canonical, digest

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "fixtures/study/message_schema.json"


def validate_message(message):
    """Validate the deliberately small JSON Schema vocabulary used by this package."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(message, dict) or set(message) != set(schema["required"]):
        raise Rejected("message_fields")
    kinds = {"string": str, "integer": int, "object": dict}
    for key, spec in schema["properties"].items():
        value = message[key]
        if type(value) is not kinds[spec["type"]]:
            raise Rejected("message_type:" + key)
        if isinstance(value, str) and not 1 <= len(value) <= spec.get("maxLength", 200):
            raise Rejected("message_string:" + key)
        if "minimum" in spec and value < spec["minimum"]:
            raise Rejected("message_minimum:" + key)
        if "enum" in spec and value not in spec["enum"]:
            raise Rejected("message_enum:" + key)
    if message["sent_at"] >= message["deadline"]:
        raise Rejected("message_deadline")
    return message


class Board:
    """A single SQLite authority atomically records transitions, receipts and events.

    Only this authority's integer tick is used for lease checks. Role/tenant are
    supplied by the trusted harness. No cross-database transaction is implied.
    """
    def __init__(self, path, message_cap=240):
        if type(message_cap) is not int or message_cap < 1:
            raise Rejected("message_cap")
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, task_id TEXT, tenant TEXT, stage TEXT,
            revision INTEGER, epoch INTEGER DEFAULT 0, owner TEXT,
            lease_until INTEGER, deadline INTEGER, state TEXT DEFAULT 'ready',
            attempts INTEGER DEFAULT 0, input_json TEXT, candidate_id TEXT,
            result_json TEXT, closed_at INTEGER);
          CREATE TABLE IF NOT EXISTS receipts (
            actor TEXT, message_id TEXT, body_digest TEXT, response_json TEXT,
            PRIMARY KEY(actor,message_id));
          CREATE TABLE IF NOT EXISTS coordination_events (
            seq INTEGER PRIMARY KEY, tick INTEGER, job_id TEXT, kind TEXT, detail_json TEXT);
          CREATE TABLE IF NOT EXISTS root_budget (
            id INTEGER PRIMARY KEY CHECK(id=1), used INTEGER, cap INTEGER);
        """)
        self.db.execute("INSERT OR IGNORE INTO root_budget VALUES(1,0,?)", (message_cap,))
        if self.db.execute("SELECT cap FROM root_budget").fetchone()[0] != message_cap:
            raise Rejected("budget_configuration_changed")

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def event(self, now, job_id, kind, **detail):
        self.db.execute("INSERT INTO coordination_events(tick,job_id,kind,detail_json) VALUES(?,?,?,?)",
                        (now, job_id, kind, canonical(detail)))

    def charge(self):
        row = self.db.execute("SELECT used,cap FROM root_budget WHERE id=1").fetchone()
        if row[0] >= row[1]:
            raise Rejected("root_message_budget")
        self.db.execute("UPDATE root_budget SET used=used+1 WHERE id=1")

    def add(self, job_id, task_id, stage, payload, deadline=10000, tenant="course", revision=1):
        with self.transaction():
            old = self.get(job_id)
            if old:
                if (old["input_json"], old["stage"], old["tenant"], old["revision"], old["deadline"]) != (
                        canonical(payload), stage, tenant, revision, deadline):
                    raise Rejected("job_identity_conflict")
                return
            self.db.execute("INSERT INTO jobs(job_id,task_id,tenant,stage,revision,deadline,input_json) VALUES(?,?,?,?,?,?,?)",
                            (job_id, task_id, tenant, stage, revision, deadline, canonical(payload)))
            self.event(0, job_id, "job_created", stage=stage, tenant=tenant)

    def get(self, job_id):
        row = self.db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def claim(self, job_id, actor, now, lease=6):
        with self.transaction():
            self.charge()
            job = self.get(job_id)
            if not job or job["state"] in {"closed", "cancelled", "escalated"}:
                return None
            if now >= job["deadline"]:
                self.db.execute("UPDATE jobs SET state='escalated',closed_at=? WHERE job_id=?", (now, job_id))
                self.event(now, job_id, "escalated", owner="coordinator")
                return None
            if job["state"] == "submitted":
                return None
            if job["state"] == "leased" and now < job["lease_until"]:
                if actor == job["owner"]:
                    self.event(now, job_id, "grant_replayed", actor=actor)
                    return self.get(job_id)
                return None
            if job["attempts"] >= 3:
                self.db.execute("UPDATE jobs SET state='escalated',closed_at=? WHERE job_id=?", (now, job_id))
                self.event(now, job_id, "escalated", owner="coordinator", reason="grant_budget")
                return None
            self.db.execute("UPDATE jobs SET state='leased',owner=?,epoch=epoch+1,lease_until=?,attempts=attempts+1 WHERE job_id=?",
                            (actor, min(now + lease, job["deadline"]), job_id))
            self.event(now, job_id, "granted", actor=actor, epoch=job["epoch"] + 1)
            return self.get(job_id)

    def envelope(self, grant, payload, message_id, now):
        return {"schema_version": "coordination-local-1", "message_id": message_id,
                "job_id": grant["job_id"], "task_id": grant["task_id"],
                "parent_task_id": grant["task_id"], "sender": grant["owner"],
                "recipient": "coordinator", "stage": grant["stage"],
                "revision": grant["revision"], "epoch": grant["epoch"],
                "lease_until": grant["lease_until"], "sent_at": now,
                "deadline": grant["deadline"], "candidate_id": message_id + ":candidate", "payload": payload}

    def submit(self, message, actor, now):
        validate_message(message)
        with self.transaction():
            self.charge()
            job_id = message["job_id"]
            old = self.db.execute("SELECT * FROM receipts WHERE actor=? AND message_id=?",
                                  (actor, message["message_id"])).fetchone()
            if old:
                if old["body_digest"] != digest(message):
                    self.event(now, job_id, "message_rejected", reason="duplicate_conflict")
                    return {"accepted": False, "reason": "duplicate_conflict"}
                self.event(now, job_id, "receipt_replayed", message_id=message["message_id"])
                return json.loads(old["response_json"])
            job = self.get(job_id)
            reason = None
            if not job:
                reason = "unknown_job"
            elif actor != message["sender"] or actor != job["owner"]:
                reason = "identity"
            elif (message["task_id"], message["parent_task_id"], message["revision"], message["stage"], message["deadline"]) != (
                    job["task_id"], job["task_id"], job["revision"], job["stage"], job["deadline"]):
                reason = "task_binding"
            elif job["state"] != "leased":
                reason = "state"
            elif message["epoch"] != job["epoch"] or message["lease_until"] != job["lease_until"]:
                reason = "assignment"
            elif now >= min(job["lease_until"], job["deadline"]) or message["sent_at"] > now:
                reason = "expired_or_clock"
            response = {"accepted": reason is None, "reason": reason, "candidate_id": message["candidate_id"]}
            if reason is None:
                self.db.execute("UPDATE jobs SET state='submitted',candidate_id=?,result_json=? WHERE job_id=?",
                                (message["candidate_id"], canonical(message["payload"]), job_id))
            self.db.execute("INSERT INTO receipts VALUES(?,?,?,?)", (actor, message["message_id"], digest(message), canonical(response)))
            self.event(now, job_id, "candidate_accepted" if reason is None else "message_rejected",
                       reason=reason, message=message)
            return response

    def close_candidate(self, job_id, candidate_id, now, passed=True):
        with self.transaction():
            self.charge()
            job = self.get(job_id)
            if not job or job["state"] != "submitted" or job["candidate_id"] != candidate_id or now >= job["deadline"]:
                self.event(now, job_id, "verification_rejected", candidate_id=candidate_id)
                return False
            state = "closed" if passed else "ready"
            self.db.execute("UPDATE jobs SET state=?,closed_at=? WHERE job_id=?", (state, now if passed else None, job_id))
            self.event(now, job_id, "closed" if passed else "candidate_returned", candidate_id=candidate_id)
            return True

    def renew(self, job_id, actor, epoch, now):
        with self.transaction():
            self.charge()
            job = self.get(job_id)
            valid = bool(job and job["state"] == "leased" and job["owner"] == actor and job["epoch"] == epoch
                         and now < job["lease_until"] and now + 1 < job["deadline"])
            if valid:
                self.db.execute("UPDATE jobs SET lease_until=? WHERE job_id=?", (min(now+6, job["deadline"]), job_id))
            self.event(now, job_id, "renewed" if valid else "renew_rejected", actor=actor, epoch=epoch)
            return valid

    def cancel(self, job_id, now):
        with self.transaction():
            self.charge()
            job = self.get(job_id)
            if not job or job["state"] in {"closed", "escalated"}:
                raise Rejected("cancel_terminal")
            self.db.execute("UPDATE jobs SET state='cancelled',closed_at=? WHERE job_id=?", (now, job_id))
            self.event(now, job_id, "cancelled", owner="coordinator")

    def events(self):
        return [{"seq": r[0], "tick": r[1], "job_id": r[2], "kind": r[3], "detail": json.loads(r[4])}
                for r in self.db.execute("SELECT * FROM coordination_events ORDER BY seq")]

    def close(self):
        self.db.close()
