#!/usr/bin/env python3
"""Email transport message identity: IMAP UIDs, not sequence numbers.

The bug this family pins: the email pipe keyed its delivered/done
bookkeeping on the IMAP message sequence number (ident "mail-<seq>").
A sequence number is only a position in the mailbox today. When the
mailbox churns -- a carried message is expunged, a new one arrives --
positions shift and a sequence number gets reused by a DIFFERENT
message. The pipe then sees the new message under an ident whose
done-file already exists, marks it seen, and never delivers it: a
job silently dropped, no journal line, no result.

The fix keys identity on the IMAP UID, which the server assigns
once and never reuses for another message in the mailbox: fetch
returns "u<uid>" tokens, the channel ident becomes "mail-u<uid>",
and mark-seen stores by UID. A seq-only fake (no uid method) keeps
the old sequence behaviour as a fallback so the existing harness
fakes keep working.
"""
import os
import sys
import tempfile
import unittest
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.tests.test_runner import FakeIMAP, FakeSMTP  # noqa: E402
from runner.transport_extensions.email import (  # noqa: E402
    __main__ as email_ext)
from runner.wire import mailbox, transports  # noqa: E402

CFG = {"mailbox_user": "runner-box@example.com",
       "poll_interval_sec": 1}


def _raw(job_id):
    head = (f"Subject: [HOMING-PIGEON] job {job_id}\r\n"
            "From: someone@example.com\r\n"
            'Content-Type: text/plain; charset="utf-8"\r\n'
            "\r\n")
    return head.encode() + b"signed-body-" + job_id.encode()


class UidIMAP:
    """A UID-capable fake mailbox that models sequence reuse.

    Messages carry a permanent UID and a seen flag. Their sequence
    number is just their current position (index + 1), so expunging
    an earlier message renumbers every message after it -- exactly
    the churn that broke the seq-keyed pipe.
    """

    def __init__(self, mails=()):
        self.messages = []       # [{uid, raw, seen}]
        for uid, raw in mails:
            self.add(uid, raw)
        self.uid_stored = []     # uids passed to UID STORE
        self.seq_stored = []     # seqs passed to plain STORE
        self.uid_fetches = []
        self.seq_fetches = []

    def add(self, uid, raw):
        self.messages.append({"uid": uid, "raw": raw, "seen": False})

    def expunge(self, uid):
        self.messages = [m for m in self.messages
                         if m["uid"] != uid]

    # -- UID commands -------------------------------------------------
    def uid(self, command, *args):
        cmd = command.upper()
        if cmd == "SEARCH":
            nums = b" ".join(str(m["uid"]).encode()
                             for m in self.messages if not m["seen"])
            return ("OK", [nums])
        if cmd == "FETCH":
            uid = int(args[0])
            self.uid_fetches.append(uid)
            for m in self.messages:
                if m["uid"] == uid:
                    raw = m["raw"]
                    head = f"{uid} (UID {uid} RFC822 {{{len(raw)}}}" \
                        .encode()
                    return ("OK", [(head, raw), b")"])
            return ("OK", [])
        if cmd == "STORE":
            uid = str(args[0])
            self.uid_stored.append(uid)
            for m in self.messages:
                if m["uid"] == int(uid):
                    m["seen"] = True
            return ("OK", [])
        raise AssertionError(f"unexpected UID command {command}")

    # -- sequence commands (the fallback path) ------------------------
    def search(self, *args):
        nums = b" ".join(str(i + 1).encode()
                         for i, m in enumerate(self.messages)
                         if not m["seen"])
        return ("OK", [nums])

    def fetch(self, num, _spec):
        seq = int(num)
        self.seq_fetches.append(seq)
        m = self.messages[seq - 1]
        raw = m["raw"]
        head = f"{seq} (RFC822 {{{len(raw)}}})".encode()
        return ("OK", [(head, raw), b")"])

    def store(self, seq, _op, _flags):
        self.seq_stored.append(str(seq))
        self.messages[int(seq) - 1]["seen"] = True
        return ("OK", [])

    def logout(self):
        return ("OK", [])


