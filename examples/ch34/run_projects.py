"""One reproducible local runner for three architecture exercises."""

import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from d_shared.projects import Project, ProjectError, load_assets

HERE = Path(__file__).resolve().parent


def run(selected=None):
    documents, tasks = load_assets()
    summaries = {}
    faults = []
    samples = []
    for mode in [selected] if selected else ["PRJ-1", "PRJ-2", "PRJ-3"]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.db"
            project = Project(path, documents)
            rows = []
            for task in tasks:
                start = time.perf_counter()
                if mode == "PRJ-3":
                    result = list(project.stream(task))[-1]["result"]
                else:
                    result = project.run(task, mode)
                elapsed = (time.perf_counter() - start) * 1000
                rows.append(
                    {
                        "task_id": task["task_id"],
                        "correct": result["decision"] == task["expected_action"],
                        "decision": result["decision"],
                        "ticket_count": project.ticket_count(task["task_id"]),
                        "latency_ms": round(elapsed, 3),
                        "events": len(project.events(task["task_id"])),
                    }
                )
            ordered = sorted(r["latency_ms"] for r in rows)
            summaries[mode] = {
                "tasks": len(rows),
                "correct": sum(r["correct"] for r in rows),
                "tickets": sum(r["ticket_count"] for r in rows),
                "events": sum(r["events"] for r in rows),
                "p50_ms": round(statistics.median(ordered), 3),
                "p95_ms": ordered[int(0.95 * (len(ordered) - 1))],
                "llm_calls": 0,
                "external_service_calls": 0,
                "rows": rows,
            }
            samples.append(
                {
                    "project": mode,
                    "input": tasks[1],
                    "output": project.get(tasks[1]["task_id"])["result"],
                }
            )
        for fault in [
            "missing_evidence",
            "duplicate",
            "worker_lost",
            "cancel",
            "late_output",
            "wrong_release",
            "restart",
            "stream_cancel",
            "release_rollback",
        ]:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "fault.db"
                p = Project(path, documents)
                task = tasks[1]
                error = None
                try:
                    if fault == "restart":
                        p.open(task)
                        p.checkpoint(task["task_id"], p.research(task["task_id"]))
                        p = Project(path, documents)
                        list(p.stream(task))
                    elif fault == "stream_cancel":
                        stream = p.stream(task)
                        next(stream)
                        p.cancel(task["task_id"])
                        next(stream)
                    elif fault == "release_rollback":
                        p.open(task)
                        try:
                            Project(path, documents, release="bad-release").run(
                                task, mode
                            )
                        except ProjectError as exc:
                            error = str(exc)
                        p = Project(path, documents)
                        p.run(task, mode)
                    else:
                        try:
                            p.run(task, mode, fault)
                        except ProjectError as exc:
                            error = str(exc)
                            if fault == "worker_lost":
                                Project(path, documents).run(task, mode)
                except ProjectError as exc:
                    error = str(exc)
                should_create = fault in {
                    "duplicate",
                    "worker_lost",
                    "restart",
                    "release_rollback",
                }
                ok = p.ticket_count(task["task_id"]) == int(should_create)
                faults.append(
                    {
                        "project": mode,
                        "fault": fault,
                        "error": error,
                        "tickets": p.ticket_count(task["task_id"]),
                        "passed": ok,
                        "events": p.events(task["task_id"]),
                    }
                )
    (HERE / "results").mkdir(exist_ok=True)
    report = {
        "evidence_kind": "local_deterministic_sqlite_reference",
        "summary": summaries,
        "faults": faults,
        "samples": samples,
    }
    (HERE / "results/report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "summary": {
                    k: {a: b for a, b in v.items() if a != "rows"}
                    for k, v in summaries.items()
                },
                "faults_passed": sum(x["passed"] for x in faults),
                "faults_total": len(faults),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not all(x["passed"] for x in faults):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", choices=["PRJ-1", "PRJ-2", "PRJ-3"])
    run(parser.parse_args().project)
