# tests/loop.Tests.ps1 — Pester (v5) das funcoes puras do espelho Windows.
# Cobre o que o CI nao pegava de outro jeito:
#   - Expand-PerfilPlaceholders (bot/loop.ps1): perfil -> placeholders {{...}};
#   - o plano do bot/dry-run.ps1 (quais adaptadores entram e a URL montada).
# O filtro de sites em detalhe (incluindo a paridade da URL com o .sh) esta em
# tests/sites.Tests.ps1; aqui so o basico, para o arquivo nao depender de bash.
# Uso (Windows): Invoke-Pester -Path tests/loop.Tests.ps1 -Output Detailed
#
# NAO executa o loop: bot/loop.ps1 e um script que roda para sempre (subiria Chrome e
# opencode). Para testar uma funcao dele, o arquivo e lido no AST e so a definicao
# desejada e extraida. Testar o resto exigiria partir o loop em modulo, que e maior que
# o ganho de um teste.
#
# Pester v5 separa Discovery de Run: caminho e funcoes auxiliares tem que estar em
# BeforeAll (fase Run). A funcao importada vai para o escopo script: de proposito — o
# escopo local do BeforeAll morre no fim do bloco e o It nao a enxergaria.

BeforeAll {
    $script:RepoRoot = Split-Path -Parent $PSScriptRoot
    $script:LoopPs1 = Join-Path $script:RepoRoot 'bot/loop.ps1'
    $script:DryRunPs1 = Join-Path $script:RepoRoot 'bot/dry-run.ps1'

    # Texto de UMA funcao de um .ps1, sem executar o resto do arquivo.
    function Get-PsFunctionText {
        param([string]$Path, [string]$Name)
        $ast = [System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$null, [ref]$null)
        $fn = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $Name }, $true)
        if (-not $fn) { throw "funcao nao encontrada em ${Path}: $Name" }
        return $fn.Extent.Text
    }

    # Perfil temporario. $script:Py = $null forca o fallback nativo de
    # Expand-PerfilPlaceholders (sem python): e o caminho que este teste precisa travar,
    # porque o fast path delega ao perfil_render.py e ja e coberto do lado bash
    # (tests/test_perfil_render.sh).
    function New-TestProfile {
        param([hashtable]$Campos)
        $p = [ordered]@{
            nome_perfil = 'perfil-teste'
            niveis      = @('junior')
            area        = 'tecnologia'
            termos      = @('termo um')
            pular_tipos = @('algo a pular')
        }
        foreach ($k in $Campos.Keys) { $p[$k] = $Campos[$k] }
        $tmp = [System.IO.Path]::GetTempFileName()
        ($p | ConvertTo-Json -Depth 5) | Set-Content -Path $tmp -Encoding UTF8
        return $tmp
    }

    # Cria o perfil, importa a funcao e expande o texto.
    #
    # A importacao acontece AQUI, dentro do It, e nao no BeforeAll: o escopo do BeforeAll do
    # Pester morre no fim do bloco, e a funcao definida la nao existe dentro do It. Ja tentei
    # Set-Item function:script: (registra a funcao, mas o corpo para de ver $PerfilFile/$Py e
    # devolve $null) e Invoke-Expression no BeforeAll (CommandNotFoundException). Dentro do It
    # o Invoke-Expression define no escopo corrente e resolve as variaveis do proprio teste.
    function Invoke-ComPerfil {
        param([hashtable]$Campos, [string]$Texto)
        $script:PerfilFile = New-TestProfile -Campos $Campos
        $script:Py = $null
        Invoke-Expression (Get-PsFunctionText -Path $script:LoopPs1 -Name 'Expand-PerfilPlaceholders')
        return (Expand-PerfilPlaceholders $Texto)
    }
}

