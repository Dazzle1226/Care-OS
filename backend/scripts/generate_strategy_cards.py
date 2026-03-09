from __future__ import annotations

import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "seed" / "strategy_cards.json"

SCENARIOS = [
    ("transition", 25, "过渡"),
    ("bedtime", 20, "睡前"),
    ("homework", 20, "作业"),
    ("outing", 15, "外出"),
    ("sensory", 10, "感官"),
    ("respite", 10, "微喘息"),
]

AGE_BANDS = ["0-3", "4-6", "7-9", "10-12"]
LANG_LEVELS = ["none", "single_word", "short_sentence", "fluent"]
SENSORY = ["sound", "light", "touch", "crowd", "smell"]


def build_card(idx: int, scenario: str, label: str, seq: int) -> dict:
    age_start = (idx + seq) % len(AGE_BANDS)
    lang_start = (idx * 3 + seq) % len(LANG_LEVELS)

    age_bands = [AGE_BANDS[age_start], AGE_BANDS[(age_start + 1) % len(AGE_BANDS)]]
    language_levels = [LANG_LEVELS[lang_start], LANG_LEVELS[(lang_start + 1) % len(LANG_LEVELS)]]

    sensory_flags = [SENSORY[(idx + i) % len(SENSORY)] for i in range(2)]

    cost_level = ["low", "medium", "high"][idx % 3]
    risk_level = ["low", "medium", "high"][((idx // 2) + seq) % 3]
    evidence_tag = ["evidence", "expert", "practice"][idx % 3]

    title = f"{label}策略卡 {seq:02d}"
    script_parent = f"我看到你现在有点难，我们先做第一步：{label}准备。"
    script_teacher = f"请先给两步以内指令，完成后马上强化。"

    return {
        "id": f"CARD-{idx:04d}",
        "title": title,
        "scenario_tags": [scenario, "low_stim", "asdhack"],
        "applicable_conditions": {
            "age_bands": age_bands,
            "language_levels": language_levels,
            "sensory": sensory_flags,
            "intensity": ["light", "medium", "heavy"],
        },
        "steps": [
            f"步骤1：提前 2 分钟预告 {label}切换。",
            f"步骤2：给两个可行选项，允许 5 秒等待。",
            f"步骤3：完成后立即低刺激强化并记录。",
        ],
        "scripts": {
            "parent": script_parent,
            "teacher": script_teacher,
        },
        "donts": [
            "不要强拉身体",
            "不要连续追问",
            "不要突然提高音量",
        ],
        "escalate_when": [
            "持续升级超过10分钟",
            "出现明显自伤/他伤风险",
            "无法通过降刺激恢复",
        ],
        "cost_level": cost_level,
        "risk_level": risk_level,
        "evidence_tag": evidence_tag,
    }


def main() -> None:
    cards: list[dict] = []
    idx = 1
    for scenario, count, label in SCENARIOS:
        for seq in range(1, count + 1):
            cards.append(build_card(idx, scenario, label, seq))
            idx += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(cards)} cards -> {OUTPUT}")


if __name__ == "__main__":
    main()
