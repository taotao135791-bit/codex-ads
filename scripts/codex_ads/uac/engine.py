"""Deterministic UAC analysis and experiment-admission engine."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .contracts import (
    _experiment_policy_errors,
    _validate_case,
    validate_analysis,
    validate_experiment,
)
from .ledger import _ledger_context
from .review import review_experiment
from .types import ANALYSIS_SCHEMA_VERSION, ContractError


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
    invalid_rate_inputs: list[str] = []
    for source_key, target_name, target_key in stages:
        source = metrics.get(source_key)
        target = metrics.get(target_key)
        if (
            isinstance(source, (int, float))
            and source > 0
            and isinstance(target, (int, float))
        ):
            rate = target / source
            drop = 1 - rate
            if not math.isfinite(rate) or not math.isfinite(drop):
                invalid_rate_inputs.append(f"{source_key}->{target_key}")
                continue
            rates.append(
                {
                    "from": source_key,
                    "to": target_name,
                    "rate": rate,
                    "drop": drop,
                }
            )
    largest = max(rates, key=lambda item: item["drop"], default=None)
    funnel_state: dict[str, Any] = {
        "observed_rates": rates,
        "largest_observed_drop": largest,
        "causal_attribution": "undetermined",
        "note": "A funnel drop is not attributed to media, creative, or product without evidence.",
    }
    if invalid_rate_inputs:
        funnel_state["invalid_rate_inputs"] = invalid_rate_inputs
    return funnel_state


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
    if can_create:
        assert experiment_candidate is not None
        experiment = _build_experiment(case, experiment_candidate, diagnosis)
    else:
        experiment = None
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
    if funnel_state.get("invalid_rate_inputs"):
        data_gaps = [
            *data_gaps,
            "Funnel rates were omitted because supplied stage values overflowed: "
            + ", ".join(funnel_state["invalid_rate_inputs"]),
        ]
    if pending_unexecuted:
        data_gaps = [
            *data_gaps,
            "An existing proposal must be approved, rejected, or closed before another experiment is created.",
        ]

    result = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
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
