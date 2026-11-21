"""Same script model, three orchestration methods; not LLM capability evidence."""
from collections import Counter
from itertools import product
import math
from time import perf_counter

from .contracts import Rejected, canonical, digest
from .project2 import DATA, load, save

LABELS = ("eligible", "ineligible", "needs_approval", "insufficient_evidence")


def rule_check(case):
    """Explicit finite uncertainty, with no access to the frozen answer key."""
    amounts = case["amount"] if isinstance(case["amount"], list) else [case["amount"]]
    if amounts == [None]:
        amounts = [0, 301, 401, 501]
    versions = [400 if case["date"] < "2026-07-01" else 300] if case["date"] else [400, 300]
    bools = lambda value: [False, True] if value is None else [value]
    possible = set()
    for amount, threshold, domestic, receipt, approval in product(
            amounts, versions, bools(case["domestic"]), bools(case["receipt_valid"]), bools(case["approval"])):
        possible.add("ineligible" if amount > 500 or not domestic or not receipt else
                     "needs_approval" if amount > threshold and not approval else "eligible")
    return next(iter(possible)) if len(possible) == 1 else "insufficient_evidence"


class ScriptModel:
    """A fault-injecting deterministic substitute, whose review mode checks rules.

    The review mode is intentionally stronger by construction. Differences
    therefore describe this programmed workflow, not learned role behaviour.
    """
    def __init__(self, cap=24000, reserve=4000, max_calls=6):
        self.cap, self.reserve, self.max_calls = cap, reserve, max_calls
        self.used, self.calls, self.messages = 0, 0, []

    def propose(self, case, seed, member, history=(), review=False):
        request = {"model": "ScriptModel-v1", "case": case, "seed": seed, "member": member,
                   "policies": load(DATA / "policy_versions.json"), "history": list(history), "review": review}
        request_bytes = len(canonical(request).encode("utf-8"))
        if self.calls >= self.max_calls or self.used + request_bytes + 1024 > self.cap - (0 if review else self.reserve):
            raise Rejected("debate_budget")
        label = rule_check(case)
        common = int(digest({"case": case, "seed": seed})[:8], 16)
        individual = int(digest({"case": case, "seed": seed, "member": member})[:8], 16)
        if not review and common % 4 == 0:
            label = "eligible"  # deliberately correlated omission of constraints
        elif not review and individual % 7 == 0:
            label = LABELS[(LABELS.index(label) + 1) % len(LABELS)]
        version = "P20-A@1.0" if case["date"] and case["date"] < "2026-07-01" else "P20-A@2.0"
        versions = ["P20-A@1.0", "P20-A@2.0"] if review and case["date"] is None else [version]
        response = {"member": member, "label": label, "evidence": [v + suffix for v in versions for suffix in ("#eligibility", "#approval")],
                    "case_digest": digest(case), "reviewed_claims": [x["member"] for x in history] if review else []}
        used = request_bytes + len(canonical(response).encode("utf-8"))
        if self.used + used > self.cap:
            raise Rejected("debate_budget")
        self.used += used
        self.calls += 1
        self.messages.append({"request": request, "response": response, "serialized_utf8_bytes": used})
        return response


def evidence_check(case, response):
    versions = {"P20-A@1.0", "P20-A@2.0"} if case["date"] is None else {
        "P20-A@1.0" if case["date"] < "2026-07-01" else "P20-A@2.0"}
    needed = {v + suffix for v in versions for suffix in ("#eligibility", "#approval")}
    return bool(response and response["case_digest"] == digest(case) and response["label"] == rule_check(case)
                and needed <= set(response["evidence"]))


def decide(case, seed, method, parameters):
    model = ScriptModel(parameters["root_serialized_bytes"], parameters["reserve_bytes"], parameters["max_model_calls"])
    started = perf_counter()
    members, review = [], []
    try:
        members = [model.propose(case, seed, f"member-{i}") for i in range(1 if method == "single" else 3)]
        if method == "single":
            label = members[0]["label"]
        elif method == "vote":
            votes = Counter(x["label"] for x in members)
            label, count = votes.most_common(1)[0]
            if count < 2:
                label = "unresolved"
        elif method == "debate":
            review = [model.propose(case, seed, role, members, review=True) for role in ("rule-reviewer", "counterevidence-reviewer")]
            label = review[0]["label"] if review[0]["label"] == review[1]["label"] else "unresolved"
        else:
            raise ValueError("unknown method")
        stop = "key_facts_missing" if label == "insufficient_evidence" else "no_majority" if label == "unresolved" else "bounded_decision"
    except Rejected:
        label, stop = "unresolved", "budget_exhausted"
    return {"task_id": case["task_id"], "seed": seed, "method": method, "label": label,
            "members": members, "reviews": review, "stop_reason": stop,
            "member_consensus": None if method == "single" else len({m["label"] for m in members}) == 1,
            "calls": model.calls, "serialized_utf8_bytes": model.used,
            "budget_cap_bytes": model.cap, "budget_within_cap": model.used <= model.cap,
            "wall_ms": round((perf_counter() - started) * 1000, 3), "messages": model.messages,
            "actual_tokens": None, "money_cost": None}


