# scripts/monitor-keepalive.ps1 — espelho Windows de scripts/monitor-keepalive.sh.
# Mantem SO o publisher do monitor de pe (heartbeat + quota-daemon).
# Sem Task Scheduler nao ha supervisor: agende este script a cada 5min.
# NAO sobe o loop nem o Chrome (dono deles: bot/guardiao.ps1). O pull-monitor.ps1
# apenas derruba o publisher quando o codigo muda; este o ressobe na proxima passada.
# Sem LINKEDIN, sem systemd — so processos locais via Get-CimInstance.

$ErrorActionPreference = 'SilentlyContinue'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
$REPO = Join-Path $BOT_ROOT 'monitor'
$PUB = Join-Path $REPO 'publish-status.mjs'
$QUOTA = Join-Path $REPO 'quota-daemon.mjs'
$LOG = Join-Path $BOT_ROOT 'monitor-keepalive.log'

$NodeCmd = Get-Command node -ErrorAction SilentlyContinue
$NODE = $null
if ($NodeCmd) { $NODE = $NodeCmd.Source }
if ([string]::IsNullOrWhiteSpace($NODE)) { $NODE = 'node' }

if ([string]::IsNullOrWhiteSpace($env:MONITOR_URL)) { $env:MONITOR_URL = 'https://sua-url.vercel.app' }
$env:CANDIDATURAS_ROOT = (Join-Path $BOT_ROOT 'bot')
if ([string]::IsNullOrWhiteSpace($env:BOT_TZ)) { $env:BOT_TZ = 'America/Sao_Paulo' }

function Write-Stamp { return (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz') }

function Test-Running([string]$fragment) {
    try {
        $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like ("*{0}*" -f $fragment) }
        if ($procs) { return $true }
    } catch { }
    return $false
}

function Start-NodeScript([string]$script, [string]$label) {
    $psiArgs = @('-ExecutionPolicy', 'Bypass', '-Command', ("& '{0}' '{1}'" -f $NODE, $script))
    Start-Process -FilePath 'powershell' -ArgumentList $psiArgs -WindowStyle Hidden
    Add-Content -Path $LOG -Value ("{0} {1} fora, subindo com {2}" -f (Write-Stamp), $label, $NODE)
}

if (-not (Test-Running 'publish-status.mjs')) {
    Set-Location $REPO
    Start-NodeScript $PUB 'publisher'
}

if (-not (Test-Running 'quota-daemon.mjs')) {
    Set-Location $REPO
    Start-NodeScript $QUOTA 'quota-daemon'
}
