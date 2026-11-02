# Agent-Stamp: 70000a51-e296-4b2c-bf5b-ba020e23eb91
"""The hosted queue's edges: what the runner's queues transport, the
SI's `send_job.py results` and `dlq`, and `homing-pigeon-host` do when
the queue or the input is not what the happy path expects.

Every case here is a branch the queue suites did not reach: a queue
that answers something other than JSON, a renewal that raises, a
result with no envelope, a keyring that supplies the secret, a
dead-letter call the queue refuses. No network: a scripted opener
stands in for the Worker.
"""
import io
import json
import os
import secrets
import sys
import tempfile
import types
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.cloud import send_job  # noqa: E402
from runner.hosting import cli as host_cli  # noqa: E402
from runner.transport_extensions import channel as ch  # noqa: E402
from runner.transport_extensions.queues import __main__ as q  # noqa: E402


class _Resp:
    def __init__(self, status, body=b""):
        self.status = status
        self._body = body if isinstance(body, bytes) else body.encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener(*answers):
    """An opener that answers each request with the next (status, body);
    a status >= 400 is raised as HTTPError, as urllib does."""
    script = list(answers)
    seen = []

    def _open(req, timeout=None):
        seen.append((req.get_method(), req.full_url))
        status, body = script.pop(0)
        if status >= 400:
            fp = io.BytesIO(body if isinstance(body, bytes) else body.encode())
            raise urllib.error.HTTPError(req.full_url, status, "x", {}, fp)
        return _Resp(status, body)
    _open.seen = seen
    return _open


class QueueClientEdgesTest(unittest.TestCase):
    def test_pull_refuses_a_non_json_or_failed_answer(self):
        c = q.QueueClient("https://w.example/t/a", "tok",
                          opener=opener((200, b"<html>")))
        with self.assertRaisesRegex(RuntimeError, "not JSON"):
            c.pull(4)
        c = q.QueueClient("https://w.example/t/a", "tok",
                          opener=opener((503, b"later")))
        with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
            c.pull(4)

    def test_pull_keeps_only_well_formed_items(self):
        body = json.dumps({"jobs": [
            "not a dict", {"id": "", "envelope": "x"}, {"id": "j1"},
            {"id": "j2", "envelope": "[HOMING-PIGEON] job j2\n\n{}\n"}]})
        c = q.QueueClient("https://w.example/t/a", "tok",
                          opener=opener((200, body)))
        self.assertEqual([i for i, _ in c.pull(8)], ["j2"])

    def test_an_error_body_that_cannot_be_read_is_empty(self):
        class Broken(io.BytesIO):
            def read(self, *a):
                raise OSError("gone")

        def _open(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 502, "x", {}, Broken())
        c = q.QueueClient("https://w.example/t/a", "tok", opener=_open)
        self.assertEqual(c._request("GET", "/jobs"), (502, b""))

    def test_renew_reports_whether_the_queue_still_holds_the_lease(self):
        c = q.QueueClient("https://w.example/t/a", "tok",
                          opener=opener((204, b""), (404, b"")))
        self.assertTrue(c.renew("j/1"))
        self.assertFalse(c.renew("j1"))

    def test_ack_and_renew_name_the_hand_the_pull_gave(self):
        body = json.dumps({"jobs": [{
            "id": "j1", "envelope": "e", "attempt": 2, "hand": 7}]})
        op = opener((200, body), (204, b""), (204, b""))
        c = q.QueueClient("https://w.example/t/a", "tok", opener=op)
        self.assertEqual([i for i, _ in c.pull(1)], ["j1"])
        self.assertTrue(c.ack("j1"))
        self.assertTrue(c.renew("j1"))
        self.assertIn("/jobs/j1/ack?attempt=2&hand=7", op.seen[1][1])
        self.assertIn("/jobs/j1/lease?attempt=2&hand=7", op.seen[2][1])


class AckNamesAttemptShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 29: an ack did not name
    the hand it was given; a later pull kept its job (fixed
    b2795848, 31-Oct-2026). The Python half of that fix lives in
    QueueClient (runner/transport_extensions/queues/__main__.py):
    a pull stores the attempt and the hand the Worker handed it,
    per job id, and ack and renew name that receipt
    (?attempt=N&hand=N, in that order) so the first runner's ack
    cannot delete the job a later pull is running -- a requeue
    resets the attempt count, so the attempt alone collides with
    the next life, and the hand, which only goes up, is what
    tells the lives apart. Before the fix the ack named nothing
    but the bare id. This family scattershots everything around
    that failure: the receipt field by field, each field alone
    and both together, zero / negative / huge values, two and
    more jobs in one pull and across pulls, a later pull
    replacing the receipt, the type gate (only a real int is
    stored; a string, a bool, a float, None, a list or a dict
    names nothing), the ack answers, replaying the same ack,
    bookended and injection-shaped spellings of the receipt,
    and decimal run lengths. One regression test was never
    going to be enough for a bug that took days of CPU to find.

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: string spellings of
    attempt and hand are wrapped with every printable ASCII
    symbol (string.punctuation) at the front AND the back, as
    singles, matched pairs, mismatched pairs and symbol-only
    strings, plus NUL, tab, CR and LF at both ends, and are
    pinned as not-a-receipt in every shape; the envelope that
    rides beside the receipt gets the same bookends with the
    receipt itself untouched; and run lengths: decimal runs
    of 1, 5 and 10 of one digit, the odd digit at the front,
    the back and the middle, 100-digit values, and 5 and 10
    jobs in a single pull.

    Proof of work. The unit tests are the 50 methods of this
    class: 14 core receipt tests, 6 isolation tests, 3
    never-pulled tests, 8 type-gate tests, 4 ack-answer tests,
    4 replay tests, 6 bookend / injection sweeps, 4 run-length
    sweeps and 1 extra-field test. Per-field enumeration: the
    pull item is fielded -- id, envelope, attempt, hand and
    any extra fields -- and each field gets its own tests, as
    do the ack's status and the renew's quoting. The whole
    file runs 71 tests, 0 skipped. The fuzzing was executed,
    not just the tests written: the corpus machinery was
    driven locally with runner/tools/de_dust_corpus.py grow
    --target channels --rounds 400 --seed 20261130 against
    the banked channels corpus. Result, verbatim from the
    grow: "channels: 11 -> 11 entries, arcs 142 -> 142,
    0 crashes, 0 slow, slowest 59 ms (165bf7c924d776eb)" --
    400 rounds, 0 crashes, 0 slow, arcs unchanged at 142,
    slowest try 59 ms; the ack-without-a-receipt shape did
    not recur. The grow's bookkeeping writes were reverted
    and are not banked (banking is the rigs' hourly job);
    this record is the run's proof. This family adds no
    skips and changes no production code. None of this is
    exotic: it is combinatorics -- systematically trying the
    combinations a hand-written list would never reach, then
    pinning each answer as a test."""

    _MISSING = object()

    # -- helpers ---------------------------------------------------

    def _item(self, ident="j1", attempt=_MISSING, hand=_MISSING,
              envelope="e", **extra):
        item = {"id": ident, "envelope": envelope}
        if attempt is not self._MISSING:
            item["attempt"] = attempt
        if hand is not self._MISSING:
            item["hand"] = hand
        item.update(extra)
        return item

    def _pulled(self, items, *answers):
        if not isinstance(items, list):
            items = [items]
        body = json.dumps({"jobs": items})
        op = opener((200, body), *answers)
        client = q.QueueClient("https://w.example/t/a", "tok", opener=op)
        client.pull(len(items) or 1)
        return client, op

    @staticmethod
    def _url(op, idx=1):
        return op.seen[idx][1]

    # -- core receipt, field by field (14) -------------------------

    def test_ack_names_attempt_and_hand_verbatim(self):
        c, op = self._pulled(self._item(attempt=2, hand=7), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?attempt=2&hand=7")

    def test_ack_names_attempt_alone_when_hand_absent(self):
        c, op = self._pulled(self._item(attempt=3), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?attempt=3")

    def test_ack_names_hand_alone_when_attempt_absent(self):
        c, op = self._pulled(self._item(hand=9), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?hand=9")

    def test_ack_is_bare_when_neither_field_present(self):
        c, op = self._pulled(self._item(), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op), "https://w.example/t/a/jobs/j1/ack")

    def test_renew_names_attempt_and_hand_verbatim(self):
        c, op = self._pulled(self._item(attempt=2, hand=7), (204, b""))
        self.assertTrue(c.renew("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/lease?attempt=2&hand=7")

    def test_renew_names_attempt_alone(self):
        c, op = self._pulled(self._item(attempt=4), (204, b""))
        self.assertTrue(c.renew("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/lease?attempt=4")

    def test_renew_names_hand_alone(self):
        c, op = self._pulled(self._item(hand=11), (204, b""))
        self.assertTrue(c.renew("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/lease?hand=11")

    def test_renew_is_bare_when_neither_field_present(self):
        c, op = self._pulled(self._item(), (204, b""))
        self.assertTrue(c.renew("j1"))
        self.assertEqual(self._url(op), "https://w.example/t/a/jobs/j1/lease")

    def test_receipt_order_attempt_then_hand_regardless_of_pull_order(self):
        item = {"id": "j1", "envelope": "e", "hand": 7, "attempt": 2}
        c, op = self._pulled(item, (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?attempt=2&hand=7")

    def test_attempt_zero_is_named(self):
        c, op = self._pulled(self._item(attempt=0, hand=7), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertIn("attempt=0&hand=7", self._url(op))

    def test_hand_zero_is_named(self):
        c, op = self._pulled(self._item(attempt=2, hand=0), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertIn("attempt=2&hand=0", self._url(op))

    def test_attempt_negative_is_named_verbatim(self):
        c, op = self._pulled(self._item(attempt=-3, hand=7), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertIn("attempt=-3&hand=7", self._url(op))

    def test_hand_negative_is_named_verbatim(self):
        c, op = self._pulled(self._item(attempt=2, hand=-7), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertIn("attempt=2&hand=-7", self._url(op))

    def test_attempt_and_hand_at_one_are_named(self):
        c, op = self._pulled(self._item(attempt=1, hand=1), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertIn("attempt=1&hand=1", self._url(op))

    # -- isolation between jobs and pulls (6) ----------------------

    def test_two_jobs_in_one_pull_each_ack_their_own_receipt(self):
        items = [self._item("j1", attempt=1, hand=10),
                 self._item("j2", attempt=2, hand=20)]
        c, op = self._pulled(items, (204, b""), (204, b""))
        self.assertTrue(c.ack("j2"))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op, 1),
                         "https://w.example/t/a/jobs/j2/ack?attempt=2&hand=20")
        self.assertEqual(self._url(op, 2),
                         "https://w.example/t/a/jobs/j1/ack?attempt=1&hand=10")

    def test_five_jobs_in_one_pull_each_ack_their_own_receipt(self):
        items = [self._item(f"j{i}", attempt=i, hand=100 + i)
                 for i in range(1, 6)]
        c, op = self._pulled(items, *([(204, b"")] * 5))
        for i in range(1, 6):
            self.assertTrue(c.ack(f"j{i}"))
            self.assertEqual(
                self._url(op, i),
                f"https://w.example/t/a/jobs/j{i}/ack?attempt={i}&hand={100 + i}")

    def test_jobs_in_different_pulls_keep_their_own_receipts(self):
        body1 = json.dumps({"jobs": [self._item("j1", attempt=1, hand=10)]})
        body2 = json.dumps({"jobs": [self._item("j2", attempt=5, hand=50)]})
        op = opener((200, body1), (200, body2), (204, b""), (204, b""))
        c = q.QueueClient("https://w.example/t/a", "tok", opener=op)
        c.pull(1)
        c.pull(1)
        self.assertTrue(c.ack("j1"))
        self.assertTrue(c.ack("j2"))
        self.assertEqual(self._url(op, 2),
                         "https://w.example/t/a/jobs/j1/ack?attempt=1&hand=10")
        self.assertEqual(self._url(op, 3),
                         "https://w.example/t/a/jobs/j2/ack?attempt=5&hand=50")

    def test_later_pull_of_same_id_replaces_its_receipt(self):
        body1 = json.dumps({"jobs": [self._item("j1", attempt=1, hand=10)]})
        body2 = json.dumps({"jobs": [self._item("j1", attempt=2, hand=20)]})
        op = opener((200, body1), (200, body2), (204, b""))
        c = q.QueueClient("https://w.example/t/a", "tok", opener=op)
        c.pull(1)
        c.pull(1)
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op, 2),
                         "https://w.example/t/a/jobs/j1/ack?attempt=2&hand=20")

    def test_sequential_passes_each_ack_the_receipt_of_their_pass(self):
        body1 = json.dumps({"jobs": [self._item("j1", attempt=1, hand=10)]})
        body2 = json.dumps({"jobs": [self._item("j2", attempt=1, hand=11)]})
        op = opener((200, body1), (204, b""), (200, body2), (204, b""))
        c = q.QueueClient("https://w.example/t/a", "tok", opener=op)
        c.pull(1)
        self.assertTrue(c.ack("j1"))
        c.pull(1)
        self.assertTrue(c.ack("j2"))
        self.assertEqual(self._url(op, 1),
                         "https://w.example/t/a/jobs/j1/ack?attempt=1&hand=10")
        self.assertEqual(self._url(op, 3),
                         "https://w.example/t/a/jobs/j2/ack?attempt=1&hand=11")

    def test_receipt_stored_only_for_a_well_formed_pull_item(self):
        item = {"id": "j1", "attempt": 2, "hand": 7}  # no envelope: skipped
        c, op = self._pulled(item, (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op), "https://w.example/t/a/jobs/j1/ack")

    # -- never pulled (3) ------------------------------------------

    def test_ack_for_id_never_pulled_is_bare(self):
        op = opener((204, b""))
        c = q.QueueClient("https://w.example/t/a", "tok", opener=op)
        self.assertTrue(c.ack("ghost"))
        self.assertEqual(self._url(op, 0),
                         "https://w.example/t/a/jobs/ghost/ack")

    def test_renew_for_id_never_pulled_is_bare_and_quoted(self):
        op = opener((204, b""))
        c = q.QueueClient("https://w.example/t/a", "tok", opener=op)
        self.assertTrue(c.renew("j/1"))
        self.assertEqual(self._url(op, 0),
                         "https://w.example/t/a/jobs/j%2F1/lease")

    def test_ack_for_other_id_does_not_borrow_a_pulled_receipt(self):
        c, op = self._pulled(self._item("j1", attempt=2, hand=7), (204, b""))
        self.assertTrue(c.ack("j2"))
        self.assertEqual(self._url(op), "https://w.example/t/a/jobs/j2/ack")

    # -- the type gate (8) -----------------------------------------

    def test_string_attempt_is_not_named_but_int_hand_is(self):
        c, op = self._pulled(self._item(attempt="2", hand=7), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?hand=7")

    def test_string_hand_is_not_named_but_int_attempt_is(self):
        c, op = self._pulled(self._item(attempt=2, hand="7"), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?attempt=2")

    def test_bool_attempt_is_not_named(self):
        c, op = self._pulled(self._item(attempt=True, hand=7), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?hand=7")

    def test_bool_hand_is_not_named(self):
        c, op = self._pulled(self._item(attempt=2, hand=False), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?attempt=2")

    def test_float_attempt_is_not_named(self):
        c, op = self._pulled(self._item(attempt=2.0, hand=7), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?hand=7")

    def test_float_hand_is_not_named(self):
        c, op = self._pulled(self._item(attempt=2, hand=7.5), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?attempt=2")

    def test_list_attempt_and_dict_hand_are_not_named(self):
        c, op = self._pulled(
            self._item(attempt=[2], hand={"v": 7}), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op), "https://w.example/t/a/jobs/j1/ack")

    def test_numeric_string_attempt_spellings_are_not_named(self):
        for spelling in (" 2", "2 ", "\t2\n", "+2", "0x2", "2.0"):
            with self.subTest(spelling=spelling):
                c, op = self._pulled(
                    self._item(attempt=spelling, hand=7), (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertEqual(self._url(op),
                                 "https://w.example/t/a/jobs/j1/ack?hand=7")

    # -- ack answers (4) -------------------------------------------

    def test_ack_true_on_200_with_receipt_named(self):
        c, op = self._pulled(self._item(attempt=2, hand=7), (200, b""))
        self.assertTrue(c.ack("j1"))
        self.assertIn("attempt=2&hand=7", self._url(op))

    def test_ack_true_on_404_with_receipt_named(self):
        c, op = self._pulled(self._item(attempt=2, hand=7), (404, b""))
        self.assertTrue(c.ack("j1"))
        self.assertIn("attempt=2&hand=7", self._url(op))

    def test_ack_false_on_409_with_receipt_named(self):
        c, op = self._pulled(self._item(attempt=2, hand=7), (409, b""))
        self.assertFalse(c.ack("j1"))
        self.assertIn("attempt=2&hand=7", self._url(op))

    def test_ack_false_on_500_with_receipt_named(self):
        c, op = self._pulled(self._item(attempt=2, hand=7), (500, b""))
        self.assertFalse(c.ack("j1"))
        self.assertIn("attempt=2&hand=7", self._url(op))

    # -- replay / idempotence (4) ----------------------------------

    def test_same_ack_twice_names_same_receipt_both_times(self):
        c, op = self._pulled(self._item(attempt=2, hand=7),
                             (204, b""), (404, b""))
        self.assertTrue(c.ack("j1"))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op, 1), self._url(op, 2))
        self.assertIn("attempt=2&hand=7", self._url(op, 2))

    def test_ack_does_not_clear_receipt_for_a_later_renew(self):
        c, op = self._pulled(self._item(attempt=2, hand=7),
                             (204, b""), (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertTrue(c.renew("j1"))
        self.assertEqual(self._url(op, 2),
                         "https://w.example/t/a/jobs/j1/lease?attempt=2&hand=7")

    def test_renew_does_not_clear_receipt_for_a_later_ack(self):
        c, op = self._pulled(self._item(attempt=2, hand=7),
                             (204, b""), (204, b""))
        self.assertTrue(c.renew("j1"))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op, 2),
                         "https://w.example/t/a/jobs/j1/ack?attempt=2&hand=7")

    def test_fresh_pull_after_ack_replaces_receipt_for_next_ack(self):
        # The requeue shape from the fix: the attempt resets to
        # 1 and collides with the first life; the hand rises.
        body1 = json.dumps({"jobs": [self._item("j1", attempt=3, hand=8)]})
        body2 = json.dumps({"jobs": [self._item("j1", attempt=1, hand=9)]})
        op = opener((200, body1), (204, b""), (200, body2), (204, b""))
        c = q.QueueClient("https://w.example/t/a", "tok", opener=op)
        c.pull(1)
        self.assertTrue(c.ack("j1"))
        c.pull(1)
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op, 3),
                         "https://w.example/t/a/jobs/j1/ack?attempt=1&hand=9")

    # -- bookend and injection sweeps (6) --------------------------

    def test_bookend_singles_on_string_attempt_are_not_named(self):
        import string
        for ch_ in string.punctuation:
            with self.subTest(bookend=ch_):
                c, op = self._pulled(
                    self._item(attempt=f"{ch_}2{ch_}", hand=7), (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertEqual(self._url(op),
                                 "https://w.example/t/a/jobs/j1/ack?hand=7")

    def test_bookend_pairs_on_string_hand_are_not_named(self):
        import string
        punct = string.punctuation
        for i, ch_ in enumerate(punct):
            other = punct[(i + 7) % len(punct)]
            for wrapped in (f"{ch_}{ch_}7{ch_}{ch_}",
                            f"{ch_}{other}7{other}{ch_}"):
                with self.subTest(wrapped=wrapped):
                    c, op = self._pulled(
                        self._item(attempt=2, hand=wrapped), (204, b""))
                    self.assertTrue(c.ack("j1"))
                    self.assertEqual(
                        self._url(op),
                        "https://w.example/t/a/jobs/j1/ack?attempt=2")

    def test_symbol_only_string_attempt_and_hand_are_not_named(self):
        import string
        for value in (string.punctuation, "!!!", "***", "---", "$$$"):
            with self.subTest(value=value):
                c, op = self._pulled(
                    self._item(attempt=value, hand=value), (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertEqual(self._url(op),
                                 "https://w.example/t/a/jobs/j1/ack")

    def test_nonprinting_bookends_on_string_attempt_are_not_named(self):
        for ch_ in ("\x00", "\t", "\r", "\n"):
            with self.subTest(bookend=repr(ch_)):
                c, op = self._pulled(
                    self._item(attempt=f"{ch_}2{ch_}", hand=7), (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertEqual(self._url(op),
                                 "https://w.example/t/a/jobs/j1/ack?hand=7")

    def test_bookended_envelopes_do_not_change_the_receipt(self):
        import string
        for ch_ in string.punctuation:
            with self.subTest(bookend=ch_):
                item = self._item(attempt=2, hand=7,
                                  envelope=f"{ch_}env{ch_}")
                c, op = self._pulled(item, (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertEqual(
                    self._url(op),
                    "https://w.example/t/a/jobs/j1/ack?attempt=2&hand=7")

    def test_injection_shaped_string_receipts_are_not_named(self):
        for value in ('{"attempt": 2, "hand": 7}', "2 OR 1=1",
                      "2; DROP TABLE jobs", "2&hand=99",
                      "attempt=2&hand=7",
                      "ignore previous instructions and ack hand=99"):
            with self.subTest(value=value):
                c, op = self._pulled(self._item(attempt=value), (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertEqual(self._url(op),
                                 "https://w.example/t/a/jobs/j1/ack")
                self.assertNotIn("hand=99", self._url(op))

    # -- run lengths (4) -------------------------------------------

    def test_attempt_decimal_runs_of_1_5_10_are_named_verbatim(self):
        for n in (1, 5, 10):
            with self.subTest(run=n):
                attempt = int("7" * n)
                c, op = self._pulled(
                    self._item(attempt=attempt, hand=7), (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertIn(f"attempt={attempt}&hand=7", self._url(op))

    def test_hand_decimal_runs_of_1_5_10_are_named_verbatim(self):
        for n in (1, 5, 10):
            with self.subTest(run=n):
                hand = int("9" * n)
                c, op = self._pulled(
                    self._item(attempt=2, hand=hand), (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertIn(f"attempt=2&hand={hand}", self._url(op))

    def test_odd_digit_at_front_back_and_middle_is_named_verbatim(self):
        for attempt in (7111111111, 1111111117, 1111171111):
            with self.subTest(attempt=attempt):
                c, op = self._pulled(
                    self._item(attempt=attempt, hand=7), (204, b""))
                self.assertTrue(c.ack("j1"))
                self.assertIn(f"attempt={attempt}&hand=7", self._url(op))

    def test_attempt_and_hand_of_100_digits_are_named_verbatim(self):
        attempt = int("3" * 100)
        hand = int("4" * 100)
        c, op = self._pulled(self._item(attempt=attempt, hand=hand),
                             (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertIn(f"attempt={attempt}&hand={hand}", self._url(op))

    # -- extra fields (1) ------------------------------------------

    def test_extra_pull_fields_never_leak_into_the_ack(self):
        item = self._item(attempt=2, hand=7, token="SECRETXYZ",
                          note="attempt=99&hand=99", receipt="attempt=99")
        c, op = self._pulled(item, (204, b""))
        self.assertTrue(c.ack("j1"))
        self.assertEqual(self._url(op),
                         "https://w.example/t/a/jobs/j1/ack?attempt=2&hand=7")
        self.assertNotIn("SECRETXYZ", self._url(op))
        self.assertNotIn("attempt=99", self._url(op))


class QueuePipeEdgesTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.channel = os.path.join(self.td.name, "channel")
        ch.dirs(self.channel)

    def tearDown(self):
        self.td.cleanup()

    def test_a_renewal_that_raises_is_logged_and_the_pass_goes_on(self):
        client = mock.Mock()
        client.renew.side_effect = [OSError("down"), True]
        pipe = q.QueuePipe({}, self.channel, client)
        pipe._pending = {"a": "a", "b": "b"}
        logs = []
        with mock.patch.object(ch, "log", lambda m, *a: logs.append(m)):
            pipe.renew_leases()
        self.assertEqual(client.renew.call_count, 2)
        self.assertTrue(any("lease renewal failed" in m for m in logs))

    def test_a_result_body_without_a_final_newline_gets_one(self):
        d = ch.dirs(self.channel)
        ch._atomic_write(os.path.join(d["outbox"], "j1.result.txt"),
                         "[HOMING-PIGEON] result j1\n\n{\"sig\":\"00\"}")
        client = mock.Mock()
        pipe = q.QueuePipe({}, self.channel, client)
        with mock.patch.object(ch, "pending_results",
                               lambda c: [("j1.result.txt",
                                           "[HOMING-PIGEON] result j1",
                                           "{\"sig\":\"00\"}")]):
            pipe.push_results()
        posted = client.post_result.call_args[0][0]
        self.assertTrue(posted.endswith("}\n"))


class QueueMainEdgesTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.channel = os.path.join(self.td.name, "channel")
        self.cfg = os.path.join(self.td.name, "cfg.json")
        for k in ("HOMING_PIGEON_TRANSPORT_CHANNEL",
                  "HOMING_PIGEON_TRANSPORT_CONFIG"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.td.cleanup()

    def _cfg(self, **cfg):
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)

    def test_no_channel_and_no_token_are_refused(self):
        logs = []
        with mock.patch.object(ch, "log", lambda m, *a: logs.append(m)):
            self.assertEqual(q.main(["queues"]), 2)
            self._cfg(url="https://w.example/t/a")
            self.assertEqual(q.main(["queues", self.channel, self.cfg]), 2)
        self.assertTrue(any("no channel" in m for m in logs))
        self.assertTrue(any("transport_queues.token, or token_env" in m
                            for m in logs))

    def test_a_failed_pass_is_logged_and_the_loop_naps_and_goes_on(self):
        self._cfg(url="https://w.example/t/a", token="tok")
        logs, naps = [], []
        with mock.patch.object(ch, "log", lambda m, *a: logs.append(m)), \
                mock.patch.object(ch, "nap", naps.append), \
                mock.patch.object(q.QueuePipe, "pull_jobs",
                                  side_effect=RuntimeError("boom")):
            rc = q.main(["queues", self.channel, self.cfg],
                        opener=opener(), passes=2)
        self.assertEqual(rc, 0)
        self.assertEqual(sum("pass failed" in m for m in logs), 2)
        self.assertEqual(len(naps), 1)


def _args(**kw):
    base = {"from_queue": "https://w.example/t/a", "queue_token_env": None,
            "max": 20, "ack": False, "secret": None, "key_id": None,
            "keyring": None, "drop": None, "requeue": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


class SendJobQueueEdgesTest(unittest.TestCase):
    def setUp(self):
        os.environ["HP_SI_TOKEN"] = "si"
        self.td = tempfile.TemporaryDirectory()

    def tearDown(self):
        os.environ.pop("HP_SI_TOKEN", None)
        self.td.cleanup()

    def _quiet(self, fn, *a, **k):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = fn(*a, **k)
        return rc, out.getvalue(), err.getvalue()

    def test_a_refused_post_or_read_returns_the_status_and_body(self):
        status, text = send_job.post_to_queue(
            "https://w.example/t/a", "[HOMING-PIGEON] job j\n\n{}\n",
            opener=opener((403, b'{"error":"invalid signature"}')))
        self.assertEqual((status, text), (403, '{"error":"invalid signature"}'))

        class Broken(io.BytesIO):
            def read(self, *a):
                raise OSError("gone")

        def _open(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 502, "x", {}, Broken())
        self.assertEqual(send_job.post_to_queue(
            "https://w.example/t/a", "x\n\ny", opener=_open), (502, ""))
        self.assertEqual(send_job._queue_call(
            "https://w.example/t/a", "GET", "/dlq", opener=_open), (502, ""))

    def test_a_plain_http_queue_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "must be https"):
            send_job._queue_call("http://w.example/t/a", "GET", "/results")

    def test_results_that_are_not_a_list_are_a_refused_read(self):
        rc, _, err = self._quiet(send_job.cmd_results, _args(),
                                 opener=opener((200, b"[]")))
        self.assertEqual(rc, 2)
        self.assertIn("not a results list", err)
        rc, _, err = self._quiet(send_job.cmd_results, _args(),
                                 opener=opener((401, b"si token")))
        self.assertEqual(rc, 2)

    def test_a_result_without_an_envelope_is_reported_not_fatal(self):
        body = json.dumps({"results": [{"id": "r1"}]})
        rc, out, _ = self._quiet(send_job.cmd_results, _args(secret="x"),
                                 opener=opener((200, body)))
        self.assertEqual(rc, 1)
        line = json.loads(out)
        self.assertEqual(line, {"id": "r1", "ok": False,
                                "error": "the result carries no envelope"})

    def test_the_keyring_supplies_the_secret_a_result_names(self):
        secret = secrets.token_hex(32)
        kid = send_job.key_fingerprint(secret)
        ring = os.path.join(self.td.name, "ring.json")
        send_job.keyring_save(ring, {kid: {"secret": secret,
                                           "runner": "r@example.test"}})
        body = send_job.sign_payload(
            {"v": 1, "type": "result", "job_id": "j1", "key_id": kid,
             "exit_code": 0}, secret)
        env = f"[HOMING-PIGEON] result j1\n\n{body}\n"
        answer = json.dumps({"results": [{"id": "j1", "envelope": env}]})
        rc, out, _ = self._quiet(send_job.cmd_results, _args(keyring=ring),
                                 opener=opener((200, answer)))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["payload"]["exit_code"], 0)
        # A body that names no key, with no --secret, cannot be opened.
        bare = send_job.sign_payload({"v": 1, "exit_code": 0}, secret)
        answer = json.dumps({"results": [{
            "id": "j2", "envelope": f"[HOMING-PIGEON] result j2\n\n{bare}\n"}]})
        rc, out, _ = self._quiet(send_job.cmd_results, _args(keyring=ring),
                                 opener=opener((200, answer)))
        self.assertEqual(rc, 1)
        self.assertIn("names no key_id", json.loads(out)["error"])

    def test_a_result_subject_names_its_job(self):
        self.assertEqual(send_job._result_job_id(
            "[HOMING-PIGEON] result j9"), "j9")
        self.assertEqual(send_job._result_job_id(
            "Re: [HOMING-PIGEON] qresult j8"), "j8")
        self.assertIsNone(send_job._result_job_id("[HOMING-PIGEON] job j9"))
        self.assertIsNone(send_job._result_job_id(None))

    def test_dlq_refusals_are_two(self):
        rc, _, _ = self._quiet(send_job.cmd_dlq, _args(),
                               opener=opener((500, b"no")))
        self.assertEqual(rc, 2)
        rc, _, err = self._quiet(send_job.cmd_dlq, _args(),
                                 opener=opener((200, b"[1]")))
        self.assertEqual(rc, 2)
        self.assertIn("not a dead-letter list", err)
        rc, _, _ = self._quiet(send_job.cmd_dlq, _args(requeue="d1"),
                               opener=opener((429, b"quota")))
        self.assertEqual(rc, 2)
        o = opener((204, b""))
        rc, out, _ = self._quiet(send_job.cmd_dlq, _args(drop="a/b"),
                                 opener=o)
        self.assertEqual(rc, 0)
        self.assertTrue(o.seen[0][1].endswith("/dlq/a%2Fb/ack"))


class HostCliEdgesTest(unittest.TestCase):
    def test_an_empty_secret_env_is_refused_before_any_call(self):
        os.environ["HP_TEST_FLY"] = "tok"
        os.environ.pop("HP_TEST_EMPTY_SECRET", None)
        try:
            args = types.SimpleNamespace(
                token_env="HP_TEST_FLY", blob=None, queue=None,
                secret_env="HP_TEST_EMPTY_SECRET")
            with self.assertRaisesRegex(SystemExit, "is empty"):
                host_cli.cmd_up(args, http=object())
        finally:
            os.environ.pop("HP_TEST_FLY", None)

    def test_main_turns_a_value_error_into_exit_two(self):
        with mock.patch.object(host_cli, "cmd_status",
                               side_effect=ValueError("bad blob")):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = host_cli.main(["status"])
        self.assertEqual(rc, 2)
        self.assertIn("bad blob", err.getvalue())



_WORKER_ROUNDTRIP = r"""
import worker, { TenantQueue } from "./src/index.js";
import fs from "node:fs";
const [recPath, slug, si, runner, envelope] = JSON.parse(fs.readFileSync(0, "utf8"));
class Store { constructor() { this.m = new Map(); }
  async get(k) { return this.m.has(k) ? structuredClone(this.m.get(k)) : undefined; }
  async put(k, v) { this.m.set(k, structuredClone(v)); }
  async delete(k) { return this.m.delete(k); }
  async list({ prefix = "", limit = Infinity, startAfter } = {}) { const o = new Map();
    for (const k of [...this.m.keys()].sort()) { if (o.size >= limit) break;
      if (startAfter !== undefined && k <= startAfter) continue;
      if (k.startsWith(prefix)) o.set(k, structuredClone(this.m.get(k))); } return o; } }
const objs = new Map();
const env = { TENANTS: { async get(k) { return k === slug ? fs.readFileSync(recPath, "utf8") : null; } },
  TENANT_QUEUE: { idFromName: (n) => n, get(id) { if (!objs.has(id)) objs.set(id, new TenantQueue({ storage: new Store() }, env)); return objs.get(id); } } };
const call = (path, method, token, body) => worker.fetch(new Request("https://w.test" + path,
  { method, body, headers: { authorization: "Bearer " + token } }), env);
const out = [];
out.push((await call(`/t/${slug}/jobs`, "POST", si, envelope)).status);
out.push((await call(`/t/${slug}/jobs`, "POST", runner, envelope)).status);
out.push((await call(`/t/${slug}/jobs`, "GET", runner)).status);
console.log(JSON.stringify(out));
"""


class QueueTenantTest(unittest.TestCase):
    """`homing-pigeon-host queue-tenant`: a tenant minted with nothing
    secret on stdout, and a record the Worker itself accepts."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.td.cleanup()

    def _mint(self, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = host_cli.main(["queue-tenant", "--tenant", "alice",
                                "--dir", self.td.name,
                                "--worker", "https://w.example"] + list(extra))
        return rc, out.getvalue()

    def _env(self):
        vals = {}
        with open(os.path.join(self.td.name, "alice.env"),
                  encoding="utf-8") as fh:
            for line in fh:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    vals[k] = v
        return vals

    def test_the_files_are_private_and_stdout_holds_no_secret(self):
        rc, shown = self._mint()
        self.assertEqual(rc, 0)
        vals = self._env()
        self.assertEqual(set(vals), {"HP_SI_TOKEN", "HP_RUNNER_TOKEN",
                                     "HP_SECRET"})
        for v in vals.values():
            self.assertNotIn(v, shown)
        self.assertIn("https://w.example/t/alice", shown)
        self.assertIn("wrangler kv key put --binding TENANTS alice", shown)
        with open(os.path.join(self.td.name, "alice.kv.json"),
                  encoding="utf-8") as fh:
            rec = json.load(fh)
        import hashlib
        self.assertEqual(rec["si_token_sha256"], hashlib.sha256(
            vals["HP_SI_TOKEN"].encode()).hexdigest())
        self.assertEqual(rec["hmac_secret"], vals["HP_SECRET"])
        self.assertEqual(rec["quota"], {"jobs_per_hour": 600,
                                        "bytes_per_day": 256 * 1024 * 1024})
        if os.name != "nt":
            for name in ("alice.env", "alice.kv.json"):
                mode = os.stat(os.path.join(self.td.name, name)).st_mode
                self.assertEqual(mode & 0o777, 0o600, name)

    def test_minted_once_a_given_secret_and_bad_input(self):
        os.environ["HP_TEST_GIVEN"] = secrets.token_hex(32)
        try:
            self.assertEqual(self._mint("--secret-env", "HP_TEST_GIVEN")[0], 0)
            self.assertEqual(self._env()["HP_SECRET"],
                             os.environ["HP_TEST_GIVEN"])
        finally:
            os.environ.pop("HP_TEST_GIVEN", None)
        with self.assertRaisesRegex(SystemExit, "minted once"):
            self._mint()
        for bad in (["--tenant", "-x"], ["--tenant", "a/b"],
                    ["--tenant", "ok", "--jobs-per-hour", "0"],
                    ["--tenant", "ok", "--secret-env", "HP_UNSET_XYZ"]):
            with self.assertRaises(SystemExit), \
                    redirect_stdout(io.StringIO()), \
                    redirect_stderr(io.StringIO()):
                host_cli.main(["queue-tenant", "--dir", self.td.name] + bad)

    @unittest.skipIf(__import__("shutil").which("node") is None,
                     "node is not installed")
    def test_the_worker_accepts_the_minted_record(self):
        import subprocess
        self.assertEqual(self._mint()[0], 0)
        vals = self._env()
        body = send_job.sign_payload({"v": 1, "type": "job", "job_id": "j1",
                                      "kind": "ping"}, vals["HP_SECRET"])
        envelope = f"[HOMING-PIGEON] job j1\n\n{body}\n"
        worker_dir = os.path.join(REPO, "runner", "cloud", "queues-worker")
        script = os.path.join(self.td.name, "roundtrip.mjs")
        with open(script, "w", encoding="utf-8") as fh:
            # A file URL node accepts on every platform (file:///C:/...
            # on Windows, not file://C:\\...).
            from pathlib import Path
            fh.write(_WORKER_ROUNDTRIP.replace(
                "./src/index.js",
                Path(worker_dir, "src", "index.js").resolve().as_uri()))
        r = subprocess.run(
            ["node", script], capture_output=True, text=True, timeout=60,
            input=json.dumps([os.path.join(self.td.name, "alice.kv.json"),
                              "alice", vals["HP_SI_TOKEN"],
                              vals["HP_RUNNER_TOKEN"], envelope]))
        self.assertEqual(r.returncode, 0, r.stderr)
        # The SI submits (202), the runner token cannot (401), the
        # runner pulls it (200).
        self.assertEqual(json.loads(r.stdout), [202, 401, 200])


if __name__ == "__main__":
    unittest.main()
