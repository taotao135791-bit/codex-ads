"""Private workspace layout and backward-compatible CLI behavior."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.workspace import (  # noqa: E402
    WORKSPACE_DIRECTORY_NAMES,
    Workspace,
    initialize_workspace,
    validate_workspace_name,
)


def _script(repo_root: Path) -> Path:
    return repo_root / "scripts" / "uac_experiment.py"


def _assets(repo_root: Path) -> Path:
    return repo_root / "skills" / "ads-google-app" / "assets"


def _run(
    repo_root: Path, *arguments: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script(repo_root)), *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def test_initialize_workspace_creates_private_safe_structure(tmp_path):
    workspace = initialize_workspace("Client Project", base_dir=tmp_path / "roots")

    assert workspace.initialized
    assert {path.name for path in workspace.root.iterdir() if path.is_dir()} == set(
        WORKSPACE_DIRECTORY_NAMES
    )
    context = yaml.safe_load(workspace.context_path.read_text(encoding="utf-8"))
    ledger = yaml.safe_load(workspace.ledger_path.read_text(encoding="utf-8"))
    assert context["privacy"] == {
        "contains_real_account_data": True,
        "commit_allowed": False,
        "anonymize_before_sharing": True,
    }
    assert context["status"] == "initialized_waiting_for_data"
    assert ledger["experiments"] == []
    assert not workspace.normalized_input_path.exists()
    assert (workspace.input_dir / "raw-summary.example.yaml").is_file()
    assert (
        (workspace.root / ".gitignore")
        .read_text(encoding="utf-8")
        .endswith("*\n!.gitignore\n")
    )

    if os.name != "nt":
        assert stat.S_IMODE(workspace.root.stat().st_mode) == 0o700
        for directory in WORKSPACE_DIRECTORY_NAMES:
            assert stat.S_IMODE((workspace.root / directory).stat().st_mode) == 0o700
        for private_file in (
            workspace.context_path,
            workspace.ledger_path,
            workspace.root / ".gitignore",
        ):
            assert stat.S_IMODE(private_file.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "client/account", r"client\account", "CON", "LPT1", "bad:name"],
)
def test_workspace_names_fail_closed_consistently_across_platforms(name):
    with pytest.raises(ValueError):
        validate_workspace_name(name)


def test_workspace_name_with_spaces_is_portable():
    assert validate_workspace_name("Client Project 01") == "Client Project 01"


def test_init_cli_uses_relative_display_path_and_doctor_workspace(repo_root, tmp_path):
    completed = _run(
        repo_root,
        "init-workspace",
        "Client Project",
        "--root",
        "workspace root",
        cwd=tmp_path,
    )

    assert completed.returncode == 0, completed.stderr
    assert "workspace root/Client Project" in completed.stdout
    assert str(tmp_path) not in completed.stdout
    workspace_path = tmp_path / "workspace root" / "Client Project"
    before = {
        path.relative_to(workspace_path): path.read_bytes()
        for path in workspace_path.rglob("*")
        if path.is_file()
    }

    doctor = _run(
        repo_root,
        "doctor",
        "--workspace",
        str(workspace_path),
        "--json",
    )

    assert doctor.returncode == 0, doctor.stderr
    report = json.loads(doctor.stdout)
    assert report["status"] == "WARN"
    assert any(
        check["id"] == "workspace-layout" and check["status"] == "PASS"
        for check in report["checks"]
    )
    assert report["files"]["ledger"] == "experiments/ADS-EXPERIMENTS.yaml"
    after = {
        path.relative_to(workspace_path): path.read_bytes()
        for path in workspace_path.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_doctor_workspace_fails_when_directory_was_not_initialized(repo_root, tmp_path):
    uninitialized = tmp_path / "not a workspace"
    uninitialized.mkdir()

    completed = _run(
        repo_root,
        "doctor",
        "--workspace",
        str(uninitialized),
        "--json",
    )

    assert completed.returncode == 2
    report = json.loads(completed.stdout)
    assert report["status"] == "FAIL"
    assert any(
        check["id"] == "workspace-layout" and check["status"] == "FAIL"
        for check in report["checks"]
    )


def test_workspace_normalization_keeps_incomplete_input_as_draft(repo_root, tmp_path):
    workspace = initialize_workspace("draft", base_dir=tmp_path)
    raw = workspace.input_dir / "summary.csv"
    raw.write_text("cost,installs\n100,20\n", encoding="utf-8")
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )
    previous_ready_input = workspace.normalized_input_path.read_bytes()

    completed = _run(
        repo_root,
        "normalize",
        "--workspace",
        str(workspace.root),
    )

    assert completed.returncode == 0, completed.stderr
    assert "not analysis-ready" in completed.stdout
    assert workspace.normalized_input_draft_path.is_file()
    assert workspace.normalized_input_path.read_bytes() == previous_ready_input
    envelope = json.loads(
        workspace.normalization_report_path.read_text(encoding="utf-8")
    )
    assert envelope["analysis_ready"] is False
    assert envelope["contract_error"]
    assert envelope["blocked_ready_input_sha256"]
    assert "do not run analysis on the draft" in envelope["next_action"]

    ledger_before = workspace.ledger_path.read_bytes()
    analyze = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
    )
    assert analyze.returncode == 2
    assert "no normalized UAC input" in analyze.stderr
    assert workspace.ledger_path.read_bytes() == ledger_before

    report_mtime = workspace.normalization_report_path.stat().st_mtime_ns
    os.utime(
        workspace.normalized_input_path,
        ns=(report_mtime + 1, report_mtime + 1),
    )
    touched_only = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
    )
    assert touched_only.returncode == 2
    assert "no normalized UAC input" in touched_only.stderr
    assert workspace.ledger_path.read_bytes() == ledger_before


def test_agent_can_complete_a_blocked_normalization_then_analyze(repo_root, tmp_path):
    workspace = initialize_workspace("agent-completed", base_dir=tmp_path)
    raw = workspace.input_dir / "summary.csv"
    raw.write_text("cost,installs\n100,20\n", encoding="utf-8")

    normalized = _run(
        repo_root,
        "normalize",
        "--workspace",
        str(workspace.root),
    )
    assert normalized.returncode == 0, normalized.stderr
    assert "not analysis-ready" in normalized.stdout

    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )

    doctor = _run(
        repo_root,
        "doctor",
        "--workspace",
        str(workspace.root),
        "--json",
    )
    assert doctor.returncode == 0, doctor.stderr
    assert json.loads(doctor.stdout)["status"] == "PASS"

    ledger_before = workspace.ledger_path.read_bytes()
    analyzed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
    )
    assert analyzed.returncode == 0, analyzed.stderr
    assert workspace.analysis_path.is_file()
    assert workspace.report_path.is_file()
    assert workspace.ledger_path.read_bytes() == ledger_before


def test_workspace_full_flow_writes_outputs_but_not_ledger_without_append(
    repo_root, tmp_path
):
    workspace = initialize_workspace("Project With Spaces", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.input_dir / "account export.yaml",
    )

    normalized = _run(
        repo_root,
        "normalize",
        "--workspace",
        str(workspace.root),
    )
    assert normalized.returncode == 0, normalized.stderr
    assert "analysis-ready input" in normalized.stdout
    assert workspace.normalized_input_path.is_file()

    doctor = _run(
        repo_root,
        "doctor",
        "--workspace",
        str(workspace.root),
        "--json",
    )
    assert doctor.returncode == 0, doctor.stderr
    assert json.loads(doctor.stdout)["status"] == "PASS"

    ledger_before = workspace.ledger_path.read_bytes()
    analyzed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
    )
    assert analyzed.returncode == 0, analyzed.stderr
    assert "ledger: unchanged" in analyzed.stdout
    assert json.loads(workspace.analysis_path.read_text(encoding="utf-8"))[
        "experiments"
    ]
    assert "UAC Experiment Loop Report" in workspace.report_path.read_text(
        encoding="utf-8"
    )
    assert workspace.ledger_path.read_bytes() == ledger_before
    if os.name != "nt":
        assert stat.S_IMODE(workspace.analysis_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(workspace.report_path.stat().st_mode) == 0o600

    validated = _run(
        repo_root,
        "validate-ledger",
        "--workspace",
        str(workspace.root),
    )
    reviewed = _run(
        repo_root,
        "review-ledger",
        "--workspace",
        str(workspace.root),
    )
    assert validated.returncode == 0, validated.stderr
    assert json.loads(reviewed.stdout) == {"reviews": [], "learnings": []}


def test_unfinished_workspace_experiment_blocks_append_without_changing_ledger(
    repo_root, tmp_path
):
    workspace = initialize_workspace("blocked", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )
    shutil.copyfile(
        _assets(repo_root) / "ADS-EXPERIMENTS.example.yaml",
        workspace.ledger_path,
    )
    before = workspace.ledger_path.read_bytes()

    completed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
        "--append-experiment",
    )

    assert completed.returncode == 2
    assert "did not produce an experiment proposal" in completed.stderr
    assert workspace.ledger_path.read_bytes() == before


def test_legacy_root_paths_still_work_and_get_migration_suggestion(repo_root, tmp_path):
    input_path = tmp_path / "UAC-INPUT.yaml"
    ledger_path = tmp_path / "ADS-EXPERIMENTS.yaml"
    shutil.copyfile(_assets(repo_root) / "UAC-INPUT.example.yaml", input_path)
    shutil.copyfile(_assets(repo_root) / "ADS-EXPERIMENTS.minimal.yaml", ledger_path)
    before = ledger_path.read_bytes()

    completed = _run(repo_root, "analyze", str(input_path), cwd=tmp_path)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["experiments"]
    assert "migration suggestion" in completed.stderr
    assert ledger_path.read_bytes() == before


def test_root_and_workspace_gitignore_protect_private_data_but_not_public_example(
    repo_root, tmp_path
):
    git_repo = tmp_path / "git repo"
    git_repo.mkdir()
    shutil.copyfile(repo_root / ".gitignore", git_repo / ".gitignore")
    subprocess.run(["git", "init", "-q"], cwd=git_repo, check=True)

    default_workspace = initialize_workspace(
        "default", base_dir=git_repo / "workspaces"
    )
    custom_workspace = initialize_workspace(
        "custom", base_dir=git_repo / "local projects"
    )
    for private_path in (
        default_workspace.context_path,
        default_workspace.ledger_path,
        custom_workspace.context_path,
        custom_workspace.ledger_path,
    ):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", str(private_path)],
            cwd=git_repo,
            check=False,
        )
        assert ignored.returncode == 0

    status = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "project-context.yaml" not in status
    assert "ADS-EXPERIMENTS.yaml" not in status

    public_example = (
        repo_root / "examples" / "replays" / "example-anonymized" / "evaluation.yaml"
    )
    public_check = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", str(public_example)],
        cwd=repo_root,
        check=False,
    )
    assert public_check.returncode == 1


def test_workspace_api_doctor_discovers_nested_files(repo_root, tmp_path):
    from codex_ads.uac.doctor import run_doctor

    workspace = initialize_workspace("api", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )

    report = run_doctor(workspace.root, assets_dir=_assets(repo_root))

    assert report["status"] == "PASS"
    assert report["files"]["input"] == "normalized/UAC-INPUT.yaml"
    assert report["files"]["ledger"] == "experiments/ADS-EXPERIMENTS.yaml"
    assert (
        Workspace.at(workspace.root).discover_case() == workspace.normalized_input_path
    )


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs Windows privileges")
def test_workspace_rejects_symlinked_output_directory_before_writing(
    repo_root, tmp_path
):
    workspace = initialize_workspace("symlink-output", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace.analysis_dir.rmdir()
    workspace.analysis_dir.symlink_to(outside, target_is_directory=True)

    completed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
    )

    assert completed.returncode == 2
    assert "workspace is not initialized" in completed.stderr
    assert not (outside / "UAC-ANALYSIS.json").exists()
    assert not workspace.report_path.exists()


def test_workspace_rejects_explicit_paths_outside_its_boundary(repo_root, tmp_path):
    workspace = initialize_workspace("outside-paths", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )
    outside_json = tmp_path / "outside.json"

    completed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
        "--json-output",
        str(outside_json),
    )

    assert completed.returncode == 2
    assert "must stay inside the private workspace" in completed.stderr
    assert not outside_json.exists()
    assert not workspace.report_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs Windows privileges")
def test_workspace_rejects_symlinked_output_file_before_writing(repo_root, tmp_path):
    workspace = initialize_workspace("symlink-file", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )
    outside = tmp_path / "outside.json"
    outside.write_text("unchanged\n", encoding="utf-8")
    workspace.analysis_path.symlink_to(outside)

    completed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
    )

    assert completed.returncode == 2
    assert "must not use a symbolic link" in completed.stderr
    assert outside.read_text(encoding="utf-8") == "unchanged\n"
    assert not workspace.report_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs Windows privileges")
def test_workspace_rejects_symlinked_root(repo_root, tmp_path):
    workspace = initialize_workspace("real-root", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(workspace.root, target_is_directory=True)

    completed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(linked_root),
    )

    assert completed.returncode == 2
    assert "workspace is not initialized" in completed.stderr
    assert not workspace.analysis_path.exists()
    assert not workspace.report_path.exists()

    doctor = _run(
        repo_root,
        "doctor",
        "--workspace",
        str(linked_root),
        "--json",
    )
    assert doctor.returncode == 2
    report = json.loads(doctor.stdout)
    assert report["status"] == "FAIL"
    assert any(
        check["id"] == "workspace-layout" and check["status"] == "FAIL"
        for check in report["checks"]
    )


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs Windows privileges")
def test_workspace_rejects_symlinked_raw_normalization_source(repo_root, tmp_path):
    workspace = initialize_workspace("linked-source", base_dir=tmp_path)
    outside = tmp_path / "outside.csv"
    outside.write_text("cost,installs\n100,20\n", encoding="utf-8")
    (workspace.input_dir / "source.csv").symlink_to(outside)

    completed = _run(
        repo_root,
        "normalize",
        "--workspace",
        str(workspace.root),
    )

    assert completed.returncode == 2
    assert "normalization input must not be a symbolic link" in completed.stderr
    assert not workspace.normalized_input_draft_path.exists()
    assert not workspace.normalization_report_path.exists()


def test_workspace_stops_when_its_private_gitignore_guard_is_removed(
    repo_root, tmp_path
):
    workspace = initialize_workspace("privacy-guard", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )
    workspace.gitignore_path.write_text("# guard removed\n", encoding="utf-8")

    completed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
    )

    assert completed.returncode == 2
    assert "workspace is not initialized" in completed.stderr
    assert not workspace.analysis_path.exists()
    assert not workspace.report_path.exists()


def test_workspace_stops_when_gitignore_reopens_private_output(repo_root, tmp_path):
    workspace = initialize_workspace("reopened-output", base_dir=tmp_path)
    shutil.copyfile(
        _assets(repo_root) / "UAC-INPUT.example.yaml",
        workspace.normalized_input_path,
    )
    workspace.gitignore_path.write_text(
        "*\n!.gitignore\n!analysis/\n!analysis/**\n",
        encoding="utf-8",
    )

    completed = _run(
        repo_root,
        "analyze",
        "--workspace",
        str(workspace.root),
    )

    assert completed.returncode == 2
    assert "workspace is not initialized" in completed.stderr
    assert not workspace.analysis_path.exists()
    assert not workspace.report_path.exists()
