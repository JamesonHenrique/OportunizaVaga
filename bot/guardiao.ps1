# bot/guardiao.ps1 — espelho Windows de bot/guardiao.sh.
# Supervisor: garante que loop.ps1 e o Chrome CDP estejam de pe.
# Chamado pelo Task Scheduler a cada 5min e no logon. Idempotente: se ja estiver
# rodando, nao faz nada. Requer PowerShell 5.1+.
# Uso: powershell -ExecutionPolicy Bypass -File bot\guardiao.ps1

$ErrorActionPreference = 'SilentlyContinue'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $BOT_ROOT 'bot')

function Write-Stamp { return (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

$MONITOR_URL = $env:MONITOR_URL
if ([string]::IsNullOrWhiteSpace($MONITOR_URL)) { $MONITOR_URL = 'https://sua-url.vercel.app' }
$env:MONITOR_URL = $MONITOR_URL
$env:CANDIDATURAS_ROOT = (Join-Path $BOT_ROOT 'bot')

$TEMP_DIR = $env:TEMP
if ([string]::IsNullOrWhiteSpace($TEMP_DIR)) { $TEMP_DIR = [System.IO.Path]::GetTempPath() }
$LOOP_LOCK = Join-Path $TEMP_DIR 'oportunizavaga-loop.lock'

function Test-Cdp {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $r = $c.BeginConnect('127.0.0.1', 9222, $null, $null)
        $ok = $r.AsyncWaitHandle.WaitOne(5000)
        $c.Close()
        return $ok
    } catch { return $false }
}

function Test-LoopRunning {
    # Checa o PROCESSO (CommandLine contem loop.ps1), nao so o lock: um job orfao
    # pode segurar o arquivo e fazer o teste de lock mentir.
    try {
        $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*loop.ps1*' }
        if ($procs) { return $true }
    } catch { }
    try {
        $ps = Get-Process | Where-Object { $_.ProcessName -like '*powershell*' -or $_.ProcessName -like '*pwsh*' }
        foreach ($p in $ps) {
            try {
                $cmd = (Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $p.Id)).CommandLine
                if ($cmd -like '*loop.ps1*') { return $true }
            } catch { }
        }
    } catch { }
    return $false
}

# 1) Loop de candidaturas (o publisher do monitor tem dono proprio:
# scripts/monitor-keepalive.ps1 — o guardiao NAO sobe publisher para nao duplicar).
if (Test-LoopRunning) {
    # loop vivo, nada a fazer
} else {
    # Lock preso sem loop vivo? Remove para a proxima subida nao travar.
    $locked = $false
    try {
        $s = [System.IO.File]::Open($LOOP_LOCK, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $s.Close(); $s.Dispose()
    } catch { $locked = $true }
    if ($locked) {
        Add-Content -Path 'guardiao.log' -Value ("[{0}] guardiao: lock preso sem loop vivo, removendo" -f (Write-Stamp))
        try { Remove-Item -Force $LOOP_LOCK } catch { }
        Start-Sleep -Seconds 2
    }
    Add-Content -Path 'guardiao.log' -Value ("[{0}] guardiao: loop caido, subindo" -f (Write-Stamp))
    $loop = Join-Path $BOT_ROOT 'bot\loop.ps1'
    Start-Process -FilePath 'powershell' -ArgumentList @('-ExecutionPolicy', 'Bypass', '-File', $loop) -WindowStyle Hidden
}

# 2) Chrome com CDP — sem ele o robo nao navega. Test-NetConnection equivalente
# via TCP direto (mais rapido e sem dependencia de modulo).
if (-not (Test-Cdp)) {
    Add-Content -Path 'guardiao.log' -Value ("[{0}] guardiao: Chrome CDP fora, subindo" -f (Write-Stamp))
    $chrome = Join-Path $BOT_ROOT 'browser\chrome-real.ps1'
    Start-Process -FilePath 'powershell' -ArgumentList @('-ExecutionPolicy', 'Bypass', '-File', $chrome) -WindowStyle Hidden
}

# Mantem guardiao.log pequeno (ultimas 200 linhas se passar de 256KB).
try {
    if ((Test-Path 'guardiao.log') -and ((Get-Item 'guardiao.log').Length -gt 262144)) {
        $lines = Get-Content 'guardiao.log' -Tail 200
        $lines | Set-Content 'guardiao.log.tmp'
        Move-Item -Force 'guardiao.log.tmp' 'guardiao.log'
    }
} catch { }
exit 0
