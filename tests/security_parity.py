#!/usr/bin/env python3
"""Parity harness for the hardening milestones (M0).

Runs a fixed corpus of jobs through poll_once under three config
variants -- no security block, all features off, all features audit --
and compares normalized outputs. Later milestones extend the corpus
with jobs that exercise their features.
"""
import copy
import json
import os
import re
import secrets
import socket
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner.runner import poll_once  # noqa: E402
from runner import security as _security  # noqa: E402
from send_job import sign_payload  # noqa: E402
from tests.test_runner import FakeIMAP, FakeSMTP  # noqa: E402

SECRET = secrets.token_hex(32)
WRONG_SECRET = secrets.token_hex(32)
EXTRA_SECRET = secrets.token_hex(32)
SENDER = "runner@example.com"


def base_config(tmpdir):
    return {
        "mailbox_user": SENDER,
        "mailbox_password": "test-gmail-password",
        "shared_secret": SECRET,
        "additional_secrets": {"restricted": EXTRA_SECRET},
        "key_policies": {"restricted": {"allowed_kinds": ["ping"]}},
        "imap_host": "fake", "imap_port": 993,
        "smtp_host": "fake", "smtp_port": 587,
        "poll_interval_sec": 20,
        "max_job_age_sec": 3600,
        "max_output_bytes": 100000,
        "base_dir": tmpdir,
        "default_timeout_sec": 300,
        "workers": 1,
    }


def _payload(job_id, issued_at=None, **kw):
    p = {
        "v": 1, "type": "job", "job_id": job_id,
        "issued_at": (issued_at or datetime.now(timezone.utc)
                      ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": "ping",
    }
    p.update(kw)
    return p


def _email(payload, secret=SECRET):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = "[HOMING-PIGEON] job %s" % payload["job_id"]
    msg.set_content(sign_payload(payload, secret))
    return msg.as_bytes()


def build_corpus():
    """Return a list of (name, raw_email_bytes). Built once and shared
    across variants so timestamps inside the corpus are identical."""
    stale_at = datetime.now(timezone.utc) - timedelta(days=2)
    corpus = [
        ("ping", _email(_payload("parity-01"))),
        ("exec_plain", _email(_payload(
            "parity-02", kind="exec", script="echo hello-parity"))),
        ("exec_env", _email(_payload(
            "parity-03", kind="exec", script="echo $MYAPP_VAR",
            env={"MYAPP_VAR": "parity"}))),
        ("exec_args", _email(_payload(
            "parity-04", kind="exec", script="echo", args=["parity-arg"]))),
        ("exec_files_rejected", _email(_payload(
            "parity-05", kind="exec", script="echo hi",
            files=[{"name": "note.txt"}]))),  # no url -> rejected
        ("exec_timeout", _email(_payload(
            "parity-06", kind="exec", script="echo hi", timeout_sec=30))),
        ("bad_signature", _email(_payload("parity-07"), secret=WRONG_SECRET)),
        ("stale", _email(_payload("parity-08", issued_at=stale_at))),
        ("replay_a", _email(_payload("parity-09"))),
        ("replay_b", _email(_payload("parity-09"))),  # same id: replay
        ("oversized_legal", _email(_payload(
            "parity-10", kind="exec", script="echo " + "x" * 50000))),
        ("key_policy_reject", _email(_payload(
            "parity-11", kind="exec", script="echo hi",
            key_id="restricted"), secret=EXTRA_SECRET)),
        ("sensor_alert", _email(_payload(
            "parity-12", kind="sensor_alert", sensor="nope",
            alert={"msg": "test"}))),
    ]
    return corpus


_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?")


def normalize(text, tmpdir):
    text = text.replace(tmpdir, "<TMP>")
    text = _TS.sub("<TS>", text)
    text = re.sub(r'"duration_ms":\s*\d+', '"duration_ms": <D>', text)
    text = re.sub(r'"duration_sec":\s*[\d.]+', '"duration_sec": <D>', text)
    text = re.sub(r"duration=\d+(\.\d+)?s", "duration=<D>s", text)
    # The HMAC covers fields we normalize away (durations); drop it so
    # identical payloads compare equal. Authenticity is not under test.
    text = re.sub(r',"sig":"[0-9a-f]{96}"', '', text)
    try:
        text = text.replace(socket.gethostname(), "<HOST>")
    except Exception:
        pass
    return text


def read_audit_lines(tmpdir):
    path = os.path.join(tmpdir, _security.AUDIT_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.readlines()
    except OSError:
        return None


def run_variant(security_block, corpus):
    """Run the corpus through one poll cycle. Returns normalized outputs."""
    tmpdir = tempfile.mkdtemp(prefix="hp-parity-")
    cfg = base_config(tmpdir)
    if security_block is not None:
        cfg["security"] = copy.deepcopy(security_block)
    mails = [raw for _, raw in corpus]
    imap = FakeIMAP(mails)
    smtp = FakeSMTP()
    seen = {}
    seen_path = os.path.join(tmpdir, "seen.json")
    poll_once(cfg, tmpdir, seen, seen_path, imap=imap, smtp=smtp)
    sent = []
    for msg in smtp.sent:
        body = msg.get_content()
        sent.append((msg["Subject"], normalize(body, tmpdir)))
    return {
        "sent": sent,
        "flagged": list(imap.flagged),
        "seen": sorted(seen.keys()),
        "audit_lines": read_audit_lines(tmpdir),
    }


def all_off_block():
    return {"modes": {f: "off" for f in _security.FEATURES}}


def all_audit_block():
    return {"modes": {f: "audit" for f in _security.FEATURES}}
