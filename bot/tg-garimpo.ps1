# bot/tg-garimpo.ps1 — espelho Windows (PowerShell 5.1+) de bot/tg-garimpo.sh.
# Wrapper de bot\tg-garimpo.py: instancia unica (lock exclusivo), timeout de 300s, log proprio.
# Opt-in: sem telegram_canais.json + credenciais o script Python sai calado.
# Uso: powershell -ExecutionPolicy Bypass -File bot\tg-garimpo.ps1 [-Login]
# Se existir um venv em bot\.venv-tg, ele e usado (pip install telethon la dentro).

[CmdletBinding()]
param([switch]$Login)

$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
$BotDir = Join-Path $BOT_ROOT 'bot'
Set-Location $BotDir
if (-not (Test-Path 'logs')) { New-Item -ItemType Directory -Path 'logs' | Out-Null }

$Py = $null
$venv = Join-Path $BotDir '.venv-tg\Scripts\python.exe'
if (Test-Path $venv) { $Py = $venv }
else {
    foreach ($c in @('python3', 'python', 'py')) {
        $g = Get-Command $c -ErrorAction SilentlyContinue
        if ($g) { $Py = $g.Source; break }
    }
}
if (-not $Py) { Write-Host 'python nao encontrado no PATH'; exit 1 }

$TempDir = $env:TEMP
if ([string]::IsNullOrWhiteSpace($TempDir)) { $TempDir = [System.IO.Path]::GetTempPath() }
try {
    $lock = [System.IO.File]::Open((Join-Path $TempDir 'oportunizavaga-tg.lock'), [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch { exit 0 }

try {
    $script = Join-Path $BotDir 'tg-garimpo.py'
    if ($Login) {
        & $Py $script --login   # interativo: sem timeout
        exit $LASTEXITCODE
    }
    $log = Join-Path $BotDir 'logs\tg-garimpo.log'
    $outFile = [IO.Path]::GetTempFileName()
    $p = Start-Process -FilePath $Py -ArgumentList @("`"$script`"") -NoNewWindow -PassThru `
        -RedirectStandardOutput $outFile -RedirectStandardError "$outFile.err"
    if (-not $p.WaitForExit(300000)) {
        try { $p.Kill() } catch { }
        Add-Content -Path $log -Value ("{0} tg-garimpo: timeout de 300s, abortado" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
    }
    Get-Content $outFile, "$outFile.err" -ErrorAction SilentlyContinue | Add-Content -Path $log
    Remove-Item $outFile, "$outFile.err" -ErrorAction SilentlyContinue
} finally {
    try { $lock.Close(); $lock.Dispose() } catch { }
}
