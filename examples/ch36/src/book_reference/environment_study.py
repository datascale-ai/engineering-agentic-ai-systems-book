"""Two local structured-view environments and bounded open/closed-loop policies."""
from collections import deque
from copy import deepcopy

from .contracts import Rejected, canonical, digest
from .project2 import DATA, load, save

TARGET = {"amount": 250, "category": "境内常规", "description": "教学申请"}


class EnvironmentAdapter:
    """Controlled single-process service: versions, request receipts and episodes.

    Policy code sees observe/act/query/reset results only. The grader alone uses
    score(). The grid supplies a known base map and observable dynamic updates;
    it is not a pixel browser, learned perception system or physical robot.
    """
    def __init__(self, case, seed, limits):
        self.kind, self.fault = case["environment"], case["fault"]
        self.task_id, self.seed, self.limits = case["task_id"], seed, limits
        self.episode, self.version, self.now = f'{case["task_id"]}:{seed}', 1, 1000
        self.fields, self.saved, self.submitted = {}, False, False
        self.position, self.goal, self.blocks = (1, 1), (1, 4), set()
        self.save_x = 3 + seed % 2
        self.overlay, self.approved = False, True
        self.actions, self.observations, self.queries, self.moves = 0, 0, 0, 0
        self.receipts, self.pending, self.events = {}, {}, []
        self.triggered, self.fault_at, self.recovered_at = False, None, None
        self.wrong_effects, self.rejected_requests = 0, 0
        self.submit_count, self.last_receipt = 0, None
        if self.fault in {"old_episode", "pending_reset"}:
            self.pending["old-action"] = {"episode": "old-episode", "due": 999999, "action": "move", "basis": 0}
            self.triggered, self.fault_at = True, self.now

    def event(self, kind, **details):
        self.events.append({"seq": len(self.events)+1, "time_ms": self.now, "episode": self.episode,
                            "actor": "environment", "kind": kind, "details": deepcopy(details)})

    def budget(self, name):
        if self.now - 1000 >= self.limits["deadline_ms"] or getattr(self, name) >= self.limits[name]:
            raise Rejected("environment_budget:" + name)
        setattr(self, name, getattr(self, name) + 1)

    def inject(self, point):
        if self.triggered:
            return
        changed = False
        if self.fault == "button_moved" and point == "first_observation":
            self.save_x += 2
            changed = True
        elif self.fault == "overlay" and point == "filled":
            self.overlay = True
            changed = True
        elif self.fault == "external_edit" and point == "filled":
            self.fields["amount"] = 260
            changed = True
        elif self.fault == "approval_revoked" and point == "saved":
            self.approved = False
            changed = True
        elif point == "first_move" and self.fault in {"goal_moved", "obstacle", "blocked"}:
            if self.fault == "goal_moved":
                self.goal = (3, 4)
            elif self.fault == "obstacle":
                self.blocks.add((1, 3))
            else:
                self.blocks = {(1, 3), (0, 2), (2, 2), (1, 1)}
            changed = True
        if changed:
            self.version += 1
            self.triggered, self.fault_at = True, self.now
            self.event("fault_injected", fault=self.fault, trigger=point)

    def observe(self):
        self.budget("observations")
        self.now += 50
        view = {"episode": self.episode, "version": self.version, "captured_ms": self.now,
                "received_ms": self.now, "pending_count": len(self.pending), "kind": self.kind}
        if self.kind == "form":
            view.update(fields=deepcopy(self.fields), saved=self.saved, submitted=self.submitted,
                        save_x=None if self.overlay else self.save_x, overlay=self.overlay, approved=self.approved)
            if self.fault == "stale_capture" and not self.triggered:
                view["captured_ms"] -= 500
                self.triggered, self.fault_at = True, self.now
                self.event("fault_injected", fault=self.fault, trigger="first_observation")
        else:
            view.update(position=list(self.position), goal=list(self.goal),
                        blocks=[list(p) for p in sorted(self.blocks)], unknown=[], grid_size=5)
            if self.fault == "position_noise" and self.observations == 2 and not self.triggered:
                view["position"] = [self.position[0], min(4, self.position[1]+1)]
                self.triggered, self.fault_at = True, self.now
                self.event("fault_injected", fault=self.fault, trigger="second_observation")
            if self.fault == "occlusion" and self.observations == 2 and not self.triggered:
                view["unknown"] = [[1, 3]]
                self.triggered, self.fault_at = True, self.now
                self.event("fault_injected", fault=self.fault, trigger="second_observation")
        self.event("observation", view=view)
        if self.observations == 1:
            self.inject("first_observation")
        return view

    def reject(self, request, reason):
        self.rejected_requests += 1
        result = {"status": "rejected", "reason": reason, "episode": self.episode, "version": self.version}
        self.event("request_rejected", request=request, result=result)
        return result

    def act(self, request):
        self.budget("actions")
        self.now += 50
        action_id = request["action_id"]
        if action_id in self.receipts:
            receipt = self.receipts[action_id]
            if receipt["request_digest"] != digest(request):
                return self.reject(request, "request_id_conflict")
            self.event("receipt_replayed", action_id=action_id)
            return deepcopy(receipt["result"])
        if request["episode"] != self.episode:
            return self.reject(request, "episode")
        if request["basis"] != self.version or self.now - request["captured_ms"] > 250:
            return self.reject(request, "stale_basis")
        action = request["action"]
        if self.kind == "form" and action == "submit" and not self.approved:
            return self.reject(request, "approval_expired")
        if self.overlay and action != "dismiss":
            return self.reject(request, "occluded")
        delayed = (self.fault == "save_delayed" and action == "save" or
                   self.fault == "move_delayed" and action == "move" and self.moves == 1)
        failed = (self.fault == "save_failed" and action == "save" or
                  self.fault == "move_failed" and action == "move" and self.moves == 1)
        if not self.triggered and (delayed or failed):
            self.triggered, self.fault_at = True, self.now
            self.event("fault_injected", fault=self.fault, trigger="action")
            if failed:
                result = {"status": "failed", "reason": "explicit_no_effect", "episode": self.episode, "version": self.version}
                self.receipts[action_id] = {"request_digest": digest(request), "result": result}
                self.event("action_failed", request=request, result=result)
                return result
            self.pending[action_id] = {"request": deepcopy(request), "episode": request["episode"],
                                       "due": self.now + (800 if self.kind == "form" else 1000)}
            self.event("action_pending", request=request)
            return {"status": "pending", "action_id": action_id, "episode": self.episode}
        result = self.perform(request)
        if not self.triggered and result["status"] == "done" and (
                self.fault == "submit_ack_lost" and action == "submit" or
                self.fault == "move_ack_lost" and action == "move" and self.moves == 2):
            self.triggered, self.fault_at = True, self.now
            self.event("fault_injected", fault=self.fault, trigger="committed_then_receipt_lost")
            return {"status": "unknown", "action_id": action_id, "episode": self.episode}
        return result

    def perform(self, request):
        action, action_id = request["action"], request["action_id"]
        before = {"episode": self.episode, "version": self.version, "position": list(self.position),
                  "blocks": [list(p) for p in sorted(self.blocks)], "approved": self.approved,
                  "fields": deepcopy(self.fields), "submitted": self.submitted, "save_x": self.save_x}
        if request["episode"] != self.episode or request["basis"] != self.version:
            return self.reject(request, "execution_precondition")
        if self.kind == "form":
            if action == "fill":
                self.fields, self.saved = deepcopy(request["fields"]), False
            elif action == "dismiss" and self.overlay:
                self.overlay = False
            elif action == "save" and request["x"] == self.save_x and self.fields == TARGET:
                self.saved = True
            elif action == "submit" and self.saved and self.fields == TARGET and self.approved and not self.submitted:
                self.submitted, self.submit_count, self.last_receipt = True, self.submit_count + 1, action_id
            else:
                return self.reject(request, "form_precondition")
        else:
            if action != "move":
                return self.reject(request, "action_not_allowed")
            destination = tuple(request["destination"])
            distance = sum(abs(a-b) for a, b in zip(destination, self.position))
            if distance != 1 or any(x < 0 or x >= 5 for x in destination) or destination in self.blocks:
                return self.reject(request, "blocked_or_invalid_move")
            self.position = destination
            self.moves += 1
        self.version += 1
        result = {"status": "done", "action_id": action_id, "episode": self.episode, "version": self.version,
                  "position": list(self.position) if self.kind == "grid" else None}
        self.receipts[action_id] = {"request_digest": digest(request), "result": deepcopy(result)}
        self.event("action_committed", request=request, result=result, before=before)
        if self.triggered and self.recovered_at is None and self.fault not in {"old_episode", "pending_reset"}:
            self.recovered_at = self.now
        self.inject("filled" if action == "fill" else "saved" if action == "save" else "first_move" if self.moves == 1 else "other")
        return result

    def query(self, action_id):
        self.budget("queries")
        self.now += 100
        pending = self.pending.get(action_id)
        if pending and self.now >= pending["due"]:
            self.perform(pending["request"])
            del self.pending[action_id]
        result = deepcopy(self.receipts[action_id]["result"]) if action_id in self.receipts else {
            "status": "pending" if pending else "unknown", "action_id": action_id,
            "episode": pending["episode"] if pending else self.episode}
        self.event("status_query", action_id=action_id, result=result)
        if result["status"] == "done" and self.triggered and self.recovered_at is None:
            self.recovered_at = self.now
        return result

    def reset(self):
        self.now += 50
        if self.pending:
            self.event("reset_rejected", reason="pending_actions", pending_ids=list(self.pending))
            return {"status": "rejected", "reason": "pending_actions", "episode": self.episode}
        raise Rejected("new_instance_required_for_new_trial")

    def cancel_pending(self):
        self.budget("actions")
        self.now += 50
        # The fixture intentionally cannot establish cancellation of the old request.
        self.event("cancellation_unknown", pending_ids=list(self.pending))
        return {"status": "unknown", "episode": "old-episode", "pending_ids": list(self.pending)}

    def score(self):
        wrong = 0
        for event in self.events:
            if event["kind"] != "action_committed":
                continue
            request, before = event["details"]["request"], event["details"]["before"]
            legal = request["episode"] == before["episode"] and request["basis"] == before["version"]
            if request["action"] == "submit":
                legal = legal and before["approved"] and before["fields"] == TARGET and not before["submitted"]
            elif request["action"] == "save":
                legal = legal and request["x"] == before["save_x"] and before["fields"] == TARGET
            elif request["action"] == "move":
                destination = request["destination"]
                legal = legal and all(0 <= p < 5 for p in destination) and destination not in before["blocks"]
                legal = legal and sum(abs(a-b) for a, b in zip(destination, before["position"])) == 1
            wrong += int(not legal)
        postcondition = (self.fields == TARGET and self.saved and self.submitted and self.submit_count == 1 and
                         self.last_receipt in self.receipts) if self.kind == "form" else self.position == self.goal
        return {"postcondition": postcondition, "wrong_effects": wrong,
                "submit_count": self.submit_count, "pending_count": len(self.pending),
                "position": list(self.position), "goal": list(self.goal), "fields": self.fields,
                "fault_triggered": self.triggered, "fault_time_ms": self.fault_at,
                "recovered_time_ms": self.recovered_at}


