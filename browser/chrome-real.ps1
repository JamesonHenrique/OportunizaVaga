# browser/chrome-real.ps1 — espelho Windows de browser/chrome-real.sh.
# Chrome persistente real para o agente (CDP): 1 login vale para tudo.
# Perfil em $env:LOCALAPPDATA\oportunizavaga-chrome-real (fora do git: guarda
# sessoes logadas — nunca commite). Suba antes do bot; guardiao.ps1 reinicia.
# Uso: powershell -ExecutionPolicy Bypass -File browser\chrome-real.ps1

$ErrorActionPreference = 'Stop'
$ProfileDir = Join-Path $env:LOCALAPPDATA 'oportunizavaga-chrome-real'
if (-not (Test-Path $ProfileDir)) { New-Item -ItemType Directory -Path $ProfileDir | Out-Null }

$Chrome = $null
foreach ($p in @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe")) {
    if (Test-Path $p) { $Chrome = $p; break }
}
if ([string]::IsNullOrWhiteSpace($Chrome)) {
    $cmd = Get-Command chrome -ErrorAction SilentlyContinue
    if ($cmd) { $Chrome = $cmd.Source }
}
if ([string]::IsNullOrWhiteSpace($Chrome)) {
    Write-Error 'Chrome nao encontrado (instale o Google Chrome primeiro).'
    exit 1
}

$Args = @(
    ("--user-data-dir={0}" -f $ProfileDir),
    '--remote-debugging-port=9222',
    '--remote-allow-origins=*',
    '--no-first-run',
    '--no-default-browser-check',
    'about:blank'
)
# Processo persistente: nao bloqueia o chamador (guardiao/loop seguem rodando).
Start-Process -FilePath $Chrome -ArgumentList $Args
