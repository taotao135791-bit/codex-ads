"""Compact operator-facing renderer for UAC Quick Decisions."""

from __future__ import annotations

from typing import Any


_ACTION_LABELS = {
    "ADD_TO_EXISTING": "加入现有 Campaign",
    "ADJUST_EXISTING": "调整现有 Campaign",
    "CREATE_NEW_SAME_LEVEL": "新建同层级 Campaign",
    "CREATE_NEW_CANDIDATE_LEVEL": "新建候选层级 Campaign",
    "DUPLICATE_FOR_CONTROLLED_TEST": "为严格对照测试新建",
    "DO_NOT_DUPLICATE": "不要复制 Campaign",
    "REQUEST_CLIENT_APPROVAL": "先申请客户批准",
    "WAIT": "保持不动并等待",
    "KEEP_RUNNING": "继续运行",
    "RUN_WITH_LIMIT": "限量继续运行",
    "WAIT_FOR_MATURITY": "等待数据成熟",
    "REDUCE_EXPOSURE": "降低曝光",
    "PAUSE": "暂停",
    "REPLACE": "替换",
    "RETEST": "重新测试",
    "INSUFFICIENT_DATA": "证据不足，暂不操作",
    "ADD_TO_EXISTING_CAMPAIGN": "加入现有 Campaign",
    "TEST_IN_NEW_CAMPAIGN": "放入候选 Campaign 测试",
    "NO_CHANGE": "保持不变",
    "INCREASE": "提高",
    "DECREASE": "降低",
}

_REASON_LABELS = {
    "split_budget_and_event_volume_are_sufficient": "预算和成熟事件量足以支撑隔离学习",
    "keep_healthy_baseline_while_testing_deeper_level": "健康的现有 Campaign 应保留为稳定基线",
    "new_assets_share_existing_campaign_semantics": "新素材与现有 Campaign 的目标和结构一致",
    "no_independent_campaign_reason": "没有独立预算、地区、受众或归因需求",
    "independent_structure_is_required": "独立预算、地区、OS、受众或归因要求需要隔离结构",
    "split_capacity_not_proven": "尚未证明预算和事件量足以支撑拆分",
    "duplicate_only_to_restart_learning": "仅为重启学习不能成为复制理由",
    "value_signal_not_ready": "支付价值、币种、事件量或对账尚未全部就绪",
    "candidate_deep_event_not_ready": "候选深层事件的量级、稳定性或业务相关性不足",
    "campaign_level_mapping_confirmation_required": "关键层级切换前仍需确认团队术语映射",
    "measurement_state_unreliable": "当前 measurement / attribution 不可靠",
    "measurement_state_not_confirmed": "measurement / attribution 状态尚未确认",
    "material_external_issue_blocks_level_change": "外部产品、技术或市场异常可能改变结论",
    "current_campaign_level_unknown": "当前 Campaign 层级尚未确认",
    "unfinished_experiment_blocks_stacked_change": "已有未完成实验，不能叠加普通变更",
    "backend_value_reconciliation_missing": "缺少后端价值对账证据",
    "mmp_without_backend_evidence": "只有 MMP 证据、缺少后端价值核对",
    "aggregate_data_cannot_support_campaign_action": "汇总数据不足以支持 Campaign 级操作",
    "current_ac30_value_gate_ready": "当前 AC3.0 的价值准入条件仍满足",
    "predeclared_rollback_triggered": "已触发预先声明的回退条件",
    "creative_conversion_delay_or_volume_not_mature": "素材的转化延迟或成熟事件量尚未满足",
    "mature_creative_guardrail_breached": "素材已触发成熟表现护栏",
    "creative_fatigue_detected": "已发现素材疲劳",
    "low_cpi_does_not_equal_high_value": "低 CPI 没有转化为更好的支付质量",
    "mature_payment_efficiency_outweighs_cpi": "成熟支付效率优于表面 CPI",
    "creative_promise_mismatches_value_goal": "素材承诺与价值目标不匹配",
    "no_mature_creative_stop_condition": "尚未触发成熟素材停止条件",
    "creative_evidence_not_supplied": "缺少素材粒度的成熟证据",
    "creative_add_not_immediately_executable": "当前权限不能立即添加新素材",
    "keep_bid_and_budget_stable_during_level_change": "层级变化期间保持出价与预算稳定，避免多变量污染",
    "ordinary_multi_variable_change_blocked": "普通运营调整不能同时改出价和预算",
    "candidate_campaign_requires_permission": "新建候选 Campaign 需要额外权限",
    "level_change_not_immediately_executable": "当前权限不足，层级变化不能立即执行",
    "level_migration_requires_permission": "迁移或回退层级需要优化事件和出价策略权限",
    "os_level_segmentation_incomplete": "Android / iOS 分层证据不完整，不能安全操作",
    "request_routes_to_different_mode": "该问题应进入诊断、实验或报告模式",
    "safe_hold_by_default": "证据不足时默认保持不动",
    "stable_payment_value_volume": "支付价值量持续稳定",
    "reliable_value_and_currency": "value 与 currency 校验可靠",
    "value_specific_reconciliation": "Google、MMP 与后端完成价值对账",
}

