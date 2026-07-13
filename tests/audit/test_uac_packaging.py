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
        "/ads decide",
        "AC2.0",
        "AC2.5",
        "AC3.0",
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
    assert 'Copy-Item (Join-Path $ScriptsSource "*.py")' in powershell
    assert "find \"${skill_dir}references\" -type f -name '*.md' -print0" in shell
    assert "Get-ChildItem -LiteralPath $SubskillReferences -File -Recurse" in powershell
    assert "$_.Extension -eq '.md' -and -not $_.LinkType" in powershell


def test_uac_natural_language_workflow_contract(repo_root):
    workflow_path = (
        repo_root / "skills" / "ads-google-app" / "references" / "agent-workflow.md"
    )
    assert workflow_path.is_file()
    workflow = workflow_path.read_text(encoding="utf-8")

    for heading in [
        "Intent 0: make a Quick Decision",
        "Intent 1: initialize a UAC project",
        "Intent 2: analyze the current period",
        "Intent 3: create an experiment draft",
        "Intent 4: record actual execution",
        "Intent 5: review the current experiment",
    ]:
        assert heading in workflow

    for command in [
        "decide",
        "init-workspace",
        "normalize",
        "doctor --workspace",
        "analyze",
        "validate-ledger",
        "review-ledger",
        "--append-experiment",
    ]:
        assert command in workflow

    assert "Do not write it to the ledger yet." in workflow
    assert "two different gates" in workflow
    assert "unfinished experiment" in workflow
    assert "YAML, schemas, or CLI syntax" in workflow

    skill = _read(repo_root, "skills/ads-google-app/SKILL.md")
    router = _read(repo_root, "skills/ads/SKILL.md")
    assert "references/agent-workflow.md" in skill
    assert "references/quick-ops.md" in skill
    assert "references/agent-workflow.md" in router
    assert "references/quick-ops.md" in router
    assert "Do not append it to the ledger" in workflow


def test_readmes_document_capability_maturity_without_equating_platforms(repo_root):
    readme = _read(repo_root, "README.md")
    readme_en = _read(repo_root, "README.en.md")

    for maturity in [
        "Deterministic Workflow",
        "Structured Agent Workflow",
        "Advisory",
        "Supporting Tools",
    ]:
        assert maturity in readme
        assert maturity in readme_en

    for deterministic_capability in [
        "Schema 校验",
        "measurement state",
        "experiment admission",
        "Privacy Doctor",
        "Router 同步",
    ]:
        assert deterministic_capability in readme

    assert "没有与 UAC 等价的确定性实验引擎" in readme
    assert "no deterministic experiment engine equivalent to UAC" in readme_en
    assert "## 无法保证的内容" in readme
    assert "## What Codex Ads cannot guarantee" in readme_en


def test_operator_docs_prefer_private_workspace_without_hiding_stop_condition(
    repo_root,
):
    documents = [
        _read(repo_root, "README.md"),
        _read(repo_root, "README.en.md"),
        _read(repo_root, "QUICKSTART.zh-CN.md"),
        _read(repo_root, "QUICKSTART.en.md"),
    ]
    for document in documents:
        for command in [
            "init-workspace my-uac-project",
            'normalize --workspace "workspaces/my-uac-project"',
            'doctor --workspace "workspaces/my-uac-project"',
            'analyze --workspace "workspaces/my-uac-project"',
        ]:
            assert command in document
        assert "UAC-INPUT.yaml" in document
        assert "draft" in document.lower()


def test_uac_version_and_docs_are_present(repo_root):
    manifest = json.loads(_read(repo_root, ".codex-plugin/plugin.json"))
    version = _read(repo_root, "VERSION").strip()
    assert manifest["version"] == version == "1.9.1"
    assert "UAC" in _read(repo_root, "README.md")
    assert "UAC" in _read(repo_root, "README.en.md")
    assert f"## {version}" in _read(repo_root, "CHANGELOG.md")


def test_uac_schema_template_and_example_set_is_complete(repo_root):
    assets = repo_root / "skills" / "ads-google-app" / "assets"
    expected = {
        "UAC-INPUT.example.yaml",
        "UAC-QUICK-OPS.example.yaml",
        "ADS-EXPERIMENTS.minimal.yaml",
        "ADS-EXPERIMENTS.full.yaml",
        "ADS-EXPERIMENTS.example.yaml",
        "uac-analysis.schema.json",
        "uac-quick-decision.schema.json",
        "ads-experiments.schema.json",
        "ads-experiments-v1.0.schema.json",
    }
    assert expected.issubset({path.name for path in assets.iterdir()})
