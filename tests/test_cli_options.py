"""Pins for the blown-up CLI surface.

Four families, one per deliverable:

- one-process overrides: apply_cli_overrides driven directly,
  and main() driven through the stubbed rig the suite already
  uses for it, proving the flags land in cfg and are pinned
  against hot reload;
- verbose levels: the resolver's matrix, the config key, the
  flag beating config, and the decision lines themselves, driven
  through a real poll cycle, the wake gate, the judge, and the
  board;
- the startup invocation line: version plus the exact argv,
  shell-quoted, as the first line of the startup block;
- the --help documents of all three entry points: group titles
  in order, every flag present, the epilog examples verbatim.
"""
import contextlib
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

from runner import runner
from runner._version import __version__
from runner.runner import (
    Board, apply_cli_overrides, handle_mail, poll_once, sign_payload,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)


def _override_args(**over):
    """A Namespace shaped like main()'s, override flags unset."""
    ns = Namespace()
    for dest, _key in runner._CLI_OVERRIDES:
        setattr(ns, dest, None)
    for dest, val in over.items():
        setattr(ns, dest, val)
    return ns


class ApplyCliOverridesTest(unittest.TestCase):
    def test_polling_family(self):
        cfg = {}
        applied = apply_cli_overrides(cfg, _override_args(
            poll_interval=45, timeout=99, max_output_bytes=1234))
        self.assertEqual(cfg["poll_interval_sec"], 45)
        self.assertEqual(cfg["default_timeout_sec"], 99)
        self.assertEqual(cfg["max_output_bytes"], 1234)
        self.assertEqual(set(applied), {"poll_interval_sec",
                                        "default_timeout_sec",
                                        "max_output_bytes"})

    def test_freshness_and_retention_family(self):
        cfg = {}
        apply_cli_overrides(cfg, _override_args(
            max_job_age=60, retention_days=0, task_timeout=3600))
        self.assertEqual(cfg["max_job_age_sec"], 60)
        # 0 is a real value (keep retained outputs forever), not
        # an unset flag: it must land in cfg.
        self.assertEqual(cfg["output_retention_days"], 0)
        self.assertEqual(cfg["task_timeout"], 3600)

    def test_query_budget_family(self):
        cfg = {}
        apply_cli_overrides(cfg, _override_args(
            max_query_budget=3, max_queries_per_hour=10))
        self.assertEqual(cfg["max_query_budget"], 3)
        self.assertEqual(cfg["max_queries_per_hour"], 10)

    def test_modes_family(self):
        cfg = {}
        apply_cli_overrides(cfg, _override_args(
            judge="enforce", dag_mode="advisory",
            oracle_mode="deterministic", max_result_view="redacted"))
        self.assertEqual(cfg["judge"], "enforce")
        self.assertEqual(cfg["dag_mode"], "advisory")
        self.assertEqual(cfg["oracle_mode"], "deterministic")
        self.assertEqual(cfg["max_result_view"], "redacted")

    def test_bool_pairs_are_tri_state(self):
        # Given (True or False) applies; absent (None) does not.
        cfg = {"require_review": False, "local_signals": True}
        apply_cli_overrides(cfg, _override_args(
            require_review=True, local_signals=False,
            oracle_log=True))
        self.assertIs(cfg["require_review"], True)
        self.assertIs(cfg["local_signals"], False)
        self.assertIs(cfg["oracle_log"], True)
        cfg = {"require_review": True}
        applied = apply_cli_overrides(cfg, _override_args())
        self.assertIs(cfg["require_review"], True)
        self.assertNotIn("require_review", applied)

    def test_local_signal_numbers(self):
        cfg = {}
        apply_cli_overrides(cfg, _override_args(
            local_signal_port=0, wake_cooldown=30))
        # Port 0 turns the listener off; it is a value, not unset.
        self.assertEqual(cfg["local_signal_port"], 0)
        self.assertEqual(cfg["local_wake_cooldown_sec"], 30)

    def test_log_bounds_family(self):
        cfg = {}
        apply_cli_overrides(cfg, _override_args(
            log_max_bytes=1024, log_backups=2,
            oracle_log_max_bytes=2048, oracle_log_backups=3))
        self.assertEqual(cfg["log_max_bytes"], 1024)
        self.assertEqual(cfg["log_backups"], 2)
        self.assertEqual(cfg["oracle_log_max_bytes"], 2048)
        self.assertEqual(cfg["oracle_log_backups"], 3)

    def test_absent_flags_change_nothing(self):
        cfg = {"judge": "off", "poll_interval_sec": 20}
        applied = apply_cli_overrides(cfg, _override_args())
        self.assertEqual(applied, [])
        self.assertEqual(cfg, {"judge": "off", "poll_interval_sec": 20})

    def test_negative_counts_are_rejected(self):
        for dest, _key in runner._CLI_OVERRIDES:
            if dest not in runner._CLI_OVERRIDE_COUNTS:
                continue
            with self.subTest(dest=dest):
                with self.assertRaises(ValueError):
                    apply_cli_overrides({}, _override_args(**{dest: -1}))

    def test_port_bounds(self):
        cfg = {}
        apply_cli_overrides(cfg, _override_args(local_signal_port=65535))
        self.assertEqual(cfg["local_signal_port"], 65535)
        with self.assertRaises(ValueError):
            apply_cli_overrides({}, _override_args(
                local_signal_port=65536))


