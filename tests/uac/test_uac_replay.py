"""Historical replay framework and metric aggregation contracts."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Callable

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.replay import (  # noqa: E402
    LEGACY_REPLAY_FILES,
    REPLAY_FILES,
    evaluate_replay,
    replay_path,
)
from codex_ads.uac.types import ContractError  # noqa: E402


def _documents(case_dir: Path) -> dict[str, dict]:
    return {
        filename: yaml.safe_load((case_dir / filename).read_text(encoding="utf-8"))
        for filename in REPLAY_FILES
    }


def _write_documents(case_dir: Path, documents: dict[str, dict]) -> None:
    for filename, document in documents.items():
        (case_dir / filename).write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


@pytest.fixture
def make_case(repo_root, tmp_path) -> Callable[[str], Path]:
    source = repo_root / "examples" / "replays" / "example-anonymized"

    def factory(name: str) -> Path:
        destination = tmp_path / name
        shutil.copytree(source, destination)
        documents = _documents(destination)
        for document in documents.values():
            document["case_id"] = name
        _write_documents(destination, documents)
        return destination

    return factory


def _make_data_blocked(case_dir: Path) -> dict[str, dict]:
    documents = _documents(case_dir)
    measurement = documents["snapshot-before.yaml"]["uac_input"]["measurement"]
    measurement["google_ads_vs_mmp"] = "unknown"
    return documents


def test_public_anonymous_positive_replay_and_all_required_metrics(repo_root):
    path = repo_root / "examples" / "replays" / "example-anonymized"
    report = replay_path(path)

    assert report["sample_size"] == 1
    assert report["cases"][0]["evaluation"]["classification"] == "positive_experiment"
    assert report["cases"][0]["evaluation"]["valid_experiment"] is True
    assert (
        report["cases"][0]["recorded_decision"]["accepted_system_recommendation"]
        is True
    )
    assert report["metrics"]["positive_experiment_rate"]["rate"] == 1.0
    assert report["metrics"]["time_saved_minutes"] == 25.0
    assert set(REPLAY_FILES) == {
        "snapshot-before.yaml",
        "system-recommendation.yaml",
        "human-decision.yaml",
        "actual-action.yaml",
        "snapshot-after.yaml",
        "evaluation.yaml",
    }
    assert set(report["metrics"]) == {
        "correct_block_rate",
        "unsafe_action_rate",
        "executable_recommendation_rate",
        "single_variable_compliance_rate",
        "experiment_completion_rate",
        "conclusive_experiment_rate",
        "confounded_rate",
        "positive_experiment_rate",
        "rollback_rate",
        "time_saved_minutes",
        "insufficient_evidence_rate",
        "direction_accuracy",
        "magnitude_error",
        "unsafe_numeric_recommendation_rate",
        "no_action_correct_rate",
        "human_acceptance_rate",
    }
    assert all(
        "causal" in item.lower() or "account" in item.lower()
        for item in report["disclaimers"][:2]
    )


def test_correct_block(make_case):
    path = make_case("correct-block")
    documents = _make_data_blocked(path)
    documents["actual-action.yaml"].update(
        {"executed": False, "executed_at": None, "variables_changed": []}
    )
    documents["evaluation.yaml"].update(
        {
            "correct_block": True,
            "recommendation_executable": False,
            "single_variable_compliant": False,
            "experiment_completed": False,
            "observation_conditions_met": False,
            "conclusive": False,
            "outcome": "not_executed",
            "insufficient_evidence": False,
        }
    )
    _write_documents(path, documents)

    result = evaluate_replay(path)
    assert result["evaluation"]["classification"] == "correct_block"
    assert result["evaluation"]["correct_block"] is True


def test_unsafe_action_while_system_is_data_blocked(make_case):
    path = make_case("unsafe-action")
    documents = _make_data_blocked(path)
    documents["evaluation.yaml"]["insufficient_evidence"] = True
    _write_documents(path, documents)

    result = evaluate_replay(path)
    assert result["evaluation"]["classification"] == "unsafe_action"
    assert result["evaluation"]["unsafe_action"] is True
    assert result["evaluation"]["valid_experiment"] is False
    assert result["evaluation"]["attributable"] is False
    assert result["evaluation"]["positive"] is False


def test_confounded_experiment_is_not_attributable(make_case):
    path = make_case("confounded")
    documents = _documents(path)
    documents["actual-action.yaml"]["concurrent_changes"] = ["product_release"]
    documents["snapshot-after.yaml"]["confounders"] = ["product_release"]
    _write_documents(path, documents)

    result = evaluate_replay(path)
    assert result["evaluation"]["classification"] == "confounded"
    assert result["evaluation"]["confounded"] is True
    assert result["evaluation"]["attributable"] is False

    aggregate = replay_path(path)
    assert aggregate["metrics"]["confounded_rate"] == {
        "numerator": 1,
        "denominator": 1,
        "rate": 1.0,
    }


def test_deviated_experiment_is_unattributable(make_case):
    path = make_case("unattributable")
    documents = _documents(path)
    documents["actual-action.yaml"]["deviated_from_recommendation"] = True
    _write_documents(path, documents)

    result = evaluate_replay(path)
    assert result["evaluation"]["classification"] == "unattributable"
    assert result["evaluation"]["valid_experiment"] is False
    aggregate = replay_path(path)
    assert aggregate["metrics"]["positive_experiment_rate"] == {
        "numerator": 0,
        "denominator": 0,
        "rate": None,
    }


def test_rejected_system_recommendation_is_not_an_effect_rate_denominator(make_case):
    path = make_case("human-rejected")
    documents = _documents(path)
    documents["human-decision.yaml"]["accepted_system_recommendation"] = False
    _write_documents(path, documents)

    result = replay_path(path)
    evaluation = result["cases"][0]["evaluation"]

    assert evaluation["classification"] == "unattributable"
    assert evaluation["valid_experiment"] is True
    assert evaluation["recommendation_accepted"] is False
    assert evaluation["attributable"] is False
    assert evaluation["positive"] is False
    assert result["metrics"]["positive_experiment_rate"] == {
        "numerator": 0,
        "denominator": 0,
        "rate": None,
    }


def test_unreported_variable_deviation_is_derived_and_unattributable(make_case):
    path = make_case("derived-deviation")
    documents = _documents(path)
    documents["actual-action.yaml"].update(
        {
            "variables_changed": ["bid"],
            "deviated_from_recommendation": False,
        }
    )
    documents["system-recommendation.yaml"]["codex_ads"]["protected_variables"] = [
        "budget"
    ]
    _write_documents(path, documents)

    result = evaluate_replay(path)

    assert result["evaluation"]["classification"] == "unattributable"
    assert result["evaluation"]["valid_experiment"] is False
    assert result["evaluation"]["attributable"] is False
    assert result["actual_action"]["reported_deviation"] is False
    assert result["actual_action"]["derived_variable_deviation"] is True
    assert result["actual_action"]["variable_matches_experiment"] is False


def test_negative_experiment_and_rollback(make_case):
    path = make_case("negative")
    documents = _documents(path)
    documents["evaluation.yaml"].update(
        {"outcome": "negative", "rollback_performed": True}
    )
    documents["actual-action.yaml"]["rollback_performed"] = True
    _write_documents(path, documents)

    result = replay_path(path)
    assert result["cases"][0]["evaluation"]["classification"] == "negative_experiment"
    assert result["cases"][0]["evaluation"]["negative"] is True
    assert result["metrics"]["rollback_rate"]["rate"] == 1.0


def test_insufficient_evidence_is_separate_from_correct_block(make_case):
    path = make_case("insufficient")
    documents = _make_data_blocked(path)
    documents["actual-action.yaml"].update(
        {"executed": False, "executed_at": None, "variables_changed": []}
    )
    documents["evaluation.yaml"].update(
        {
            "correct_block": False,
            "recommendation_executable": False,
            "single_variable_compliant": False,
            "experiment_completed": False,
            "observation_conditions_met": False,
            "conclusive": False,
            "outcome": "not_executed",
            "insufficient_evidence": True,
        }
    )
    _write_documents(path, documents)

    result = replay_path(path)
    assert result["cases"][0]["evaluation"]["classification"] == "insufficient_evidence"
    assert result["metrics"]["insufficient_evidence_rate"]["rate"] == 1.0


def test_insufficient_evidence_cannot_count_as_a_positive_experiment(make_case):
    path = make_case("insufficient-positive-label")
    documents = _documents(path)
    documents["evaluation.yaml"]["insufficient_evidence"] = True
    _write_documents(path, documents)

    result = replay_path(path)
    evaluation = result["cases"][0]["evaluation"]

    assert evaluation["classification"] == "insufficient_evidence"
    assert evaluation["valid_experiment"] is False
    assert evaluation["attributable"] is False
    assert evaluation["positive"] is False
    assert result["metrics"]["positive_experiment_rate"]["rate"] is None


def test_parent_directory_aggregates_multiple_cases(make_case, tmp_path):
    first = make_case("aggregate-positive")
    second = make_case("aggregate-negative")
    documents = _documents(second)
    documents["evaluation.yaml"]["outcome"] = "negative"
    _write_documents(second, documents)

    report = replay_path(tmp_path)
    assert {case["case_id"] for case in report["cases"]} == {
        first.name,
        second.name,
    }
    assert report["metrics"]["positive_experiment_rate"] == {
        "numerator": 1,
        "denominator": 2,
        "rate": 0.5,
    }


def test_non_experiment_action_cannot_push_experiment_rates_above_one(
    make_case, tmp_path
):
    make_case("valid-experiment")
    action_only = make_case("action-only")
    documents = _documents(action_only)
    documents["system-recommendation.yaml"]["codex_ads"]["created_experiment"] = False
    documents["actual-action.yaml"]["rollback_performed"] = True
    documents["evaluation.yaml"].update(
        {
            "experiment_completed": False,
            "observation_conditions_met": False,
            "conclusive": False,
            "outcome": "inconclusive",
            "rollback_performed": True,
        }
    )
    _write_documents(action_only, documents)

    report = replay_path(tmp_path)

    assert report["metrics"]["single_variable_compliance_rate"]["rate"] == 1.0
    assert report["metrics"]["experiment_completion_rate"]["rate"] == 1.0
    assert report["metrics"]["rollback_rate"] == {
        "numerator": 0,
        "denominator": 1,
        "rate": 0.0,
    }


def test_duplicate_case_ids_are_rejected(make_case, tmp_path):
    first = make_case("duplicate-one")
    second = make_case("duplicate-two")
    documents = _documents(second)
    for document in documents.values():
        document["case_id"] = first.name
    _write_documents(second, documents)

    with pytest.raises(ContractError, match="case_id values must be unique"):
        replay_path(tmp_path)


@pytest.mark.parametrize("invalid", [float("inf"), 123, True])
def test_case_id_must_be_a_nonempty_string(make_case, invalid):
    path = make_case("invalid-case-id")
    documents = _documents(path)
    for document in documents.values():
        document["case_id"] = invalid
    _write_documents(path, documents)

    with pytest.raises(ContractError, match="case_id must be a non-empty string"):
        evaluate_replay(path)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_time_saved_is_rejected(make_case, invalid):
    path = make_case("invalid-time")
    documents = _documents(path)
    documents["evaluation.yaml"]["time_saved_minutes"] = invalid
    _write_documents(path, documents)

    with pytest.raises(ContractError, match="time_saved_minutes"):
        evaluate_replay(path)


def test_conclusive_outcome_requires_numeric_after_metrics(make_case):
    path = make_case("missing-after-metrics")
    documents = _documents(path)
    documents["snapshot-after.yaml"]["metrics"] = {
        "install_guardrail_held": True,
        "comment": "no numeric outcome supplied",
    }
    _write_documents(path, documents)

    with pytest.raises(ContractError, match="finite numeric after-metric"):
        evaluate_replay(path)


@pytest.mark.parametrize("observation_days", [0, 6.99])
def test_claimed_maturity_cannot_override_minimum_observation_days(
    make_case, observation_days
):
    path = make_case(f"immature-{observation_days}")
    documents = _documents(path)
    documents["snapshot-after.yaml"]["observation_days"] = observation_days
    _write_documents(path, documents)

    with pytest.raises(ContractError, match="experiment_policy.minimum_days"):
        evaluate_replay(path)


def test_observation_days_equal_to_policy_minimum_are_conclusive(make_case):
    path = make_case("exact-minimum-days")
    documents = _documents(path)
    documents["snapshot-after.yaml"]["observation_days"] = 7
    _write_documents(path, documents)

    result = evaluate_replay(path)

    assert result["evaluation"]["classification"] == "positive_experiment"
    assert result["evaluation"]["observation_days"] == 7.0
    assert result["evaluation"]["minimum_observation_days"] == 7.0


def test_nonconclusive_replay_may_have_no_after_metrics(make_case):
    path = make_case("inconclusive-without-metrics")
    documents = _documents(path)
    documents["snapshot-after.yaml"].update(
        {
            "observation_days": 2,
            "conversion_delay_mature": False,
            "minimum_conversions_met": False,
            "metrics": {},
        }
    )
    documents["evaluation.yaml"].update(
        {
            "observation_conditions_met": False,
            "conclusive": False,
            "outcome": "inconclusive",
        }
    )
    _write_documents(path, documents)

    result = evaluate_replay(path)

    assert result["evaluation"]["classification"] == "unattributable"
    assert result["evaluation"]["attributable"] is False
    assert result["evaluation"]["has_numeric_after_metric"] is False


@pytest.mark.parametrize(
    ("executed", "outcome", "conclusive", "message"),
    [
        (True, "not_executed", False, "executed action"),
        (True, "inconclusive", True, "positive or negative outcome"),
    ],
)
def test_contradictory_execution_and_outcome_labels_are_rejected(
    make_case, executed, outcome, conclusive, message
):
    path = make_case(f"contradictory-{outcome}-{conclusive}")
    documents = _documents(path)
    documents["actual-action.yaml"]["executed"] = executed
    documents["evaluation.yaml"].update({"outcome": outcome, "conclusive": conclusive})
    _write_documents(path, documents)

    with pytest.raises(ContractError, match=message):
        evaluate_replay(path)


def test_aggregate_time_saved_overflow_is_rejected(make_case, tmp_path):
    first = make_case("overflow-one")
    second = make_case("overflow-two")
    for path in (first, second):
        documents = _documents(path)
        documents["evaluation.yaml"]["time_saved_minutes"] = 1e308
        _write_documents(path, documents)

    with pytest.raises(ContractError, match="aggregate time_saved_minutes"):
        replay_path(tmp_path)


def test_replay_requires_human_context_and_explicit_non_causal_label(make_case):
    path = make_case("missing-human-context")
    documents = _documents(path)
    del documents["human-decision.yaml"]["human_judgment"]
    _write_documents(path, documents)

    with pytest.raises(ContractError, match="human_judgment"):
        evaluate_replay(path)

    documents = _documents(path)
    documents["human-decision.yaml"]["human_judgment"] = "Reviewed locally."
    documents["evaluation.yaml"]["causal_claim"] = True
    _write_documents(path, documents)

    with pytest.raises(ContractError, match="causal_claim must be false"):
        evaluate_replay(path)


def test_legacy_five_file_replay_remains_compatible(make_case):
    path = make_case("legacy-five-file")
    documents = _documents(path)
    system = documents.pop("system-recommendation.yaml")
    human = documents.pop("human-decision.yaml")
    legacy = {
        **documents,
        "decision-at-the-time.yaml": {
            "schema_version": human["schema_version"],
            "case_id": human["case_id"],
            "human_judgment": human["human_judgment"],
            "codex_ads": system["codex_ads"],
        },
    }
    for filename in REPLAY_FILES:
        (path / filename).unlink(missing_ok=True)
    _write_documents(path, legacy)

    result = evaluate_replay(path)

    assert all((path / filename).is_file() for filename in LEGACY_REPLAY_FILES)
    assert result["evaluation"]["classification"] == "positive_experiment"
    assert result["recorded_decision"]["accepted_system_recommendation"] is None


def test_unexecuted_action_rejects_contradictory_change_records(make_case):
    path = make_case("contradictory-action")
    documents = _documents(path)
    documents["actual-action.yaml"].update(
        {"executed": False, "executed_at": None, "variables_changed": ["creative"]}
    )
    documents["evaluation.yaml"].update(
        {
            "experiment_completed": False,
            "observation_conditions_met": False,
            "conclusive": False,
            "outcome": "not_executed",
        }
    )
    _write_documents(path, documents)

    with pytest.raises(ContractError, match="unexecuted action"):
        evaluate_replay(path)
