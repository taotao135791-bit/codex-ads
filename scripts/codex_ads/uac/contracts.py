"""Input, analysis, experiment, and ledger validation contracts."""

from __future__ import annotations

from datetime import date
import math
from typing import Any

from .review import review_experiment
from .types import (
    EVIDENCE_QUALITY_STATES,
    EXPERIMENT_RESULTS,
    EXPERIMENT_STATUSES,
    FEASIBILITY_STATES,
    LEARNING_SCOPES,
    LEARNING_STATES,
    MEASUREMENT_STATES,
    PERMISSION_CLASSES,
    SUPPORTED_LEDGER_SCHEMA_VERSIONS,
    TERMINAL_EXPERIMENT_RESULTS,
    ContractError,
)


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


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        try:
            return math.isfinite(float(value))
        except OverflowError:
            return False
    return isinstance(value, float) and math.isfinite(value)


def _non_finite_number_paths(value: Any, path: str) -> list[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [path]
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            paths.extend(_non_finite_number_paths(child, f"{path}.{key}"))
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            paths.extend(_non_finite_number_paths(child, f"{path}[{index}]"))
        return paths
    return []


def _is_number_at_least(value: Any, minimum: int | float) -> bool:
    if not _is_finite_number(value):
        return False
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return value >= minimum


def _is_allowed(value: Any, allowed: Any) -> bool:
    try:
        return value in allowed
    except TypeError:
        return False


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
        "campaign_level_glossary",
        "quick_ops",
    )
    for field in object_fields:
        if field in case and not isinstance(case[field], dict):
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
        if field in measurement and not _is_allowed(
            measurement[field],
            {
                "consistent",
                "material_mismatch",
                "unknown",
                None,
            },
        ):
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
        if field in learning and not _is_allowed(learning[field], allowed):
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
        if value is not None and not _is_number_at_least(value, 0):
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
        if value is not None and not _is_number_at_least(value, 0):
            raise ContractError(
                f"facts.metrics.{name} must be a non-negative number or null"
            )

    goal = case.get("goal", {})
    for field in ("business_goal", "optimization_event", "bidding_strategy"):
        if goal.get(field) is not None and not isinstance(goal[field], str):
            raise ContractError(f"goal.{field} must be a string or null")
    if not _is_allowed(
        goal.get("proxy_evidence"),
        {
            None,
            "unknown",
            "supported_by_mature_cohort",
            "contradicted_by_mature_cohort",
        },
    ):
        raise ContractError("goal.proxy_evidence has an invalid value")

    for field in (
        "target_cpa",
        "target_roas",
        "maximum_acceptable_cpa",
        "minimum_acceptable_roas",
        "daily_budget_cap",
    ):
        value = goal.get(field)
        if value is not None and not _is_number_at_least(value, 0):
            raise ContractError(f"goal.{field} must be a non-negative number")
    maximum_refund_rate = goal.get("maximum_acceptable_refund_rate")
    if maximum_refund_rate is not None and (
        not _is_number_at_least(maximum_refund_rate, 0) or maximum_refund_rate > 1
    ):
        raise ContractError(
            "goal.maximum_acceptable_refund_rate must be between 0 and 1"
        )
    if goal.get("optimization_priority") not in {
        None,
        "scale",
        "efficiency",
        "balanced",
    }:
        raise ContractError(
            "goal.optimization_priority must be scale, efficiency, or balanced"
        )

    for field in (
        "daily_budget",
        "minimum_daily_mature_events",
        "minimum_creative_installs",
    ):
        value = facts.get(field)
        if value is not None and not _is_number_at_least(value, 0):
            raise ContractError(f"facts.{field} must be a non-negative number")
    if facts.get("budget_limited") is not None and not isinstance(
        facts.get("budget_limited"), bool
    ):
        raise ContractError("facts.budget_limited must be boolean or null")

    daily_series = facts.get("daily_series", [])
    if not isinstance(daily_series, list):
        raise ContractError("facts.daily_series must be an array")
    daily_dates: list[str] = []
    for index, row in enumerate(daily_series):
        if not isinstance(row, dict):
            raise ContractError(f"facts.daily_series[{index}] must be an object")
        if not isinstance(row.get("date"), str):
            raise ContractError(f"facts.daily_series[{index}].date must be text")
        try:
            date.fromisoformat(row["date"])
        except ValueError as exc:
            raise ContractError(
                f"facts.daily_series[{index}].date must use YYYY-MM-DD"
            ) from exc
        daily_dates.append(row["date"])
        for field in ("spend", "mature_events", "value"):
            value = row.get(field)
            if value is not None and not _is_number_at_least(value, 0):
                raise ContractError(
                    f"facts.daily_series[{index}].{field} must be non-negative"
                )
    if len(daily_dates) != len(set(daily_dates)):
        raise ContractError("facts.daily_series dates must be unique")

    event_candidates = facts.get("event_candidates", [])
    if not isinstance(event_candidates, list):
        raise ContractError("facts.event_candidates must be an array")
    for index, candidate in enumerate(event_candidates):
        if not isinstance(candidate, dict):
            raise ContractError(f"facts.event_candidates[{index}] must be an object")
        if (
            not isinstance(candidate.get("event"), str)
            or not candidate["event"].strip()
        ):
            raise ContractError(
                f"facts.event_candidates[{index}].event must be non-empty text"
            )
        if candidate.get("reliable") is not None and not isinstance(
            candidate.get("reliable"), bool
        ):
            raise ContractError(
                f"facts.event_candidates[{index}].reliable must be boolean"
            )
        if candidate.get("too_shallow") is not None and not isinstance(
            candidate.get("too_shallow"), bool
        ):
            raise ContractError(
                f"facts.event_candidates[{index}].too_shallow must be boolean"
            )
        funnel_depth = candidate.get("funnel_depth")
        if funnel_depth is not None and (
            not _is_number_at_least(funnel_depth, 0) or funnel_depth > 1
        ):
            raise ContractError(
                f"facts.event_candidates[{index}].funnel_depth must be between 0 and 1"
            )
        for field in (
            "mature_events",
            "mature_payments",
            "median_payment_delay_days",
        ):
            value = candidate.get(field)
            if value is not None and not _is_number_at_least(value, 0):
                raise ContractError(
                    f"facts.event_candidates[{index}].{field} must be non-negative"
                )
        daily_candidate_events = candidate.get("daily_mature_events")
        if daily_candidate_events is not None and (
            not isinstance(daily_candidate_events, list)
            or len(daily_candidate_events) < 1
            or any(
                not _is_number_at_least(value, 0) for value in daily_candidate_events
            )
        ):
            raise ContractError(
                f"facts.event_candidates[{index}].daily_mature_events must be a non-empty array of non-negative numbers"
            )

    creative_cohorts = facts.get("creative_cohorts", [])
    if not isinstance(creative_cohorts, list):
        raise ContractError("facts.creative_cohorts must be an array")
    for index, cohort in enumerate(creative_cohorts):
        if not isinstance(cohort, dict):
            raise ContractError(f"facts.creative_cohorts[{index}] must be an object")
        if (
            not isinstance(cohort.get("creative"), str)
            or not cohort["creative"].strip()
        ):
            raise ContractError(
                f"facts.creative_cohorts[{index}].creative must be non-empty text"
            )
        if cohort.get("mature") is not None and not isinstance(
            cohort.get("mature"), bool
        ):
            raise ContractError(
                f"facts.creative_cohorts[{index}].mature must be boolean"
            )
        for field in (
            "spend",
            "installs",
            "registrations",
            "deep_events",
            "payments",
            "value",
        ):
            value = cohort.get(field)
            if value is not None and not _is_number_at_least(value, 0):
                raise ContractError(
                    f"facts.creative_cohorts[{index}].{field} must be non-negative"
                )
        prior_rate = cohort.get("prior_deep_event_rate")
        if prior_rate is not None and (
            not _is_number_at_least(prior_rate, 0) or prior_rate > 1
        ):
            raise ContractError(
                f"facts.creative_cohorts[{index}].prior_deep_event_rate must be between 0 and 1"
            )

    split_plan = facts.get("split_plan", {})
    if not isinstance(split_plan, dict):
        raise ContractError("facts.split_plan must be an object")
    for field in (
        "campaign_count",
        "minimum_daily_events_per_campaign",
        "minimum_mature_events_per_campaign",
        "minimum_daily_budget_per_campaign",
        "total_daily_budget",
        "existing_daily_budget_floor",
        "candidate_event_mature_events",
    ):
        value = split_plan.get(field)
        if value is not None and not _is_number_at_least(value, 0):
            raise ContractError(f"facts.split_plan.{field} must be non-negative")
    campaign_count = split_plan.get("campaign_count")
    if campaign_count is not None and (
        isinstance(campaign_count, bool)
        or not isinstance(campaign_count, int)
        or campaign_count < 2
    ):
        raise ContractError("facts.split_plan.campaign_count must be an integer >= 2")
    for field in ("existing_level", "candidate_level"):
        value = split_plan.get(field)
        if value is not None and value not in {"AC2.0", "AC2.5", "AC3.0"}:
            raise ContractError(
                f"facts.split_plan.{field} must be AC2.0, AC2.5, or AC3.0"
            )

    for field in (
        "days_since_last_change",
        "mature_events_since_change",
        "previous_target",
        "previous_daily_budget",
    ):
        value = maturity.get(field)
        if value is not None and not _is_number_at_least(value, 0):
            raise ContractError(f"maturity.{field} must be a non-negative number")
    if "last_change_at" in maturity:
        if not isinstance(maturity["last_change_at"], str):
            raise ContractError("maturity.last_change_at must be text")
        try:
            date.fromisoformat(maturity["last_change_at"])
        except ValueError as exc:
            raise ContractError("maturity.last_change_at must use YYYY-MM-DD") from exc
        if scope.get("end_date") and date.fromisoformat(
            maturity["last_change_at"]
        ) > date.fromisoformat(scope["end_date"]):
            raise ContractError(
                "maturity.last_change_at must not be after scope.end_date"
            )
    last_change_variables = maturity.get("last_change_variables", [])
    if not isinstance(last_change_variables, list) or not all(
        isinstance(item, str) and item.strip() for item in last_change_variables
    ):
        raise ContractError(
            "maturity.last_change_variables must be an array of non-empty strings"
        )

    for field in (
        "value_missing_rate",
        "currency_consistency_rate",
        "google_mmp_value_difference_rate",
        "mmp_backend_value_difference_rate",
        "refund_rate",
    ):
        value = measurement.get(field)
        if value is not None and (not _is_number_at_least(value, 0) or value > 1):
            raise ContractError(f"measurement.{field} must be between 0 and 1")
    if measurement.get("subscription_renewal_included") is not None and not isinstance(
        measurement.get("subscription_renewal_included"), bool
    ):
        raise ContractError(
            "measurement.subscription_renewal_included must be boolean or null"
        )


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
    if not _is_allowed(policy.get("confidence", "medium"), {"low", "medium", "high"}):
        errors.append("experiment_policy.confidence is invalid")
    for field in ("minimum_days", "minimum_conversions", "conversion_delay_days"):
        value = policy.get(field)
        minimum = 0 if field == "conversion_delay_days" else 1
        if not _is_number_at_least(value, minimum):
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
    elif not _is_allowed(
        primary_metric.get("direction"),
        {
            "increase",
            "decrease",
            "maintain",
            "within_range",
        },
    ):
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


