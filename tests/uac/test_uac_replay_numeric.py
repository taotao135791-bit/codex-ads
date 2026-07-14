"""Numeric Quick Decision replay metrics and compatibility contracts."""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.replay import REPLAY_FILES, evaluate_replay, replay_path  # noqa: E402
from codex_ads.uac.types import ContractError  # noqa: E402

replay_module = importlib.import_module("codex_ads.uac.replay")


def _documents(case_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        filename: yaml.safe_load((case_dir / filename).read_text(encoding="utf-8"))
        for filename in REPLAY_FILES
    }


def _write_documents(case_dir: Path, documents: dict[str, dict[str, Any]]) -> None:
    for filename, document in documents.items():
        (case_dir / filename).write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


@pytest.fixture
def make_numeric_case(repo_root: Path, tmp_path: Path) -> Callable[[str], Path]:
    source = repo_root / "examples" / "replays" / "example-anonymized"

    def factory(name: str) -> Path:
        destination = tmp_path / name
        shutil.copytree(source, destination)
        documents = _documents(destination)
        for document in documents.values():
            document["case_id"] = name
        _add_numeric_input(documents["snapshot-before.yaml"]["uac_input"])
        system = documents["system-recommendation.yaml"]["codex_ads"]
        system["recommended_variables"] = ["bid"]
        system["protected_variables"] = ["budget", "creative"]
        documents["human-decision.yaml"]["human_judgment"] = (
            "Accept the bounded target-only recommendation and hold budget."
        )
        documents["actual-action.yaml"]["variables_changed"] = ["bid"]
        _write_documents(destination, documents)
        return destination

    return factory


def _daily_series() -> list[dict[str, Any]]:
    return [
        {
            "date": f"2026-07-{day:02d}",
            "spend": 65.0,
            "mature_events": 10,
            "value": 100.0,
        }
        for day in range(1, 8)
    ]


def _add_numeric_input(case: dict[str, Any]) -> None:
    case["goal"].update(
        {
            "target_cpa": 5.0,
            "maximum_acceptable_cpa": 6.0,
            "minimum_acceptable_roas": 1.5,
            "optimization_priority": "scale",
            "daily_budget_cap": 160.0,
        }
    )
    case["facts"].update(
        {
            "campaign_level": "AC2.5",
            "daily_budget": 100.0,
            "daily_series": _daily_series(),
        }
    )
    case["facts"]["metrics"].update(
        {
            "mature_actual_cpa": 4.8,
            "mature_actual_roas": 2.2,
            "mature_conversions": 70,
            "mature_revenue": 1001.0,
        }
    )
    case["maturity"].update(
        {
            "days_since_last_change": 7,
            "last_change_variables": [],
            "mature_events_since_change": 70,
        }
    )
    case["measurement"].update(
        {
            "value_missing_rate": 0.0,
            "currency_consistency_rate": 1.0,
            "google_mmp_value_difference_rate": 0.02,
            "mmp_backend_value_difference_rate": 0.03,
            "refund_rate": 0.05,
        }
    )
    case["quick_ops"] = {
        "question": "今天 tCPA 和预算怎么调？",
        "question_type": "bid_and_budget",
        "terminology_mapping_confirmed": True,
        "current_campaign": {
            "id": "anonymous-campaign",
            "level": "AC2.5",
            "optimization_event": "registration",
            "bidding_strategy": "tcpa",
            "value_optimization": False,
            "healthy": True,
        },
        "candidate_campaign": {
            "level": "AC2.5",
            "optimization_event": "registration",
            "bidding_strategy": "tcpa",
            "value_optimization": False,
        },
        "structure": {"same_optimization_event": True},
        "bid_budget": {
            "current_target": 5.0,
            "current_daily_budget": 100.0,
        },
        "review": {
            "after_days": 3,
            "minimum_additional_mature_events": 10,
            "maximum_additional_spend": 100.0,
        },
    }


def _ground_truth(
    *,
    target_direction: str = "INCREASE",
    target_value: float = 5.5,
    target_safe: bool = True,
    budget_direction: str = "NO_CHANGE",
    budget_value: float = 100.0,
    budget_safe: bool = True,
    no_action_expected: bool = False,
) -> dict[str, Any]:
    return {
        "target": {
            "expected_direction": target_direction,
            "expected_value": target_value,
            "safe_to_recommend": target_safe,
            "minimum_safe_value": 4.0,
            "maximum_safe_value": 6.0,
        },
        "budget": {
            "expected_direction": budget_direction,
            "expected_value": budget_value,
            "safe_to_recommend": budget_safe,
            "minimum_safe_value": 50.0,
            "maximum_safe_value": 160.0,
        },
        "no_action_expected": no_action_expected,
    }


def _set_ground_truth(case_dir: Path, value: dict[str, Any]) -> None:
    documents = _documents(case_dir)
    documents["snapshot-before.yaml"]["numeric_ground_truth"] = value
    _write_documents(case_dir, documents)


