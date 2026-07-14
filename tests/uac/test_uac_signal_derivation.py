"""Behavior contracts for deterministic UAC signal derivation.

These tests intentionally assert states and safety properties, not a particular
percentage threshold or recommendation formula. All fixtures are synthetic.
"""

from __future__ import annotations

from copy import deepcopy
import math
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.signals import derive_signals  # noqa: E402


def _daily_series(
    spends: list[float],
    events: list[int],
    values: list[float] | None = None,
) -> list[dict[str, Any]]:
    if values is None:
        values = [event * 5.0 for event in events]
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


def _base_case() -> dict[str, Any]:
    return {
        "goal": {
            "business_goal": "payment",
            "bidding_strategy": "tcpa",
            "target_cpa": 5.0,
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
            "event_candidates": [
                {
                    "event": "qualified_registration",
                    "mature_events": 180,
                    "mature_payments": 25,
                    "median_payment_delay_days": 3,
                    "reliable": True,
                },
                {
                    "event": "trial_start",
                    "mature_events": 100,
                    "mature_payments": 60,
                    "median_payment_delay_days": 1,
                    "reliable": True,
                },
                {
                    "event": "payment",
                    "mature_events": 5,
                    "mature_payments": 5,
                    "median_payment_delay_days": 0,
                    "reliable": True,
                },
            ],
            "creative_cohorts": [
                {
                    "creative": "synthetic-cheap-install",
                    "spend": 100.0,
                    "installs": 100,
                    "deep_events": 5,
                    "payments": 1,
                    "value": 10.0,
                    "mature": True,
                },
                {
                    "creative": "synthetic-high-value",
                    "spend": 200.0,
                    "installs": 50,
                    "deep_events": 20,
                    "payments": 10,
                    "value": 500.0,
                    "mature": True,
                },
            ],
            "split_plan": {
                "campaign_count": 2,
                "minimum_daily_budget_per_campaign": 40.0,
                "minimum_mature_events_per_campaign": 20,
            },
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
    }


def test_derive_signals_is_pure_and_returns_the_required_states():
    case = _base_case()
    before = deepcopy(case)

    result = derive_signals(case)

    assert case == before
    assert result["maturity"]["state"] == "MATURE"
    assert result["budget_delivery"]["state"] == "UNDER_DELIVERING"
    assert result["target_constraint"]["state"] == "TARGET_LIKELY_TOO_TIGHT"
    assert result["event_volume"]["state"] == "SUFFICIENT_AND_STABLE"
    assert result["value_signal"]["state"] == "VALUE_SIGNAL_READY"


@pytest.mark.parametrize(
    ("patch", "expected"),
    [
        ({"days_since_last_change": 7, "mature_events_since_change": 70}, "MATURE"),
        (
            {"days_since_last_change": 3, "mature_events_since_change": 5},
            "PARTIALLY_MATURE",
        ),
        (
            {
                "days_since_last_change": 1,
                "last_change_variables": ["target_cpa"],
                "mature_events_since_change": 1,
            },
            "NOT_MATURE",
        ),
    ],
)
def test_maturity_uses_time_delay_volume_and_recent_change(patch, expected):
    case = _base_case()
    case["maturity"].update(patch)

    assert derive_signals(case)["maturity"]["state"] == expected


def test_missing_maturity_inputs_do_not_become_a_mature_claim():
    case = _base_case()
    case["maturity"].pop("days_since_last_change")
    case["maturity"].pop("mature_events_since_change")

    assert derive_signals(case)["maturity"]["state"] == "INSUFFICIENT_EVIDENCE"


def test_old_multi_variable_change_does_not_block_after_full_maturity_window():
    case = _base_case()
    case["maturity"]["last_change_variables"] = ["bid", "budget", "creative"]

    assert derive_signals(case)["maturity"]["state"] == "MATURE"


def test_budget_delivery_uses_a_multi_day_window_not_the_latest_day_only():
    case = _base_case()
    case["facts"]["daily_series"] = _daily_series(
        [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 5.0],
        [10, 10, 10, 10, 10, 10, 1],
    )

    result = derive_signals(case)

    assert result["budget_delivery"]["state"] != "UNDER_DELIVERING"
    assert result["budget_delivery"]["observation_days"] == 7


def test_full_delivery_can_be_identified_as_budget_constrained():
    case = _base_case()
    case["facts"]["daily_series"] = _daily_series([100.0] * 7, [10] * 7)
    case["facts"]["metrics"]["spend"] = 700.0
    case["facts"]["budget_limited"] = True

    assert derive_signals(case)["budget_delivery"]["state"] == "BUDGET_CONSTRAINED"


def test_event_series_reports_sufficient_but_volatile_with_real_statistics():
    case = _base_case()
    events = [0, 20, 1, 19, 0, 20, 10]
    case["facts"]["daily_series"] = _daily_series([65.0] * 7, events)

    result = derive_signals(case)
    metrics = result["event_volume"]

    assert metrics["state"] == "SUFFICIENT_BUT_VOLATILE"
    assert metrics["total_events"] == sum(events)
    assert metrics["zero_event_days"] == 2
    assert metrics["minimum"] == 0
    assert metrics["maximum"] == 20
    assert math.isfinite(metrics["mean_daily_events"])
    assert math.isfinite(metrics["coefficient_of_variation"])


def test_low_event_volume_is_not_upgraded_to_stable_by_averaging():
    case = _base_case()
    case["facts"]["daily_series"] = _daily_series([20.0] * 7, [0, 1, 0, 1, 0, 1, 0])

    assert derive_signals(case)["event_volume"]["state"] == "INSUFFICIENT"


@pytest.mark.parametrize(
    ("measurement", "expected"),
    [
        (
            {
                "value_missing_rate": 0.0,
                "currency_consistency_rate": 1.0,
                "google_mmp_value_difference_rate": 0.02,
                "mmp_backend_value_difference_rate": 0.03,
                "refund_rate": 0.05,
            },
            "VALUE_SIGNAL_READY",
        ),
        (
            {
                "value_missing_rate": 0.35,
                "currency_consistency_rate": 0.6,
                "google_mmp_value_difference_rate": 0.4,
                "mmp_backend_value_difference_rate": 0.5,
                "refund_rate": 0.3,
            },
            "VALUE_SIGNAL_UNRELIABLE",
        ),
        ({}, "INSUFFICIENT_EVIDENCE"),
    ],
)
def test_value_signal_is_derived_from_numeric_quality_rates(measurement, expected):
    case = _base_case()
    case["measurement"] = measurement

    assert derive_signals(case)["value_signal"]["state"] == expected


def test_refund_business_limit_and_subscription_definition_gate_value_signal():
    refund_case = _base_case()
    refund_case["goal"]["maximum_acceptable_refund_rate"] = 0.1
    refund_case["measurement"]["refund_rate"] = 0.25
    assert derive_signals(refund_case)["value_signal"]["state"] == (
        "VALUE_SIGNAL_UNRELIABLE"
    )

    subscription_case = _base_case()
    subscription_case["goal"]["business_goal"] = "subscription"
    subscription_case["measurement"]["subscription_renewal_included"] = False
    assert derive_signals(subscription_case)["value_signal"]["state"] == (
        "VALUE_SIGNAL_UNRELIABLE"
    )


def test_candidate_events_are_ranked_from_volume_relationship_delay_and_reliability():
    result = derive_signals(_base_case())
    candidates = result["event_candidates"]

    assert [item["event"] for item in candidates] == [
        "trial_start",
        "qualified_registration",
        "payment",
    ]
    assert candidates[0]["recommendation"] == "current_best_proxy"
    assert candidates[1]["recommendation"] in {"next_candidate", "not_ready"}
    assert candidates[-1]["recommendation"] == "not_ready"


def test_unreliable_or_overly_shallow_event_cannot_become_the_best_proxy():
    case = _base_case()
    case["facts"]["event_candidates"][0]["too_shallow"] = True
    case["facts"]["event_candidates"][1]["daily_mature_events"] = [14] * 7

    candidates = derive_signals(case)["event_candidates"]
    best = next(
        item for item in candidates if item["recommendation"] == "current_best_proxy"
    )

    assert best["event"] == "trial_start"
    assert best["stability_score"] == "high"


def test_creative_quality_uses_mature_deep_outcomes_instead_of_cpi_alone():
    result = derive_signals(_base_case())
    by_asset = {item["creative"]: item for item in result["creative_quality"]}

    assert by_asset["synthetic-cheap-install"]["classification"] == (
        "CHEAP_LOW_QUALITY"
    )
    assert by_asset["synthetic-high-value"]["classification"] in {
        "EXPENSIVE_HIGH_VALUE",
        "STRONG_DEEP_CONVERSION",
    }
    assert (
        by_asset["synthetic-high-value"]["value_per_install"]
        > (by_asset["synthetic-cheap-install"]["value_per_install"])
    )


def test_immature_creative_cohort_is_insufficient_even_with_cheap_installs():
    case = _base_case()
    case["facts"]["creative_cohorts"][0]["mature"] = False

    result = derive_signals(case)
    by_asset = {item["creative"]: item for item in result["creative_quality"]}

    assert by_asset["synthetic-cheap-install"]["classification"] == (
        "INSUFFICIENT_DATA"
    )


def test_missing_window_and_series_return_unknown_instead_of_using_one_day():
    case = _base_case()
    case["facts"].pop("daily_series")
    case["facts"]["metrics"].pop("spend")
    case["maturity"].pop("days_elapsed")

    result = derive_signals(case)

    assert result["budget_delivery"]["state"] == "UNKNOWN"
    assert result["event_volume"]["state"] == "UNKNOWN"
