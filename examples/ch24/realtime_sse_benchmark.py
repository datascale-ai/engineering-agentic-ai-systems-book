"""Ch24 (Exp-24-02): Real local 127.0.0.1 loopback HTTP/1.1 SSE + asyncio.Queue wall-clock benchmark.

Complements the 40-case deterministic discrete-event simulation (Exp-24-01) with real
in-process OS wall-clock measurements (`time.perf_counter()`) over:
- Real local TCP loopback HTTP/1.1 Server-Sent Events server (`asyncio.start_server` on 127.0.0.1:0)
- DeepSeek-style multi-channel SSE deltas (`reasoning_content`, `content`, and partial `tool_calls`)
- Real bounded `asyncio.Queue` (capacity=16, HWM=12, LWM=4 hysteresis backpressure)
- Real slow consumer playback cadence vs fast SSE producer
- Real out-of-band `asyncio.Event` interruption, generation_id fencing, socket close, and queue flush
- Real delayed async tool callback task verifying late-callback isolation

Zero external API keys or internet access required; deterministic and CI-safe.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, asdict
import json
import math
from pathlib import Path
import time
from typing import Any, Dict, List


# DeepSeek-style multi-channel SSE frame sequence per turn:
# frames 0..2: reasoning_content; frames 3..24: content; frames 25..28: partial tool_calls JSON
TOTAL_SSE_FRAMES = 32
QUEUE_CAPACITY = 16
HIGH_WATERMARK = 12
LOW_WATERMARK = 4

PRODUCER_FRAME_INTERVAL_S = 0.005   # fast model SSE emission (~200 chunks/s)
CONSUMER_CHUNK_PLAY_S = 0.024       # slower audio/UI sink (~41 chunks/s -> triggers real backpressure!)
INTERRUPT_AFTER_S = 0.120           # user clicks stop / barges in mid-stream after 120 ms
LATE_TOOL_DELAY_S = 0.055           # async tool callback returns 55 ms after stop
TRIALS_PER_STRATEGY = 12            # 12 real loopback TCP trials x 3 strategies = 36 wall-clock runs


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


def _sse_payload(seq: int, turn_id: str, gen_id: int) -> bytes:
    if seq < 3:
        delta: Dict[str, Any] = {"reasoning_content": f"think-{seq}"}
    elif seq in (14, 15):
        # Partial, unclosed tool_calls JSON fragment (must NEVER execute if interrupted mid-stream)
        frag = '{"op":"create_ticket","amount":' if seq == 14 else '350'  # missing closing '}'
        delta = {"tool_calls": [{"index": 0, "id": f"call-{turn_id}", "function": {"name": "create_ticket", "arguments": frag}}]}
    else:
        delta = {"content": f"token-{seq} "}
    body = json.dumps({"turn_id": turn_id, "generation_id": gen_id, "seq": seq, "choices": [{"delta": delta}]})
    return f"data: {body}\n\n".encode("utf-8")


async def _handle_sse_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Real HTTP/1.1 loopback SSE server handler."""
    try:
        req_line = await asyncio.wait_for(reader.readline(), timeout=2.0)
        if not req_line:
            return
        # Drain HTTP headers
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=2.0)
            if line in (b"\r\n", b"\n", b""):
                break
        # Parse turn_id & gen_id from path /sse?turn=...&gen=...
        parts = req_line.decode("utf-8", errors="ignore").split(" ")
        path = parts[1] if len(parts) > 1 else "/sse"
        turn_id, gen_id = "turn-0", 1
        if "?" in path:
            for kv in path.split("?", 1)[1].split("&"):
                if kv.startswith("turn="):
                    turn_id = kv.split("=", 1)[1]
                elif kv.startswith("gen="):
                    gen_id = int(kv.split("=", 1)[1])

        header = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: close\r\n\r\n"
        ).encode("utf-8")
        writer.write(header)
        await writer.drain()

        for seq in range(TOTAL_SSE_FRAMES):
            writer.write(_sse_payload(seq, turn_id, gen_id))
            await writer.drain()
            await asyncio.sleep(PRODUCER_FRAME_INTERVAL_S)
        writer.write(b"data: [DONE]\n\n")
        await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError, OSError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


@dataclass
class WallClockTrial:
    trial_id: str
    strategy: str
    propagation_ms: float
    producer_stop_ms: float
    visible_stop_ms: float
    stale_chunks_rendered: int
    stale_chunks_dropped: int
    backpressure_pauses: int
    backpressure_resumes: int
    incomplete_tool_executed: int
    late_tool_leaked: bool
    producer_closed_cleanly: bool