def correlation(pairs):
    n = len(pairs)
    sx, sy = sum(x for x, _ in pairs), sum(y for _, y in pairs)
    den = math.sqrt(sx * (n-sx) * sy * (n-sy))
    return (n * sum(x*y for x, y in pairs) - sx*sy) / den if den else None


def run_debate(output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = load(DATA / "study_manifest.json")
    questions, expected = load(DATA / "questions.json"), load(DATA / "question_expected.json")
    rows, claims = [], []
    for seed in manifest["seeds"]:
        for case in questions:
            for method in ("single", "vote", "debate"):
                row = decide(case, seed, method, manifest["debate"])
                answer = expected[case["task_id"]]
                row["expected"] = answer
                row["correct"] = row["label"] == answer
                adopted = next((r for r in row["reviews"] + row["members"] if r["label"] == row["label"]), None)
                row["evidence_qualified"] = evidence_check(case, adopted)
                rows.append(row)
                if method == "debate":
                    counts = Counter(m["label"] for m in row["members"])
                    for member in row["members"]:
                        minority = counts[member["label"]] == 1 and any(v >= 2 for v in counts.values())
                        claims.append({"task_id": case["task_id"], "seed": seed, "claim": member,
                                       "minority": minority, "correct_counterevidence": minority and member["label"] == answer,
                                       "resolution": "supported" if member["label"] == row["label"] else "not_adopted_after_rule_review",
                                       "reviewers": [r["member"] for r in row["reviews"]]})
    groups = {}
    for method in ("single", "vote", "debate"):
        selected = [r for r in rows if r["method"] == method]
        determined = [r for r in selected if r["label"] in LABELS[:3]]
        groups[method] = {"trials": len(selected), "correct": sum(r["correct"] for r in selected),
                          "evidence_qualified": sum(r["evidence_qualified"] for r in selected),
                          "member_consensus": None if method == "single" else sum(r["member_consensus"] for r in selected),
                          "consensus_wrong": None if method == "single" else sum(r["member_consensus"] and r["members"][0]["label"] != r["expected"] for r in selected),
                          "determined_answers": len(determined), "determined_correct": sum(r["correct"] for r in determined),
                          "calls": sum(r["calls"] for r in selected),
                          "serialized_utf8_bytes": sum(r["serialized_utf8_bytes"] for r in selected),
                          "per_seed_correct": {str(seed): sum(r["correct"] for r in selected if r["seed"] == seed) for seed in manifest["seeds"]}}
    vote = [r for r in rows if r["method"] == "vote"]
    errors = [(int(r["members"][0]["label"] != r["expected"]), int(r["members"][1]["label"] != r["expected"])) for r in vote]
    minority = [c for c in claims if c["correct_counterevidence"]]
    report = {"experiment": "Exp-20-01-script", "model": "ScriptModel-v1", "questions": 20,
              "seeds": manifest["seeds"], "trials": len(rows), "groups": groups,
              "member_0_1_error_correlation": correlation(errors), "correct_minority_claims": len(minority),
              "correct_minority_reviewed": sum(len(c["reviewers"]) == 2 for c in minority),
              "scope": "programmed errors and deterministic rule review; no real model, tokens or price measurements",
              "passed": len(rows) == 300 and all(r["budget_within_cap"] for r in rows)
                        and all(rule_check(q) == expected[q["task_id"]] for q in questions)}
    for name, values in (("trials.jsonl", rows), ("claim_evidence_matrix.jsonl", claims)):
        (output / name).write_text("".join(canonical(r) + "\n" for r in values), encoding="utf-8", newline="\n")
    save(output / "report.json", report)
    return report
