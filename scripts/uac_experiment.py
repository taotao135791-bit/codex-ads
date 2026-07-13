#!/usr/bin/env python3
"""Deterministic Google App campaigns analysis and experiment-loop helper.

The module deliberately does not call an LLM or an advertising API. It turns
user-provided/exported facts into a conservative structured decision, can read
an existing experiment ledger, and renders a Markdown report from that single
source of truth.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by CLI error path
    yaml = None


MEASUREMENT_STATES = {
    "measurement_reliable",
    "measurement_uncertain",
    "measurement_unreliable",
    "insufficient_evidence",
}
LEARNING_STATES = {
    "LEARNABLE",
    "BORDERLINE",
    "INSUFFICIENT_EVENT_VOLUME",
    "BUDGET_CONSTRAINED",
    "TARGET_TOO_AGGRESSIVE",
    "MEASUREMENT_UNRELIABLE",
    "CONVERSION_DELAY_NOT_MATURE",
    "INSUFFICIENT_EVIDENCE",
}
FEASIBILITY_STATES = {
    "DIRECTLY_OPTIMIZABLE",
    "LIMITED_INCREMENT_AVAILABLE",
    "EXPERIMENT_AVAILABLE",
    "DATA_BLOCKED",
    "PERMISSION_BLOCKED",
    "TRACKING_BLOCKED",
    "PRODUCT_FUNNEL_BLOCKED",
    "LEARNING_BLOCKED",
    "NO_ACTION_RECOMMENDED",
}
PERMISSION_CLASSES = {
    "OPTIMIZER_CAN_EXECUTE",
    "CLIENT_APPROVAL_REQUIRED",
    "CLIENT_DATA_REQUIRED",
    "PRODUCT_DEPENDENCY",
    "TRACKING_DEPENDENCY",
    "PLATFORM_LIMITATION",
    "NOT_ACTIONABLE",
    "INSUFFICIENT_EVIDENCE",
}
EXPERIMENT_RESULTS = {
    "WIN",
    "LOSS",
    "INCONCLUSIVE",
    "INVALIDATED",
    "STOPPED_FOR_GUARDRAIL",
    "WAITING_FOR_MATURITY",
    "INSUFFICIENT_VOLUME",
    "CONFOUNDED",
}
TERMINAL_EXPERIMENT_RESULTS = {
    "WIN",
    "LOSS",
    "INCONCLUSIVE",
    "INVALIDATED",
    "STOPPED_FOR_GUARDRAIL",
    "CONFOUNDED",
}
EXPERIMENT_STATUSES = {
    "proposed",
    "approved",
    "running",
    "observing",
    "completed",
    "stopped",
    "cancelled",
}
EVIDENCE_QUALITY_STATES = {
    "pending",
    "platform_only",
    "account_specific",
    "reconciled",
    "insufficient",
    "not_executed",
}
LEARNING_SCOPES = {
    "account_specific",
    "product_specific",
    "creative_specific",
    "reusable_heuristic",
}


class ContractError(ValueError):
    """Raised when input or ledger data violates a safety contract."""


def _normalize_campaign_type(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower().replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())
    aliases = {
        "app campaign",
        "app campaigns",
        "google app campaign",
        "google app campaigns",
        "uac",
    }
    return "app_campaign" if normalized in aliases else normalized.replace(" ", "_")


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
    else:
        if yaml is None:
            raise ContractError(
                "PyYAML is required for YAML input; use JSON or install PyYAML"
            )
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ContractError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain an object at the top level")
    return value


def _dump(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n"
    else:
        if yaml is None:
            raise ContractError("PyYAML is required for YAML output")
        text = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = temporary.name
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _validate_case(case: dict[str, Any]) -> None:
    if not isinstance(case, dict):
        raise ContractError("UAC input must be an object")
    object_fields = (
        "scope",
        "goal",
        "facts",
        "measurement",
        "learning",
        "maturity",
        "permissions",
        "signals",
        "experiment_policy",
        "next_review",
        "active_experiment",
    )
    for field in object_fields:
        if (
            field in case
            and case[field] is not None
            and not isinstance(case[field], dict)
        ):
            raise ContractError(f"{field} must be an object")

    scope = case.get("scope")
    if not isinstance(scope, dict):
        raise ContractError("scope must be an object")
    if scope.get("platform") != "google_ads":
        raise ContractError("scope.platform must be google_ads")
    if _normalize_campaign_type(scope.get("campaign_type")) != "app_campaign":
        raise ContractError("scope.campaign_type must be app_campaign")
    for field in ("start_date", "end_date", "timezone"):
        if field in scope and (
            not isinstance(scope[field], str) or not scope[field].strip()
        ):
            raise ContractError(f"scope.{field} must be a non-empty string")
    for field in ("start_date", "end_date"):
        if field in scope:
            try:
                date.fromisoformat(scope[field])
            except ValueError as exc:
                raise ContractError(f"scope.{field} must use YYYY-MM-DD") from exc
    if scope.get("start_date") and scope.get("end_date"):
        if date.fromisoformat(scope["start_date"]) > date.fromisoformat(
            scope["end_date"]
        ):
            raise ContractError("scope.start_date must not be after scope.end_date")

    evidence = case.get("evidence")
    if not isinstance(evidence, list):
        raise ContractError("evidence must be an array")
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise ContractError(f"evidence[{index}] must be an object")
        for field in ("id", "observation", "source_kind"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ContractError(
                    f"evidence[{index}].{field} must be a non-empty string"
                )

    facts = case.get("facts", {})
    if "segmentation_complete" in facts and facts["segmentation_complete"] is not None:
        if not isinstance(facts["segmentation_complete"], bool):
            raise ContractError("facts.segmentation_complete must be boolean or null")

    signals = case.get("signals", {})
    for field in (
        "multiple_simultaneous_changes",
        "country_segment_anomaly",
        "lowest_cpi_has_worst_payment_rate",
        "paywall_drop",
        "stable_no_material_anomaly",
    ):
        if field in signals and signals[field] is not None:
            if not isinstance(signals[field], bool):
                raise ContractError(f"signals.{field} must be boolean or null")

    measurement = case.get("measurement", {})
    comparisons = ("google_ads_vs_firebase", "google_ads_vs_mmp", "mmp_vs_backend")
    for field in comparisons:
        if field in measurement and measurement[field] not in {
            "consistent",
            "material_mismatch",
            "unknown",
            None,
        }:
            raise ContractError(f"measurement.{field} has an invalid value")
    for field in (
        "duplicate_events",
        "value_currency_valid",
        "delay_known",
        "os_discrepancy",
        "first_repeat_definition_clear",
        "payment_trial_refund_distinguished",
        "attribution_window_reviewed",
    ):
        if (
            field in measurement
            and measurement[field] is not None
            and not isinstance(measurement[field], bool)
        ):
            raise ContractError(f"measurement.{field} must be boolean or null")

    learning = case.get("learning", {})
    allowed_learning = {
        "event_volume_assessment": {
            "sufficient",
            "borderline",
            "insufficient",
            "unknown",
            None,
        },
        "budget_assessment": {"sufficient", "constrained", "unknown", None},
        "target_assessment": {"reasonable", "aggressive", "unknown", None},
    }
    for field, allowed in allowed_learning.items():
        if field in learning and learning[field] not in allowed:
            raise ContractError(f"learning.{field} has an invalid value")

    maturity = case.get("maturity", {})
    for field in (
        "days_elapsed",
        "minimum_days",
        "conversions_observed",
        "minimum_conversions",
        "conversion_delay_elapsed_days",
        "conversion_delay_days",
    ):
        value = maturity.get(field)
        if value is not None and (
            not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
        ):
            raise ContractError(f"maturity.{field} must be a non-negative number")

    permissions = case.get("permissions", {})
    permission_sets: list[set[str]] = []
    for field in (
        "optimizer_can",
        "client_approval_required",
        "client_data_required",
        "platform_limitations",
        "unavailable",
    ):
        value = permissions.get(field, [])
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ContractError(f"permissions.{field} must be an array of strings")
        permission_sets.append(set(value))
    if any(
        permission_sets[left] & permission_sets[right]
        for left in range(len(permission_sets))
        for right in range(left + 1, len(permission_sets))
    ):
        raise ContractError("a variable cannot appear in multiple permission classes")

    metrics = case.get("facts", {}).get("metrics", {})
    if not isinstance(metrics, dict):
        raise ContractError("facts.metrics must be an object")
    for name, value in metrics.items():
        if value is not None and (
            not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
        ):
            raise ContractError(
                f"facts.metrics.{name} must be a non-negative number or null"
            )

    goal = case.get("goal", {})
    for field in ("business_goal", "optimization_event", "bidding_strategy"):
        if goal.get(field) is not None and not isinstance(goal[field], str):
            raise ContractError(f"goal.{field} must be a string or null")
    if goal.get("proxy_evidence") not in {
        None,
        "unknown",
        "supported_by_mature_cohort",
        "contradicted_by_mature_cohort",
    }:
        raise ContractError("goal.proxy_evidence has an invalid value")


def _normalize_event_name(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower()
    for character in ("-", " ", "/"):
        normalized = normalized.replace(character, "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    aliases = {
        "installs": "install",
        "registrations": "registration",
        "in_app_actions": "in_app_action",
        "likely_to_perform_an_in_app_action": "in_app_action",
        "purchase": "payment",
        "purchases": "payment",
        "payments": "payment",
        "subscription": "payment",
        "subscriptions": "payment",
        "revenue": "value",
        "in_app_action_value": "value",
        "retained_users": "retention",
    }
    return aliases.get(normalized, normalized)


def _goal_assessment(case: dict[str, Any], measurement_state: str) -> dict[str, Any]:
    goal = case.get("goal", {})
    business_goal_raw = goal.get("business_goal")
    optimization_event_raw = goal.get("optimization_event")
    business_goal = _normalize_event_name(business_goal_raw)
    optimization_event = _normalize_event_name(optimization_event_raw)
    proxy_evidence = goal.get("proxy_evidence", "unknown")
    depth = {
        "install": 0,
        "registration": 1,
        "key_action": 2,
        "in_app_action": 2,
        "paywall_view": 3,
        "trial": 3,
        "payment": 4,
        "purchase": 4,
        "retention": 5,
        "value": 5,
        "in_app_action_value": 5,
    }
    if not isinstance(business_goal, str) or not isinstance(optimization_event, str):
        alignment = "insufficient_evidence"
    elif business_goal not in depth or optimization_event not in depth:
        alignment = "requires_explicit_event_definition"
    elif depth[optimization_event] < depth[business_goal]:
        alignment = "optimization_event_too_shallow"
    elif depth[optimization_event] > depth[business_goal]:
        alignment = "optimization_event_may_be_too_deep"
    else:
        alignment = "aligned"

    if measurement_state == "measurement_unreliable":
        proxy_quality = "unsupported_while_measurement_unreliable"
    elif proxy_evidence == "supported_by_mature_cohort":
        proxy_quality = "supported_proxy"
    elif proxy_evidence == "contradicted_by_mature_cohort":
        proxy_quality = "unsupported_proxy"
    else:
        proxy_quality = "insufficient_evidence"
    return {
        "business_goal_raw": business_goal_raw,
        "optimization_event_raw": optimization_event_raw,
        "business_goal": business_goal,
        "optimization_event": optimization_event,
        "bidding_strategy": goal.get("bidding_strategy"),
        "alignment": alignment,
        "proxy_quality": proxy_quality,
        "required_evidence": [
            "event definition and firing behavior",
            "mature cohort relationship to the business goal",
            "volume, delay, deduplication, value, and currency reliability",
        ],
    }


def _funnel_state(case: dict[str, Any]) -> dict[str, Any]:
    metrics = case.get("facts", {}).get("metrics", {})
    if not isinstance(metrics, dict):
        raise ContractError("facts.metrics must be an object")
    stages = (
        ("installs", "registration", "registrations"),
        ("registrations", "key_action", "key_actions"),
        ("key_actions", "paywall_view", "paywall_views"),
        ("paywall_views", "trial", "trials"),
        ("trials", "payment", "payments"),
        ("payments", "retention", "retained_users"),
    )
    rates: list[dict[str, Any]] = []
    for source_key, target_name, target_key in stages:
        source = metrics.get(source_key)
        target = metrics.get(target_key)
        if (
            isinstance(source, (int, float))
            and source > 0
            and isinstance(target, (int, float))
        ):
            rates.append(
                {
                    "from": source_key,
                    "to": target_name,
                    "rate": target / source,
                    "drop": 1 - (target / source),
                }
            )
    largest = max(rates, key=lambda item: item["drop"], default=None)
    return {
        "observed_rates": rates,
        "largest_observed_drop": largest,
        "causal_attribution": "undetermined",
        "note": "A funnel drop is not attributed to media, creative, or product without evidence.",
    }


def _experiment_policy_errors(policy: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["experiment_policy is missing"]
    errors: list[str] = []
    if not isinstance(policy.get("id"), str) or not policy.get("id", "").strip():
        errors.append("experiment_policy.id is missing")
    string_fields = (
        "hypothesis",
        "control_definition",
        "maturity_rule",
        "success_rule",
        "rollback_rule",
        "inconclusive_rule",
    )
    for field in string_fields:
        if not isinstance(policy.get(field), str) or not policy.get(field, "").strip():
            errors.append(f"experiment_policy.{field} is missing")
    if "treatment_definition" in policy and (
        not isinstance(policy["treatment_definition"], str)
        or not policy["treatment_definition"].strip()
    ):
        errors.append("experiment_policy.treatment_definition is invalid")
    if policy.get("confidence", "medium") not in {"low", "medium", "high"}:
        errors.append("experiment_policy.confidence is invalid")
    for field in ("minimum_days", "minimum_conversions", "conversion_delay_days"):
        value = policy.get(field)
        minimum = 0 if field == "conversion_delay_days" else 1
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < minimum
        ):
            errors.append(f"experiment_policy.{field} is invalid")
    if not isinstance(policy.get("baseline"), dict):
        errors.append("experiment_policy.baseline is missing")
    primary_metric = policy.get("primary_metric")
    if (
        not isinstance(primary_metric, dict)
        or not isinstance(primary_metric.get("name"), str)
        or not primary_metric.get("name", "").strip()
    ):
        errors.append("experiment_policy.primary_metric is missing")
    elif primary_metric.get("direction") not in {
        "increase",
        "decrease",
        "maintain",
        "within_range",
    }:
        errors.append("experiment_policy.primary_metric.direction is invalid")
    secondary_metrics = policy.get("secondary_metrics", [])
    if not isinstance(secondary_metrics, list) or not all(
        isinstance(item, str) and item.strip() for item in secondary_metrics
    ):
        errors.append("experiment_policy.secondary_metrics is invalid")
    guardrails = policy.get("guardrail_metrics")
    if (
        not isinstance(guardrails, list)
        or not guardrails
        or not all(isinstance(item, str) and item.strip() for item in guardrails)
    ):
        errors.append("experiment_policy.guardrail_metrics is missing")
    return errors


def _measurement_state(case: dict[str, Any]) -> tuple[str, list[str]]:
    measurement = case.get("measurement", {})
    reasons: list[str] = []
    comparisons = [
        "google_ads_vs_firebase",
        "google_ads_vs_mmp",
        "mmp_vs_backend",
    ]

    for field in comparisons:
        if measurement.get(field) == "material_mismatch":
            reasons.append(f"{field}=material_mismatch")
    if measurement.get("duplicate_events") is True:
        reasons.append("duplicate_events=true")
    if measurement.get("value_currency_valid") is False:
        reasons.append("value_currency_valid=false")
    if measurement.get("os_discrepancy") is True:
        reasons.append("os_discrepancy=true")
    business_goal = _normalize_event_name(case.get("goal", {}).get("business_goal"))
    deep_goal_checks = business_goal in {"payment", "value", "retention"}
    if deep_goal_checks and measurement.get("first_repeat_definition_clear") is False:
        reasons.append("first_repeat_definition_clear=false")
    if (
        deep_goal_checks
        and measurement.get("payment_trial_refund_distinguished") is False
    ):
        reasons.append("payment_trial_refund_distinguished=false")
    if reasons:
        return "measurement_unreliable", reasons

    known = 0
    unknown_fields: list[str] = []
    for field in comparisons:
        value = measurement.get(field, "unknown")
        if value == "consistent":
            known += 1
        elif value in {"unknown", None}:
            unknown_fields.append(field)
    for field in ("duplicate_events", "value_currency_valid", "os_discrepancy"):
        if measurement.get(field) is None:
            unknown_fields.append(field)
        else:
            known += 1
    if measurement.get("delay_known") is True:
        known += 1
    else:
        unknown_fields.append("delay_known")

    if deep_goal_checks:
        for field in (
            "first_repeat_definition_clear",
            "payment_trial_refund_distinguished",
            "attribution_window_reviewed",
        ):
            if measurement.get(field) is True:
                known += 1
            else:
                unknown_fields.append(field)

    if known == 0:
        return "insufficient_evidence", ["measurement checks were not provided"]
    if unknown_fields:
        return "measurement_uncertain", [
            "unknown measurement checks: " + ", ".join(unknown_fields)
        ]
    return "measurement_reliable", [
        "provided reconciliation and event checks are consistent"
    ]


def _maturity(case: dict[str, Any]) -> tuple[bool, list[str]]:
    maturity = case.get("maturity", {})
    missing = [
        key
        for key in (
            "days_elapsed",
            "minimum_days",
            "conversions_observed",
            "minimum_conversions",
            "conversion_delay_elapsed_days",
            "conversion_delay_days",
        )
        if maturity.get(key) is None
    ]
    if missing:
        return False, ["missing maturity fields: " + ", ".join(missing)]

    reasons: list[str] = []
    if maturity["days_elapsed"] < maturity["minimum_days"]:
        reasons.append("minimum observation days not reached")
    if maturity["conversion_delay_elapsed_days"] < maturity["conversion_delay_days"]:
        reasons.append("conversion delay window is not mature")
    if maturity["conversions_observed"] < maturity["minimum_conversions"]:
        reasons.append("minimum mature conversion volume not reached")
    return not reasons, reasons or [
        "time, volume, and conversion-delay requirements are mature"
    ]


def _learning_state(
    case: dict[str, Any],
    measurement_state: str,
    mature: bool,
    maturity_reasons: list[str],
) -> tuple[str, list[str]]:
    learning = case.get("learning", {})
    if measurement_state == "measurement_unreliable":
        return "MEASUREMENT_UNRELIABLE", [
            "deep-event measurement cannot support optimization"
        ]
    if measurement_state in {"measurement_uncertain", "insufficient_evidence"}:
        return "INSUFFICIENT_EVIDENCE", ["measurement evidence is incomplete"]
    if not mature and any(
        reason.startswith("missing maturity fields") for reason in maturity_reasons
    ):
        return "INSUFFICIENT_EVIDENCE", maturity_reasons
    if not mature and any(
        "delay" in reason or "observation" in reason for reason in maturity_reasons
    ):
        return "CONVERSION_DELAY_NOT_MATURE", maturity_reasons
    if not mature and any("conversion volume" in reason for reason in maturity_reasons):
        return "INSUFFICIENT_EVENT_VOLUME", maturity_reasons
    if learning.get("event_volume_assessment") == "insufficient":
        return "INSUFFICIENT_EVENT_VOLUME", [
            "account-provided event-volume rule is not met"
        ]
    if learning.get("budget_assessment") == "constrained":
        return "BUDGET_CONSTRAINED", [
            "account/platform evidence marks budget as constrained"
        ]
    if learning.get("target_assessment") == "aggressive":
        return "TARGET_TOO_AGGRESSIVE", [
            "historical evidence marks the target as aggressive"
        ]
    if learning.get("event_volume_assessment") == "borderline":
        return "BORDERLINE", ["event volume is borderline under the supplied rule"]
    required = ("event_volume_assessment", "budget_assessment", "target_assessment")
    if any(learning.get(key) in {None, "unknown"} for key in required):
        return "INSUFFICIENT_EVIDENCE", ["learning evidence is incomplete"]
    return "LEARNABLE", [
        "supplied volume, budget, target, and maturity checks are eligible"
    ]


def _primary_diagnosis(
    case: dict[str, Any], measurement_state: str, learning_state: str
) -> str:
    signals = case.get("signals", {})
    metrics = case.get("facts", {}).get("metrics", {})
    if measurement_state == "measurement_unreliable":
        if case.get("measurement", {}).get("os_discrepancy"):
            return "ios_measurement_anomaly"
        return "measurement_mismatch"
    if measurement_state in {"measurement_uncertain", "insufficient_evidence"}:
        return "insufficient_evidence"
    if learning_state == "INSUFFICIENT_EVENT_VOLUME":
        return "insufficient_event_volume"
    if learning_state == "TARGET_TOO_AGGRESSIVE":
        return "target_too_aggressive"
    if learning_state == "BUDGET_CONSTRAINED":
        return "budget_cannot_support_goal"
    if learning_state == "CONVERSION_DELAY_NOT_MATURE":
        return "conversion_not_mature"
    if signals.get("multiple_simultaneous_changes"):
        return "experiment_confounded"
    if signals.get("country_segment_anomaly"):
        return "segmented_geo_anomaly"
    if signals.get("lowest_cpi_has_worst_payment_rate"):
        return "low_cpi_low_value_creative"
    if signals.get("paywall_drop"):
        return "post_install_product_funnel_drop"
    business_goal = _normalize_event_name(case.get("goal", {}).get("business_goal", ""))
    if (
        metrics.get("installs", 0) > 0
        and metrics.get("payments") == 0
        and business_goal in {"payment", "value", "retention"}
    ):
        return "cheap_installs_zero_payments"
    if signals.get("stable_no_material_anomaly"):
        return "no_material_anomaly"
    return "insufficient_evidence"


def _permission_class(case: dict[str, Any], variable: str) -> str:
    permissions = case.get("permissions", {})
    if variable in permissions.get("optimizer_can", []):
        return "OPTIMIZER_CAN_EXECUTE"
    if variable in permissions.get("client_approval_required", []):
        return "CLIENT_APPROVAL_REQUIRED"
    if variable in permissions.get("client_data_required", []) or variable in {
        "cohort_data",
        "measurement_export",
    }:
        return "CLIENT_DATA_REQUIRED"
    if variable in permissions.get("platform_limitations", []):
        return "PLATFORM_LIMITATION"
    if variable in permissions.get("unavailable", []):
        if variable in {"paywall", "product", "store_page"}:
            return "PRODUCT_DEPENDENCY"
        if variable in {"tracking", "sdk", "mmp", "backend_event"}:
            return "TRACKING_DEPENDENCY"
        return "NOT_ACTIONABLE"
    return "INSUFFICIENT_EVIDENCE"


def _action_candidates(case: dict[str, Any], diagnosis: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(variable: str, action: str, kind: str, reason: str) -> None:
        candidates.append(
            {
                "variable": variable,
                "action": action,
                "kind": kind,
                "permission": _permission_class(case, variable),
                "reason": reason,
            }
        )

    if diagnosis in {"measurement_mismatch", "ios_measurement_anomaly"}:
        add(
            "tracking",
            "reconcile Google Ads, MMP, and backend deep events",
            "investigation",
            diagnosis,
        )
        add(
            "measurement_export",
            "request aligned platform, MMP, and backend cohorts",
            "client_request",
            diagnosis,
        )
    elif diagnosis == "insufficient_event_volume":
        add(
            "tracking",
            "confirm the deepest reliable proxy event and its cohort relationship",
            "investigation",
            diagnosis,
        )
    elif diagnosis == "target_too_aggressive":
        add("bid", "test one evidence-based target relaxation", "experiment", diagnosis)
    elif diagnosis == "budget_cannot_support_goal":
        add(
            "budget",
            "test one budget level that matches the supplied learning rule",
            "experiment",
            diagnosis,
        )
    elif diagnosis == "conversion_not_mature":
        add(
            "monitoring",
            "hold settings until the observation and delay windows mature",
            "monitoring",
            diagnosis,
        )
    elif diagnosis == "segmented_geo_anomaly":
        add(
            "analysis",
            "break the anomaly down by campaign, asset group, OS, event, and cohort",
            "investigation",
            diagnosis,
        )
    elif diagnosis in {"low_cpi_low_value_creative", "cheap_installs_zero_payments"}:
        add(
            "creative",
            "test a paid-value prefilter creative concept",
            "experiment",
            diagnosis,
        )
        add(
            "cohort_data",
            "request mature payment/value cohorts by creative concept",
            "client_request",
            diagnosis,
        )
    elif diagnosis == "post_install_product_funnel_drop":
        add(
            "paywall",
            "request paywall cohort evidence or a client-side test",
            "client_request",
            diagnosis,
        )
        add(
            "creative",
            "test clearer paid-value expectation before install",
            "experiment",
            diagnosis,
        )
    elif diagnosis == "experiment_confounded":
        add(
            "monitoring",
            "invalidate the mixed-variable result and restore a clean baseline",
            "monitoring",
            diagnosis,
        )
    elif diagnosis == "no_material_anomaly":
        add(
            "monitoring",
            "do not modify the account; continue scheduled monitoring",
            "monitoring",
            diagnosis,
        )
    else:
        add(
            "data",
            "collect the missing campaign, OS, event, asset, and cohort evidence",
            "investigation",
            diagnosis,
        )

    return candidates


def _diagnosis_permission(diagnosis: str, candidates: list[dict[str, Any]]) -> str:
    if diagnosis in {
        "conversion_not_mature",
        "experiment_confounded",
        "no_material_anomaly",
    }:
        return "NOT_ACTIONABLE"
    if diagnosis in {
        "insufficient_event_volume",
        "segmented_geo_anomaly",
        "insufficient_evidence",
    }:
        return "INSUFFICIENT_EVIDENCE"
    if candidates:
        return candidates[0]["permission"]
    return "INSUFFICIENT_EVIDENCE"


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
    if any(
        not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
        for value in numeric_values
    ):
        return {
            "id": experiment.get("id"),
            "status": "INVALIDATED",
            "reasons": [
                "experiment review requires non-negative numeric maturity fields"
            ],
        }

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


def _build_experiment(
    case: dict[str, Any], candidate: dict[str, Any], diagnosis: str
) -> dict[str, Any]:
    policy = case["experiment_policy"]
    variable = candidate["variable"]
    treatment = {
        "creative": "paid_value_prefilter_creative",
        "bid": "evidence_based_relaxed_target",
        "budget": "evidence_based_learning_budget",
    }[variable]
    primary_metric = policy["primary_metric"]
    return {
        "id": policy.get("id", "UAC-PROPOSED-001"),
        "platform": "google_ads",
        "campaign_type": "app_campaign",
        "status": "proposed",
        "problem": {
            "symptom": diagnosis,
            "evidence": deepcopy(case.get("evidence", [])),
            "confidence": policy.get("confidence", "medium"),
        },
        "hypothesis": {
            "statement": policy["hypothesis"],
            "falsifiable": True,
        },
        "permission": {"classification": candidate["permission"]},
        "variable": {
            "type": variable,
            "single_variable_change": True,
            "control_definition": policy["control_definition"],
            "treatment_definition": policy.get("treatment_definition", treatment),
        },
        "baseline": deepcopy(policy["baseline"]),
        "observation": {
            "minimum_days": policy["minimum_days"],
            "minimum_conversions": policy["minimum_conversions"],
            "conversion_delay_days": policy["conversion_delay_days"],
            "maturity_rule": policy["maturity_rule"],
        },
        "primary_metric": deepcopy(primary_metric),
        "secondary_metrics": deepcopy(policy.get("secondary_metrics", [])),
        "guardrail_metrics": deepcopy(policy["guardrail_metrics"]),
        "success_rule": policy["success_rule"],
        "rollback_rule": policy["rollback_rule"],
        "inconclusive_rule": policy["inconclusive_rule"],
        "execution": {"approved": False, "executed_at": None, "notes": ""},
        "result": {
            "status": "pending",
            "metrics": {},
            "confounders": [],
            "evidence_quality": None,
        },
        "decision": {"outcome": "pending", "next_action": None, "learning": None},
    }


def validate_experiment(experiment: dict[str, Any]) -> list[str]:
    if not isinstance(experiment, dict):
        return ["experiment must be an object"]
    errors: list[str] = []

    def nonempty(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    if not nonempty(experiment.get("id")):
        errors.append("id must be a non-empty string")
    if experiment.get("platform") != "google_ads":
        errors.append("platform must be google_ads")
    if experiment.get("campaign_type") != "app_campaign":
        errors.append("campaign_type must be app_campaign")
    if experiment.get("status") not in EXPERIMENT_STATUSES:
        errors.append("status is invalid")

    problem = experiment.get("problem")
    if not isinstance(problem, dict):
        errors.append("problem must be an object")
        problem = {}
    if not nonempty(problem.get("symptom")):
        errors.append("problem.symptom must be a non-empty string")
    problem_evidence = problem.get("evidence")
    if not isinstance(problem_evidence, list) or not problem_evidence:
        errors.append("problem.evidence must be a non-empty array")
    elif not all(isinstance(item, dict) for item in problem_evidence):
        errors.append("problem.evidence items must be objects")
    else:
        for index, item in enumerate(problem_evidence):
            for field in ("id", "observation", "source_kind"):
                if not nonempty(item.get(field)):
                    errors.append(
                        f"problem.evidence[{index}].{field} must be a non-empty string"
                    )
    if problem.get("confidence") not in {"low", "medium", "high"}:
        errors.append("problem.confidence is invalid")

    hypothesis = experiment.get("hypothesis")
    if not isinstance(hypothesis, dict):
        errors.append("hypothesis must be an object")
        hypothesis = {}
    if not nonempty(hypothesis.get("statement")):
        errors.append("hypothesis.statement must be a non-empty string")
    if hypothesis.get("falsifiable") is not True:
        errors.append("hypothesis.falsifiable must be true")

    permission = experiment.get("permission")
    if not isinstance(permission, dict):
        errors.append("permission must be an object")
        permission = {}
    if permission.get("classification") not in PERMISSION_CLASSES:
        errors.append("permission.classification is invalid")

    variable = experiment.get("variable")
    if not isinstance(variable, dict):
        errors.append("variable must be an object")
        variable = {}
    if variable.get("single_variable_change") is not True:
        errors.append("variable.single_variable_change must be true")
    for field in ("type", "control_definition", "treatment_definition"):
        if not nonempty(variable.get(field)):
            errors.append(f"variable.{field} must be a non-empty string")

    if not isinstance(experiment.get("baseline"), dict):
        errors.append("baseline must be an object")
    observation = experiment.get("observation")
    if not isinstance(observation, dict):
        errors.append("observation must be an object")
        observation = {}
    for field in ("minimum_days", "minimum_conversions", "conversion_delay_days"):
        value = observation.get(field)
        minimum = 0 if field == "conversion_delay_days" else 1
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < minimum
        ):
            errors.append(f"observation.{field} must be a number >= {minimum}")
    if not nonempty(observation.get("maturity_rule")):
        errors.append("observation.maturity_rule must be a non-empty string")

    primary_metric = experiment.get("primary_metric")
    if not isinstance(primary_metric, dict):
        errors.append("primary_metric must be an object")
        primary_metric = {}
    if not nonempty(primary_metric.get("name")):
        errors.append("primary_metric.name must be a non-empty string")
    if primary_metric.get("direction") not in {
        "increase",
        "decrease",
        "maintain",
        "within_range",
    }:
        errors.append("primary_metric.direction is invalid")
    secondary_metrics = experiment.get("secondary_metrics", [])
    if not isinstance(secondary_metrics, list) or not all(
        nonempty(item) for item in secondary_metrics
    ):
        errors.append("secondary_metrics must be an array of non-empty strings")
    guardrails = experiment.get("guardrail_metrics")
    if (
        not isinstance(guardrails, list)
        or not guardrails
        or not all(nonempty(item) for item in guardrails)
    ):
        errors.append("guardrail_metrics must be a non-empty array of strings")
    for field in ("success_rule", "rollback_rule", "inconclusive_rule"):
        if not nonempty(experiment.get(field)):
            errors.append(f"{field} must be a non-empty string")

    execution = experiment.get("execution")
    if not isinstance(execution, dict):
        errors.append("execution must be an object")
        execution = {}
    if not isinstance(execution.get("approved"), bool):
        errors.append("execution.approved must be boolean")
    result = experiment.get("result")
    if not isinstance(result, dict):
        errors.append("result must be an object")
        result = {}
    if result.get("status") not in {"pending", *EXPERIMENT_RESULTS}:
        errors.append("result.status is invalid")
    result_metrics = result.get("metrics")
    if not isinstance(result_metrics, dict):
        errors.append("result.metrics must be an object")
        result_metrics = {}
    confounders = result.get("confounders", [])
    if not isinstance(confounders, list) or not all(
        nonempty(item) for item in confounders
    ):
        errors.append("result.confounders must be an array of non-empty strings")
    evidence_quality = result.get("evidence_quality")
    if evidence_quality not in {None, *EVIDENCE_QUALITY_STATES}:
        errors.append("result.evidence_quality is invalid")
    if result.get("evaluation") not in {
        None,
        "success",
        "failure",
        "inconclusive",
        "invalidated",
    }:
        errors.append("result.evaluation is invalid")
    rule_evaluation = result.get("rule_evaluation")
    if rule_evaluation is not None:
        if not isinstance(rule_evaluation, dict):
            errors.append("result.rule_evaluation must be an object")
        else:
            fields = (
                "success_rule_met",
                "rollback_rule_met",
                "inconclusive_rule_met",
                "invalidated",
            )
            if any(
                rule_evaluation.get(field) is not None
                and not isinstance(rule_evaluation.get(field), bool)
                for field in fields
            ):
                errors.append("result.rule_evaluation values must be boolean or null")
            if sum(rule_evaluation.get(field) is True for field in fields) > 1:
                errors.append("only one result.rule_evaluation outcome may be true")
    if result.get("evaluation") is not None and isinstance(rule_evaluation, dict):
        errors.append(
            "result.evaluation and result.rule_evaluation are mutually exclusive"
        )

    status = experiment.get("status")
    result_status = result.get("status")
    executed_at = execution.get("executed_at")
    statuses_requiring_snapshot = {"running", "observing", "completed", "stopped"}
    snapshot = result.get("review_snapshot")
    if status in statuses_requiring_snapshot or snapshot is not None:
        if not isinstance(snapshot, dict):
            errors.append(f"{status} experiment requires result.review_snapshot")
        else:
            for field in ("days_elapsed", "conversions_observed"):
                value = snapshot.get(field)
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or value < 0
                ):
                    errors.append(
                        f"result.review_snapshot.{field} must be a non-negative number"
                    )
            for field in ("conversion_delay_mature", "guardrail_breached"):
                if not isinstance(snapshot.get(field), bool):
                    errors.append(f"result.review_snapshot.{field} must be boolean")
            changes = snapshot.get("concurrent_changes")
            if (
                not isinstance(changes, list)
                or not changes
                or not all(nonempty(item) for item in changes)
            ):
                errors.append(
                    "result.review_snapshot.concurrent_changes must be a non-empty array of variable names"
                )

    if status == "proposed":
        if (
            execution.get("approved") is not False
            or executed_at is not None
            and executed_at != ""
        ):
            errors.append("proposed experiment must be unapproved and unexecuted")
    elif status == "approved":
        if (
            execution.get("approved") is not True
            or executed_at is not None
            and executed_at != ""
        ):
            errors.append("approved experiment must be approved but not yet executed")
    elif status == "cancelled":
        if (
            execution.get("approved") is not False
            or executed_at is not None
            and executed_at != ""
        ):
            errors.append("cancelled experiment must be unapproved and unexecuted")
    elif status in statuses_requiring_snapshot:
        if execution.get("approved") is not True:
            errors.append(f"{status} experiment must be approved")
        if not nonempty(executed_at):
            errors.append(f"{status} experiment requires execution.executed_at")

    if status in {"proposed", "approved", "running", "observing"}:
        if result_status != "pending":
            errors.append(f"{status} experiment result.status must be pending")
    elif status == "cancelled":
        if result_status != "INVALIDATED":
            errors.append("cancelled experiment result.status must be INVALIDATED")
        if evidence_quality != "not_executed":
            errors.append(
                "cancelled experiment result.evidence_quality must be not_executed"
            )
    elif status in {"completed", "stopped"}:
        if result_status not in TERMINAL_EXPERIMENT_RESULTS:
            errors.append(f"{status} experiment requires a terminal result.status")
        elif review_experiment(experiment).get("status") != result_status:
            errors.append(
                f"{status} experiment result.status conflicts with its maturity, guardrail, confounder, or rule evidence"
            )
        if result_status in {"WIN", "LOSS"}:
            has_legacy_evaluation = result.get("evaluation") in {
                "success",
                "failure",
            }
            has_rule_evaluation = isinstance(rule_evaluation, dict) and any(
                rule_evaluation.get(field) is True
                for field in ("success_rule_met", "rollback_rule_met")
            )
            if not has_legacy_evaluation and not has_rule_evaluation:
                errors.append(
                    f"{result_status} requires an explicit predeclared rule evaluation"
                )
        if result_status == "CONFOUNDED" and not confounders:
            errors.append("CONFOUNDED result requires result.confounders")
        terminal_quality_states = {
            "platform_only",
            "account_specific",
            "reconciled",
            "insufficient",
        }
        if evidence_quality not in terminal_quality_states:
            errors.append(
                f"{status} experiment requires terminal result.evidence_quality"
            )
        if result_status in {"WIN", "LOSS"} and not result_metrics:
            errors.append(f"{result_status} requires non-empty result.metrics")
        if result_status in {"WIN", "LOSS"} and evidence_quality == "insufficient":
            errors.append(
                f"{result_status} cannot use insufficient result.evidence_quality"
            )

    decision = experiment.get("decision")
    if not isinstance(decision, dict):
        errors.append("decision must be an object")
        decision = {}
    outcome = decision.get("outcome")
    next_action = decision.get("next_action")
    if not nonempty(outcome):
        errors.append("decision.outcome must be a non-empty string")
    if next_action is not None and not nonempty(next_action):
        errors.append("decision.next_action must be null or a non-empty string")
    if status in {"proposed", "approved", "running", "observing"}:
        if outcome != "pending":
            errors.append(f"{status} experiment decision.outcome must be pending")
    elif status in {"completed", "stopped"}:
        if outcome != result_status:
            errors.append(
                f"{status} experiment decision.outcome must equal result.status"
            )
        if not nonempty(next_action):
            errors.append(f"{status} experiment requires decision.next_action")
    elif status == "cancelled":
        if outcome != "CANCELLED":
            errors.append("cancelled experiment decision.outcome must be CANCELLED")
        if not nonempty(next_action):
            errors.append(f"{status} experiment requires decision.next_action")
    learning = decision.get("learning")
    if learning is not None:
        if not isinstance(learning, dict):
            errors.append("decision.learning must be an object or null")
        else:
            if learning.get("scope") not in LEARNING_SCOPES:
                errors.append("decision.learning.scope is invalid")
            if not nonempty(learning.get("statement")):
                errors.append("decision.learning.statement must be a non-empty string")
            learning_evidence = learning.get("evidence", [])
            if (
                not isinstance(learning_evidence, list)
                or not learning_evidence
                or not all(nonempty(item) for item in learning_evidence)
            ):
                errors.append(
                    "decision.learning.evidence must be a non-empty array of evidence ids"
                )
            if (
                result_status in {"INCONCLUSIVE", "INVALIDATED", "CONFOUNDED"}
                and learning.get("scope") == "reusable_heuristic"
            ):
                errors.append(
                    "inconclusive, invalidated, or confounded results cannot publish a reusable_heuristic"
                )
    return errors


def validate_ledger(ledger: dict[str, Any]) -> list[str]:
    if not isinstance(ledger, dict):
        return ["ledger must be an object"]
    errors: list[str] = []
    if ledger.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    if "project" in ledger and not isinstance(ledger["project"], dict):
        errors.append("project must be an object")
    experiments = ledger.get("experiments")
    if not isinstance(experiments, list):
        return errors + ["experiments must be an array"]
    seen: set[str] = set()
    for index, experiment in enumerate(experiments):
        if not isinstance(experiment, dict):
            errors.append(f"experiments[{index}] must be an object")
            continue
        experiment_id = experiment.get("id")
        if experiment_id in seen:
            errors.append(f"duplicate experiment id: {experiment_id}")
        seen.add(experiment_id)
        errors.extend(
            f"experiments[{index}].{error}" for error in validate_experiment(experiment)
        )
    return errors


def _ledger_context(
    ledger: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not ledger:
        return [], []
    errors = validate_ledger(ledger)
    if errors:
        raise ContractError("invalid experiment ledger: " + "; ".join(errors))
    reviews: list[dict[str, Any]] = []
    learnings: list[dict[str, Any]] = []
    for item in ledger["experiments"]:
        status = item["status"]
        if status == "proposed":
            review = {
                "id": item["id"],
                "status": "PROPOSED_NOT_EXECUTED",
                "reasons": ["proposal is not approved or executed"],
                "active": False,
            }
        elif status == "approved" and not item.get("execution", {}).get("executed_at"):
            review = {
                "id": item["id"],
                "status": "APPROVED_NOT_EXECUTED",
                "reasons": ["experiment is approved but execution is not recorded"],
                "active": False,
            }
        elif status == "cancelled":
            review = {
                "id": item["id"],
                "status": "CANCELLED_NOT_EXECUTED",
                "reasons": ["proposal was explicitly cancelled before execution"],
                "active": False,
            }
        else:
            review = review_experiment(item)
            review["active"] = status in {"running", "observing"}
        reviews.append(review)

        learning = item.get("decision", {}).get("learning")
        terminal_learning = status in {"completed", "stopped"} and review["status"] in {
            "WIN",
            "LOSS",
            "INCONCLUSIVE",
            "INVALIDATED",
            "STOPPED_FOR_GUARDRAIL",
            "CONFOUNDED",
        }
        if terminal_learning and isinstance(learning, dict):
            learnings.append(
                {
                    "experiment_id": item["id"],
                    "scope": learning["scope"],
                    "statement": learning["statement"],
                    "evidence": deepcopy(learning.get("evidence", [])),
                }
            )
    return reviews, learnings


def analyze_case(
    case: dict[str, Any], ledger: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Analyze one UAC case using only supplied facts and declared rules."""
    _validate_case(case)
    evidence = case.get("evidence")
    if not isinstance(evidence, list):
        raise ContractError("evidence must be an array")

    measurement_state, measurement_reasons = _measurement_state(case)
    goal_assessment = _goal_assessment(case, measurement_state)
    funnel_state = _funnel_state(case)
    mature, maturity_reasons = _maturity(case)
    learning_state, learning_reasons = _learning_state(
        case, measurement_state, mature, maturity_reasons
    )
    diagnosis = _primary_diagnosis(case, measurement_state, learning_state)
    candidates = _action_candidates(case, diagnosis)
    ledger_reviews, prior_learnings = _ledger_context(ledger)
    scope = case["scope"]
    missing_scope_context = [
        f"scope.{field}"
        for field in ("start_date", "end_date", "timezone")
        if not isinstance(scope.get(field), str) or not scope[field].strip()
    ]
    scope_ready = not missing_scope_context
    segmentation_ready = case.get("facts", {}).get("segmentation_complete") is True

    active_experiment = case.get("active_experiment")
    if active_experiment:
        review = review_experiment(active_experiment)
        review["active"] = True
        ledger_reviews.append(review)
    confounded = diagnosis == "experiment_confounded" or any(
        review["status"] == "CONFOUNDED" and review.get("active", True)
        for review in ledger_reviews
    )
    unresolved_active = any(review.get("active", True) for review in ledger_reviews)
    pending_unexecuted = any(
        review["status"] in {"PROPOSED_NOT_EXECUTED", "APPROVED_NOT_EXECUTED"}
        for review in ledger_reviews
    )

    policy_candidate = next(
        (item for item in candidates if item["kind"] == "experiment"), None
    )
    experiment_candidate = (
        policy_candidate
        if policy_candidate
        and policy_candidate["permission"] == "OPTIMIZER_CAN_EXECUTE"
        else None
    )
    policy = case.get("experiment_policy")
    policy_errors = _experiment_policy_errors(policy)
    existing_experiment_ids = {
        item.get("id")
        for item in (ledger or {}).get("experiments", [])
        if isinstance(item, dict)
    }
    if (
        isinstance(policy, dict)
        and policy.get("id")
        and policy["id"] in existing_experiment_ids
    ):
        policy_errors.append(
            "experiment_policy.id already exists in the ledger; use a new unique id"
        )
    policy_ready = not policy_errors
    goal_ready = goal_assessment["alignment"] == "aligned" or (
        goal_assessment["alignment"] == "optimization_event_too_shallow"
        and goal_assessment["proxy_quality"] == "supported_proxy"
    )
    can_create = bool(
        experiment_candidate
        and policy_ready
        and evidence
        and scope_ready
        and segmentation_ready
        and measurement_state == "measurement_reliable"
        and goal_ready
        and mature
        and not confounded
        and not unresolved_active
        and not pending_unexecuted
    )
    experiment = (
        _build_experiment(case, experiment_candidate, diagnosis) if can_create else None
    )
    if experiment:
        errors = validate_experiment(experiment)
        if errors:
            raise ContractError("generated experiment is invalid: " + "; ".join(errors))

    if diagnosis in {"measurement_mismatch", "ios_measurement_anomaly"}:
        feasibility = "TRACKING_BLOCKED"
    elif measurement_state in {"measurement_uncertain", "insufficient_evidence"}:
        feasibility = "DATA_BLOCKED"
    elif not evidence or not scope_ready or not segmentation_ready:
        feasibility = "DATA_BLOCKED"
    elif learning_state == "INSUFFICIENT_EVIDENCE" or not goal_ready:
        feasibility = "DATA_BLOCKED"
    elif confounded or unresolved_active:
        feasibility = "LEARNING_BLOCKED"
    elif pending_unexecuted:
        feasibility = "PERMISSION_BLOCKED"
    elif policy_candidate and not policy_ready:
        feasibility = "DATA_BLOCKED"
    elif policy_candidate and policy_candidate["permission"] != "OPTIMIZER_CAN_EXECUTE":
        feasibility = "PERMISSION_BLOCKED"
    elif (
        learning_state
        in {
            "INSUFFICIENT_EVENT_VOLUME",
            "CONVERSION_DELAY_NOT_MATURE",
            "BUDGET_CONSTRAINED",
        }
        and not can_create
    ):
        feasibility = "LEARNING_BLOCKED"
    elif diagnosis == "post_install_product_funnel_drop" and not can_create:
        feasibility = "PRODUCT_FUNNEL_BLOCKED"
    elif diagnosis == "no_material_anomaly":
        feasibility = "NO_ACTION_RECOMMENDED"
    elif (
        diagnosis in {"insufficient_evidence", "segmented_geo_anomaly"}
        and not can_create
    ):
        feasibility = "DATA_BLOCKED"
    elif can_create:
        feasibility = "EXPERIMENT_AVAILABLE"
    else:
        feasibility = "LIMITED_INCREMENT_AVAILABLE"

    recommendations = deepcopy(candidates)
    admission_blocked = bool(
        policy_candidate
        and (
            not policy_ready
            or not evidence
            or not scope_ready
            or not segmentation_ready
            or not goal_ready
            or measurement_state != "measurement_reliable"
            or not mature
            or confounded
            or unresolved_active
            or pending_unexecuted
        )
    )
    if admission_blocked:
        for item in recommendations:
            if item["kind"] != "experiment":
                continue
            if pending_unexecuted:
                item.update(
                    {
                        "action": "approve, reject, or close the existing proposal before creating another experiment",
                        "kind": "client_request",
                        "permission": "CLIENT_APPROVAL_REQUIRED",
                        "reason": "pending_experiment_decision",
                    }
                )
            elif not mature or unresolved_active:
                item.update(
                    {
                        "action": "review or close the current observation window before proposing another experiment",
                        "kind": "monitoring",
                        "permission": "NOT_ACTIONABLE",
                        "reason": "experiment_observation_blocked",
                    }
                )
            else:
                item.update(
                    {
                        "action": "complete experiment admission evidence and rules before proposing a test",
                        "kind": "investigation",
                        "permission": "INSUFFICIENT_EVIDENCE",
                        "reason": "experiment_admission_blocked",
                    }
                )

    do_not_touch = [
        "Do not change budget, bid target, and creative at the same time.",
        "Do not make pause or scale decisions from country totals alone.",
    ]
    if measurement_state != "measurement_reliable":
        do_not_touch.append(
            "Do not optimize toward payment until payment measurement is reliable."
        )
    if not mature:
        do_not_touch.append(
            "Do not declare a winner before observation and conversion-delay maturity."
        )
    if diagnosis == "no_material_anomaly":
        do_not_touch.append("Do not modify the account merely to create activity.")

    data_gaps = case.get("data_gaps", [])
    if measurement_state != "measurement_reliable":
        data_gaps = [*data_gaps, *measurement_reasons]
    if not goal_ready:
        data_gaps = [
            *data_gaps,
            "Optimization goal/event alignment lacks supporting evidence.",
        ]
    if policy_candidate and policy_candidate["permission"] == "OPTIMIZER_CAN_EXECUTE":
        data_gaps = [*data_gaps, *policy_errors]
    if not evidence:
        data_gaps = [*data_gaps, "No evidence items were supplied."]
    if missing_scope_context:
        data_gaps = [
            *data_gaps,
            "Missing analysis context: " + ", ".join(missing_scope_context),
        ]
    if not segmentation_ready:
        data_gaps = [*data_gaps, "无法在当前证据下完成该层级判断。"]
    if pending_unexecuted:
        data_gaps = [
            *data_gaps,
            "An existing proposal must be approved, rejected, or closed before another experiment is created.",
        ]

    result = {
        "schema_version": "1.0",
        "account_state": deepcopy(case.get("scope", {})),
        "optimization_goal": goal_assessment,
        "funnel_state": funnel_state,
        "measurement_state": {
            "status": measurement_state,
            "reasons": measurement_reasons,
        },
        "learning_eligibility": {
            "status": learning_state,
            "reasons": learning_reasons,
        },
        "optimization_feasibility": {
            "status": feasibility,
            "evidence": [item.get("id") for item in evidence if isinstance(item, dict)],
        },
        "evidence": deepcopy(evidence),
        "diagnoses": [
            {
                "code": diagnosis,
                "causal_claim": False,
                "permission_classification": _diagnosis_permission(
                    diagnosis, recommendations
                ),
            }
        ],
        "constraints": deepcopy(case.get("constraints", [])),
        "permissions": [
            {"variable": item["variable"], "classification": item["permission"]}
            for item in recommendations
        ],
        "recommendations": recommendations,
        "experiments": [experiment] if experiment else [],
        "experiment_reviews": ledger_reviews,
        "prior_learnings": prior_learnings,
        "client_dependencies": [
            item["action"]
            for item in recommendations
            if item["permission"]
            in {
                "CLIENT_APPROVAL_REQUIRED",
                "CLIENT_DATA_REQUIRED",
                "PRODUCT_DEPENDENCY",
                "TRACKING_DEPENDENCY",
            }
        ],
        "do_not_touch": do_not_touch,
        "confidence": {
            "level": case.get("confidence", "low" if data_gaps else "medium"),
            "data_gaps": data_gaps,
        },
        "next_review": {
            "when": case.get("next_review", {}).get(
                "when", "after declared maturity conditions"
            ),
            "required_inputs": case.get("next_review", {}).get("required_inputs", []),
        },
    }
    validate_analysis(result)
    return result