def route(view):
    start, goal = tuple(view["position"]), tuple(view["goal"])
    blocked = {tuple(p) for p in view["blocks"] + view["unknown"]}
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        pos, path = queue.popleft()
        if pos == goal:
            return path
        for dy, dx in ((0, 1), (1, 0), (-1, 0), (0, -1)):
            nxt = (pos[0]+dy, pos[1]+dx)
            if all(0 <= v < view["grid_size"] for v in nxt) and nxt not in blocked and nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, path + [list(nxt)]))
    return None


def run_policy(env, method):
    """No fault ID or grading state is accessed by this controller."""
    view, last_position = env.observe(), None
    actions, reason, confirmed = [], "step_limit", False
    if view["pending_count"]:
        reset = env.reset()
        old_feedback = env.cancel_pending()
        return {"reason": "pending_handoff", "confirmed": False, "ignored_old_episode": old_feedback["episode"] != view["episode"],
                "reset_rejected": reset["status"] == "rejected", "action_ids": []}
    initial_plan = ["fill", "save", "submit"] if view["kind"] == "form" else route(view)
    while len(actions) < env.limits["actions"]:
        if method == "C" and actions:
            view = env.observe()
        if view["received_ms"] - view["captured_ms"] > 250:
            if method == "C":
                view = env.observe()
                continue
            reason = "stale_observation"
            break
        if view["kind"] == "form":
            if method == "O":
                if len(actions) >= len(initial_plan):
                    confirmed, reason = True, "plan_finished"
                    break
                action = initial_plan[len(actions)]
            elif view["submitted"]:
                confirmed, reason = True, "postcondition_observed"
                break
            elif view["overlay"]:
                action = "dismiss"
            elif view["fields"] != TARGET:
                action = "fill"
            elif not view["saved"]:
                action = "save"
            elif not view["approved"]:
                reason = "approval_required"
                break
            else:
                action = "submit"
            arguments = {"fields": TARGET} if action == "fill" else {"x": view["save_x"]} if action == "save" else {}
        else:
            if method == "C" and last_position is not None and view["position"] != last_position:
                # An observation contradicts the last committed location: obtain another view.
                view = env.observe()
                if view["position"] != last_position:
                    reason = "position_conflict"
                    break
            path = route(view) if method == "C" else initial_plan[len(actions):]
            if not path:
                confirmed = view["position"] == view["goal"]
                reason = "goal_observed" if confirmed else "no_confirmed_path"
                break
            action, arguments = "move", {"destination": path[0]}
        request = {"action_id": view["episode"] + ":" + str(len(actions)+1), "episode": view["episode"],
                   "basis": view["version"], "captured_ms": view["captured_ms"], "action": action, **arguments}
        actions.append(request["action_id"])
        feedback = env.act(request)
        if feedback["status"] in {"pending", "unknown"}:
            if method == "O":
                reason = "outcome_unknown"
                break
            while feedback["status"] in {"pending", "unknown"}:
                feedback = env.query(request["action_id"])
        if feedback["episode"] != view["episode"]:
            reason = "old_episode_feedback"
            break
        if feedback["status"] in {"rejected", "failed"}:
            if method == "C" and feedback.get("reason") not in {"approval_expired", "episode"}:
                continue
            reason = feedback.get("reason", feedback["status"])
            break
        view["version"] = feedback["version"]
        # ACK supplies its commit instant; later external changes are not disclosed.
        view["captured_ms"] = env.now
        if view["kind"] == "grid":
            view["position"] = feedback["position"]
            last_position = feedback["position"]
    return {"reason": reason, "confirmed": confirmed, "action_ids": actions,
            "ignored_old_episode": False, "reset_rejected": False}


