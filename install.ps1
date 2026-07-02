#Requires -Version 5.1
<#
.SYNOPSIS
    Codex Ads Installer for Windows (multi-host).
.DESCRIPTION
    Installs the Codex Ads skill, sub-skills, agents, and reference files
    for Codex CLI (default) or any of the supported experimental host CLIs.

    Targets:
      codex      OpenAI Codex CLI
      cursor     Cursor IDE (experimental)
      windsurf   Windsurf IDE (experimental)
      gemini     Gemini CLI (experimental)
      goose      Goose CLI (experimental)
.PARAMETER Target
    Which host CLI to install for. Default: codex.
.PARAMETER SkillDir
    Override the target's default skill install root.
.PARAMETER AgentDir
    Override the target's default agent install root.
.EXAMPLE
    .\install.ps1
.EXAMPLE
    .\install.ps1 -Target codex
.EXAMPLE
    .\install.ps1 -SkillDir C:\Custom\Skills
#>

param(
    [ValidateSet('codex','cursor','windsurf','gemini','goose')]
    [string]$Target = 'codex',
    [string]$SkillDir = '',
    [string]$AgentDir = ''
)

$ErrorActionPreference = "Stop"

function Resolve-TargetPaths {
    param([string]$T)
    switch ($T) {
        'codex' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".codex\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".codex\agents"
                AllowPip  = $true
                Label     = "OpenAI Codex CLI"
            }
        }
        'cursor' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".cursor\extensions\codex-ads\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".cursor\extensions\codex-ads\agents"
                AllowPip  = $false
                Label     = "Cursor IDE"
            }
        }
        'windsurf' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".windsurf\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".windsurf\agents"
                AllowPip  = $false
                Label     = "Windsurf IDE"
            }
        }
        'gemini' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".gemini\extensions\codex-ads\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".gemini\extensions\codex-ads\agents"
                AllowPip  = $false
                Label     = "Gemini CLI"
            }
        }
        'goose' {
            return @{
                SkillBase = Join-Path $env:USERPROFILE ".config\goose\skills"
                AgentDir  = Join-Path $env:USERPROFILE ".config\goose\agents"
                AllowPip  = $false
                Label     = "Goose CLI"
            }
        }
        default {
            throw "Unknown target: $T"
        }
    }
}

function Test-InstallPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if ($Path -match '[\;\&\|\$\(\)\<\>\`]') { return $false }
    if ($Path -match '\.\.') { return $false }
    if ($Path -match '^[-]') { return $false }
    if ($Path -match '^(\\\\|//)') { return $false }   # UNC paths
    return $true
}

