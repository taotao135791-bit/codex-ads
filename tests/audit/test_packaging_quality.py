"""Packaging and install-quality regression tests."""

from __future__ import annotations

import json
import re


def _read(repo_root, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def test_runtime_version_strings_stay_in_sync(repo_root):
    manifest = json.loads(_read(repo_root, ".codex-plugin/plugin.json"))
    version = manifest["version"]

    report = _read(repo_root, "scripts/generate_report.py")
    fetch_page = _read(repo_root, "scripts/fetch_page.py")

    assert f'__version__ = "{version}"' in report
    assert f"CodexAds/{version}" in fetch_page
    assert "github.com/taotao135791-bit/codex-ads" in fetch_page
    assert "github.com/taotao135791-bit/codex-ads" in report


def test_installer_uses_local_venv_without_breaking_system_packages(repo_root):
    install_sh = _read(repo_root, "install.sh")
    install_ps1 = _read(repo_root, "install.ps1")

    assert "--break-system-packages" not in install_sh
    assert "--break-system-packages" not in install_ps1
    assert "python3 -m venv" in install_sh
    assert "-m venv" in install_ps1
    assert ".venv" in install_sh
    assert ".venv" in install_ps1


def test_docs_describe_ads_slash_entries_as_routing_shorthand(repo_root):
    readme = _read(repo_root, "README.md")
    readme_en = _read(repo_root, "README.en.md")
    install_sh = _read(repo_root, "install.sh")

    assert "路由 shorthand" in readme
    assert "不是安装到系统里的 shell 命令" in readme
    assert "Routing Shorthand" in readme_en
    assert "not shell commands" in readme_en
    assert "Ask naturally" in install_sh
    assert "Run commands" not in install_sh


def test_reference_paths_have_installed_fallbacks(repo_root):
    skill_files = sorted((repo_root / "skills").glob("*/SKILL.md"))
    agent_files = sorted((repo_root / "agents").glob("*.md"))
    failures: list[str] = []

    for path in skill_files + agent_files:
        text = path.read_text(encoding="utf-8")
        if "ads/references/" not in text:
            continue
        required = [
            "## Reference Resolution",
            "~/.codex/skills/ads/references/<file>.md",
            "ads/references/<file>.md",
        ]
        missing = [phrase for phrase in required if phrase not in text]
        if missing:
            failures.append(f"{path.relative_to(repo_root)} missing {missing}")

    assert not failures, "shared reference path fallbacks missing:\n" + "\n".join(failures)


def test_gitignore_blocks_generated_python_cache(repo_root):
    gitignore = _read(repo_root, ".gitignore")
    assert "__pycache__/" in gitignore
    assert re.search(r"^\*\.py\[cod\]$", gitignore, re.MULTILINE)


def test_private_dashboard_tool_gate_requires_computer_use(repo_root):
    files = [
        "ads/SKILL.md",
        "skills/ads/SKILL.md",
        "ads/references/computer-use-live-audit.md",
        "skills/ads/references/computer-use-live-audit.md",
        "ads/references/orchestrator.md",
        "skills/ads/references/orchestrator.md",
    ]
    required = [
        "MUST use Computer Use",
        "MUST NOT use Browser Plugin",
        "Playwright",
        "screenshot scripts",
        "page HTML extraction",
        "network scraping",
        "instead of switching to Browser Plugin",
        "public landing pages",
        "do not contain logged-in account data",
    ]

    failures: list[str] = []
    for relative_path in files:
        text = _read(repo_root, relative_path)
        missing = [phrase for phrase in required if phrase not in text]
        if missing:
            failures.append(f"{relative_path} missing {missing}")

    assert not failures, "private dashboard tool gate softened:\n" + "\n".join(failures)
