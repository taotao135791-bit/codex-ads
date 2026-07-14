"""Read-only Campaign Level Quick Ops decision layer for Google App campaigns."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
from typing import Any, cast

from .engine import _permission_class, analyze_case
from .numeric_decision import recommend_numeric
from .routing import route_question
from .signals import apply_derived_signals, derive_signals
from .terminology import (
    CAMPAIGN_LEVELS,
    canonical_campaign_level,
    extract_campaign_levels,
    normalize_glossary,
    resolve_campaign_level,
)
from .types import (
    BUDGET_DELIVERY_STATES,
    CALCULATION_EVIDENCE_TYPES,
    EVENT_VOLUME_STATES,
    MATURITY_STATES,
    SPLIT_FEASIBILITY_STATES,
    TARGET_CONSTRAINT_STATES,
    VALUE_SIGNAL_STATES,
    ContractError,
)


QUICK_DECISION_SCHEMA_VERSION = "1.0"

CAMPAIGN_VERDICTS = {
    "CONTINUE_CURRENT_AC20",
    "ADJUST_CURRENT_AC20",
    "CREATE_NEW_AC20",
    "CONTINUE_CURRENT_AC25",
    "ADJUST_CURRENT_AC25",
    "CREATE_NEW_AC25",
    "CONTINUE_CURRENT_AC30",
    "ADJUST_CURRENT_AC30",
    "CREATE_NEW_AC30",
    "MOVE_AC20_TO_AC25",
    "MOVE_AC25_TO_AC30",
    "KEEP_AC20_AND_TEST_AC25",
    "KEEP_AC25_AND_TEST_AC30",
    "DO_NOT_START_AC25",
    "DO_NOT_START_AC30",
    "ROLL_BACK_TO_AC20",
    "ROLL_BACK_TO_AC25",
    "WAIT_FOR_MORE_DEEP_EVENTS",
    "WAIT_FOR_VALUE_SIGNAL",
    "INSUFFICIENT_EVIDENCE",
}

STRUCTURE_ACTIONS = {
    "ADD_TO_EXISTING",
    "ADJUST_EXISTING",
    "CREATE_NEW_SAME_LEVEL",
    "CREATE_NEW_CANDIDATE_LEVEL",
    "DUPLICATE_FOR_CONTROLLED_TEST",
    "DO_NOT_DUPLICATE",
    "REQUEST_CLIENT_APPROVAL",
    "WAIT",
}

CREATIVE_ACTIONS = {
    "KEEP_RUNNING",
    "RUN_WITH_LIMIT",
    "WAIT_FOR_MATURITY",
    "REDUCE_EXPOSURE",
    "PAUSE",
    "REPLACE",
    "RETEST",
    "INSUFFICIENT_DATA",
}

_LEVEL_SUFFIX = {"AC2.0": "AC20", "AC2.5": "AC25", "AC3.0": "AC30"}
_PROFILE_PERMISSION: dict[str, dict[str, str]] = {
    "read_only": {"*": "NOT_ACTIONABLE"},
    "creative_only": {
        "creative": "OPTIMIZER_CAN_EXECUTE",
        "creative_add": "OPTIMIZER_CAN_EXECUTE",
        "creative_remove": "OPTIMIZER_CAN_EXECUTE",
        "*": "NOT_ACTIONABLE",
    },
    "creative_permission_but_no_new_assets": {
        "creative": "OPTIMIZER_CAN_EXECUTE",
        "creative_add": "NOT_ACTIONABLE",
        "creative_remove": "OPTIMIZER_CAN_EXECUTE",
        "*": "NOT_ACTIONABLE",
    },
    "budget_only": {"budget": "OPTIMIZER_CAN_EXECUTE", "*": "NOT_ACTIONABLE"},
    "bid_only": {
        "bid": "OPTIMIZER_CAN_EXECUTE",
        "bid_strategy": "OPTIMIZER_CAN_EXECUTE",
        "*": "NOT_ACTIONABLE",
    },
    "campaign_create_only_with_approval": {
        "campaign_create": "CLIENT_APPROVAL_REQUIRED"
    },
    "event_change_requires_client": {"optimization_event": "CLIENT_APPROVAL_REQUIRED"},
    "all_changes_require_client_approval": {"*": "CLIENT_APPROVAL_REQUIRED"},
    "aggregate_data_only": {"*": "NOT_ACTIONABLE"},
    "campaign_locked_asset_editable": {
        "creative": "OPTIMIZER_CAN_EXECUTE",
        "creative_add": "OPTIMIZER_CAN_EXECUTE",
        "creative_remove": "OPTIMIZER_CAN_EXECUTE",
        "campaign_create": "PLATFORM_LIMITATION",
        "optimization_event": "PLATFORM_LIMITATION",
        "budget": "PLATFORM_LIMITATION",
        "bid": "PLATFORM_LIMITATION",
    },
    "cannot_change_optimization_event": {"optimization_event": "PLATFORM_LIMITATION"},
    "cannot_create_new_campaign": {"campaign_create": "PLATFORM_LIMITATION"},
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _non_negative_or_none(value: Any) -> bool:
    return value is None or (_finite_number(value) and value >= 0)


def _level(value: Any) -> str | None:
    return canonical_campaign_level(value)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _validate_quick_input(case: Mapping[str, Any]) -> None:
    quick = case.get("quick_ops", {})
    if not isinstance(quick, Mapping):
        raise ContractError("quick_ops must be an object")
    glossary = case.get("campaign_level_glossary", {})
    if not isinstance(glossary, Mapping):
        raise ContractError("campaign_level_glossary must be an object")
    for key, definition in glossary.items():
        if _level(str(key)) is None:
            raise ContractError(
                f"campaign_level_glossary.{key} is not a supported AC label"
            )
        if not isinstance(definition, Mapping):
            raise ContractError(f"campaign_level_glossary.{key} must be an object")
    for field in (
        "current_campaign",
        "candidate_campaign",
        "candidate_event",
        "value_signal",
        "split_capacity",
        "structure",
        "creative",
        "bid_budget",
        "operational",
        "review",
        "rollback",
        "external_checks",
    ):
        if field in quick and not isinstance(quick[field], Mapping):
            raise ContractError(f"quick_ops.{field} must be an object")
    for container_name in ("current_campaign", "candidate_campaign"):
        container = _mapping(quick.get(container_name))
        if "level" in container and _level(container.get("level")) is None:
            raise ContractError(
                f"quick_ops.{container_name}.level must be AC2.0, AC2.5, or AC3.0"
            )
    if "candidate_level" in quick and _level(quick.get("candidate_level")) is None:
        raise ContractError("quick_ops.candidate_level must be a campaign-level label")
    for container_name in ("review", "bid_budget", "creative"):
        container = _mapping(quick.get(container_name))
        for name, value in container.items():
            if (
                any(
                    marker in str(name)
                    for marker in (
                        "days",
                        "events",
                        "spend",
                        "budget",
                        "target",
                        "value",
                    )
                )
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            ):
                if not _non_negative_or_none(value):
                    raise ContractError(
                        f"quick_ops.{container_name}.{name} must be a finite non-negative number"
                    )
    if "question" in quick and not isinstance(quick["question"], str):
        raise ContractError("quick_ops.question must be text")
    profile = quick.get("permission_profile")
    if profile is not None and not isinstance(profile, str):
        raise ContractError("quick_ops.permission_profile must be text")


def _permission_for(case: dict[str, Any], variable: str) -> str:
    quick = _mapping(case.get("quick_ops"))
    profile = quick.get("permission_profile")
    profile_map = _PROFILE_PERMISSION.get(str(profile), {})
    if variable in profile_map:
        return profile_map[variable]
    if "*" in profile_map:
        return profile_map["*"]
    if profile == "android_editable_ios_locked":
        if _mapping(case.get("facts")).get("segmentation_complete") is not True:
            return "NOT_ACTIONABLE"
        os_name = str(
            _mapping(quick.get("current_campaign")).get("os")
            or _mapping(case.get("scope")).get("os", "")
        ).lower()
        if os_name == "android":
            return "OPTIMIZER_CAN_EXECUTE"
        return "PLATFORM_LIMITATION"
    classification = _permission_class(case, variable)
    if (
        variable in {"creative_add", "creative_remove"}
        and classification == "INSUFFICIENT_EVIDENCE"
    ):
        return _permission_class(case, "creative")
    return classification


def _permission_block(
    case: dict[str, Any], variables: tuple[str, ...]
) -> tuple[str, str, list[str]] | None:
    blocked: dict[str, str] = {}
    for variable in variables:
        classification = _permission_for(case, variable)
        if classification != "OPTIMIZER_CAN_EXECUTE":
            blocked[variable] = classification
    if not blocked:
        return None
    action = (
        "REQUEST_CLIENT_APPROVAL"
        if any(value == "CLIENT_APPROVAL_REQUIRED" for value in blocked.values())
        else "WAIT"
    )
    requests = [
        _permission_request(variable, classification)
        for variable, classification in blocked.items()
    ]
    return action, next(iter(blocked.values())), requests


def _tri_state_gate(
    source: Mapping[str, Any],
    *,
    true_fields: tuple[str, ...],
    enum_fields: Mapping[str, str],
    prefix: str,
) -> tuple[str, list[str], list[str]]:
    blocked: list[str] = []
    unknown: list[str] = []
    for field in true_fields:
        value = source.get(field)
        if value is False:
            blocked.append(f"{prefix}_{field}_failed")
        elif value is not True and value != "not_applicable":
            unknown.append(f"{prefix}_{field}_unknown")
    for field, expected in enum_fields.items():
        value = source.get(field)
        if value is None or value == "unknown":
            unknown.append(f"{prefix}_{field}_unknown")
        elif value != expected:
            blocked.append(f"{prefix}_{field}_failed")
    if blocked:
        return "blocked", blocked, unknown
    if unknown:
        return "unknown", blocked, unknown
    return "ready", blocked, unknown


def _candidate_event_gate(
    quick: Mapping[str, Any], analysis: Mapping[str, Any]
) -> tuple[str, list[str], list[str]]:
    candidate = _mapping(quick.get("candidate_event"))
    state, blocked, unknown = _tri_state_gate(
        candidate,
        true_fields=("reliable", "delay_mature"),
        enum_fields={
            "volume_assessment": "sufficient",
            "stability_assessment": "stable",
            "relationship_to_business_goal": "stronger",
        },
        prefix="candidate_event",
    )
    measurement = _mapping(analysis.get("measurement_state")).get("status")
    if measurement == "measurement_unreliable":
        blocked.append("measurement_state_unreliable")
        state = "blocked"
    elif measurement != "measurement_reliable" and state != "blocked":
        unknown.append("measurement_state_not_confirmed")
        state = "unknown"
    return state, _unique(blocked), _unique(unknown)


def _value_gate(
    quick: Mapping[str, Any],
    analysis: Mapping[str, Any],
    campaign: Mapping[str, Any],
) -> tuple[str, list[str], list[str]]:
    signal = _mapping(quick.get("value_signal"))
    state, blocked, unknown = _tri_state_gate(
        signal,
        true_fields=(
            "business_kpi_is_value",
            "strategy_supports_value",
            "payment_reliable",
            "value_reliable",
            "currency_reliable",
            "duplicates_handled",
            "refunds_handled",
            "subscriptions_defined",
            "delay_mature",
        ),
        enum_fields={
            "value_reconciliation": "consistent",
            "volume_assessment": "sufficient",
            "stability_assessment": "stable",
            "single_campaign_budget_assessment": "sufficient",
        },
        prefix="value_signal",
    )
    value_optimization = campaign.get("value_optimization")
    if value_optimization is False:
        blocked.append("candidate_campaign_value_optimization_failed")
        state = "blocked"
    elif value_optimization is not True and state != "blocked":
        unknown.append("candidate_campaign_value_optimization_unknown")
        state = "unknown"
    bidding_strategy = str(campaign.get("bidding_strategy", "")).lower()
    if bidding_strategy in {
        "cpi",
        "tcpi",
        "tcpa",
        "maximize_conversions",
        "max_conversions",
    }:
        blocked.append("candidate_campaign_value_bidding_strategy_failed")
        state = "blocked"
    elif not bidding_strategy and state != "blocked":
        unknown.append("candidate_campaign_value_bidding_strategy_unknown")
        state = "unknown"
    measurement = _mapping(analysis.get("measurement_state")).get("status")
    if measurement == "measurement_unreliable":
        blocked.append("measurement_state_unreliable")
        state = "blocked"
    elif measurement != "measurement_reliable" and state != "blocked":
        unknown.append("measurement_state_not_confirmed")
        state = "unknown"
    return state, _unique(blocked), _unique(unknown)


def _split_gate(quick: Mapping[str, Any]) -> tuple[str, list[str], list[str]]:
    split = _mapping(quick.get("split_capacity"))
    return _tri_state_gate(
        split,
        true_fields=("isolatable",),
        enum_fields={
            "budget_assessment": "sufficient",
            "event_volume_assessment": "sufficient",
        },
        prefix="split_capacity",
    )


def _permission_request(variable: str, classification: str) -> str:
    if classification == "CLIENT_APPROVAL_REQUIRED":
        return f"request client approval for {variable}"
    if classification == "CLIENT_DATA_REQUIRED":
        return f"request client data for {variable}"
    if classification == "PLATFORM_LIMITATION":
        return f"confirm platform capability for {variable}"
    if classification == "NOT_ACTIONABLE":
        return f"keep {variable} unchanged because it is not actionable"
    return f"confirm permission for {variable}"


def _same_level_structure(
    case: dict[str, Any], quick: Mapping[str, Any]
) -> dict[str, Any]:
    structure = _mapping(quick.get("structure"))
    split_state, split_blocked, split_unknown = _split_gate(quick)
    duplicate_reason = str(structure.get("duplicate_reason", ""))
    restart_only = duplicate_reason in {
        "restart_learning",
        "recent_performance_drop",
        "try_again",
    }
    isolation_reasons = [
        field
        for field in (
            "independent_geo_required",
            "independent_os_required",
            "independent_budget_required",
            "different_user_hypothesis",
            "different_audience_required",
            "client_attribution_isolation_required",
        )
        if structure.get(field) is True
    ]
    same_semantics = structure.get("same_semantics") is True or all(
        structure.get(field) is True
        for field in (
            "same_optimization_event",
            "same_geo",
            "same_os",
            "same_bid_strategy",
            "same_business_goal",
        )
    )
    create_permission = _permission_for(case, "campaign_create")
    client_requests: list[str] = []
    reasons: list[str] = []
    data_gaps: list[str] = []

    if restart_only:
        action = "DO_NOT_DUPLICATE"
        reasons.append("duplicate_only_to_restart_learning")
    elif isolation_reasons and split_state == "ready":
        if create_permission != "OPTIMIZER_CAN_EXECUTE":
            action = (
                "REQUEST_CLIENT_APPROVAL"
                if create_permission == "CLIENT_APPROVAL_REQUIRED"
                else "WAIT"
            )
            reasons.append("campaign_create_not_immediately_executable")
            client_requests.append(
                _permission_request("campaign_create", create_permission)
            )
        elif (
            structure.get("controlled_test_required") is True
            and structure.get("experiment_admission_ready") is True
            and structure.get("traffic_isolation_ready") is True
        ):
            action = "DUPLICATE_FOR_CONTROLLED_TEST"
            reasons.append("controlled_test_isolation_ready")
        else:
            action = "CREATE_NEW_SAME_LEVEL"
            reasons.append("independent_structure_is_required")
    elif same_semantics and structure.get("new_assets_only") is True:
        action = "ADD_TO_EXISTING"
        reasons.append("new_assets_share_existing_campaign_semantics")
    elif split_state == "blocked":
        action = "DO_NOT_DUPLICATE"
        reasons.extend(split_blocked)
    elif isolation_reasons and split_state == "unknown":
        action = "WAIT"
        reasons.append("split_capacity_not_proven")
        data_gaps.extend(split_unknown)
    else:
        action = "DO_NOT_DUPLICATE"
        reasons.append("no_independent_campaign_reason")

    if structure.get("controlled_test_required") is True and action not in {
        "DUPLICATE_FOR_CONTROLLED_TEST"
    }:
        reasons.append("not_a_valid_experiment")
    return {
        "action": action,
        "create_new_campaign": action
        in {"CREATE_NEW_SAME_LEVEL", "DUPLICATE_FOR_CONTROLLED_TEST"},
        "run_in_parallel": action
        in {"CREATE_NEW_SAME_LEVEL", "DUPLICATE_FOR_CONTROLLED_TEST"},
        "permission": create_permission,
        "reason_codes": _unique(reasons),
        "data_gaps": _unique(data_gaps),
        "client_requests": _unique(client_requests),
    }


def _keep_verdict(level: str | None, *, adjust: bool = False) -> str:
    if level is None:
        return "INSUFFICIENT_EVIDENCE"
    action = "ADJUST" if adjust else "CONTINUE"
    return f"{action}_CURRENT_{_LEVEL_SUFFIX[level]}"


def _level_decision(
    case: dict[str, Any],
    quick: Mapping[str, Any],
    analysis: Mapping[str, Any],
    current: str | None,
    candidate: str | None,
    terminology: Mapping[str, Any],
    question_type: str,
    numeric: Mapping[str, Any],
) -> dict[str, Any]:
    gaps: list[str] = []
    client_requests: list[str] = []
    structure = {
        "action": "ADJUST_EXISTING",
        "create_new_campaign": False,
        "run_in_parallel": False,
        "permission": "INSUFFICIENT_EVIDENCE",
        "reason_codes": [],
        "data_gaps": [],
        "client_requests": [],
    }
    if current is None:
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "recommended": None,
            "action": "wait",
            "structure": {**structure, "action": "WAIT"},
            "reason_codes": ["current_campaign_level_unknown"],
            "data_gaps": ["current campaign level and actual account settings"],
            "client_requests": [],
        }

    signals = _mapping(quick.get("signals"))
    rollback = _mapping(quick.get("rollback"))
    if signals.get("rollback_triggered") is True:
        baseline = _level(rollback.get("baseline_level"))
        rollback_verdict = None
        if current == "AC2.5" and baseline == "AC2.0":
            rollback_verdict = "ROLL_BACK_TO_AC20"
        elif current == "AC3.0" and baseline == "AC2.5":
            rollback_verdict = "ROLL_BACK_TO_AC25"
        if rollback_verdict is not None:
            permission_block = _permission_block(
                case, ("optimization_event", "bid_strategy")
            )
            if permission_block is not None:
                permission_action, permission, requests = permission_block
                return {
                    "verdict": _keep_verdict(current),
                    "recommended": current,
                    "action": "keep",
                    "structure": {
                        **structure,
                        "action": permission_action,
                        "permission": permission,
                        "reason_codes": ["level_migration_requires_permission"],
                        "client_requests": requests,
                    },
                    "reason_codes": ["level_change_not_immediately_executable"],
                    "data_gaps": [],
                    "client_requests": requests,
                }
            return {
                "verdict": rollback_verdict,
                "recommended": baseline,
                "action": "rollback",
                "structure": structure,
                "reason_codes": ["predeclared_rollback_triggered"],
                "data_gaps": [],
                "client_requests": [],
            }
        gaps.append("known stable rollback baseline")

    permission_profile = quick.get("permission_profile")
    if (
        permission_profile == "android_editable_ios_locked"
        and _mapping(case.get("facts")).get("segmentation_complete") is not True
    ):
        return {
            "verdict": _keep_verdict(current),
            "recommended": current,
            "action": "keep",
            "structure": {**structure, "action": "WAIT"},
            "reason_codes": ["os_level_segmentation_incomplete"],
            "data_gaps": ["OS-segmented campaign and conversion evidence"],
            "client_requests": ["request OS-segmented campaign evidence"],
        }
    if permission_profile == "aggregate_data_only":
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "recommended": current,
            "action": "keep",
            "structure": {**structure, "action": "WAIT"},
            "reason_codes": ["aggregate_data_cannot_support_campaign_action"],
            "data_gaps": ["campaign, OS, event, and asset-level evidence"],
            "client_requests": [],
        }
    if (
        permission_profile == "mmp_access_without_backend_access"
        and candidate == "AC3.0"
    ):
        return {
            "verdict": "WAIT_FOR_VALUE_SIGNAL",
            "recommended": current,
            "action": "wait",
            "structure": {**structure, "action": "WAIT"},
            "reason_codes": ["backend_value_reconciliation_missing"],
            "data_gaps": ["backend value reconciliation"],
            "client_requests": ["request backend value reconciliation"],
        }

    active_experiment = any(
        isinstance(item, Mapping) and item.get("active", True)
        for item in analysis.get("experiment_reviews", [])
        if isinstance(item, Mapping)
    )
    urgent = _mapping(quick.get("operational")).get("urgent_confirmed") is True
    if active_experiment and not urgent:
        return {
            "verdict": _keep_verdict(current),
            "recommended": current,
            "action": "keep",
            "structure": {**structure, "action": "WAIT"},
            "reason_codes": ["unfinished_experiment_blocks_stacked_change"],
            "data_gaps": ["close or mature the current experiment first"],
            "client_requests": [],
        }

    constraint = _mapping(numeric.get("constraint_analysis"))
    numeric_evidence = constraint.get("has_numeric_evidence") is True
    if (
        candidate is not None
        and candidate != current
        and numeric_evidence
        and constraint.get("maturity_state") != "MATURE"
    ):
        return {
            "verdict": _keep_verdict(current),
            "recommended": current,
            "action": "wait",
            "structure": {
                **structure,
                "action": "WAIT",
                "reason_codes": ["numeric_data_not_mature_precedes_level_change"],
            },
            "reason_codes": ["numeric_data_not_mature_precedes_level_change"],
            "data_gaps": ["mature numeric evidence after the latest change"],
            "client_requests": [],
        }
    if (
        candidate is not None
        and candidate != current
        and constraint.get("target_state") == "TARGET_LIKELY_TOO_TIGHT"
    ):
        return {
            "verdict": _keep_verdict(current, adjust=True),
            "recommended": current,
            "action": "keep",
            "structure": {
                **structure,
                "action": "ADJUST_EXISTING",
                "reason_codes": ["target_constraint_precedes_level_change"],
            },
            "reason_codes": ["target_constraint_precedes_level_change"],
            "data_gaps": [],
            "client_requests": [],
        }

    if question_type == "same_level_campaign" or candidate == current:
        structure = _same_level_structure(case, quick)
        action = structure["action"]
        if action in {"CREATE_NEW_SAME_LEVEL", "DUPLICATE_FOR_CONTROLLED_TEST"}:
            verdict = f"CREATE_NEW_{_LEVEL_SUFFIX[current]}"
        elif action == "ADJUST_EXISTING":
            verdict = _keep_verdict(current, adjust=True)
        else:
            verdict = _keep_verdict(current)
        return {
            "verdict": verdict,
            "recommended": current,
            "action": "keep" if not structure["create_new_campaign"] else "create",
            "structure": structure,
            "reason_codes": structure["reason_codes"],
            "data_gaps": structure["data_gaps"],
            "client_requests": structure["client_requests"],
        }

    if candidate is None:
        return {
            "verdict": _keep_verdict(current),
            "recommended": current,
            "action": "keep",
            "structure": structure,
            "reason_codes": ["no_level_change_requested"],
            "data_gaps": [],
            "client_requests": [],
        }

    if terminology.get("confirmation_required") is True:
        return {
            "verdict": _keep_verdict(current),
            "recommended": current,
            "action": "keep",
            "structure": {**structure, "action": "WAIT"},
            "reason_codes": ["campaign_level_mapping_confirmation_required"],
            "data_gaps": ["confirmed project meaning for the requested AC level"],
            "client_requests": [],
        }

    external = _mapping(quick.get("external_checks"))
    material_external = [
        str(name)
        for name, value in external.items()
        if value is True or value == "material_issue"
    ]
    if material_external:
        return {
            "verdict": _keep_verdict(current),
            "recommended": current,
            "action": "keep",
            "structure": {**structure, "action": "WAIT"},
            "reason_codes": ["material_external_issue_blocks_level_change"],
            "data_gaps": [
                f"resolve external issue: {name}" for name in material_external
            ],
            "client_requests": [],
        }

    if current == "AC2.0" and candidate == "AC2.5":
        gate, blocked, unknown = _candidate_event_gate(quick, analysis)
        if gate == "blocked":
            verdict = (
                "WAIT_FOR_MORE_DEEP_EVENTS"
                if any(
                    "volume_assessment" in reason or "delay_mature" in reason
                    for reason in blocked
                )
                else "DO_NOT_START_AC25"
            )
            return {
                "verdict": verdict,
                "recommended": current,
                "action": "wait" if verdict.startswith("WAIT") else "keep",
                "structure": {**structure, "action": "WAIT"},
                "reason_codes": blocked,
                "data_gaps": unknown,
                "client_requests": [],
            }
        if gate == "unknown":
            return {
                "verdict": "WAIT_FOR_MORE_DEEP_EVENTS",
                "recommended": current,
                "action": "wait",
                "structure": {**structure, "action": "WAIT"},
                "reason_codes": ["candidate_deep_event_not_ready"],
                "data_gaps": unknown,
                "client_requests": [],
            }
        return _admit_level_change(
            case,
            quick,
            current=current,
            candidate=candidate,
            parallel_verdict="KEEP_AC20_AND_TEST_AC25",
            move_verdict="MOVE_AC20_TO_AC25",
            do_not_verdict="DO_NOT_START_AC25",
        )

    if current == "AC2.5" and candidate == "AC3.0":
        gate, blocked, unknown = _value_gate(
            quick, analysis, _mapping(quick.get("candidate_campaign"))
        )
        if gate == "blocked":
            soft_wait_reasons = {
                "value_signal_delay_mature_failed",
                "value_signal_volume_assessment_failed",
                "value_signal_stability_assessment_failed",
            }
            waits_for_signal = bool(blocked) and set(blocked).issubset(
                soft_wait_reasons
            )
            return {
                "verdict": (
                    "WAIT_FOR_VALUE_SIGNAL" if waits_for_signal else "DO_NOT_START_AC30"
                ),
                "recommended": current,
                "action": "wait" if waits_for_signal else "keep",
                "structure": {**structure, "action": "WAIT"},
                "reason_codes": blocked,
                "data_gaps": unknown,
                "client_requests": [],
            }
        if gate == "unknown":
            return {
                "verdict": "WAIT_FOR_VALUE_SIGNAL",
                "recommended": current,
                "action": "wait",
                "structure": {**structure, "action": "WAIT"},
                "reason_codes": ["value_signal_not_ready"],
                "data_gaps": unknown,
                "client_requests": [],
            }
        return _admit_level_change(
            case,
            quick,
            current=current,
            candidate=candidate,
            parallel_verdict="KEEP_AC25_AND_TEST_AC30",
            move_verdict="MOVE_AC25_TO_AC30",
            do_not_verdict="DO_NOT_START_AC30",
        )

    if current == "AC3.0":
        gate, blocked, unknown = _value_gate(
            quick, analysis, _mapping(quick.get("current_campaign"))
        )
        if gate == "blocked" and _level(rollback.get("baseline_level")) == "AC2.5":
            verdict = "ROLL_BACK_TO_AC25"
            recommended = "AC2.5"
        elif gate == "blocked":
            verdict = "ADJUST_CURRENT_AC30"
            recommended = current
            gaps.append("known stable AC2.5 rollback baseline")
        elif gate == "unknown":
            verdict = "WAIT_FOR_VALUE_SIGNAL"
            recommended = current
        else:
            verdict = "CONTINUE_CURRENT_AC30"
            recommended = current
        if verdict == "ROLL_BACK_TO_AC25":
            permission_block = _permission_block(
                case, ("optimization_event", "bid_strategy")
            )
            if permission_block is not None:
                structure_action, permission, requests = permission_block
                verdict = _keep_verdict(current)
                recommended = current
                structure = {
                    **structure,
                    "action": structure_action,
                    "permission": permission,
                    "reason_codes": ["level_migration_requires_permission"],
                    "client_requests": requests,
                }
                client_requests.extend(requests)
                blocked.append("level_change_not_immediately_executable")
        return {
            "verdict": verdict,
            "recommended": recommended,
            "action": "rollback" if verdict.startswith("ROLL_BACK") else "keep",
            "structure": structure,
            "reason_codes": blocked or ["current_ac30_value_gate_ready"],
            "data_gaps": _unique([*unknown, *gaps]),
            "client_requests": client_requests,
        }

    return {
        "verdict": _keep_verdict(current),
        "recommended": current,
        "action": "keep",
        "structure": {**structure, "action": "WAIT"},
        "reason_codes": ["unsupported_or_unconfirmed_level_transition"],
        "data_gaps": ["account-specific transition evidence"],
        "client_requests": [],
    }


def _admit_level_change(
    case: dict[str, Any],
    quick: Mapping[str, Any],
    *,
    current: str,
    candidate: str,
    parallel_verdict: str,
    move_verdict: str,
    do_not_verdict: str,
) -> dict[str, Any]:
    current_campaign = _mapping(quick.get("current_campaign"))
    transition = _mapping(quick.get("transition"))
    split_state, split_blocked, split_unknown = _split_gate(quick)
    create_permission = _permission_for(case, "campaign_create")
    event_permission = _permission_for(case, "optimization_event")
    strategy_permission = _permission_for(case, "bid_strategy")
    current_healthy = current_campaign.get("healthy")
    direct_ready = all(
        transition.get(field) is True
        for field in (
            "direct_migration_safe",
            "single_campaign_learning_ready",
            "rollback_baseline_available",
        )
    )
    current_misaligned = (
        current_campaign.get("healthy") is False
        or current_campaign.get("goal_misaligned") is True
    )

    if split_state == "ready" and current_healthy is not False:
        if create_permission == "OPTIMIZER_CAN_EXECUTE":
            return {
                "verdict": parallel_verdict,
                "recommended": candidate,
                "action": "parallel_test",
                "structure": {
                    "action": "CREATE_NEW_CANDIDATE_LEVEL",
                    "create_new_campaign": True,
                    "run_in_parallel": True,
                    "permission": create_permission,
                    "reason_codes": ["split_budget_and_event_volume_are_sufficient"],
                    "data_gaps": [],
                    "client_requests": [],
                },
                "reason_codes": ["keep_healthy_baseline_while_testing_deeper_level"],
                "data_gaps": [],
                "client_requests": [],
            }
        return {
            "verdict": _keep_verdict(current),
            "recommended": current,
            "action": "keep",
            "structure": {
                "action": (
                    "REQUEST_CLIENT_APPROVAL"
                    if create_permission == "CLIENT_APPROVAL_REQUIRED"
                    else "WAIT"
                ),
                "create_new_campaign": False,
                "run_in_parallel": False,
                "permission": create_permission,
                "reason_codes": ["candidate_campaign_requires_permission"],
                "data_gaps": [],
                "client_requests": [
                    _permission_request("campaign_create", create_permission)
                ],
            },
            "reason_codes": ["level_change_not_immediately_executable"],
            "data_gaps": [],
            "client_requests": [
                _permission_request("campaign_create", create_permission)
            ],
        }

    if current_misaligned and direct_ready:
        required = {
            "optimization_event": event_permission,
            "bid_strategy": strategy_permission,
        }
        blocked_permissions = {
            name: value
            for name, value in required.items()
            if value != "OPTIMIZER_CAN_EXECUTE"
        }
        if not blocked_permissions:
            return {
                "verdict": move_verdict,
                "recommended": candidate,
                "action": "move",
                "structure": {
                    "action": "ADJUST_EXISTING",
                    "create_new_campaign": False,
                    "run_in_parallel": False,
                    "permission": "OPTIMIZER_CAN_EXECUTE",
                    "reason_codes": ["direct_migration_gate_ready"],
                    "data_gaps": [],
                    "client_requests": [],
                },
                "reason_codes": ["current_level_misaligned_and_migration_safe"],
                "data_gaps": [],
                "client_requests": [],
            }
        requests = [
            _permission_request(name, value)
            for name, value in blocked_permissions.items()
        ]
        return {
            "verdict": _keep_verdict(current),
            "recommended": current,
            "action": "keep",
            "structure": {
                "action": (
                    "REQUEST_CLIENT_APPROVAL"
                    if any(
                        value == "CLIENT_APPROVAL_REQUIRED"
                        for value in blocked_permissions.values()
                    )
                    else "WAIT"
                ),
                "create_new_campaign": False,
                "run_in_parallel": False,
                "permission": next(iter(blocked_permissions.values())),
                "reason_codes": ["level_migration_requires_permission"],
                "data_gaps": [],
                "client_requests": requests,
            },
            "reason_codes": ["level_change_not_immediately_executable"],
            "data_gaps": [],
            "client_requests": requests,
        }

    reasons = split_blocked or ["healthy_current_campaign_should_not_be_closed"]
    gaps = split_unknown
    return {
        "verdict": do_not_verdict
        if split_state == "blocked"
        else _keep_verdict(current),
        "recommended": current,
        "action": "keep",
        "structure": {
            "action": "DO_NOT_DUPLICATE" if split_state == "blocked" else "WAIT",
            "create_new_campaign": False,
            "run_in_parallel": False,
            "permission": create_permission,
            "reason_codes": reasons,
            "data_gaps": gaps,
            "client_requests": [],
        },
        "reason_codes": reasons,
        "data_gaps": gaps,
        "client_requests": [],
    }


def _creative_decision(
    case: dict[str, Any],
    quick: Mapping[str, Any],
    structure_action: str,
    question_type: str,
) -> dict[str, Any]:
    creative = _mapping(quick.get("creative"))
    permission = _permission_for(case, "creative")
    add_permission = _permission_for(case, "creative_add")
    reasons: list[str] = []
    requests: list[str] = []
    gaps: list[str] = []

    if creative.get("asset_grain_available") is False:
        action = "INSUFFICIENT_DATA"
        reasons.append("asset_level_mature_cohort_missing")
    elif creative.get("new_asset") is True and creative.get("mature") is not True:
        action = "WAIT_FOR_MATURITY"
        reasons.append("creative_conversion_delay_or_volume_not_mature")
    elif creative.get("guardrail_breached") is True:
        if creative.get("replacement_available") is True:
            action = "REPLACE"
        else:
            action = "REDUCE_EXPOSURE"
        reasons.append("mature_creative_guardrail_breached")
    elif creative.get("fatigued") is True:
        action = (
            "REPLACE"
            if creative.get("replacement_available") is True
            else "REDUCE_EXPOSURE"
        )
        reasons.append("creative_fatigue_detected")
    elif creative.get("lowest_cpi_worst_payment_rate") is True:
        action = (
            "REPLACE"
            if creative.get("replacement_available") is True
            else "RUN_WITH_LIMIT"
        )
        reasons.append("low_cpi_does_not_equal_high_value")
    elif creative.get("high_cpi_best_payment_efficiency") is True:
        action = "KEEP_RUNNING"
        reasons.append("mature_payment_efficiency_outweighs_cpi")
    elif creative.get("value_goal_mismatch") is True:
        action = (
            "REPLACE"
            if creative.get("replacement_available") is True
            else "RUN_WITH_LIMIT"
        )
        reasons.append("creative_promise_mismatches_value_goal")
    elif creative.get("mature") is True:
        action = "KEEP_RUNNING"
        reasons.append("no_mature_creative_stop_condition")
    else:
        action = "INSUFFICIENT_DATA"
        reasons.append("creative_evidence_not_supplied")

    if permission != "OPTIMIZER_CAN_EXECUTE" and action in {
        "REPLACE",
        "PAUSE",
        "REDUCE_EXPOSURE",
        "RETEST",
    }:
        requests.append(_permission_request("creative", permission))
        action = "KEEP_RUNNING"
        reasons.append("creative_change_not_immediately_executable")
    if creative.get("new_assets_available") is False:
        requests.append("request approved replacement assets")
        if action == "REPLACE":
            action = "REDUCE_EXPOSURE"
        reasons.append("no_approved_replacement_assets")
    if creative.get("stop_condition") is None and (
        creative.get("new_asset") is True or question_type == "creative_action"
    ):
        gaps.append("creative stop condition")

    add_new_assets = (
        creative.get("new_asset") is True
        and creative.get("new_assets_available") is not False
    )
    if add_new_assets and add_permission != "OPTIMIZER_CAN_EXECUTE":
        requests.append(_permission_request("creative_add", add_permission))
        reasons.append("creative_add_not_immediately_executable")
        add_new_assets = False

    if add_new_assets and structure_action in {
        "CREATE_NEW_SAME_LEVEL",
        "CREATE_NEW_CANDIDATE_LEVEL",
        "DUPLICATE_FOR_CONTROLLED_TEST",
    }:
        placement = "TEST_IN_NEW_CAMPAIGN"
    elif add_new_assets:
        placement = "ADD_TO_EXISTING_CAMPAIGN"
    else:
        placement = None

    review = _mapping(quick.get("review"))
    return {
        "action": action,
        "placement": placement,
        "keep_existing_assets": action not in {"PAUSE", "REPLACE"},
        "add_new_assets": add_new_assets,
        "minimum_additional_days": review.get("after_days"),
        "minimum_additional_mature_events": review.get(
            "minimum_additional_mature_events"
        ),
        "maximum_additional_spend": review.get("maximum_additional_spend"),
        "stop_condition": creative.get("stop_condition"),
        "permission": permission,
        "add_permission": add_permission,
        "reason_codes": _unique(reasons),
        "data_gaps": _unique(gaps),
        "client_requests": _unique(requests),
    }


def _bid_budget_decisions(
    case: dict[str, Any],
    numeric: Mapping[str, Any],
    level_action: str,
    *,
    execution_block_reason: str | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[str],
    list[str],
    dict[str, Any],
    dict[str, Any],
]:
    target = deepcopy(dict(_mapping(numeric.get("target_recommendation"))))
    budget_recommendation = deepcopy(
        dict(_mapping(numeric.get("budget_recommendation")))
    )
    current_target = target.get("current_value")
    recommended_target = target.get("recommended_value")
    current_budget = budget_recommendation.get("current_daily_budget")
    recommended_budget = budget_recommendation.get("recommended_value")
    target_action = str(target.get("recommended_action", "NO_CHANGE"))
    budget_action = str(budget_recommendation.get("recommended_action", "NO_CHANGE"))
    target_magnitude = (
        abs(float(target["change_percent"])) / 100
        if _finite_number(target.get("change_percent"))
        else None
    )
    budget_magnitude = (
        abs(float(budget_recommendation["change_percent"])) / 100
        if _finite_number(budget_recommendation.get("change_percent"))
        else None
    )
    reasons: list[str] = []
    requests: list[str] = []
    level_is_changing = level_action in {"move", "parallel_test", "rollback"}
    if level_is_changing:
        target_action = "NO_CHANGE"
        budget_action = "NO_CHANGE"
        recommended_target = current_target
        recommended_budget = current_budget
        target_magnitude = 0.0 if current_target is not None else None
        budget_magnitude = 0.0 if current_budget is not None else None
        reasons.append("keep_bid_and_budget_stable_during_level_change")
        target_execution_reason = "campaign_level_change_selected"
        budget_execution_reason = "campaign_level_change_selected"
    elif execution_block_reason is not None:
        target_action = "NO_CHANGE"
        budget_action = "NO_CHANGE"
        recommended_target = current_target
        recommended_budget = current_budget
        target_magnitude = 0.0 if current_target is not None else None
        budget_magnitude = 0.0 if current_budget is not None else None
        reasons.append(execution_block_reason)
        target_execution_reason = execution_block_reason
        budget_execution_reason = execution_block_reason
    else:
        target_execution_reason = None
        budget_execution_reason = None

    bid_permission = _permission_for(case, "bid")
    budget_permission = _permission_for(case, "budget")
    if (
        target.get("recommended_value") is not None
        and target.get("recommended_action") not in {"NO_CHANGE", "WAIT"}
        and bid_permission != "OPTIMIZER_CAN_EXECUTE"
    ):
        requests.append(_permission_request("bid", bid_permission))
        target_action = "NO_CHANGE"
        recommended_target = current_target
        target_magnitude = 0.0 if current_target is not None else None
        target_execution_reason = "permission_or_approval_required"
    if (
        budget_recommendation.get("recommended_value") is not None
        and budget_recommendation.get("recommended_action") not in {"NO_CHANGE", "WAIT"}
        and budget_permission != "OPTIMIZER_CAN_EXECUTE"
    ):
        requests.append(_permission_request("budget", budget_permission))
        budget_action = "NO_CHANGE"
        recommended_budget = current_budget
        budget_magnitude = 0.0 if current_budget is not None else None
        budget_execution_reason = "permission_or_approval_required"

    target["execution"] = {
        "executable_now": bool(
            target.get("recommended_value") is not None
            and target_action not in {"NO_CHANGE", "WAIT"}
            and bid_permission == "OPTIMIZER_CAN_EXECUTE"
        ),
        "permission": bid_permission,
        "immediate_action": target_action,
        "reason": target_execution_reason,
    }
    budget_recommendation["execution"] = {
        "executable_now": bool(
            budget_recommendation.get("recommended_value") is not None
            and budget_action not in {"NO_CHANGE", "WAIT"}
            and budget_permission == "OPTIMIZER_CAN_EXECUTE"
        ),
        "permission": budget_permission,
        "immediate_action": budget_action,
        "reason": budget_execution_reason,
    }

    bid = {
        "action": target_action,
        "current_target": current_target,
        "recommended_target": recommended_target,
        "recommended_change_ratio": target_magnitude,
        "source": "deterministic_numeric_decision",
        "permission": bid_permission,
    }
    budget = {
        "action": budget_action,
        "current_daily_budget": current_budget,
        "recommended_daily_budget": recommended_budget,
        "recommended_change_ratio": budget_magnitude,
        "source": "deterministic_numeric_decision",
        "permission": budget_permission,
    }
    return (
        bid,
        budget,
        _unique(reasons),
        _unique(requests),
        target,
        budget_recommendation,
    )


def _operational_classification(
    quick: Mapping[str, Any], analysis: Mapping[str, Any]
) -> dict[str, Any]:
    operational = _mapping(quick.get("operational"))
    changes = operational.get("simultaneous_changes", [])
    changes = [str(item) for item in changes] if isinstance(changes, list) else []
    active_reviews = analysis.get("experiment_reviews", [])
    active_experiment = any(
        isinstance(item, Mapping) and item.get("active", True)
        for item in active_reviews
        if isinstance(item, Mapping)
    )
    urgent = operational.get("urgent_confirmed") is True
    if urgent and len(set(changes)) > 1:
        review = _mapping(quick.get("review"))
        return {
            "classification": "OPERATIONAL_INTERVENTION",
            "experiment_validity": "NOT_A_VALID_EXPERIMENT",
            "attribution": "ATTRIBUTION_WILL_BE_CONFOUNDED",
            "causal_attribution_allowed": False,
            "active_experiment_conflict": active_experiment,
            "changed_variables": sorted(set(changes)),
            "intervention_reason": operational.get("reason"),
            "stable_baseline_review": {
                "minimum_days": review.get("after_days"),
                "minimum_mature_events": review.get("minimum_additional_mature_events"),
                "conversion_delay_must_be_mature": review.get(
                    "conversion_delay_must_be_mature"
                ),
            },
        }
    return {
        "classification": "OPERATIONAL_DECISION",
        "experiment_validity": "NOT_AN_EXPERIMENT",
        "attribution": "NOT_APPLICABLE",
        "causal_attribution_allowed": False,
        "active_experiment_conflict": active_experiment,
    }


def _review_condition(quick: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    review = _mapping(quick.get("review"))
    result = {
        "after_days": review.get("after_days"),
        "minimum_additional_mature_events": review.get(
            "minimum_additional_mature_events"
        ),
        "maximum_additional_spend": review.get("maximum_additional_spend"),
        "conversion_delay_must_be_mature": review.get(
            "conversion_delay_must_be_mature"
        ),
        "safety_review_rule": "ANY supplied time, event, or spend limit",
        "performance_conclusion_rule": "ALL declared time, volume, and delay gates",
    }
    numeric = (
        result["after_days"],
        result["minimum_additional_mature_events"],
        result["maximum_additional_spend"],
    )
    gaps = (
        []
        if any(value is not None for value in numeric)
        else ["account-specific review time, mature-event, or spend limit"]
    )
    return result, gaps


def _rollback_condition(
    quick: Mapping[str, Any], level_action: str, structure: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    supplied = _mapping(quick.get("rollback"))
    applies = level_action in {"move", "parallel_test", "rollback"} or bool(
        structure.get("create_new_campaign")
    )
    if not applies:
        return {
            "applicable": False,
            "condition": None,
            "action": None,
            "baseline_level": _level(supplied.get("baseline_level")),
        }, []
    condition = supplied.get("condition")
    action = supplied.get("action")
    gaps: list[str] = []
    if condition is None:
        gaps.append("predeclared rollback condition")
    if action is None:
        gaps.append("predeclared rollback action")
    return {
        "applicable": True,
        "condition": condition,
        "action": action,
        "baseline_level": _level(supplied.get("baseline_level")),
    }, gaps


def _summary(verdict: str, current: str | None, recommended: str | None) -> str:
    messages = {
        "KEEP_AC20_AND_TEST_AC25": "保留现有 AC2.0，同时在独立条件下测试 AC2.5。",
        "KEEP_AC25_AND_TEST_AC30": "保留现有 AC2.5，同时小规模测试 AC3.0。",
        "MOVE_AC20_TO_AC25": "把当前主力从 AC2.0 调整到已确认口径的 AC2.5。",
        "MOVE_AC25_TO_AC30": "把当前主力从 AC2.5 调整到已确认口径的 AC3.0。",
        "DO_NOT_START_AC25": "继续现有 AC2.0，暂时不要进入 AC2.5。",
        "DO_NOT_START_AC30": "继续现有 AC2.5，暂时不要进入 AC3.0。",
        "WAIT_FOR_MORE_DEEP_EVENTS": "保持现有层级，等待更多成熟深层事件。",
        "WAIT_FOR_VALUE_SIGNAL": "保持现有层级，等待可靠且成熟的价值信号。",
        "ROLL_BACK_TO_AC20": "停止扩大当前深层层级，按预案回退到 AC2.0。",
        "ROLL_BACK_TO_AC25": "停止扩大 AC3.0，按预案回退到 AC2.5。",
        "INSUFFICIENT_EVIDENCE": "当前不改层级；先补齐会改变决策的证据。",
    }
    if verdict in messages:
        return messages[verdict]
    if verdict.startswith("CREATE_NEW_"):
        return f"保留现有 {current}，并按已验证的隔离条件新建同层级 campaign。"
    if verdict.startswith("ADJUST_CURRENT_"):
        return f"调整现有 {current}，不通过复制 campaign 重启学习。"
    if verdict.startswith("CONTINUE_CURRENT_"):
        return f"继续现有 {current}，当前不新建、不并行、不切换层级。"
    return f"保持 {recommended or current or '当前设置'}，等待下一次安全复查。"


def validate_quick_decision(result: Mapping[str, Any]) -> None:
    errors: list[str] = []
    if result.get("schema_version") != QUICK_DECISION_SCHEMA_VERSION:
        errors.append("schema_version must be 1.0")
    if result.get("mode") != "quick_decision":
        errors.append("mode must be quick_decision")
    decision = _mapping(result.get("decision"))
    if decision.get("verdict") not in CAMPAIGN_VERDICTS:
        errors.append("decision.verdict is invalid")
    if decision.get("confidence") not in {"low", "medium", "high"}:
        errors.append("decision.confidence is invalid")
    if not isinstance(decision.get("summary"), str) or not decision.get("summary"):
        errors.append("decision.summary is required")
    if decision.get("primary_action_count") != 1:
        errors.append("decision.primary_action_count must be 1")
    level = _mapping(result.get("campaign_level_decision"))
    for field in ("current", "recommended", "next_candidate"):
        value = level.get(field)
        if value is not None and value not in CAMPAIGN_LEVELS:
            errors.append(f"campaign_level_decision.{field} is invalid")
    structure = _mapping(result.get("campaign_structure_decision"))
    if structure.get("action") not in STRUCTURE_ACTIONS:
        errors.append("campaign_structure_decision.action is invalid")
    for field in ("create_new_campaign", "run_in_parallel"):
        if not isinstance(structure.get(field), bool):
            errors.append(f"campaign_structure_decision.{field} must be boolean")
    if structure.get("campaign_id") is not None and not isinstance(
        structure.get("campaign_id"), str
    ):
        errors.append("campaign_structure_decision.campaign_id must be text or null")
    creative = _mapping(result.get("creative_decision"))
    if creative.get("action") not in CREATIVE_ACTIONS:
        errors.append("creative_decision.action is invalid")
    for section_name in ("bid_decision", "budget_decision"):
        section = _mapping(result.get(section_name))
        for name, value in section.items():
            if isinstance(value, float) and not math.isfinite(value):
                errors.append(f"{section_name}.{name} must be finite")
    constraint = _mapping(result.get("constraint_analysis"))
    constraint_enums = {
        "budget_state": BUDGET_DELIVERY_STATES,
        "maturity_state": MATURITY_STATES,
        "target_state": TARGET_CONSTRAINT_STATES,
        "event_volume_state": EVENT_VOLUME_STATES,
        "value_signal_state": VALUE_SIGNAL_STATES,
    }
    for field, allowed in constraint_enums.items():
        if constraint.get(field) not in allowed:
            errors.append(f"constraint_analysis.{field} is invalid")
    if not isinstance(constraint.get("has_numeric_evidence"), bool):
        errors.append("constraint_analysis.has_numeric_evidence must be boolean")
    numeric_actions = {"INCREASE", "DECREASE", "NO_CHANGE", "WAIT", "ROLLBACK"}
    recommendation_specs = {
        "target_recommendation": (
            "current_value",
            "conservative_value",
            "recommended_value",
            "aggressive_value",
            "rollback_value",
        ),
        "budget_recommendation": (
            "current_daily_budget",
            "conservative_value",
            "recommended_value",
            "aggressive_value",
            "rollback_value",
        ),
    }
    executable_count = 0
    for section_name, numeric_fields in recommendation_specs.items():
        recommendation = _mapping(result.get(section_name))
        if recommendation.get("recommended_action") not in numeric_actions:
            errors.append(f"{section_name}.recommended_action is invalid")
        for field in numeric_fields:
            if not _non_negative_or_none(recommendation.get(field)):
                errors.append(f"{section_name}.{field} must be finite and non-negative")
        current_field = (
            "current_value"
            if section_name == "target_recommendation"
            else "current_daily_budget"
        )
        ordered_values = [
            recommendation.get(current_field),
            recommendation.get("conservative_value"),
            recommendation.get("recommended_value"),
            recommendation.get("aggressive_value"),
        ]
        if all(_finite_number(value) for value in ordered_values):
            numeric_values = [
                float(cast(int | float, value)) for value in ordered_values
            ]
            if recommendation.get("recommended_action") == "INCREASE" and any(
                left > right for left, right in zip(numeric_values, numeric_values[1:])
            ):
                errors.append(f"{section_name} increase candidates must be ordered")
            if recommendation.get("recommended_action") == "DECREASE" and any(
                left < right for left, right in zip(numeric_values, numeric_values[1:])
            ):
                errors.append(f"{section_name} decrease candidates must be ordered")
        if (
            recommendation.get("recommended_action")
            in {
                "INCREASE",
                "DECREASE",
                "ROLLBACK",
            }
            and recommendation.get("recommended_value") is None
        ):
            errors.append(f"{section_name}.recommended_value is required for a change")
        if recommendation.get("change_percent") is not None and not _finite_number(
            recommendation.get("change_percent")
        ):
            errors.append(f"{section_name}.change_percent must be finite or null")
        execution = _mapping(recommendation.get("execution"))
        if execution.get("executable_now") is True:
            executable_count += 1
    if executable_count > 1:
        errors.append("only one numeric recommendation may be executable now")
    split = _mapping(result.get("split_feasibility"))
    if split.get("state") not in SPLIT_FEASIBILITY_STATES:
        errors.append("split_feasibility.state is invalid")
    evidence = result.get("calculation_evidence")
    if not isinstance(evidence, list):
        errors.append("calculation_evidence must be a list")
    else:
        for index, item in enumerate(evidence):
            if (
                not isinstance(item, Mapping)
                or item.get("type") not in CALCULATION_EVIDENCE_TYPES
            ):
                errors.append(f"calculation_evidence[{index}].type is invalid")
    heuristics = result.get("heuristics_used")
    if not isinstance(heuristics, list) or not all(
        isinstance(item, str) and item for item in heuristics
    ):
        errors.append("heuristics_used must be a list of non-empty strings")
    legacy_hints = result.get("legacy_hints_ignored")
    if not isinstance(legacy_hints, list) or not all(
        item in {"recommended_target", "recommended_daily_budget"}
        for item in legacy_hints
    ):
        errors.append("legacy_hints_ignored is invalid")
    if result.get("account_write") is not False:
        errors.append("account_write must be false")
    if result.get("ledger_write") is not False:
        errors.append("ledger_write must be false")
    if result.get("experiments") != []:
        errors.append("Quick Decision must not create experiments")
    if result.get("human_confirmation_required_for_live_write") is not True:
        errors.append("human_confirmation_required_for_live_write must be true")
    if not isinstance(result.get("reason_codes"), list) or not result.get(
        "reason_codes"
    ):
        errors.append("reason_codes must be non-empty")
    if not isinstance(result.get("review_condition"), Mapping):
        errors.append("review_condition is required")
    if not isinstance(result.get("rollback"), Mapping):
        errors.append("rollback is required")
    upgrade = _mapping(result.get("upgrade_condition"))
    if (
        upgrade.get("target_level") is not None
        and upgrade.get("target_level") not in CAMPAIGN_LEVELS
    ):
        errors.append("upgrade_condition.target_level is invalid")
    if not isinstance(upgrade.get("requirements"), list):
        errors.append("upgrade_condition.requirements must be a list")
    permission = _mapping(result.get("permission_check"))
    for field in (
        "allowed",
        "requires_client_approval",
        "requires_exact_live_edit_confirmation",
    ):
        if not isinstance(permission.get(field), bool):
            errors.append(f"permission_check.{field} must be boolean")
    if not isinstance(permission.get("client_requests"), list):
        errors.append("permission_check.client_requests must be a list")
    if errors:
        raise ContractError("invalid Quick Decision: " + "; ".join(errors))


def decide_case(
    case: dict[str, Any],
    ledger: dict[str, Any] | None = None,
    *,
    question: str | None = None,
    project_glossary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one deterministic, read-only operation card from supplied facts."""

    _validate_quick_input(case)
    analysis = analyze_case(case, ledger)
    derived_signals = derive_signals(case)
    numeric = recommend_numeric(case, derived_signals)
    decision_case = apply_derived_signals(case, derived_signals)
    quick = _mapping(decision_case.get("quick_ops"))
    prompt = question if question is not None else str(quick.get("question", ""))
    route = route_question(prompt)
    current_campaign = _mapping(quick.get("current_campaign"))
    candidate_campaign = _mapping(quick.get("candidate_campaign"))
    current = _level(current_campaign.get("level"))
    mentioned = extract_campaign_levels(prompt)
    candidate = _level(candidate_campaign.get("level")) or _level(
        quick.get("candidate_level")
    )
    if candidate is None:
        candidate = next((item for item in mentioned if item != current), None)
    if candidate is None and len(mentioned) == 1 and mentioned[0] != current:
        candidate = mentioned[0]
    switching = candidate is not None and current is not None and candidate != current

    merged_glossary = normalize_glossary(
        _mapping(decision_case.get("campaign_level_glossary"))
    )
    merged_glossary.update(normalize_glossary(project_glossary))
    target_term: Any = quick.get("user_term") or candidate or current
    terminology = resolve_campaign_level(
        target_term,
        glossary=merged_glossary,
        account=candidate_campaign if candidate is not None else current_campaign,
        mapping_confirmed=quick.get("terminology_mapping_confirmed") is True,
        switching=switching,
    )
    current_resolution = resolve_campaign_level(
        current,
        glossary=merged_glossary,
        account=current_campaign,
        mapping_confirmed=quick.get("terminology_mapping_confirmed") is True,
        switching=False,
    )
    terminology = {**terminology, "current_resolution": current_resolution}

    requested_question_type = str(quick.get("question_type") or route["question_type"])
    level_decision: dict[str, Any]
    if route["mode"] != "quick_decision":
        level_decision = {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "recommended": current,
            "action": "keep",
            "structure": {
                "action": "WAIT",
                "create_new_campaign": False,
                "run_in_parallel": False,
                "permission": "NOT_ACTIONABLE",
                "reason_codes": ["request_routes_to_different_mode"],
                "data_gaps": [],
                "client_requests": [],
            },
            "reason_codes": ["request_routes_to_different_mode"],
            "data_gaps": [f"use {route['mode']} mode for this request"],
            "client_requests": [],
        }
    else:
        level_decision = _level_decision(
            decision_case,
            quick,
            analysis,
            current,
            candidate,
            terminology,
            requested_question_type,
            numeric,
        )

    structure = _mapping(level_decision["structure"])
    creative = _creative_decision(
        decision_case,
        quick,
        str(structure.get("action", "WAIT")),
        requested_question_type,
    )
    (
        bid,
        budget,
        bid_budget_reasons,
        bid_budget_requests,
        target_recommendation,
        budget_recommendation,
    ) = _bid_budget_decisions(
        decision_case,
        numeric,
        str(level_decision["action"]),
        execution_block_reason=(
            "numeric_change_blocked_by_unfinished_experiment"
            if "unfinished_experiment_blocks_stacked_change"
            in level_decision["reason_codes"]
            else None
        ),
    )
    classification = _operational_classification(quick, analysis)
    review, review_gaps = _review_condition(quick)
    rollback, rollback_gaps = _rollback_condition(
        quick, str(level_decision["action"]), structure
    )

    reason_codes = _unique(
        [
            *level_decision["reason_codes"],
            *structure.get("reason_codes", []),
            *creative["reason_codes"],
            *bid_budget_reasons,
        ]
    )
    if derived_signals.get("has_numeric_evidence") is True:
        target_reason = str(target_recommendation.get("reason", ""))
        budget_reason = str(budget_recommendation.get("reason", ""))
        reason_codes.extend(
            item
            for item in (
                f"numeric_target_{target_reason}" if target_reason else "",
                f"numeric_budget_{budget_reason}" if budget_reason else "",
            )
            if item
        )
    data_gaps = _unique(
        [
            *level_decision["data_gaps"],
            *structure.get("data_gaps", []),
            *creative["data_gaps"],
            *review_gaps,
            *rollback_gaps,
        ]
    )
    if derived_signals.get("has_numeric_evidence") is True:
        gap_reasons = {
            "business_cpa_ceiling_missing",
            "business_roas_floor_missing",
            "business_daily_budget_cap_missing",
            "current_target_missing",
            "current_daily_budget_missing",
            "mature_actual_cpa_missing",
            "mature_actual_roas_missing",
            "insufficient_mature_conversion_data",
            "value_signal_not_reliable_enough_for_troas",
        }
        data_gaps.extend(
            reason
            for reason in (
                target_recommendation.get("reason"),
                budget_recommendation.get("reason"),
            )
            if reason in gap_reasons
        )
    client_requests = _unique(
        [
            *level_decision["client_requests"],
            *structure.get("client_requests", []),
            *creative["client_requests"],
            *bid_budget_requests,
        ]
    )
    if quick.get("permission_profile") == "mmp_access_without_backend_access":
        data_gaps.append("backend value reconciliation")
        reason_codes.append("mmp_without_backend_evidence")
    if quick.get("permission_profile") == "aggregate_data_only":
        data_gaps.append("campaign and asset-level segmented evidence")
        reason_codes.append("aggregate_data_cannot_support_action")
    reason_codes = _unique(reason_codes)
    data_gaps = _unique(data_gaps)

    if terminology.get("confidence") == "low" or data_gaps:
        confidence = "low"
    elif terminology.get("confidence") == "medium":
        confidence = "medium"
    else:
        confidence = str(quick.get("confidence", "medium"))
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"

    verdict = str(level_decision["verdict"])
    recommended_value = level_decision["recommended"]
    recommended = recommended_value if isinstance(recommended_value, str) else None
    next_candidate = candidate if candidate != recommended else None
    campaign_id = current_campaign.get("id") or current_campaign.get("campaign_id")
    structure_decision = deepcopy(dict(structure))
    structure_decision["campaign_id"] = campaign_id
    upgrade_requirements = _unique(
        [
            *level_decision["data_gaps"],
            *(
                [
                    "stable_payment_value_volume",
                    "reliable_value_and_currency",
                    "value_specific_reconciliation",
                ]
                if candidate == "AC3.0"
                and level_decision["action"] not in {"move", "parallel_test"}
                else []
            ),
        ]
    )
    result = {
        "schema_version": QUICK_DECISION_SCHEMA_VERSION,
        "mode": "quick_decision",
        "requested_mode": route["mode"],
        "question_type": requested_question_type,
        "terminology": terminology,
        "decision": {
            "verdict": verdict,
            "confidence": confidence,
            "summary": _summary(verdict, current, recommended),
            "primary_action_count": 1,
        },
        "campaign_level_decision": {
            "current": current,
            "recommended": recommended,
            "next_candidate": next_candidate,
            "action": level_decision["action"],
            "upgrade_allowed": level_decision["action"] in {"move", "parallel_test"},
        },
        "campaign_structure_decision": structure_decision,
        "creative_decision": creative,
        "bid_decision": bid,
        "budget_decision": budget,
        "constraint_analysis": numeric["constraint_analysis"],
        "target_recommendation": target_recommendation,
        "budget_recommendation": budget_recommendation,
        "split_feasibility": numeric["split_feasibility"],
        "derived_signals": derived_signals,
        "calculation_evidence": numeric["calculation_evidence"],
        "heuristics_used": numeric["heuristics_used"],
        "legacy_hints_ignored": numeric["legacy_hints_ignored"],
        "permission_check": {
            "allowed": not client_requests,
            "requires_client_approval": any(
                "approval" in request for request in client_requests
            ),
            "requires_exact_live_edit_confirmation": True,
            "client_requests": client_requests,
        },
        "classification": classification,
        "reason_codes": reason_codes or ["safe_hold_by_default"],
        "data_gaps": data_gaps,
        "do_not_do": _unique(
            [
                "do_not_treat_ac_labels_as_bid_values",
                "do_not_duplicate_only_to_restart_learning",
                "do_not_change_level_bid_budget_and_creative_together",
                "do_not_edit_google_ads_without_exact_human_confirmation",
            ]
        ),
        "review_condition": review,
        "upgrade_condition": {
            "target_level": candidate,
            "requirements": upgrade_requirements,
        },
        "upgrade_requirements": upgrade_requirements,
        "rollback": rollback,
        "experiments": [],
        "account_write": False,
        "ledger_write": False,
        "human_confirmation_required_for_live_write": True,
    }
    validate_quick_decision(result)
    return result