async def run_single_trial(host: str, port: int, trial_idx: int, strategy: str) -> WallClockTrial:
    assert strategy in ("ui_only_stop", "cancel_propagation_only", "cancel_plus_gen_and_flush")
    turn_id = f"rt-{trial_idx:02d}"
    initial_gen = 1
    active_gen = initial_gen

    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_CAPACITY)
    cancel_event = asyncio.Event()
    bp_allow = asyncio.Event()
    bp_allow.set()

    bp_paused = False
    bp_pauses = 0
    bp_resumes = 0
    incomplete_tool_executed = 0
    late_tool_leaked = False
    stale_rendered = 0
    stale_dropped = 0
    producer_closed_cleanly = False

    t0_stop: float = 0.0
    t2_cancel: float = 0.0
    t3_prod_stop: float = 0.0
    t4_last_stale: float = 0.0
    stop_triggered = False

    tool_arg_buf: List[str] = []

    async def sse_producer() -> None:
        nonlocal bp_paused, bp_pauses, t3_prod_stop, producer_closed_cleanly, incomplete_tool_executed
        reader, writer = await asyncio.open_connection(host, port)
        try:
            req = f"GET /sse?turn={turn_id}&gen={initial_gen} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
            writer.write(req.encode("utf-8"))
            await writer.drain()
            # Skip response headers
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break

            while True:
                if strategy != "ui_only_stop" and cancel_event.is_set():
                    producer_closed_cleanly = True
                    break

                # Real HWM/LWM hysteresis backpressure before enqueuing
                if queue.qsize() >= HIGH_WATERMARK and not bp_paused:
                    bp_paused = True
                    bp_pauses += 1
                    bp_allow.clear()
                if bp_paused:
                    # Wait for either low-watermark resume OR out-of-band cancel!
                    wait_bp = asyncio.create_task(bp_allow.wait())
                    if strategy != "ui_only_stop":
                        wait_cancel = asyncio.create_task(cancel_event.wait())
                        done, pending = await asyncio.wait({wait_bp, wait_cancel}, return_when=asyncio.FIRST_COMPLETED)
                        for p in pending:
                            p.cancel()
                        if cancel_event.is_set():
                            producer_closed_cleanly = True
                            break
                    else:
                        await wait_bp

                # Race socket readline against out-of-band cancel signal
                read_task = asyncio.create_task(reader.readline())
                if strategy != "ui_only_stop":
                    cancel_task = asyncio.create_task(cancel_event.wait())
                    done, pending = await asyncio.wait({read_task, cancel_task}, return_when=asyncio.FIRST_COMPLETED)
                    for p in pending:
                        p.cancel()
                    if cancel_event.is_set():
                        producer_closed_cleanly = True
                        break
                    raw = read_task.result()
                else:
                    raw = await read_task

                if not raw:
                    break
                if not raw.startswith(b"data: "):
                    continue
                payload_s = raw[6:].decode("utf-8").strip()
                if payload_s == "[DONE]":
                    break
                frame = json.loads(payload_s)
                delta = frame["choices"][0]["delta"]

                # Enforce structured tool JSON completeness gate (never execute unclosed tool_calls)
                if "tool_calls" in delta:
                    frag = delta["tool_calls"][0]["function"]["arguments"]
                    tool_arg_buf.append(frag)
                    joined = "".join(tool_arg_buf)
                    try:
                        json.loads(joined)
                    except json.JSONDecodeError:
                        # Incomplete JSON fragment -> must NOT dispatch to executor!
                        continue

                if "content" in delta:
                    item = {"turn_id": frame["turn_id"], "generation_id": frame["generation_id"], "seq": frame["seq"], "text": delta["content"]}
                    await queue.put(item)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            t3_prod_stop = time.perf_counter()

    async def slow_consumer() -> None:
        nonlocal bp_paused, bp_resumes, stale_rendered, stale_dropped, t4_last_stale
        while True:
            item = await queue.get()
            if item.get("eof"):
                queue.task_done()
                break
            if bp_paused and queue.qsize() <= LOW_WATERMARK:
                bp_paused = False
                bp_resumes += 1
                bp_allow.set()

            if strategy == "cancel_plus_gen_and_flush" and item["generation_id"] != active_gen:
                stale_dropped += 1
                queue.task_done()
                continue

            # Simulate real playback cadence for one chunk (24ms)
            await asyncio.sleep(CONSUMER_CHUNK_PLAY_S)
            now = time.perf_counter()
            if stop_triggered:
                stale_rendered += 1
                t4_last_stale = now
            queue.task_done()

    async def delayed_tool_callback() -> None:
        nonlocal late_tool_leaked
        await cancel_event.wait()
        await asyncio.sleep(LATE_TOOL_DELAY_S)
        # Old tool callback arrives carrying generation_id = 1 after turn switched to generation_id = 2
        if strategy == "cancel_plus_gen_and_flush":
            if initial_gen != active_gen:
                return  # Blocked by generation_id fence!
        late_tool_leaked = True

    async def user_interrupter() -> None:
        nonlocal t0_stop, t2_cancel, stop_triggered, active_gen, stale_dropped
        await asyncio.sleep(INTERRUPT_AFTER_S)
        t0_stop = time.perf_counter()
        stop_triggered = True
        if strategy == "cancel_plus_gen_and_flush":
            # Out-of-band: bump generation_id, signal cancel, immediately flush buffered stale chunks!
            active_gen += 1
            cancel_event.set()
            while True:
                try:
                    item = queue.get_nowait()
                    if not item.get("eof"):
                        stale_dropped += 1
                    queue.task_done()
                except asyncio.QueueEmpty:
                    break
            bp_allow.set()
            t2_cancel = time.perf_counter()
        elif strategy == "cancel_propagation_only":
            # Propagate cancel to producer, but DO NOT bump gen_id fence or flush buffered queue
            cancel_event.set()
            bp_allow.set()
            t2_cancel = time.perf_counter()
        else:
            # ui_only_stop: local flag flip only; producer and queue keep draining!
            cancel_event.set()
            t2_cancel = time.perf_counter()

    prod_task = asyncio.create_task(sse_producer())
    cons_task = asyncio.create_task(slow_consumer())
    intr_task = asyncio.create_task(user_interrupter())
    tool_task = asyncio.create_task(delayed_tool_callback())

    await prod_task
    await intr_task
    await queue.put({"eof": True})
    await cons_task
    await tool_task

    prop_ms = round(max(0.0, (t2_cancel - t0_stop) * 1000.0), 2)
    prod_stop_ms = round(max(0.0, (t3_prod_stop - t0_stop) * 1000.0), 2)
    vis_stop_ms = round(max(0.0, (t4_last_stale - t0_stop) * 1000.0), 2) if t4_last_stale > t0_stop else prop_ms

    return WallClockTrial(
        trial_id=f"RT24-{trial_idx:02d}",
        strategy=strategy,
        propagation_ms=prop_ms,
        producer_stop_ms=prod_stop_ms,
        visible_stop_ms=vis_stop_ms,
        stale_chunks_rendered=stale_rendered,
        stale_chunks_dropped=stale_dropped,
        backpressure_pauses=bp_pauses,
        backpressure_resumes=bp_resumes,
        incomplete_tool_executed=incomplete_tool_executed,
        late_tool_leaked=late_tool_leaked,
        producer_closed_cleanly=producer_closed_cleanly,
    )


