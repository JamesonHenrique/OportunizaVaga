# bot/doctor.ps1 — espelho Windows (PowerShell 5.1+) de bot/doctor.sh.
# Checklist de diagnostico (saida colavel em issue).
# Checa: versao do PowerShell, node, opencode, chrome, CDP 127.0.0.1:9222,
# JSONs presentes e validos, cron.env ausente do git, espaco em disco.
# Exit 0 = essencial ok (avisos [??] permitidos); 1 = falta algo essencial.
# So LE o sistema: nao abre browser, nao se candidata, nao altera nada.
# Uso: powershell -ExecutionPolicy Bypass -File bot\doctor.ps1

$ErrorActionPreference = 'SilentlyContinue'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $BOT_ROOT 'bot')

$script:FaltaEssencial = 0
function Write-Ok([string]$m) { Write-Host ("  [ok] {0}" -f $m) }
function Write-Info([string]$m) { Write-Host ("  [..] {0}" -f $m) }
function Write-Aviso([string]$m, [string]$dica) { Write-Host ("  [??] {0} -- {1}" -f $m, $dica) }
function Write-Falha([string]$m, [string]$dica) { Write-Host ("  [FALHA] {0} -- {1}" -f $m, $dica); $script:FaltaEssencial = 1 }

function Test-JsonValido([string]$f) {
    try { Get-Content $f -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop | Out-Null; return $true }
    catch { return $false }
}

Write-Host '== OportunizaVaga — doctor (Windows) =='
Write-Host ("Raiz: {0}" -f $BOT_ROOT)
Write-Host ("Data: {0}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))
Write-Host ''

Write-Host '-- 1) Interpretador --'
Write-Info ("PowerShell {0}" -f $PSVersionTable.PSVersion)
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-Aviso 'PowerShell < 5.1' 'atualize para PowerShell 5.1+ (scripts espelho exigem).'
} else {
    Write-Ok 'PowerShell'
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Ok 'python (presente; validate usa se achar jsonschema).'
} else {
    Write-Info 'python ausente — validate cai para checagem minima nativa (ok).'
}
Write-Host ''

Write-Host '-- 2) Dependencias do loop real --'
if (Get-Command node -ErrorAction SilentlyContinue) { Write-Ok 'node' }
else { Write-Falha 'node ausente' 'instale Node 20+ (veja docs/QUICKSTART.md).' }
if (Get-Command opencode -ErrorAction SilentlyContinue) { Write-Ok 'opencode' }
elseif (Test-Path (Join-Path $env:USERPROFILE '.opencode\bin\opencode.exe')) { Write-Ok 'opencode (%USERPROFILE%\.opencode\bin)' }
else { Write-Falha 'opencode ausente' 'instale via https://opencode.ai (veja docs/QUICKSTART.md).' }
$chromeOk = $false
foreach ($p in @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe")) {
    if (Test-Path $p) { $chromeOk = $true }
}
if (Get-Command chrome -ErrorAction SilentlyContinue) { $chromeOk = $true }
if ($chromeOk) { Write-Ok 'chrome' }
else { Write-Falha 'Chrome ausente' 'instale o Chrome (necessario p/ browser\chrome-real.ps1).' }
Write-Host ''

Write-Host '-- 3) Chrome CDP (127.0.0.1:9222) --'
$cdpOk = $false
try {
    $c = New-Object Net.Sockets.TcpClient
    $r = $c.BeginConnect('127.0.0.1', 9222, $null, $null)
    $cdpOk = $r.AsyncWaitHandle.WaitOne(5000)
    $c.Close()
} catch { $cdpOk = $false }
if ($cdpOk) { Write-Ok 'CDP acessivel (Chrome com remote debugging aberto).' }
else { Write-Aviso 'CDP 127.0.0.1:9222 inacessivel' 'suba com browser\chrome-real.ps1 e faca login 1x (aviso: nao bloqueia nada, so o loop real precisa).' }
Write-Host ''

Write-Host '-- 4) JSONs (presentes e validos) --'
foreach ($f in @((Join-Path $BOT_ROOT 'examples\dados_candidato.example.json'), (Join-Path $BOT_ROOT 'examples\aplicadas.example.json'))) {
    if (-not (Test-Path $f)) { Write-Falha ("{0} ausente" -f $f) ("restaure com git checkout -- {0}." -f $f) }
    elseif (Test-JsonValido $f) { Write-Ok ("{0} valido." -f (Split-Path $f -Leaf)) }
    else { Write-Falha ("{0} invalido" -f (Split-Path $f -Leaf)) 'rode scripts\validate.ps1 p/ detalhes e corrija o JSON.' }
}
foreach ($f in @('dados_candidato.json', 'aplicadas.json')) {
    if (-not (Test-Path $f)) { Write-Info ("{0} ausente (normal antes do setup — sera copiado do .example)." -f $f) }
    elseif (Test-JsonValido $f) { Write-Ok ("{0} valido." -f $f) }
    else { Write-Falha ("{0} invalido" -f $f) 'rode scripts\validate.ps1 p/ detalhes e corrija o JSON.' }
}
Write-Host ''

Write-Host '-- 5) Segredos fora do git --'
$gitOk = $false
try { git rev-parse --is-inside-work-tree 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { $gitOk = $true } } catch { }
if ($gitOk) {
    $vazou = git ls-files 2>$null | Select-String -Pattern '(cron\.env|dados_candidato\.json|aplicadas\.json|auth\.json)$'
    if ($vazou) { Write-Falha ("arquivo sensivel rastreado pelo git: {0}" -f ($vazou -join ', ')) 'remova com git rm --cached <arq> e confira o .gitignore; segredo visto = comprometido.' }
    else { Write-Ok 'nenhum cron.env/dados/aplicadas/auth rastreado.' }
} else {
    Write-Info 'fora de repo git — checagem de tracked pulada.'
}
$CronEnv = Join-Path $env:USERPROFILE '.config\opencode\cron.env'
if (Test-Path $CronEnv) { Write-Ok 'cron.env existe (chaves fora do repo).' }
else { Write-Aviso 'cron.env ausente' 'crie %USERPROFILE%\.config\opencode\cron.env (veja docs/QUICKSTART.md sec. 3).' }
Write-Host ''

Write-Host '-- 6) Disco --'
try {
    $drive = (Get-Item $BOT_ROOT).PSDrive.Name
    $freeMB = [int]((Get-PSDrive $drive).Free / 1MB)
    if ($freeMB -lt 500) { Write-Falha ("disco com {0}MB livres" -f $freeMB) 'libere espaco (logs em bot\logs, perfil do Chrome).' }
    elseif ($freeMB -lt 2048) { Write-Aviso ("disco com {0}MB livres" -f $freeMB) 'fique de olho; logs e perfil do Chrome crescem.' }
    else { Write-Ok ("disco ({0}MB livres)." -f $freeMB) }
} catch {
    Write-Info 'nao foi possivel medir espaco em disco.'
}
Write-Host ''

if ($script:FaltaEssencial -eq 0) { Write-Host 'doctor: essencial OK (resolva os [??] se for rodar o loop real).' }
else { Write-Host 'doctor: FALHOU — resolva os itens [FALHA] acima e rode de novo.' }
Write-Host 'Para colar numa issue: copie deste bloco para cima e confira que nao ha dados pessoais.'
exit $script:FaltaEssencial