_DO_NOT_LABELS = {
    "do_not_treat_ac_labels_as_bid_values": "不要把 AC2.0 / AC2.5 / AC3.0 当作出价数值",
    "do_not_duplicate_only_to_restart_learning": "不要只为“重启学习”复制 Campaign",
    "do_not_change_level_bid_budget_and_creative_together": "不要同时改层级、出价、预算和素材",
    "do_not_edit_google_ads_without_exact_human_confirmation": "没有逐项人工确认，不要修改真实 Google Ads 账户",
}

_CONFIDENCE_LABELS = {"low": "低", "medium": "中", "high": "高"}

_NUMERIC_CONSTRAINT_LABELS = {
    "TARGET_LIKELY_TOO_TIGHT": "当前更像目标受限，而不是预算受限。",
    "TARGET_LIKELY_TOO_LOOSE": "当前目标与业务效率约束不一致，优先修正目标。",
    "BUDGET_CONSTRAINED": "当前更像预算受限，成熟效率仍在业务范围内。",
    "BUSINESS_BUDGET_CAP": "当前预算超过业务上限，先纠正预算并保持其他变量不变。",
    "BUSINESS_TARGET_BOUNDARY": "当前目标越过业务硬边界，先纠正目标并保持其他变量不变。",
    "DATA_MATURITY": "最近修改或转化延迟尚未成熟，暂不提供精确调整值。",
    "INSUFFICIENT_EVENT_VOLUME": "成熟事件量不足，增加预算也不能替代学习证据。",
    "NO_NUMERIC_CHANGE_EVIDENCED": "当前没有足够证据支持修改预算或目标。",
}

_GATE_FIELD_LABELS = {
    "business_kpi_is_value": "业务 KPI 是否为价值 / 收入 / ROAS",
    "strategy_supports_value": "出价策略是否支持价值优化",
    "payment_reliable": "支付事件可靠性",
    "value_reliable": "value 回传可靠性",
    "currency_reliable": "currency 回传正确性",
    "duplicates_handled": "重复支付处理",
    "refunds_handled": "退款处理",
    "subscriptions_defined": "订阅价值口径",
    "delay_mature": "转化延迟成熟度",
    "value_reconciliation": "Google、MMP 与后端价值对账",
    "volume_assessment": "成熟事件量",
    "stability_assessment": "事件或价值稳定性",
    "single_campaign_budget_assessment": "单 Campaign 学习预算",
    "budget_assessment": "并行预算",
    "event_volume_assessment": "并行事件量",
    "isolatable": "流量与归因隔离条件",
    "reliable": "候选事件回传可靠性",
    "relationship_to_business_goal": "候选事件与业务目标的关系",
    "value_optimization": "候选 Campaign 的价值优化设置",
    "value_bidding_strategy": "候选 Campaign 的价值出价策略",
}

_VARIABLE_LABELS = {
    "campaign_create": "新建 Campaign",
    "optimization_event": "修改优化事件",
    "bid_strategy": "修改出价策略",
    "creative": "素材调整",
    "creative_add": "添加新素材",
    "bid": "修改出价目标",
    "budget": "修改预算",
}

