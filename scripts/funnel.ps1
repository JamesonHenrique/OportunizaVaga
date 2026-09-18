# scripts/funnel.ps1 — espelho simples de scripts/funnel.sh.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\funnel.ps1 [-Aplicadas PATH] [-Csv PATH]
# Senhor sem parâmetros: imprime o funil. -Csv exporta para funil.csv (ou PATH dado).
[CmdletBinding()]
param([string]$Aplicadas = '', [string]$Csv = '')
$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Aplicadas)) {
    if ($env:BOT_APLICADAS) { $Aplicadas = $env:BOT_APLICADAS }
    else { $Aplicadas = Join-Path $BOT_ROOT 'bot\aplicadas.json' }
}
if (-not (Test-Path $Aplicadas)) { Write-Error "aplicadas.json não encontrado: $Aplicadas"; exit 1 }

$d = Get-Content $Aplicadas -Raw | ConvertFrom-Json
$apl = @($d.aplicadas)
$bloqN = @($d.bloqueados.PSObject.Properties).Count
$desc = $d.descartes_listagem
$descTotal = 0
if ($desc) {
    if ($desc.total) { $descTotal = [int]$desc.total }
    else { foreach ($p in $desc.PSObject.Properties) { $descTotal += [int]$p.Value } }
}
$vistas = $descTotal + $apl.Count + $bloqN
$resps = @($apl | Where-Object { ($_.status -and $_.status -ne 'enviada') -or $_.respondida_em -or $_.desfecho })
$taxaAp = if ($vistas -gt 0) { [math]::Round(100.0 * $apl.Count / $vistas, 1) } else { 0 }
$taxaRp = if ($apl.Count -gt 0) { [math]::Round(100.0 * $resps.Count / $apl.Count, 1) } else { 0 }

'Funil vistas -> aplicadas -> respostas'
('  {0,-10} {1}' -f 'vistas', $vistas)
('  {0,-10} {1}' -f 'aplicadas', $apl.Count)
('  {0,-10} {1}' -f 'respostas', $resps.Count)
"Taxa vistas->aplicadas: $taxaAp% | aplicadas->respostas: $taxaRp%"
"Descartes na listagem: $descTotal | Bloqueadas: $bloqN"

if ($PSBoundParameters.ContainsKey('Csv')) {
    if ([string]::IsNullOrWhiteSpace($Csv)) { $Csv = 'funil.csv' }
    "etapa,quantidade`nvistas,$vistas`naplicadas,$($apl.Count)`nrespostas,$($resps.Count)" | Out-File -FilePath $Csv -Encoding utf8
    "CSV exportado: $Csv"
}