def _main_rig(argv, cfg_extra=None):
    """Drive runner.main() the way test_coverage_resolve does:
    mailbox, model, and poll stubbed; reload spied on so the
    pinned set is observable."""
    from runner import setup
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
        setup, "is_tty", return_value=False))
    stack.enter_context(mock.patch.object(
        setup, "needs_setup", return_value=None))
    stack.enter_context(mock.patch.object(
        setup, "run_setup_wizard", return_value={}))
    reloads = []

    def _reload(cfg_, path, state, pinned=None):
        reloads.append(set(pinned or ()))
        return []

    stack.enter_context(mock.patch.object(
        runner, "reload_hot_config", side_effect=_reload))
    stack.enter_context(mock.patch.object(
        runner, "_start_local_signals"))
    directory = stack.enter_context(tempfile.TemporaryDirectory())
    body = {"shared_secret": SECRET, "mailbox_user": "a@b.c",
            "mailbox_password": "pw", "base_dir": directory}
    if cfg_extra:
        body.update(cfg_extra)
    path = os.path.join(directory, "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    stack.enter_context(mock.patch.object(
        sys, "argv", ["runner", "--config", path, *argv]))
    try:
        with redirect_stdout(io.StringIO()):
            code = runner.main()
    finally:
        stack.close()
    return code, poll, reloads