_GAP_LABELS = {
    "confirmed project meaning for the requested AC level": "确认本项目中目标 AC 层级的实际定义",
    "OS-segmented campaign and conversion evidence": "按 Android / iOS 拆分的 Campaign 与转化证据",
    "backend value reconciliation": "后端支付价值对账",
    "campaign, OS, event, and asset-level evidence": "Campaign、OS、事件与素材粒度证据",
    "close or mature the current experiment first": "先结束当前实验，或等待其数据成熟",
    "account-specific transition evidence": "该账户的层级切换证据",
    "current campaign level and actual account settings": "当前 Campaign 层级与真实账户设置",
    "known stable AC2.5 rollback baseline": "已知稳定的 AC2.5 回退基线",
    "known stable rollback baseline": "已知稳定的回退基线",
    "account-specific review time, mature-event, or spend limit": "该账户的复查天数、成熟事件量或消耗上限",
    "creative stop condition": "素材的成熟停止条件",
    "business_cpa_ceiling_missing": "缺少业务可接受 CPA 上限",
    "business_roas_floor_missing": "缺少业务最低可接受 ROAS",
    "business_daily_budget_cap_missing": "缺少业务日预算上限",
    "current_target_missing": "缺少当前 tCPA / tROAS",
    "current_daily_budget_missing": "缺少当前日预算",
    "mature_actual_cpa_missing": "缺少成熟实际 CPA",
    "mature_actual_roas_missing": "缺少成熟实际 ROAS",
    "insufficient_mature_conversion_data": "转化延迟、观察天数或成熟事件量尚未满足",
    "value_signal_not_reliable_enough_for_troas": "value、currency 或金额对账不足以支持 tROAS",
}


def _display(value: Any, fallback: str = "保持不变") -> str:
    if value is None:
        return fallback
    return str(value)


def _numeric_display(value: Any, fallback: str = "未知") -> str:
    if value is None:
        return fallback
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):g}"
    return str(value)


def _action_label(value: Any) -> str:
    text = _display(value, "保持不动")
    return _ACTION_LABELS.get(text, text)


def _reason_label(code: str) -> str:
    if code in _REASON_LABELS:
        return _REASON_LABELS[code]
    for suffix, state in (("_failed", "未通过"), ("_unknown", "尚未确认")):
        if code.endswith(suffix):
            stem = code[: -len(suffix)]
            for prefix in (
                "candidate_event_",
                "value_signal_",
                "split_capacity_",
                "candidate_campaign_",
            ):
                if stem.startswith(prefix):
                    field = stem[len(prefix) :]
                    return f"{_GATE_FIELD_LABELS.get(field, field)}{state}"
    return f"内部安全门禁：{code}"


def _request_label(request: str) -> str:
    exact = {
        "request approved replacement assets": "请客户提供已批准的替代素材",
        "request backend value reconciliation": "请客户提供后端支付价值对账",
        "request OS-segmented campaign evidence": "请提供按 Android / iOS 拆分的 Campaign 证据",
    }
    if request in exact:
        return exact[request]
    prefixes = (
        ("request client approval for ", "请客户批准："),
        ("request client data for ", "请客户提供数据："),
        ("confirm platform capability for ", "请确认平台是否支持："),
        ("keep ", "当前不可执行，保持不变："),
        ("confirm permission for ", "请确认操作权限："),
    )
    for prefix, label in prefixes:
        if request.startswith(prefix):
            variable = request[len(prefix) :]
            if prefix == "keep ":
                for suffix in (
                    " unchanged under read-only permission",
                    " unchanged because it is not actionable",
                ):
                    if variable.endswith(suffix):
                        variable = variable[: -len(suffix)]
                        break
            return f"{label}{_VARIABLE_LABELS.get(variable, variable)}"
    return request


def _gap_label(gap: str) -> str:
    if gap in _GAP_LABELS:
        return _GAP_LABELS[gap]
    if gap.endswith(("_failed", "_unknown")):
        return _reason_label(gap)
    if gap.startswith("resolve external issue: "):
        return f"先处理外部异常：{gap.removeprefix('resolve external issue: ')}"
    return gap


def _requirement_label(requirement: str) -> str:
    if requirement in _GAP_LABELS or " " in requirement:
        return _gap_label(requirement)
    return _reason_label(requirement)


def _level_action(level: dict[str, Any], structure: dict[str, Any]) -> str:
    current = _display(level.get("current"), "未知")
    recommended = _display(level.get("recommended"), "保持当前")
    if structure.get("run_in_parallel") is True:
        return f"保持 {current}；并行候选 {recommended}"
    if level.get("action") in {"move", "rollback"}:
        return f"{current} → {recommended}"
    return f"保持 {recommended}"


