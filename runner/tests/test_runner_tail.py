"""The branches the 90 percent run still missed, as their own suites.

Each test calls the function the runner calls. Windows parsers get
their tool output handed to them. Nothing here starts a real daemon
or a real setuid. The job-user syscalls stay untested.
"""
import json
import os
import tempfile
import unittest
from email.message import EmailMessage
from unittest import mock

from runner.tests.security_parity import (
    SECRET, FakeIMAP, FakeSMTP, _email, _payload, base_config)


def _result_text(msg):
    """Inner signed text of a result mail, unwrapping the hp_enc
    envelope an encrypted job's result mirrors. Falls back to the
    raw body when the mail is not a verifiable envelope."""
    from runner.wire import jobcrypto
    from runner.runner import verify_body
    text = msg.get_content()
    try:
        body = verify_body(text, SECRET)
        if jobcrypto.is_envelope(body):
            job_id = str(msg["Subject"]).rsplit(" ", 1)[-1]
            return jobcrypto.decrypt_body(
                body, SECRET, job_id, body.get("key_id") or "")
    except Exception:
        pass
    return text


NS = "{http://schemas.microsoft.com/win/2004/08/events/event}"
EVENT_XML = (
    '<Events xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
    "<Event><System>"
    '<Provider Name="Logon"/>'
    "<EventID>4625</EventID>"
    "<Level>2</Level>"
    '<TimeCreated SystemTime="2020-01-01T00:00:00Z"/>'
    "</System>"
    "<EventData><Data>alice</Data><Data>bad</Data>"
    "<Data>three</Data><Data>four</Data></EventData>"
    "</Event>"
    "<Event><Nope/></Event>"
    "<Event><System>"
    "<EventID>nope</EventID><Level>nope</Level>"
    "</System></Event>"
    "</Events>"
)


class ExecuteEdgesTest(unittest.TestCase):
    def test_poison_shapes_and_a_failed_download(self):
        from runner.runner import JobRejected, execute_job
        with tempfile.TemporaryDirectory() as d:
            ping = execute_job(None, {"kind": "ping", "job_id": "p"}, d)
            self.assertEqual(ping["stdout"], "pong")
            with self.assertRaises(JobRejected):
                execute_job({}, {
                    "kind": "exec", "job_id": "sha",
                    "files": [{"name": "a", "url": "http://x", "sha384": 1}],
                    "script": "echo",
                }, d)
            with self.assertRaises(JobRejected):
                execute_job({}, {
                    "kind": "exec", "job_id": "ssha", "script": "echo",
                    "script_sha384": 1,
                }, d)
            with self.assertRaises(JobRejected):
                execute_job({}, {
                    "kind": "exec", "job_id": "nul", "script": "echo",
                    "interpreter": ["sh\x00"],
                }, d)
            with mock.patch("runner.runner.download", side_effect=RuntimeError("net")):
                with self.assertRaises(RuntimeError):
                    execute_job({}, {
                        "kind": "exec", "job_id": "dl",
                        "files": [{"name": "a.txt", "url": "http://example.test/a"}],
                        "script": "echo",
                    }, d)
                with self.assertRaises(RuntimeError):
                    execute_job({}, {
                        "kind": "exec", "job_id": "sdl",
                        "script_url": "http://example.test/s",
                    }, d)

    def test_a_script_hash_mismatch_and_a_long_stderr(self):
        from runner.runner import JobRejected, execute_job

        def write(url, dest, max_bytes=None):
            with open(dest, "wb") as fh:
                fh.write(b"echo hi\n")

        with tempfile.TemporaryDirectory() as d:
            with mock.patch("runner.runner.download", side_effect=write):
                with self.assertRaises(JobRejected) as caught:
                    execute_job({}, {
                        "kind": "exec", "job_id": "mis",
                        "script_url": "http://example.test/s",
                        "script_sha384": "0" * 96,
                    }, d)
            self.assertIn("SHA384", str(caught.exception))
            result = execute_job(
                {"max_output_bytes": 8},
                {"kind": "exec", "job_id": "err",
                 "script": "python3 -c 'import sys; sys.stderr.write(\"e\"*40)'"},
                d)
            self.assertTrue(result["stderr_truncated"])
            self.assertLessEqual(len(result["stderr"]), 8)

    def test_a_scan_that_raises_does_not_fail_the_job(self):
        from runner.runner import execute_job
        with tempfile.TemporaryDirectory() as d, \
             mock.patch("runner.runner._artifact_findings", side_effect=RuntimeError("scan")):
            result = execute_job({}, {
                "kind": "exec", "job_id": "scan", "script": "echo ok",
            }, d)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["artifact_scan"], [])


class MailTailTest(unittest.TestCase):
    def test_detection_scan_and_a_protected_path(self):
        from runner.runner import poll_once
        with tempfile.TemporaryDirectory() as d:
            other = tempfile.mkdtemp()
            ws = os.path.join(other, "ws")
            os.makedirs(ws)
            watched = os.path.join(other, "watched.txt")
            with open(watched, "w", encoding="utf-8") as fh:
                fh.write("before")
            cfg = base_config(d)
            cfg["max_script_bytes"] = "nope"
            cfg["workspace_root"] = ws
            cfg["protected_paths"] = [watched]
            payload = _payload(
                "det-1", kind="exec", script="echo eval(",
                plan=[{"timeout_sec": 90}] * 9,
                result_policy={"queries": "nope"})

            def ran(cfg, job, base):
                with open(watched, "w", encoding="utf-8") as fh:
                    fh.write("after")
                return {
                    "stdout": "x" * 100001, "stderr": "", "exit_code": 0,
                    "timed_out": False, "duration_sec": 0.1,
                    "artifact_scan": ["yara hit"],
                }

            imap = FakeIMAP([_email(payload)])
            smtp = FakeSMTP()
            with mock.patch("runner.runner.execute_job", side_effect=ran):
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=imap, smtp=smtp)
            sent = _result_text(smtp.sent[-1])
            self.assertIn("detection_hits", sent)
            self.assertIn("plan_budget", sent)
            self.assertIn("artifact_scan", sent)
            self.assertIn("protected_paths_changed", sent)
            retained = os.listdir(os.path.join(d, "retained"))
            self.assertTrue(any(name.startswith("det-1") for name in retained))

    def test_a_rejection_that_cannot_be_sent_is_logged(self):
        from runner.runner import poll_once
        with tempfile.TemporaryDirectory() as d:
            cfg = base_config(d)
            payload = _payload("bad-kind", kind="nope")
            imap = FakeIMAP([_email(payload)])
            smtp = FakeSMTP()
            with mock.patch("runner.runner.send_mail", side_effect=RuntimeError("down")):
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=imap, smtp=smtp)
            self.assertEqual(smtp.sent, [])


