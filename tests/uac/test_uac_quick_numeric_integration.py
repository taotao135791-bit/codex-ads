"""End-to-end contracts for numeric Quick Decisions and compact cards."""

from __future__ import annotations

from copy import deepcopy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.quick_ops import decide_case  # noqa: E402
from codex_ads.uac.quick_reporting import render_quick_card  # noqa: E402
from codex_ads.uac.types import ContractError  # noqa: E402


def _numeric_case(repo_root: Path) -> dict:
    return yaml.safe_load(
        (
            repo_root
            / "skills"
            / "ads-google-app"
            / "assets"
            / "UAC-QUICK-NUMERIC.example.yaml"
        ).read_text(encoding="utf-8")
    )


def _ac30_split_case(repo_root: Path, *, feasible: bool) -> dict:
    case = yaml.safe_load(
        (
            repo_root
            / "skills"
            / "ads-google-app"
            / "assets"
            / "UAC-QUICK-OPS.example.yaml"
        ).read_text(encoding="utf-8")
    )
    daily_budget = 200.0 if feasible else 100.0
    daily_spend = 180.0 if feasible else 90.0
    daily_events = 50 if feasible else 14
    minimum_budget = 40.0 if feasible else 60.0
    minimum_events = 20.0 if feasible else 15.0
    existing_budget = 160.0 if feasible else 80.0
    case["goal"].update(
        {
            "target_cpa": 5.0,
            "maximum_acceptable_cpa": 6.0,
            "minimum_acceptable_roas": 2.0,
            "daily_budget_cap": daily_budget,
            "optimization_priority": "balanced",
        }
    )
    case["facts"].update(
        {
            "daily_budget": daily_budget,
            "budget_limited": False,
            "minimum_daily_mature_events": 10,
        }
    )
    case["facts"]["metrics"].update(
        {
            "spend": daily_spend * 7,
            "mature_conversions": daily_events * 7,
            "mature_actual_cpa": 4.0,
            "mature_revenue": daily_events * 7 * 10,
            "mature_actual_roas": 2.2,
        }
    )
    case["facts"]["daily_series"] = [
        {
            "date": f"2026-06-{day:02d}",
            "spend": daily_spend,
            "mature_events": daily_events,
            "value": daily_events * 10,
        }
        for day in range(15, 22)
    ]
    case["facts"]["split_plan"] = {
        "campaign_count": 2,
        "minimum_daily_budget_per_campaign": minimum_budget,
        "minimum_daily_events_per_campaign": minimum_events,
        "existing_daily_budget_floor": existing_budget,
        "existing_level": "AC2.5",
        "candidate_level": "AC3.0",
        "candidate_target_type": "troas",
    }
    case["maturity"].update(
        {
            "days_since_last_change": 14,
            "mature_events_since_change": daily_events * 7,
            "last_change_variables": [],
        }
    )
    case["measurement"].update(
        {
            "value_missing_rate": 0.0,
            "currency_consistency_rate": 1.0,
            "google_mmp_value_difference_rate": 0.02,
            "mmp_backend_value_difference_rate": 0.03,
            "refund_rate": 0.02,
            "subscription_renewal_included": True,
        }
    )
    return case


def test_numeric_example_is_schema_valid_deterministic_and_read_only(repo_root):
    case = _numeric_case(repo_root)
    before = deepcopy(case)
    first = decide_case(case)
    second = decide_case(case)
    schema = json.loads(
        (
            repo_root
            / "skills"
            / "ads-google-app"
            / "assets"
            / "uac-quick-decision.schema.json"
        ).read_text(encoding="utf-8")
    )

    Draft202012Validator(schema).validate(first)
    assert first == second
    assert case == before
    assert first["constraint_analysis"]["primary_constraint"] == (
        "TARGET_LIKELY_TOO_TIGHT"
    )
    assert first["target_recommendation"]["recommended_value"] == 5.5
    assert first["budget_recommendation"]["recommended_value"] == 100.0
    assert first["bid_decision"]["action"] == "INCREASE"
    assert first["budget_decision"]["action"] == "NO_CHANGE"
    assert first["account_write"] is False
    assert first["ledger_write"] is False
    assert first["experiments"] == []


