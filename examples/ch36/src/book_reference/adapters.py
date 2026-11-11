"""Deterministic replacements for model and clock boundaries."""
from copy import deepcopy


class ControlledClock:
    def __init__(self, now_ms=1000):
        self.now_ms = now_ms

    def advance(self, milliseconds):
        if milliseconds < 0:
            raise ValueError("clock_must_not_go_backwards")
        self.now_ms += milliseconds


class FixedModel:
    def __init__(self, response):
        self.response = deepcopy(response)
        self.calls = 0

    def propose(self, task):
        self.calls += 1
        return {"message_id": "proposal-1", "task_id": task["task_id"],
                "revision": task["revision"], "assignment_epoch": task["assignment_epoch"],
                **deepcopy(self.response)}
