# tests/validate.Tests.ps1 — espelho Pester (v5) de tests/test_validate.sh.
# Cobre: scripts/validate.ps1 (exit 0 nos validos, exit !=0 nos invalidos)
# e bot/dry-run.ps1 -json (saida parseavel com ok == true).
# Uso (Windows): Invoke-Pester -Path tests/validate.Tests.ps1 -Output Detailed
# Nao executa nada destrutivo: fixtures invalidas sao copiadas por cima dos
# exemplos e restauradas em finally. Nao commite bot/*.json (dados locais).
#
# Pester v5 separa Discovery de Run: variaveis de caminho tem que ser definidas
# em BeforeAll (fase Run), senao chegam $null dentro dos It.

BeforeAll {
    $script:RepoRoot = Split-Path -Parent $PSScriptRoot
    $script:FixDir = Join-Path $PSScriptRoot 'fixtures'
}

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
    It '--json sai parseavel com ok true e plano global' {
        $saida = & (Join-Path $RepoRoot 'bot\dry-run.ps1') -json
        $LASTEXITCODE | Should -Be 0
        $obj = ($saida | Out-String) | ConvertFrom-Json
        $obj.ok | Should -Be $true
        $obj.dry_run | Should -Be $true
        $obj.global | Should -Be $true
        $obj.site_count | Should -Be 6
        $obj.perfil.slug | Should -Be 'default'
        $obj.estado.isolado | Should -Be $false
    }

    It '-Profile cria slug e estado isolado a partir do nome do perfil' {
        $tmp = [System.IO.Path]::GetTempFileName()
        @'
{
  "nome_perfil": "Frontend Teste",
  "nivel": "junior",
  "termos": ["frontend junior remoto"],
  "pular_tipos": ["design/UX"]
}
'@ | Set-Content -Path $tmp -Encoding UTF8
        try {
            $saida = & (Join-Path $RepoRoot 'bot\dry-run.ps1') -json -Profile $tmp
            $LASTEXITCODE | Should -Be 0
            $obj = ($saida | Out-String) | ConvertFrom-Json
            $obj.perfil.slug | Should -Be 'frontend-teste'
            $obj.estado.isolado | Should -Be $true
            $obj.estado.diretorio | Should -BeLike '*state\frontend-teste'
        }
        finally {
            Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        }
    }

    It '-Site indeed restrige o plano a um adaptador' {
        $saida = & (Join-Path $RepoRoot 'bot\dry-run.ps1') -json -Site indeed
        $LASTEXITCODE | Should -Be 0
        $obj = ($saida | Out-String) | ConvertFrom-Json
        $obj.global | Should -Be $false
        $obj.site_count | Should -Be 1
        $obj.sites[0].site_id | Should -Be 'indeed'
    }
}
