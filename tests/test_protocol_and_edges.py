import io
import contextlib
#!/usr/bin/env python3
"""Expanded unit and integration tests for homing-pigeon.

Covers protocol validation (age, version, job_id, sender), execution
edges (env, args, truncation, missing script, SHA mismatch via mock),
seen-set capping, multipart bodies, crypto edge cases, and install
helpers that do not touch the real system.
"""

import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "cloud"))

from runner.runner import (  # noqa: E402
    JobRejected,
    execute_job,
    fetch_job_mails,
    get_text_body,
    load_seen,
    _worker_count,
    platform_interpreter,
    poll_once,
    save_seen,
    sha384_of,
    sign_payload,
    verify_body,
    SEEN_CAP,
)
from runner import install as install_mod  # noqa: E402
from send_job import sign_payload as cloud_sign  # noqa: E402

SECRET = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
SENDER = "runner@example.com"


class FakeIMAP:
    def __init__(self, mails):
        self.mails = list(mails)
        self.flagged = []

    def login(self, u, p):
        return ("OK", [])

    def select(self, box):
        return ("OK", [])

    def search(self, *args):
        nums = b" ".join(str(i + 1).encode() for i in range(len(self.mails)))
        return ("OK", [nums])

    def fetch(self, num, _spec):
        raw = self.mails[int(num) - 1]
        head = f"{num.decode()} (RFC822 {{{len(raw)}}}".encode()
        return ("OK", [(head, raw), b")"])

    def store(self, seq, _op, _flags):
        self.flagged.append(seq)
        return ("OK", [])

    def logout(self):
        return ("OK", [])


class FakeSMTP:
    def __init__(self):
        self.sent = []

    def starttls(self):
        pass

    def login(self, u, p):
        pass

    def send_message(self, msg):
        self.sent.append(msg)

    def quit(self):
        pass


def now_iso(delta=None):
    dt = datetime.now(timezone.utc)
    if delta:
        dt = dt + delta
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def job_email(payload, secret=SECRET, sender=SENDER, subject_id=None):
    jid = subject_id or payload.get("job_id", "x")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = sender
    msg["Subject"] = f"[HOMING-PIGEON] job {jid}"
    msg.set_content(sign_payload(payload, secret))
    return msg.as_bytes()


def base_job(jid, **kw):
    p = {
        "v": 1, "type": "job", "job_id": jid,
        "issued_at": now_iso(), "kind": "ping",
    }
    p.update(kw)
    return p


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-edge-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
            "shared_secret": SECRET,
            "imap_host": "fake", "imap_port": 993,
            "smtp_host": "fake", "smtp_port": 587,
            "max_job_age_sec": 3600,
            "max_output_bytes": 40,
            "default_timeout_sec": 300,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, cfg=None, seen=None, opts=None):
        cfg = cfg or self.cfg
        seen = {} if seen is None else seen
        imap, smtp = FakeIMAP(mails), FakeSMTP()
        poll_once(cfg, self.tmp, seen, self.seen_path, imap=imap, smtp=smtp,
                  opts=opts)
        return imap, smtp, seen

    def test_too_old(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, issued_at=now_iso(timedelta(hours=-3)))
        imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 0)
        self.assertIn("1", imap.flagged)
        self.assertNotIn(jid, seen)

    def test_future_beyond_skew(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, issued_at=now_iso(timedelta(minutes=10)))
        _, smtp, _ = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 0)

    def test_within_skew_accepted(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, issued_at=now_iso(timedelta(seconds=-30)))
        _, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid, seen)

    def test_unparseable_issued_at(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, issued_at="yesterday")
        _, smtp, _ = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 0)

    def test_job_id_mismatch(self):
        body_id = str(uuid.uuid4())
        subj_id = str(uuid.uuid4())
        p = base_job(body_id)
        _, smtp, _ = self.cycle([job_email(p, subject_id=subj_id)])
        self.assertEqual(len(smtp.sent), 0)

    def test_wrong_version(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, v=2)
        _, smtp, _ = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 0)

    def test_wrong_type(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, type="result")
        _, smtp, _ = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 0)

    def test_any_sender_accepted_with_valid_signature(self):
        # Sender address is not validated; the HMAC signature is the
        # sole authentication gate.
        jid = str(uuid.uuid4())
        _, smtp, seen = self.cycle(
            [job_email(base_job(jid), sender="stranger@example.com")])
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid, seen)

    def test_any_sender_rejected_with_bad_signature(self):
        jid = str(uuid.uuid4())
        _, smtp, _ = self.cycle(
            [job_email(base_job(jid), secret="wrong-secret",
                       sender="stranger@example.com")])
        self.assertEqual(len(smtp.sent), 0)

    def test_subject_pattern_mismatch(self):
        jid = str(uuid.uuid4())
        msg = EmailMessage()
        msg["From"] = SENDER
        msg["To"] = SENDER
        msg["Subject"] = "just a normal email"
        msg.set_content(sign_payload(base_job(jid), SECRET))
        imap, smtp, _ = self.cycle([msg.as_bytes()])
        self.assertEqual(len(smtp.sent), 0)
        self.assertIn("1", imap.flagged)

    def test_subject_allows_test_word_and_re(self):
        # The connector happy-path used "[HOMING-PIGEON] TEST job <id>".
        for prefix in ("[HOMING-PIGEON] TEST job ", "Re: [HOMING-PIGEON] job "):
            jid = str(uuid.uuid4())
            msg = EmailMessage()
            msg["From"] = SENDER
            msg["To"] = SENDER
            msg["Subject"] = prefix + jid
            msg.set_content(sign_payload(base_job(jid), SECRET))
            imap, smtp, seen = self.cycle([msg.as_bytes()])
            self.assertEqual(len(smtp.sent), 1, prefix)
            self.assertIn(jid, seen)


class ExecutionEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-exec-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
            "shared_secret": SECRET,
            "max_output_bytes": 30,
            "default_timeout_sec": 300,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, cfg=None):
        cfg = cfg or self.cfg
        imap, smtp, seen = FakeIMAP(mails), FakeSMTP(), {}
        poll_once(cfg, self.tmp, seen, self.seen_path, imap=imap, smtp=smtp)
        return imap, smtp, seen

    def test_missing_script_or_url(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec")
        _, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("requires script", r["stderr"])
        self.assertIn(jid, seen)

    def test_env_and_args(self):
        jid = str(uuid.uuid4())
        script = 'echo "A=$1 E=$MYE"'
        p = base_job(jid, kind="exec", script=script, interpreter=["sh"],
                     args=["zz"], env={"MYE": "yy"})
        _, smtp, _ = self.cycle([job_email(p)])
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], 0)
        self.assertIn("A=zz", r["stdout"])
        self.assertIn("E=yy", r["stdout"])

    def test_stdout_truncation_flag(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec",
                     script="printf '%s' 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'",
                     interpreter=["sh"])
        _, smtp, _ = self.cycle([job_email(p)])
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertTrue(r["stdout_truncated"])
        self.assertLessEqual(len(r["stdout"]), 30)

    def test_timeout_capped(self):
        job = {
            "job_id": "cap",
            "kind": "exec",
            "script": "echo capped",
            "interpreter": ["sh"],
            "timeout_sec": 999999,
        }
        r = execute_job(self.cfg, job, self.tmp)
        self.assertEqual(r["exit_code"], 0)
        self.assertIn("capped", r["stdout"])

    def test_unknown_kind_direct(self):
        with self.assertRaises(JobRejected):
            execute_job(self.cfg, {"job_id": "k", "kind": "nope"}, self.tmp)

    def test_path_traversal_direct(self):
        job = {
            "job_id": "t",
            "kind": "exec",
            "script": "echo",
            "files": [{"name": "../escape", "url": "http://invalid"}],
        }
        with self.assertRaises(JobRejected):
            execute_job(self.cfg, job, self.tmp)

    def test_sha384_mismatch_mocked(self):
        job = {
            "job_id": "sha",
            "kind": "exec",
            "script": "echo",
            "files": [{"name": "f.txt", "url": "http://x", "sha384": "deadbeef"}],
        }
        with patch("runner.runner.download", lambda u, d: open(d, "w").write("data")):
            with self.assertRaises(JobRejected) as cm:
                execute_job(self.cfg, job, self.tmp)
            self.assertIn("SHA384 mismatch", str(cm.exception))

    def test_sha384_match_mocked(self):
        content = b"hello-file"
        job = {
            "job_id": "shaok",
            "kind": "exec",
            "script": "cat f.txt",
            "interpreter": ["sh"],
            "files": [{"name": "f.txt", "url": "http://x", "sha384": "PLACEHOLDER"}],
        }

        def fake_dl(url, dest):
            with open(dest, "wb") as f:
                f.write(content)

        with patch("runner.runner.download", fake_dl):
            import hashlib
            h = hashlib.sha384(content).hexdigest()
            job["files"][0]["sha384"] = h
            r = execute_job(self.cfg, job, self.tmp)
            self.assertEqual(r["exit_code"], 0)
            self.assertIn("hello-file", r["stdout"])