class BoardTailTest(unittest.TestCase):
    def _board(self, d):
        from runner.runner import Board
        return Board(os.path.join(d, "board.json"))

    def test_offer_skips_bad_rows_and_a_blocked_dag(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            board.tasks = {
                1: "not-a-task",
                "claimed": {"state": "claimed", "claimed_by": "w", "task_id": "claimed"},
                "hidden": {"state": "open", "task_id": "hidden",
                           "compartments": ["red"], "capabilities": [],
                           "requires": [], "priority": True},
                "need": {"state": "open", "task_id": "need",
                         "capabilities": ["root"], "compartments": [],
                         "requires": [], "priority": float("nan")},
                "blocked": {"state": "open", "task_id": "blocked",
                            "capabilities": [], "compartments": [],
                            "requires": [{"nope": 1}, "missing"],
                            "priority": 1},
                "open": {"state": "open", "task_id": "open",
                         "capabilities": ["sh"], "compartments": ["blue"],
                         "requires": [], "priority": 2,
                         "submitted_at": "b"},
            }

            class Boom:
                def __eq__(self, other):
                    raise RuntimeError("cmp")

            cfg_blocked = {
                "worker_allowlist": [Boom()],
                "worker_compartments": {"w": ["blue"]},
                "dag_mode": "enforce",
            }
            self.assertIsNone(board.offer(Boom(), ["sh"], cfg=cfg_blocked))
            chosen = board.offer("w", ["sh"], cfg={
                "worker_allowlist": ["w"],
                "worker_compartments": {"w": ["blue"]},
                "dag_mode": "enforce",
            })
            self.assertEqual(chosen["task_id"], "claimed")

    def test_task_approve_and_a_board_that_raises(self):
        from runner.wire import jobcrypto
        from runner.cloud.send_job import sign_payload
        from runner.runner import Board, handle_board_mail
        with tempfile.TemporaryDirectory() as d:
            board = Board(os.path.join(d, "board.json"))
            board.tasks["t1"] = {"task_id": "t1", "state": "pending_review"}

            def _approve(task_id):
                signed = sign_payload(
                    {"v": 1, "type": "task_approve"}, SECRET)
                return jobcrypto.encrypt_body(
                    signed, SECRET, job_id=task_id, key_id="",
                    sign=sign_payload)

            msg = EmailMessage()
            msg["Subject"] = "[HOMING-PIGEON] task_approve t1"
            msg.set_content(_approve("t1"))
            cfg = base_config(d)
            imap = FakeIMAP([])
            smtp = FakeSMTP()
            handled = handle_board_mail(
                cfg, imap, smtp, "1", msg.as_bytes(), msg["Subject"],
                board, {"": SECRET}, None, d)
            self.assertTrue(handled)
            self.assertEqual(board.tasks["t1"]["state"], "done")
            self.assertTrue(smtp.sent)

            def explode(task_id):
                raise RuntimeError("board")

            board.approve = explode
            msg2 = EmailMessage()
            msg2["Subject"] = "[HOMING-PIGEON] task_approve t2"
            msg2.set_content(_approve("t2"))
            smtp2 = FakeSMTP()
            handled = handle_board_mail(
                cfg, imap, smtp2, "2", msg2.as_bytes(), msg2["Subject"],
                board, {"": SECRET}, None, d)
            self.assertTrue(handled)


class WatchTailTest(unittest.TestCase):
    def test_canary_unreadable_restored_and_a_snapshot_that_cannot_save(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as d:
            runner._canary_watch(d)
            name = runner._CANARY_NAMES[0]
            snap = os.path.join(d, "canary-watch.json")
            with open(snap, encoding="utf-8") as fh:
                old = json.load(fh)
            old["files"][name] = {"exists": False, "hash": "gone"}
            old["alerted"] = {name: "deleted"}
            with open(snap, "w", encoding="utf-8") as fh:
                json.dump(old, fh)
            text = runner._canary_watch(d)
            self.assertIn("untouched", text)
            real_open = open

            def fail_write(path, *args, **kwargs):
                if str(path).endswith("canary-watch.json") and "w" in args:
                    raise OSError("full")
                return real_open(path, *args, **kwargs)

            with mock.patch("builtins.open", side_effect=fail_write):
                runner._canary_watch(d)

            states = {n: "?" for n in runner._CANARY_NAMES}
            with mock.patch.object(runner, "_canary_state", side_effect=lambda p: states.get(os.path.basename(p))):
                quiet = runner._canary_watch(d)
            self.assertNotIn("TRIPPED", quiet)

    def test_yara_parses_hits_and_survives_a_dead_tool(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "note.txt")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("x")

            def which(name):
                return "/usr/bin/yara" if name == "yara" else None

            class Proc:
                stdout = "EvilRule " + target + "\nwarning skip me\n\n"

            with mock.patch.object(runner.shutil, "which", side_effect=which), \
                 mock.patch.object(runner.subprocess, "run", return_value=Proc()):
                hits = runner._yara_hits(d, [target], {})
            self.assertTrue(any("EvilRule" in h for h in hits))
            with mock.patch.object(runner.shutil, "which", side_effect=which), \
                 mock.patch.object(runner.subprocess, "run", side_effect=RuntimeError("down")), \
                 mock.patch.object(runner.tempfile, "mkstemp", side_effect=OSError("no tmp")):
                self.assertEqual(runner._yara_hits(d, [target], {}), [])
            with mock.patch.object(runner.shutil, "which", side_effect=which), \
                 mock.patch.object(runner.subprocess, "run", side_effect=RuntimeError("down")):
                self.assertEqual(runner._yara_hits(d, [target], {}), [])

    def test_event_log_parser_and_registry_diff(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(runner.sys, "platform", "win32"), \
             mock.patch.object(runner, "_wevtutil_query", return_value=EVENT_XML):
            text = runner._eventlog_tail(max_events=30, max_chars=40, base_dir=d)
        self.assertIn("alice", text)
        self.assertLess(len(text), 80)
        key = runner._REG_WATCH_KEYS[0]
        snap = {
            "keys": {
                key: {f"n{i}": str(i) for i in range(20)},
                key + "\x00raw": {f"n{i}": "v" for i in range(20)},
            },
            "services": {"count": 4, "hash": "new"},
        }
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(runner.sys, "platform", "win32"), \
             mock.patch.object(runner, "_registry_snapshot", return_value=snap):
            first = runner._registry_watch(d, max_chars=80)
            self.assertIn("baseline", first)
            old = {
                "keys": {key: "not-a-dict"},
                "services": {"count": "nope", "hash": "old"},
            }
            with open(os.path.join(d, "oracle-regwatch.json"), "w", encoding="utf-8") as fh:
                json.dump(old, fh)
            second = runner._registry_watch(d, max_chars=5000)
        self.assertIn("services:", second)
        self.assertIn("[T1543.003]", second)


class PolicyAndQueryTest(unittest.TestCase):
    def test_policy_skips_bad_names_and_a_broken_pattern(self):
        from runner.runner import check_policy_constraints
        findings = check_policy_constraints(
            {"allowed_env": ["OK"], "args_pattern": "(",
             "allowed_script_sha384": "abc", "allowed_files": ["keep"]},
            "k", {},
            {"kind": "exec",
             "env": {1: "a", "NOPE": "b"},
             "args": [1, "zz"],
             "files": ["bad", {"name": 1}, {"name": "keep", "url": "http://x"},
                       {"name": "other"}]})
        reasons = [item[1] for item in findings]
        self.assertIn("env_not_allowed", reasons)

    def test_queries_budget_attest_and_a_sensor_parse_failure(self):
        from runner import runner
        answers, spent = runner.answer_queries(
            [{"op": "attest"}, {"op": "ask", "max_chars": "nope", "question": "q"},
             {"op": "senses"}],
            {"stdout": "hi", "exit_code": 0}, {}, -1,
            cfg={"inference": {"endpoint": "http://127.0.0.1:9/v1", "model": "m",
                               "max_answer_chars": 20}},
            base_dir=None)
        self.assertEqual(spent, 3)
        self.assertTrue(all(item.get("rejected") == "budget" for item in answers))
        with tempfile.TemporaryDirectory() as base, \
             mock.patch.object(runner._senses, "parse_sensors", side_effect=RuntimeError("bad")), \
             mock.patch.object(runner._senses, "load_alerts", return_value=[{
                 "sensor": "host", "severity": "low", "title": "t",
                 "detail": 5, "weight": "nope"}]):
            sensed, spent = runner.answer_queries(
                [{"op": "senses"}], {"stdout": ""}, {}, 4,
                cfg={}, base_dir=base)
        self.assertEqual(spent, 1)
        self.assertEqual(sensed[0]["op"], "senses")
        self.assertEqual(sensed[0]["count"], 1)
        self.assertEqual(sensed[0]["alerts"][0]["detail"], "")
        self.assertEqual(sensed[0]["alerts"][0]["weight"], 1.0)


class ToolAndModelTailTest(unittest.TestCase):
    def test_tool_errors_that_are_not_os_errors(self):
        from runner import runner
        with mock.patch("builtins.open", side_effect=RuntimeError("read")):
            self.assertIn("cannot read", runner._run_oracle_tool(
                "read_file", {"path": "/tmp/hp-face-read"}))
        self.assertIn("path must", runner._run_oracle_tool("list_dir", {"path": ""}))
        with mock.patch.object(runner.os, "listdir", side_effect=RuntimeError("list")):
            self.assertIn("cannot list", runner._run_oracle_tool(
                "list_dir", {"path": "/tmp"}))
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(runner.os.path, "isdir", side_effect=OSError("stat")):
            listing = runner._run_oracle_tool("list_dir", {"path": d})
        self.assertTrue(listing)
        with mock.patch.object(runner.os, "makedirs", side_effect=RuntimeError("write")):
            self.assertIn("cannot write", runner._run_oracle_tool(
                "write_file", {"path": "/tmp/hp-face-write", "content": "hi"}))
        with mock.patch.object(runner.subprocess, "run", side_effect=RuntimeError("run")):
            self.assertIn("cannot run", runner._run_oracle_tool(
                "run", {"command": "true"}))

    def test_tool_call_parser_and_a_dead_model(self):
        from runner.runner import _ask_model_once, _parse_tool_calls
        parsed = _parse_tool_calls({
            "tool_calls": [
                "nope",
                {"function": "nope"},
                {"function": {"name": "read_file", "arguments": "{"}},
                {"function": {"name": "list_dir", "arguments": [1]}},
                {"id": "", "function": {"name": "run", "arguments": {}}},
            ]
        })
        self.assertGreaterEqual(len(parsed), 2)
        self.assertEqual(parsed[-1][0], "call-1")

        class Err(Exception):
            def read(self):
                raise RuntimeError("body")

        def opener(req, timeout=60):
            raise Err("http")

        ans = _ask_model_once(
            {"endpoint": "http://127.0.0.1:9/v1", "model": "m", "timeout_sec": 0},
            "q", "", 20, opener=opener)
        self.assertEqual(ans["rejected"], "inference_error")
        self.assertEqual(
            _ask_model_once(["nope"], "q", "", 20)["rejected"],
            "inference_unconfigured")

    def test_agent_wall_clock_and_a_non_string_reply(self):
        from runner import runner
        cfg = {"endpoint": "http://127.0.0.1:9/v1", "model": "m",
               "timeout_sec": 0, "agent_wall_clock_sec": 0}
        seen = {"n": 0}

        def chat(cfg, messages, tools, opener, timeout):
            seen["n"] += 1
            if tools is None:
                return {"role": "error"}
            return {"role": "assistant", "content": None}

        with mock.patch.object(runner, "_inference_chat", side_effect=chat), \
             mock.patch.object(runner, "_parse_tool_calls", return_value=[]):
            ans = runner.ask_model_agent(cfg, "q", "", 20)
        self.assertEqual(ans.get("rejected") or ans.get("op"), ans.get("rejected") or "ask")

    def test_endpoint_resolver_failures(self):
        from runner import runner
        with mock.patch.object(runner, "urlparse", side_effect=RuntimeError("bad")):
            self.assertFalse(runner._endpoint_is_loopback("http://127.0.0.1/v1"))
        with mock.patch.object(runner.socket, "getaddrinfo", return_value=[]):
            self.assertFalse(runner._endpoint_is_loopback("http://loop.example/v1"))
        with mock.patch.object(runner.socket, "getaddrinfo",
                               return_value=[(0, 0, 0, "", ("not-an-ip", 80))]):
            self.assertFalse(runner._endpoint_is_loopback("http://loop.example/v1"))
        with mock.patch.object(runner.socket, "getaddrinfo",
                               return_value=[(0, 0, 0, "", ("127.0.0.1", 80))]):
            self.assertTrue(runner._endpoint_is_loopback("http://loop.example/v1"))

    def test_secret_fragment_bounds(self):
        from runner.runner import secret_fragment_hit
        self.assertFalse(secret_fragment_hit("abc", "abc", {1: 2}, min_len=True))
        self.assertFalse(secret_fragment_hit("abc", "abc", {"a": "("}, min_len=0))
        self.assertFalse(secret_fragment_hit("zzzzzzzz", "token zzzzzzzz", {"a": "token (z+)"}, min_len=8) is None)


class DownloadAndScanTest(unittest.TestCase):
    def test_download_caps_and_a_server_error(self):
        from runner.runner import JobRejected, download
        from urllib.error import HTTPError

        class Body:
            def __init__(self, data):
                self.data = data
            def read(self, n):
                chunk, self.data = self.data[:n], self.data[n:]
                return chunk
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "out")
            with mock.patch("runner.runner._open_download", return_value=Body(b"abcdef")):
                download("https://example.test/a", dest, max_bytes=0)
                self.assertTrue(os.path.exists(dest))
            with mock.patch("runner.runner._open_download", return_value=Body(b"abcdef")):
                with self.assertRaises(JobRejected):
                    download("https://example.test/a", dest, max_bytes=3)
            err = HTTPError("https://example.test/a", 500, "no", hdrs=None, fp=None)
            with mock.patch("runner.runner._open_download", side_effect=err):
                with self.assertRaises(HTTPError):
                    download("https://example.test/a", dest, max_bytes="nope")

    def test_artifact_scan_stops_and_survives_a_walk_error(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(runner, "_work_files", side_effect=RuntimeError("walk")):
                self.assertEqual(runner._artifact_findings(d, {}, {}), [])
            big = {os.path.join(d, f"f{i}"): (10, i) for i in range(45)}
            big[os.path.join(d, "huge")] = ("nope", 0)
            with mock.patch.object(runner, "_work_files", return_value=big), \
                 mock.patch.object(runner, "_yara_hits", return_value=["y"]), \
                 mock.patch.object(runner, "_clam_hits", side_effect=RuntimeError("clam")):
                hits = runner._artifact_findings(d, {}, {})
            self.assertEqual(hits, ["y"])

    def test_log_rotation_bounds(self):
        from runner.runner import append_bounded_log
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.log")
            append_bounded_log(path, "hello", max_bytes=0, backups=0)
            append_bounded_log(path, "x" * 50, max_bytes=8, backups=200)
            with mock.patch("runner.runner.os.replace", side_effect=OSError("busy")):
                append_bounded_log(path, "more", max_bytes=4, backups=2)
            with mock.patch("runner.runner.os.makedirs", side_effect=RuntimeError("no")):
                append_bounded_log(os.path.join(d, "sub", "b.log"), "z")
            self.assertTrue(os.path.exists(path))


class StartupTailTest(unittest.TestCase):
    def test_poll_closes_a_connection_that_fails(self):
        from runner import runner

        class Conn:
            def logout(self):
                raise RuntimeError("imap")
            def quit(self):
                raise RuntimeError("smtp")

        with tempfile.TemporaryDirectory() as d:
            cfg = base_config(d)
            with mock.patch.object(runner, "connect_imap", return_value=Conn()), \
                 mock.patch.object(runner, "connect_smtp", return_value=Conn()), \
                 mock.patch.object(runner, "fetch_job_mails", return_value=[]):
                runner.poll_once(cfg, d, {}, os.path.join(d, "seen.json"))

    def test_snapshot_walk_failures_and_the_file_cap(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as d:
            ws = os.path.join(d, "ws")
            os.makedirs(ws)
            with mock.patch.object(runner.os, "walk", side_effect=OSError("no")):
                self.assertEqual(runner.snapshot_outside(ws), {})

            def walk(path):
                yield os.path.dirname(ws), [], ["f"] * 50001
                raise OSError("mid")

            real_stat = os.stat

            def stat(path, *args, **kwargs):
                try:
                    return real_stat(path, *args, **kwargs)
                except OSError:
                    return type("S", (), {"st_size": 1, "st_mtime": 1, "st_mode": 0o100644})()

            with mock.patch.object(runner.os, "walk", side_effect=walk), \
                 mock.patch.object(runner.os, "stat", side_effect=stat):
                snap = runner.snapshot_outside(ws)
            self.assertTrue(snap)

    def test_inference_start_and_oracle_open_failures(self):
        from runner import runner
        cfg = {"inference": {"endpoint": "http://127.0.0.1:9/v1", "model": "m"},
               "base_dir": tempfile.mkdtemp(), "oracle_log": True}
        with mock.patch.object(runner.socket, "create_connection", side_effect=OSError("down")), \
             mock.patch.object(runner.shutil, "which", return_value=None):
            runner.ensure_inference_ready(cfg)
        with mock.patch.object(runner.socket, "create_connection", side_effect=OSError("down")), \
             mock.patch.object(runner.shutil, "which", return_value="/usr/bin/ollama"), \
             mock.patch.object(runner, "_spawn_daemon", side_effect=OSError("no")):
            runner.ensure_inference_ready(cfg)
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(runner, "make_oracle_server") as made, \
             mock.patch.object(runner, "record_oracle_turn",
                               side_effect=lambda *a, **k: (_ for _ in ()).throw(OSError("full"))
                               if k.get("event") == "open" else None), \
             mock.patch.object(runner, "_inference_chat", side_effect=RuntimeError("warm")):
            server = mock.Mock()
            server.socket.getsockname.return_value = ("127.0.0.1", 9)
            server.serve_forever.side_effect = KeyboardInterrupt
            server.server_close.return_value = None
            made.return_value = server
            code = runner.oracle_window(
                {"base_dir": d, "inference": {
                    "endpoint": "http://127.0.0.1:9/v1", "model": "m"}},
                open_browser=False)
        self.assertEqual(code, 0)

    def test_setup_ports_and_diagnose(self):
        import contextlib
        import sys
        from runner import runner
        from runner.ops import setup
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(setup, "is_tty", return_value=True))
            stack.enter_context(mock.patch.object(setup, "prompt_yes_no", return_value=True))
            stack.enter_context(mock.patch.object(
                setup, "run_setup_wizard",
                return_value={
                    "shared_secret": "0123456789abcdef" * 4,
                    "mailbox_user": "a@b.c",
                    "mailbox_password": "pw",
                    "imap_port": 993,
                    "smtp_port": 587,
                }))
            stack.enter_context(mock.patch.object(setup, "needs_setup", return_value=None))
            harness = stack.enter_context(mock.patch("runner.ops.harness.main", return_value=5))
            stack.enter_context(mock.patch.object(runner, "ensure_inference_ready"))
            directory = stack.enter_context(tempfile.TemporaryDirectory())
            path = os.path.join(directory, "missing.json")
            stack.enter_context(mock.patch.object(
                sys, "argv", ["runner", "--config", path, "--diagnose"]))
            code = runner.main()
        self.assertEqual(code, 5)
        self.assertEqual(harness.call_count, 1)

    def test_oracle_status_while_thinking_and_a_non_loopback_bind(self):
        import threading
        import time
        import urllib.request
        from runner import runner
        # The ask handler writes the chat log in this directory.
        # On Windows that handle outlives serve_forever, so a
        # context-manager cleanup dies with WinError 145. Shut
        # the server down, then retry the remove.
        tmp = tempfile.TemporaryDirectory()
        d = tmp.name
        try:
            httpd = runner.make_oracle_server({"base_dir": d}, "127.0.0.1", 0, base_dir=d)
            port = httpd.server_address[1]
            server = threading.Thread(target=httpd.serve_forever, daemon=True)
            server.start()
            time.sleep(0.05)
            try:
                def hang(*a, **k):
                    time.sleep(0.4)
                    return {"answer": "ok"}
                with mock.patch.object(runner, "ask_model_agent", side_effect=hang):
                    def post():
                        req = urllib.request.Request(
                            f"http://127.0.0.1:{port}/ask",
                            data=b'{"question":"status"}',
                            headers={"X-Oracle-Token": httpd.oracle_token,
                                     "Origin": "http://127.0.0.1"},
                            method="POST")
                        urllib.request.urlopen(req, timeout=3).read()
                    worker = threading.Thread(target=post)
                    worker.start()
                    time.sleep(0.1)
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{port}/status",
                        headers={"X-Oracle-Token": httpd.oracle_token,
                                 "Host": "evil.example"})
                    try:
                        urllib.request.urlopen(req, timeout=2)
                    except Exception:
                        pass
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{port}/status",
                        headers={"X-Oracle-Token": httpd.oracle_token})
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                    worker.join(3)
                self.assertIn("elapsed_sec", body)
            finally:
                httpd.shutdown()
                httpd.server_close()
                server.join(timeout=5)
        finally:
            for _ in range(20):
                try:
                    tmp.cleanup()
                    break
                except OSError:
                    time.sleep(0.05)
        with mock.patch.object(runner, "_is_loopback_ip", return_value=False):
            with self.assertRaises(ValueError):
                runner.make_oracle_server({}, "127.0.0.1", 0)


class BoardOfferTailTest(unittest.TestCase):
    """Offer, approve, and count when saved rows are the wrong shape."""

    def test_board_filters_a_failed_save_and_the_counts(self):
        from runner.runner import Board
        with tempfile.TemporaryDirectory() as d:
            broken = Board(os.path.join(d, "missing", "board.json"))
            broken.tasks = {"a": {"task_id": "a", "state": "open"}}
            broken.save()
            board = Board(os.path.join(d, "board.json"))
            board.tasks = {
                "row": "nope",
                "shape": {
                    "task_id": "shape", "state": "open",
                    "compartments": "nope", "capabilities": "nope",
                    "priority": True, "submitted_at": "1",
                },
                "need": {
                    "task_id": "need", "state": "open",
                    "capabilities": ["root"], "compartments": [],
                    "requires": [], "priority": 1, "submitted_at": "2",
                },
                "reqs": {
                    "task_id": "reqs", "state": "open",
                    "capabilities": [], "compartments": [],
                    "requires": "nope", "priority": float("nan"),
                    "submitted_at": "3",
                },
                "dep": {
                    "task_id": "dep", "state": "open",
                    "capabilities": [], "compartments": [],
                    "requires": ["still-open"], "priority": 0,
                    "submitted_at": "4",
                },
                "still-open": {
                    "task_id": "still-open", "state": "open",
                    "capabilities": [], "compartments": [],
                    "requires": [], "priority": 9, "submitted_at": "0",
                },
                "limbo": {"task_id": "limbo", "state": "limbo"},
                "stale": {
                    "task_id": "stale", "state": "claimed",
                    "claimed_by": "other", "claimed_at": "not-a-date",
                },
                "review": {"task_id": "review", "state": "open"},
            }
            chosen = board.offer("w", ["sh"], cfg={
                "worker_allowlist": ["w"],
                "dag_mode": "enforce",
                "worker_compartments": {"w": ["blue"]},
            })
            self.assertEqual(chosen["task_id"], "still-open")
            self.assertFalse(board.approve("review")[0])
            self.assertEqual(board.reoffer_expired(), 0)
            self.assertGreaterEqual(board.counts()["open"], 1)


class AgentClockTest(unittest.TestCase):
    def test_agent_gives_up_when_the_clock_runs_out(self):
        from runner import runner
        cfg = {"endpoint": "http://127.0.0.1:9/v1", "model": "m",
               "timeout_sec": -1, "agent_wall_clock_sec": -5}
        ticks = {"n": 0}

        def mono():
            ticks["n"] += 1
            return 0 if ticks["n"] == 1 else 10_000

        def chat_for(later):
            def chat(cfg, messages, tools, opener, timeout):
                if tools is None:
                    return later
                return {"role": "assistant", "content": "", "tool_calls": [{
                    "id": "c1",
                    "function": {"name": "read_file",
                                 "arguments": {"path": "/no/such/hp-gap"}},
                }]}
            return chat

        with mock.patch.object(runner.time, "monotonic", side_effect=mono):
            ticks["n"] = 0
            with mock.patch.object(runner, "_inference_chat",
                                   side_effect=chat_for({"role": "error", "content": ""})):
                err = runner.ask_model_agent(cfg, "q", "", 20)
            ticks["n"] = 0
            with mock.patch.object(runner, "_inference_chat",
                                   side_effect=chat_for({"role": "assistant", "content": 7})):
                prose = runner.ask_model_agent(cfg, "q", "", 20)
        self.assertEqual(err["rejected"], "inference_error")
        self.assertIn("did not answer", err["detail"])
        self.assertIn("7", prose.get("answer") or "")


class InferenceOnceTest(unittest.TestCase):
    def test_one_model_call_rejects_a_bad_endpoint_and_a_dead_body(self):
        from urllib.error import HTTPError
        from runner.runner import _ask_model_once, _inference_chat, _inference_failure_text

        class Dead(HTTPError):
            def __init__(self):
                super().__init__("http://127.0.0.1:9/v1", 500, "no", None, None)

            def read(self):
                raise RuntimeError("body")

        def opener(req, timeout=60):
            raise Dead()

        self.assertEqual(
            _ask_model_once({"endpoint": 5, "model": "m"}, "q", "", 20)["rejected"],
            "inference_unconfigured")
        ans = _ask_model_once(
            {"endpoint": "http://127.0.0.1:9/v1", "model": "m", "timeout_sec": -1},
            "q", "", 20, opener=opener)
        self.assertEqual(ans["rejected"], "inference_error")
        self.assertIn("30s", _inference_failure_text(TimeoutError("timed out"), 30))

        class BadGet(dict):
            def get(self, *args, **kwargs):
                raise RuntimeError("get")

        msg = _inference_chat(
            {"endpoint": "http://127.0.0.1:9/v1", "model": "m"},
            [BadGet(role="user", content="hi")], None, opener, 5)
        self.assertEqual(msg["role"], "error")


class HashAndChatLogTest(unittest.TestCase):
    def test_hashes_paths_and_a_chat_line_with_bad_fields(self):
        import os as osmod
        from runner.runner import record_oracle_turn, sha384_of

        class BadPath(osmod.PathLike):
            def __fspath__(self):
                raise RuntimeError("no path")

        self.assertEqual(sha384_of(BadPath()), "")
        self.assertEqual(sha384_of(b"/no/such/hp-sha"), "")
        self.assertIsNone(record_oracle_turn(None, {}, "q", {}))
        with tempfile.TemporaryDirectory() as d:
            record_oracle_turn(d, {}, "q", {
                "answer": "hi", "model": 5, "tool_rounds": "nope", "detail": 9,
            })
            self.assertTrue(os.path.exists(os.path.join(d, "oracle-chat.jsonl")))


class MailDetectorTailTest(unittest.TestCase):
    def test_mail_rejects_a_non_object_and_a_detector_that_raises(self):
        from runner import runner
        from runner.runner import poll_once
        with tempfile.TemporaryDirectory() as d:
            cfg = base_config(d)
            payload = _payload("nd-1", kind="ping")
            smtp = FakeSMTP()
            with mock.patch("runner.runner.verify_body_keyed", return_value=([1], "")):
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=FakeIMAP([_email(payload)]), smtp=smtp)
            self.assertEqual(smtp.sent, [])

            smtp = FakeSMTP()
            with mock.patch.object(runner._detection, "evaluate_rules", return_value=[]), \
                 mock.patch.object(runner._detection, "update_baseline", return_value={}), \
                 mock.patch.object(runner._detection, "baseline_anomaly",
                                   return_value={"fresh": True}):
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=FakeIMAP([_email(_payload("anom-1", kind="ping"))]),
                          smtp=smtp)
            self.assertIn("detection_anomaly", _result_text(smtp.sent[-1]))

            smtp = FakeSMTP()
            with mock.patch.object(runner._detection, "evaluate_rules",
                                   side_effect=RuntimeError("det")):
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=FakeIMAP([_email(_payload("boom-1", kind="ping"))]),
                          smtp=smtp)
            self.assertTrue(smtp.sent)
            self.assertNotIn("detection_hits", _result_text(smtp.sent[-1]))