Describe 'Expand-PerfilPlaceholders' {
    Context 'perfil so-remoto (padrao)' {
        It 'substitui NIVEIS, AREA e TERMO_PRINCIPAL' {
            (Invoke-ComPerfil -Campos @{ } -Texto 'niveis={{NIVEIS}} area={{AREA}} termo={{TERMO_PRINCIPAL}}') |
                Should -Be 'niveis=junior area=tecnologia termo=termo um'
        }

        It 'TERMOS sai entre aspas e separados por virgula' {
            (Invoke-ComPerfil -Campos @{ termos = @('dev remoto', 'qa remoto') } -Texto '{{TERMOS}}') |
                Should -Be '"dev remoto", "qa remoto"'
        }

        It 'PULAR_TIPOS entra como lista separada por virgula' {
            (Invoke-ComPerfil -Campos @{ pular_tipos = @('venda porta a porta', 'telemarketing') } -Texto '{{PULAR_TIPOS}}') |
                Should -Be 'venda porta a porta, telemarketing'
        }

        It 'modelo so remoto manda a regra e o filtro corretos' {
            (Invoke-ComPerfil -Campos @{ modelos = @('remoto') } -Texto '{{REGRA_MODELO}}|{{FILTRO_MODELO}}|{{LOCAL_BUSCA}}') |
                Should -Be 'SOMENTE vagas REMOTAS (home office). Nunca presencial/hibrida.|remoto|Remoto'
        }

        It 'LINKEDIN_WT vira 2 (remoto) no filtro do LinkedIn' {
            (Invoke-ComPerfil -Campos @{ modelos = @('remoto') } -Texto '{{LINKEDIN_WT}}') | Should -Be '2'
        }
    }

    Context 'perfil com hibrido' {
        It 'REGRA_MODELO deixa de ser so-remoto e cita os modelos aceitos' {
            $out = Invoke-ComPerfil -Campos @{ modelos = @('remoto', 'hibrido') } -Texto '{{REGRA_MODELO}}'
            $out | Should -Not -Be 'SOMENTE vagas REMOTAS (home office). Nunca presencial/hibrida.'
            $out | Should -BeLike '*remoto | hibrido*'
        }

        It 'FILTRO_MODELO cita a cidade onde hibrido vale' {
            (Invoke-ComPerfil -Campos @{ modelos = @('remoto', 'hibrido'); cidades = @('Recife/PE') } -Texto '{{FILTRO_MODELO}}') |
                Should -Be 'remoto + hibrido em Recife/PE'
        }

        It 'LOCAL_BUSCA usa a primeira cidade quando hibrido' {
            (Invoke-ComPerfil -Campos @{ modelos = @('remoto', 'hibrido'); cidades = @('Recife/PE') } -Texto '{{LOCAL_BUSCA}}') |
                Should -Be 'Recife/PE'
        }

        It 'LINKEDIN_WT lista os varios modelos separados por %2C' {
            (Invoke-ComPerfil -Campos @{ modelos = @('remoto', 'hibrido', 'presencial') } -Texto '{{LINKEDIN_WT}}') |
                Should -Be '2%2C3%2C1'
        }
    }

    Context 'legado e fail-open' {
        It 'aceita o perfil com "nivel" singular em vez de "niveis"' {
            (Invoke-ComPerfil -Campos @{ niveis = $null; nivel = 'pleno' } -Texto '{{NIVEIS}}') | Should -Be 'pleno'
        }

        It 'perfil ilegivel nao estoura: usa os defaults e nao deixa placeholder no texto' {
            $quebrado = [System.IO.Path]::GetTempFileName()
            '{ isso nao e json' | Set-Content -Path $quebrado -Encoding UTF8
            $script:PerfilFile = $quebrado
            $script:Py = $null
            Invoke-Expression (Get-PsFunctionText -Path $script:LoopPs1 -Name 'Expand-PerfilPlaceholders')
            $out = Expand-PerfilPlaceholders '{{NIVEIS}}|{{AREA}}'
            $out | Should -Be 'junior | trainee|tecnologia'
            $out | Should -Not -BeLike '*{{*}}*'
        }

        It 'texto sem placeholder volta inalterado' {
            (Invoke-ComPerfil -Campos @{ } -Texto 'regra 7: so candidatura no Brasil') |
                Should -Be 'regra 7: so candidatura no Brasil'
        }
    }
}

