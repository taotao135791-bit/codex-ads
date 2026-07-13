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
.PARAMETER Ref
    Install one exact final release tag, for example v1.8.3.
.EXAMPLE
    .\install.ps1
.EXAMPLE
    .\install.ps1 -Target codex
.EXAMPLE
    .\install.ps1 -SkillDir C:\Custom\Skills
.EXAMPLE
    .\install.ps1 -Ref v1.8.3
#>

param(
    [ValidateSet('codex','cursor','windsurf','gemini','goose')]
    [string]$Target = 'codex',
    [string]$SkillDir = '',
    [string]$AgentDir = '',
    [ValidatePattern('^v[0-9]+\.[0-9]+\.[0-9]+$')]
    [string]$Ref
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
    if ($Path -match '(^|[\\/])\.\.([\\/]|$)') { return $false }
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
    # The environment override supports packaging smoke tests and downstream
    # mirrors. Normal installs keep using the canonical repository.
    $RepoUrl = if ($env:CODEX_ADS_REPO_URL) {
        $env:CODEX_ADS_REPO_URL
    } else {
        "https://github.com/taotao135791-bit/codex-ads.git"
    }

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
    if ($Ref) {
        Write-Host "Downloading Codex Ads $Ref..."
    } else {
        Write-Host "Downloading Codex Ads..."
    }

    try {
        # Temporarily allow stderr (git writes progress to stderr — treated as error in PS 5.1)
        $ErrorActionPreference = "Continue"
        $SourceDir = Join-Path $TempDir "codex-ads"
        if ($Ref) {
            New-Item -ItemType Directory -Path $SourceDir -Force | Out-Null
            git -C $SourceDir init --quiet 2>&1 | Out-Null
            $FetchOutput = git -C $SourceDir fetch --depth 1 --no-tags -- $RepoUrl "refs/tags/${Ref}:refs/tags/${Ref}" 2>&1
            $FetchExitCode = $LASTEXITCODE
            if ($FetchExitCode -ne 0) {
                $ErrorActionPreference = "Stop"
                Write-Host "X Ref $Ref does not resolve to a release tag" -ForegroundColor Red
                $FetchOutput | ForEach-Object { Write-Host "  $_" }
                exit 1
            }
            git -C $SourceDir show-ref --verify --quiet "refs/tags/$Ref"
            $TagExitCode = $LASTEXITCODE
            if ($TagExitCode -ne 0) {
                $ErrorActionPreference = "Stop"
                Write-Host "X Ref $Ref does not resolve to a release tag" -ForegroundColor Red
                exit 1
            }
            git -C $SourceDir checkout --quiet --detach "refs/tags/${Ref}^{commit}" 2>&1 | Out-Null
            $CheckoutExitCode = $LASTEXITCODE
            $HeadCommit = git -C $SourceDir rev-parse --verify 'HEAD^{commit}' 2>$null
            $HeadExitCode = $LASTEXITCODE
            $TagCommit = git -C $SourceDir rev-parse --verify "refs/tags/${Ref}^{commit}" 2>$null
            $TagCommitExitCode = $LASTEXITCODE
            $ErrorActionPreference = "Stop"
            if (
                $CheckoutExitCode -ne 0 -or
                $HeadExitCode -ne 0 -or
                $TagCommitExitCode -ne 0 -or
                "$HeadCommit".Trim() -ne "$TagCommit".Trim()
            ) {
                Write-Host "X Checked-out commit does not match tag $Ref" -ForegroundColor Red
                exit 1
            }
        } else {
            $CloneOutput = git clone --depth 1 -- $RepoUrl $SourceDir 2>&1
            $CloneExitCode = $LASTEXITCODE
            $ErrorActionPreference = "Stop"
            if ($CloneExitCode -ne 0) {
                Write-Host "X Failed to clone Codex Ads from $RepoUrl" -ForegroundColor Red
                Write-Host "  Check that the repository exists and that you have access." -ForegroundColor Yellow
                $CloneOutput | ForEach-Object { Write-Host "  $_" }
                exit 1
            }
        }

        # Copy main skill + references from the plugin-compatible skill tree.
        Write-Host "Installing skill files..."
        $SkillsSource = Join-Path $SourceDir "skills"
        $AdsSource = Join-Path $SkillsSource "ads"
        $ReferencesSource = Join-Path $AdsSource "references"
        $ReferencesTarget = Join-Path $SkillDirResolved "references"
        Copy-Item (Join-Path $AdsSource "SKILL.md") -Destination (Join-Path $SkillDirResolved "SKILL.md") -Force
        Copy-Item (Join-Path $ReferencesSource "*.md") -Destination $ReferencesTarget -Force
        Copy-Item (Join-Path $SourceDir "VERSION") -Destination (Join-Path $SkillDirResolved "VERSION") -Force

        # Copy sub-skills
        Write-Host "Installing sub-skills..."
        Get-ChildItem $SkillsSource -Directory | ForEach-Object {
            if ($_.Name -eq "ads") {
                return
            }
            $TargetDir = Join-Path $SkillBase $_.Name
            New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
            Copy-Item (Join-Path $_.FullName "SKILL.md") -Destination (Join-Path $TargetDir "SKILL.md") -Force

            # Copy the supported asset/template formats. UAC experiment
            # ledgers and schemas require YAML/JSON as well as Markdown.
            $AssetsDir = Join-Path $_.FullName "assets"
            if (Test-Path $AssetsDir) {
                $TargetAssets = Join-Path $TargetDir "assets"
                New-Item -ItemType Directory -Path $TargetAssets -Force | Out-Null
                Get-ChildItem $AssetsDir -File | Where-Object {
                    $_.Extension -in '.md', '.yaml', '.yml', '.json'
                } | ForEach-Object {
                    Copy-Item $_.FullName -Destination $TargetAssets -Force
                }
            }
        }

        # Copy agents
        Write-Host "Installing subagents..."
        $AgentsSource = Join-Path $SourceDir "agents"
        Copy-Item (Join-Path $AgentsSource "*.md") -Destination $AgentDirResolved -Force

        # Copy scripts (optional Python tools)
        $ScriptsSource = Join-Path $SourceDir "scripts"
        if (Test-Path $ScriptsSource) {
            Write-Host "Installing Python scripts..."
            $ScriptsDir = Join-Path $SkillDirResolved "scripts"
            New-Item -ItemType Directory -Path $ScriptsDir -Force | Out-Null
            Copy-Item (Join-Path $ScriptsSource "*.py") -Destination $ScriptsDir -Force
            $InternalPackage = Join-Path $ScriptsSource "codex_ads"
            if (Test-Path $InternalPackage) {
                Copy-Item $InternalPackage -Destination $ScriptsDir -Recurse -Force
            }
            Copy-Item (Join-Path $SourceDir "requirements.txt") -Destination (Join-Path $SkillDirResolved "requirements.txt") -Force
        }

        Write-Host ""
        if ($AllowPip) {
            Write-Host "Installing Python dependencies into local skill venv..."
            $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
            if (-not $PythonCmd) {
                $PythonCmd = Get-Command py -ErrorAction SilentlyContinue
            }
            if ($PythonCmd) {
                $VenvDir = Join-Path $SkillDirResolved ".venv"
                $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
                $ErrorActionPreference = "Continue"
                & $PythonCmd.Source -m venv $VenvDir 2>$null
                if (($LASTEXITCODE -eq 0) -and (Test-Path $VenvPython)) {
                    & $VenvPython -m pip install -q --upgrade pip 2>$null
                    & $VenvPython -m pip install -q -r "$SkillDirResolved\requirements.txt" 2>$null
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "  OK Python dependencies installed in $VenvDir" -ForegroundColor Green
                        Write-Host "  Use: $VenvPython $SkillDirResolved\scripts\<script>.py"
                    } else {
                        Write-Host "  Warning: venv pip install failed. Run manually:" -ForegroundColor Yellow
                        Write-Host "    $VenvPython -m pip install -r $SkillDirResolved\requirements.txt"
                    }
                } else {
                    Write-Host "  Warning: python -m venv failed. Install deps in your preferred environment:" -ForegroundColor Yellow
                    Write-Host "    python -m pip install -r $SkillDirResolved\requirements.txt"
                }
                $ErrorActionPreference = "Stop"
            } else {
                Write-Host "  Warning: python not found. Install deps in your preferred environment:" -ForegroundColor Yellow
                Write-Host "    python -m pip install -r $SkillDirResolved\requirements.txt"
            }
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
        Write-Host "    - 26 sub-skills (platform + functional + creative + agency ops)"
        Write-Host "    - 10 agents (6 audit + 4 creative)"
        Write-Host "    - 28 reference files"
        Write-Host "    - 15 templates (12 industry + 3 ops memory)"
        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  1. Start your host CLI"
        Write-Host "  2. Ask naturally, for example:"
        Write-Host "       Read-only review this ad account. Check KPI, spend pacing, conversion goals, and today's actions."
        Write-Host "       Or use shorthand: /ads audit, /ads plan saas, /ads google"
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
