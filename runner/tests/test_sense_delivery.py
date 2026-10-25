#!/usr/bin/env python3
"""Q14: every sense extension's alert delivery, parameterized.

The campaign hunted each extension's decide() through fifteen
shapes, but the step that hands the finished alert to the
runner -- sign it, then drop it in the local inbox or push it
to the local signal socket -- never ran in any of the
extensions the coverage map names. The copies are one shape by
design (the Lab Results shape), so this is one parameterized
test over all twenty-eight, per docs/extend/senses.md:

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
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import senses  # noqa: E402
from runner.runner import (  # noqa: E402
    _ingest_local_envelope, _scan_local_inbox)

EXTENSIONS = [
    ("aide-feed", "aide_feed.py"),
    ("airwaves", "airwaves.py"),
    ("backup-freshness", "backup_freshness.py"),
    ("cert-sentinel", "cert_sentinel.py"),
    ("crash-watch", "crash_watch.py"),
    ("failed-login-watch", "failed_login_watch.py"),
    ("falco-feed", "falco_feed.py"),
    ("job-fuzz", "job_fuzz.py"),
    ("job-watcher", "job_watcher.py"),
    ("lab-results", "lab_results.py"),
    ("latency-post", "latency_post.py"),
    ("log-sentinel", "log_sentinel.py"),
    ("osquery-feed", "osquery_feed.py"),
    ("pi-health", "pi_health.py"),
    ("port-watch", "port_watch.py"),
    ("release-drop", "release_drop.py"),
    ("resource-sentinel", "resource_sentinel.py"),
    ("service-watch", "service_watch.py"),
    ("sky-watcher", "sky_watcher.py"),
    ("softflowd-feed", "softflowd_feed.py"),
    ("suricata-feed", "suricata_feed.py"),
    ("sysmon-feed", "sysmon_feed.py"),
    ("training-watch", "training_watch.py"),
    ("tripwire", "tripwire.py"),
    ("usb-arrivals", "usb_arrivals.py"),
    ("wazuh-feed", "wazuh_feed.py"),
    ("wire-arrivals", "wire_arrivals.py"),
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


class UnimportableRepoTest(unittest.TestCase):
    """The same refusal as OutsideTheCloneTest, in-process
    for every sense on the roster: coverage run
    40183585961 still showed the refusal lines unrun in
    all nineteen copies then on it, because the subprocess proof
    measures its lines in a child whose coverage data
    never reaches the map. Here the runner's producer
    module is made unimportable through the module
    table (and the package attribute the from-import
    consults first), and each copy must answer None and
    print the refusal naming itself.
    """

    def test_every_sense_refuses_when_the_repo_cannot_import(self):
        import runner.ops as ops_pkg
        had_attr = hasattr(ops_pkg, "extensions")
        saved = getattr(ops_pkg, "extensions", None)
        if had_attr:
            delattr(ops_pkg, "extensions")
        try:
            with mock.patch.dict(
                    sys.modules,
                    {"runner.ops.extensions": None}):
                for dirname, filename in EXTENSIONS:
                    with self.subTest(sense=dirname):
                        mod = _load(dirname, filename)
                        err = StringIO()
                        with redirect_stderr(err):
                            got = mod._deliver_local(
                                [], _args())
                        self.assertIsNone(got)
                        self.assertIn(
                            "local delivery needs the "
                            "homing-pigeon repo importable",
                            err.getvalue())
        finally:
            if had_attr:
                ops_pkg.extensions = saved


class RepoPathInsertTest(unittest.TestCase):
    """Queue A residue in every copy of _deliver_local:
    the sys.path insert at its top never fired in the
    full suite (coverage run 40185441322 left exactly
    that one line per copy), because in every suite
    process the repo root is already on the path by the
    time any delivery runs. Scrubbed of it, each sense's
    delivery must put it back before it imports -- the
    standalone-run promise the insert exists for.
    """

    def test_every_sense_reinserts_the_repo_root(self):
        root = os.path.normpath(REPO)
        for dirname, filename in EXTENSIONS:
            with self.subTest(sense=dirname):
                mod = _load(dirname, filename)
                saved = list(sys.path)
                sys.path[:] = [
                    p for p in sys.path
                    if os.path.realpath(p or os.getcwd())
                    != os.path.realpath(REPO)]
                try:
                    with redirect_stderr(StringIO()):
                        got = mod._deliver_local(
                            [], _args(
                                secret_env="HP_Q14_UNSET"))
                    self.assertIsNone(got)
                    self.assertIn(root, sys.path)
                finally:
                    sys.path[:] = saved


class OutsideTheCloneTest(unittest.TestCase):
    """Queue A residue in every copy of _deliver_local: the
    branch that refuses when the homing-pigeon repo is not
    importable. It runs only when an extension finds itself
    outside a clone, so the test copies one extension out
    and drives it in a subprocess with nothing on the path:
    delivery is None, the reason names the sense and the
    clone, and nothing is delivered.
    """

    def test_delivery_outside_a_clone_refuses_by_name(self):
        import shutil
        import subprocess
        import tempfile
        src = os.path.join(REPO, "runner", "extensions",
                           "port-watch", "port_watch.py")
        with tempfile.TemporaryDirectory() as d:
            copy = os.path.join(d, "port_watch.py")
            shutil.copy2(src, copy)
            code = (
                "import importlib.util, types\n"
                "spec = importlib.util.spec_from_file_location("
                "'pw', %r)\n"
                "m = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(m)\n"
                "args = types.SimpleNamespace("
                "secret_env='NOPE', key_id='', local_port=None, "
                "local_dir=%r)\n"
                "print('DELIVERED', m._deliver_local([], args))\n"
                % (copy, d))
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            proc = subprocess.run(
                [sys.executable, "-c", code], cwd=d, env=env,
                capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("DELIVERED None", proc.stdout)
        self.assertIn("port-watch: local delivery needs the "
                      "homing-pigeon repo importable", proc.stderr)


class LocalEnvelopeIssuedAtTest(unittest.TestCase):
    """Queue A refill: _ingest_local_envelope_inner's
    secret-build and issued_at legs (coverage run
    40189608702: 5 lines on both platforms). The local
    intake's contract is the mail intake's, stated in
    AGENTS.md's "Do not emit" table and PROTOCOL.md:
    an issued_at that does not parse, and one that
    parses without a timezone, are each rejected --
    and a config whose secrets cannot be built
    rejects every envelope before any of them is
    read.
    """

    def _cfg(self):
        return {"shared_secret": ROOT_SECRET,
                "additional_secrets": {KEY_ID: SENSE_SECRET},
                "key_policies": {
                    KEY_ID: {"allowed_kinds": ["sensor_alert"]}},
                "sensors": {"lab_results": {
                    "enabled": True, "key_id": KEY_ID,
                    "weight": 1.0, "profile": {}}}}

    def _text(self, issued_at):
        from runner.ops import extensions as ext_ops
        payload = ext_ops.build_sensor_alert(
            "lab_results", "info", "issued-at probe",
            key_id=KEY_ID, signal="experiment_finished")
        payload["issued_at"] = issued_at
        return ext_ops.sign_envelope(payload, SENSE_SECRET)

    def _ingest(self, cfg, text):
        with tempfile.TemporaryDirectory() as base:
            with redirect_stderr(StringIO()):
                record = _ingest_local_envelope(
                    cfg, base, text, "file")
            stored = senses.load_alerts(base, limit=50)
        return record, stored

    def test_an_unbuildable_secret_set_rejects_everything(self):
        record, stored = self._ingest(
            {"shared_secret": "short"}, "any envelope")
        self.assertIsNone(record)
        self.assertEqual(stored, [])

    def test_an_unparseable_issued_at_is_rejected(self):
        record, stored = self._ingest(
            self._cfg(), self._text("not-a-date"))
        self.assertIsNone(record)
        self.assertEqual(stored, [])

    def test_a_naive_issued_at_is_rejected(self):
        record, stored = self._ingest(
            self._cfg(), self._text("2026-10-15T12:00:00"))
        self.assertIsNone(record)
        self.assertEqual(stored, [])

    def test_a_zoned_issued_at_is_stored(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        record, stored = self._ingest(
            self._cfg(), self._text(now))
        self.assertIsNotNone(record)
        self.assertEqual(len(stored), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
