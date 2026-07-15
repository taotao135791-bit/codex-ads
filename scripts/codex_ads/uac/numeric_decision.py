"""Deterministic bid, budget, and split recommendations for UAC Quick Ops."""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from .policy_loader import LoadedPolicy, load_policy
from .signals import _numeric_context, derive_signals
from .types import ContractError


NUMERIC_DECISION_SCHEMA_VERSION = "1.0"

NORMAL_OPTIMIZATION = "NORMAL_OPTIMIZATION"
STAGED_OPTIMIZATION = "STAGED_OPTIMIZATION"
OPERATIONAL_CORRECTION = "OPERATIONAL_CORRECTION"
EMERGENCY_INTERVENTION = "EMERGENCY_INTERVENTION"

_OPERATION_CLASSIFICATIONS = {
    NORMAL_OPTIMIZATION,
    STAGED_OPTIMIZATION,
    OPERATIONAL_CORRECTION,
    EMERGENCY_INTERVENTION,
}

_MAX_EXPLICIT_STAGED_CHECKPOINTS = 25


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


def _policy_values(policy: LoadedPolicy) -> Mapping[str, Any]:
    values = policy.values
    if not isinstance(values, Mapping):
        raise ContractError("loaded numeric policy must be an object")
    return values


def _change_limit_percent(
    policy: LoadedPolicy, *, variable: str, direction: str
) -> float:
    limits = _mapping(_policy_values(policy).get("numeric_change_limits"))
    variable_limits = _mapping(limits.get(variable))
    key = f"normal_max_{direction}_percent"
    value = _number(variable_limits.get(key))
    if value is None or value < 0 or value > 100:
        raise ContractError(
            f"numeric policy numeric_change_limits.{variable}.{key} "
            "must be between 0 and 100"
        )
    return value


def _limit_candidate(
    current: float,
    candidate: float,
    *,
    variable: str,
    direction: str,
    policy: LoadedPolicy,
) -> tuple[float, float, bool]:
    limit_percent = _change_limit_percent(
        policy, variable=variable, direction=direction
    )
    if direction == "increase":
        limit_boundary = current * (1 + limit_percent / 100)
        raw_limited = min(candidate, limit_boundary)
    else:
        limit_boundary = current * (1 - limit_percent / 100)
        raw_limited = max(candidate, limit_boundary)
    capped = not math.isclose(raw_limited, candidate, rel_tol=1e-9, abs_tol=1e-9)
    if not capped:
        return candidate, limit_percent, False
    limited = _quantize(raw_limited, current)
    if direction == "increase":
        limited = min(limited, candidate, limit_boundary)
    else:
        limited = max(limited, candidate, limit_boundary)
    return limited, limit_percent, True


def _stage_review_values(
    policy: LoadedPolicy, review_gate: Mapping[str, Any]
) -> tuple[float | None, float | None]:
    staged = _mapping(_policy_values(policy).get("staged_adjustment"))
    days = _number(review_gate.get("minimum_days"))
    events = _number(review_gate.get("minimum_mature_events"))
    if days is None:
        days = _number(staged.get("review_after_days"))
    if events is None:
        events = _number(staged.get("minimum_mature_events"))
    return days, events


