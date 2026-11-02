"""Shared builder for the content-independence redo.

One command per line, a catalog cycled from a chosen start,
then one pad line that makes the character count exact.
"""
import os
import shutil
import tempfile
from argparse import Namespace
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

BASH = (
    "echo ok",
    "true",
    "printf x",
    ":",
    "echo ok | wc -c",
    "echo a && echo b",
    "echo a || true",
    "if true; then echo a; fi",
    "for i in a; do echo $i; done",
    "f(){ echo a; }; f",
    "(echo a)",
    "{ echo a; }",
    "echo {a,b}",
    "echo $HOME",
    "echo $(true)",
    "echo $((1+2))",
    "echo a > /dev/null",
    "echo 'a b'",
    'echo "a b"',
    "echo allowed_interpreters",
    "pwd",
    "echo ${HOME}",
)

POWERSHELL = (
    "Write-Output ok",
    "Get-Location",
    "$true",
    "Write-Output 'a b'",
    'Write-Output "a b"',
    "Write-Output $HOME",
    "Write-Output (1 + 2)",
    "Write-Output $($true)",
    "if ($true) { Write-Output a }",
    "foreach ($i in 1) { Write-Output $i }",
    "function f { Write-Output a }; f",
    "& { Write-Output a }",
    "Write-Output a > $null",
    "Write-Output allowed_interpreters",
    "Get-Date",
    "Write-Output ${HOME}",
)


def pwsh():
    found = shutil.which("pwsh")
    if found:
        return found
    candidate = "/workspace/pwsh/pwsh"
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def compose(n, catalog, start, pad_open, pad_close):
    min_pad = 1 + len(pad_open) + 1 + len(pad_close)
    lines = []
    i = start
    while i - start < 1000000:
        line = catalog[i % len(catalog)]
        trial = "\n".join(lines + [line])
        if len(trial) + min_pad > n:
            break
        lines.append(line)
        i += 1
    if not lines:
        raise AssertionError("catalog line longer than the rung")
    body = "\n".join(lines)
    payload = "p" * (
        n - len(body) - len("\n") - len(pad_open) - len(pad_close))
    script = body + "\n" + pad_open + payload + pad_close
    if len(script) != n:
        raise AssertionError("%s != %s" % (len(script), n))
    return script


def bash_script(n, start):
    return compose(n, BASH, start, "echo '", "'")


def ps_script(n, start):
    return compose(n, POWERSHELL, start, "Write-Output '", "'")


def present(script, job_id, cap=None):
    from runner import runner
    from runner.runner import handle_mail, sign_payload
    from runner.wire import jobcrypto

    secret = (
        "0123456789abcdef"
        "fedcba9876543210"
        "0011223344556677"
        "8899aabbccddeeff"
    )
    executed = []

    def execute(*_a, **_k):
        executed.append(len(script))
        return {"exit_code": 0, "stdout": "", "stderr": "",
                "timed_out": False, "duration_sec": 0.0}

    notes = []
    job = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "kind": "exec", "script": script,
    }
    signed = sign_payload(job, secret)
    body = jobcrypto.encrypt_body(
        signed, secret, job_id=job["job_id"], key_id="",
        sign=sign_payload)
    msg = EmailMessage()
    msg["Subject"] = "[HOMING-PIGEON] job " + job["job_id"]
    msg["From"] = "si@example.com"
    msg.set_content(body)
    with tempfile.TemporaryDirectory() as directory:
        cfg = {
            "mailbox_user": "t@example.com",
            "shared_secret": secret,
            "base_dir": directory,
            "oracle_opinion_mode": "off",
        }
        if cap is not None:
            cfg["max_script_bytes"] = cap
        with mock.patch.object(runner, "execute_job", execute):
            with mock.patch.object(
                    runner, "log",
                    lambda message, level="INFO": notes.append(message)):
                handle_mail(
                    cfg, mock.Mock(), mock.Mock(), 3, msg.as_bytes(),
                    directory, {}, runner.build_secrets(cfg),
                    Namespace(dry_run=False, no_send=True), None)
    return executed, notes
