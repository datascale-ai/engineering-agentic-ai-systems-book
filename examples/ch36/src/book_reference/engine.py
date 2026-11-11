"""A bounded local workflow with persistent intent and explicit verification."""
import json
from .contracts import Rejected, ReplyGate, SimulatedCrash, canonical, payload_for, policy_decision, validate_task


class Engine:
    def __init__(self, store, service, model, clock, policy, max_attempts=2, deadline_ms=5000):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
            raise Rejected("attempt_configuration")
        if type(deadline_ms) is not int or deadline_ms < 0:
            raise Rejected("deadline_configuration")
        self.store, self.service, self.model, self.clock = store, service, model, clock
        self.policy, self.max_attempts, self.deadline_ms = policy, max_attempts, deadline_ms

    def _finish_cancelled(self, task, state):
        if state["operation_id"]:
            try:
                ticket_id = self.service.lookup(task["tenant"], state["operation_id"], json.loads(state["payload_json"]))
            except TimeoutError:
                return self.store.transition(task, "cancelled", "cancelled_outcome_unknown", reason="outcome_unknown")
            self.store.transition(task, "cancelled", "cancelled_outcome_checked", ticket_id=ticket_id)
        return self.store.get(task)

    def run(self, raw_task, approval, project="PRJ-1", fault=None):
        if project not in {"PRJ-1", "PRJ-2", "PRJ-3"}:
            raise Rejected("project")
        if fault not in {None, "before_send", "after_commit", "cancel_after_commit", "response_lost"}:
            raise Rejected("fault")
        task = validate_task(raw_task)
        state = self.store.ensure(task)
        if state["status"] == "cancelled":
            return self._finish_cancelled(task, state)
        if state["status"] in {"completed", "rejected"}:
            return state
        if state["payload_json"] is None:
            try:
                proposal = self.model.propose(task)
                ReplyGate().accept(task, proposal)
                self.store.transition(task, "new", "proposal_accepted", reason=None)
                decision = policy_decision(task, self.policy)
                required = {self.policy["version"] + "#1", self.policy["version"] + "#2"}
                if proposal["decision"] != decision or not required <= set(proposal["evidence"]):
                    raise Rejected("proposal_not_supported")
                if decision != "eligible":
                    raise Rejected(decision)
                if project != "PRJ-1":
                    self.store.transition(task, "new", "research_verified", reason=None)
                payload = payload_for(task)
                # Stable for the same tenant/task/revision; no new key on recovery.
                operation_id = f'{task["task_id"]}:{task["revision"]}:create'
                state = self.store.transition(task, "pending", "intent_saved", operation_id=operation_id,
                                              payload_json=canonical(payload))
            except Rejected as error:
                return self.store.transition(task, "rejected", "rejected", reason=str(error))
        payload = json.loads(state["payload_json"])
        if fault == "before_send":
            raise SimulatedCrash("before_send")
        try:
            ticket_id = self.service.lookup(task["tenant"], state["operation_id"], payload)
        except TimeoutError:
            return self.store.transition(task, "pending", "outcome_unknown", reason="lookup_timeout")
        if ticket_id is None:
            if self.clock.now_ms >= self.deadline_ms:
                return self.store.transition(task, "rejected", "deadline_reached", reason="deadline")
            if state["attempts"] >= self.max_attempts:
                return self.store.transition(task, "rejected", "budget_reached", reason="attempt_budget")
            state = self.store.transition(task, "pending", "action_requested", attempts=state["attempts"]+1)
            try:
                ticket_id = self.service.create(task["tenant"], state["operation_id"], payload, approval, self.clock.now_ms)
            except TimeoutError:
                return self.store.transition(task, "pending", "response_unknown", reason="response_timeout")
            except Rejected as error:
                return self.store.transition(task, "rejected", "action_rejected", reason=str(error))
            if fault == "after_commit":
                raise SimulatedCrash("after_service_commit_before_client_receipt")
            if fault == "cancel_after_commit":
                self.store.cancel(task)
                return self._finish_cancelled(task, self.store.get(task))
            if fault == "response_lost":
                self.store.transition(task, "pending", "response_unknown", reason="response_lost")
                try:
                    ticket_id = self.service.lookup(task["tenant"], state["operation_id"], payload)
                except TimeoutError:
                    return self.store.transition(task, "pending", "outcome_unknown", reason="lookup_timeout")
        else:
            self.store.transition(task, "pending", "outcome_resolved", ticket_id=ticket_id)
        if ticket_id is None or not self.service.verify(task["tenant"], ticket_id, payload):
            return self.store.transition(task, "pending", "verification_pending", reason="postcondition_unknown")
        self.store.transition(task, "pending", "postcondition_verified", ticket_id=ticket_id, reason=None)
        return self.store.transition(task, "completed", "completed", ticket_id=ticket_id, reason=None)
