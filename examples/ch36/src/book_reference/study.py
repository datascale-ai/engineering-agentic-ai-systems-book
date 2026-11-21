"""Stable entry points for the student E local project and experiments."""
import argparse
import json
from pathlib import Path
import sys

from .cli import provenance, verify_inventory
from .contracts import Rejected, digest
from .project2 import ROOT, DATA, load, run_project, save, worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("all", "project2", "experiments", "deploy", "worker"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--job")
    parser.add_argument("--actor", choices=("researcher", "executor", "verifier"))
    parser.add_argument("--tick", type=int, default=0)
    parser.add_argument("--crash-after-commit", action="store_true")
    args = parser.parse_args()
    try:
        verify_inventory(ROOT)
        if sys.version_info[:2] != (3, 12):
            raise Rejected("python_minor: use Python 3.12")
        output = Path(args.output).resolve()
        if args.command == "worker":
            if not args.job or not args.actor or not (output / "coordination.sqlite").is_file():
                raise Rejected("worker_arguments")
            return worker(output, args.job, args.actor, args.tick, args.crash_after_commit)
        if output.exists():
            raise Rejected("output_already_exists: choose a new directory")
        # Source trees must never become output directories.
        if output == ROOT or ROOT.is_relative_to(output) or any(output.is_relative_to(ROOT / p) for p in ("src", "fixtures", "reports")):
            raise Rejected("output_path")
        from .coordination_study import run_coordination
        from .debate_study import run_debate
        from .environment_study import run_environments
        from .deployment_study import run_deployment
        if args.command == "project2":
            report = run_project(output)
        elif args.command == "deploy":
            report = run_deployment(output)
        else:
            output.mkdir(parents=True, exist_ok=False)
            results = {}
            if args.command == "all":
                results["project2"] = run_project(output / "project2")
            results["ch19"] = run_coordination(output / "ch19")
            results["ch20"] = run_debate(output / "ch20")
            results["ch21"] = run_environments(output / "ch21")
            if args.command == "all":
                results["deploy"] = run_deployment(output / "deploy")
            report = {"baseline": load(DATA / "study_manifest.json"), "source_inventory_digest": digest(load(ROOT / "asset_inventory.json")),
                      "environment": provenance(), "results": {name: {"passed": r["passed"], "report": name + "/report.json"} for name, r in results.items()},
                      "passed": all(r["passed"] for r in results.values())}
            save(output / "report.json", report)
        print(json.dumps({"passed": report["passed"], "command": args.command}, ensure_ascii=False))
        return 0 if report["passed"] else 1
    except (Rejected, OSError, json.JSONDecodeError) as error:
        print("REJECTED: " + str(error), file=sys.stderr)
        return 2