class MainOverridesTest(unittest.TestCase):
    def test_new_flags_reach_the_poll_cfg(self):
        code, poll, _reloads = _main_rig([
            "--once", "--dry-run",
            "--judge", "enforce", "--dag-mode", "advisory",
            "--oracle-mode", "deterministic",
            "--max-job-age", "60", "--retention-days", "3",
            "--task-timeout", "7200", "--max-query-budget", "5",
            "--local-signal-port", "0", "--no-local-signals",
            "--wake-cooldown", "30", "--log-backups", "2",
            "--require-review", "--max-result-view", "summary",
        ])
        self.assertEqual(code, 0)
        cfg = poll.call_args[0][0]
        self.assertEqual(cfg["judge"], "enforce")
        self.assertEqual(cfg["dag_mode"], "advisory")
        self.assertEqual(cfg["oracle_mode"], "deterministic")
        self.assertEqual(cfg["max_job_age_sec"], 60)
        self.assertEqual(cfg["output_retention_days"], 3)
        self.assertEqual(cfg["task_timeout"], 7200)
        self.assertEqual(cfg["max_query_budget"], 5)
        self.assertEqual(cfg["local_signal_port"], 0)
        self.assertIs(cfg["local_signals"], False)
        self.assertEqual(cfg["local_wake_cooldown_sec"], 30)
        self.assertEqual(cfg["log_backups"], 2)
        self.assertIs(cfg["require_review"], True)
        self.assertEqual(cfg["max_result_view"], "summary")

    def test_new_flags_are_pinned_against_reload(self):
        code, _poll, reloads = _main_rig([
            "--once", "--dry-run", "--judge", "enforce",
            "--dag-mode", "advisory", "--local-signal-port", "0",
            "--require-review",
        ])
        self.assertEqual(code, 0)
        self.assertTrue(reloads)
        self.assertTrue({
            "judge", "dag_mode", "local_signal_port",
            "require_review",
        } <= reloads[0])

    def test_a_bad_override_value_exits_2_before_polling(self):
        code, poll, _reloads = _main_rig(
            ["--once", "--log-backups", "-1"])
        self.assertEqual(code, 2)
        self.assertFalse(poll.called)
        code, poll, _reloads = _main_rig(
            ["--once", "--local-signal-port", "70000"])
        self.assertEqual(code, 2)
        self.assertFalse(poll.called)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _IMAP:
    def __init__(self, raws=()):
        self.raws = list(raws)

    def search(self, *a):
        ids = [str(i + 1).encode() for i in range(len(self.raws))]
        return "OK", [b" ".join(ids)] if ids else [b""]

    def fetch(self, num, what):
        idx = int(num) - 1
        if 0 <= idx < len(self.raws):
            return "OK", [(None, self.raws[idx])]
        return "NO", None

    def store(self, *a):
        return "OK", None

    def expunge(self):
        return "OK", None

    def logout(self):
        return "OK", None


class _SMTP:
    def send_message(self, *a, **k):
        return {}

    def quit(self):
        pass


class _Opts:
    workers = 1
    once = True
    dry_run = False
    verbose = False
    no_send = True
    inspect = False
    oracle = False
    pdb = False


@contextlib.contextmanager
def _captured_log():
    """Capture log() output with a fresh per-minute budget and
    no log file, restoring both afterwards."""
    old_file = runner._LOG_FILE
    old_minute, old_count = runner._LOG_MINUTE, runner._LOG_COUNT
    runner._LOG_FILE = None
    runner._LOG_MINUTE = 0.0
    runner._LOG_COUNT = 0
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            yield buf
    finally:
        runner._LOG_FILE = old_file
        runner._LOG_MINUTE, runner._LOG_COUNT = old_minute, old_count


class _VerbosityGuard(unittest.TestCase):
    def setUp(self):
        self._saved = (runner._VERBOSE, runner._VERBOSE_LEVEL)

    def tearDown(self):
        runner._VERBOSE, runner._VERBOSE_LEVEL = self._saved


class ResolveVerbosityTest(unittest.TestCase):
    def test_the_matrix(self):
        r = runner._resolve_verbosity
        # No flag, no config key: the base level, today's log.
        self.assertEqual(r({}, None), 1)
        self.assertEqual(r(None, None), 1)
        # Config speaks when the flag is silent.
        self.assertEqual(r({"verbose": True}, None), 2)
        self.assertEqual(r({"verbose": "true"}, None), 2)
        self.assertEqual(r({"verbose": False}, None), 0)
        # The flag beats config, both ways.
        self.assertEqual(r({"verbose": True}, False), 0)
        self.assertEqual(r({"verbose": False}, 1), 2)
        self.assertEqual(r({}, 1), 2)
        self.assertEqual(r({}, 2), 3)
        self.assertEqual(r({}, False), 0)


