"""End-to-end for the IDS collector feed adapters.

Two legs through the real local-signal path -- producer main()
over the shipped fixture, signed envelopes dropped into the
local inbox, the real ingest (R._scan_local_inbox) filing the
alerts:

- osquery-feed: the light-pack fixture files four alerts
  (process/user/listener differentials). Its severities top
  out at medium BY DESIGN -- osquery differentials carry no
  severity of their own, and the honest mapping never reaches
  high -- so the wake gate correctly stays shut: no brief.
  That restraint is pinned here, not worked around.
- falco-feed: the fixture's Critical lines file falco_critical
  at high severity, which crosses the wake gate and files a
  deterministic wake brief (the configs carry no inference,
  so the brief is the no_inference fallback) -- the feed
  family's fixture -> ingest -> wake brief leg.

No live collectors, no live network: fixtures only.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner import senses as S  # noqa: E402

DEFAULT_SECRET = "ids-e2e-default-" + "0123456789abcdef" * 2
OQ_SECRET = "ids-e2e-osquery-" + "1122334455667788" * 2
FALCO_SECRET = "ids-e2e-falco-" + "2233445566778899" * 2


def _load(folder, filename, modname):
    spec = importlib.util.spec_from_file_location(
        modname, os.path.join(REPO, "extensions",
                              folder, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OQ = _load("osquery-feed", "osquery_feed.py", "osquery_feed_example")
FALCO = _load("falco-feed", "falco_feed.py", "falco_feed_example")


class FeedFixture(unittest.TestCase):
    folder = None       # example folder name
    mod = None          # producer module
    sensor = None       # manifest sensor name
    secret = None
    key_id = None
    fixture = None      # fixture file inside the folder

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(os.path.join(REPO, "extensions",
                                     self.folder),
                        os.path.join(self.ext_root, self.folder))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {self.key_id: self.secret},
            "key_policies": {
                self.key_id: {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                self.sensor: {"enabled": True, "key_id": self.key_id,
                              "weight": 1.0, "profile": {}},
            },
            "extensions_dir": self.ext_root,
        }
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)
        self.state_path = os.path.join(self._tmp.name, "state.json")

    def tearDown(self):
        for th in threading.enumerate():
            if th.name == "oracle-brief":
                th.join(timeout=5)
        last = None
        for _ in range(20):
            try:
                self._tmp.cleanup()
                return
            except OSError as exc:
                last = exc
                time.sleep(0.05)
        if last is not None:
            raise last

    def run_producer(self):
        fixture = os.path.join(REPO, "extensions",
                               self.folder, "fixtures", self.fixture)
        env = {"HOMING_PIGEON_SENSOR_SECRET": self.secret}
        with unittest.mock.patch.dict(os.environ, env):
            return self.mod.main(
                ["--log-file", fixture,
                 "--local-dir", self.base,
                 "--key-id", self.key_id,
                 "--state", self.state_path])

    def inbox_names(self):
        inbox = os.path.join(self.base, "local-inbox")
        if not os.path.isdir(inbox):
            return []
        return sorted(os.listdir(inbox))

    def brief_lines(self):
        path = os.path.join(self.base, "oracle-briefs.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln.strip()]

    def wait_briefs(self, n, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            lines = self.brief_lines()
            if len(lines) >= n:
                return lines
            time.sleep(0.05)
        self.fail(f"expected {n} brief(s), got {self.brief_lines()}")


class OsqueryFeedEndToEndTest(FeedFixture):
    folder = "osquery-feed"
    mod = OQ
    sensor = "osquery_feed"
    secret = OQ_SECRET
    key_id = "osquery-key"
    fixture = "light-pack.jsonl"

    def test_light_pack_fixture_files_alerts_and_stays_below_the_gate(self):
        self.assertEqual(self.run_producer(), 0)
        self.assertEqual(len(self.inbox_names()), 4)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 4)
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 4)
        for rec in recs:
            self.assertEqual(rec["sensor"], "osquery_feed")
            self.assertEqual(rec["source"], "local")
            self.assertEqual(rec["extension"], "osquery_feed")
        by_kind = {}
        for rec in recs:
            detail = json.loads(rec["detail"]) \
                if isinstance(rec.get("detail"), str) \
                else rec.get("detail") or {}
            by_kind.setdefault(detail.get("kind"), []).append(rec)
        # The new user and the new listener are the mediums; the
        # process add and the listener removal ride at info.
        # Select by signal, never by position: the two listener
        # records arrive in inbox order, which is not stable.
        self.assertEqual(by_kind["user"][0]["signal"], "osquery_added")
        self.assertEqual(by_kind["user"][0]["severity"], "medium")
        listener_by_signal = {r["signal"]: r for r in by_kind["listener"]}
        self.assertEqual(
            listener_by_signal["osquery_added"]["severity"], "medium")
        self.assertEqual(
            listener_by_signal["osquery_removed"]["severity"], "info")
        self.assertEqual(by_kind["process"][0]["severity"], "info")
        # Nothing the light pack reports reaches high, so the
        # wake gate stays shut -- by design, not by accident.
        for rec in recs:
            self.assertFalse(R._wake_gate_decide(self.cfg, rec))
        self.assertEqual(self.brief_lines(), [])


class FalcoFeedEndToEndTest(FeedFixture):
    folder = "falco-feed"
    mod = FALCO
    sensor = "falco_feed"
    secret = FALCO_SECRET
    key_id = "falco-key"
    fixture = "falco-alerts.jsonl"

    def test_critical_fixture_files_and_wakes_a_brief(self):
        self.assertEqual(self.run_producer(), 0)
        self.assertEqual(len(self.inbox_names()), 3)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 3)
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 3)
        crits = [r for r in recs if r["signal"] == "falco_critical"]
        self.assertEqual(len(crits), 2)
        for rec in crits:
            self.assertEqual(rec["sensor"], "falco_feed")
            self.assertEqual(rec["source"], "local")
            self.assertEqual(rec["extension"], "falco_feed")
            self.assertEqual(rec["severity"], "high")
        lines = self.wait_briefs(1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "falco_critical")
        self.assertEqual(brief["status"], "no_inference")


if __name__ == "__main__":
    unittest.main()
