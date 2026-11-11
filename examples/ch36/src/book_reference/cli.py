"""Strict manifest loading, explicit baseline sealing and local reproduction."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tomllib
from datetime import datetime, timezone

from .adapters import ControlledClock, FixedModel
from .contracts import Approval, Rejected, SimulatedCrash, digest, payload_for, validate_task
from .engine import Engine
from .storage import SessionStore, TicketService

ROOT = Path(__file__).resolve().parents[2]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset_paths(root):
    paths = [root / p for p in (".gitattributes", "run.py", "pyproject.toml", "uv.lock", "run_manifest.toml")]
    paths += sorted((root / "src").rglob("*.py"))
    paths += sorted(p for p in (root / "fixtures").rglob("*") if p.is_file())
    return paths


def current_assets(root):
    return {p.relative_to(root).as_posix(): file_digest(p) for p in asset_paths(root)}


def verify_inventory(root):
    inventory = read_json(root / "asset_inventory.json")
    actual = current_assets(root)
    if inventory.get("schema_version") != "inventory-1" or actual != inventory.get("assets"):
        raise Rejected("asset_drift: compare against asset_inventory.json; review before seal")
    return actual


def exact_fields(value, names, code):
    if not isinstance(value, dict) or set(value) != set(names):
        raise Rejected(code)


def load_manifest(root):
    manifest = tomllib.loads((root / "run_manifest.toml").read_text(encoding="utf-8"))
    exact_fields(manifest, ("schema_version", "baseline_id", "projects", "environment", "inputs", "budget"), "manifest_fields")
    if manifest["schema_version"] != "reference-demo-1" or manifest["projects"] != ["PRJ-1", "PRJ-2", "PRJ-3"]:
        raise Rejected("manifest_version_or_projects")
    exact_fields(manifest["environment"], ("python_minor", "lockfile", "runtime"), "environment_fields")
    if manifest["environment"] != {"python_minor": "3.12", "lockfile": "uv.lock", "runtime": "stdlib-sqlite"}:
        raise Rejected("environment_contract")
    if sys.version_info[:2] != (3, 12):
        raise Rejected("python_minor: use Python 3.12")
    exact_fields(manifest["inputs"], ("task", "policy", "model_response", "prompt", "expected"), "input_fields")
    for path in manifest["inputs"].values():
        resolved = (root / path).resolve()
        if not resolved.is_relative_to((root / "fixtures").resolve()) or not resolved.is_file():
            raise Rejected("input_path")
    exact_fields(manifest["budget"], ("max_attempts", "deadline_ms", "clock_start_ms", "approval_expires_at_ms"), "budget_fields")
    budget = manifest["budget"]
    if any(type(x) is not int or x < 0 for x in budget.values()) or not 1 <= budget["max_attempts"] <= 10:
        raise Rejected("budget_value")
    if not budget["clock_start_ms"] < budget["approval_expires_at_ms"] <= budget["deadline_ms"]:
        raise Rejected("budget_time_order")
    return manifest


def provenance():
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    return {"git_head": head, "source_identity": "asset_inventory.json (includes uncommitted assets)",
            "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "platform": platform.platform(), "recorded_at_utc": datetime.now(timezone.utc).isoformat()}


def prepare_output(output, resume, identity):
    output = output.resolve()
    if ROOT == output or ROOT.is_relative_to(output) or any(output.is_relative_to(ROOT / p) for p in ("src", "fixtures")):
        raise Rejected("output_path")
    if resume:
        if not all((output / name).is_file() for name in ("resolved_manifest.json", "session.sqlite", "service.sqlite")):
            raise Rejected("resume_missing_state")
        old = read_json(output / "resolved_manifest.json")
        if old["identity"] != identity:
            raise Rejected("resume_baseline_conflict")
    else:
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise Rejected("output_not_empty")
        output.mkdir(parents=True, exist_ok=True)
        write_json(output / "resolved_manifest.json", {"identity": identity, "environment": provenance(),
                   "approval_source": "trusted local fixture harness; no production authentication"})
    return output


def snapshot(output, state, expected):
    # New connections read persistent state independently of Engine.verify().
    with sqlite3.connect(output / "service.sqlite") as db:
        rows = db.execute("SELECT payload_json,approved_digest FROM tickets").fetchall()
        created = db.execute("SELECT count(*) FROM service_events WHERE kind='created'").fetchone()[0]
    with sqlite3.connect(output / "session.sqlite") as db:
        events = [{"sequence": seq, "kind": kind, "details": json.loads(details)}
                  for seq, kind, details in db.execute("SELECT sequence,kind,details_json FROM events ORDER BY sequence")]
    checks = {"status": state["status"] == expected["status"],
              "ticket_count": len(rows) == expected["ticket_count"],
              "created_event_count": created == expected["created_event_count"],
              "payload": all(json.loads(row[0]) == expected["payload"] for row in rows),
              "approved_scope": all(row[1] == digest(expected["payload"]) for row in rows)}
    summary = {"status": state["status"], "ticket_count": len(rows), "created_event_count": created,
               "operation_id": state["operation_id"], "attempts": state["attempts"],
               "checks": checks, "oracle_passed": all(checks.values()),
               "event_kinds": [e["kind"] for e in events]}
    write_json(output / "events.json", events)
    write_json(output / "summary.json", summary)
    return summary


def run_one(args):
    assets = verify_inventory(ROOT)
    manifest = load_manifest(ROOT)
    if args.project not in manifest["projects"]:
        raise Rejected("project")
    identity = {"manifest": manifest, "assets": assets, "project": args.project}
    output = prepare_output(Path(args.output), args.resume, identity)
    task = validate_task(read_json(ROOT / manifest["inputs"]["task"]))
    policy = read_json(ROOT / manifest["inputs"]["policy"])
    exact_fields(policy, ("version", "amount_limit", "supervisor_threshold", "clauses"), "policy_fields")
    if any(type(policy[k]) is not int or policy[k] < 0 for k in ("amount_limit", "supervisor_threshold")) or policy["supervisor_threshold"] > policy["amount_limit"]:
        raise Rejected("policy_limit")
    budget = manifest["budget"]
    model = FixedModel(read_json(ROOT / manifest["inputs"]["model_response"]))
    grant = Approval(task["tenant"], digest(payload_for(task)), budget["approval_expires_at_ms"])
    store = SessionStore(output / "session.sqlite")
    service = TicketService(output / "service.sqlite")
    crashed = False
    try:
        engine = Engine(store, service, model, ControlledClock(budget["clock_start_ms"]), policy,
                        budget["max_attempts"], budget["deadline_ms"])
        try:
            state = engine.run(task, grant, project=args.project, fault=args.fault)
        except SimulatedCrash:
            crashed = True
            state = store.get(task)
        summary = snapshot(output, state, read_json(ROOT / manifest["inputs"]["expected"]))
    finally:
        store.close()
        service.close()
    print(json.dumps({"project": args.project, "status": summary["status"], "ticket_count": summary["ticket_count"],
                      "oracle_passed": summary["oracle_passed"], "simulated_crash": crashed}, ensure_ascii=False))
    return 42 if crashed else (0 if summary["oracle_passed"] else 1)


def reproduce(args):
    verify_inventory(ROOT)
    load_manifest(ROOT)
    output = Path(args.output).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise Rejected("output_not_empty")
    if ROOT == output or ROOT.is_relative_to(output) or any(output.is_relative_to(ROOT / p) for p in ("src", "fixtures")):
        raise Rejected("output_path")
    output.mkdir(parents=True, exist_ok=True)
    commands = []
    for project in ("PRJ-1", "PRJ-2", "PRJ-3"):
        command = [sys.executable, str(ROOT / "run.py"), "run", "--project", project, "--output", str(output / project)]
        if project == "PRJ-3":
            crash = subprocess.run(command + ["--fault", "after_commit"], capture_output=True, text=True)
            commands.append({"project": project, "phase": "commit_then_exit", "exit_code": crash.returncode,
                             "stdout": crash.stdout.strip(), "stderr": crash.stderr.strip()})
            if crash.returncode != 42:
                write_json(output / "reproduction.json", {"passed": False, "commands": commands})
                return 1
            command += ["--resume"]
        result = subprocess.run(command, capture_output=True, text=True)
        commands.append({"project": project, "phase": "resume" if project == "PRJ-3" else "run", "exit_code": result.returncode,
                         "stdout": result.stdout.strip(), "stderr": result.stderr.strip()})
    passed = all(c["exit_code"] == (42 if c["phase"] == "commit_then_exit" else 0) for c in commands)
    report = {"scope": "same-machine local teaching slices; PRJ-3 uses two child processes", "passed": passed,
              "environment": provenance(), "commands": commands}
    write_json(output / "reproduction.json", report)
    print(json.dumps({"passed": passed, "project_slices": 3}, ensure_ascii=False))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal", help="explicit maintainer step after review; never auto-update on run")
    seal.add_argument("--reason", required=True)
    run = commands.add_parser("run")
    run.add_argument("--project", choices=("PRJ-1", "PRJ-2", "PRJ-3"), default="PRJ-1")
    run.add_argument("--output", required=True)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--fault", choices=("before_send", "after_commit", "response_lost", "cancel_after_commit"))
    repro = commands.add_parser("reproduce")
    repro.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "seal":
            load_manifest(ROOT)
            write_json(ROOT / "asset_inventory.json", {"schema_version": "inventory-1", "reason": args.reason,
                                                       "assets": current_assets(ROOT)})
            print("Baseline inventory updated explicitly; review this diff before distributing.")
            return 0
        return run_one(args) if args.command == "run" else reproduce(args)
    except (Rejected, FileNotFoundError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        # Report the stable rejection code; do not dump the full input/configuration.
        print("REJECTED: " + str(error), file=sys.stderr)
        return 2
