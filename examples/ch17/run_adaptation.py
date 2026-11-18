"""Executable policy patches under a fixed two-candidate budget.

Candidates are scripted programs, not LLM output. Independent input/output
cases evaluate repairs and holdouts. Results measure update acceptance only.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def decide(case, patch):
    if patch == "wrong_limit":
        return case["amount"] <= 1000
    if patch == "stale_policy":
        return case["version"] == 1 and case["amount"] <= case["limit"]
    if patch == "wrong_owner":
        return case["amount"] <= case["limit"]
    if patch == "overfit":
        return case["amount"] == 500
    if patch == "correct":
        return (
            case["version"] == 2
            and case["owner"] == case["caller"]
            and case["amount"] <= case["limit"]
        )
    raise ValueError(patch)


def validate(patch, cases):
    return all(decide(case, patch) == expected for case, expected in cases)


def accepted(proposal, current, validation):
    if (
        proposal["scope"] != current["scope"]
        or proposal["revision"] <= current["revision"]
    ):
        return False, "scope_or_revision"
    if not validation["repair_pass"] or not validation["holdout_pass"]:
        return False, "independent_validation_failed"
    return True, "validated"


def fixtures(index):
    base = {"amount": 500, "limit": 600, "version": 2, "owner": "u1", "caller": "u1"}
    kind = ["wrong_limit", "stale_policy", "wrong_owner"][index % 3]
    bad = dict(base)
    if kind == "wrong_limit":
        bad["amount"] = 800
    if kind == "wrong_owner":
        bad["owner"] = "u2"
    repair = [(bad, decide(bad, "correct"))]
    holdout = [
        (dict(base, amount=550), True),
        (dict(base, amount=700), False),
        (dict(base, owner="u2"), False),
        (dict(base, version=1), False),
    ]
    # Five first candidates pass the repair case but fail an unseen positive.
    first = "overfit" if index % 6 == 0 else ("correct" if index % 3 == 0 else kind)
    return kind, repair, holdout, first


def run():
    rows = []
    for index in range(30):
        kind, repair, holdout, first = fixtures(index)
        current = {"revision": 1, "scope": kind, "patch": kind}
        candidates = [
            {"revision": 2, "scope": kind, "patch": first, "self_rating": "pass"},
            {"revision": 3, "scope": kind, "patch": "correct", "self_rating": "pass"},
        ]
        for mode in ["no_update", "self_rating", "external_validation"]:
            active = dict(current)
            attempts = 0
            rejected = []
            for proposal in [] if mode == "no_update" else candidates:
                attempts += 1
                validation = {
                    "repair_pass": validate(proposal["patch"], repair),
                    "holdout_pass": validate(proposal["patch"], holdout),
                }
                ok = (
                    proposal["self_rating"] == "pass"
                    if mode == "self_rating"
                    else accepted(proposal, active, validation)[0]
                )
                if ok:
                    active = dict(proposal)
                    break
                rejected.append(
                    {"revision": proposal["revision"], "validation": validation}
                )
            rows.append(
                {
                    "task_id": f"F{index + 1:02d}",
                    "kind": kind,
                    "mode": mode,
                    "attempts": attempts,
                    "active_revision": active["revision"],
                    "patch": active["patch"],
                    "repaired": validate(active["patch"], repair),
                    "holdout_regression": not validate(active["patch"], holdout),
                    "rejected": rejected,
                    "repair_cases": repair,
                    "holdout_cases": holdout,
                }
            )
    summary = {
        m: {
            "tasks": 30,
            "repairs": sum(r["repaired"] for r in rows if r["mode"] == m),
            "holdout_failures": sum(
                r["holdout_regression"] for r in rows if r["mode"] == m
            ),
            "candidate_checks": sum(r["attempts"] for r in rows if r["mode"] == m),
        }
        for m in ["no_update", "self_rating", "external_validation"]
    }
    HERE.joinpath("reflection_update_log.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    )
    HERE.joinpath("results").mkdir(exist_ok=True)
    HERE.joinpath("results/report.json").write_text(
        json.dumps(
            {
                "kind": "scripted_program_patch_protocol",
                "candidate_budget": 2,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
