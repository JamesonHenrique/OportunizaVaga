# bot/dry-run.ps1 — espelho Windows (PowerShell 5.1+) de bot/dry-run.sh.
# Simula UMA rodada global sem se candidatar (teste sem risco). So LE arquivos:
# valida os JSONs, monta o plano por site e mostra o que a rodada FARIA.
# Nao abre browser, nao chama o opencode, nao escreve nada, nao se candidata.
# Uso: powershell -ExecutionPolicy Bypass -File bot\dry-run.ps1 [-json] [-Site indeed] [-Profile caminho] [-Reconhecimento]

[CmdletBinding()]
param(
    [switch]$json,
    [switch]$help,
    [string]$Site,
    [string]$Profile,
    [switch]$Reconhecimento
)

$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $BOT_ROOT 'bot')

if ($help) {
    Write-Host 'Uso: bot\dry-run.ps1 [-json] [-Site SITE_ID] [-Profile CAMINHO] [-Reconhecimento]'
    Write-Host 'Plano global: todos os adaptadores; nada e escrito, nenhum browser e aberto.'
    exit 0
}

function Resolve-Profile {
    param([string]$ExplicitProfile)

    $profilePath = $ExplicitProfile
    if ([string]::IsNullOrWhiteSpace($profilePath)) { $profilePath = $env:BOT_PERFIL }
    if ([string]::IsNullOrWhiteSpace($profilePath)) {
        $candidate = Join-Path $BOT_ROOT 'bot\perfil.json'
        if (Test-Path $candidate) { $profilePath = $candidate }
    }
    if ([string]::IsNullOrWhiteSpace($profilePath)) {
        $profilePath = Join-Path $BOT_ROOT 'config\perfis\junior-backend.example.json'
    }
    if (-not (Test-Path $profilePath)) {
        throw "perfil nao encontrado: $profilePath"
    }
    return $profilePath
}

function Get-Slug {
    param([string]$Name)
    $slug = $Name.ToLowerInvariant() -replace '[^a-z0-9]+', '-'
    $slug = $slug.Trim('-')
    if ($slug.Length -gt 48) { $slug = $slug.Substring(0, 48) }
    return $slug
}

$ProfileFile = Resolve-Profile $Profile
$ExplicitProfile = $false
if ((-not [string]::IsNullOrWhiteSpace($Profile)) -or (-not [string]::IsNullOrWhiteSpace($env:BOT_PERFIL)) -or (Test-Path (Join-Path $BOT_ROOT 'bot\perfil.json'))) {
    $ExplicitProfile = $true
}
if ($ProfileFile -ne (Join-Path $BOT_ROOT 'config\perfis\junior-backend.example.json')) {
    $ExplicitProfile = $true
}

