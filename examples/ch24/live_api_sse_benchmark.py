"""Ch24 (Exp-24-03): Live OpenAI-compatible HTTPS/TLS SSE streaming interruption benchmark.

Measures real wall-clock interruption behavior (`time.perf_counter()`) against a live LLM
chat-completions streaming endpoint (e.g., `gpt-6.2-astra`) using only Python stdlib:
- Real HTTPS/TLS Server-Sent Events stream (`stream=True`)
- Real bounded `asyncio.Queue` (cap=16, HWM=12, LWM=4) feeding a rate-mismatched slow consumer
- Mid-stream interruption triggered dynamically once 12 live SSE content chunks have arrived
- Compares 3 strategies (`ui_only_stop`, `cancel_propagation_only`, `cancel_plus_gen_and_flush`)
  on real producer socket close latency, wasted post-stop SSE chunks, visible stop latency,
  stale chunks rendered/dropped, and late async tool callback isolation.

Privacy & CI policy:
- Credentials and endpoint URL are read strictly from environment variables:
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
- Neither credentials nor private endpoint hostnames/IPs are written into output reports.
- Offline CI (`pytest`) does NOT invoke live network calls; readers with an API key can
  reproduce locally by setting the environment variables above.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, asdict
import http.client
import json
import math
import os
from pathlib import Path
import ssl
import sys
import threading
import time
from typing import Any, Dict, List
from urllib.parse import urlparse


QUEUE_CAPACITY = 16
HIGH_WATERMARK = 12
LOW_WATERMARK = 4
INTERRUPT_AFTER_CHUNKS = 20     # interrupt live stream once 20 real content deltas arrive
CONSUMER_CHUNK_PLAY_S = 0.025   # 25 ms/chunk simulated speech/UI playback -> creates real backlog
LATE_TOOL_DELAY_S = 0.060       # 60 ms delayed async tool callback
TRIALS_PER_STRATEGY = 5         # 5 live HTTPS SSE trials x 3 strategies = 15 live calls
MAX_TOKENS = 140

PROMPT = (
    "请用中文分 4 条简短列出企业差旅报销审批的核心步骤（事前申请、标准核验、超额审批、财务归档），"
    "每条一句话，总字数严格控制在 120 字以内。"
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


@dataclass
class LiveSseTrial:
    trial_id: str
    strategy: str
    model: str
    ttft_ms: float
    propagation_ms: float
    producer_stop_ms: float
    visible_stop_ms: float
    chunks_before_stop: int
    chunks_received_after_stop: int
    stale_chunks_rendered: int
    stale_chunks_dropped: int
    late_tool_leaked: bool
    socket_aborted_on_cancel: bool


async def run_live_trial(
    base_url: str,
    api_key: str,
    model: str,
    trial_idx: int,
    strategy: str,
) -> LiveSseTrial:
    assert strategy in ("ui_only_stop", "cancel_propagation_only", "cancel_plus_gen_and_flush")
    parsed = urlparse(base_url.rstrip("/"))
    scheme = parsed.scheme or "https"
    host = parsed.hostname or ""
    port = parsed.port or (443 if scheme == "https" else 80)
    path = (parsed.path.rstrip("/") + "/chat/completions")

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_CAPACITY)
    interrupt_ready = asyncio.Event()
    cancel_event = asyncio.Event()

    initial_gen = 1
    active_gen = initial_gen
    stop_triggered = False
    socket_aborted = False

    t_req_start = time.perf_counter()
    ttft_ms = 0.0
    t0_stop = 0.0
    t2_cancel = 0.0
    t3_prod_stop = 0.0
    t4_last_stale = 0.0

    chunks_before_stop = 0
    chunks_after_stop = 0
    stale_rendered = 0
    stale_dropped = 0
    late_tool_leaked = False

    # Shared connection handle so out-of-band cancel can immediately abort the live TLS socket!
    conn_box: Dict[str, Any] = {"conn": None, "sock": None, "abort_flag": False}

    def abort_live_socket() -> None:
        nonlocal socket_aborted
        conn_box["abort_flag"] = True
        sock = conn_box.get("sock")
        conn = conn_box.get("conn")
        try:
            if sock is not None:
                sock.shutdown(2)  # SHUT_RDWR to wake blocked TLS recv immediately
        except Exception:
            pass
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
        socket_aborted = True

    def blocking_sse_reader() -> None:
        nonlocal ttft_ms, chunks_before_stop, chunks_after_stop, t3_prod_stop
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "stream": True,
            "max_tokens": MAX_TOKENS,
            "temperature": 0.2,
        }).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Connection": "close",
        }
        ctx = ssl.create_default_context()
        if scheme == "https":
            conn = http.client.HTTPSConnection(host, port, timeout=30, context=ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=30)
        conn_box["conn"] = conn
        try:
            conn.request("POST", path, body=body, headers=headers)
            conn_box["sock"] = conn.sock
            resp = conn.getresponse()
            if resp.status != 200:
                err_txt = resp.read().decode("utf-8", errors="replace")[:200]
                raise RuntimeError(f"Live SSE HTTP {resp.status}: {err_txt}")
            seq = 0
            while True:
                if conn_box["abort_flag"]:
                    break
                raw = resp.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data_s = line[5:].strip()
                if data_s == "[DONE]":
                    break
                obj = json.loads(data_s)
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content") or delta.get("reasoning_content")
                if not content:
                    continue
                seq += 1
                if ttft_ms == 0.0:
                    ttft_ms = round((time.perf_counter() - t_req_start) * 1000.0, 2)
                if stop_triggered:
                    chunks_after_stop += 1
                else:
                    chunks_before_stop += 1
                item = {"generation_id": initial_gen, "seq": seq, "text": content}
                # Put into bounded queue; drop silently if aborted during put
                fut = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
                while not fut.done():
                    if conn_box["abort_flag"]:
                        fut.cancel()
                        break
                    time.sleep(0.002)
                if chunks_before_stop == INTERRUPT_AFTER_CHUNKS and not stop_triggered:
                    loop.call_soon_threadsafe(interrupt_ready.set)
        except Exception:
            if not conn_box["abort_flag"]:
                raise
        finally:
            t3_prod_stop = time.perf_counter()
            try:
                conn.close()
            except Exception:
                pass
            loop.call_soon_threadsafe(interrupt_ready.set)
            asyncio.run_coroutine_threadsafe(queue.put({"eof": True}), loop)

    async def slow_consumer() -> None:
        nonlocal stale_rendered, stale_dropped, t4_last_stale
        while True:
            item = await queue.get()
            if item.get("eof"):
                queue.task_done()
                break
            if strategy == "cancel_plus_gen_and_flush" and item["generation_id"] != active_gen:
                stale_dropped += 1
                queue.task_done()
                continue
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
        if strategy == "cancel_plus_gen_and_flush" and initial_gen != active_gen:
            return
        late_tool_leaked = True

    async def user_interrupter() -> None:
        nonlocal t0_stop, t2_cancel, stop_triggered, active_gen, stale_dropped
        await interrupt_ready.wait()
        t0_stop = time.perf_counter()
        stop_triggered = True
        if strategy == "cancel_plus_gen_and_flush":
            active_gen += 1
            cancel_event.set()
            abort_live_socket()
            while True:
                try:
                    item = queue.get_nowait()
                    if item.get("eof"):
                        await queue.put(item)
                        queue.task_done()
                        break
                    stale_dropped += 1
                    queue.task_done()
                except asyncio.QueueEmpty:
                    break
            t2_cancel = time.perf_counter()
        elif strategy == "cancel_propagation_only":
            cancel_event.set()
            abort_live_socket()
            t2_cancel = time.perf_counter()
        else:
            cancel_event.set()
            t2_cancel = time.perf_counter()

    reader_thread = threading.Thread(target=blocking_sse_reader, daemon=True)
    reader_thread.start()

    cons_task = asyncio.create_task(slow_consumer())
    intr_task = asyncio.create_task(user_interrupter())
    tool_task = asyncio.create_task(delayed_tool_callback())

    await intr_task
    await asyncio.to_thread(reader_thread.join)
    await cons_task
    await tool_task

    prop_ms = round(max(0.0, (t2_cancel - t0_stop) * 1000.0), 2)
    prod_stop_ms = round(max(0.0, (t3_prod_stop - t0_stop) * 1000.0), 2)
    vis_stop_ms = round(max(0.0, (t4_last_stale - t0_stop) * 1000.0), 2) if t4_last_stale > t0_stop else prop_ms

    return LiveSseTrial(
        trial_id=f"LIVE24-{strategy[:4].upper()}-{trial_idx:02d}",
        strategy=strategy,
        model=model,
        ttft_ms=ttft_ms,
        propagation_ms=prop_ms,
        producer_stop_ms=prod_stop_ms,
        visible_stop_ms=vis_stop_ms,
        chunks_before_stop=chunks_before_stop,
        chunks_received_after_stop=chunks_after_stop,
        stale_chunks_rendered=stale_rendered,
        stale_chunks_dropped=stale_dropped,
        late_tool_leaked=late_tool_leaked,
        socket_aborted_on_cancel=socket_aborted,
    )


async def run_all(base_url: str, api_key: str, model: str, trials: int = TRIALS_PER_STRATEGY) -> Dict[str, Any]:
    strategies = ("ui_only_stop", "cancel_propagation_only", "cancel_plus_gen_and_flush")
    all_trials: List[LiveSseTrial] = []
    for strat in strategies:
        for i in range(1, trials + 1):
            res = await run_live_trial(base_url, api_key, model, i, strat)
            all_trials.append(res)
            print(
                f"[{res.trial_id}] ttft={res.ttft_ms:.1f}ms prod_stop={res.producer_stop_ms:.1f}ms "
                f"vis_stop={res.visible_stop_ms:.1f}ms after_stop_chunks={res.chunks_received_after_stop} "
                f"rendered={res.stale_chunks_rendered} dropped={res.stale_chunks_dropped} leak={res.late_tool_leaked}",
                flush=True,
            )

    summary: Dict[str, Any] = {
        "experiment_id": "Exp-24-03",
        "environment": "live_openai_compatible_https_tls_sse_wallclock",
        "endpoint_type": "openai_compatible_https_sse",
        "model": model,
        "trials_per_strategy": trials,
        "interrupt_after_chunks": INTERRUPT_AFTER_CHUNKS,
        "consumer_chunk_ms": int(CONSUMER_CHUNK_PLAY_S * 1000),
        "ttft_p50_ms": percentile([t.ttft_ms for t in all_trials], 50),
        "ttft_p95_ms": percentile([t.ttft_ms for t in all_trials], 95),
        "strategies": {},
    }
    for strat in strategies:
        grp = [t for t in all_trials if t.strategy == strat]
        summary["strategies"][strat] = {
            "trials": len(grp),
            "propagation_p50_ms": percentile([t.propagation_ms for t in grp], 50),
            "propagation_p95_ms": percentile([t.propagation_ms for t in grp], 95),
            "producer_stop_p50_ms": percentile([t.producer_stop_ms for t in grp], 50),
            "producer_stop_p95_ms": percentile([t.producer_stop_ms for t in grp], 95),
            "visible_stop_p50_ms": percentile([t.visible_stop_ms for t in grp], 50),
            "visible_stop_p95_ms": percentile([t.visible_stop_ms for t in grp], 95),
            "visible_stop_max_ms": round(max(t.visible_stop_ms for t in grp), 2),
            "chunks_received_after_stop_total": sum(t.chunks_received_after_stop for t in grp),
            "stale_chunks_rendered_total": sum(t.stale_chunks_rendered for t in grp),
            "stale_chunks_dropped_total": sum(t.stale_chunks_dropped for t in grp),
            "late_tool_leaks": sum(1 for t in grp if t.late_tool_leaked),
            "socket_abort_rate": round(sum(1 for t in grp if t.socket_aborted_on_cancel) / len(grp), 4),
        }
    return {"summary": summary, "trials": [asdict(t) for t in all_trials]}


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.environ.get("OPENAI_MODEL", "gpt-6.2-astra").strip()
    if not api_key:
        print("OPENAI_API_KEY is not set; skipping live HTTPS SSE benchmark.", file=sys.stderr)
        sys.exit(0)

    root = Path(__file__).resolve().parent
    res_dir = root / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    out = asyncio.run(run_all(base_url, api_key, model))
    (res_dir / "live_llm_sse_wallclock.json").write_text(
        json.dumps(out["summary"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (res_dir / "live_llm_sse_wallclock.jsonl").open("w", encoding="utf-8") as fh:
        for row in out["trials"]:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("\n=== SUMMARY ===")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
