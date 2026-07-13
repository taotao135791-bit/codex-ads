"""Campaign-level terminology must stay separate from bid numbers."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.normalization import normalize_uac_input  # noqa: E402
from codex_ads.uac.terminology import (  # noqa: E402
    canonical_campaign_level,
    extract_campaign_levels,
    resolve_campaign_level,
)


def test_explicit_ac_and_chinese_advertising_labels_are_campaign_levels():
    assert canonical_campaign_level("AC2.0", explicit_context=True) == "AC2.0"
    assert canonical_campaign_level("AC2.5", explicit_context=True) == "AC2.5"
    assert canonical_campaign_level("广告 3.0", explicit_context=True) == "AC3.0"
    assert extract_campaign_levels("保留 AC2.5，再测试广告 3.0") == [
        "AC2.5",
        "AC3.0",
    ]


def test_tcpa_and_bare_numbers_never_become_campaign_levels():
    assert canonical_campaign_level("tCPA 2.5", explicit_context=True) is None
    assert canonical_campaign_level("2.5", explicit_context=True) is None
    assert extract_campaign_levels("tCPA 2.5，预算 100") == []

    normalized = normalize_uac_input({"广告层级": "广告 2.5", "target_cpa": None})[
        "normalized"
    ]
    assert normalized.get("goal", {}).get("target_cpa") is None


def test_project_glossary_defines_team_semantics_without_claiming_official_name():
    result = resolve_campaign_level(
        "AC2.5",
        glossary={
            "ac25": {
                "optimization_event": "qualified_registration",
                "value_optimization": False,
                "bidding_strategy": "tcpa",
            }
        },
        account={
            "optimization_event": "qualified_registration",
            "value_optimization": False,
            "bidding_strategy": "tcpa",
        },
        switching=True,
    )

    assert result["resolution_source"] == "project_glossary"
    assert result["confidence"] == "high"
    assert result["official_google_product_name"] is False
    assert result["not_a_bid_value"] is True
    assert result["confirmation_required"] is False


def test_missing_glossary_is_labeled_inference_and_requires_switch_confirmation():
    result = resolve_campaign_level(
        "AC3.0",
        account={
            "optimization_event": "payment",
            "value_optimization": True,
            "bidding_strategy": "troas",
        },
        switching=True,
    )

    assert result["resolution_source"] == "account_inference"
    assert result["inferred"] is True
    assert result["confirmation_required"] is True


def test_actual_account_settings_override_conflicting_team_glossary():
    result = resolve_campaign_level(
        "AC2.5",
        glossary={
            "ac25": {
                "optimization_event": "registration",
                "value_optimization": False,
                "bidding_strategy": "tcpa",
            }
        },
        account={
            "optimization_event": "payment",
            "value_optimization": True,
            "bidding_strategy": "troas",
        },
        switching=True,
    )

    assert result["resolution_source"] == "account_settings_override"
    assert set(result["glossary_conflicts"]) == {
        "optimization_event",
        "value_optimization",
        "bidding_strategy",
    }
    assert result["resolved_meaning"]["optimization_event"] == "payment"
    assert result["confirmation_required"] is True
