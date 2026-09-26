# scripts/digest.ps1 — espelho Windows de scripts/digest.sh.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\digest.ps1 [-Markdown] [-Send]
# Lê aplicadas.json + loop.log e gera o resumo do dia. -Send usa
# $env:TELEGRAM_BOT_TOKEN / $env:TELEGRAM_CHAT_ID (nunca imprime o token).
[CmdletBinding()]
param([switch]$Markdown, [switch]$Send, [string]$Aplicadas = '', [string]$Log = '')
$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Aplicadas)) {
    if ($env:BOT_APLICADAS) { $Aplicadas = $env:BOT_APLICADAS }
    else { $Aplicadas = Join-Path $BOT_ROOT 'bot\aplicadas.json' }
}
if ([string]::IsNullOrWhiteSpace($Log)) { $Log = Join-Path $BOT_ROOT 'bot\loop.log' }
if (-not (Test-Path $Aplicadas)) { Write-Error "aplicadas.json não encontrado: $Aplicadas"; exit 1 }

$d = Get-Content $Aplicadas -Raw | ConvertFrom-Json
$hoje = (Get-Date).ToString('yyyy-MM-dd')
$feitas = @($d.aplicadas | Where-Object { $_.data -eq $hoje })
$bloqNomes = @()
if ($d.bloqueados) {
    foreach ($p in $d.bloqueados.PSObject.Properties) {
        $v = $p.Value
        $em = $null
        if ($v -is [pscustomobject]) { $em = $v.bloqueado_em; if (-not $em) { $em = $v.em }; if (-not $em) { $em = $v.criadoEm } }
        if ($em -and $em.StartsWith($hoje)) { $bloqNomes += $p.Name }
    }
}
$prox = $d.rodizio.proximo
$ult = $d.rodizio.ultima_rodada
$totalA = @($d.aplicadas).Count
$totalB = @($d.bloqueados.PSObject.Properties).Count

$lines = New-Object System.Collections.ArrayList
if ($Markdown) {
    [void]$lines.Add("# Resumo do dia $hoje"); [void]$lines.Add('')
    [void]$lines.Add("- Aplicadas hoje: **$($feitas.Count)**")
    foreach ($a in ($feitas | Select-Object -First 10)) { [void]$lines.Add("  - $($a.chave)") }
    [void]$lines.Add("- Bloqueadas hoje: **$($bloqNomes.Count)**")
    [void]$lines.Add("- Total: $totalA aplicadas / $totalB bloqueadas")
    [void]$lines.Add("- Rodízio atual: próximo **$prox** (última rodada: $ult)")
    [void]$lines.Add("- Próximo passo: rodar o site **$prox** (ver rodizio.proximo em aplicadas.json)")
} else {
    [void]$lines.Add("Resumo do dia $hoje")
    [void]$lines.Add("Aplicadas hoje: $($feitas.Count)")
    foreach ($a in ($feitas | Select-Object -First 10)) { [void]$lines.Add("  - $($a.chave)") }
    [void]$lines.Add("Bloqueadas hoje: $($bloqNomes.Count)")
    [void]$lines.Add("Total: $totalA aplicadas / $totalB bloqueadas")
    [void]$lines.Add("Rodízio atual: próximo $prox (última rodada: $ult)")
    [void]$lines.Add("Próximo passo: rodar o site $prox (ver rodizio.proximo em aplicadas.json)")
}
# Alertas de anomalia: regras simples sobre as linhas de HOJE do loop.log
# (nenhuma rodada ok, sequencia longa de rodadas vazias, muitos timeouts/quota).
$alertas = New-Object System.Collections.ArrayList
if (Test-Path $Log) {
    $hojeL = @(Get-Content $Log -ErrorAction SilentlyContinue | Where-Object { $_.StartsWith("[$hoje") })
    $oks = @($hojeL | Where-Object { $_ -match 'rodada ok' })
    $vazias = @($hojeL | Where-Object { $_ -match 'NENHUMA vaga nova' })
    $estouros = @($hojeL | Where-Object { $_ -match 'estourou' })
    $quotas = @($hojeL | Where-Object { $_ -match 'quota/limite|no limite' })
    $erros = @($hojeL | Where-Object { $_ -match 'terminou com erro|sessao opencode invalida' })
    $streak = 0
    $combinado = @($oks + $vazias)
    for ($i = $combinado.Count - 1; $i -ge 0; $i--) {
        $l = $combinado[$i]
        if ($l -match 'NENHUMA vaga nova') {
            if ($l -match '\((\d+)x seguidas\)') { $streak = [int]$Matches[1]; break }
            $streak++
        } else { break }
    }
    if ($hojeL.Count -gt 0 -and $oks.Count -eq 0) {
        [void]$alertas.Add('ALERTA: nenhuma rodada ok hoje — loop pode estar preso em erro/quota.')
    }
    if ($streak -ge 3) {
        [void]$alertas.Add("ALERTA: ${streak}x rodadas vazias seguidas — considerar pular o site atual por 24h.")
    }
    if ($estouros.Count -ge 2) {
        [void]$alertas.Add("ALERTA: $($estouros.Count) timeouts hoje — rodadas estourando o limite, rever META de tempo.")
    }
    if ($quotas.Count -ge 3) {
        [void]$alertas.Add("INFO: $($quotas.Count) sinais de quota hoje — avaliar reordenar a cascata de modelos.")
    }
    if ($erros.Count -gt 0) {
        [void]$alertas.Add("INFO: $($erros.Count) erro(s) de sessao/modelo hoje (ver loop.log).")
    }
}
if ($alertas.Count -gt 0) {
    if ($Markdown) { [void]$lines.Add(''); [void]$lines.Add('## Alertas') }
    else { [void]$lines.Add('--- alertas ---') }
    foreach ($a in $alertas) { [void]$lines.Add($a) }
}
if (Test-Path $Log) {
    if ($Markdown) { [void]$lines.Add(''); [void]$lines.Add('## Últimas linhas do loop.log') }
    else { [void]$lines.Add('--- últimas linhas do loop.log ---') }
    foreach ($l in (Get-Content $Log -Tail 5 -ErrorAction SilentlyContinue)) { [void]$lines.Add($l) }
}
$lines | ForEach-Object { $_ }

if ($Send) {
    $tok = $env:TELEGRAM_BOT_TOKEN
    $chat = $env:TELEGRAM_CHAT_ID
    if ($tok -and $chat) {
        $text = "Resumo ${hoje}: $($feitas.Count) aplicadas hoje, $($bloqNomes.Count) bloqueadas hoje. Rodízio: próximo $prox."
        # Token vai só na URL do POST; nunca impresso.
        $uri = "https://api.telegram.org/bot$tok/sendMessage"
        Invoke-RestMethod -Uri $uri -Method Post -Body @{ chat_id = $chat; text = $text } | Out-Null
    } else {
        Write-Warning '(Telegram não configurado: defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID para -Send)'
    }
}
