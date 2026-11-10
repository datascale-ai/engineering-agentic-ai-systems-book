"""Actual lexical/dense/hybrid retrieval. Dense requires fastembed + weights.

No generated answers: a closed-domain evidence renderer uses the policy
amount. Permission and temporal checks execute before any encoder/reranker.
"""

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from d_shared.retrieval import bm25, permitted, evidence_answer

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "d_shared/data"


def evaluate(use_dense=False, cache_dir=None):
    docs = [json.loads(s) for s in (DATA / "policies.jsonl").read_text().splitlines()]
    questions = [
        json.loads(s) for s in (DATA / "rag_eval_set.jsonl").read_text().splitlines()
    ]
    model = None
    vectors = {}
    if use_dense:
        import numpy as np
        from fastembed import TextEmbedding

        model = TextEmbedding("BAAI/bge-small-zh-v1.5", cache_dir=cache_dir)
        eligible = [d for d in docs if permitted(d, "B", "2026-11-09")]
        embeddings = list(
            model.passage_embed([d["title"] + " " + d["text"] for d in eligible])
        )
        vectors = {d["chunk_id"]: v for d, v in zip(eligible, embeddings)}
    rows = []
    adaptive = []
    for q in questions:
        eligible = [d for d in docs if permitted(d, q["department"], q["as_of"])]
        started = time.perf_counter()
        lexical = bm25(q["query"], eligible)
        lexical_ms = (time.perf_counter() - started) * 1000
        rankings = {"bm25": lexical}
        if model:
            dense_started = time.perf_counter()
            query = next(model.query_embed(q["query"]))
            dense = sorted(
                [(float(np.dot(query, vectors[d["chunk_id"]])), d) for d in eligible],
                key=lambda x: -x[0],
            )
            fused = {}
            for ranking in [lexical, dense]:
                for rank, (_, d) in enumerate(ranking, 1):
                    fused[d["chunk_id"]] = fused.get(d["chunk_id"], 0) + 1 / (60 + rank)
            hybrid = sorted(
                [(fused[d["chunk_id"]], d) for d in eligible], key=lambda x: -x[0]
            )[:8]
            # Transparent metadata reranking, distinct from a neural cross-encoder.
            reranked = sorted(
                hybrid, key=lambda x: (q["query"].find(x[1]["topic"]) < 0, -x[0])
            )
            rankings.update(dense=dense, hybrid_metadata_rerank=reranked)
            dense_and_fusion_ms = (time.perf_counter() - dense_started) * 1000
            if len(adaptive) < 12:
                # A deployable, deliberately simple routing heuristic. It does
                # not inspect gold labels or relevant-document IDs.
                retry = not any(d["topic"] in q["query"] for _, d in lexical[:1])
                chosen = dense if retry else lexical
                out = evidence_answer(
                    q["query"], chosen[:3], q["department"], q["as_of"]
                )
                fixed = evidence_answer(
                    q["query"], lexical[:3], q["department"], q["as_of"]
                )
                adaptive.append(
                    {
                        "question_id": q["question_id"],
                        "retrieval_calls": 2 if retry else 1,
                        "fixed_correct": fixed["evidence"] in q["relevant"]
                        if q["relevant"]
                        else fixed["evidence"] is None,
                        "adaptive_correct": out["evidence"] in q["relevant"]
                        if q["relevant"]
                        else out["evidence"] is None,
                    }
                )
        elapsed = (time.perf_counter() - started) * 1000
        for name, ranking in rankings.items():
            top = ranking[:3]
            answer = evidence_answer(q["query"], top, q["department"], q["as_of"])
            relevant = set(q["relevant"])
            observed = {d["chunk_id"] for _, d in top}
            rows.append(
                {
                    "question_id": q["question_id"],
                    "slice": q["kind"],
                    "strategy": name,
                    "top3": [d["chunk_id"] for _, d in top],
                    "recall_at_3": len(relevant & observed) / len(relevant)
                    if relevant
                    else None,
                    "correct": answer["evidence"] in relevant
                    if relevant
                    else answer["evidence"] is None,
                    "answer": answer,
                    "permission_leaks": sum(
                        not permitted(d, q["department"], q["as_of"]) for _, d in top
                    ),
                    "pipeline_ms": round(elapsed, 3),
                }
            )
            rows[-1]["lexical_ms"] = round(lexical_ms, 3)
            rows[-1]["dense_and_fusion_ms"] = (
                round(dense_and_fusion_ms, 3) if model else None
            )
    summary = {}
    for name in {r["strategy"] for r in rows}:
        subset = [r for r in rows if r["strategy"] == name]
        answerable = [r for r in subset if r["recall_at_3"] is not None]
        summary[name] = {
            "questions": len(subset),
            "answerable": len(answerable),
            "recall_at_3": sum(r["recall_at_3"] for r in answerable) / len(answerable),
            "correct": sum(r["correct"] for r in subset),
            "permission_leaks": sum(r["permission_leaks"] for r in subset),
        }
    report = {
        "kind": "local_retrieval_with_deterministic_renderer",
        "encoder": "BAAI/bge-small-zh-v1.5" if model else None,
        "generation_model": None,
        "reranker": "topic_metadata_then_rrf",
        "summary": summary,
        "rows": rows,
        "adaptive_pilot": adaptive,
    }
    (HERE / "results").mkdir(exist_ok=True)
    path = (
        HERE
        / "results"
        / ("retrieval_dense.json" if model else "retrieval_lexical.json")
    )
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dense", action="store_true")
    p.add_argument("--cache-dir")
    a = p.parse_args()
    evaluate(a.dense, a.cache_dir)
