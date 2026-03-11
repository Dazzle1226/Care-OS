from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.support_cards import SupportCardAgent


def test_support_card_agent_fallback_returns_sections(db_session: Session, seeded_family) -> None:
    cards = SupportCardAgent().generate_cards(family=seeded_family, profile=seeded_family.child_profile)

    assert len(cards) == 2
    assert cards[0].title == "支持卡"
    assert cards[1].title == "交接卡"
    assert cards[0].sections[0].title == "沟通"
    assert cards[1].sections[-1].title == "联系方式"


def test_support_card_agent_accepts_llm_shape(db_session: Session, seeded_family) -> None:
    agent = SupportCardAgent()
    agent.llm = type(
        "StubLLM",
        (),
        {
            "generate_json": staticmethod(
                lambda **_: {
                    "support_cards": [
                        {
                            "card_id": "ONB-SUPPORT",
                            "icon": "support",
                            "title": "支持卡",
                            "summary": "给长期协作者看的支持说明。",
                            "one_liner": "先降刺激，再给下一步。",
                            "quick_actions": ["先用短句", "先给选择"],
                            "sections": [
                                {"key": "communication", "title": "沟通", "items": ["短句", "二选一"]},
                                {"key": "triggers", "title": "触发器", "items": ["过渡", "等待"]},
                                {"key": "signals", "title": "早期信号", "items": ["捂耳朵"]},
                                {"key": "support", "title": "有效支持", "items": ["提前预告"]},
                                {"key": "donts", "title": "不要做", "items": ["不要强拉"]},
                                {"key": "escalation", "title": "升级处理", "items": ["先退到安静处"]},
                            ],
                        },
                        {
                            "card_id": "ONB-HANDOFF",
                            "icon": "handoff",
                            "title": "交接卡",
                            "summary": "给临时照护者的接手卡。",
                            "one_liner": "先保平稳，再推进任务。",
                            "quick_actions": ["先保平稳", "升级就联系家长"],
                            "sections": [
                                {"key": "status", "title": "当前状态", "items": ["未提供当日信息"]},
                                {"key": "now", "title": "现在要做", "items": ["只留一件事"]},
                                {"key": "soothe", "title": "安抚方式", "items": ["安静角落"]},
                                {"key": "taboo", "title": "禁忌", "items": ["不要催"]},
                                {"key": "steps", "title": "升级步骤", "items": ["先降刺激"]},
                                {"key": "safety", "title": "安全信息", "items": ["贴身看护"]},
                                {"key": "contact", "title": "联系方式", "items": ["先联系家长"]},
                            ],
                        },
                    ]
                }
            )
        },
    )()

    cards = agent.generate_cards(family=seeded_family, profile=seeded_family.child_profile)

    assert cards[0].quick_actions[0] == "先用短句"
    assert cards[1].sections[0].items == ["未提供当日信息"]
