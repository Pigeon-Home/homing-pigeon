# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Windows platform proofs, from the Germany rig's first day
(2026-10-31). Each family pins a behavior that was exercised live
on a Windows runner and would otherwise rest on a chat report:

- The mailbox setup gate fired on a file-transport-only box and
  sat it forever at a setup prompt for a mailbox it never uses.
  The gate now applies only when the email transport is enabled.
- security.modes.job_user=enforce was accepted on Windows while
  the mechanism (a POSIX setuid demote) silently did nothing:
  jobs ran as the runner's own account. Enforce is now refused
  at startup, the way confinement=enforce already was, and audit
  leaves an audit record instead of silence.
- Confinement's startup refusal on a non-Linux platform is pinned
  here as the precedent the job_user refusal follows.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from runner import runner
from runner.guard import sandbox as SANDBOX
from runner.ops import setup as SETUP

SECRET = (
    "9f8e7d6c5b4a3928"
    "1f0e1d2c3b4a5968"
    "7766554433221100"
    "ffeeddccbbaa9988"
)


def _main_rig(argv, body):
    """Drive runner.main() headless: model, mailbox and poll
    stubbed, the REAL setup gate in place. Returns (code, poll,
    stderr)."""
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch.object(
        runner, "ensure_inference_ready"))
    stack.enter_context(mock.patch.object(
        runner, "update_llama_from_config"))
    stack.enter_context(mock.patch.object(runner, "connect_imap"))
    stack.enter_context(mock.patch.object(runner, "connect_smtp"))
    poll = stack.enter_context(mock.patch.object(
        runner, "poll_once", return_value=None))
    stack.enter_context(mock.patch.object(
        SETUP, "is_tty", return_value=False))
    stack.enter_context(mock.patch.object(
        runner, "_start_local_signals"))
    stack.enter_context(mock.patch.object(
        runner, "reload_hot_config", return_value=[]))
    directory = stack.enter_context(tempfile.TemporaryDirectory())
    body = dict(body, shared_secret=SECRET, base_dir=directory)
    path = os.path.join(directory, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    stack.enter_context(mock.patch.object(
        sys, "argv", ["runner", "--config", path, *argv]))
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = runner.main()
    finally:
        stack.close()
    return code, poll, err.getvalue()


class MailboxGateReasonTest(unittest.TestCase):
    """The gate guards mailbox auth; no email transport, no gate."""

    def test_file_only_without_mailbox_fields_passes(self):
        self.assertIsNone(SETUP.mailbox_gate_reason({}, ["file"]))

    def test_file_only_with_placeholder_mailbox_passes(self):
        cfg = {"mailbox_user": "homing-pigeon-runner@gmail.com",
               "mailbox_password": "paste-app-password-here-in-plaintext"}
        self.assertIsNone(SETUP.mailbox_gate_reason(cfg, ["file"]))

    def test_email_without_mailbox_user_trips(self):
        self.assertEqual(SETUP.mailbox_gate_reason({}, ["email"]),
                         "mailbox_user is not set")

    def test_email_among_several_transports_trips(self):
        self.assertEqual(
            SETUP.mailbox_gate_reason({}, ["file", "email"]),
            "mailbox_user is not set")

    def test_unknown_transport_set_keeps_the_gate(self):
        self.assertEqual(SETUP.mailbox_gate_reason({}, None),
                         "mailbox_user is not set")

    def test_email_with_mailbox_filled_passes(self):
        cfg = {"mailbox_user": "a@b.c", "mailbox_password": "pw"}
        self.assertIsNone(SETUP.mailbox_gate_reason(cfg, ["email"]))


class MailboxGateMainTest(unittest.TestCase):
    """The same, through main(): the live failure was the service
    never reaching its poll loop on a file-only box."""

    def test_file_only_box_reaches_the_poll(self):
        code, poll, _err = _main_rig(["--once"], {"transports": ["file"]})
        self.assertEqual(code, 0)
        self.assertTrue(poll.called)

    def test_email_box_without_mailbox_is_refused(self):
        code, poll, err = _main_rig(["--once"], {"transports": ["email"]})
        self.assertEqual(code, 2)
        self.assertIn("mailbox_user is not set", err)
        self.assertFalse(poll.called)

    def test_default_transports_without_mailbox_is_refused(self):
        code, poll, err = _main_rig(["--once"], {})
        self.assertEqual(code, 2)
        self.assertIn("mailbox_user is not set", err)
        self.assertFalse(poll.called)


class JobUserStartupProblemTest(unittest.TestCase):
    def _sec(self, mode):
        sec = mock.Mock()
        sec.sec_mode.return_value = mode
        return sec

    def _problem(self, mode, platform):
        cfg = {"security": {"modes": {"job_user": mode}}}
        with mock.patch.object(runner, "_security", self._sec(mode)):
            return runner._job_user_startup_problem(cfg, platform=platform)

    def test_enforce_on_win32_is_a_problem(self):
        problem = self._problem("enforce", "win32")
        self.assertIsNotNone(problem)
        self.assertIn("win32", problem)

    def test_enforce_on_linux_is_fine(self):
        self.assertIsNone(self._problem("enforce", "linux"))

    def test_audit_on_win32_is_not_refused(self):
        self.assertIsNone(self._problem("audit", "win32"))

    def test_off_on_win32_is_fine(self):
        self.assertIsNone(self._problem("off", "win32"))

    def test_no_security_module_is_fine(self):
        cfg = {"security": {"modes": {"job_user": "enforce"}}}
        with mock.patch.object(runner, "_security", None):
            self.assertIsNone(
                runner._job_user_startup_problem(cfg, platform="win32"))


class JobUserMainRefusalTest(unittest.TestCase):
    CFG = {"transports": ["file"],
           "security": {"modes": {"job_user": "enforce"},
                        "job_user": {"user": "root"}}}

    def test_enforce_on_win32_refuses_to_start(self):
        with mock.patch.object(sys, "platform", "win32"):
            code, poll, err = _main_rig(["--once"], dict(self.CFG))
        self.assertEqual(code, 2)
        self.assertIn("job_user", err)
        self.assertFalse(poll.called)

    def test_enforce_on_linux_starts(self):
        with mock.patch.object(sys, "platform", "linux"):
            code, poll, _err = _main_rig(["--once"], dict(self.CFG))
        self.assertEqual(code, 0)
        self.assertTrue(poll.called)


class JobUserWindowsAuditTest(unittest.TestCase):
    """At spawn time on Windows the demote cannot engage; audit
    mode still writes its record (the old code returned before
    the mode was even read)."""

    def _preexec_on_nt(self, mode):
        sec = mock.Mock()
        sec.sec_mode.return_value = mode
        cfg = {"security": {"modes": {"job_user": mode},
                            "job_user": {"user": "jobber"}}}
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work")
            os.makedirs(work, exist_ok=True)
            with mock.patch.object(runner, "_security", sec), \
                    mock.patch.object(os, "name", "nt"):
                out = runner._job_user_preexec(cfg, base, "job-9", work)
        return out, sec

    def test_audit_records_unsupported_platform(self):
        out, sec = self._preexec_on_nt("audit")
        self.assertIsNone(out)
        sec.write_audit_entry.assert_called()
        args = sec.write_audit_entry.call_args[0]
        self.assertEqual(args[2], "unsupported_platform")

    def test_enforce_records_too_if_it_ever_gets_here(self):
        out, sec = self._preexec_on_nt("enforce")
        self.assertIsNone(out)
        sec.write_audit_entry.assert_called()

    def test_off_is_silent(self):
        out, sec = self._preexec_on_nt("off")
        self.assertIsNone(out)
        sec.write_audit_entry.assert_not_called()


class ConfinementPlatformPinTest(unittest.TestCase):
    """The precedent: on a non-Linux platform the sandbox's
    startup problem names the platform before any bwrap trial."""

    def test_win32_names_linux_only(self):
        with mock.patch.object(os, "name", "nt"), \
                mock.patch.object(sys, "platform", "win32"):
            problem = SANDBOX.startup_problem()
        self.assertIsNotNone(problem)
        self.assertIn("Linux-only", problem)
        self.assertIn("win32", problem)


if __name__ == "__main__":
    unittest.main()
