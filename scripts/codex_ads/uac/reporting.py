"""Markdown rendering for deterministic UAC analysis results."""

from __future__ import annotations

from typing import Any


def render_markdown(result: dict[str, Any]) -> str:
    """Render the required UAC report order from the structured result."""
    diagnosis = result["diagnoses"][0]["code"]
    feasibility = result["optimization_feasibility"]["status"]
    experiment = result["experiments"][0] if result["experiments"] else None
    evidence_lines = [
        f"- {item.get('id', 'evidence')}: {item.get('observation', '')} ({item.get('source_kind', 'unspecified')})"
        for item in result["evidence"]
    ] or ["- No evidence supplied."]
    controllable = [
        f"- {item['action']} [{item['permission']}]"
        for item in result["recommendations"]
        if item["permission"] == "OPTIMIZER_CAN_EXECUTE"
    ] or ["- None proven under current permissions and evidence."]
    uncontrollable = [
        f"- {item['action']} [{item['permission']}]"
        for item in result["recommendations"]
        if item["permission"] != "OPTIMIZER_CAN_EXECUTE"
    ] or ["- None identified."]
    client = [f"- {item}" for item in result["client_dependencies"]] or [
        "- None identified."
    ]
    gaps = [f"- {item}" for item in result["confidence"]["data_gaps"]] or [
        "- None declared."
    ]
    review_lines = [
        f"- Previous experiment `{item.get('id')}`: `{item['status']}` — "
        + "; ".join(item.get("reasons", []))
        for item in result.get("experiment_reviews", [])
    ] or ["- No prior experiment requires review."]
    learning_lines = [
        f"- Prior {item['scope']} learning from `{item['experiment_id']}`: "
        f"{item['statement']}"
        for item in result.get("prior_learnings", [])
    ]
    goal = result.get("optimization_goal", {})
    funnel_drop = result.get("funnel_state", {}).get("largest_observed_drop")
    funnel_line = (
        f"- Largest observed funnel drop: {funnel_drop['from']} → {funnel_drop['to']} "
        f"({funnel_drop['drop']:.1%}); causal attribution remains undetermined."
        if funnel_drop
        else "- Largest funnel drop cannot be calculated from current fields."
    )

    if experiment:
        experiment_lines = [
            f"- ID: {experiment['id']}",
            f"- Variable: {experiment['variable']['type']} (single variable)",
            f"- Hypothesis: {experiment['hypothesis']['statement']}",
            f"- Primary metric: {experiment['primary_metric']['name']}",
        ]
        observation_lines = [
            f"- Minimum days: {experiment['observation']['minimum_days']}",
            f"- Minimum conversions: {experiment['observation']['minimum_conversions']}",
            f"- Conversion delay: {experiment['observation']['conversion_delay_days']} days",
            f"- Success: {experiment['success_rule']}",
            f"- Rollback: {experiment['rollback_rule']}",
            f"- Inconclusive: {experiment['inconclusive_rule']}",
            "- Execution requires human approval; this proposal does not edit Google Ads.",
        ]
    else:
        experiment_lines = ["- No experiment is safe to create from current evidence."]
        observation_lines = [
            "- Resolve blockers or reach declared maturity before proposing a test."
        ]

    sections = [
        "# UAC Experiment Loop Report",
        "",
        "## 1. Executive summary",
        f"- Primary diagnosis: `{diagnosis}`",
        f"- Current optimization state: `{feasibility}`",
        "",
        "## 2. 当前优化状态",
        f"- `{feasibility}`",
        f"- Business goal: `{goal.get('business_goal')}`",
        f"- Optimization event: `{goal.get('optimization_event')}`",
        f"- Goal alignment: `{goal.get('alignment')}`",
        f"- Proxy quality: `{goal.get('proxy_quality')}`",
        "",
        "## 3. 数据与测量可靠性",
        f"- `{result['measurement_state']['status']}`",
        *[f"- {reason}" for reason in result["measurement_state"]["reasons"]],
        "",
        "## 4. 学习资格",
        f"- `{result['learning_eligibility']['status']}`",
        *[f"- {reason}" for reason in result["learning_eligibility"]["reasons"]],
        "",
        "## 5. 关键证据",
        *evidence_lines,
        *learning_lines,
        "",
        "## 6. 当前主要阻塞",
        f"- `{diagnosis}`",
        funnel_line,
        *review_lines,
        "",
        "## 7. 可控变量",
        *controllable,
        "",
        "## 8. 不可控变量",
        *uncontrollable,
        "",
        "## 9. 当前唯一优先实验",
        *experiment_lines,
        "",
        "## 10. 实验观察条件",
        *observation_lines,
        "",
        "## 11. 客户需要配合的事项",
        *client,
        "",
        "## 12. Do not touch",
        *[f"- {item}" for item in result["do_not_touch"]],
        "",
        "## 13. 下一次复盘条件",
        f"- {result['next_review']['when']}",
        *[f"- Required: {item}" for item in result["next_review"]["required_inputs"]],
        "",
        "## 14. 置信度和数据缺口",
        f"- Confidence: `{result['confidence']['level']}`",
        *gaps,
        "",
    ]
    return "\n".join(sections)
