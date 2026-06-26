#Requires -Version 5.1
<#
.SYNOPSIS
    Codex Ads Uninstaller for Windows (multi-host).
.DESCRIPTION
    Removes every ads-* sub-skill directory plus the orchestrator and bundled
    agents from the chosen host's install root. Uses glob discovery so new
    sub-skills don't require uninstaller updates.
.PARAMETER Target
    Which host CLI to uninstall from. Default: codex.
#>

param(
    [ValidateSet('codex','cursor','windsurf','gemini','goose')]
    [string]$Target = 'codex'
)

$ErrorActionPreference = "Stop"

function Resolve-TargetPaths {
    param([string]$T)
    switch ($T) {
        'codex'    { return @{ SkillBase = Join-Path $env:USERPROFILE ".codex\skills";                                 AgentDir = Join-Path $env:USERPROFILE ".codex\agents" } }
        'cursor'   { return @{ SkillBase = Join-Path $env:USERPROFILE ".cursor\extensions\codex-ads\skills";          AgentDir = Join-Path $env:USERPROFILE ".cursor\extensions\codex-ads\agents" } }
        'windsurf' { return @{ SkillBase = Join-Path $env:USERPROFILE ".windsurf\skills";                              AgentDir = Join-Path $env:USERPROFILE ".windsurf\agents" } }
        'gemini'   { return @{ SkillBase = Join-Path $env:USERPROFILE ".gemini\extensions\codex-ads\skills";          AgentDir = Join-Path $env:USERPROFILE ".gemini\extensions\codex-ads\agents" } }
        'goose'    { return @{ SkillBase = Join-Path $env:USERPROFILE ".config\goose\skills";                          AgentDir = Join-Path $env:USERPROFILE ".config\goose\agents" } }
        default    { throw "Unknown target: $T" }
    }
}

function Main {
    $paths = Resolve-TargetPaths -T $Target
    $SkillBase = $paths.SkillBase
    $AgentDir = $paths.AgentDir

    Write-Host "Uninstalling Codex Ads from $SkillBase and $AgentDir..."

    # Remove orchestrator
    $MainSkill = Join-Path $SkillBase "ads"
    if (Test-Path $MainSkill) {
        Remove-Item -Path $MainSkill -Recurse -Force
    }

    # Remove all ads-* sub-skills via glob
    if (Test-Path $SkillBase) {
        Get-ChildItem -Path $SkillBase -Directory -Filter "ads-*" -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -Path $_.FullName -Recurse -Force
        }
    }

    # Remove bundled audit + creative agents.
    # NOTE: Keep this list in sync with the contents of `agents/` in the repo.
    # install.ps1 uses `Copy-Item agents\*.md` so any new agent file added
    # there must also be appended below. Pre-v1.7.1 the list contained
    # non-existent entries (audit-amazon, audit-attribution, audit-server-side)
    # and missed the actual shipped agents.
    $Agents = @(
        "audit-budget", "audit-compliance", "audit-creative",
        "audit-google", "audit-meta", "audit-tracking",
        "copy-writer", "creative-strategist", "format-adapter", "visual-designer"
    )
    foreach ($agent in $Agents) {
        $AgentPath = Join-Path $AgentDir "$agent.md"
        if (Test-Path $AgentPath) {
            Remove-Item -Path $AgentPath -Force
        }
    }

    Write-Host "[OK] Codex Ads uninstalled." -ForegroundColor Green
}

Main