def _make_unexecuted(documents: dict[str, dict[str, Any]]) -> None:
    documents["actual-action.yaml"].update(
        {
            "executed": False,
            "executed_at": None,
            "variables_changed": [],
        }
    )
    documents["evaluation.yaml"].update(
        {
            "single_variable_compliant": False,
            "experiment_completed": False,
            "observation_conditions_met": False,
            "conclusive": False,
            "outcome": "not_executed",
        }
    )


def test_numeric_snapshot_runs_real_quick_decision_and_scores_all_metrics(
    make_numeric_case: Callable[[str], Path],
) -> None:
    path = make_numeric_case("numeric-correct")
    _set_ground_truth(path, _ground_truth())

    report = replay_path(path)
    numeric = report["cases"][0]["numeric_replay"]

    assert numeric["ground_truth_present"] is True
    assert numeric["system_recommendation"]["target"] == {
        "direction": "INCREASE",
        "action": "INCREASE",
        "execution_action": "INCREASE",
        "current_value": 5.0,
        "recommended_value": 5.5,
        "effective_value": 5.5,
    }
    assert numeric["system_recommendation"]["budget"]["direction"] == "NO_CHANGE"
    assert numeric["human_decision"]["accepted_system_recommendation"] is True
    assert numeric["after"] == {
        "executed": True,
        "confounded": False,
        "deviated": False,
        "mature_result_available": True,
    }
    assert numeric["evaluation"]["business_result_evaluable"] is True
    assert report["metrics"]["direction_accuracy"] == {
        "numerator": 1,
        "denominator": 1,
        "rate": 1.0,
    }
    assert report["metrics"]["magnitude_error"] == {
        "total_absolute_percentage_error": 0.0,
        "denominator": 1,
        "mean_absolute_percentage_error": 0.0,
    }
    assert report["metrics"]["unsafe_numeric_recommendation_rate"]["rate"] == 0.0
    assert report["metrics"]["no_action_correct_rate"]["rate"] is None
    assert report["metrics"]["human_acceptance_rate"]["rate"] == 1.0


def test_direction_can_be_correct_while_magnitude_has_error(
    make_numeric_case: Callable[[str], Path],
) -> None:
    path = make_numeric_case("numeric-magnitude-error")
    _set_ground_truth(path, _ground_truth(target_value=6.0))

    report = replay_path(path)

    assert report["metrics"]["direction_accuracy"]["rate"] == 1.0
    assert report["metrics"]["magnitude_error"] == {
        "total_absolute_percentage_error": 4.1667,
        "denominator": 1,
        "mean_absolute_percentage_error": 4.1667,
    }


def test_single_variable_ground_truth_excludes_the_missing_variable(
    make_numeric_case: Callable[[str], Path],
) -> None:
    path = make_numeric_case("numeric-target-only")
    truth = _ground_truth()
    truth.pop("budget")
    _set_ground_truth(path, truth)

    report = replay_path(path)
    numeric = report["cases"][0]["numeric_replay"]

    assert set(numeric["evaluation"]["components"]) == {"target"}
    assert report["metrics"]["direction_accuracy"]["rate"] == 1.0
    assert report["metrics"]["magnitude_error"]["mean_absolute_percentage_error"] == (
        0.0
    )


def test_mature_operational_action_can_score_without_claiming_an_experiment(
    make_numeric_case: Callable[[str], Path],
) -> None:
    path = make_numeric_case("numeric-operation")
    documents = _documents(path)
    documents["snapshot-before.yaml"]["numeric_ground_truth"] = _ground_truth()
    documents["system-recommendation.yaml"]["codex_ads"]["created_experiment"] = False
    documents["evaluation.yaml"].update(
        {
            "experiment_completed": False,
            "conclusive": False,
            "outcome": "inconclusive",
        }
    )
    _write_documents(path, documents)

    report = replay_path(path)

    assert report["cases"][0]["evaluation"]["attributable"] is False
    assert (
        report["cases"][0]["numeric_replay"]["evaluation"]["business_result_evaluable"]
        is True
    )
    assert report["metrics"]["direction_accuracy"]["rate"] == 1.0
    assert report["metrics"]["magnitude_error"]["denominator"] == 1


@pytest.mark.parametrize("excluded", ["rejected", "unexecuted", "confounded"])
def test_rejected_unexecuted_and_confounded_cases_do_not_score_business_result(
    make_numeric_case: Callable[[str], Path], excluded: str
) -> None:
    path = make_numeric_case(f"numeric-{excluded}")
    documents = _documents(path)
    documents["snapshot-before.yaml"]["numeric_ground_truth"] = _ground_truth()
    if excluded == "rejected":
        documents["human-decision.yaml"]["accepted_system_recommendation"] = False
    elif excluded == "unexecuted":
        _make_unexecuted(documents)
    else:
        documents["actual-action.yaml"]["concurrent_changes"] = ["product_release"]
        documents["snapshot-after.yaml"]["confounders"] = ["product_release"]
    _write_documents(path, documents)

    report = replay_path(path)
    numeric = report["cases"][0]["numeric_replay"]

    assert numeric["evaluation"]["business_result_evaluable"] is False
    assert numeric["evaluation"]["direction_correct"] is None
    assert numeric["evaluation"]["magnitude_error"] is None
    assert report["metrics"]["direction_accuracy"]["denominator"] == 0
    assert report["metrics"]["magnitude_error"]["denominator"] == 0
    assert report["metrics"]["unsafe_numeric_recommendation_rate"]["denominator"] == 1


