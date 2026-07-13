"""Four-mode natural-language routing regression tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.routing import route_question  # noqa: E402


@pytest.mark.parametrize(
    ("question", "mode", "question_type"),
    [
        ("这素材还能跑吗", "quick_decision", "creative_action"),
        ("为什么支付差", "diagnosis", "root_cause"),
        ("帮我验证 AC3.0", "experiment", "experiment_design"),
        ("帮我做一个 AC3.0 实验", "experiment", "experiment_design"),
        ("我想开一个 AC3.0 对照实验", "experiment", "experiment_design"),
        ("请生成 AC3.0 实验草案", "experiment", "experiment_design"),
        ("写周报", "report", "formal_report"),
        ("给我出个 UAC 报告", "report", "formal_report"),
        ("/ads report", "report", "formal_report"),
        (
            "我现在该跑 AC2.5 还是 AC3.0",
            "quick_decision",
            "campaign_level_selection",
        ),
        ("要不要测试 AC3.0", "quick_decision", "campaign_level_selection"),
        ("新素材放现有还是新开", "quick_decision", "creative_action"),
        ("今天预算和目标怎么调", "quick_decision", "bid_and_budget"),
    ],
)
def test_mode_routing(question, mode, question_type):
    result = route_question(question)
    assert result == {"mode": mode, "question_type": question_type}


def test_explicit_report_and_experiment_language_win_over_ac_terms():
    assert route_question("写 AC3.0 周报")["mode"] == "report"
    assert route_question("创建一个 AC2.5 对照实验")["mode"] == "experiment"
