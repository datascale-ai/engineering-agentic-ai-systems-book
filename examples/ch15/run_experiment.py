"""Three users x ten sessions: selection behavior, not model personalization."""

from dataclasses import asdict
import json
from pathlib import Path
from memory import Memory, MemoryStore

HERE = Path(__file__).resolve().parent


def run():
    store = MemoryStore()
    all_records = []
    rows = []
    base = {"u1": "上午", "u2": "下午", "u3": "晚间"}
    for user, preference in base.items():
        m = Memory(
            f"{user}:base",
            "teaching",
            user,
            "departure",
            preference,
            "semantic",
            "user",
            None,
            0,
            100,
            1,
            f"{user}:consent:1",
        )
        store.put(m, "teaching", user)
        all_records.append(m)
    for session in range(1, 11):
        for user in base:
            sid = f"{user}:s{session}"
            if session == 3:
                m = Memory(
                    f"{user}:temporary",
                    "teaching",
                    user,
                    "departure",
                    "中午",
                    "episodic",
                    "session",
                    sid,
                    3,
                    4,
                    1,
                    sid,
                )
                store.put(m, "teaching", user)
                all_records.append(m)
            if session == 6:
                m = Memory(
                    f"{user}:base",
                    "teaching",
                    user,
                    "departure",
                    "清晨",
                    "semantic",
                    "user",
                    None,
                    6,
                    100,
                    2,
                    sid,
                )
                store.put(m, "teaching", user)
                all_records.append(m)
            expected = (
                "中午" if session == 3 else ("清晨" if session >= 6 else base[user])
            )
            # Compare absent memory, unscoped append-only latest selection, and controlled selection.
            selected = store.recall("teaching", user, "departure", sid, session)
            for strategy, record in [
                ("none", None),
                ("unfiltered_latest", all_records[-1]),
                ("scoped", selected),
            ]:
                value = record.value if record else None
                rows.append(
                    {
                        "session": session,
                        "owner_id": user,
                        "strategy": strategy,
                        "expected": expected,
                        "value": value,
                        "correct": value == expected,
                        "cross_user": bool(record and record.owner_id != user),
                        "stale": bool(
                            record
                            and (
                                not record.valid_from <= session < record.valid_until
                                or (
                                    record.scope == "session"
                                    and record.session_id != sid
                                )
                            )
                        ),
                    }
                )
    store.snapshot()
    store.recall("teaching", "u1", "departure", "u1:s10", 10)
    deletion = store.delete("u1:base", "teaching", "u1")
    store.restore()
    deletion["recall_after_restore"] = (
        store.recall("teaching", "u1", "departure", "u1:s11", 11) is None
    )
    output = HERE / "results"
    output.mkdir(exist_ok=True)
    (HERE / "personalization_eval.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    summary = {
        strategy: {
            "cases": 30,
            "correct": sum(r["correct"] for r in rows if r["strategy"] == strategy),
            "cross_user": sum(
                r["cross_user"] for r in rows if r["strategy"] == strategy
            ),
            "stale": sum(r["stale"] for r in rows if r["strategy"] == strategy),
        }
        for strategy in ["none", "unfiltered_latest", "scoped"]
    }
    (output / "report.json").write_text(
        json.dumps(
            {
                "kind": "deterministic_selection",
                "summary": summary,
                "deletion": deletion,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {"summary": summary, "deletion": deletion}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    run()
