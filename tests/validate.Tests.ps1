# tests/validate.Tests.ps1 — espelho Pester (PowerShell 5.1+) de tests/test_validate.sh.
# Cobre: scripts/validate.ps1 (exit 0 nos validos, exit !=0 nos invalidos)
# e bot/dry-run.ps1 -json (saida parseavel com ok == true).
# Uso (Windows): Invoke-Pester -Path tests/validate.Tests.ps1 -Output Detailed
# Nao executa nada destrutivo: fixtures invalidas sao copiadas por cima dos
# exemplos e restauradas em finally. Nao commite bot/*.json (dados locais).

$RepoRoot = Split-Path -Parent $PSScriptRoot
$FixDir = Join-Path $PSScriptRoot 'fixtures'

Describe 'validate.ps1' {
    Context 'exemplos validos' {
        It 'exit 0 com os exemplos do repo' {
            & (Join-Path $RepoRoot 'scripts\validate.ps1')
            $LASTEXITCODE | Should -Be 0
        }
    }

    Context 'fixtures invalidas (swap temporario com restore)' {
        It 'exit diferente de 0 com dados_candidato sem email' {
            $alvo = Join-Path $RepoRoot 'examples\dados_candidato.example.json'
            $fix = Join-Path $FixDir 'dados_candidato.sem-email.json'
            $bak = [System.IO.Path]::GetTempFileName()
            try {
                Copy-Item $alvo $bak -Force
                Copy-Item $fix $alvo -Force
                & (Join-Path $RepoRoot 'scripts\validate.ps1')
                $LASTEXITCODE | Should -Not -Be 0
            }
            finally {
                Copy-Item $bak $alvo -Force
                Remove-Item $bak -Force -ErrorAction SilentlyContinue
            }
        }

        It 'exit diferente de 0 com aplicadas sem rodizio.proximo' {
            $alvo = Join-Path $RepoRoot 'examples\aplicadas.example.json'
            $fix = Join-Path $FixDir 'aplicadas.sem-rodizio-proximo.json'
            $bak = [System.IO.Path]::GetTempFileName()
            try {
                Copy-Item $alvo $bak -Force
                Copy-Item $fix $alvo -Force
                & (Join-Path $RepoRoot 'scripts\validate.ps1')
                $LASTEXITCODE | Should -Not -Be 0
            }
            finally {
                Copy-Item $bak $alvo -Force
                Remove-Item $bak -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

Describe 'dry-run.ps1' {
    It '--json sai parseavel com ok true' {
        $saida = & (Join-Path $RepoRoot 'bot\dry-run.ps1') -json
        $LASTEXITCODE | Should -Be 0
        $obj = ($saida | Out-String) | ConvertFrom-Json
        $obj.ok | Should -Be $true
        $obj.dry_run | Should -Be $true
    }
}
