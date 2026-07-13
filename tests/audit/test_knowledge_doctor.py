"""Tests for advisory and strict knowledge freshness checks."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from knowledge_doctor import (  # noqa: E402
    evaluate_metadata,
    exit_code,
    load_metadata,
)


def _metadata(*, verified_on: str | None, path: str = "knowledge.md") -> dict:
    return {
        "schema_version": "1.0",
        "policy": {"default_review_after_days": 30, "advisory_by_default": True},
        "required_topics": ["google_uac"],
        "entries": [
            {
                "id": "google-uac",
                "topic": "google_uac",
                "paths": [path],
                "source_type": "official_platform_documentation",
                "source_reference": "Authoritative source to verify",
                "rule_type": "platform_guidance",
                "confidence": "medium",
                "verified_on": verified_on,
                "review_after_days": 30,
            }
        ],
    }


def test_fresh_and_stale_results_are_frozen_to_as_of(tmp_path: Path) -> None:
    (tmp_path / "knowledge.md").write_text("facts\n", encoding="utf-8")
    metadata = _metadata(verified_on="2026-01-01")

    fresh = evaluate_metadata(metadata, repo_root=tmp_path, as_of=date(2026, 1, 20))
    stale = evaluate_metadata(metadata, repo_root=tmp_path, as_of=date(2026, 2, 15))

    assert fresh["status"] == "PASS"
    assert fresh["checks"][0]["age_days"] == 19
    assert stale["status"] == "WARN"
    assert stale["checks"][0]["age_days"] == 45


def test_unverified_warning_is_advisory_unless_strict(tmp_path: Path) -> None:
    (tmp_path / "knowledge.md").write_text("facts\n", encoding="utf-8")
    report = evaluate_metadata(
        _metadata(verified_on=None), repo_root=tmp_path, as_of=date(2026, 7, 13)
    )

    assert report["status"] == "WARN"
    assert exit_code(report, strict=False) == 0
    assert exit_code(report, strict=True) == 1


def test_missing_repository_path_is_a_structural_failure(tmp_path: Path) -> None:
    report = evaluate_metadata(
        _metadata(verified_on="2026-07-01", path="missing.md"),
        repo_root=tmp_path,
        as_of=date(2026, 7, 13),
    )

    assert report["status"] == "FAIL"
    assert "missing repository file" in report["checks"][0]["reason"]
    assert exit_code(report, strict=False) == 2


def test_repository_metadata_covers_priority_topics_without_claiming_verification(
    repo_root: Path,
) -> None:
    metadata = load_metadata(repo_root / "knowledge" / "metadata.yaml")
    report = evaluate_metadata(metadata, repo_root=repo_root, as_of=date(2026, 7, 13))

    assert set(metadata["required_topics"]) == {
        "google_uac",
        "meta",
        "tiktok",
        "policy",
        "platform_specs",
        "attribution",
        "budget",
    }
    assert report["status"] == "WARN"
    assert report["summary"]["fail"] == 0
    assert report["summary"]["warn"] >= 8
    assert all(entry["verified_on"] is None for entry in metadata["entries"])
    assert {entry["rule_type"] for entry in metadata["entries"]} >= {
        "platform_guidance",
        "policy",
        "heuristic",
    }
    assert report["link_check"]["status"] == "NOT_RUN"


def test_missing_rule_type_and_confidence_fail_structurally(tmp_path: Path) -> None:
    (tmp_path / "knowledge.md").write_text("facts\n", encoding="utf-8")
    metadata = _metadata(verified_on="2026-07-01")
    del metadata["entries"][0]["rule_type"]
    del metadata["entries"][0]["confidence"]

    report = evaluate_metadata(metadata, repo_root=tmp_path, as_of=date(2026, 7, 13))

    assert report["status"] == "FAIL"
    assert "rule_type" in report["checks"][0]["reason"]
    assert "confidence" in report["checks"][0]["reason"]


def test_absolute_heuristic_language_is_flagged_without_quoting_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "knowledge.md").write_text(
        "You must always scale this rule.\n", encoding="utf-8"
    )
    metadata = _metadata(verified_on="2026-07-01")
    metadata["entries"][0]["rule_type"] = "heuristic"

    report = evaluate_metadata(metadata, repo_root=tmp_path, as_of=date(2026, 7, 13))

    assert report["status"] == "WARN"
    warning = next(
        check for check in report["checks"] if check["id"].endswith("absolute-language")
    )
    assert "human review" in warning["reason"]
    assert "always" not in warning["reason"]


def test_json_cli_is_reproducible_and_does_not_emit_absolute_repo_path(
    repo_root: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "knowledge_doctor.py"),
            "--json",
            "--as-of",
            "2026-07-13",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["status"] == "WARN"
    assert str(repo_root) not in completed.stdout
