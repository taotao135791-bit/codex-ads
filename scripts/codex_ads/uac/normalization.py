"""Lightweight, decision-free normalization for operator-provided UAC facts."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .io import _load
from .models import NormalizationIssue, NormalizationResult, NormalizationSource
from .types import ContractError


_STRUCTURED_KEYS = {
    "scope",
    "goal",
    "facts",
    "measurement",
    "learning",
    "maturity",
    "permissions",
    "signals",
    "evidence",
    "experiment_policy",
    "next_review",
    "active_experiment",
    "campaign_level_glossary",
    "quick_ops",
}

_ALIASES: dict[str, tuple[str, str]] = {
    "spend": ("facts.metrics.spend", "non_negative_number"),
    "cost": ("facts.metrics.spend", "non_negative_number"),
    "花费": ("facts.metrics.spend", "non_negative_number"),
    "installs": ("facts.metrics.installs", "non_negative_number"),
    "install": ("facts.metrics.installs", "non_negative_number"),
    "安装": ("facts.metrics.installs", "non_negative_number"),
    "registrations": ("facts.metrics.registrations", "non_negative_number"),
    "registration": ("facts.metrics.registrations", "non_negative_number"),
    "注册": ("facts.metrics.registrations", "non_negative_number"),
    "payments": ("facts.metrics.payments", "non_negative_number"),
    "payment": ("facts.metrics.payments", "non_negative_number"),
    "支付": ("facts.metrics.payments", "non_negative_number"),
    "revenue": ("facts.metrics.revenue", "non_negative_number"),
    "value": ("facts.metrics.revenue", "non_negative_number"),
    "收入": ("facts.metrics.revenue", "non_negative_number"),
    "budget": ("facts.daily_budget", "non_negative_number"),
    "daily_budget": ("facts.daily_budget", "non_negative_number"),
    "日预算": ("facts.daily_budget", "non_negative_number"),
    "tcpa": ("goal.target_cpa", "non_negative_number"),
    "target_cpa": ("goal.target_cpa", "non_negative_number"),
    "目标单次转化费用": ("goal.target_cpa", "non_negative_number"),
    "troas": ("goal.target_roas", "roas"),
    "target_roas": ("goal.target_roas", "roas"),
    "目标广告支出回报率": ("goal.target_roas", "roas"),
    "maximum_acceptable_cpa": (
        "goal.maximum_acceptable_cpa",
        "non_negative_number",
    ),
    "max_acceptable_cpa": ("goal.maximum_acceptable_cpa", "non_negative_number"),
    "业务_cpa_上限": ("goal.maximum_acceptable_cpa", "non_negative_number"),
    "minimum_acceptable_roas": ("goal.minimum_acceptable_roas", "roas"),
    "min_acceptable_roas": ("goal.minimum_acceptable_roas", "roas"),
    "业务_roas_下限": ("goal.minimum_acceptable_roas", "roas"),
    "daily_budget_cap": ("goal.daily_budget_cap", "non_negative_number"),
    "日预算上限": ("goal.daily_budget_cap", "non_negative_number"),
    "optimization_priority": ("goal.optimization_priority", "text"),
    "优化优先级": ("goal.optimization_priority", "text"),
    "bidding_strategy": ("goal.bidding_strategy", "text"),
    "出价策略": ("goal.bidding_strategy", "text"),
    "mature_actual_cpa": (
        "facts.metrics.mature_actual_cpa",
        "non_negative_number",
    ),
    "成熟实际_cpa": ("facts.metrics.mature_actual_cpa", "non_negative_number"),
    "mature_actual_roas": ("facts.metrics.mature_actual_roas", "roas"),
    "成熟实际_roas": ("facts.metrics.mature_actual_roas", "roas"),
    "mature_conversions": (
        "facts.metrics.mature_conversions",
        "non_negative_number",
    ),
    "成熟转化": ("facts.metrics.mature_conversions", "non_negative_number"),
    "mature_revenue": ("facts.metrics.mature_revenue", "non_negative_number"),
    "成熟收入": ("facts.metrics.mature_revenue", "non_negative_number"),
    "days_since_last_change": (
        "maturity.days_since_last_change",
        "non_negative_number",
    ),
    "距上次修改天数": ("maturity.days_since_last_change", "non_negative_number"),
    "mature_events_since_change": (
        "maturity.mature_events_since_change",
        "non_negative_number",
    ),
    "修改后成熟事件": (
        "maturity.mature_events_since_change",
        "non_negative_number",
    ),
    "value_missing_rate": ("measurement.value_missing_rate", "percent"),
    "value_缺失率": ("measurement.value_missing_rate", "percent"),
    "currency_consistency_rate": (
        "measurement.currency_consistency_rate",
        "percent",
    ),
    "币种一致率": ("measurement.currency_consistency_rate", "percent"),
    "google_mmp_value_difference_rate": (
        "measurement.google_mmp_value_difference_rate",
        "percent",
    ),
    "google_mmp_价值差异率": (
        "measurement.google_mmp_value_difference_rate",
        "percent",
    ),
    "mmp_backend_value_difference_rate": (
        "measurement.mmp_backend_value_difference_rate",
        "percent",
    ),
    "mmp_后端价值差异率": (
        "measurement.mmp_backend_value_difference_rate",
        "percent",
    ),
    "refund_rate": ("measurement.refund_rate", "percent"),
    "退款率": ("measurement.refund_rate", "percent"),
    "maximum_acceptable_refund_rate": (
        "goal.maximum_acceptable_refund_rate",
        "percent",
    ),
    "可接受退款率上限": ("goal.maximum_acceptable_refund_rate", "percent"),
    "country": ("scope.country", "text"),
    "国家": ("scope.country", "text"),
    "os": ("scope.os", "text"),
    "system": ("scope.os", "text"),
    "系统": ("scope.os", "text"),
    "asset": ("facts.asset", "text"),
    "creative": ("facts.asset", "text"),
    "素材": ("facts.asset", "text"),
    "start_date": ("scope.start_date", "date"),
    "开始日期": ("scope.start_date", "date"),
    "end_date": ("scope.end_date", "date"),
    "结束日期": ("scope.end_date", "date"),
    "timezone": ("scope.timezone", "text"),
    "时区": ("scope.timezone", "text"),
    "conversion_rate": ("facts.metrics.conversion_rate", "percent"),
    "cvr": ("facts.metrics.conversion_rate", "percent"),
    "转化率": ("facts.metrics.conversion_rate", "percent"),
}

_BASE_MINIMUM_FIELDS = (
    "scope.start_date",
    "scope.end_date",
    "scope.timezone",
    "scope.country",
    "scope.os",
    "facts.metrics.spend",
    "facts.metrics.installs",
    "facts.metrics.registrations",
    "facts.metrics.payments",
    "facts.daily_budget",
)

_DROP_VALUE = object()


def _alias_key(value: str) -> str:
    return "_".join(value.strip().lower().replace("-", " ").split())


def _normalize_number(
    value: Any, *, percent: bool = False, non_negative: bool = False
) -> int | float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric metric")
    had_percent = False
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        for symbol in ("$", "¥", "￥"):
            cleaned = cleaned.replace(symbol, "")
        if cleaned.endswith("%"):
            had_percent = True
            cleaned = cleaned[:-1].strip()
        try:
            number = float(cleaned)
        except ValueError as exc:
            raise ValueError("must be a number or numeric string") from exc
    elif isinstance(value, int) and not isinstance(value, bool):
        number = value
    elif isinstance(value, float):
        number = value
    else:
        raise ValueError("must be a number or numeric string")
    try:
        number_is_finite = math.isfinite(float(number))
    except OverflowError:
        number_is_finite = False
    if not number_is_finite:
        raise ValueError("must be a finite number within the supported range")
    if had_percent and not percent:
        raise ValueError("percentage notation is only valid for percentage fields")
    if percent:
        if had_percent:
            number /= 100
        if not 0 <= number <= 1:
            raise ValueError("percentage must be between 0% and 100%")
    if non_negative and number < 0:
        raise ValueError("must be a non-negative number")
    if (
        not percent
        and not had_percent
        and isinstance(number, float)
        and number.is_integer()
    ):
        return int(number)
    return number


def _normalize_date(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError("must be a date string")
    candidate = value.strip()
    formats = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日")
    for format_string in formats:
        try:
            return datetime.strptime(candidate, format_string).date().isoformat()
        except ValueError:
            continue
    try:
        return (
            datetime.fromisoformat(candidate.replace("Z", "+00:00")).date().isoformat()
        )
    except ValueError as exc:
        raise ValueError("must use an unambiguous date such as YYYY-MM-DD") from exc


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("must be text")
    stripped = value.strip()
    return stripped or None


def _convert(value: Any, kind: str) -> Any:
    if kind == "number":
        return _normalize_number(value)
    if kind == "non_negative_number":
        return _normalize_number(value, non_negative=True)
    if kind == "percent":
        return _normalize_number(value, percent=True)
    if kind == "roas":
        if isinstance(value, str) and value.strip().endswith("%"):
            raw_percent = value.strip()[:-1].strip()
            normalized_percent = _normalize_number(raw_percent, non_negative=True)
            if normalized_percent is None:
                return None
            return float(normalized_percent) / 100
        return _normalize_number(value, non_negative=True)
    if kind == "date":
        return _normalize_date(value)
    return _normalize_text(value)


def _set_path(target: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current = target
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _delete_path(target: dict[str, Any], dotted: str) -> None:
    parts = dotted.split(".")
    current: Any = target
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _get_path(target: Mapping[str, Any], dotted: str) -> Any:
    current: Any = target
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _remove_non_finite_values(
    value: Any, path: str, issues: list[NormalizationIssue]
) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        issues.append(
            {
                "field": path,
                "message": "must be a finite number within the supported range",
            }
        )
        return _DROP_VALUE
    if isinstance(value, dict):
        cleaned: dict[Any, Any] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            sanitized = _remove_non_finite_values(child, child_path, issues)
            if sanitized is not _DROP_VALUE:
                cleaned[key] = sanitized
        return cleaned
    if isinstance(value, list):
        cleaned_list: list[Any] = []
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            sanitized = _remove_non_finite_values(child, child_path, issues)
            if sanitized is not _DROP_VALUE:
                cleaned_list.append(sanitized)
        return cleaned_list
    return value


def _normalize_existing_structure(
    normalized: dict[str, Any], issues: list[NormalizationIssue]
) -> None:
    paths: list[tuple[str, str]] = [
        ("scope.start_date", "date"),
        ("scope.end_date", "date"),
        ("facts.daily_budget", "non_negative_number"),
        ("goal.target_cpa", "non_negative_number"),
        ("goal.target_roas", "roas"),
        ("goal.maximum_acceptable_cpa", "non_negative_number"),
        ("goal.minimum_acceptable_roas", "roas"),
        ("goal.daily_budget_cap", "non_negative_number"),
        ("goal.maximum_acceptable_refund_rate", "percent"),
        ("maturity.days_since_last_change", "non_negative_number"),
        ("maturity.mature_events_since_change", "non_negative_number"),
        ("maturity.previous_target", "non_negative_number"),
        ("maturity.previous_daily_budget", "non_negative_number"),
        ("measurement.value_missing_rate", "percent"),
        ("measurement.currency_consistency_rate", "percent"),
        ("measurement.google_mmp_value_difference_rate", "percent"),
        ("measurement.mmp_backend_value_difference_rate", "percent"),
        ("measurement.refund_rate", "percent"),
    ]
    metrics = _get_path(normalized, "facts.metrics")
    if isinstance(metrics, Mapping):
        for name in metrics:
            metric_name = str(name).lower()
            if metric_name.endswith("_rate"):
                kind = "percent"
            elif metric_name == "mature_actual_roas":
                kind = "roas"
            elif metric_name in {"spend", "installs", "registrations", "payments"}:
                kind = "non_negative_number"
            else:
                kind = "number"
            paths.append((f"facts.metrics.{name}", kind))
    for dotted, kind in paths:
        original = _get_path(normalized, dotted)
        if original is None:
            continue
        try:
            _set_path(normalized, dotted, _convert(original, kind))
        except ValueError as exc:
            issues.append({"field": dotted, "message": str(exc)})
            _delete_path(normalized, dotted)
    facts = _get_path(normalized, "facts")
    if isinstance(facts, Mapping):
        daily_series = facts.get("daily_series")
        if isinstance(daily_series, list):
            for index, row in enumerate(daily_series):
                if not isinstance(row, dict):
                    continue
                if row.get("date") is not None:
                    try:
                        row["date"] = _convert(row["date"], "date")
                    except ValueError as exc:
                        issues.append(
                            {
                                "field": f"facts.daily_series[{index}].date",
                                "message": str(exc),
                            }
                        )
                        row.pop("date", None)
                for field in ("spend", "mature_events", "value"):
                    if row.get(field) is None:
                        continue
                    try:
                        row[field] = _convert(row[field], "non_negative_number")
                    except ValueError as exc:
                        issues.append(
                            {
                                "field": f"facts.daily_series[{index}].{field}",
                                "message": str(exc),
                            }
                        )
                        row.pop(field, None)


def normalize_uac_input(
    raw: Mapping[str, Any], *, source_label: str = "user_provided"
) -> NormalizationResult:
    """Map common flat/nested fields without making an advertising decision."""

    if not isinstance(raw, Mapping):
        raise ContractError("normalization input must be an object")

    normalized: dict[str, Any] = {
        key: deepcopy(value) for key, value in raw.items() if key in _STRUCTURED_KEYS
    }
    normalized.setdefault("scope", {})
    scope = normalized["scope"]
    if isinstance(scope, dict):
        scope.setdefault("platform", "google_ads")
        scope.setdefault("campaign_type", "app_campaign")

    issues: list[NormalizationIssue] = []
    extras: dict[str, Any] = {}
    field_map: dict[str, str] = {}
    _normalize_existing_structure(normalized, issues)

    assigned_values: dict[str, tuple[str, Any]] = {}
    for dotted, _kind in set(_ALIASES.values()):
        existing = _get_path(normalized, dotted)
        if existing is not None:
            assigned_values[dotted] = ("structured input", deepcopy(existing))
    conflicted_paths: set[str] = set()

    for raw_key, value in raw.items():
        if raw_key in _STRUCTURED_KEYS:
            field_map[str(raw_key)] = str(raw_key)
            continue
        alias = _ALIASES.get(_alias_key(str(raw_key)))
        if alias is None:
            extras[str(raw_key)] = deepcopy(value)
            continue
        dotted, kind = alias
        field_map[str(raw_key)] = dotted
        try:
            converted = _convert(value, kind)
        except ValueError as exc:
            issues.append({"field": str(raw_key), "message": str(exc)})
            continue
        if converted is None:
            continue
        if dotted in conflicted_paths:
            issues.append(
                {
                    "field": str(raw_key),
                    "message": f"conflicts with another source field mapped to {dotted}",
                }
            )
            continue
        previous = assigned_values.get(dotted)
        if previous is not None:
            previous_source, previous_value = previous
            if converted != previous_value:
                issues.append(
                    {
                        "field": str(raw_key),
                        "message": f"conflicts with {previous_source} mapped to {dotted}",
                    }
                )
                _delete_path(normalized, dotted)
                conflicted_paths.add(dotted)
            continue
        _set_path(normalized, dotted, converted)
        assigned_values[dotted] = (str(raw_key), deepcopy(converted))

    normalized = _remove_non_finite_values(normalized, "", issues)
    extras = _remove_non_finite_values(extras, "", issues)
    assert isinstance(normalized, dict)
    assert isinstance(extras, dict)

    minimum_fields = list(_BASE_MINIMUM_FIELDS)
    bidding_strategy = str(_get_path(normalized, "goal.bidding_strategy") or "").lower()
    if (
        "roas" in bidding_strategy
        or _get_path(normalized, "goal.target_roas") is not None
    ):
        minimum_fields.append("goal.target_roas")
    else:
        minimum_fields.append("goal.target_cpa")
    missing = []
    for dotted in minimum_fields:
        value = _get_path(normalized, dotted)
        if value is None or value == "":
            missing.append(dotted)
    source: NormalizationSource = {
        "label": source_label,
        "received_fields": sorted(str(key) for key in raw),
        "field_map": field_map,
    }
    return {
        "schema_version": "1.0",
        "normalized": normalized,
        "missing_fields": missing,
        "conversion_errors": issues,
        "extras": extras,
        "source": source,
        "decision_made": False,
    }


def load_normalization_source(path: Path) -> dict[str, Any]:
    """Load one summary object from JSON, YAML, or a one-row CSV export."""

    if path.suffix.lower() != ".csv":
        return _load(path)
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        raise ContractError(f"unable to read CSV {path.name}: {exc}") from exc
    if len(rows) != 1:
        raise ContractError("CSV normalization expects exactly one summary row")
    return dict(rows[0])


def render_normalization(result: NormalizationResult) -> str:
    return json.dumps(result, ensure_ascii=True, indent=2, default=str, allow_nan=False)
