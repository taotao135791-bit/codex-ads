"""Regression tests for the main Ads router and project-memory templates."""

from __future__ import annotations

import json


def _read(repo_root, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def test_plugin_repository_points_to_actual_repo(repo_root):
    manifest = json.loads(_read(repo_root, ".codex-plugin/plugin.json"))
    assert manifest["repository"] == "https://github.com/taotao135791-bit/codex-ads"


def test_main_ads_skill_stays_lean_router(repo_root):
    text = _read(repo_root, "ads/SKILL.md")
    lines = text.splitlines()

    assert len(lines) <= 180
    assert max(len(line) for line in lines) <= 180
    assert "## Route Table" in text
    assert "references/orchestrator.md" in text
    assert "## Project Memory" in text


def test_raw_sensitive_files_have_reasonable_line_lengths(repo_root):
    for relative_path in ["ads/SKILL.md", "install.sh"]:
        lines = _read(repo_root, relative_path).splitlines()
        long_lines = [(i, len(line)) for i, line in enumerate(lines, 1) if len(line) > 220]
        assert not long_lines, f"{relative_path} has very long raw lines: {long_lines[:5]}"


def test_project_memory_templates_are_wired(repo_root):
    ops_skill = _read(repo_root, "skills/ads-ops/SKILL.md")
    expected_files = [
        "ADS-PROJECT-CONTEXT.md",
        "ADS-OPS-LOG.md",
        "ADS-REPORT-FORMAT.md",
        "project-context-template.md",
        "ops-log-template.md",
        "report-format-template.md",
    ]

    for expected in expected_files:
        assert expected in ops_skill

    for template in [
        "skills/ads-ops/assets/project-context-template.md",
        "skills/ads-ops/assets/ops-log-template.md",
        "skills/ads-ops/assets/report-format-template.md",
    ]:
        assert (repo_root / template).exists()
