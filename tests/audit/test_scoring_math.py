"""Scoring algorithm sanity + stability tests.

The weighted-score formula from ``ads/references/scoring-system.md`` is:

    S_total = Σ(C_pass × W_sev × W_cat) / Σ(C_total × W_sev × W_cat) × 100

where C_pass ∈ {0, 0.5, 1}, W_sev is the severity multiplier, and W_cat is
the category weight for the platform.

This test re-implements the formula and asserts:
- It returns the same score for the same input across 10 runs (no hidden
  nondeterminism from float ordering or dict iteration).
- Hand-worked edge cases (all PASS, all FAIL, mixed) match expectations.

Wave 3 will add fixture-based audit replays; this is the unit foundation.
"""

from __future__ import annotations


def _score(checks: list[dict], category_weights: dict[str, float], severity_multipliers: dict[str, float]) -> float:
    """Compute a 0-100 Ads Health Score from a list of check results.

    Each check is a dict with: id, category, severity, result (pass/warning/fail/na).
    """
    result_points = {"pass": 1.0, "warning": 0.5, "fail": 0.0}
    earned = 0.0
    total = 0.0
    for check in checks:
        if check["result"] == "na":
            continue
        w_sev = severity_multipliers[check["severity"]]
        w_cat = category_weights[check["category"]]
        weight = w_sev * w_cat
        earned += result_points[check["result"]] * weight
        total += weight
    if total == 0.0:
        return 0.0
    return round((earned / total) * 100.0, 2)


SEVERITY_MULTIPLIERS = {"critical": 5.0, "high": 3.0, "medium": 1.5, "low": 0.5}
CATEGORY_WEIGHTS = {
    "conversion_tracking": 0.25,
    "wasted_spend": 0.20,
    "account_structure": 0.15,
    "keywords_quality": 0.15,
    "ads_assets": 0.15,
    "settings_targeting": 0.10,
}


def _sample_checks(result: str) -> list[dict]:
    return [
        {"id": "G42", "category": "conversion_tracking", "severity": "critical", "result": result},
        {"id": "G43", "category": "conversion_tracking", "severity": "critical", "result": result},
        {"id": "G13", "category": "wasted_spend", "severity": "high", "result": result},
        {"id": "G01", "category": "account_structure", "severity": "medium", "result": result},
        {"id": "G26", "category": "ads_assets", "severity": "low", "result": result},
    ]


def test_all_pass_scores_100():
    assert _score(_sample_checks("pass"), CATEGORY_WEIGHTS, SEVERITY_MULTIPLIERS) == 100.0


def test_all_fail_scores_0():
    assert _score(_sample_checks("fail"), CATEGORY_WEIGHTS, SEVERITY_MULTIPLIERS) == 0.0


def test_all_warning_scores_50():
    assert _score(_sample_checks("warning"), CATEGORY_WEIGHTS, SEVERITY_MULTIPLIERS) == 50.0


def test_na_checks_excluded_from_total():
    """An NA check should not affect the score at all."""
    checks_with_na = _sample_checks("pass") + [
        {"id": "G44", "category": "conversion_tracking", "severity": "critical", "result": "na"}
    ]
    assert _score(checks_with_na, CATEGORY_WEIGHTS, SEVERITY_MULTIPLIERS) == 100.0


def test_scoring_is_deterministic_across_runs():
    """Same input → same output across 10 runs. Catches accidental
    nondeterminism (e.g., set iteration leaking into the algorithm)."""
    checks = [
        {"id": "G42", "category": "conversion_tracking", "severity": "critical", "result": "pass"},
        {"id": "G13", "category": "wasted_spend", "severity": "high", "result": "fail"},
        {"id": "G01", "category": "account_structure", "severity": "medium", "result": "warning"},
        {"id": "G26", "category": "ads_assets", "severity": "low", "result": "pass"},
    ]
    scores = {_score(checks, CATEGORY_WEIGHTS, SEVERITY_MULTIPLIERS) for _ in range(10)}
    assert len(scores) == 1, f"Scoring not deterministic: got {scores}"


def test_critical_failure_weighs_more_than_low_pass():
    """A FAIL on a critical-severity check should hurt the score MORE than a
    PASS on a low-severity check helps it."""
    one_critical_fail = [
        {"id": "G42", "category": "conversion_tracking", "severity": "critical", "result": "fail"},
        {"id": "G26", "category": "ads_assets", "severity": "low", "result": "pass"},
    ]
    one_critical_pass = [
        {"id": "G42", "category": "conversion_tracking", "severity": "critical", "result": "pass"},
        {"id": "G26", "category": "ads_assets", "severity": "low", "result": "fail"},
    ]
    s_fail = _score(one_critical_fail, CATEGORY_WEIGHTS, SEVERITY_MULTIPLIERS)
    s_pass = _score(one_critical_pass, CATEGORY_WEIGHTS, SEVERITY_MULTIPLIERS)
    assert s_pass > s_fail, f"Expected critical-pass ({s_pass}) > critical-fail ({s_fail})"
    # And specifically the gap should be large
    assert s_pass - s_fail > 50.0
