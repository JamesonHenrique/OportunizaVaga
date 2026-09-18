# scripts/setup.ps1 — instalador interativo do OportunizaVaga (Windows).
# Espelho de scripts/setup.sh: copia os .example, valida dependencias e imprime
# os comandos schtasks sugeridos. Seguro: nunca apaga arquivo existente,
# nunca commita nada. Requer PowerShell 5.1+.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = 'SilentlyContinue'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $BOT_ROOT

function Write-Ok([string]$m) { Write-Host ("  [ok] {0}" -f $m) }
function Write-Bad([string]$m) { Write-Host ("  [!!] {0}" -f $m) }

Write-Host '== OportunizaVaga — setup (Windows) =='
Write-Host ("Raiz: {0}" -f $BOT_ROOT)
Write-Host ''

function Copy-Example([string]$src, [string]$dst) {
    if (Test-Path $dst) {
        Write-Host ("  [pq] {0} ja existe — mantido." -f $dst)
    } else {
        Copy-Item $src $dst
        Write-Host ("  [ok] criado {0} (PREENCHA com seus dados — nunca commite)." -f $dst)
    }
}

Write-Host '-- 1) Arquivos de dados (gitignored) --'
Copy-Example 'examples\dados_candidato.example.json' 'bot\dados_candidato.json'
Copy-Example 'examples\aplicadas.example.json' 'bot\aplicadas.json'
$CronEnv = Join-Path $env:USERPROFILE '.config\opencode\cron.env'
if (Test-Path $CronEnv) {
    Write-Ok '.config\opencode\cron.env existe (chaves fora do repo).'
} else {
    Write-Bad '.config\opencode\cron.env AUSENTE — crie com suas chaves:'
    Write-Host '       $null = New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\opencode"'
    Write-Host '       notepad "$env:USERPROFILE\.config\opencode\cron.env"  # OPENROUTER_API_KEY=... (so se USAR_OPENROUTER=1)'
}
Write-Host ''

Write-Host '-- 2) Dependencias --'
$HAVE_ALL = $true
foreach ($bin in @('node', 'python', 'git')) {
    if (Get-Command $bin -ErrorAction SilentlyContinue) { Write-Ok $bin }
    else { Write-Bad ("{0} NAO encontrado" -f $bin); $HAVE_ALL = $false }
}
if (Get-Command opencode -ErrorAction SilentlyContinue) { Write-Ok 'opencode' }
else {
    Write-Bad 'opencode ausente — instale via winget (se publicado) ou https://opencode.ai:'
    Write-Host '       winget install opencode   # se disponivel; senao siga o instalador do site'
    $HAVE_ALL = $false
}
$ChromeFound = $false
foreach ($p in @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe")) {
    if (Test-Path $p) { $ChromeFound = $true }
}
if (Get-Command chrome -ErrorAction SilentlyContinue) { $ChromeFound = $true }
if ($ChromeFound) { Write-Ok 'chrome' }
else { Write-Bad 'Chrome ausente (necessario p/ browser\chrome-real.ps1)'; $HAVE_ALL = $false }
# ExecutionPolicy afeta a primeira execucao dos .ps1.
try {
    $pol = Get-ExecutionPolicy -Scope CurrentUser
    Write-Host ("  [..] ExecutionPolicy (CurrentUser): {0}" -f $pol)
    if ($pol -eq 'Restricted' -or $pol -eq 'AllSigned') {
        Write-Host '       Rode 1x como usuario: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned'
    }
} catch { }
Write-Host ''

Write-Host '-- 3) Validacao rapida (JSON) --'
try {
    Get-Content 'config\sites_permitidos.json' -Raw | ConvertFrom-Json | Out-Null
    Write-Ok 'sites_permitidos.json valido.'
} catch { Write-Bad 'sites_permitidos.json invalido.'; $HAVE_ALL = $false }
try {
    Get-Content 'examples\dados_candidato.example.json' -Raw | ConvertFrom-Json | Out-Null
    Get-Content 'examples\aplicadas.example.json' -Raw | ConvertFrom-Json | Out-Null
    Write-Ok 'examples/*.json validos.'
} catch { Write-Bad 'example .json invalido (veja acima).'; $HAVE_ALL = $false }
Write-Host ''

Write-Host '-- 4) Agendamento sugerido (Task Scheduler — ajuste os caminhos) --'
Write-Host ("  BOT_DIR={0}" -f $BOT_ROOT)
Write-Host ''
Write-Host '  # Guardiao a cada 5min (loop + Chrome):'
Write-Host ('  schtasks /Create /TN "OportunizaVaga\Guardiao" /TR "powershell -ExecutionPolicy Bypass -File \"{0}\bot\guardiao.ps1\"" /SC MINUTE /MO 5 /F' -f $BOT_ROOT)
Write-Host ''
Write-Host '  # Guardiao no logon:'
Write-Host ('  schtasks /Create /TN "OportunizaVaga\GuardiaoLogon" /TR "powershell -ExecutionPolicy Bypass -File \"{0}\bot\guardiao.ps1\"" /SC ONLOGON /F' -f $BOT_ROOT)
Write-Host ''
Write-Host '  # Follow-up semanal (seg 09:00):'
Write-Host ('  schtasks /Create /TN "OportunizaVaga\Followup" /TR "powershell -ExecutionPolicy Bypass -File \"{0}\bot\followup.ps1\"" /SC WEEKLY /D MON /ST 09:00 /F' -f $BOT_ROOT)
Write-Host ''
Write-Host '  Guia completo em config\TaskScheduler.md (equivale ao config\crontab.example).'
Write-Host ''
Write-Host '-- 5) Validacao contra schemas (scripts\validate.ps1) --'
& (Join-Path $BOT_ROOT 'scripts\validate.ps1')
if ($LASTEXITCODE -eq 0) { Write-Ok 'JSONs conferem com os schemas em config/.' }
else { Write-Bad 'validate.ps1 falhou (veja acima) — corrija antes de rodar o loop.'; $HAVE_ALL = $false }
Write-Host ''
if ($HAVE_ALL) { Write-Host 'Setup pronto. Proximo passo: docs/QUICKSTART.md (aba Windows).' }
else { Write-Host 'Resolva os itens [!!] acima e rode de novo.' }
