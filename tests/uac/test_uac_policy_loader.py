"""Versioned UAC heuristic-policy loading and validation."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from codex_ads.uac.policy_loader import (  # noqa: E402
    POLICY_DIRECTORY,
    POLICY_SCHEMA_PATH,
    load_policy,
    load_policy_set,
)
from codex_ads.uac.types import ContractError  # noqa: E402
from codex_ads.uac.workspace import initialize_workspace  # noqa: E402


_NUMERIC_OVERRIDE_NAME = "uac-numeric-policy.yaml"
_SIGNAL_OVERRIDE_NAME = "uac-signal-policy.yaml"


def _write_yaml(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _override(
    *,
    kind: str,
    version: str,
    extends: str,
    section: str,
    values: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "policy_version": version,
        "policy_kind": kind,
        "policy_mode": "override",
        "extends": extends,
        section: values,
    }


def _bundled(name: str) -> dict[str, object]:
    loaded = yaml.safe_load((POLICY_DIRECTORY / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_bundled_defaults_and_aliases_load_with_versions() -> None:
    numeric = load_policy("numeric")
    signal = load_policy("uac_signal")

    assert numeric.policy_kind == "uac_numeric"
    assert numeric.policy_version == "uac-numeric-policy-v1"
    assert numeric.sources == ("bundled_default",)
    assert numeric.source_versions == ("uac-numeric-policy-v1",)
    assert numeric.degraded is False
    assert numeric.warnings == ()
    assert numeric.values["numeric_change_limits"]["daily_budget"] == {
        "normal_max_increase_percent": 20,
        "normal_max_decrease_percent": 20,
    }

    assert signal.policy_kind == "uac_signal"
    assert signal.policy_version == "uac-signal-policy-v1"
    assert sum(signal.values["proxy_event_scoring_weights"].values()) == 100


def test_load_policy_set_returns_both_canonical_kinds() -> None:
    policies = load_policy_set()

    assert set(policies) == {"uac_numeric", "uac_signal"}
    assert policies["uac_numeric"].policy_version == "uac-numeric-policy-v1"
    assert policies["uac_signal"].policy_version == "uac-signal-policy-v1"


def test_formal_schema_accepts_bundled_defaults_and_partial_override() -> None:
    schema = json.loads(POLICY_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    override = _override(
        kind="uac_numeric",
        version="project-numeric-v2",
        extends="uac-numeric-policy-v1",
        section="numeric_change_limits",
        values={"target_cpa": {"normal_max_increase_percent": 12}},
    )

    for document in (
        _bundled("uac-numeric-policy-v1.yaml"),
        _bundled("uac-signal-policy-v1.yaml"),
        override,
    ):
        Draft202012Validator.check_schema(schema)
        assert list(validator.iter_errors(document)) == []

    empty_override = {
        "schema_version": "1.0",
        "policy_version": "empty-numeric-v2",
        "policy_kind": "uac_numeric",
        "policy_mode": "override",
        "extends": "uac-numeric-policy-v1",
    }
    assert validator.is_valid(empty_override) is False
    assert (
        validator.is_valid(
            {
                **override,
                "human_confirmation_required_for_live_write": False,
            }
        )
        is False
    )


def test_project_partial_override_merges_and_records_provenance(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_yaml(
        project / "policies" / _NUMERIC_OVERRIDE_NAME,
        _override(
            kind="uac_numeric",
            version="project-numeric-v2",
            extends="uac-numeric-policy-v1",
            section="numeric_change_limits",
            values={"target_cpa": {"normal_max_increase_percent": 12}},
        ),
    )

    policy = load_policy("numeric", project_root=project)

    assert policy.policy_version == "project-numeric-v2"
    assert policy.sources == ("bundled_default", "project_override")
    assert policy.source_versions == (
        "uac-numeric-policy-v1",
        "project-numeric-v2",
    )
    assert policy.values["numeric_change_limits"]["target_cpa"] == {
        "normal_max_increase_percent": 12,
        "normal_max_decrease_percent": 20,
    }
    assert policy.as_record() == {
        "policy_kind": "uac_numeric",
        "policy_version": "project-numeric-v2",
        "sources": ["bundled_default", "project_override"],
        "source_versions": ["uac-numeric-policy-v1", "project-numeric-v2"],
        "degraded": False,
        "warnings": [],
    }


def test_workspace_override_wins_after_project_override(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_yaml(
        project / "policies" / _NUMERIC_OVERRIDE_NAME,
        _override(
            kind="uac_numeric",
            version="project-numeric-v2",
            extends="uac-numeric-policy-v1",
            section="numeric_change_limits",
            values={"daily_budget": {"normal_max_increase_percent": 15}},
        ),
    )
    workspace = initialize_workspace("account", base_dir=tmp_path / "workspaces")
    _write_yaml(
        workspace.root / "policies" / _NUMERIC_OVERRIDE_NAME,
        _override(
            kind="uac_numeric",
            version="workspace-numeric-v3",
            extends="project-numeric-v2",
            section="numeric_change_limits",
            values={"daily_budget": {"normal_max_increase_percent": 9}},
        ),
    )

    policy = load_policy("uac_numeric", project_root=project, workspace=workspace.root)

    assert policy.policy_version == "workspace-numeric-v3"
    assert policy.sources == (
        "bundled_default",
        "project_override",
        "workspace_override",
    )
    assert policy.values["numeric_change_limits"]["daily_budget"] == {
        "normal_max_increase_percent": 9,
        "normal_max_decrease_percent": 20,
    }


def test_workspace_without_policies_remains_backward_compatible(tmp_path: Path) -> None:
    workspace = initialize_workspace("legacy", base_dir=tmp_path)

    policy = load_policy("signal", workspace=workspace)

    assert workspace.initialized
    assert not (workspace.root / "policies").exists()
    assert policy.policy_version == "uac-signal-policy-v1"
    assert policy.sources == ("bundled_default",)
    assert policy.degraded is False


def test_missing_default_degrades_to_marked_zero_change_policy(tmp_path: Path) -> None:
    policy = load_policy(
        "numeric", default_policy_path=tmp_path / "missing-policy.yaml"
    )

    assert policy.policy_version == "uac-numeric-policy-safe-degraded-v1"
    assert policy.sources == ("builtin_safe_default",)
    assert policy.degraded is True
    assert policy.warnings == ("bundled_default_missing_using_zero_change_safe_policy",)
    for limits in policy.values["numeric_change_limits"].values():
        assert limits == {
            "normal_max_increase_percent": 0,
            "normal_max_decrease_percent": 0,
        }


@pytest.mark.parametrize("percentage", [-0.01, 100.01])
def test_override_rejects_negative_and_too_large_percentages(
    tmp_path: Path, percentage: float
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_yaml(
        project / "policies" / _NUMERIC_OVERRIDE_NAME,
        _override(
            kind="uac_numeric",
            version="invalid-numeric-v2",
            extends="uac-numeric-policy-v1",
            section="numeric_change_limits",
            values={"daily_budget": {"normal_max_increase_percent": percentage}},
        ),
    )

    with pytest.raises(ContractError, match="normal_max_increase_percent"):
        load_policy("numeric", project_root=project)


def test_percentage_rejects_boolean_even_though_bool_is_an_int(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_yaml(
        project / "policies" / _SIGNAL_OVERRIDE_NAME,
        _override(
            kind="uac_signal",
            version="invalid-signal-v2",
            extends="uac-signal-policy-v1",
            section="event_stability",
            values={"zero_event_days_max_percent": True},
        ),
    )

    with pytest.raises(ContractError, match="zero_event_days_max_percent"):
        load_policy("signal", project_root=project)


def test_merged_signal_thresholds_must_preserve_warning_block_order(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_yaml(
        project / "policies" / _SIGNAL_OVERRIDE_NAME,
        _override(
            kind="uac_signal",
            version="invalid-signal-v2",
            extends="uac-signal-policy-v1",
            section="value_quality",
            values={"difference_warning_percent": 21},
        ),
    )

    with pytest.raises(ContractError, match="difference_warning_percent"):
        load_policy("signal", project_root=project)


def test_merged_proxy_weights_must_still_sum_to_one_hundred(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_yaml(
        project / "policies" / _SIGNAL_OVERRIDE_NAME,
        _override(
            kind="uac_signal",
            version="invalid-signal-v2",
            extends="uac-signal-policy-v1",
            section="proxy_event_scoring_weights",
            values={"volume_percent": 26},
        ),
    )

    with pytest.raises(ContractError, match="must sum to 100"):
        load_policy("signal", project_root=project)


def test_product_safety_contracts_cannot_be_added_to_policy(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    policy = _override(
        kind="uac_numeric",
        version="unsafe-numeric-v2",
        extends="uac-numeric-policy-v1",
        section="staged_adjustment",
        values={"review_after_days": 4},
    )
    policy["human_confirmation_required_for_live_write"] = False
    _write_yaml(project / "policies" / _NUMERIC_OVERRIDE_NAME, policy)

    with pytest.raises(
        ContractError, match="human_confirmation_required_for_live_write"
    ):
        load_policy("numeric", project_root=project)


def test_override_must_extend_exact_effective_version(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_yaml(
        project / "policies" / _NUMERIC_OVERRIDE_NAME,
        _override(
            kind="uac_numeric",
            version="project-numeric-v2",
            extends="some-other-policy-v1",
            section="staged_adjustment",
            values={"review_after_days": 4},
        ),
    )

    with pytest.raises(ContractError, match="must match uac-numeric-policy-v1"):
        load_policy("numeric", project_root=project)


def test_existing_invalid_default_fails_instead_of_degrading(tmp_path: Path) -> None:
    invalid_default = deepcopy(_bundled("uac-numeric-policy-v1.yaml"))
    limits = invalid_default["numeric_change_limits"]
    assert isinstance(limits, dict)
    budget = limits["daily_budget"]
    assert isinstance(budget, dict)
    budget["normal_max_decrease_percent"] = -1
    path = tmp_path / "invalid-default.yaml"
    _write_yaml(path, invalid_default)

    with pytest.raises(ContractError, match="normal_max_decrease_percent"):
        load_policy("numeric", default_policy_path=path)


def test_project_policy_symlink_is_rejected(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symbolic links are unavailable")
    project = tmp_path / "project"
    policies = project / "policies"
    policies.mkdir(parents=True)
    external = tmp_path / "external.yaml"
    _write_yaml(
        external,
        _override(
            kind="uac_numeric",
            version="linked-numeric-v2",
            extends="uac-numeric-policy-v1",
            section="staged_adjustment",
            values={"review_after_days": 4},
        ),
    )
    (policies / _NUMERIC_OVERRIDE_NAME).symlink_to(external)

    with pytest.raises(ContractError, match="symbolic link"):
        load_policy("numeric", project_root=project)


def test_loaded_values_are_defensive_copies() -> None:
    policy = load_policy("numeric")
    first = policy.values
    first["numeric_change_limits"]["target_cpa"]["normal_max_increase_percent"] = 99

    assert (
        policy.values["numeric_change_limits"]["target_cpa"][
            "normal_max_increase_percent"
        ]
        == 20
    )
