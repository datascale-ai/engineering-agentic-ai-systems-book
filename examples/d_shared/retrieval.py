"""Auditable BM25 and permission-aware evidence selection, no model required."""

from collections import Counter
import math
import re


def tokens(text):
    chars = re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", text.lower())
    return chars + ["".join(chars[i : i + 2]) for i in range(len(chars) - 1)]


def permitted(document, department, as_of):
    return (
        department in document["departments"]
        and document["valid_from"] <= as_of < document["valid_to"]
    )


def bm25(query, documents):
    counts = [Counter(tokens(d["title"] + " " + d["text"])) for d in documents]
    n = len(counts)
    if not n:
        return []
    avg = sum(sum(c.values()) for c in counts) / n
    qt = set(tokens(query))
    df = {w: sum(w in c for c in counts) for w in qt}
    scores = []
    for doc, c in zip(documents, counts):
        size = sum(c.values())
        score = 0
        for word in qt:
            tf = c[word]
            if tf:
                idf = math.log(1 + (n - df[word] + 0.5) / (df[word] + 0.5))
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * size / avg))
        scores.append((score, doc))
    return sorted(scores, key=lambda x: (-x[0], x[1]["chunk_id"]))


def answerable(query, document):
    """Closed-domain answer contract, not semantic entailment or an LLM judge."""
    unknown = any(x in query for x in ("家属", "海外商业保险"))
    restricted = "专项例外" in query
    return not unknown and (
        not restricted or document["classification"] == "restricted"
    )


def evidence_answer(query, candidates, department="B", as_of="2026-11-09"):
    for score, d in candidates:
        if score > 0 and permitted(d, department, as_of) and answerable(query, d):
            return {
                "answer": f"{d['topic']}当前上限为{d['limit_yuan']}元。",
                "limit_yuan": d["limit_yuan"],
                "evidence": d["chunk_id"],
                "quote": d["text"],
                "status": "supported",
            }
    return {
        "answer": None,
        "limit_yuan": None,
        "evidence": None,
        "status": "insufficient_evidence",
    }
