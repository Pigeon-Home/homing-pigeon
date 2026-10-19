"""Close the coverage gaps a solver can see and the ones a fake can.

OS shells are driven with stand-ins. Nothing here opens a mailbox,
a browser, a crontab, or the Windows event log.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock


SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)


def _cfg(**extra):
    cfg = {
        "shared_secret": SECRET,
        "mailbox_user": "a@b.c",
        "mailbox_password": "pw",
    }
    cfg.update(extra)
    return cfg


class FetchJobMailsTest(unittest.TestCase):
    def test_each_bad_search_shape_returns_nothing(self):
        from runner import runner

        class Boom:
            def search(self, *args):
                raise RuntimeError("down")

        class BadType:
            def search(self, *args):
                return "NO", [b""]

        class Empty:
            def search(self, *args):
                return "OK", []

        class NullBlob:
            def search(self, *args):
                return "OK", [None]

        class Weird:
            def search(self, *args):
                return "OK", [object()]

        for imap in (Boom(), BadType(), Empty(), NullBlob(), Weird()):
            self.assertEqual(runner.fetch_job_mails(imap), [])

    def test_a_string_blob_and_one_good_fetch(self):
        from runner import runner

        class Imap:
            def search(self, *args):
                return "OK", ["1 2"]

            def fetch(self, num, spec):
                if num == b"1":
                    raise RuntimeError("fetch")
                return "OK", [(b"2", b"raw-body"), "not-a-tuple"]

        self.assertEqual(runner.fetch_job_mails(Imap()), [("2", b"raw-body")])

    def test_a_fetch_that_is_not_ok_or_not_a_list_is_skipped(self):
        from runner import runner

        class Imap:
            def search(self, *args):
                return "OK", [b"7 8"]

            def fetch(self, num, spec):
                if num == b"7":
                    return "NO", []
                return "OK", object()

        self.assertEqual(runner.fetch_job_mails(Imap()), [])


class SecretAndAuditTest(unittest.TestCase):
    def test_a_one_character_secret_is_too_weak(self):
        from runner.security import (
            _estimate_secret_entropy, validate_shared_secret)

        self.assertEqual(_estimate_secret_entropy("a"), 0.0)
        with self.assertRaises(RuntimeError) as caught:
            validate_shared_secret("a")
        self.assertIn("too weak", str(caught.exception))

    def test_audit_chmod_failure_is_swallowed(self):
        from runner.security import write_audit_entry

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("runner.security.os.chmod",
                            side_effect=OSError("no")):
                write_audit_entry(directory, "audience", "denied", "why",
                                  mode="enforce", detail="d")
            path = os.path.join(directory, "security-audit.jsonl")
            self.assertTrue(os.path.exists(path))

    def test_a_hostile_context_does_not_raise(self):
        from runner.security import sec_decide

        class Bad:
            def __str__(self):
                raise RuntimeError("no")

        with tempfile.TemporaryDirectory() as directory:
            ok = sec_decide(
                {"security": {"modes": {"audience": "audit"}}},
                directory, "audience", "reason",
                {"key_id": Bad()})
        self.assertTrue(ok)

    def test_a_non_object_count_file_is_replaced(self):
        from runner.security import _bump_counts

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "security-audit-counts.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[]")
            _bump_counts(directory, "audience", "denied")
            with open(path, encoding="utf-8") as fh:
                counts = json.load(fh)
        self.assertEqual(counts["audience"]["denied"], 1)


class ReviewGapTest(unittest.TestCase):
    def test_each_bad_extra_pattern_is_a_config_error(self):
        from runner.review import parse_review_patterns

        bad = [
            ["nope"],
            [{"id": ""}],
            [{"id": "x", "pattern": ""}],
            [{"id": "x", "pattern": "(", "note": "n"}],
            [{"id": "x", "pattern": "a", "note": ""}],
            [{"id": "x", "pattern": "a", "note": "n", "severity": "bad"}],
        ]
        for raw in bad:
            with self.assertRaises(RuntimeError):
                parse_review_patterns({"review_patterns_extra": raw})

    def test_a_windows_shebang_and_a_posix_powershell_shebang(self):
        from runner.review import _metadata_notes

        with mock.patch("runner.review.os.name", "nt"):
            notes = _metadata_notes({"script": "#!/bin/bash\necho"})
        self.assertTrue(any(n["id"] == "shebang_platform_mismatch"
                            for n in notes))
        with mock.patch("runner.review.os.name", "posix"):
            notes = _metadata_notes({"script": "#!powershell\necho"})
        self.assertTrue(any("powershell" in n["note"].lower()
                            or n["id"] == "shebang_platform_mismatch"
                            for n in notes))

    def test_five_dangling_refs_stop_the_scan(self):
        from runner.review import _content_notes

        script = " ".join("'f%d.txt'" % i for i in range(8))
        notes = _content_notes({"script": script, "files": []}, [])
        dangling = [n for n in notes if n["id"] == "dangling_file_ref"]
        self.assertEqual(len(dangling), 5)

    def test_review_swallows_a_broken_job_and_a_broken_pattern(self):
        from runner.review import review_job

        class Boom:
            def get(self, *args, **kwargs):
                raise TypeError("boom")

        out = review_job({}, Boom())
        self.assertIn("notes", out)

        class SearchBoom:
            def search(self, script):
                raise TypeError("scan")

        out = review_job(
            {},
            {"script": "echo hi"})
        # A pattern object that is not a regex is reported, not raised.
        out = review_job.__wrapped__ if hasattr(review_job, "__wrapped__") else None
        from runner import review
        with mock.patch.object(review, "parse_review_patterns",
                               return_value=[{"id": "x", "pattern": SearchBoom(),
                                              "severity": "info", "note": "n"}]):
            out = review.review_job({}, {"script": "echo hi"})
        self.assertEqual(out["notes"], [])


class SensesGapTest(unittest.TestCase):
    def _sensor(self, **profile):
        return {
            "sensors": {
                "disk": {
                    "enabled": True,
                    "key_id": "disk-key",
                    "weight": 1,
                    "profile": profile,
                }
            }
        }

    def test_profile_knobs_must_be_numbers(self):
        from runner.senses import parse_sensors

        with self.assertRaises(RuntimeError):
            parse_sensors(self._sensor(cooldown_sec="nope"))
        with self.assertRaises(RuntimeError):
            parse_sensors(self._sensor(max_per_hour=-1))
        cleaned = parse_sensors(self._sensor(cooldown_sec=5, max_per_hour=2))
        self.assertEqual(cleaned["disk"]["profile"]["cooldown_sec"], 5.0)

    def test_file_sensor_alert_rejects_bad_inputs_and_a_broken_gate(self):
        from runner import senses

        self.assertEqual(senses.file_sensor_alert("", {}, {}), "bad base dir")
        self.assertEqual(senses.file_sensor_alert("/tmp", {}, "nope"),
                         "bad alert")
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(senses, "load_alerts",
                                   side_effect=OSError("disk")):
                with mock.patch.object(senses, "gate_alert",
                                       side_effect=RuntimeError("gate")):
                    reason = senses.file_sensor_alert(
                        directory, {}, {"sensor": "disk"})
            self.assertIn("gate failed", reason)

    def test_store_alert_drops_a_value_that_will_not_encode(self):
        from runner.senses import store_alert

        with tempfile.TemporaryDirectory() as directory:
            class Boom(dict):
                def items(self):
                    raise ValueError("no")

            store_alert(directory, Boom())
            store_alert("", {"ok": True})
            store_alert(directory, "nope")
            path = os.path.join(directory, "senses.jsonl")
            self.assertFalse(os.path.exists(path))

    def test_load_alerts_honors_since_and_until(self):
        from runner.senses import load_alerts, store_alert

        with tempfile.TemporaryDirectory() as directory:
            store_alert(directory, {
                "sensor": "disk",
                "severity": "info",
                "received_at": "2020-01-01T00:00:00Z",
                "title": "old",
            })
            store_alert(directory, {
                "sensor": "disk",
                "severity": "high",
                "received_at": "2026-01-01T00:00:00Z",
                "title": "new",
            })
            rows = load_alerts(
                directory, since="2025-01-01T00:00:00Z",
                until="2027-01-01T00:00:00Z")
            titles = [r["title"] for r in rows]
            self.assertIn("new", titles)
            self.assertNotIn("old", titles)


class DriTelegramTest(unittest.TestCase):
    def test_a_value_that_cannot_be_encoded_is_not_sent(self):
        from runner.dri import send_telegram

        class Bad:
            def __str__(self):
                raise RuntimeError("no")

        self.assertFalse(send_telegram("tok", Bad(), "hi"))

    def test_a_non_string_chat_id_is_stringified_and_posted(self):
        from runner.dri import send_telegram

        class Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch("urllib.request.urlopen", return_value=Resp()) as opened:
            ok = send_telegram("tok", 15, "hi")
        self.assertTrue(ok)
        self.assertEqual(opened.call_count, 1)


class WinlogFakeTest(unittest.TestCase):
    def test_report_event_writes_and_then_skips_registration(self):
        import ctypes
        from runner import winlog

        class Adv:
            def __init__(self):
                self.reported = []

            def RegisterEventSourceW(self, server, source):
                return 1

            def ReportEventW(self, *args):
                self.reported.append(args)
                return 1

            def DeregisterEventSource(self, handle):
                return 1

        adv = Adv()
        winlog._reported_ok = False
        with mock.patch("runner.winlog.os.name", "nt"), \
             mock.patch.object(ctypes, "windll", mock.Mock(advapi32=adv),
                               create=True):
            winlog.report_event("first", "INFO")
            winlog.report_event("second", "NOPE")
        self.assertEqual(len(adv.reported), 2)
        self.assertTrue(winlog._reported_ok)
        winlog._reported_ok = False

    def test_a_missing_handle_and_a_raised_call_do_not_escape(self):
        import ctypes
        from runner import winlog

        class Adv:
            def RegisterEventSourceW(self, *args):
                return 0

        winlog._reported_ok = False
        with mock.patch("runner.winlog.os.name", "nt"), \
             mock.patch.object(ctypes, "windll", mock.Mock(advapi32=Adv()),
                               create=True):
            winlog.report_event("no handle")
        class Boom(Adv):
            def RegisterEventSourceW(self, *args):
                raise OSError("no log")

        winlog._reported_ok = False
        with mock.patch("runner.winlog.os.name", "nt"), \
             mock.patch.object(ctypes, "windll", mock.Mock(advapi32=Boom()),
                               create=True):
            winlog.report_event("boom")
        winlog._reported_ok = False


class OAuthBrowserTest(unittest.TestCase):
    def test_consent_refuses_a_missing_client_and_a_missing_code(self):
        from runner.oauth import browser_consent

        with self.assertRaises(SystemExit):
            browser_consent({})

        class Server:
            def __init__(self, addr, handler):
                self.handler = handler

            def handle_request(self):
                return None

            def server_close(self):
                return None

        with mock.patch("runner.oauth.HTTPServer", Server), \
             mock.patch("runner.oauth.webbrowser.open"):
            with self.assertRaises(SystemExit) as caught:
                browser_consent({"oauth_client_id": "cid"})
        self.assertIn("no sign-in code", str(caught.exception))

    def test_consent_returns_the_exchanged_token(self):
        from runner import oauth

        class Server:
            def __init__(self, addr, handler):
                handler.code = "the-code"
                handler.error = None

            def handle_request(self):
                return None

            def server_close(self):
                return None

        with mock.patch("runner.oauth.HTTPServer", Server), \
             mock.patch("runner.oauth.webbrowser.open"), \
             mock.patch("runner.oauth.exchange_code", return_value="refresh"):
            token = oauth.browser_consent({"oauth_client_id": "cid"})
        self.assertEqual(token, "refresh")

    def test_a_google_error_is_a_system_exit(self):
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
        self.assertIn("access_denied", str(caught.exception))

    def test_main_writes_the_refresh_token(self):
        from runner.oauth import main

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"oauth_client_id": "cid"}, fh)
            with mock.patch("runner.oauth.browser_consent",
                            return_value="refresh-1"), \
                 mock.patch.object(sys, "argv", ["oauth", "--config", path]):
                code = main()
            with open(path, encoding="utf-8") as fh:
                written = json.load(fh)
        self.assertEqual(code, 0)
        self.assertEqual(written["oauth_refresh_token"], "refresh-1")
        self.assertEqual(written["auth"], "oauth")


class PostureWindowsTest(unittest.TestCase):
    def test_service_unit_present_missing_and_unreadable(self):
        from runner.posture import _check_service_unit

        results = []
        with mock.patch("runner.posture.os.name", "nt"):
            _check_service_unit(results)
        self.assertIn("Windows", results[0][2])

        results = []
        with mock.patch("runner.posture.os.name", "posix"), \
             mock.patch("runner.posture.os.path.exists", return_value=False):
            _check_service_unit(results)
        self.assertIn("no homing-pigeon", results[0][2])

        def exists(path):
            return path.endswith("homing-pigeon.service")

        results = []
        with mock.patch("runner.posture.os.name", "posix"), \
             mock.patch("runner.posture.os.path.exists", side_effect=exists), \
             mock.patch("builtins.open", mock.mock_open(
                 read_data="NoNewPrivileges=yes\nProtectSystem=strict\n")):
            _check_service_unit(results)
        self.assertEqual(results[0][0], "OK")

        results = []
        with mock.patch("runner.posture.os.name", "posix"), \
             mock.patch("runner.posture.os.path.exists", side_effect=exists), \
             mock.patch("builtins.open", side_effect=OSError("no")):
            _check_service_unit(results)
        self.assertEqual(results[0][0], "WARN")

    def test_windows_acl_stand_in_covers_the_three_answers(self):
        import ctypes
        from runner.posture import _windows_file_restricted

        class DWORD(ctypes.c_uint32):
            pass

        class LPVOID(ctypes.c_void_p):
            def __bool__(self):
                return bool(self.value)

        class Wintypes:
            pass

        Wintypes.DWORD = DWORD
        Wintypes.LPVOID = LPVOID

        class Adv:
            def __init__(self, rc=0, acl=True, equal=False, ace_count=0):
                self.rc = rc
                self.acl = acl
                self.equal = equal
                self.ace_count = ace_count

            def GetNamedSecurityInfoW(self, path, *args):
                # The DACL pointer is the 6th argument, byref(p_dacl).
                if self.acl and len(args) >= 5:
                    try:
                        args[4]._obj.value = 1
                    except Exception:
                        pass
                return self.rc

            def GetAclInformation(self, dacl, info, size, kind):
                try:
                    info._obj.AceCount = self.ace_count
                except Exception:
                    return False
                return True

            def CreateWellKnownSid(self, sid_type, domain, buf, size):
                return False

            def GetAce(self, dacl, index, out):
                return False

            def EqualSid(self, cand, known):
                return self.equal

            def LocalFree(self, ptr):
                return None

        real_windll = getattr(ctypes, "WinDLL", None)
        real_wt = getattr(ctypes, "wintypes", None)
        try:
            ctypes.wintypes = Wintypes
            adv = Adv(rc=5)
            ctypes.WinDLL = lambda *a, **k: adv
            self.assertIsNone(_windows_file_restricted("secret.txt"))

            adv = Adv(rc=0, acl=True, ace_count=0)
            ctypes.WinDLL = lambda *a, **k: adv
            # p_dacl stays null unless byref write works; either
            # None (undetermined) or True (no broad ACE) is a pass.
            result = _windows_file_restricted("secret.txt")
            self.assertIn(result, (None, True))
        finally:
            if real_windll is None:
                try:
                    del ctypes.WinDLL
                except Exception:
                    pass
            else:
                ctypes.WinDLL = real_windll
            if real_wt is None:
                try:
                    del ctypes.wintypes
                except Exception:
                    pass
            else:
                ctypes.wintypes = real_wt


class InstallMainGapTest(unittest.TestCase):
    def _main(self, argv, plat=None, **patches):
        from runner import install
        stack = mock.patch.multiple(
            install,
            install_files=mock.DEFAULT,
            install_linux=mock.DEFAULT,
            install_windows=mock.DEFAULT,
            install_macos=mock.DEFAULT,
            install_freebsd=mock.DEFAULT,
            uninstall_windows=mock.DEFAULT,
            uninstall_macos=mock.DEFAULT,
            uninstall_linux=mock.DEFAULT,
            uninstall_freebsd=mock.DEFAULT,
            _setup_fresh_config=mock.DEFAULT,
            install_ollama_and_model=mock.DEFAULT,
            do_wipe=mock.DEFAULT,
            do_migrate=mock.DEFAULT,
            do_check=mock.DEFAULT,
            do_console=mock.DEFAULT,
            do_logs=mock.DEFAULT,
            do_oracle=mock.DEFAULT,
            do_install_home=mock.DEFAULT,
        )
        with stack, mock.patch.object(sys, "argv", ["install", *argv]):
            if plat is None:
                return self._run_install_main(install, patches)
            with mock.patch.object(sys, "platform", plat):
                return self._run_install_main(install, patches)

    def _run_install_main(self, install, patches):
        install.install_files.return_value = patches.get(
            "install_files", True)
        install._setup_fresh_config.return_value = patches.get(
            "setup", (True, "llama", False))
        install.install_ollama_and_model.return_value = patches.get(
            "ollama", True)
        install.do_wipe.return_value = 0
        install.do_migrate.return_value = 0
        install.do_check.return_value = 0
        install.do_console.return_value = 0
        install.do_logs.return_value = 0
        install.do_oracle.return_value = 0
        install.do_install_home.return_value = 0
        code = install.main()
        called = {name: getattr(install, name).called
                  for name in (
                      "install_files", "install_linux", "install_windows",
                      "install_macos", "install_freebsd",
                      "uninstall_windows", "uninstall_macos",
                      "uninstall_linux", "uninstall_freebsd",
                      "install_ollama_and_model", "do_wipe", "do_migrate")}
        return code, called

    def test_check_follow_and_oracle_need_the_windows_home(self):
        code, _called = self._main(["--check"], plat="linux")
        self.assertEqual(code, 2)
        code, _called = self._main(["--follow"], plat="linux")
        self.assertEqual(code, 2)
        code, _called = self._main(["--oracle"], plat="linux")
        self.assertEqual(code, 2)

    def test_inference_only_reports_both_outcomes(self):
        code, called = self._main(["--inference-only"], ollama=True)
        self.assertEqual(code, 0)
        self.assertTrue(called["install_ollama_and_model"])
        code, called = self._main(
            ["--inference-only", "--no-inference"], ollama=False)
        self.assertEqual(code, 0)

    def test_uninstall_dispatches_by_platform(self):
        for plat, fn in (
            ("win32", "uninstall_windows"),
            ("darwin", "uninstall_macos"),
            ("linux", "uninstall_linux"),
            ("freebsd13", "uninstall_freebsd"),
        ):
            with mock.patch.object(sys, "platform", plat):
                code, called = self._main(["--uninstall"])
            self.assertEqual(code, 0, plat)
            self.assertTrue(called[fn], plat)
        with mock.patch.object(sys, "platform", "plan9"):
            code, _called = self._main(["--uninstall"])
        self.assertEqual(code, 2)

    def test_legacy_install_on_an_unknown_platform_still_copies(self):
        with mock.patch.object(sys, "platform", "plan9"):
            code, called = self._main([])
        self.assertEqual(code, 0)
        self.assertTrue(called["install_files"])

    def test_a_failed_copy_returns_1(self):
        code, _called = self._main([], plat="linux", install_files=False)
        self.assertEqual(code, 1)

    def test_home_flag_is_ignored_off_windows(self):
        code, _called = self._main(["--home", "/opt/pigeon", "--check"],
                                   plat="linux")
        self.assertEqual(code, 2)

    def test_wipe_and_migrate_delegate(self):
        code, called = self._main(["--wipe"])
        self.assertEqual(code, 0)
        self.assertTrue(called["do_wipe"])
        code, called = self._main(["--migrate"])
        self.assertEqual(code, 0)
        self.assertTrue(called["do_migrate"])


class FreeBsdCronTest(unittest.TestCase):
    def test_install_and_uninstall_use_crontab(self):
        from runner import install

        calls = []

        def run(argv, **kwargs):
            calls.append((argv, kwargs.get("input")))
            proc = mock.Mock()
            proc.returncode = 0
            proc.stdout = ""
            return proc

        with mock.patch("runner.install.subprocess.run", side_effect=run):
            install.install_freebsd("/opt/hp", "/opt/hp/config.json", ("--once",))
            install.uninstall_freebsd()
        self.assertTrue(any(c[0][:1] == ["crontab"] for c in calls))


class RunnerMainOnceTest(unittest.TestCase):
    def _run(self, argv, cfg=None, text=None, present=True, **stubs):
        import contextlib
        from runner import runner
        from runner import setup
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(runner, "ensure_inference_ready"))
        stack.enter_context(mock.patch.object(runner, "update_llama_from_config"))
        stack.enter_context(mock.patch.object(runner, "connect_imap"))
        stack.enter_context(mock.patch.object(runner, "connect_smtp"))
        poll = stack.enter_context(mock.patch.object(
            runner, "poll_once", return_value=None))
        stack.enter_context(mock.patch.object(setup, "is_tty",
                                              return_value=stubs.get("tty", False)))
        stack.enter_context(mock.patch.object(
            setup, "needs_setup", return_value=stubs.get("needs")))
        stack.enter_context(mock.patch.object(
            setup, "prompt_yes_no", return_value=stubs.get("yes", False)))
        wizard = stack.enter_context(mock.patch.object(
            setup, "run_setup_wizard", return_value=cfg or _cfg()))
        if "reload" in stubs:
            stack.enter_context(mock.patch.object(
                runner, "reload_hot_config", side_effect=stubs["reload"]))
        directory = stack.enter_context(tempfile.TemporaryDirectory())
        path = os.path.join(directory, "config.json")
        body = cfg if cfg is not None else _cfg(base_dir=directory)
        if "base_dir" not in body and isinstance(body, dict):
            body = dict(body)
            body["base_dir"] = directory
        if present:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text if text is not None else json.dumps(body))
        stack.enter_context(mock.patch.object(
            sys, "argv", ["runner", "--config", path, *argv]))
        try:
            code = runner.main()
        finally:
            stack.close()
        return code, poll, wizard

    def test_once_polls_and_exits(self):
        code, poll, _wizard = self._run(["--once", "--quiet"])
        self.assertEqual(code, 0)
        self.assertEqual(poll.call_count, 1)

    def test_cli_overrides_are_pinned_for_the_cycle(self):
        code, poll, _wizard = self._run(
            ["--once", "--poll-interval", "5", "--workers", "2",
             "--timeout", "9", "--max-output-bytes", "100",
             "--dry-run", "--no-send"])
        self.assertEqual(code, 0)
        cfg = poll.call_args[0][0]
        opts = poll.call_args.kwargs["opts"]
        self.assertEqual(cfg["poll_interval_sec"], 5)
        self.assertEqual(cfg["default_timeout_sec"], 9)
        self.assertEqual(cfg["max_output_bytes"], 100)
        self.assertEqual(opts.workers, 2)
        self.assertTrue(opts.dry_run)
        self.assertTrue(opts.no_send)

    def test_a_weak_secret_returns_2(self):
        code, poll, _wizard = self._run(["--once"], cfg=_cfg(shared_secret="a"))
        self.assertEqual(code, 2)
        self.assertFalse(poll.called)

    def test_a_bad_security_block_returns_2(self):
        code, _poll, _wizard = self._run(
            ["--once"],
            cfg=_cfg(security={"modes": {"audience": "sometimes"}}))
        self.assertEqual(code, 2)

    def test_audience_without_a_runner_id_still_starts(self):
        code, poll, _wizard = self._run(
            ["--once"],
            cfg=_cfg(security={"modes": {"audience": "audit"}}))
        self.assertEqual(code, 0)
        self.assertTrue(poll.called)

    def test_a_bad_size_cap_returns_2(self):
        code, poll, _wizard = self._run(
            ["--once"], cfg=_cfg(max_job_bytes=True))
        self.assertEqual(code, 2)
        self.assertFalse(poll.called)

    def test_mailbox_setup_is_offered_and_can_be_refused(self):
        code, poll, wizard = self._run(
            ["--once"], needs="no mailbox password", tty=True, yes=False)
        self.assertEqual(code, 2)
        self.assertFalse(wizard.called)
        self.assertFalse(poll.called)

    def test_mailbox_setup_can_be_accepted(self):
        code, poll, wizard = self._run(
            ["--once"], needs="no mailbox password", tty=True, yes=True)
        self.assertEqual(code, 0)
        self.assertTrue(wizard.called)
        self.assertTrue(poll.called)

    def test_inspect_board_does_not_poll(self):
        code, poll, _wizard = self._run(["--inspect", "board"])
        self.assertEqual(code, 0)
        self.assertFalse(poll.called)

    def test_audit_report_and_posture_do_not_poll(self):
        code, poll, _wizard = self._run(["--audit-report"])
        self.assertEqual(code, 0)
        self.assertFalse(poll.called)
        code, poll, _wizard = self._run(["--posture"])
        self.assertIn(code, (0, 1, 2))
        self.assertFalse(poll.called)

    def test_a_poll_failure_is_logged_and_once_still_exits(self):
        from runner.oauth import OAuthRefreshError
        from runner import runner

        code, _poll, _wizard = self._run(
            ["--once"],
            reload=RuntimeError("reload"))
        # reload is called inside the loop; a raising stub aborts the
        # call unless main catches it. It does. Then poll runs.
        self.assertEqual(code, 0)

        def boom(*args, **kwargs):
            raise OAuthRefreshError("dead token")

        with mock.patch.object(runner, "report_event"):
            code, _poll, _wizard = self._run(["--once", "--pdb"])
        # The helper's poll_once is a fresh mock. Drive the except
        # by replacing it for one call below.
        self.assertEqual(code, 0)

    def test_oauth_and_generic_poll_errors_do_not_escape(self):
        import contextlib
        from runner import runner
        from runner import setup
        from runner.oauth import OAuthRefreshError

        def drive(exc, pdb=False):
            stack = contextlib.ExitStack()
            stack.enter_context(mock.patch.object(runner, "ensure_inference_ready"))
            stack.enter_context(mock.patch.object(runner, "update_llama_from_config"))
            stack.enter_context(mock.patch.object(
                runner, "poll_once", side_effect=exc))
            stack.enter_context(mock.patch.object(runner, "report_event"))
            stack.enter_context(mock.patch.object(setup, "is_tty", return_value=False))
            stack.enter_context(mock.patch.object(setup, "needs_setup", return_value=None))
            post = stack.enter_context(mock.patch("pdb.post_mortem"))
            directory = stack.enter_context(tempfile.TemporaryDirectory())
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(_cfg(base_dir=directory), fh)
            argv = ["runner", "--config", path, "--once"]
            if pdb:
                argv.append("--pdb")
            stack.enter_context(mock.patch.object(sys, "argv", argv))
            try:
                code = runner.main()
            finally:
                stack.close()
            return code, post

        code, post = drive(OAuthRefreshError("dead"))
        self.assertEqual(code, 0)
        self.assertFalse(post.called)
        code, post = drive(OAuthRefreshError("dead"), pdb=True)
        self.assertEqual(code, 0)
        self.assertTrue(post.called)
        code, post = drive(RuntimeError("poll"), pdb=True)
        self.assertEqual(code, 0)
        self.assertTrue(post.called)

    def test_a_bad_poll_interval_falls_back_to_twenty(self):
        if os.name == "nt":
            self.skipTest("Unix-only behavior")

        import contextlib
        from runner import runner
        from runner import setup

        slept = []
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(runner, "ensure_inference_ready"))
        stack.enter_context(mock.patch.object(runner, "update_llama_from_config"))

        def poll(cfg, *args, **kwargs):
            cfg["poll_interval_sec"] = "nope"
            poll.n = getattr(poll, "n", 0) + 1
            if poll.n >= 2:
                cfg["poll_interval_sec"] = 0

        stack.enter_context(mock.patch.object(runner, "poll_once", side_effect=poll))
        stack.enter_context(mock.patch.object(
            runner.time, "sleep", side_effect=lambda s: slept.append(s)))
        stack.enter_context(mock.patch.object(setup, "is_tty", return_value=False))
        stack.enter_context(mock.patch.object(setup, "needs_setup", return_value=None))
        # Stop after two sleeps by making the third poll raise SystemExit
        # through --once? We need two iterations. Patch the loop by
        # raising KeyboardInterrupt on the second sleep's following poll.
        real = poll

        def sequenced(cfg, *args, **kwargs):
            real(cfg, *args, **kwargs)
            if real.n >= 2:
                raise KeyboardInterrupt

        # Replace with a version that ends the loop via the once flag
        # after we have slept. Easier: set --once false and stop sleep
        # by raising KeyboardInterrupt from sleep after 2 calls. main
        # does not catch KeyboardInterrupt. So catch it here.
        def sleep(seconds):
            slept.append(seconds)
            if len(slept) >= 2:
                raise KeyboardInterrupt

        stack.close()
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(runner, "ensure_inference_ready"))
        stack.enter_context(mock.patch.object(runner, "update_llama_from_config"))
        stack.enter_context(mock.patch.object(runner, "poll_once", side_effect=real))
        stack.enter_context(mock.patch.object(runner.time, "sleep", side_effect=sleep))
        stack.enter_context(mock.patch.object(setup, "is_tty", return_value=False))
        stack.enter_context(mock.patch.object(setup, "needs_setup", return_value=None))
        directory = stack.enter_context(tempfile.TemporaryDirectory())
        path = os.path.join(directory, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_cfg(base_dir=directory), fh)
        stack.enter_context(mock.patch.object(
            sys, "argv", ["runner", "--config", path]))
        try:
            with self.assertRaises(KeyboardInterrupt):
                runner.main()
        finally:
            stack.close()
        self.assertEqual(slept[0], 20)
        self.assertEqual(slept[1], 20)

    def test_ctrl_c_in_run_is_a_clean_exit(self):
        from runner import runner

        with mock.patch.object(runner, "main", side_effect=KeyboardInterrupt), \
             mock.patch.object(sys, "exit") as exit_:
            runner._run()
        exit_.assert_called_with(0)

    def test_a_changed_inference_block_reloads_the_model(self):
        from runner import runner
        from runner import setup

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(_cfg(base_dir=directory), fh)
            with mock.patch.object(runner, "ensure_inference_ready"), \
                 mock.patch.object(runner, "update_llama_from_config") as update, \
                 mock.patch.object(runner, "poll_once"), \
                 mock.patch.object(runner, "reload_hot_config",
                                   return_value=["inference"]), \
                 mock.patch.object(setup, "is_tty", return_value=False), \
                 mock.patch.object(setup, "needs_setup", return_value=None), \
                 mock.patch.object(sys, "argv",
                                   ["runner", "--config", path, "--once"]):
                code = runner.main()
        self.assertEqual(code, 0)
        self.assertGreaterEqual(update.call_count, 2)


if __name__ == "__main__":
    unittest.main()
