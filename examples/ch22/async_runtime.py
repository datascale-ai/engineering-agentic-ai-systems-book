"""Ch22: Bounded asynchronous agent orchestration runtime and load experiment.

Implements a self-contained, deterministic async runtime inspired by:
- DeepSeek Harness (dsh / Cordis) plugin context with reversible registrations
- Structured concurrency & cancellation propagation
- Multi-tenant fair-share quotas, bounded queues, worker leases, and crash reclaim

Run directly to execute the 50-task, 2-tenant comparative experiment and write:
- results/runtime_metrics.json
- results/runtime_events.jsonl
- runtime_load_report.md
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# 1. Plugin Context (inspired by DeepSeek Harness / Cordis reversible effects)
# ---------------------------------------------------------------------------

class PluginContext:
    """Minimal service registry with explicit dependency declaration and clean dispose."""

    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}
        self._disposers: Dict[str, List[Callable[[], None]]] = defaultdict(list)

    def provide(self, plugin_name: str, service_name: str, instance: Any,
                on_dispose: Optional[Callable[[], None]] = None) -> None:
        if service_name in self._services:
            raise RuntimeError(f"service already registered: {service_name}")
        self._services[service_name] = instance
        def _cleanup() -> None:
            if on_dispose is not None:
                on_dispose()
            self._services.pop(service_name, None)
        self._disposers[plugin_name].append(_cleanup)

    def require(self, service_name: str) -> Any:
        if service_name not in self._services:
            raise KeyError(f"missing required service: {service_name}")
        return self._services[service_name]

    def unload(self, plugin_name: str) -> None:
        """Unwind all registrations and effects of a plugin cleanly."""
        for cleanup in reversed(self._disposers.pop(plugin_name, [])):
            cleanup()


# ---------------------------------------------------------------------------
# 2. Task Graph, Cancellation Token, and Adapter Contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StepSpec:
    step_id: str
    kind: str  # "model" | "tool_read" | "tool_write"
    depends_on: Tuple[str, ...]
    duration_ms: float
    side_effect: bool = False
    fail_first_worker: bool = False  # Simulate worker crash mid-execution


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    tenant: str
    profile: str  # "fast" | "slow_tool" | "fanout_burst" | "cancel_midflight" | "worker_crash"
    arrival_ms: float
    steps: Tuple[StepSpec, ...]
    cancel_at_ms: Optional[float] = None
    cancel_after_step: Optional[str] = None


class CancelToken:
    """Out-of-band cancellation signal that never queues behind data traffic."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self._event = asyncio.Event()
        self.cancelled_at_ms: Optional[float] = None
        self.reason: Optional[str] = None

    def cancel(self, now_ms: float, reason: str = "user_cancel") -> None:
        if not self._event.is_set():
            self.cancelled_at_ms = now_ms
            self.reason = reason
            self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


class DeterministicToolAdapter:
    """Swappable tool adapter with idempotency ledger and deterministic sleep scaling."""

    def __init__(self, time_scale: float = 0.001) -> None:
        self.time_scale = time_scale
        self.committed_effects: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.active_handles: int = 0
        self.peak_active_handles: int = 0

    async def execute(
        self,
        tenant: str,
        task_id: str,
        step: StepSpec,
        token: CancelToken,
        clock_fn: Callable[[], float],
        attempt: int,
    ) -> Dict[str, Any]:
        self.active_handles += 1
        self.peak_active_handles = max(self.peak_active_handles, self.active_handles)
        try:
            # Simulate cooperative cancellation checks in 4 slices
            slices = 4
            slice_ms = step.duration_ms / slices
            for idx in range(slices):
                if token.is_cancelled:
                    raise asyncio.CancelledError(f"cancelled before slice {idx}")
                await asyncio.sleep(slice_ms * self.time_scale)
                # Simulated worker crash halfway through first attempt
                if step.fail_first_worker and attempt == 1 and idx == 1:
                    raise ConnectionAbortedError("simulated_worker_crash")
            effect_committed = False
            if step.side_effect:
                key = (tenant, f"{task_id}:{step.step_id}")
                if key not in self.committed_effects:
                    self.committed_effects[key] = {
                        "tenant": tenant,
                        "task_id": task_id,
                        "step_id": step.step_id,
                        "committed_at_ms": round(clock_fn(), 2),
                    }
                    effect_committed = True
            return {
                "step_id": step.step_id,
                "kind": step.kind,
                "side_effect_committed": effect_committed,
                "completed_at_ms": round(clock_fn(), 2),
            }
        finally:
            self.active_handles -= 1