function Main {
    $paths = Resolve-TargetPaths -T $Target
    $SkillBase = $paths.SkillBase
    $AgentDirResolved = $paths.AgentDir
    $AllowPip = $paths.AllowPip
    $HostLabel = $paths.Label

    if ($SkillDir) {
        if (-not (Test-InstallPath -Path $SkillDir)) {
            Write-Host "X Invalid -SkillDir: contains forbidden characters or traversal" -ForegroundColor Red
            exit 1
        }
        $SkillBase = $SkillDir
    }
    if ($AgentDir) {
        if (-not (Test-InstallPath -Path $AgentDir)) {
            Write-Host "X Invalid -AgentDir: contains forbidden characters or traversal" -ForegroundColor Red
            exit 1
        }
        $AgentDirResolved = $AgentDir
    }

    $SkillDirResolved = Join-Path $SkillBase "ads"
    $RepoUrl = "https://github.com/taotao135791-bit/codex-ads.git"

    Write-Host "=================================="
    Write-Host "   Codex Ads - Installer"
    Write-Host "   Target: $HostLabel"
    Write-Host "=================================="
    Write-Host ""

    # Check prerequisites
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Host "X Git is required but not installed." -ForegroundColor Red
        exit 1
    }
    Write-Host "OK Git detected" -ForegroundColor Green

    # Create directories
    New-Item -ItemType Directory -Path (Join-Path $SkillDirResolved "references") -Force | Out-Null
    New-Item -ItemType Directory -Path $AgentDirResolved -Force | Out-Null

    # Clone to temp directory
    $TempDir = Join-Path $env:TEMP "codex-ads-install-$(Get-Random)"
    Write-Host "Downloading Codex Ads..."

    try {
        # Temporarily allow stderr (git writes progress to stderr — treated as error in PS 5.1)
        $ErrorActionPreference = "Continue"
        $CloneOutput = git clone --depth 1 $RepoUrl "$TempDir\codex-ads" 2>&1
        $ErrorActionPreference = "Stop"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "X Failed to clone Codex Ads from $RepoUrl" -ForegroundColor Red
            Write-Host "  Check that the repository exists and that you have access." -ForegroundColor Yellow
            $CloneOutput | ForEach-Object { Write-Host "  $_" }
            exit 1
        }

        # Copy main skill + references from the plugin-compatible skill tree.
        Write-Host "Installing skill files..."
        Copy-Item "$TempDir\codex-ads\skills\ads\SKILL.md" -Destination "$SkillDirResolved\SKILL.md" -Force
        Copy-Item "$TempDir\codex-ads\skills\ads\references\*.md" -Destination "$SkillDirResolved\references\" -Force

        # Copy sub-skills
        Write-Host "Installing sub-skills..."
        Get-ChildItem "$TempDir\codex-ads\skills" -Directory | ForEach-Object {
            if ($_.Name -eq "ads") {
                return
            }
            $TargetDir = Join-Path $SkillBase $_.Name
            New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
            Copy-Item (Join-Path $_.FullName "SKILL.md") -Destination "$TargetDir\SKILL.md" -Force

            # Copy assets/templates if they exist
            $AssetsDir = Join-Path $_.FullName "assets"
            if (Test-Path $AssetsDir) {
                $TargetAssets = Join-Path $TargetDir "assets"
                New-Item -ItemType Directory -Path $TargetAssets -Force | Out-Null
                Copy-Item "$AssetsDir\*.md" -Destination "$TargetAssets\" -Force
            }
        }

        # Copy agents
        Write-Host "Installing subagents..."
        Copy-Item "$TempDir\codex-ads\agents\*.md" -Destination "$AgentDirResolved\" -Force

        # Copy scripts (optional Python tools)
        $ScriptsSource = "$TempDir\codex-ads\scripts"
        if (Test-Path $ScriptsSource) {
            Write-Host "Installing Python scripts..."
            $ScriptsDir = Join-Path $SkillDirResolved "scripts"
            New-Item -ItemType Directory -Path $ScriptsDir -Force | Out-Null
            Copy-Item "$ScriptsSource\*.py" -Destination "$ScriptsDir\" -Force
            Copy-Item "$TempDir\codex-ads\requirements.txt" -Destination "$SkillDirResolved\requirements.txt" -Force
        }

        Write-Host ""
        if ($AllowPip) {
            Write-Host "Installing Python dependencies..."
            $ErrorActionPreference = "Continue"
            pip install -q -r "$SkillDirResolved\requirements.txt" 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  OK Python dependencies installed" -ForegroundColor Green
            } else {
                Write-Host "  Warning: pip install failed. Run manually: pip install -r $SkillDirResolved\requirements.txt" -ForegroundColor Yellow
            }
            $ErrorActionPreference = "Stop"
        } else {
            Write-Host "i  Skipping Python dependencies - $HostLabel host runtime may not execute Python skills directly." -ForegroundColor Yellow
            Write-Host "   If you need PDF reports / landing-page analysis / screenshots, install manually:"
            Write-Host "     pip install -r $SkillDirResolved\requirements.txt"
        }

        Write-Host ""
        Write-Host "i  Image generation uses scripts/generate_image.py with ADS_IMAGE_PROVIDER." -ForegroundColor Yellow
        Write-Host "   Set GOOGLE_API_KEY, OPENAI_API_KEY, STABILITY_API_KEY, or REPLICATE_API_TOKEN as needed."

        Write-Host ""
        Write-Host "Codex Ads installed successfully for $HostLabel!" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Installed to:"
        Write-Host "    Skills: $SkillBase"
        Write-Host "    Agents: $AgentDirResolved"
        Write-Host ""
        Write-Host "  Bundled:"
        Write-Host "    - 1 main skill (ads orchestrator)"
        Write-Host "    - 25 sub-skills (platform + functional + creative + agency ops)"
        Write-Host "    - 10 agents (6 audit + 4 creative)"
        Write-Host "    - 28 reference files"
        Write-Host "    - 15 templates (12 industry + 3 ops memory)"
        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  1. Start your host CLI"
        Write-Host "  2. Run commands:       /ads audit"
        Write-Host "                         /ads plan saas"
        Write-Host "                         /ads google"
        Write-Host ""
        Write-Host "To uninstall: .\uninstall.ps1 -Target $Target"
    }
    finally {
        # Cleanup temp directory
        if (Test-Path $TempDir) {
            Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Main
