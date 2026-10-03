# scripts/funnel.ps1 — casca do funil de candidatura, espelho de scripts/funnel.sh.
# A lógica esta em bot/funil.py (fonte unica, compartilhada com o Linux e coberta por
# tests/test_funil.sh): aqui so resolvemos o caminho do python e repassamos os flags.
# Sem python, avisa e sai em vez de duplicar a regra de contagem.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\funnel.ps1 [-Aplicadas PATH] [-Csv PATH] [-Markdown PATH] [-Json]
[CmdletBinding()]
param(
    [string]$Aplicadas = '',
    [string]$Csv = '',
    [string]$Markdown = '',
    [switch]$Json
)
$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($Aplicadas)) {
    if ($env:BOT_APLICADAS) { $Aplicadas = $env:BOT_APLICADAS }
    else { $Aplicadas = Join-Path $BOT_ROOT 'bot/aplicadas.json' }
}
$FunilPy = Join-Path $BOT_ROOT 'bot/funil.py'

$Py = $null
foreach ($c in @('python3', 'python', 'py')) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $Py = (Get-Command $c).Source; break }
}
if (-not $Py) {
    Write-Error 'funnel.ps1: python3 nao encontrado no PATH (a logica do funil esta em bot/funil.py)'
    exit 1
}

$args = @($FunilPy, '--aplicadas', $Aplicadas)
if ($Json) { $args += '--json' }
# -Csv/-Markdown com valor vazio = nome padrao (o argparse resolve com nargs='?').
if ($PSBoundParameters.ContainsKey('Csv')) { $args += @('--csv', $(if ($Csv) { $Csv } else { 'funil.csv' })) }
if ($PSBoundParameters.ContainsKey('Markdown')) { $args += @('--markdown', $(if ($Markdown) { $Markdown } else { 'funil.md' })) }

& $Py @args
exit $LASTEXITCODE