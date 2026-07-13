"""Explicit ledger-schema migration and backward-compatibility tests."""

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

from codex_ads.uac.ledger import (  # noqa: E402
    _append_proposal,
    _append_to_ledger_path,
    _cancel_proposal_path,
    _ledger_context,
)
from uac_experiment import (  # noqa: E402
    ANALYSIS_SCHEMA_VERSION,
    CURRENT_LEDGER_SCHEMA_VERSION,
    SUPPORTED_LEDGER_SCHEMA_VERSIONS,
    ContractError,
    analyze_case,
    migrate_ledger,
    validate_ledger,
)


@pytest.fixture
def uac_assets(repo_root) -> Path:
    return repo_root / "skills" / "ads-google-app" / "assets"


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _legacy_ledger(
    uac_assets: Path, name: str = "ADS-EXPERIMENTS.example.yaml"
) -> dict:
    ledger = _yaml(uac_assets / name)
    ledger["schema_version"] = "1.0"
    return ledger


def _analysis(uac_assets: Path) -> dict:
    return analyze_case(_yaml(uac_assets / "UAC-INPUT.example.yaml"))


def test_schema_version_constants_keep_analysis_and_ledger_versions_separate():
    assert ANALYSIS_SCHEMA_VERSION == "1.0"
    assert CURRENT_LEDGER_SCHEMA_VERSION == "1.1"
    assert SUPPORTED_LEDGER_SCHEMA_VERSIONS == frozenset({"1.0", "1.1"})


def test_migrate_ledger_is_lossless_pure_and_idempotent(uac_assets):
    source = _legacy_ledger(uac_assets)
    original = deepcopy(source)
    expected = deepcopy(source)
    expected["schema_version"] = CURRENT_LEDGER_SCHEMA_VERSION

    migrated = migrate_ledger(source)
    migrated_again = migrate_ledger(migrated)

    assert source == original
    assert migrated == expected
    assert migrated is not source
    assert migrated["experiments"] is not source["experiments"]
    assert migrated_again == migrated
    assert migrated_again is not migrated


def test_validate_and_migrate_reject_unknown_ledger_versions():
    unknown = {"schema_version": "9.9", "experiments": []}

    assert validate_ledger(unknown) == ["schema_version must be one of: 1.0, 1.1"]
    with pytest.raises(ContractError, match="schema_version must be one of"):
        migrate_ledger(unknown)


def test_legacy_ledger_remains_readable_and_analysis_output_stays_v1(
    uac_assets,
):
    legacy = _legacy_ledger(uac_assets, "ADS-EXPERIMENTS.minimal.yaml")

    assert validate_ledger(legacy) == []
    result = analyze_case(_yaml(uac_assets / "UAC-INPUT.example.yaml"), legacy)

    assert result["schema_version"] == ANALYSIS_SCHEMA_VERSION == "1.0"
    assert legacy["schema_version"] == "1.0"


