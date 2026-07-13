"""Decision-free input-normalization contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.normalization import (  # noqa: E402
    load_normalization_source,
    normalize_uac_input,
    render_normalization,
)


def test_chinese_aliases_numbers_percent_dates_and_extras(repo_root):
    raw = yaml.safe_load(
        (repo_root / "examples" / "normalization" / "uac-flat-input.yaml").read_text(
            encoding="utf-8"
        )
    )

    result = normalize_uac_input(raw, source_label="anonymous-example")
    normalized = result["normalized"]

    assert normalized["scope"]["start_date"] == "2026-06-15"
    assert normalized["scope"]["end_date"] == "2026-06-28"
    assert normalized["facts"]["metrics"]["spend"] == 1200
    assert normalized["facts"]["metrics"]["conversion_rate"] == 0.03
    assert normalized["facts"]["daily_budget"] == 100
    assert normalized["goal"]["target_cpa"] == 65
    assert result["missing_fields"] == []
    assert result["conversion_errors"] == []
    assert result["extras"] == {
        "自定义备注": "This extra field is preserved rather than discarded."
    }
    assert result["source"]["label"] == "anonymous-example"
    assert result["source"]["field_map"]["花费"] == "facts.metrics.spend"
    assert result["decision_made"] is False


def test_english_aliases_empty_values_and_invalid_numbers_are_reported():
    raw = {
        "start_date": "2026-07-01",
        "end_date": "2026-07-14",
        "timezone": "UTC",
        "country": "anonymous-market",
        "os": "ios",
        "cost": "not-a-number",
        "installs": "100",
        "registrations": "",
        "payments": "2",
        "budget": "50",
        "tcpa": "25",
    }

    result = normalize_uac_input(raw)

    assert result["normalized"]["facts"]["metrics"]["installs"] == 100
    assert "facts.metrics.spend" in result["missing_fields"]
    assert "facts.metrics.registrations" in result["missing_fields"]
    assert result["conversion_errors"] == [
        {"field": "cost", "message": "must be a number or numeric string"}
    ]


def test_nested_input_is_preserved_and_cleaned_without_decision_logic():
    result = normalize_uac_input(
        {
            "scope": {
                "platform": "google_ads",
                "campaign_type": "app_campaign",
                "start_date": "2026.07.01",
            },
            "facts": {"metrics": {"spend": "1,250", "payment_rate": "4%"}},
            "custom": {"keep": True},
        }
    )

    assert result["normalized"]["scope"]["start_date"] == "2026-07-01"
    assert result["normalized"]["facts"]["metrics"] == {
        "spend": 1250,
        "payment_rate": 0.04,
    }
    assert result["extras"] == {"custom": {"keep": True}}
    assert result["decision_made"] is False


def test_one_row_csv_is_supported_and_multiple_rows_fail(tmp_path):
    one_row = tmp_path / "one.csv"
    one_row.write_text("cost,installs\n100,20\n", encoding="utf-8")
    assert load_normalization_source(one_row) == {"cost": "100", "installs": "20"}

    multiple = tmp_path / "multiple.csv"
    multiple.write_text("cost,installs\n100,20\n200,30\n", encoding="utf-8")
    try:
        load_normalization_source(multiple)
    except ValueError as exc:
        assert "exactly one summary row" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("multiple CSV rows must fail closed")


def test_conflicting_aliases_remove_the_ambiguous_value_and_report_it():
    result = normalize_uac_input({"spend": "100", "cost": "999"})

    assert "spend" not in result["normalized"].get("facts", {}).get("metrics", {})
    assert "facts.metrics.spend" in result["missing_fields"]
    assert result["conversion_errors"] == [
        {
            "field": "cost",
            "message": "conflicts with spend mapped to facts.metrics.spend",
        }
    ]


def test_invalid_nested_value_is_removed_and_counted_as_missing():
    result = normalize_uac_input({"facts": {"metrics": {"spend": "not-a-number"}}})

    assert "spend" not in result["normalized"]["facts"]["metrics"]
    assert "facts.metrics.spend" in result["missing_fields"]
    assert result["conversion_errors"] == [
        {
            "field": "facts.metrics.spend",
            "message": "must be a number or numeric string",
        }
    ]


def test_negative_and_non_finite_operating_values_are_not_normalized():
    result = normalize_uac_input(
        {
            "budget": -1,
            "tcpa": "nan",
            "installs": "inf",
            "payments": -2,
        }
    )

    assert {issue["field"] for issue in result["conversion_errors"]} == {
        "budget",
        "tcpa",
        "installs",
        "payments",
    }
    for field in (
        "facts.daily_budget",
        "goal.target_cpa",
        "facts.metrics.installs",
        "facts.metrics.payments",
    ):
        assert field in result["missing_fields"]


def test_integer_outside_supported_numeric_range_is_reported_not_raised():
    result = normalize_uac_input({"spend": 10**10000})

    assert result["conversion_errors"] == [
        {
            "field": "spend",
            "message": "must be a finite number within the supported range",
        }
    ]
    assert "facts.metrics.spend" in result["missing_fields"]


def test_nested_non_finite_unknown_values_are_removed_before_json_output():
    result = normalize_uac_input(
        {
            "scope": {"custom": float("inf")},
            "custom": {"nested": [1, float("nan"), 2]},
        }
    )

    assert "custom" not in result["normalized"]["scope"]
    assert result["extras"] == {"custom": {"nested": [1, 2]}}
    assert {item["field"] for item in result["conversion_errors"]} == {
        "scope.custom",
        "custom.nested[1]",
    }
    rendered = render_normalization(result)
    json.loads(rendered)
    assert "Infinity" not in rendered
    assert "NaN" not in rendered


@pytest.mark.parametrize(
    ("field", "missing"),
    [
        ("spend", "facts.metrics.spend"),
        ("installs", "facts.metrics.installs"),
        ("budget", "facts.daily_budget"),
        ("tcpa", "goal.target_cpa"),
        ("revenue", None),
    ],
)
def test_percentage_suffix_is_rejected_for_non_percentage_fields(field, missing):
    result = normalize_uac_input({field: "50%"})

    assert result["conversion_errors"] == [
        {
            "field": field,
            "message": "percentage notation is only valid for percentage fields",
        }
    ]
    if missing is not None:
        assert missing in result["missing_fields"]
    else:
        assert "revenue" not in result["normalized"].get("facts", {}).get("metrics", {})
