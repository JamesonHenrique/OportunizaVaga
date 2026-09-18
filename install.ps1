# install.ps1 — one-line installer for OportunizaVaga (Windows, PowerShell 5.1+).
# Usage:
#   irm https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.ps1 | iex
#   # custom dir:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/JamesonHenrique/OportunizaVaga/main/install.ps1))) "$HOME\my-bot"
# Clones the repo to $HOME\oportunizavaga (or $args[0]) and runs scripts\setup.ps1.
# Safe: never overwrites an existing checkout, never commits anything.
# Requires PowerShell 5.1+.

$ErrorActionPreference = 'Stop'
$REPO_URL = 'https://github.com/JamesonHenrique/OportunizaVaga'
$DEST = if ($args.Count -ge 1 -and $args[0]) { $args[0] } else { Join-Path $HOME 'oportunizavaga' }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host '[!!] git not found — install git first (https://git-scm.com) and rerun.'
    exit 1
}

if (Test-Path $DEST) {
    if (Test-Path (Join-Path $DEST '.git')) {
        Write-Host ("[ok] existing checkout at {0} — pulling latest." -f $DEST)
        & git -C $DEST pull --ff-only
        if ($LASTEXITCODE -ne 0) { Write-Host ("[!!] git pull failed in {0}." -f $DEST); exit 1 }
    } else {
        Write-Host ("[!!] {0} exists but is not a git checkout — pass another directory." -f $DEST)
        exit 1
    }
} else {
    Write-Host ("[..] cloning {0} to {1} ..." -f $REPO_URL, $DEST)
    & git clone $REPO_URL $DEST
    if ($LASTEXITCODE -ne 0) { Write-Host '[!!] git clone failed.'; exit 1 }
}

Write-Host '[..] running setup ...'
powershell -ExecutionPolicy Bypass -File (Join-Path $DEST 'scripts\setup.ps1')
Write-Host ''
Write-Host ("Next: fill in {0} (never commit it)" -f (Join-Path $DEST 'bot\dados_candidato.json'))
Write-Host ("and follow docs/QUICKSTART.md inside {0}." -f $DEST)
