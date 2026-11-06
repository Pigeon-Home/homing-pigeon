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
import string
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
    # A body that states no security block gets the platform
    # gates stated off: under the lockdown default they read
    # enforce and refuse this host before the gate under test.
    # A body that states its own block (the job_user refusal
    # tests) keeps it untouched.
    body.setdefault("security", {"modes": {"confinement": "off",
                                           "job_user": "off"}})
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
           # Confinement stated off: it is checked first, and
           # these tests are about the job_user refusal naming
           # job_user, on win32 and at startup on Linux.
           "security": {"modes": {"job_user": "enforce",
                                  "confinement": "off"},
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


class MailboxGateShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 42: the mailbox setup
    gate demanded mailbox auth from a runner with no email
    transport, hanging it at an unseen prompt (found live
    31-Oct-2026 on a file-transport-only box; fixed 8174b51f --
    the gate routes through setup.mailbox_gate_reason, which
    applies needs_setup only when the email transport is among
    the enabled transports, and keeps the gate when the enabled
    set could not be read). The MailboxGate tests above pin the
    headline shapes; this family scattershots everything around
    them: every field the gate reads, the transports argument in
    every container and spelling, the example placeholders in
    both mailbox fields, the auth field's exact oauth reading,
    inert neighbour fields, and the gate through main() in its
    string and mixed transport spellings. One regression test
    was never going to be enough for a bug that sat a live
    service at a prompt nobody could see.

    Per-field enumeration: the gate reads exactly these fields
    -- the config object itself, mailbox_user, mailbox_password,
    auth, oauth_client_id and oauth_refresh_token (the last
    three through needs_setup), and the transports argument
    (the enabled set main() hands it). Each gets its own
    generated test below, sweeping that field alone while the
    others stand still; the config's own "transports" key is
    pinned as NOT one of them (the argument, not the key, is
    what the gate reads).

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: the text surfaces --
    the transport name "email", mailbox_user, and the auth
    value "oauth" -- get bookended variants: all 32 printable
    ASCII symbols (string.punctuation) at the front and at the
    back, as singles, matched pairs, mismatched pairs and
    symbol-only strings, plus NUL, tab, CR and LF at both ends;
    and run lengths: runs of the odd character, and runs of
    ordinary characters with the odd one at the front, the back
    and the middle.

    Proof of work (6-Nov-2026). The unit tests are the 50
    methods of this class: 27 hand-written seams (3 of them
    through main()), 7 generated per-field tests, 12 bookend
    sweeps and 4 run-length sweeps. The fuzzing was executed,
    not just the tests written: runner/tools/de_dust_corpus.py
    grow --target mail --rounds 400 --seed 20261143, run
    locally against the banked mail corpus (26 entries).
    Result: 400 rounds, 0 crashes, 0 slow, arcs unchanged at
    131, slowest try 500 ms; the gate demanding auth from an
    email-less runner did not recur. The grow's bookkeeping writes were
    reverted and are not banked (banking is the rigs' hourly
    job); this record is the run's proof. None of this is
    exotic: it is combinatorics -- systematically trying the
    combinations a hand-written list would never reach, then
    pinning each answer as a test."""

    PW = {"mailbox_user": "a@b.c", "mailbox_password": "pw"}
    OAUTH = {"mailbox_user": "a@b.c", "auth": "oauth",
             "oauth_client_id": "cid", "oauth_refresh_token": "tok"}
    USER_PH = SETUP.EXAMPLE_PLACEHOLDERS["mailbox_user"]
    PW_PH = SETUP.EXAMPLE_PLACEHOLDERS["mailbox_password"]

    @staticmethod
    def _gate(cfg, transports):
        return SETUP.mailbox_gate_reason(cfg, transports)

    # -- hand-written seams --

    def test_empty_transport_list_skips_the_gate(self):
        self.assertIsNone(self._gate({}, []))
        self.assertIsNone(self._gate({}, ["file", "nats", "dtls"]))

    def test_email_in_any_position_trips_the_gate(self):
        for transports in (["email"], ["email", "file"],
                           ["file", "email"],
                           ["nats", "email", "file"]):
            self.assertEqual(self._gate({}, transports),
                             "mailbox_user is not set", transports)

    def test_unknown_transport_set_keeps_the_gate_for_each_reason(self):
        self.assertEqual(self._gate({}, None),
                         "mailbox_user is not set")
        self.assertEqual(self._gate({"mailbox_user": "a@b.c"}, None),
                         "mailbox_password is not set")
        oauth = {"mailbox_user": "a@b.c", "auth": "oauth",
                 "oauth_client_id": "cid"}
        self.assertEqual(self._gate(oauth, None),
                         "no OAuth refresh token (sign-in never completed)")
        self.assertEqual(self._gate([], None), "config is not an object")

    def test_non_dict_config_skips_without_email_and_trips_with(self):
        for cfg in ([], "cfg", 7, None, True):
            self.assertIsNone(self._gate(cfg, ["file"]), repr(cfg))
            self.assertEqual(self._gate(cfg, ["email"]),
                             "config is not an object", repr(cfg))

    def test_transports_as_a_string_reads_by_substring(self):
        # main() always hands a list, but the gate's own seam
        # only does a membership test: a bare string answers by
        # substring, and the family pins that reading as-is.
        self.assertIsNone(self._gate({}, "file"))
        self.assertIsNone(self._gate({}, ""))
        self.assertEqual(self._gate({}, "email"),
                         "mailbox_user is not set")
        self.assertEqual(self._gate({}, "file,email"),
                         "mailbox_user is not set")

    def test_transports_container_shapes(self):
        self.assertIsNone(self._gate({}, {"file"}))
        self.assertIsNone(self._gate({}, ("file", "nats")))
        self.assertEqual(self._gate({}, {"email"}),
                         "mailbox_user is not set")
        self.assertEqual(self._gate({}, ("email",)),
                         "mailbox_user is not set")
        self.assertEqual(self._gate({}, {"email": "x"}),
                         "mailbox_user is not set")
        self.assertIsNone(self._gate({}, frozenset(["file"])))

    def test_email_name_is_exact_in_case_and_spacing(self):
        for name in ("Email", "EMAIL", "eMail", " email", "email ",
                     "e-mail", "email\n", "email\x00", "mail"):
            self.assertIsNone(self._gate({}, [name]), repr(name))

    def test_duplicate_email_entries_trip_the_same_once(self):
        self.assertEqual(self._gate({}, ["email", "email"]),
                         "mailbox_user is not set")
        self.assertEqual(self._gate(dict(self.PW), ["email", "email"]),
                         None)

    def test_mailbox_user_placeholder_counts_as_unset(self):
        cfg = {"mailbox_user": self.USER_PH, "mailbox_password": "pw"}
        self.assertEqual(self._gate(cfg, ["email"]),
                         "mailbox_user is not set")

    def test_mailbox_password_placeholder_counts_as_unset(self):
        cfg = {"mailbox_user": "a@b.c", "mailbox_password": self.PW_PH}
        self.assertEqual(self._gate(cfg, ["email"]),
                         "mailbox_password is not set")

    def test_both_placeholders_report_the_user_first(self):
        cfg = {"mailbox_user": self.USER_PH,
               "mailbox_password": self.PW_PH}
        self.assertEqual(self._gate(cfg, ["email"]),
                         "mailbox_user is not set")

    def test_falsy_mailbox_user_shapes_are_unset(self):
        for user in ("", None, 0, False, [], {}):
            cfg = {"mailbox_user": user, "mailbox_password": "pw"}
            self.assertEqual(self._gate(cfg, ["email"]),
                             "mailbox_user is not set", repr(user))

    def test_truthy_nonstring_mailbox_user_counts_as_set(self):
        for user in (["a@b.c"], 123, {"a": 1}, " "):
            cfg = {"mailbox_user": user, "mailbox_password": "pw"}
            self.assertIsNone(self._gate(cfg, ["email"]), repr(user))

    def test_password_auth_ignores_the_oauth_fields(self):
        for cfg in (dict(self.PW),
                    dict(self.PW, oauth_client_id=""),
                    dict(self.PW, oauth_refresh_token=""),
                    dict(self.PW, auth="password",
                         oauth_client_id=None)):
            self.assertIsNone(self._gate(cfg, ["email"]), cfg)

    def test_oauth_auth_ignores_the_mailbox_password(self):
        for cfg in (dict(self.OAUTH),
                    dict(self.OAUTH, mailbox_password=""),
                    dict(self.OAUTH, mailbox_password=self.PW_PH)):
            self.assertIsNone(self._gate(cfg, ["email"]), cfg)

    def test_oauth_missing_client_is_reported_before_the_token(self):
        base = {"mailbox_user": "a@b.c", "auth": "oauth"}
        self.assertEqual(self._gate(base, ["email"]),
                         "oauth_client_id is not set")
        self.assertEqual(
            self._gate(dict(base, oauth_refresh_token="tok"), ["email"]),
            "oauth_client_id is not set")
        self.assertEqual(
            self._gate(dict(base, oauth_client_id="cid"), ["email"]),
            "no OAuth refresh token (sign-in never completed)")

    def test_auth_reading_is_lowercased_but_not_stripped(self):
        for auth in ("OAuth", "OAUTH", "oAuTh"):
            cfg = {"mailbox_user": "a@b.c", "auth": auth,
                   "oauth_client_id": "cid"}
            self.assertEqual(
                self._gate(cfg, ["email"]),
                "no OAuth refresh token (sign-in never completed)", auth)
        for auth in ("oauth ", " oauth", "oauth\n", "oauth2"):
            cfg = {"mailbox_user": "a@b.c", "auth": auth,
                   "mailbox_password": "pw", "oauth_client_id": "cid"}
            self.assertIsNone(self._gate(cfg, ["email"]), repr(auth))

    def test_auth_nonstring_values_read_as_password_auth(self):
        for auth in (123, None, True, ["oauth"], {"a": 1}):
            cfg = {"mailbox_user": "a@b.c", "auth": auth,
                   "mailbox_password": "pw"}
            self.assertIsNone(self._gate(cfg, ["email"]), repr(auth))
            cfg.pop("mailbox_password")
            self.assertEqual(self._gate(cfg, ["email"]),
                             "mailbox_password is not set", repr(auth))

    def test_the_user_reason_precedes_every_auth_specific_reason(self):
        for cfg in ({"auth": "oauth"},
                    {"auth": "oauth", "oauth_client_id": "cid",
                     "oauth_refresh_token": "tok"},
                    {"mailbox_password": "pw"}):
            self.assertEqual(self._gate(cfg, ["email"]),
                             "mailbox_user is not set", cfg)

    def test_every_reason_is_the_exact_string_or_none(self):
        self.assertEqual(SETUP.needs_setup("x"), "config is not an object")
        self.assertEqual(SETUP.needs_setup({}), "mailbox_user is not set")
        self.assertEqual(SETUP.needs_setup({"mailbox_user": "a@b.c"}),
                         "mailbox_password is not set")
        oauth = {"mailbox_user": "a@b.c", "auth": "oauth"}
        self.assertEqual(SETUP.needs_setup(oauth),
                         "oauth_client_id is not set")
        self.assertEqual(
            SETUP.needs_setup(dict(oauth, oauth_client_id="c")),
            "no OAuth refresh token (sign-in never completed)")
        self.assertIsNone(SETUP.needs_setup(dict(self.PW)))
        self.assertIsNone(SETUP.needs_setup(dict(self.OAUTH)))

    def test_the_config_transports_key_is_not_what_the_gate_reads(self):
        # The gate reads its transports argument only: a config
        # claiming file-only still trips when the enabled set
        # says email, and the reverse holds too.
        cfg = dict(self.PW, transports=["file"])
        self.assertIsNone(self._gate({}, ["file"]))
        self.assertEqual(self._gate({"transports": ["file"]}, ["email"]),
                         "mailbox_user is not set")
        self.assertIsNone(self._gate({"transports": ["email"]}, ["file"]))

    def test_inert_neighbour_fields_do_not_move_the_gate(self):
        base = self._gate({}, ["email"])
        for extra in ({"imap_host": "imap.example.com"},
                      {"shared_secret": "x" * 64},
                      {"runner_id": "r1"}, {"base_dir": "/tmp/x"},
                      {"poll_interval_sec": 5}):
            self.assertEqual(self._gate(extra, ["email"]), base, extra)
            self.assertIsNone(self._gate(dict(self.PW, **extra),
                                         ["file"]), extra)

    def test_gate_does_not_mutate_config_or_transports(self):
        cfg = {"mailbox_user": "a@b.c", "auth": "oauth",
               "nested": {"k": [1, 2]}}
        transports = ["file", "email"]
        cfg_copy = json.loads(json.dumps(cfg))
        self._gate(cfg, transports)
        self._gate(cfg, ["file"])
        self.assertEqual(cfg, cfg_copy)
        self.assertEqual(transports, ["file", "email"])

    def test_repeated_and_interleaved_calls_are_deterministic(self):
        for _ in range(10):
            self.assertEqual(self._gate({}, ["email"]),
                             "mailbox_user is not set")
            self.assertIsNone(self._gate({}, ["file"]))
            self.assertIsNone(self._gate(dict(self.PW), ["email"]))

    def test_main_file_only_with_placeholder_mailbox_reaches_poll(self):
        body = {"transports": ["file"], "mailbox_user": self.USER_PH,
                "mailbox_password": self.PW_PH}
        code, poll, _err = _main_rig(["--once"], body)
        self.assertEqual(code, 0)
        self.assertTrue(poll.called)

    def test_main_string_email_transports_without_mailbox_refused(self):
        code, poll, err = _main_rig(["--once"], {"transports": "email"})
        self.assertEqual(code, 2)
        self.assertIn("mailbox_user is not set", err)
        self.assertFalse(poll.called)

    def test_main_mixed_file_and_email_without_mailbox_refused(self):
        code, poll, err = _main_rig(
            ["--once"], {"transports": ["file", "email"]})
        self.assertEqual(code, 2)
        self.assertIn("mailbox_user is not set", err)
        self.assertFalse(poll.called)

    # -- the bookend rule: the whole symbol table, both ends --

    def test_bookend_front_symbols_on_email_skip_the_gate(self):
        for symbol in string.punctuation:
            self.assertIsNone(self._gate({}, [symbol + "email"]), symbol)

    def test_bookend_back_symbols_on_email_skip_the_gate(self):
        for symbol in string.punctuation:
            self.assertIsNone(self._gate({}, ["email" + symbol]), symbol)

    def test_bookend_matched_pairs_on_email_skip_the_gate(self):
        for symbol in string.punctuation:
            self.assertIsNone(
                self._gate({}, [symbol + "email" + symbol]), symbol)

    def test_bookend_mismatched_pairs_on_email_skip_the_gate(self):
        symbols = string.punctuation
        rotated = symbols[1:] + symbols[:1]
        for front, back in zip(symbols, rotated):
            self.assertIsNone(self._gate({}, [front + "email" + back]),
                              (front, back))

    def test_symbol_only_transport_names_skip_the_gate(self):
        for symbol in string.punctuation:
            self.assertIsNone(self._gate({}, [symbol]), symbol)
        self.assertIsNone(self._gate({}, [string.punctuation]))

    def test_bookend_nonprinting_on_email_skips_the_gate(self):
        for char in ("\x00", "\t", "\r", "\n"):
            self.assertIsNone(self._gate({}, [char + "email"]), repr(char))
            self.assertIsNone(self._gate({}, ["email" + char]), repr(char))
            self.assertIsNone(self._gate({}, [char]), repr(char))

    def test_bookend_symbols_on_the_mailbox_user_keep_it_set(self):
        for symbol in string.punctuation:
            for user in (symbol + "a@b.c", "a@b.c" + symbol):
                cfg = {"mailbox_user": user, "mailbox_password": "pw"}
                self.assertIsNone(self._gate(cfg, ["email"]), user)

    def test_bookended_placeholder_user_is_no_longer_the_placeholder(self):
        # The placeholder reading is exact: one symbol at either
        # end and the value counts as a real, set address.
        for symbol in string.punctuation:
            for user in (symbol + self.USER_PH, self.USER_PH + symbol):
                cfg = {"mailbox_user": user, "mailbox_password": "pw"}
                self.assertIsNone(self._gate(cfg, ["email"]), user)

    def test_bookend_pairs_on_the_mailbox_user_keep_it_set(self):
        symbols = string.punctuation
        rotated = symbols[1:] + symbols[:1]
        for symbol in string.punctuation:
            cfg = {"mailbox_user": symbol + "a@b.c" + symbol,
                   "mailbox_password": "pw"}
            self.assertIsNone(self._gate(cfg, ["email"]), symbol)
        for front, back in zip(symbols, rotated):
            cfg = {"mailbox_user": front + "a@b.c" + back,
                   "mailbox_password": "pw"}
            self.assertIsNone(self._gate(cfg, ["email"]), (front, back))

    def test_symbol_only_mailbox_user_counts_as_set(self):
        for symbol in string.punctuation:
            cfg = {"mailbox_user": symbol, "mailbox_password": "pw"}
            self.assertIsNone(self._gate(cfg, ["email"]), symbol)
            cfg.pop("mailbox_password")
            self.assertEqual(self._gate(cfg, ["email"]),
                             "mailbox_password is not set", symbol)

    def test_bookend_nonprinting_on_the_mailbox_user(self):
        for char in ("\x00", "\t", "\r", "\n"):
            for user in (char + "a@b.c", "a@b.c" + char, char):
                cfg = {"mailbox_user": user, "mailbox_password": "pw"}
                self.assertIsNone(self._gate(cfg, ["email"]), repr(user))

    def test_bookended_oauth_auth_reads_as_password_auth(self):
        symbols = string.punctuation
        variants = ([s + "oauth" for s in symbols]
                    + ["oauth" + s for s in symbols]
                    + [s + "oauth" + s for s in symbols]
                    + list(symbols))
        for auth in variants:
            cfg = {"mailbox_user": "a@b.c", "auth": auth,
                   "mailbox_password": "pw"}
            self.assertIsNone(self._gate(cfg, ["email"]), repr(auth))
            cfg.pop("mailbox_password")
            self.assertEqual(self._gate(cfg, ["email"]),
                             "mailbox_password is not set", repr(auth))

    # -- run lengths: counts, not just characters --

    def test_runs_in_the_transport_name_skip_the_gate(self):
        for name in (";" * 10 + "email", "email" + ";" * 10,
                     "em" + "x" * 10 + "ail",
                     "x" * 10 + ";" + "email", "e" * 10 + "mail"):
            self.assertIsNone(self._gate({}, [name]), name)
        self.assertEqual(self._gate({}, ["email"] * 10),
                         "mailbox_user is not set")

    def test_runs_in_the_mailbox_user_keep_it_set(self):
        for user in ("x" * 10, ";" * 10, "x" * 5 + ";" + "x" * 5,
                     ";" + "x" * 10, "x" * 10 + ";",
                     self.USER_PH + "x" * 10):
            cfg = {"mailbox_user": user, "mailbox_password": "pw"}
            self.assertIsNone(self._gate(cfg, ["email"]), user)

    def test_runs_in_the_auth_value_read_as_password_auth(self):
        for auth in ("oauth" + "h" * 10, "o" * 10 + "auth",
                     "oa" + "u" * 10 + "th", "oauthoauth",
                     ";" * 10):
            cfg = {"mailbox_user": "a@b.c", "auth": auth,
                   "mailbox_password": "pw"}
            self.assertIsNone(self._gate(cfg, ["email"]), auth)

    def test_runs_in_the_mailbox_password_keep_it_set(self):
        for password in (";" * 10, "x" * 10 + ";", ";" + "x" * 10,
                         "x" * 5 + ";" + "x" * 5,
                         self.PW_PH + "x" * 10):
            cfg = {"mailbox_user": "a@b.c", "mailbox_password": password}
            self.assertIsNone(self._gate(cfg, ["email"]), password)
        cfg = {"mailbox_user": "a@b.c", "mailbox_password": ""}
        self.assertEqual(self._gate(cfg, ["email"]),
                         "mailbox_password is not set")


class JobUserEnforceShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 43: job_user=enforce
    on Windows was a silent no-op and jobs ran as the runner's
    own account (found live 31-Oct-2026; fixed 8174b51f --
    job_user_startup_problem refuses enforce at startup on
    win32, and _job_user_preexec on Windows writes an
    unsupported_platform audit record instead of returning in
    silence). The JobUser tests above pin the headline shapes,
    and queue item 2's AuditEntryShotgunTest pins how the
    parity check reads that record; this family pins the
    mode/platform/startup-refusal surface itself, and stays
    distinct from both: every field the refusal and the
    Windows preexec read, the exact refusal string, the
    sec_mode defaults that make an unset mode an enforce, the
    record's exact call shape, and the POSIX contrast (the
    same mode on a POSIX name writes would_run_as, never
    unsupported_platform). No test here runs a job as another
    user: the platform is passed as a parameter, os.name is
    patched, and the security module is mocked or driven
    against a temporary directory, so the family runs on any
    host. One regression test was never going to be enough for
    a silent no-op in a security mode.

    Per-field enumeration: the surface reads exactly these
    fields -- security, security.modes,
    security.modes.job_user, security.job_user,
    security.job_user.user, the platform argument, job_id and
    base_dir. Each gets its own generated test below, sweeping
    that field alone; user is pinned as read on POSIX and
    inert on Windows and at startup, and base_dir as passed
    through verbatim to both audit calls.

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: the text surfaces --
    the platform string, the mode string, the config key
    names, job_id and the job_user user -- get bookended
    variants: all 32 printable ASCII symbols
    (string.punctuation) at the front and at the back, as
    singles, matched pairs, mismatched pairs and symbol-only
    strings, plus NUL, tab, CR and LF at both ends; and run
    lengths: runs of the odd character, and runs of ordinary
    characters with the odd one at the front, the back and
    the middle. A bookended key name is its own case here:
    "job_user" with one symbol at either end is an unknown
    key, so the unset default -- enforce -- takes over.

    Proof of work (6-Nov-2026). The unit tests are the 50
    methods of this class: 26 hand-written seams (2 of them
    through main()), 8 generated per-field tests, 12 bookend
    sweeps and 4 run-length sweeps. The fuzzing was executed,
    not just the tests written: runner/tools/de_dust_corpus.py
    grow --target secret --rounds 400 --seed 20261144, run
    locally against the banked secret corpus (26
    entries) -- the target that exercises
    runner/guard/security.py, the module that owns the mode
    set this surface reads. Result: 400 rounds, 0 crashes,
    0 slow, arcs unchanged at 78, slowest try 89 ms; the
    silent Windows no-op did not recur. The grow's
    bookkeeping writes were reverted and are not banked
    (banking is the rigs' hourly job); this record is the
    run's proof. None of this is exotic: it is combinatorics
    -- systematically trying the combinations a hand-written
    list would never reach, then pinning each answer as a
    test."""

    PROBLEM = ("job_user (a POSIX setuid demote) is POSIX-only; "
               "this machine is win32")
    ENFORCE = {"security": {"modes": {"job_user": "enforce"}}}

    @staticmethod
    def _problem(cfg, platform="win32"):
        return runner._job_user_startup_problem(cfg, platform=platform)

    def _preexec(self, mode, os_name="nt", cfg=None, job_id="job-9",
                 base="base-x"):
        sec = mock.Mock()
        sec.sec_mode.return_value = mode
        if cfg is None:
            cfg = {"security": {"modes": {"job_user": mode},
                                "job_user": {"user": "jobber"}}}
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, "work")
            os.makedirs(work, exist_ok=True)
            with mock.patch.object(runner, "_security", sec), \
                    mock.patch.object(os, "name", os_name):
                out = runner._job_user_preexec(cfg, base, job_id, work)
        return out, sec

    # -- hand-written seams: the startup refusal --

    def test_enforce_on_win32_problem_is_the_exact_string(self):
        self.assertEqual(self._problem(dict(self.ENFORCE)), self.PROBLEM)

    def test_unset_security_block_defaults_to_enforce_and_refuses(self):
        self.assertEqual(self._problem({}), self.PROBLEM)

    def test_none_security_block_defaults_to_enforce_and_refuses(self):
        self.assertEqual(self._problem({"security": None}), self.PROBLEM)

    def test_modes_absent_defaults_to_enforce_and_refuses(self):
        self.assertEqual(self._problem({"security": {}}), self.PROBLEM)
        self.assertEqual(
            self._problem({"security": {"job_user": {"user": "x"}}}),
            self.PROBLEM)

    def test_feature_absent_from_modes_defaults_to_enforce(self):
        cfg = {"security": {"modes": {"confinement": "off",
                                      "audience": "audit"}}}
        self.assertEqual(self._problem(cfg), self.PROBLEM)

    def test_audit_and_off_on_win32_are_not_refused(self):
        for mode in ("audit", "off"):
            cfg = {"security": {"modes": {"job_user": mode}}}
            self.assertIsNone(self._problem(cfg), mode)

    def test_invalid_modes_on_win32_read_off_and_are_not_refused(self):
        for mode in ("bogus", "", None, 7, ["enforce"], {"m": 1}):
            cfg = {"security": {"modes": {"job_user": mode}}}
            self.assertIsNone(self._problem(cfg), repr(mode))

    def test_mode_spelling_is_exact_in_case_and_spacing(self):
        for mode in ("Enforce", "ENFORCE", "enforce ", " enforce",
                     "enforce\n"):
            cfg = {"security": {"modes": {"job_user": mode}}}
            self.assertIsNone(self._problem(cfg), repr(mode))

    def test_enforce_on_non_windows_platforms_is_not_refused(self):
        for platform in ("linux", "darwin", "freebsd13", "linux2",
                         "sunos5", ""):
            self.assertIsNone(
                self._problem(dict(self.ENFORCE), platform), platform)

    def test_platform_spelling_is_exact_in_case_and_spacing(self):
        for platform in ("WIN32", "Win32", "win32 ", " win32", "win",
                         "windows", "win32\x00"):
            self.assertIsNone(
                self._problem(dict(self.ENFORCE), platform),
                repr(platform))

    def test_platform_none_defaults_to_the_host_platform(self):
        self.assertIsNone(self._problem(dict(self.ENFORCE), None))
        with mock.patch.object(sys, "platform", "win32"):
            self.assertEqual(self._problem(dict(self.ENFORCE), None),
                             self.PROBLEM)

    def test_no_security_module_means_no_refusal(self):
        with mock.patch.object(runner, "_security", None):
            self.assertIsNone(self._problem(dict(self.ENFORCE)))

    def test_the_refusal_asks_the_security_module_about_job_user(self):
        sec = mock.Mock()
        sec.sec_mode.side_effect = (
            lambda cfg, feature: "enforce" if feature == "job_user"
            else "off")
        with mock.patch.object(runner, "_security", sec):
            self.assertEqual(self._problem({}), self.PROBLEM)
        sec.sec_mode.assert_called_with({}, "job_user")
        sec2 = mock.Mock()
        sec2.sec_mode.side_effect = (
            lambda cfg, feature: "off" if feature == "job_user"
            else "enforce")
        with mock.patch.object(runner, "_security", sec2):
            self.assertIsNone(self._problem({}))

    def test_malformed_security_shapes_read_off_and_are_not_refused(self):
        for cfg in ([], "x", 7, None,
                    {"security": "x"}, {"security": 7},
                    {"security": {"modes": "x"}},
                    {"security": {"modes": ["job_user"]}}):
            self.assertIsNone(self._problem(cfg), repr(cfg))

    def test_startup_problem_is_deterministic_and_does_not_mutate(self):
        cfg = {"security": {"modes": {"job_user": "enforce"},
                            "job_user": {"user": "jobber"}}}
        before = json.loads(json.dumps(cfg))
        for _ in range(10):
            self.assertEqual(self._problem(cfg), self.PROBLEM)
            self.assertIsNone(self._problem(cfg, "linux"))
        self.assertEqual(cfg, before)

    def test_main_audit_on_win32_starts(self):
        cfg = {"transports": ["file"],
               "security": {"modes": {"job_user": "audit",
                                      "confinement": "off"},
                            "job_user": {"user": "root"}}}
        with mock.patch.object(sys, "platform", "win32"):
            code, poll, _err = _main_rig(["--once"], cfg)
        self.assertEqual(code, 0)
        self.assertTrue(poll.called)

    def test_main_enforce_on_darwin_starts(self):
        cfg = {"transports": ["file"],
               "security": {"modes": {"job_user": "enforce",
                                      "confinement": "off"},
                            "job_user": {"user": "root"}}}
        with mock.patch.object(sys, "platform", "darwin"):
            code, poll, _err = _main_rig(["--once"], cfg)
        self.assertEqual(code, 0)
        self.assertTrue(poll.called)

    # -- hand-written seams: the Windows preexec record --

    def test_nt_audit_writes_the_exact_unsupported_record_call(self):
        out, sec = self._preexec("audit")
        self.assertIsNone(out)
        sec.bump_evaluated.assert_called_once_with("base-x", "job_user")
        sec.write_audit_entry.assert_called_once_with(
            "base-x", "job_user", "unsupported_platform",
            "job_user_posix_only", job_id="job-9",
            cfg={"security": {"modes": {"job_user": "audit"},
                              "job_user": {"user": "jobber"}}},
            mode="audit")

    def test_nt_enforce_writes_the_record_with_its_mode(self):
        out, sec = self._preexec("enforce")
        self.assertIsNone(out)
        args = sec.write_audit_entry.call_args
        self.assertEqual(args[0][2], "unsupported_platform")
        self.assertEqual(args[1]["mode"], "enforce")

    def test_nt_off_is_silent_with_no_bump_and_no_record(self):
        out, sec = self._preexec("off")
        self.assertIsNone(out)
        sec.bump_evaluated.assert_not_called()
        sec.write_audit_entry.assert_not_called()

    def test_nt_record_reaches_the_real_audit_log(self):
        cfg = {"security": {"modes": {"job_user": "audit"},
                            "job_user": {"user": "jobber"}}}
        with tempfile.TemporaryDirectory() as base:
            work = os.path.join(base, "work")
            os.makedirs(work, exist_ok=True)
            with mock.patch.object(os, "name", "nt"):
                out = runner._job_user_preexec(cfg, base, 123, work)
            self.assertIsNone(out)
            with open(os.path.join(base, "security-audit.jsonl"),
                      encoding="utf-8") as fh:
                record = json.loads(fh.readline())
        self.assertEqual(record["feature"], "job_user")
        self.assertEqual(record["decision"], "unsupported_platform")
        self.assertEqual(record["reason"], "job_user_posix_only")
        self.assertEqual(record["job_id"], "123")
        self.assertEqual(record["mode"], "audit")
        self.assertEqual(len(record["chain"]), 64)

    def test_nt_a_failing_audit_write_is_swallowed(self):
        out, sec = self._preexec("audit")
        sec.write_audit_entry.side_effect = RuntimeError("disk")
        # Re-drive with the failing writer in place.
        sec2 = mock.Mock()
        sec2.sec_mode.return_value = "audit"
        sec2.write_audit_entry.side_effect = RuntimeError("disk")
        cfg = {"security": {"modes": {"job_user": "audit"}}}
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, "work")
            os.makedirs(work, exist_ok=True)
            with mock.patch.object(runner, "_security", sec2), \
                    mock.patch.object(os, "name", "nt"):
                self.assertIsNone(
                    runner._job_user_preexec(cfg, td, "job-9", work))
        sec2.bump_evaluated.assert_called_once()

    def test_preexec_without_a_security_module_returns_none(self):
        cfg = {"security": {"modes": {"job_user": "enforce"}}}
        with tempfile.TemporaryDirectory() as td:
            work = os.path.join(td, "work")
            os.makedirs(work, exist_ok=True)
            with mock.patch.object(runner, "_security", None), \
                    mock.patch.object(os, "name", "nt"):
                self.assertIsNone(
                    runner._job_user_preexec(cfg, td, "job-9", work))

    def test_nt_job_id_is_stringified_into_the_record(self):
        for job_id, want in ((123, "123"), (None, "None"),
                             (("a", 1), "('a', 1)")):
            _out, sec = self._preexec("audit", job_id=job_id)
            self.assertEqual(
                sec.write_audit_entry.call_args[1]["job_id"], want,
                repr(job_id))

    def test_the_user_field_is_inert_on_windows(self):
        for user in (None, "", 7, ["root"], {"name": "root"}):
            cfg = {"security": {"modes": {"job_user": "audit"},
                                "job_user": {"user": user}}}
            if user is not None:
                cfg["security"]["job_user"] = {"user": user}
            _out, sec = self._preexec("audit", cfg=cfg)
            sec.write_audit_entry.assert_called_once()
            self.assertNotIn(
                "detail", sec.write_audit_entry.call_args[1])
        cfg = {"security": {"modes": {"job_user": "audit"}}}
        _out, sec = self._preexec("audit", cfg=cfg)
        sec.write_audit_entry.assert_called_once()

    def test_posix_audit_writes_would_run_as_not_unsupported(self):
        out, sec = self._preexec("audit", os_name="posix")
        self.assertIsNone(out)
        args = sec.write_audit_entry.call_args
        self.assertEqual(args[0][2], "would_run_as")
        self.assertEqual(args[0][3], "would_run_as_user")
        self.assertEqual(args[1]["detail"], "jobber")

    # -- the bookend rule: the whole symbol table, both ends --

    def test_bookend_front_symbols_on_the_platform_drop_the_refusal(self):
        for symbol in string.punctuation:
            self.assertIsNone(
                self._problem(dict(self.ENFORCE), symbol + "win32"),
                symbol)

    def test_bookend_back_symbols_on_the_platform_drop_the_refusal(self):
        for symbol in string.punctuation:
            self.assertIsNone(
                self._problem(dict(self.ENFORCE), "win32" + symbol),
                symbol)

    def test_bookend_pairs_on_the_platform_drop_the_refusal(self):
        symbols = string.punctuation
        rotated = symbols[1:] + symbols[:1]
        for symbol in string.punctuation:
            self.assertIsNone(self._problem(
                dict(self.ENFORCE), symbol + "win32" + symbol), symbol)
        for front, back in zip(symbols, rotated):
            self.assertIsNone(self._problem(
                dict(self.ENFORCE), front + "win32" + back),
                (front, back))

    def test_symbol_only_and_nonprinting_platforms_drop_the_refusal(self):
        for platform in list(string.punctuation) + [
                "\x00win32", "win32\x00", "\twin32", "win32\r\n",
                "\x00", "\n"]:
            self.assertIsNone(
                self._problem(dict(self.ENFORCE), platform),
                repr(platform))

    def test_bookend_front_symbols_on_the_mode_read_off(self):
        for symbol in string.punctuation:
            cfg = {"security": {"modes": {
                "job_user": symbol + "enforce"}}}
            self.assertIsNone(self._problem(cfg), symbol)

    def test_bookend_back_symbols_on_the_mode_read_off(self):
        for symbol in string.punctuation:
            cfg = {"security": {"modes": {
                "job_user": "enforce" + symbol}}}
            self.assertIsNone(self._problem(cfg), symbol)

    def test_bookend_pairs_and_symbol_only_modes_read_off(self):
        symbols = string.punctuation
        rotated = symbols[1:] + symbols[:1]
        variants = ([s + "enforce" + s for s in symbols]
                    + [f + "enforce" + b
                       for f, b in zip(symbols, rotated)]
                    + list(symbols))
        for mode in variants:
            cfg = {"security": {"modes": {"job_user": mode}}}
            self.assertIsNone(self._problem(cfg), repr(mode))

    def test_bookend_nonprinting_on_the_mode_reads_off(self):
        for char in ("\x00", "\t", "\r", "\n"):
            for mode in (char + "enforce", "enforce" + char, char):
                cfg = {"security": {"modes": {"job_user": mode}}}
                self.assertIsNone(self._problem(cfg), repr(mode))

    def test_bookended_feature_key_falls_back_to_the_enforce_default(self):
        # An off mode under a bookended key is a mode for an
        # unknown key: job_user itself is unset, and an unset
        # job_user reads enforce, so win32 refuses after all.
        for symbol in string.punctuation:
            for key in (symbol + "job_user", "job_user" + symbol):
                cfg = {"security": {"modes": {key: "off"}}}
                self.assertEqual(self._problem(cfg), self.PROBLEM,
                                 key)

    def test_bookended_block_keys_fall_back_to_the_enforce_default(self):
        for symbol in string.punctuation:
            cfg = {symbol + "security": {"modes": {"job_user": "off"}}}
            self.assertEqual(self._problem(cfg), self.PROBLEM, symbol)
            cfg = {"security" + symbol: {"modes": {"job_user": "off"}}}
            self.assertEqual(self._problem(cfg), self.PROBLEM, symbol)
            cfg = {"security": {symbol + "modes":
                                {"job_user": "off"}}}
            self.assertEqual(self._problem(cfg), self.PROBLEM, symbol)
            cfg = {"security": {"modes" + symbol:
                                {"job_user": "off"}}}
            self.assertEqual(self._problem(cfg), self.PROBLEM, symbol)

    def test_bookended_job_ids_ride_the_record_verbatim(self):
        for symbol in string.punctuation:
            for job_id in (symbol + "job-9", "job-9" + symbol,
                           symbol + "job-9" + symbol, symbol):
                _out, sec = self._preexec("audit", job_id=job_id)
                self.assertEqual(
                    sec.write_audit_entry.call_args[1]["job_id"],
                    job_id, repr(job_id))

    def test_bookended_users_never_reach_the_windows_record(self):
        for symbol in string.punctuation:
            cfg = {"security": {"modes": {"job_user": "audit"},
                                "job_user": {
                                    "user": symbol + "jobber" + symbol}}}
            _out, sec = self._preexec("audit", cfg=cfg)
            sec.write_audit_entry.assert_called_once()
            self.assertNotIn("detail",
                             sec.write_audit_entry.call_args[1])

    # -- run lengths: counts, not just characters --

    def test_runs_in_the_mode_read_off(self):
        for mode in ("enforce" + "e" * 10, "e" * 10 + "enforce",
                     "enf" + "o" * 10 + "rce", ";" * 10,
                     "x" * 5 + ";" + "x" * 5):
            cfg = {"security": {"modes": {"job_user": mode}}}
            self.assertIsNone(self._problem(cfg), mode)

    def test_runs_in_the_platform_drop_the_refusal(self):
        for platform in ("win32" + "2" * 10, "w" * 10 + "in32",
                         "win" + "3" * 10 + "2", ";" * 10,
                         "w" * 5 + ";" + "in32"):
            self.assertIsNone(
                self._problem(dict(self.ENFORCE), platform), platform)

    def test_runs_in_the_job_id_ride_the_record_verbatim(self):
        for job_id in ("x" * 10 + ";", ";" * 10, ";" + "x" * 10,
                       "x" * 5 + ";" + "x" * 5):
            _out, sec = self._preexec("audit", job_id=job_id)
            self.assertEqual(
                sec.write_audit_entry.call_args[1]["job_id"], job_id,
                job_id)

    def test_runs_in_key_names_fall_back_to_the_enforce_default(self):
        for key in ("job_user" + "r" * 10, "j" * 10 + "ob_user",
                    "job_" + "u" * 10 + "ser"):
            cfg = {"security": {"modes": {key: "off"}}}
            self.assertEqual(self._problem(cfg), self.PROBLEM, key)
        cfg = {"security": {"modes": {"job_user": "off"}}}
        self.assertIsNone(self._problem(cfg))


