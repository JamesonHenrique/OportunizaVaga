# scripts/validate.ps1 — espelho Windows (PowerShell 5.1+) de scripts/validate.sh.
# Valida os JSONs do projeto contra os schemas em config/.
# Alvos: examples/*.example.json (obrigatorios) + bot/dados_candidato.json e
# bot/aplicadas.json quando existirem (dados locais, gitignored — nunca commite).
# Usa python+jsonschema (draft 2020-12) se disponivel; senao faz checagem
# estrutural minima embutida (JSON valido + chaves obrigatorias).
# Exit 0 = tudo ok; 1 = alguma falha. Chamado pelo setup e pelo CI.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\validate.ps1

$ErrorActionPreference = 'Stop'
$BOT_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $BOT_ROOT

$pairs = @(
    @('examples\dados_candidato.example.json', 'config\dados_candidato.schema.json', $true),
    @('examples\aplicadas.example.json', 'config\aplicadas.schema.json', $true),
    @('bot\dados_candidato.json', 'config\dados_candidato.schema.json', $false),
    @('bot\aplicadas.json', 'config\aplicadas.schema.json', $false)
)

$check = @()
foreach ($p in $pairs) {
    $f = $p[0]; $s = $p[1]; $req = $p[2]
    if (-not (Test-Path $f)) {
        if ($req) { Write-Host ("  [FALHA] {0} ausente" -f $f); exit 1 }
        else { Write-Host ("  [pq] {0} ausente — pulando (dado local, gitignored)." -f $f) }
    } elseif (-not (Test-Path $s)) {
        Write-Host ("  [FALHA] schema ausente: {0}" -f $s); exit 1
    } else {
        $check += ('{0}|{1}' -f $f, $s)
    }
}

# Localiza um python (qualquer um serve p/ a checagem).
$Py = $null
$PyIsLauncher = $false
foreach ($c in @('python3', 'python', 'py')) {
    $g = Get-Command $c -ErrorAction SilentlyContinue
    if ($g) { $Py = $g.Source; if ($c -eq 'py') { $PyIsLauncher = $true }; break }
}

function Test-MinimalPs([string]$f, [string]$s) {
    # Checagem estrutural minima nativa (sem python): JSON valido + obrigatorias.
    try { $doc = Get-Content $f -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
    catch { Write-Host ("  [FALHA] {0}: JSON invalido ({1})" -f $f, $_.Exception.Message); return $false }
    try { $schema = Get-Content $s -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop }
    catch { Write-Host ("  [FALHA] {0}: schema invalido ({1})" -f $s, $_.Exception.Message); return $false }
    $ok = $true
    foreach ($k in @($schema.required)) {
        if ($null -eq $k) { continue }
        if ($null -eq $doc.PSObject.Properties[$k]) {
            Write-Host ("  [FALHA] {0}: chave obrigatoria ausente: '{1}'" -f $f, $k); $ok = $false
        }
    }
    if ($null -ne $schema.properties.rodizio -and $null -ne $doc.rodizio) {
        foreach ($k in @($schema.properties.rodizio.required)) {
            if ($null -eq $k) { continue }
            if ($null -eq $doc.rodizio.PSObject.Properties[$k]) {
                Write-Host ("  [FALHA] {0}: chave obrigatoria ausente: 'rodizio.{1}'" -f $f, $k); $ok = $false
            }
        }
    }
    if ($null -ne $doc.PSObject.Properties['aplicadas'] -and $doc.aplicadas -isnot [System.Collections.IEnumerable]) {
        Write-Host ("  [FALHA] {0}: 'aplicadas' precisa ser array" -f $f); $ok = $false
    }
    if ($ok) { Write-Host ("  [ok] {0} (minima: chaves obrigatorias presentes)." -f $f) }
    return $ok
}

if ($null -eq $Py) {
    Write-Host "  [..] nenhum python encontrado — checagem estrutural minima nativa."
    $fails = 0
    foreach ($c in $check) {
        $parts = $c.Split('|', 2)
        if (-not (Test-MinimalPs $parts[0] $parts[1])) { $fails = 1 }
    }
    if ($fails -eq 0) { Write-Host 'validate: OK.' } else { Write-Host 'validate: FALHOU (veja itens [FALHA] acima).' }
    exit $fails
}

$pyCode = @'
import json, sys

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    HAVE = True
except ImportError:
    HAVE = False
    print("  [..] pacote 'jsonschema' ausente — checagem estrutural minima.")

def minima(doc, schema, rotulo):
    erros = []
    if not isinstance(doc, dict):
        return [rotulo + ": raiz precisa ser objeto JSON"]
    for k in schema.get("required", []):
        if k not in doc:
            erros.append(rotulo + ": chave obrigatoria ausente: '" + k + "'")
    props = schema.get("properties", {})
    if "rodizio" in props and isinstance(doc.get("rodizio"), dict):
        for k in props["rodizio"].get("required", []):
            if k not in doc["rodizio"]:
                erros.append(rotulo + ": chave obrigatoria ausente: 'rodizio." + k + "'")
    if "aplicadas" in doc and not isinstance(doc["aplicadas"], list):
        erros.append(rotulo + ": 'aplicadas' precisa ser array")
    return erros

falhas = 0
for arg in sys.argv[1:]:
    f, s = arg.split("|", 1)
    try:
        doc = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        print("  [FALHA] %s: JSON invalido (%s)" % (f, e))
        falhas = 1
        continue
    try:
        schema = json.load(open(s, encoding="utf-8"))
    except Exception as e:
        print("  [FALHA] %s: schema invalido (%s)" % (s, e))
        falhas = 1
        continue
    if HAVE:
        errs = sorted(Draft202012Validator(schema).iter_errors(doc),
                      key=lambda e: list(e.path))
        if errs:
            falhas = 1
            for e in errs:
                loc = "/".join(str(x) for x in e.path) or "(raiz)"
                print("  [FALHA] %s: %s -> %s" % (f, loc, e.message))
        else:
            print("  [ok] %s (jsonschema, draft 2020-12)." % f)
    else:
        errs = minima(doc, schema, f)
        if errs:
            falhas = 1
            for e in errs:
                print("  [FALHA] " + e)
        else:
            print("  [ok] %s (minima: chaves obrigatorias presentes)." % f)

sys.exit(1 if falhas else 0)
'@

if ($PyIsLauncher) {
    $pyCode | & $Py -3 - $check
} else {
    $pyCode | & $Py - $check
}
$STATUS = $LASTEXITCODE
if ($STATUS -eq 0) { Write-Host 'validate: OK.' } else { Write-Host 'validate: FALHOU (veja itens [FALHA] acima).' }
exit $STATUS
