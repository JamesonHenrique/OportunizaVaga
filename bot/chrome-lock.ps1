# bot/chrome-lock.ps1 — espelho Windows de bot/chrome-lock.sh (mesmo protocolo, mesmos codigos de saida).
#
#   CLI:      chrome-lock.ps1 NOME alta|normal ESPERA_S -- CMD [ARGS...]
#   Funcoes:  . chrome-lock.ps1   (dot-source; usado por loop.ps1 e followup.ps1)
#             $h = Enter-ChromeLock -Name loop -Prio normal -WaitSeconds 900
#             ... $h.Status -eq 0 => tem o Chrome ...   Exit-ChromeLock $h
#
#   alta   = job curto/diario (follow-up, leitor do Gmail): marca a vez com a flag
#            <temp>\agent-chrome-9222.prio.NOME e espera ate ESPERA_S pelo lock.
#   normal = o loop de candidaturas: CEDE a vez se houver flag fresca (< 120 min) de outro job.
# Saida: codigo do CMD; 75 = timeout do lock; 76 = cedeu a um job prioritario (CHROME_LOCK_YIELD_RC muda);
# 2 = uso. Uma flag que ja existia quando a chamada comecou e do job pai e NAO e removida aqui.
# Env: CHROME_LOCK_FILE, CHROME_LOCK_DIR, CHROME_LOCK_LOG, CHROME_LOCK_YIELD_RC (testes nao tocam o lock real).
# Requer PowerShell 5.1+.

param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CliArgs)

function Get-ChromeLockPath([string]$Kind) {
    $tmp = $env:TEMP
    if ([string]::IsNullOrWhiteSpace($tmp)) { $tmp = [System.IO.Path]::GetTempPath() }
    switch ($Kind) {
        'lock' { if ($env:CHROME_LOCK_FILE) { return $env:CHROME_LOCK_FILE } else { return (Join-Path $tmp 'agent-chrome-9222.lock') } }
        'flags' { if ($env:CHROME_LOCK_DIR) { return $env:CHROME_LOCK_DIR } else { return $tmp } }
        'log' { if ($env:CHROME_LOCK_LOG) { return $env:CHROME_LOCK_LOG } else { return (Join-Path $PSScriptRoot 'logs\chrome-lock.log') } }
    }
}

function Write-ChromeLockLog([string]$Name, [string]$Prio, [string]$Msg) {
    try {
        $log = Get-ChromeLockPath 'log'
        $dir = Split-Path -Parent $log
        if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Add-Content -Path $log -Value ("[{0}] {1}({2}) {3}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $Name, $Prio, $Msg)
    } catch { }
}

# Retorna @{ Status; Stream; Flag; FlagCreated; Name; Prio; T1 }. Status 0 = tem o Chrome.
function Enter-ChromeLock([string]$Name, [string]$Prio, [int]$WaitSeconds) {
    $h = @{ Status = 0; Stream = $null; Flag = $null; FlagCreated = $false; Name = $Name; Prio = $Prio; T1 = Get-Date }
    $flagDir = Get-ChromeLockPath 'flags'
    $flag = Join-Path $flagDir "agent-chrome-9222.prio.$Name"
    if ($Prio -eq 'alta') {
        $h.Flag = $flag
        if (-not (Test-Path $flag)) { New-Item -ItemType File -Path $flag -Force | Out-Null; $h.FlagCreated = $true }
        else { (Get-Item $flag).LastWriteTime = Get-Date }
    } elseif ($Prio -eq 'normal') {
        $limite = (Get-Date).AddMinutes(-120)
        $outro = Get-ChildItem -Path $flagDir -Filter 'agent-chrome-9222.prio.*' -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne "agent-chrome-9222.prio.$Name" -and $_.LastWriteTime -gt $limite } | Select-Object -First 1
        if ($outro) {
            Write-ChromeLockLog $Name $Prio ("cedeu a vez para {0}" -f ($outro.Name -replace '^agent-chrome-9222\.prio\.', ''))
            $h.Status = if ($env:CHROME_LOCK_YIELD_RC) { [int]$env:CHROME_LOCK_YIELD_RC } else { 76 }
            return $h
        }
    } else {
        $h.Status = 2
        return $h
    }
    $lockFile = Get-ChromeLockPath 'lock'
    $t0 = Get-Date
    $deadline = $t0.AddSeconds($WaitSeconds)
    while ($true) {
        try {
            $h.Stream = [System.IO.File]::Open($lockFile, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            break
        } catch {
            if ((Get-Date) -ge $deadline) { break }
            Start-Sleep -Seconds 1
        }
    }
    if ($null -eq $h.Stream) {
        Write-ChromeLockLog $Name $Prio "timeout esperando o Chrome (${WaitSeconds}s)"
        $h.Status = 75
        Exit-ChromeLock $h
        return $h
    }
    $h.T1 = Get-Date
    $esperou = [int]($h.T1 - $t0).TotalSeconds
    if ($esperou -gt 5) { Write-ChromeLockLog $Name $Prio "pegou o Chrome apos ${esperou}s de espera" }
    return $h
}

function Exit-ChromeLock($h) {
    if ($null -eq $h) { return }
    if ($h.Stream) {
        Write-ChromeLockLog $h.Name $h.Prio ("liberou o Chrome apos {0}s" -f [int]((Get-Date) - $h.T1).TotalSeconds)
        try { $h.Stream.Close(); $h.Stream.Dispose() } catch { }
        $h.Stream = $null
    }
    if ($h.FlagCreated -and $h.Flag) { Remove-Item -Path $h.Flag -Force -ErrorAction SilentlyContinue; $h.FlagCreated = $false }
}

# Dot-sourced: so define as funcoes.
if ($MyInvocation.InvocationName -eq '.') { return }

$a = @($CliArgs)
if ($a.Count -lt 4) { [Console]::Error.WriteLine('uso: chrome-lock.ps1 NOME alta|normal ESPERA_S -- CMD [ARGS...]'); exit 2 }
$rest = @($a[3..($a.Count - 1)])
if ($rest[0] -eq '--') { $rest = @($rest | Select-Object -Skip 1) }
if ($rest.Count -eq 0) { [Console]::Error.WriteLine('uso: chrome-lock.ps1 NOME alta|normal ESPERA_S -- CMD [ARGS...]'); exit 2 }
$handle = Enter-ChromeLock -Name $a[0] -Prio $a[1] -WaitSeconds ([int]$a[2])
if ($handle.Status -ne 0) { exit $handle.Status }
$rc = 0
try {
    $cmd = $rest[0]
    $cmdArgs = @($rest | Select-Object -Skip 1)
    & $cmd @cmdArgs
    $rc = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 0 }
} finally {
    Exit-ChromeLock $handle
}
exit $rc
