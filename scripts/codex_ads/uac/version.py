"""Read the repository/installed version from the canonical VERSION file."""

from __future__ import annotations

import re
from pathlib import Path


_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def read_project_version(module_path: Path | None = None) -> str:
    origin = (module_path or Path(__file__)).resolve()
    candidates = [parent / "VERSION" for parent in origin.parents]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        value = candidate.read_text(encoding="utf-8").strip()
        if _SEMVER.fullmatch(value):
            return value
        return "invalid"
    return "unknown"
