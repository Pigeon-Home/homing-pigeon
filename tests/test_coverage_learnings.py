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


class InfinityFromFileTest(unittest.TestCase):
    """Infinity loaded with the config, not applied later by hot reload.

    The hot-key gate never sees these. int() has to tolerate them
    on the poll path or the process dies after the first cycle.
    """

    SECRET = (
        "0123456789abcdef"
        "fedcba9876543210"
        "0011223344556677"
        "8899aabbccddeeff"
    )

    def test_the_poll_sleeps_the_default_and_the_worker_count_stays_one(self):
        import sys
        from runner import runner
        from runner import setup

        delays = []

        def sleep(seconds):
            delays.append(seconds)
            raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(
                    '{"shared_secret": "%s", "mailbox_user": "a@b.c", '
                    '"mailbox_password": "pw", "base_dir": "%s", '
                    '"poll_interval_sec": Infinity, "workers": Infinity, '
                    '"max_job_age_sec": Infinity, '
                    '"default_timeout_sec": -Infinity}'
                    % (self.SECRET, directory.replace("\\", "\\\\")))
            with mock.patch.object(runner, "ensure_inference_ready"), \
                 mock.patch.object(runner, "update_llama_from_config"), \
                 mock.patch.object(runner, "poll_once"), \
                 mock.patch.object(runner.time, "sleep", side_effect=sleep), \
                 mock.patch.object(setup, "is_tty", return_value=False), \
                 mock.patch.object(setup, "needs_setup", return_value=None), \
                 mock.patch.object(sys, "argv", ["runner", "--config", path]):
                with self.assertRaises(KeyboardInterrupt):
                    runner.main()
        self.assertEqual(delays, [20])
        self.assertEqual(runner._worker_count(
            {"workers": float("inf")}, None), 1)

    def test_a_mail_cap_of_infinity_does_not_raise(self):
        from runner.runner import handle_mail

        raw = b"Subject: [HOMING-PIGEON] job abc\r\n\r\nnope"
        cfg = {
            "max_job_bytes": float("inf"),
            "max_script_bytes": float("inf"),
            "max_job_age_sec": float("inf"),
            "shared_secret": self.SECRET,
        }

        class Imap:
            def store(self, *args):
                return None

        with tempfile.TemporaryDirectory() as directory:
            handle_mail(cfg, Imap(), None, "1", raw, directory, {},
                        {"": self.SECRET})

    def test_an_infinite_job_timeout_is_rejected(self):
        from runner.runner import JobRejected, execute_job

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(JobRejected):
                execute_job(
                    {"default_timeout_sec": float("inf")},
                    {"job_id": "abc", "kind": "exec",
                     "timeout_sec": float("inf")},
                    directory)

    def test_an_infinite_model_timeout_is_a_rejection(self):
        from runner.runner import ask_model

        def cut(req, timeout=60):
            raise TimeoutError("cut")

        out = ask_model(
            {"endpoint": "http://127.0.0.1:9/v1", "model": "test",
             "timeout_sec": float("inf")},
            "when?", "12:00", 100, opener=cut)
        self.assertEqual(out.get("rejected"), "inference_error")

    def test_infinity_retention_does_not_stop_the_poll(self):
        from runner.runner import (
            _issued_at_ok, poll_once, retained_expired)

        class Imap:
            def search(self, *args):
                return "OK", [b""]

            def logout(self):
                return None

        cfg = {
            "shared_secret": self.SECRET,
            "output_retention_days": float("inf"),
            "max_job_age_sec": float("inf"),
            "max_output_bytes": float("inf"),
        }
        with tempfile.TemporaryDirectory() as directory:
            poll_once(cfg, directory, {}, os.path.join(directory, "seen.json"),
                      imap=Imap(), smtp=object())
        self.assertIs(retained_expired(
            {"saved_at": 0}, {"output_retention_days": float("inf")}), True)
        ok, _reason = _issued_at_ok(
            "2020-01-01T00:00:00Z", {"max_job_age_sec": float("inf")})
        self.assertFalse(ok)

    def test_an_infinite_output_cap_does_not_raise(self):
        from runner.runner import execute_job

        class Proc:
            pid = 1
            returncode = 0

            def communicate(self, timeout=None):
                return b"ok", b""

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("runner.runner.subprocess.Popen",
                            return_value=Proc()):
                result = execute_job(
                    {"max_output_bytes": float("inf"),
                     "default_timeout_sec": 5},
                    {"job_id": "abc", "kind": "exec", "script": "echo hi",
                     "timeout_sec": 5},
                    directory)
        self.assertEqual(result["exit_code"], 0)


