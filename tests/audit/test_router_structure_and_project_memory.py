"""Regression tests for the main Ads router and project-memory templates."""

from __future__ import annotations

import json


def _read(repo_root, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def test_plugin_repository_points_to_actual_repo(repo_root):
    manifest = json.loads(_read(repo_root, ".codex-plugin/plugin.json"))
    assert manifest["repository"] == "https://github.com/taotao135791-bit/codex-ads"
    assert manifest["skills"] == "./skills/"
    assert "interface" in manifest
    assert manifest["interface"]["displayName"] == "Codex Ads"
    assert manifest["interface"]["defaultPrompt"]


def test_main_ads_skill_stays_lean_router(repo_root):
    text = _read(repo_root, "ads/SKILL.md")
    lines = text.splitlines()

    assert len(lines) <= 180
    assert max(len(line) for line in lines) <= 180
    assert "## Route Table" in text
    assert "references/orchestrator.md" in text
    assert "## Project Memory" in text
    assert "~/.codex/skills/ads-google/SKILL.md" in text

    frontmatter_description = next(
        line for line in lines if line.startswith("description:")
    )
    for trigger in ["广告账户审计", "日报/周报", "甲方模板", "每日巡检", "KPI受限诊断"]:
        assert trigger in frontmatter_description


def test_raw_sensitive_files_have_reasonable_line_lengths(repo_root):
    for relative_path in ["ads/SKILL.md", "install.sh"]:
        lines = _read(repo_root, relative_path).splitlines()
        long_lines = [(i, len(line)) for i, line in enumerate(lines, 1) if len(line) > 220]
        assert not long_lines, f"{relative_path} has very long raw lines: {long_lines[:5]}"


def test_plugin_ads_entry_matches_legacy_raw_entry(repo_root):
    assert _read(repo_root, "skills/ads/SKILL.md") == _read(repo_root, "ads/SKILL.md")

    legacy_refs = sorted((repo_root / "ads" / "references").glob("*.md"))
    plugin_refs = sorted((repo_root / "skills" / "ads" / "references").glob("*.md"))
    assert [path.name for path in plugin_refs] == [path.name for path in legacy_refs]

    for legacy_path in legacy_refs:
        plugin_path = repo_root / "skills" / "ads" / "references" / legacy_path.name
        assert plugin_path.read_text(encoding="utf-8") == legacy_path.read_text(
            encoding="utf-8"
        )


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
    assert "assets/` directory next to this `SKILL.md`" in ops_skill

    for template in [
        "skills/ads-ops/assets/project-context-template.md",
        "skills/ads-ops/assets/ops-log-template.md",
        "skills/ads-ops/assets/report-format-template.md",
    ]:
        assert (repo_root / template).exists()
