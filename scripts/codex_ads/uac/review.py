"""Deterministic experiment review rules."""

from __future__ import annotations

import math
from typing import Any

from .types import EXPERIMENT_RESULTS


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def _non_negative_finite_number(value: Any) -> bool:
    if not _finite_number(value):
        return False
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return value >= 0


def review_experiment(experiment: dict[str, Any]) -> dict[str, Any]:
    """Derive an auditable result status without inventing thresholds."""
    observation = experiment.get("observation", {})
    result = experiment.get("result", {})
    snapshot = result.get("review_snapshot", {})
    reasons: list[str] = []
    if (
        not isinstance(observation, dict)
        or not isinstance(result, dict)
        or not isinstance(snapshot, dict)
    ):
        return {
            "id": experiment.get("id"),
            "status": "INVALIDATED",
            "reasons": ["experiment review fields are not objects"],
        }
    minimum_days = observation.get("minimum_days")
    minimum_conversions = observation.get("minimum_conversions")
    days_elapsed = snapshot.get("days_elapsed")
    conversions_observed = snapshot.get("conversions_observed")
    numeric_values = (
        minimum_days,
        minimum_conversions,
        days_elapsed,
        conversions_observed,
    )
    if any(not _non_negative_finite_number(value) for value in numeric_values):
        return {
            "id": experiment.get("id"),
            "status": "INVALIDATED",
            "reasons": [
                "experiment review requires non-negative numeric maturity fields"
            ],
        }
    assert isinstance(minimum_days, (int, float))
    assert isinstance(minimum_conversions, (int, float))
    assert isinstance(days_elapsed, (int, float))
    assert isinstance(conversions_observed, (int, float))

    for field in ("conversion_delay_mature", "guardrail_breached"):
        if not isinstance(snapshot.get(field), bool):
            return {
                "id": experiment.get("id"),
                "status": "INVALIDATED",
                "reasons": [f"{field} must be supplied as a boolean"],
            }

    changes = snapshot.get("concurrent_changes", [])
    if not isinstance(changes, list) or not all(
        isinstance(item, str) for item in changes
    ):
        return {
            "id": experiment.get("id"),
            "status": "INVALIDATED",
            "reasons": ["concurrent_changes must be an array of variable names"],
        }
    variable = experiment.get("variable", {})
    if not isinstance(variable, dict):
        return {
            "id": experiment.get("id"),
            "status": "INVALIDATED",
            "reasons": ["experiment variable must be an object"],
        }
    declared_variable = variable.get("type")
    distinct_changes = set(changes)
    wrong_single_variable = bool(
        declared_variable and distinct_changes != {declared_variable}
    )

    if len(distinct_changes) > 1 or wrong_single_variable:
        status = "CONFOUNDED"
        if len(distinct_changes) > 1:
            reasons.append("more than one variable changed during the experiment")
        else:
            reasons.append(
                "the declared experiment variable was not the only recorded change"
            )
        if snapshot.get("guardrail_breached"):
            reasons.append("a declared guardrail was also breached")
    elif snapshot.get("guardrail_breached"):
        status = "STOPPED_FOR_GUARDRAIL"
        reasons.append("a declared guardrail was breached")
    elif snapshot.get("conversion_delay_mature") is False:
        status = "WAITING_FOR_MATURITY"
        reasons.append("conversion delay is not mature")
    elif days_elapsed < minimum_days:
        status = "WAITING_FOR_MATURITY"
        reasons.append("minimum observation days not reached")
    elif conversions_observed < minimum_conversions:
        status = "INSUFFICIENT_VOLUME"
        reasons.append("minimum conversion volume not reached")
    elif isinstance(result.get("rule_evaluation"), dict):
        evaluation = result["rule_evaluation"]
        if evaluation.get("invalidated") is True:
            status = "INVALIDATED"
        elif evaluation.get("rollback_rule_met") is True:
            status = "LOSS"
        elif evaluation.get("success_rule_met") is True:
            status = "WIN"
        elif evaluation.get("inconclusive_rule_met") is True:
            status = "INCONCLUSIVE"
        else:
            status = "INCONCLUSIVE"
        reasons.append("predeclared rule evaluation was supplied")
    elif result.get("evaluation") in {
        "success",
        "failure",
        "inconclusive",
        "invalidated",
    }:
        status = {
            "success": "WIN",
            "failure": "LOSS",
            "inconclusive": "INCONCLUSIVE",
            "invalidated": "INVALIDATED",
        }[result["evaluation"]]
        reasons.append("predeclared evaluation was supplied")
    elif result.get("status") in {"WIN", "LOSS", "INCONCLUSIVE", "INVALIDATED"}:
        status = result["status"]
        reasons.append("a final experiment result status was supplied")
    elif result.get("status") in EXPERIMENT_RESULTS:
        status = "INVALIDATED"
        reasons.append(
            "the supplied evidence-derived result status lacks supporting snapshot evidence"
        )
    else:
        status = "INCONCLUSIVE"
        reasons.append(
            "mature volume exists but no predeclared rule evaluation was supplied"
        )
    return {"id": experiment.get("id"), "status": status, "reasons": reasons}
