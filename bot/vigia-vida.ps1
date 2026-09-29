# bot/vigia-vida.ps1 - espelho Windows de bot/vigia-vida.sh (dead man's switch do robo).
# Task Scheduler a cada 15 min. Avisa no Telegram (scripts/notificar.ps1) quando:
#   1. o loop.ps1 NAO esta rodando em 2 checagens seguidas (o guardiao religa; uma falta e normal);
#   2. o heartbeat do monitor (MONITOR_URL/api/status?ping=1) tem mais de HB_MAX_MIN minutos
#      (so checa se MONITOR_URL estiver definido);
#   3. o aplicadas.json do perfil ativo esta ausente ou ilegivel.
# Limite: roda NA maquina; PC desligado nao avisa. Requer PowerShell 5.1+ e python no PATH (checagem 3).
# Env: MONITOR_URL (opcional, sem padrao), HB_MAX_MIN (20), VIGIA_INTERVALO_MIN (15), VIGIA_STATE, VIGIA_NOTIFY.
# Uso: powershell -ExecutionPolicy Bypass -File bot\vigia-vida.ps1   (exit 0 = ok, 2 = alerta enviado)

$ErrorActionPreference = 'SilentlyContinue'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $BOT_ROOT 'bot')

function Write-Stamp { return (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

$MonitorUrl = $env:MONITOR_URL
if ([string]::IsNullOrWhiteSpace($MonitorUrl) -or $MonitorUrl -like '*sua-url*' -or $MonitorUrl -like '*example.invalid*') { $MonitorUrl = '' }
$HbMax = 20
if ($env:HB_MAX_MIN) { $HbMax = [int]$env:HB_MAX_MIN }
$Intervalo = 15
if ($env:VIGIA_INTERVALO_MIN) { $Intervalo = [int]$env:VIGIA_INTERVALO_MIN }
$StateFile = $env:VIGIA_STATE
if ([string]::IsNullOrWhiteSpace($StateFile)) { $StateFile = Join-Path $BOT_ROOT 'bot\state\vigia-vida.falhas' }
$Notify = $env:VIGIA_NOTIFY
if ([string]::IsNullOrWhiteSpace($Notify)) { $Notify = Join-Path $BOT_ROOT 'scripts\notificar.ps1' }
$StateDir = Split-Path -Parent $StateFile
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
$problemas = @()

$Py = $null
foreach ($c in @('python3', 'python', 'py')) {
    $g = Get-Command $c -ErrorAction SilentlyContinue
    if ($g) { $Py = $g.Source; break }
}

# 1) loop vivo? (mesmo teste do guardiao.ps1: linha de comando com loop.ps1)
function Test-LoopRunning {
    try {
        $procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*loop.ps1*' })
        if ($procs.Count -gt 0) { return $true }
    } catch { }
    return $false
}
if (Test-LoopRunning) {
    Remove-Item -Force $StateFile -ErrorAction SilentlyContinue
} else {
    $n = 0
    if (Test-Path $StateFile) { try { $n = [int](Get-Content $StateFile -TotalCount 1) } catch { $n = 0 } }
    $n = $n + 1
    Set-Content -Path $StateFile -Value $n
    if ($n -ge 2) { $problemas += ("loop.ps1 parado ha ~{0} min (guardiao nao religou)" -f ($n * $Intervalo)) }
}

# 2) heartbeat do monitor (opcional)
if ($MonitorUrl) {
    $hb = 'erro'
    try {
        $r = Invoke-RestMethod -Uri ($MonitorUrl.TrimEnd('/') + '/api/status?ping=1') -TimeoutSec 15
        if ($r.updatedAt) {
            $u = [DateTimeOffset]::Parse([string]$r.updatedAt)
            $hb = [int][Math]::Floor(([DateTimeOffset]::UtcNow - $u).TotalMinutes)
        } else { $hb = 'sem' }
    } catch { $hb = 'erro' }
    if ($hb -is [string]) {
        $problemas += ("monitor sem heartbeat ({0}): publisher parado ou servidor frio" -f $hb)
    } elseif ($hb -gt $HbMax) {
        $problemas += ("heartbeat do monitor ha {0} min (limite {1})" -f $hb, $HbMax)
    }
}

# 3) estado legivel? (aplicadas.json do perfil ativo; sem BOT_PERFIL usa o mais recente de bot\state\*\)
$Aplicadas = $env:APLICADAS_FILE
if ([string]::IsNullOrWhiteSpace($Aplicadas) -and $Py) {
    try { $Aplicadas = ((& $Py -c "import sys; sys.path.insert(0, '.'); import vagas_filtros as v; print(v.resolve_paths()['aplicadas'])" 2>$null) -join '').Trim() } catch { $Aplicadas = '' }
}
if ([string]::IsNullOrWhiteSpace($Aplicadas) -or -not (Test-Path $Aplicadas)) {
    $ultimo = Get-ChildItem -Path (Join-Path $BOT_ROOT 'bot\state') -Filter 'aplicadas.json' -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($ultimo) { $Aplicadas = $ultimo.FullName }
}
$estadoOk = $false
if ($Aplicadas -and (Test-Path $Aplicadas)) {
    try { Get-Content $Aplicadas -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop | Out-Null; $estadoOk = $true } catch { $estadoOk = $false }
}
if (-not $estadoOk) { $problemas += ("aplicadas.json ausente ou ilegivel ({0})" -f $Aplicadas) }

if ($problemas.Count -gt 0) {
    $msg = "[ALERTA] Robo: " + ($problemas -join '; ') + " - rode scripts\ctl.ps1 status"
    Write-Output ("[{0}] {1}" -f (Write-Stamp), $msg)
    try { & powershell -NoProfile -ExecutionPolicy Bypass -File $Notify $msg | Out-Null } catch { }
    exit 2
}
exit 0