def validate_analysis(result: dict[str, Any]) -> None:
    errors: list[str] = []
    if result.get("measurement_state", {}).get("status") not in MEASUREMENT_STATES:
        errors.append("invalid measurement_state.status")
    if result.get("learning_eligibility", {}).get("status") not in LEARNING_STATES:
        errors.append("invalid learning_eligibility.status")
    if (
        result.get("optimization_feasibility", {}).get("status")
        not in FEASIBILITY_STATES
    ):
        errors.append("invalid optimization_feasibility.status")
    for item in result.get("permissions", []):
        if item.get("classification") not in PERMISSION_CLASSES:
            errors.append("invalid permission classification")
    for diagnosis in result.get("diagnoses", []):
        if diagnosis.get("permission_classification") not in PERMISSION_CLASSES:
            errors.append("invalid diagnosis permission classification")
    experiments = result.get("experiments", [])
    if len(experiments) > 1:
        errors.append("only one priority experiment may be proposed")
    for experiment in experiments:
        errors.extend(validate_experiment(experiment))
    if errors:
        raise ContractError("invalid analysis result: " + "; ".join(errors))


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


def _append_proposal(ledger: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    proposals = result.get("experiments", [])
    if not proposals:
        raise ContractError("analysis did not produce an experiment proposal")
    updated = deepcopy(ledger)
    updated.setdefault("schema_version", "1.0")
    updated.setdefault("project", {"name": "anonymized-uac-project"})
    updated.setdefault("experiments", [])
    if any(item.get("id") == proposals[0]["id"] for item in updated["experiments"]):
        raise ContractError(f"experiment id already exists: {proposals[0]['id']}")
    updated["experiments"].append(proposals[0])
    errors = validate_ledger(updated)
    if errors:
        raise ContractError("updated ledger is invalid: " + "; ".join(errors))
    return updated


def _append_to_ledger_path(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ContractError(f"ledger is locked by another process: {path}") from exc
    try:
        os.close(descriptor)
        current = (
            _load(path)
            if path.exists()
            else {"schema_version": "1.0", "experiments": []}
        )
        _dump(path, _append_proposal(current, result))
    finally:
        lock_path.unlink(missing_ok=True)


def _cancel_proposal_path(
    path: Path, experiment_id: str, reason: str, next_action: str
) -> None:
    if not reason.strip():
        raise ContractError("cancellation reason must be non-empty")
    if not next_action.strip():
        raise ContractError("cancellation next action must be non-empty")
    lock_path = path.with_name(f".{path.name}.lock")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ContractError(f"ledger is locked by another process: {path}") from exc
    try:
        os.close(descriptor)
        ledger = _load(path)
        errors = validate_ledger(ledger)
        if errors:
            raise ContractError("invalid experiment ledger: " + "; ".join(errors))
        matches = [
            item for item in ledger["experiments"] if item.get("id") == experiment_id
        ]
        if not matches:
            raise ContractError(f"experiment id not found: {experiment_id}")
        experiment = matches[0]
        if experiment.get("status") != "proposed":
            raise ContractError(
                "only an unexecuted proposed experiment can be cancelled"
            )
        experiment["status"] = "cancelled"
        experiment["execution"] = {
            "approved": False,
            "executed_at": None,
            "notes": reason,
        }
        experiment["result"].update(
            {
                "status": "INVALIDATED",
                "metrics": {},
                "confounders": [],
                "evidence_quality": "not_executed",
            }
        )
        experiment["result"].pop("evaluation", None)
        experiment["result"].pop("rule_evaluation", None)
        experiment["result"].pop("review_snapshot", None)
        experiment["decision"] = {
            "outcome": "CANCELLED",
            "next_action": next_action,
            "learning": None,
        }
        errors = validate_ledger(ledger)
        if errors:
            raise ContractError("cancelled ledger is invalid: " + "; ".join(errors))
        _dump(path, ledger)
    finally:
        lock_path.unlink(missing_ok=True)


def _discover_ledger(input_path: Path) -> Path | None:
    roots = (input_path.expanduser().resolve().parent, Path.cwd().resolve())
    candidates = {
        (root / name).resolve()
        for root in roots
        for name in (
            "ADS-EXPERIMENTS.yaml",
            "ADS-EXPERIMENTS.yml",
            "ADS-EXPERIMENTS.json",
        )
        if (root / name).is_file()
    }
    if len(candidates) > 1:
        paths = ", ".join(str(path) for path in sorted(candidates))
        raise ContractError(
            "multiple experiment ledgers were discovered; select one with --ledger: "
            + paths
        )
    return next(iter(candidates), None)


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="UAC Experiment Loop deterministic helper"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="analyze a UAC input file")
    analyze_parser.add_argument("input", type=Path)
    analyze_parser.add_argument("--ledger", type=Path)
    analyze_parser.add_argument("--json-output", type=Path)
    analyze_parser.add_argument("--markdown-output", type=Path)
    analyze_parser.add_argument(
        "--append-experiment",
        action="store_true",
        help="append only an unapproved proposed experiment to --ledger",
    )

    validate_parser = subparsers.add_parser(
        "validate-ledger", help="validate ADS-EXPERIMENTS"
    )
    validate_parser.add_argument("ledger", type=Path)

    review_parser = subparsers.add_parser(
        "review-ledger", help="review active ledger experiments"
    )
    review_parser.add_argument("ledger", type=Path)

    cancel_parser = subparsers.add_parser(
        "cancel-proposal", help="cancel one unexecuted local proposal"
    )
    cancel_parser.add_argument("ledger", type=Path)
    cancel_parser.add_argument("experiment_id")
    cancel_parser.add_argument("--reason", required=True)
    cancel_parser.add_argument(
        "--next-action",
        default="Reassess the account before proposing another experiment.",
    )

    args = parser.parse_args()
    try:
        if args.command == "validate-ledger":
            errors = validate_ledger(_load(args.ledger))
            if errors:
                raise ContractError("; ".join(errors))
            print(f"valid: {args.ledger}")
            return 0
        if args.command == "review-ledger":
            reviews, learnings = _ledger_context(_load(args.ledger))
            print(
                json.dumps(
                    {"reviews": reviews, "learnings": learnings},
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return 0
        if args.command == "cancel-proposal":
            _cancel_proposal_path(
                args.ledger, args.experiment_id, args.reason, args.next_action
            )
            print(f"cancelled: {args.experiment_id}")
            return 0

        if args.ledger is None:
            args.ledger = _discover_ledger(args.input)

        protected_paths = {args.input.expanduser().resolve()}
        if args.ledger:
            protected_paths.add(args.ledger.expanduser().resolve())
        output_paths = [
            path.expanduser().resolve()
            for path in (args.json_output, args.markdown_output)
            if path is not None
        ]
        if len(output_paths) != len(set(output_paths)):
            raise ContractError("JSON and Markdown output paths must be different")
        if any(path in protected_paths for path in output_paths):
            raise ContractError("output paths must not overwrite the input or ledger")

        case = _load(args.input)
        ledger = _load(args.ledger) if args.ledger and args.ledger.exists() else None
        result = analyze_case(case, ledger)
        if args.json_output:
            _dump(args.json_output, result)
        if args.markdown_output:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(render_markdown(result), encoding="utf-8")
        if args.append_experiment:
            if not args.ledger:
                raise ContractError("--append-experiment requires --ledger")
            _append_to_ledger_path(args.ledger, result)
        if not args.json_output and not args.markdown_output:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
