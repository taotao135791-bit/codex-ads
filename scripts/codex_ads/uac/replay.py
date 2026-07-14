"""Local, anonymization-aware replay evaluation for historical UAC cases."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .engine import analyze_case
from .io import _load
from .models import FeasibilityState, RateMetric
from .quick_ops import decide_case
from .types import FEASIBILITY_STATES, ContractError


REPLAY_FILES = (
    "snapshot-before.yaml",
    "system-recommendation.yaml",
    "human-decision.yaml",
    "actual-action.yaml",
    "snapshot-after.yaml",
    "evaluation.yaml",
)

LEGACY_REPLAY_FILES = (
    "snapshot-before.yaml",
    "decision-at-the-time.yaml",
    "actual-action.yaml",
    "snapshot-after.yaml",
    "evaluation.yaml",
)

_BLOCKING_FEASIBILITY = {
    FeasibilityState.DATA_BLOCKED.value,
    FeasibilityState.PERMISSION_BLOCKED.value,
    FeasibilityState.TRACKING_BLOCKED.value,
    FeasibilityState.PRODUCT_FUNNEL_BLOCKED.value,
    FeasibilityState.LEARNING_BLOCKED.value,
    FeasibilityState.NO_ACTION_RECOMMENDED.value,
}

REPLAY_DISCLAIMERS = [
    "Replay metrics are retrospective workflow diagnostics, not causal proof.",
    "Small samples cannot support platform-wide or account-independent conclusions.",
    "Account-specific outcomes may improve this project but do not become global rules automatically.",
    "A recommendation that a human did not execute is neither a system success nor a system failure.",
    "Confounded experiments never enter positive or negative effect rates.",
    "Numeric direction and magnitude exclude rejected, unexecuted, immature, deviated, or confounded cases.",
    "A replay never authorizes an advertising-account change.",
]

_NUMERIC_DIRECTIONS = {"INCREASE", "DECREASE", "NO_CHANGE"}
_NUMERIC_ACTIONS = _NUMERIC_DIRECTIONS | {"WAIT", "ROLLBACK"}
_NUMERIC_COMPONENTS = {
    "target": (
        "target_recommendation",
        "current_value",
        "recommended_value",
        "recommended_action",
        "bid_decision",
    ),
    "budget": (
        "budget_recommendation",
        "current_daily_budget",
        "recommended_value",
        "recommended_action",
        "budget_decision",
    ),
}


def _require_bool(document: dict[str, Any], field: str) -> bool:
    value = document.get(field)
    if not isinstance(value, bool):
        raise ContractError(f"{field} must be boolean")
    return value


def _require_text(document: dict[str, Any], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")
    return value


def _non_negative_finite(value: Any, field: str) -> float:
    try:
        finite = math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        finite = False
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not finite
        or value < 0
    ):
        raise ContractError(f"{field} must be a finite non-negative number")
    return float(value)


def _positive_finite(value: Any, field: str) -> float:
    number = _non_negative_finite(value, field)
    if number <= 0:
        raise ContractError(f"{field} must be greater than zero")
    return number


def _optional_non_negative_finite(value: Any, field: str) -> float | None:
    if value is None:
        return None
    return _non_negative_finite(value, field)


def _numeric_ground_truth(before: dict[str, Any]) -> dict[str, Any] | None:
    """Validate the optional numeric replay label without changing legacy cases."""

    if "numeric_ground_truth" not in before:
        return None
    value = before["numeric_ground_truth"]
    if not isinstance(value, dict):
        raise ContractError(
            "snapshot-before.yaml numeric_ground_truth must be an object"
        )
    if not all(isinstance(key, str) and key for key in value):
        raise ContractError("numeric_ground_truth keys must be non-empty strings")
    allowed_root = {"target", "budget", "no_action_expected"}
    unknown_root = sorted(set(value) - allowed_root)
    if unknown_root:
        raise ContractError(
            "numeric_ground_truth contains unsupported fields: "
            + ", ".join(unknown_root)
        )
    declared_components = [
        component for component in _NUMERIC_COMPONENTS if component in value
    ]
    if not declared_components:
        raise ContractError("numeric_ground_truth must define target or budget")
    no_action_expected = value.get("no_action_expected")
    if not isinstance(no_action_expected, bool):
        raise ContractError("numeric_ground_truth.no_action_expected must be boolean")

    normalized: dict[str, Any] = {"no_action_expected": no_action_expected}
    allowed_component = {
        "expected_direction",
        "expected_value",
        "safe_to_recommend",
        "minimum_safe_value",
        "maximum_safe_value",
    }
    for component in declared_components:
        raw = value.get(component)
        field = f"numeric_ground_truth.{component}"
        if not isinstance(raw, dict):
            raise ContractError(f"{field} must be an object")
        if not all(isinstance(key, str) and key for key in raw):
            raise ContractError(f"{field} keys must be non-empty strings")
        unknown = sorted(set(raw) - allowed_component)
        if unknown:
            raise ContractError(
                f"{field} contains unsupported fields: " + ", ".join(unknown)
            )
        direction = raw.get("expected_direction")
        if direction not in _NUMERIC_DIRECTIONS:
            raise ContractError(
                f"{field}.expected_direction must be INCREASE, DECREASE, or NO_CHANGE"
            )
        safe = raw.get("safe_to_recommend")
        if not isinstance(safe, bool):
            raise ContractError(f"{field}.safe_to_recommend must be boolean")
        expected = _positive_finite(
            raw.get("expected_value"), f"{field}.expected_value"
        )
        minimum = _optional_non_negative_finite(
            raw.get("minimum_safe_value"), f"{field}.minimum_safe_value"
        )
        maximum = _optional_non_negative_finite(
            raw.get("maximum_safe_value"), f"{field}.maximum_safe_value"
        )
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ContractError(
                f"{field}.minimum_safe_value must not exceed maximum_safe_value"
            )
        if safe and minimum is not None and expected < minimum:
            raise ContractError(f"{field}.expected_value is below minimum_safe_value")
        if safe and maximum is not None and expected > maximum:
            raise ContractError(f"{field}.expected_value is above maximum_safe_value")
        if not safe and direction != "NO_CHANGE":
            raise ContractError(
                f"{field} must expect NO_CHANGE when safe_to_recommend=false"
            )
        if no_action_expected and (safe or direction != "NO_CHANGE"):
            raise ContractError(
                "numeric_ground_truth.no_action_expected=true requires every "
                "declared component to be unsafe to change and expect NO_CHANGE"
            )
        normalized[component] = {
            "expected_direction": direction,
            "expected_value": expected,
            "safe_to_recommend": safe,
            "minimum_safe_value": minimum,
            "maximum_safe_value": maximum,
        }
    return normalized


def _quick_numeric_recommendation(
    quick_decision: dict[str, Any], component: str
) -> dict[str, Any]:
    (
        section_name,
        current_field,
        recommended_field,
        action_field,
        execution_section_name,
    ) = _NUMERIC_COMPONENTS[component]
    section = quick_decision.get(section_name)
    if not isinstance(section, dict):
        raise ContractError(f"Quick Decision {section_name} must be an object")
    raw_action = section.get(action_field)
    if not isinstance(raw_action, str):
        raise ContractError(
            f"Quick Decision {section_name}.{action_field} must be text"
        )
    action = raw_action.upper()
    if action not in _NUMERIC_ACTIONS:
        raise ContractError(
            f"Quick Decision {section_name}.action must be INCREASE, DECREASE, "
            "NO_CHANGE, WAIT, or ROLLBACK"
        )
    current = _optional_non_negative_finite(
        section.get(current_field), f"Quick Decision {section_name}.{current_field}"
    )
    recommended = _optional_non_negative_finite(
        section.get(recommended_field),
        f"Quick Decision {section_name}.{recommended_field}",
    )
    if action == "ROLLBACK":
        if current is None or recommended is None:
            raise ContractError(
                f"Quick Decision {section_name} ROLLBACK requires current and recommended values"
            )
        if recommended > current:
            direction = "INCREASE"
        elif recommended < current:
            direction = "DECREASE"
        else:
            direction = "NO_CHANGE"
    else:
        direction = "NO_CHANGE" if action == "WAIT" else action
    if direction in {"INCREASE", "DECREASE"}:
        if current is None or recommended is None:
            raise ContractError(
                f"Quick Decision {section_name} numeric change requires current and recommended values"
            )
        if direction == "INCREASE" and recommended <= current:
            raise ContractError(
                f"Quick Decision {section_name} INCREASE conflicts with its values"
            )
        if direction == "DECREASE" and recommended >= current:
            raise ContractError(
                f"Quick Decision {section_name} DECREASE conflicts with its values"
            )
    elif (
        current is not None
        and recommended is not None
        and not math.isclose(current, recommended, rel_tol=1e-9, abs_tol=1e-9)
    ):
        raise ContractError(
            f"Quick Decision {section_name} NO_CHANGE conflicts with its values"
        )
    execution_section = quick_decision.get(execution_section_name)
    if not isinstance(execution_section, dict):
        raise ContractError(
            f"Quick Decision {execution_section_name} must be an object"
        )
    execution_action = execution_section.get("action")
    if not isinstance(execution_action, str):
        raise ContractError(
            f"Quick Decision {execution_section_name}.action must be text"
        )
    normalized_execution_action = execution_action.upper()
    if normalized_execution_action not in _NUMERIC_ACTIONS:
        raise ContractError(
            f"Quick Decision {execution_section_name}.action must be INCREASE, "
            "DECREASE, NO_CHANGE, WAIT, or ROLLBACK"
        )
    return {
        "direction": direction,
        "action": action,
        "execution_action": normalized_execution_action,
        "current_value": current,
        "recommended_value": recommended,
        "effective_value": recommended if recommended is not None else current,
    }


def _evaluate_numeric_replay(
    ground_truth: dict[str, Any],
    quick_decision: dict[str, Any],
    *,
    accepted_recommendation: bool | None,
    executed: bool,
    confounded: bool,
    deviated: bool,
    mature_result_available: bool,
    business_result_evaluable: bool,
) -> dict[str, Any]:
    system = {
        component: _quick_numeric_recommendation(quick_decision, component)
        for component in _NUMERIC_COMPONENTS
    }
    component_evaluations: dict[str, dict[str, Any]] = {}
    raw_direction_matches: list[bool] = []
    raw_magnitude_errors: list[float] = []
    unsafe_components: list[str] = []

    for component in (item for item in _NUMERIC_COMPONENTS if item in ground_truth):
        recommendation = system[component]
        label = ground_truth[component]
        current = recommendation["current_value"]
        effective = recommendation["effective_value"]
        expected = label["expected_value"]
        if current is None or effective is None:
            raise ContractError(
                f"numeric_ground_truth.{component} requires a current numeric account value"
            )
        expected_direction = label["expected_direction"]
        if expected_direction == "INCREASE" and expected <= current:
            raise ContractError(
                f"numeric_ground_truth.{component} INCREASE conflicts with expected_value"
            )
        if expected_direction == "DECREASE" and expected >= current:
            raise ContractError(
                f"numeric_ground_truth.{component} DECREASE conflicts with expected_value"
            )
        if expected_direction == "NO_CHANGE" and not math.isclose(
            expected, current, rel_tol=1e-9, abs_tol=1e-9
        ):
            raise ContractError(
                f"numeric_ground_truth.{component} NO_CHANGE conflicts with expected_value"
            )

        changes_value = recommendation["direction"] != "NO_CHANGE"
        below_minimum = bool(
            changes_value
            and label["minimum_safe_value"] is not None
            and effective < label["minimum_safe_value"]
        )
        above_maximum = bool(
            changes_value
            and label["maximum_safe_value"] is not None
            and effective > label["maximum_safe_value"]
        )
        unsafe = bool(
            changes_value
            and (not label["safe_to_recommend"] or below_minimum or above_maximum)
        )
        if unsafe:
            unsafe_components.append(component)
        direction_matches = recommendation["direction"] == expected_direction
        magnitude_error = abs(effective - expected) / expected * 100
        raw_direction_matches.append(direction_matches)
        raw_magnitude_errors.append(magnitude_error)
        component_evaluations[component] = {
            "expected_direction": expected_direction,
            "expected_value": expected,
            "safe_to_recommend": label["safe_to_recommend"],
            "direction_correct": (
                direction_matches if business_result_evaluable else None
            ),
            "absolute_percentage_error": (
                round(magnitude_error, 4) if business_result_evaluable else None
            ),
            "unsafe": unsafe,
        }

    any_numeric_change = any(
        item["direction"] != "NO_CHANGE" for item in system.values()
    )
    no_action_expected = ground_truth["no_action_expected"]
    no_action_correct = not any_numeric_change if no_action_expected else None
    unsafe_numeric = bool(
        unsafe_components or (no_action_expected and any_numeric_change)
    )
    direction_correct = (
        all(raw_direction_matches) if business_result_evaluable else None
    )
    magnitude_error = (
        sum(raw_magnitude_errors) / len(raw_magnitude_errors)
        if business_result_evaluable
        else None
    )
    return {
        "ground_truth_present": True,
        "system_recommendation": system,
        "human_decision": {
            "accepted_system_recommendation": accepted_recommendation,
        },
        "after": {
            "executed": executed,
            "confounded": confounded,
            "deviated": deviated,
            "mature_result_available": mature_result_available,
        },
        "evaluation": {
            "business_result_evaluable": business_result_evaluable,
            "direction_correct": direction_correct,
            "magnitude_error": (
                round(magnitude_error, 4) if magnitude_error is not None else None
            ),
            "unsafe_numeric_recommendation": unsafe_numeric,
            "unsafe_components": unsafe_components,
            "no_action_expected": no_action_expected,
            "no_action_correct": no_action_correct,
            "components": component_evaluations,
        },
        "ground_truth": ground_truth,
    }


def _string_list(document: dict[str, Any], field: str) -> list[str]:
    if field not in document:
        raise ContractError(f"{field} is required")
    value = document[field]
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ContractError(f"{field} must be an array of non-empty strings")
    return value


def _contains_finite_numeric_metric(value: Any, field: str) -> bool:
    """Validate nested metric values and report whether numeric evidence exists."""

    if isinstance(value, bool) or value is None or isinstance(value, str):
        return False
    if isinstance(value, (int, float)):
        try:
            finite = math.isfinite(float(value))
        except OverflowError:
            finite = False
        if not finite:
            raise ContractError(f"{field} must contain only finite numeric values")
        return True
    if isinstance(value, dict):
        contains_numeric = False
        for name, child in value.items():
            if not isinstance(name, str) or not name.strip():
                raise ContractError(f"{field} keys must be non-empty strings")
            contains_numeric = (
                _contains_finite_numeric_metric(child, f"{field}.{name}")
                or contains_numeric
            )
        return contains_numeric
    if isinstance(value, list):
        contains_numeric = False
        for index, child in enumerate(value):
            contains_numeric = (
                _contains_finite_numeric_metric(child, f"{field}[{index}]")
                or contains_numeric
            )
        return contains_numeric
    raise ContractError(f"{field} contains an unsupported metric value")


def _positive_policy_minimum_days(uac_input: dict[str, Any]) -> float | None:
    policy = uac_input.get("experiment_policy")
    if not isinstance(policy, dict):
        return None
    value = policy.get("minimum_days")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        finite = math.isfinite(float(value))
    except OverflowError:
        return None
    return float(value) if finite and value > 0 else None


def _load_replay(case_dir: Path) -> dict[str, dict[str, Any]]:
    if case_dir.is_symlink():
        raise ContractError("replay case directories must not be symbolic links")
    if not case_dir.is_dir():
        raise ContractError("replay path must be a directory")
    selected_files: tuple[str, ...]
    if all((case_dir / filename).is_file() for filename in REPLAY_FILES):
        selected_files = REPLAY_FILES
        contract = "six-stage"
    elif all((case_dir / filename).is_file() for filename in LEGACY_REPLAY_FILES):
        selected_files = LEGACY_REPLAY_FILES
        contract = "legacy-five-file"
    else:
        raise ContractError(
            "replay must contain either the six-stage contract or all legacy five files"
        )

    documents: dict[str, dict[str, Any]] = {}
    for filename in selected_files:
        path = case_dir / filename
        if path.is_symlink() or not path.is_file():
            raise ContractError(f"replay is missing a regular {filename}")
        document = _load(path)
        if document.get("schema_version") != "1.0":
            raise ContractError(f"{filename} schema_version must be 1.0")
        documents[filename] = document
    case_ids = {_require_text(document, "case_id") for document in documents.values()}
    if len(case_ids) != 1:
        raise ContractError("all replay documents must share one non-empty case_id")
    if contract == "six-stage":
        system_recommendation = documents["system-recommendation.yaml"]
        human_decision = documents["human-decision.yaml"]
        _require_text(system_recommendation, "recorded_at")
        _require_text(human_decision, "decided_at")
        _require_bool(human_decision, "accepted_system_recommendation")
        documents["decision-at-the-time.yaml"] = {
            **human_decision,
            "codex_ads": system_recommendation.get("codex_ads"),
        }
    return documents


def evaluate_replay(case_dir: Path) -> dict[str, Any]:
    """Re-run the deterministic decision and compare it with recorded action."""

    documents = _load_replay(case_dir)
    before = documents["snapshot-before.yaml"]
    recorded_decision = documents["decision-at-the-time.yaml"]
    action = documents["actual-action.yaml"]
    after = documents["snapshot-after.yaml"]
    evaluation = documents["evaluation.yaml"]

    _require_text(before, "captured_at")
    uac_input = before.get("uac_input")
    if not isinstance(uac_input, dict):
        raise ContractError("snapshot-before.yaml uac_input must be an object")
    numeric_ground_truth = _numeric_ground_truth(before)
    quick_decision: dict[str, Any] | None = None
    if numeric_ground_truth is not None:
        if not isinstance(uac_input.get("quick_ops"), dict):
            raise ContractError(
                "numeric_ground_truth requires snapshot-before.yaml uac_input.quick_ops"
            )
        quick_decision = decide_case(uac_input)
    analysis = analyze_case(uac_input)
    feasibility = analysis["optimization_feasibility"]["status"]
    generated_experiment = bool(analysis["experiments"])
    current_experiment_variables = sorted(
        {
            str(experiment.get("variable", {}).get("type"))
            for experiment in analysis["experiments"]
            if isinstance(experiment.get("variable"), dict)
            and isinstance(experiment["variable"].get("type"), str)
            and experiment["variable"]["type"].strip()
        }
    )
    current_recommended = sorted(
        {
            item["variable"]
            for item in analysis["recommendations"]
            if item.get("permission") == "OPTIMIZER_CAN_EXECUTE"
        }
    )

    decision_data = recorded_decision.get("codex_ads")
    if not isinstance(decision_data, dict):
        raise ContractError("recorded system recommendation must be an object")
    human_judgment = _require_text(recorded_decision, "human_judgment")
    accepted_recommendation = recorded_decision.get("accepted_system_recommendation")
    if accepted_recommendation is not None and not isinstance(
        accepted_recommendation, bool
    ):
        raise ContractError("accepted_system_recommendation must be boolean")
    recorded_version = _require_text(decision_data, "version")
    recorded_feasibility = decision_data.get("feasibility")
    if recorded_feasibility not in FEASIBILITY_STATES:
        raise ContractError("codex_ads.feasibility is invalid")
    recorded_confidence = decision_data.get("confidence")
    if recorded_confidence not in {"low", "medium", "high"}:
        raise ContractError("codex_ads.confidence is invalid")
    recorded_data_gaps = _string_list(decision_data, "data_gaps")
    recorded_recommended = _string_list(decision_data, "recommended_variables")
    protected = _string_list(decision_data, "protected_variables")
    recorded_created = _require_bool(decision_data, "created_experiment")

    executed = _require_bool(action, "executed")
    approved_by_role = _require_text(action, "approved_by_role")
    executed_at = action.get("executed_at")
    if executed:
        if not isinstance(executed_at, str) or not executed_at.strip():
            raise ContractError("executed_at must be recorded for an executed action")
    elif executed_at is not None and executed_at != "":
        raise ContractError("executed_at must be null when no action was executed")
    actual_variables = _string_list(action, "variables_changed")
    concurrent_changes = _string_list(action, "concurrent_changes")
    reported_deviation = _require_bool(action, "deviated_from_recommendation")
    action_rollback = _require_bool(action, "rollback_performed")

    correct_block_label = _require_bool(evaluation, "correct_block")
    executable_label = _require_bool(evaluation, "recommendation_executable")
    single_variable_label = _require_bool(evaluation, "single_variable_compliant")
    experiment_completed = _require_bool(evaluation, "experiment_completed")
    observation_conditions_met = _require_bool(evaluation, "observation_conditions_met")
    conclusive_label = _require_bool(evaluation, "conclusive")
    evaluation_rollback = _require_bool(evaluation, "rollback_performed")
    insufficient_label = _require_bool(evaluation, "insufficient_evidence")
    _require_text(evaluation, "human_rating")
    if evaluation.get("causal_claim") is not False:
        raise ContractError("evaluation.yaml causal_claim must be false")

    _require_text(after, "captured_at")
    observation_days = _non_negative_finite(
        after.get("observation_days"), "observation_days"
    )
    after_metrics = after.get("metrics")
    if not isinstance(after_metrics, dict):
        raise ContractError("snapshot-after.yaml metrics must be an object")
    has_numeric_after_metric = _contains_finite_numeric_metric(
        after_metrics, "snapshot-after.yaml metrics"
    )
    _require_bool(after, "backend_data_available")
    confounders = _string_list(after, "confounders")
    delay_mature = _require_bool(after, "conversion_delay_mature")
    volume_mature = _require_bool(after, "minimum_conversions_met")
    outcome = evaluation.get("outcome")
    if outcome not in {"positive", "negative", "inconclusive", "not_executed"}:
        raise ContractError(
            "evaluation.yaml outcome must be positive, negative, inconclusive, or not_executed"
        )
    time_saved = _non_negative_finite(
        evaluation.get("time_saved_minutes"), "evaluation.yaml time_saved_minutes"
    )

    if not executed and (actual_variables or concurrent_changes or action_rollback):
        raise ContractError(
            "an unexecuted action cannot record changed variables, concurrent changes, or rollback"
        )
    if not executed and experiment_completed:
        raise ContractError("an unexecuted action cannot be a completed experiment")
    if executed and outcome == "not_executed":
        raise ContractError("an executed action cannot have outcome=not_executed")
    if not executed and outcome != "not_executed":
        raise ContractError("an unexecuted action requires outcome=not_executed")
    if conclusive_label and not experiment_completed:
        raise ContractError("a conclusive evaluation must be a completed experiment")
    if outcome in {"positive", "negative"} and not conclusive_label:
        raise ContractError(
            "positive or negative outcome requires a conclusive evaluation"
        )
    if conclusive_label and outcome not in {"positive", "negative"}:
        raise ContractError(
            "a conclusive evaluation requires a positive or negative outcome"
        )
    if conclusive_label and not observation_conditions_met:
        raise ContractError(
            "a conclusive evaluation requires observation_conditions_met=true"
        )
    if observation_conditions_met and not (delay_mature and volume_mature):
        raise ContractError(
            "observation_conditions_met=true requires mature delay and conversion volume"
        )
    requires_outcome_evidence = conclusive_label or outcome in {"positive", "negative"}
    if requires_outcome_evidence and not has_numeric_after_metric:
        raise ContractError(
            "a conclusive or positive/negative outcome requires at least one finite numeric after-metric"
        )
    minimum_observation_days = _positive_policy_minimum_days(uac_input)
    if (
        observation_conditions_met
        and minimum_observation_days is not None
        and observation_days < minimum_observation_days
    ):
        raise ContractError(
            "observation_conditions_met=true conflicts with experiment_policy.minimum_days"
        )
    if action_rollback != evaluation_rollback:
        raise ContractError(
            "rollback_performed must agree across action and evaluation"
        )

    system_should_block = feasibility in _BLOCKING_FEASIBILITY
    protected_changes = sorted(set(actual_variables) & set(protected))
    actual_variable = actual_variables[0] if len(actual_variables) == 1 else None
    matches_recorded_experiment = bool(
        recorded_created
        and len(recorded_recommended) == 1
        and actual_variable == recorded_recommended[0]
    )
    matches_current_experiment = bool(
        generated_experiment
        and len(current_experiment_variables) == 1
        and actual_variable == current_experiment_variables[0]
    )
    variable_matches_experiment = bool(executed and matches_recorded_experiment)
    derived_variable_deviation = bool(
        executed and recorded_created and not variable_matches_experiment
    )
    deviated = bool(reported_deviation or derived_variable_deviation)
    single_variable = bool(
        executed
        and recorded_created
        and len(actual_variables) == 1
        and variable_matches_experiment
        and not concurrent_changes
        and not deviated
        and single_variable_label
    )
    confounded = bool(confounders or concurrent_changes)
    unsafe_action = bool(
        executed
        and (system_should_block or protected_changes or len(actual_variables) != 1)
    )
    correct_block = bool(system_should_block and not executed and correct_block_label)
    recommendation_available = bool(current_recommended or analysis["recommendations"])
    executable_recommendation = bool(
        recommendation_available and executable_label and current_recommended
    )
    experiment_opportunity = bool(generated_experiment or recorded_created)
    executed_experiment = bool(executed and recorded_created)
    completed = bool(executed_experiment and experiment_completed)
    maturity_met = bool(observation_conditions_met and delay_mature and volume_mature)
    insufficient_evidence = bool(
        insufficient_label or feasibility == FeasibilityState.DATA_BLOCKED.value
    )
    conclusive = bool(
        completed
        and maturity_met
        and conclusive_label
        and not confounded
        and not unsafe_action
        and not insufficient_evidence
    )
    valid_experiment = bool(
        executed_experiment
        and completed
        and maturity_met
        and single_variable
        and not confounded
        and not unsafe_action
        and not insufficient_evidence
    )
    recommendation_accepted = accepted_recommendation is not False
    attributable = bool(
        valid_experiment and conclusive and not deviated and recommendation_accepted
    )
    positive = bool(attributable and outcome == "positive")
    negative = bool(attributable and outcome == "negative")
    rollback = bool(action_rollback or evaluation_rollback)
    numeric_business_result_evaluable = bool(
        accepted_recommendation is True
        and executed
        and not confounded
        and not deviated
        and observation_conditions_met
        and delay_mature
        and volume_mature
        and not insufficient_evidence
    )
    numeric_replay = (
        _evaluate_numeric_replay(
            numeric_ground_truth,
            quick_decision,
            accepted_recommendation=accepted_recommendation,
            executed=executed,
            confounded=confounded,
            deviated=deviated,
            mature_result_available=maturity_met,
            business_result_evaluable=numeric_business_result_evaluable,
        )
        if numeric_ground_truth is not None and quick_decision is not None
        else None
    )
    if unsafe_action:
        classification = "unsafe_action"
    elif correct_block:
        classification = "correct_block"
    elif insufficient_evidence:
        classification = "insufficient_evidence"
    elif confounded:
        classification = "confounded"
    elif executed and experiment_opportunity and not attributable:
        classification = "unattributable"
    elif positive:
        classification = "positive_experiment"
    elif negative:
        classification = "negative_experiment"
    else:
        classification = "incomplete_or_monitoring"

    case_id = next(iter({doc["case_id"] for doc in documents.values()}))
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "system_at_the_time": {
            "rule_basis": "current_rules_on_historical_snapshot",
            "feasibility": feasibility,
            "diagnosis": analysis["diagnoses"][0]["code"],
            "generated_experiment": generated_experiment,
            "recommended_variables": current_recommended,
            "experiment_variables": current_experiment_variables,
            "system_should_block": system_should_block,
        },
        "recorded_decision": {
            "human_judgment": human_judgment,
            "accepted_system_recommendation": accepted_recommendation,
            "version": recorded_version,
            "feasibility": recorded_feasibility,
            "confidence": recorded_confidence,
            "data_gaps": recorded_data_gaps,
            "recommended_variables": recorded_recommended,
            "created_experiment": recorded_created,
        },
        "actual_action": {
            "executed": executed,
            "approved_by_role": approved_by_role,
            "executed_at": executed_at,
            "variables_changed": actual_variables,
            "protected_changes": protected_changes,
            "deviated": deviated,
            "reported_deviation": reported_deviation,
            "derived_variable_deviation": derived_variable_deviation,
            "variable_matches_experiment": variable_matches_experiment,
            "variable_matches_current_rules": matches_current_experiment,
        },
        "evaluation": {
            "classification": classification,
            "correct_block": correct_block,
            "unsafe_action": unsafe_action,
            "recommendation_available": recommendation_available,
            "executable_recommendation": executable_recommendation,
            "experiment_opportunity": experiment_opportunity,
            "executed_experiment": executed_experiment,
            "single_variable_compliant": single_variable,
            "confounded": confounded,
            "experiment_completed": completed,
            "conclusive": conclusive,
            "valid_experiment": valid_experiment,
            "attributable": attributable,
            "recommendation_accepted": recommendation_accepted,
            "positive": positive,
            "negative": negative,
            "rollback": rollback,
            "insufficient_evidence": insufficient_evidence,
            "time_saved_minutes": time_saved,
            "observation_days": observation_days,
            "minimum_observation_days": minimum_observation_days,
            "has_numeric_after_metric": has_numeric_after_metric,
        },
        "numeric_replay": numeric_replay,
        "disclaimers": REPLAY_DISCLAIMERS,
    }


def _rate(numerator: int, denominator: int) -> RateMetric:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": round(numerator / denominator, 4) if denominator else None,
    }


def _magnitude_error(values: list[float]) -> dict[str, float | int | None]:
    total = 0.0
    for value in values:
        total += value
        if not math.isfinite(total):
            raise ContractError("aggregate numeric magnitude error must remain finite")
    return {
        "total_absolute_percentage_error": round(total, 4),
        "denominator": len(values),
        "mean_absolute_percentage_error": (
            round(total / len(values), 4) if values else None
        ),
    }


def _case_directories(path: Path) -> list[Path]:
    if path.is_symlink() or not path.is_dir():
        raise ContractError("replay path must be a regular directory")
    if all((path / filename).is_file() for filename in REPLAY_FILES) or all(
        (path / filename).is_file() for filename in LEGACY_REPLAY_FILES
    ):
        return [path]
    cases = sorted(
        {
            candidate.parent
            for candidate in path.rglob("snapshot-before.yaml")
            if candidate.is_file() and not candidate.is_symlink()
        }
    )
    if not cases:
        raise ContractError("no replay cases were found")
    return cases


def replay_path(path: Path) -> dict[str, Any]:
    """Evaluate one case or aggregate all cases below a directory."""

    cases = [evaluate_replay(case_dir) for case_dir in _case_directories(path)]
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ContractError("replay case_id values must be unique")
    evaluations = [case["evaluation"] for case in cases]

    block_opportunities = sum(
        bool(case["system_at_the_time"]["system_should_block"]) for case in cases
    )
    recommendation_opportunities = sum(
        bool(item["recommendation_available"]) for item in evaluations
    )
    created_experiments = sum(
        bool(case["recorded_decision"]["created_experiment"]) for case in cases
    )
    executed_experiments = sum(
        bool(item["executed_experiment"]) for item in evaluations
    )
    completed_experiments = sum(
        bool(item["experiment_completed"]) for item in evaluations
    )
    conclusive_experiments = sum(bool(item["conclusive"]) for item in evaluations)
    attributable_experiments = sum(bool(item["attributable"]) for item in evaluations)
    numeric_replays = [
        case["numeric_replay"]
        for case in cases
        if isinstance(case.get("numeric_replay"), dict)
    ]
    numeric_evaluations = [item["evaluation"] for item in numeric_replays]
    direction_evaluations = [
        item
        for item in numeric_evaluations
        if item["business_result_evaluable"] is True
    ]
    magnitude_errors = [
        float(item["magnitude_error"])
        for item in direction_evaluations
        if item["magnitude_error"] is not None
    ]
    no_action_evaluations = [
        item for item in numeric_evaluations if item["no_action_expected"] is True
    ]
    human_decisions = [
        item["human_decision"]["accepted_system_recommendation"]
        for item in numeric_replays
        if isinstance(item["human_decision"]["accepted_system_recommendation"], bool)
    ]

    time_saved_total = 0.0
    for item in evaluations:
        time_saved_total += float(item["time_saved_minutes"])
        if not math.isfinite(time_saved_total):
            raise ContractError("aggregate time_saved_minutes must remain finite")

    metrics = {
        "correct_block_rate": _rate(
            sum(bool(item["correct_block"]) for item in evaluations),
            block_opportunities,
        ),
        "unsafe_action_rate": _rate(
            sum(bool(item["unsafe_action"]) for item in evaluations), len(cases)
        ),
        "executable_recommendation_rate": _rate(
            sum(bool(item["executable_recommendation"]) for item in evaluations),
            recommendation_opportunities,
        ),
        "single_variable_compliance_rate": _rate(
            sum(
                bool(item["single_variable_compliant"])
                and bool(item["executed_experiment"])
                for item in evaluations
            ),
            executed_experiments,
        ),
        "experiment_completion_rate": _rate(completed_experiments, created_experiments),
        "conclusive_experiment_rate": _rate(
            conclusive_experiments, completed_experiments
        ),
        "confounded_rate": _rate(
            sum(
                bool(item["confounded"]) and bool(item["executed_experiment"])
                for item in evaluations
            ),
            executed_experiments,
        ),
        "positive_experiment_rate": _rate(
            sum(bool(item["positive"]) for item in evaluations),
            attributable_experiments,
        ),
        "rollback_rate": _rate(
            sum(
                bool(item["rollback"]) and bool(item["executed_experiment"])
                for item in evaluations
            ),
            executed_experiments,
        ),
        "time_saved_minutes": round(time_saved_total, 2),
        "insufficient_evidence_rate": _rate(
            sum(bool(item["insufficient_evidence"]) for item in evaluations),
            len(cases),
        ),
        "direction_accuracy": _rate(
            sum(bool(item["direction_correct"]) for item in direction_evaluations),
            len(direction_evaluations),
        ),
        "magnitude_error": _magnitude_error(magnitude_errors),
        "unsafe_numeric_recommendation_rate": _rate(
            sum(
                bool(item["unsafe_numeric_recommendation"])
                for item in numeric_evaluations
            ),
            len(numeric_evaluations),
        ),
        "no_action_correct_rate": _rate(
            sum(bool(item["no_action_correct"]) for item in no_action_evaluations),
            len(no_action_evaluations),
        ),
        "human_acceptance_rate": _rate(
            sum(value is True for value in human_decisions), len(human_decisions)
        ),
    }
    return {
        "schema_version": "1.0",
        "sample_size": len(cases),
        "cases": cases,
        "metrics": metrics,
        "disclaimers": REPLAY_DISCLAIMERS,
    }


def render_replay(report: dict[str, Any]) -> str:
    lines = [f"UAC Replay: {report['sample_size']} case(s)"]
    for case in report["cases"]:
        evaluation = case["evaluation"]
        lines.append(
            f"- {case['case_id']}: {evaluation['classification']} "
            f"(attributable={str(evaluation['attributable']).lower()})"
        )
    lines.append("")
    lines.append("Metrics:")
    for name, metric in report["metrics"].items():
        if isinstance(metric, dict):
            if "rate" in metric:
                rate = "n/a" if metric["rate"] is None else metric["rate"]
                lines.append(
                    f"- {name}: {rate} ({metric['numerator']}/{metric['denominator']})"
                )
            else:
                mean = metric["mean_absolute_percentage_error"]
                rendered = "n/a" if mean is None else mean
                lines.append(
                    f"- {name}: {rendered} ({metric['denominator']} evaluated case(s))"
                )
        else:
            lines.append(f"- {name}: {metric}")
    lines.append("")
    lines.extend(f"Warning: {item}" for item in report["disclaimers"])
    return "\n".join(lines)
