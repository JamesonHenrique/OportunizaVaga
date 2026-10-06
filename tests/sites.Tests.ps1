# tests/sites.Tests.ps1 — Pester v5 do filtro de sites do bot/dry-run.ps1.
# O dry-run.ps1 monta a URL de busca sem bash: le SEARCH_ENCODING do adaptador em vez de
# chamar site_url_busca. Isso ja deu bug (path com hifen montando %20, que o portal ignora),
# entao o teste fixa a URL de CADA adaptador contra o que o .sh produz de verdade.
#
# Uso (Windows): Invoke-Pester -Path tests/sites.Tests.ps1 -Output Detailed
# Nao abre browser, nao chama o opencode, nao escreve nada.

BeforeAll {
    $script:RepoRoot = Split-Path -Parent $PSScriptRoot
    $script:AdapterDir = Join-Path $RepoRoot 'bot\sites'

    # id | URL esperada com o termo "analista financeiro" (mesma tabela do tests/test_sites.sh)
    $script:Casos = @(
        @{ Id = 'vagas';      Url = 'https://www.vagas.com.br/vagas-de-analista-financeiro?m%5B%5D=home-office' },
        @{ Id = 'indeed';     Url = 'https://br.indeed.com/jobs?q=analista%20financeiro&l=Remoto&sort=date' },
        @{ Id = 'gupy';       Url = 'https://portal.gupy.io/job-search/term=analista%20financeiro' },
        @{ Id = 'linkedin';   Url = 'https://www.linkedin.com/jobs/search/?keywords=analista%20financeiro&location=Brasil&f_WT=2&sortBy=DD' },
        @{ Id = 'programathor'; Url = 'https://programathor.com.br/jobs?search=analista%20financeiro' },
        @{ Id = 'geekhunter'; Url = 'https://www.geekhunter.com.br/vagas?busca=analista%20financeiro&remoto=1' },
        @{ Id = 'catho';      Url = 'https://www.catho.com.br/vagas/analista-financeiro/' },
        @{ Id = 'infojobs';   Url = 'https://www.infojobs.com.br/vagas-de-emprego-analista%20financeiro.aspx' },
        @{ Id = 'solides';    Url = 'https://vagas.solides.com.br/vagas/analista-financeiro' },
        @{ Id = 'trampos';    Url = 'https://trampos.co/oportunidades/?tr=analista%20financeiro' },
        # sites sem busca por termo: a URL e o template (bash: site_url_busca devolve o template)
        @{ Id = 'abler';      Url = 'https://candidatos.abler.com.br/vagas' },
        @{ Id = 'eu-dev-br';  SiteId = 'eu.dev.br'; Url = 'https://eu.dev.br/vagas/' },
        @{ Id = 'jooble';     Url = 'https://br.jooble.org/empregos' },
        @{ Id = 'netvagas';   Url = 'https://www.netvagas.com.br/empresa/anuncios/cargo/desenvolvedor/' },
        @{ Id = 'remotar';    Url = 'https://remotar.com.br/search/jobs' },
        @{ Id = 'trabalhabrasil'; Url = 'https://www.trabalhabrasil.com.br/vagas-de-emprego' }
    )

    function New-TestProfile {
        param([hashtable]$Extra)
        $p = [ordered]@{
            nome_perfil = 'Teste Sites'
            niveis      = @('pleno')
            area        = 'tecnologia'
            termos      = @('analista financeiro')
            pular_tipos = @('vaga comissionada')
        }
        if ($Extra) { foreach ($k in $Extra.Keys) { $p[$k] = $Extra[$k] } }
        $tmp = [System.IO.Path]::GetTempFileName()
        ($p | ConvertTo-Json -Depth 5) | Set-Content -Path $tmp -Encoding UTF8
        return $tmp
    }

    function Get-DryRunJson {
        param([string]$ProfilePath, [string]$Site)
        if ($Site) {
            $saida = & (Join-Path $RepoRoot 'bot\dry-run.ps1') -json -Profile $ProfilePath -Site $Site
        } else {
            $saida = & (Join-Path $RepoRoot 'bot\dry-run.ps1') -json -Profile $ProfilePath
        }
        return (($saida | Out-String) | ConvertFrom-Json)
    }
}

