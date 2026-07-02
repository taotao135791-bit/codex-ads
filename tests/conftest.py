"""Pytest configuration for the codex-ads eval harness.

Shared fixtures:
- ``repo_root``        — path to the repo root
- ``check_catalog``    — parsed dict from fixtures/check-catalog.yaml
- ``creative_evals``   — parsed list from evals/creative-evals.json
- ``skill_descriptions`` — dict mapping skill name → description text (extracted
  from every SKILL.md frontmatter)

These are session-scoped to keep test runs fast even as the harness grows.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def check_catalog() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("pyyaml not installed; run `pip install -r requirements-dev.txt`")
    catalog_path = REPO_ROOT / "tests" / "fixtures" / "check-catalog.yaml"
    return yaml.safe_load(catalog_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def creative_evals() -> list[dict]:
    evals_path = REPO_ROOT / "evals" / "creative-evals.json"
    return json.loads(evals_path.read_text(encoding="utf-8"))


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    """Parse SKILL.md frontmatter with YAML semantics.

    Skill descriptions may use block scalars to keep raw files readable.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    parsed = yaml.safe_load(m.group(1))
    return parsed if isinstance(parsed, dict) else {}


@pytest.fixture(scope="session")
def skill_descriptions() -> dict[str, str]:
    """Returns {skill_name: description_text} for every SKILL.md under ads/ and skills/."""
    skill_files = [REPO_ROOT / "ads" / "SKILL.md"] + sorted(
        (REPO_ROOT / "skills").glob("*/SKILL.md")
    )
    result: dict[str, str] = {}
    for path in skill_files:
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if "name" in fm and "description" in fm:
            result[fm["name"]] = fm["description"]
    return result
