"""Safety-edge regression tests for the deterministic UAC loop."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from uac_experiment import (  # noqa: E402
    ContractError,
    analyze_case,
    migrate_ledger,
    render_markdown,
    review_experiment,
    validate_analysis,
    validate_ledger,
)


@pytest.fixture(scope="module")
def cases(repo_root) -> dict[str, dict]:
    path = repo_root / "tests" / "fixtures" / "uac-cases.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {item["id"]: item["input"] for item in loaded["cases"]}


def test_client_approval_experiment_is_permission_blocked(cases):
    case = deepcopy(cases["tcpa_target_too_tight"])
    case["permissions"]["optimizer_can"].remove("bid")
    case["permissions"]["client_approval_required"] = ["bid"]

    result = analyze_case(case)

    assert result["optimization_feasibility"]["status"] == "PERMISSION_BLOCKED"
    assert result["experiments"] == []
    assert result["recommendations"][0]["permission"] == "CLIENT_APPROVAL_REQUIRED"


def test_budget_approval_and_missing_policy_have_safe_priority(cases):
    approval_case = deepcopy(cases["budget_cannot_support_goal"])
    approval_case["permissions"]["optimizer_can"].remove("budget")
    approval_case["permissions"]["client_approval_required"] = ["budget"]

    approval_result = analyze_case(approval_case)

    assert approval_result["optimization_feasibility"]["status"] == "PERMISSION_BLOCKED"
    assert approval_result["experiments"] == []

    missing_policy_case = deepcopy(cases["budget_cannot_support_goal"])
    del missing_policy_case["experiment_policy"]

    missing_policy_result = analyze_case(missing_policy_case)

    assert missing_policy_result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert missing_policy_result["experiments"] == []


def test_mature_days_without_minimum_conversions_blocks_new_experiment(cases):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    case["maturity"]["conversions_observed"] = 1
    case["maturity"]["minimum_conversions"] = 10

    result = analyze_case(case)

    assert result["learning_eligibility"]["status"] == "INSUFFICIENT_EVENT_VOLUME"
    assert result["optimization_feasibility"]["status"] == "LEARNING_BLOCKED"
    assert result["experiments"] == []


def test_unexecuted_proposal_blocks_stacking_without_fake_maturity(cases):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    proposal = analyze_case(case)["experiments"][0]
    ledger = {"schema_version": "1.0", "experiments": [proposal]}

    result = analyze_case(case, ledger)

    assert result["experiment_reviews"][0]["status"] == "PROPOSED_NOT_EXECUTED"
    assert result["experiment_reviews"][0]["active"] is False
    assert result["optimization_feasibility"]["status"] == "PERMISSION_BLOCKED"
    assert result["learning_eligibility"]["status"] == "LEARNABLE"
    assert result["experiments"] == []
    assert all(item["kind"] != "experiment" for item in result["recommendations"])


def test_unexecuted_proposal_cannot_publish_prior_learning(cases):
    proposal = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    proposal["decision"]["learning"] = {
        "scope": "reusable_heuristic",
        "statement": "This unexecuted idea must not become a learning.",
        "evidence": ["E-UNEXECUTED"],
    }

    result = analyze_case(
        deepcopy(cases["no_material_anomaly_hold"]),
        {"schema_version": "1.0", "experiments": [proposal]},
    )

    assert result["prior_learnings"] == []


def test_wrong_single_variable_and_multi_variable_guardrail_are_confounded():
    experiment = {
        "id": "UAC-EDGE",
        "variable": {"type": "creative"},
        "observation": {"minimum_days": 7, "minimum_conversions": 10},
        "result": {
            "review_snapshot": {
                "days_elapsed": 8,
                "conversions_observed": 12,
                "conversion_delay_mature": True,
                "concurrent_changes": ["budget"],
                "guardrail_breached": False,
            }
        },
    }
    assert review_experiment(experiment)["status"] == "CONFOUNDED"

    experiment["result"]["review_snapshot"]["concurrent_changes"] = [
        "creative",
        "budget",
    ]
    experiment["result"]["review_snapshot"]["guardrail_breached"] = True
    review = review_experiment(experiment)
    assert review["status"] == "CONFOUNDED"
    assert any("guardrail" in reason for reason in review["reasons"])


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_maturity_values_fail_closed(cases, invalid):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    case["maturity"]["days_elapsed"] = invalid

    with pytest.raises(ContractError, match="non-negative number"):
        analyze_case(case)


def test_funnel_overflow_is_omitted_and_reported_as_a_data_gap(cases):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    case["facts"]["metrics"].update({"installs": 1e-308, "registrations": 1e308})

    result = analyze_case(case)

    assert "installs->registrations" in result["funnel_state"]["invalid_rate_inputs"]
    assert not any(
        item["from"] == "installs" for item in result["funnel_state"]["observed_rates"]
    )
    assert any(
        "Funnel rates were omitted" in gap for gap in result["confidence"]["data_gaps"]
    )
    json.dumps(result, allow_nan=False, default=str)


def test_analysis_contract_rejects_nested_non_finite_output(cases):
    result = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))
    result["funnel_state"]["observed_rates"][0]["rate"] = float("inf")

    with pytest.raises(ContractError, match="non-finite number"):
        validate_analysis(result)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_review_rejects_non_finite_thresholds(invalid):
    experiment = {
        "id": "UAC-NON-FINITE",
        "variable": {"type": "creative"},
        "observation": {"minimum_days": invalid, "minimum_conversions": 1},
        "result": {
            "review_snapshot": {
                "days_elapsed": 8,
                "conversions_observed": 12,
                "conversion_delay_mature": True,
                "concurrent_changes": ["creative"],
                "guardrail_breached": False,
            }
        },
    }

    review = review_experiment(experiment)

    assert review["status"] == "INVALIDATED"
    assert "non-negative numeric maturity" in review["reasons"][0]


def test_completed_learning_is_preserved_in_context_and_report(cases):
    base_case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    completed = analyze_case(base_case)["experiments"][0]
    completed["status"] = "completed"
    completed["execution"] = {
        "approved": True,
        "executed_at": "2026-07-01T00:00:00Z",
        "notes": "",
    }
    completed["result"].update(
        {
            "status": "WIN",
            "rule_evaluation": {"success_rule_met": True},
            "metrics": {"cost_per_payment": 52.0, "install_volume": 480},
            "evidence_quality": "reconciled",
            "review_snapshot": {
                "days_elapsed": 8,
                "conversions_observed": 12,
                "conversion_delay_mature": True,
                "concurrent_changes": ["creative"],
                "guardrail_breached": False,
            },
        }
    )
    completed["decision"]["learning"] = {
        "scope": "account_specific",
        "statement": "Paid-value prefiltering improved this account under the declared conditions.",
        "evidence": ["E-EDGE"],
    }
    completed["decision"].update(
        {
            "outcome": "WIN",
            "next_action": "Keep the treatment and monitor declared guardrails.",
        }
    )
    ledger = {"schema_version": "1.0", "experiments": [completed]}

    result = analyze_case(deepcopy(cases["no_material_anomaly_hold"]), ledger)

    assert result["experiment_reviews"][0]["status"] == "WIN"
    assert result["prior_learnings"][0]["scope"] == "account_specific"
    assert "Prior account_specific learning" in render_markdown(result)


def test_invalid_enums_and_missing_maturity_degrade_safely(cases):
    typo = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    typo["learning"]["target_assessment"] = "reasnoable"
    with pytest.raises(ContractError):
        analyze_case(typo)

    missing = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    del missing["maturity"]["conversion_delay_elapsed_days"]
    result = analyze_case(missing)
    assert result["learning_eligibility"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert result["experiments"] == []


def test_install_goal_is_not_judged_by_zero_payments(cases):
    case = deepcopy(cases["cheap_installs_zero_payments"])
    case["goal"] = {
        "business_goal": "install",
        "optimization_event": "install",
        "bidding_strategy": "maximize_conversions",
        "proxy_evidence": "unknown",
    }

    result = analyze_case(case)

    assert result["diagnoses"][0]["code"] != "cheap_installs_zero_payments"


@pytest.mark.parametrize(
    ("human_name", "normalized"),
    [
        ("Install", "install"),
        ("Registration", "registration"),
        ("In-app action", "in_app_action"),
    ],
)
def test_human_readable_goal_names_are_normalized(cases, human_name, normalized):
    case = deepcopy(cases["no_material_anomaly_hold"])
    case["goal"].update(
        {
            "business_goal": human_name,
            "optimization_event": human_name,
            "proxy_evidence": "unknown",
        }
    )

    result = analyze_case(case)

    assert result["optimization_goal"]["business_goal"] == normalized
    assert result["optimization_goal"]["optimization_event"] == normalized
    assert result["optimization_goal"]["alignment"] == "aligned"


def test_missing_experiment_policy_does_not_raise_key_error(cases):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    del case["experiment_policy"]

    result = analyze_case(case)

    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert result["experiments"] == []


def test_ledger_validator_rejects_unsafe_contract(cases):
    experiment = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    experiment["platform"] = "meta_ads"
    experiment["hypothesis"]["falsifiable"] = False
    experiment["observation"]["minimum_days"] = -1
    experiment["guardrail_metrics"] = []

    errors = validate_ledger({"schema_version": "1.0", "experiments": [experiment]})

    assert any("platform" in error for error in errors)
    assert any("falsifiable" in error for error in errors)
    assert any("minimum_days" in error for error in errors)
    assert any("guardrail" in error for error in errors)


def test_ledger_validator_enforces_state_snapshot_and_schema_fields(cases):
    experiment = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    experiment["status"] = "completed"
    experiment["execution"] = {
        "approved": True,
        "executed_at": "2026-07-01T00:00:00Z",
        "notes": "",
    }
    experiment["result"]["status"] = "WIN"
    experiment["problem"]["confidence"] = "certainly"
    experiment["secondary_metrics"] = ["payment_rate", 1]
    experiment["decision"]["learning"] = {
        "scope": "account_specific",
        "statement": "Supported account-specific result.",
        "evidence": [1],
    }

    errors = validate_ledger({"schema_version": "1.0", "experiments": [experiment]})

    assert any("confidence" in error for error in errors)
    assert any("secondary_metrics" in error for error in errors)
    assert any("review_snapshot" in error for error in errors)
    assert any("learning.evidence" in error for error in errors)


def test_running_experiment_cannot_claim_a_terminal_result(cases):
    experiment = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    experiment["status"] = "running"
    experiment["execution"] = {
        "approved": True,
        "executed_at": "2026-07-01T00:00:00Z",
        "notes": "",
    }
    experiment["result"].update(
        {
            "status": "WIN",
            "review_snapshot": {
                "days_elapsed": 8,
                "conversions_observed": 12,
                "conversion_delay_mature": True,
                "concurrent_changes": ["creative"],
                "guardrail_breached": False,
            },
        }
    )

    errors = validate_ledger({"schema_version": "1.0", "experiments": [experiment]})

    assert any(
        "running experiment result.status must be pending" in error for error in errors
    )


def test_completed_result_cannot_bypass_maturity_or_guardrails(cases):
    experiment = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    experiment["status"] = "completed"
    experiment["execution"] = {
        "approved": True,
        "executed_at": "2026-07-01T00:00:00Z",
        "notes": "",
    }
    experiment["result"].update(
        {
            "status": "WIN",
            "review_snapshot": {
                "days_elapsed": 8,
                "conversions_observed": 12,
                "conversion_delay_mature": False,
                "concurrent_changes": ["creative"],
                "guardrail_breached": False,
            },
        }
    )

    errors = validate_ledger({"schema_version": "1.0", "experiments": [experiment]})

    assert any("conflicts with its maturity" in error for error in errors)


def test_deep_goal_missing_measurement_definitions_is_data_blocked(cases):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    for field in (
        "first_repeat_definition_clear",
        "payment_trial_refund_distinguished",
        "attribution_window_reviewed",
    ):
        del case["measurement"][field]

    result = analyze_case(case)

    assert result["measurement_state"]["status"] == "measurement_uncertain"
    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert result["experiments"] == []


@pytest.mark.parametrize(
    ("platform", "campaign_type"),
    [("meta_ads", "app_campaign"), ("google_ads", "search")],
)
def test_non_uac_scope_is_rejected(cases, platform, campaign_type):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    case["scope"].update({"platform": platform, "campaign_type": campaign_type})

    with pytest.raises(ContractError):
        analyze_case(case)


def test_string_boolean_signal_and_blank_evidence_are_rejected(cases):
    bad_signal = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    bad_signal["signals"]["lowest_cpi_has_worst_payment_rate"] = "false"
    with pytest.raises(ContractError):
        analyze_case(bad_signal)

    bad_evidence = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    bad_evidence["evidence"][0]["observation"] = "   "
    with pytest.raises(ContractError):
        analyze_case(bad_evidence)


def test_missing_evidence_or_window_degrades_without_experiment_advice(cases):
    missing_evidence = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    missing_evidence["evidence"] = []
    result = analyze_case(missing_evidence)
    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert result["experiments"] == []
    assert all(item["kind"] != "experiment" for item in result["recommendations"])

    missing_window = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    del missing_window["scope"]["start_date"]
    result = analyze_case(missing_window)
    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert any("scope.start_date" in gap for gap in result["confidence"]["data_gaps"])


@pytest.mark.parametrize(
    "mutation",
    [
        "empty_id",
        "invalid_confidence",
        "missing_direction",
        "invalid_guardrail",
        "empty_treatment",
    ],
)
def test_incomplete_experiment_policy_degrades_to_investigation(cases, mutation):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    policy = case["experiment_policy"]
    if mutation == "empty_id":
        policy["id"] = ""
    elif mutation == "invalid_confidence":
        policy["confidence"] = "certain"
    elif mutation == "missing_direction":
        del policy["primary_metric"]["direction"]
    elif mutation == "invalid_guardrail":
        policy["guardrail_metrics"] = [1]
    else:
        policy["treatment_definition"] = ""

    result = analyze_case(case)

    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert result["experiments"] == []
    assert all(item["kind"] != "experiment" for item in result["recommendations"])
    assert any("experiment_policy" in gap for gap in result["confidence"]["data_gaps"])


@pytest.mark.parametrize("goal", ["registration", "In-app action"])
def test_zero_payments_does_not_invent_payment_problem_for_shallow_goals(cases, goal):
    case = deepcopy(cases["cheap_installs_zero_payments"])
    case["goal"].update(
        {
            "business_goal": goal,
            "optimization_event": goal,
            "proxy_evidence": "unknown",
        }
    )

    result = analyze_case(case)

    assert result["diagnoses"][0]["code"] != "cheap_installs_zero_payments"


def test_malformed_lightweight_active_experiment_fails_closed(cases):
    case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    case["active_experiment"] = {
        "id": "UAC-BAD-ACTIVE",
        "variable": "creative",
        "observation": {"minimum_days": 7, "minimum_conversions": 10},
        "result": {
            "review_snapshot": {
                "days_elapsed": 8,
                "conversions_observed": 12,
                "conversion_delay_mature": True,
                "concurrent_changes": ["creative"],
                "guardrail_breached": False,
            }
        },
    }

    result = analyze_case(case)

    assert result["experiment_reviews"][0]["status"] == "INVALIDATED"
    assert result["experiments"] == []


def test_terminal_evidence_and_decision_cannot_be_self_declared(cases):
    experiment = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    experiment["status"] = "completed"
    experiment["execution"] = {
        "approved": True,
        "executed_at": "2026-07-01T00:00:00Z",
        "notes": "",
    }
    experiment["result"].update(
        {
            "status": "WIN",
            "rule_evaluation": {"success_rule_met": True},
            "metrics": {"cost_per_payment": 52.0},
            "evidence_quality": "reconciled",
            "review_snapshot": {
                "days_elapsed": 8,
                "conversions_observed": 12,
                "conversion_delay_mature": True,
                "concurrent_changes": [],
                "guardrail_breached": False,
            },
        }
    )
    experiment["decision"].update(
        {"outcome": "LOSS", "next_action": "Scale the treatment."}
    )

    errors = validate_ledger({"schema_version": "1.0", "experiments": [experiment]})

    assert any("concurrent_changes" in error for error in errors)
    assert any("decision.outcome" in error for error in errors)


def test_cancelled_proposal_is_a_valid_auditable_close_path(cases):
    proposal = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    proposal["status"] = "cancelled"
    proposal["result"].update(
        {"status": "INVALIDATED", "evidence_quality": "not_executed"}
    )
    proposal["decision"] = {
        "outcome": "CANCELLED",
        "next_action": "Reassess after new cohort evidence arrives.",
        "learning": None,
    }
    ledger = {"schema_version": "1.0", "experiments": [proposal]}

    assert validate_ledger(ledger) == []
    result = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]), ledger)
    assert result["experiment_reviews"][0]["status"] == "CANCELLED_NOT_EXECUTED"
    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert any("unique id" in gap for gap in result["confidence"]["data_gaps"])

    next_case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    next_case["experiment_policy"]["id"] = "UAC-FIXTURE-002"
    next_result = analyze_case(next_case, ledger)
    assert next_result["optimization_feasibility"]["status"] == "EXPERIMENT_AVAILABLE"
    assert next_result["experiments"][0]["id"] == "UAC-FIXTURE-002"


def test_schema_and_runtime_reject_conflicting_rule_outcomes(repo_root, cases):
    jsonschema = pytest.importorskip("jsonschema")
    experiment = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    experiment["result"]["rule_evaluation"] = {
        "success_rule_met": True,
        "rollback_rule_met": True,
    }
    ledger = {"schema_version": "1.0", "experiments": [experiment]}
    schema = json.loads(
        (
            repo_root
            / "skills"
            / "ads-google-app"
            / "assets"
            / "ads-experiments.schema.json"
        ).read_text(encoding="utf-8")
    )

    assert any("only one" in error for error in validate_ledger(ledger))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(ledger)


def test_malformed_yaml_cli_returns_clean_error(repo_root, tmp_path):
    malformed = tmp_path / "bad.yaml"
    malformed.write_text("evidence: [\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "uac_experiment.py"),
            "analyze",
            str(malformed),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "error:" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_out_of_range_integer_is_rejected_without_overflow(cases):
    source_case = deepcopy(cases["lowest_cpi_has_worst_payment_rate"])
    source_case["facts"]["metrics"]["spend"] = 10**10000

    with pytest.raises(ContractError, match="non-negative number"):
        analyze_case(source_case)


@pytest.mark.parametrize(
    ("path", "invalid"),
    [
        (("id",), []),
        (("status",), []),
        (("result", "evaluation"), []),
        (("result", "evidence_quality"), {}),
    ],
)
def test_validate_ledger_returns_errors_for_unhashable_values(cases, path, invalid):
    experiment = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    target = experiment
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = invalid

    errors = validate_ledger({"schema_version": "1.1", "experiments": [experiment]})

    assert errors


def test_ledger_rejects_nested_non_finite_values_before_migration(cases):
    experiment = analyze_case(deepcopy(cases["lowest_cpi_has_worst_payment_rate"]))[
        "experiments"
    ][0]
    experiment["result"]["metrics"] = {"nested": {"value": float("inf")}}
    ledger = {
        "schema_version": "1.1",
        "project": {"extra": {"score": float("nan")}},
        "experiments": [experiment],
    }

    errors = validate_ledger(ledger)

    assert any("ledger.project.extra.score" in error for error in errors)
    assert any(
        "ledger.experiments[0].result.metrics.nested.value" in error for error in errors
    )
    with pytest.raises(ContractError, match="non-finite number"):
        migrate_ledger(ledger)


def test_cli_refuses_to_overwrite_input_with_output(repo_root, tmp_path):
    source = (
        repo_root / "skills" / "ads-google-app" / "assets" / "UAC-INPUT.example.yaml"
    )
    input_path = tmp_path / "input.yaml"
    original = source.read_text(encoding="utf-8")
    input_path.write_text(original, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "uac_experiment.py"),
            "analyze",
            str(input_path),
            "--json-output",
            str(input_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "must not overwrite" in completed.stderr
    assert input_path.read_text(encoding="utf-8") == original


def test_cli_auto_discovers_ledger_and_can_cancel_proposal(repo_root, tmp_path):
    script = repo_root / "scripts" / "uac_experiment.py"
    assets = repo_root / "skills" / "ads-google-app" / "assets"
    input_path = tmp_path / "UAC-INPUT.yaml"
    ledger_path = tmp_path / "ADS-EXPERIMENTS.yaml"
    input_path.write_text(
        (assets / "UAC-INPUT.example.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    ledger_path.write_text(
        (assets / "ADS-EXPERIMENTS.minimal.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    append = subprocess.run(
        [
            sys.executable,
            str(script),
            "analyze",
            str(input_path),
            "--append-experiment",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert append.returncode == 0, append.stderr
    stored = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    proposal_id = stored["experiments"][0]["id"]

    readback = subprocess.run(
        [sys.executable, str(script), "analyze", str(input_path)],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert readback.returncode == 0, readback.stderr
    result = json.loads(readback.stdout)
    assert result["optimization_feasibility"]["status"] == "PERMISSION_BLOCKED"
    assert result["experiments"] == []

    cancelled = subprocess.run(
        [
            sys.executable,
            str(script),
            "cancel-proposal",
            str(ledger_path),
            proposal_id,
            "--reason",
            "Client declined this concept.",
            "--next-action",
            "Wait for the next approved creative brief.",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert cancelled.returncode == 0, cancelled.stderr
    stored = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    assert stored["experiments"][0]["status"] == "cancelled"
    assert stored["experiments"][0]["decision"]["outcome"] == "CANCELLED"
