"""Read-only UAC Doctor behavior and CLI contracts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.doctor import doctor_exit_code, run_doctor  # noqa: E402


def _assets(repo_root: Path) -> Path:
    return repo_root / "skills" / "ads-google-app" / "assets"


def _status(report: dict, check_id: str) -> str:
    return next(
        check["status"] for check in report["checks"] if check["id"] == check_id
    )


def test_doctor_reports_valid_ready_project_without_writing(repo_root, tmp_path):
    assets = _assets(repo_root)
    shutil.copyfile(assets / "UAC-INPUT.example.yaml", tmp_path / "UAC-INPUT.yaml")
    shutil.copyfile(
        assets / "ADS-EXPERIMENTS.minimal.yaml", tmp_path / "ADS-EXPERIMENTS.yaml"
    )
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    report = run_doctor(tmp_path, assets_dir=assets)

    assert report["status"] == "PASS"
    assert report["mutated_files"] is False
    assert report["files"] == {
        "input": "UAC-INPUT.yaml",
        "ledger": "ADS-EXPERIMENTS.yaml",
        "assets_available": True,
    }
    assert "可以运行确定性分析" in report["next_action"]
    assert doctor_exit_code(report) == 0
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_doctor_warns_on_legacy_ledger_and_gives_explicit_migration_step(
    repo_root, tmp_path
):
    assets = _assets(repo_root)
    shutil.copyfile(assets / "UAC-INPUT.example.yaml", tmp_path / "UAC-INPUT.yaml")
    ledger = yaml.safe_load(
        (assets / "ADS-EXPERIMENTS.minimal.yaml").read_text(encoding="utf-8")
    )
    ledger["schema_version"] = "1.0"
    (tmp_path / "ADS-EXPERIMENTS.yaml").write_text(
        yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8"
    )

    report = run_doctor(tmp_path, assets_dir=assets)

    assert report["status"] == "WARN"
    assert _status(report, "ledger-schema-version") == "WARN"
    assert "migrate-ledger" in report["next_action"]
    assert doctor_exit_code(report) == 0


def test_doctor_detects_waiting_experiment_and_blocks_new_one(repo_root, tmp_path):
    assets = _assets(repo_root)
    shutil.copyfile(assets / "UAC-INPUT.example.yaml", tmp_path / "UAC-INPUT.yaml")
    shutil.copyfile(
        assets / "ADS-EXPERIMENTS.example.yaml", tmp_path / "ADS-EXPERIMENTS.yaml"
    )

    report = run_doctor(tmp_path, assets_dir=assets)

    assert report["status"] == "WARN"
    assert _status(report, "open-experiments") == "WARN"
    assert _status(report, "waiting-maturity") == "WARN"
    assert "不应创建新实验" in report["next_action"]


def test_doctor_identifies_experiment_ready_for_terminal_review(repo_root, tmp_path):
    assets = _assets(repo_root)
    shutil.copyfile(assets / "UAC-INPUT.example.yaml", tmp_path / "UAC-INPUT.yaml")
    ledger = yaml.safe_load(
        (assets / "ADS-EXPERIMENTS.example.yaml").read_text(encoding="utf-8")
    )
    snapshot = ledger["experiments"][0]["result"]["review_snapshot"]
    snapshot["days_elapsed"] = 8
    snapshot["conversions_observed"] = 12
    (tmp_path / "ADS-EXPERIMENTS.yaml").write_text(
        yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8"
    )

    report = run_doctor(tmp_path, assets_dir=assets)

    assert report["status"] == "WARN"
    assert _status(report, "ready-for-review") == "WARN"
    assert "达到复盘条件" in report["next_action"]


def test_doctor_fails_closed_on_unknown_schema_and_missing_input(repo_root, tmp_path):
    ledger = {"schema_version": "9.9", "experiments": []}
    (tmp_path / "ADS-EXPERIMENTS.yaml").write_text(
        yaml.safe_dump(ledger), encoding="utf-8"
    )

    report = run_doctor(tmp_path, assets_dir=_assets(repo_root))

    assert report["status"] == "FAIL"
    assert _status(report, "experiment-ledger") == "FAIL"
    assert _status(report, "uac-input") == "WARN"
    assert doctor_exit_code(report) == 2
    assert report["project"] == "."
    assert str(tmp_path) not in json.dumps(report, ensure_ascii=False)


def test_doctor_requires_quick_numeric_example_and_output_schema(repo_root, tmp_path):
    source_assets = _assets(repo_root)
    assets = tmp_path / "assets"
    shutil.copytree(source_assets, assets)
    (assets / "UAC-QUICK-NUMERIC.example.yaml").unlink()
    project = tmp_path / "project"
    project.mkdir()

    report = run_doctor(project, assets_dir=assets)
    assets_check = next(
        check for check in report["checks"] if check["id"] == "uac-assets"
    )

    assert report["status"] == "FAIL"
    assert assets_check["status"] == "FAIL"
    assert assets_check["detail"] == ["UAC-QUICK-NUMERIC.example.yaml"]


def test_doctor_validates_quick_decision_schema(repo_root, tmp_path):
    source_assets = _assets(repo_root)
    assets = tmp_path / "assets"
    shutil.copytree(source_assets, assets)
    (assets / "uac-quick-decision.schema.json").write_text(
        '{"$schema":"https://json-schema.org/draft/2020-12/schema",'
        '"type":"not-a-json-schema-type"}',
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()

    report = run_doctor(project, assets_dir=assets)

    assert report["status"] == "FAIL"
    assert _status(report, "schema-json") == "FAIL"


def test_doctor_cli_json_is_machine_readable_and_preserves_exit_codes(
    repo_root, tmp_path
):
    assets = _assets(repo_root)
    shutil.copyfile(assets / "UAC-INPUT.example.yaml", tmp_path / "UAC-INPUT.yaml")
    shutil.copyfile(
        assets / "ADS-EXPERIMENTS.minimal.yaml", tmp_path / "ADS-EXPERIMENTS.yaml"
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "uac_experiment.py"),
            "doctor",
            str(tmp_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "PASS"
    assert report["mutated_files"] is False
    assert str(tmp_path) not in completed.stdout


def test_doctor_cli_survives_when_the_inherited_stream_is_ascii(repo_root, tmp_path):
    assets = _assets(repo_root)
    shutil.copyfile(assets / "UAC-INPUT.example.yaml", tmp_path / "UAC-INPUT.yaml")
    shutil.copyfile(
        assets / "ADS-EXPERIMENTS.minimal.yaml", tmp_path / "ADS-EXPERIMENTS.yaml"
    )
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "ascii"

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "uac_experiment.py"),
            "doctor",
            str(tmp_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr.decode("ascii")
    assert json.loads(completed.stdout.decode("ascii"))["status"] == "PASS"


def test_doctor_cli_missing_explicit_file_returns_two_without_traceback(
    repo_root, tmp_path
):
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "uac_experiment.py"),
            "doctor",
            str(tmp_path),
            "--input",
            "missing.yaml",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["status"] == "FAIL"
    assert "Traceback" not in completed.stderr