def _numeric_action_line(
    label: str,
    current: Any,
    recommended: Any,
    action: Any,
) -> str:
    if action in {"INCREASE", "DECREASE", "ROLLBACK"} and recommended is not None:
        return (
            f"- {label}：{_numeric_display(current)} → {_numeric_display(recommended)}"
        )
    if current is None:
        return f"- {label}：暂不提供精确数值"
    return f"- {label}：保持 {_numeric_display(current)}"


def _rollback_text(recommendation: dict[str, Any], label: str) -> str | None:
    rollback_value = recommendation.get("rollback_value")
    condition = recommendation.get("rollback_condition")
    if rollback_value is None or not isinstance(condition, dict) or not condition:
        return None
    key, threshold = next(iter(condition.items()))
    condition_labels = {
        "mature_cpa_above": "成熟 CPA 超过",
        "mature_roas_below": "成熟 ROAS 低于",
        "delivery_rate_below": "预算消耗率低于",
    }
    return (
        f"若{condition_labels.get(str(key), str(key))} {_numeric_display(threshold)}，"
        f"将 {label} 恢复到 {_numeric_display(rollback_value)}。"
    )


def _split_hold_text(split: dict[str, Any], candidate_level: str) -> str | None:
    if split.get("state") not in {"SPLIT_BORDERLINE", "SPLIT_NOT_FEASIBLE"}:
        return None
    reasons: list[str] = []
    projected_events = split.get("projected_daily_events_per_campaign")
    minimum_events = split.get("minimum_daily_events_per_campaign")
    if (
        isinstance(projected_events, (int, float))
        and isinstance(minimum_events, (int, float))
        and projected_events < minimum_events
    ):
        reasons.append(
            "预计每条 Campaign 日均成熟事件 "
            f"{_numeric_display(projected_events)} < 最低 {_numeric_display(minimum_events)}"
        )
    available_budget = split.get("available_total_daily_budget")
    required_budget = split.get("required_total_daily_budget")
    if (
        isinstance(available_budget, (int, float))
        and isinstance(required_budget, (int, float))
        and available_budget < required_budget
    ):
        reasons.append(
            f"所需总日预算 {_numeric_display(required_budget)} > "
            f"可用 {_numeric_display(available_budget)}"
        )
    if not reasons:
        reasons.append("拆分预算或成熟事件密度尚未达到已声明门槛")
    return f"不建议新开 {candidate_level}：" + "；".join(reasons) + "。"


def _campaign_rollback_text(rollback: dict[str, Any]) -> str | None:
    if rollback.get("applicable") is not True:
        return None
    condition = rollback.get("condition")
    action = rollback.get("action")
    if not isinstance(condition, str) or not condition.strip():
        return None
    if not isinstance(action, str) or not action.strip():
        return None
    condition_text = condition.strip().rstrip("。")
    if not condition_text.startswith(("若", "当")):
        condition_text = "若" + condition_text
    return f"回退：{condition_text}，{action.strip()}"


