#!/usr/bin/env python3
"""Q14: every sense extension's alert delivery, parameterized.

The campaign hunted each extension's decide() through fifteen
shapes, but the step that hands the finished alert to the
runner -- sign it, then drop it in the local inbox or push it
to the local signal socket -- never ran in any of the thirteen
extensions the coverage map names. The copies are one shape by
design (the Lab Results shape), so this is one parameterized
test over all thirteen, per docs/extend/senses.md:

  - the alert the runner files is the alert the extension
    decided (same sensor, title, signal), and its signature
    verifies under the sense's own key;
  - delivery goes both ways the contract offers: the local
    inbox (file) and the loopback signal socket;
  - a missing secret delivers nothing and says so (the
    return is None, not zero);
  - a delivery failure -- an inbox that cannot be written, a
    socket that refuses -- is reported per alert and counted
    as not delivered, never silently dropped and never fatal.
"""
import importlib.util
import json
import os
import secrets
import socket
import sys
import tempfile
import threading
import types
import unittest
from contextlib import redirect_stderr
from io import StringIO

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import senses  # noqa: E402
from runner.runner import (  # noqa: E402
    _ingest_local_envelope, _scan_local_inbox)

EXTENSIONS = [
    ("aide-feed", "aide_feed.py"),
    ("job-fuzz", "job_fuzz.py"),
    ("job-watcher", "job_watcher.py"),
    ("latency-post", "latency_post.py"),
    ("release-drop", "release_drop.py"),
    ("resource-sentinel", "resource_sentinel.py"),
    ("sky-watcher", "sky_watcher.py"),
    ("softflowd-feed", "softflowd_feed.py"),
    ("suricata-feed", "suricata_feed.py"),
    ("sysmon-feed", "sysmon_feed.py"),
    ("training-watch", "training_watch.py"),
    ("wazuh-feed", "wazuh_feed.py"),
    ("zeek-feed", "zeek_feed.py"),
]

ROOT_SECRET = secrets.token_hex(32)
SENSE_SECRET = secrets.token_hex(32)
ENV_NAME = "HP_Q14_SENSE_SECRET"
KEY_ID = "q14-sense"


def _load(dirname, filename):
    path = os.path.join(REPO, "runner", "extensions", dirname,
                        filename)
    spec = importlib.util.spec_from_file_location(
        "q14_" + filename[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _manifest(dirname):
    path = os.path.join(REPO, "runner", "extensions", dirname,
                        "extension.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _args(**kw):
    base = {"secret_env": ENV_NAME, "key_id": KEY_ID,
            "local_port": None, "local_dir": None,
            "state": None, "manifest": None, "readings": None}
    base.update(kw)
    return types.SimpleNamespace(**base)


class SenseDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ[ENV_NAME] = SENSE_SECRET

    def _runner_cfg(self, sensor):
        return {"shared_secret": ROOT_SECRET,
                "additional_secrets": {KEY_ID: SENSE_SECRET},
                "sensors": {sensor: {"enabled": True,
                                     "key_id": KEY_ID}}}

    def _alert(self, dirname, sensor):
        signals = _manifest(dirname).get("signals") or []
        signal = signals[0]["name"] if signals else None
        return {"sensor": sensor, "severity": "high",
                "title": "Q14 delivery probe",
                "signal": signal, "detail": {"probe": "q14"}}

    def _stored(self, base, sensor):
        return [a for a in senses.load_alerts(base, limit=50)
                if a.get("sensor") == sensor
                and a.get("title") == "Q14 delivery probe"]

    def test_delivery_both_styles_and_failures(self):
        for dirname, filename in EXTENSIONS:
            with self.subTest(extension=dirname):
                self._one_extension(dirname, filename)

    def _one_extension(self, dirname, filename):
        mod = _load(dirname, filename)
        sensor = _manifest(dirname)["name"]
        alert = self._alert(dirname, sensor)
        cfg = self._runner_cfg(sensor)
        base = tempfile.mkdtemp(prefix="hp-q14-")

        # File style: the envelope lands in the runner's
        # local inbox, and the runner files exactly the alert
        # the extension decided.
        with redirect_stderr(StringIO()):
            n = mod._deliver_local([alert],
                                   _args(local_dir=base))
        self.assertEqual(n, 1)
        inbox = os.path.join(base, "local-inbox")
        names = os.listdir(inbox)
        self.assertEqual(len(names), 1)
        with open(os.path.join(inbox, names[0]),
                  encoding="utf-8") as fh:
            envelope = json.loads(fh.read())
        self.assertEqual(envelope["sensor"], sensor)
        self.assertEqual(envelope["title"], alert["title"])
        self.assertEqual(envelope["kind"], "sensor_alert")
        self.assertEqual(_scan_local_inbox(cfg, base), 1)
        self.assertEqual(os.listdir(inbox), [])
        self.assertEqual(len(self._stored(base, sensor)), 1)

        # Socket style: the bytes pushed to the loopback
        # listener are the envelope the runner verifies and
        # files.
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        captured = []

        def serve():
            conn, _addr = srv.accept()
            data = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            captured.append(data.decode("utf-8"))
            conn.close()
            srv.close()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        with redirect_stderr(StringIO()):
            n = mod._deliver_local(
                [alert], _args(local_dir=base, local_port=port))
        thread.join(timeout=10)
        self.assertEqual(n, 1)
        self.assertEqual(len(captured), 1)
        record = _ingest_local_envelope(cfg, base, captured[0],
                                         "socket")
        self.assertIsNotNone(record)
        self.assertEqual(record["sensor"], sensor)
        self.assertEqual(record["title"], alert["title"])

        # No secret in the named env var: not set up, nothing
        # delivered, and the return says so (None, not 0).
        with redirect_stderr(StringIO()):
            n = mod._deliver_local(
                [alert], _args(local_dir=base,
                               secret_env="HP_Q14_UNSET"))
        self.assertIsNone(n)
        self.assertEqual(os.listdir(inbox), [])

        # An inbox that cannot be written: the failure is
        # reported and counted as not delivered.
        blocker = os.path.join(base, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("not a directory")
        err = StringIO()
        with redirect_stderr(err):
            n = mod._deliver_local([alert],
                                   _args(local_dir=blocker))
        self.assertEqual(n, 0)
        self.assertIn("delivery failed", err.getvalue())

        # A socket that refuses: same contract.
        err = StringIO()
        with redirect_stderr(err):
            n = mod._deliver_local(
                [alert], _args(local_dir=base, local_port=1))
        self.assertEqual(n, 0)
        self.assertIn("delivery failed", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
