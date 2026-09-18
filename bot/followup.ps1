# bot/followup.ps1 — espelho Windows de bot/followup.sh.
# Follow-up semanal das candidaturas (segundas 09:00, via Task Scheduler).
# Sessao unica: le o status das vagas ja aplicadas e grava em aplicadas.json.
# NUNCA se candidata. Requer PowerShell 5.1+.

$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $BOT_ROOT 'bot')

function Write-Stamp { return (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

$OpencodeCmd = Get-Command opencode -ErrorAction SilentlyContinue
$OpencodeBin = $null
if ($OpencodeCmd) { $OpencodeBin = $OpencodeCmd.Source }
if ([string]::IsNullOrWhiteSpace($OpencodeBin)) {
    $cand = Join-Path $env:USERPROFILE '.opencode\bin\opencode.exe'
    if (Test-Path $cand) { $OpencodeBin = $cand }
}
if ([string]::IsNullOrWhiteSpace($OpencodeBin)) {
    Add-Content -Path 'followup.log' -Value ("[{0}] ERRO: opencode nao encontrado" -f (Write-Stamp))
    exit 1
}

$CronEnv = Join-Path $env:USERPROFILE '.config\opencode\cron.env'
if (Test-Path $CronEnv) {
    foreach ($line in (Get-Content $CronEnv)) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $i = $t.IndexOf('=')
        if ($i -gt 0) {
            $k = $t.Substring(0, $i).Trim()
            $v = $t.Substring($i + 1).Trim().Trim('"').Trim("'")
            if ($k -ne '') { Set-Item -Path ("env:{0}" -f $k) -Value $v }
        }
    }
}

$TEMP_DIR = $env:TEMP
if ([string]::IsNullOrWhiteSpace($TEMP_DIR)) { $TEMP_DIR = [System.IO.Path]::GetTempPath() }
$FOLLOWUP_LOCK = Join-Path $TEMP_DIR 'oportunizavaga-followup.lock'
$BROWSER_LOCK = Join-Path $TEMP_DIR 'agent-chrome-9222.lock'

# Instancia unica: lock exclusivo; se ja houver dono, sai calado.
try {
    $LockStream = [System.IO.File]::Open($FOLLOWUP_LOCK, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch { exit 0 }

$MODELO = 'opencode/muse-spark-1.3-contributor-free'
$FLOG = 'logs/followup-{0}.log' -f (Get-Date).ToString('yyyyMMdd-HHmmss')
if (-not (Test-Path 'logs')) { New-Item -ItemType Directory -Path 'logs' | Out-Null }

Add-Content -Path 'followup.log' -Value ("[{0}] follow-up iniciado" -f (Write-Stamp))

function Test-Cdp {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $r = $c.BeginConnect('127.0.0.1', 9222, $null, $null)
        $ok = $r.AsyncWaitHandle.WaitOne(5000)
        $c.Close()
        return $ok
    } catch { return $false }
}

if (Test-Cdp) {
    # Disputa exclusiva pelo Chrome (ate 900s). Timeout = pula a semana.
    $chromeLock = $null
    $deadline = (Get-Date).AddSeconds(900)
    while ((Get-Date) -lt $deadline) {
        try {
            $chromeLock = [System.IO.File]::Open($BROWSER_LOCK, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            break
        } catch { Start-Sleep -Seconds 5 }
    }
    if ($null -eq $chromeLock) {
        Add-Content -Path 'followup.log' -Value ("[{0}] follow-up pulado: Chrome ocupado (lock)" -f (Write-Stamp))
    } else {
        try {
            $prompt = Get-Content (Join-Path $BOT_ROOT 'bot\prompt_followup.md') -Raw
            $title = 'followup-{0}' -f (Get-Date).ToString('yyyy-MM-dd')
            $job = Start-Job -ScriptBlock {
                param($bin, $mod, $ttl, $pr)
                & $bin run -m $mod --title $ttl $pr 2>&1
            } -ArgumentList $OpencodeBin, $MODELO, $title, $prompt
            # Sessao unica semanal: timeout de 15min (900s), igual ao .sh.
            $done = Wait-Job -Job $job -Timeout 900
            if ($done) {
                $out = Receive-Job -Job $job
                $out | Out-File -FilePath $FLOG -Encoding utf8
                Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
                $STATUS = 0
                if ($job.State -eq 'Failed') { $STATUS = 1 }
            } else {
                Stop-Job -Job $job -ErrorAction SilentlyContinue
                Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
                Add-Content -Path $FLOG -Value 'follow-up excedeu o timeout de 900s e foi abortado'
                $STATUS = 124
            }
            try {
                Add-Content -Path 'followup.log' -Value ("--- saida do follow-up (completa em {0}) ---" -f $FLOG)
                Get-Content $FLOG -Tail 20 -ErrorAction SilentlyContinue | Add-Content -Path 'followup.log'
            } catch { }
            Add-Content -Path 'followup.log' -Value ("[{0}] follow-up ok (status {1})" -f (Write-Stamp), $STATUS)
        } finally {
            try { $chromeLock.Close(); $chromeLock.Dispose() } catch { }
        }
    }
} else {
    Add-Content -Path 'followup.log' -Value ("[{0}] follow-up pulado: Chrome CDP fora" -f (Write-Stamp))
}

try {
    $files = Get-ChildItem 'logs/followup-*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if ($files -and $files.Count -gt 10) {
        $files | Select-Object -Skip 10 | Remove-Item -Force -ErrorAction SilentlyContinue
    }
} catch { }

try { $LockStream.Close(); $LockStream.Dispose() } catch { }