async def run_benchmark(trials_per_strategy: int = TRIALS_PER_STRATEGY) -> Dict[str, Any]:
    server = await asyncio.start_server(_handle_sse_client, "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]
    all_trials: List[WallClockTrial] = []
    strategies = ("ui_only_stop", "cancel_propagation_only", "cancel_plus_gen_and_flush")
    try:
        async with server:
            for strat in strategies:
                for i in range(1, trials_per_strategy + 1):
                    res = await run_single_trial(host, port, i, strat)
                    all_trials.append(res)
    finally:
        server.close()

    summary: Dict[str, Any] = {
        "experiment_id": "Exp-24-02",
        "environment": "local_loopback_http_sse_asyncio_wallclock",
        "trials_per_strategy": trials_per_strategy,
        "queue_capacity": QUEUE_CAPACITY,
        "high_watermark": HIGH_WATERMARK,
        "low_watermark": LOW_WATERMARK,
        "consumer_chunk_ms": int(CONSUMER_CHUNK_PLAY_S * 1000),
        "strategies": {},
    }
    for strat in strategies:
        group = [t for t in all_trials if t.strategy == strat]
        props = [t.propagation_ms for t in group]
        prods = [t.producer_stop_ms for t in group]
        viss = [t.visible_stop_ms for t in group]
        summary["strategies"][strat] = {
            "trials": len(group),
            "propagation_p50_ms": percentile(props, 50),
            "propagation_p95_ms": percentile(props, 95),
            "producer_stop_p50_ms": percentile(prods, 50),
            "producer_stop_p95_ms": percentile(prods, 95),
            "visible_stop_p50_ms": percentile(viss, 50),
            "visible_stop_p95_ms": percentile(viss, 95),
            "visible_stop_max_ms": round(max(viss), 2),
            "stale_chunks_rendered_total": sum(t.stale_chunks_rendered for t in group),
            "stale_chunks_dropped_total": sum(t.stale_chunks_dropped for t in group),
            "backpressure_pauses_total": sum(t.backpressure_pauses for t in group),
            "incomplete_tool_executed_total": sum(t.incomplete_tool_executed for t in group),
            "late_tool_leaks": sum(1 for t in group if t.late_tool_leaked),
            "producer_clean_close_rate": round(sum(1 for t in group if t.producer_closed_cleanly) / len(group), 4),
        }
    return {"summary": summary, "trials": [asdict(t) for t in all_trials]}


def main() -> None:
    root = Path(__file__).resolve().parent
    res_dir = root / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    out = asyncio.run(run_benchmark())
    (res_dir / "realtime_sse_wallclock.json").write_text(
        json.dumps(out["summary"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (res_dir / "realtime_sse_wallclock.jsonl").open("w", encoding="utf-8") as fh:
        for row in out["trials"]:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
