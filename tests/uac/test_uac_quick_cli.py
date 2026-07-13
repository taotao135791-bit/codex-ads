"""CLI and Workspace contracts for the read-only Quick Decision entry."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.workspace import initialize_workspace  # noqa: E402


def _run(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "uac_experiment.py"), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def _example(repo_root: Path) -> Path:
    return (
        repo_root
        / "skills"
        / "ads-google-app"
        / "assets"
        / "UAC-QUICK-OPS.example.yaml"
    )


def test_decide_help_exposes_no_ledger_append_or_live_write(repo_root):
    completed = _run(repo_root, "decide", "--help")

    assert completed.returncode == 0
    assert "read-only Campaign Level operation card" in completed.stdout
    assert "--append-experiment" not in completed.stdout
    assert "--workspace" in completed.stdout


def test_legacy_decide_prints_compact_card_and_machine_json(repo_root):
    card = _run(repo_root, "decide", str(_example(repo_root)))
    machine = _run(repo_root, "decide", str(_example(repo_root)), "--json")

    assert card.returncode == 0, card.stderr
    assert card.stdout.startswith("结论：")
    assert "# UAC Experiment Loop Report" not in card.stdout
    assert machine.returncode == 0, machine.stderr
    result = json.loads(machine.stdout)
    assert result["decision"]["verdict"] == "KEEP_AC25_AND_TEST_AC30"
    assert result["account_write"] is False
    assert result["ledger_write"] is False
    assert result["experiments"] == []


def test_workspace_decide_writes_private_outputs_but_never_changes_ledger(
    repo_root, tmp_path
):
    workspace = initialize_workspace("quick-ops", base_dir=tmp_path)
    raw = workspace.input_dir / "anonymous-export.yaml"
    shutil.copyfile(_example(repo_root), raw)
    normalized = _run(repo_root, "normalize", "--workspace", str(workspace.root))
    assert normalized.returncode == 0, normalized.stderr
    ready = yaml.safe_load(workspace.normalized_input_path.read_text(encoding="utf-8"))
    assert ready["quick_ops"]["current_campaign"]["level"] == "AC2.5"
    assert ready["campaign_level_glossary"]["ac30"]["value_optimization"] is True

    ledger_before = workspace.ledger_path.read_bytes()
    completed = _run(repo_root, "decide", "--workspace", str(workspace.root))

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("结论：")
    assert "ledger: unchanged" in completed.stdout
    assert workspace.ledger_path.read_bytes() == ledger_before
    assert workspace.quick_decision_path.is_file()
    assert workspace.quick_decision_report_path.is_file()
    structured = json.loads(workspace.quick_decision_path.read_text(encoding="utf-8"))
    assert structured["decision"]["primary_action_count"] == 1
    assert workspace.quick_decision_report_path.read_text(encoding="utf-8").startswith(
        "结论："
    )


def test_decide_refuses_to_overwrite_input_or_ledger(repo_root, tmp_path):
    source = tmp_path / "input.yaml"
    ledger = tmp_path / "ledger.yaml"
    shutil.copyfile(_example(repo_root), source)
    ledger.write_text('schema_version: "1.1"\nexperiments: []\n', encoding="utf-8")

    overwrite_input = _run(
        repo_root,
        "decide",
        str(source),
        "--ledger",
        str(ledger),
        "--json-output",
        str(source),
    )
    overwrite_ledger = _run(
        repo_root,
        "decide",
        str(source),
        "--ledger",
        str(ledger),
        "--markdown-output",
        str(ledger),
    )

    assert overwrite_input.returncode == 2
    assert "must not overwrite" in overwrite_input.stderr
    assert overwrite_ledger.returncode == 2
    assert "must not overwrite" in overwrite_ledger.stderr


def test_decide_refuses_to_overwrite_glossary_or_workspace_controls(
    repo_root, tmp_path
):
    source = tmp_path / "input.yaml"
    glossary = tmp_path / "glossary.yaml"
    shutil.copyfile(_example(repo_root), source)
    glossary.write_text(
        "campaign_level_glossary:\n  ac25:\n    display_name: AC2.5\n",
        encoding="utf-8",
    )
    overwrite_glossary = _run(
        repo_root,
        "decide",
        str(source),
        "--glossary",
        str(glossary),
        "--json-output",
        str(glossary),
    )

    workspace = initialize_workspace("protected-controls", base_dir=tmp_path)
    shutil.copyfile(_example(repo_root), workspace.input_dir / "anonymous.yaml")
    normalized = _run(repo_root, "normalize", "--workspace", str(workspace.root))
    assert normalized.returncode == 0, normalized.stderr
    overwrite_context = _run(
        repo_root,
        "decide",
        "--workspace",
        str(workspace.root),
        "--json-output",
        str(workspace.context_path),
    )

    assert overwrite_glossary.returncode == 2
    assert "must not overwrite" in overwrite_glossary.stderr
    assert overwrite_context.returncode == 2
    assert "must not overwrite" in overwrite_context.stderr
