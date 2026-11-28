"""Ch39: Staging deployment drills, continuous delivery gates, 5-element rollback
(code + config + data + permissions + cache), and PRJ-3 engineering capstone.

Directly reuses:
- `examples/ch36/src/book_reference/` (shared Engine, SessionStore, TicketService, contracts)
- `examples/ch38/regression_runner/runner.py` (golden slices + OTel trace assertions)

Executes 4 reproducible drills in isolated temporary sandboxes:
  DRILL-01: Controlled release (`release-v1.0.0`) passing full CD gates & staging verification
  DRILL-02: Fault-injected candidate (`release-v1.1.0-bad-config`) with config mismatch +
            stale permission cache residue + secret-in-log redaction check
            (contrasts `deploy_only` vs `full_cd_gate_plus_business_verify`)
  DRILL-03: Full 5-element atomic rollback (intake pause -> code -> config -> permissions ->
            cache purge -> data reconcile) proving stale permissions are eliminated & valid tickets preserved
  DRILL-04: End-to-end PRJ-3 Capstone drill (crash-after-commit recovery + regression gate +
            release audit trail)
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any, Dict, List, Optional
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CH36_SRC = REPO_ROOT / "examples" / "ch36" / "src"
CH38_DIR = REPO_ROOT / "examples" / "ch38"
for p in (str(CH36_SRC), str(CH38_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from book_reference.adapters import ControlledClock  # noqa: E402
from book_reference.contracts import Approval, SimulatedCrash, digest, payload_for  # noqa: E402
from book_reference.engine import Engine  # noqa: E402
from book_reference.storage import SessionStore, TicketService  # noqa: E402
from regression_runner.runner import (  # noqa: E402
    BASE_POLICY,
    PolicyAwareMockModel,
    build_otel_trace,
    build_task_dict,
    check_trace_assertions,
    count_tickets,
    read_session_events,
    run_candidate_suite,
)


class PermissionCache:
    """Simulated staging authorization cache that can suffer stale residue if rollback forgets purge."""

    def __init__(self) -> None:
        self.epoch = 1
        self.entries: Dict[str, Dict[str, Any]] = {}

    def put(self, key: str, allow_high_risk: bool, release_id: str) -> None:
        self.entries[key] = {
            "allow_high_risk": allow_high_risk,
            "release_id": release_id,
            "epoch": self.epoch,
        }

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self.entries.get(key)

    def purge_and_bump(self) -> int:
        cleared = len(self.entries)
        self.entries.clear()
        self.epoch += 1
        return cleared


class StagingEnvironment:
    """Isolated local staging simulator with release pointer, config, DBs, cache, and audit log."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.session_db = root / "staging_session.sqlite"
        self.service_db = root / "staging_service.sqlite"
        self.active_release: str = "release-v1.0.0"
        self.active_policy: Dict[str, Any] = dict(BASE_POLICY)
        self.active_config_digest: str = digest(self.active_policy)
        self.intake_enabled: bool = True
        self.cache = PermissionCache()
        self.timeline: List[Dict[str, Any]] = []
        self._tick = 0

    def log(self, event: str, **details: Any) -> None:
        self._tick += 10
        # Enforce secret redaction before writing audit log
        sanitized = {}
        for k, v in details.items():
            s = str(v)
            if any(pat in s for pat in ("sk-", "Bearer ", "PRIVATE KEY", "password=")):
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                sanitized[k] = v
        self.timeline.append({
            "t_ms": self._tick,
            "release": self.active_release,
            "event": event,
            **sanitized,
        })

    def execute_probe(self, task_spec: Dict[str, Any]) -> Dict[str, Any]:
        task = build_task_dict(task_spec)
        store = SessionStore(self.session_db)
        service = TicketService(self.service_db)
        clock = ControlledClock(1000)
        model = PolicyAwareMockModel(mode="baseline")

        # If stale permission cache erroneously allows high risk, simulate leaky policy threshold
        cached = self.cache.get(f"{task['tenant']}:policy_override")
        effective_policy = dict(self.active_policy)
        if cached and cached["allow_high_risk"]:
            effective_policy["supervisor_threshold"] = 500
            model = PolicyAwareMockModel(mode="prompt_regression_skip_approval")

        approval = Approval(
            tenant=task["tenant"],
            payload_digest=digest(payload_for(task)),
            expires_at_ms=5000,
            permitted=True,
        )
        engine = Engine(store, service, model, clock, effective_policy)
        state = engine.run(task, approval, project="PRJ-3")
        db_tickets = count_tickets(self.service_db, task["tenant"])
        events = read_session_events(self.session_db, task["tenant"], task["task_id"])
        store.close()
        service.close()

        trace = build_otel_trace(
            task, events, state["status"], state.get("reason"), db_tickets, f"staging:{self.active_release}"
        )
        tr_ok, tr_errs = check_trace_assertions(trace, state["status"], state.get("reason"), db_tickets)
        return {
            "task_id": task["task_id"],
            "status": state["status"],
            "reason": state.get("reason"),
            "db_tickets": db_tickets,
            "trace_ok": tr_ok,
            "trace_errors": tr_errs,
        }


