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

SECRET = "edge-test-secret"
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
            "imap_host": "fake", "imap_port": 993,
            "smtp_host": "fake", "smtp_port": 587,
            "max_job_age_sec": 3600,
            "max_output_bytes": 40,
            "default_timeout_sec": 300,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, cfg=None, seen=None):
        cfg = cfg or self.cfg
        seen = {} if seen is None else seen
        imap, smtp = FakeIMAP(mails), FakeSMTP()
        poll_once(cfg, self.tmp, seen, self.seen_path, imap=imap, smtp=smtp)
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

    def test_allowed_sender_override_accepts(self):
        jid = str(uuid.uuid4())
        cfg = dict(self.cfg, allowed_sender="other@example.com")
        _, smtp, seen = self.cycle(
            [job_email(base_job(jid), sender="other@example.com")], cfg=cfg)
        self.assertEqual(len(smtp.sent), 1)
        self.assertIn(jid, seen)

    def test_allowed_sender_override_rejects_mailbox(self):
        jid = str(uuid.uuid4())
        cfg = dict(self.cfg, allowed_sender="other@example.com")
        _, smtp, _ = self.cycle([job_email(base_job(jid))], cfg=cfg)
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
            open(os.path.join(src, "config.example.json"), "w").write("{}\n")
            with patch.object(install_mod, "FROZEN", False):
                install_mod.install_files(src, dst)
            self.assertTrue(os.path.exists(os.path.join(dst, "runner.py")))

    def test_macos_plist_escapes_xml_metachars(self):
        import plistlib
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "a&b<c")
            os.makedirs(dst)
            la = os.path.join(tmp, "LA")
            with patch.object(install_mod, "run", lambda *a, **k: None):
                with patch("os.path.expanduser",
                           lambda p: p.replace("~/Library/LaunchAgents", la)):
                    install_mod.install_macos(dst, os.path.join(dst, "config.json"))
            with open(os.path.join(la, "com.homing-pigeon.runner.plist"),
                      "rb") as fh:
                pl = plistlib.load(fh)  # raises on malformed XML
            self.assertEqual(pl["ProgramArguments"][-1],
                             os.path.join(dst, "config.json"))

    def test_linux_unit_quotes_spaced_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "my dir")
            udir = os.path.join(tmp, "systemd")
            with patch.object(install_mod, "run", lambda *a, **k: None):
                with patch("os.path.expanduser", lambda p: udir):
                    install_mod.install_linux(dst, os.path.join(dst, "config.json"),
                                              system=False)
            with open(os.path.join(udir, "homing-pigeon.service")) as fh:
                unit = fh.read()
            self.assertIn("'%s/runner.py'" % dst, unit)
            self.assertIn("--config '%s/config.json'" % dst, unit)


class InfiniteRetryBugs(unittest.TestCase):
    """Lock in the two bugs that previously caused permanent retries."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-retry-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
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
            "max_job_age_sec": 3600,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails, seen=None):
        imap, smtp = FakeIMAP(mails), FakeSMTP()
        seen = {} if seen is None else seen
        poll_once(self.cfg, self.tmp, seen, self.seen_path,
                  imap=imap, smtp=smtp)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
