"""Public CLI shared by all three project launchers."""

import argparse
import json
from pathlib import Path
from .projects import Project, ProjectError, load_assets


def main(mode):
    parser = argparse.ArgumentParser(description=mode + " local teaching reference")
    parser.add_argument("--database", default="/tmp/book-" + mode.lower() + ".sqlite3")
    parser.add_argument("--task", default="T01-1")
    parser.add_argument("--release", default="teaching-0.1")
    parser.add_argument(
        "--fault",
        choices=[
            "missing_evidence",
            "duplicate",
            "worker_lost",
            "cancel",
            "late_output",
            "wrong_release",
        ],
    )
    parser.add_argument("--cancel-after-evidence", action="store_true")
    args = parser.parse_args()
    docs, tasks = load_assets()
    task = next((t for t in tasks if t["task_id"] == args.task), None)
    if task is None:
        parser.error("unknown task")
    # Gold fields are only for the experiment harness, never runtime input.
    task = {
        k: v
        for k, v in task.items()
        if k not in {"expected_action", "expected_evidence", "document_id"}
    }
    project = Project(Path(args.database), docs, args.release)
    try:
        if mode == "PRJ-3" and not args.fault:
            stream = project.stream(task)
            for event in stream:
                print(json.dumps(event, ensure_ascii=False), flush=True)
                if args.cancel_after_evidence and event["kind"] == "evidence_ready":
                    project.cancel(task["task_id"])
        else:
            print(json.dumps(project.run(task, mode, args.fault), ensure_ascii=False))
    except ProjectError as exc:
        print(
            json.dumps(
                {"status": "rejected", "reason": str(exc), "task_id": task["task_id"]},
                ensure_ascii=False,
            )
        )
        raise SystemExit(2)
    print(
        json.dumps(
            {
                "ticket": project.query_ticket(task["task_id"]),
                "events": project.events(task["task_id"]),
            },
            ensure_ascii=False,
        )
    )
