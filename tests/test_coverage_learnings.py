"""Scenarios from the coverage run, each one a behavior that surprised us.

The entropy estimate accepts a repeated hex block. The poll loop reports
a dead refresh token once. A sensor record that is not JSON is repaired
rather than dropped, unless building it raises.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock


REPEATED = "0123456789abcdef" * 4


class RepeatedSecretTest(unittest.TestCase):
    def test_the_entropy_estimate_accepts_a_repeated_hex_block(self):
        from runner.security import (
            _estimate_secret_entropy, validate_shared_secret)

        # 64 hex chars, 16-symbol alphabet: 256 bits on paper.
        # The string is four copies of one block, so it is not a secret.
        self.assertGreaterEqual(_estimate_secret_entropy(REPEATED), 128)
        with self.assertRaises(RuntimeError) as caught:
            validate_shared_secret(REPEATED)
        self.assertIn("repeats the 16-character unit", str(caught.exception))

    def test_one_character_is_weak_for_a_different_reason_than_two(self):
        from runner.security import validate_shared_secret

        with self.assertRaises(RuntimeError) as one:
            validate_shared_secret("a")
        with self.assertRaises(RuntimeError) as two:
            validate_shared_secret("aa")
        # Length 1 never enters the period loop. Length 2 is a repeat.
        self.assertNotIn("repeats", str(one.exception))
        self.assertIn("too weak", str(one.exception))
        self.assertIn("repeats the 1-character unit", str(two.exception))

    def test_the_solver_rejects_are_stable(self):
        from runner.security import validate_shared_secret

        cases = {
            "": "shared_secret is required",
            "ėė": "repeats the 1-character unit",
            "Xxxĳ": "example placeholder",
        }
        for secret, fragment in cases.items():
            with self.assertRaises(RuntimeError) as caught:
                validate_shared_secret(secret)
            self.assertIn(fragment, str(caught.exception), secret)

    def test_posture_fails_the_repeated_block(self):
        from runner.posture import main

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            cfg = {
                "shared_secret": REPEATED,
                "mailbox_user": "a@b.c",
                "mailbox_password": "pw",
                "base_dir": directory,
            }
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(cfg, path, directory)
        self.assertEqual(code, 2)
        self.assertIn("repeats the 16-character unit", buf.getvalue())


class HotReloadPinTest(unittest.TestCase):
    def test_a_cli_worker_count_is_not_overwritten_by_the_file(self):
        from runner.runner import reload_hot_config

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "workers": 4,
                    "poll_interval_sec": 9,
                }, fh)
            # mtime must differ from the remembered one.
            cfg = {"workers": 1, "poll_interval_sec": 20}
            changed = reload_hot_config(
                cfg, path, {"mtime": 0}, pinned={"workers"})
        self.assertEqual(cfg["workers"], 1)
        self.assertEqual(cfg["poll_interval_sec"], 9)
        self.assertEqual(changed, ["poll_interval_sec"])
        self.assertNotIn("workers", changed)

    def test_a_bad_file_is_retried_next_cycle(self):
        from runner.runner import reload_hot_config

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{")
            state = {"mtime": 0}
            changed = reload_hot_config({"workers": 1}, path, state)
        self.assertEqual(changed, [])
        self.assertEqual(state["mtime"], 0)

    def test_zero_is_not_a_legal_hot_value(self):
        from runner.runner import reload_hot_config

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"workers": 0, "poll_interval_sec": "nope"}, fh)
            cfg = {"workers": 2, "poll_interval_sec": 20}
            changed = reload_hot_config(cfg, path, {"mtime": 0})
        self.assertEqual(changed, [])
        self.assertEqual(cfg["workers"], 2)
        self.assertEqual(cfg["poll_interval_sec"], 20)

    def test_infinity_is_ignored_and_the_other_key_still_loads(self):
        from runner.runner import reload_hot_config

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            # JSON accepts Infinity. int() of it raises OverflowError,
            # which used to abort the whole reload.
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(
                    '{"workers": Infinity, "poll_interval_sec": NaN, '
                    '"default_timeout_sec": 15}')
            cfg = {"workers": 2, "poll_interval_sec": 20,
                   "default_timeout_sec": 30}
            state = {"mtime": 0}
            changed = reload_hot_config(cfg, path, state)
        self.assertEqual(cfg["workers"], 2)
        self.assertEqual(cfg["poll_interval_sec"], 20)
        self.assertEqual(cfg["default_timeout_sec"], 15)
        self.assertEqual(changed, ["default_timeout_sec"])
        self.assertNotEqual(state["mtime"], 0)


class SensorRecordTest(unittest.TestCase):
    def test_nan_is_stored_as_null_and_a_cycle_does_not_recurse(self):
        from runner.senses import load_alerts, store_alert

        cycle = {"title": "loop"}
        cycle["self"] = cycle
        with tempfile.TemporaryDirectory() as directory:
            store_alert(directory, {
                "sensor": "disk",
                "title": "temp",
                "reading": float("nan"),
            })
            store_alert(directory, cycle)
            rows = load_alerts(directory, limit=10)
        readings = [r.get("reading") for r in rows if r.get("title") == "temp"]
        self.assertEqual(readings, [None])
        looped = [r for r in rows if r.get("title") == "loop"]
        self.assertEqual(len(looped), 1)
        self.assertIsNone(looped[0]["self"])

    def test_a_record_whose_items_raise_is_not_stored(self):
        from runner.senses import store_alert

        class Boom(dict):
            def items(self):
                raise ValueError("no")

        with tempfile.TemporaryDirectory() as directory:
            store_alert(directory, Boom(title="x"))
            path = os.path.join(directory, "senses.jsonl")
            self.assertFalse(os.path.exists(path))

    def test_an_undecodable_sequence_number_is_skipped(self):
        from runner.runner import fetch_job_mails

        class Imap:
            def search(self, *args):
                return "OK", [b"\xff 3"]

            def fetch(self, num, spec):
                return "OK", [(num, b"body")]

        self.assertEqual(fetch_job_mails(Imap()), [("3", b"body")])


class OAuthLatchTest(unittest.TestCase):
    def test_a_dead_token_is_shouted_once_and_recovery_is_logged(self):
        from runner import runner
        from runner import setup
        from runner.oauth import OAuthRefreshError

        secret = (
            "0123456789abcdef"
            "fedcba9876543210"
            "0011223344556677"
            "8899aabbccddeeff"
        )
        polls = {"n": 0}

        def poll(*args, **kwargs):
            polls["n"] += 1
            if polls["n"] < 3:
                raise OAuthRefreshError("dead token")

        def sleep(_seconds):
            if polls["n"] >= 3:
                raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "shared_secret": secret,
                    "mailbox_user": "a@b.c",
                    "mailbox_password": "pw",
                    "base_dir": directory,
                }, fh)
            with mock.patch.object(runner, "ensure_inference_ready"), \
                 mock.patch.object(runner, "update_llama_from_config"), \
                 mock.patch.object(runner, "poll_once", side_effect=poll), \
                 mock.patch.object(runner, "report_event") as reported, \
                 mock.patch.object(runner.time, "sleep", side_effect=sleep), \
                 mock.patch.object(setup, "is_tty", return_value=False), \
                 mock.patch.object(setup, "needs_setup", return_value=None), \
                 mock.patch.object(sys, "argv", ["runner", "--config", path]):
                with self.assertRaises(KeyboardInterrupt):
                    runner.main()
            log_path = os.path.join(directory, "runner.log")
            with open(log_path, encoding="utf-8") as fh:
                log = fh.read()
        self.assertEqual(reported.call_count, 1)
        self.assertIn("sign-in failed", reported.call_args[0][0])
        self.assertIn("gmail authentication recovered", log)
        self.assertEqual(polls["n"], 3)


class ShellOrderingTest(unittest.TestCase):
    def test_the_event_source_is_registered_only_on_the_first_report(self):
        import ctypes
        from runner import winlog

        class Adv:
            def RegisterEventSourceW(self, *args):
                return 1

            def ReportEventW(self, *args):
                return 1

            def DeregisterEventSource(self, handle):
                return 1

        winlog._reported_ok = False
        with mock.patch("runner.winlog.os.name", "nt"), \
             mock.patch.object(ctypes, "windll",
                               mock.Mock(advapi32=Adv()), create=True), \
             mock.patch("runner.winlog._ensure_source") as ensure:
            winlog.report_event("one")
            winlog.report_event("two")
        self.assertEqual(ensure.call_count, 1)
        winlog._reported_ok = False

    def test_a_google_error_wins_over_a_missing_code(self):
        from runner.oauth import browser_consent

        class Server:
            def __init__(self, addr, handler):
                handler.error = "access_denied"
                handler.code = None

            def handle_request(self):
                return None

            def server_close(self):
                return None

        with mock.patch("runner.oauth.HTTPServer", Server), \
             mock.patch("runner.oauth.webbrowser.open"):
            with self.assertRaises(SystemExit) as caught:
                browser_consent({"oauth_client_id": "cid"})
        text = str(caught.exception)
        self.assertIn("access_denied", text)
        self.assertNotIn("no sign-in code", text)

    def test_home_on_this_platform_is_a_note_not_a_switch(self):
        from runner import install

        buf = io.StringIO()
        with mock.patch.object(sys, "argv",
                               ["install", "--home", "/opt/pigeon", "--check"]), \
             mock.patch.object(sys, "platform", "linux"), \
             mock.patch.multiple(
                 install,
                 install_files=mock.Mock(return_value=True),
                 install_linux=mock.Mock(),
                 _setup_fresh_config=mock.Mock(return_value=(True, "m")),
                 do_check=mock.Mock(return_value=0)):
            with redirect_stdout(buf):
                code = install.main()
            checked = install.do_check.called
        self.assertEqual(code, 2)
        self.assertIn("Windows-only", buf.getvalue())
        self.assertFalse(checked)


if __name__ == "__main__":
    unittest.main()