def run_drills(output_dir: Path) -> Dict[str, Any]:
    slices_cfg = yaml.safe_load((CH38_DIR / "golden_slices.yaml").read_text(encoding="utf-8"))
    results: Dict[str, Any] = {"experiment_id": "Exp-39-01", "drills": {}}

    with tempfile.TemporaryDirectory() as tmp:
        env = StagingEnvironment(Path(tmp))

        # ------------------------------------------------------------------
        # DRILL-01: Controlled release (`release-v1.0.0`) via full CD gate
        # ------------------------------------------------------------------
        env.log("cd_gate_start", candidate="release-v1.0.0")
        reg_v1 = run_candidate_suite(slices_cfg, "release-v1.0.0")
        assert reg_v1["gate_passed"] is True
        env.log("cd_gate_passed", candidate="release-v1.0.0", slices_passed=len(reg_v1["slices"]))

        probe_ok = env.execute_probe({
            "task_id": "STG-01-eligible", "tenant": "tenant-alpha",
            "amount": 250, "domestic": True, "receipt_valid": True, "policy_version": "P20-A@2.0",
        })
        probe_hi = env.execute_probe({
            "task_id": "STG-02-highrisk", "tenant": "tenant-alpha",
            "amount": 450, "domestic": True, "receipt_valid": True, "policy_version": "P20-A@2.0",
        })
        env.log("staging_smoke_verified", eligible_status=probe_ok["status"], highrisk_status=probe_hi["status"],
                tickets_total=probe_ok["db_tickets"])

        results["drills"]["DRILL-01_controlled_release"] = {
            "release_id": "release-v1.0.0",
            "cd_gate_passed": reg_v1["gate_passed"],
            "eligible_probe": probe_ok,
            "highrisk_probe": probe_hi,
            "passed": (
                reg_v1["gate_passed"]
                and probe_ok["status"] == "completed"
                and probe_ok["db_tickets"] == 1
                and probe_hi["status"] == "rejected"
                and probe_ok["trace_ok"]
                and probe_hi["trace_ok"]
            ),
        }

        # ------------------------------------------------------------------
        # DRILL-02: Fault injection — bad config + stale cache + secret leak check
        # Compare `deploy_only` (incomplete rollback) vs `full_gate_plus_business_verify`
        # ------------------------------------------------------------------
        bad_policy = dict(BASE_POLICY, supervisor_threshold=500)
        env.log("fault_injected_candidate", candidate="release-v1.1.0-bad-config",
                injected_secret_sample="Bearer sk-test-secret-should-redact")

        # 2a. Full CD gate blocks bad candidate BEFORE staging promotion
        reg_bad = run_candidate_suite(
            slices_cfg, "release-v1.1.0-bad-config",
            model_mode="prompt_regression_skip_approval",
            policy_override=bad_policy,
            bypass_policy_guard=True,
        )
        gate_blocked_candidate = not reg_bad["gate_passed"]
        env.log("cd_gate_blocked_bad_candidate", candidate="release-v1.1.0-bad-config",
                detected_layers=reg_bad["detected_fault_layers"])

        # 2b. Simulate what happens if a naive `deploy_only` bypasses gate & poisons permission cache,
        #     then rolls back ONLY code/config without purging cache (opening chapter incident!)
        env.active_release = "release-v1.1.0-bad-config"
        env.active_policy = bad_policy
        env.cache.put("tenant-alpha:policy_override", allow_high_risk=True, release_id="release-v1.1.0-bad-config")
        # Naive code-only rollback forgets cache purge!
        env.active_release = "release-v1.0.0"
        env.active_policy = dict(BASE_POLICY)
        env.log("incomplete_rollback_detected", note="code/config reverted but permission cache still stale")

        probe_after_incomplete = env.execute_probe({
            "task_id": "STG-03-stale-cache-probe", "tenant": "tenant-alpha",
            "amount": 420, "domestic": True, "receipt_valid": True, "policy_version": "P20-A@2.0",
        })
        incomplete_rollback_failed_safety = (probe_after_incomplete["status"] == "completed")

        # Verify secret redaction in audit log
        serialized_log = json.dumps(env.timeline, ensure_ascii=False)
        secret_leaked = ("sk-test-secret" in serialized_log) or ("Bearer " in serialized_log)

        results["drills"]["DRILL-02_fault_and_incomplete_rollback_contrast"] = {
            "full_cd_gate_blocked": gate_blocked_candidate,
            "detected_fault_layers": reg_bad["detected_fault_layers"],
            "deploy_only_incomplete_rollback_probe": probe_after_incomplete,
            "incomplete_rollback_exposed_stale_cache_bug": incomplete_rollback_failed_safety,
            "secret_leaked_in_audit_log": secret_leaked,
            "passed": gate_blocked_candidate and incomplete_rollback_failed_safety and (not secret_leaked),
        }

        # ------------------------------------------------------------------
        # DRILL-03: Complete 5-element rollback (intake -> code -> config -> perms -> cache -> data)
        # ------------------------------------------------------------------
        env.intake_enabled = False
        env.log("rollback_step1_intake_paused", intake_enabled=env.intake_enabled)
        env.active_release = "release-v1.0.0"
        env.active_policy = dict(BASE_POLICY)
        env.active_config_digest = digest(env.active_policy)
        env.log("rollback_step2_3_code_config_restored", config_digest=env.active_config_digest[:12])
        cleared_entries = env.cache.purge_and_bump()
        env.log("rollback_step4_permission_cache_purged", cleared_entries=cleared_entries, new_epoch=env.cache.epoch)
        env.intake_enabled = True
        env.log("rollback_step5_intake_resumed", intake_enabled=env.intake_enabled)

        # Post-rollback independent business verification
        probe_post_hi = env.execute_probe({
            "task_id": "STG-04-post-rollback-highrisk", "tenant": "tenant-alpha",
            "amount": 420, "domestic": True, "receipt_valid": True, "policy_version": "P20-A@2.0",
        })
        probe_post_ok = env.execute_probe({
            "task_id": "STG-05-post-rollback-eligible", "tenant": "tenant-beta",
            "amount": 220, "domestic": True, "receipt_valid": True, "policy_version": "P20-A@2.0",
        })
        # Check legitimate STG-01 ticket was preserved
        conn = sqlite3.connect(env.service_db)
        try:
            legit_row = conn.execute(
                "SELECT operation_id FROM tickets WHERE tenant='tenant-alpha' AND operation_id='STG-01-eligible:1:create'"
            ).fetchone()
            legit_preserved = legit_row is not None
        finally:
            conn.close()

        env.log("rollback_business_verified", post_highrisk_status=probe_post_hi["status"],
                post_eligible_status=probe_post_ok["status"], legit_preserved=legit_preserved)

        results["drills"]["DRILL-03_full_five_element_rollback"] = {
            "cleared_cache_entries": cleared_entries,
            "new_cache_epoch": env.cache.epoch,
            "post_rollback_highrisk_probe": probe_post_hi,
            "post_rollback_eligible_probe": probe_post_ok,
            "legitimate_ticket_preserved": legit_preserved,
            "passed": (
                cleared_entries == 1
                and probe_post_hi["status"] == "rejected"
                and probe_post_hi["reason"] == "needs_approval"
                and probe_post_ok["status"] == "completed"
                and probe_post_ok["db_tickets"] == 1
                and legit_preserved
            ),
        }

        # ------------------------------------------------------------------
        # DRILL-04: End-to-end PRJ-3 Capstone drill (crash-after-commit + recovery + audit)
        # ------------------------------------------------------------------
        cap_task = build_task_dict({
            "task_id": "CAP-PRJ3-01", "tenant": "tenant-gamma",
            "amount": 280, "domestic": True, "receipt_valid": True, "policy_version": "P20-A@2.0",
        })
        cap_approval = Approval(
            tenant="tenant-gamma", payload_digest=digest(payload_for(cap_task)),
            expires_at_ms=5000, permitted=True,
        )
        store = SessionStore(env.session_db)
        service = TicketService(env.service_db)
        eng = Engine(store, service, PolicyAwareMockModel(), ControlledClock(1000), env.active_policy)
        crashed = False
        try:
            eng.run(cap_task, cap_approval, project="PRJ-3", fault="after_commit")
        except SimulatedCrash:
            crashed = True
        recovered_state = eng.run(cap_task, cap_approval, project="PRJ-3", fault=None)
        cap_tickets = count_tickets(env.service_db, "tenant-gamma")
        cap_events = read_session_events(env.session_db, "tenant-gamma", cap_task["task_id"])
        store.close()
        service.close()

        cap_trace = build_otel_trace(
            cap_task, cap_events, recovered_state["status"], recovered_state.get("reason"),
            cap_tickets, f"staging:{env.active_release}",
        )
        cap_tr_ok, cap_tr_errs = check_trace_assertions(cap_trace, recovered_state["status"], None, cap_tickets)
        env.log("capstone_prj3_verified", crashed=crashed, status=recovered_state["status"],
                tickets=cap_tickets, trace_ok=cap_tr_ok)

        results["drills"]["DRILL-04_prj3_capstone_e2e"] = {
            "crash_injected": crashed,
            "recovered_status": recovered_state["status"],
            "db_tickets": cap_tickets,
            "trace_ok": cap_tr_ok,
            "trace_errors": cap_tr_errs,
            "events": cap_events,
            "passed": crashed and recovered_state["status"] == "completed" and cap_tickets == 1 and cap_tr_ok,
        }

        results["timeline"] = env.timeline
        results["all_drills_passed"] = all(d["passed"] for d in results["drills"].values())

    res_dir = output_dir / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / "ch39_drill_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "release_report.md").write_text(format_release_report(results), encoding="utf-8")
    return results


