#!/usr/bin/env python3
"""Redacted secret/identity checks for the current tree or reachable history.

Findings report only a location and category. Matched values are never printed,
which makes this suitable for release logs and CI output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


_BINARY_SUFFIXES = {
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".webp",
    ".zip",
}

_CONTENT_PATTERNS: tuple[tuple[str, str, re.Pattern[bytes]], ...] = (
    (
        "github-token",
        "HIGH",
        re.compile(rb"(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})"),
    ),
    ("aws-access-key", "HIGH", re.compile(rb"(?:AKIA|ASIA)[0-9A-Z]{16}")),
    ("google-api-key", "HIGH", re.compile(rb"AIza[0-9A-Za-z_-]{30,}")),
    (
        "google-oauth-refresh-token",
        "HIGH",
        re.compile(rb"(?<![A-Za-z0-9._~-])1//[A-Za-z0-9._~-]{20,}"),
    ),
    (
        "meta-access-token",
        "HIGH",
        re.compile(rb"\bEAA[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "openai-api-key",
        "HIGH",
        re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "private-key",
        "HIGH",
        re.compile(
            rb"-----BEGIN (?:(?:(?:RSA|EC|OPENSSH|ENCRYPTED|DSA) )?PRIVATE KEY|"
            rb"PGP PRIVATE KEY BLOCK)-----"
        ),
    ),
    (
        "mac-home-path",
        "MEDIUM",
        re.compile(
            rb"/Users/(?!example(?=/|[\s\"']|$)|username(?=/|[\s\"']|$)|<)"
            rb"[^/\s\"']+(?=/|[\s\"']|$)"
        ),
    ),
    (
        "windows-home-path",
        "MEDIUM",
        re.compile(
            rb"[A-Za-z]:(?:\\\\|\\)Users(?:\\\\|\\)"
            rb"(?!example(?=(?:\\\\|\\)|[\s\"']|$)|"
            rb"username(?=(?:\\\\|\\)|[\s\"']|$)|<)"
            rb"[^\\\s\"']+(?=(?:\\\\|\\)|[\s\"']|$)"
        ),
    ),
    (
        "linux-home-path",
        "MEDIUM",
        re.compile(
            rb"/home/(?!example(?=/|[\s\"']|$)|runner(?=/|[\s\"']|$)|"
            rb"username(?=/|[\s\"']|$)|<)[^/\s\"']+(?=/|[\s\"']|$)"
        ),
    ),
)

_SENSITIVE_VALUE_PATTERNS: tuple[tuple[str, str, re.Pattern[bytes]], ...] = (
    (
        "bearer-token",
        "HIGH",
        re.compile(
            rb"\bbearer\s+(?P<value>[A-Za-z0-9._~+/=-]{24,})",
            re.IGNORECASE,
        ),
    ),
    (
        "oauth-client-secret",
        "HIGH",
        re.compile(
            rb"\b[A-Za-z0-9_-]{0,40}(?:client|app)[_ -]?secret\b"
            rb"[\"']?\s*[:=]\s*[\"']?"
            rb"(?P<value>[A-Za-z0-9._~+/:|=-]{16,})",
            re.IGNORECASE,
        ),
    ),
    (
        "google-ads-developer-token",
        "HIGH",
        re.compile(
            rb"\b[A-Za-z0-9_-]{0,40}developer[_ -]?token\b"
            rb"[\"']?\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9._~+/:|=-]{12,})",
            re.IGNORECASE,
        ),
    ),
    (
        "oauth-refresh-token",
        "HIGH",
        re.compile(
            rb"\b[A-Za-z0-9_-]{0,40}refresh[_ -]?token\b"
            rb"[\"']?\s*[:=]\s*[\"']?"
            rb"(?P<value>[A-Za-z0-9._~+/:|=-]{20,})",
            re.IGNORECASE,
        ),
    ),
    (
        "access-token",
        "HIGH",
        re.compile(
            rb"\b[A-Za-z0-9_-]{0,40}access[_ -]?token\b"
            rb"[\"']?\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9._~+/:|=-]{20,})",
            re.IGNORECASE,
        ),
    ),
    (
        "google-ads-customer-id",
        "HIGH",
        re.compile(
            rb"\b(?:google[_ -]?ads[_ -]?(?:login[_ -]?)?customer[_ -]?id|"
            rb"login[_ -]?customer[_ -]?id)\b[\"']?\s*[:=]\s*[\"']?"
            rb"(?P<value>[0-9]{3}-?[0-9]{3}-?[0-9]{4})\b",
            re.IGNORECASE,
        ),
    ),
    (
        "meta-ad-account-id",
        "HIGH",
        re.compile(rb"\b(?P<value>act_[0-9]{8,20})\b", re.IGNORECASE),
    ),
    (
        "mmp-token",
        "HIGH",
        re.compile(
            rb"\b(?:appsflyer(?:[_-]?dev)?[_-]?key|"
            rb"adjust[_-]?(?:app[_-]?)?token|"
            rb"branch[_-]?(?:sdk[_-]?)?key|singular[_-]?api[_-]?key|"
            rb"kochava[_-]?app[_-]?guid|mmp[_-]?(?:api[_-]?)?token)\b"
            rb"[\"']?\s*[:=]\s*[\"']?"
            rb"(?P<value>[A-Za-z0-9._~+/:|=-]{12,})",
            re.IGNORECASE,
        ),
    ),
)

_EMAIL = re.compile(
    rb"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9.-])"
)
_TAGGER_IDENTITY = re.compile(
    rb"^tagger (?P<name>.*?) <(?P<email>[^<>]+)> -?[0-9]+ [+-][0-9]{4}$",
    re.MULTILINE,
)
_SAFE_EMAIL_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
    "example.invalid",
    "users.noreply.github.com",
}
_CREDENTIALED_URL = re.compile(
    rb"[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@(?P<host>[^\s/:]+)"
)
_RESERVED_URL_HOSTS = {
    "example.com",
    "example.net",
    "example.org",
    "host",
    "localhost",
}
_INTENTIONAL_DETECTOR_PATHS = {
    ("linux-home-path", "scripts/privacy_doctor.py"),
    ("mac-home-path", "scripts/privacy_doctor.py"),
}

_SAFE_IDENTIFIER_VALUES = {
    "google-ads-customer-id": {
        "0000000000",
        "1112223333",
        "1234567890",
        "9999999999",
    },
    "meta-ad-account-id": {
        "act_0000000000",
        "act_1234567890",
    },
}
_SAFE_PLACEHOLDER_VALUES = {
    "changeme",
    "dummy",
    "dummy_token",
    "example",
    "example_secret",
    "example_token",
    "placeholder",
    "placeholder_token",
    "redacted",
    "redacted_token",
    "replace-me",
    "replace_me",
    "sample",
    "sample_token",
    "synthetic",
    "test",
    "test-token",
    "test_token",
    "your",
    "your_access_token",
    "your_client_secret",
    "your_developer_token",
    "your_refresh_token_here",
    "your_token_here",
}
_SYNTHETIC_JWT_VALUE = re.compile(
    r"^ey[a-z0-9_-]{10,}\.payload\.(?:sig|signature)$",
    re.IGNORECASE,
)
_VIRTUAL_FINDING_PATHS = {
    "<commit-message>",
    "<commit-metadata>",
    "<tag-message>",
    "<tag-metadata>",
}
_PRIVATE_DIRECTORY_NAMES = {
    "account-exports",
    "customer-data",
    "private-replays",
    "private",
    "workspaces",
}
_PRIVATE_PROJECT_FILENAMES = {
    "ads-experiments.yaml",
    "ads-experiments.yml",
    "ads-experiments.json",
    "ads-ops-log.md",
    "ads-project-context.md",
    "ads-report-format.md",
    "codex_ads_optimizer.md",
    "normalization.json",
    "project-context.json",
    "project-context.yaml",
    "project-context.yml",
    "uac-analysis.json",
    "uac-input.draft.json",
    "uac-input.draft.yaml",
    "uac-input.draft.yml",
    "uac-input.yaml",
    "uac-input.yml",
    "uac-input.json",
    "uac-report.md",
}
_SAFE_ENV_FILENAMES = {".env.example", ".env.sample", ".env.template"}


class PrivacyAuditError(RuntimeError):
    """Raised when the repository cannot be inspected safely."""


def _git(root: Path, *arguments: str, text: bool = False) -> bytes | str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=text,
    )
    if completed.returncode != 0:
        reason = (
            completed.stderr.strip()
            if text
            else completed.stderr.decode(errors="replace").strip()
        )
        raise PrivacyAuditError(reason or "git inspection failed")
    return completed.stdout


def _finding(
    scope: str, reference: str, path: str, kind: str, severity: str
) -> dict[str, str]:
    return {
        "scope": scope,
        "reference": reference,
        "path": _reported_path(path),
        "kind": kind,
        "severity": severity,
    }


def _line_has_identifier_allowlist(content: bytes, start: int, end: int) -> bool:
    line_start = content.rfind(b"\n", 0, start) + 1
    line_end = content.find(b"\n", end)
    if line_end < 0:
        line_end = len(content)
    return b"privacy-doctor: allow" in content[line_start:line_end].lower()


def _is_placeholder_value(kind: str, value: bytes) -> bool:
    decoded = value.decode("ascii", errors="ignore").strip().lower()
    if kind == "google-ads-customer-id":
        normalized = re.sub(r"\D", "", decoded)
    else:
        normalized = decoded
    if normalized in _SAFE_IDENTIFIER_VALUES.get(kind, set()):
        return True
    if _SYNTHETIC_JWT_VALUE.fullmatch(decoded):
        return True
    return decoded in _SAFE_PLACEHOLDER_VALUES


def _reported_path(path: str) -> str:
    """Keep findings actionable without echoing secrets or client path labels."""

    if path in _VIRTUAL_FINDING_PATHS:
        return path
    normalized = path.replace("\\", "/")
    digest = hashlib.sha256(os.fsencode(normalized)).hexdigest()[:12]
    return f"<redacted-path:{digest}>"


def _path_findings(*, scope: str, reference: str, path: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    pure_path = PurePosixPath(normalized)
    lower_path = normalized.lower()
    lower_name = pure_path.name.lower()

    findings.extend(
        finding
        for finding in _scan_content(
            os.fsencode(normalized),
            scope=scope,
            reference=reference,
            path=path,
        )
        if finding["kind"] != "public-replay-anonymization-missing"
    )

    if lower_name == ".env" or (
        lower_name.startswith(".env.") and lower_name not in _SAFE_ENV_FILENAMES
    ):
        findings.append(_finding(scope, reference, path, "environment-file", "HIGH"))
    if set(part.lower() for part in pure_path.parts) & _PRIVATE_DIRECTORY_NAMES:
        findings.append(
            _finding(scope, reference, path, "private-workspace-path", "HIGH")
        )
    if lower_name in _PRIVATE_PROJECT_FILENAMES:
        findings.append(
            _finding(scope, reference, path, "root-private-project-file", "HIGH")
        )
    replay_parts = tuple(part.lower() for part in pure_path.parts)
    private_replay = "replays" in replay_parts and not (
        pure_path.parts[:2] == ("examples", "replays")
        or lower_path == "replays/readme.md"
    )
    if private_replay:
        findings.append(
            _finding(scope, reference, path, "private-replay-outside-workspace", "HIGH")
        )
    return findings


def _public_replay_marker_finding(
    content: bytes, *, scope: str, reference: str, path: str
) -> list[dict[str, str]]:
    pure_path = PurePosixPath(path.replace("\\", "/"))
    if (
        len(pure_path.parts) < 4
        or pure_path.parts[:2] != ("examples", "replays")
        or pure_path.name.lower()
        not in {"snapshot-before.yaml", "snapshot-before.yml", "snapshot-before.json"}
    ):
        return []
    expected = {
        "public_example": True,
        "synthetic_values": True,
        "contains_real_account_data": False,
    }
    if pure_path.suffix.lower() == ".json":
        try:
            document = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError):
            markers_valid = False
        else:
            anonymization = (
                document.get("anonymization") if isinstance(document, dict) else None
            )
            markers_valid = isinstance(anonymization, dict) and all(
                anonymization.get(key) is value for key, value in expected.items()
            )
    else:
        markers_valid = _yaml_has_expected_boolean_mapping(
            content, mapping_name="anonymization", expected=expected
        )
    if markers_valid:
        return []
    return [
        _finding(
            scope,
            reference,
            path,
            "public-replay-anonymization-missing",
            "HIGH",
        )
    ]


def _yaml_has_expected_boolean_mapping(
    content: bytes, *, mapping_name: str, expected: dict[str, bool]
) -> bool:
    """Validate one simple top-level YAML boolean mapping without dependencies."""

    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return False
    any_header = re.compile(
        rf'^["\']?{re.escape(mapping_name)}["\']?\s*:',
        re.IGNORECASE,
    )
    header = re.compile(
        rf'^["\']?{re.escape(mapping_name)}["\']?\s*:\s*(?:#.*)?$',
        re.IGNORECASE,
    )
    header_indexes = [
        index for index, line in enumerate(lines) if any_header.match(line)
    ]
    if len(header_indexes) != 1 or header.fullmatch(lines[header_indexes[0]]) is None:
        return False

    values: dict[str, bool] = {}
    child_indent: int | None = None
    pair = re.compile(
        r'^["\']?(?P<key>[A-Za-z0-9_]+)["\']?\s*:\s*'
        r"(?P<value>true|false)\s*(?:#.*)?$",
        re.IGNORECASE,
    )
    for line in lines[header_indexes[0] + 1 :]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("\t"):
            return False
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            break
        if child_indent is None:
            child_indent = indent
        if indent != child_indent:
            continue
        match = pair.fullmatch(line.strip())
        if match is None:
            continue
        key = match.group("key").lower()
        if key in values:
            return False
        values[key] = match.group("value").lower() == "true"
    return values == expected


def _scan_content(
    content: bytes, *, scope: str, reference: str, path: str
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for kind, severity, pattern in _CONTENT_PATTERNS:
        if pattern.search(content) and (kind, path) not in _INTENTIONAL_DETECTOR_PATHS:
            findings.append(_finding(scope, reference, path, kind, severity))
    for kind, severity, pattern in _SENSITIVE_VALUE_PATTERNS:
        unsafe_match = next(
            (
                match
                for match in pattern.finditer(content)
                if not _is_placeholder_value(kind, match.group("value"))
                and not (
                    kind in {"google-ads-customer-id", "meta-ad-account-id"}
                    and _line_has_identifier_allowlist(
                        content, match.start(), match.end()
                    )
                )
            ),
            None,
        )
        if unsafe_match is not None:
            findings.append(_finding(scope, reference, path, kind, severity))
    credential_hosts = {
        match.group("host").decode("ascii", errors="ignore").lower()
        for match in _CREDENTIALED_URL.finditer(content)
    }
    unsafe_credential_hosts = {
        host
        for host in credential_hosts
        if not any(
            host == allowed or host.endswith(f".{allowed}")
            for allowed in _RESERVED_URL_HOSTS
        )
    }
    if unsafe_credential_hosts:
        findings.append(_finding(scope, reference, path, "credentialed-url", "HIGH"))
    email_domains = {
        match.group(1).decode("ascii", errors="ignore").lower()
        for match in _EMAIL.finditer(content)
    }
    unsafe_email_domains = {
        domain
        for domain in email_domains
        if not any(
            domain == allowed or domain.endswith(f".{allowed}")
            for allowed in _SAFE_EMAIL_DOMAINS
        )
    }
    if unsafe_email_domains:
        findings.append(
            _finding(scope, reference, path, "non-placeholder-email", "MEDIUM")
        )
    findings.extend(
        _public_replay_marker_finding(
            content, scope=scope, reference=reference, path=path
        )
    )
    return findings


def _candidate_paths(root: Path) -> list[str]:
    raw = _git(
        root,
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    )
    assert isinstance(raw, bytes)
    return sorted(
        item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\0")
        if item
    )


def audit_tree(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for relative in _candidate_paths(root):
        path = root / relative
        findings.extend(
            _path_findings(scope="tree", reference="WORKTREE", path=relative)
        )
        if path.is_symlink():
            try:
                link_target = os.fsencode(os.readlink(path))
            except OSError as exc:
                raise PrivacyAuditError(
                    f"unable to inspect repository symlink: {relative}"
                ) from exc
            target_text = link_target.decode("utf-8", errors="surrogateescape")
            findings.extend(
                _path_findings(scope="tree", reference="WORKTREE", path=target_text)
            )
            continue
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix.lower() == ".pyc":
            findings.append(
                _finding("tree", "WORKTREE", relative, "python-bytecode", "MEDIUM")
            )
            continue
        if path.suffix.lower() in _BINARY_SUFFIXES:
            continue
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise PrivacyAuditError(
                f"unable to read repository path: {relative}"
            ) from exc
        findings.extend(
            _scan_content(content, scope="tree", reference="WORKTREE", path=relative)
        )
    return findings


def _unsafe_identity(email: str) -> bool:
    if "@" not in email:
        return True
    domain = email.rsplit("@", 1)[1].lower()
    return domain not in _SAFE_EMAIL_DOMAINS


def _unsafe_noreply_identity_name(name: str, email: str) -> bool:
    """Require a GitHub noreply display name to remain a pseudonymous handle."""

    if (
        "@" not in email
        or email.rsplit("@", 1)[1].lower() != "users.noreply.github.com"
    ):
        return False
    local_part = email.rsplit("@", 1)[0]
    handle = local_part.split("+", 1)[-1]
    safe_names = {
        handle.casefold(),
        f"{handle}[bot]".casefold(),
        "github",
        "github-actions[bot]",
    }
    return name.strip().casefold() not in safe_names


def _identity_findings(
    *, reference: str, path: str, identities: tuple[tuple[str, str], ...]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if any(_unsafe_identity(email) for _, email in identities):
        findings.append(
            _finding(
                "history",
                reference,
                path,
                "non-noreply-identity",
                "HIGH",
            )
        )
    if any(
        not _unsafe_identity(email) and _unsafe_noreply_identity_name(name, email)
        for name, email in identities
    ):
        findings.append(
            _finding(
                "history",
                reference,
                path,
                "non-pseudonymous-identity-name",
                "HIGH",
            )
        )
    return findings


def _audit_tag_objects(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    refs = _git(
        root,
        "for-each-ref",
        "--format=%(objectname)%00%(objecttype)%00%(refname)",
        text=True,
    )
    assert isinstance(refs, str)
    pending_objects: list[str] = []
    for row in refs.splitlines():
        fields = row.split("\x00")
        if len(fields) != 3:
            continue
        object_id, object_type, _refname = fields
        if object_type == "tag":
            pending_objects.append(object_id)

    scanned_objects: set[str] = set()
    while pending_objects:
        object_id = pending_objects.pop()
        if object_id in scanned_objects:
            continue
        scanned_objects.add(object_id)
        content = _git(root, "cat-file", "tag", object_id)
        assert isinstance(content, bytes)
        metadata, separator, message = content.partition(b"\n\n")
        target = re.search(rb"^object ([0-9a-fA-F]{40,64})$", metadata, re.MULTILINE)
        target_type = re.search(rb"^type ([a-z]+)$", metadata, re.MULTILINE)
        if (
            target is not None
            and target_type is not None
            and target_type.group(1) == b"tag"
        ):
            pending_objects.append(target.group(1).decode("ascii").lower())
        tagger = _TAGGER_IDENTITY.search(metadata)
        if tagger is not None:
            name = tagger.group("name").decode("utf-8", errors="replace")
            email = tagger.group("email").decode("utf-8", errors="replace")
            findings.extend(
                _identity_findings(
                    reference=object_id[:12],
                    path="<tag-metadata>",
                    identities=((name, email),),
                )
            )
        findings.extend(
            _scan_content(
                metadata,
                scope="history",
                reference=object_id[:12],
                path="<tag-metadata>",
            )
        )
        if separator:
            findings.extend(
                _scan_content(
                    message,
                    scope="history",
                    reference=object_id[:12],
                    path="<tag-message>",
                )
            )
    return findings


def audit_history(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    identities = _git(
        root,
        "log",
        "--all",
        "--format=%H%x00%an%x00%ae%x00%cn%x00%ce",
        text=True,
    )
    assert isinstance(identities, str)
    for row in identities.splitlines():
        fields = row.split("\x00")
        if len(fields) != 5:
            continue
        commit, author_name, author_email, committer_name, committer_email = fields
        findings.extend(
            _identity_findings(
                reference=commit[:12],
                path="<commit-metadata>",
                identities=(
                    (author_name, author_email),
                    (committer_name, committer_email),
                ),
            )
        )

    findings.extend(_audit_tag_objects(root))

    commits = _git(root, "rev-list", "--all", text=True)
    assert isinstance(commits, str)
    scanned_entries: set[tuple[str, str, str]] = set()
    for commit in commits.splitlines():
        message = _git(root, "show", "-s", "--format=%B", "--no-patch", commit)
        assert isinstance(message, bytes)
        findings.extend(
            _scan_content(
                message,
                scope="history",
                reference=commit[:12],
                path="<commit-message>",
            )
        )
        tree = _git(root, "ls-tree", "-r", "--full-tree", "-z", commit)
        assert isinstance(tree, bytes)
        for entry in tree.split(b"\0"):
            if not entry or b"\t" not in entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            parts = metadata.split()
            if len(parts) != 3 or parts[1] != b"blob":
                continue
            blob = parts[2].decode("ascii")
            mode = parts[0]
            relative = raw_path.decode("utf-8", errors="surrogateescape")
            entry_key = (mode.decode("ascii"), blob, relative)
            if entry_key in scanned_entries:
                continue
            scanned_entries.add(entry_key)
            findings.extend(
                _path_findings(scope="history", reference=commit[:12], path=relative)
            )
            if mode == b"120000":
                content = _git(root, "cat-file", "blob", blob)
                assert isinstance(content, bytes)
                target_text = content.decode("utf-8", errors="surrogateescape")
                findings.extend(
                    _path_findings(
                        scope="history",
                        reference=commit[:12],
                        path=target_text,
                    )
                )
                continue
            if "__pycache__" in Path(relative).parts or relative.endswith(".pyc"):
                findings.append(
                    _finding(
                        "history", commit[:12], relative, "python-bytecode", "MEDIUM"
                    )
                )
                continue
            if Path(relative).suffix.lower() in _BINARY_SUFFIXES:
                continue
            content = _git(root, "cat-file", "blob", blob)
            assert isinstance(content, bytes)
            findings.extend(
                _scan_content(
                    content,
                    scope="history",
                    reference=commit[:12],
                    path=relative,
                )
            )
    return findings


def build_report(root: Path, *, history: bool) -> dict[str, Any]:
    findings = audit_history(root) if history else audit_tree(root)
    findings = sorted(
        findings,
        key=lambda item: (
            item["severity"],
            item["scope"],
            item["reference"],
            item["path"],
            item["kind"],
        ),
    )
    return {
        "schema_version": "1.0",
        "scope": "reachable-history" if history else "current-tree",
        "status": "FAIL" if findings else "PASS",
        "finding_count": len(findings),
        "findings": findings,
        "redaction": (
            "Matched values are omitted. Real repository paths are represented by "
            "stable short hashes; only virtual commit/tag locations are named."
        ),
        "limitations": (
            "Pattern scanning cannot prove the mathematical absence of every secret or identity; "
            "review platform caches, forks, clones, and revoked credentials separately."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a redacted repository privacy audit"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="scan all commits reachable from local refs",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = build_report(
            args.repo_root.expanduser().resolve(), history=args.history
        )
    except PrivacyAuditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"privacy audit: {report['status']} ({report['finding_count']} finding(s))"
        )
        for finding in report["findings"]:
            print(
                f"- {finding['severity']} {finding['kind']}: "
                f"{finding['reference']} {finding['path']}"
            )
        print(report["redaction"])
        print(report["limitations"])
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
