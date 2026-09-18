# scripts/pull-monitor.ps1 — espelho Windows de scripts/pull-monitor.sh.
# "Correio" do monitor via git: fast-forward do codigo e, se mudou, derruba o
# publisher para o monitor-keepalive.ps1 o ressubir com a versao nova.
# Nunca commita, nunca envia segredo. Exit 0 = ok, 2 = atencao (ver log).

$ErrorActionPreference = 'SilentlyContinue'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
$REPO = Join-Path $BOT_ROOT 'monitor'
$LOG = Join-Path $BOT_ROOT 'monitor-pull.log'
if ([string]::IsNullOrWhiteSpace($env:BOT_TZ)) { $env:BOT_TZ = 'America/Sao_Paulo' }

function Write-Stamp { return (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz') }

Remove-Item 'env:GITHUB_TOKEN' -ErrorAction SilentlyContinue
Remove-Item 'env:GH_TOKEN' -ErrorAction SilentlyContinue

# O monitor mora no mesmo repo: prefere monitor/.git, cai para a raiz.
$GitDir = $REPO
if (-not (Test-Path (Join-Path $REPO '.git'))) {
    if (Test-Path (Join-Path $BOT_ROOT '.git')) { $GitDir = $BOT_ROOT }
    else {
        Add-Content -Path $LOG -Value ("{0} ERRO: {1} sem .git" -f (Write-Stamp), $REPO)
        exit 2
    }
}

try { $before = (& git -C $GitDir rev-parse HEAD 2>$null).Trim() } catch { $before = '' }
& git -C $GitDir pull --ff-only --quiet 2>> $LOG
if ($LASTEXITCODE -ne 0) {
    Add-Content -Path $LOG -Value ("{0} ERRO: git pull falhou (conflito local? rode git status)" -f (Write-Stamp))
    exit 2
}
try { $after = (& git -C $GitDir rev-parse HEAD 2>$null).Trim() } catch { $after = '' }

if (($before -ne '') -and ($after -ne '') -and ($before -ne $after)) {
    Add-Content -Path $LOG -Value ("{0} atualizado {1} -> {2}; derrubando publisher p/ recarregar" -f (Write-Stamp), $before, $after)
    try {
        $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*publish-status.mjs*' }
        foreach ($p in $procs) {
            try { Stop-Process -Id $p.ProcessId -Force } catch { }
        }
    } catch { }
}
exit 0
