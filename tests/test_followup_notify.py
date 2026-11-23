"""Offline regression: execute only follow-up notification code, never its runner."""

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "bot/followup.sh").read_text(encoding="utf-8")
SENTINEL = "FOLLOWUP_PRIVATE_SENTINEL"
PRIVATE = f"{SENTINEL} person@example.invalid https://example.invalid/private?secret={SENTINEL}"
SUCCESS = "📬 Follow-up semanal: concluído (status: sucesso)."
BUSY = "⚠️ Follow-up semanal: não concluído (motivo: Chrome ocupado); tenta de novo amanhã."
FAILURE = "⚠️ Follow-up semanal: falhou (motivo: falha de execução); tenta de novo amanhã."


def _run(status, *, direct=False, transport_status=0, missing_transport=False):
    # Extract only the real function and terminal result branch. Sourcing the whole
    # script would load credentials, acquire shared locks and start browser work.
    notify = SOURCE[SOURCE.index("notify() {"):SOURCE.index('\n\nFLOG=')]
    start = SOURCE.rindex('\n  if [ "$STATUS" -eq 0 ]; then')
    result = SOURCE[start:SOURCE.index('\nelse\n', start)]
    with tempfile.TemporaryDirectory(prefix=".followup-notify-", dir=ROOT / "tests") as directory:
        sandbox = Path(directory)
        capture = sandbox / "transport.args"
        log = sandbox / "synthetic.log"
        log.write_text((PRIVATE + "\n") * 25, encoding="utf-8")
        marker = sandbox / "followup.ok"
        curl = sandbox / "curl"
        curl.write_text(
            '#!/bin/bash\nprintf "%s\\0" "$@" >> "$CAPTURE"\nexit "$TRANSPORT_STATUS"\n',
            encoding="utf-8",
        )
        curl.chmod(0o700)
        # Deliberately do not inherit user configuration or real Telegram credentials.
        env = {
            "PATH": f"{sandbox}:{os.defpath}",
            "STATUS": str(status),
            "MODELO": PRIVATE,
            "FLOG": str(log),
            "OK_MARK": str(marker),
            "NOTIFICAR_SH": str(sandbox / "missing" if missing_transport else ROOT / "scripts/notificar.sh"),
            "CAPTURE": str(capture),
            "TRANSPORT_STATUS": str(transport_status),
            "TELEGRAM_BOT_TOKEN": "synthetic-token",
            "TELEGRAM_CHAT_ID": "synthetic-chat",
            "OV_NOTIFY_STATE": str(sandbox / "notify-state"),
            "OV_NOTIFY_JANELA_S": "0",
        }
        completed = subprocess.run(
            ["bash", "-c", notify + ('\nnotify "$STATUS"' if direct else result)],
            cwd=sandbox, env=env, capture_output=True, text=True, check=False,
        )
        assert completed.returncode == 0, completed.stderr
        args = capture.read_bytes().decode().split("\0")[:-1] if capture.exists() else []
        payloads = [arg.removeprefix("text=") for arg in args if arg.startswith("text=")]
        for secret in (SENTINEL, "person@example.invalid", "https://example.invalid/private"):
            assert secret not in "\n".join(args), "Private data reached the transport"
        return payloads, marker.exists()


def test_success_uses_fixed_template_and_preserves_success_marker():
    assert _run(0) == ([SUCCESS], True)


def test_failures_use_enumerated_reasons_without_success_marker():
    for status in (1, 75, 124, 137):
        assert _run(status) == ([BUSY if status == 75 else FAILURE], False)


def test_notification_boundary_rejects_free_text_and_unknown_status():
    for value in (PRIVATE, "", "0\n" + PRIVATE, "75 " + PRIVATE, "999"):
        assert _run(value, direct=True) == ([FAILURE], False)


def test_transport_failure_or_absence_remains_best_effort():
    assert _run(0, transport_status=22) == ([SUCCESS], True)
    assert _run(1, missing_transport=True) == ([], False)


if __name__ == "__main__":
    for name, function in sorted(list(globals().items())):
        if name.startswith("test_") and callable(function):
            function()
            print("ok -", name)