def test_unsafe_change_and_correct_no_action_are_separate_metrics(
    make_numeric_case: Callable[[str], Path],
) -> None:
    unsafe_path = make_numeric_case("unsafe-numeric")
    _set_ground_truth(
        unsafe_path,
        _ground_truth(
            target_direction="NO_CHANGE",
            target_value=5.0,
            target_safe=False,
            budget_safe=False,
            no_action_expected=True,
        ),
    )

    unsafe = replay_path(unsafe_path)

    assert unsafe["metrics"]["unsafe_numeric_recommendation_rate"]["rate"] == 1.0
    assert unsafe["metrics"]["no_action_correct_rate"]["rate"] == 0.0

    no_action_path = make_numeric_case("correct-no-action")
    documents = _documents(no_action_path)
    case = documents["snapshot-before.yaml"]["uac_input"]
    case["maturity"].update(
        {
            "days_since_last_change": 1,
            "last_change_variables": ["target_cpa"],
            "mature_events_since_change": 1,
            "conversion_delay_elapsed_days": 0,
        }
    )
    documents["snapshot-before.yaml"]["numeric_ground_truth"] = _ground_truth(
        target_direction="NO_CHANGE",
        target_value=5.0,
        target_safe=False,
        budget_safe=False,
        no_action_expected=True,
    )
    _make_unexecuted(documents)
    _write_documents(no_action_path, documents)

    no_action = replay_path(no_action_path)

    assert no_action["metrics"]["unsafe_numeric_recommendation_rate"]["rate"] == 0.0
    assert no_action["metrics"]["no_action_correct_rate"]["rate"] == 1.0
    assert no_action["metrics"]["direction_accuracy"]["denominator"] == 0


def test_legacy_replay_can_add_numeric_labels_without_claiming_unknown_acceptance(
    make_numeric_case: Callable[[str], Path],
) -> None:
    path = make_numeric_case("legacy-numeric")
    documents = _documents(path)
    documents["snapshot-before.yaml"]["numeric_ground_truth"] = _ground_truth()
    system = documents.pop("system-recommendation.yaml")
    human = documents.pop("human-decision.yaml")
    documents["decision-at-the-time.yaml"] = {
        "schema_version": "1.0",
        "case_id": "legacy-numeric",
        "human_judgment": human["human_judgment"],
        "codex_ads": system["codex_ads"],
    }
    for filename in REPLAY_FILES:
        (path / filename).unlink(missing_ok=True)
    _write_documents(path, documents)

    report = replay_path(path)

    assert report["sample_size"] == 1
    assert report["cases"][0]["numeric_replay"]["ground_truth_present"] is True
    assert report["metrics"]["direction_accuracy"]["denominator"] == 0
    assert report["metrics"]["magnitude_error"]["denominator"] == 0
    assert report["metrics"]["human_acceptance_rate"]["denominator"] == 0


def test_legacy_snapshot_without_numeric_label_never_calls_quick_decision(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(_: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("legacy replay must not call decide_case")

    monkeypatch.setattr(replay_module, "decide_case", forbidden)

    report = replay_path(repo_root / "examples" / "replays" / "example-anonymized")

    assert report["cases"][0]["numeric_replay"] is None
    assert report["metrics"]["direction_accuracy"]["denominator"] == 0
    assert report["metrics"]["magnitude_error"]["denominator"] == 0
    assert report["metrics"]["unsafe_numeric_recommendation_rate"]["denominator"] == 0
    assert report["metrics"]["no_action_correct_rate"]["denominator"] == 0
    assert report["metrics"]["human_acceptance_rate"]["denominator"] == 0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_quick_ops", "requires snapshot-before.yaml uac_input.quick_ops"),
        ("missing_components", "must define target or budget"),
        ("unknown_direction", "expected_direction"),
        ("non_finite_value", "expected_value"),
        ("contradictory_direction", "INCREASE conflicts with expected_value"),
    ],
)
def test_numeric_ground_truth_fails_closed(
    make_numeric_case: Callable[[str], Path], mutation: str, message: str
) -> None:
    path = make_numeric_case(f"invalid-{mutation}")
    documents = _documents(path)
    truth = _ground_truth()
    if mutation == "missing_quick_ops":
        documents["snapshot-before.yaml"]["uac_input"].pop("quick_ops")
    elif mutation == "missing_components":
        truth.pop("target")
        truth.pop("budget")
    elif mutation == "unknown_direction":
        truth["target"]["expected_direction"] = "RELAX"
    elif mutation == "non_finite_value":
        truth["target"]["expected_value"] = float("nan")
    else:
        truth["target"]["expected_value"] = 4.5
    documents["snapshot-before.yaml"]["numeric_ground_truth"] = truth
    _write_documents(path, documents)

    with pytest.raises(ContractError, match=message):
        evaluate_replay(path)
