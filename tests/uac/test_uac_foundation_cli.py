"""CLI smoke tests for normalization and historical replay additions."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
import yaml


def test_normalize_cli_maps_example_without_overwriting_source(repo_root, tmp_path):
    source = repo_root / "examples" / "normalization" / "uac-flat-input.yaml"
    output = tmp_path / "normalized.yaml"
    original = source.read_bytes()
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "uac_experiment.py"),
            "normalize",
            str(source),
            "--output",
            str(output),
            "--source-label",
            "anonymous-cli-example",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert result["source"]["label"] == "anonymous-cli-example"
    assert result["decision_made"] is False
    assert source.read_bytes() == original


def test_normalize_cli_refuses_input_overwrite(repo_root):
    source = repo_root / "examples" / "normalization" / "uac-flat-input.yaml"
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "uac_experiment.py"),
            "normalize",
            str(source),
            "--output",
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "must not overwrite" in completed.stderr


def test_replay_cli_human_and_json_outputs(repo_root):
    script = repo_root / "scripts" / "uac_experiment.py"
    case = repo_root / "examples" / "replays" / "example-anonymized"
    human = subprocess.run(
        [sys.executable, str(script), "replay", str(case)],
        check=False,
        capture_output=True,
        text=True,
    )
    machine = subprocess.run(
        [sys.executable, str(script), "replay", str(case), "--json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert human.returncode == 0, human.stderr
    assert "positive_experiment" in human.stdout
    assert "not causal proof" in human.stdout
    assert machine.returncode == 0, machine.stderr
    assert json.loads(machine.stdout)["sample_size"] == 1


@pytest.mark.parametrize(
    "object_field",
    [
        "scope",
        "goal",
        "facts",
        "measurement",
        "learning",
        "maturity",
        "permissions",
        "signals",
        "experiment_policy",
        "next_review",
        "active_experiment",
    ],
)
def test_analyze_cli_rejects_null_object_fields_without_traceback(
    repo_root, tmp_path, object_field
):
    source = tmp_path / "invalid.yaml"
    payload = {
        "scope": {
            "platform": "google_ads",
            "campaign_type": "app_campaign",
        },
        "evidence": [],
        object_field: None,
    }
    source.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "uac_experiment.py"),
            "analyze",
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert f"{object_field} must be an object" in completed.stderr
    assert "Traceback" not in completed.stderr