Describe 'dry-run.ps1: filtro de sites' {
    Context 'descoberta dos adaptadores' {
        It 'inclui todo .sh de bot/sites exceto _template e lib' {
            $prof = New-TestProfile
            try {
                $obj = Get-DryRunJson $prof
                $adaptadores = @(Get-ChildItem $AdapterDir -Filter '*.sh' |
                    Where-Object { $_.Name -notin @('_template.sh', 'lib.sh') })
                $obj.site_count | Should -Be $adaptadores.Count
                $ids = @($obj.sites | ForEach-Object { $_.site_id }) | Sort-Object
                foreach ($a in $adaptadores) { $ids | Should -Contain ([System.IO.Path]::GetFileNameWithoutExtension($a.Name)) }
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }

        It 'nao devolve _template nem lib no plano' {
            $prof = New-TestProfile
            try {
                $obj = Get-DryRunJson $prof
                @($obj.sites | ForEach-Object { $_.site_id }) | Should -Not -Contain '_template'
                @($obj.sites | ForEach-Object { $_.site_id }) | Should -Not -Contain 'lib'
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }

        It '-Site restringe o plano a um adaptador' {
            $prof = New-TestProfile
            try {
                $obj = Get-DryRunJson $prof 'catho'
                $obj.site_count | Should -Be 1
                $obj.sites[0].site_id | Should -Be 'catho'
                $obj.global | Should -Be $false
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }

        It '-Site com id inexistente devolve plano vazio, nao erro' {
            $prof = New-TestProfile
            try {
                $obj = Get-DryRunJson $prof 'nao-existe'
                $obj.ok | Should -Be $true
                $obj.site_count | Should -Be 0
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }
    }

    Context 'URL de busca por adaptador (paridade com o .sh)' {
        # O .sh e o canonico: site_url_busca roda de verdade no bash. Aqui conferimos que o
        # espelho PowerShell, que le SEARCH_ENCODING, chega na MESMA URL.
        It 'a URL do dry-run.ps1 bate com a do site_url_busca (bash) em todos os adaptadores' {
            $bash = Get-Command bash -ErrorAction SilentlyContinue
            if (-not $bash) { Set-ItResult -Skipped -Because 'bash nao disponivel no PATH'; return }

            $prof = New-TestProfile
            try {
                $obj = Get-DryRunJson $prof
                $porId = @{}
                foreach ($s in $obj.sites) { $porId[$s.site_id] = $s.url_busca }

                foreach ($caso in $Casos) {
                    $esperado = (& $bash.Source -c "cd '$RepoRoot'; source bot/sites/lib.sh; site_adapter_source '$($caso.Id)' '$RepoRoot'; site_url_busca 'analista financeiro'").Trim()
                    # arquivo (Id) e SITE_ID podem diferir: eu-dev-br.sh declara SITE_ID="eu.dev.br"
                    $sid = if ($caso.SiteId) { $caso.SiteId } else { $caso.Id }
                    $porId.ContainsKey($sid) | Should -Be $true -Because "$sid tem que entrar no plano"
                    $porId[$sid] | Should -Be $esperado -Because "URL do $sid divergiu entre dry-run.ps1 e site_url_busca"
                }
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }

        It 'cada adaptador com slug de path declara SEARCH_ENCODING=hifen' {
            # Sem a declaracao o dry-run.ps1 monta %20 num path que quer hifen: URL que o portal
            # ignora, sem erro visivel. Os slugs de path tem que declarar.
            foreach ($id in @('vagas', 'catho', 'solides')) {
                $texto = Get-Content (Join-Path $AdapterDir "$id.sh") -Raw
                $texto | Should -Match 'SEARCH_ENCODING="hifen"' -Because "$id usa slug de path com hifen"
            }
        }

        It 'a tabela de casos do teste continua em dia com a arvore de adaptadores' {
            $adaptadores = @(Get-ChildItem $AdapterDir -Filter '*.sh' |
                Where-Object { $_.Name -notin @('_template.sh', 'lib.sh') } |
                ForEach-Object { [System.IO.Path]::GetFileNameWithoutExtension($_.Name) } | Sort-Object)
            $casos = @($Casos | ForEach-Object { $_.Id } | Sort-Object)
            ($adaptadores -join ',') | Should -Be ($casos -join ',')
        }
    }

    Context 'pulado_pelo_perfil (restrito_a_area e restrito_a_modelo)' {
        It 'perfil tech nao pula adaptadores so-tech' {
            $prof = New-TestProfile @{ area = 'tecnologia (desenvolvimento backend)' }
            try {
                $obj = Get-DryRunJson $prof
                foreach ($id in @('programathor', 'geekhunter')) {
                    ($obj.sites | Where-Object { $_.site_id -eq $id }).pulado_pelo_perfil | Should -Be $false
                }
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }

        It 'perfil fora de tech pula os adaptadores so-tech' {
            $prof = New-TestProfile @{ area = 'jurídico (direito)' }
            try {
                $obj = Get-DryRunJson $prof
                foreach ($id in @('programathor', 'geekhunter')) {
                    ($obj.sites | Where-Object { $_.site_id -eq $id }).pulado_pelo_perfil | Should -Be $true
                }
                # os generalistas continuam no plano (so marcados como pulados, nao removidos)
                ($obj.sites | Where-Object { $_.site_id -eq 'catho' }).pulado_pelo_perfil | Should -Be $false
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }

        It 'sites_pular do perfil tem precedencia sobre o filtro automatico' {
            $prof = New-TestProfile @{ area = 'tecnologia (backend)'; sites_pular = @('indeed') }
            try {
                $obj = Get-DryRunJson $prof
                ($obj.sites | Where-Object { $_.site_id -eq 'indeed' }).pulado_pelo_perfil | Should -Be $true
                # area tech mantem os so-tech, porque sites_pular explicito desliga o filtro automatico
                ($obj.sites | Where-Object { $_.site_id -eq 'programathor' }).pulado_pelo_perfil | Should -Be $false
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }

        It 'sites_pular do perfil aparece no resumo do plano' {
            $prof = New-TestProfile @{ sites_pular = @('indeed', 'vagas') }
            try {
                $obj = Get-DryRunJson $prof
                @($obj.perfil.sites_pular) | Should -Contain 'indeed'
                @($obj.perfil.sites_pular) | Should -Contain 'vagas'
            }
            finally { Remove-Item $prof -Force -ErrorAction SilentlyContinue }
        }
    }
}