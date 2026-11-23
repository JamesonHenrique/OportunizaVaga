#!/bin/bash
# All fixtures and scans stay inside disposable Git repositories.
set -eu
TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$TEST_ROOT/scripts/sanitize.sh" <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(sys.argv[1])
TOKEN = 'ghp_' + 'SyntheticSentinel0123456789'
PLACEHOLDER = 'jameson.henrique.dev' + '@gmail.com'
CASES = []


def case(function):
    CASES.append(function)
    return function


class Repo:
    def __init__(self, root):
        self.root = Path(root)
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0')
        # Do not inherit a caller's index, repository, or injected Git config.
        for key in list(self.env):
            if key.startswith('GIT_') and key not in (
                'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL', 'GIT_TERMINAL_PROMPT',
            ):
                del self.env[key]
        self.git('init', '-q')
        (self.root / 'scripts').mkdir()
        shutil.copyfile(SOURCE, self.root / 'scripts/sanitize.sh')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, env=self.env,
                              check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout

    def write(self, path, content='safe fixture\n', staged=False):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        if staged:
            self.git('add', '--', path)

    def check(self, success, operational=False):
        result = subprocess.run(['bash', 'scripts/sanitize.sh'], cwd=self.root,
                                env=self.env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        output = result.stdout.decode()
        assert (result.returncode == 0) == success, output
        assert TOKEN not in output and PLACEHOLDER not in output, 'Leaked fixture'
        assert ('sanitize OK' in output) == success, output
        if operational:
            assert 'erro operacional' in output, output

    def break_git(self, command, truncated=False):
        real_git = shutil.which('git')
        shim = self.root / '.git/test-bin'
        shim.mkdir()
        target = shim / 'git'
        action = "printf 'incomplete'; exit 0" if truncated else 'exit 73'
        target.write_text('#!/bin/bash\n'
                          f'if [ "$1" = "{command}" ]; then {action}; fi\n'
                          'exec ' + repr(real_git) + ' "$@"\n')
        target.chmod(0o755)
        self.env['PATH'] = str(shim) + os.pathsep + self.env['PATH']


@case
def safe_staged_and_untracked(repo):
    repo.write('tracked.txt', staged=True)
    repo.write('new file.txt')
    repo.check(True)


@case
def staged_secret_with_clean_local_content(repo):
    repo.write('index.txt', TOKEN, staged=True)
    repo.write('index.txt')
    repo.check(False)


@case
def staged_secret_without_local_diff(repo):
    repo.write('index.txt', TOKEN, staged=True)
    assert not repo.git('diff', '--name-only')
    repo.check(False)


@case
def staged_secret_deleted_locally(repo):
    repo.write('deleted.txt', TOKEN, staged=True)
    (repo.root / 'deleted.txt').unlink()
    repo.check(False)


@case
def safe_staged_deleted_locally(repo):
    repo.write('deleted.txt', staged=True)
    (repo.root / 'deleted.txt').unlink()
    repo.check(True)


@case
def unstaged_tracked_secret(repo):
    repo.write('tracked.txt', staged=True)
    repo.write('tracked.txt', TOKEN)
    repo.check(False)


@case
def untracked_secret_alongside_tracked(repo):
    repo.write('tracked.txt', staged=True)
    repo.write('untracked.txt', TOKEN)
    repo.check(False)


@case
def untracked_secret_without_tracked(repo):
    repo.write('untracked.txt', TOKEN)
    repo.check(False)


@case
def ignored_untracked_secret(repo):
    repo.write('.gitignore', 'ignored.txt\n')
    repo.write('ignored.txt', TOKEN)
    repo.check(True)


@case
def ignored_but_tracked_secret(repo):
    repo.write('tracked.txt', TOKEN, staged=True)
    repo.write('.gitignore', 'tracked.txt\n')
    repo.check(False)


@case
def isolated_placeholder(repo):
    repo.write('allowed.txt', PLACEHOLDER, staged=True)
    repo.check(True)


@case
def public_host_and_sample_postal_code_allow_only_the_match(repo):
    public_host = 'oportunizavaga-demo' + '.vercel.app'
    other_host = 'synthetic-unlisted' + '.vercel.app'
    sample_postal_code = '90000' + '-0000'
    repo.write('docs.txt', f'Visit https://{public_host}/guide to read more. CEP: {sample_postal_code}.', staged=True)
    repo.check(True)
    repo.write('mixed.txt', f'https://{public_host}/guide https://{other_host}')
    repo.check(False)
    repo.write('mixed.txt', sample_postal_code + ' ' + sample_postal_code[:-1])
    repo.check(False)


@case
def placeholder_then_token(repo):
    repo.write('mixed.txt', PLACEHOLDER + ' ' + TOKEN, staged=True)
    repo.check(False)


@case
def token_then_placeholder(repo):
    repo.write('mixed.txt', TOKEN + ' ' + PLACEHOLDER)
    repo.check(False)


@case
def placeholder_cannot_allow_same_pattern(repo):
    repo.write('mixed.txt', PLACEHOLDER + ' another' + '@gmail.com')
    repo.check(False)


@case
def prefix_placeholder_cannot_allow_token(repo):
    repo.write('mixed.txt', 'SEU_' + TOKEN)
    repo.check(False)


@case
def placeholder_filename_cannot_allow_content(repo):
    repo.write('SEU_ file with spaces.txt', TOKEN, staged=True)
    repo.check(False)


@case
def safe_placeholder_filename_with_spaces(repo):
    repo.write('SEU_ file with spaces.txt', staged=True)
    repo.check(True)


@case
def placeholder_filename_cannot_allow_other_path_match(repo):
    repo.write('SEU_ ' + TOKEN + '.txt', staged=True)
    repo.check(False)


@case
def token_before_path_placeholder(repo):
    repo.write(TOKEN + ' SUA_ file.txt')
    repo.check(False)


@case
def quoted_newline_tab_and_option_paths(repo):
    for name in ["quotes ' and \".txt", 'line\nbreak.txt', 'tab\tfile.txt', '-n.txt']:
        repo.write(name, staged=True)
    repo.check(True)
    repo.write('line\nbreak.txt', TOKEN)
    repo.check(False)


@case
def binary_secret(repo):
    (repo.root / 'binary.dat').write_bytes(b'\0' + TOKEN.encode() + b'\0')
    repo.check(False)


@case
def symlink_target_path_scanned(repo):
    repo.write(TOKEN)
    (repo.root / 'link').symlink_to(TOKEN)
    repo.git('add', '--', 'link')
    repo.check(False)


@case
def symlink_content_preserves_local_scan(repo):
    repo.write('.gitignore', 'ignored.txt\n')
    repo.write('ignored.txt', TOKEN)
    (repo.root / 'link').symlink_to('ignored.txt')
    repo.check(False)


@case
def broken_symlink_read_error(repo):
    (repo.root / 'link').symlink_to('missing.txt')
    repo.check(False, operational=True)


@case
def forbidden_ignored_file(repo):
    repo.write('.gitignore', 'auth.json\n')
    repo.write('auth.json')
    repo.check(False)


@case
def forbidden_staged_deleted_file(repo):
    repo.write('bot/private.pdf', staged=True)
    (repo.root / 'bot/private.pdf').unlink()
    repo.check(False)


@case
def nested_private_names_are_blocked_even_when_ignored(repo):
    paths = ['export/deep/.env.local', 'export/deep/dados_candidato.json',
             'export/deep/aplicadas.json', 'export/deep/perfil.json']
    repo.write('.gitignore', 'export/\n')
    for path in paths:
        repo.write(path)
        repo.check(False)
        (repo.root / path).unlink()
    repo.check(True)


@case
def example_and_fixture_filenames_are_allowed(repo):
    repo.write('export/perfil.example.json', staged=True)
    repo.write('tests/fixtures/nested/.env.test', staged=True)
    repo.write('tests/fixtures/nested/aplicadas.json', staged=True)
    repo.check(True)


@case
def existing_exclusions(repo):
    repo.write('docs/SEGURANCA.md', TOKEN, staged=True)
    repo.check(True)


@case
def enumeration_error(repo):
    repo.break_git('ls-files')
    repo.check(False, operational=True)


@case
def incomplete_enumeration(repo):
    repo.break_git('ls-files', truncated=True)
    repo.check(False, operational=True)


@case
def blob_read_error(repo):
    repo.write('tracked.txt', staged=True)
    repo.break_git('cat-file')
    repo.check(False, operational=True)


@case
def local_read_error(repo):
    repo.write('tracked.txt', staged=True)
    (repo.root / 'tracked.txt').unlink()
    # Opening a directory as a file must fail rather than be silently skipped.
    (repo.root / 'tracked.txt').mkdir()
    repo.check(False, operational=True)


for test in CASES:
    with tempfile.TemporaryDirectory(prefix='sanitize-test-') as root:
        test(Repo(root))
    print('PASS ' + test.__name__)
print(f'{len(CASES)} isolated sanitizer cases passed.')
PY