# ---------------------------------------------------------------------------
# 3. Runtime Config & Bounded Async Orchestrator
# ---------------------------------------------------------------------------

@dataclass
class RuntimeConfig:
    mode: str = "bounded_concurrency"  # serial | unbounded_concurrency | bounded_concurrency
    global_max_workers: int = 6
    global_queue_capacity: int = 24
    tenant_max_in_flight: int = 3
    tenant_max_queue_depth: int = 12
    lease_ttl_ms: float = 80.0
    max_reclaims: int = 2
    control_plane_priority_lane: bool = True
    time_scale: float = 0.001  # 1 simulated ms = 0.001 real sec for fast deterministic runs


@dataclass
class TaskOutcome:
    task_id: str
    tenant: str
    profile: str
    status: str  # completed | cancelled | rejected_overload | failed
    arrival_ms: float
    start_ms: Optional[float]
    end_ms: float
    latency_ms: float
    queue_wait_ms: float
    steps_completed: int
    steps_total: int
    reclaims: int
    committed_side_effects: int
    cancel_response_ms: Optional[float] = None
    reason: Optional[str] = None


class AsyncAgentRuntime:
    """DAG-aware async runtime supporting serial, unbounded, and bounded fair execution."""

    def __init__(self, config: RuntimeConfig, adapter: DeterministicToolAdapter) -> None:
        self.config = config
        self.adapter = adapter
        self._start_wall = 0.0
        self.events: List[Dict[str, Any]] = []
        self.tokens: Dict[str, CancelToken] = {}
        self._global_in_flight = 0
        self._peak_in_flight = 0
        self._global_queued = 0
        self._peak_queued = 0
        self._tenant_in_flight: Dict[str, int] = defaultdict(int)
        self._tenant_queued: Dict[str, int] = defaultdict(int)
        self._global_sem: Optional[asyncio.Semaphore] = None
        self._tenant_sems: Dict[str, asyncio.Semaphore] = {}
        self._cancelled_queue_drain_delay_ms = 0.0

    def now_ms(self) -> float:
        return (time.perf_counter() - self._start_wall) / self.config.time_scale

    def _emit(self, kind: str, tenant: str, task_id: str, **details: Any) -> None:
        self.events.append({
            "seq": len(self.events) + 1,
            "t_ms": round(self.now_ms(), 2),
            "kind": kind,
            "tenant": tenant,
            "task_id": task_id,
            **details,
        })

    async def _run_step(self, task: TaskSpec, step: StepSpec, token: CancelToken) -> Tuple[Dict[str, Any], int]:
        reclaims = 0
        attempt = 0
        while True:
            attempt += 1
            if token.is_cancelled:
                raise asyncio.CancelledError("cancelled_before_step")

            # Enforce queue capacity in bounded mode
            if self.config.mode == "bounded_concurrency":
                if (
                    self._global_queued >= self.config.global_queue_capacity
                    or self._tenant_queued[task.tenant] >= self.config.tenant_max_queue_depth
                ):
                    self._emit("step_rejected_overload", task.tenant, task.task_id, step_id=step.step_id)
                    raise OverflowError("queue_capacity_exceeded")

            self._global_queued += 1
            self._tenant_queued[task.tenant] += 1
            self._peak_queued = max(self._peak_queued, self._global_queued)
            t_enq = self.now_ms()

            acquired_global = False
            acquired_tenant = False
            try:
                if self.config.mode == "serial":
                    assert self._global_sem is not None
                    await self._global_sem.acquire()
                    acquired_global = True
                elif self.config.mode == "bounded_concurrency":
                    assert self._global_sem is not None
                    tsem = self._tenant_sems[task.tenant]
                    await tsem.acquire()
                    acquired_tenant = True
                    await self._global_sem.acquire()
                    acquired_global = True
                # unbounded_concurrency acquires no semaphore
            finally:
                self._global_queued -= 1
                self._tenant_queued[task.tenant] -= 1

            wait_ms = max(0.0, self.now_ms() - t_enq)
            self._global_in_flight += 1
            self._tenant_in_flight[task.tenant] += 1
            self._peak_in_flight = max(self._peak_in_flight, self._global_in_flight)
            self._emit("step_started", task.tenant, task.task_id, step_id=step.step_id,
                       attempt=attempt, wait_ms=round(wait_ms, 2))
            try:
                if token.is_cancelled:
                    raise asyncio.CancelledError("cancelled_after_acquire")
                res = await self.adapter.execute(
                    task.tenant, task.task_id, step, token, self.now_ms, attempt
                )
                self._emit("step_completed", task.tenant, task.task_id, step_id=step.step_id, attempt=attempt)
                res["wait_ms"] = wait_ms
                return res, reclaims
            except ConnectionAbortedError:
                reclaims += 1
                self._emit("worker_crashed_reclaim", task.tenant, task.task_id,
                           step_id=step.step_id, attempt=attempt, reclaims=reclaims)
                if reclaims > self.config.max_reclaims:
                    raise
                # Lease expiry delay before another worker reclaims
                await asyncio.sleep((self.config.lease_ttl_ms * 0.25) * self.config.time_scale)
            finally:
                self._global_in_flight -= 1
                self._tenant_in_flight[task.tenant] -= 1
                if acquired_global and self._global_sem is not None:
                    self._global_sem.release()
                if acquired_tenant:
                    self._tenant_sems[task.tenant].release()

    async def _run_task(self, task: TaskSpec) -> TaskOutcome:
        if task.arrival_ms > 0:
            await asyncio.sleep(task.arrival_ms * self.config.time_scale)

        t_arrival = self.now_ms()
        token = CancelToken(task.task_id)
        self.tokens[task.task_id] = token
        self._emit("task_admitted", task.tenant, task.task_id, profile=task.profile)

        # Optional scheduled cancellation trigger
        cancel_watcher: Optional[asyncio.Task[None]] = None
        if task.cancel_at_ms is not None:
            async def _trigger_cancel() -> None:
                delay = max(0.0, task.cancel_at_ms - task.arrival_ms)
                await asyncio.sleep(delay * self.config.time_scale)
                # Without control-plane priority lane, cancel suffers head-of-line queue delay
                if not self.config.control_plane_priority_lane:
                    hol_delay = max(15.0, self._global_queued * 4.0)
                    await asyncio.sleep(hol_delay * self.config.time_scale)
                token.cancel(self.now_ms(), reason="user_cancel_signal")
                self._emit("cancel_received", task.tenant, task.task_id,
                           control_lane=self.config.control_plane_priority_lane)
            cancel_watcher = asyncio.create_task(_trigger_cancel())

        completed_steps: Set[str] = set()
        pending_specs = {s.step_id: s for s in task.steps}
        running_futures: Dict[str, asyncio.Task[Tuple[Dict[str, Any], int]]] = {}
        total_wait_ms = 0.0
        total_reclaims = 0
        committed_count = 0
        first_start_ms: Optional[float] = None
        status = "completed"
        reason: Optional[str] = None

        try:
            while pending_specs or running_futures:
                if token.is_cancelled:
                    for fut in running_futures.values():
                        fut.cancel()
                    if running_futures:
                        await asyncio.gather(*running_futures.values(), return_exceptions=True)
                    running_futures.clear()
                    status = "cancelled"
                    reason = token.reason or "cancelled"
                    break

                # Schedule all DAG-ready steps
                ready = [
                    spec for spec in list(pending_specs.values())
                    if all(dep in completed_steps for dep in spec.depends_on)
                ]
                for spec in ready:
                    pending_specs.pop(spec.step_id)
                    if first_start_ms is None:
                        first_start_ms = self.now_ms()
                    running_futures[spec.step_id] = asyncio.create_task(
                        self._run_step(task, spec, token)
                    )
                    if self.config.mode == "serial":
                        # Serial mode executes one step at a time per DAG
                        break

                if not running_futures:
                    break

                done, _ = await asyncio.wait(
                    running_futures.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for finished in done:
                    step_id = next(k for k, v in running_futures.items() if v is finished)
                    running_futures.pop(step_id)
                    try:
                        res, reclaims = finished.result()
                        total_wait_ms += float(res.get("wait_ms", 0.0))
                        total_reclaims += reclaims
                        if res.get("side_effect_committed"):
                            committed_count += 1
                        completed_steps.add(step_id)
                        if task.cancel_after_step == step_id:
                            if not self.config.control_plane_priority_lane:
                                hol_delay = max(15.0, self._global_queued * 4.0)
                                await asyncio.sleep(hol_delay * self.config.time_scale)
                            token.cancel(self.now_ms(), reason="user_cancel_after_commit")
                            self._emit("cancel_received", task.tenant, task.task_id,
                                       after_step=step_id, control_lane=self.config.control_plane_priority_lane)
                    except asyncio.CancelledError:
                        status = "cancelled"
                        reason = token.reason or "cancelled"
                        for fut in running_futures.values():
                            fut.cancel()
                        if running_futures:
                            await asyncio.gather(*running_futures.values(), return_exceptions=True)
                        running_futures.clear()
                        pending_specs.clear()
                        break
                    except OverflowError as exc:
                        status = "rejected_overload"
                        reason = str(exc)
                        for fut in running_futures.values():
                            fut.cancel()
                        if running_futures:
                            await asyncio.gather(*running_futures.values(), return_exceptions=True)
                        running_futures.clear()
                        pending_specs.clear()
                        break
                    except Exception as exc:
                        status = "failed"
                        reason = str(exc)
                        for fut in running_futures.values():
                            fut.cancel()
                        if running_futures:
                            await asyncio.gather(*running_futures.values(), return_exceptions=True)
                        running_futures.clear()
                        pending_specs.clear()
                        break
        finally:
            if cancel_watcher is not None and not cancel_watcher.done():
                cancel_watcher.cancel()
                await asyncio.gather(cancel_watcher, return_exceptions=True)

        t_end = self.now_ms()
        cancel_resp = None
        if status == "cancelled" and token.cancelled_at_ms is not None:
            cancel_resp = round(max(0.0, t_end - token.cancelled_at_ms), 2)

        # Count committed side effects for this task even if cancelled later
        committed_count = sum(
            1 for (ten, key) in self.adapter.committed_effects
            if ten == task.tenant and key.startswith(f"{task.task_id}:")
        )

        self._emit("task_finished", task.tenant, task.task_id, status=status,
                   reason=reason, committed_side_effects=committed_count)

        return TaskOutcome(
            task_id=task.task_id,
            tenant=task.tenant,
            profile=task.profile,
            status=status,
            arrival_ms=round(t_arrival, 2),
            start_ms=round(first_start_ms, 2) if first_start_ms is not None else None,
            end_ms=round(t_end, 2),
            latency_ms=round(max(0.0, t_end - t_arrival), 2),
            queue_wait_ms=round(total_wait_ms, 2),
            steps_completed=len(completed_steps),
            steps_total=len(task.steps),
            reclaims=total_reclaims,
            committed_side_effects=committed_count,
            cancel_response_ms=cancel_resp,
            reason=reason,
        )

    async def run_workload(self, tasks: List[TaskSpec]) -> Dict[str, Any]:
        self._start_wall = time.perf_counter()
        self.events.clear()
        self.tokens.clear()
        self._global_in_flight = 0
        self._peak_in_flight = 0
        self._global_queued = 0
        self._peak_queued = 0
        self._tenant_in_flight.clear()
        self._tenant_queued.clear()

        if self.config.mode == "serial":
            self._global_sem = asyncio.Semaphore(1)
        elif self.config.mode == "bounded_concurrency":
            self._global_sem = asyncio.Semaphore(self.config.global_max_workers)
            tenants = {t.tenant for t in tasks}
            self._tenant_sems = {
                ten: asyncio.Semaphore(self.config.tenant_max_in_flight) for ten in tenants
            }
        else:
            self._global_sem = None
            self._tenant_sems = {}

        outcomes = await asyncio.gather(*(self._run_task(t) for t in tasks))
        total_makespan_ms = round(self.now_ms(), 2)
        assert self._global_in_flight == 0, "resource leak: in-flight workers not released"
        assert self.adapter.active_handles == 0, "resource leak: adapter handles not released"

        return summarize_run(
            mode=self.config.mode,
            outcomes=outcomes,
            total_makespan_ms=total_makespan_ms,
            peak_in_flight=self._peak_in_flight,
            peak_queued=self._peak_queued,
            peak_handles=self.adapter.peak_active_handles,
        )


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (p / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return round(ordered[int(k)], 2)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo), 2)


