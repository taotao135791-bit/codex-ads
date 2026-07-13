"""Deterministic behavior regression tests for the UAC Experiment Loop.

These tests replay account facts through the real rule engine.  They do not
call Google Ads, an LLM, or any other external service.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest
import yaml

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "uac-cases.yaml"
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from uac_experiment import (  # noqa: E402
    PERMISSION_CLASSES,
    analyze_case,
    review_experiment,
    validate_experiment,
)


FIXTURES = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
CASES = FIXTURES["cases"]
REVIEW_CASES = FIXTURES["review_cases"]

REQUIRED_CASE_IDS = {
    "cheap_installs_zero_payments",
    "severely_insufficient_payment_events",
    "tcpa_target_too_tight",
    "budget_cannot_support_goal",
    "new_creative_not_mature",
    "short_term_creative_drop_with_delay",
    "country_total_hides_segment_anomaly",
    "android_normal_ios_tracking_abnormal",
    "google_mmp_payment_mismatch",
    "registration_normal_paywall_low",
    "payment_kpi_without_reliable_payment_event",
    "optimizer_has_only_budget_bid_creative",
    "budget_and_creative_changed_together",
    "observation_elapsed_but_volume_low",
    "lowest_cpi_has_worst_payment_rate",
    "no_material_anomaly_hold",
}
BLOCKING_STATES = {
    "DATA_BLOCKED",
    "PERMISSION_BLOCKED",
    "TRACKING_BLOCKED",
    "PRODUCT_FUNNEL_BLOCKED",
    "LEARNING_BLOCKED",
}


def _case(case_id: str) -> dict:
    return next(item for item in CASES if item["id"] == case_id)


def _analyze(case_id: str) -> dict:
    return analyze_case(deepcopy(_case(case_id)["input"]))


def test_fixture_suite_contains_the_16_required_user_scenarios() -> None:
    assert len(CASES) == 16
    assert {case["id"] for case in CASES} == REQUIRED_CASE_IDS


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_each_fixture_declares_replay_facts_permissions_maturity_and_expectations(
    case: dict,
) -> None:
    input_case = case["input"]
    expected = case["expected"]

    assert input_case["facts"]["metrics"]
    assert input_case["evidence"]
    assert set(input_case["permissions"]) >= {
        "optimizer_can",
        "client_approval_required",
        "unavailable",
    }
    assert set(input_case["maturity"]) >= {
        "days_elapsed",
        "minimum_days",
        "conversions_observed",
        "minimum_conversions",
        "conversion_delay_elapsed_days",
        "conversion_delay_days",
    }
    assert set(expected) >= {
        "diagnosis",
        "feasibility",
        "blocker",
        "learning",
        "allowed_variables",
        "forbidden_variables",
        "experiment_allowed",
        "experiment_status",
    }
    assert expected["allowed_variables"]
    assert expected["forbidden_variables"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_analyze_case_replays_expected_diagnosis_blocker_and_recommendation_policy(
    case: dict,
) -> None:
    result = analyze_case(deepcopy(case["input"]))
    expected = case["expected"]

    assert len(result["diagnoses"]) == 1
    assert result["diagnoses"][0]["code"] == expected["diagnosis"]
    assert result["diagnoses"][0]["causal_claim"] is False
    assert result["diagnoses"][0]["permission_classification"] in PERMISSION_CLASSES
    assert result["optimization_feasibility"]["status"] == expected["feasibility"]
    actual_blocker = (
        expected["feasibility"] if expected["feasibility"] in BLOCKING_STATES else None
    )
    assert actual_blocker == expected["blocker"]
    assert result["learning_eligibility"]["status"] == expected["learning"]

    recommendation_variables = {
        recommendation["variable"] for recommendation in result["recommendations"]
    }
    assert set(expected["allowed_variables"]) <= recommendation_variables
    assert recommendation_variables.isdisjoint(expected["forbidden_variables"])

    reviews = result["experiment_reviews"]
    actual_review_status = reviews[0]["status"] if reviews else None
    assert actual_review_status == expected["experiment_status"]
    assert bool(result["experiments"]) is expected["experiment_allowed"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_recommendations_and_experiments_never_overstate_optimizer_permission(
    case: dict,
) -> None:
    result = analyze_case(deepcopy(case["input"]))
    permissions = case["input"]["permissions"]

    for recommendation in result["recommendations"]:
        variable = recommendation["variable"]
        classification = recommendation["permission"]
        if classification == "OPTIMIZER_CAN_EXECUTE":
            assert variable in permissions["optimizer_can"]
        if variable in permissions["client_approval_required"]:
            assert classification == "CLIENT_APPROVAL_REQUIRED"
        if variable in permissions["unavailable"]:
            assert classification != "OPTIMIZER_CAN_EXECUTE"

    for experiment in result["experiments"]:
        assert experiment["permission"]["classification"] == "OPTIMIZER_CAN_EXECUTE"
        assert experiment["variable"]["type"] in permissions["optimizer_can"]
        assert experiment["execution"]["approved"] is False


@pytest.mark.parametrize(
    "case",
    [case for case in CASES if case["expected"]["experiment_allowed"]],
    ids=lambda case: case["id"],
)
def test_safe_proposals_are_single_variable_auditable_experiments(case: dict) -> None:
    result = analyze_case(deepcopy(case["input"]))
    policy = case["input"]["experiment_policy"]

    assert len(result["experiments"]) == 1
    experiment = result["experiments"][0]
    assert validate_experiment(experiment) == []
    assert experiment["variable"]["single_variable_change"] is True
    assert isinstance(experiment["variable"]["type"], str)
    assert experiment["problem"]["evidence"] == case["input"]["evidence"]
    assert experiment["baseline"] == policy["baseline"]
    assert experiment["primary_metric"] == policy["primary_metric"]
    assert experiment["guardrail_metrics"] == policy["guardrail_metrics"]
    assert experiment["observation"] == {
        "minimum_days": policy["minimum_days"],
        "minimum_conversions": policy["minimum_conversions"],
        "conversion_delay_days": policy["conversion_delay_days"],
        "maturity_rule": policy["maturity_rule"],
    }
    assert experiment["success_rule"] == policy["success_rule"]
    assert experiment["rollback_rule"] == policy["rollback_rule"]
    assert experiment["inconclusive_rule"] == policy["inconclusive_rule"]


@pytest.mark.parametrize("review_case", REVIEW_CASES, ids=lambda case: case["id"])
def test_review_experiment_applies_maturity_volume_confounder_and_outcome_rules(
    review_case: dict,
) -> None:
    review = review_experiment(deepcopy(review_case["experiment"]))

    assert review["id"] == review_case["experiment"]["id"]
    assert review["status"] == review_case["expected"]["status"]
    assert review_case["expected"]["reason"] in review["reasons"]


@pytest.mark.parametrize(
    "case_id", ["new_creative_not_mature", "short_term_creative_drop_with_delay"]
)
def test_conversion_delay_or_observation_immaturity_blocks_changes(
    case_id: str,
) -> None:
    result = _analyze(case_id)

    assert result["learning_eligibility"]["status"] == "CONVERSION_DELAY_NOT_MATURE"
    assert result["experiments"] == []
    assert any("conversion-delay maturity" in rule for rule in result["do_not_touch"])
    assert result["recommendations"][0]["kind"] == "monitoring"


def test_unfinished_low_volume_experiment_prevents_stacking_a_new_variable() -> None:
    result = _analyze("observation_elapsed_but_volume_low")

    assert result["experiment_reviews"][0]["status"] == "INSUFFICIENT_VOLUME"
    assert result["optimization_feasibility"]["status"] == "LEARNING_BLOCKED"
    assert result["experiments"] == []


def test_stable_account_explicitly_recommends_no_account_change() -> None:
    result = _analyze("no_material_anomaly_hold")

    assert result["optimization_feasibility"]["status"] == "NO_ACTION_RECOMMENDED"
    assert result["experiments"] == []
    assert [item["kind"] for item in result["recommendations"]] == ["monitoring"]
    assert any("Do not modify the account" in rule for rule in result["do_not_touch"])


def test_lowest_cpi_is_not_promoted_to_an_unfounded_causal_winner() -> None:
    result = _analyze("lowest_cpi_has_worst_payment_rate")

    assert all(diagnosis["causal_claim"] is False for diagnosis in result["diagnoses"])
    assert all(
        "winner" not in item["action"].lower() for item in result["recommendations"]
    )
    assert result["experiments"][0]["variable"]["type"] == "creative"


def test_product_dependency_is_requested_not_misrepresented_as_direct_access() -> None:
    result = _analyze("registration_normal_paywall_low")
    paywall = next(
        item for item in result["recommendations"] if item["variable"] == "paywall"
    )

    assert paywall["kind"] == "client_request"
    assert paywall["permission"] == "PRODUCT_DEPENDENCY"
    assert result["experiments"][0]["variable"]["type"] == "creative"
