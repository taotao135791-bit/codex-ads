#!/usr/bin/env python3
"""Redacted secret/identity checks for the current tree or reachable history.

Findings report only a location and category. Matched values are never printed,
which makes this suitable for release logs and CI output.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
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
    ("aws-access-key", "HIGH", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("google-api-key", "HIGH", re.compile(rb"AIza[0-9A-Za-z_-]{30,}")),
    (
        "private-key",
        "HIGH",
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "mac-home-path",
        "MEDIUM",
        re.compile(rb"/Users/(?!example(?:/|$)|username(?:/|$)|<)[^/\s]+/"),
    ),
    (
        "windows-home-path",
        "MEDIUM",
        re.compile(
            rb"[A-Za-z]:\\Users\\(?!example(?:\\|$)|username(?:\\|$)|<)[^\\\s]+\\"
        ),
    ),
)

_EMAIL = re.compile(
    rb"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9.-])"
)
_SAFE_EMAIL_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
    "example.invalid",
    "users.noreply.github.com",
}
_CREDENTIALED_URL = re.compile(rb"https?://[^\s/:@]+:[^\s/@]+@(?P<host>[^\s/:]+)")
_RESERVED_URL_HOSTS = {
    "example.com",
    "example.net",
    "example.org",
    "host",
    "localhost",
}
_INTENTIONAL_DETECTOR_PATHS = {
    ("mac-home-path", "scripts/privacy_doctor.py"),
}


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
        "path": path,
        "kind": kind,
        "severity": severity,
    }


def _scan_content(
    content: bytes, *, scope: str, reference: str, path: str
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for kind, severity, pattern in _CONTENT_PATTERNS:
        if pattern.search(content) and (kind, path) not in _INTENTIONAL_DETECTOR_PATHS:
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
        if not path.is_file() or path.is_symlink():
            continue
        if "__pycache__" in path.parts or path.suffix.lower() == ".pyc":
            findings.append(
                _finding("tree", "WORKTREE", relative, "python-bytecode", "MEDIUM")
            )
            continue
        if path.name in {".env", ".env.local", ".env.production"}:
            findings.append(
                _finding("tree", "WORKTREE", relative, "environment-file", "HIGH")
            )
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


def audit_history(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    identities = _git(
        root,
        "log",
        "--all",
        "--format=%H%x00%ae%x00%ce",
        text=True,
    )
    assert isinstance(identities, str)
    for row in identities.splitlines():
        fields = row.split("\x00")
        if len(fields) != 3:
            continue
        commit, author_email, committer_email = fields
        if _unsafe_identity(author_email) or _unsafe_identity(committer_email):
            findings.append(
                _finding(
                    "history",
                    commit[:12],
                    "<commit-metadata>",
                    "non-noreply-identity",
                    "HIGH",
                )
            )

    commits = _git(root, "rev-list", "--all", text=True)
    assert isinstance(commits, str)
    scanned_blobs: set[str] = set()
    for commit in commits.splitlines():
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
            if blob in scanned_blobs:
                continue
            scanned_blobs.add(blob)
            relative = raw_path.decode("utf-8", errors="surrogateescape")
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
        "redaction": "Matched values are intentionally omitted.",
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