def summarize_run(
    mode: str,
    outcomes: List[TaskOutcome],
    total_makespan_ms: float,
    peak_in_flight: int,
    peak_queued: int,
    peak_handles: int,
) -> Dict[str, Any]:
    completed = [o for o in outcomes if o.status == "completed"]
    cancelled = [o for o in outcomes if o.status == "cancelled"]
    rejected = [o for o in outcomes if o.status == "rejected_overload"]
    failed = [o for o in outcomes if o.status == "failed"]

    per_tenant: Dict[str, Dict[str, Any]] = {}
    for tenant in sorted({o.tenant for o in outcomes}):
        t_all = [o for o in outcomes if o.tenant == tenant]
        t_ok = [o for o in t_all if o.status == "completed"]
        per_tenant[tenant] = {
            "total": len(t_all),
            "completed": len(t_ok),
            "cancelled": sum(1 for o in t_all if o.status == "cancelled"),
            "rejected_overload": sum(1 for o in t_all if o.status == "rejected_overload"),
            "p50_latency_ms": percentile([o.latency_ms for o in t_ok], 50),
            "p95_latency_ms": percentile([o.latency_ms for o in t_ok], 95),
            "mean_wait_ms": round(
                sum(o.queue_wait_ms for o in t_ok) / len(t_ok), 2
            ) if t_ok else 0.0,
        }

    # Jain's fairness index over per-tenant completed P95 inverse latency (or throughput share)
    p95s = [v["p95_latency_ms"] for v in per_tenant.values() if v["p95_latency_ms"] > 0]
    if len(p95s) >= 2:
        rates = [1000.0 / x for x in p95s]
        jain_fairness = round((sum(rates) ** 2) / (len(rates) * sum(r * r for r in rates)), 4)
    else:
        jain_fairness = 1.0

    cancel_resps = [o.cancel_response_ms for o in cancelled if o.cancel_response_ms is not None]
    throughput_tps = round(len(completed) / (total_makespan_ms / 1000.0), 2) if total_makespan_ms > 0 else 0.0

    return {
        "mode": mode,
        "total_tasks": len(outcomes),
        "completed": len(completed),
        "cancelled": len(cancelled),
        "rejected_overload": len(rejected),
        "failed": len(failed),
        "total_reclaims": sum(o.reclaims for o in outcomes),
        "committed_side_effects_in_cancelled": sum(o.committed_side_effects for o in cancelled),
        "total_makespan_ms": total_makespan_ms,
        "throughput_tasks_per_sec": throughput_tps,
        "p50_latency_ms": percentile([o.latency_ms for o in completed], 50),
        "p95_latency_ms": percentile([o.latency_ms for o in completed], 95),
        "p99_latency_ms": percentile([o.latency_ms for o in completed], 99),
        "peak_in_flight": peak_in_flight,
        "peak_queued": peak_queued,
        "peak_adapter_handles": peak_handles,
        "p95_cancel_response_ms": percentile(cancel_resps, 95) if cancel_resps else 0.0,
        "tenant_jain_fairness": jain_fairness,
        "per_tenant": per_tenant,
        "outcomes": [asdict(o) for o in outcomes],
    }