def _build_staged_plan(
    *,
    current: float,
    first_stage: float,
    final_candidate: float,
    variable: str,
    direction: str,
    policy: LoadedPolicy,
    review_gate: Mapping[str, Any],
) -> dict[str, Any]:
    review_after_days, minimum_mature_events = _stage_review_values(policy, review_gate)
    limit_percent = _change_limit_percent(
        policy, variable=variable, direction=direction
    )
    stages: list[dict[str, Any]] = []
    value = current
    next_value = first_stage
    fully_enumerated = False
    for stage_number in range(1, _MAX_EXPLICIT_STAGED_CHECKPOINTS + 1):
        immediate = stage_number == 1
        stage: dict[str, Any] = {
            "stage": stage_number,
            "target": next_value,
            "immediate": immediate,
            "approval_state": "PROPOSED" if immediate else "REQUIRES_FRESH_REVIEW",
            "review_after_days": review_after_days,
            "minimum_mature_events": minimum_mature_events,
            "automatic_execution": False,
        }
        if not immediate:
            stage["condition"] = {
                "fresh_mature_data_required": True,
                "conversion_delay_mature": True,
                "mature_efficiency_within_business_limit": True,
                "delivery_improved_or_control_objective_met": True,
                "no_unreviewed_concurrent_change": True,
            }
        stages.append(stage)
        if math.isclose(next_value, final_candidate, rel_tol=1e-9, abs_tol=1e-9):
            fully_enumerated = True
            break
        value = next_value
        if direction == "increase":
            raw_next = min(final_candidate, value * (1 + limit_percent / 100))
        else:
            raw_next = max(final_candidate, value * (1 - limit_percent / 100))
        raw_next = round(raw_next, 12)
        next_value = _quantize(raw_next, value)
        if direction == "increase":
            next_value = min(next_value, raw_next, final_candidate)
        else:
            next_value = max(next_value, raw_next, final_candidate)
        if math.isclose(next_value, value, rel_tol=1e-9, abs_tol=1e-9):
            # A valid sub-1% policy can be smaller than the display quantizer.
            # Preserve the exact safe cap boundary instead of crashing or
            # silently widening the configured percentage.
            next_value = round(raw_next, 12)
        if math.isclose(next_value, value, rel_tol=1e-12, abs_tol=1e-12):
            break
    return {
        "final_candidate": final_candidate,
        "immediate_stage": 1,
        "stages": stages,
        "stages_fully_enumerated": fully_enumerated,
        "remaining_stages_require_fresh_recalculation": not fully_enumerated,
        "future_stages_require_fresh_review": True,
        "automatic_execution": False,
    }


def _empty_numeric_safety(policy: LoadedPolicy) -> dict[str, Any]:
    return {
        "policy_version": policy.policy_version,
        "raw_candidate": None,
        "business_bounded_candidate": None,
        "change_limited_candidate": None,
        "final_recommendation": None,
        "current_change_percent": None,
        "staged_adjustment_required": False,
        "operation_classification": NORMAL_OPTIMIZATION,
        "limit_reasons": [],
        "applied_change_limit_percent": None,
        "capped_by_policy": False,
        "staged_plan": None,
        "correction_evidence": None,
    }


def _correction_request(
    case: Mapping[str, Any], *, variable: str, target_type: str | None = None
) -> tuple[bool, float | None, str | None]:
    operational = _mapping(_mapping(case.get("quick_ops")).get("operational"))
    if operational.get("operation_classification") != OPERATIONAL_CORRECTION:
        return False, None, None
    affected = str(operational.get("affected_variable", ""))
    if variable == "target":
        specific_target = "target_roas" if target_type == "tROAS" else "target_cpa"
        accepted_variables = {"target", "bid", specific_target}
    else:
        accepted_variables = {"daily_budget", "budget"}
    if affected not in accepted_variables:
        if variable == "target" and affected in {"target_cpa", "target_roas"}:
            return True, None, "operational_correction_target_type_mismatch"
        return False, None, None
    historical = _number(operational.get("historical_approved_value"))
    rollback_target = _number(operational.get("rollback_target"))
    evidence = operational.get("configuration_error_evidence")
    if (
        historical is None
        or rollback_target is None
        or historical <= 0
        or rollback_target <= 0
        or not math.isclose(historical, rollback_target, rel_tol=1e-9, abs_tol=1e-9)
        or not isinstance(evidence, str)
        or not evidence.strip()
        or operational.get("configuration_error_confirmed") is not True
        or operational.get("human_confirmation") is not True
    ):
        return True, None, "operational_correction_evidence_incomplete"
    return True, historical, None


def _correction_within_business_boundary(
    value: float, *, variable: str, target_type: str | None, context: Mapping[str, Any]
) -> bool:
    if value <= 0:
        return False
    if variable == "daily_budget":
        cap = _number(context.get("daily_budget_cap"))
        return cap is not None and value <= cap
    if target_type == "tROAS":
        floor = _number(context.get("minimum_acceptable_roas"))
        return floor is not None and value >= floor
    ceiling = _number(context.get("maximum_acceptable_cpa"))
    return ceiling is not None and value <= ceiling


