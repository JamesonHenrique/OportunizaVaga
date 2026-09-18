# bot/dry-run.ps1 — espelho Windows (PowerShell 5.1+) de bot/dry-run.sh.
# Simula UMA rodada sem se candidatar (teste sem risco). So LE arquivos:
# valida os JSONs, mostra o site do rodizio e lista o que a rodada FARIA
# (site, termos de busca, limite, modelo preferido). Nao abre browser, nao
# chama o opencode, nao escreve nada, nao se candidata.
# Requer apenas PowerShell (funciona sem Chrome/opencode instalados).
# Uso: powershell -ExecutionPolicy Bypass -File bot\dry-run.ps1 [--json]

[CmdletBinding()]
param(
    [switch]$json,
    [switch]$help
)

$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $BOT_ROOT 'bot')

if ($help) {
    Write-Host 'Uso: bot\dry-run.ps1 [--json]'
    Write-Host 'Simula uma rodada sem se candidatar. Exit 0 = rodada simulada ok.'
    exit 0
}

# Modelo preferido = primeiro da escada em bot/loop.ps1 (fonte unica de verdade).
$ModeloPreferido = 'opencode/muse-spark-1.3-contributor-free'
try {
    $hit = Select-String -Path (Join-Path $BOT_ROOT 'bot\loop.ps1') -Pattern "Add\('([^']+)'\)" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit -and $hit.Matches[0].Groups[1].Value) { $ModeloPreferido = $hit.Matches[0].Groups[1].Value }
} catch { }

$dadosCaminho = 'dados_candidato.json'
$dadosReais = $true
if (-not (Test-Path $dadosCaminho)) { $dadosCaminho = Join-Path $BOT_ROOT 'examples\dados_candidato.example.json'; $dadosReais = $false }
$aplicCaminho = 'aplicadas.json'
$aplicReais = $true
if (-not (Test-Path $aplicCaminho)) { $aplicCaminho = Join-Path $BOT_ROOT 'examples\aplicadas.example.json'; $aplicReais = $false }

$erros = New-Object System.Collections.ArrayList

try { $dados = Get-Content $dadosCaminho -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
catch { $dados = $null; [void]$erros.Add(('dados_candidato: JSON invalido ou ilegivel ({0})' -f $_.Exception.Message)) }
if ($null -ne $dados) {
    foreach ($k in @('nome', 'email', 'telefone', 'linkedin', 'local')) {
        if ($null -eq $dados.PSObject.Properties[$k]) { [void]$erros.Add(("dados_candidato: chave obrigatoria ausente: '{0}'" -f $k)) }
    }
}

try { $aplic = Get-Content $aplicCaminho -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
catch { $aplic = $null; [void]$erros.Add(('aplicadas: JSON invalido ou ilegivel ({0})' -f $_.Exception.Message)) }
$ordem = @(); $proximo = '?'
if ($null -ne $aplic) {
    if ($null -ne $aplic.rodizio) {
        if ($null -ne $aplic.rodizio.ordem) { $ordem = @($aplic.rodizio.ordem) }
        if ($null -ne $aplic.rodizio.proximo) { $proximo = [string]$aplic.rodizio.proximo }
    }
    if ($null -eq $aplic.PSObject.Properties['aplicadas']) { [void]$erros.Add("aplicadas: chave obrigatoria ausente: 'aplicadas'") }
    if ([string]::IsNullOrWhiteSpace($proximo) -or $proximo -eq '?') { [void]$erros.Add("aplicadas: chave obrigatoria ausente: 'rodizio.proximo'") }
}

$seguinte = '?'
if ($ordem.Count -gt 0 -and $ordem -contains $proximo) {
    $seguinte = $ordem[([Array]::IndexOf($ordem, $proximo) + 1) % $ordem.Count]
}

# Termos espelham bot/prompt_loop.md (secao b, TERMOS) — a rodada real alterna
# entre eles priorizando o stack real de dados_candidato.json.
$termos = @(
    'desenvolvedor fullstack junior',
    'backend junior remoto',
    'desenvolvedor junior remoto',
    'trainee desenvolvedor remoto'
)
$limite = 3  # regra 5 do prompt_loop.md: maximo 3 candidaturas novas por rodada
$nAplic = 0; $nBloq = 0
if ($null -ne $aplic) {
    if ($null -ne $aplic.aplicadas) { $nAplic = @($aplic.aplicadas).Count }
    if ($null -ne $aplic.bloqueados) {
        if ($aplic.bloqueados -is [System.Collections.IDictionary]) { $nBloq = $aplic.bloqueados.Count }
        else { $nBloq = @($aplic.bloqueados | Get-Member -MemberType NoteProperty).Count }
    }
}

if ($erros.Count -gt 0) {
    if ($json) {
        $out = @{ ok = $false; dry_run = $true; erros = @($erros) } | ConvertTo-Json -Depth 4
        Write-Host $out
    } else {
        Write-Host 'dry-run: FALHOU — corrija antes de rodar o loop real:'
        foreach ($x in $erros) { Write-Host ("  [FALHA] {0}" -f $x) }
    }
    exit 1
}

$dadosFonte = 'examples/dados_candidato.example.json'
if ($dadosReais) { $dadosFonte = 'bot/dados_candidato.json' }
$aplicFonte = 'examples/aplicadas.example.json'
if ($aplicReais) { $aplicFonte = 'bot/aplicadas.json' }

if ($json) {
    $out = [ordered]@{
        ok = $true
        dry_run = $true
        site = $proximo
        site_seguinte = $seguinte
        ordem_rodizio = @($ordem)
        termos_busca = @($termos)
        limite_candidaturas = $limite
        modelo_preferido = $ModeloPreferido
        dados_fonte = $dadosFonte
        estado_fonte = $aplicFonte
        aplicadas_registradas = $nAplic
        bloqueados_registrados = $nBloq
        browser_aberto = $false
        candidaturas_enviadas = 0
    } | ConvertTo-Json -Depth 4
    Write-Host $out
} else {
    Write-Host 'dry-run: UMA rodada simulada (nada foi enviado, nenhum browser aberto).'
    Write-Host ("  JSONs validos: {0} | {1}" -f $dadosCaminho, $aplicCaminho)
    Write-Host ("  site desta rodada (rodizio.proximo): {0}" -f $proximo)
    Write-Host ("  site seguinte sera: {0}" -f $seguinte)
    Write-Host ("  termos de busca que usaria: {0}" -f ($termos -join '; '))
    Write-Host ("  limite: {0} candidaturas novas (regra 5)" -f $limite)
    Write-Host ("  modelo preferido (1o da escada em bot/loop.ps1): {0}" -f $ModeloPreferido)
    Write-Host ("  estado atual: {0} aplicadas, {1} bloqueados" -f $nAplic, $nBloq)
}
exit 0