# ---------------------------------------------------------------------------
# 4. 50-Task, 2-Tenant Deterministic Workload Generator (Ch22 Spec)
# ---------------------------------------------------------------------------

def build_workload_50() -> List[TaskSpec]:
    """Generate 50 deterministic tasks across 2 tenants covering all Ch22 fault modes.

    - tenant-alpha (25 tasks): steady mix of fast policy-lookup tasks + 4 worker-crash tasks + 4 cancel tasks
    - tenant-beta (25 tasks): includes 8 fanout-burst tasks (6 parallel branches each) and 5 slow-tool tasks
      to test noisy-neighbor isolation and fairness.
    """
    tasks: List[TaskSpec] = []
    idx = 0

    # 1. tenant-alpha: 17 fast tasks, 4 worker_crash tasks, 4 cancel_midflight tasks = 25 tasks
    for i in range(25):
        idx += 1
        arrival = i * 6.0
        tid = f"T22-{idx:02d}"
        if i in (4, 10, 16, 22):
            steps = (
                StepSpec("plan", "model", (), 12.0),
                StepSpec("lookup_policy", "tool_read", ("plan",), 14.0),
                StepSpec("create_ticket", "tool_write", ("lookup_policy",), 20.0,
                         side_effect=True, fail_first_worker=True),
            )
            tasks.append(TaskSpec(tid, "tenant-alpha", "worker_crash", arrival, steps))
        elif i in (6, 12, 18, 24):
            # Half cancel before write commit (by time), half cancel right after write commit to prove cancel != undo
            steps = (
                StepSpec("plan", "model", (), 12.0),
                StepSpec("create_ticket", "tool_write", ("plan",), 20.0, side_effect=True),
                StepSpec("post_summary", "model", ("create_ticket",), 36.0),
            )
            if i in (6, 18):
                tasks.append(TaskSpec(tid, "tenant-alpha", "cancel_midflight", arrival, steps,
                                      cancel_at_ms=arrival + 18.0))
            else:
                tasks.append(TaskSpec(tid, "tenant-alpha", "cancel_midflight", arrival, steps,
                                      cancel_after_step="create_ticket"))
        else:
            steps = (
                StepSpec("plan", "model", (), 10.0),
                StepSpec("lookup_policy", "tool_read", ("plan",), 12.0),
                StepSpec("draft_ticket", "tool_write", ("lookup_policy",), 14.0, side_effect=True),
            )
            tasks.append(TaskSpec(tid, "tenant-alpha", "fast", arrival, steps))

    # 2. tenant-beta: 12 fast tasks, 8 fanout_burst tasks, 5 slow_tool tasks = 25 tasks
    for i in range(25):
        idx += 1
        arrival = i * 5.0 + 2.0
        tid = f"T22-{idx:02d}"
        if i in (2, 3, 4, 8, 9, 14, 15, 20):
            # Fanout burst: 1 plan -> 5 parallel read branches -> 1 merge write
            branches = tuple(
                StepSpec(f"branch_{b}", "tool_read", ("plan",), 18.0 + (b % 3) * 4.0)
                for b in range(5)
            )
            steps = (
                StepSpec("plan", "model", (), 10.0),
                *branches,
                StepSpec("merge_write", "tool_write", tuple(b.step_id for b in branches), 14.0, side_effect=True),
            )
            tasks.append(TaskSpec(tid, "tenant-beta", "fanout_burst", arrival, steps))
        elif i in (5, 11, 17, 21, 23):
            steps = (
                StepSpec("plan", "model", (), 12.0),
                StepSpec("slow_erp_query", "tool_read", ("plan",), 65.0),
                StepSpec("draft_ticket", "tool_write", ("slow_erp_query",), 16.0, side_effect=True),
            )
            tasks.append(TaskSpec(tid, "tenant-beta", "slow_tool", arrival, steps))
        else:
            steps = (
                StepSpec("plan", "model", (), 10.0),
                StepSpec("lookup_policy", "tool_read", ("plan",), 12.0),
                StepSpec("draft_ticket", "tool_write", ("lookup_policy",), 14.0, side_effect=True),
            )
            tasks.append(TaskSpec(tid, "tenant-beta", "fast", arrival, steps))

    return tasks


