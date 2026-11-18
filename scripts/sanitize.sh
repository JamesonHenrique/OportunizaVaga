#!/bin/bash
# Scan index blobs and tracked/non-ignored untracked local files before commit.
set -u
BOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
cd "$BOT_ROOT" || exit 1

command -v python3 >/dev/null 2>&1 || { echo '[FALHA] python3 necessário para sanitizar.'; exit 1; }
python3 - <<'PY'
import os
import re
import stat
import subprocess
import sys

PATTERNS = [
    rb'@gmail\.com', rb'@hotmail\.', rb'@outlook\.', rb'@yahoo\.',
    rb'home/james', rb'/home/[a-z]',
    rb'monitor-one-bice', rb'vercel\.app.*[a-z0-9-]{3,}',
    rb'BEGIN (RSA )?PRIVATE KEY', rb'AKIA[0-9A-Z]{16}',
    rb'ghp_[A-Za-z0-9]{20,}', rb'gho_[A-Za-z0-9]{20,}',
    rb'sk-ant-[A-Za-z0-9-]{10,}', rb'sk-or-[A-Za-z0-9-]{10,}',
    rb'xox[bpas]-[A-Za-z0-9-]{10,}',
    rb'''OPENROUTER_API_KEY=["']?[A-Za-z0-9_-]{16,}''',
    rb'Bearer [A-Za-z0-9._-]{20,}',
    rb'[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}', rb'[0-9]{5}-[0-9]{3}',
    rb'R\$ ?[0-9]\.[0-9]{3}',
]
ALLOW = re.compile(
    rb'seu-email@example\.com|jameson\.henrique\.dev@gmail\.com|SEU_|SUA_|'
    rb'SUA-EMPRESA|<sua-empresa>|sua-url\.vercel\.app|'
    rb'oportunizavaga-demo\.vercel\.app|jamesonhenrique-portfolio\.vercel\.app|'
    rb'\$HOME|\${BOT_ROOT}|\$BOT_ROOT|\$HOME/opensource|00000-0000|'
    rb'\(00\)|OPENROUTER_API_KEY=\(\.\+\)'
)
EXCLUDED = {b'scripts/sanitize.sh', b'docs/SEGURANCA.md'}
FORBIDDEN = {
    b'bot/dados_candidato.json', b'bot/aplicadas.json', b'config/cron.env',
    b'cron.env', b'auth.json', b'bot/auth.json',
}
patterns = [re.compile(pattern) for pattern in PATTERNS]


def git(*args):
    # Never forward Git diagnostics: they can contain sensitive paths/data.
    return subprocess.run(
        ['git', *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        check=True,
    ).stdout


def records(data):
    if data and not data.endswith(b'\0'):
        raise ValueError('Incomplete path enumeration')
    return data[:-1].split(b'\0') if data else []


def forbidden(path):
    return path in FORBIDDEN or (
        path.startswith(b'bot/') and b'/' not in path[4:] and path.endswith(b'.pdf')
    )


def detected(data):
    # Exempt only matches fully contained in a known placeholder. A placeholder
    # elsewhere on the same line (or in its filename) cannot suppress a hit.
    for line in data.split(b'\n'):
        allowed = [match.span() for match in ALLOW.finditer(line)]
        for pattern in patterns:
            for match in pattern.finditer(line):
                if not any(start <= match.start() and match.end() <= end
                           for start, end in allowed):
                    return True
    return False


def scan():
    failed = False
    index = records(git('ls-files', '--stage', '-z'))
    local = records(git('ls-files', '--cached', '--others', '--exclude-standard', '-z'))
    deleted = set(records(git('ls-files', '--deleted', '-z')))
    for entry in index:
        metadata, path = entry.split(b'\t', 1)
        mode, oid, stage = metadata.split(b' ')
        if stage != b'0':
            raise ValueError('Unmerged index')
        failed |= forbidden(path) or detected(path)
        if path in EXCLUDED:
            continue
        if mode not in (b'100644', b'100755', b'120000'):
            raise ValueError('Unsupported index entry')
        failed |= detected(git('cat-file', 'blob', oid.decode('ascii')))
    for path in set(local):
        failed |= forbidden(path) or detected(path)
        if path in EXCLUDED:
            continue
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            if path in deleted:
                continue  # Its index blob was still inspected above.
            raise
        if stat.S_ISLNK(info.st_mode):
            failed |= detected(os.readlink(path))
            # Preserve the original local content scan through file symlinks.
            # Missing/unreadable targets fail closed, just like other read errors.
            if not stat.S_ISREG(os.stat(path).st_mode):
                raise ValueError('Unsupported symlink target')
        elif not stat.S_ISREG(info.st_mode):
            raise ValueError('Unsupported local entry')
        with open(path, 'rb') as stream:
            data = stream.read()
        failed |= detected(data)
    # Preserve checks for forbidden local files even when Git ignores them.
    for path in FORBIDDEN:
        failed |= os.path.lexists(path)
    if os.path.isdir(b'bot'):
        with os.scandir(b'bot') as entries:
            failed |= any(entry.name.endswith(b'.pdf') for entry in entries)
    return failed


try:
    failed = scan()
except Exception:
    print('[FALHA] erro operacional: inspeção incompleta; nenhum conteúdo exibido.')
    sys.exit(1)
if failed:
    print('[FALHA] segredo, dado pessoal ou arquivo proibido detectado; nenhum conteúdo exibido.')
    sys.exit(1)
print('sanitize OK: nenhum segredo ou dado pessoal detectado.')
PY