def _correction_recommendation(
    *,
    current: float,
    historical: float,
    target_type: str | None,
    context: Mapping[str, Any],
    case: Mapping[str, Any],
    budget: bool,
) -> dict[str, Any]:
    if math.isclose(current, historical, rel_tol=1e-9, abs_tol=1e-9):
        action = "NO_CHANGE"
    else:
        action = "INCREASE" if historical > current else "DECREASE"
    current_key = "current_daily_budget" if budget else "current_value"
    result: dict[str, Any] = {
        current_key: current,
        "conservative_value": historical,
        "recommended_value": historical,
        "aggressive_value": historical,
        "recommended_action": action,
        "change_percent": _change_percent(current, historical),
        "evidence_quality": "high",
        "calculation_basis": [
            "confirmed_configuration_error",
            "historical_approved_value",
            "explicit_human_confirmation",
        ],
        "calculation_evidence": [
            {
                "type": "ACCOUNT_EVIDENCE",
                "fact": "historical_approved_value",
                "value": historical,
            },
            {
                "type": "BUSINESS_CONSTRAINT",
                "fact": "confirmed_configuration_error",
            },
        ],
        "do_not_change_before": _review_gate(case, context),
        "rollback_value": historical,
        "rollback_condition": {"configuration_error_reappears": True},
        "reason": "restore_confirmed_historical_value_after_configuration_error",
        "numeric_safety": {
            "policy_version": None,
            "raw_candidate": historical,
            "business_bounded_candidate": historical,
            "change_limited_candidate": historical,
            "final_recommendation": historical,
            "current_change_percent": _change_percent(current, historical),
            "staged_adjustment_required": False,
            "operation_classification": OPERATIONAL_CORRECTION,
            "limit_reasons": [
                "confirmed_operational_correction_bypasses_normal_change_cap"
            ],
            "applied_change_limit_percent": None,
            "capped_by_policy": False,
            "staged_plan": None,
            "correction_evidence": {
                "historical_approved_value": historical,
                "rollback_target": historical,
                "configuration_error_confirmed": True,
                "human_confirmation_recorded": True,
            },
        },
    }
    if not budget:
        result["target_type"] = target_type
    return result


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


def _candidate_within_business_boundary(
    value: float,
    *,
    variable: str,
    target_type: str | None,
    context: Mapping[str, Any],
) -> bool:
    return _correction_within_business_boundary(
        value,
        variable=variable,
        target_type=target_type,
        context=context,
    )


