"""Project Platinum, cycle 3: the Oracle's paging and alert
store.

Targets from the cycle-2 refreshed table
(`docs/reports/v3.13.27/coverage-gaps.md`):

  except  oracle/senses.py:load_alerts (2) -- a stored line
          that is not an alert object is skipped, never
          fatal; the valid lines around it still load.
  except  oracle/dri.py:evaluate_page_triggers / _one (2)
          -- the top-signals sort scores a record whose
          scoring raises as 0.0 and still pages; and the
          real path takes adversarial weights without
          raising at all (alert_score refuses them itself).
  except  oracle/dri.py:send_telegram (2) -- a chat_id JSON
          cannot carry is coerced to text and the message
          still goes out, instead of the send dying on the
          dumps.

Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90
"""
import json
import os
import shutil
import tempfile
import time
import unittest
import urllib.request
from unittest import mock

from runner.oracle import dri, senses


def _iso(ts):
    import datetime
    return datetime.datetime.fromtimestamp(
        ts, datetime.timezone.utc).isoformat()


class LoadAlertsTest(unittest.TestCase):
    def test_a_non_object_line_is_skipped_not_fatal(self):
        td = tempfile.mkdtemp(prefix="hp-plat-oracle-")
        try:
            good = {"sensor": "s1", "severity": "high",
                    "observed_at": _iso(time.time())}
            with open(os.path.join(td, senses.SENSES_FILE), "w",
                      encoding="utf-8") as fh:
                fh.write(json.dumps(good) + "\n")
                fh.write("[1, 2, 3]\n")
                fh.write('"a bare string"\n')
                fh.write(json.dumps(good) + "\n")
            out = senses.load_alerts(td, limit=50)
            self.assertEqual(len(out), 2)
            self.assertTrue(all(isinstance(r, dict) for r in out))
        finally:
            shutil.rmtree(td, ignore_errors=True)


class PageTriggersTest(unittest.TestCase):
    DCFG = {"triggers": {"sensor_fused_score": {
        "window_sec": 3600, "threshold": 0.5}}}

    def _dir_with(self, recs):
        td = tempfile.mkdtemp(prefix="hp-plat-oracle-")
        with open(os.path.join(td, senses.SENSES_FILE), "w",
                  encoding="utf-8") as fh:
            for rec in recs:
                fh.write(json.dumps(rec) + "\n")
        return td

    def test_a_record_whose_scoring_raises_scores_zero(self):
        now = time.time()
        good = {"sensor": "s1", "severity": "critical",
                "observed_at": _iso(now), "weight": 1.0}
        bad = {"sensor": "s1", "severity": "critical",
               "observed_at": _iso(now), "weight": "heavy"}
        td = self._dir_with([good, bad])
        try:
            real = senses.alert_score

            def flaky(rec, weight=1.0):
                if isinstance(rec, dict) and \
                        rec.get("weight") == "heavy":
                    raise TypeError("not a weight")
                return real(rec, weight)

            with mock.patch.object(senses, "alert_score", flaky):
                events = dri.evaluate_page_triggers(
                    self.DCFG, td, now - 60, now=now)
            self.assertTrue(events)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_adversarial_weights_never_raise(self):
        now = time.time()
        recs = [{"sensor": "s1", "severity": "critical",
                 "observed_at": _iso(now), "weight": w}
                for w in ("heavy", None, [1], {"x": 1}, 10 ** 400,
                          -3, float("nan"))]
        td = self._dir_with(recs)
        try:
            events = dri.evaluate_page_triggers(
                self.DCFG, td, now - 60, now=now)
            self.assertIsInstance(events, list)
        finally:
            shutil.rmtree(td, ignore_errors=True)


class SendTelegramTest(unittest.TestCase):
    def test_a_chat_id_json_cannot_carry_is_coerced(self):
        sent = {}

        class _Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"{}"

        def fake_urlopen(req, timeout=None):
            sent["payload"] = req.data
            return _Resp()

        with mock.patch.object(urllib.request, "urlopen",
                               fake_urlopen):
            ok = dri.send_telegram("tok", {1, 2}, "the page text")
        self.assertTrue(ok)
        body = json.loads(sent["payload"])
        self.assertIsInstance(body["chat_id"], str)
        self.assertEqual(body["text"], "the page text")