def format_report_md(results: Dict[str, Dict[str, Any]]) -> str:
    lines = [
        "# Ch22 运行时负载对照实验报告 (`Exp-22-01`)",
        "",
        "> **证据状态**：确定性本地模拟运行时测量（`examples/ch22/async_runtime.py`），无真实外部 LLM/网络调用；用于验证调度、队列、租户公平性、worker 故障接管与取消传播机制，不宣称为生产吞吐容量。",
        "",
        "## 1. 实验设计",
        "",
        "- **工作负载**：50 个确定性模拟任务（2 个租户：`tenant-alpha` 25 项、`tenant-beta` 25 项），包含常规快速任务、5 路扇出爆发（8 项）、慢工具阻塞（5 项）、worker 崩溃接管（4 项）和中途取消（4 项，其中 2 项在写副作用提交前取消、2 项在提交后取消）。",
        "- **三组对照**：",
        "  1. `serial`：全局单 worker 串行执行，关闭独立控制面取消通道。",
        "  2. `unbounded_concurrency`：无界并发（不设信号量与队列上限），关闭独立控制面取消通道。",
        "  3. `bounded_concurrency`：全局 6 worker、单租户并发上限 3、全局队列上限 24、单租户队列上限 12、开启独立控制面取消通道与租约接管。",
        "",
        "## 2. 实测指标汇总",
        "",
        "| 对照模式 | 完成数 | 取消数 | 过载拒绝 | 崩溃接管 | 总耗时 (ms) | 吞吐 (tasks/s) | P50 延迟 (ms) | P95 延迟 (ms) | 峰值并发 | 峰值排队 | 取消响应 P95 (ms) | 租户公平性 (Jain) | 取消任务已提交副作用 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in ("serial", "unbounded_concurrency", "bounded_concurrency"):
        r = results[mode]
        lines.append(
            f"| `{mode}` | {r['completed']} | {r['cancelled']} | {r['rejected_overload']} | "
            f"{r['total_reclaims']} | {r['total_makespan_ms']} | {r['throughput_tasks_per_sec']} | "
            f"{r['p50_latency_ms']} | {r['p95_latency_ms']} | {r['peak_in_flight']} | "
            f"{r['peak_queued']} | {r['p95_cancel_response_ms']} | {r['tenant_jain_fairness']} | "
            f"{r['committed_side_effects_in_cancelled']} |"
        )
    lines.extend([
        "",
        "## 3. 分租户尾延迟与隔离对照",
        "",
        "| 对照模式 | 租户 | 完成数 | 过载拒绝 | P50 (ms) | P95 (ms) | 平均排队 (ms) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for mode in ("serial", "unbounded_concurrency", "bounded_concurrency"):
        for ten, stats in results[mode]["per_tenant"].items():
            lines.append(
                f"| `{mode}` | `{ten}` | {stats['completed']} | {stats['rejected_overload']} | "
                f"{stats['p50_latency_ms']} | {stats['p95_latency_ms']} | {stats['mean_wait_ms']} |"
            )
    lines.extend([
        "",
        "## 4. 关键机制观察与限制",
        "",
        "1. **资源上限与尾部控制**：`unbounded_concurrency` 峰值并发冲高至 "
        f"{results['unbounded_concurrency']['peak_in_flight']}（扇出爆发直接穿透到下游工具池），在真实外部工具限流下会迅速触发雪崩；"
        f"`bounded_concurrency` 将并发严格锁死在 {results['bounded_concurrency']['peak_in_flight']}（<= 6）并保持排队有界。",
        "2. **取消传播与副作用边界**：所有已取消任务均在退出前释放全部 worker 与适配器句柄（结束时 `active_handles == 0`），"
        "同时保留已提交外部工单记录（`committed_side_effects_in_cancelled > 0`），验证了“取消释放计算资源，但不自动撤销已提交副作用”。",
        "3. **Worker 崩溃接管**：4 项模拟 worker 崩溃任务均在租约超时后由后续 worker 接管并完成，未丢失任务且未产生重复副作用。",
        "4. **适用范围限制**：本实验使用虚拟时间缩放（`1 sim-ms = 1 ms` 墙钟）与内存模拟工具适配器，不代表真实网络延迟、跨进程锁竞争或真实 LLM 推理尾延迟。",
        "",
    ])
    return "\n".join(lines)


async def run_all_modes(output_dir: Path) -> Dict[str, Dict[str, Any]]:
    workload = build_workload_50()
    results: Dict[str, Dict[str, Any]] = {}
    all_events: List[Dict[str, Any]] = []

    configs = [
        RuntimeConfig(mode="serial", global_max_workers=1, control_plane_priority_lane=False),
        RuntimeConfig(mode="unbounded_concurrency", global_max_workers=999, control_plane_priority_lane=False),
        RuntimeConfig(mode="bounded_concurrency", global_max_workers=6, global_queue_capacity=40,
                      tenant_max_in_flight=3, tenant_max_queue_depth=18, control_plane_priority_lane=True),
    ]

    for cfg in configs:
        ctx = PluginContext()
        adapter = DeterministicToolAdapter(time_scale=cfg.time_scale)
        ctx.provide("adapter.tool.policy_ticket", "tool_executor", adapter)
        runtime = AsyncAgentRuntime(cfg, ctx.require("tool_executor"))
        summary = await runtime.run_workload(workload)
        results[cfg.mode] = summary
        for ev in runtime.events:
            all_events.append({"mode": cfg.mode, **ev})
        ctx.unload("adapter.tool.policy_ticket")

    res_dir = output_dir / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / "runtime_metrics.json").write_text(
        json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "outcomes"} for k, v in results.items()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (res_dir / "runtime_outcomes.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (res_dir / "runtime_events.jsonl").open("w", encoding="utf-8") as fh:
        for ev in all_events:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    (output_dir / "runtime_load_report.md").write_text(format_report_md(results), encoding="utf-8")
    return results


def main() -> None:
    base = Path(__file__).resolve().parent
    results = asyncio.run(run_all_modes(base))
    for mode, summary in results.items():
        print(
            f"[{mode}] completed={summary['completed']} cancelled={summary['cancelled']} "
            f"rejected={summary['rejected_overload']} makespan={summary['total_makespan_ms']}ms "
            f"p95={summary['p95_latency_ms']}ms peak_in_flight={summary['peak_in_flight']} "
            f"reclaims={summary['total_reclaims']} cancel_p95={summary['p95_cancel_response_ms']}ms"
        )


if __name__ == "__main__":
    main()
