"""Fixture-driven Campaign Level Quick Ops behavior tests."""

from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.quick_ops import (  # noqa: E402
    decide_case,
    validate_quick_decision,
)
from codex_ads.uac.quick_reporting import render_quick_card  # noqa: E402
from codex_ads.uac.routing import route_question  # noqa: E402
from codex_ads.uac.terminology import (  # noqa: E402
    canonical_campaign_level,
    resolve_campaign_level,
)


QUICK_SCENARIOS = yaml.safe_load(
    (
        Path(__file__).resolve().parents[1] / "fixtures" / "uac-quick-ops-cases.yaml"
    ).read_text(encoding="utf-8")
)["cases"]


def _deep_update(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = deepcopy(value)


@pytest.fixture(scope="session")
def quick_fixture(repo_root) -> dict[str, Any]:
    return yaml.safe_load(
        (repo_root / "tests" / "fixtures" / "uac-quick-ops-cases.yaml").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture(scope="session")
def quick_base(repo_root) -> dict[str, Any]:
    return yaml.safe_load(
        (
            repo_root
            / "skills"
            / "ads-google-app"
            / "assets"
            / "UAC-QUICK-OPS.example.yaml"
        ).read_text(encoding="utf-8")
    )


@pytest.fixture(scope="session")
def quick_schema(repo_root) -> dict[str, Any]:
    return json.loads(
        (
            repo_root
            / "skills"
            / "ads-google-app"
            / "assets"
            / "uac-quick-decision.schema.json"
        ).read_text(encoding="utf-8")
    )


def _transition(case: dict[str, Any], name: str | None) -> None:
    quick = case["quick_ops"]
    glossary = case["campaign_level_glossary"]
    if name == "ac20_to_ac25":
        quick["question"] = "保留 AC2.0 还是测试 AC2.5"
        quick["question_type"] = "campaign_level_selection"
        quick["current_campaign"] = {
            "id": "anonymized-campaign-a",
            "level": "AC2.0",
            "optimization_event": "registration",
            "bidding_strategy": "tcpa",
            "value_optimization": False,
            "healthy": True,
        }
        quick["candidate_campaign"] = {
            "level": "AC2.5",
            "optimization_event": "qualified_registration",
            "bidding_strategy": "tcpa",
            "value_optimization": False,
        }
        glossary["ac20"] = {
            "optimization_event": "registration",
            "value_optimization": False,
            "bidding_strategy": "tcpa",
        }
        glossary["ac25"] = {
            "optimization_event": "qualified_registration",
            "value_optimization": False,
            "bidding_strategy": "tcpa",
        }
    elif name == "same_level":
        quick["question"] = "现有 AC2.5 要不要再开一个 AC2.5"
        quick["question_type"] = "same_level_campaign"
        quick["candidate_campaign"] = deepcopy(quick["current_campaign"])
    elif name == "current_ac30":
        quick["question"] = "当前 AC3.0 是否应该回退"
        quick["current_campaign"] = {
            "id": "anonymized-campaign-a",
            "level": "AC3.0",
            "optimization_event": "payment",
            "bidding_strategy": "troas",
            "value_optimization": True,
            "healthy": False,
        }
        quick.pop("candidate_campaign", None)
    elif name == "direct_move_ac25_to_ac30":
        quick["current_campaign"]["healthy"] = False
        quick["current_campaign"]["goal_misaligned"] = True
        quick["transition"] = {
            "direct_migration_safe": True,
            "single_campaign_learning_ready": True,
            "rollback_baseline_available": True,
        }


def _build_case(base: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    case = deepcopy(base)
    _transition(case, scenario.get("transition"))
    if scenario.get("clear_glossary"):
        case["campaign_level_glossary"] = {}
    _deep_update(case, scenario.get("override", {}))
    return case


def test_fixture_covers_all_forty_two_required_scenarios(quick_fixture):
    cases = quick_fixture["cases"]
    assert len(cases) >= 42
    assert len({case["id"] for case in cases}) == len(cases)


@pytest.mark.parametrize(
    "scenario", QUICK_SCENARIOS, ids=[case["id"] for case in QUICK_SCENARIOS]
)
def test_quick_ops_fixture_matrix(scenario, quick_base, quick_schema):
    failures: list[str] = []
    validator = Draft202012Validator(quick_schema)
    scenario_id = scenario["id"]
    kind = scenario["kind"]
    if kind == "routing":
        routed = route_question(scenario["question"])
        assert routed["mode"] == scenario["expected_mode"]
        return
    if kind == "terminology":
        actual = canonical_campaign_level(scenario["term"], explicit_context=True)
        assert actual == scenario["expected_level"]
        assert resolve_campaign_level(scenario["term"])["not_a_bid_value"]
        return

    case = _build_case(quick_base, scenario)
    before = deepcopy(case)
    result = decide_case(case)
    validate_quick_decision(result)
    schema_errors = sorted(
        validator.iter_errors(result), key=lambda item: list(item.path)
    )
    if schema_errors:
        failures.append(f"{scenario_id}: schema={schema_errors[0].message}")
    if case != before:
        failures.append(f"{scenario_id}: decide_case mutated input")

    expected = scenario.get("expected_verdict")
    if expected and result["decision"]["verdict"] != expected:
        failures.append(f"{scenario_id}: verdict={result['decision']['verdict']}")
    forbidden = scenario.get("forbidden_verdict")
    if forbidden and result["decision"]["verdict"] == forbidden:
        failures.append(f"{scenario_id}: forbidden verdict={forbidden}")
    expected_source = scenario.get("expected_resolution_source")
    if (
        expected_source
        and result["terminology"]["resolution_source"] != expected_source
    ):
        failures.append(
            f"{scenario_id}: source={result['terminology']['resolution_source']}"
        )
    expected_structure = scenario.get("expected_structure")
    if (
        expected_structure
        and result["campaign_structure_decision"]["action"] != expected_structure
    ):
        failures.append(
            f"{scenario_id}: structure={result['campaign_structure_decision']['action']}"
        )
    expected_creative = scenario.get("expected_creative")
    if expected_creative and result["creative_decision"]["action"] != expected_creative:
        failures.append(
            f"{scenario_id}: creative={result['creative_decision']['action']}"
        )
    expected_placement = scenario.get("expected_placement")
    if (
        expected_placement
        and result["creative_decision"]["placement"] != expected_placement
    ):
        failures.append(
            f"{scenario_id}: placement={result['creative_decision']['placement']}"
        )
    if (
        "expected_parallel" in scenario
        and result["campaign_structure_decision"]["run_in_parallel"]
        is not scenario["expected_parallel"]
    ):
        failures.append(f"{scenario_id}: parallel mismatch")
    if (
        "expected_permission_allowed" in scenario
        and result["permission_check"]["allowed"]
        is not scenario["expected_permission_allowed"]
    ):
        failures.append(f"{scenario_id}: permission mismatch")
    if (
        scenario.get("expected_bid_action")
        and result["bid_decision"]["action"] != scenario["expected_bid_action"]
    ):
        failures.append(f"{scenario_id}: bid action mismatch")
    if (
        scenario.get("expected_budget_action")
        and result["budget_decision"]["action"] != scenario["expected_budget_action"]
    ):
        failures.append(f"{scenario_id}: budget action mismatch")

    card = render_quick_card(result)
    if not card.startswith("结论："):
        failures.append(f"{scenario_id}: card does not lead with verdict")
    if "# UAC Experiment Loop Report" in card or "## 14." in card:
        failures.append(f"{scenario_id}: Quick Decision rendered a full report")
    if result["experiments"] or result["ledger_write"] or result["account_write"]:
        failures.append(f"{scenario_id}: Quick Decision requested a write")
    if result["decision"]["primary_action_count"] != 1:
        failures.append(f"{scenario_id}: multiple primary actions")

    assert not failures, "Quick Ops fixture failures:\n" + "\n".join(failures)


def test_ac_label_never_populates_bid_or_budget_fields(quick_base):
    case = deepcopy(quick_base)
    case["quick_ops"]["question"] = "广告 2.5 还是 AC3.0"
    case["quick_ops"]["bid_budget"] = {}
    result = decide_case(case)

    assert result["terminology"]["not_a_bid_value"] is True
    assert result["bid_decision"]["current_target"] is None
    assert result["bid_decision"]["recommended_target"] is None
    assert result["budget_decision"]["recommended_daily_budget"] is None


def test_unknown_review_thresholds_remain_null_instead_of_being_invented(quick_base):
    case = deepcopy(quick_base)
    case["quick_ops"]["review"] = {}
    result = decide_case(case)

    assert result["review_condition"]["after_days"] is None
    assert result["review_condition"]["minimum_additional_mature_events"] is None
    assert result["review_condition"]["maximum_additional_spend"] is None
    assert any("review" in gap for gap in result["data_gaps"])


def test_confirmed_emergency_multi_variable_action_is_not_called_an_experiment(
    quick_base,
):
    case = deepcopy(quick_base)
    case["quick_ops"]["operational"] = {
        "urgent_confirmed": True,
        "simultaneous_changes": ["budget", "bid", "creative"],
    }
    result = decide_case(case)
    classification = result["classification"]

    assert classification["classification"] == "OPERATIONAL_INTERVENTION"
    assert classification["experiment_validity"] == "NOT_A_VALID_EXPERIMENT"
    assert classification["attribution"] == "ATTRIBUTION_WILL_BE_CONFOUNDED"
    assert classification["causal_attribution_allowed"] is False
    assert result["ledger_write"] is False


def test_direct_ac20_to_ac25_migration_requires_all_declared_safety_gates(quick_base):
    case = deepcopy(quick_base)
    _transition(case, "ac20_to_ac25")
    case["quick_ops"]["current_campaign"]["healthy"] = False
    case["quick_ops"]["candidate_event"] = {
        "reliable": True,
        "delay_mature": True,
        "volume_assessment": "sufficient",
        "stability_assessment": "stable",
        "relationship_to_business_goal": "stronger",
    }
    case["quick_ops"]["transition"] = {
        "direct_migration_safe": True,
        "single_campaign_learning_ready": True,
        "rollback_baseline_available": True,
    }

    result = decide_case(case)
    assert result["decision"]["verdict"] == "MOVE_AC20_TO_AC25"
    assert result["campaign_structure_decision"]["create_new_campaign"] is False


def test_direct_ac25_to_ac30_migration_is_possible_only_when_current_is_misaligned(
    quick_base,
):
    case = deepcopy(quick_base)
    _transition(case, "direct_move_ac25_to_ac30")

    result = decide_case(case)
    assert result["decision"]["verdict"] == "MOVE_AC25_TO_AC30"
    assert result["campaign_structure_decision"]["action"] == "ADJUST_EXISTING"


def test_failed_ac25_can_roll_back_to_known_ac20_baseline(quick_base):
    case = deepcopy(quick_base)
    case["quick_ops"]["signals"] = {"rollback_triggered": True}
    case["quick_ops"]["rollback"] = {
        "baseline_level": "AC2.0",
        "condition": "Declared mature guardrail breach.",
        "action": "Restore the declared AC2.0 baseline.",
    }

    result = decide_case(case)
    assert result["decision"]["verdict"] == "ROLL_BACK_TO_AC20"


def test_same_level_duplicate_is_called_controlled_test_only_after_strict_admission(
    quick_base,
):
    case = deepcopy(quick_base)
    _transition(case, "same_level")
    case["quick_ops"]["structure"] = {
        "different_user_hypothesis": True,
        "controlled_test_required": True,
        "experiment_admission_ready": True,
        "traffic_isolation_ready": True,
    }

    result = decide_case(case)
    assert (
        result["campaign_structure_decision"]["action"]
        == "DUPLICATE_FOR_CONTROLLED_TEST"
    )
    assert result["classification"]["experiment_validity"] == "NOT_AN_EXPERIMENT"
    assert result["ledger_write"] is False


def test_unfinished_ledger_experiment_blocks_stacking_a_level_change(
    quick_base, repo_root
):
    ledger = yaml.safe_load(
        (
            repo_root
            / "skills"
            / "ads-google-app"
            / "assets"
            / "ADS-EXPERIMENTS.example.yaml"
        ).read_text(encoding="utf-8")
    )
    result = decide_case(deepcopy(quick_base), ledger)

    assert result["decision"]["verdict"] == "CONTINUE_CURRENT_AC25"
    assert "unfinished_experiment_blocks_stacked_change" in result["reason_codes"]
    assert result["campaign_structure_decision"]["action"] == "WAIT"


def test_bid_and_budget_remain_separate_from_campaign_level(quick_base):
    bid_case = deepcopy(quick_base)
    _transition(bid_case, "same_level")
    bid_case["learning"]["target_assessment"] = "aggressive"
    bid_case["quick_ops"]["bid_budget"]["recommended_target"] = 6.0
    bid_result = decide_case(bid_case)
    assert bid_result["bid_decision"]["action"] == "INCREASE"
    assert bid_result["budget_decision"]["action"] == "NO_CHANGE"

    budget_case = deepcopy(quick_base)
    _transition(budget_case, "same_level")
    budget_case["learning"]["budget_assessment"] = "constrained"
    budget_case["quick_ops"]["bid_budget"]["recommended_daily_budget"] = 120
    budget_result = decide_case(budget_case)
    assert budget_result["budget_decision"]["action"] == "INCREASE"
    assert budget_result["bid_decision"]["action"] == "NO_CHANGE"


def test_ordinary_multi_variable_request_is_blocked_to_preserve_attribution(
    quick_base,
):
    case = deepcopy(quick_base)
    _transition(case, "same_level")
    case["quick_ops"]["bid_budget"]["recommended_target"] = 6.0
    case["quick_ops"]["bid_budget"]["recommended_daily_budget"] = 120

    result = decide_case(case)
    assert result["bid_decision"]["action"] == "NO_CHANGE"
    assert result["budget_decision"]["action"] == "NO_CHANGE"
    assert "ordinary_multi_variable_change_blocked" in result["reason_codes"]


def test_actual_candidate_settings_override_claimed_ac30_readiness(quick_base):
    case = deepcopy(quick_base)
    case["quick_ops"]["candidate_campaign"]["value_optimization"] = False
    case["quick_ops"]["candidate_campaign"]["bidding_strategy"] = "tcpa"

    result = decide_case(case)

    assert result["decision"]["verdict"] == "DO_NOT_START_AC30"
    assert "candidate_campaign_value_optimization_failed" in result["reason_codes"]
    assert result["campaign_structure_decision"]["create_new_campaign"] is False


def test_ac20_to_ac25_is_blocked_when_measurement_is_unreliable(quick_base):
    case = deepcopy(quick_base)
    _transition(case, "ac20_to_ac25")
    case["quick_ops"]["candidate_event"] = {
        "reliable": True,
        "delay_mature": True,
        "volume_assessment": "sufficient",
        "stability_assessment": "stable",
        "relationship_to_business_goal": "stronger",
    }
    case["measurement"]["google_ads_vs_mmp"] = "material_mismatch"

    result = decide_case(case)

    assert result["decision"]["verdict"] == "DO_NOT_START_AC25"
    assert "measurement_state_unreliable" in result["reason_codes"]
    assert result["campaign_structure_decision"]["run_in_parallel"] is False


def test_read_only_profile_cannot_execute_a_predeclared_rollback(quick_base):
    case = deepcopy(quick_base)
    _transition(case, "current_ac30")
    case["quick_ops"]["permission_profile"] = "read_only"
    case["quick_ops"]["signals"] = {"rollback_triggered": True}
    case["quick_ops"]["rollback"] = {"baseline_level": "AC2.5"}

    result = decide_case(case)

    assert result["decision"]["verdict"] == "CONTINUE_CURRENT_AC30"
    assert result["campaign_structure_decision"]["action"] == "WAIT"
    assert result["permission_check"]["allowed"] is False
    assert result["permission_check"]["client_requests"]


@pytest.mark.parametrize(
    "profile",
    [
        "read_only",
        "budget_only",
        "bid_only",
        "creative_permission_but_no_new_assets",
        "aggregate_data_only",
    ],
)
def test_restricted_profiles_never_claim_they_can_add_new_assets(quick_base, profile):
    case = deepcopy(quick_base)
    _transition(case, "same_level")
    case["quick_ops"]["permission_profile"] = profile
    case["quick_ops"]["structure"] = {
        "same_semantics": True,
        "new_assets_only": True,
    }
    case["quick_ops"]["creative"]["new_asset"] = True
    case["quick_ops"]["creative"]["new_assets_available"] = True

    result = decide_case(case)

    assert result["creative_decision"]["add_new_assets"] is False
    assert result["creative_decision"]["placement"] is None
    assert result["permission_check"]["allowed"] is False


def test_explicit_creative_add_unavailable_overrides_umbrella_permission(quick_base):
    case = deepcopy(quick_base)
    _transition(case, "same_level")
    case["permissions"]["unavailable"].append("creative_add")
    case["quick_ops"]["structure"] = {
        "same_semantics": True,
        "new_assets_only": True,
    }
    case["quick_ops"]["creative"]["new_asset"] = True

    result = decide_case(case)

    assert result["creative_decision"]["add_new_assets"] is False
    assert result["creative_decision"]["add_permission"] == "NOT_ACTIONABLE"
    assert result["permission_check"]["allowed"] is False


def test_mixed_os_permission_requires_segmented_evidence(quick_base):
    case = deepcopy(quick_base)
    case["quick_ops"]["permission_profile"] = "android_editable_ios_locked"
    case["quick_ops"]["current_campaign"].pop("os", None)
    case["facts"]["segmentation_complete"] = False

    blocked = decide_case(case)

    assert blocked["decision"]["verdict"] == "CONTINUE_CURRENT_AC25"
    assert blocked["campaign_structure_decision"]["action"] == "WAIT"
    assert blocked["permission_check"]["allowed"] is False
    assert "os_level_segmentation_incomplete" in blocked["reason_codes"]

    case["facts"]["segmentation_complete"] = True
    allowed = decide_case(case)
    assert allowed["decision"]["verdict"] == "KEEP_AC25_AND_TEST_AC30"
    assert allowed["campaign_structure_decision"]["run_in_parallel"] is True


def test_client_approval_is_structured_and_visible_in_operator_card(quick_base):
    case = deepcopy(quick_base)
    case["quick_ops"]["permission_profile"] = "all_changes_require_client_approval"

    result = decide_case(case)
    card = render_quick_card(result)

    assert result["permission_check"]["requires_client_approval"] is True
    assert "需客户 / 管理员：" in card
    assert "请客户批准：新建 Campaign" in card


def test_operator_card_localizes_common_actions_and_preserves_campaign_identity(
    quick_base,
):
    result = decide_case(deepcopy(quick_base))
    card = render_quick_card(result)

    assert result["campaign_structure_decision"]["campaign_id"] == (
        "anonymized-campaign-a"
    )
    assert result["upgrade_condition"]["target_level"] == "AC3.0"
    assert "Campaign：anonymized-campaign-a" in card
    assert "保持 AC2.5；并行候选 AC3.0" in card
    assert "置信度：中" in card
    assert "=true" not in card
    assert "do_not_" not in card


def test_unconfirmed_glossary_gap_is_human_readable_in_card(quick_base):
    case = deepcopy(quick_base)
    case["campaign_level_glossary"] = {}
    case["quick_ops"]["terminology_mapping_confirmed"] = False

    card = render_quick_card(decide_case(case))

    assert "确认本项目中目标 AC 层级的实际定义" in card
    assert "confirmed project meaning for the requested AC level" not in card