class FetchIdentityTest(unittest.TestCase):
    def test_fetch_returns_uid_tokens_not_sequence_numbers(self):
        imap = UidIMAP([(101, _raw("a")), (102, _raw("b"))])
        mails = mailbox.fetch_job_mails(imap)
        self.assertEqual([t for t, _raw_ in mails], ["u101", "u102"])
        self.assertEqual(imap.uid_fetches, [101, 102])
        self.assertEqual(imap.seq_fetches, [])

    def test_a_message_keeps_its_token_when_positions_shift(self):
        imap = UidIMAP([(101, _raw("a")), (102, _raw("b"))])
        first = dict(mailbox.fetch_job_mails(imap))
        imap.expunge(101)          # b was seq 2, is now seq 1
        second = dict(mailbox.fetch_job_mails(imap))
        self.assertEqual(list(second), ["u102"])
        self.assertEqual(second["u102"], first["u102"])

    def test_a_new_message_never_inherits_a_carried_messages_token(
            self):
        imap = UidIMAP([(101, _raw("a")), (102, _raw("b"))])
        before = dict(mailbox.fetch_job_mails(imap))
        imap.expunge(101)
        imap.add(103, _raw("c"))   # c takes seq 2 -- b's old position
        after = dict(mailbox.fetch_job_mails(imap))
        self.assertIn("u103", after)
        self.assertNotEqual(after["u103"], before["u102"])
        self.assertEqual(set(after), {"u102", "u103"})

    def test_mark_seen_by_uid_token_stores_the_uid(self):
        imap = UidIMAP([(101, _raw("a")), (102, _raw("b"))])
        imap.expunge(101)          # b is seq 1 now; seq 1 is not b's id
        mailbox.mark_seen(imap, "u102")
        self.assertEqual(imap.uid_stored, ["102"])
        self.assertEqual(imap.seq_stored, [])
        self.assertTrue(imap.messages[0]["seen"])

    def test_seq_only_fake_still_uses_sequence_numbers(self):
        imap = FakeIMAP([_raw("a"), _raw("b")])
        mails = mailbox.fetch_job_mails(imap)
        self.assertEqual([t for t, _r in mails], ["1", "2"])
        mailbox.mark_seen(imap, "2")
        self.assertEqual(imap.flagged, ["2"])


class PipeIdentityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-uid-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.paths = transports.channel_paths(self.tmp, "email")
        transports.ensure_channel_dirs(self.tmp, "email")
        self.channel = self.paths["root"]

    def _pipe(self, imap):
        return email_ext.EmailPipe(
            CFG, self.channel,
            imap_factory=lambda cfg: imap,
            smtp_factory=lambda cfg: FakeSMTP())

    def test_pipe_delivers_under_uid_idents(self):
        imap = UidIMAP([(101, _raw("a"))])
        self._pipe(imap).pass_once()
        inbox = os.listdir(os.path.join(self.channel, "inbox"))
        self.assertIn("mail-u101.job.txt", inbox)

    def test_seq_reuse_does_not_drop_the_new_job(self):
        # Pass 1: job A (uid 101, seq 1) is delivered and carried;
        # the core's done-file for it exists.
        imap = UidIMAP([(101, _raw("a"))])
        self._pipe(imap).pass_once()
        done_dir = os.path.join(self.channel, "inbox", "done")
        with open(os.path.join(done_dir, "mail-u101.job.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write("carried")
        # A leaves the mailbox (seen + expunged). Job C arrives and
        # takes seq 1 -- the very position A held. Under seq keying
        # C's ident would be mail-1, whose done-file (as mail-u101's
        # seq twin) already proved a carry, and C would be marked
        # seen and dropped without ever being delivered.
        mailbox.mark_seen(imap, "u101")
        imap.expunge(101)
        imap.add(103, _raw("c"))
        self._pipe(imap).pass_once()
        inbox = os.listdir(os.path.join(self.channel, "inbox"))
        self.assertIn("mail-u103.job.txt", inbox)
        c = [m for m in imap.messages if m["uid"] == 103][0]
        self.assertFalse(c["seen"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