class SeenAndHelpersTests(unittest.TestCase):
    def test_seen_cap_keeps_newest(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            seen = {f"id-{i:04d}": True for i in range(2500)}
            save_seen(path, seen)
            loaded = load_seen(path)
            self.assertEqual(len(loaded), 2000)
            self.assertIn("id-2499", loaded)
            self.assertNotIn("id-0000", loaded)

    def test_load_seen_missing(self):
        self.assertEqual(load_seen("/no/such/seen.json"), {})

    def test_load_seen_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.json")
            with open(path, "w") as f:
                f.write("{broken")
            self.assertEqual(load_seen(path), {})

    def test_load_seen_not_list(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "obj.json")
            with open(path, "w") as f:
                json.dump({"a": 1}, f)
            self.assertEqual(load_seen(path), {})

    def test_get_text_body_plain(self):
        m = EmailMessage()
        m.set_content("plain body")
        self.assertIn("plain body", get_text_body(m))

    def test_multipart_prefers_plain(self):
        jid = str(uuid.uuid4())
        signed = sign_payload(base_job(jid), SECRET)
        msg = MIMEMultipart()
        msg["From"] = SENDER
        msg["To"] = SENDER
        msg["Subject"] = f"[HOMING-PIGEON] job {jid}"
        msg.attach(MIMEText("<b>html</b>", "html"))
        msg.attach(MIMEText(signed, "plain"))
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "mailbox_user": SENDER,
                "mailbox_password": SECRET,
            "shared_secret": SECRET,
                "max_job_age_sec": 3600,
            }
            imap, smtp, seen = FakeIMAP([msg.as_bytes()]), FakeSMTP(), {}
            poll_once(cfg, d, seen, os.path.join(d, "s.json"),
                      imap=imap, smtp=smtp)
            self.assertEqual(len(smtp.sent), 1)
            self.assertIn(jid, seen)

    def test_platform_interpreter(self):
        interp = platform_interpreter()
        self.assertIsInstance(interp, list)
        self.assertTrue(len(interp) >= 1)
        if os.name == "nt":
            self.assertEqual(interp[0], "powershell")
        else:
            self.assertEqual(interp, ["sh"])

    def test_cloud_runner_sign_compatible(self):
        p = {"v": 1, "type": "job", "job_id": "c", "kind": "ping"}
        self.assertEqual(sign_payload(p, SECRET), cloud_sign(p, SECRET))
        self.assertEqual(verify_body(cloud_sign(p, SECRET), SECRET)["job_id"], "c")

    def test_sha384_of_known(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f")
            with open(path, "wb") as f:
                f.write(b"abc")
            # SHA-384 of "abc"
            self.assertEqual(
                sha384_of(path),
                "cb00753f45a35e8bb5a03d699ac65007272c32ab0eded1631a8b605a43ff5bed"
                "8086072ba1e7cc2358baeca134c825a7",
            )


class InstallHelperTests(unittest.TestCase):
    def test_src_dir_not_frozen(self):
        # When not frozen, _src_dir points at the runner package directory
        d = install_mod._src_dir()
        self.assertTrue(os.path.isdir(d))
        self.assertTrue(os.path.exists(os.path.join(d, "runner.py")))

    def test_runner_argv_not_frozen(self):
        argv = install_mod._runner_argv("/tmp/dst")
        self.assertIn("runner.py", argv[-1])
        self.assertTrue(argv[-1].endswith("runner.py"))

    def test_install_files_copies_and_config(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            # minimal source layout
            open(os.path.join(src, "runner.py"), "w").write("# stub\n")
            open(os.path.join(src, "oauth.py"), "w").write("# stub\n")
            open(os.path.join(src, "winlog.py"), "w").write("# stub\n")
            open(os.path.join(src, "config.example.json"), "w").write("{}\n")
            with patch.object(install_mod, "FROZEN", False):
                install_mod.install_files(src, dst)
            self.assertTrue(os.path.exists(os.path.join(dst, "runner.py")))

    def test_macos_plist_escapes_xml_metachars(self):
        import plistlib
        with tempfile.TemporaryDirectory() as tmp:
            # & needs XML escaping but is a valid filename on all platforms
            # (< and > would also test escaping but are illegal on Windows)
            dst = os.path.join(tmp, "a&b")
            os.makedirs(dst)
            la = os.path.join(tmp, "LA")
            with patch.object(install_mod, "run", lambda *a, **k: None), \
                 patch("os.getuid", lambda: 501, create=True), \
                 patch("os.path.expanduser",
                       lambda p: p.replace("~/Library/LaunchAgents", la)):
                install_mod.install_macos(dst, os.path.join(dst, "config.json"))
            with open(os.path.join(la, "com.homing-pigeon.runner.plist"),
                      "rb") as fh:
                pl = plistlib.load(fh)  # raises on malformed XML
            self.assertEqual(pl["ProgramArguments"][-1],
                             os.path.join(dst, "config.json"))

    def test_linux_unit_includes_forwarded_flags(self):
        import types
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "d")
            udir = os.path.join(tmp, "systemd")
            fake = types.SimpleNamespace(
                dry_run=True, no_oracle=False, no_send=True, verbose=True,
                pdb=False, poll_interval=30, max_output_bytes=None,
                timeout=None)
            with patch.object(install_mod, "run", lambda *a, **k: None):
                with patch("os.path.expanduser", lambda p: udir):
                    install_mod.install_linux(
                        dst, os.path.join(dst, "config.json"),
                        system=False,
                        extra=install_mod._forwarded_args(fake))
            with open(os.path.join(udir, "homing-pigeon.service")) as fh:
                unit = fh.read()
            self.assertIn("--dry-run", unit)
            self.assertIn("--no-send", unit)
            self.assertNotIn("--quiet", unit)
            self.assertIn("--poll-interval 30", unit)
            self.assertNotIn("--no-oracle", unit)

    def test_forwarded_args_empty_by_default(self):
        import types
        fake = types.SimpleNamespace(
            dry_run=False, no_oracle=False, no_send=False, verbose=False,
            pdb=False, poll_interval=None, max_output_bytes=None,
            timeout=None)
        self.assertEqual(install_mod._forwarded_args(fake), ["--quiet"])

    def test_linux_unit_quotes_spaced_paths(self):
        import shlex
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "my dir")
            udir = os.path.join(tmp, "systemd")
            with patch.object(install_mod, "run", lambda *a, **k: None):
                with patch("os.path.expanduser", lambda p: udir):
                    install_mod.install_linux(dst, os.path.join(dst, "config.json"),
                                              system=False)
            with open(os.path.join(udir, "homing-pigeon.service")) as fh:
                unit = fh.read()
            self.assertIn(shlex.quote(os.path.join(dst, "runner.py")), unit)
            self.assertIn("--config " + shlex.quote(os.path.join(dst, "config.json")),
                          unit)


