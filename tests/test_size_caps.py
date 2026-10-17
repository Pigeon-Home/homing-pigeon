#!/usr/bin/env python3
"""M1b tests: max_job_bytes and max_script_bytes caps."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))

from runner.runner import poll_once  # noqa: E402
from tests.security_parity import (  # noqa: E402
    EXTRA_SECRET,
    SECRET,
    FakeIMAP,
    FakeSMTP,
    _email,
    _payload,
    base_config,
)


class SizeCapTest(unittest.TestCase):
    def _run(self, cfg_extra, payload):
        tmpdir = tempfile.mkdtemp(prefix="hp-cap-")
        cfg = base_config(tmpdir)
        cfg.update(cfg_extra)
        mail = _email(payload)
        imap = FakeIMAP([mail])
        smtp = FakeSMTP()
        poll_once(cfg, tmpdir, {}, os.path.join(tmpdir, "seen.json"),
                  imap=imap, smtp=smtp)
        return imap, smtp, len(mail)

    def test_job_cap_boundary(self):
        payload = _payload("cap-01", kind="exec", script="echo hi")
        n = len(_email(payload))
        # just over -> rejected, marked seen, no result mail
        imap, smtp, _ = self._run({"max_job_bytes": n - 1}, payload)
        self.assertEqual(len(smtp.sent), 0)
        self.assertEqual(imap.flagged, ["1"])
        # just under -> runs
        imap, smtp, _ = self._run({"max_job_bytes": n}, payload)
        self.assertEqual(len(smtp.sent), 1)

    def test_script_cap_boundary(self):
        script = "echo " + "x" * 100
        n = len(script.encode("utf-8"))
        payload = _payload("cap-02", kind="exec", script=script)
        imap, smtp, _ = self._run({"max_script_bytes": n - 1}, payload)
        self.assertEqual(len(smtp.sent), 0)
        self.assertEqual(imap.flagged, ["1"])
        imap, smtp, _ = self._run({"max_script_bytes": n}, payload)
        self.assertEqual(len(smtp.sent), 1)

    def test_zero_disables(self):
        payload = _payload("cap-03", kind="exec",
                           script="echo " + "x" * 200000)
        imap, smtp, _ = self._run(
            {"max_job_bytes": 0, "max_script_bytes": 0}, payload)
        self.assertEqual(len(smtp.sent), 1)

    def test_bad_signature_still_checked_first(self):
        # The job cap sits before the signature check; an oversized
        # mail is rejected on size even with a bad signature.
        payload = _payload("cap-04", kind="exec",
                           script="echo " + "x" * 5000)
        tmpdir = tempfile.mkdtemp(prefix="hp-cap-")
        cfg = base_config(tmpdir)
        cfg["max_job_bytes"] = 100
        mail = _email(payload, secret=EXTRA_SECRET)
        imap = FakeIMAP([mail])
        smtp = FakeSMTP()
        poll_once(cfg, tmpdir, {}, os.path.join(tmpdir, "seen.json"),
                  imap=imap, smtp=smtp)
        self.assertEqual(len(smtp.sent), 0)
        self.assertEqual(imap.flagged, ["1"])


class CapConfigTest(unittest.TestCase):
    def _main_with_caps(self, **caps):
        from runner.runner import main
        with tempfile.TemporaryDirectory() as d:
            cfg_path = os.path.join(d, "config.json")
            cfg = {
                "mailbox_user": "a@b.c",
                "mailbox_password": "p",
                "shared_secret": "ab" * 32,
            }
            cfg.update(caps)
            json.dump(cfg, open(cfg_path, "w"))
            with mock.patch.object(sys, "argv",
                                   ["runner", "--config", cfg_path]):
                return main()

    def test_negative_cap_stops_startup(self):
        self.assertEqual(self._main_with_caps(max_job_bytes=-1), 2)

    def test_non_integer_cap_stops_startup(self):
        self.assertEqual(self._main_with_caps(max_script_bytes="big"), 2)

    def test_zero_cap_ok(self):
        from runner.runner import _validate_size_caps
        self.assertIsNone(_validate_size_caps({"max_job_bytes": 0}))
        self.assertIsNone(
            _validate_size_caps({"max_script_bytes": 1048576}))
        self.assertIsNone(_validate_size_caps({}))
        self.assertIsNotNone(
            _validate_size_caps({"max_job_bytes": -1}))
        self.assertIsNotNone(
            _validate_size_caps({"max_script_bytes": "big"}))
        self.assertIsNotNone(
            _validate_size_caps({"max_job_bytes": True}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