class VlogGatingTest(_VerbosityGuard):
    def test_silent_at_base_level_and_printed_at_verbose(self):
        runner._set_verbosity(1)
        with _captured_log() as buf:
            runner.vlog("a decision")
        self.assertNotIn("verbose:", buf.getvalue())
        runner._set_verbosity(2)
        with _captured_log() as buf:
            runner.vlog("a decision")
        self.assertIn("verbose: a decision", buf.getvalue())

    def test_the_noisier_lines_need_the_second_v(self):
        runner._set_verbosity(2)
        with _captured_log() as buf:
            runner.vlog("a whisper", level=3)
        self.assertNotIn("whisper", buf.getvalue())
        runner._set_verbosity(3)
        with _captured_log() as buf:
            runner.vlog("a whisper", level=3)
        self.assertIn("verbose: a whisper", buf.getvalue())


class WakeGateVerboseTest(_VerbosityGuard):
    def setUp(self):
        super().setUp()
        self._saved_last = dict(runner._LOCAL_WAKE_LAST)
        self._saved_inflight = runner._LOCAL_WAKE_INFLIGHT
        runner._LOCAL_WAKE_LAST.clear()
        runner._LOCAL_WAKE_INFLIGHT = False

    def tearDown(self):
        runner._LOCAL_WAKE_LAST.clear()
        runner._LOCAL_WAKE_LAST.update(self._saved_last)
        runner._LOCAL_WAKE_INFLIGHT = self._saved_inflight
        super().tearDown()

    def test_below_threshold_names_score_and_threshold(self):
        runner._set_verbosity(2)
        rec = {"sensor": "smoke", "signal": "alarm",
               "severity": "low"}
        with _captured_log() as buf:
            ok = runner._wake_gate_decide({}, rec, now=1000.0)
        self.assertFalse(ok)
        out = buf.getvalue()
        self.assertIn("verbose: wake gate: smoke/alarm", out)
        self.assertIn("score=1 < high 3", out)
        self.assertIn("no wake", out)

    def test_fire_cooldown_and_inflight_each_narrate(self):
        runner._set_verbosity(2)
        rec = {"sensor": "smoke", "signal": "alarm",
               "severity": "high"}
        with _captured_log() as buf:
            ok = runner._wake_gate_decide({}, rec, now=1000.0)
        self.assertTrue(ok)
        self.assertIn("score=3 >= high 3", buf.getvalue())
        self.assertIn("waking the Oracle", buf.getvalue())
        # Still in flight: the next alert is narrated as such.
        with _captured_log() as buf:
            ok = runner._wake_gate_decide({}, rec, now=1010.0)
        self.assertFalse(ok)
        self.assertIn("already in flight", buf.getvalue())
        # Flight released, cooldown still running: narrated too.
        runner._wake_gate_release()
        with _captured_log() as buf:
            ok = runner._wake_gate_decide({}, rec, now=1010.0)
        self.assertFalse(ok)
        self.assertIn("cooldown is 900s", buf.getvalue())

    def test_quiet_at_base_level(self):
        runner._set_verbosity(1)
        rec = {"sensor": "smoke", "signal": "alarm",
               "severity": "critical"}
        with _captured_log() as buf:
            runner._wake_gate_decide({}, rec, now=1000.0)
        self.assertNotIn("verbose:", buf.getvalue())


def _poll_setup(d):
    with open(os.path.join(d, "resources.json"), "w") as f:
        f.write("[]")
    with open(os.path.join(d, "dri-state.json"), "w") as f:
        f.write("null")
    os.makedirs(os.path.join(d, "retained"))
    with open(os.path.join(d, "retained", "old.json"), "w") as f:
        f.write("not json")
    return {"mailbox_user": "t@example.com", "shared_secret": SECRET,
            "resources": {"enabled": True}, "dri": {"enabled": True}}


