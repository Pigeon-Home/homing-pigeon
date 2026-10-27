# Agent-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""Version 2 messages keep the job path's replay cache and freshness
window (the version 2 draft's section 5; Q86): a message acted on
-- an answer stored, a question answered, a determination logged --
is recorded by its msg_id under the runner's namespace, a copy of
it is dropped without acting again, and an issued_at outside the
job window is rejected before anything is read."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner import runner  # noqa: E402
from runner.runner import handle_v2_mail  # noqa: E402
from runner.tests.test_cli_options import (  # noqa: E402
    SECRET, _IMAP, _SMTP, _Opts, _captured_log, _mail, _seal_v2)
from runner.wire import protocol_v2 as v2  # noqa: E402


class _DryOpts(_Opts):
    dry_run = True


def _stamp(delta_sec):
    when = datetime.now(timezone.utc) + timedelta(seconds=delta_sec)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


class V2ReplayTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="hp-v2-replay-")
        self.addCleanup(self._rm)
        self.saved = (runner._VERBOSE, runner._VERBOSE_LEVEL)
        runner._set_verbosity(2)

    def _rm(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)
        runner._VERBOSE, runner._VERBOSE_LEVEL = self.saved

    def _cfg(self, **extra):
        cfg = {"mailbox_user": "t@example.com", "shared_secret": SECRET,
               "protocol_v2": True, "answer_only": True,
               "max_job_age_sec": 3600}
        cfg.update(extra)
        return cfg

    def _take(self, cfg, kind, obj, opts=None, seen=None):
        subject = f"[HOMING-PIGEON] {kind} " + obj["msg_id"]
        imap = _IMAP()
        imap.marked = []
        imap.store = lambda *args: imap.marked.append(args) or ("OK", None)
        with _captured_log() as buf:
            taken = handle_v2_mail(
                cfg, imap, _SMTP(), 9, _mail(subject, _seal_v2(obj)),
                subject, runner.build_secrets(cfg), opts or _Opts(),
                self.dir, seen)
        return taken, buf.getvalue(), imap.marked

    def _seen(self):
        try:
            with open(os.path.join(self.dir, "seen.json"),
                      encoding="utf-8") as fh:
                return json.load(fh)
        except OSError:
            return {}

    def _question(self):
        return v2.question_for({"protocol_v2": True},
                               {"job_id": "j1", "kind": "exec"})

    def test_a_question_is_answered_once_and_its_copy_is_dropped(self):
        q = self._question()
        cfg = self._cfg(runner_id="rid-1")
        taken, out, marked = self._take(cfg, "question", q)
        self.assertTrue(taken)
        self.assertIn("answerer replied to " + q["msg_id"], out)
        self.assertIn("rid-1:v2:" + q["msg_id"], self._seen())
        taken, out, marked = self._take(cfg, "question", q)
        self.assertTrue(taken)
        self.assertNotIn("answerer replied", out)
        self.assertIn("already seen", out)
        self.assertEqual(len(marked), 1)

    def test_the_poll_dict_is_the_cache_when_the_caller_hands_one(self):
        q = self._question()
        seen = {}
        self._take(self._cfg(), "question", q, seen=seen)
        self.assertEqual(seen, {"v2:" + q["msg_id"]: True})
        self.assertIn("v2:" + q["msg_id"], self._seen())
        _taken, out, _m = self._take(self._cfg(), "question", q, seen=seen)
        self.assertIn("already seen", out)

    def test_an_answer_and_a_determination_are_recorded_once(self):
        ans = v2.answer_for(self._question(), "the left")
        _t, out, _m = self._take(self._cfg(), "answer", ans)
        self.assertIn("stored", out)
        _t, out, _m = self._take(self._cfg(), "answer", ans)
        self.assertIn("already seen", out)
        self.assertNotIn("already stored", out)
        det = v2.determination_for({"job_id": "j1"},
                                   {"findings": [{"detail": "rm"}]})
        _t, out, _m = self._take(self._cfg(), "determination", det)
        self.assertIn("version 2 determination", out)
        _t, out, _m = self._take(self._cfg(), "determination", det)
        self.assertNotIn("for job", out)
        self.assertIn("already seen", out)
        self.assertEqual(set(self._seen()),
                         {"v2:" + ans["msg_id"], "v2:" + det["msg_id"]})

    def test_a_stale_or_future_message_is_rejected_unread(self):
        q = self._question()
        q["issued_at"] = _stamp(-7200)
        _t, out, marked = self._take(self._cfg(), "question", q)
        self.assertIn("issued_at outside allowed window", out)
        self.assertNotIn("answerer replied", out)
        self.assertEqual(len(marked), 1)
        q["issued_at"] = _stamp(600)
        _t, out, _m = self._take(self._cfg(), "question", q)
        self.assertIn("issued_at outside allowed window", out)
        self.assertEqual(self._seen(), {})
        # The window is the owner's: a day-old message under a
        # two-day window is fresh.
        q["issued_at"] = _stamp(-86400)
        _t, out, _m = self._take(self._cfg(max_job_age_sec=172800),
                                 "question", q)
        self.assertIn("answerer replied", out)

    def test_a_dry_run_records_nothing(self):
        q = self._question()
        _t, out, marked = self._take(self._cfg(), "question", q,
                                     opts=_DryOpts())
        self.assertIn("answerer replied", out)
        self.assertEqual(self._seen(), {})
        self.assertEqual(marked, [])
        _t, out, _m = self._take(self._cfg(), "question", q)
        self.assertIn("answerer replied", out)

    def test_a_question_left_for_another_reader_is_not_recorded(self):
        q = self._question()
        _t, out, marked = self._take(self._cfg(answer_only=False),
                                     "question", q)
        self.assertNotIn("answerer replied", out)
        self.assertEqual(marked, [])
        self.assertEqual(self._seen(), {})
        _t, out, _m = self._take(self._cfg(), "question", q)
        self.assertIn("answerer replied", out)


if __name__ == "__main__":
    unittest.main()
