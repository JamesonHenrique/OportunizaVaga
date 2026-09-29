"""Single-writer access to the state JSON files.

Without a lock, two writers doing load -> modify -> save at the same time (e.g. gmail-status
during a round) lose one of the updates, or race on a fixed tmp file name.

  with travado(path):            # exclusive, blocks up to `espera` seconds
      d = ler(path)
      ...
      gravar(path, d)            # atomic: unique tmp in the same dir + fsync + os.replace

Readers need no lock: os.replace makes every read see a whole file.
Portable: fcntl.flock on POSIX, msvcrt.locking on Windows (lock file: PATH.lock).
"""
import contextlib
import json
import os
import tempfile
import time


def _try_lock(fh):
    if os.name == "nt":
        import msvcrt
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(fh):
    if os.name == "nt":
        import msvcrt
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fh, fcntl.LOCK_UN)


@contextlib.contextmanager
def travado(path, espera=120):
    fh = open(path + ".lock", "a+")
    fim = time.time() + espera
    while True:
        try:
            _try_lock(fh)
            break
        except OSError:   # busy: BlockingIOError on POSIX, PermissionError on Windows
            if time.time() > fim:
                fh.close()
                raise TimeoutError(f"{path} locked by another process for {espera}s")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            _unlock(fh)
        finally:
            fh.close()


def ler(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        if default is None:
            raise
        return default


def gravar(path, d, indent=2):
    pasta = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=pasta)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=indent)
            fh.flush()
            os.fsync(fh.fileno())
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o777)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
