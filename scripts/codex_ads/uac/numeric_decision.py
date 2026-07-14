"""Deterministic bid, budget, and split recommendations for UAC Quick Ops."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from .signals import _numeric_context, derive_signals
from .types import ContractError


NUMERIC_DECISION_SCHEMA_VERSION = "1.0"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _number(value: Any) -> float | None:
    return float(value) if _finite_number(value) else None


def _quantize(value: float, reference: float) -> float:
    step = max(0.01, round(abs(reference) * 0.01, 2))
    quantized = round(value / step) * step
    digits = 2 if step < 1 else 1 if step < 10 else 0
    return round(max(0.0, quantized), digits)


def _change_percent(current: float | None, recommended: float | None) -> float | None:
    if current in {None, 0} or recommended is None:
        return None
    assert current is not None
    return round((recommended - current) / current * 100, 2)


def _candidate_values(
    current: float,
    boundary: float,
    *,
    direction: str,
    priority: str,
) -> tuple[float, float, float]:
    gap = abs(boundary - current)
    if direction == "increase":
        conservative_fraction = 0.25
        recommended_fraction = {
            "scale": 0.5,
            "balanced": 0.4,
            "efficiency": 0.25,
        }[priority]
        aggressive_fraction = {
            "scale": 1.0,
            "balanced": 0.75,
            "efficiency": 0.5,
        }[priority]
        raw = (
            current + gap * conservative_fraction,
            current + gap * recommended_fraction,
            current + gap * aggressive_fraction,
        )
    else:
        conservative_fraction = 0.25
        recommended_fraction = {
            "scale": 0.5,
            "balanced": 0.6,
            "efficiency": 1.0,
        }[priority]
        aggressive_fraction = 1.0
        raw = (
            current - gap * conservative_fraction,
            current - gap * recommended_fraction,
            current - gap * aggressive_fraction,
        )
    quantized = [_quantize(value, current) for value in raw]
    if direction == "increase":
        quantized = [min(value, boundary) for value in quantized]
    else:
        quantized = [max(value, boundary) for value in quantized]
    return tuple(quantized)  # type: ignore[return-value]


def _measurement_block(case: Mapping[str, Any], *, value_target: bool) -> str | None:
    measurement = _mapping(case.get("measurement"))
    goal = _mapping(case.get("goal"))
    comparisons = (
        "google_ads_vs_firebase",
        "google_ads_vs_mmp",
        "mmp_vs_backend",
    )
    if any(measurement.get(field) == "material_mismatch" for field in comparisons):
        return "measurement_reconciliation_unreliable"
    if measurement.get("duplicate_events") is True:
        return "duplicate_conversion_events"
    if value_target and measurement.get("value_currency_valid") is False:
        return "value_or_currency_not_verified"
    business_goal = str(goal.get("business_goal", "")).lower()
    if (
        business_goal in {"payment", "value", "retention", "revenue", "subscription"}
        and measurement.get("payment_trial_refund_distinguished") is False
    ):
        return "payment_trial_or_refund_definition_unreliable"
    if (
        business_goal in {"subscription", "retention"}
        and measurement.get("subscription_renewal_included") is False
    ):
        return "subscription_renewal_value_not_included"
    missing_rate = _number(measurement.get("value_missing_rate"))
    currency_rate = _number(measurement.get("currency_consistency_rate"))
    google_mmp_rate = _number(measurement.get("google_mmp_value_difference_rate"))
    mmp_backend_rate = _number(measurement.get("mmp_backend_value_difference_rate"))
    refund_rate = _number(measurement.get("refund_rate"))
    maximum_refund_rate = _number(goal.get("maximum_acceptable_refund_rate"))
    if business_goal in {"payment", "value", "retention", "revenue"} and (
        (missing_rate is not None and missing_rate > 0.1)
        or (currency_rate is not None and currency_rate < 0.95)
        or (google_mmp_rate is not None and google_mmp_rate > 0.2)
        or (mmp_backend_rate is not None and mmp_backend_rate > 0.2)
        or (
            refund_rate is not None
            and maximum_refund_rate is not None
            and refund_rate > maximum_refund_rate
        )
    ):
        return "numeric_value_measurement_unreliable"
    return None


def _review_gate(case: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    review = _mapping(_mapping(case.get("quick_ops")).get("review"))
    return {
        "minimum_days": review.get("after_days") or context.get("minimum_days"),
        "minimum_mature_events": review.get("minimum_additional_mature_events")
        or context.get("minimum_conversions"),
        "conversion_delay_must_be_mature": review.get(
            "conversion_delay_must_be_mature", True
        ),
    }


def _empty_target(
    *,
    target_type: str,
    current: float | None,
    reason: str,
    action: str = "NO_CHANGE",
    context: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    hold_current = reason in {
        "target_is_not_primary_constraint",
        "budget_is_the_primary_constraint",
        "business_budget_cap_correction_precedes_target_change",
    }
    hold_value = current if hold_current else None
    return {
        "target_type": target_type,
        "current_value": current,
        "conservative_value": hold_value,
        "recommended_value": hold_value,
        "aggressive_value": hold_value,
        "recommended_action": action,
        "change_percent": None,
        "evidence_quality": "insufficient",
        "calculation_basis": [],
        "calculation_evidence": [{"type": "INSUFFICIENT_EVIDENCE", "fact": reason}],
        "do_not_change_before": _review_gate(case, context),
        "rollback_value": None,
        "rollback_condition": None,
        "reason": reason,
    }


def _hard_target_boundary_correction(
    *,
    target_type: str,
    current: float,
    boundary: float,
    context: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any] | None:
    if target_type == "tROAS":
        if current >= boundary:
            return None
        action = "INCREASE"
        boundary_fact = "business_roas_floor"
    else:
        if current <= boundary:
            return None
        action = "DECREASE"
        boundary_fact = "business_cpa_ceiling"
    return {
        "target_type": target_type,
        "current_value": current,
        "conservative_value": boundary,
        "recommended_value": boundary,
        "aggressive_value": boundary,
        "recommended_action": action,
        "change_percent": _change_percent(current, boundary),
        "evidence_quality": "high",
        "calculation_basis": ["current_account_target", boundary_fact],
        "calculation_evidence": [
            {
                "type": "ACCOUNT_EVIDENCE",
                "fact": "current_account_target",
                "value": current,
            },
            {
                "type": "BUSINESS_CONSTRAINT",
                "fact": boundary_fact,
                "value": boundary,
            },
        ],
        "do_not_change_before": _review_gate(case, context),
        "rollback_value": None,
        "rollback_condition": None,
        "reason": "current_target_violates_business_boundary",
    }


def _target_recommendation(
    case: Mapping[str, Any],
    signals: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    goal = _mapping(case.get("goal"))
    strategy = str(goal.get("bidding_strategy", "")).lower()
    value_target = "roas" in strategy or context.get("target_roas") is not None
    target_type = "tROAS" if value_target else "tCPA"
    current = _number(context.get("target_roas" if value_target else "target_cpa"))
    maturity = _mapping(signals.get("maturity"))
    target_state = _mapping(signals.get("target_constraint")).get("state")
    if not context.get("has_numeric_evidence"):
        return _empty_target(
            target_type=target_type,
            current=current,
            reason="numeric_account_evidence_not_supplied",
            context=context,
            case=case,
        )
    current_budget = _number(context.get("current_daily_budget"))
    daily_budget_cap = _number(context.get("daily_budget_cap"))
    if (
        current_budget is not None
        and daily_budget_cap is not None
        and current_budget > daily_budget_cap
    ):
        return _empty_target(
            target_type=target_type,
            current=current,
            reason="business_budget_cap_correction_precedes_target_change",
            context=context,
            case=case,
        )
    if current is None:
        return _empty_target(
            target_type=target_type,
            current=None,
            reason="current_target_missing",
            context=context,
            case=case,
        )
    boundary = _number(
        context.get(
            "minimum_acceptable_roas" if value_target else "maximum_acceptable_cpa"
        )
    )
    if boundary is None:
        return _empty_target(
            target_type=target_type,
            current=current,
            reason=(
                "business_roas_floor_missing"
                if value_target
                else "business_cpa_ceiling_missing"
            ),
            context=context,
            case=case,
        )
    hard_correction = _hard_target_boundary_correction(
        target_type=target_type,
        current=current,
        boundary=boundary,
        context=context,
        case=case,
    )
    if hard_correction is not None:
        return hard_correction
    if maturity.get("state") != "MATURE":
        return _empty_target(
            target_type=target_type,
            current=current,
            reason="insufficient_mature_conversion_data",
            action="WAIT",
            context=context,
            case=case,
        )
    measurement_reason = _measurement_block(case, value_target=value_target)
    if measurement_reason is not None:
        return _empty_target(
            target_type=target_type,
            current=current,
            reason=measurement_reason,
            context=context,
            case=case,
        )
    if value_target and _mapping(signals.get("value_signal")).get("state") != (
        "VALUE_SIGNAL_READY"
    ):
        return _empty_target(
            target_type=target_type,
            current=current,
            reason="value_signal_not_reliable_enough_for_troas",
            context=context,
            case=case,
        )
    if value_target and _mapping(signals.get("event_volume")).get("state") not in {
        "SUFFICIENT_AND_STABLE",
        "SUFFICIENT_BUT_VOLATILE",
    }:
        return _empty_target(
            target_type=target_type,
            current=current,
            reason="mature_value_event_volume_is_insufficient",
            context=context,
            case=case,
        )
    priority = str(context.get("optimization_priority", "balanced"))
    if value_target:
        actual = context.get("mature_actual_roas")
        if actual is None:
            reason = "mature_actual_roas_missing"
        else:
            reason = "target_is_not_primary_constraint"
        if actual is None:
            return _empty_target(
                target_type=target_type,
                current=current,
                reason=reason,
                context=context,
                case=case,
            )
        if target_state == "TARGET_LIKELY_TOO_TIGHT" and current > boundary:
            conservative, recommended, aggressive = _candidate_values(
                current,
                float(boundary),
                direction="decrease",
                priority=priority,
            )
            action = "DECREASE"
            basis = [
                "mature_actual_roas",
                "spend_delivery_rate",
                "business_roas_floor",
            ]
            rollback_condition = {"mature_roas_below": float(boundary)}
        elif target_state == "TARGET_LIKELY_TOO_LOOSE" and current < boundary:
            conservative = recommended = aggressive = float(boundary)
            action = "INCREASE"
            basis = ["mature_actual_roas", "business_roas_floor"]
            rollback_condition = None
        else:
            return _empty_target(
                target_type=target_type,
                current=current,
                reason="target_is_not_primary_constraint",
                context=context,
                case=case,
            )
    else:
        actual = context.get("mature_actual_cpa")
        if actual is None:
            reason = "mature_actual_cpa_missing"
        else:
            reason = "target_is_not_primary_constraint"
        if actual is None:
            return _empty_target(
                target_type=target_type,
                current=current,
                reason=reason,
                context=context,
                case=case,
            )
        if actual > boundary and current <= boundary:
            return _empty_target(
                target_type=target_type,
                current=current,
                reason="mature_cpa_above_business_ceiling_do_not_relax",
                context=context,
                case=case,
            )
        if target_state == "TARGET_LIKELY_TOO_TIGHT" and current < boundary:
            conservative, recommended, aggressive = _candidate_values(
                current,
                float(boundary),
                direction="increase",
                priority=priority,
            )
            action = "INCREASE"
            basis = [
                "mature_actual_cpa",
                "spend_delivery_rate",
                "business_cpa_ceiling",
            ]
            rollback_condition = {"mature_cpa_above": float(boundary)}
        elif target_state == "TARGET_LIKELY_TOO_LOOSE" and current > boundary:
            conservative = recommended = aggressive = float(boundary)
            action = "DECREASE"
            basis = ["mature_actual_cpa", "business_cpa_ceiling"]
            rollback_condition = None
        else:
            return _empty_target(
                target_type=target_type,
                current=current,
                reason="target_is_not_primary_constraint",
                context=context,
                case=case,
            )
    evidence_quality = (
        "high"
        if _mapping(signals.get("event_volume")).get("state") == "SUFFICIENT_AND_STABLE"
        else "medium"
    )
    return {
        "target_type": target_type,
        "current_value": current,
        "conservative_value": conservative,
        "recommended_value": recommended,
        "aggressive_value": aggressive,
        "recommended_action": action,
        "change_percent": _change_percent(current, recommended),
        "evidence_quality": evidence_quality,
        "calculation_basis": basis,
        "calculation_evidence": [
            {
                "type": "ACCOUNT_EVIDENCE",
                "fact": basis[0],
                "value": actual,
            },
            {
                "type": "ACCOUNT_EVIDENCE",
                "fact": "spend_delivery_rate",
                "value": _mapping(signals.get("budget_delivery")).get("delivery_rate"),
            },
            {
                "type": "BUSINESS_CONSTRAINT",
                "fact": basis[-1],
                "value": boundary,
            },
            {
                "type": "PLATFORM_GUIDANCE",
                "fact": "avoid_large_frequent_target_changes",
            },
            {
                "type": "HEURISTIC",
                "fact": "candidate_values_use_account_specific_headroom",
            },
        ],
        "do_not_change_before": _review_gate(case, context),
        "rollback_value": current if rollback_condition is not None else None,
        "rollback_condition": rollback_condition,
        "reason": "account_evidence_supports_one_bounded_target_change",
    }


def _empty_budget(
    *,
    current: float | None,
    reason: str,
    context: Mapping[str, Any],
    case: Mapping[str, Any],
    action: str = "NO_CHANGE",
) -> dict[str, Any]:
    hold_current = reason in {
        "target_change_selected_as_the_single_numeric_variable",
        "budget_is_not_the_primary_constraint",
    }
    hold_value = current if hold_current else None
    return {
        "current_daily_budget": current,
        "conservative_value": hold_value,
        "recommended_value": hold_value,
        "aggressive_value": hold_value,
        "recommended_action": action,
        "change_percent": None,
        "evidence_quality": "insufficient",
        "calculation_basis": [],
        "calculation_evidence": [{"type": "INSUFFICIENT_EVIDENCE", "fact": reason}],
        "do_not_change_before": _review_gate(case, context),
        "rollback_value": None,
        "rollback_condition": None,
        "reason": reason,
    }


def _hard_budget_cap_correction(
    *,
    current: float,
    cap: float,
    context: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "current_daily_budget": current,
        "conservative_value": cap,
        "recommended_value": cap,
        "aggressive_value": cap,
        "recommended_action": "DECREASE",
        "change_percent": _change_percent(current, cap),
        "evidence_quality": "high",
        "calculation_basis": ["current_daily_budget", "business_daily_budget_cap"],
        "calculation_evidence": [
            {
                "type": "ACCOUNT_EVIDENCE",
                "fact": "current_daily_budget",
                "value": current,
            },
            {
                "type": "BUSINESS_CONSTRAINT",
                "fact": "daily_budget_cap",
                "value": cap,
            },
        ],
        "do_not_change_before": _review_gate(case, context),
        "rollback_value": None,
        "rollback_condition": None,
        "reason": "current_budget_exceeds_business_cap",
    }


def _budget_recommendation(
    case: Mapping[str, Any],
    signals: Mapping[str, Any],
    context: Mapping[str, Any],
    target: Mapping[str, Any],
) -> dict[str, Any]:
    current = _number(context.get("current_daily_budget"))
    if not context.get("has_numeric_evidence"):
        return _empty_budget(
            current=current,
            reason="numeric_account_evidence_not_supplied",
            context=context,
            case=case,
        )
    if current is None:
        return _empty_budget(
            current=None,
            reason="current_daily_budget_missing",
            context=context,
            case=case,
        )
    cap = context.get("daily_budget_cap")
    if cap is None:
        return _empty_budget(
            current=current,
            reason="business_daily_budget_cap_missing",
            context=context,
            case=case,
        )
    cap = float(cap)
    if current > cap:
        return _hard_budget_cap_correction(
            current=current,
            cap=cap,
            context=context,
            case=case,
        )
    if _mapping(signals.get("maturity")).get("state") != "MATURE":
        return _empty_budget(
            current=current,
            reason="insufficient_mature_conversion_data",
            context=context,
            case=case,
            action="WAIT",
        )
    if target.get("recommended_action") not in {"NO_CHANGE", "WAIT", None}:
        return _empty_budget(
            current=current,
            reason="target_change_selected_as_the_single_numeric_variable",
            context=context,
            case=case,
        )
    priority = str(context.get("optimization_priority", "balanced"))
    budget_state = _mapping(signals.get("budget_delivery")).get("state")
    event_state = _mapping(signals.get("event_volume")).get("state")
    strategy = str(_mapping(case.get("goal")).get("bidding_strategy", "")).lower()
    if "roas" in strategy:
        actual = context.get("mature_actual_roas")
        boundary = context.get("minimum_acceptable_roas")
        efficient = actual is not None and boundary is not None and actual >= boundary
    else:
        actual = context.get("mature_actual_cpa")
        boundary = context.get("maximum_acceptable_cpa")
        efficient = actual is not None and boundary is not None and actual <= boundary
    if budget_state == "BUDGET_CONSTRAINED" and cap > current:
        measurement_reason = _measurement_block(case, value_target="roas" in strategy)
        if measurement_reason is not None:
            return _empty_budget(
                current=current,
                reason=measurement_reason,
                context=context,
                case=case,
            )
        if event_state not in {
            "SUFFICIENT_AND_STABLE",
            "SUFFICIENT_BUT_VOLATILE",
        }:
            return _empty_budget(
                current=current,
                reason="event_volume_cannot_support_budget_increase",
                context=context,
                case=case,
            )
        if not efficient:
            return _empty_budget(
                current=current,
                reason="mature_efficiency_outside_business_constraint",
                context=context,
                case=case,
            )
        conservative, recommended, aggressive = _candidate_values(
            current, cap, direction="increase", priority=priority
        )
        action = "INCREASE"
        reason = "budget_constraint_with_mature_efficiency_inside_business_limit"
        rollback_value = current
        rollback_condition = (
            {"mature_cpa_above": boundary}
            if "roas" not in strategy
            else {"mature_roas_below": boundary}
        )
    else:
        return _empty_budget(
            current=current,
            reason="budget_is_not_the_primary_constraint",
            context=context,
            case=case,
        )
    return {
        "current_daily_budget": current,
        "conservative_value": conservative,
        "recommended_value": recommended,
        "aggressive_value": aggressive,
        "recommended_action": action,
        "change_percent": _change_percent(current, recommended),
        "evidence_quality": (
            "high" if event_state == "SUFFICIENT_AND_STABLE" else "medium"
        ),
        "calculation_basis": [
            "multi_day_spend_delivery",
            "mature_efficiency",
            "business_daily_budget_cap",
        ],
        "calculation_evidence": [
            {
                "type": "ACCOUNT_EVIDENCE",
                "fact": "multi_day_spend_delivery",
                "value": _mapping(signals.get("budget_delivery")).get("delivery_rate"),
            },
            {
                "type": "ACCOUNT_EVIDENCE",
                "fact": "mature_efficiency",
                "value": actual,
            },
            {
                "type": "BUSINESS_CONSTRAINT",
                "fact": "daily_budget_cap",
                "value": cap,
            },
            {
                "type": "HEURISTIC",
                "fact": "candidate_values_use_account_specific_budget_headroom",
            },
        ],
        "do_not_change_before": _review_gate(case, context),
        "rollback_value": rollback_value,
        "rollback_condition": rollback_condition,
        "reason": reason,
    }


def _primary_constraint(signals: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    maturity = _mapping(signals.get("maturity")).get("state")
    target = _mapping(signals.get("target_constraint")).get("state")
    budget = _mapping(signals.get("budget_delivery")).get("state")
    events = _mapping(signals.get("event_volume")).get("state")
    current_budget = _number(context.get("current_daily_budget"))
    daily_budget_cap = _number(context.get("daily_budget_cap"))
    if (
        current_budget is not None
        and daily_budget_cap is not None
        and current_budget > daily_budget_cap
    ):
        return "BUSINESS_BUDGET_CAP"
    target_cpa = _number(context.get("target_cpa"))
    maximum_cpa = _number(context.get("maximum_acceptable_cpa"))
    target_roas = _number(context.get("target_roas"))
    minimum_roas = _number(context.get("minimum_acceptable_roas"))
    if target_roas is not None:
        target_boundary_violated = (
            minimum_roas is not None and target_roas < minimum_roas
        )
    else:
        target_boundary_violated = (
            target_cpa is not None
            and maximum_cpa is not None
            and target_cpa > maximum_cpa
        )
    if target_boundary_violated:
        return "BUSINESS_TARGET_BOUNDARY"
    if maturity != "MATURE":
        return "DATA_MATURITY"
    if target in {"TARGET_LIKELY_TOO_TIGHT", "TARGET_LIKELY_TOO_LOOSE"}:
        return str(target)
    if budget == "BUDGET_CONSTRAINED":
        return "BUDGET_CONSTRAINED"
    if events == "INSUFFICIENT":
        return "INSUFFICIENT_EVENT_VOLUME"
    return "NO_NUMERIC_CHANGE_EVIDENCED"


def _permission_class(case: Mapping[str, Any], variable: str) -> str:
    permissions = _mapping(case.get("permissions"))
    if variable in permissions.get("optimizer_can", []):
        return "OPTIMIZER_CAN_EXECUTE"
    if variable in permissions.get("client_approval_required", []):
        return "CLIENT_APPROVAL_REQUIRED"
    if variable in permissions.get("client_data_required", []):
        return "CLIENT_DATA_REQUIRED"
    if variable in permissions.get("platform_limitations", []):
        return "PLATFORM_LIMITATION"
    if variable in permissions.get("unavailable", []):
        return "NOT_ACTIONABLE"
    return "NOT_ACTIONABLE"


def _apply_permission(
    recommendation: dict[str, Any], case: Mapping[str, Any], variable: str
) -> None:
    permission = _permission_class(case, variable)
    changes = recommendation.get("recommended_value") is not None and (
        recommendation.get("recommended_action") not in {"NO_CHANGE", "WAIT"}
    )
    executable = bool(changes and permission == "OPTIMIZER_CAN_EXECUTE")
    if not changes or executable:
        request = None
    elif permission == "CLIENT_APPROVAL_REQUIRED":
        request = f"request client approval for {variable} recommendation"
    elif permission == "CLIENT_DATA_REQUIRED":
        request = f"request client data before {variable} recommendation"
    elif permission == "PLATFORM_LIMITATION":
        request = (
            f"keep {variable} as a future recommendation; platform access is blocked"
        )
    else:
        request = f"ask an authorized operator to apply the {variable} recommendation"
    recommendation["executable_now"] = executable
    recommendation["permission"] = permission
    recommendation["client_request"] = request


def _campaign_level_guidance(
    case: Mapping[str, Any], primary_constraint: str, split: Mapping[str, Any]
) -> dict[str, Any]:
    facts = _mapping(case.get("facts"))
    plan = _mapping(facts.get("split_plan"))
    quick = _mapping(case.get("quick_ops"))
    current_campaign = _mapping(quick.get("current_campaign"))
    current = facts.get("campaign_level") or current_campaign.get("level")
    candidate = plan.get("candidate_level")
    permission = _permission_class(case, "campaign_create")
    if primary_constraint in {
        "TARGET_LIKELY_TOO_TIGHT",
        "TARGET_LIKELY_TOO_LOOSE",
        "BUSINESS_BUDGET_CAP",
        "BUSINESS_TARGET_BOUNDARY",
        "DATA_MATURITY",
        "INSUFFICIENT_EVENT_VOLUME",
    }:
        immediate = "KEEP_CURRENT"
        recommended = current
    elif split.get("state") == "SPLIT_FEASIBLE" and permission == (
        "OPTIMIZER_CAN_EXECUTE"
    ):
        immediate = "TEST_IN_PARALLEL"
        recommended = candidate or current
    else:
        immediate = "KEEP_CURRENT"
        recommended = current
    return {
        "current_level": current,
        "recommended_level": recommended,
        "immediate_action": immediate,
        "future_candidate": candidate,
        "executable_now": bool(
            immediate == "TEST_IN_PARALLEL" and permission == "OPTIMIZER_CAN_EXECUTE"
        ),
        "permission": permission,
    }


def recommend_numeric(
    case: Mapping[str, Any], signals: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Return bounded target, budget, and split recommendations from facts."""

    if not isinstance(case, Mapping):
        raise ContractError("UAC input must be an object")
    derived = dict(signals) if signals is not None else derive_signals(case)
    context = _numeric_context(case)
    target = _target_recommendation(case, derived, context)
    budget = _budget_recommendation(case, derived, context, target)
    _apply_permission(target, case, "bid")
    _apply_permission(budget, case, "budget")
    supplied = _mapping(_mapping(case.get("quick_ops")).get("bid_budget"))
    ignored_hints = []
    for name in ("recommended_target", "recommended_daily_budget"):
        if supplied.get(name) is not None:
            ignored_hints.append(name)
    evidence = list(derived.get("calculation_evidence", []))
    evidence.extend(target.get("calculation_evidence", []))
    evidence.extend(budget.get("calculation_evidence", []))
    heuristics = list(derived.get("heuristics_used", []))
    heuristics.extend(
        [
            "candidate_values_are_bounded_by_account_specific_business_limits",
            "only_one_ordinary_numeric_variable_may_change_at_a_time",
        ]
    )
    if ignored_hints:
        heuristics.append(
            "legacy_recommended_values_are_untrusted_hints_and_do_not_bypass_gates"
        )
    primary_constraint = _primary_constraint(derived, context)
    missing_markers = (
        "missing",
        "insufficient",
        "unreliable",
        "not_supplied",
        "not_reliable",
    )
    data_gaps = [
        str(reason)
        for reason in (target.get("reason"), budget.get("reason"))
        if isinstance(reason, str)
        and any(marker in reason for marker in missing_markers)
    ]
    split = dict(_mapping(derived.get("split_feasibility")))
    return {
        "schema_version": NUMERIC_DECISION_SCHEMA_VERSION,
        "constraint_analysis": {
            "has_numeric_evidence": derived.get("has_numeric_evidence") is True,
            "primary_constraint": primary_constraint,
            "budget_state": _mapping(derived.get("budget_delivery")).get("state"),
            "maturity_state": _mapping(derived.get("maturity")).get("state"),
            "target_state": _mapping(derived.get("target_constraint")).get("state"),
            "event_volume_state": _mapping(derived.get("event_volume")).get("state"),
            "value_signal_state": _mapping(derived.get("value_signal")).get("state"),
        },
        "target_recommendation": target,
        "budget_recommendation": budget,
        "split_feasibility": split,
        "campaign_level_guidance": _campaign_level_guidance(
            case, primary_constraint, split
        ),
        "calculation_evidence": evidence,
        "heuristics_used": list(dict.fromkeys(heuristics)),
        "legacy_hints_ignored": ignored_hints,
        "data_gaps": list(dict.fromkeys(data_gaps)),
        "classification": {
            "type": "OPERATIONAL_DECISION",
            "experiment_validity": "NOT_AN_EXPERIMENT",
        },
        "account_write": False,
        "ledger_write": False,
    }


__all__ = ["NUMERIC_DECISION_SCHEMA_VERSION", "recommend_numeric"]
