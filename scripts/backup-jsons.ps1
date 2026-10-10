# scripts/backup-jsons.ps1 — espelho Windows de scripts/backup-jsons.sh.
# Copia versionada dos JSONs-estado (aplicadas.json, dados_candidato.json, por
# perfil). So LE os arquivos vivos e ESCREVE em bot\backups\ (nunca toca no
# original). Guarda as ultimas 14 copias por arquivo.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\backup-jsons.ps1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
$Dest = if ($env:OV_BACKUP_DIR) { $env:OV_BACKUP_DIR } else { Join-Path $BOT_ROOT 'bot\backups' }
if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }
$Stamp = (Get-Date).ToString('yyyyMMdd-HHmm')
$Keep = 14
$Rc = 0

function Backup-File([string]$Src, [string]$Prefix) {
    if (-not (Test-Path $Src)) { return }   # perfil/arquivo ainda nao existe: nada a fazer
    $destFile = Join-Path $Dest ("{0}.{1}.json" -f $Prefix, $Stamp)
    try {
        Get-Content -Path $Src -Raw -Encoding UTF8 | ConvertFrom-Json | Out-Null
    } catch {
        # Corrupt source: skip it and keep the old copies (otherwise rotation would push them out).
        Write-Error ("[{0}] FALHA: {1} nao e JSON valido - backup pulado" -f $Stamp, $Src) -ErrorAction Continue
        $script:Rc = 1
        return
    }
    try {
        Copy-Item -Path $Src -Destination $destFile -Force
        Write-Output ("[{0}] ok: {1} -> {2}" -f $Stamp, $Src, (Split-Path -Leaf $destFile))
    } catch {
        Write-Error ("[{0}] FALHA ao copiar: {1}" -f $Stamp, $Src) -ErrorAction Continue
        $script:Rc = 1
        return
    }
    # rotacao: mantem as 14 mais recentes
    $existentes = Get-ChildItem -Path $Dest -Filter ("{0}.*.json" -f $Prefix) -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match ('^' + [regex]::Escape($Prefix) + '\.\d') } |
        Sort-Object LastWriteTime -Descending
    if ($existentes -and $existentes.Count -gt $Keep) {
        $existentes | Select-Object -Skip $Keep | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

# 1) estado raiz (perfil default / sem perfil)
Backup-File (Join-Path $BOT_ROOT 'bot\aplicadas.json') 'aplicadas'
Backup-File (Join-Path $BOT_ROOT 'bot\dados_candidato.json') 'dados_candidato'

# 2) estado isolado de CADA perfil ativo (bot\state\<slug>\), se houver.
$stateRoot = Join-Path $BOT_ROOT 'bot\state'
if (Test-Path $stateRoot) {
    Get-ChildItem -Path $stateRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $slug = $_.Name
        $aplicadas = Join-Path $_.FullName 'aplicadas.json'
        $dados = Join-Path $_.FullName 'dados_candidato.json'
        if (Test-Path $aplicadas) {
            Backup-File $aplicadas ("aplicadas.perfil-{0}" -f $slug)
            Backup-File $dados ("dados.perfil-{0}" -f $slug)
        }
    }
}
exit $Rc
