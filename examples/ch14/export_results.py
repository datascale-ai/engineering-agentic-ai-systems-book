"""Reproduce manuscript tables; this script does not invoke external services."""
import csv
import json
from pathlib import Path

from representation_experiment import measure

HERE = Path(__file__).resolve().parent


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    cases = [json.loads(s) for s in HERE.joinpath("state_update_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    report = measure(cases)
    results.joinpath("representation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(results / "representation_summary.csv", report["summary"])
    capacity_rows = []
    for limit in (120, 240, 480, 960, 1920):
        sample = measure(cases, limit)
        row = next(s for s in sample["summary"] if s["strategy"] == "recent_summary")
        capacity_rows.append({"summary_limit_codepoints": limit, **row})
    write_csv(results / "summary_capacity.csv", capacity_rows)
    print("Exported main report and two manuscript tables.")
