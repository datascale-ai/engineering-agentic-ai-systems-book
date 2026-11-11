"""Shared, deliberately small contracts. JSON schemas live in this module only."""
from dataclasses import dataclass
import hashlib
import json


class Rejected(ValueError):
    """A known validation or authorization rejection with a stable reason code."""


class SimulatedCrash(RuntimeError):
    """An explicit test hook; never a claim to emulate every process failure."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def validate_task(task):
    required = {"schema_version", "task_id", "tenant", "revision", "assignment_epoch",
                "amount", "domestic", "receipt_valid", "policy_version"}
    if not isinstance(task, dict) or set(task) != required:
        raise Rejected("task_fields")
    if task["schema_version"] != "demo-1":
        raise Rejected("task_schema_version")
    for key in ("task_id", "tenant", "policy_version"):
        if not isinstance(task[key], str) or not task[key] or len(task[key]) > 120:
            raise Rejected("task_identifier")
    for key in ("revision", "assignment_epoch", "amount"):
        if type(task[key]) is not int or task[key] < (0 if key == "amount" else 1):
            raise Rejected("task_integer")
    if type(task["domestic"]) is not bool or type(task["receipt_valid"]) is not bool:
        raise Rejected("task_boolean")
    return dict(task)


def policy_decision(task, policy):
    if task["policy_version"] != policy["version"]:
        raise Rejected("policy_version")
    if task["amount"] > policy["amount_limit"] or not task["domestic"] or not task["receipt_valid"]:
        return "ineligible"
    # This minimal slice deliberately accepts only amounts not requiring supervisor approval.
    if task["amount"] > policy["supervisor_threshold"]:
        return "needs_approval"
    return "eligible"


def payload_for(task):
    return {key: task[key] for key in ("task_id", "revision", "amount", "domestic",
                                      "receipt_valid", "policy_version")}


@dataclass(frozen=True)
class Approval:
    """An in-process trusted fixture grant, not a cryptographic approval token."""
    tenant: str
    payload_digest: str
    expires_at_ms: int
    permitted: bool = True


class ReplyGate:
    """Bind a proposal to the current task and reject altered duplicate messages."""
    def __init__(self):
        self.accepted = {}

    def accept(self, task, reply):
        expected = {"message_id", "task_id", "revision", "assignment_epoch", "decision", "evidence"}
        if not isinstance(reply, dict) or set(reply) != expected:
            raise Rejected("reply_fields")
        if reply["task_id"] != task["task_id"]:
            raise Rejected("reply_task")
        for key in ("revision", "assignment_epoch"):
            if type(reply[key]) is not int or reply[key] != task[key]:
                raise Rejected("reply_" + key)
        if not isinstance(reply["message_id"], str) or not reply["message_id"]:
            raise Rejected("reply_message_id")
        if not isinstance(reply["decision"], str) or reply["decision"] not in {"eligible", "ineligible", "needs_approval"}:
            raise Rejected("reply_decision")
        if not isinstance(reply["evidence"], list) or not reply["evidence"] or not all(isinstance(x, str) and x for x in reply["evidence"]):
            raise Rejected("reply_evidence")
        key = (task["tenant"], task["task_id"], reply["message_id"])
        value = digest(reply)
        if key in self.accepted:
            if self.accepted[key] != value:
                raise Rejected("reply_duplicate_conflict")
            return False
        self.accepted[key] = value
        return True