$PerfilDoc = $null
try { $PerfilDoc = Get-Content $ProfileFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
catch { throw "perfil: JSON invalido ou ilegivel ($($_.Exception.Message))" }

foreach ($key in @('nome_perfil', 'nivel', 'termos', 'pular_tipos')) {
    if ($null -eq $PerfilDoc.PSObject.Properties[$key]) { throw "perfil: chave obrigatoria ausente: '$key'" }
}
if (-not $PerfilDoc.termos -or @($PerfilDoc.termos).Count -eq 0) { throw 'perfil: termos precisa ser uma lista nao vazia' }

$PerfilNome = [string]$PerfilDoc.nome_perfil
$PerfilSlug = Get-Slug $PerfilNome
if ($ExplicitProfile) { $StateDir = Join-Path $BOT_ROOT "bot\state\$PerfilSlug" } else { $PerfilSlug = 'default'; $StateDir = Join-Path $BOT_ROOT 'bot' }
$AplicadasFile = Join-Path $StateDir 'aplicadas.json'
if (-not (Test-Path $AplicadasFile)) { $AplicadasFile = Join-Path $BOT_ROOT 'examples\aplicadas.example.json' }
$DadosFile = Join-Path $BOT_ROOT 'bot\dados_candidato.json'
if (-not (Test-Path $DadosFile)) { $DadosFile = Join-Path $BOT_ROOT 'examples\dados_candidato.example.json' }

$DadosDoc = $null
try { $DadosDoc = Get-Content $DadosFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
catch { throw "dados_candidato: JSON invalido ou ilegivel ($($_.Exception.Message))" }
foreach ($key in @('nome', 'email', 'telefone', 'linkedin', 'local')) {
    if ($null -eq $DadosDoc.PSObject.Properties[$key]) { throw "dados_candidato: chave obrigatoria ausente: '$key'" }
}

$AplicDoc = $null
try { $AplicDoc = Get-Content $AplicadasFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
catch { throw "aplicadas: JSON invalido ou ilegivel ($($_.Exception.Message))" }
if ($null -eq $AplicDoc.PSObject.Properties['aplicadas']) { throw "aplicadas: chave obrigatoria ausente: 'aplicadas'" }
if ($null -eq $AplicDoc.rodizio -or [string]::IsNullOrWhiteSpace([string]$AplicDoc.rodizio.proximo)) {
    throw "aplicadas: chave obrigatoria ausente: 'rodizio.proximo'"
}

$Sites = New-Object System.Collections.ArrayList
$adapterDir = Join-Path $BOT_ROOT 'bot\sites'
foreach ($file in (Get-ChildItem $adapterDir -Filter '*.sh' | Sort-Object Name)) {
    if ($file.Name -eq '_template.sh' -or $file.Name -eq 'lib.sh') { continue }
    $text = Get-Content $file.FullName -Raw
    $siteId = [regex]::Match($text, 'SITE_ID="([^"]+)"').Groups[1].Value
    if ([string]::IsNullOrWhiteSpace($siteId)) { continue }
    if ((-not [string]::IsNullOrWhiteSpace($Site)) -and ($siteId -ne $Site)) { continue }
    $label = [regex]::Match($text, 'SITE_LABEL="([^"]+)"').Groups[1].Value
    if ([string]::IsNullOrWhiteSpace($label)) { $label = $siteId }
    $home = [regex]::Match($text, 'SITE_HOME="([^"]+)"').Groups[1].Value
    $template = [regex]::Match($text, 'SEARCH_URL_TEMPLATE="([^"]+)"').Groups[1].Value
    if ([string]::IsNullOrWhiteSpace($template)) { throw "adaptador invalido: $siteId (sem SEARCH_URL_TEMPLATE)" }
    $term = [string]@($PerfilDoc.termos)[0]
    $encoded = if ($template -like '*vagas-de-*') { $term.Replace(' ', '-') } else { $term.Replace(' ', '%20') }
    $url = $template.Replace('SEU_TERMO', $encoded)
    [void]$Sites.Add([ordered]@{
        site_id = $siteId
        label = $label
        home = $home
        termos = @($PerfilDoc.termos)
        url_busca = $url
    })
}

$ModeloPreferido = 'openrouter/nex-agi/nex-n2.5-pro:free'
$ProximoSite = $null
if ($null -ne $AplicDoc.rodizio) { $ProximoSite = [string]$AplicDoc.rodizio.proximo }

$Result = [ordered]@{
    ok = $true
    dry_run = $true
    global = [string]::IsNullOrWhiteSpace($Site)
    modo = if ($Reconhecimento) { 'reconhecimento' } else { 'candidaturas' }
    perfil = [ordered]@{
        nome = $PerfilNome
        slug = $PerfilSlug
        arquivo = $ProfileFile
        nivel = [string]$PerfilDoc.nivel
        termos = @($PerfilDoc.termos)
        pular_tipos = @($PerfilDoc.pular_tipos)
    }
    estado = [ordered]@{
        diretorio = $StateDir
        arquivo_aplicadas = $AplicadasFile
        isolado = ($PerfilSlug -ne 'default')
        aplicadas_registradas = @($AplicDoc.aplicadas).Count
        proximo_site = $ProximoSite
    }
    sites = @($Sites)
    site_count = $Sites.Count
    limite_candidaturas = 3
    limite_reconhecimento = 10
    modelo_preferido = $ModeloPreferido
    browser_aberto = $false
    candidaturas_enviadas = 0
    telemetria = [ordered]@{
        modo = 'aggregate'
        detalhes = $false
    }
}

if ($json) {
    $out = $Result | ConvertTo-Json -Depth 6
    Write-Output $out
} else {
    Write-Host 'dry-run global: plano de uma rodada (nada foi enviado, nenhum browser aberto).'
    Write-Host ("  perfil: {0} | estado isolado: {1}" -f $PerfilNome, $Result.estado.isolado)
    Write-Host ("  sites: {0} | proximo do rodizio: {1}" -f $Sites.Count, $ProximoSite)
    foreach ($site in $Sites) {
        Write-Host ("  - {0}: {1}" -f $site.site_id, $site.url_busca)
    }
}
exit 0
