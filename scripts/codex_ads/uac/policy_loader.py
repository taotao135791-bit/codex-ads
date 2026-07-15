"""Versioned, strict loading for calibratable UAC heuristic policies.

This module deliberately excludes product safety contracts such as permission
classes, live-write confirmation, privacy rules, AC terminology, and the hard
block on unreliable value optimization. Missing bundled defaults degrade to a
zero-change policy; malformed policy files always fail explicitly.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
import math
from pathlib import Path
import re
from typing import Any

from .io import _load
from .types import ContractError
from .workspace import Workspace


POLICY_SCHEMA_VERSION = "1.0"
POLICY_DIRECTORY = Path(__file__).with_name("policies")
POLICY_SCHEMA_PATH = POLICY_DIRECTORY / "uac-heuristic-policy.schema.json"

_POLICY_KINDS = ("uac_numeric", "uac_signal")
_KIND_ALIASES = {
    "numeric": "uac_numeric",
    "signal": "uac_signal",
    "uac_numeric": "uac_numeric",
    "uac_signal": "uac_signal",
}
_DEFAULT_FILENAMES = {
    "uac_numeric": "uac-numeric-policy-v1.yaml",
    "uac_signal": "uac-signal-policy-v1.yaml",
}
_OVERRIDE_FILENAMES = {
    "uac_numeric": "uac-numeric-policy.yaml",
    "uac_signal": "uac-signal-policy.yaml",
}
_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
_MAX_POLICY_BYTES = 1_000_000
_METADATA_KEYS = {
    "schema_version",
    "policy_version",
    "policy_kind",
    "policy_mode",
    "extends",
}
_NUMERIC_SECTIONS = {"numeric_change_limits", "staged_adjustment"}
_SIGNAL_SECTIONS = {
    "value_quality",
    "event_stability",
    "campaign_split",
    "creative_sample",
    "proxy_event_scoring_weights",
    "maturity_defaults",
}


@dataclass(frozen=True)
class LoadedPolicy:
    """One effective policy plus privacy-safe provenance metadata."""

    policy_kind: str
    policy_version: str
    sources: tuple[str, ...]
    source_versions: tuple[str, ...]
    degraded: bool = False
    warnings: tuple[str, ...] = ()
    _values: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def values(self) -> dict[str, Any]:
        """Return a defensive copy of the complete effective policy."""

        copied = deepcopy(self._values)
        assert isinstance(copied, dict)
        return copied

    def as_record(self) -> dict[str, Any]:
        """Return compact metadata suitable for analysis or Replay output."""

        return {
            "policy_kind": self.policy_kind,
            "policy_version": self.policy_version,
            "sources": list(self.sources),
            "source_versions": list(self.source_versions),
            "degraded": self.degraded,
            "warnings": list(self.warnings),
        }


def _canonical_kind(kind: str) -> str:
    if not isinstance(kind, str):
        raise ContractError("policy kind must be text")
    canonical = _KIND_ALIASES.get(kind.strip().lower())
    if canonical is None:
        raise ContractError(
            "policy kind must be numeric, signal, uac_numeric, or uac_signal"
        )
    return canonical


def _safe_degraded_policy(kind: str) -> dict[str, Any]:
    if kind == "uac_numeric":
        return {
            "schema_version": POLICY_SCHEMA_VERSION,
            "policy_version": "uac-numeric-policy-safe-degraded-v1",
            "policy_kind": kind,
            "policy_mode": "default",
            "numeric_change_limits": {
                variable: {
                    "normal_max_increase_percent": 0,
                    "normal_max_decrease_percent": 0,
                }
                for variable in ("target_cpa", "target_roas", "daily_budget")
            },
            "staged_adjustment": {
                "review_after_days": None,
                "minimum_mature_events": None,
            },
        }
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_version": "uac-signal-policy-safe-degraded-v1",
        "policy_kind": kind,
        "policy_mode": "default",
        "value_quality": {
            "difference_warning_percent": 0,
            "difference_blocking_percent": 0,
            "missing_value_warning_percent": 0,
            "missing_value_blocking_percent": 0,
            "currency_consistency_warning_min_percent": 100,
            "currency_consistency_blocking_min_percent": 100,
            "value_coefficient_of_variation_warning": 0,
        },
        "event_stability": {
            "minimum_daily_points": 365,
            "coefficient_of_variation_max": 0,
            "zero_event_days_max_percent": 0,
        },
        "campaign_split": {
            "default_minimum_daily_mature_events_per_campaign": None,
            "borderline_capacity_percent": 100,
        },
        "creative_sample": {"default_minimum_installs": None},
        "proxy_event_scoring_weights": {
            "volume_percent": 25,
            "payment_relationship_percent": 30,
            "delay_percent": 15,
            "reliability_percent": 15,
            "stability_percent": 10,
            "funnel_depth_percent": 5,
        },
        "maturity_defaults": {
            "minimum_days": None,
            "minimum_mature_events": None,
        },
    }


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{path} must be an object")
    return value


def _validate_keys(
    value: Mapping[str, Any],
    *,
    path: str,
    allowed: set[str],
    required: set[str] | None = None,
    non_empty: bool = False,
) -> None:
    unknown = sorted(str(key) for key in value if key not in allowed)
    if unknown:
        raise ContractError(f"{path} contains unsupported field: {unknown[0]}")
    missing = sorted((required or set()) - set(value))
    if missing:
        raise ContractError(f"{path}.{missing[0]} is required")
    if non_empty and not value:
        raise ContractError(f"{path} must contain at least one override")


def _validate_number(
    value: Any,
    path: str,
    *,
    minimum: float,
    maximum: float | None = None,
    integer: bool = False,
    allow_none: bool = False,
    exclusive_minimum: bool = False,
) -> None:
    if value is None and allow_none:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        expected = "integer" if integer else "number"
        raise ContractError(f"{path} must be a finite {expected}")
    try:
        finite = math.isfinite(float(value))
    except OverflowError:
        finite = False
    if not finite or (integer and not isinstance(value, int)):
        expected = "integer" if integer else "number"
        raise ContractError(f"{path} must be a finite {expected}")
    too_small = value <= minimum if exclusive_minimum else value < minimum
    if too_small:
        operator = "greater than" if exclusive_minimum else "at least"
        raise ContractError(f"{path} must be {operator} {minimum:g}")
    if maximum is not None and value > maximum:
        raise ContractError(f"{path} must not exceed {maximum:g}")


def _validate_percentage(value: Any, path: str, *, positive: bool = False) -> None:
    _validate_number(
        value,
        path,
        minimum=0,
        maximum=100,
        exclusive_minimum=positive,
    )


def _validate_change_limits(
    value: Any, *, full: bool, path: str = "numeric_change_limits"
) -> None:
    limits = _require_mapping(value, path)
    variables = {"target_cpa", "target_roas", "daily_budget"}
    _validate_keys(
        limits,
        path=path,
        allowed=variables,
        required=variables if full else None,
        non_empty=not full,
    )
    fields = {"normal_max_increase_percent", "normal_max_decrease_percent"}
    for variable, raw in limits.items():
        variable_path = f"{path}.{variable}"
        rule = _require_mapping(raw, variable_path)
        _validate_keys(
            rule,
            path=variable_path,
            allowed=fields,
            required=fields if full else None,
            non_empty=not full,
        )
        for name, percentage in rule.items():
            _validate_percentage(percentage, f"{variable_path}.{name}")


def _validate_staged(value: Any, *, full: bool) -> None:
    path = "staged_adjustment"
    staged = _require_mapping(value, path)
    fields = {"review_after_days", "minimum_mature_events"}
    _validate_keys(
        staged,
        path=path,
        allowed=fields,
        required=fields if full else None,
        non_empty=not full,
    )
    if "review_after_days" in staged:
        _validate_number(
            staged["review_after_days"],
            f"{path}.review_after_days",
            minimum=1,
            maximum=365,
            integer=True,
            allow_none=True,
        )
    if "minimum_mature_events" in staged:
        _validate_number(
            staged["minimum_mature_events"],
            f"{path}.minimum_mature_events",
            minimum=1,
            integer=True,
            allow_none=True,
        )


def _validate_value_quality(value: Any, *, full: bool) -> None:
    path = "value_quality"
    quality = _require_mapping(value, path)
    percentage_fields = {
        "difference_warning_percent",
        "difference_blocking_percent",
        "missing_value_warning_percent",
        "missing_value_blocking_percent",
        "currency_consistency_warning_min_percent",
        "currency_consistency_blocking_min_percent",
    }
    fields = percentage_fields | {"value_coefficient_of_variation_warning"}
    _validate_keys(
        quality,
        path=path,
        allowed=fields,
        required=fields if full else None,
        non_empty=not full,
    )
    for name in percentage_fields.intersection(quality):
        _validate_percentage(quality[name], f"{path}.{name}")
    if "value_coefficient_of_variation_warning" in quality:
        _validate_number(
            quality["value_coefficient_of_variation_warning"],
            f"{path}.value_coefficient_of_variation_warning",
            minimum=0,
            maximum=10,
        )
    if full:
        if (
            quality["difference_warning_percent"]
            > quality["difference_blocking_percent"]
        ):
            raise ContractError(
                "value_quality.difference_warning_percent must not exceed "
                "difference_blocking_percent"
            )
        if (
            quality["missing_value_warning_percent"]
            > quality["missing_value_blocking_percent"]
        ):
            raise ContractError(
                "value_quality.missing_value_warning_percent must not exceed "
                "missing_value_blocking_percent"
            )
        if (
            quality["currency_consistency_warning_min_percent"]
            < quality["currency_consistency_blocking_min_percent"]
        ):
            raise ContractError(
                "value_quality.currency_consistency_warning_min_percent must be "
                "at least currency_consistency_blocking_min_percent"
            )


def _validate_event_stability(value: Any, *, full: bool) -> None:
    path = "event_stability"
    stability = _require_mapping(value, path)
    fields = {
        "minimum_daily_points",
        "coefficient_of_variation_max",
        "zero_event_days_max_percent",
    }
    _validate_keys(
        stability,
        path=path,
        allowed=fields,
        required=fields if full else None,
        non_empty=not full,
    )
    if "minimum_daily_points" in stability:
        _validate_number(
            stability["minimum_daily_points"],
            f"{path}.minimum_daily_points",
            minimum=3,
            maximum=365,
            integer=True,
        )
    if "coefficient_of_variation_max" in stability:
        _validate_number(
            stability["coefficient_of_variation_max"],
            f"{path}.coefficient_of_variation_max",
            minimum=0,
            maximum=10,
        )
    if "zero_event_days_max_percent" in stability:
        _validate_percentage(
            stability["zero_event_days_max_percent"],
            f"{path}.zero_event_days_max_percent",
        )


def _validate_campaign_split(value: Any, *, full: bool) -> None:
    path = "campaign_split"
    split = _require_mapping(value, path)
    fields = {
        "default_minimum_daily_mature_events_per_campaign",
        "borderline_capacity_percent",
    }
    _validate_keys(
        split,
        path=path,
        allowed=fields,
        required=fields if full else None,
        non_empty=not full,
    )
    minimum_name = "default_minimum_daily_mature_events_per_campaign"
    if minimum_name in split:
        _validate_number(
            split[minimum_name],
            f"{path}.{minimum_name}",
            minimum=0,
            exclusive_minimum=True,
            allow_none=True,
        )
    if "borderline_capacity_percent" in split:
        _validate_percentage(
            split["borderline_capacity_percent"],
            f"{path}.borderline_capacity_percent",
        )


def _validate_creative_sample(value: Any, *, full: bool) -> None:
    path = "creative_sample"
    sample = _require_mapping(value, path)
    fields = {"default_minimum_installs"}
    _validate_keys(
        sample,
        path=path,
        allowed=fields,
        required=fields if full else None,
        non_empty=not full,
    )
    if "default_minimum_installs" in sample:
        _validate_number(
            sample["default_minimum_installs"],
            f"{path}.default_minimum_installs",
            minimum=1,
            integer=True,
            allow_none=True,
        )


def _validate_proxy_weights(value: Any, *, full: bool) -> None:
    path = "proxy_event_scoring_weights"
    weights = _require_mapping(value, path)
    fields = {
        "volume_percent",
        "payment_relationship_percent",
        "delay_percent",
        "reliability_percent",
        "stability_percent",
        "funnel_depth_percent",
    }
    _validate_keys(
        weights,
        path=path,
        allowed=fields,
        required=fields if full else None,
        non_empty=not full,
    )
    for name, percentage in weights.items():
        _validate_percentage(percentage, f"{path}.{name}")
    if full and not math.isclose(
        sum(float(weights[name]) for name in fields), 100.0, abs_tol=1e-9
    ):
        raise ContractError("proxy_event_scoring_weights must sum to 100 percent")


def _validate_maturity_defaults(value: Any, *, full: bool) -> None:
    path = "maturity_defaults"
    maturity = _require_mapping(value, path)
    fields = {"minimum_days", "minimum_mature_events"}
    _validate_keys(
        maturity,
        path=path,
        allowed=fields,
        required=fields if full else None,
        non_empty=not full,
    )
    if "minimum_days" in maturity:
        _validate_number(
            maturity["minimum_days"],
            f"{path}.minimum_days",
            minimum=1,
            maximum=365,
            integer=True,
            allow_none=True,
        )
    if "minimum_mature_events" in maturity:
        _validate_number(
            maturity["minimum_mature_events"],
            f"{path}.minimum_mature_events",
            minimum=1,
            integer=True,
            allow_none=True,
        )


def _validate_policy(
    value: Mapping[str, Any],
    *,
    kind: str,
    expected_mode: str | None,
    full: bool,
) -> None:
    sections = _NUMERIC_SECTIONS if kind == "uac_numeric" else _SIGNAL_SECTIONS
    _validate_keys(
        value,
        path="policy",
        allowed=_METADATA_KEYS | sections,
        required={"schema_version", "policy_version", "policy_kind", "policy_mode"},
    )
    if value.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ContractError("policy.schema_version must be 1.0")
    version = value.get("policy_version")
    if not isinstance(version, str) or _VERSION_PATTERN.fullmatch(version) is None:
        raise ContractError(
            "policy.policy_version must use lowercase letters, digits, dots, underscores, or hyphens"
        )
    if value.get("policy_kind") != kind:
        raise ContractError(f"policy.policy_kind must be {kind}")
    mode = value.get("policy_mode")
    if mode not in {"default", "override"}:
        raise ContractError("policy.policy_mode must be default or override")
    if expected_mode is not None and mode != expected_mode:
        raise ContractError(f"policy.policy_mode must be {expected_mode}")
    extends = value.get("extends")
    if mode == "override":
        if not isinstance(extends, str) or _VERSION_PATTERN.fullmatch(extends) is None:
            raise ContractError("policy.extends is required for an override")
    elif "extends" in value:
        raise ContractError("policy.extends is only valid for an override")
    present_sections = sections.intersection(value)
    if full and present_sections != sections:
        missing = sorted(sections - present_sections)[0]
        raise ContractError(f"policy.{missing} is required")
    if mode == "override" and not present_sections:
        raise ContractError(
            "policy override must contain at least one heuristic section"
        )

    if kind == "uac_numeric":
        if "numeric_change_limits" in value:
            _validate_change_limits(value["numeric_change_limits"], full=full)
        if "staged_adjustment" in value:
            _validate_staged(value["staged_adjustment"], full=full)
        return

    if "value_quality" in value:
        _validate_value_quality(value["value_quality"], full=full)
    if "event_stability" in value:
        _validate_event_stability(value["event_stability"], full=full)
    if "campaign_split" in value:
        _validate_campaign_split(value["campaign_split"], full=full)
    if "creative_sample" in value:
        _validate_creative_sample(value["creative_sample"], full=full)
    if "proxy_event_scoring_weights" in value:
        _validate_proxy_weights(value["proxy_event_scoring_weights"], full=full)
    if "maturity_defaults" in value:
        _validate_maturity_defaults(value["maturity_defaults"], full=full)


def _load_policy_file(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink():
        raise ContractError(f"{label} policy must not be a symbolic link")
    if not path.is_file():
        raise ContractError(f"{label} policy must be a regular file")
    try:
        if path.stat().st_size > _MAX_POLICY_BYTES:
            raise ContractError(f"{label} policy is larger than 1 MB")
        return _load(path)
    except ContractError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise ContractError(f"unable to load {label} policy file {path.name}") from exc


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(base))
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _project_override(root: Path, kind: str) -> Path | None:
    expanded = root.expanduser()
    if expanded.is_symlink():
        raise ContractError("project policy root must not be a symbolic link")
    if not expanded.is_dir():
        raise ContractError("project policy root must be an existing directory")
    policy_dir = expanded / "policies"
    if policy_dir.is_symlink():
        raise ContractError("project policies directory must not be a symbolic link")
    candidate = policy_dir / _OVERRIDE_FILENAMES[kind]
    if candidate.is_symlink():
        raise ContractError("project policy must not be a symbolic link")
    if candidate.exists() and not candidate.is_file():
        raise ContractError("project policy must be a regular file")
    return candidate.resolve() if candidate.is_file() else None


def _workspace_override(
    workspace: Workspace | Path, kind: str
) -> tuple[Workspace, Path | None]:
    selected = (
        workspace if isinstance(workspace, Workspace) else Workspace.at(workspace)
    )
    selected.require_initialized()
    candidate = selected.require_contained_path(
        selected.root / "policies" / _OVERRIDE_FILENAMES[kind],
        "workspace policy",
    )
    if candidate.exists() and not candidate.is_file():
        raise ContractError("workspace policy must be a regular file")
    return selected, candidate if candidate.is_file() else None


def load_policy(
    kind: str,
    *,
    project_root: Path | None = None,
    workspace: Workspace | Path | None = None,
    default_policy_path: Path | None = None,
) -> LoadedPolicy:
    """Load default < project < Workspace heuristic policy precedence.

    Missing optional overrides preserve the default. A missing bundled default
    returns a marked, zero-change safe policy. Existing but invalid files raise
    :class:`ContractError` and are never ignored.
    """

    canonical = _canonical_kind(kind)
    bundled_path = POLICY_DIRECTORY / _DEFAULT_FILENAMES[canonical]
    default_path = default_policy_path or bundled_path
    sources: list[str] = []
    source_versions: list[str] = []
    warnings: list[str] = []
    degraded = False

    if default_path.is_file() and not default_path.is_symlink():
        effective = _load_policy_file(default_path, label="default")
        _validate_policy(
            effective,
            kind=canonical,
            expected_mode="default",
            full=True,
        )
        sources.append(
            "bundled_default" if default_path == bundled_path else "explicit_default"
        )
    elif default_path.exists() or default_path.is_symlink():
        raise ContractError("default policy must be a regular non-symbolic file")
    else:
        effective = _safe_degraded_policy(canonical)
        _validate_policy(
            effective,
            kind=canonical,
            expected_mode="default",
            full=True,
        )
        sources.append("builtin_safe_default")
        degraded = True
        warnings.append("bundled_default_missing_using_zero_change_safe_policy")
    source_versions.append(str(effective["policy_version"]))

    override_candidates: list[tuple[str, Path]] = []
    if project_root is not None:
        project_path = _project_override(project_root, canonical)
        if project_path is not None:
            override_candidates.append(("project_override", project_path))
    if workspace is not None:
        _, workspace_path = _workspace_override(workspace, canonical)
        if workspace_path is not None:
            override_candidates.append(("workspace_override", workspace_path))

    seen_paths: set[Path] = set()
    for source, path in override_candidates:
        resolved = path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        override = _load_policy_file(resolved, label=source.replace("_", " "))
        _validate_policy(
            override,
            kind=canonical,
            expected_mode="override",
            full=False,
        )
        current_version = str(effective["policy_version"])
        if override.get("extends") != current_version:
            raise ContractError(f"{source} policy.extends must match {current_version}")
        next_version = str(override["policy_version"])
        if next_version in source_versions:
            raise ContractError(f"{source} policy_version must be new")
        effective = _deep_merge(effective, override)
        _validate_policy(
            effective,
            kind=canonical,
            expected_mode=None,
            full=True,
        )
        sources.append(source)
        source_versions.append(next_version)

    return LoadedPolicy(
        policy_kind=canonical,
        policy_version=str(effective["policy_version"]),
        sources=tuple(sources),
        source_versions=tuple(source_versions),
        degraded=degraded,
        warnings=tuple(warnings),
        _values=effective,
    )


def load_policy_set(
    *,
    project_root: Path | None = None,
    workspace: Workspace | Path | None = None,
    default_policy_dir: Path | None = None,
) -> dict[str, LoadedPolicy]:
    """Load both effective UAC heuristic policies with identical precedence."""

    result: dict[str, LoadedPolicy] = {}
    for kind in _POLICY_KINDS:
        default_path = (
            default_policy_dir / _DEFAULT_FILENAMES[kind]
            if default_policy_dir is not None
            else None
        )
        result[kind] = load_policy(
            kind,
            project_root=project_root,
            workspace=workspace,
            default_policy_path=default_path,
        )
    return result


__all__ = [
    "LoadedPolicy",
    "POLICY_DIRECTORY",
    "POLICY_SCHEMA_PATH",
    "POLICY_SCHEMA_VERSION",
    "load_policy",
    "load_policy_set",
]