def _make_job_user_field_tests():
    """One generated test per field this surface reads."""
    problem = JobUserEnforceShotgunTest._problem
    want = JobUserEnforceShotgunTest.PROBLEM

    def field_security(self):
        for sec, expected in (
                (None, want), ({}, want), ("x", None), (7, None),
                ({"modes": {"job_user": "off"}}, None)):
            self.assertEqual(problem({"security": sec}), expected,
                             repr(sec))
        self.assertEqual(problem({}), want)
        self.assertEqual(problem({"securityx": {}}), want)

    def field_modes(self):
        for modes, expected in (
                (None, None), ("x", None), ([], None),
                ({}, want), ({"job_user": "enforce"}, want),
                ({"job_user": "audit"}, None)):
            cfg = {"security": {"modes": modes}}
            self.assertEqual(problem(cfg), expected, repr(modes))

    def field_job_user_mode(self):
        for mode, expected in (
                ("enforce", want), ("audit", None), ("off", None),
                ("bogus", None), (None, None), ("Enforce", None)):
            cfg = {"security": {"modes": {"job_user": mode}}}
            self.assertEqual(problem(cfg), expected, repr(mode))

    def field_job_user_block(self):
        # The block beside modes is startup-inert in every shape.
        for block in (None, "x", 7, [], {}, {"user": "root"},
                      {"user": None}):
            cfg = {"security": {"modes": {"job_user": "enforce"},
                                "job_user": block}}
            self.assertEqual(problem(cfg), want, repr(block))
            cfg["security"]["modes"]["job_user"] = "off"
            self.assertIsNone(problem(cfg), repr(block))

    def field_user(self):
        # Read on POSIX, inert at startup and on Windows.
        for user in ("root", "jobber", "", None, 7, ["root"]):
            cfg = {"security": {"modes": {"job_user": "enforce"},
                                "job_user": {"user": user}}}
            self.assertEqual(problem(cfg), want, repr(user))

    def field_platform(self):
        for platform, expected in (
                ("win32", want), ("linux", None), ("darwin", None),
                ("WIN32", None), ("", None), (None, None)):
            self.assertEqual(
                problem(dict(JobUserEnforceShotgunTest.ENFORCE),
                        platform),
                expected, repr(platform))

    def field_job_id(self):
        probe = JobUserEnforceShotgunTest()
        for job_id, text in (("job-9", "job-9"), (123, "123"),
                             (None, "None"), (1.5, "1.5")):
            _out, sec = probe._preexec("audit", job_id=job_id)
            self.assertEqual(
                sec.write_audit_entry.call_args[1]["job_id"], text,
                repr(job_id))

    def field_base_dir(self):
        probe = JobUserEnforceShotgunTest()
        for base in ("base-x", "/tmp/deep/base", "relative-base"):
            _out, sec = probe._preexec("enforce", base=base)
            sec.bump_evaluated.assert_called_once_with(base, "job_user")
            self.assertEqual(sec.write_audit_entry.call_args[0][0],
                             base)

    for name, fn in list(locals().items()):
        if name.startswith("field_"):
            setattr(JobUserEnforceShotgunTest, "test_" + name, fn)


