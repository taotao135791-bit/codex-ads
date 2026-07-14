"""Safety-first behavior contracts for UAC numeric recommendations.

The public contract is deliberately formula-agnostic: tests constrain direction,
business limits, evidence, permissions, and no-action behavior without requiring
one universal percentage step. All account values are synthetic.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.numeric_decision import recommend_numeric  # noqa: E402


ALLOWED_EVIDENCE_TYPES = {
    "ACCOUNT_EVIDENCE",
    "BUSINESS_CONSTRAINT",
    "PLATFORM_GUIDANCE",
    "HEURISTIC",
    "INSUFFICIENT_EVIDENCE",
}


def _daily_series(
    spends: list[float], events: list[int], values: list[float] | None = None
) -> list[dict[str, Any]]:
    if values is None:
        values = [event * 10.0 for event in events]
    return [
        {
            "date": f"2026-07-{index:02d}",
            "spend": spend,
            "mature_events": event,
            "value": value,
        }
        for index, (spend, event, value) in enumerate(
            zip(spends, events, values, strict=True), start=1
        )
    ]


def _permissions(*optimizer_can: str) -> dict[str, list[str]]:
    return {
        "optimizer_can": list(optimizer_can),
        "client_approval_required": [],
        "client_data_required": [],
        "platform_limitations": [],
        "unavailable": [],
    }


def _base_case() -> dict[str, Any]:
    return {
        "goal": {
            "business_goal": "payment",
            "bidding_strategy": "tcpa",
            "target_cpa": 5.0,
            "target_roas": None,
            "maximum_acceptable_cpa": 6.0,
            "minimum_acceptable_roas": 1.5,
            "optimization_priority": "scale",
            "daily_budget_cap": 160.0,
        },
        "facts": {
            "campaign_level": "AC2.5",
            "daily_budget": 100.0,
            "metrics": {
                "spend": 455.0,
                "mature_actual_cpa": 4.8,
                "mature_actual_roas": 2.2,
                "mature_conversions": 70,
                "mature_revenue": 1001.0,
            },
            "daily_series": _daily_series([65.0] * 7, [10] * 7),
        },
        "maturity": {
            "days_elapsed": 7,
            "minimum_days": 3,
            "conversion_delay_days": 2,
            "conversion_delay_elapsed_days": 7,
            "days_since_last_change": 7,
            "last_change_variables": [],
            "mature_events_since_change": 70,
            "minimum_conversions": 10,
        },
        "measurement": {
            "value_missing_rate": 0.0,
            "currency_consistency_rate": 1.0,
            "google_mmp_value_difference_rate": 0.02,
            "mmp_backend_value_difference_rate": 0.03,
            "refund_rate": 0.05,
        },
        "permissions": _permissions(
            "bid", "budget", "creative", "campaign_create", "optimization_event"
        ),
    }


def _action(section: dict[str, Any]) -> str:
    return str(section["recommended_action"]).upper()


def _recommendation(result: dict[str, Any], name: str) -> dict[str, Any]:
    section = result[name]
    assert isinstance(section, dict)
    return section


def test_target_limited_mature_case_recommends_one_bounded_tcpa_value():
    case = _base_case()
    result = recommend_numeric(case)
    target = _recommendation(result, "target_recommendation")
    budget = _recommendation(result, "budget_recommendation")

    assert result["constraint_analysis"]["primary_constraint"] == (
        "TARGET_LIKELY_TOO_TIGHT"
    )
    assert _action(target) == "INCREASE"
    assert 5.0 < target["recommended_value"] <= 6.0
    assert 5.0 <= target["conservative_value"] <= target["recommended_value"]
    assert target["recommended_value"] <= target["aggressive_value"] <= 6.0
    assert target["change_percent"] > 0
    assert _action(budget) == "NO_CHANGE"
    assert budget["recommended_value"] == 100.0


def test_numeric_recommendation_has_typed_evidence_review_and_rollback():
    result = recommend_numeric(_base_case())
    target = result["target_recommendation"]

    assert result["calculation_evidence"]
    assert {item["type"] for item in result["calculation_evidence"]}.issubset(
        ALLOWED_EVIDENCE_TYPES
    )
    assert "ACCOUNT_EVIDENCE" in {
        item["type"] for item in result["calculation_evidence"]
    }
    assert "BUSINESS_CONSTRAINT" in {
        item["type"] for item in result["calculation_evidence"]
    }
    assert target["calculation_basis"]
    assert target["rollback_value"] == 5.0
    assert target["rollback_condition"]
    assert target["do_not_change_before"]["minimum_days"] > 0
    assert target["do_not_change_before"]["minimum_mature_events"] > 0


def test_recent_target_change_waits_instead_of_changing_again():
    case = _base_case()
    case["maturity"].update(
        {
            "days_since_last_change": 1,
            "last_change_variables": ["target_cpa"],
            "mature_events_since_change": 1,
        }
    )

    target = recommend_numeric(case)["target_recommendation"]

    assert _action(target) in {"WAIT", "NO_CHANGE"}
    assert target["recommended_value"] is None


def test_budget_constrained_case_increases_budget_without_changing_target():
    case = _base_case()
    case["facts"]["daily_series"] = _daily_series([100.0] * 7, [10] * 7)
    case["facts"]["metrics"]["spend"] = 700.0
    case["facts"]["budget_limited"] = True

    result = recommend_numeric(case)
    budget = result["budget_recommendation"]
    target = result["target_recommendation"]

    assert result["constraint_analysis"]["primary_constraint"] == ("BUDGET_CONSTRAINED")
    assert _action(budget) == "INCREASE"
    assert 100.0 < budget["recommended_value"] <= 160.0
    assert _action(target) == "NO_CHANGE"
    assert target["recommended_value"] == 5.0


def test_unknown_primary_constraint_returns_null_instead_of_guessing():
    case = _base_case()
    case["facts"].pop("daily_series")
    case["facts"]["metrics"].pop("spend")
    case["facts"]["metrics"].pop("mature_actual_cpa")
    case["maturity"].pop("days_elapsed")

    result = recommend_numeric(case)

    assert result["constraint_analysis"]["primary_constraint"] in {
        "UNKNOWN",
        "INSUFFICIENT_EVIDENCE",
        "DATA_MATURITY",
    }
    assert result["target_recommendation"]["recommended_value"] is None
    assert result["budget_recommendation"]["recommended_value"] is None
    assert result["data_gaps"]


def test_mature_cpa_over_business_limit_never_relaxes_tcpa_further():
    case = _base_case()
    case["facts"]["metrics"]["mature_actual_cpa"] = 7.0

    target = recommend_numeric(case)["target_recommendation"]

    assert _action(target) != "INCREASE"
    assert target["recommended_value"] is None or target["recommended_value"] <= 5.0


def test_business_limits_are_hard_boundaries_and_never_unsafe_rollback_values():
    target_case = _base_case()
    target_case["goal"]["target_cpa"] = 7.0
    target_case["facts"]["metrics"]["mature_actual_cpa"] = 7.0
    target = recommend_numeric(target_case)["target_recommendation"]

    assert _action(target) == "DECREASE"
    assert target["recommended_value"] <= 6.0
    assert target["rollback_value"] is None

    budget_case = _base_case()
    budget_case["facts"]["daily_budget"] = 200.0
    budget_case["goal"]["daily_budget_cap"] = 160.0
    budget = recommend_numeric(budget_case)["budget_recommendation"]

    assert _action(budget) == "DECREASE"
    assert budget["recommended_value"] <= 160.0
    assert budget["rollback_value"] is None


def test_immature_settings_are_still_corrected_to_declared_hard_boundaries():
    budget_case = _base_case()
    budget_case["facts"]["daily_budget"] = 200.0
    budget_case["goal"]["daily_budget_cap"] = 140.0
    budget_case["maturity"].update(
        {
            "days_since_last_change": 1,
            "mature_events_since_change": 1,
            "conversion_delay_elapsed_days": 0,
        }
    )
    budget_result = recommend_numeric(budget_case)
    assert budget_result["constraint_analysis"]["primary_constraint"] == (
        "BUSINESS_BUDGET_CAP"
    )
    assert budget_result["budget_recommendation"]["recommended_action"] == "DECREASE"
    assert budget_result["budget_recommendation"]["recommended_value"] == 140.0
    assert budget_result["budget_recommendation"]["rollback_value"] is None

    tcpa_case = _base_case()
    tcpa_case["goal"]["target_cpa"] = 7.0
    tcpa_case["maturity"].update(
        {
            "days_since_last_change": 1,
            "mature_events_since_change": 1,
            "conversion_delay_elapsed_days": 0,
        }
    )
    tcpa_result = recommend_numeric(tcpa_case)
    assert tcpa_result["constraint_analysis"]["primary_constraint"] == (
        "BUSINESS_TARGET_BOUNDARY"
    )
    assert tcpa_result["target_recommendation"]["recommended_action"] == "DECREASE"
    assert tcpa_result["target_recommendation"]["recommended_value"] == 6.0
    assert tcpa_result["target_recommendation"]["rollback_value"] is None

    troas_case = _base_case()
    troas_case["goal"].update(
        {
            "bidding_strategy": "troas",
            "target_cpa": None,
            "target_roas": 1.5,
            "minimum_acceptable_roas": 2.0,
        }
    )
    troas_case["maturity"].update(
        {
            "days_since_last_change": 1,
            "mature_events_since_change": 1,
            "conversion_delay_elapsed_days": 0,
        }
    )
    troas_result = recommend_numeric(troas_case)
    assert troas_result["constraint_analysis"]["primary_constraint"] == (
        "BUSINESS_TARGET_BOUNDARY"
    )
    assert troas_result["target_recommendation"]["recommended_action"] == "INCREASE"
    assert troas_result["target_recommendation"]["recommended_value"] == 2.0
    assert troas_result["target_recommendation"]["rollback_value"] is None


@pytest.mark.parametrize("strategy", ["tcpa", "troas"])
def test_measurement_mismatch_does_not_block_a_declared_target_boundary(strategy):
    case = _base_case()
    case["measurement"]["google_ads_vs_mmp"] = "material_mismatch"
    if strategy == "tcpa":
        case["goal"]["target_cpa"] = 7.0
        expected_action = "DECREASE"
        expected_value = 6.0
    else:
        case["goal"].update(
            {
                "bidding_strategy": "troas",
                "target_cpa": None,
                "target_roas": 1.5,
                "minimum_acceptable_roas": 2.0,
            }
        )
        expected_action = "INCREASE"
        expected_value = 2.0

    target = recommend_numeric(case)["target_recommendation"]

    assert target["recommended_action"] == expected_action
    assert target["recommended_value"] == expected_value
    assert target["rollback_value"] is None


def test_budget_cap_correction_precedes_a_simultaneous_target_boundary_violation():
    case = _base_case()
    case["facts"]["daily_budget"] = 200.0
    case["goal"]["daily_budget_cap"] = 140.0
    case["goal"]["target_cpa"] = 7.0

    result = recommend_numeric(case)

    assert result["constraint_analysis"]["primary_constraint"] == (
        "BUSINESS_BUDGET_CAP"
    )
    assert result["budget_recommendation"]["recommended_action"] == "DECREASE"
    assert result["budget_recommendation"]["recommended_value"] == 140.0
    assert result["target_recommendation"]["recommended_action"] == "NO_CHANGE"
    assert result["target_recommendation"]["recommended_value"] == 7.0


def test_scale_priority_is_capped_and_not_more_conservative_than_efficiency():
    scale_case = _base_case()
    efficiency_case = deepcopy(scale_case)
    efficiency_case["goal"]["optimization_priority"] = "efficiency"

    scale = recommend_numeric(scale_case)["target_recommendation"]
    efficiency = recommend_numeric(efficiency_case)["target_recommendation"]

    assert scale["recommended_value"] <= scale_case["goal"]["maximum_acceptable_cpa"]
    assert efficiency["recommended_value"] <= scale["recommended_value"]


def test_missing_business_limit_never_returns_an_aggressive_value():
    case = _base_case()
    case["goal"].pop("maximum_acceptable_cpa")

    target = recommend_numeric(case)["target_recommendation"]

    assert target["aggressive_value"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "immature",
        "measurement_unreliable",
        "recent_multi_variable_change",
    ],
)
def test_high_risk_states_prohibit_precise_target_values(mutation):
    case = _base_case()
    if mutation == "immature":
        case["maturity"].update(
            {
                "days_since_last_change": 1,
                "mature_events_since_change": 1,
                "conversion_delay_elapsed_days": 0,
            }
        )
    elif mutation == "measurement_unreliable":
        case["measurement"].update(
            {
                "currency_consistency_rate": 0.5,
                "google_mmp_value_difference_rate": 0.5,
                "mmp_backend_value_difference_rate": 0.5,
            }
        )
    else:
        case["maturity"].update(
            {
                "days_since_last_change": 1,
                "last_change_variables": ["bid", "budget", "creative"],
                "mature_events_since_change": 1,
            }
        )

    target = recommend_numeric(case)["target_recommendation"]

    assert _action(target) in {"WAIT", "NO_CHANGE", "UNABLE_TO_CALCULATE"}
    assert target["recommended_value"] is None


def test_reliable_value_data_can_produce_a_bounded_troas_candidate():
    case = _base_case()
    case["goal"].update(
        {
            "bidding_strategy": "troas",
            "target_cpa": None,
            "target_roas": 3.0,
            "minimum_acceptable_roas": 2.0,
        }
    )
    case["facts"]["metrics"]["mature_actual_roas"] = 2.5

    target = recommend_numeric(case)["target_recommendation"]

    assert target["target_type"].upper() == "TROAS"
    assert _action(target) == "DECREASE"
    assert 2.0 <= target["recommended_value"] < 3.0
    assert target["rollback_value"] == 3.0


def test_unreliable_value_data_prohibits_a_troas_number():
    case = _base_case()
    case["goal"].update(
        {
            "bidding_strategy": "troas",
            "target_cpa": None,
            "target_roas": 3.0,
        }
    )
    case["measurement"].update(
        {
            "value_missing_rate": 0.4,
            "currency_consistency_rate": 0.5,
            "google_mmp_value_difference_rate": 0.5,
            "mmp_backend_value_difference_rate": 0.5,
        }
    )

    target = recommend_numeric(case)["target_recommendation"]

    assert target["target_type"].upper() == "TROAS"
    assert target["recommended_value"] is None
    assert _action(target) in {"WAIT", "NO_CHANGE", "UNABLE_TO_CALCULATE"}


def test_troas_requires_sufficient_mature_value_event_volume():
    case = _base_case()
    case["goal"].update(
        {
            "bidding_strategy": "troas",
            "target_cpa": None,
            "target_roas": 3.0,
        }
    )
    case["facts"]["daily_series"] = _daily_series([65.0] * 7, [0, 1, 0, 1, 0, 1, 0])

    target = recommend_numeric(case)["target_recommendation"]

    assert target["recommended_value"] is None
    assert _action(target) in {"WAIT", "NO_CHANGE"}


def test_caller_supplied_extreme_values_cannot_bypass_numeric_safety():
    case = _base_case()
    case["quick_ops"] = {
        "bid_budget": {
            "recommended_target": 100.0,
            "recommended_daily_budget": 10_000.0,
        }
    }

    result = recommend_numeric(case)

    assert result["target_recommendation"]["recommended_value"] <= 6.0
    budget_value = result["budget_recommendation"]["recommended_value"]
    assert budget_value is None or budget_value <= 160.0


def test_ac_label_is_never_used_as_a_numeric_target():
    case = _base_case()
    case["goal"]["target_cpa"] = None
    case["goal"]["target_roas"] = None
    case["facts"]["campaign_level"] = "AC2.5"

    target = recommend_numeric(case)["target_recommendation"]

    assert target["current_value"] is None
    assert target["recommended_value"] is None
    assert 2.5 not in {
        target.get("conservative_value"),
        target.get("recommended_value"),
        target.get("aggressive_value"),
    }


def test_one_day_volatility_cannot_trigger_a_large_numeric_change():
    case = _base_case()
    case["facts"]["daily_series"] = _daily_series([1.0], [0])
    case["maturity"].update(
        {
            "days_elapsed": 1,
            "days_since_last_change": 1,
            "mature_events_since_change": 0,
        }
    )

    result = recommend_numeric(case)

    assert result["target_recommendation"]["recommended_value"] is None
    assert result["budget_recommendation"]["recommended_value"] is None


def test_ordinary_recommendation_changes_at_most_one_numeric_variable():
    result = recommend_numeric(_base_case())
    changed = [
        name
        for name in ("target_recommendation", "budget_recommendation")
        if _action(result[name]) in {"INCREASE", "DECREASE"}
    ]

    assert len(changed) <= 1
    assert result.get("classification", {}).get("experiment_validity") != (
        "VALID_EXPERIMENT"
    )


def test_split_not_feasible_when_budget_or_events_fail_after_division():
    case = _base_case()
    case["facts"]["daily_budget"] = 100.0
    case["facts"]["metrics"]["mature_conversions"] = 20
    case["facts"]["split_plan"] = {
        "campaign_count": 2,
        "minimum_daily_budget_per_campaign": 60.0,
        "minimum_daily_events_per_campaign": 15,
        "existing_level": "AC2.5",
        "candidate_level": "AC3.0",
    }

    split = recommend_numeric(case)["split_feasibility"]

    assert split["state"] == "SPLIT_NOT_FEASIBLE"
    assert (
        split["projected_daily_events_per_campaign"]
        < (split["minimum_daily_events_per_campaign"])
    )


def test_split_uses_current_total_budget_before_a_larger_business_cap():
    case = _base_case()
    case["facts"]["daily_budget"] = 60.0
    case["goal"]["daily_budget_cap"] = 200.0
    case["facts"]["split_plan"] = {
        "campaign_count": 2,
        "minimum_daily_budget_per_campaign": 40.0,
        "minimum_daily_events_per_campaign": 2,
    }

    split = recommend_numeric(case)["split_feasibility"]

    assert split["available_total_daily_budget"] == 60.0
    assert split["state"] == "SPLIT_NOT_FEASIBLE"


def test_feasible_ac30_parallel_plan_has_separate_budgets_without_fake_troas():
    case = _base_case()
    case["facts"]["daily_budget"] = 200.0
    case["goal"]["daily_budget_cap"] = 200.0
    case["facts"]["metrics"]["mature_conversions"] = 100
    case["facts"]["daily_series"] = _daily_series([180.0] * 7, [50] * 7)
    case["facts"]["split_plan"] = {
        "campaign_count": 2,
        "minimum_daily_budget_per_campaign": 40.0,
        "minimum_daily_events_per_campaign": 20,
        "existing_daily_budget_floor": 160.0,
        "existing_level": "AC2.5",
        "candidate_level": "AC3.0",
        "candidate_target_type": "troas",
    }
    case["goal"]["target_roas"] = None

    result = recommend_numeric(case)
    split = result["split_feasibility"]

    assert split["state"] == "SPLIT_FEASIBLE"
    assert split["existing_campaign_daily_budget"] == 160.0
    assert split["new_campaign_daily_budget"] == 40.0
    assert (
        split["existing_campaign_daily_budget"] + split["new_campaign_daily_budget"]
        <= 200.0
    )
    assert split.get("candidate_target_value") is None


def test_missing_split_thresholds_return_insufficient_evidence():
    case = _base_case()
    case["facts"]["split_plan"] = {
        "campaign_count": 2,
        "existing_level": "AC2.5",
        "candidate_level": "AC3.0",
    }

    split = recommend_numeric(case)["split_feasibility"]

    assert split["state"] == "INSUFFICIENT_EVIDENCE"
    assert split.get("data_gaps") or split.get("reasons")


def test_target_constraint_keeps_current_campaign_level_before_ac30():
    case = _base_case()
    case["facts"]["split_plan"] = {
        "campaign_count": 2,
        "minimum_daily_budget_per_campaign": 40.0,
        "minimum_daily_events_per_campaign": 20,
        "existing_level": "AC2.5",
        "candidate_level": "AC3.0",
    }

    result = recommend_numeric(case)

    assert result["constraint_analysis"]["primary_constraint"] == (
        "TARGET_LIKELY_TOO_TIGHT"
    )
    assert result["campaign_level_guidance"]["immediate_action"] == "KEEP_CURRENT"
    assert result["campaign_level_guidance"]["recommended_level"] == "AC2.5"


def test_low_candidate_event_density_is_not_fixed_by_forcing_more_budget():
    case = _base_case()
    case["facts"]["split_plan"] = {
        "campaign_count": 2,
        "minimum_daily_budget_per_campaign": 40.0,
        "minimum_daily_events_per_campaign": 20,
        "candidate_event_mature_events": 5,
        "existing_level": "AC2.5",
        "candidate_level": "AC3.0",
    }

    result = recommend_numeric(case)

    assert result["split_feasibility"]["state"] == "SPLIT_NOT_FEASIBLE"
    assert _action(result["budget_recommendation"]) != "INCREASE"


def test_budget_only_permission_exposes_only_an_executable_budget_change():
    case = _base_case()
    case["facts"]["daily_series"] = _daily_series([100.0] * 7, [10] * 7)
    case["facts"]["metrics"]["spend"] = 700.0
    case["facts"]["budget_limited"] = True
    case["permissions"] = _permissions("budget")

    result = recommend_numeric(case)

    assert result["budget_recommendation"]["executable_now"] is True
    assert _action(result["budget_recommendation"]) == "INCREASE"
    assert _action(result["target_recommendation"]) == "NO_CHANGE"


def test_bid_only_permission_exposes_only_an_executable_target_change():
    case = _base_case()
    case["permissions"] = _permissions("bid")

    result = recommend_numeric(case)

    assert result["target_recommendation"]["executable_now"] is True
    assert _action(result["target_recommendation"]) == "INCREASE"
    assert _action(result["budget_recommendation"]) == "NO_CHANGE"


@pytest.mark.parametrize(
    "permissions",
    [
        _permissions("creative"),
        _permissions(),
        {
            **_permissions(),
            "client_approval_required": ["bid", "budget", "campaign_create"],
        },
    ],
    ids=["creative-only", "read-only", "approval-required"],
)
def test_restricted_permissions_preserve_ideal_value_but_do_not_execute(permissions):
    case = _base_case()
    case["permissions"] = permissions

    result = recommend_numeric(case)
    target = result["target_recommendation"]

    assert target["recommended_value"] > target["current_value"]
    assert target["executable_now"] is False
    assert target["client_request"]


def test_read_only_numeric_recommendation_does_not_mutate_input_or_claim_a_write():
    case = _base_case()
    case["permissions"] = _permissions()
    before = deepcopy(case)

    result = recommend_numeric(case)

    assert case == before
    assert result["account_write"] is False
    assert result.get("ledger_write", False) is False


def test_cannot_create_campaign_keeps_ac30_as_a_future_candidate_only():
    case = _base_case()
    case["permissions"] = _permissions("bid", "budget", "creative")
    case["permissions"]["platform_limitations"] = ["campaign_create"]
    case["facts"]["split_plan"] = {
        "campaign_count": 2,
        "minimum_daily_budget_per_campaign": 40.0,
        "minimum_daily_events_per_campaign": 20,
        "existing_level": "AC2.5",
        "candidate_level": "AC3.0",
    }

    guidance = recommend_numeric(case)["campaign_level_guidance"]

    assert guidance["immediate_action"] == "KEEP_CURRENT"
    assert guidance["future_candidate"] == "AC3.0"
    assert guidance["executable_now"] is False