class PollVerboseTest(_VerbosityGuard):
    def _run_poll(self, raws, cfg=None):
        with tempfile.TemporaryDirectory() as d:
            cfg = cfg if cfg is not None else _poll_setup(d)
            with _captured_log() as buf:
                poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                          imap=_IMAP(raws), smtp=_SMTP(), opts=_Opts())
            return buf.getvalue()

    def test_decision_lines_appear_at_verbose(self):
        runner._set_verbosity(2)
        good = sign_payload({
            "v": 1, "type": "job", "job_id": "good1",
            "issued_at": _now(), "kind": "ping"}, SECRET)
        out = self._run_poll([
            _mail("[HOMING-PIGEON] job good1", good),
            _mail("[HOMING-PIGEON] job garbage", "not signed json"),
            _mail("a newsletter", "hello"),
        ])
        self.assertIn("verbose: ingest: job good1: accepted", out)
        self.assertIn("verbose: ingest: seq 2: rejected: "
                      "bad signature", out)
        self.assertIn("verbose: ingest: seq 3: skipped; "
                      "not a job message", out)
        self.assertIn("verbose: poll: 3 message(s) handled by "
                      "1 worker(s)", out)

    def test_no_decision_lines_at_base_level(self):
        runner._set_verbosity(1)
        good = sign_payload({
            "v": 1, "type": "job", "job_id": "good1",
            "issued_at": _now(), "kind": "ping"}, SECRET)
        out = self._run_poll([
            _mail("[HOMING-PIGEON] job good1", good),
            _mail("[HOMING-PIGEON] job garbage", "not signed json"),
        ])
        self.assertNotIn("verbose:", out)
        # The pre-existing lines are untouched.
        self.assertIn("executing job good1", out)
        self.assertIn("rejecting seq 2: bad signature", out)

    def test_empty_poll_narrates_only_at_verbose(self):
        runner._set_verbosity(2)
        out = self._run_poll([])
        self.assertIn("verbose: poll: no new messages", out)
        runner._set_verbosity(1)
        out = self._run_poll([])
        self.assertNotIn("verbose:", out)


class IngestVerboseTest(_VerbosityGuard):
    def test_already_seen_is_a_verbose_line(self):
        runner._set_verbosity(2)
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": SECRET}
        body = sign_payload({
            "v": 1, "type": "job", "job_id": "dup1",
            "issued_at": _now(), "kind": "ping"}, SECRET)
        seen = {runner._seen_key(cfg, "dup1"): 1}
        with _captured_log() as buf:
            handle_mail(cfg, _IMAP(), _SMTP(), 7,
                        _mail("[HOMING-PIGEON] job dup1", body),
                        tempfile.gettempdir(), seen,
                        runner.build_secrets(cfg), _Opts())
        self.assertIn("verbose: ingest: seq 7 job dup1: skipped; "
                      "already seen", buf.getvalue())


class JudgeVerboseTest(_VerbosityGuard):
    def _handle(self, cfg, job):
        raw = _mail(f"[HOMING-PIGEON] job {job['job_id']}",
                    sign_payload(job, SECRET))
        with tempfile.TemporaryDirectory() as d:
            with _captured_log() as buf:
                handle_mail(cfg, _IMAP(), _SMTP(), 1, raw, d, {},
                            runner.build_secrets(cfg), _Opts())
            return buf.getvalue()

    def test_enforce_verdict_is_narrated(self):
        runner._set_verbosity(2)
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": SECRET, "judge": "enforce"}
        out = self._handle(cfg, {
            "v": 1, "type": "job", "job_id": "bad1",
            "issued_at": _now(), "kind": "exec",
            "script": "rm -rf /"})
        self.assertIn("verbose: judge: job bad1: mode=enforce "
                      "verdict=fail", out)

    def test_advisory_pass_is_narrated_and_quiet_at_base(self):
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": SECRET, "judge": "advisory"}
        job = {"v": 1, "type": "job", "job_id": "ok1",
               "issued_at": _now(), "kind": "ping"}
        runner._set_verbosity(2)
        out = self._handle(cfg, job)
        self.assertIn("verbose: judge: job ok1: mode=advisory "
                      "verdict=pass", out)
        runner._set_verbosity(1)
        out = self._handle(cfg, job)
        self.assertNotIn("verbose: judge:", out)


