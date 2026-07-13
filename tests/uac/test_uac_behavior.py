"""Fixture replay tests for deterministic UAC decisions."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from uac_experiment import (  # noqa: E402
    analyze_case,
    render_markdown,
    review_experiment,
    validate_experiment,
    validate_ledger,
)


@pytest.fixture(scope="session")
def uac_cases(repo_root) -> list[dict]:
    path = repo_root / "tests" / "fixtures" / "uac-cases.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["cases"]


def test_at_least_twelve_real_behavior_cases_exist(uac_cases):
    assert len(uac_cases) >= 12
    assert len({case["id"] for case in uac_cases}) == len(uac_cases)


def test_uac_fixture_replay_contract(uac_cases):
    failures: list[str] = []
    for fixture in uac_cases:
        result = analyze_case(fixture["input"])
        expected = fixture["expected"]
        diagnosis = result["diagnoses"][0]["code"]
        feasibility = result["optimization_feasibility"]["status"]
        learning = result["learning_eligibility"]["status"]
        variables = {item["variable"] for item in result["recommendations"]}
        rendered_actions = " ".join(
            item["action"] for item in result["recommendations"]
        )

        if diagnosis != expected["diagnosis"]:
            failures.append(f"{fixture['id']}: diagnosis {diagnosis}")
        if feasibility != expected["feasibility"]:
            failures.append(f"{fixture['id']}: feasibility {feasibility}")
        if learning != expected["learning"]:
            failures.append(f"{fixture['id']}: learning {learning}")
        if bool(result["experiments"]) != expected["experiment_allowed"]:
            failures.append(f"{fixture['id']}: experiment admission mismatch")
        if not set(expected["allowed_variables"]).issubset(variables):
            failures.append(f"{fixture['id']}: missing allowed variable")
        for forbidden in expected["forbidden_variables"]:
            if forbidden in variables or forbidden in rendered_actions:
                failures.append(
                    f"{fixture['id']}: emitted forbidden action {forbidden}"
                )

        status = expected["experiment_status"]
        if status and status not in {
            review["status"] for review in result["experiment_reviews"]
        }:
            failures.append(f"{fixture['id']}: missing review status {status}")

    assert not failures, "fixture replay failures:\n" + "\n".join(failures)


def test_every_generated_experiment_is_single_variable_and_reversible(uac_cases):
    generated = [analyze_case(case["input"])["experiments"] for case in uac_cases]
    experiments = [items[0] for items in generated if items]
    assert experiments

    for experiment in experiments:
        assert validate_experiment(experiment) == []
        assert experiment["variable"]["single_variable_change"] is True
        assert experiment["permission"]["classification"] == "OPTIMIZER_CAN_EXECUTE"
        assert experiment["execution"]["approved"] is False
        assert experiment["observation"]["minimum_days"] is not None
        assert experiment["observation"]["minimum_conversions"] is not None
        assert experiment["observation"]["conversion_delay_days"] is not None
        assert experiment["success_rule"]
        assert experiment["rollback_rule"]
        assert experiment["inconclusive_rule"]
        assert experiment["guardrail_metrics"]


def test_tracking_and_maturity_blocks_never_create_experiments(uac_cases):
    for fixture in uac_cases:
        result = analyze_case(fixture["input"])
        state = result["optimization_feasibility"]["status"]
        if state in {"TRACKING_BLOCKED", "NO_ACTION_RECOMMENDED"}:
            assert result["experiments"] == [], fixture["id"]
        if result["learning_eligibility"]["status"] == "CONVERSION_DELAY_NOT_MATURE":
            assert result["experiments"] == [], fixture["id"]


def test_missing_evidence_degrades_safely_without_action():
    result = analyze_case(
        {
            "scope": {"platform": "google_ads", "campaign_type": "app_campaign"},
            "facts": {"segmentation_complete": False, "metrics": {}},
            "measurement": {},
            "learning": {},
            "maturity": {},
            "permissions": {"optimizer_can": ["budget", "bid", "creative"]},
            "evidence": [],
        }
    )
    assert result["measurement_state"]["status"] == "insufficient_evidence"
    assert result["learning_eligibility"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert result["experiments"] == []
    assert "无法在当前证据下完成该层级判断。" in result["confidence"]["data_gaps"]


def test_goal_and_funnel_are_structured_without_claiming_causality(uac_cases):
    result = analyze_case(uac_cases[0]["input"])
    assert result["optimization_goal"]["alignment"] == "optimization_event_too_shallow"
    assert result["optimization_goal"]["proxy_quality"] == "supported_proxy"
    assert result["funnel_state"]["observed_rates"]
    assert result["funnel_state"]["causal_attribution"] == "undetermined"


def test_uncertain_measurement_cannot_admit_an_experiment(uac_cases):
    case = json.loads(json.dumps(uac_cases[0]["input"], default=str))
    case["measurement"]["google_ads_vs_mmp"] = "unknown"
    result = analyze_case(case)
    assert result["measurement_state"]["status"] == "measurement_uncertain"
    assert result["learning_eligibility"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["optimization_feasibility"]["status"] == "DATA_BLOCKED"
    assert result["experiments"] == []


def test_permission_classes_separate_operator_client_product_and_tracking(uac_cases):
    funnel = next(
        case for case in uac_cases if case["id"] == "registration_normal_paywall_low"
    )
    funnel_result = analyze_case(funnel["input"])
    funnel_permissions = {
        item["variable"]: item["classification"]
        for item in funnel_result["permissions"]
    }
    assert funnel_permissions["creative"] == "OPTIMIZER_CAN_EXECUTE"
    assert funnel_permissions["paywall"] == "PRODUCT_DEPENDENCY"

    mismatch = next(
        case for case in uac_cases if case["id"] == "google_mmp_payment_mismatch"
    )
    mismatch_result = analyze_case(mismatch["input"])
    mismatch_permissions = {
        item["variable"]: item["classification"]
        for item in mismatch_result["permissions"]
    }
    assert mismatch_permissions["tracking"] == "TRACKING_DEPENDENCY"
    assert mismatch_permissions["measurement_export"] == "CLIENT_DATA_REQUIRED"


def test_country_case_never_recommends_country_total_action(uac_cases):
    fixture = next(
        case
        for case in uac_cases
        if case["id"] == "country_total_hides_segment_anomaly"
    )
    result = analyze_case(fixture["input"])
    actions = " ".join(item["action"] for item in result["recommendations"])
    assert "break the anomaly down" in actions
    assert "pause country" not in actions
    assert "scale country" not in actions
    assert any("country totals alone" in item for item in result["do_not_touch"])


def test_no_anomaly_case_explicitly_holds(uac_cases):
    fixture = next(
        case for case in uac_cases if case["id"] == "no_material_anomaly_hold"
    )
    result = analyze_case(fixture["input"])
    assert result["optimization_feasibility"]["status"] == "NO_ACTION_RECOMMENDED"
    assert result["recommendations"][0]["kind"] == "monitoring"
    assert "do not modify" in result["recommendations"][0]["action"]


def test_experiment_review_distinguishes_maturity_volume_and_confounding():
    base = {
        "id": "UAC-REVIEW",
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
    waiting = json.loads(json.dumps(base))
    waiting["result"]["review_snapshot"]["conversion_delay_mature"] = False
    assert review_experiment(waiting)["status"] == "WAITING_FOR_MATURITY"

    low_volume = json.loads(json.dumps(base))
    low_volume["result"]["review_snapshot"]["conversions_observed"] = 3
    assert review_experiment(low_volume)["status"] == "INSUFFICIENT_VOLUME"

    confounded = json.loads(json.dumps(base))
    confounded["result"]["review_snapshot"]["concurrent_changes"] = [
        "budget",
        "creative",
    ]
    assert review_experiment(confounded)["status"] == "CONFOUNDED"


def test_completed_learning_is_read_as_context_not_global_truth(uac_cases):
    source = next(
        case for case in uac_cases if case["id"] == "lowest_cpi_has_worst_payment_rate"
    )
    completed = analyze_case(source["input"])["experiments"][0]
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
        "scope": "creative_specific",
        "statement": "Paid-value framing worked for this account and concept only.",
        "evidence": ["E-015"],
    }
    completed["decision"].update(
        {
            "outcome": "WIN",
            "next_action": "Keep the winning treatment and continue guardrail monitoring.",
        }
    )
    ledger = {"schema_version": "1.0", "experiments": [completed]}
    assert validate_ledger(ledger) == []

    result = analyze_case(source["input"], ledger)
    assert result["prior_learnings"] == [
        {
            "experiment_id": completed["id"],
            "scope": "creative_specific",
            "statement": "Paid-value framing worked for this account and concept only.",
            "evidence": ["E-015"],
        }
    ]


def test_markdown_report_uses_required_order(uac_cases):
    result = analyze_case(uac_cases[0]["input"])
    report = render_markdown(result)
    headings = [
        "## 1. Executive summary",
        "## 2. 当前优化状态",
        "## 3. 数据与测量可靠性",
        "## 4. 学习资格",
        "## 5. 关键证据",
        "## 6. 当前主要阻塞",
        "## 7. 可控变量",
        "## 8. 不可控变量",
        "## 9. 当前唯一优先实验",
        "## 10. 实验观察条件",
        "## 11. 客户需要配合的事项",
        "## 12. Do not touch",
        "## 13. 下一次复盘条件",
        "## 14. 置信度和数据缺口",
    ]
    positions = [report.index(heading) for heading in headings]
    assert positions == sorted(positions)


def test_example_ledger_and_json_schemas_validate(repo_root, uac_cases):
    jsonschema = pytest.importorskip("jsonschema")
    assets = repo_root / "skills" / "ads-google-app" / "assets"
    ledger = yaml.safe_load(
        (assets / "ADS-EXPERIMENTS.example.yaml").read_text(encoding="utf-8")
    )
    assert validate_ledger(ledger) == []

    ledger_schema = json.loads(
        (assets / "ads-experiments.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(ledger_schema).validate(ledger)

    analysis = analyze_case(uac_cases[0]["input"])
    analysis_schema = json.loads(
        (assets / "uac-analysis.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(analysis_schema).validate(analysis)


def test_uac_cli_report_smoke(repo_root, tmp_path):
    script = repo_root / "scripts" / "uac_experiment.py"
    sample = (
        repo_root / "skills" / "ads-google-app" / "assets" / "UAC-INPUT.example.yaml"
    )
    output_json = tmp_path / "analysis.json"
    output_md = tmp_path / "report.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "analyze",
            str(sample),
            "--json-output",
            str(output_json),
            "--markdown-output",
            str(output_md),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output_json.read_text(encoding="utf-8"))["experiments"]
    assert "UAC Experiment Loop Report" in output_md.read_text(encoding="utf-8")


def test_cli_appends_only_unapproved_proposal_and_reads_it_back(repo_root, tmp_path):
    script = repo_root / "scripts" / "uac_experiment.py"
    assets = repo_root / "skills" / "ads-google-app" / "assets"
    ledger = tmp_path / "ADS-EXPERIMENTS.yaml"
    shutil.copyfile(assets / "ADS-EXPERIMENTS.minimal.yaml", ledger)

    append = subprocess.run(
        [
            sys.executable,
            str(script),
            "analyze",
            str(assets / "UAC-INPUT.example.yaml"),
            "--ledger",
            str(ledger),
            "--append-experiment",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert append.returncode == 0, append.stderr
    stored = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    assert len(stored["experiments"]) == 1
    assert stored["experiments"][0]["status"] == "proposed"
    assert stored["experiments"][0]["execution"]["approved"] is False

    result = analyze_case(
        yaml.safe_load((assets / "UAC-INPUT.example.yaml").read_text(encoding="utf-8")),
        stored,
    )
    assert result["experiments"] == []
    assert result["experiment_reviews"][0]["status"] == "PROPOSED_NOT_EXECUTED"
    assert result["experiment_reviews"][0]["active"] is False
    assert result["optimization_feasibility"]["status"] == "PERMISSION_BLOCKED"
    assert all(item["kind"] != "experiment" for item in result["recommendations"])