class ToolParseTailTest(unittest.TestCase):
    def test_content_tool_calls_and_secret_slices(self):
        from runner.runner import (
            _parse_content_tool_call, _wire_tool_arguments, secret_fragment_hit,
        )
        self.assertEqual(_parse_content_tool_call(None), [])
        self.assertEqual(_parse_content_tool_call("[1]"), [])
        self.assertEqual(
            _parse_content_tool_call('{"name": "read_file", "parameters": "nope"}'),
            [])
        parsed = _parse_content_tool_call(
            'note {"name": "read_file", "arguments": {"path": "a"}}')
        self.assertEqual(parsed[0][1], "read_file")
        self.assertEqual(_wire_tool_arguments("[1]"), "[1]")
        self.assertEqual(_wire_tool_arguments({"a": {1}}), "{}")
        self.assertFalse(secret_fragment_hit("abcdefghij", "abcdefghij", {1: 2}))
        self.assertFalse(secret_fragment_hit("abcdefghij", "abcdefghij", {"a": "("}))
        self.assertFalse(secret_fragment_hit(
            "aaaaaaaa", "xx aa yy", {"a": "a+"}, min_len=8))


class InspectAndSecretsTest(unittest.TestCase):
    def test_inspect_job_errors_and_weak_secret_files(self):
        import contextlib
        import io
        from runner.runner import build_secrets, run_inspect
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_dir": d}

            class Args:
                inspect = "job"
                job_id = ""
                config = None

            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(run_inspect(cfg, Args), 2)
            Args.job_id = "missing-job"
            with contextlib.redirect_stderr(err):
                self.assertEqual(run_inspect(cfg, Args), 1)
        with self.assertRaises(RuntimeError):
            build_secrets({"shared_secret": SECRET, "additional_secrets_files": [1]})
        with self.assertRaises(RuntimeError):
            build_secrets({"shared_secret": SECRET, "additional_secrets": {"": SECRET}})
        with self.assertRaises(RuntimeError):
            build_secrets({
                "shared_secret": SECRET, "additional_secrets_files": {1: "x"},
            })
        with self.assertRaises(RuntimeError):
            build_secrets({
                "shared_secret": SECRET, "additional_secrets_files": {"": "/tmp/x"},
            })