class BoardVerboseTest(_VerbosityGuard):
    def _board(self, d):
        b = Board(os.path.join(d, "board.json"))
        b.submit({"task_id": "a"})
        b.submit({"task_id": "b", "requires": ["a"]})
        return b

    def test_enforce_withheld_is_narrated(self):
        runner._set_verbosity(2)
        with tempfile.TemporaryDirectory() as d:
            b = self._board(d)
            with _captured_log() as buf:
                got = b.offer("w1", [], cfg={"dag_mode": "enforce"})
            # Only task a can go out; b is withheld, and says so.
            self.assertEqual(got["task_id"], "a")
            self.assertIn("verbose: board: task b withheld "
                          "(dag_mode=enforce): incomplete "
                          "requires: a", buf.getvalue())

    def test_offer_and_empty_board_are_narrated(self):
        runner._set_verbosity(2)
        with tempfile.TemporaryDirectory() as d:
            b = Board(os.path.join(d, "board.json"))
            b.submit({"task_id": "a"})
            # Top-ranked, so advisory hands it out first, with
            # its incomplete dependency still pending.
            b.submit({"task_id": "b", "requires": ["a"],
                      "priority": 5})
            with _captured_log() as buf:
                got = b.offer("w1", [], cfg={"dag_mode": "advisory"})
            self.assertEqual(got["task_id"], "b")
            self.assertIn("dag_warning", got)
            self.assertIn("verbose: board: offered b to w1 "
                          "(dag_mode=advisory", buf.getvalue())
            empty = Board(os.path.join(d, "empty.json"))
            with _captured_log() as buf:
                self.assertIsNone(
                    empty.offer("w1", [], cfg={"dag_mode": "off"}))
            self.assertIn("verbose: board: nothing to offer w1",
                          buf.getvalue())

    def test_quiet_at_base_level(self):
        runner._set_verbosity(1)
        with tempfile.TemporaryDirectory() as d:
            b = self._board(d)
            with _captured_log() as buf:
                b.offer("w1", [], cfg={"dag_mode": "enforce"})
            self.assertNotIn("verbose:", buf.getvalue())


