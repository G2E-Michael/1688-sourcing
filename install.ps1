<#
.SYNOPSIS
  Install the 1688-supplier-finder skill into DSH and/or WorkBuddy.

.EXAMPLE
  pwsh -File .\install.ps1 -Target both
  pwsh -File .\install.ps1 -Target dsh -Force
#>
[CmdletBinding()]
param(
    [ValidateSet('dsh', 'workbuddy', 'both')]
    [string]$Target = 'both',

    # overwrite an existing install
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$SkillName = '1688-supplier-finder'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path (Join-Path $Root 'SKILL.md'))) {
    throw "SKILL.md not found next to install.ps1 — run this from the cloned repo root."
}

function Write-Section($text) {
    Write-Host ''
    Write-Host "== $text" -ForegroundColor Cyan
}

function Install-Skill([string]$Dest, [string]$Label) {
    Write-Section "install -> $Label"
    if (Test-Path $Dest) {
        if (-not $Force) {
            Write-Host "   exists: $Dest" -ForegroundColor Yellow
            Write-Host "   skipped (use -Force to overwrite)" -ForegroundColor Yellow
            return $false
        }
        Write-Host "   replacing existing install"
        Remove-Item $Dest -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    robocopy $Root $Dest /E /XD .git out __pycache__ .venv /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
    Write-Host "   ok: $Dest" -ForegroundColor Green
    return $true
}

function Test-Deps {
    Write-Section 'dependencies'

    $ok = $true

    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        Write-Host ("   node      : " + (& node --version)) -ForegroundColor Green
    } else {
        Write-Host '   node      : MISSING (install Node 20+ from https://nodejs.org)' -ForegroundColor Red
        $ok = $false
    }

    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        Write-Host ("   python    : " + (& python --version 2>&1)) -ForegroundColor Green
    } else {
        Write-Host '   python    : MISSING (install Python 3.10+)' -ForegroundColor Red
        $ok = $false
    }

    $chrome = @(
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe')
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($chrome) {
        Write-Host "   chrome    : $chrome" -ForegroundColor Green
    } else {
        Write-Host '   chrome    : MISSING (the driver uses channel=chrome; install Google Chrome)' -ForegroundColor Red
        $ok = $false
    }

    if ($ok) {
        $cli = $null
        try {
            $root = (& npm root -g 2>$null).Trim()
            if ($root -and (Test-Path (Join-Path $root '1688-cli\dist\cli.js'))) {
                $cli = Join-Path $root '1688-cli\dist\cli.js'
            }
        } catch { }
        if ($cli) {
            Write-Host "   1688-cli  : $cli" -ForegroundColor Green
        } else {
            Write-Host '   1688-cli  : MISSING -> run:  npm i -g 1688-cli' -ForegroundColor Yellow
        }

        $deps = & python -c "import openpyxl, requests, PIL; print('ok')" 2>$null
        if ($deps -eq 'ok') {
            Write-Host '   py deps   : openpyxl / requests / Pillow ok' -ForegroundColor Green
        } else {
            Write-Host '   py deps   : MISSING -> run:  python -m pip install -r requirements.txt' -ForegroundColor Yellow
        }
    }
}

$installed = @()
if ($Target -in @('dsh', 'both')) {
    $dest = Join-Path $env:USERPROFILE ".dsh\skills\$SkillName"
    if (Install-Skill $dest 'DSH') { $installed += $dest }
}
if ($Target -in @('workbuddy', 'both')) {
    $dest = Join-Path $env:USERPROFILE ".workbuddy\skills\$SkillName"
    if (Install-Skill $dest 'WorkBuddy') { $installed += $dest }
}

Test-Deps

Write-Section 'next steps'
if ($installed.Count -eq 0) {
    Write-Host '   nothing installed (use -Force to overwrite an existing copy)' -ForegroundColor Yellow
}
Write-Host '   1) one-time login   :  & "$env:APPDATA\npm\1688.cmd" login --headed'
Write-Host '   2) self check       :  python run.py check'
Write-Host '   3) try it           :  python run.py keyword "<product keyword>" --max 12 --top 6 --enrich 3'
Write-Host '   4) reload client    :  DSH refresh page / WorkBuddy restart or refresh skill list'
Write-Host ''
