"""Configurable campaign-level terminology for UAC Quick Ops."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping


CAMPAIGN_LEVELS = ("AC2.0", "AC2.5", "AC3.0")
_CANONICAL_KEYS = {"ac20": "AC2.0", "ac25": "AC2.5", "ac30": "AC3.0"}
_EXPLICIT_LEVEL = re.compile(
    r"(?P<prefix>(?<![\w])AC|广告)\s*(?P<number>2(?:[._]?0|[._]?5)?|3(?:[._]?0)?)(?![\d.])",
    re.IGNORECASE,
)


def _number_to_level(number: str) -> str | None:
    normalized = number.replace("_", ".")
    if normalized in {"2", "2.0"}:
        return "AC2.0"
    if normalized == "2.5":
        return "AC2.5"
    if normalized in {"3", "3.0"}:
        return "AC3.0"
    return None


def canonical_campaign_level(
    value: Any, *, explicit_context: bool = False
) -> str | None:
    """Return a canonical level without ever treating a bid number as a level.

    Free text requires an ``AC`` or ``广告`` prefix. Structured level fields may
    additionally use the canonical label or the stable ``ac20``/``ac25``/``ac30``
    keys. Numeric values and bare strings such as ``2.5`` always return ``None``.
    """

    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    key = re.sub(r"[^a-z0-9]", "", text.lower())
    if not explicit_context and key in _CANONICAL_KEYS:
        return _CANONICAL_KEYS[key]
    match = _EXPLICIT_LEVEL.fullmatch(text)
    if not match:
        return None
    return _number_to_level(match.group("number"))


def extract_campaign_levels(text: str) -> list[str]:
    """Extract unique explicit campaign-level labels in mention order."""

    levels: list[str] = []
    for match in _EXPLICIT_LEVEL.finditer(text):
        level = _number_to_level(match.group("number"))
        if level is not None and level not in levels:
            levels.append(level)
    return levels


def glossary_key(level: str) -> str:
    return {value: key for key, value in _CANONICAL_KEYS.items()}[level]


def normalize_glossary(glossary: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Normalize supported glossary keys while preserving team-defined semantics."""

    if glossary is None:
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for raw_key, raw_definition in glossary.items():
        level = canonical_campaign_level(str(raw_key))
        if level is None or not isinstance(raw_definition, Mapping):
            continue
        normalized[glossary_key(level)] = deepcopy(dict(raw_definition))
    return normalized


def _normalized_token(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return "_".join(value.strip().lower().replace("-", " ").split())


def _account_semantics(account: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(account, Mapping):
        return {}
    event = _normalized_token(account.get("optimization_event"))
    strategy = _normalized_token(account.get("bidding_strategy"))
    declared_value = account.get("value_optimization")
    strategy_implies_value = strategy in {
        "troas",
        "target_roas",
        "maximize_conversion_value",
        "max_conversion_value",
    }
    if isinstance(declared_value, bool):
        value_optimization: bool | None = declared_value
    elif isinstance(strategy, str) and strategy:
        value_optimization = strategy_implies_value
    else:
        value_optimization = None
    if value_optimization is True:
        objective_type = "conversion_value"
    elif event == "install":
        objective_type = "install"
    elif isinstance(event, str) and event:
        objective_type = "in_app_action"
    else:
        objective_type = None
    return {
        "objective_type": objective_type,
        "optimization_event": event,
        "value_optimization": value_optimization,
        "bidding_strategy": strategy,
        "value_currency_required": value_optimization
        if value_optimization is not None
        else None,
    }


def _mapping_conflicts(
    definition: Mapping[str, Any], account_semantics: Mapping[str, Any]
) -> list[str]:
    conflicts: list[str] = []
    comparable = (
        "optimization_event",
        "value_optimization",
        "bidding_strategy",
    )
    for field in comparable:
        declared = definition.get(field)
        actual = account_semantics.get(field)
        if declared is None or declared in ("configurable", "unknown"):
            continue
        if actual is None or actual == "":
            continue
        if _normalized_token(declared) != _normalized_token(actual):
            conflicts.append(field)
    return conflicts


def resolve_campaign_level(
    user_term: Any,
    *,
    glossary: Mapping[str, Any] | None = None,
    account: Mapping[str, Any] | None = None,
    mapping_confirmed: bool = False,
    switching: bool = False,
) -> dict[str, Any]:
    """Resolve a team label without presenting it as a Google product name."""

    level = canonical_campaign_level(user_term, explicit_context=True)
    if level is None:
        level = canonical_campaign_level(user_term)
    normalized_glossary = normalize_glossary(glossary)
    account_semantics = _account_semantics(account)
    definition = (
        normalized_glossary.get(glossary_key(level), {}) if level is not None else {}
    )
    conflicts = _mapping_conflicts(definition, account_semantics)

    if level is None:
        source = "unresolved"
        confidence = "low"
        resolved: dict[str, Any] = {}
    elif conflicts:
        source = "account_settings_override"
        confidence = "medium"
        resolved = account_semantics
    elif definition:
        source = "project_glossary"
        confidence = "high"
        resolved = deepcopy(definition)
        resolved.update(
            {
                key: value
                for key, value in account_semantics.items()
                if value is not None
            }
        )
    elif account_semantics:
        source = "account_inference"
        confidence = "medium"
        resolved = account_semantics
    else:
        source = "unconfirmed_inference"
        confidence = "low"
        resolved = {}

    inferred = source not in {"project_glossary"}
    confirmation_required = bool(
        switching
        and (
            conflicts
            or source in {"account_inference", "unconfirmed_inference", "unresolved"}
        )
        and not mapping_confirmed
    )
    return {
        "user_term": user_term if isinstance(user_term, str) else None,
        "resolved_level": level,
        "display_name": level,
        "resolved_meaning": resolved or None,
        "resolution_source": source,
        "confidence": confidence,
        "inferred": inferred,
        "official_google_product_name": False,
        "not_a_bid_value": True,
        "glossary_conflicts": conflicts,
        "confirmation_required": confirmation_required,
    }
