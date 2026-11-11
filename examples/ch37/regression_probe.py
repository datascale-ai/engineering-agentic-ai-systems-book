"""Repeatable negative control: a deliberately faulty client changes retry keys."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

CH36 = Path(__file__).resolve().parent.parent / "ch36"
sys.path.insert(0, str(CH36 / "src"))
from book_reference.adapters import ControlledClock, FixedModel
from book_reference.contracts import Approval, SimulatedCrash
from book_reference.engine import Engine
from book_reference.storage import SessionStore, TicketService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=("buggy", "fixed"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        parser.error("output must be new or empty")
    args.output.mkdir(parents=True, exist_ok=True)
    task = json.loads((CH36 / "fixtures/task.json").read_text(encoding="utf-8"))
    expected = json.loads((CH36 / "fixtures/expected.json").read_text(encoding="utf-8"))
    policy = json.loads((CH36 / "fixtures/policy.json").read_text(encoding="utf-8"))
    payload = expected["payload"]
    scope = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    grant = Approval(task["tenant"], scope, 4000)
    service = TicketService(args.output / "service.sqlite")
    store = SessionStore(args.output / "session.sqlite")
    try:
        if args.client == "buggy":
            # Test-only faulty client; the shipped Engine has no such mode.
            service.create(task["tenant"], "bad-attempt-1", payload, grant, 1000)
            service.create(task["tenant"], "bad-attempt-2", payload, grant, 1000)
            status = "completed"
        else:
            model = FixedModel(json.loads((CH36 / "fixtures/model_response.json").read_text(encoding="utf-8")))
            try:
                Engine(store, service, model, ControlledClock(), policy).run(task, grant, fault="after_commit")
            except SimulatedCrash:
                pass
            store.close()
            service.close()
            store = SessionStore(args.output / "session.sqlite")
            service = TicketService(args.output / "service.sqlite")
            status = Engine(store, service, model, ControlledClock(), policy).run(task, grant)["status"]
        with sqlite3.connect(args.output / "service.sqlite") as independent:
            rows = independent.execute("SELECT payload_json,approved_digest FROM tickets").fetchall()
            created = independent.execute("SELECT count(*) FROM service_events WHERE kind='created'").fetchone()[0]
        oracle = status == "completed" and len(rows) == 1 and created == 1 and all(json.loads(p) == payload and d == scope for p, d in rows)
        report = {"client": args.client, "presentation_only_passed": status == "completed",
                  "ticket_count": len(rows), "created_event_count": created, "independent_oracle_passed": oracle,
                  "scope": "controlled local defect, not a historical production incident"}
        (args.output / "regression.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0 if oracle else 1
    finally:
        store.close()
        service.close()


if __name__ == "__main__":
    raise SystemExit(main())
