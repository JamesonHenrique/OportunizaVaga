# scripts/validate-rodada.ps1 — espelho Windows (PowerShell 5.1+) de scripts/validate-rodada.sh.
# Sanidade semantica de aplicadas.json (a logica vive em validate-rodada.py, multiplataforma).
# Exit 0 = ok; 1 = falha. Sem python no PATH, avisa e sai 0 (nao bloqueia o loop).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\validate-rodada.ps1 [aplicadas.json]

param([string]$Arquivo)

$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $BOT_ROOT
$Py = $null
foreach ($c in @('python3', 'python', 'py')) {
    $g = Get-Command $c -ErrorAction SilentlyContinue
    if ($g) { $Py = $g.Source; break }
}
if (-not $Py) { Write-Host '[pq] python nao encontrado — validate-rodada pulado.'; exit 0 }
$script = Join-Path $BOT_ROOT 'scripts\validate-rodada.py'
if ($Arquivo) { & $Py $script $Arquivo } else { & $Py $script }
exit $LASTEXITCODE