Describe 'dry-run.ps1: plano da rodada' {
    Context 'descoberta dos adaptadores' {
        It 'inclui um site por adaptador versionado (fora _template e lib)' {
            $saida = & $script:DryRunPs1 -json
            $LASTEXITCODE | Should -Be 0
            $obj = ($saida | Out-String) | ConvertFrom-Json
            # Nao fixar o numero: contar a arvore e o que garante que um adapter novo entre
            # no plano sem ninguem editar o teste (ja quebrou uma vez com o "6" fixo).
            $adaptadores = @(Get-ChildItem (Join-Path $script:RepoRoot 'bot/sites') -Filter '*.sh' |
                Where-Object { $_.Name -notin @('_template.sh', 'lib.sh') })
            $adaptadores.Count | Should -BeGreaterThan 0
            $obj.site_count | Should -Be $adaptadores.Count
            @($obj.sites).Count | Should -Be $adaptadores.Count
        }

        It 'cobre os 10 adaptadores atuais' {
            $obj = (& $script:DryRunPs1 -json | Out-String) | ConvertFrom-Json
            $ids = @($obj.sites | ForEach-Object { $_.site_id })
            foreach ($esperado in @('indeed', 'gupy', 'linkedin', 'catho', 'infojobs', 'solides', 'trampos', 'vagas', 'programathor', 'geekhunter')) {
                $ids | Should -Contain $esperado
            }
        }

        It 'nao inclui _template nem lib no plano' {
            $obj = (& $script:DryRunPs1 -json | Out-String) | ConvertFrom-Json
            $ids = @($obj.sites | ForEach-Object { $_.site_id })
            $ids | Should -Not -Contain '_template'
            $ids | Should -Not -Contain 'lib'
        }
    }

    Context 'URL montada sem bash' {
        It 'slug de path usa hifen: catho e solidas' {
            foreach ($id in @('catho', 'solides')) {
                $obj = (& $script:DryRunPs1 -json -Site $id | Out-String) | ConvertFrom-Json
                $obj.sites[0].url_busca | Should -Not -BeLike '*%20*' -Because "$id usa hifen, nao %20"
                $obj.sites[0].url_busca | Should -BeLike '*-*'
            }
        }

        It 'query string usa %20: indeed, gupy e infojobs' {
            foreach ($id in @('indeed', 'gupy', 'infojobs')) {
                $obj = (& $script:DryRunPs1 -json -Site $id | Out-String) | ConvertFrom-Json
                $obj.sites[0].url_busca | Should -BeLike '*%20*'
            }
        }

        It 'nenhum site fica com o marcador SEU_TERMO na URL' {
            $obj = (& $script:DryRunPs1 -json | Out-String) | ConvertFrom-Json
            foreach ($s in $obj.sites) {
                $s.url_busca | Should -Not -BeLike '*SEU_TERMO*'
                $s.url_busca | Should -BeLike 'http*'
            }
        }
    }

    Context 'sites fora da area do perfil' {
        It 'perfil juridico marca os sites so-tech como pulados' {
            $tmp = [System.IO.Path]::GetTempFileName()
            @'
{
  "nome_perfil": "juridico-teste",
  "niveis": ["pleno"],
  "area": "jurídico (direito)",
  "termos": ["advogado pleno remoto"],
  "pular_tipos": ["vaga comissionada"]
}
'@ | Set-Content -Path $tmp -Encoding UTF8
            try {
                $obj = (& $script:DryRunPs1 -json -Profile $tmp | Out-String) | ConvertFrom-Json
                @($obj.perfil.sites_pular) | Should -Contain 'programathor'
                @($obj.perfil.sites_pular) | Should -Contain 'geekhunter'
                $pulados = @($obj.sites | Where-Object { $_.pulado_pelo_perfil } | ForEach-Object { $_.site_id })
                $pulados | Should -Contain 'programathor'
                $pulados | Should -Not -Contain 'catho'
            }
            finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
        }

        It 'sites_pular do perfil tem precedencia sobre o filtro automatico' {
            $tmp = [System.IO.Path]::GetTempFileName()
            @'
{
  "nome_perfil": "tech-pular-catho",
  "niveis": ["pleno"],
  "area": "tecnologia (backend)",
  "sites_pular": ["catho"],
  "termos": ["dev pleno remoto"],
  "pular_tipos": ["vaga comissionada"]
}
'@ | Set-Content -Path $tmp -Encoding UTF8
            try {
                $obj = (& $script:DryRunPs1 -json -Profile $tmp | Out-String) | ConvertFrom-Json
                $pulados = @($obj.sites | Where-Object { $_.pulado_pelo_perfil } | ForEach-Object { $_.site_id })
                $pulados | Should -Contain 'catho'
                # area tech mantem os so-tech: sites_pular explicito desliga o filtro por area
                $pulados | Should -Not -Contain 'geekhunter'
            }
            finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
        }
    }
}