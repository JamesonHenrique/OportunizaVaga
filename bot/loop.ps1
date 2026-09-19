# bot/loop.ps1 — espelho Windows (PowerShell 5.1+) de bot/loop.sh.
# Mantem o Linux intacto: a logica do .sh nao foi alterada, este arquivo apenas
# replica comportamento (mesma escada de modelos, mesmos tempos de espera).
# Requer PowerShell 5.1+ (compativel com Windows PowerShell e PowerShell 7+).
# Uso: powershell -ExecutionPolicy Bypass -File bot\loop.ps1
#
# TZ / FUSO (importante, leia):
# $env:BOT_TZ continua documentado (default "America/Sao_Paulo") por paridade com
# os .sh, MAS o Node no Windows ignora TZ com string IANA em process.env.TZ.
# Por isso os carimbos deste script usam a hora local da maquina e assumem o
# offset fixo -03:00 documentado (horario de Brasilia sem horario de verao).
# Mantenha o Windows com o fuso "E. South America Standard Time" (UTC-3) para os
# logs baterem com o monitor. O snapshot.mjs exibe os carimbos como recebidos,
# sem tentar reconverter fuso no Windows.
#
# Diferencas assumidas vs loop.sh (simplificacoes documentadas):
# - Watchdog simplificado: Start-Job + Wait-Job com timeout por modelo
#   (RUN_TIMEOUT). O .sh inspeciona o log interno do opencode para matar rodada
#   travada em quota antes do timeout; aqui nao ha OC_LOG_DIR no Windows, entao
#   rodada presa em retry silencioso morre no timeout cheio.
# - Lock via arquivo .lock com tentativa exclusiva ([IO.File]::Open,
#   FileShare::None) em vez de flock(1). Segunda instancia sai calada (exit 0),
#   como no .sh.
# - Disputa pelo Chrome: espera exclusiva de ate 900s pelo lock do Chrome;
#   timeout retorna o codigo 75 (mesmo do `flock -E 75` no .sh).

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $BOT_ROOT 'bot')

$BOT_TZ = $env:BOT_TZ
if ([string]::IsNullOrWhiteSpace($BOT_TZ)) { $BOT_TZ = 'America/Sao_Paulo' }

# Binarios resolvidos explicitamente (o Task Scheduler tem PATH minimo).
$NodeCmd = Get-Command node -ErrorAction SilentlyContinue
$OpencodeCmd = Get-Command opencode -ErrorAction SilentlyContinue
$NodeBin = $null
if ($NodeCmd) { $NodeBin = $NodeCmd.Source }
$OpencodeBin = $null
if ($OpencodeCmd) { $OpencodeBin = $OpencodeCmd.Source }
if ([string]::IsNullOrWhiteSpace($OpencodeBin)) {
    $cand = Join-Path $env:USERPROFILE '.opencode\bin\opencode.exe'
    if (Test-Path $cand) { $OpencodeBin = $cand }
}
if ([string]::IsNullOrWhiteSpace($OpencodeBin)) {
    $cand = Join-Path $env:USERPROFILE '.opencode\bin\opencode.cmd'
    if (Test-Path $cand) { $OpencodeBin = $cand }
}