class NonFiniteElsewhereTest(unittest.TestCase):
    def test_dri_and_sensor_weight_and_exit_code(self):
        from runner.dri import parse_dri
        from runner.runner import _as_int, download
        from runner.senses import parse_sensors

        with self.assertRaises(RuntimeError) as caught:
            parse_dri({
                "dri": {
                    "enabled": False,
                    "triggers": {"key_probe": {"threshold": float("inf")}},
                },
            })
        self.assertIn("must be numbers", str(caught.exception))

        with self.assertRaises(RuntimeError) as caught:
            parse_sensors({
                "sensors": {
                    "disk": {
                        "enabled": True,
                        "key_id": "k",
                        "weight": float("inf"),
                    },
                },
            })
        self.assertIn("finite", str(caught.exception))

        self.assertEqual(_as_int(float("inf"), -1), -1)
        self.assertEqual(_as_int(float("-inf"), -1), -1)

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("runner.runner._open_download",
                            side_effect=RuntimeError("stop")):
                with self.assertRaises(RuntimeError):
                    download(
                        "https://example.invalid/x",
                        os.path.join(directory, "out"),
                        max_bytes=float("inf"))


class ResourceAndFragmentTest(unittest.TestCase):
    def test_infinite_cooldown_and_fragment_length_do_not_escape(self):
        from runner.resources import parse_resources
        from runner.runner import answer_queries, secret_fragment_hit
        from runner.senses import _path

        with self.assertRaises(RuntimeError) as caught:
            parse_resources({
                "resources": {"enabled": True, "cooldown_sec": float("inf")},
            })
        self.assertIn("finite", str(caught.exception))
        self.assertFalse(secret_fragment_hit(
            "hello", "hello", {}, min_len=float("inf")))

        with tempfile.TemporaryDirectory() as directory:
            with open(_path(directory), "w", encoding="utf-8") as fh:
                fh.write(
                    '{"sensor": "disk", "title": "hot", "severity": "info", '
                    '"weight": Infinity}\n')
            answers, _spent = answer_queries(
                [{"op": "senses"}], {}, {}, 5, cfg={}, base_dir=directory)
        item = answers[0]["alerts"][0]
        self.assertEqual(item["weight"], 1.0)
        self.assertEqual(item["weight"], item["weight"])


class RetentionAndGateTest(unittest.TestCase):
    def test_a_non_finite_timestamp_is_expired_and_does_not_silence(self):
        import time
        from runner.runner import retained_expired
        from runner.senses import gate_alert

        cfg = {"output_retention_days": 7}
        self.assertTrue(retained_expired({"saved_at": float("inf")}, cfg))
        self.assertTrue(retained_expired({"saved_at": float("nan")}, cfg))
        self.assertFalse(retained_expired({"saved_at": time.time()}, cfg))

        recent = [{"title": "hot", "received_at": "2026-10-16T00:00:00Z"}]
        self.assertIsNone(gate_alert(
            {"profile": {"cooldown_sec": float("inf")}},
            {"title": "hot", "severity": "info"}, recent, now=time.time()))
        reason = gate_alert(
            {"profile": {"max_per_hour": float("inf")}},
            {"title": "other", "severity": "info"}, recent, now=time.time())
        self.assertIn("unreadable cap", reason)


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
                # The log budget is process-global. Pytest (the mutation
                # job's clean run) can fill the minute before this test,
                # and an INFO line would be dropped. Start from empty.
                runner._LOG_MINUTE = 0.0
                runner._LOG_COUNT = 0
                runner._LOG_DROPPED = 0
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

    def test_the_event_source_points_at_the_system_message_file(self):
        import sys
        from runner import winlog

        class Key:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        class Reg:
            HKEY_LOCAL_MACHINE = object()
            REG_EXPAND_SZ = 2
            REG_DWORD = 4
            def __init__(self):
                self.created = []
                self.values = []
            def CreateKey(self, hive, path):
                self.created.append((hive, path))
                return Key()
            def SetValueEx(self, key, name, reserved, typ, value):
                self.values.append((name, typ, value))

        reg = Reg()
        sys.modules["winreg"] = reg
        try:
            winlog._ensure_source()
        finally:
            sys.modules.pop("winreg", None)
        self.assertIn("EventLog\\Application\\HomingPigeon",
                      reg.created[0][1])
        names = {name: value for name, _typ, value in reg.values}
        self.assertIn("EventCreate.exe", names["EventMessageFile"])
        self.assertEqual(names["TypesSupported"], 7)

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

        # browser_consent builds its listener from _ConsentServer
        # (the hardened HTTPServer subclass) since 3e61d86; patching
        # HTTPServer left a real listener waiting out the full
        # consent window and failing with "no sign-in code".
        with mock.patch("runner.oauth._ConsentServer", Server), \
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
                 _setup_fresh_config=mock.Mock(return_value=(True, "m", False)),
                 do_check=mock.Mock(return_value=0)):
            with redirect_stdout(buf):
                code = install.main()
            checked = install.do_check.called
        self.assertEqual(code, 2)
        self.assertIn("Windows-only", buf.getvalue())
        self.assertFalse(checked)


if __name__ == "__main__":
    unittest.main()