class QueryPolicyTailTest(unittest.TestCase):
    def test_queries_reject_a_policy_and_a_bad_ask_cap(self):
        from runner import runner
        with mock.patch.object(runner, "build_attestations", return_value=[]):
            answers, spent = runner.answer_queries(
                [{"op": "attest"}], {"stdout": "hi"}, {}, 4)
        self.assertEqual(spent, 1)
        self.assertEqual(answers[0]["rejected"], "policy")
        with mock.patch.object(runner, "ask_model", return_value={"op": "ask", "answer": "a"}):
            answers, spent = runner.answer_queries(
                [{"op": "ask", "max_chars": "nope", "question": "q"}],
                {"stdout": "hi"}, {}, 4,
                cfg={"inference": {
                    "endpoint": "http://127.0.0.1:9/v1", "model": "m",
                    "max_answer_chars": 20}})
        self.assertEqual(answers[0]["op"], "ask")


class WatchAndPostureTest(unittest.TestCase):
    def test_watches_logs_and_a_frozen_doc(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as d:
            ws = os.path.join(d, "ws")
            os.makedirs(ws)
            real_stat = os.stat

            def walk_then_fail(path):
                yield path, [], ["one"]
                raise OSError("mid")

            def stat_one(path, *args, **kwargs):
                if os.path.basename(str(path)) == "one":
                    raise RuntimeError("stat")
                return real_stat(path, *args, **kwargs)

            with mock.patch.object(runner.os, "walk", side_effect=walk_then_fail), \
                 mock.patch.object(runner.os, "stat", side_effect=stat_one):
                self.assertEqual(runner.snapshot_outside(ws), {})

            with mock.patch.object(runner.os, "walk", side_effect=OSError("no")):
                self.assertEqual(runner._work_files(d), {})

            def walk_gone(path):
                yield path, [], ["gone"]

            def stat_gone(path, *args, **kwargs):
                if os.path.basename(str(path)) == "gone":
                    raise OSError("gone")
                return real_stat(path, *args, **kwargs)

            with mock.patch.object(runner.os, "walk", side_effect=walk_gone), \
                 mock.patch.object(runner.os, "stat", side_effect=stat_gone):
                self.assertEqual(runner._work_files(d), {})

            path = os.path.join(d, "runner.log")
            open(path, "w", encoding="utf-8").close()
            self.assertEqual(runner._runner_log_tail(base_dir=d), "")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("line\n" * 2000)
            self.assertLessEqual(len(runner._runner_log_tail(base_dir=d, max_chars=40)), 40)
            real_open = open

            def fail_log(path, *args, **kwargs):
                if str(path).endswith("runner.log"):
                    raise OSError("busy")
                return real_open(path, *args, **kwargs)

            with mock.patch("builtins.open", side_effect=fail_log):
                self.assertEqual(runner._runner_log_tail(base_dir=d), "")

            runner._file_watch_alert("", "canary", "high", "title", "T1")
            runner._file_watch_alert(d, "canary", "high", "  ", "T1")
            with mock.patch.object(runner._senses, "store_alert", side_effect=RuntimeError("no")):
                runner._file_watch_alert(d, "canary", "high", "title", "T1")

            name = runner._CANARY_NAMES[0]
            snap = os.path.join(d, "canary-watch.json")
            with open(snap, "w", encoding="utf-8") as fh:
                json.dump({"files": {name: "nope"}, "alerted": {}}, fh)
            with mock.patch.object(runner, "_canary_state", return_value="?"):
                runner._canary_watch(d)
            with open(snap, "w", encoding="utf-8") as fh:
                json.dump({
                    "files": {n: {"exists": False, "hash": "x"}
                              for n in runner._CANARY_NAMES},
                    "alerted": {},
                }, fh)
            with mock.patch.object(runner, "_canary_state", return_value=None):
                runner._canary_watch(d)
            with open(snap, "w", encoding="utf-8") as fh:
                json.dump({"files": {}, "alerted": {}}, fh)

            def fail_snap(path, *args, **kwargs):
                if str(path).endswith("canary-watch.json") and args and "w" in str(args[0]):
                    raise OSError("full")
                return real_open(path, *args, **kwargs)

            with mock.patch("builtins.open", side_effect=fail_snap), \
                 mock.patch.object(runner, "_canary_state", return_value="abc"):
                runner._canary_watch(d)

            docs = os.path.join(d, "pigeon-docs")
            os.makedirs(docs)
            with open(os.path.join(docs, "PROTOCOL.md"), "w", encoding="utf-8") as fh:
                fh.write("spec")
            with mock.patch.object(runner.sys, "frozen", True, create=True), \
                 mock.patch.object(runner.sys, "_MEIPASS", d, create=True):
                self.assertTrue(runner._bundled_doc_path("PROTOCOL.md").endswith("PROTOCOL.md"))

        class Proc:
            returncode = 0
            stdout = "denied for user\n" * 40

        with mock.patch.object(runner, "_tail_marked", return_value=None), \
             mock.patch.object(runner.subprocess, "run", return_value=Proc()), \
             mock.patch.object(runner.sys, "platform", "linux"):
            # The platform patch matters: _host_log_tail returns
            # None on win32 by contract (the Event Log covers
            # Windows; None means unreadable, never clean). The
            # journal fallback under test here is the Linux path.
            self.assertIsInstance(runner._host_log_tail(max_chars="nope"), str)
            short = runner._host_log_tail(max_chars=5)
        self.assertTrue(short)
        self.assertLessEqual(len(short), 5)

        def which(name):
            if name == "ufw":
                return "/usr/sbin/ufw"
            if name == "iptables":
                return "/sbin/iptables"
            return None

        with mock.patch.object(runner.sys, "platform", "darwin"), \
             mock.patch.object(runner, "_run_text", return_value=""), \
             mock.patch.object(runner, "_parse_socketfilterfw", return_value="fw on"):
            self.assertEqual(runner._firewall_posture(), "fw on")
        with mock.patch.object(runner.sys, "platform", "linux"), \
             mock.patch.object(runner.shutil, "which", side_effect=which), \
             mock.patch.object(runner, "_run_text", return_value=""), \
             mock.patch.object(runner, "_parse_ufw", return_value="ufw on"):
            self.assertEqual(runner._firewall_posture(), "ufw on")
        with mock.patch.object(runner.sys, "platform", "linux"), \
             mock.patch.object(runner.shutil, "which",
                               side_effect=lambda name: which(name) if name == "iptables" else None), \
             mock.patch.object(runner, "_run_text", return_value=""), \
             mock.patch.object(runner, "_parse_iptables_policy", return_value="drop"):
            self.assertEqual(runner._firewall_posture(), "drop")


class YaraDeadlineTest(unittest.TestCase):
    def test_yara_stops_at_the_deadline_and_a_rules_file_that_sticks(self):
        from runner import runner
        ticks = {"n": 0}

        def mono():
            ticks["n"] += 1
            return 0 if ticks["n"] <= 2 else 1000

        class Proc:
            stdout = None

        def which(name):
            return "/usr/bin/yara" if name == "yara" else None

        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "note.txt")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("x")
            with mock.patch.object(runner.shutil, "which", side_effect=which), \
                 mock.patch.object(runner.subprocess, "run", return_value=Proc()), \
                 mock.patch.object(runner.time, "monotonic", side_effect=mono), \
                 mock.patch.object(runner.os, "remove", side_effect=OSError("busy")):
                self.assertEqual(runner._yara_hits(d, [target, target], {}), [])


