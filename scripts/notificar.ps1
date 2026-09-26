# scripts/notificar.ps1 — espelho Windows de scripts/notificar.sh.
# Push generico via Telegram Bot API (sendMessage). Silencioso sem
# $env:TELEGRAM_BOT_TOKEN e $env:TELEGRAM_CHAT_ID (mesmas envs do digest.ps1
# -Send; nunca hardcode, nunca imprime o token).
# Dedupe: a MESMA mensagem nao e reenviada dentro de 6h (state/notify-sent).
# Uso: powershell -ExecutionPolicy Bypass -File scripts\notificar.ps1 "texto"
[CmdletBinding()]
param([Parameter(Position = 0)][string]$Mensagem = '')
$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($Mensagem)) { exit 0 }
$tok = $env:TELEGRAM_BOT_TOKEN
$chat = $env:TELEGRAM_CHAT_ID
if (-not $tok -or -not $chat) { exit 0 }

$StatePath = if ($env:OV_NOTIFY_STATE) { $env:OV_NOTIFY_STATE } else { Join-Path $BOT_ROOT 'bot\state\notify-sent' }
$StateDir = Split-Path -Parent $StatePath
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
if (-not (Test-Path $StatePath)) { New-Item -ItemType File -Path $StatePath | Out-Null }

$md5 = [System.Security.Cryptography.MD5]::Create()
$hashBytes = $md5.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Mensagem))
$Key = ([System.BitConverter]::ToString($hashBytes) -replace '-', '').ToLowerInvariant().Substring(0, 12)
$Now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

$linhas = @(Get-Content $StatePath -ErrorAction SilentlyContinue)
foreach ($l in $linhas) {
    $partes = $l -split '\s+'
    if ($partes.Count -ge 2 -and $partes[0] -eq $Key) {
        if (($Now - [int64]$partes[1]) -lt 21600) { exit 0 }   # mesma mensagem enviada nas ultimas 6h
    }
}

try {
    $uri = "https://api.telegram.org/bot$tok/sendMessage"
    Invoke-RestMethod -Uri $uri -Method Post -Body @{ chat_id = $chat; text = $Mensagem } -TimeoutSec 15 | Out-Null
    Add-Content -Path $StatePath -Value ("{0} {1}" -f $Key, $Now)
    $kept = Get-Content $StatePath -ErrorAction SilentlyContinue | Select-Object -Last 200
    Set-Content -Path $StatePath -Value $kept
} catch { }
exit 0
