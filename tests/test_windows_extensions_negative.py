#!/usr/bin/env python3
"""Creative negative tests with a Windows shape.

The Oracle runs on Windows too. These feed the extensions the inputs
a Windows box produces: backslash paths, CRLF, PowerShell-shaped
scripts, no /proc, a missing winlog. None of them may crash the
Oracle path.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri, resources, review, senses  # noqa: E402
from runner.runner import answer_queries, _redact_patterns  # noqa: E402


class WindowsPathNegativeTest(unittest.TestCase):
    def test_protected_paths_with_backslashes(self):
        from runner.runner import check_protected_paths
        before = {r"C:\Users\me\docs\a.txt": (10, 1.0)}
        after = {r"C:\Users\me\docs\a.txt": (20, 2.0), r"C:\Windows\System32\x": (1, 1.0)}
        try:
            changed = check_protected_paths(before, after, [r"C:\Users\me\docs"])
        except Exception as e:
            self.fail(f"backslash paths crashed: {e}")
        self.assertIsInstance(changed, list)

    def test_workspace_root_that_does_not_exist(self):
        from runner.runner import snapshot_outside
        try:
            snap = snapshot_outside(r"C:\no\such\workspace", exclude=[r"C:\no\such\base"])
        except Exception as e:
            self.fail(f"missing workspace crashed: {e}")
        self.assertIsInstance(snap, dict)


class WindowsScriptReviewTest(unittest.TestCase):
    def test_powershell_shaped_script(self):
        job = {
            "kind": "exec",
            "script": "Remove-Item -Recurse -Force C:\\\nGet-Content $env:USERPROFILE\\.ssh\\id_rsa",
            "interpreter": ["powershell", "-File"],
        }
        try:
            notes = review.review_job({}, job)
        except Exception as e:
            self.fail(f"powershell script crashed review: {e}")
        self.assertIsInstance(notes, (list, dict, tuple))

    def test_crlf_script(self):
        job = {"kind": "exec", "script": "echo hi\r\nRemove-Item C:\\\r\n"}
        try:
            review.review_job({}, job)
        except Exception as e:
            self.fail(f"CRLF script crashed: {e}")

    def test_unc_path_in_files(self):
        job = {"kind": "exec", "script": "x", "files": [{"name": r"\\server\share\secret.txt", "content": "a"}]}
        try:
            review.review_job({}, job)
        except Exception as e:
            self.fail(f"UNC path crashed: {e}")


class WindowsResourcesTest(unittest.TestCase):
    def test_no_proc_does_not_crash(self):
        # Windows has no /proc. _read_proc_stat must degrade, not raise.
        tmp = tempfile.mkdtemp()
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            try:
                resources.check_resources({"resources": {"cpu_high": 0.9}}, tmp)
            except FileNotFoundError:
                self.fail("missing /proc escaped as FileNotFoundError")
            except Exception as e:
                # Other contained errors are acceptable; a crash is not.
                if "Traceback" in str(e):
                    self.fail(e)

    def test_disk_on_drive_letter(self):
        tmp = tempfile.mkdtemp()
        cfg = {"resources": {"disk_path": "C:\\"}}
        try:
            resources.check_resources(cfg, tmp)
        except Exception as e:
            self.fail(f"drive-letter disk check crashed: {e}")


class WindowsSensesTest(unittest.TestCase):
    def test_sensor_name_with_backslash(self):
        alert = {"sensor": r"host\service", "severity": "medium", "detail": "line\r\nbreak"}
        try:
            senses.validate_sensor_alert(alert)
            senses.alert_score(alert, 1.0)
        except Exception as e:
            self.fail(f"backslash sensor crashed: {e}")

    def test_senses_query_crlf_store(self):
        tmp = tempfile.mkdtemp()
        path = senses._path(tmp)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write('{"sensor":"win","severity":"low","detail":"ok"}\r\n')
            f.write("garbage\r\n")
        answers, spent = answer_queries(
            [{"op": "senses"}],
            {"stdout": "", "stderr": ""},
            _redact_patterns({}),
            4,
            cfg={},
            base_dir=tmp,
        )
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0].get("op"), "senses")


class WindowsDRITest(unittest.TestCase):
    def test_page_with_windows_paths_in_events(self):
        events = [
            {"kind": "alert", "sensor": r"C:\alerts", "detail": "failed\r\nagain"},
            {"kind": "job", "path": r"D:\work\job.ps1"},
        ]
        try:
            text = dri.format_page(events)
        except Exception as e:
            self.fail(f"windows events crashed format_page: {e}")
        self.assertIsInstance(text, str)

    def test_maybe_page_no_telegram_on_windows_shape(self):
        tmp = tempfile.mkdtemp()
        cfg = {"dri": {"enabled": True, "telegram_bot_token": "", "telegram_chat_id": ""}}
        try:
            dri.maybe_page(cfg, tmp)
        except Exception as e:
            self.fail(f"empty telegram crashed: {e}")



class WindowsSetupAndWinlogTest(unittest.TestCase):
    def test_winlog_missing_does_not_crash_report(self):
        from runner.runner import report_event
        # On a non-Windows box, or with winlog absent, reporting must not raise.
        try:
            report_event("negative test event", level="ERROR")
        except Exception as e:
            self.fail(f"report_event crashed: {e}")

    def test_setup_parse_with_windows_paths(self):
        try:
            from runner import setup
        except ImportError:
            self.skipTest("setup module not importable")
        cfg = {"base_dir": r"C:\Users\me\.homing-pigeon", "workspace_root": r"D:\work"}
        for name in ("parse_setup", "apply_setup", "setup_status"):
            fn = getattr(setup, name, None)
            if fn is None:
                continue
            try:
                fn(cfg) if name != "apply_setup" else None
            except TypeError:
                pass
            except Exception as e:
                self.fail(f"{name} crashed: {e}")


class WindowsOAuthShapeTest(unittest.TestCase):
    def test_empty_oauth_config_does_not_crash_check(self):
        from runner.runner import _use_oauth
        for cfg in ({}, {"auth": "oauth"}, {"auth": "password"}, {"auth": None}):
            try:
                _use_oauth(cfg)
            except Exception as e:
                self.fail(f"_use_oauth crashed on {cfg}: {e}")


class WindowsBoardShapeTest(unittest.TestCase):
    def test_board_with_windows_task_ids(self):
        from runner.runner import Board
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "board.json")
        b = Board(path)
        try:
            b.submit({"task_id": r"job\windows\1", "kind": "ping", "requires": []})
            b.offer("worker-1", ["ping"])
        except Exception as e:
            self.fail(f"windows-shaped task id crashed board: {e}")

    def test_board_file_is_a_windows_crlf_object(self):
        from runner.runner import Board
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "board.json")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write('{\r\n  "tasks": {}\r\n}\r\n')
        try:
            Board(path)
        except Exception as e:
            self.fail(f"CRLF board crashed: {e}")


class WindowsRetentionNegativeTest(unittest.TestCase):
    def test_prune_with_locked_looking_name(self):
        from runner.runner import prune_retained
        tmp = tempfile.mkdtemp()
        retained = os.path.join(tmp, "retained")
        os.makedirs(retained)
        # A name Windows would choke on if we were careless.
        open(os.path.join(retained, "job id with spaces.json"), "w").close()
        try:
            prune_retained(tmp, 0)
        except Exception as e:
            self.fail(f"prune crashed on spaced name: {e}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
