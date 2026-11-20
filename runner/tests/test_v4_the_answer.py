#!/usr/bin/env python3
"""A mail the library cannot follow is decided once.

docs/infrastructure-documents/proofs/v4-the-ladder.md, finding
F15, the change J2. A deep address is for the log only, so the
job goes on. A shape the library cannot follow is marked, or
left where it is when the box is already stopped. No new row
in the constraint inventory.
"""
import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner as RUNNER  # noqa: E402
from runner.ops import mail as MAIL  # noqa: E402
from runner.tests import test_proof_conformance as DOOR  # noqa: E402
from runner.tests import test_v4_at_a_bound as BOUND  # noqa: E402
from runner.tests import test_v4_before_the_mac as PRE  # noqa: E402
from runner.tests import test_v4_bindings as BIND  # noqa: E402
from runner.tests import test_v4_models as MODELS  # noqa: E402
from runner.tests import test_v4_the_folder as FOLDER  # noqa: E402

PAGE = os.path.join(MODELS.PROOFS, "v4-the-ladder.md")


def nested(depth):
    """A mail of `depth` parts inside parts. The library raises
    on this interpreter once depth passes about 980."""
    lines = ["From: a@b.c", "Subject: plain", "MIME-Version: 1.0",
             "Content-Type: multipart/mixed; boundary=b0", ""]
    for index in range(depth):
        lines.append("--b%d" % index)
        lines.append("Content-Type: multipart/mixed; boundary=b%d"
                     % (index + 1))
        lines.append("")
    lines.append("--b%d" % depth)
    lines.append("")
    lines.append("hi")
    lines.append("--b%d--" % depth)
    for index in range(depth - 1, -1, -1):
        lines.append("--b%d--" % index)
    return "\r\n".join(lines).encode("ascii")


class _Box:
    def __init__(self):
        self.marked = []

    def store(self, seq, *_args):
        self.marked.append(seq)
        return "OK", None


def once(raw, folder, sender_job=False):
    """One arrival. (whether a job ran, the log lines, the seqs
    marked)."""
    notes, sent = [], []
    box = _Box()
    cfg = {"mailbox_user": "t@example.com", "base_dir": folder,
           "oracle_opinion_mode": "off"}
    cfg.update(BIND.KEYS)
    RUNNER._set_allow_cleartext_jobs(True)
    try:
        with mock.patch.object(
                RUNNER, "send_mail",
                lambda _smtp, _cfg, subject, body, to=None: sent.append(body)), \
            mock.patch.object(
                RUNNER, "log",
                lambda msg, level="INFO": notes.append(msg)), \
                contextlib.redirect_stdout(io.StringIO()):
            RUNNER.handle_mail(
                cfg, box, DOOR._SMTP2(), 7, raw, folder, {},
                RUNNER.build_secrets(cfg),
                Namespace(dry_run=False, no_send=False), None)
    finally:
        RUNNER._set_allow_cleartext_jobs(False)
    ran = False
    if sent:
        ran = json.loads(sent[0]).get("exit_code") == 0
    return ran, notes, box.marked


class TheAnswer(unittest.TestCase):
    """J2, on this interpreter."""

    @classmethod
    def setUpClass(cls):
        cls.payload, cls.job_id = BOUND.honest_job()

    def job(self, sender):
        job = copy.deepcopy(self.payload)
        job["script"] = "true"
        job["interpreter"] = ["bash"]
        job.pop("shell", None)
        return PRE._mail(PRE._subject(self.job_id), BIND._signed(job),
                         sender=sender)

    def test_the_bars_are_below_the_raise_and_above_a_real_address(self):
        self.assertFalse(MAIL._sender_is_deep("Ada <ada@example.com>"))
        self.assertFalse(MAIL._sender_is_deep("a:" * 64 + "a"))
        self.assertTrue(MAIL._sender_is_deep("a:" * 65 + "a"))
        self.assertFalse(MAIL._sender_is_deep("a " + "()" * 8 + " <a@b.c>"))
        # 9 nested comments, not 8 side by side.
        deep = "a " + ("(" * 9) + (")" * 9) + " <a@b.c>"
        self.assertTrue(MAIL._sender_is_deep(deep))
        self.assertEqual(64, MAIL.ADDRESS_COLON_BAR)
        self.assertEqual(8, MAIL.COMMENT_DEPTH_BAR)

    def test_a_deep_address_runs_and_the_log_says_so(self):
        raw = self.job("a:" * 1200 + "a")
        with tempfile.TemporaryDirectory() as folder:
            ran, notes, marked = once(raw, folder)
        # The job runs where the sandbox engages. Where it does
        # not, the runner under enforce answers with a signed
        # refusal. The address is unread and the mail is marked
        # either way.
        self.assertEqual(FOLDER.ENGAGES, ran)
        self.assertTrue(any("sender could not be read" in note
                            for note in notes), notes)
        self.assertEqual([7], marked)

    def test_a_shape_that_raises_is_marked_and_not_run(self):
        raw = nested(1000)
        with tempfile.TemporaryDirectory() as folder:
            ran, notes, marked = once(raw, folder)
        self.assertFalse(ran)
        self.assertEqual(
            ["seq 7: the mail's shape could not be read"], notes)
        self.assertEqual([7], marked)

    def test_a_stopped_box_leaves_the_unreadable_mail(self):
        raw = nested(1000)
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(RUNNER._panic, "fired",
                                   lambda _base: True):
                ran, notes, marked = once(raw, folder)
        self.assertFalse(ran)
        self.assertEqual([], notes)
        self.assertEqual([], marked)

    def test_five_polls_fetch_the_deep_mail_once(self):
        raw = self.job("a:" * 1200 + "a")
        marked = set()
        box = _Box()

        def store(seq, *_args):
            box.marked.append(seq)
            marked.add(seq)
            return "OK", None

        box.store = store
        fetches = 0
        with tempfile.TemporaryDirectory() as folder:
            cfg = {"mailbox_user": "t@example.com", "base_dir": folder,
                   "oracle_opinion_mode": "off"}
            cfg.update(BIND.KEYS)
            RUNNER._set_allow_cleartext_jobs(True)
            try:
                for _poll in range(5):
                    if 2 in marked:
                        continue
                    fetches += 1
                    sent = []
                    with mock.patch.object(
                            RUNNER, "send_mail",
                            lambda _s, _c, subject, body, to=None:
                            sent.append(body)), \
                        mock.patch.object(RUNNER, "log",
                                          lambda msg, level="INFO": None), \
                            contextlib.redirect_stdout(io.StringIO()):
                        RUNNER.handle_mail(
                            cfg, box, DOOR._SMTP2(), 2, raw, folder, {},
                            RUNNER.build_secrets(cfg),
                            Namespace(dry_run=False, no_send=False), None)
                    self.assertTrue(sent)
            finally:
                RUNNER._set_allow_cleartext_jobs(False)
        self.assertEqual(1, fetches)
        self.assertEqual([2], box.marked)

    def test_the_page_records_the_answer(self):
        with open(PAGE, encoding="utf-8") as handle:
            page = " ".join(handle.read().split())
        for stated in (
                "J2 was run.",
                "64 colons, or 8 comments deep",
                "marks the message and returns",
                "No new row in the constraint inventory."):
            self.assertIn(stated, page, stated)


if __name__ == "__main__":
    unittest.main()
