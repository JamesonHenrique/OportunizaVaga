# bot/followup.ps1 — espelho Windows de bot/followup.sh.
# Follow-up semanal das candidaturas (segundas 09:00, via Task Scheduler).
# Sessao unica: le o status das vagas ja aplicadas e grava em aplicadas.json.
# NUNCA se candidata. Requer PowerShell 5.1+.
#
# Diferenca assumida vs followup.sh (simplificacao documentada): o .sh tem um
# stall watchdog que aborta a rodada se a saida ficar parada N segundos (modelo
# com quota segurando o Chrome calado); aqui o Start-Job so espera o job inteiro
# (sem poll incremental do log), entao uma rodada presa em retry silencioso
# morre no timeout cheio. GAP documentado (mesma limitacao do bot/loop.ps1).

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
. (Join-Path $PSScriptRoot 'chrome-lock.ps1')   # Enter-ChromeLock / Exit-ChromeLock

# Instancia unica: lock exclusivo; se ja houver dono, sai calado.
try {
    $LockStream = [System.IO.File]::Open($FOLLOWUP_LOCK, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch { exit 0 }

# Semanal com retentativa diaria: o Task Scheduler pode rodar todo dia; pula se
# o ultimo SUCESSO tiver menos de 6 dias (assim uma falha nao trava 7 dias sem
# tentar de novo).
if (-not (Test-Path 'state')) { New-Item -ItemType Directory -Path 'state' | Out-Null }
$OkMark = if ($env:OV_FOLLOWUP_OK_MARK) { $env:OV_FOLLOWUP_OK_MARK } else { 'state/followup.ok' }
if (Test-Path $OkMark) {
    $idade = (Get-Date) - (Get-Item $OkMark).LastWriteTime
    if ($idade.TotalDays -lt 6) { exit 0 }
}

# Cascata de modelos gratuitos (mesma familia do loop.sh); se um bater quota ou
# nao existir mais, cascateia para o proximo.
$MODELOS = @(
    'opencode/muse-spark-1.3-contributor-free',
    'opencode/nemotron-3-ultra-free',
    'opencode/nemotron-3.5-lightning-free',
    'opencode/mimo-v2.5-free'
)
# Config enxuta do opencode (bot/opencode-enxuto.py, fail-open): OV_OPENCODE_CONFIG_CONTENT explicito tem precedencia.
$OcCfg = $env:OV_OPENCODE_CONFIG_CONTENT
if ([string]::IsNullOrWhiteSpace($OcCfg)) {
    foreach ($c in @('python3', 'python', 'py')) {
        $g = Get-Command $c -ErrorAction SilentlyContinue
        if ($g) {
            try { $OcCfg = (& $g.Source (Join-Path $BOT_ROOT 'bot\opencode-enxuto.py') 2>$null) -join '' } catch { $OcCfg = '' }
            break
        }
    }
}
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
    # Protocolo unico do Chrome (bot/chrome-lock.ps1): job prioritario ("alta"), espera ate 900s.
    # A flag de prioridade fica durante TODAS as tentativas de modelo. Timeout = pula a semana.
    $env:CHROME_LOCK_FILE = $BROWSER_LOCK
    $chromeLock = Enter-ChromeLock -Name 'followup' -Prio 'alta' -WaitSeconds 900
    if ($chromeLock.Status -ne 0) {
        Add-Content -Path 'followup.log' -Value ("[{0}] follow-up pulado: Chrome ocupado (lock)" -f (Write-Stamp))
    } else {
        try {
            $promptBase = Get-Content (Join-Path $BOT_ROOT 'bot\prompt_followup.md') -Raw
            $aplicadasFile = if ($env:APLICADAS_FILE) { $env:APLICADAS_FILE } else { Join-Path $BOT_ROOT 'bot\aplicadas.json' }
            $resumoLinhas = @()
            try {
                $doc = Get-Content $aplicadasFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
                foreach ($a in @($doc.aplicadas)) {
                    $vaga = [string]$a.vaga; if ($vaga.Length -gt 60) { $vaga = $vaga.Substring(0, 60) }
                    $como = [string]$a.como; if ($como.Length -gt 40) { $como = $como.Substring(0, 40) }
                    $st = if ($a.status) { $a.status } else { '-' }
                    $resumoLinhas += ("  {0} | {1} | {2} | {3} | {4} | {5}" -f $a.chave, $a.empresa, $vaga, $como, $a.data, $st)
                }
            } catch { }
            $prompt = $promptBase + "`n`nAPLICADAS (gerado agora; NAO leia aplicadas.json inteiro) — chave | empresa | vaga | como | data | status atual:`n" + ($resumoLinhas -join "`n")
            $title = 'followup-{0}' -f (Get-Date).ToString('yyyy-MM-dd')

            $STATUS = 1
            foreach ($MODELO in $MODELOS) {
                $job = Start-Job -ScriptBlock {
                    param($bin, $mod, $ttl, $pr, $cfg)
                    if ($cfg) { $env:OPENCODE_CONFIG_CONTENT = $cfg }
                    & $bin run -m $mod --title $ttl $pr 2>&1
                } -ArgumentList $OpencodeBin, $MODELO, $title, $prompt, $OcCfg
                # Sessao unica semanal: timeout de 55min por modelo, igual ao .sh.
                $done = Wait-Job -Job $job -Timeout 3300
                if ($done) {
                    $out = Receive-Job -Job $job
                    $out | Out-File -FilePath $FLOG -Encoding utf8
                    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
                    $STATUS = 0
                    if ($job.State -eq 'Failed') { $STATUS = 1 }
                } else {
                    Stop-Job -Job $job -ErrorAction SilentlyContinue
                    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
                    Add-Content -Path $FLOG -Value 'follow-up excedeu o timeout e foi abortado'
                    $STATUS = 124
                }
                $semCota = ($null -ne (Select-String -Path $FLOG -Pattern 'QUOTA_EXAUSTA|Rate limit|Model not found' -ErrorAction SilentlyContinue))
                if ($semCota) {
                    Add-Content -Path 'followup.log' -Value ("[{0}] follow-up: {1} sem cota/indisponivel, proximo" -f (Write-Stamp), $MODELO)
                    $STATUS = 1
                    continue
                }
                break
            }
            try {
                Add-Content -Path 'followup.log' -Value ("--- saida do follow-up (completa em {0}) ---" -f $FLOG)
                Get-Content $FLOG -Tail 20 -ErrorAction SilentlyContinue | Add-Content -Path 'followup.log'
            } catch { }
            if ($STATUS -eq 0) {
                Set-Content -Path $OkMark -Value (Write-Stamp)
                Add-Content -Path 'followup.log' -Value ("[{0}] follow-up ok (modelo {1})" -f (Write-Stamp), $MODELO)
            } else {
                Add-Content -Path 'followup.log' -Value ("[{0}] follow-up FALHOU (status {1}); tenta de novo amanha" -f (Write-Stamp), $STATUS)
            }
        } finally {
            Exit-ChromeLock $chromeLock
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