def _apply_numeric_safety(
    recommendation: dict[str, Any],
    *,
    variable: str,
    current_field: str,
    target_type: str | None,
    context: Mapping[str, Any],
    case: Mapping[str, Any],
    policy: LoadedPolicy,
) -> None:
    current = _number(recommendation.get(current_field))
    candidate = _number(recommendation.get("recommended_value"))
    action = str(recommendation.get("recommended_action", "NO_CHANGE"))
    existing_safety = recommendation.get("numeric_safety")
    if (
        isinstance(existing_safety, dict)
        and existing_safety.get("operation_classification") == OPERATIONAL_CORRECTION
    ):
        existing_safety["policy_version"] = policy.policy_version
        return
    safety = _empty_numeric_safety(policy)
    recommendation["numeric_safety"] = safety
    if current is None or candidate is None or action not in {"INCREASE", "DECREASE"}:
        return

    direction = "increase" if action == "INCREASE" else "decrease"
    limited, limit_percent, capped = _limit_candidate(
        current,
        candidate,
        variable=variable,
        direction=direction,
        policy=policy,
    )
    limit_reason = (
        "max_single_budget_change_percent"
        if variable == "daily_budget"
        else "max_single_target_change_percent"
    )
    safety.update(
        {
            "raw_candidate": candidate,
            "business_bounded_candidate": candidate,
            "change_limited_candidate": limited,
            "current_change_percent": _change_percent(current, limited),
            "applied_change_limit_percent": limit_percent,
            "capped_by_policy": capped,
        }
    )

    if limit_percent == 0:
        zero_cap_reason = (
            "numeric_policy_degraded_to_zero_change_cap"
            if policy.degraded
            else "numeric_policy_zero_change_cap"
        )
        recommendation.update(
            {
                "conservative_value": current,
                "recommended_value": current,
                "aggressive_value": current,
                "recommended_action": "NO_CHANGE",
                "change_percent": 0.0,
                "rollback_value": None,
                "rollback_condition": None,
                "reason": zero_cap_reason,
            }
        )
        safety.update(
            {
                "change_limited_candidate": current,
                "final_recommendation": current,
                "current_change_percent": 0.0,
                "limit_reasons": [
                    (
                        "degraded_policy_zero_change_cap"
                        if policy.degraded
                        else "configured_policy_zero_change_cap"
                    )
                ],
            }
        )
        return

    if math.isclose(limited, current, rel_tol=1e-9, abs_tol=1e-9):
        recommendation.update(
            {
                "conservative_value": current,
                "recommended_value": current,
                "aggressive_value": current,
                "recommended_action": "NO_CHANGE",
                "change_percent": 0.0,
                "rollback_value": None,
                "rollback_condition": None,
                "reason": "numeric_change_cap_below_minimum_safe_increment",
            }
        )
        safety.update(
            {
                "change_limited_candidate": current,
                "final_recommendation": current,
                "current_change_percent": 0.0,
                "limit_reasons": [
                    limit_reason,
                    "minimum_safe_increment_not_reached",
                ],
            }
        )
        return

    if not _candidate_within_business_boundary(
        limited,
        variable=variable,
        target_type=target_type,
        context=context,
    ):
        recommendation.update(
            {
                "conservative_value": None,
                "recommended_value": None,
                "aggressive_value": None,
                "recommended_action": "NO_CHANGE",
                "change_percent": None,
                "evidence_quality": "insufficient",
                "rollback_value": None,
                "rollback_condition": None,
                "reason": "business_boundary_and_change_limit_have_no_safe_intersection",
            }
        )
        safety.update(
            {
                "final_recommendation": None,
                "current_change_percent": None,
                "limit_reasons": [
                    limit_reason,
                    "business_boundary_and_change_limit_have_no_safe_intersection",
                ],
            }
        )
        return

    for field in ("conservative_value", "recommended_value", "aggressive_value"):
        value = _number(recommendation.get(field))
        if value is None or math.isclose(value, current, rel_tol=1e-9, abs_tol=1e-9):
            continue
        value_direction = "increase" if value > current else "decrease"
        value_limited, _, _ = _limit_candidate(
            current,
            value,
            variable=variable,
            direction=value_direction,
            policy=policy,
        )
        recommendation[field] = value_limited
    recommendation["recommended_value"] = limited
    recommendation["change_percent"] = _change_percent(current, limited)
    safety["final_recommendation"] = limited
    if capped:
        review_gate = _review_gate(case, context)
        safety.update(
            {
                "staged_adjustment_required": True,
                "operation_classification": STAGED_OPTIMIZATION,
                "limit_reasons": [limit_reason],
                "staged_plan": _build_staged_plan(
                    current=current,
                    first_stage=limited,
                    final_candidate=candidate,
                    variable=variable,
                    direction=direction,
                    policy=policy,
                    review_gate=review_gate,
                ),
            }
        )
        recommendation["reason"] = (
            "account_evidence_supports_first_stage_of_bounded_numeric_change"
        )
        recommendation["calculation_basis"] = list(
            dict.fromkeys([*recommendation.get("calculation_basis", []), limit_reason])
        )
        recommendation["calculation_evidence"] = [
            *recommendation.get("calculation_evidence", []),
            {
                "type": "HEURISTIC",
                "fact": limit_reason,
                "value": limit_percent,
                "policy_version": policy.policy_version,
            },
        ]