def validate_experiment(experiment: Any) -> list[str]:
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
    raw_status = experiment.get("status")
    status = raw_status if isinstance(raw_status, str) else None
    if not _is_allowed(status, EXPERIMENT_STATUSES):
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
    if not _is_allowed(problem.get("confidence"), {"low", "medium", "high"}):
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
    if not _is_allowed(permission.get("classification"), PERMISSION_CLASSES):
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
        if not _is_number_at_least(value, minimum):
            errors.append(f"observation.{field} must be a number >= {minimum}")
    if not nonempty(observation.get("maturity_rule")):
        errors.append("observation.maturity_rule must be a non-empty string")

    primary_metric = experiment.get("primary_metric")
    if not isinstance(primary_metric, dict):
        errors.append("primary_metric must be an object")
        primary_metric = {}
    if not nonempty(primary_metric.get("name")):
        errors.append("primary_metric.name must be a non-empty string")
    if not _is_allowed(
        primary_metric.get("direction"),
        {
            "increase",
            "decrease",
            "maintain",
            "within_range",
        },
    ):
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
    raw_result_status = result.get("status")
    result_status = raw_result_status if isinstance(raw_result_status, str) else None
    if not _is_allowed(result_status, {"pending", *EXPERIMENT_RESULTS}):
        errors.append("result.status is invalid")
    result_metrics = result.get("metrics")
    if not isinstance(result_metrics, dict):
        errors.append("result.metrics must be an object")
        result_metrics = {}
    for name, value in result_metrics.items():
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(f"result.metrics.{name} must be finite")
    if "confounders" not in result:
        errors.append("result.confounders is required")
    confounders = result.get("confounders", [])
    if not isinstance(confounders, list) or not all(
        nonempty(item) for item in confounders
    ):
        errors.append("result.confounders must be an array of non-empty strings")
    if "evidence_quality" not in result:
        errors.append("result.evidence_quality is required")
    evidence_quality = result.get("evidence_quality")
    if not _is_allowed(evidence_quality, {None, *EVIDENCE_QUALITY_STATES}):
        errors.append("result.evidence_quality is invalid")
    evaluation = result.get("evaluation")
    if not _is_allowed(
        evaluation,
        {
            None,
            "success",
            "failure",
            "inconclusive",
            "invalidated",
        },
    ):
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

    executed_at = execution.get("executed_at")
    statuses_requiring_snapshot = {"running", "observing", "completed", "stopped"}
    snapshot = result.get("review_snapshot")
    if status in statuses_requiring_snapshot or snapshot is not None:
        if not isinstance(snapshot, dict):
            errors.append(f"{status} experiment requires result.review_snapshot")
        else:
            for field in ("days_elapsed", "conversions_observed"):
                value = snapshot.get(field)
                if not _is_number_at_least(value, 0):
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
        if execution.get("approved") is not False or executed_at is not None:
            errors.append("proposed experiment must be unapproved and unexecuted")
    elif status == "approved":
        if execution.get("approved") is not True or executed_at is not None:
            errors.append("approved experiment must be approved but not yet executed")
    elif status == "cancelled":
        if execution.get("approved") is not False or executed_at is not None:
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
            has_legacy_evaluation = _is_allowed(
                evaluation,
                {
                    "success",
                    "failure",
                },
            )
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
    if "next_action" not in decision:
        errors.append("decision.next_action is required")
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
            if not _is_allowed(learning.get("scope"), LEARNING_SCOPES):
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