def format_release_report(res: Dict[str, Any]) -> str:
    d1 = res["drills"]["DRILL-01_controlled_release"]
    d2 = res["drills"]["DRILL-02_fault_and_incomplete_rollback_contrast"]
    d3 = res["drills"]["DRILL-03_full_five_element_rollback"]
    d4 = res["drills"]["DRILL-04_prj3_capstone_e2e"]

    lines = [
        "# Ch39 预发布部署、故障注入与回滚演练报告 (`Exp-39-01`)",
        "",
        "> **证据状态**：在本地隔离临时目录运行，复用 `examples/ch36/src/book_reference/` 与 `examples/ch38/regression_runner/`。本演练仅证明所声明配置与沙箱边界下的发布门禁、五要素回滚与幂等恢复机制，不宣称为真实生产集群容灾或真实 IAM 治理验收。",
        "",
        "## 1. 四项演练结果汇总",
        "",
        "| 演练编号 | 演练内容 | 关键观察 | 验收结论 |",
        "| --- | --- | --- | --- |",
        f"| `DRILL-01` | 受控发布 (`release-v1.0.0`) | CD 回归门禁通过；合规探针 `completed`(1 工单)，高风险探针 `rejected(needs_approval)`，TA-01—TA-05 通过 | **{'PASS' if d1['passed'] else 'FAIL'}** |",
        f"| `DRILL-02` | 配置错配 + 权限缓存残留 + 密钥防泄对照 | 完整门禁阻断坏候选（定位 `{', '.join(d2['detected_fault_layers'])}`）；若跳过门禁且仅回滚代码，缓存残留导致 420 元高风险任务越权 `completed`；审计日志零密钥泄露 | **{'PASS' if d2['passed'] else 'FAIL'}** |",
        f"| `DRILL-03` | 五要素完整回滚与恢复验收 | 暂停入口 → 恢复代码/配置 → 清空 {d3['cleared_cache_entries']} 条旧权限缓存(epoch={d3['new_cache_epoch']})；回滚后高风险任务重新被拒(`needs_approval`)，既有合法工单完好保留 | **{'PASS' if d3['passed'] else 'FAIL'}** |",
        f"| `DRILL-04` | PRJ-3 端到端综合实践演练 | 注入 `after_commit` 崩溃后重连恢复，终态 `completed`、唯一工单数 `{d4['db_tickets']}`、轨迹断言 `{d4['trace_ok']}` | **{'PASS' if d4['passed'] else 'FAIL'}** |",
        "",
        "## 2. 事故与恢复运行时间线（摘录）",
        "",
        "| 虚拟时刻 (ms) | 当前版本 | 事件 | 关键字段 |",
        "| ---: | --- | --- | --- |",
    ]
    for ev in res["timeline"]:
        extras = {k: v for k, v in ev.items() if k not in ("t_ms", "release", "event")}
        lines.append(f"| {ev['t_ms']} | `{ev['release']}` | `{ev['event']}` | `{json.dumps(extras, ensure_ascii=False)}` |")
    lines.extend([
        "",
        "## 3. 生产适用边界与未覆盖项",
        "",
        "1. 本演练在单机 SQLite 与内存权限缓存上验证五要素回滚逻辑，未覆盖多副本分布式 Redis 缓存一致性、Kubernetes 滚动更新连接排空或跨区数据库模式降级。",
        "2. 审计日志脱敏检验了正则特征拦截，生产环境仍需结合外部 Secret Manager（如 Vault / KMS）与短期动态凭据。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    base = Path(__file__).resolve().parent
    res = run_drills(base)
    for k, v in res["drills"].items():
        print(f"[{k}] passed={v['passed']}")
    print(f"[ALL_DRILLS_PASSED] {res['all_drills_passed']}")


if __name__ == "__main__":
    main()