def _measurement_block(
    case: Mapping[str, Any],
    *,
    value_target: bool,
    signal_policy: LoadedPolicy,
) -> str | None:
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
    value_quality = _mapping(_policy_values(signal_policy).get("value_quality"))
    missing_block_value = _number(value_quality.get("missing_value_blocking_percent"))
    currency_block_value = _number(
        value_quality.get("currency_consistency_blocking_min_percent")
    )
    difference_block_value = _number(value_quality.get("difference_blocking_percent"))
    if (
        missing_block_value is None
        or currency_block_value is None
        or difference_block_value is None
    ):
        raise ContractError("signal policy value blocking thresholds are incomplete")
    missing_block = missing_block_value / 100
    currency_block = currency_block_value / 100
    difference_block = difference_block_value / 100
    if business_goal in {"payment", "value", "retention", "revenue"} and (
        (missing_rate is not None and missing_rate > missing_block)
        or (currency_rate is not None and currency_rate < currency_block)
        or (google_mmp_rate is not None and google_mmp_rate > difference_block)
        or (mmp_backend_rate is not None and mmp_backend_rate > difference_block)
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
        "operational_budget_correction_selected_as_single_variable",
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
    signal_policy: LoadedPolicy,
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
    operational = _mapping(_mapping(case.get("quick_ops")).get("operational"))
    if operational.get("operation_classification") == OPERATIONAL_CORRECTION and str(
        operational.get("affected_variable", "")
    ) in {"daily_budget", "budget"}:
        return _empty_target(
            target_type=target_type,
            current=current,
            reason="operational_budget_correction_selected_as_single_variable",
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
    measurement_reason = _measurement_block(
        case, value_target=value_target, signal_policy=signal_policy
    )
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
    correction_requested, historical, correction_error = _correction_request(
        case, variable="target", target_type=target_type
    )
    if correction_requested:
        if correction_error is not None or historical is None:
            return _empty_target(
                target_type=target_type,
                current=current,
                reason=correction_error or "operational_correction_evidence_incomplete",
                context=context,
                case=case,
            )
        if not _correction_within_business_boundary(
            historical,
            variable="target",
            target_type=target_type,
            context=context,
        ):
            return _empty_target(
                target_type=target_type,
                current=current,
                reason="historical_correction_value_violates_business_boundary",
                context=context,
                case=case,
            )
        return _correction_recommendation(
            current=current,
            historical=historical,
            target_type=target_type,
            context=context,
            case=case,
            budget=False,
        )
    if maturity.get("state") != "MATURE":
        return _empty_target(
            target_type=target_type,
            current=current,
            reason="insufficient_mature_conversion_data",
            action="WAIT",
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
        "operational_target_correction_selected_as_single_variable",
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
    signal_policy: LoadedPolicy,
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
    operational = _mapping(_mapping(case.get("quick_ops")).get("operational"))
    if operational.get("operation_classification") == OPERATIONAL_CORRECTION and str(
        operational.get("affected_variable", "")
    ) in {"target", "bid", "target_cpa", "target_roas"}:
        return _empty_budget(
            current=current,
            reason="operational_target_correction_selected_as_single_variable",
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
    correction_requested, historical, correction_error = _correction_request(
        case, variable="daily_budget"
    )
    if correction_requested:
        if correction_error is not None or historical is None:
            return _empty_budget(
                current=current,
                reason=correction_error or "operational_correction_evidence_incomplete",
                context=context,
                case=case,
            )
        if not _correction_within_business_boundary(
            historical,
            variable="daily_budget",
            target_type=None,
            context=context,
        ):
            return _empty_budget(
                current=current,
                reason="historical_correction_value_violates_business_boundary",
                context=context,
                case=case,
            )
        return _correction_recommendation(
            current=current,
            historical=historical,
            target_type=None,
            context=context,
            case=case,
            budget=True,
        )
    if _mapping(signals.get("maturity")).get("state") != "MATURE":
        return _empty_budget(
            current=current,
            reason="insufficient_mature_conversion_data",
            context=context,
            case=case,
            action="WAIT",
        )
    if current > cap:
        return _hard_budget_cap_correction(
            current=current,
            cap=cap,
            context=context,
            case=case,
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
        measurement_reason = _measurement_block(
            case,
            value_target="roas" in strategy,
            signal_policy=signal_policy,
        )
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
    safety = recommendation.get("numeric_safety")
    if isinstance(safety, dict):
        if changes and not executable:
            current_key = (
                "current_daily_budget" if variable == "budget" else "current_value"
            )
            safety["final_recommendation"] = recommendation.get(current_key)
            safety["limit_reasons"] = list(
                dict.fromkeys([*safety.get("limit_reasons", []), "permission_boundary"])
            )
        elif changes:
            safety["final_recommendation"] = recommendation.get("recommended_value")


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


def _operation_classification(
    case: Mapping[str, Any],
    target: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> str:
    operational = _mapping(_mapping(case.get("quick_ops")).get("operational"))
    simultaneous = operational.get("simultaneous_changes", [])
    emergency_changes = (
        {str(item) for item in simultaneous}
        if isinstance(simultaneous, list)
        else set()
    )
    if operational.get("urgent_confirmed") is True and len(emergency_changes) > 1:
        return EMERGENCY_INTERVENTION
    recommendation_classes = {
        _mapping(section.get("numeric_safety")).get("operation_classification")
        for section in (target, budget)
    }
    if OPERATIONAL_CORRECTION in recommendation_classes:
        return OPERATIONAL_CORRECTION
    if STAGED_OPTIMIZATION in recommendation_classes:
        return STAGED_OPTIMIZATION
    return NORMAL_OPTIMIZATION


def _validate_operation_input(case: Mapping[str, Any]) -> None:
    operational = _mapping(_mapping(case.get("quick_ops")).get("operational"))
    requested = operational.get("operation_classification")
    if requested is not None and requested not in _OPERATION_CLASSIFICATIONS:
        allowed = ", ".join(sorted(_OPERATION_CLASSIFICATIONS))
        raise ContractError(
            f"quick_ops.operational.operation_classification must be one of {allowed}"
        )
    if requested == OPERATIONAL_CORRECTION and str(
        operational.get("affected_variable", "")
    ) not in {"target", "bid", "target_cpa", "target_roas", "daily_budget", "budget"}:
        raise ContractError(
            "OPERATIONAL_CORRECTION requires affected_variable target or daily_budget"
        )


def recommend_numeric(
    case: Mapping[str, Any],
    signals: Mapping[str, Any] | None = None,
    *,
    numeric_policy: LoadedPolicy | None = None,
    signal_policy: LoadedPolicy | None = None,
) -> dict[str, Any]:
    """Return bounded target, budget, and split recommendations from facts."""

    if not isinstance(case, Mapping):
        raise ContractError("UAC input must be an object")
    _validate_operation_input(case)
    loaded_numeric_policy = numeric_policy or load_policy("numeric")
    loaded_signal_policy = signal_policy or load_policy("signal")
    derived = (
        dict(signals)
        if signals is not None
        else derive_signals(case, policy=loaded_signal_policy)
    )
    context = _numeric_context(case, loaded_signal_policy)
    target = _target_recommendation(case, derived, context, loaded_signal_policy)
    budget = _budget_recommendation(
        case, derived, context, target, loaded_signal_policy
    )
    _apply_numeric_safety(
        target,
        variable=(
            "target_roas" if target.get("target_type") == "tROAS" else "target_cpa"
        ),
        current_field="current_value",
        target_type=str(target.get("target_type")),
        context=context,
        case=case,
        policy=loaded_numeric_policy,
    )
    _apply_numeric_safety(
        budget,
        variable="daily_budget",
        current_field="current_daily_budget",
        target_type=None,
        context=context,
        case=case,
        policy=loaded_numeric_policy,
    )
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
        "incomplete",
        "no_safe_intersection",
        "violates_business_boundary",
        "degraded",
        "mismatch",
    )
    data_gaps = [
        str(reason)
        for reason in (target.get("reason"), budget.get("reason"))
        if isinstance(reason, str)
        and any(marker in reason for marker in missing_markers)
    ]
    split = dict(_mapping(derived.get("split_feasibility")))
    operation_classification = _operation_classification(case, target, budget)
    emergency = operation_classification == EMERGENCY_INTERVENTION
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
        "policy": {
            "numeric": loaded_numeric_policy.as_record(),
            "signal": loaded_signal_policy.as_record(),
        },
        "legacy_hints_ignored": ignored_hints,
        "data_gaps": list(dict.fromkeys(data_gaps)),
        "classification": {
            "type": "OPERATIONAL_DECISION",
            "operation_classification": operation_classification,
            "experiment_validity": (
                "NOT_A_VALID_EXPERIMENT" if emergency else "NOT_AN_EXPERIMENT"
            ),
            "attribution": (
                "ATTRIBUTION_WILL_BE_CONFOUNDED" if emergency else "NOT_APPLICABLE"
            ),
        },
        "account_write": False,
        "ledger_write": False,
    }


__all__ = ["NUMERIC_DECISION_SCHEMA_VERSION", "recommend_numeric"]