def test_numeric_card_shows_one_value_and_stays_compact(repo_root):
    card = render_quick_card(decide_case(_numeric_case(repo_root)))

    assert card.startswith("结论：")
    assert "tCPA：5 → 5.5" in card
    assert "日预算：保持 100" in card
    assert "3 天或新增 10 个成熟事件后复查" in card
    assert "成熟 CPA 超过 6" in card
    assert "保守" not in card
    assert "激进" not in card
    assert len([line for line in card.splitlines() if line]) <= 14


def test_read_only_card_keeps_ideal_value_as_a_client_recommendation(repo_root):
    case = _numeric_case(repo_root)
    case["permissions"]["optimizer_can"] = []
    case["permissions"]["unavailable"] = [
        "bid",
        "budget",
        "campaign_create",
        "optimization_event",
        "product",
        "paywall",
        "sdk",
    ]

    result = decide_case(case)
    card = render_quick_card(result)

    assert result["target_recommendation"]["recommended_value"] == 5.5
    assert result["target_recommendation"]["execution"]["executable_now"] is False
    assert result["bid_decision"]["action"] == "NO_CHANGE"
    assert "tCPA：保持 5" in card
    assert "建议（需授权或审批）：tCPA 5 → 5.5" in card
    assert result["account_write"] is False


def test_active_experiment_blocks_numeric_execution_without_hiding_the_ideal_value(
    repo_root,
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

    result = decide_case(_numeric_case(repo_root), ledger)

    assert result["target_recommendation"]["recommended_value"] == 5.5
    assert result["bid_decision"]["action"] == "NO_CHANGE"
    assert result["target_recommendation"]["execution"]["executable_now"] is False
    assert "numeric_change_blocked_by_unfinished_experiment" in result["reason_codes"]
    assert result["ledger_write"] is False


def test_duplicate_daily_dates_and_future_change_dates_fail_closed(repo_root):
    duplicate = _numeric_case(repo_root)
    duplicate["facts"]["daily_series"][1]["date"] = duplicate["facts"]["daily_series"][
        0
    ]["date"]
    with pytest.raises(ContractError, match="dates must be unique"):
        decide_case(duplicate)

    future_change = _numeric_case(repo_root)
    future_change["maturity"]["last_change_at"] = "2026-01-08"
    with pytest.raises(ContractError, match="must not be after scope.end_date"):
        decide_case(future_change)


def test_feasible_ac30_card_shows_each_budget_missing_target_and_campaign_rollback(
    repo_root,
):
    result = decide_case(_ac30_split_case(repo_root, feasible=True))
    card = render_quick_card(result)

    assert result["split_feasibility"]["state"] == "SPLIT_FEASIBLE"
    assert "Campaign：保持 AC2.5；并行新开 AC3.0" in card
    assert "总日预算：保持 200" in card
    assert "拆分预算：现有 AC2.5 160；新 AC3.0 40" in card
    assert "新 AC3.0 目标：暂不提供精确数值" in card
    assert "需成熟价值数据或后台模拟器确认" in card
    assert "回退：若成熟价值表现跌破已声明的业务下限" in card
    assert "日预算：保持 200" not in card.replace("总日预算：保持 200", "")


def test_infeasible_ac30_card_names_event_and_budget_shortfalls(repo_root):
    result = decide_case(_ac30_split_case(repo_root, feasible=False))
    card = render_quick_card(result)

    assert result["split_feasibility"]["state"] == "SPLIT_NOT_FEASIBLE"
    assert "不建议新开 AC3.0" in card
    assert "日均成熟事件 7 < 最低 15" in card
    assert "所需总日预算 120 > 可用 100" in card
    assert result["campaign_structure_decision"]["create_new_campaign"] is False


def test_numeric_gaps_are_localized_and_visible_when_current_values_are_held(repo_root):
    immature = _numeric_case(repo_root)
    immature["maturity"].update(
        {
            "days_since_last_change": 1,
            "mature_events_since_change": 1,
            "conversion_delay_elapsed_days": 0,
        }
    )
    immature_card = render_quick_card(decide_case(immature))
    assert "转化延迟、观察天数或成熟事件量尚未满足" in immature_card
    assert "insufficient_mature_conversion_data" not in immature_card

    missing_boundary = _numeric_case(repo_root)
    missing_boundary["goal"].pop("maximum_acceptable_cpa")
    missing_boundary_card = render_quick_card(decide_case(missing_boundary))
    assert "缺少业务可接受 CPA 上限" in missing_boundary_card
    assert "business_cpa_ceiling_missing" not in missing_boundary_card