def _render_numeric_card(result: dict[str, Any]) -> str:
    decision = result["decision"]
    level = result["campaign_level_decision"]
    structure = result["campaign_structure_decision"]
    creative = result["creative_decision"]
    target = result["target_recommendation"]
    budget = result["budget_recommendation"]
    bid_execution = result["bid_decision"]
    budget_execution = result["budget_decision"]
    constraint = result["constraint_analysis"]
    review = result["review_condition"]
    permissions = result["permission_check"]
    split = result.get("split_feasibility", {})
    rollback = result.get("rollback", {})
    target_label = str(target.get("target_type") or "目标")
    current_level = _display(level.get("current"), "当前层级")
    recommended_level = _display(level.get("recommended"), current_level)
    next_candidate = _display(level.get("next_candidate"), "候选 Campaign")
    candidate_level = (
        recommended_level if recommended_level != current_level else next_candidate
    )
    split_is_active = bool(
        structure.get("create_new_campaign")
        and structure.get("run_in_parallel")
        and split.get("state") == "SPLIT_FEASIBLE"
    )

    if split_is_active:
        campaign_action = f"保持 {current_level}；并行新开 {candidate_level}"
    else:
        campaign_action = f"保持 {current_level}；" + (
            "新开独立 Campaign"
            if structure.get("create_new_campaign")
            else "不新开 Campaign"
        )
    if creative.get("placement") == "ADD_TO_EXISTING_CAMPAIGN":
        creative_action = f"新素材加入现有 {current_level}"
    else:
        creative_action = _action_label(creative.get("action"))

    budget_label = "总日预算" if split_is_active else "日预算"
    action_lines = [
        f"- Campaign：{campaign_action}",
        _numeric_action_line(
            target_label,
            bid_execution.get("current_target"),
            bid_execution.get("recommended_target"),
            bid_execution.get("action"),
        ),
        _numeric_action_line(
            budget_label,
            budget_execution.get("current_daily_budget"),
            budget_execution.get("recommended_daily_budget"),
            budget_execution.get("action"),
        ),
    ]
    if split_is_active:
        existing_budget = split.get("existing_campaign_daily_budget")
        new_budget = split.get("new_campaign_daily_budget")
        if existing_budget is not None and new_budget is not None:
            action_lines.append(
                f"- 拆分预算：现有 {current_level} {_numeric_display(existing_budget)}；"
                f"新 {candidate_level} {_numeric_display(new_budget)}"
            )
        else:
            action_lines.append("- 拆分预算：可行，但两条 Campaign 的分配仍需确认")
        if candidate_level != current_level:
            candidate_target = split.get("candidate_target_value")
            if candidate_target is None:
                action_lines.append(
                    f"- 新 {candidate_level} 目标：暂不提供精确数值；"
                    "需成熟价值数据或后台模拟器确认"
                )
            else:
                action_lines.append(
                    f"- 新 {candidate_level} 目标：{_numeric_display(candidate_target)}"
                )
    action_lines.append(f"- 素材：{creative_action}")

    constraint_text = _NUMERIC_CONSTRAINT_LABELS.get(
        str(constraint.get("primary_constraint")),
        "当前证据不足以支持更激进的数值动作。",
    )
    if split_is_active and constraint.get("primary_constraint") == (
        "NO_NUMERIC_CHANGE_EVIDENCED"
    ):
        constraint_text = "本次只做 Campaign 拆分，现有目标和总日预算保持不变。"

    lines = [
        f"结论：{decision['summary']}",
        "",
        "现在执行：",
        *action_lines,
        "",
        constraint_text,
    ]
    split_hold_text = _split_hold_text(split, candidate_level)
    if split_hold_text:
        lines.append(split_hold_text)

    ideal_changes: list[str] = []
    if target.get("recommended_action") in {
        "INCREASE",
        "DECREASE",
        "ROLLBACK",
    } and not target.get("execution", {}).get("executable_now"):
        ideal_changes.append(
            f"{target_label} {_numeric_display(target.get('current_value'))} → "
            f"{_numeric_display(target.get('recommended_value'))}"
        )
    if budget.get("recommended_action") in {
        "INCREASE",
        "DECREASE",
        "ROLLBACK",
    } and not budget.get("execution", {}).get("executable_now"):
        ideal_changes.append(
            f"日预算 {_numeric_display(budget.get('current_daily_budget'))} → "
            f"{_numeric_display(budget.get('recommended_value'))}"
        )
    if ideal_changes:
        lines.extend(["", "建议（需授权或审批）：" + "；".join(ideal_changes)])

    after_days = review.get("after_days") or target.get("do_not_change_before", {}).get(
        "minimum_days"
    )
    mature_events = review.get("minimum_additional_mature_events") or target.get(
        "do_not_change_before", {}
    ).get("minimum_mature_events")
    if after_days is not None or mature_events is not None:
        lines.extend(
            [
                "",
                f"{_numeric_display(after_days, '声明天数')} 天或新增 "
                f"{_numeric_display(mature_events, '声明数量')} 个成熟事件后复查。",
            ]
        )

    changed_recommendation = (
        target
        if target.get("recommended_action") in {"INCREASE", "DECREASE", "ROLLBACK"}
        else budget
    )
    changed_label = target_label if changed_recommendation is target else "日预算"
    rollback_text = _rollback_text(changed_recommendation, changed_label)
    if rollback_text:
        if not changed_recommendation.get("execution", {}).get("executable_now"):
            rollback_text = "实际执行上述建议后，" + rollback_text
        lines.append(rollback_text)
    if split_is_active:
        campaign_rollback_text = _campaign_rollback_text(rollback)
        if campaign_rollback_text:
            lines.append(campaign_rollback_text)

    if permissions.get("client_requests"):
        requests = "；".join(
            _request_label(item) for item in permissions["client_requests"][:2]
        )
        lines.extend(["", f"需客户 / 管理员：{requests}"])
    has_numeric_change = any(
        section.get("recommended_value") is not None
        and section.get("recommended_action") in {"INCREASE", "DECREASE", "ROLLBACK"}
        for section in (target, budget)
    )
    if result.get("data_gaps") and not has_numeric_change:
        gaps = "；".join(_gap_label(item) for item in result["data_gaps"][:3])
        lines.extend(["", f"补充数据后再给具体数值：{gaps}"])
    lines.extend(
        [
            "",
            "真实账户写入仍需逐项人工确认。",
            f"置信度：{_CONFIDENCE_LABELS.get(decision['confidence'], decision['confidence'])}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_quick_card(result: dict[str, Any]) -> str:
    """Render one short card whose first line is always the operation verdict."""

    if result.get("derived_signals", {}).get("has_numeric_evidence") is True:
        return _render_numeric_card(result)

    decision = result["decision"]
    level = result["campaign_level_decision"]
    structure = result["campaign_structure_decision"]
    creative = result["creative_decision"]
    bid = result["bid_decision"]
    budget = result["budget_decision"]
    review = result["review_condition"]
    rollback = result["rollback"]
    permissions = result["permission_check"]
    upgrade = result.get("upgrade_condition", {})
    upgrade_requirements = upgrade.get("requirements", [])
    campaign_label = _display(
        structure.get("campaign_id") or level.get("current"), "当前 App campaign"
    )

    lines = [
        f"结论：{decision['summary']}",
        "",
        "现在执行：",
        f"- Campaign：{campaign_label}",
        f"- 广告层级：{_level_action(level, structure)}",
        f"- Campaign 结构：{_action_label(structure['action'])}；新建={'是' if structure['create_new_campaign'] else '否'}；并行={'是' if structure['run_in_parallel'] else '否'}",
        f"- 素材：{_action_label(creative['action'])}；放置={_action_label(creative.get('placement')) if creative.get('placement') else '不适用'}",
        f"- 出价目标：{_action_label(bid['action'])}；当前={_display(bid.get('current_target'), '未知')}；建议={_display(bid.get('recommended_target'), '不提供伪造数值')}",
        f"- 日预算：{_action_label(budget['action'])}；当前={_display(budget.get('current_daily_budget'), '未知')}；建议={_display(budget.get('recommended_daily_budget'), '不提供伪造数值')}",
        "",
        "原因：",
        *[f"- {_reason_label(item)}" for item in result["reason_codes"][:3]],
        *(
            [
                "",
                f"进入 {_display(upgrade.get('target_level'), '下一层级')} 前：",
                *[f"- {_requirement_label(item)}" for item in upgrade_requirements],
            ]
            if upgrade_requirements
            else []
        ),
        "",
        "不要：",
        *[f"- {_DO_NOT_LABELS.get(item, item)}" for item in result["do_not_do"]],
        "",
        "复查：",
        f"- 天数：{_display(review.get('after_days'), '未提供')}",
        f"- 新增成熟事件：{_display(review.get('minimum_additional_mature_events'), '未提供')}",
        f"- 新增消耗上限：{_display(review.get('maximum_additional_spend'), '未提供')}",
        f"- 素材停止条件：{_display(creative.get('stop_condition'), '未提供；保持不动并补充')}",
        "- 成熟判定：声明的天数、事件量和延迟门槛需全部满足",
        "",
        "撤回：",
        f"- 适用：{'是' if rollback['applicable'] else '否'}",
        f"- 条件：{_display(rollback.get('condition'), '当前没有已声明撤回条件')}",
        f"- 动作：{_display(rollback.get('action'), '当前不执行变更')}",
        *(
            [
                "",
                "需客户 / 管理员：",
                *[
                    f"- {_request_label(item)}"
                    for item in permissions["client_requests"]
                ],
            ]
            if permissions["client_requests"]
            else []
        ),
        "",
        f"权限：{'可在声明权限内准备操作' if permissions['allowed'] else '存在审批、数据或平台限制'}；真实账户写入仍需逐项人工确认。",
        f"置信度：{_CONFIDENCE_LABELS.get(decision['confidence'], decision['confidence'])}",
    ]
    if result["data_gaps"]:
        lines.extend(
            [
                "",
                "还缺：",
                *[f"- {_gap_label(item)}" for item in result["data_gaps"]],
            ]
        )
    return "\n".join(lines) + "\n"
