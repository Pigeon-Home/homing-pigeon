#!/usr/bin/env python3
"""Stage 5 conformance for P6: Decision 1's configuration
behavior at startup and on live reload.

Startup is driven through the real main() with a real config
file on disk, in the shape of the audit-report test: the
--audit-report flag returns right after the configuration
gauntlet, so a clean config comes back 0 and a refuse-class
defect comes back 2 without entering the poll loop. Reload is
driven through the real reload_hot_config against a real file.
Clause numbers are properties.md's P6 clauses.

One sub-case is deliberately NOT pinned here: a boolean
written live for a hot key. Stage 4's record for P6 (finding
F2 there) shows the code reading it as 1 through int(value)
where the property says the default, named -- a divergence on
record, not a behavior this family asserts either way.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner  # noqa: E402
from runner.runner import main  # noqa: E402


def _startup(cfg_dict):
    """Run main() over a temp config; return (rc, stderr, logs)."""
    logs = []

    def grab(msg, level="INFO"):
        logs.append(str(msg))

    with tempfile.TemporaryDirectory() as td:
        cfg = {"base_dir": td}
        cfg.update(cfg_dict)
        path = os.path.join(td, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        err = io.StringIO()
        argv = ["runner", "--config", path, "--audit-report"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(runner, "log", grab), \
                redirect_stderr(err), \
                redirect_stdout(io.StringIO()):
            rc = main()
    return rc, err.getvalue(), logs


class StartupTest(unittest.TestCase):
    """Clauses 1 to 4 in the real startup path."""

    def test_an_absent_key_is_not_named(self):
        # Clause 1: nothing written, nothing defaulted, nothing
        # named -- startup proceeds.
        rc, _err, logs = _startup({})
        self.assertEqual(rc, 0)
        self.assertFalse(any("read as their default" in line
                             for line in logs), logs)

    def test_a_usable_value_is_not_named(self):
        # Clause 2's other half: written and usable -- used as
        # written, and not in the defaulted line.
        rc, _err, logs = _startup({"max_job_age_sec": 7200})
        self.assertEqual(rc, 0)
        self.assertFalse(any("max_job_age_sec" in line
                             for line in logs), logs)

    def test_an_unusable_default_class_value_is_named(self):
        # Clause 3: named in the startup line, and startup
        # proceeds on the documented default.
        rc, _err, logs = _startup({"max_job_age_sec": "nope"})
        self.assertEqual(rc, 0)
        self.assertTrue(any(
            "read as their default" in line
            and "max_job_age_sec" in line for line in logs), logs)

    def test_a_refuse_class_port_stops_startup_and_is_named(self):
        # Clause 4: the runner does not start, and the error
        # names the setting.
        rc, err, _logs = _startup({"imap_port": "banana"})
        self.assertEqual(rc, 2)
        self.assertIn("imap_port", err)

    def test_a_refuse_class_size_cap_stops_startup_and_is_named(self):
        rc, err, _logs = _startup({"max_job_bytes": "lots"})
        self.assertEqual(rc, 2)
        self.assertIn("max_job_bytes", err)

    def test_the_defaulted_line_is_printed_before_a_refusal(self):
        # Clauses 3 and 4 together, in the gauntlet's real
        # order: the default-class value is named in the
        # startup line even though startup then refuses on
        # the port.
        rc, err, logs = _startup({"max_job_age_sec": "nope",
                                  "imap_port": "banana"})
        self.assertEqual(rc, 2)
        self.assertIn("imap_port", err)
        self.assertTrue(any("max_job_age_sec" in line
                            for line in logs), logs)


def _reload(running, file_dict, state=None, pinned=None):
    """One reload cycle over a real file; returns
    (changed, logs, state). file_dict=None writes a bad file."""
    logs = []

    def grab(msg, level="INFO"):
        logs.append(str(msg))

    if state is None:
        state = {}
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            if file_dict is None:
                fh.write("{ not json")
            else:
                json.dump(file_dict, fh)
        with mock.patch.object(runner, "log", grab):
            changed = runner.reload_hot_config(
                running, path, state, pinned=pinned)
    return changed, logs, state


class ReloadTest(unittest.TestCase):
    """Clauses 5, 6, and 7 on the live path."""

    def test_an_unusable_hot_value_reads_as_the_default_named(self):
        # Clause 5, hot half.
        running = {"poll_interval_sec": 45}
        changed, logs, _state = _reload(
            running, {"poll_interval_sec": "fast"})
        self.assertEqual(running["poll_interval_sec"], 20)
        self.assertIn("poll_interval_sec", changed)
        self.assertTrue(any("poll_interval_sec" in line
                            for line in logs), logs)

    def test_a_usable_hot_value_applies_as_written(self):
        running = {"workers": 1}
        changed, _logs, _state = _reload(running, {"workers": 3})
        self.assertEqual(running["workers"], 3)
        self.assertIn("workers", changed)

    def test_an_unusable_default_class_value_is_replaced_and_named(self):
        # Clause 5, the rest of the class: task_timeout is in
        # no hot or live set; a bad live write replaces the
        # running value with the documented default (86400)
        # and the log names it.
        running = {"task_timeout": 1234}
        changed, logs, _state = _reload(
            running, {"task_timeout": "junk"})
        self.assertEqual(running["task_timeout"], 86400)
        self.assertIn("task_timeout", changed)
        self.assertTrue(any("task_timeout" in line
                            for line in logs), logs)

    def test_a_refuse_class_value_written_live_changes_nothing(self):
        # Clause 6: the size caps and the ports are not in any
        # reload set; the running binding stands until the
        # next start.
        running = {"max_job_bytes": 4194304, "imap_port": 993}
        changed, _logs, _state = _reload(
            running, {"max_job_bytes": 123, "imap_port": 1})
        self.assertEqual(running["max_job_bytes"], 4194304)
        self.assertEqual(running["imap_port"], 993)
        self.assertNotIn("max_job_bytes", changed)
        self.assertNotIn("imap_port", changed)

    def test_a_pinned_key_is_left_alone(self):
        running = {"workers": 1}
        changed, _logs, _state = _reload(
            running, {"workers": 9}, pinned={"workers"})
        self.assertEqual(running["workers"], 1)
        self.assertEqual(changed, [])

    def test_an_unchanged_file_is_not_reapplied(self):
        running = {"workers": 1}
        state = {}
        changed, _logs, state = _reload(
            running, {"workers": 4}, state=state)
        self.assertIn("workers", changed)
        # Same state, same file: the mtime marker says done.
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"workers": 4}, fh)
            state2 = {"mtime": os.path.getmtime(path)}
            changed2 = runner.reload_hot_config(
                running, path, state2)
        self.assertEqual(changed2, [])

    def test_a_bad_file_holds_the_marker_and_the_fix_applies(self):
        # Clause 7: an unreadable file changes nothing and
        # does not advance the state marker, so the fixed
        # file is picked up on the next cycle.
        running = {"workers": 1}
        state = {}
        changed, _logs, state = _reload(
            running, None, state=state)
        self.assertEqual(changed, [])
        self.assertEqual(running["workers"], 1)
        self.assertNotIn("mtime", state)
        changed, _logs, _state = _reload(
            running, {"workers": 5}, state=state)
        self.assertEqual(running["workers"], 5)
        self.assertIn("workers", changed)


if __name__ == "__main__":
    unittest.main()
