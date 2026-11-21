"""Local configuration-release rehearsal; no production rollout or real IAM."""
from copy import deepcopy
import sqlite3

from .contracts import Approval, Rejected, digest, payload_for
from .coordination import Board
from .project2 import DATA, ROOT, load, run_project, save
from .storage import TicketService


def validate_release(config, actual_policy):
    required = {"release_id", "source_inventory", "policy_version", "workers", "identity_mode"}
    if set(config) != required or type(config["workers"]) is not int or not 1 <= config["workers"] <= 3:
        raise Rejected("release_fields")
    if config["identity_mode"] != "trusted_local_fixture" or config["policy_version"] != actual_policy:
        raise Rejected("release_contract_mismatch")
    if config["source_inventory"] != digest(load(ROOT / "asset_inventory.json")):
        raise Rejected("release_source_mismatch")


def business_snapshot(path):
    with sqlite3.connect(path) as db:
        return {"tickets": db.execute("SELECT tenant,operation_id,payload_digest FROM tickets ORDER BY tenant,operation_id").fetchall(),
                "created": db.execute("SELECT count(*) FROM service_events WHERE kind='created'").fetchone()[0]}


def admission(control, config):
    row = control.execute("SELECT intake,grants,active,canary FROM control WHERE id=1").fetchone()
    if not row or row[:2] != (1, 1):
        raise Rejected("release_retired")
    if config["release_id"] not in row[2:]:
        raise Rejected("release_not_routed")
    validate_release(config, "P20-A@2.0")


def run_deployment(output):
    output.mkdir(parents=True, exist_ok=False)
    source = digest(load(ROOT / "asset_inventory.json"))
    release = {"release_id": "local-v1", "source_inventory": source, "policy_version": "P20-A@2.0",
               "workers": 3, "identity_mode": "trusted_local_fixture"}
    validate_release(release, "P20-A@2.0")
    control = sqlite3.connect(output / "release.sqlite")
    control.execute("CREATE TABLE control(id INTEGER PRIMARY KEY,active TEXT,canary TEXT,intake INTEGER,grants INTEGER)")
    control.execute("INSERT INTO control VALUES(1,'local-v1',NULL,1,1)")
    control.commit()
    admission(control, release)
    project = run_project(output / "launch-project")
    before = business_snapshot(output / "launch-project/service.sqlite")
    records = [{"id": "D-LAUNCH-01", "operation": "launch", "actor": "trusted_local_driver",
                "expected": "24 role jobs closed; 3 unique tickets", "actual": {"closed_jobs": project["closed_jobs"], "ticket_count": project["ticket_count"]},
                "passed": project["passed"], "evidence": "launch-project/report.json"}]
    candidate = {**release, "release_id": "local-v2", "policy_version": "P20-A@9.9"}
    control.execute("UPDATE control SET canary='local-v2' WHERE id=1")
    control.commit()
    rejected = None
    try:
        admission(control, candidate)
    except Rejected as error:
        rejected = str(error)
    unchanged = business_snapshot(output / "launch-project/service.sqlite") == before
    records.append({"id": "D-CANARY-01", "operation": "canary", "scope": ["T-DEMO-01"],
                    "expected": "mismatched policy blocks dispatch before new effect", "actual": rejected,
                    "passed": rejected == "release_contract_mismatch" and unchanged,
                    "traffic": "local routing assignment only; no network traffic"})
    control.execute("UPDATE control SET active='local-v1',canary=NULL WHERE id=1")
    control.commit()
    admission(control, release)
    old_candidate_blocked = False
    try:
        admission(control, {**release, "release_id": "local-v2"})
    except Rejected as error:
        old_candidate_blocked = str(error) == "release_not_routed"
    after = business_snapshot(output / "launch-project/service.sqlite")
    records.append({"id": "D-ROLLBACK-01", "operation": "rollback", "from": "local-v2-canary", "to": "local-v1",
                    "expected": "routing restored; existing effects unchanged", "actual": {"source_unchanged": source == digest(load(ROOT / "asset_inventory.json")), "business_snapshot_equal": before == after, "old_candidate_admission_rejected": old_candidate_blocked},
                    "passed": before == after and old_candidate_blocked and control.execute("SELECT active,canary FROM control").fetchone() == ("local-v1", None),
                    "boundary": "configuration pointer rollback; no schema downgrade or business compensation"})
    board = Board(output / "launch-project/coordination.sqlite")
    in_flight = board.db.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('closed','cancelled','escalated')").fetchone()[0]
    board.close()
    control.execute("UPDATE control SET intake=0,grants=0 WHERE id=1")
    control.commit()
    stopped = control.execute("SELECT intake,grants FROM control").fetchone() == (0, 0)
    admission_rejected = False
    try:
        admission(control, release)
    except Rejected as error:
        admission_rejected = str(error) == "release_retired"
    archive = sqlite3.connect(output / "retired-control.sqlite")
    control.backup(archive)
    archive.close()
    records.append({"id": "D-RETIRE-01", "operation": "retire", "expected": "intake closed, local grants disabled, no in-flight role jobs",
                    "actual": {"in_flight": in_flight, "intake_and_grants_disabled": stopped, "new_admission_rejected": admission_rejected, "archive": "retired-control.sqlite"},
                    "passed": in_flight == 0 and stopped and admission_rejected,
                    "retention": "original teaching data retained locally; no deletion or production credential revocation"})
    control.close()
    # Explicitly exercise the service's limited tenant partition; this is not IAM.
    task = load(DATA / "project_tasks.json")[0]
    payload = payload_for(task)
    service = TicketService(output / "tenant-probe.sqlite")
    tenant_probe = {}
    try:
        for tenant in ("course-A", "course-B"):
            grant = Approval(tenant, digest(payload), 4000)
            tenant_probe[tenant] = service.create(tenant, "same-operation", payload, grant, 1000)
        try:
            service.create("course-B", "another-operation", payload, Approval("course-A", digest(payload), 4000), 1000)
        except Rejected as error:
            tenant_probe["cross_tenant_grant_rejected"] = str(error) == "approval_tenant"
    finally:
        service.close()
    report = {"experiment": "D-DEPLOY-LOCAL-01", "release": release, "candidate": candidate,
              "records": records, "tenant_probe": tenant_probe,
              "profiles": load(DATA / "deploy_profiles.json"), "source_inventory_digest": source,
              "scope": "local configuration, SQLite routing/archival and trusted tenant fixtures; no real queues, IAM, TLS, capacity or production rollout",
              "independent_review_F": "pending", "passed": all(r["passed"] for r in records) and tenant_probe.get("cross_tenant_grant_rejected", False)}
    save(output / "report.json", report)
    return report
