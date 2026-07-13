"""Deterministic mode routing for Google App campaign operator questions."""

from __future__ import annotations

import re
from typing import Any


_REPORT_PATTERNS = (
    r"/ads\s+report\b",
    r"日报",
    r"周报",
    r"月报",
    r"客户报告",
    r"正式(?:报告|审计)",
    r"(?:出|生成|制作|写)(?:个|一份)?(?:\s*UAC)?\s*报告",
    r"\b(?:daily|weekly|monthly)\s+report\b",
    r"\bpdf\b",
)
_EXPERIMENT_PATTERNS = (
    r"/ads\s+experiment\b",
    r"(?:创建|设计|建立|登记|记录).{0,24}(?:实验|对照测试)",
    r"(?:帮我做|想开|生成|起草|草拟).{0,24}(?:实验|对照实验|对照测试)",
    r"(?:实验|对照测试).{0,12}(?:草案|方案)",
    r"帮我验证",
    r"正式(?:实验|测试)",
    r"\b(?:create|design|validate)\s+(?:an?\s+)?experiment\b",
    r"\ba/b\s+test\b",
)
_DIAGNOSIS_PATTERNS = (
    r"为什么",
    r"原因",
    r"根因",
    r"不消耗",
    r"支付差",
    r"没有深层事件",
    r"哪里异常",
    r"\bwhy\b",
    r"\broot cause\b",
    r"\bdiagnos(?:e|is)\b",
)
_QUICK_PATTERNS = (
    r"还能跑吗",
    r"要不要",
    r"该怎么操作",
    r"直接给我操作结论",
    r"调现有还是复制",
    r"新素材",
    r"预算和目标",
    r"\bAC\s*[23](?:[._]?0|[._]?5)?\b",
    r"广告\s*[23](?:[._]?0|[._]?5)?",
    r"\b(?:keep|pause|replace|duplicate|parallel)\b",
)


def _matches(question: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, question, re.IGNORECASE) for pattern in patterns)


def _quick_question_type(question: str) -> str:
    if re.search(r"素材|创意|asset|creative", question, re.IGNORECASE):
        return "creative_action"
    if re.search(
        r"(?:再开|新开|复制|duplicate|same[- ]level)", question, re.IGNORECASE
    ):
        return "same_level_campaign"
    if re.search(
        r"\bAC\s*[23](?:[._]?0|[._]?5)?\b|广告\s*[23](?:[._]?0|[._]?5)?|层级",
        question,
        re.IGNORECASE,
    ):
        return "campaign_level_selection"
    if re.search(r"预算|tCPA|tROAS|出价|budget|bid|target", question, re.IGNORECASE):
        return "bid_and_budget"
    return "general_operation"


def route_question(question: str) -> dict[str, Any]:
    """Route one natural-language request without calling a model API.

    Explicit report and experiment language wins over ordinary AC wording.
    Asking whether an AC level should be tested remains a Quick Decision;
    asking to create or formally validate an experiment enters Experiment.
    """

    text = question.strip()
    if _matches(text, _REPORT_PATTERNS):
        return {"mode": "report", "question_type": "formal_report"}
    if _matches(text, _EXPERIMENT_PATTERNS):
        return {"mode": "experiment", "question_type": "experiment_design"}
    if _matches(text, _DIAGNOSIS_PATTERNS):
        return {"mode": "diagnosis", "question_type": "root_cause"}
    if _matches(text, _QUICK_PATTERNS) or not text:
        return {
            "mode": "quick_decision",
            "question_type": _quick_question_type(text),
        }
    return {"mode": "quick_decision", "question_type": "general_operation"}