function Write-Stamp { return (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

if ([string]::IsNullOrWhiteSpace($OpencodeBin)) {
    Add-Content -Path 'loop.log' -Value ("[{0}] ERRO: opencode nao encontrado no PATH nem em ~/.opencode/bin" -f (Write-Stamp))
    exit 1
}
if ([string]::IsNullOrWhiteSpace($NodeBin)) {
    Add-Content -Path 'loop.log' -Value ("[{0}] ERRO: node nao encontrado no PATH" -f (Write-Stamp))
    exit 1
}

# Chaves fora do repo: $env:USERPROFILE\.config\opencode\cron.env (600 so nesta
# maquina, nunca commitado). Formato KEY=VALUE por linha, mesmo do Linux.
$CronEnv = Join-Path $env:USERPROFILE '.config\opencode\cron.env'
if (Test-Path $CronEnv) {
    foreach ($line in (Get-Content $CronEnv)) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $i = $t.IndexOf('=')
        if ($i -gt 0) {
            $k = $t.Substring(0, $i).Trim()
            $v = $t.Substring($i + 1).Trim().Trim('"').Trim("'")
            if ($k -ne '') { Set-Item -Path ("env:{0}" -f $k) -Value $v }
        }
    }
}

# Ritmo (pacing) — configuravel por env (defaults preservam o comportamento).
# Ver docs/USO-ETICO.md e config/pacing.example.env.
function EnvInt($name, $def) { if ($env:$name) { return [int]$env:$name } else { return $def } }
$RUN_TIMEOUT_SEC = EnvInt 'OV_RUN_TIMEOUT_SEC' 1200   # 20m, igual ao RUN_TIMEOUT do loop.sh
$RETRY_BASE = EnvInt 'OV_RETRY_BASE' 300              # backoff exponencial: 5min, 10min, 20min, teto 30min
$RETRY_MAX = EnvInt 'OV_RETRY_MAX' 1800
$QUOTA_STEPS = @(900, 1800, 3600)  # quota: 15min -> 30min -> 1h, reseta ao dar certo
$NORMAL_WAIT = EnvInt 'OV_NORMAL_WAIT' 1200           # sleep base apos rodada ok (20min)
$VAZIA_BASE = EnvInt 'OV_VAZIA_BASE' 3600             # backoff por rodada sem vaga nova: 1h na primeira
$MONITOR_URL = $env:MONITOR_URL
if ([string]::IsNullOrWhiteSpace($MONITOR_URL)) { $MONITOR_URL = 'https://sua-url.vercel.app' }
$LOG_MAX_BYTES = 2097152 # 2MB -> rotaciona
$ROUNDS_KEPT = 20
$TEMP_DIR = $env:TEMP
if ([string]::IsNullOrWhiteSpace($TEMP_DIR)) { $TEMP_DIR = [System.IO.Path]::GetTempPath() }
$BROWSER_LOCK = Join-Path $TEMP_DIR 'agent-chrome-9222.lock'
$LOOP_LOCK = Join-Path $TEMP_DIR 'oportunizavaga-loop.lock'

# Escada de modelos GRATUITOS, mesma ordem do loop.sh. Nao invente IDs: qualquer
# modelo novo entra primeiro no loop.sh e depois e espelhado aqui.
function Get-ModelList {
    $list = New-Object System.Collections.ArrayList
    [void]$list.Add('openrouter/nex-agi/nex-n2.5-pro:free')
    [void]$list.Add('opencode/muse-spark-1.3-contributor-free')
    [void]$list.Add('opencode/nemotron-3-ultra-free')
    [void]$list.Add('opencode/nemotron-3.5-lightning-free')
    [void]$list.Add('opencode/mimo-v2.5-free')
    [void]$list.Add('opencode/muse-spark-1.2-contributor-free')
    [void]$list.Add('opencode/ling-3.0-flash-fin-free')
    $usarOpenrouter = $env:USAR_OPENROUTER
    if ([string]::IsNullOrWhiteSpace($usarOpenrouter)) { $usarOpenrouter = '1' }
    if ($usarOpenrouter -eq '1') {
        [void]$list.Add('openrouter/nvidia/nemotron-3-ultra-550b-a55b:free')
        [void]$list.Add('openrouter/nvidia/nemotron-3-super-120b-a12b:free')
        [void]$list.Add('openrouter/z-ai/glm-5.2:free')
        [void]$list.Add('openrouter/poolside/laguna-s-2.1:free')
        [void]$list.Add('openrouter/thinkingmachines/inkling:free')
        [void]$list.Add('openrouter/cohere/north-mini-code:free')
        [void]$list.Add('openrouter/nex-agi/nex-n2.5-pro:free')
        [void]$list.Add('openrouter/dots-studio/dots-3-note-preview:free')
        [void]$list.Add('openrouter/nvidia/nemotron-3.5-lightning:free')
    }
    $usarNvidia = $env:USAR_NVIDIA
    if ([string]::IsNullOrWhiteSpace($usarNvidia)) { $usarNvidia = '1' }
    if ($usarNvidia -eq '1') { [void]$list.Add('nvidia/nvidia/nemotron-3-super-120b-a12b') }
    $usarGroq = $env:USAR_GROQ
    if ([string]::IsNullOrWhiteSpace($usarGroq)) { $usarGroq = '1' }
    if ($usarGroq -eq '1') {
        [void]$list.Add('groq/openai/gpt-oss-120b')
        [void]$list.Add('groq/qwen/qwen3.8-27b')
        [void]$list.Add('groq/openai/gpt-oss-20b')
        [void]$list.Add('groq/meta-llama/llama-3.3-70b-versatile')
    }
    $usarCerebras = $env:USAR_CEREBRAS
    if ([string]::IsNullOrWhiteSpace($usarCerebras)) { $usarCerebras = '1' }
    if ($usarCerebras -eq '1') {
        [void]$list.Add('cerebras/gpt-oss-120b')
        [void]$list.Add('cerebras/qwen-3.8-27b')
    }
    $usarHf = $env:USAR_HF
    if ([string]::IsNullOrWhiteSpace($usarHf)) { $usarHf = '1' }
    if ($usarHf -eq '1') {
        [void]$list.Add('huggingface/deepseek-ai/DeepSeek-V4-Pro')
        [void]$list.Add('huggingface/deepseek-ai/DeepSeek-V3.2')
        [void]$list.Add('huggingface/google/gemma-3-27b-it')
    }
    $usarCopilot = $env:USAR_COPILOT
    if ([string]::IsNullOrWhiteSpace($usarCopilot)) { $usarCopilot = '0' }
    if ($usarCopilot -eq '1') { [void]$list.Add('github-copilot/claude-sonnet-4.6') }
    return $list
}

if (-not (Test-Path 'logs')) { New-Item -ItemType Directory -Path 'logs' | Out-Null }

# Perfil ativo e estado isolado (espelho do loop.sh).
$PerfilFile = $env:BOT_PERFIL
if ([string]::IsNullOrWhiteSpace($PerfilFile)) {
    $candidate = Join-Path $BOT_ROOT 'bot\perfil.json'
    if (Test-Path $candidate) { $PerfilFile = $candidate }
}
if ([string]::IsNullOrWhiteSpace($PerfilFile)) {
    $PerfilFile = Join-Path $BOT_ROOT 'config\perfis\junior-backend.example.json'
}
if (-not (Test-Path $PerfilFile)) {
    Add-Content -Path 'loop.log' -Value ("[{0}] ERRO: perfil nao encontrado: {1}" -f (Write-Stamp), $PerfilFile)
    exit 1
}
try { $PerfilDoc = Get-Content $PerfilFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
catch {
    Add-Content -Path 'loop.log' -Value ("[{0}] ERRO: perfil invalido: {1}" -f (Write-Stamp), $_.Exception.Message)
    exit 1
}
$PerfilNome = [string]$PerfilDoc.nome_perfil
$PerfilSlug = ($PerfilNome.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
if ($PerfilSlug.Length -gt 48) { $PerfilSlug = $PerfilSlug.Substring(0, 48) }
$PerfilExplicito = $false
if ((-not [string]::IsNullOrWhiteSpace($env:BOT_PERFIL)) -or (Test-Path (Join-Path $BOT_ROOT 'bot\perfil.json'))) { $PerfilExplicito = $true }
if ($PerfilFile -ne (Join-Path $BOT_ROOT 'config\perfis\junior-backend.example.json')) { $PerfilExplicito = $true }
if ($PerfilExplicito) {
    $StateDir = Join-Path $BOT_ROOT "bot\state\$PerfilSlug"
} else {
    $PerfilSlug = 'default'
    $StateDir = Join-Path $BOT_ROOT 'bot'
}
$AplicadasFile = Join-Path $StateDir 'aplicadas.json'
$DadosCandidatoFile = Join-Path $BOT_ROOT 'bot\dados_candidato.json'
$RuntimePromptFile = Join-Path $StateDir 'prompt_loop.runtime.md'
$ReconhecimentoFile = Join-Path $StateDir ("reconhecimento-{0}.json" -f (Get-Date).ToString('yyyyMMdd-HHmmss'))
if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir | Out-Null }
if (-not (Test-Path $AplicadasFile)) {
    Copy-Item (Join-Path $BOT_ROOT 'examples\aplicadas.example.json') $AplicadasFile -Force
}
$env:BOT_PERFIL = $PerfilFile
$env:OV_RECONHECIMENTO = if ([string]::IsNullOrWhiteSpace($env:OV_RECONHECIMENTO)) { '0' } else { $env:OV_RECONHECIMENTO }
$env:OV_MAX_CANDIDATURAS = if ([string]::IsNullOrWhiteSpace($env:OV_MAX_CANDIDATURAS)) { '3' } else { $env:OV_MAX_CANDIDATURAS }
$env:OV_RECONHECIMENTO_LIMIT = if ([string]::IsNullOrWhiteSpace($env:OV_RECONHECIMENTO_LIMIT)) { '10' } else { $env:OV_RECONHECIMENTO_LIMIT }
$env:OV_TELEMETRY_MODE = if ([string]::IsNullOrWhiteSpace($env:OV_TELEMETRY_MODE)) { 'aggregate' } else { $env:OV_TELEMETRY_MODE }
$env:OV_MONITOR_INCLUDE_DETAILS = if ([string]::IsNullOrWhiteSpace($env:OV_MONITOR_INCLUDE_DETAILS)) { '0' } else { $env:OV_MONITOR_INCLUDE_DETAILS }

# Instancia unica: lock exclusivo no arquivo. Se ja houver dono, sai calado
# (o guardiao chama este script a cada 5min so para garantir que esta de pe).
try {
    $LoopLockStream = [System.IO.File]::Open($LOOP_LOCK, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch {
    exit 0
}

function Rotate-Log {
    try {
        $size = 0
        if (Test-Path 'loop.log') { $size = (Get-Item 'loop.log').Length }
        if ($size -gt $LOG_MAX_BYTES) {
            Move-Item -Force 'loop.log' 'loop.log.1'
            Add-Content -Path 'loop.log' -Value ("[{0}] loop.log rotacionado (anterior em loop.log.1)" -f (Write-Stamp))
        }
    } catch { }
    try {
        $files = Get-ChildItem 'logs/rodada-*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
        if ($files -and $files.Count -gt $ROUNDS_KEPT) {
            $files | Select-Object -Skip $ROUNDS_KEPT | Remove-Item -Force -ErrorAction SilentlyContinue
        }
    } catch { }
}

function Write-LoopLog([string]$msg) {
    Add-Content -Path 'loop.log' -Value ("[{0}] {1}" -f (Write-Stamp), $msg)
    # Publica no monitor em background (nao bloqueia a rodada).
    try {
        $pub = Join-Path $BOT_ROOT 'monitor\publish-once.mjs'
        $job = Start-Job -ScriptBlock {
            param($node, $pub, $url, $root)
            $env:MONITOR_URL = $url
            $env:CANDIDATURAS_ROOT = (Join-Path $root 'bot')
            & $node $pub 2>&1 | Out-Null
        } -ArgumentList $NodeBin, $pub, $MONITOR_URL, $BOT_ROOT
        # Nao espera: limpa jobs velhos para nao acumular.
        Get-Job -State Completed -ErrorAction SilentlyContinue | Remove-Job -ErrorAction SilentlyContinue
    } catch { }
}

function Test-Cdp {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $r = $c.BeginConnect('127.0.0.1', 9222, $null, $null)
        $ok = $r.AsyncWaitHandle.WaitOne(5000)
        $c.Close()
        return $ok
    } catch { return $false }
}

function Ensure-Chrome {
    if (Test-Cdp) { return $true }
    Write-LoopLog 'Chrome CDP fora do ar, subindo novamente'
    try {
        $chrome = Join-Path $BOT_ROOT 'browser\chrome-real.ps1'
        Start-Process -FilePath 'powershell' -ArgumentList @('-ExecutionPolicy', 'Bypass', '-File', $chrome) -WindowStyle Hidden
    } catch { }
    Start-Sleep -Seconds 6
    return (Test-Cdp)
}

function Ensure-Monitor {
    try {
        $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*publish-status.mjs*' }
        if ($procs) { return }
        $pub = Join-Path $BOT_ROOT 'monitor\publish-status.mjs'
        $startArgs = "`$env:MONITOR_URL='{0}'; `$env:CANDIDATURAS_ROOT='{1}'; & '{2}' '{3}'" -f $MONITOR_URL, (Join-Path $BOT_ROOT 'bot'), $NodeBin, $pub
        Start-Process -FilePath 'powershell' -ArgumentList @('-ExecutionPolicy', 'Bypass', '-Command', $startArgs) -WindowStyle Hidden
    } catch { }
}

function Test-IsQuota([string]$file) {
    if (-not (Test-Path $file)) { return $false }
    $hit = Select-String -Path $file -Pattern '^\s*QUOTA_EXAUSTA|Error from provider.*([Rr]ate limit|[Qq]uota|429|[Ee]xhausted|[Tt]oo [Mm]any)|AI_RetryError|RateLimitError' -ErrorAction SilentlyContinue
    return ($null -ne $hit)
}

function Test-BrokenSession([string]$file) {
    if (-not (Test-Path $file)) { return $false }
    $hit = Select-String -Path $file -Pattern 'Session not found|session (expired|invalid)|invalid session' -CaseSensitive:$false -ErrorAction SilentlyContinue
    return ($null -ne $hit)
}

# Impressao digital do estado: aplicadas + bloqueados + descartes da listagem.
function Get-Fingerprint {
    try {
        $d = Get-Content $AplicadasFile -Raw -ErrorAction Stop | ConvertFrom-Json
        $a = 0; $b = 0; $desc = 0
        if ($d.aplicadas) { $a = @($d.aplicadas).Count }
        if ($d.bloqueados) {
            if ($d.bloqueados -is [System.Collections.IDictionary]) { $b = $d.bloqueados.Count }
            else { $b = @($d.bloqueados | Get-Member -MemberType NoteProperty).Count }
        }
        if ($d.descartes_listagem_total) { $desc = [int]$d.descartes_listagem_total }
        return ($a + $b + $desc)
    } catch { return -1 }
}

# Backoff por rodada vazia: 1h na primeira e dobra SEM TETO (3600 -> 7200 -> ...).
function Get-EmptyWait([int]$n) {
    $w = $VAZIA_BASE
    for ($i = 1; $i -lt $n; $i++) { $w = $w * 2 }
    return $w
}

function Get-FailWait([int]$n) {
    $w = $RETRY_BASE
    for ($i = 1; $i -lt $n; $i++) { $w = $w * 2 }
    if ($w -gt $RETRY_MAX) { $w = $RETRY_MAX }
    return $w
}

function Render-Prompt {
    $source = Join-Path $BOT_ROOT 'bot\prompt_loop.md'
    $text = Get-Content $source -Raw
    $text = $text.Replace('$APLICADAS_FILE', $AplicadasFile)
    $text = $text.Replace('$DADOS_CANDIDATO_FILE', $DadosCandidatoFile)
    $text = $text.Replace('bot/perfil.json', $PerfilFile)
    $text = $text.Replace('SEU_NOME', $PerfilNome)
    $text = $text.Replace('YOUR_NAME', $PerfilNome)
    $reconhecimento = @('1', 'true', 'True', 'sim', 'Sim') -contains $env:OV_RECONHECIMENTO
    if ($reconhecimento) {
        $text += "`n`nMODO RECONHECIMENTO (obrigatorio): NAO se candidate, NAO preencha formulario, NAO envie mensagem, NAO altere aplicadas.json. Avalie no maximo $env:OV_RECONHECIMENTO_LIMIT vagas recentes do site da rodada e grave somente $ReconhecimentoFile com schema compativel com config\reconhecimento.schema.json. Use chave estavel site+vaga, score 0-5, URL, empresa, vaga, remota, nivel, stack, motivos e observacoes; nunca inclua dados pessoais.`n"
    } else {
        $text += "`n`nPERFIL ATIVO: $PerfilNome. Use somente os termos, filtros e estado deste perfil. O limite desta rodada e $env:OV_MAX_CANDIDATURAS candidaturas novas.`n"
    }
    Set-Content -Path $RuntimePromptFile -Value $text -Encoding UTF8
    return $text
}

# Roda o opencode com timeout (watchdog simplificado via Start-Job + Wait-Job).
# Retorna hashtable @{ Status = <int>; TimedOut = <bool> }.
function Invoke-ModelRound([string]$modelo, [string]$prompt, [string]$roundLog) {
    $title = 'candidaturas-{0}' -f (Get-Date).ToString('yyyy-MM-dd-HHmm')
    # Disputa exclusiva pelo Chrome (ate 900s), espelhando `flock -w 900 -E 75`.
    $chromeLock = $null
    $deadline = (Get-Date).AddSeconds(900)
    while ((Get-Date) -lt $deadline) {
        try {
            $chromeLock = [System.IO.File]::Open($BROWSER_LOCK, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            break
        } catch { Start-Sleep -Seconds 5 }
    }
    if ($null -eq $chromeLock) { return @{ Status = 75; TimedOut = $false } }
    try {
        $job = Start-Job -ScriptBlock {
            param($bin, $mod, $ttl, $pr)
            & $bin run -m $mod --title $ttl $pr 2>&1
        } -ArgumentList $OpencodeBin, $modelo, $title, $prompt
        $done = Wait-Job -Job $job -Timeout $RUN_TIMEOUT_SEC
        if ($done) {
            $out = Receive-Job -Job $job
            $out | Out-File -FilePath $roundLog -Encoding utf8
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
            if ($job.State -eq 'Failed') { return @{ Status = 1; TimedOut = $false } }
            return @{ Status = 0; TimedOut = $false }
        } else {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
            Add-Content -Path $roundLog -Value ("rodada excedeu o timeout de {0}s e foi abortada" -f $RUN_TIMEOUT_SEC)
            return @{ Status = 124; TimedOut = $true }
        }
    } finally {
        try { $chromeLock.Close(); $chromeLock.Dispose() } catch { }
    }
}

if (-not (Ensure-Chrome)) { Start-Sleep -Seconds $RETRY_BASE }
Ensure-Monitor

$FAILS = 0
$QUOTA_HITS = 0
$VAZIAS = 0
$MODELOS = Get-ModelList

while ($true) {
    Rotate-Log
    if (-not (Ensure-Chrome)) {
        $FAILS++
        $W = Get-FailWait $FAILS
        Write-LoopLog ("Chrome CDP indisponivel (falha {0}), nova tentativa em {1}s" -f $FAILS, $W)
        Start-Sleep -Seconds $W
        continue
    }
    Ensure-Monitor

    $ROUND_LOG = 'logs/rodada-{0}.log' -f (Get-Date).ToString('yyyyMMdd-HHmmss')
    $FP_ANTES = Get-Fingerprint
    Write-LoopLog ("rodada iniciada (perfil {0}, rodadas vazias seguidas: {1})" -f $PerfilNome, $VAZIAS)
    $prompt = Render-Prompt

    $STATUS = 0
    $MODELO_OK = ''
    $TODOS_NO_LIMITE = $true

    foreach ($MODELO in $MODELOS) {
        $res = Invoke-ModelRound $MODELO $prompt $ROUND_LOG
        $STATUS = $res.Status
        if (Test-IsQuota $ROUND_LOG) {
            Write-LoopLog ("modelo {0} no limite, cascateando para o proximo" -f $MODELO)
            continue
        }
        $MODELO_OK = $MODELO
        $TODOS_NO_LIMITE = $false
        break
    }

    if ($MODELO_OK -ne '') { Write-LoopLog ("rodada usou o modelo {0}" -f $MODELO_OK) }

    try {
        $tail = Get-Content $ROUND_LOG -Tail 40 -ErrorAction SilentlyContinue
        Add-Content -Path 'loop.log' -Value ("--- saida da rodada (completa em {0}) ---" -f $ROUND_LOG)
        $tail | Add-Content -Path 'loop.log'
    } catch { }

    if (Test-BrokenSession $ROUND_LOG) {
        $FAILS++
        $W = Get-FailWait $FAILS
        Write-LoopLog ("sessao opencode invalida, nova tentativa em {0}s" -f $W)
        Start-Sleep -Seconds $W
    } elseif ($TODOS_NO_LIMITE) {
        $IDX = $QUOTA_HITS
        if ($IDX -ge $QUOTA_STEPS.Count) { $IDX = $QUOTA_STEPS.Count - 1 }
        $W = $QUOTA_STEPS[$IDX]
        $QUOTA_HITS++
        Write-LoopLog ("quota/limite: TODOS os {0} modelos gratuitos no teto ({1}x seguidas), rechecando em {2}s" -f $MODELOS.Count, $QUOTA_HITS, $W)
        Start-Sleep -Seconds $W
    } elseif ($STATUS -eq 124 -or $STATUS -eq 137 -or $STATUS -eq 143) {
        $FAILS++
        $W = Get-FailWait $FAILS
        Write-LoopLog ("rodada estourou o timeout, nova tentativa em {0}s" -f $W)
        Start-Sleep -Seconds $W
    } elseif ($STATUS -eq 75) {
        Write-LoopLog ("outro agente segurou o Chrome por 15min (lock), tentando de novo em {0}s" -f $RETRY_BASE)
        Start-Sleep -Seconds $RETRY_BASE
    } elseif ($STATUS -ne 0) {
        $FAILS++
        $W = Get-FailWait $FAILS
        Write-LoopLog ("opencode terminou com erro (status {0}), nova tentativa em {1}s" -f $STATUS, $W)
        Start-Sleep -Seconds $W
    } else {
        $FAILS = 0
        $QUOTA_HITS = 0
        $FP_DEPOIS = Get-Fingerprint
        if (($FP_ANTES -ne -1) -and ($FP_DEPOIS -ne -1) -and ($FP_ANTES -eq $FP_DEPOIS)) {
            $VAZIAS++
            $W = Get-EmptyWait $VAZIAS
            Write-LoopLog ("rodada ok, NENHUMA vaga nova ({0}x seguidas), dormindo {1}min" -f $VAZIAS, ([int]($W / 60)))
            Start-Sleep -Seconds $W
        } else {
            $VAZIAS = 0
            Write-LoopLog 'rodada ok, vaga nova processada, dormindo 20min'
            Start-Sleep -Seconds $NORMAL_WAIT
        }
    }

    if ($FAILS -ge 8) {
        Write-LoopLog ("ALERTA: {0} falhas consecutivas — loop pode estar quebrado, verifique {1}" -f $FAILS, $ROUND_LOG)
    }
}