class LogClosedStdoutTest(unittest.TestCase):
    def test_log_survives_a_closed_stdout_and_a_bad_message(self):
        from runner import runner
        saved = (runner._LOG_MINUTE, runner._LOG_COUNT, runner._LOG_DROPPED,
                 runner._VERBOSE, runner._LOG_FILE)
        try:
            runner._VERBOSE = False
            runner._LOG_MINUTE = 0
            runner._LOG_DROPPED = 3
            runner._LOG_COUNT = 0
            runner._LOG_FILE = None

            class Bad:
                def __str__(self):
                    raise RuntimeError("no")

            with mock.patch("builtins.print", side_effect=OSError("closed")):
                runner.log(Bad(), "ERROR")
        finally:
            (runner._LOG_MINUTE, runner._LOG_COUNT, runner._LOG_DROPPED,
             runner._VERBOSE, runner._LOG_FILE) = saved


class ConfinementTailTest(unittest.TestCase):
    def test_confinement_without_a_security_module_and_with_a_built_sandbox(self):
        from runner import runner
        with tempfile.TemporaryDirectory() as d:
            script = os.path.join(d, "job.sh")
            saved = runner._security
            try:
                runner._security = None
                _argv, host_env, boxed = runner._confinement_argv(
                    {}, d, "j", ["sh"], script, d, [], {})
                self.assertTrue(host_env)
                self.assertFalse(boxed)
            finally:
                runner._security = saved
            with mock.patch.object(runner._security, "sec_mode", return_value="enforce"), \
                 mock.patch.object(runner._security, "bump_evaluated"), \
                 mock.patch.object(runner._security, "write_audit_entry",
                                   side_effect=RuntimeError("audit")), \
                 mock.patch.object(runner._sandbox, "sandbox_available", return_value=True), \
                 mock.patch.object(runner._sandbox, "build_bwrap_command",
                                   return_value=["bwrap", "sh"]):
                argv, host_env, boxed = runner._confinement_argv(
                    {}, d, "j", ["sh"], script, d, [], {})
            self.assertEqual(argv[0], "bwrap")
            self.assertFalse(host_env)
            self.assertTrue(boxed)


if __name__ == "__main__":
    unittest.main()