class InfiniteRetryBugs(unittest.TestCase):
    """Lock in the two bugs that previously caused permanent retries."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-retry-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
            "shared_secret": SECRET,
            "max_job_age_sec": 3600,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, seen=None):
        imap, smtp = FakeIMAP(mails), FakeSMTP()
        if seen is None:
            seen = {}
        poll_once(self.cfg, self.tmp, seen, self.seen_path,
                  imap=imap, smtp=smtp)
        return imap, smtp, seen

    def test_naive_issued_at_rejected_not_retried(self):
        jid = str(uuid.uuid4())
        # No Z, no offset -> naive datetime. Previously TypeError -> infinite retry.
        p = base_job(jid, issued_at="2026-10-13T17:00:00")
        imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 0)
        self.assertIn("1", imap.flagged)   # marked seen
        self.assertNotIn(jid, seen)

    def test_string_interpreter_rejected_not_retried(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo hi", interpreter="sh")
        imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("interpreter must be", r["stderr"])
        self.assertIn("1", imap.flagged)
        self.assertIn(jid, seen)



    def test_missing_interpreter_is_poison_not_retried(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo hi",
                     interpreter=["/no/such/homing-pigeon-binary"])
        imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("cannot start interpreter", r["stderr"])
        self.assertIn(jid, seen)
        self.assertIn("1", imap.flagged)
        # second cycle must not re-execute
        imap2, smtp2, seen2 = self.cycle([job_email(p)], seen=seen)
        self.assertEqual(len(smtp2.sent), 0)
        self.assertIn(jid, seen2)

class PoisonShapeTests(unittest.TestCase):
    """Malformed-but-signed jobs are poison: rejected (exit -2), never retried."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-poison-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
            "shared_secret": SECRET,
            "max_job_age_sec": 3600,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails):
        imap, smtp, seen = FakeIMAP(mails), FakeSMTP(), {}
        poll_once(self.cfg, self.tmp, seen, self.seen_path,
                  imap=imap, smtp=smtp)
        return imap, smtp, seen

    def assert_rejected(self, payload, needle):
        """execute_job-level poison: -2 result sent, mail seen, job recorded."""
        jid = payload["job_id"]
        imap, smtp, seen = self.cycle([job_email(payload)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn(needle, r["stderr"])
        self.assertIn("1", imap.flagged)
        self.assertIn(jid, seen)

    def exec_job(self, jid, **kw):
        p = base_job(jid, kind="exec", script="echo hi")
        p.update(kw)
        return p

    def test_timeout_sec_string(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(self.exec_job(jid, timeout_sec="abc"), "timeout_sec")

    def test_timeout_sec_float_string(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(self.exec_job(jid, timeout_sec="1.5"), "timeout_sec")

    def test_timeout_sec_list(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(self.exec_job(jid, timeout_sec=[30]), "timeout_sec")

    def test_files_not_list(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(self.exec_job(jid, files={"name": "x"}),
                             "files must be a list")

    def test_file_entry_missing_url(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(self.exec_job(jid, files=[{"name": "x"}]),
                             "each file needs")

    def test_file_entry_nonstring_name(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(
            self.exec_job(jid, files=[{"name": 5, "url": "http://x"}]),
            "each file needs")

    def test_env_not_dict(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(self.exec_job(jid, env=["A=1"]),
                             "env must be an object")

    def test_args_not_list(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(self.exec_job(jid, args=5), "args must be a list")

    def test_script_not_string(self):
        jid = str(uuid.uuid4())
        self.assert_rejected(self.exec_job(jid, script={"x": 1}),
                             "script must be a string")

    def test_script_url_not_string(self):
        jid = str(uuid.uuid4())
        p = self.exec_job(jid)
        del p["script"]
        p["script_url"] = 5
        self.assert_rejected(p, "script_url must be a string")

    def test_nondict_body_rejected(self):
        # Hand-signed JSON list: pre-execution reject, no result, marked seen.
        jid = str(uuid.uuid4())
        raw = "[1,2,3]"
        sig = hmac.new(SECRET.encode(), raw.encode(),
                       hashlib.sha384).hexdigest()
        body = raw[:-1] + ',"sig":"' + sig + '"}'
        msg = EmailMessage()
        msg["From"] = SENDER
        msg["To"] = SENDER
        msg["Subject"] = f"[HOMING-PIGEON] job {jid}"
        msg.set_content(body)
        imap, smtp, seen = self.cycle([msg.as_bytes()])
        self.assertEqual(len(smtp.sent), 0)
        self.assertIn("1", imap.flagged)
        self.assertNotIn(jid, seen)


class AdversarialTests(unittest.TestCase):
    """Attacker-minded cases: traversal, poison passthrough, resource caps."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-adv-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
            "shared_secret": SECRET,
            "max_job_age_sec": 3600,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, seen=None, opts=None):
        imap, smtp = FakeIMAP(mails), FakeSMTP()
        seen = {} if seen is None else seen
        poll_once(self.cfg, self.tmp, seen, self.seen_path,
                  imap=imap, smtp=smtp, opts=opts)
        return imap, smtp, seen

    def assert_rejected(self, payload, needle):
        jid = payload["job_id"]
        imap, smtp, seen = self.cycle([job_email(payload)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn(needle, r["stderr"])
        self.assertIn(jid, seen)
        return imap, smtp, seen

    def test_job_id_dotdot_rejected_and_base_dir_untouched(self):
        # ".." collapses work/ onto base_dir; without the fix,
        # files[].name="config.json" would overwrite the runner's config.
        p = base_job("..", kind="exec", script="echo hi",
                     files=[{"name": "config.json", "url": "http://x/"}])
        self.assert_rejected(p, "must not be '.' or '..'")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "config.json")))

    def test_job_id_dot_rejected(self):
        p = base_job(".", kind="exec", script="echo hi")
        self.assert_rejected(p, "must not be '.' or '..'")

    def test_file_traversal_rejected(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo hi",
                     files=[{"name": "../../evil", "url": "http://x/"}])
        self.assert_rejected(p, "unsafe file name")

    def test_file_absolute_path_rejected(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo hi",
                     files=[{"name": "/etc/evil", "url": "http://x/"}])
        self.assert_rejected(p, "unsafe file name")

    def test_oversize_download_is_poison_not_transient(self):
        # Without the `except JobRejected: raise` passthrough, the size
        # error would be wrapped as RuntimeError -> retried forever.
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo hi",
                     files=[{"name": "big.bin", "url": "http://x/big"}])
        with patch("runner.runner.download",
                   side_effect=JobRejected("download exceeded 104857600 bytes")):
            imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("download exceeded", r["stderr"])
        self.assertIn(jid, seen)
        self.assertIn("1", imap.flagged)

    def test_bad_scheme_is_poison(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo hi",
                     files=[{"name": "x.bin", "url": "file:///etc/passwd"}])
        imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("unsupported url scheme", r["stderr"])
        self.assertIn(jid, seen)

    def test_nxdomain_is_poison(self):
        from urllib.error import URLError
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec",
                     script_url="https://no-such-host.invalid/s")
        with patch("runner.runner.urlopen",
                   side_effect=URLError("Name or service not known")):
            imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("does not resolve", r["stderr"])
        self.assertIn(jid, seen)

    def test_http_404_is_poison(self):
        from urllib.error import HTTPError
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec",
                     script_url="https://example.com/missing")
        with patch("runner.runner.urlopen",
                   side_effect=HTTPError("https://example.com/missing", 404, "missing", {}, None)):
            imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], -2)
        self.assertIn("404", r["stderr"])
        self.assertIn(jid, seen)

    def test_work_dir_cleaned_between_runs(self):
        jid = str(uuid.uuid4())
        base = self.tmp
        work = os.path.join(base, "work", jid)
        os.makedirs(work)
        fh = open(os.path.join(work, "leftover"), "w"); fh.write("stale"); fh.close()
        p = base_job(jid, kind="exec", script="ls")
        imap, smtp, seen = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["exit_code"], 0)
        self.assertNotIn("leftover", r["stdout"])

    def test_seen_dict_trimmed_in_memory(self):
        seen = {f"old-{i}": True for i in range(SEEN_CAP + 5)}
        jid = str(uuid.uuid4())
        _, _, seen = self.cycle([job_email(base_job(jid))], seen=seen)
        self.assertLessEqual(len(seen), SEEN_CAP)
        self.assertIn(jid, seen)  # newest entry survives the trim

    def test_fetch_search_uses_broad_tag(self):
        # Decorated subjects ("[HOMING-PIGEON] TEST job <id>") do not
        # contain the exact "[HOMING-PIGEON] job" substring, so the
        # search must use the broad tag and let handle_mail filter.
        imap = FakeIMAP([])
        searches = []
        orig_search = imap.search
        imap.search = lambda *a: (searches.append(a), orig_search(*a))[1]
        fetch_job_mails(imap)
        joined = " ".join(" ".join(str(x) for x in a) for a in searches)
        self.assertIn("[HOMING-PIGEON]", joined)
        self.assertNotIn("[HOMING-PIGEON] job", joined)

    def test_decorated_subject_executes(self):
        jid = str(uuid.uuid4())
        raw = job_email(base_job(jid, kind="ping"))
        raw = raw.replace(b"[HOMING-PIGEON] job ",
                          b"[HOMING-PIGEON] TEST job ")
        imap, smtp, seen = self.cycle([raw])
        self.assertEqual(len(smtp.sent), 1)
        r = verify_body(smtp.sent[0].get_content(), SECRET)
        self.assertEqual(r["stdout"], "pong")
        self.assertIn(jid, seen)

    def test_result_subject_ignored_and_seen(self):
        # Result mails now match the broad search; they must be
        # ignored (not executed), just marked seen.
        jid = str(uuid.uuid4())
        raw = job_email(base_job(jid, kind="ping"))
        raw = raw.replace(b"[HOMING-PIGEON] job ",
                          b"[HOMING-PIGEON] result ")
        imap, smtp, seen = self.cycle([raw])
        self.assertEqual(len(smtp.sent), 0)
        self.assertIn("1", imap.flagged)
        self.assertNotIn(jid, seen)

    def test_dry_run_verifies_but_changes_nothing(self):
        import types
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo hi")
        opts = types.SimpleNamespace(dry_run=True, no_send=False)
        imap, smtp, seen = self.cycle([job_email(p)], opts=opts)
        self.assertEqual(len(smtp.sent), 0)   # nothing sent
        self.assertEqual(seen, {})            # nothing recorded
        self.assertEqual(imap.flagged, [])    # nothing marked seen
        # ...but the signature was verified (a bad sig would reject).
        # No work dir means nothing executed.
        self.assertFalse(os.path.isdir(os.path.join(self.tmp, "work", jid)))

    def test_dry_run_rejects_without_mutation(self):
        import types
        jid = str(uuid.uuid4())
        p = base_job(jid)
        raw = job_email(p).replace(b'"sig":"', b'"sig":"0')
        opts = types.SimpleNamespace(dry_run=True, no_send=False)
        imap, smtp, seen = self.cycle([raw], opts=opts)
        # Rejected, but dry-run changes nothing: mail left unseen.
        self.assertEqual(imap.flagged, [])
        self.assertEqual(seen, {})

    def test_no_send_executes_without_email(self):
        import types
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo hi")
        opts = types.SimpleNamespace(dry_run=False, no_send=True)
        imap, smtp, seen = self.cycle([job_email(p)], opts=opts)
        self.assertEqual(len(smtp.sent), 0)   # executed, not emailed
        self.assertIn(jid, seen)              # processed normally
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "work", jid)))

    def test_concurrent_two_jobs(self):
        import types
        jids = [str(uuid.uuid4()) for _ in range(2)]
        mails = [job_email(base_job(j, kind="ping")) for j in jids]
        opts = types.SimpleNamespace(dry_run=False, no_send=False, workers=2)
        imap, smtp, seen = self.cycle(mails, opts=opts)
        self.assertEqual(len(smtp.sent), 2)
        for j in jids:
            self.assertIn(j, seen)

    def test_duplicate_job_id_executes_once(self):
        # Same job_id delivered twice in one cycle: the in-flight claim
        # must prevent double execution, whichever thread wins.
        import types
        jid = str(uuid.uuid4())
        mails = [job_email(base_job(jid, kind="ping")) for _ in range(2)]
        opts = types.SimpleNamespace(dry_run=False, no_send=False, workers=4)
        imap, smtp, seen = self.cycle(mails, opts=opts)
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid, seen)
        self.assertEqual(sorted(imap.flagged), ["1", "2"])

    def test_worker_count_resolution(self):
        import types
        # CLI beats config; garbage falls back to 1; default is 1.
        self.assertEqual(_worker_count({}, None), 1)
        self.assertEqual(_worker_count({"workers": 3}, None), 3)
        self.assertEqual(_worker_count({"workers": "bogus"}, None), 1)
        opts = types.SimpleNamespace(workers=5)
        self.assertEqual(_worker_count({"workers": 3}, opts), 5)
        opts = types.SimpleNamespace(workers=None)
        self.assertEqual(_worker_count({"workers": 3}, opts), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class OAuthAuthTests(unittest.TestCase):
    def test_xoauth2_string_shape(self):
        from runner.oauth import xoauth2_raw
        raw = xoauth2_raw("a@b.com", "ya29.token")
        self.assertEqual(
            raw,
            "user=a@b.com\x01auth=Bearer ya29.token\x01\x01",
        )
        # The wire form is this string, base64'd once. Not twice.
        import base64
        blob = base64.b64encode(raw.encode("ascii"))
        self.assertTrue(blob.startswith(b"dXNlcj"))

    def test_password_auth_is_the_default(self):
        from runner.runner import _use_oauth
        self.assertFalse(_use_oauth({}))
        self.assertFalse(_use_oauth({"auth": "password"}))
        self.assertTrue(_use_oauth({"auth": "oauth"}))
        self.assertTrue(_use_oauth({"auth": "OAuth"}))


class ScriptNameTests(unittest.TestCase):
    def test_script_filename(self):
        from runner.runner import script_filename
        self.assertEqual(
            script_filename(["powershell", "-File"]), "script.ps1")
        self.assertEqual(
            script_filename(["pwsh", "-NoProfile", "-File"]), "script.ps1")
        self.assertEqual(script_filename(["python3"]), "script.py")
        self.assertEqual(script_filename(["sh"]), "script")


class OAuthRefreshErrorTests(unittest.TestCase):
    def test_refresh_rejection_raises_distinct_error(self):
        import io
        import urllib.error
        from unittest import mock
        from runner.oauth import refresh_access_token, OAuthRefreshError

        err_body = json.dumps({"error": "invalid_grant",
                               "error_description": "Token has been revoked"}).encode()
        http_err = urllib.error.HTTPError(
            "https://oauth2.googleapis.com/token", 400, "Bad Request",
            {}, io.BytesIO(err_body))
        cfg = {"oauth_client_id": "x", "oauth_client_secret": "y",
               "oauth_refresh_token": "dead"}
        with mock.patch("urllib.request.urlopen", side_effect=http_err):
            with self.assertRaises(OAuthRefreshError) as cm:
                refresh_access_token(cfg)
        self.assertIn("invalid_grant", str(cm.exception))
        self.assertIn("browser login", str(cm.exception))

    def test_refresh_error_is_a_runtime_error(self):
        from runner.oauth import OAuthRefreshError
        self.assertTrue(issubclass(OAuthRefreshError, RuntimeError))


class WinlogTests(unittest.TestCase):
    def test_report_event_is_noop_off_windows(self):
        # We're on Linux here; must not raise and must do nothing.
        from runner import winlog
        self.assertFalse(winlog._reported_ok)
        winlog.report_event("test message")  # must not raise
        winlog.report_event("test message", level="WARN")
        self.assertFalse(winlog._reported_ok)  # still untouched

    def test_report_event_never_raises(self):
        # Even if ctypes/winreg blow up, the runner must survive.
        import sys
        from unittest import mock
        from runner import winlog
        with mock.patch.dict(sys.modules, {"ctypes": None}):
            winlog.report_event("test")  # must not raise


class HotReloadTests(unittest.TestCase):
    def _cfg(self, **over):
        base = {
            "poll_interval_sec": 20,
            "workers": 1,
            "default_timeout_sec": 300,
            "max_output_bytes": 100000,
            "max_job_age_sec": 3600,
            "mailbox_password": "secret",
        }
        base.update(over)
        return base

    def _write(self, path, cfg, mtime):
        import json
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        os.utime(path, (mtime, mtime))

    def test_no_change_when_mtime_same(self):
        from runner.runner import reload_hot_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            cfg = self._cfg()
            self._write(path, cfg, 1000)
            state = {"mtime": 1000}
            self.assertEqual(reload_hot_config(cfg, path, state), [])
            self.assertEqual(cfg["poll_interval_sec"], 20)

    def test_applies_hot_keys(self):
        from runner.runner import reload_hot_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            cfg = self._cfg()
            self._write(path, self._cfg(poll_interval_sec=5, workers=4), 2000)
            state = {"mtime": 1000}
            changed = reload_hot_config(cfg, path, state)
            self.assertEqual(changed, ["poll_interval_sec", "workers"])
            self.assertEqual(cfg["poll_interval_sec"], 5)
            self.assertEqual(cfg["workers"], 4)
            self.assertEqual(state["mtime"], 2000)

    def test_does_not_touch_credentials(self):
        from runner.runner import reload_hot_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            cfg = self._cfg()
            fresh = self._cfg(mailbox_password="stolen",
                              oauth_refresh_token="nope")
            self._write(path, fresh, 2000)
            state = {"mtime": 1000}
            self.assertEqual(reload_hot_config(cfg, path, state), [])
            self.assertEqual(cfg["mailbox_password"], "secret")
            self.assertNotIn("oauth_refresh_token", cfg)

    def test_bad_file_does_not_advance_mtime(self):
        from runner.runner import reload_hot_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            cfg = self._cfg()
            with open(path, "w") as fh:
                fh.write("{not json")
            os.utime(path, (2000, 2000))
            state = {"mtime": 1000}
            with self.assertRaises(Exception):
                reload_hot_config(cfg, path, state)
            self.assertEqual(state["mtime"], 1000)
            self.assertEqual(cfg["poll_interval_sec"], 20)
            # A later good write with a new mtime still applies.
            self._write(path, self._cfg(poll_interval_sec=9), 3000)
            changed = reload_hot_config(cfg, path, state)
            self.assertEqual(changed, ["poll_interval_sec"])
            self.assertEqual(cfg["poll_interval_sec"], 9)

    def test_pinned_cli_keys_are_not_overwritten(self):
        from runner.runner import reload_hot_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            cfg = self._cfg(poll_interval_sec=5)  # CLI said 5
            self._write(path, self._cfg(poll_interval_sec=99, workers=3), 2000)
            state = {"mtime": 1000}
            changed = reload_hot_config(
                cfg, path, state, pinned={"poll_interval_sec"})
            self.assertEqual(changed, ["workers"])
            self.assertEqual(cfg["poll_interval_sec"], 5)
            self.assertEqual(cfg["workers"], 3)

    def test_invalid_values_are_rejected(self):
        from runner.runner import reload_hot_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            cfg = self._cfg()
            fresh = self._cfg(poll_interval_sec=-1, workers=0,
                              max_output_bytes="lots",
                              default_timeout_sec=30)
            self._write(path, fresh, 2000)
            state = {"mtime": 1000}
            changed = reload_hot_config(cfg, path, state)
            self.assertEqual(changed, ["default_timeout_sec"])
            self.assertEqual(cfg["poll_interval_sec"], 20)
            self.assertEqual(cfg["workers"], 1)
            self.assertEqual(cfg["max_output_bytes"], 100000)
            self.assertEqual(cfg["default_timeout_sec"], 30)
            # mtime still advances: the file was readable, bad keys skipped
            self.assertEqual(state["mtime"], 2000)


class UnderDashboardTests(unittest.TestCase):
    def test_rate_limit_persists(self):
        from runner.runner import check_rate_limit, budget_status
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "query_times.json")
            cfg = {"max_queries_per_hour": 2}
            self.assertTrue(check_rate_limit("k", cfg, path))
            self.assertTrue(check_rate_limit("k", cfg, path))
            self.assertFalse(check_rate_limit("k", cfg, path))
            status = budget_status(path, cfg)
            self.assertEqual(status[0]["spent"], 2)
            self.assertEqual(status[0]["limit"], 2)
            # a new process sees the same window
            self.assertFalse(check_rate_limit("k", cfg, path))

    def test_inspect_redact(self):
        from runner.runner import run_inspect
        cfg = {"redact_patterns_extra": {"aws": "AKIA[0-9A-Z]{16}"}}
        class A:
            inspect = "redact"
            job_id = None
        import io
        old = sys.stdin
        sys.stdin = io.StringIO("key AKIAIOSFODNN7EXAMPLE end")
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = run_inspect(cfg, A())
        finally:
            sys.stdin = old
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertIn("aws_key", out["families"])
        self.assertIn("[REDACTED:aws_key]", out["redacted"])

    def test_inspect_board_and_job(self):
        from runner.runner import run_inspect, save_retained
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d}
            class A:
                inspect = "board"
                job_id = None
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_inspect(cfg, A()), 0)
            self.assertEqual(json.loads(buf.getvalue())["counts"]["open"], 0)
            save_retained(d, "job-1", {"job_id": "job-1", "judgment":
                                       {"verdict": "ok", "reasons": []}})
            A.inspect = "job"
            A.job_id = "job-1"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(run_inspect(cfg, A()), 0)
            self.assertEqual(json.loads(buf.getvalue())["judgment"]["verdict"],
                             "ok")
