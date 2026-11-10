"""Exp-14-01: representation retention, not a language-model benchmark.

Recent-utterance summary: select complete utterances in reverse time order
under a 240-codepoint limit, then restore chronological order. It preserves
utterance text exactly; no LLM or negative-word deletion is used here.
"""
import argparse
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
CHECKPOINTS = (12, 24, 36, 48, 60)


def recent_summary(turns, limit=240):
    selected, used = [], 0
    for turn in reversed(turns):
        length = len(turn["text"])
        if used + length > limit:
            break
        selected.append(turn)
        used += length
    return list(reversed(selected))


def latest_facts(turns):
    result = {}
    for turn in turns:
        if "fact" in turn:
            result[turn["fact"]["field"]] = {
                **turn["fact"], "source_ref": turn["source_ref"], "turn": turn["turn"]}
    return result


def measure(cases, summary_limit=240):
    rows = []
    for case in cases:
        for checkpoint in CHECKPOINTS:
            history = case["turns"][:checkpoint]
            truth = latest_facts(history)
            summary = recent_summary(history, summary_limit)
            views = {
                "full_history": {"turns": history},
                "recent_summary": {"turns": summary},
                "state_plus_summary": {"facts": truth, "turns": summary},
            }
            for strategy, view in views.items():
                actual = view.get("facts", latest_facts(view["turns"]))
                retained = sum(actual.get(k) == v for k, v in truth.items())
                stale = sum(k in actual and actual[k] != v for k, v in truth.items())
                text = json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                rows.append({"case_id": case["case_id"], "checkpoint": checkpoint,
                             "strategy": strategy, "required_facts": len(truth),
                             "retained_facts": retained, "stale_facts": stale,
                             "serialized_utf8_bytes": len(text.encode("utf-8")),
                             "serialized_codepoints": len(text)})
    summary = []
    for strategy in views:
        subset = [r for r in rows if r["strategy"] == strategy]
        required = sum(r["required_facts"] for r in subset)
        retained = sum(r["retained_facts"] for r in subset)
        summary.append({"strategy": strategy, "checkpoints": len(subset),
                        "retained_facts": retained, "required_facts": required,
                        "retention_rate": retained / required,
                        "stale_facts": sum(r["stale_facts"] for r in subset),
                        "mean_utf8_bytes": round(statistics.mean(r["serialized_utf8_bytes"] for r in subset), 1),
                        "mean_codepoints": round(statistics.mean(r["serialized_codepoints"] for r in subset), 1)})
    return {"experiment_id": "Exp-14-01", "kind": "deterministic_representation_measurement",
            "case_count": len(cases), "turns_per_case": 60, "checkpoints": list(CHECKPOINTS),
            "summary_limit_codepoints": summary_limit, "model": None,
            "repeat_count": 1, "summary": summary, "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-limit", type=int, default=240)
    args = parser.parse_args()
    cases = [json.loads(line) for line in HERE.joinpath("state_update_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    if args.summary_limit < 1:
        parser.error("--summary-limit must be positive")
    report = measure(cases, args.summary_limit)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False, indent=2))
