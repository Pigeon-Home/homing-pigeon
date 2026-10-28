"""first_ping times the README's first prompt and keeps every batch.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""
import email
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from email.message import EmailMessage
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "cloud"))

from runner.tools import first_ping as fp  # noqa: E402
import send_job  # noqa: E402


class SummaryAndTableTest(unittest.TestCase):
    def test_summary(self):
        self.assertEqual(fp.summarize([]), {"p50_s": None, "p95_s": None,
                                            "max_s": None})
        s = fp.summarize([0.3, 0.1, 0.2, 0.4, 10.0])
        self.assertEqual(s["p50_s"], 0.3)
        self.assertEqual(s["max_s"], 10.0)
        self.assertEqual(s["p95_s"], 10.0)

    def test_record_writes_a_header_once_and_rebuilds_the_table(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(fp.load(td), [])
            row = {"when": "w", "mode": "bench", "provider": "in-memory",
                   "kind": "ping", "runs": 2, "ok": 2, "p50_s": 0.01,
                   "p95_s": None, "max_s": 0.02, "version": "v",
                   "platform": "box"}
            fp.record(row, td)
            fp.record(dict(row, kind="exec"), td)
            with open(os.path.join(td, "runs.jsonl")) as fh:
                lines = [json.loads(l) for l in fh]
            self.assertEqual(lines[0]["first_ping"], 1)
            self.assertEqual(len(lines), 3)
            self.assertEqual([r["kind"] for r in fp.load(td)], ["ping", "exec"])
            with open(os.path.join(td, "README.md")) as fh:
                text = fh.read()
            self.assertIn("| w | bench | in-memory | exec | 2 | 2 | 0.010 |  | 0.020 |", text)
            self.assertIn(fp.STAMP, text)

    def test_the_committed_table_matches_its_runs(self):
        rows = fp.load()
        self.assertTrue(rows, "docs/reports/first-ping/runs.jsonl has rows")
        with open(os.path.join(fp.OUT_DIR, "README.md")) as fh:
            text = fh.read()
        for r in rows:
            self.assertIn(f"| {r['when']} | {r['mode']} |", text)


class BenchTest(unittest.TestCase):
    def test_both_kinds_come_back_verified(self):
        rows = fp.bench(2)
        self.assertEqual([r["kind"] for r in rows], ["ping", "exec"])
        for r in rows:
            self.assertEqual(r["ok"], 2, r)
            self.assertLess(r["max_s"], 30)

    def test_a_result_that_does_not_open_is_not_ok(self):
        self.assertFalse(fp._result_ok("nonsense", "s" * 40, "j", "ping",
                                       send_job))

    def test_main_bench_no_record(self):
        out = io.StringIO()
        with mock.patch.object(fp, "record") as rec, redirect_stdout(out):
            rc = fp.main(["bench", "--runs", "1", "--no-record"])
        self.assertEqual(rc, 0)
        rec.assert_not_called()
        self.assertEqual(len(out.getvalue().splitlines()), 2)

    def test_main_table(self):
        with mock.patch.object(fp, "write_table") as wt:
            self.assertEqual(fp.main(["table"]), 0)
        wt.assert_called_once_with()


class _IMAP:
    """Serves the result the runner would have sent, after one empty poll."""

    def __init__(self, body, jid):
        self.body, self.jid, self.polls = body, jid, 0

    def login(self, *_):
        return ("OK", [])

    def noop(self):
        return ("OK", [])

    def select(self, *_):
        return ("OK", [])

    def search(self, _charset, _key, value):
        self.polls += 1
        return ("OK", [b"1" if self.polls > 1 else b""])

    def fetch(self, num, _spec):
        msg = EmailMessage()
        msg["Subject"] = f"[HOMING-PIGEON] result {self.jid}"
        msg.set_content(self.body)
        return ("OK", [(b"1 (RFC822", msg.as_bytes()), b")"])

    def logout(self):
        raise OSError("gone")


class LiveTest(unittest.TestCase):
    ARGS = ["live", "--runner-email", "runner@example.test",
            "--user", "si@example.test", "--imap-host", "imap.example.test",
            "--smtp-host", "smtp.example.test", "--runs", "1",
            "--no-record", "--provider", "example"]

    def test_needs_both_env_values(self):
        err = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), redirect_stderr(err):
            self.assertEqual(fp.main(self.ARGS), 2)
        self.assertIn("HP_SI_PASSWORD", err.getvalue())

    def _run(self, imap_factory):
        sent = []

        class SMTP:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def starttls(self):
                pass

            def login(self, *a):
                pass

            def send_message(self, msg):
                sent.append(msg)

        out, err = io.StringIO(), io.StringIO()
        env = {"HP_SI_PASSWORD": "pw", "HP_SECRET": "fp-" + "ab12" * 12}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(fp.smtplib, "SMTP", SMTP), \
                mock.patch.object(fp.imaplib, "IMAP4_SSL",
                                  side_effect=lambda *a: imap_factory(sent)), \
                mock.patch.object(fp.time, "sleep"), \
                redirect_stdout(out), redirect_stderr(err):
            rc = fp.main(self.ARGS + ["--timeout", "5"])
        return rc, sent, [json.loads(l) for l in out.getvalue().splitlines()]

    def test_a_signed_result_round_trips(self):
        secret = "fp-" + "ab12" * 12

        class Lazy(_IMAP):
            def __init__(self, sent):
                super().__init__("", "")
                self.sent = sent

            def search(self, *a):
                job = self.sent[-1]
                self.jid = job["Subject"].split()[-1]
                payload = {"v": 1, "type": "result", "job_id": self.jid,
                           "kind": "exec", "exit_code": 0}
                self.body = send_job.sign_payload(payload, secret)
                return super().search(*a)

        rc, sent, rows = self._run(Lazy)
        self.assertEqual(rc, 0)
        self.assertEqual(sent[0]["To"], "runner@example.test")
        self.assertIn("[HOMING-PIGEON] job ", sent[0]["Subject"])
        self.assertEqual(rows[0]["ok"], 1)
        self.assertEqual(rows[0]["provider"], "example")

    def test_no_result_in_time_is_a_miss(self):
        class Empty(_IMAP):
            def __init__(self, sent):
                super().__init__("", "")

            def search(self, *a):
                return ("OK", [b""])

        with mock.patch.object(fp.time, "monotonic",
                               side_effect=[0.0, 0.0, 99.0, 99.0]):
            rc, _, rows = self._run(Empty)
        self.assertEqual(rc, 1)
        self.assertEqual(rows[0]["ok"], 0)
        self.assertIsNone(rows[0]["p50_s"])

    def test_text_body_of_a_multipart_reply(self):
        msg = EmailMessage()
        msg.set_content("signed body")
        msg.add_alternative("<p>html</p>", subtype="html")
        self.assertEqual(fp._text_body(msg).strip(), "signed body")
        bare = email.message_from_string(
            "Content-Type: multipart/mixed; boundary=b\n\n--b\n"
            "Content-Type: text/html\n\nx\n--b--\n")
        self.assertEqual(fp._text_body(bare), "")

    def test_verify_refuses_a_bad_body(self):
        self.assertIsNone(fp._verify("not signed", "fp-" + "ab12" * 12, "j"))


if __name__ == "__main__":
    unittest.main()
