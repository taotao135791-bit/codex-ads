"""Deterministic signal derivation for UAC Quick Decisions.

The functions in this module only transform supplied account facts. They do
not read an advertising account, write files, or treat platform guidance as a
substitute for account evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date
import math
from statistics import fmean, pstdev
from typing import Any

from .policy_loader import LoadedPolicy, load_policy
from .types import ContractError


SIGNAL_DERIVATION_SCHEMA_VERSION = "1.0"

_NEW_NUMERIC_FIELDS = {
    "mature_actual_cpa",
    "mature_actual_roas",
    "mature_conversions",
    "mature_revenue",
    "google_value",
    "mmp_value",
    "backend_value",
}
_VALUE_RATE_FIELDS = (
    "value_missing_rate",
    "currency_consistency_rate",
    "google_mmp_value_difference_rate",
    "mmp_backend_value_difference_rate",
    "refund_rate",
)


def _signal_policy_values(policy: LoadedPolicy) -> Mapping[str, Any]:
    values = policy.values
    if not isinstance(values, Mapping):
        raise ContractError("loaded signal policy must be an object")
    return values


def _policy_number(values: Mapping[str, Any], section: str, field: str) -> float | None:
    return _number(_mapping(values.get(section)).get(field))


def _policy_ratio(values: Mapping[str, Any], section: str, field: str) -> float:
    number = _policy_number(values, section, field)
    if number is None or number < 0 or number > 100:
        raise ContractError(
            f"signal policy {section}.{field} must be between 0 and 100"
        )
    return number / 100


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _number(value: Any) -> float | None:
    return float(value) if _finite_number(value) else None


def _non_negative(value: Any, path: str) -> float | None:
    if value is None:
        return None
    number = _number(value)
    if number is None or number < 0:
        raise ContractError(f"{path} must be a finite non-negative number")
    return number


def _rate(value: Any, path: str) -> float | None:
    number = _non_negative(value, path)
    if number is not None and number > 1:
        raise ContractError(f"{path} must be between 0 and 1")
    return number


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    result = numerator / denominator
    return result if math.isfinite(result) else None


def _round_metric(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _date_window_days(scope: Mapping[str, Any]) -> int | None:
    start = scope.get("start_date")
    end = scope.get("end_date")
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        return None


def _days_since_last_change(
    maturity: Mapping[str, Any], scope: Mapping[str, Any]
) -> float | None:
    supplied = _non_negative(
        maturity.get("days_since_last_change"),
        "maturity.days_since_last_change",
    )
    if supplied is not None:
        return supplied
    changed_at = maturity.get("last_change_at")
    end = scope.get("end_date")
    if not isinstance(changed_at, str) or not isinstance(end, str):
        return None
    try:
        return float((date.fromisoformat(end) - date.fromisoformat(changed_at)).days)
    except ValueError:
        return None


def _numeric_series(
    rows: Any,
    field: str,
    *,
    path: str,
) -> list[float]:
    if rows is None:
        return []
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ContractError(f"{path} must be an array")
    values: list[float] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ContractError(f"{path}[{index}] must be an object")
        if field not in row or row[field] is None:
            continue
        value = _non_negative(row[field], f"{path}[{index}].{field}")
        assert value is not None
        values.append(value)
    return values


def _difference_rate(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    denominator = max(abs(left), abs(right))
    if denominator == 0:
        return 0.0
    return abs(left - right) / denominator


def _has_new_numeric_evidence(case: Mapping[str, Any]) -> bool:
    facts = _mapping(case.get("facts"))
    metrics = _mapping(facts.get("metrics"))
    goal = _mapping(case.get("goal"))
    maturity = _mapping(case.get("maturity"))
    measurement = _mapping(case.get("measurement"))
    return bool(
        _NEW_NUMERIC_FIELDS.intersection(metrics)
        or any(
            key in facts
            for key in (
                "daily_series",
                "event_candidates",
                "creative_cohorts",
                "split_plan",
                "minimum_daily_mature_events",
                "budget_limited",
            )
        )
        or any(
            key in goal
            for key in (
                "maximum_acceptable_cpa",
                "minimum_acceptable_roas",
                "daily_budget_cap",
                "target_roas",
                "optimization_priority",
            )
        )
        or any(
            key in maturity
            for key in (
                "last_change_at",
                "days_since_last_change",
                "last_change_variables",
                "mature_events_since_change",
                "previous_target",
                "previous_daily_budget",
            )
        )
        or any(key in measurement for key in _VALUE_RATE_FIELDS)
    )


def _numeric_context(
    case: Mapping[str, Any], policy: LoadedPolicy | None = None
) -> dict[str, Any]:
    loaded_policy = policy or load_policy("signal")
    policy_values = _signal_policy_values(loaded_policy)
    maturity_defaults = _mapping(policy_values.get("maturity_defaults"))
    facts = _mapping(case.get("facts"))
    metrics = _mapping(facts.get("metrics"))
    goal = _mapping(case.get("goal"))
    maturity = _mapping(case.get("maturity"))
    scope = _mapping(case.get("scope"))
    quick = _mapping(case.get("quick_ops"))
    legacy = _mapping(quick.get("bid_budget"))
    daily_rows = facts.get("daily_series")
    spend_series = _numeric_series(daily_rows, "spend", path="facts.daily_series")
    event_series = _numeric_series(
        daily_rows, "mature_events", path="facts.daily_series"
    )
    value_series = _numeric_series(daily_rows, "value", path="facts.daily_series")
    observation_days = len(daily_rows) if isinstance(daily_rows, list) else None
    if isinstance(daily_rows, list) and daily_rows:
        supplied_dates = [
            row.get("date")
            for row in daily_rows
            if isinstance(row, Mapping) and isinstance(row.get("date"), str)
        ]
        if len(supplied_dates) == len(daily_rows):
            observation_days = len(set(supplied_dates))
    if not observation_days:
        observation_days = int(
            _non_negative(maturity.get("days_elapsed"), "maturity.days_elapsed")
            or _date_window_days(scope)
            or 0
        )
    total_spend = _non_negative(metrics.get("spend"), "facts.metrics.spend")
    if spend_series:
        total_spend = sum(spend_series)
    current_budget = _non_negative(
        facts.get("daily_budget", legacy.get("current_daily_budget")),
        "facts.daily_budget",
    )
    average_spend = (
        fmean(spend_series)
        if spend_series
        else _safe_ratio(total_spend, float(observation_days))
    )
    target_cpa = _non_negative(
        goal.get("target_cpa", legacy.get("current_target")),
        "goal.target_cpa",
    )
    target_roas = _non_negative(goal.get("target_roas"), "goal.target_roas")
    mature_conversions = _non_negative(
        metrics.get("mature_conversions", maturity.get("conversions_observed")),
        "facts.metrics.mature_conversions",
    )
    mature_revenue = _non_negative(
        metrics.get("mature_revenue", metrics.get("revenue")),
        "facts.metrics.mature_revenue",
    )
    actual_cpa = _non_negative(
        metrics.get("mature_actual_cpa"), "facts.metrics.mature_actual_cpa"
    )
    if actual_cpa is None:
        actual_cpa = _safe_ratio(total_spend, mature_conversions)
    actual_roas = _non_negative(
        metrics.get("mature_actual_roas"), "facts.metrics.mature_actual_roas"
    )
    if actual_roas is None:
        actual_roas = _safe_ratio(mature_revenue, total_spend)
    return {
        "has_numeric_evidence": _has_new_numeric_evidence(case),
        "observation_days": observation_days or None,
        "spend_series": spend_series,
        "event_series": event_series,
        "value_series": value_series,
        "total_spend": total_spend,
        "average_daily_spend": average_spend,
        "current_daily_budget": current_budget,
        "delivery_rate": _safe_ratio(average_spend, current_budget),
        "target_cpa": target_cpa,
        "target_roas": target_roas,
        "mature_actual_cpa": actual_cpa,
        "mature_actual_roas": actual_roas,
        "mature_conversions": mature_conversions,
        "mature_revenue": mature_revenue,
        "maximum_acceptable_cpa": _non_negative(
            goal.get("maximum_acceptable_cpa"),
            "goal.maximum_acceptable_cpa",
        ),
        "minimum_acceptable_roas": _non_negative(
            goal.get("minimum_acceptable_roas"),
            "goal.minimum_acceptable_roas",
        ),
        "daily_budget_cap": _non_negative(
            goal.get("daily_budget_cap"), "goal.daily_budget_cap"
        ),
        "optimization_priority": goal.get("optimization_priority", "balanced"),
        "days_since_last_change": _days_since_last_change(maturity, scope),
        "mature_events_since_change": _non_negative(
            maturity.get("mature_events_since_change"),
            "maturity.mature_events_since_change",
        ),
        "last_change_variables": maturity.get("last_change_variables", []),
        "minimum_days": _non_negative(
            maturity.get("minimum_days", maturity_defaults.get("minimum_days")),
            "maturity.minimum_days",
        ),
        "minimum_conversions": _non_negative(
            maturity.get(
                "minimum_conversions",
                maturity_defaults.get("minimum_mature_events"),
            ),
            "maturity.minimum_conversions",
        ),
        "delay_elapsed": _non_negative(
            maturity.get("conversion_delay_elapsed_days"),
            "maturity.conversion_delay_elapsed_days",
        ),
        "delay_days": _non_negative(
            maturity.get("conversion_delay_days"),
            "maturity.conversion_delay_days",
        ),
    }


def _derive_maturity(context: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "observation_days": context.get("observation_days"),
        "minimum_days": context.get("minimum_days"),
        "mature_conversions": context.get("mature_conversions"),
        "minimum_conversions": context.get("minimum_conversions"),
        "delay_elapsed": context.get("delay_elapsed"),
        "delay_days": context.get("delay_days"),
        "days_since_last_change": context.get("days_since_last_change"),
        "mature_events_since_change": context.get("mature_events_since_change"),
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        state = "INSUFFICIENT_EVIDENCE"
        reasons = ["missing maturity facts: " + ", ".join(missing)]
    else:
        observation_days = _number(required["observation_days"])
        minimum_days = _number(required["minimum_days"])
        mature_conversions = _number(required["mature_conversions"])
        minimum_conversions = _number(required["minimum_conversions"])
        delay_elapsed = _number(required["delay_elapsed"])
        delay_days = _number(required["delay_days"])
        assert observation_days is not None
        assert minimum_days is not None
        assert mature_conversions is not None
        assert minimum_conversions is not None
        assert delay_elapsed is not None
        assert delay_days is not None
        hard_failures: list[str] = []
        partial_failures: list[str] = []
        if observation_days < minimum_days:
            hard_failures.append("minimum_observation_days_not_reached")
        if delay_elapsed < delay_days:
            hard_failures.append("conversion_delay_not_mature")
        if mature_conversions < minimum_conversions:
            partial_failures.append("minimum_mature_events_not_reached")
        days_since_change = context.get("days_since_last_change")
        events_since_change = context.get("mature_events_since_change")
        if days_since_change is not None and days_since_change < minimum_days:
            hard_failures.append("recent_change_cooldown_not_reached")
        if (
            events_since_change is not None
            and events_since_change < minimum_conversions
        ):
            partial_failures.append("post_change_mature_events_not_reached")
        changes = context.get("last_change_variables", [])
        change_window_open = (
            days_since_change is None
            or events_since_change is None
            or days_since_change < minimum_days
            or events_since_change < minimum_conversions
        )
        if (
            isinstance(changes, list)
            and len(set(str(item) for item in changes)) > 1
            and change_window_open
        ):
            hard_failures.append("recent_multi_variable_change")
        if hard_failures:
            state = "NOT_MATURE"
            reasons = hard_failures + partial_failures
        elif partial_failures:
            state = "PARTIALLY_MATURE"
            reasons = partial_failures
        else:
            state = "MATURE"
            reasons = ["time_volume_delay_and_change_window_are_mature"]
    return {
        "state": state,
        "observation_days": context.get("observation_days"),
        "mature_events": context.get("mature_conversions"),
        "days_since_last_change": context.get("days_since_last_change"),
        "mature_events_since_change": context.get("mature_events_since_change"),
        "reasons": reasons,
    }


def _derive_budget_delivery(
    case: Mapping[str, Any], context: Mapping[str, Any]
) -> dict[str, Any]:
    facts = _mapping(case.get("facts"))
    days = context.get("observation_days")
    delivery_rate = context.get("delivery_rate")
    if days is None or days < 2 or delivery_rate is None:
        state = "UNKNOWN"
        reasons = ["multi_day_budget_and_spend_evidence_required"]
    elif facts.get("budget_limited") is True and delivery_rate >= 0.9:
        state = "BUDGET_CONSTRAINED"
        reasons = ["multi_day_delivery_is_high_and_account_is_budget_limited"]
    elif delivery_rate < 0.75:
        state = "UNDER_DELIVERING"
        reasons = ["multi_day_delivery_below_declared_budget"]
    elif delivery_rate >= 0.9:
        state = "NEAR_FULL_DELIVERY"
        reasons = ["multi_day_delivery_near_declared_budget"]
    else:
        state = "NOT_BUDGET_CONSTRAINED"
        reasons = ["multi_day_delivery_does_not_show_a_budget_constraint"]
    return {
        "state": state,
        "observation_days": days,
        "average_daily_spend": _round_metric(context.get("average_daily_spend"), 2),
        "current_daily_budget": context.get("current_daily_budget"),
        "delivery_rate": _round_metric(delivery_rate),
        "platform_budget_limited": facts.get("budget_limited"),
        "reasons": reasons,
    }


def _derive_event_volume(
    case: Mapping[str, Any],
    context: Mapping[str, Any],
    policy_values: Mapping[str, Any],
) -> dict[str, Any]:
    facts = _mapping(case.get("facts"))
    values = list(context.get("event_series", []))
    minimum = _non_negative(
        facts.get("minimum_daily_mature_events"),
        "facts.minimum_daily_mature_events",
    )
    if minimum is None:
        minimum = _safe_ratio(
            context.get("minimum_conversions"), context.get("minimum_days")
        )
    minimum_points = _policy_number(
        policy_values, "event_stability", "minimum_daily_points"
    )
    coefficient_max = _policy_number(
        policy_values, "event_stability", "coefficient_of_variation_max"
    )
    zero_days_max = _policy_ratio(
        policy_values, "event_stability", "zero_event_days_max_percent"
    )
    if minimum_points is None or coefficient_max is None:
        raise ContractError("signal policy event_stability is incomplete")
    if len(values) < int(minimum_points) or minimum is None:
        return {
            "state": "UNKNOWN",
            "days": len(values),
            "total_events": _round_metric(sum(values), 2) if values else None,
            "mean_daily_events": None,
            "minimum_daily_events": minimum,
            "zero_event_days": None,
            "coefficient_of_variation": None,
            "reasons": ["declared_daily_event_points_and_a_minimum_are_required"],
        }
    mean = fmean(values)
    deviation = pstdev(values)
    cv = deviation / mean if mean > 0 else None
    zero_days = sum(value == 0 for value in values)
    if mean < minimum:
        state = "INSUFFICIENT"
        reasons = ["mean_daily_mature_events_below_declared_minimum"]
    elif cv is not None and (
        cv > coefficient_max or zero_days / len(values) > zero_days_max
    ):
        state = "SUFFICIENT_BUT_VOLATILE"
        reasons = ["event_volume_meets_minimum_but_is_volatile"]
    else:
        state = "SUFFICIENT_AND_STABLE"
        reasons = ["event_volume_meets_minimum_and_is_stable"]
    return {
        "state": state,
        "days": len(values),
        "total_events": _round_metric(sum(values), 2),
        "mean_daily_events": _round_metric(mean),
        "minimum_daily_events": _round_metric(minimum),
        "minimum": _round_metric(min(values), 2),
        "maximum": _round_metric(max(values), 2),
        "zero_event_days": zero_days,
        "coefficient_of_variation": _round_metric(cv),
        "reasons": reasons,
    }


def _derive_target_constraint(
    case: Mapping[str, Any],
    context: Mapping[str, Any],
    maturity: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    strategy = str(_mapping(case.get("goal")).get("bidding_strategy", "")).lower()
    if maturity.get("state") != "MATURE":
        return {"state": "UNKNOWN", "reasons": ["mature_performance_required"]}
    if budget.get("state") == "BUDGET_CONSTRAINED":
        return {
            "state": "TARGET_NOT_PRIMARY_CONSTRAINT",
            "reasons": ["budget_is_the_primary_evidenced_constraint"],
        }
    delivery = _number(context.get("delivery_rate"))
    if "roas" in strategy:
        current = _number(context.get("target_roas"))
        actual = _number(context.get("mature_actual_roas"))
        floor = _number(context.get("minimum_acceptable_roas"))
        if current is None or actual is None or floor is None or delivery is None:
            return {"state": "UNKNOWN", "reasons": ["troas_constraint_facts_missing"]}
        if delivery < 0.75 and actual >= floor and current >= actual * 0.9:
            state = "TARGET_LIKELY_TOO_TIGHT"
            reasons = ["under_delivery_with_mature_roas_above_business_floor"]
        elif actual < floor and current < floor:
            state = "TARGET_LIKELY_TOO_LOOSE"
            reasons = ["mature_roas_and_target_below_business_floor"]
        else:
            state = "TARGET_NOT_PRIMARY_CONSTRAINT"
            reasons = ["target_is_not_the_primary_evidenced_constraint"]
    else:
        current = _number(context.get("target_cpa"))
        actual = _number(context.get("mature_actual_cpa"))
        ceiling = _number(context.get("maximum_acceptable_cpa"))
        if current is None or actual is None or ceiling is None or delivery is None:
            return {"state": "UNKNOWN", "reasons": ["tcpa_constraint_facts_missing"]}
        relative_actual = _safe_ratio(actual, current)
        if (
            delivery < 0.75
            and actual <= ceiling
            and relative_actual is not None
            and relative_actual >= 0.8
        ):
            state = "TARGET_LIKELY_TOO_TIGHT"
            reasons = ["under_delivery_with_mature_cpa_inside_business_ceiling"]
        elif actual > ceiling and current > ceiling:
            state = "TARGET_LIKELY_TOO_LOOSE"
            reasons = ["mature_cpa_and_target_above_business_ceiling"]
        else:
            state = "TARGET_NOT_PRIMARY_CONSTRAINT"
            reasons = ["target_is_not_the_primary_evidenced_constraint"]
    return {"state": state, "reasons": reasons}


def _derive_value_signal(
    case: Mapping[str, Any],
    context: Mapping[str, Any],
    maturity: Mapping[str, Any],
    event_volume: Mapping[str, Any],
    policy_values: Mapping[str, Any],
) -> dict[str, Any]:
    measurement = _mapping(case.get("measurement"))
    goal = _mapping(case.get("goal"))
    metrics = _mapping(_mapping(case.get("facts")).get("metrics"))
    missing_rate = _rate(
        measurement.get("value_missing_rate"), "measurement.value_missing_rate"
    )
    currency_rate = _rate(
        measurement.get("currency_consistency_rate"),
        "measurement.currency_consistency_rate",
    )
    google_value = _non_negative(
        metrics.get("google_value"), "facts.metrics.google_value"
    )
    mmp_value = _non_negative(metrics.get("mmp_value"), "facts.metrics.mmp_value")
    backend_value = _non_negative(
        metrics.get("backend_value"), "facts.metrics.backend_value"
    )
    google_mmp = _rate(
        measurement.get("google_mmp_value_difference_rate"),
        "measurement.google_mmp_value_difference_rate",
    )
    if google_mmp is None:
        google_mmp = _difference_rate(google_value, mmp_value)
    mmp_backend = _rate(
        measurement.get("mmp_backend_value_difference_rate"),
        "measurement.mmp_backend_value_difference_rate",
    )
    if mmp_backend is None:
        mmp_backend = _difference_rate(mmp_value, backend_value)
    refund_rate = _rate(measurement.get("refund_rate"), "measurement.refund_rate")
    maximum_refund_rate = _rate(
        goal.get("maximum_acceptable_refund_rate"),
        "goal.maximum_acceptable_refund_rate",
    )
    value_series = list(context.get("value_series", []))
    value_mean = fmean(value_series) if value_series else None
    value_cv = (
        pstdev(value_series) / value_mean
        if value_series and value_mean is not None and value_mean > 0
        else None
    )
    business_goal = str(goal.get("business_goal", "")).lower()
    subscription_required = business_goal in {
        "subscription",
        "subscriptions",
        "retention",
    }
    renewal_included = measurement.get("subscription_renewal_included")
    supplied = [missing_rate, currency_rate, google_mmp, mmp_backend, refund_rate]
    missing_warning = _policy_ratio(
        policy_values, "value_quality", "missing_value_warning_percent"
    )
    missing_blocking = _policy_ratio(
        policy_values, "value_quality", "missing_value_blocking_percent"
    )
    difference_warning = _policy_ratio(
        policy_values, "value_quality", "difference_warning_percent"
    )
    difference_blocking = _policy_ratio(
        policy_values, "value_quality", "difference_blocking_percent"
    )
    currency_warning = _policy_ratio(
        policy_values,
        "value_quality",
        "currency_consistency_warning_min_percent",
    )
    currency_blocking = _policy_ratio(
        policy_values,
        "value_quality",
        "currency_consistency_blocking_min_percent",
    )
    value_cv_warning = _policy_number(
        policy_values,
        "value_quality",
        "value_coefficient_of_variation_warning",
    )
    if value_cv_warning is None:
        raise ContractError(
            "signal policy value_quality.value_coefficient_of_variation_warning is required"
        )
    existing_bad = bool(
        measurement.get("value_currency_valid") is False
        or measurement.get("google_ads_vs_mmp") == "material_mismatch"
        or measurement.get("mmp_vs_backend") == "material_mismatch"
        or measurement.get("duplicate_events") is True
        or measurement.get("payment_trial_refund_distinguished") is False
        or (subscription_required and renewal_included is False)
        or (
            refund_rate is not None
            and maximum_refund_rate is not None
            and refund_rate > maximum_refund_rate
        )
    )
    if (
        existing_bad
        or (missing_rate is not None and missing_rate > missing_blocking)
        or (currency_rate is not None and currency_rate < currency_blocking)
        or (google_mmp is not None and google_mmp > difference_blocking)
        or (mmp_backend is not None and mmp_backend > difference_blocking)
    ):
        state = "VALUE_SIGNAL_UNRELIABLE"
        reasons = ["value_currency_or_reconciliation_failed"]
    elif (
        any(value is None for value in supplied)
        or context.get("mature_revenue") is None
        or (subscription_required and renewal_included is None)
        or maturity.get("state") != "MATURE"
        or event_volume.get("state") in {"UNKNOWN", "INSUFFICIENT"}
    ):
        state = "INSUFFICIENT_EVIDENCE"
        reasons = ["value_quality_or_mature_revenue_facts_missing"]
    elif (
        missing_rate is not None
        and currency_rate is not None
        and google_mmp is not None
        and mmp_backend is not None
        and (
            missing_rate > missing_warning
            or currency_rate < currency_warning
            or google_mmp > difference_warning
            or mmp_backend > difference_warning
            or (value_cv is not None and value_cv > value_cv_warning)
            or event_volume.get("state") == "SUFFICIENT_BUT_VOLATILE"
        )
    ):
        state = "VALUE_SIGNAL_BORDERLINE"
        reasons = ["value_signal_is_present_but_borderline"]
    else:
        state = "VALUE_SIGNAL_READY"
        reasons = ["mature_value_currency_and_reconciliation_are_reliable"]
    return {
        "state": state,
        "value_missing_rate": _round_metric(missing_rate),
        "currency_consistency_rate": _round_metric(currency_rate),
        "google_mmp_difference_rate": _round_metric(google_mmp),
        "mmp_backend_difference_rate": _round_metric(mmp_backend),
        "refund_rate": _round_metric(refund_rate),
        "maximum_acceptable_refund_rate": _round_metric(maximum_refund_rate),
        "value_coefficient_of_variation": _round_metric(value_cv),
        "mature_revenue": context.get("mature_revenue"),
        "average_mature_value": _round_metric(
            _safe_ratio(
                _number(context.get("mature_revenue")),
                _number(context.get("mature_conversions")),
            )
        ),
        "mature_roas": _round_metric(context.get("mature_actual_roas")),
        "subscription_renewal_included": renewal_included,
        "reasons": reasons,
    }


def _score_label(value: float) -> str:
    if value >= 0.67:
        return "high"
    if value >= 0.34:
        return "medium"
    return "low"


def _rank_event_candidates(
    case: Mapping[str, Any], policy_values: Mapping[str, Any]
) -> list[dict[str, Any]]:
    candidates = _mapping(case.get("facts")).get("event_candidates", [])
    if candidates is None:
        return []
    if not isinstance(candidates, list):
        raise ContractError("facts.event_candidates must be an array")
    prepared: list[dict[str, Any]] = []
    minimum_points = _policy_number(
        policy_values, "event_stability", "minimum_daily_points"
    )
    coefficient_max = _policy_number(
        policy_values, "event_stability", "coefficient_of_variation_max"
    )
    zero_days_max = _policy_ratio(
        policy_values, "event_stability", "zero_event_days_max_percent"
    )
    if minimum_points is None or coefficient_max is None:
        raise ContractError("signal policy event_stability is incomplete")
    weights = _mapping(policy_values.get("proxy_event_scoring_weights"))
    scoring_weights = {
        name: (_number(weights.get(name)) or 0.0) / 100
        for name in (
            "volume_percent",
            "payment_relationship_percent",
            "delay_percent",
            "reliability_percent",
            "stability_percent",
            "funnel_depth_percent",
        )
    }
    max_events = 0.0
    max_relationship = 0.0
    delays: list[float] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            raise ContractError(f"facts.event_candidates[{index}] must be an object")
        event = candidate.get("event")
        if not isinstance(event, str) or not event.strip():
            raise ContractError(f"facts.event_candidates[{index}].event is required")
        events = _non_negative(
            candidate.get("mature_events"),
            f"facts.event_candidates[{index}].mature_events",
        )
        payments = _non_negative(
            candidate.get("mature_payments"),
            f"facts.event_candidates[{index}].mature_payments",
        )
        delay = _non_negative(
            candidate.get("median_payment_delay_days"),
            f"facts.event_candidates[{index}].median_payment_delay_days",
        )
        relationship = _safe_ratio(payments, events)
        daily_raw = candidate.get("daily_mature_events")
        daily_values: list[float] = []
        if daily_raw is not None:
            if not isinstance(daily_raw, Sequence) or isinstance(
                daily_raw, (str, bytes)
            ):
                raise ContractError(
                    f"facts.event_candidates[{index}].daily_mature_events must be an array"
                )
            for daily_index, daily_value in enumerate(daily_raw):
                normalized_daily = _non_negative(
                    daily_value,
                    f"facts.event_candidates[{index}].daily_mature_events[{daily_index}]",
                )
                assert normalized_daily is not None
                daily_values.append(normalized_daily)
        daily_mean = fmean(daily_values) if daily_values else None
        stability = (
            1.0
            if len(daily_values) >= int(minimum_points)
            and daily_mean is not None
            and daily_mean > 0
            and pstdev(daily_values) / daily_mean <= coefficient_max
            and sum(value == 0 for value in daily_values) / len(daily_values)
            <= zero_days_max
            else 0.5
            if not daily_values
            else 0.0
        )
        funnel_depth = _rate(
            candidate.get("funnel_depth"),
            f"facts.event_candidates[{index}].funnel_depth",
        )
        too_shallow = candidate.get("too_shallow")
        if too_shallow is not None and not isinstance(too_shallow, bool):
            raise ContractError(
                f"facts.event_candidates[{index}].too_shallow must be boolean"
            )
        max_events = max(max_events, events or 0.0)
        max_relationship = max(max_relationship, relationship or 0.0)
        if delay is not None:
            delays.append(delay)
        prepared.append(
            {
                "event": event,
                "mature_events": events,
                "payment_conversion_rate": relationship,
                "median_payment_delay_days": delay,
                "reliable": candidate.get("reliable"),
                "stability": stability,
                "funnel_depth": funnel_depth,
                "too_shallow": too_shallow is True,
            }
        )
    max_delay = max(delays, default=0.0)
    minimum_sample = _number(_mapping(case.get("maturity")).get("minimum_conversions"))
    for item in prepared:
        volume_score = _safe_ratio(item["mature_events"], max_events) or 0.0
        relationship_score = (
            _safe_ratio(item["payment_conversion_rate"], max_relationship) or 0.0
        )
        delay = item["median_payment_delay_days"]
        delay_score = 0.0 if delay is None else 1 - _safe_ratio(delay, max_delay + 1)  # type: ignore[operator]
        reliability_score = 1.0 if item["reliable"] is True else 0.0
        stability_score = float(item["stability"])
        depth_score = (
            float(item["funnel_depth"]) if item["funnel_depth"] is not None else 0.5
        )
        total = (
            volume_score * scoring_weights["volume_percent"]
            + relationship_score * scoring_weights["payment_relationship_percent"]
            + delay_score * scoring_weights["delay_percent"]
            + reliability_score * scoring_weights["reliability_percent"]
            + stability_score * scoring_weights["stability_percent"]
            + depth_score * scoring_weights["funnel_depth_percent"]
        )
        sample_ready = bool(
            item["mature_events"] is not None
            and (minimum_sample is None or item["mature_events"] >= minimum_sample)
        )
        if not sample_ready:
            total *= 0.25
        if item["reliable"] is not True or item["too_shallow"] is True:
            total *= 0.25
        item.update(
            {
                "volume_score": _score_label(volume_score),
                "payment_relationship_score": _score_label(relationship_score),
                "delay_score": _score_label(delay_score),
                "reliability_score": "high" if reliability_score else "low",
                "stability_score": _score_label(stability_score),
                "funnel_depth_score": _score_label(depth_score),
                "score": round(total, 4),
                "sample_ready": sample_ready,
            }
        )
    prepared.sort(key=lambda item: (-item["score"], item["event"]))
    best_ready_assigned = False
    for item in prepared:
        if (
            item["reliable"] is not True
            or item["mature_events"] in {None, 0}
            or item["sample_ready"] is not True
            or item["too_shallow"] is True
        ):
            recommendation = "not_ready"
        elif not best_ready_assigned:
            recommendation = "current_best_proxy"
            best_ready_assigned = True
        else:
            recommendation = "next_candidate"
        item["recommendation"] = recommendation
        item.pop("reliable", None)
        item.pop("stability", None)
        item.pop("funnel_depth", None)
        item.pop("too_shallow", None)
    return prepared


def _creative_quality(
    case: Mapping[str, Any], policy_values: Mapping[str, Any]
) -> list[dict[str, Any]]:
    facts = _mapping(case.get("facts"))
    cohorts = facts.get("creative_cohorts", [])
    if cohorts is None:
        return []
    if not isinstance(cohorts, list):
        raise ContractError("facts.creative_cohorts must be an array")
    minimum_installs = _non_negative(
        facts.get(
            "minimum_creative_installs",
            _mapping(policy_values.get("creative_sample")).get(
                "default_minimum_installs"
            ),
        ),
        "facts.minimum_creative_installs",
    )
    rows: list[dict[str, Any]] = []
    for index, cohort in enumerate(cohorts):
        if not isinstance(cohort, Mapping):
            raise ContractError(f"facts.creative_cohorts[{index}] must be an object")
        creative = cohort.get("creative")
        if not isinstance(creative, str) or not creative.strip():
            raise ContractError(f"facts.creative_cohorts[{index}].creative is required")
        values = {
            name: _non_negative(
                cohort.get(name), f"facts.creative_cohorts[{index}].{name}"
            )
            for name in (
                "spend",
                "installs",
                "registrations",
                "deep_events",
                "payments",
                "value",
            )
        }
        installs = values["installs"]
        sample_ready = bool(
            cohort.get("mature") is True
            and installs is not None
            and (minimum_installs is None or installs >= minimum_installs)
        )
        row: dict[str, Any] = {
            "creative": creative,
            "mature": cohort.get("mature") is True,
            "sample_size": installs,
            "minimum_sample_size": minimum_installs,
            "sample_ready": sample_ready,
            "cpi": _safe_ratio(values["spend"], installs),
            "registration_rate": _safe_ratio(values["registrations"], installs),
            "deep_event_rate": _safe_ratio(values["deep_events"], installs),
            "payment_rate": _safe_ratio(values["payments"], installs),
            "payment_cpa": _safe_ratio(values["spend"], values["payments"]),
            "value_per_install": _safe_ratio(values["value"], installs),
            "prior_deep_event_rate": _rate(
                cohort.get("prior_deep_event_rate"),
                f"facts.creative_cohorts[{index}].prior_deep_event_rate",
            ),
        }
        rows.append(row)
    mature = [row for row in rows if row["sample_ready"] and row["cpi"] is not None]
    cpis = [row["cpi"] for row in mature if row["cpi"] is not None]
    payments = [
        row["payment_rate"] for row in mature if row["payment_rate"] is not None
    ]
    value_scores = [
        row["value_per_install"]
        for row in mature
        if row["value_per_install"] is not None
    ]
    for row in rows:
        current_deep = _number(row["deep_event_rate"])
        prior_deep = _number(row.pop("prior_deep_event_rate"))
        if not row["sample_ready"] or row["cpi"] is None:
            classification = "INSUFFICIENT_DATA"
        elif (
            prior_deep is not None
            and current_deep is not None
            and prior_deep > 0
            and current_deep < prior_deep * 0.8
        ):
            classification = "FATIGUING"
        elif (
            cpis
            and payments
            and row["cpi"] == min(cpis)
            and row["payment_rate"] == min(payments)
            and len(rows) > 1
        ):
            classification = "CHEAP_LOW_QUALITY"
        elif (
            value_scores
            and row["value_per_install"] == max(value_scores)
            and cpis
            and row["cpi"] > min(cpis)
        ):
            classification = "EXPENSIVE_HIGH_VALUE"
        elif payments and row["payment_rate"] == max(payments):
            classification = "STRONG_DEEP_CONVERSION"
        else:
            classification = "STABLE"
        row["classification"] = classification
        for name, value in list(row.items()):
            if isinstance(value, float):
                row[name] = round(value, 4)
    return rows


def _derive_split(
    case: Mapping[str, Any],
    event_volume: Mapping[str, Any],
    policy_values: Mapping[str, Any],
) -> dict[str, Any]:
    facts = _mapping(case.get("facts"))
    plan = _mapping(facts.get("split_plan"))
    if not plan:
        return {
            "state": "INSUFFICIENT_EVIDENCE",
            "reasons": ["split_plan_not_supplied"],
        }
    count = _non_negative(plan.get("campaign_count"), "facts.split_plan.campaign_count")
    if count is not None and not count.is_integer():
        raise ContractError("facts.split_plan.campaign_count must be an integer")
    minimum_events = _non_negative(
        plan.get(
            "minimum_daily_events_per_campaign",
            _mapping(policy_values.get("campaign_split")).get(
                "default_minimum_daily_mature_events_per_campaign"
            ),
        ),
        "facts.split_plan.minimum_daily_events_per_campaign",
    )
    if minimum_events is None:
        minimum_period_events = _non_negative(
            plan.get("minimum_mature_events_per_campaign"),
            "facts.split_plan.minimum_mature_events_per_campaign",
        )
        event_days = _number(event_volume.get("days"))
        minimum_events = _safe_ratio(minimum_period_events, event_days)
    minimum_budget = _non_negative(
        plan.get("minimum_daily_budget_per_campaign"),
        "facts.split_plan.minimum_daily_budget_per_campaign",
    )
    declared_total_budget = _non_negative(
        plan.get("total_daily_budget"),
        "facts.split_plan.total_daily_budget",
    )
    current_total_budget = _non_negative(
        facts.get("daily_budget"),
        "facts.daily_budget",
    )
    business_budget_cap = _non_negative(
        _mapping(case.get("goal")).get("daily_budget_cap"),
        "goal.daily_budget_cap",
    )
    safe_budget_boundaries = [
        value
        for value in (current_total_budget, business_budget_cap)
        if value is not None
    ]
    safe_total_budget = min(safe_budget_boundaries) if safe_budget_boundaries else None
    split_budget_increase_requested = bool(
        declared_total_budget is not None
        and safe_total_budget is not None
        and declared_total_budget > safe_total_budget
    )
    available_budget = (
        min(declared_total_budget, safe_total_budget)
        if declared_total_budget is not None and safe_total_budget is not None
        else safe_total_budget
    )
    mean_events = _number(event_volume.get("mean_daily_events"))
    candidate_events = _non_negative(
        plan.get("candidate_event_mature_events"),
        "facts.split_plan.candidate_event_mature_events",
    )
    candidate_daily_events = None
    if candidate_events is not None:
        event_days = _number(event_volume.get("days"))
        candidate_daily_events = _safe_ratio(candidate_events, event_days)
    if (
        count is None
        or count < 2
        or minimum_events is None
        or minimum_events <= 0
        or mean_events is None
        or (minimum_budget is not None and minimum_budget <= 0)
    ):
        return {
            "state": "INSUFFICIENT_EVIDENCE",
            "campaign_count": count,
            "reasons": [
                "campaign_count_event_density_and_multi_day_series_are_required"
            ],
        }
    projected_events = mean_events / count
    if candidate_daily_events is not None:
        projected_events = min(projected_events, candidate_daily_events)
    event_ratio = projected_events / minimum_events if minimum_events > 0 else 1.0
    required_budget = minimum_budget * count if minimum_budget is not None else None
    budget_ratio = (
        available_budget / required_budget
        if available_budget is not None
        and required_budget is not None
        and required_budget != 0
        else None
    )
    borderline_ratio = _policy_ratio(
        policy_values, "campaign_split", "borderline_capacity_percent"
    )
    current_budget_violates_cap = bool(
        current_total_budget is not None
        and business_budget_cap is not None
        and current_total_budget > business_budget_cap
    )
    if split_budget_increase_requested:
        state = "SPLIT_NOT_FEASIBLE"
        reasons = ["split_plan_cannot_increase_total_budget_during_campaign_creation"]
    elif current_budget_violates_cap:
        state = "SPLIT_NOT_FEASIBLE"
        reasons = ["current_total_budget_exceeds_business_cap_before_split"]
    elif minimum_budget is not None and available_budget is None:
        state = "INSUFFICIENT_EVIDENCE"
        reasons = ["total_daily_budget_or_business_cap_is_required"]
    elif event_ratio >= 1 and (budget_ratio is None or budget_ratio >= 1):
        state = "SPLIT_FEASIBLE"
        reasons = ["projected_event_density_and_budget_meet_declared_minimums"]
    elif event_ratio >= borderline_ratio and (
        budget_ratio is None or budget_ratio >= borderline_ratio
    ):
        state = "SPLIT_BORDERLINE"
        reasons = ["projected_split_capacity_is_close_to_declared_minimums"]
    else:
        state = "SPLIT_NOT_FEASIBLE"
        reasons = ["projected_event_density_or_budget_is_below_declared_minimum"]
    existing_floor = _non_negative(
        plan.get("existing_daily_budget_floor"),
        "facts.split_plan.existing_daily_budget_floor",
    )
    candidate_budget = (
        minimum_budget
        if state == "SPLIT_FEASIBLE"
        and minimum_budget is not None
        and available_budget is not None
        and (existing_floor or 0) + minimum_budget <= available_budget
        else None
    )
    return {
        "state": state,
        "campaign_count": int(count),
        "projected_daily_events_per_campaign": round(projected_events, 4),
        "minimum_daily_events_per_campaign": minimum_events,
        "available_total_daily_budget": available_budget,
        "required_total_daily_budget": required_budget,
        "existing_campaign_daily_budget": existing_floor,
        "new_campaign_daily_budget": candidate_budget,
        "candidate_target_value": None,
        "reasons": reasons,
    }


def derive_signals(
    case: Mapping[str, Any], *, policy: LoadedPolicy | None = None
) -> dict[str, Any]:
    """Derive business signals from normalized, multi-day account facts."""

    if not isinstance(case, Mapping):
        raise ContractError("UAC input must be an object")
    loaded_policy = policy or load_policy("signal")
    policy_values = _signal_policy_values(loaded_policy)
    context = _numeric_context(case, loaded_policy)
    priority = context.get("optimization_priority")
    if priority not in {"scale", "efficiency", "balanced"}:
        raise ContractError(
            "goal.optimization_priority must be scale, efficiency, or balanced"
        )
    maturity = _derive_maturity(context)
    budget = _derive_budget_delivery(case, context)
    event_volume = _derive_event_volume(case, context, policy_values)
    target = _derive_target_constraint(case, context, maturity, budget)
    value = _derive_value_signal(case, context, maturity, event_volume, policy_values)
    split = _derive_split(case, event_volume, policy_values)
    evidence = [
        {
            "type": "ACCOUNT_EVIDENCE",
            "fact": "multi_day_budget_delivery",
            "value": budget.get("delivery_rate"),
        },
        {
            "type": "ACCOUNT_EVIDENCE",
            "fact": "mature_actual_cpa",
            "value": _round_metric(context.get("mature_actual_cpa"), 4),
        },
        {
            "type": "ACCOUNT_EVIDENCE",
            "fact": "mature_actual_roas",
            "value": _round_metric(context.get("mature_actual_roas"), 4),
        },
        {
            "type": "BUSINESS_CONSTRAINT",
            "fact": "maximum_acceptable_cpa",
            "value": context.get("maximum_acceptable_cpa"),
        },
        {
            "type": "BUSINESS_CONSTRAINT",
            "fact": "minimum_acceptable_roas",
            "value": context.get("minimum_acceptable_roas"),
        },
    ]
    return {
        "schema_version": SIGNAL_DERIVATION_SCHEMA_VERSION,
        "has_numeric_evidence": context["has_numeric_evidence"],
        "maturity": maturity,
        "budget_delivery": budget,
        "target_constraint": target,
        "event_volume": event_volume,
        "value_signal": value,
        "split_feasibility": split,
        "event_candidates": _rank_event_candidates(case, policy_values),
        "creative_quality": _creative_quality(case, policy_values),
        "policy": loaded_policy.as_record(),
        "calculation_evidence": evidence,
        "heuristics_used": [
            "multi_day_delivery_bands_are_diagnostic_not_platform_laws",
            "event_stability_uses_account_series_coefficient_of_variation",
            "proxy_event_scores_rank_only_candidates_inside_this_account",
        ],
    }


def apply_derived_signals(
    case: Mapping[str, Any], derived: Mapping[str, Any]
) -> dict[str, Any]:
    """Project derived facts onto legacy Quick gates without mutating input."""

    projected = deepcopy(dict(case))
    quick_value = projected.get("quick_ops")
    quick = dict(quick_value) if isinstance(quick_value, Mapping) else {}
    projected["quick_ops"] = quick
    if derived.get("has_numeric_evidence") is not True:
        return projected

    split = _mapping(derived.get("split_feasibility"))
    split_state = split.get("state")
    if split_state != "INSUFFICIENT_EVIDENCE" or _mapping(
        _mapping(case.get("facts")).get("split_plan")
    ):
        legacy_split = dict(_mapping(quick.get("split_capacity")))
        if split_state == "SPLIT_FEASIBLE":
            legacy_split.update(
                {
                    "budget_assessment": "sufficient",
                    "event_volume_assessment": "sufficient",
                    "isolatable": True,
                    "source": "derived_account_evidence",
                }
            )
        elif split_state == "SPLIT_BORDERLINE":
            legacy_split.update(
                {
                    "budget_assessment": "borderline",
                    "event_volume_assessment": "borderline",
                    "isolatable": True,
                    "source": "derived_account_evidence",
                }
            )
        elif split_state == "SPLIT_NOT_FEASIBLE":
            legacy_split.update(
                {
                    "budget_assessment": "insufficient",
                    "event_volume_assessment": "insufficient",
                    "isolatable": False,
                    "source": "derived_account_evidence",
                }
            )
        else:
            legacy_split.update(
                {
                    "budget_assessment": "unknown",
                    "event_volume_assessment": "unknown",
                    "isolatable": None,
                    "source": "derived_account_evidence",
                }
            )
        quick["split_capacity"] = legacy_split

    value = _mapping(derived.get("value_signal"))
    value_state = value.get("state")
    measurement = _mapping(case.get("measurement"))
    goal = _mapping(case.get("goal"))
    business_goal = str(goal.get("business_goal", "")).lower()
    event_state = _mapping(derived.get("event_volume")).get("state")
    maturity_state = _mapping(derived.get("maturity")).get("state")
    legacy_value = dict(_mapping(quick.get("value_signal")))
    if value_state == "VALUE_SIGNAL_READY":
        legacy_value.update(
            {
                "payment_reliable": True,
                "value_reliable": True,
                "currency_reliable": True,
                "duplicates_handled": measurement.get("duplicate_events") is False,
                "refunds_handled": measurement.get("payment_trial_refund_distinguished")
                is True,
                "subscriptions_defined": (
                    measurement.get("subscription_renewal_included") is True
                    if business_goal in {"subscription", "subscriptions", "retention"}
                    else True
                ),
                "delay_mature": maturity_state == "MATURE",
                "value_reconciliation": "consistent",
                "volume_assessment": (
                    "sufficient"
                    if event_state
                    in {"SUFFICIENT_AND_STABLE", "SUFFICIENT_BUT_VOLATILE"}
                    else "insufficient"
                ),
                "stability_assessment": (
                    "stable" if event_state == "SUFFICIENT_AND_STABLE" else "volatile"
                ),
                "source": "derived_account_evidence",
            }
        )
    elif value_state == "VALUE_SIGNAL_UNRELIABLE":
        legacy_value.update(
            {
                "value_reliable": False,
                "currency_reliable": False,
                "value_reconciliation": "material_mismatch",
                "source": "derived_account_evidence",
            }
        )
    elif value_state == "VALUE_SIGNAL_BORDERLINE":
        legacy_value.update(
            {
                "volume_assessment": "borderline",
                "stability_assessment": "volatile",
                "source": "derived_account_evidence",
            }
        )
    else:
        legacy_value.update(
            {
                "volume_assessment": "unknown",
                "stability_assessment": "unknown",
                "source": "derived_account_evidence",
            }
        )
    quick["value_signal"] = legacy_value

    candidates = derived.get("event_candidates")
    if isinstance(candidates, list) and candidates:
        best = next(
            (
                item
                for item in candidates
                if isinstance(item, Mapping)
                and item.get("recommendation") == "current_best_proxy"
            ),
            candidates[0],
        )
        legacy_candidate = dict(_mapping(quick.get("candidate_event")))
        ready = (
            best.get("recommendation") == "current_best_proxy"
            and maturity_state == "MATURE"
            and event_state == "SUFFICIENT_AND_STABLE"
        )
        legacy_candidate.update(
            {
                "reliable": ready,
                "delay_mature": best.get("delay_score") != "low",
                "volume_assessment": (
                    "sufficient"
                    if best.get("volume_score") != "low"
                    else "insufficient"
                ),
                "stability_assessment": "stable" if ready else "unknown",
                "relationship_to_business_goal": (
                    "stronger"
                    if best.get("payment_relationship_score") != "low"
                    else "unknown"
                ),
                "source": "derived_account_evidence",
            }
        )
        quick["candidate_event"] = legacy_candidate

    creative_quality = derived.get("creative_quality")
    if isinstance(creative_quality, list) and creative_quality:
        classifications = {
            item.get("classification")
            for item in creative_quality
            if isinstance(item, Mapping)
        }
        creative = dict(_mapping(quick.get("creative")))
        creative["asset_grain_available"] = True
        creative["mature"] = any(
            classification != "INSUFFICIENT_DATA" for classification in classifications
        )
        creative["lowest_cpi_worst_payment_rate"] = (
            "CHEAP_LOW_QUALITY" in classifications
        )
        creative["fatigued"] = "FATIGUING" in classifications
        quick["creative"] = creative
    return projected


__all__ = [
    "SIGNAL_DERIVATION_SCHEMA_VERSION",
    "apply_derived_signals",
    "derive_signals",
]