def test_append_review_and_cancel_do_not_implicitly_upgrade_legacy_ledgers(
    uac_assets,
    tmp_path,
):
    proposal_result = _analysis(uac_assets)
    legacy = {"schema_version": "1.0", "experiments": []}

    appended = _append_proposal(legacy, proposal_result)
    assert legacy == {"schema_version": "1.0", "experiments": []}
    assert appended["schema_version"] == "1.0"

    before_review = deepcopy(appended)
    reviews, _ = _ledger_context(appended)
    assert reviews[0]["status"] == "PROPOSED_NOT_EXECUTED"
    assert appended == before_review

    ledger_path = tmp_path / "legacy-ledger.yaml"
    ledger_path.write_text(
        yaml.safe_dump(appended, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _cancel_proposal_path(
        ledger_path,
        appended["experiments"][0]["id"],
        "Proposal declined.",
        "Wait for new evidence.",
    )
    cancelled = _yaml(ledger_path)
    assert cancelled["schema_version"] == "1.0"
    assert cancelled["experiments"][0]["status"] == "cancelled"


def test_newly_created_ledger_uses_current_schema(uac_assets, tmp_path):
    ledger_path = tmp_path / "new-ledger.yaml"

    _append_to_ledger_path(ledger_path, _analysis(uac_assets))

    assert _yaml(ledger_path)["schema_version"] == CURRENT_LEDGER_SCHEMA_VERSION


def test_current_and_archived_schemas_validate_their_versions(uac_assets):
    jsonschema = pytest.importorskip("jsonschema")
    current_schema = json.loads(
        (uac_assets / "ads-experiments.schema.json").read_text(encoding="utf-8")
    )
    legacy_schema = json.loads(
        (uac_assets / "ads-experiments-v1.0.schema.json").read_text(encoding="utf-8")
    )

    for name in (
        "ADS-EXPERIMENTS.minimal.yaml",
        "ADS-EXPERIMENTS.full.yaml",
        "ADS-EXPERIMENTS.example.yaml",
    ):
        current = _yaml(uac_assets / name)
        assert current["schema_version"] == "1.1"
        jsonschema.Draft202012Validator(current_schema).validate(current)

    legacy = _legacy_ledger(uac_assets)
    jsonschema.Draft202012Validator(legacy_schema).validate(legacy)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(current_schema).validate(legacy)


@pytest.mark.parametrize(
    ("section", "field", "expected_error"),
    [
        ("result", "confounders", "result.confounders is required"),
        ("result", "evidence_quality", "result.evidence_quality is required"),
        ("decision", "next_action", "decision.next_action is required"),
    ],
)
def test_runtime_and_json_schema_agree_on_required_ledger_fields(
    uac_assets, section, field, expected_error
):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (uac_assets / "ads-experiments.schema.json").read_text(encoding="utf-8")
    )
    ledger = _yaml(uac_assets / "ADS-EXPERIMENTS.example.yaml")
    del ledger["experiments"][0][section][field]

    errors = validate_ledger(ledger)

    assert any(expected_error in error for error in errors)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(ledger)


def test_unexecuted_timestamp_and_nullable_rule_evaluation_match_both_schemas(
    uac_assets,
):
    jsonschema = pytest.importorskip("jsonschema")
    current_schema = json.loads(
        (uac_assets / "ads-experiments.schema.json").read_text(encoding="utf-8")
    )
    legacy_schema = json.loads(
        (uac_assets / "ads-experiments-v1.0.schema.json").read_text(encoding="utf-8")
    )
    experiment = _analysis(uac_assets)["experiments"][0]
    experiment["result"]["rule_evaluation"] = None
    legacy = {"schema_version": "1.0", "experiments": [experiment]}

    assert validate_ledger(legacy) == []
    jsonschema.Draft202012Validator(legacy_schema).validate(legacy)
    migrated = migrate_ledger(legacy)
    jsonschema.Draft202012Validator(current_schema).validate(migrated)

    legacy["experiments"][0]["execution"]["executed_at"] = ""
    assert any(
        "unapproved and unexecuted" in error for error in validate_ledger(legacy)
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(legacy_schema).validate(legacy)
    with pytest.raises(ContractError):
        migrate_ledger(legacy)


def test_migrate_cli_previews_without_mutating_and_supports_output(
    repo_root,
    uac_assets,
    tmp_path,
):
    script = repo_root / "scripts" / "uac_experiment.py"
    source = tmp_path / "legacy.yaml"
    source.write_text(
        yaml.safe_dump(_legacy_ledger(uac_assets), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    original = source.read_text(encoding="utf-8")

    preview = subprocess.run(
        [sys.executable, str(script), "migrate-ledger", str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert preview.returncode == 0, preview.stderr
    assert json.loads(preview.stdout)["schema_version"] == "1.1"
    assert source.read_text(encoding="utf-8") == original

    output = tmp_path / "migrated.yaml"
    written = subprocess.run(
        [
            sys.executable,
            str(script),
            "migrate-ledger",
            str(source),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert written.returncode == 0, written.stderr
    assert _yaml(output)["schema_version"] == "1.1"
    assert source.read_text(encoding="utf-8") == original


def test_migrate_cli_requires_write_for_source_overwrite_and_rejects_unknown(
    repo_root,
    uac_assets,
    tmp_path,
):
    script = repo_root / "scripts" / "uac_experiment.py"
    source = tmp_path / "legacy.yaml"
    source.write_text(
        yaml.safe_dump(_legacy_ledger(uac_assets), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    original = source.read_text(encoding="utf-8")

    collision = subprocess.run(
        [
            sys.executable,
            str(script),
            "migrate-ledger",
            str(source),
            "--output",
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert collision.returncode == 2
    assert "use --write" in collision.stderr
    assert source.read_text(encoding="utf-8") == original

    written = subprocess.run(
        [
            sys.executable,
            str(script),
            "migrate-ledger",
            str(source),
            "--write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert written.returncode == 0, written.stderr
    assert _yaml(source)["schema_version"] == "1.1"

    unknown = tmp_path / "unknown.json"
    unknown.write_text(
        json.dumps({"schema_version": "9.9", "experiments": []}),
        encoding="utf-8",
    )
    unknown_before = unknown.read_text(encoding="utf-8")
    rejected = subprocess.run(
        [
            sys.executable,
            str(script),
            "migrate-ledger",
            str(unknown),
            "--write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 2
    assert "schema_version must be one of" in rejected.stderr
    assert "Traceback" not in rejected.stderr
    assert unknown.read_text(encoding="utf-8") == unknown_before


def test_migrate_write_respects_the_shared_ledger_lock(repo_root, uac_assets, tmp_path):
    script = repo_root / "scripts" / "uac_experiment.py"
    source = tmp_path / "legacy.yaml"
    source.write_text(
        yaml.safe_dump(_legacy_ledger(uac_assets), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    original = source.read_text(encoding="utf-8")
    lock = source.with_name(f".{source.name}.lock")
    lock.write_text("occupied", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "migrate-ledger",
            str(source),
            "--write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "ledger is locked" in completed.stderr
    assert source.read_text(encoding="utf-8") == original
    assert lock.read_text(encoding="utf-8") == "occupied"
