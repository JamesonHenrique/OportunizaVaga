# setup-wizard.ps1 — espelho Windows de setup-wizard.sh.
# Cria bot\dados_candidato.json por perguntas, a partir do exemplo oficial.
# O arquivo gerado e gitignored e NUNCA vai ao repo.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\setup-wizard.ps1
$ErrorActionPreference = "Stop"
$BotRoot = Split-Path -Parent $PSScriptRoot
Set-Location $BotRoot

$Exemplo = "examples/dados_candidato.example.json"
$Destino = "bot/dados_candidato.json"

if (-not (Test-Path $Exemplo)) { Write-Error "faltando $Exemplo"; exit 1 }
if (Test-Path $Destino) {
  $ok = Read-Host "$Destino ja existe. Sobrescrever? [s/N]"
  if ($ok -notmatch '^(s|S|sim|Sim)$') { Write-Host "cancelado."; exit 0 }
}

Write-Host "Preencha com dados REAIS. Deixe em branco o que nao quiser informar —"
Write-Host "campo vazio faz o robo registrar 'bloqueado' em vez de inventar. (Enter pula.)"
Write-Host ""

function Ask($p) { return (Read-Host $p) }

$nome     = Ask "Nome completo"
$email    = Ask "E-mail"
$telefone = Ask "Telefone (+55 (00) 90000-0000)"
$linkedin = Ask "URL do LinkedIn"
$github   = Ask "URL do GitHub"
$local    = Ask "Cidade/UF"
$formacao = Ask "Formacao (curso - instituicao - periodo)"
$idiomas  = Ask "Idiomas (so o real, ex.: Portugues nativo; Ingles intermediario)"
$objetivo = Ask "Objetivo (ex.: tech lead remoto, advogado pleno remoto)"
$resumo   = Ask "Resumo profissional (3-4 linhas verdadeiras)"
$techs    = Ask "Tecnologias que voce domina (separadas por virgula)"
$nivel    = Ask "Niveis aceitos, separados por virgula (estagio, trainee, junior, pleno, senior, especialista, lider, gestor, diretor)"

$d = Get-Content $Exemplo -Raw | ConvertFrom-Json

function SetIf($obj, $prop, $val) { if ($val -and $val.Trim().Length -gt 0) { $obj.$prop = $val } }
SetIf $d "nome" $nome
SetIf $d "email" $email
SetIf $d "telefone" $telefone
SetIf $d "linkedin" $linkedin
SetIf $d "github" $github
SetIf $d "local" $local
SetIf $d "formacao" $formacao
SetIf $d "idiomas" $idiomas
SetIf $d "objetivo" $objetivo
SetIf $d "resumo" $resumo

if ($techs -and $techs.Trim().Length -gt 0) {
  $arr = @($techs -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 })
  $d.experiencia.tecnologias = $arr
  $d.palavras_chave_ats = $arr
}
if ($nivel -and $nivel.Trim().Length -gt 0) { $d.situacao_profissional.nivel = (($nivel -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join '|') }

$d | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $Destino
Write-Host ""
Write-Host "Gerado: $Destino (gitignored — nao commite)."

# ---- Perfil de busca (bot\perfil.json): nivel, area, modelo e termos ----
function Lista([string]$s) { @($s -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 }) }
$PerfilDestino = "bot/perfil.json"
$geraPerfil = $true
if (Test-Path $PerfilDestino) {
  $ok = Read-Host "$PerfilDestino ja existe. Sobrescrever? [s/N]"
  if ($ok -notmatch '^(s|sim)$') { $geraPerfil = $false }
}
if ($geraPerfil) {
  Write-Host ""
  Write-Host "Perfil de busca (o que o robo aceita/recusa):"
  $area    = Ask "Area de atuacao (ex.: tecnologia, juridico, marketing, saude)"
  $modelos = Ask "Modelos aceitos, separados por virgula (remoto, hibrido, presencial) [remoto]"
  $cidades = Ask "Cidades p/ hibrido/presencial, separadas por virgula (Enter = $local)"
  $termos  = Ask "Termos de busca, separados por virgula (ex.: tech lead remoto, advogado pleno)"
  $pular   = Ask "Tipos de vaga a pular, separados por virgula (opcional)"
  $alias = @{ 'estágio' = 'estagio'; 'estagiario' = 'estagio'; 'júnior' = 'junior'; 'jr' = 'junior'; 'sênior' = 'senior'; 'sr' = 'senior';
              'líder' = 'lider'; 'tech lead' = 'lider'; 'gerente' = 'gestor'; 'híbrido' = 'hibrido' }
  $canon = { param($x) $k = $x.ToLowerInvariant(); if ($alias.ContainsKey($k)) { $alias[$k] } else { $k } }
  $validos = @('estagio', 'trainee', 'junior', 'pleno', 'senior', 'especialista', 'lider', 'gestor', 'diretor')
  $niveis = @(Lista $nivel | ForEach-Object { & $canon $_ } | Where-Object { $validos -contains $_ })
  if (-not $niveis.Count) { $niveis = @('junior', 'trainee') }
  $mods = @(Lista $modelos | ForEach-Object { & $canon $_ } | Where-Object { @('remoto', 'hibrido', 'presencial') -contains $_ })
  if (-not $mods.Count) { $mods = @('remoto') }
  $termosL = @(Lista $termos)
  if (-not $termosL.Count -and $objetivo) { $termosL = @($objetivo.Trim()) }
  if (-not $termosL.Count) { Write-Host "perfil: informe ao menos um termo de busca (ou o objetivo) e rode de novo."; exit 1 }
  $areaTxt = if ($area) { $area.Trim() } else { 'tecnologia' }
  $perfil = [ordered]@{
    nome_perfil = "$($niveis[-1])-$(($areaTxt -split ' ')[0].ToLowerInvariant())"
    niveis = $niveis
    area = $areaTxt
    modelos = $mods
    termos = $termosL
    pular_tipos = @(Lista $pular)
  }
  $cid = @(Lista $cidades); if ($cid.Count) { $perfil.cidades = $cid }
  $perfil | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $PerfilDestino
  Write-Host "Gerado: $PerfilDestino (gitignored). Confira: .\bot\dry-run.ps1"
}
Write-Host "Proximo: .\browser\chrome-real.ps1  entao  .\bot\dry-run.ps1  (ver docs/QUICKSTART.md)."
