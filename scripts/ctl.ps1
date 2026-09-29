# scripts/ctl.ps1 — espelho Windows de scripts/ctl.sh: inspeciona o bot sem abrir logs grandes.
# So le; nao altera nada. Requer PowerShell 5.1+.
#   powershell -File scripts\ctl.ps1 status   saude de cada parte em ~20 linhas (comece por aqui)
#   powershell -File scripts\ctl.ps1 rodada   resultado da ultima rodada (modelo, final)
#   powershell -File scripts\ctl.ps1 chrome   quem usou o Chrome compartilhado (bot\logs\chrome-lock.log)
# Estado lido: $env:APLICADAS_FILE, senao bot\aplicadas.json, senao o primeiro bot\state\*\aplicadas.json.
param([Parameter(Position = 0)][string]$Cmd = 'status')
$ErrorActionPreference = 'SilentlyContinue'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
$Bot = Join-Path $BOT_ROOT 'bot'
Set-Location $Bot

function Get-EstadoJson {
    if ($env:APLICADAS_FILE -and (Test-Path $env:APLICADAS_FILE)) { return $env:APLICADAS_FILE }
    $p = Join-Path $Bot 'aplicadas.json'
    if (Test-Path $p) { return $p }
    $c = Get-ChildItem (Join-Path $Bot 'state') -Filter 'aplicadas.json' -Recurse -Depth 1 | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($c) { return $c.FullName }
    return $null
}

function Show-Status {
    Write-Output '== Motor'
    $proc = Get-CimInstance Win32_Process -Filter "Name like 'powershell%' or Name like 'pwsh%'" | Where-Object { $_.CommandLine -match 'bot[\\/]loop\.ps1' } | Select-Object -First 1
    if ($proc) { Write-Output ("loop: vivo (pid {0})" -f $proc.ProcessId) } else { Write-Output 'loop: PARADO (o guardiao.ps1 religa em ate 5 min, se agendado)' }
    if (Test-Path 'loop.log') {
        Select-String -Path 'loop.log' -Pattern 'rodada (iniciada|usou|estourou|ok)|FALHOU|dormindo|ALERTA' | Select-Object -Last 2 | ForEach-Object { $_.Line.Substring(0, [Math]::Min(140, $_.Line.Length)) }
    }
    $cool = 'state\model_cooldown'
    if (Test-Path $cool) {
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $last = @{}
        foreach ($l in Get-Content $cool) { $p = $l -split '\s+'; if ($p.Count -ge 2) { $last[$p[0]] = [long]$p[1] } }
        $b = @($last.Values | Where-Object { $_ -gt $now }).Count
        Write-Output ("modelos em cooldown: {0} de {1} vistos" -f $b, $last.Count)
    }
    Write-Output '== Prompt (ultima rodada)'
    $f = Get-ChildItem 'logs\rodada-*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $rt = Get-ChildItem -Path 'prompt_loop.runtime.md', 'state\*\prompt_loop.runtime.md' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($f -and $rt) {
        $ja = @(Select-String -Path $f.FullName -Pattern 'estado\.py.*ja-visto').Count
        $inteiro = @(Select-String -Path $f.FullName -Pattern '(Read|cat ).*aplicadas\.json').Count
        Write-Output ("prompt: {0} bytes | ja-visto: {1} | leu aplicadas.json inteiro: {2} (meta 0)" -f $rt.Length, $ja, $inteiro)
    } else { Write-Output 'sem prompt renderizado ou sem log de rodada ainda' }
    Write-Output '== Estado'
    $ap = Get-EstadoJson
    if ($ap) {
        $d = Get-Content $ap -Raw -Encoding UTF8 | ConvertFrom-Json
        $lista = @($d.aplicadas)
        $hoje = (Get-Date).ToString('yyyy-MM-dd')
        $nHoje = @($lista | Where-Object { ([string]$_.data).StartsWith($hoje) }).Count
        $st = $lista | Group-Object { if ($_.status) { $_.status } else { 'enviada' } } | Sort-Object Count -Descending | ForEach-Object { '{0}={1}' -f $_.Name, $_.Count }
        Write-Output ("enviadas: {0} (hoje {1}) | status: {2}" -f $lista.Count, $nHoje, $(if ($st) { $st -join ', ' } else { '-' }))
        $nq = if ($d.quase_la) { @($d.quase_la.PSObject.Properties).Count } else { 0 }
        $nb = if ($d.bloqueados) { @($d.bloqueados.PSObject.Properties).Count } else { 0 }
        Write-Output ("quase_la: {0} | bloqueados: {1} | proximo site: {2} | ordem calculada em: {3}" -f $nq, $nb, $d.rodizio.proximo, $(if ($d.rodizio.ordem_calculada_em) { $d.rodizio.ordem_calculada_em } else { '-' }))
    } else { Write-Output 'aplicadas.json nao encontrado (defina APLICADAS_FILE)' }
    Write-Output '== Navegador'
    $cdp = $false
    try { $cdp = (New-Object Net.Sockets.TcpClient).BeginConnect('127.0.0.1', 9222, $null, $null).AsyncWaitHandle.WaitOne(3000) } catch { }
    if ($cdp) { Write-Output 'chrome 9222: ok' } else { Write-Output 'chrome 9222: FORA' }
    if (Test-Path 'logs\chrome-lock.log') { Get-Content 'logs\chrome-lock.log' -Tail 1 }
    $tmp = if ($env:CHROME_LOCK_DIR) { $env:CHROME_LOCK_DIR } else { $env:TEMP }
    Get-ChildItem -Path $tmp -Filter 'agent-chrome-9222.prio.*' | ForEach-Object { 'prioridade ativa: ' + ($_.Name -replace '^agent-chrome-9222\.prio\.', '') }
    Write-Output '== Logs'
    foreach ($n in 'logs\redact.log', 'gmail-status.log', 'validate-rodada.log') {
        if (Test-Path $n) { Get-Content $n -Tail 1 | ForEach-Object { $_.Substring(0, [Math]::Min(120, $_.Length)) } }
    }
}

function Show-Rodada {
    $f = Get-ChildItem 'logs\rodada-*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $f) { Write-Output 'sem log de rodada'; return }
    Write-Output ("arquivo: logs\{0} ({1} bytes)" -f $f.Name, $f.Length)
    $m = Select-String -Path $f.FullName -Pattern 'build · \S+' | Select-Object -First 1
    if ($m) { $m.Matches[0].Value }
    Write-Output '--- final:'
    Get-Content $f.FullName -Encoding UTF8 | ForEach-Object { $_ -replace '\x1b\[[0-9;]*m', '' } |
        Where-Object { $_.Trim() -ne '' -and $_ -notmatch '^[⚙→$✗]' } | Select-Object -Last 12 |
        ForEach-Object { $_.Substring(0, [Math]::Min(200, $_.Length)) }
}

switch ($Cmd) {
    'status' { Show-Status }
    'rodada' { Show-Rodada }
    'chrome' { if (Test-Path 'logs\chrome-lock.log') { Get-Content 'logs\chrome-lock.log' -Tail 15 } else { Write-Output 'sem bot\logs\chrome-lock.log ainda' } }
    default { Get-Content $PSCommandPath -TotalCount 8 | Select-Object -Skip 1 }
}
