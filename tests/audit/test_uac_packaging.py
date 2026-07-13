"""Packaging, routing, and documentation contracts for UAC Experiment Loop."""

from __future__ import annotations

import json


def _read(repo_root, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def test_uac_triggers_route_before_generic_google(repo_root):
    router = _read(repo_root, "skills/ads/SKILL.md")
    app_row = "| UAC, Google App campaigns, 应用安装/应用内行为广告, App tCPA/tROAS | `ads-google-app` |"
    google_row = "| Google Ads, Search, PMax, AI Max, broad match | `ads-google` |"
    assert app_row in router
    assert router.index(app_row) < router.index(google_row)

    description = _read(repo_root, "skills/ads-google-app/SKILL.md").split("---", 2)[1]
    for trigger in [
        "UAC",
        "Google UAC",
        "App campaign",
        "Google App campaigns",
        "应用安装广告",
        "应用内行为广告",
        "tCPA App campaign",
        "tROAS App campaign",
        "Google 应用广告",
    ]:
        assert trigger in description


def test_uac_assets_and_scripts_are_installed(repo_root):
    shell = _read(repo_root, "install.sh")
    powershell = _read(repo_root, "install.ps1")
    for extension in ["*.md", "*.yaml", "*.yml", "*.json"]:
        assert extension in shell
    for extension in ["'.md'", "'.yaml'", "'.yml'", "'.json'"]:
        assert extension in powershell
    assert 'cp "${TEMP_DIR}/codex-ads/scripts/"*.py' in shell
    assert 'Copy-Item "$ScriptsSource\\*.py"' in powershell


def test_uac_version_and_docs_are_present(repo_root):
    manifest = json.loads(_read(repo_root, ".codex-plugin/plugin.json"))
    assert manifest["version"] == "1.8.0"
    assert "UAC" in _read(repo_root, "README.md")
    assert "UAC" in _read(repo_root, "README.en.md")
    assert "## 1.8.0" in _read(repo_root, "CHANGELOG.md")


def test_uac_schema_template_and_example_set_is_complete(repo_root):
    assets = repo_root / "skills" / "ads-google-app" / "assets"
    expected = {
        "UAC-INPUT.example.yaml",
        "ADS-EXPERIMENTS.minimal.yaml",
        "ADS-EXPERIMENTS.full.yaml",
        "ADS-EXPERIMENTS.example.yaml",
        "uac-analysis.schema.json",
        "ads-experiments.schema.json",
    }
    assert expected.issubset({path.name for path in assets.iterdir()})
