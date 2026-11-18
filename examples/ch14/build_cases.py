"""Generate ten original 60-turn policy-assistant conversations."""
import json
from pathlib import Path


def make_cases():
    cases = []
    for index in range(10):
        facts = {
            1: ("goal", f"为项目{index + 1}准备差旅申请草稿"),
            2: ("budget_minor", 200000 + index * 10000),
            3: ("approval", "pending"),
            4: ("preference", "优先上午出发"),
            19: ("preference", "本次改为下午出发"),
            27: ("budget_minor", 150000 + index * 10000),
            35: ("approval", "approved"),
            43: ("approval", "revoked" if index % 2 == 0 else "approved"),
        }
        turns = []
        for turn in range(1, 61):
            if turn in facts:
                field, value = facts[turn]
                text = {"goal": f"本次任务是{value}。", "budget_minor": f"当前预算为{value}分。",
                        "approval": {"pending": "审批尚未通过。", "approved": "审批已通过。",
                                     "revoked": "原有审批已经撤销。"}.get(value, ""),
                        "preference": f"出发偏好是{value}。"}[field]
                turns.append({"turn": turn, "text": text, "fact": {"field": field, "value": value},
                              "source_ref": f"T{index + 1:02d}:turn:{turn}"})
            else:
                text = (f"第{turn}轮补充说明：候选行程{index + 1}-{turn}还需要核对换乘位置和到达时间，"
                        "这条说明没有改变任务目标、预算、审批或出发偏好。")
                turns.append({"turn": turn, "text": text})
        cases.append({"case_id": f"T{index + 1:02d}", "turns": turns})
    return cases


if __name__ == "__main__":
    target = Path(__file__).with_name("state_update_cases.jsonl")
    target.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in make_cases()), encoding="utf-8")
    print(f"Wrote {len(make_cases())} conversations to {target.name}")
