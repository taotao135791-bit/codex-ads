"""Redacted privacy scan behavior and current-tree release gate."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from privacy_doctor import build_report  # noqa: E402


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_current_repository_tree_has_no_high_confidence_privacy_findings(repo_root):
    report = build_report(repo_root, history=False)

    assert report["status"] == "PASS"
    assert report["findings"] == []


def test_tree_finding_is_redacted_and_nonzero(tmp_path):
    _git(tmp_path, "init", "-q")
    token = "ghp_" + "A" * 36
    (tmp_path / "unsafe.txt").write_text(token, encoding="utf-8")

    report = build_report(tmp_path, history=False)
    serialized = json.dumps(report)

    assert report["status"] == "FAIL"
    assert report["findings"][0]["kind"] == "github-token"
    assert token not in serialized


def test_history_flags_identity_and_bytecode_without_printing_email(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Anonymous Test")
    unsafe_email = "private" + "@" + "mail.invalid"
    _git(tmp_path, "config", "user.email", unsafe_email)
    cache = tmp_path / "scripts" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "sample.pyc").write_bytes(b"compiled")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "fixture")

    report = build_report(tmp_path, history=True)
    serialized = json.dumps(report)
    kinds = {finding["kind"] for finding in report["findings"]}

    assert {"non-noreply-identity", "python-bytecode"}.issubset(kinds)
    assert unsafe_email not in serialized