_make_job_user_field_tests()


def _make_mailbox_gate_field_tests():
    """One generated test per field the gate reads."""
    gate = MailboxGateShotgunTest._gate
    pw = MailboxGateShotgunTest.PW
    oauth = MailboxGateShotgunTest.OAUTH

    def field_config_object(self):
        for cfg in ({}, [], "x", 7, None):
            self.assertIsNone(gate(cfg, ["file"]), repr(cfg))
        self.assertEqual(gate(None, ["email"]), "config is not an object")
        self.assertIsNone(gate(dict(pw), ["email"]))

    def field_transports(self):
        for transports, want in (
                (["file"], None), (["email"], "mailbox_user is not set"),
                (None, "mailbox_user is not set"), ([], None),
                (["file", "email"], "mailbox_user is not set")):
            self.assertEqual(gate({}, transports), want, transports)
            self.assertIsNone(gate(dict(pw), transports), transports)

    def field_mailbox_user(self):
        for user, want in (
                (None, "mailbox_user is not set"),
                ("", "mailbox_user is not set"),
                (MailboxGateShotgunTest.USER_PH,
                 "mailbox_user is not set"),
                ("a@b.c", "mailbox_password is not set"),
                ("x@y", "mailbox_password is not set")):
            self.assertEqual(gate({"mailbox_user": user}, ["email"]),
                             want, user)

    def field_mailbox_password(self):
        for password, want in (
                (None, "mailbox_password is not set"),
                ("", "mailbox_password is not set"),
                (MailboxGateShotgunTest.PW_PH,
                 "mailbox_password is not set"),
                ("pw", None), (" ", None)):
            cfg = {"mailbox_user": "a@b.c", "mailbox_password": password}
            self.assertEqual(gate(cfg, ["email"]), want, password)

    def field_auth(self):
        for auth, want in (
                (None, None), ("password", None), ("PASSWORD", None),
                ("oauth", "oauth_client_id is not set"),
                ("OAuth", "oauth_client_id is not set")):
            cfg = {"mailbox_user": "a@b.c", "auth": auth,
                   "mailbox_password": "pw"}
            self.assertEqual(gate(cfg, ["email"]), want, auth)

    def field_oauth_client_id(self):
        for client, want in (
                (None, "oauth_client_id is not set"),
                ("", "oauth_client_id is not set"),
                ("cid", "no OAuth refresh token "
                        "(sign-in never completed)")):
            cfg = {"mailbox_user": "a@b.c", "auth": "oauth",
                   "oauth_client_id": client}
            self.assertEqual(gate(cfg, ["email"]), want, client)
        # Inert under password auth, present or not.
        self.assertIsNone(gate(dict(pw), ["email"]))

    def field_oauth_refresh_token(self):
        for token, want in (
                (None, "no OAuth refresh token "
                       "(sign-in never completed)"),
                ("", "no OAuth refresh token "
                     "(sign-in never completed)"),
                ("tok", None)):
            cfg = {"mailbox_user": "a@b.c", "auth": "oauth",
                   "oauth_client_id": "cid", "oauth_refresh_token": token}
            self.assertEqual(gate(cfg, ["email"]), want, token)
        self.assertIsNone(gate(dict(oauth), ["email"]))

    for name, fn in list(locals().items()):
        if name.startswith("field_"):
            setattr(MailboxGateShotgunTest, "test_" + name, fn)


_make_mailbox_gate_field_tests()


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