def run_environments(output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = load(DATA / "study_manifest.json")
    rows, traces = [], []
    for case in load(DATA / "environment_cases.json"):
        for seed in manifest["seeds"]:
            for method in ("O", "C"):
                env = EnvironmentAdapter(case, seed, manifest["environment"])
                try:
                    result = run_policy(env, method)
                except Rejected as error:
                    result = {"reason": str(error), "confirmed": False, "action_ids": [],
                              "ignored_old_episode": False, "reset_rejected": False}
                score = env.score()
                safe = score["wrong_effects"] == 0 and score["submit_count"] <= 1
                if case["fault"] in {"old_episode", "pending_reset"}:
                    safe = safe and result["reset_rejected"] and result["ignored_old_episode"] and score["pending_count"] == 1
                row = {"task_id": case["task_id"], "environment": case["environment"], "fault": case["fault"],
                       "seed": seed, "method": method, "result": result, "oracle": score,
                       "business_success": result["confirmed"] and score["postcondition"] and safe,
                       "constraint_handling_passed": safe, "actions": env.actions, "observations": env.observations,
                       "reobservations": max(0, env.observations-1), "queries": env.queries,
                       "blocked_requests": env.rejected_requests, "virtual_elapsed_ms": env.now-1000,
                       "recovery_ms": None if env.recovered_at is None else env.recovered_at-env.fault_at,
                       "unrecovered": env.fault_at is not None and env.recovered_at is None}
                row["normal_path_passed"] = case["fault"] != "normal" or row["business_success"]
                rows.append(row)
                traces.extend({"task_id": case["task_id"], "seed": seed, "method": method, **event} for event in env.events)
    groups = {}
    for kind in ("form", "grid"):
        for method in ("O", "C"):
            chosen = [r for r in rows if r["environment"] == kind and r["method"] == method]
            groups[kind + "-" + method] = {"trials": len(chosen), "business_success": sum(r["business_success"] for r in chosen),
                "constraint_handling_passed": sum(r["constraint_handling_passed"] for r in chosen),
                "actions": sum(r["actions"] for r in chosen), "reobservations": sum(r["reobservations"] for r in chosen),
                "queries": sum(r["queries"] for r in chosen), "blocked_requests": sum(r["blocked_requests"] for r in chosen),
                "wrong_effects": sum(r["oracle"]["wrong_effects"] for r in chosen),
                "unrecovered": sum(r["unrecovered"] for r in chosen)}
    report = {"experiment": "Exp-21-01-local", "tasks": 20, "trials": len(rows), "seeds": manifest["seeds"], "groups": groups,
              "capability": manifest["environment"]["capability"],
              "scope": "known base map and structured views; deterministic policies; no browser pixels or physical device",
              "passed": len(rows) == 200 and all(r["constraint_handling_passed"] and r["normal_path_passed"] for r in rows)}
    for name, values in (("trials.jsonl", rows), ("events.jsonl", traces)):
        (output / name).write_text("".join(canonical(r) + "\n" for r in values), encoding="utf-8", newline="\n")
    save(output / "report.json", report)
    return report
