#!/usr/bin/env python3
"""Audit sidecar freshness metadata without accessing the network.

Unverified or stale knowledge is advisory by default so ordinary CI does not
start failing merely because time passed. Maintainers can opt into ``--strict``
to turn warnings into a non-zero maintenance signal.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by the CLI dependency error
    yaml = None


class MetadataError(ValueError):
    """Raised when freshness metadata cannot be loaded."""


_RULE_TYPES = {
    "platform_guidance",
    "policy",
    "heuristic",
    "account_specific_learning",
}
_CONFIDENCE_LEVELS = {"low", "medium", "high"}
_ABSOLUTE_LANGUAGE = re.compile(
    r"\b(always|never|guarantee(?:d|s)?|must)\b|必须|保证|绝对",
    re.IGNORECASE,
)


def load_metadata(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise MetadataError("PyYAML is required to read knowledge metadata")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MetadataError(f"unable to read metadata file: {path.name}") from exc
    except yaml.YAMLError as exc:
        raise MetadataError(f"invalid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise MetadataError("knowledge metadata must contain an object")
    return value


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("must be an ISO date or null")
    return date.fromisoformat(value)


def _safe_relative_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be a non-empty repository-relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("must stay inside the repository")
    return path


def _check(
    check_id: str,
    topic: str,
    status: str,
    reason: str,
    *,
    age_days: int | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "topic": topic,
        "status": status,
        "reason": reason,
        "age_days": age_days,
    }


def evaluate_metadata(
    metadata: dict[str, Any], *, repo_root: Path, as_of: date
) -> dict[str, Any]:
    """Validate metadata and return a deterministic freshness report."""

    checks: list[dict[str, Any]] = []
    if metadata.get("schema_version") != "1.0":
        checks.append(
            _check("metadata-schema", "metadata", "FAIL", "schema_version must be 1.0")
        )

    policy = metadata.get("policy")
    default_days: int | None = None
    if not isinstance(policy, dict):
        checks.append(
            _check("metadata-policy", "metadata", "FAIL", "policy must be an object")
        )
    else:
        candidate = policy.get("default_review_after_days")
        if (
            isinstance(candidate, int)
            and not isinstance(candidate, bool)
            and candidate > 0
        ):
            default_days = candidate
        else:
            checks.append(
                _check(
                    "metadata-policy",
                    "metadata",
                    "FAIL",
                    "default_review_after_days must be a positive integer",
                )
            )

    required_topics = metadata.get("required_topics")
    if (
        not isinstance(required_topics, list)
        or not required_topics
        or not all(isinstance(topic, str) and topic for topic in required_topics)
    ):
        checks.append(
            _check(
                "required-topics",
                "metadata",
                "FAIL",
                "required_topics must be a non-empty string array",
            )
        )
        required_topic_set: set[str] = set()
    else:
        required_topic_set = set(required_topics)
        if len(required_topic_set) != len(required_topics):
            checks.append(
                _check(
                    "required-topics",
                    "metadata",
                    "FAIL",
                    "required_topics contains duplicates",
                )
            )

    entries = metadata.get("entries")
    if not isinstance(entries, list) or not entries:
        checks.append(
            _check(
                "metadata-entries",
                "metadata",
                "FAIL",
                "entries must be a non-empty array",
            )
        )
        entries = []

    seen_ids: set[str] = set()
    covered_topics: set[str] = set()
    for index, entry in enumerate(entries):
        fallback_id = f"entries[{index}]"
        if not isinstance(entry, dict):
            checks.append(
                _check(fallback_id, "unknown", "FAIL", "entry must be an object")
            )
            continue

        check_id = entry.get("id")
        topic = entry.get("topic")
        if not isinstance(check_id, str) or not check_id.strip():
            checks.append(
                _check(
                    fallback_id, str(topic or "unknown"), "FAIL", "id must be non-empty"
                )
            )
            continue
        if check_id in seen_ids:
            checks.append(
                _check(check_id, str(topic or "unknown"), "FAIL", "duplicate id")
            )
            continue
        seen_ids.add(check_id)

        if not isinstance(topic, str) or not topic.strip():
            checks.append(
                _check(check_id, "unknown", "FAIL", "topic must be non-empty")
            )
            continue
        covered_topics.add(topic)

        source_type = entry.get("source_type")
        source_reference = entry.get("source_reference")
        rule_type = entry.get("rule_type")
        confidence = entry.get("confidence")
        paths = entry.get("paths")
        resolved_paths: list[Path] = []
        entry_errors: list[str] = []
        if not isinstance(source_type, str) or not source_type.strip():
            entry_errors.append("source_type must be non-empty")
        if not isinstance(source_reference, str) or not source_reference.strip():
            entry_errors.append("source_reference must be non-empty")
        if rule_type not in _RULE_TYPES:
            entry_errors.append("rule_type is invalid or missing")
        if confidence not in _CONFIDENCE_LEVELS:
            entry_errors.append("confidence is invalid or missing")
        if not isinstance(paths, list) or not paths:
            entry_errors.append("paths must be a non-empty array")
        else:
            for raw_path in paths:
                try:
                    relative = _safe_relative_path(raw_path)
                except ValueError as exc:
                    entry_errors.append(f"invalid path: {exc}")
                    continue
                resolved = repo_root / Path(*relative.parts)
                if not resolved.is_file():
                    entry_errors.append(
                        f"missing repository file: {relative.as_posix()}"
                    )
                else:
                    resolved_paths.append(resolved)

        review_after = entry.get("review_after_days", default_days)
        if (
            not isinstance(review_after, int)
            or isinstance(review_after, bool)
            or review_after <= 0
        ):
            entry_errors.append("review_after_days must be a positive integer")

        try:
            verified_on = _parse_date(entry.get("verified_on"))
        except ValueError as exc:
            entry_errors.append(f"verified_on {exc}")
            verified_on = None

        if entry_errors:
            checks.append(_check(check_id, topic, "FAIL", "; ".join(entry_errors)))
            continue
        if rule_type == "heuristic":
            risky_files = 0
            for knowledge_path in resolved_paths:
                try:
                    content = knowledge_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if _ABSOLUTE_LANGUAGE.search(content):
                    risky_files += 1
            if risky_files:
                checks.append(
                    _check(
                        f"{check_id}:absolute-language",
                        topic,
                        "WARN",
                        f"heuristic wording needs human review in {risky_files} file(s)",
                    )
                )
        if verified_on is None:
            checks.append(
                _check(
                    check_id,
                    topic,
                    "WARN",
                    "authoritative source verification has not been recorded",
                )
            )
            continue

        age_days = (as_of - verified_on).days
        if age_days < 0:
            checks.append(
                _check(
                    check_id,
                    topic,
                    "FAIL",
                    "verified_on is later than the audit date",
                    age_days=age_days,
                )
            )
        elif age_days > review_after:
            checks.append(
                _check(
                    check_id,
                    topic,
                    "WARN",
                    f"verification is older than {review_after} days",
                    age_days=age_days,
                )
            )
        else:
            checks.append(
                _check(
                    check_id,
                    topic,
                    "PASS",
                    "verification is within its review window",
                    age_days=age_days,
                )
            )

    for topic in sorted(required_topic_set - covered_topics):
        checks.append(
            _check(
                f"required-topic:{topic}",
                topic,
                "FAIL",
                "required topic has no metadata entry",
            )
        )

    summary = {
        status.lower(): sum(check["status"] == status for check in checks)
        for status in ("PASS", "WARN", "FAIL")
    }
    overall = "FAIL" if summary["fail"] else "WARN" if summary["warn"] else "PASS"
    return {
        "schema_version": "1.0",
        "as_of": as_of.isoformat(),
        "status": overall,
        "summary": summary,
        "checks": checks,
        "link_check": {
            "status": "NOT_RUN",
            "reason": (
                "offline mode does not verify external links; exact authoritative "
                "URLs should be recorded during maintainer verification"
            ),
        },
        "disclaimer": (
            "Freshness metadata records maintenance status only; it does not prove "
            "that a platform rule is correct or applicable to a specific account."
        ),
    }


def exit_code(report: dict[str, Any], *, strict: bool) -> int:
    if report["summary"]["fail"]:
        return 2
    if strict and report["summary"]["warn"]:
        return 1
    return 0


def _failure_report(as_of: date, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "as_of": as_of.isoformat(),
        "status": "FAIL",
        "summary": {"pass": 0, "warn": 0, "fail": 1},
        "checks": [_check("metadata-load", "metadata", "FAIL", reason)],
        "link_check": {
            "status": "NOT_RUN",
            "reason": "metadata could not be loaded, so links were not checked",
        },
        "disclaimer": (
            "Freshness metadata records maintenance status only; it does not prove "
            "that a platform rule is correct or applicable to a specific account."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Audit knowledge freshness metadata")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=repo_root / "knowledge" / "metadata.yaml",
        help="metadata YAML path (default: knowledge/metadata.yaml)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return exit 1 when freshness warnings exist",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
        metavar="YYYY-MM-DD",
        help="audit date for reproducible maintenance checks",
    )
    parser.add_argument(
        "--repo-root", type=Path, default=repo_root, help=argparse.SUPPRESS
    )
    return parser


def _print_human(report: dict[str, Any], *, strict: bool) -> None:
    summary = report["summary"]
    print(
        f"knowledge freshness: {report['status']} "
        f"({summary['pass']} pass, {summary['warn']} warn, {summary['fail']} fail)"
    )
    for check in report["checks"]:
        print(f"- {check['status']} {check['id']}: {check['reason']}")
    print(report["disclaimer"])
    if report["status"] == "WARN" and not strict:
        print("Warnings are advisory by default; maintainers can run --strict.")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.repo_root.expanduser().resolve()
    metadata_path = args.metadata.expanduser()
    if not metadata_path.is_absolute():
        metadata_path = root / metadata_path
    try:
        metadata = load_metadata(metadata_path)
        report = evaluate_metadata(metadata, repo_root=root, as_of=args.as_of)
    except MetadataError as exc:
        report = _failure_report(args.as_of, str(exc))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report, strict=args.strict)
    return exit_code(report, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