class ConfigVerboseMainTest(_VerbosityGuard):
    def test_config_verbose_is_honored(self):
        code, _poll, _reloads = _main_rig(
            ["--once", "--dry-run"], cfg_extra={"verbose": True})
        self.assertEqual(code, 0)
        self.assertEqual(runner._VERBOSE_LEVEL, 2)
        self.assertTrue(runner._VERBOSE)

    def test_config_verbose_false_quiets(self):
        code, _poll, _reloads = _main_rig(
            ["--once", "--dry-run"], cfg_extra={"verbose": False})
        self.assertEqual(code, 0)
        self.assertEqual(runner._VERBOSE_LEVEL, 0)
        self.assertFalse(runner._VERBOSE)

    def test_flag_beats_config_both_ways(self):
        code, _poll, _reloads = _main_rig(
            ["--once", "--dry-run", "--quiet"],
            cfg_extra={"verbose": True})
        self.assertEqual(code, 0)
        self.assertEqual(runner._VERBOSE_LEVEL, 0)
        code, _poll, _reloads = _main_rig(
            ["--once", "--dry-run", "-v"],
            cfg_extra={"verbose": False})
        self.assertEqual(code, 0)
        self.assertEqual(runner._VERBOSE_LEVEL, 2)

    def test_no_flag_no_key_is_the_base_level(self):
        code, _poll, _reloads = _main_rig(["--once", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertEqual(runner._VERBOSE_LEVEL, 1)
        self.assertTrue(runner._VERBOSE)


class InvocationLineTest(_VerbosityGuard):
    """The startup block opens with the exact invocation:
    version plus argv, shell-quoted so the line can be pasted
    back into a shell to reproduce the run."""

    def _startup_first_line(self, argv):
        args = Namespace(dry_run=False, no_send=False, once=False,
                         verbose=False)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(sys, "argv", argv):
                with _captured_log() as buf:
                    runner.log_startup({"mailbox_user": "a@b.c"},
                                       args, d)
        lines = [ln for ln in buf.getvalue().splitlines()
                 if ln.strip()]
        return lines[0] if lines else ""

    def test_first_line_carries_version_and_exact_flags(self):
        first = self._startup_first_line(
            ["runner.py", "--config", "cfg.json", "--verbose",
             "--dag-mode", "advisory"])
        self.assertIn(f"homing-pigeon {__version__} invocation:",
                      first)
        self.assertIn("--verbose", first)
        self.assertIn("--dag-mode advisory", first)

    def test_no_optional_flags_still_prints_cleanly(self):
        first = self._startup_first_line(["runner.py"])
        self.assertTrue(
            first.endswith("invocation: runner.py"), first)

    def test_values_with_spaces_are_shell_quoted(self):
        if os.name == "nt":
            self.skipTest("POSIX quoting is the live shell here")
        first = self._startup_first_line(
            ["runner.py", "--config", "my cfg.json"])
        self.assertIn("'my cfg.json'", first)
        tail = first.split("invocation: ", 1)[1]
        self.assertEqual(shlex.split(tail),
                         ["runner.py", "--config", "my cfg.json"])


def _help_output(*argv):
    env = dict(os.environ, COLUMNS="80")
    return subprocess.run([sys.executable, *argv],
                          capture_output=True, text=True, timeout=60,
                          cwd=REPO, env=env)


class RunnerHelpDocumentTest(unittest.TestCase):
    """--help is a designed document: chapters in order, every
    flag present, the worked examples verbatim."""

    GROUPS = ["running", "one-process overrides", "modes",
              "local signals", "logging", "the Oracle",
              "reports and harnesses"]
    FLAGS = [
        "--help", "--version",
        "--config", "--once", "--dry-run", "--no-send", "--setup",
        "--pdb",
        "--workers", "--poll-interval", "--timeout",
        "--max-output-bytes", "--max-job-age", "--retention-days",
        "--task-timeout", "--max-query-budget",
        "--max-queries-per-hour", "--max-result-view",
        "--judge", "--dag-mode", "--oracle-mode", "--require-review",
        "--no-require-review", "--faster",
        "--local-signals", "--no-local-signals",
        "--local-signal-port", "--wake-cooldown",
        "--verbose", "--quiet", "--log-max-bytes", "--log-backups",
        "--oracle-log", "--no-oracle-log", "--oracle-log-max-bytes",
        "--oracle-log-backups",
        "--oracle", "--oracle-cli", "--oracle-port",
        "--inspect", "--job-id", "--audit-report", "--since",
        "--key", "--feature", "--posture", "--diagnose",
        "--diagnose-timeout", "--local-test", "--browser",
    ]
    EXAMPLES = [
        "runner.py --config config.json",
        "runner.py --config config.json --once --dry-run -v",
        "runner.py --oracle-mode deterministic --inspect board",
        "runner.py --oracle",
        "runner.py --oracle-cli",
    ]

    @classmethod
    def setUpClass(cls):
        cls.proc = _help_output(
            os.path.join("runner", "runner.py"), "--help")
        cls.out = cls.proc.stdout

    def test_help_exits_0(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_every_flag_is_listed(self):
        for flag in self.FLAGS:
            with self.subTest(flag=flag):
                self.assertIn(flag, self.out)
        self.assertIn("-v, --verbose", self.out)

    def test_group_titles_appear_in_order(self):
        positions = []
        for title in self.GROUPS:
            at = self.out.find(f"\n{title}:\n")
            self.assertGreaterEqual(at, 0, title)
            positions.append(at)
        self.assertEqual(positions, sorted(positions))

    def test_description_and_examples_are_verbatim(self):
        self.assertIn("Your cloud SI is smart, but it can't touch "
                      "your computer.", self.out)
        self.assertIn("The signature is the only gate.", self.out)
        for example in self.EXAMPLES:
            with self.subTest(example=example):
                self.assertIn(f"  {example}\n", self.out)

    def test_defaults_shown_match_the_example_config(self):
        # Whitespace-normalized: at 80 columns argparse may wrap
        # "(default:" and its value onto separate lines.
        flat = " ".join(self.out.split())
        for text in ("(default: 20)", "(default: 300)",
                     "(default: 100000)", "(default: 3600)",
                     "(default: 86400)", "(default: 39271;",
                     "(default: 33554432)", "(default: 11436"):
            with self.subTest(text=text):
                self.assertIn(text, flat)


class InstallHelpDocumentTest(unittest.TestCase):
    """install.py --help: same hand as the runner's page."""

    GROUPS = ["where it installs", "instead of installing",
              "what gets installed", "inference",
              "baked into the service"]
    FLAGS = [
        "--help", "--version",
        "--dir", "--home", "--config", "--system", "--run-as",
        "--check", "--console", "--logs", "--follow", "--lines",
        "--oracle", "--migrate", "--uninstall", "--wipe",
        "--backup-dir", "--no-backup",
        "--shared-secret", "--instructions", "--instructions-add",
        "--profile", "--no-profile", "--additional-secret",
        "--no-inference", "--inference-only", "--inference-model",
        "--faster",
        "--dry-run", "--workers", "--poll-interval",
        "--max-output-bytes", "--no-send", "--timeout",
        "--verbose", "--quiet", "--pdb",
    ]
    EXAMPLES = [
        "install.py",
        "install.py --verbose --poll-interval 30",
        "install.py --check",
        "install.py --logs --follow",
    ]

    @classmethod
    def setUpClass(cls):
        cls.proc = _help_output(
            os.path.join("runner", "install.py"), "--help")
        cls.out = cls.proc.stdout

    def test_help_exits_0(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_every_flag_is_listed(self):
        for flag in self.FLAGS:
            with self.subTest(flag=flag):
                self.assertIn(flag, self.out)

    def test_group_titles_appear_in_order(self):
        positions = []
        for title in self.GROUPS:
            at = self.out.find(f"\n{title}:\n")
            self.assertGreaterEqual(at, 0, title)
            positions.append(at)
        self.assertEqual(positions, sorted(positions))

    def test_examples_are_verbatim(self):
        self.assertIn("Install Homing Pigeon as a service on this "
                      "machine.", self.out)
        for example in self.EXAMPLES:
            with self.subTest(example=example):
                self.assertIn(f"  {example}\n", self.out)


class SendJobHelpDocumentTest(unittest.TestCase):
    """send_job.py --help and `new --help`: same hand again."""

    @classmethod
    def setUpClass(cls):
        cls.proc = _help_output(
            os.path.join("cloud", "send_job.py"), "--help")
        cls.out = cls.proc.stdout

    def test_help_exits_0(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_top_level_document(self):
        self.assertIn("If it isn't signed, it isn't sent.",
                      self.out)
        for example in (
                "send_job.py new --kind ping --secret <secret>",
                "send_job.py verify --secret <secret> < result.txt"):
            with self.subTest(example=example):
                self.assertIn(f"  {example}\n", self.out)
        for cmd in ("new", "task-submit", "task-request", "verify"):
            self.assertIn(cmd, self.out)

    def test_new_help_groups_and_flags(self):
        proc = _help_output(os.path.join("cloud", "send_job.py"),
                            "new", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        positions = []
        for title in ("the job", "files, arguments, environment",
                      "addressing and signing"):
            at = out.find(f"\n{title}:\n")
            self.assertGreaterEqual(at, 0, title)
            positions.append(at)
        self.assertEqual(positions, sorted(positions))
        for flag in ("--kind", "--job-id", "--script-file",
                     "--script-url", "--script-sha384",
                     "--interpreter", "--timeout", "--file",
                     "--arg", "--env", "--key-id", "--aud",
                     "--reply-to", "--secret"):
            with self.subTest(flag=flag):
                self.assertIn(flag, out)

    def test_every_subcommand_help_exits_0(self):
        for cmd in ("task-submit", "task-request", "verify"):
            with self.subTest(cmd=cmd):
                proc = _help_output(
                    os.path.join("cloud", "send_job.py"), cmd,
                    "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
