"""Regression tests for Google Ads learning-unit guardrails.

These tests prevent the skill from drifting back toward country-level rollups
that ignore the campaign/ad-group or asset-group units that actually learn.
"""

from __future__ import annotations


def _read(repo_root, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8").lower()


def test_google_skill_requires_learning_unit_before_geo_decisions(repo_root):
    text = _read(repo_root, "skills/ads-google/SKILL.md")

    required_phrases = [
        "learning unit",
        "country/geo totals",
        "ad group",
        "asset group",
        "geo analysis workflow",
        "campaign x ad group/asset group x geo",
    ]

    missing = [phrase for phrase in required_phrases if phrase not in text]
    assert not missing, "ads-google is missing learning-unit guardrails: " + ", ".join(missing)


def test_gaql_notes_preserve_grain_before_country_rollup(repo_root):
    text = _read(repo_root, "ads/references/gaql-notes.md")

    required_phrases = [
        "learning-unit aggregation guardrail",
        "country is a segment",
        "minimum grain",
        "campaign_id",
        "ad_group_id",
        "asset_group_id",
        "safe rollups",
        "unsafe rollups",
    ]

    missing = [phrase for phrase in required_phrases if phrase not in text]
    assert not missing, "gaql-notes is missing aggregation guardrails: " + ", ".join(missing)


def test_daily_reporting_does_not_collapse_google_to_country(repo_root):
    text = _read(repo_root, "skills/ads-report/SKILL.md")

    assert "do not summarize performance by country alone" in text
    assert "ad group / asset group" in text
