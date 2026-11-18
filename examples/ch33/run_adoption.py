"""Declared business assumptions and executable revocation checks, no field data."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Directory:
    def __init__(self):
        self.grants = {"alice": {"A"}, "bob": {"B"}}
        self.epoch = 0
        self.cache = {}

    def read(self, subject, department):
        key = (subject, department, self.epoch)
        if key not in self.cache:
            self.cache[key] = department in self.grants.get(subject, set())
        return self.cache[key]

    def revoke(self, subject):
        self.grants.pop(subject, None)
        self.epoch += 1
        self.cache.clear()


def business_case(review_minutes=2, volume=1000):
    # CNY/month; source = explicit teaching assumptions.
    hourly = 120
    baseline = volume * 12 / 60 * hourly
    assist = volume * (4 + review_minutes + 0.1 * 6) / 60 * hourly + 1200 + 1800 + 1000
    action = volume * (2 + review_minutes + 0.05 * 8) / 60 * hourly + 1800 + 2400 + 1600
    return {
        "volume": volume,
        "review_minutes": review_minutes,
        "baseline_yuan": baseline,
        "assist_cost_yuan": round(assist, 2),
        "action_cost_yuan": round(action, 2),
        "assist_net_yuan": round(baseline - assist, 2),
        "action_net_yuan": round(baseline - action, 2),
    }


def simulate_flow(mode, review_minutes=2, tasks=60, arrival_interval=5):
    """Deterministic single-reviewer queue, time units are assumed minutes."""
    draft = {"manual": 8, "assist": 4, "approved_action": 2}[mode]
    review = 4 if mode == "manual" else review_minutes
    review_free = 0
    rows = []
    for index in range(tasks):
        arrival = index * arrival_interval
        ready = arrival + draft
        start = max(ready, review_free)
        finish = start + review
        review_free = finish
        rows.append(
            {
                "task_id": f"S{index + 1:02d}",
                "arrival": arrival,
                "review_ready": ready,
                "review_start": start,
                "finish": finish,
                "wait_minutes": start - ready,
                "elapsed_minutes": finish - arrival,
            }
        )
    return {
        "mode": mode,
        "review_minutes": review,
        "tasks": tasks,
        "mean_elapsed_minutes": sum(r["elapsed_minutes"] for r in rows) / tasks,
        "mean_wait_minutes": sum(r["wait_minutes"] for r in rows) / tasks,
        "human_review_minutes": review * tasks,
        "peak_waiting": max(
            sum(
                x["review_ready"] <= r["review_ready"] < x["review_start"] for x in rows
            )
            for r in rows
        ),
        "rows": rows,
    }


def run():
    directory = Directory()
    checks = {
        "A_read_A": directory.read("alice", "A"),
        "B_denied_A": not directory.read("bob", "A"),
    }
    directory.revoke("alice")
    checks["revocation_after_cached_read"] = not directory.read("alice", "A")
    report = {
        "kind": "declared_cost_scenarios_and_local_authorization",
        "checks": checks,
        "flow_simulation": [
            simulate_flow(m, r)
            for m, r in [
                ("manual", 4),
                ("assist", 2),
                ("approved_action", 2),
                ("assist", 6),
                ("approved_action", 6),
            ]
        ],
        "scenarios": [business_case(m, v) for v in [200, 1000] for m in [2, 6, 10]],
        "assumptions": {
            "hourly_yuan": 120,
            "baseline_minutes": 12,
            "assist_draft_minutes": 4,
            "action_operator_minutes": 2,
            "assist_rework_probability": 0.1,
            "assist_rework_minutes": 6,
            "action_rework_probability": 0.05,
            "action_rework_minutes": 8,
        },
    }
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