def validate_ledger(ledger: Any) -> list[str]:
    if not isinstance(ledger, dict):
        return ["ledger must be an object"]
    errors = [
        f"non-finite number at {path}"
        for path in _non_finite_number_paths(ledger, "ledger")
    ]
    if not _is_allowed(ledger.get("schema_version"), SUPPORTED_LEDGER_SCHEMA_VERSIONS):
        supported = ", ".join(sorted(SUPPORTED_LEDGER_SCHEMA_VERSIONS))
        errors.append(f"schema_version must be one of: {supported}")
    if "project" in ledger and not isinstance(ledger["project"], dict):
        errors.append("project must be an object")
    experiments = ledger.get("experiments")
    if not isinstance(experiments, list):
        return errors + ["experiments must be an array"]
    seen: set[Any] = set()
    for index, experiment in enumerate(experiments):
        if not isinstance(experiment, dict):
            errors.append(f"experiments[{index}] must be an object")
            continue
        experiment_id = experiment.get("id")
        if isinstance(experiment_id, str):
            if experiment_id in seen:
                errors.append(f"duplicate experiment id: {experiment_id}")
            seen.add(experiment_id)
        errors.extend(
            f"experiments[{index}].{error}" for error in validate_experiment(experiment)
        )
    return errors


def validate_analysis(result: dict[str, Any]) -> None:
    errors = [
        f"non-finite number at {path}"
        for path in _non_finite_number_paths(result, "analysis")
    ]
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