class OracleServerChatLogTest(unittest.TestCase):
    """Cycle 3 target, except class:
    `ops/oracle_server.py:Handler.do_POST` (2) -- when the
    chat log write fails, the failure is a logged WARN and
    the ask is still answered: the conversation record is
    bookkeeping, not the answer. Driven over a real loopback
    socket against the deterministic Oracle, with the
    runner's `record_oracle_turn` made to raise.
    """

    def test_a_failed_chat_log_still_answers(self):
        import http.client
        import threading
        from runner import runner as R
        from runner.ops import oracle_server
        td = tempfile.mkdtemp(prefix="hp-plat-oracle-")
        httpd = None
        try:
            cfg = {"base_dir": td, "oracle_mode": "deterministic"}
            httpd = oracle_server.make_oracle_server(
                cfg, "127.0.0.1", 0, td)
            port = httpd.socket.getsockname()[1]
            thread = threading.Thread(target=httpd.serve_forever,
                                      daemon=True)
            thread.start()
            with mock.patch.object(
                    R, "record_oracle_turn",
                    side_effect=RuntimeError("the log is stuck")):
                conn = http.client.HTTPConnection(
                    "127.0.0.1", port, timeout=10)
                conn.request(
                    "POST", "/ask",
                    body=json.dumps({"question": "status?"}),
                    headers={
                        "Content-Type": "application/json",
                        "X-Oracle-Token": httpd.oracle_token})
                resp = conn.getresponse()
                raw = resp.read()
                conn.close()
            self.assertEqual(resp.status, 200)
            payload = json.loads(raw)
            self.assertTrue(
                "answer" in payload or "rejected" in payload)
        finally:
            if httpd is not None:
                httpd.shutdown()
                httpd.server_close()
            shutil.rmtree(td, ignore_errors=True)


class BinaryFlagArmsTest(unittest.TestCase):
    """Cycle 5 targets, logic class: the O_BINARY arms in
    `oracle/learning.py:_append` (255) and
    `oracle/senses.py:_write_private` (328) -- the same
    Windows flag as the audit writer's, simulated by the
    attribute's presence with value 0 (see the guard
    module's AuditBinaryFlagTest).
    """

    def test_learning_append_with_the_flag_present(self):
        from runner.oracle import learning
        td = tempfile.mkdtemp(prefix="hp-plat-oracle-")
        try:
            with mock.patch.object(os, "O_BINARY", 0, create=True):
                learning._append(td, {"kind": "lesson", "n": 1})
            files = os.listdir(td)
            self.assertEqual(len(files), 1)
            with open(os.path.join(td, files[0]),
                      encoding="utf-8") as fh:
                self.assertIn('"lesson"', fh.read())
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_write_private_with_the_flag_present(self):
        td = tempfile.mkdtemp(prefix="hp-plat-oracle-")
        try:
            path = os.path.join(td, "senses.jsonl")
            with mock.patch.object(os, "O_BINARY", 0, create=True):
                senses._write_private(path, b"one\n", append=False)
                senses._write_private(path, b"two\n", append=True)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"one\ntwo\n")
        finally:
            shutil.rmtree(td, ignore_errors=True)


class SampleTreePsTest(unittest.TestCase):
    """Cycle 5 target, logic class:
    `oracle/remediation.py:sample_tree_ps` (555) -- a root
    the ps table does not know at all still gets its
    (0.0, None) sample entry, from the fallback after the
    walk, not from a row.
    """

    def test_an_unknown_root_samples_as_zero(self):
        from types import SimpleNamespace
        from runner.oracle import remediation
        header_only = SimpleNamespace(stdout="  PID  PPID\n")
        sample = remediation.sample_tree_ps(
            999999, run=lambda *a, **k: header_only)
        self.assertEqual(sample, {999999: (0.0, None)})


if __name__ == "__main__":
    unittest.main()
