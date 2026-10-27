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
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

from runner import runner
from runner.wire import jobcrypto
from runner._version import __version__
from runner.runner import (
    Board, apply_cli_overrides, handle_mail, handle_v2_mail, poll_once,
    sign_payload,
)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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

    def test_version_2_flags_are_opt_in(self):
        cfg = {}
        applied = apply_cli_overrides(cfg, _override_args(
            protocol_v2=True, answer_only=True))
        self.assertIs(cfg["protocol_v2"], True)
        self.assertIs(cfg["answer_only"], True)
        self.assertEqual(set(applied), {"protocol_v2", "answer_only"})
        cfg = {"protocol_v2": True}
        applied = apply_cli_overrides(cfg, _override_args())
        self.assertIs(cfg["protocol_v2"], True)
        self.assertNotIn("protocol_v2", applied)

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
    from runner.ops import setup
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


def _encrypted_body_for(job):
    """The wire form of a job since the HMAC-only form was
    removed: the signed body, encrypted, the envelope signed."""
    return jobcrypto.encrypt_body(
        sign_payload(job, SECRET), SECRET,
        job_id=job["job_id"], key_id="", sign=sign_payload)


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
        good = _encrypted_body_for({
            "v": 1, "type": "job", "job_id": "good1",
            "issued_at": _now(), "kind": "ping"})
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
        good = _encrypted_body_for({
            "v": 1, "type": "job", "job_id": "good1",
            "issued_at": _now(), "kind": "ping"})
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


def _seal_v2(obj):
    return jobcrypto.encrypt_body(
        sign_payload(obj, SECRET), SECRET,
        job_id=obj["msg_id"], key_id="", sign=sign_payload)


class DiskClaimIngestTest(_VerbosityGuard):
    def _ping(self, job_id):
        job = {"v": 1, "type": "job", "job_id": job_id,
               "issued_at": _now(), "kind": "ping"}
        return _mail("[HOMING-PIGEON] job " + job_id,
                     _encrypted_body_for(job))

    def _handle(self, job_id, owns):
        runner._set_verbosity(2)
        cfg = {"mailbox_user": "t@example.com", "shared_secret": SECRET}
        imap = _IMAP()
        imap.marked = []
        imap.store = lambda *args: imap.marked.append(args) or ("OK", None)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(runner, "_disk_owns", owns), \
                    _captured_log() as buf:
                handle_mail(cfg, imap, _SMTP(), 4, self._ping(job_id),
                            d, {}, runner.build_secrets(cfg), _Opts())
        return buf.getvalue(), imap.marked

    def test_a_job_the_disk_already_finished_is_not_run(self):
        def owns(_base, key, seen):
            seen[key] = True
            return False

        out, marked = self._handle("disk1", owns)
        self.assertIn("job disk1: skipped; already seen", out)
        self.assertEqual(len(marked), 1)

    def test_a_job_another_process_holds_stays_unseen(self):
        def owns(_base, _key, _seen):
            return False

        out, marked = self._handle("held1", owns)
        self.assertIn("another process holds it", out)
        self.assertEqual(marked, [])


class Version2IngestTest(_VerbosityGuard):
    def _cfg(self, **extra):
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": SECRET,
               "protocol_v2": True}
        cfg.update(extra)
        return cfg

    def _question(self):
        from runner.wire import protocol_v2 as v2
        return v2.question_for(
            {"protocol_v2": True},
            {"job_id": "j1", "kind": "exec"})

    def _take(self, cfg, subject, body):
        imap = _IMAP()
        with tempfile.TemporaryDirectory() as d:
            with _captured_log() as buf:
                taken = handle_v2_mail(
                    cfg, imap, _SMTP(), 9,
                    _mail(subject, body), subject,
                    runner.build_secrets(cfg), _Opts(), d)
        return taken, buf.getvalue()

    def test_a_bad_signature_and_a_bad_envelope_are_refused(self):
        q = self._question()
        cfg = self._cfg()
        taken, out = self._take(
            cfg, "[HOMING-PIGEON] question " + q["msg_id"], "nope")
        self.assertTrue(taken)
        self.assertIn("bad signature", out)
        taken, out = self._take(
            cfg, "[HOMING-PIGEON] question wrong-id", _seal_v2(q))
        self.assertTrue(taken)
        self.assertIn("bad envelope", out)

    def test_cleartext_and_an_unlisted_answerer_are_refused(self):
        q = self._question()
        saved = runner._ALLOW_CLEARTEXT_JOBS
        runner._ALLOW_CLEARTEXT_JOBS = False
        try:
            taken, out = self._take(
                self._cfg(),
                "[HOMING-PIGEON] question " + q["msg_id"],
                sign_payload(q, SECRET))
        finally:
            runner._ALLOW_CLEARTEXT_JOBS = saved
        self.assertTrue(taken)
        self.assertIn("cleartext version 2 message refused", out)
        taken, out = self._take(
            self._cfg(v2_answerers=["someone-else"]),
            "[HOMING-PIGEON] question " + q["msg_id"],
            _seal_v2(q))
        self.assertTrue(taken)
        self.assertIn("answerer is not enabled", out)

    def test_a_question_the_schema_refuses_is_not_answered(self):
        q = self._question()
        q["deadline_sec"] = 99
        taken, out = self._take(
            self._cfg(),
            "[HOMING-PIGEON] question " + q["msg_id"],
            _seal_v2(q))
        self.assertTrue(taken)
        self.assertIn("deadline_sec", out)

    def test_the_answerer_uses_the_model_and_survives_it_failing(self):
        from runner.wire import protocol_v2 as v2
        q = self._question()
        cfg = self._cfg(answer_only=True)
        subject = "[HOMING-PIGEON] question " + q["msg_id"]
        body = _seal_v2(q)
        used = {}
        real = v2.answer_for

        def answer_for(payload, text):
            used["text"] = text
            return real(payload, text)

        with mock.patch.object(
                runner, "inference_config", return_value={"model": "x"}), \
                mock.patch.object(
                    runner, "ask_model",
                    return_value={"answer": "  hold the job  "}), \
                mock.patch.object(
                    runner._protocol_v2, "answer_for", answer_for):
            taken, out = self._take(cfg, subject, body)
        self.assertTrue(taken)
        self.assertEqual(used["text"], "hold the job")
        self.assertNotIn("answerer model failed", out)

        with mock.patch.object(
                runner, "inference_config", return_value={"model": "x"}), \
                mock.patch.object(
                    runner, "ask_model",
                    side_effect=RuntimeError("down")):
            taken, out = self._take(cfg, subject, body)
        self.assertTrue(taken)
        self.assertIn("answerer model failed", out)

    def test_version_2_off_marks_the_message_and_does_not_answer(self):
        runner._set_verbosity(2)
        q = self._question()
        cfg = {"mailbox_user": "t@example.com", "shared_secret": SECRET}
        imap = _IMAP()
        imap.marked = []
        imap.store = lambda *args: imap.marked.append(args) or ("OK", None)
        with tempfile.TemporaryDirectory() as d:
            with _captured_log() as buf:
                taken = handle_v2_mail(
                    cfg, imap, _SMTP(), 9,
                    _mail("[HOMING-PIGEON] question " + q["msg_id"],
                          _seal_v2(q)),
                    "[HOMING-PIGEON] question " + q["msg_id"],
                    runner.build_secrets(cfg), _Opts(), d)
        self.assertTrue(taken)
        self.assertIn("protocol_v2 is off", buf.getvalue())
        self.assertEqual(len(imap.marked), 1)

    def test_a_determination_is_logged_and_not_executed(self):
        from runner.wire import protocol_v2 as v2
        det = v2.determination_for(
            {"job_id": "j1"},
            {"findings": [{"detail": "rm"}]})
        taken, out = self._take(
            self._cfg(),
            "[HOMING-PIGEON] determination " + det["msg_id"],
            _seal_v2(det))
        self.assertTrue(taken)
        self.assertIn("version 2 determination", out)
        self.assertIn("fail", out)


class Version2IngestRejectionsTest(unittest.TestCase):
    """Queue A refill: handle_v2_mail's remaining
    rejection legs (coverage run 40187685363: 6 lines
    on both platforms). The v2 intake contract: with
    the v2 module unavailable the message is not this
    function's at all (False, the caller treats it as
    a job); a sealed message whose body disagrees
    with its subject -- type or msg_id -- is rejected
    and taken, never acted on; and a question the
    answer builder itself refuses (its ids are not
    safe ids) is rejected the same way.
    """

    def _cfg(self, **extra):
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": SECRET,
               "protocol_v2": True}
        cfg.update(extra)
        return cfg

    def _question(self):
        from runner.wire import protocol_v2 as v2
        return v2.question_for(
            {"protocol_v2": True},
            {"job_id": "j1", "kind": "exec"})

    def _take(self, cfg, subject, body):
        imap = _IMAP()
        with tempfile.TemporaryDirectory() as d:
            with _captured_log() as buf:
                taken = handle_v2_mail(
                    cfg, imap, _SMTP(), 9,
                    _mail(subject, body), subject,
                    runner.build_secrets(cfg), _Opts(), d)
        return taken, buf.getvalue()

    def test_no_v2_module_is_not_taken(self):
        q = self._question()
        with mock.patch.object(runner, "_protocol_v2", None):
            taken, _out = self._take(
                self._cfg(),
                "[HOMING-PIGEON] question " + q["msg_id"],
                _seal_v2(q))
        self.assertFalse(taken)

    def test_a_subject_body_mismatch_is_rejected(self):
        from runner.wire import protocol_v2 as v2
        det = v2.determination_for(
            {"job_id": "j1"},
            {"findings": [{"detail": "rm"}]})
        taken, out = self._take(
            self._cfg(),
            "[HOMING-PIGEON] question " + det["msg_id"],
            _seal_v2(det))
        self.assertTrue(taken)
        self.assertIn("subject does not match the body", out)

    def test_an_unanswerable_question_is_rejected(self):
        q = self._question()
        with mock.patch.object(
                runner._protocol_v2, "answer_for",
                side_effect=ValueError(
                    "question msg_id is not a safe id")):
            taken, out = self._take(
                self._cfg(answer_only=True),
                "[HOMING-PIGEON] question " + q["msg_id"],
                _seal_v2(q))
        self.assertTrue(taken)
        self.assertIn("not a safe id", out)


class Version2IngestPumpTest(unittest.TestCase):
    def _cfg(self):
        return {"mailbox_user": "t@example.com",
                "shared_secret": SECRET, "protocol_v2": True}

    def test_a_fetch_that_throws_does_not_start_a_job(self):
        cfg = self._cfg()
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    runner, "fetch_job_mails",
                    side_effect=OSError("down")), \
                    _captured_log() as buf:
                runner._v2_ingest(
                    cfg, _IMAP(), d, {}, runner.build_secrets(cfg),
                    _Opts())
        self.assertIn("version 2 ingest failed", buf.getvalue())

    def test_no_transport_means_nothing_to_file(self):
        cfg = self._cfg()
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(runner, "_transports", None):
                runner._v2_ingest(
                    cfg, None, d, {}, runner.build_secrets(cfg),
                    _Opts())

    def test_a_channel_that_throws_is_skipped(self):
        cfg = self._cfg()

        class Msg:
            subject = "hello there"
            body = "nope"

            def ack(self):
                raise AssertionError("a non-version-2 mail was acked")

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    runner, "_enabled_transports",
                    side_effect=[RuntimeError("no"), ["file"]]), \
                    _captured_log() as buf:
                runner._v2_ingest(
                    cfg, None, d, {}, runner.build_secrets(cfg),
                    _Opts())
            self.assertIn("version 2 ingest failed", buf.getvalue())
            with mock.patch.object(
                    runner, "_enabled_transports", return_value=["file"]), \
                    mock.patch.object(
                        runner._transports, "fetch_channel_messages",
                        side_effect=OSError("closed")), \
                    _captured_log() as buf:
                runner._v2_ingest(
                    cfg, None, d, {}, runner.build_secrets(cfg),
                    _Opts())
            self.assertIn("ingest file failed", buf.getvalue())
            with mock.patch.object(
                    runner, "_enabled_transports", return_value=["file"]), \
                    mock.patch.object(
                        runner._transports, "fetch_channel_messages",
                        return_value=[Msg()]):
                runner._v2_ingest(
                    cfg, None, d, {}, runner.build_secrets(cfg),
                    _Opts())


class DigestRewriteTest(_VerbosityGuard):
    def test_a_remediation_digest_is_rewritten_to_the_job_as_received(self):
        job = {"v": 1, "type": "job", "job_id": "rem1",
               "issued_at": _now(), "kind": "ping"}
        raw = _mail("[HOMING-PIGEON] job rem1", _encrypted_body_for(job))
        cfg = {"mailbox_user": "t@example.com", "shared_secret": SECRET}
        seen = {}

        def execute_job(_cfg, _job, _base):
            return {"exit_code": 0, "stdout": "", "stderr": "",
                    "duration_sec": 0.0,
                    "remediation": {"received_digest": "stale"}}

        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(runner, "execute_job", execute_job), \
                    mock.patch.object(
                        runner._remediation, "fix_marker_digest") as fix:
                handle_mail(cfg, _IMAP(), _SMTP(), 1, raw, d, seen,
                            runner.build_secrets(cfg), _Opts())
        self.assertTrue(fix.called)
        self.assertNotEqual(fix.call_args[0][2], "stale")


class PollCloseTest(unittest.TestCase):
    def test_a_logout_and_a_quit_that_fail_do_not_fail_the_poll(self):
        cfg = {"mailbox_user": "t@example.com", "shared_secret": SECRET}
        imap = _IMAP()

        def logout():
            raise OSError("gone")

        imap.logout = logout
        smtp = _SMTP()

        def quit_():
            raise OSError("gone")

        smtp.quit = quit_
        with tempfile.TemporaryDirectory() as d:
            seen_path = os.path.join(d, "seen.json")
            with mock.patch.object(runner, "connect_imap",
                                    return_value=imap):
                poll_once(cfg, d, {}, seen_path, imap=None,
                          smtp=_SMTP(), opts=_Opts())
            with mock.patch.object(runner, "connect_smtp",
                                    return_value=smtp):
                poll_once(cfg, d, {}, seen_path, imap=_IMAP(),
                          smtp=None, opts=_Opts())


class ExtensionReportTest(unittest.TestCase):
    def test_a_loader_that_throws_is_a_warning(self):
        with mock.patch.object(
                runner._extensions, "load_extensions",
                side_effect=RuntimeError("boom")), \
                _captured_log() as buf:
            runner._report_extensions({}, "/tmp")
        self.assertIn("loader failed", buf.getvalue())

    def test_a_registry_that_is_not_a_map_loads_nothing(self):
        with mock.patch.object(
                runner._extensions, "load_extensions",
                return_value=(["nope"], [])), \
                _captured_log() as buf:
            runner._report_extensions({}, "/tmp")
        self.assertNotIn("extension loaded", buf.getvalue())


class JudgeVerboseTest(_VerbosityGuard):
    def _handle(self, cfg, job):
        raw = _mail(f"[HOMING-PIGEON] job {job['job_id']}",
                    _encrypted_body_for(job))
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
        # The suite shares one process, and log() drops INFO past
        # the per-minute cap. mutmut's stats run hits that cap, so
        # the line under test was the suppression notice instead
        # of the invocation. This call is a fresh start.
        runner._LOG_MINUTE = 0.0
        runner._LOG_COUNT = 0
        runner._LOG_DROPPED = 0
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(sys, "argv", argv):
                with _captured_log() as buf:
                    runner.log_startup({"mailbox_user": "a@b.c"},
                                       args, d)
        lines = [ln for ln in buf.getvalue().splitlines()
                 if ln.strip() and "suppressed this minute" not in ln]
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
        "--config", "--once", "--drain", "--drain-seconds",
        "--dry-run", "--no-send", "--setup",
        "--pdb", "--ignore-personal-documents",
        "--workers", "--poll-interval", "--timeout",
        "--max-output-bytes", "--max-job-age", "--retention-days",
        "--task-timeout", "--max-query-budget",
        "--max-queries-per-hour", "--max-result-view",
        "--judge", "--dag-mode", "--oracle-mode", "--require-review",
        "--protocol-v2", "--answer-only",
        "--no-require-review", "--faster",
        "--local-signals", "--no-local-signals",
        "--local-signal-port", "--wake-cooldown",
        "--verbose", "--quiet", "--log-max-bytes", "--log-backups",
        "--oracle-log", "--no-oracle-log", "--oracle-log-max-bytes",
        "--oracle-log-backups",
        "--oracle", "--oracle-cli", "--oracle-port",
        "--inspect", "--job-id", "--fetch-sources", "--audit-report",
        "--since",
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
        "--ignore-personal-documents",
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
            os.path.join("runner", "ops", "install.py"), "--help")
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
            os.path.join("runner", "cloud", "send_job.py"), "--help")
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
        proc = _help_output(os.path.join("runner", "cloud", "send_job.py"),
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
                    os.path.join("runner", "cloud", "send_job.py"), cmd,
                    "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)


class _RecordingSMTP:
    def __init__(self):
        self.messages = []

    def send_message(self, msg, *a, **k):
        self.messages.append(msg)
        return {}

    def quit(self):
        pass


class HandleMailFailureBranchesTest(_VerbosityGuard):
    """Queue A: handle_mail's failure branches (coverage run
    40180268696: 13 lines on both platforms) -- every one is
    the same promise from a different side path: a failure
    in the Oracle's opinion, the version 2 exchange, the
    remediation follow-up, or the diagnosis must never cost
    the sender their result. The side path is scripted to
    raise at the runner's own seam; the job's result --
    decrypted and verified from the recorded mail -- is
    the assertion.
    """

    def _opts(self):
        opts = _Opts()
        opts.no_send = False
        return opts

    def _exec_mail(self, job_id, script, **job_kw):
        job = {"v": 1, "type": "job", "job_id": job_id,
               "issued_at": _now(), "kind": "exec",
               "interpreter": [sys.executable],
               "script": script}
        job.update(job_kw)
        return _mail("[HOMING-PIGEON] job " + job_id,
                     _encrypted_body_for(job))

    def _result(self, smtp, job_id):
        from runner.cloud import send_job
        for msg in smtp.messages:
            if job_id not in str(msg["Subject"]):
                continue
            body = msg.get_content()
            try:
                data = json.loads(body)
            except ValueError:
                data = None
            if isinstance(data, dict) and jobcrypto.is_envelope(data):
                body = jobcrypto.decrypt_body(
                    data, SECRET, job_id=job_id,
                    key_id=data.get("key_id") or "")
            return send_job.verify_body(body, SECRET)
        return None

    def _run(self, raw, cfg=None, patches=()):
        cfg = cfg or {"mailbox_user": "t@example.com",
                      "shared_secret": SECRET}
        smtp = _RecordingSMTP()
        with tempfile.TemporaryDirectory() as d:
            started = [mock.patch.object(*p) if len(p) == 2
                       else mock.patch.object(*p[:2], **p[2])
                       for p in patches]
            for p in started:
                p.start()
            try:
                with _captured_log() as buf:
                    handle_mail(cfg, _IMAP(), smtp, 1, raw, d, {},
                                runner.build_secrets(cfg),
                                self._opts())
            finally:
                for p in started:
                    p.stop()
        return smtp, buf.getvalue()

    def test_an_encrypted_exec_job_runs_and_reports(self):
        smtp, _log = self._run(
            self._exec_mail("enc-exec-1", "print('sealed hi')"))
        result = self._result(smtp, "enc-exec-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("sealed hi", result["stdout"])

    def test_an_opinion_failure_costs_no_result(self):
        smtp, logs = self._run(
            self._exec_mail("op-fail-1", "print('still ran')"),
            patches=[(runner._opinion, "plan_before",
                      {"side_effect": RuntimeError("opinion down")})])
        result = self._result(smtp, "op-fail-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("still ran", result["stdout"])
        self.assertNotIn("oracle_opinion", result)
        self.assertIn("oracle opinion failed for op-fail-1", logs)

    def test_a_v2_exchange_failure_costs_no_result(self):
        cfg = {"mailbox_user": "t@example.com",
               "shared_secret": SECRET, "protocol_v2": True}
        smtp, logs = self._run(
            self._exec_mail("v2-fail-1", "print('v1 result')"),
            cfg=cfg,
            patches=[(runner, "_v2_before_execute",
                      {"side_effect": RuntimeError("v2 down")})])
        result = self._result(smtp, "v2-fail-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("version 2 exchange failed for v2-fail-1",
                      logs)

    def test_a_malformed_envelope_claim_is_rejected(self):
        # A signed body that carries an hp_enc member which
        # is not a real envelope: the signature verifies, the
        # claim does not, and the job is rejected as a bad
        # envelope -- never decrypted, never run.
        job = {"v": 1, "type": "job", "job_id": "badenv-1",
               "issued_at": _now(), "kind": "ping",
               "hp_enc": {"alg": "not-a-suite"}}
        raw = _mail("[HOMING-PIGEON] job badenv-1",
                    sign_payload(job, SECRET))
        smtp, logs = self._run(raw)
        self.assertEqual(smtp.messages, [])
        self.assertIn("malformed encryption envelope", logs)

    def test_a_remediation_followup_failure_costs_no_result(self):
        # The followup runs when a protected path changed.
        # Confinement snapshots watch the workspace's
        # parent (paths outside the workspace), so the
        # guarded file is the workspace's sibling and the
        # job rewrites it.
        followup = mock.Mock(
            side_effect=RuntimeError("followup down"))
        smtp = _RecordingSMTP()
        with tempfile.TemporaryDirectory() as root:
            base = os.path.join(root, "base")
            ws = os.path.join(root, "ws")
            os.makedirs(base)
            os.makedirs(ws)
            guarded = os.path.join(root, "guarded.txt")
            with open(guarded, "w", encoding="utf-8") as fh:
                fh.write("original\n")
            cfg = {"mailbox_user": "t@example.com",
                   "shared_secret": SECRET,
                   "workspace_root": ws,
                   "protected_paths": [guarded]}
            script = ("open(%r, 'a').write('changed\\n')"
                      % guarded)
            raw = self._exec_mail("rem-fail-1", script)
            with mock.patch.object(
                    runner, "_remediation_confinement_followup",
                    followup):
                with _captured_log():
                    handle_mail(cfg, _IMAP(), smtp, 1, raw, base,
                                {}, runner.build_secrets(cfg),
                                self._opts())
        result = self._result(smtp, "rem-fail-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(followup.called,
                        "the followup branch was never reached")

    def test_a_diagnosis_failure_still_files_the_opinion(self):
        plan = {"active": True, "mode": "deterministic",
                "findings": [], "checks_run": False,
                "attach": None, "repair_action": None}
        smtp, _logs = self._run(
            self._exec_mail("diag-fail-1",
                            "import sys; sys.exit(3)"),
            patches=[
                (runner._opinion, "plan_before",
                 {"return_value": plan}),
                (runner._opinion, "tier1_findings",
                 {"side_effect": RuntimeError("diag down")})])
        result = self._result(smtp, "diag-fail-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["exit_code"], 3)
        self.assertIn("oracle_opinion", result)

    def test_a_rejected_jobs_diagnosis_failure_still_reports(self):
        plan = {"active": True, "mode": "deterministic",
                "findings": [], "checks_run": False,
                "attach": None, "repair_action": None}
        smtp, logs = self._run(
            self._exec_mail("rej-diag-1", "print('never runs')",
                            interpreter=["/nonexistent/hp-bin"]),
            patches=[
                (runner._opinion, "plan_before",
                 {"return_value": plan}),
                (runner._opinion, "tier1_findings",
                 {"side_effect": RuntimeError("diag down")})])
        result = self._result(smtp, "rej-diag-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["exit_code"], -2)
        self.assertNotIn("oracle_opinion", result)


class MainDispatchBranchesTest(_VerbosityGuard):
    """Queue A: the runner.main branches the rig tests
    never drove on Windows (coverage run 40183585961: 11
    lines) -- the --setup wizard hand-off, the Q9
    confinement refusal at startup, the two one-shot
    dispatches that return before the mailbox gate, a
    transport supervisor that fails to start, and a live
    verbose edit re-resolving the level. The rig is
    _main_rig's stub set with the seams under test left
    scriptable.
    """

    def _rig(self, argv, cfg_extra=None, reload_changed=(),
             wizard_cfg=None, extra_patches=()):
        from runner.ops import setup
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(
            runner, "ensure_inference_ready"))
        stack.enter_context(mock.patch.object(
            runner, "update_llama_from_config"))
        stack.enter_context(mock.patch.object(
            runner, "connect_imap"))
        stack.enter_context(mock.patch.object(
            runner, "connect_smtp"))
        poll = stack.enter_context(mock.patch.object(
            runner, "poll_once", return_value=None))
        stack.enter_context(mock.patch.object(
            setup, "is_tty", return_value=False))
        stack.enter_context(mock.patch.object(
            setup, "needs_setup", return_value=None))
        wizard = stack.enter_context(mock.patch.object(
            setup, "run_setup_wizard",
            return_value=wizard_cfg))
        stack.enter_context(mock.patch.object(
            runner, "_start_local_signals"))

        def _reload(cfg_, path, state, pinned=None):
            if "verbose" in reload_changed:
                cfg_["verbose"] = True
            return list(reload_changed)

        stack.enter_context(mock.patch.object(
            runner, "reload_hot_config", side_effect=_reload))
        for target, name, value in extra_patches:
            stack.enter_context(mock.patch.object(
                target, name, value))
        directory = stack.enter_context(
            tempfile.TemporaryDirectory())
        body = {"shared_secret": SECRET,
                "mailbox_user": "a@b.c",
                "mailbox_password": "pw",
                "base_dir": directory}
        if cfg_extra:
            body.update(cfg_extra)
        if wizard_cfg is not None:
            wizard.return_value = dict(body)
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
        return code, poll, wizard, out.getvalue(), err.getvalue()

    def test_setup_hands_the_config_to_the_wizard(self):
        code, poll, wizard, _out, _err = self._rig(
            ["--setup", "--once"], wizard_cfg={})
        self.assertEqual(code, 0)
        self.assertEqual(wizard.call_count, 1)
        self.assertTrue(
            wizard.call_args[0][0].endswith("config.json"))
        self.assertTrue(poll.called)

    def test_enforce_without_a_sandbox_refuses_to_start(self):
        code, poll, _w, _out, err = self._rig(
            ["--once"],
            cfg_extra={"security": {"modes":
                                    {"confinement": "enforce"}}},
            extra_patches=[(runner._sandbox,
                            "startup_problem",
                            lambda: "bwrap is not installed")])
        self.assertEqual(code, 2)
        self.assertIn("the sandbox cannot engage", err)
        self.assertFalse(poll.called)

    def test_fetch_sources_dispatches_and_returns(self):
        fetch = mock.Mock(return_value=7)
        code, _p, _w, _o, _e = self._rig(
            ["--fetch-sources"],
            extra_patches=[(runner, "run_fetch_sources", fetch)])
        self.assertEqual(code, 7)
        self.assertTrue(fetch.called)

    def test_run_variant_dispatches_and_returns(self):
        variant = mock.Mock(return_value=4)
        code, _p, _w, _o, _e = self._rig(
            ["--run-variant", "some-variant.json"],
            extra_patches=[(runner, "run_variant", variant)])
        self.assertEqual(code, 4)
        self.assertTrue(variant.called)

    def test_local_test_dispatches_and_returns(self):
        # The last dispatch line the coverage map still showed
        # unrun on Windows (run 40186249031: runner.py's
        # --local-test return).
        module = mock.Mock()
        module.main.return_value = 7
        load = mock.Mock(return_value=module)
        code, poll, _w, _o, _e = self._rig(
            ["--local-test"],
            extra_patches=[(runner, "_load_mod", load)])
        self.assertEqual(code, 7)
        self.assertTrue(module.main.called)
        self.assertFalse(module.main.call_args[1]["browser"])
        self.assertFalse(poll.called)

    def test_a_dead_supervisor_is_logged_and_the_poll_runs(self):
        code, poll, _w, _o, _e = self._rig(
            ["--once"],
            extra_patches=[(runner._transports,
                            "start_supervisor",
                            mock.Mock(side_effect=RuntimeError(
                                "no transports today")))])
        self.assertEqual(code, 0)
        self.assertTrue(poll.called)

    def test_a_live_verbose_edit_re_resolves_the_level(self):
        code, _p, _w, _o, _e = self._rig(
            ["--once"], reload_changed=("verbose",))
        self.assertEqual(code, 0)
        self.assertEqual(runner._VERBOSE_LEVEL, 2)


class Version2IngestBranchesTest(_VerbosityGuard):
    """Queue A: the _v2_ingest branches the pump tests
    never reached (coverage run 40183585961: 11 lines on
    both platforms) -- the two absent-module returns, an
    unparseable mail in the IMAP fetch, the IMAP hand-off
    itself, and the transport path's ack discipline. The
    docstring's contract: jobs stay where they are, a
    message this process does not consume is never acked
    (acking would mark it seen), and one bad message or
    channel never stops the rest.
    """

    def _cfg(self):
        return {"mailbox_user": "t@example.com",
                "shared_secret": SECRET, "protocol_v2": True}

    def _ingest(self, cfg, imap, d):
        runner._v2_ingest(cfg, imap, d, {},
                           runner.build_secrets(cfg), _Opts())

    def test_no_v2_module_and_no_fetch_both_return_quietly(self):
        cfg = self._cfg()
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(runner, "_protocol_v2", None):
                self._ingest(cfg, _IMAP(), d)
            saved = runner.fetch_job_mails
            del runner.fetch_job_mails
            try:
                self._ingest(cfg, _IMAP(), d)
            finally:
                runner.fetch_job_mails = saved

    def test_the_imap_path_skips_bad_mail_and_hands_off_v2(self):
        cfg = self._cfg()
        plain = _mail("[HOMING-PIGEON] job plain-1",
                      sign_payload(
                          {"v": 1, "type": "job",
                           "job_id": "plain-1",
                           "issued_at": _now(), "kind": "ping"},
                          SECRET))
        v2_raw = _mail(
            "[HOMING-PIGEON] determination det-1", "sealed")
        handed = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    runner, "fetch_job_mails",
                    return_value=[(1, None), (2, plain),
                                  (3, v2_raw)]), \
                    mock.patch.object(
                        runner, "handle_v2_mail",
                        lambda *a, **kw: handed.append(a)):
                self._ingest(cfg, _IMAP(), d)
        self.assertEqual(len(handed), 1)
        self.assertEqual(handed[0][3], 3)  # the v2 mail's seq
        self.assertIn("determination", handed[0][5])

    class _Msg:
        def __init__(self, subject, ack_error=None):
            self.subject = subject
            self.body = "sealed"
            self.acked = False
            self._ack_error = ack_error

        def ack(self):
            self.acked = True
            if self._ack_error is not None:
                raise self._ack_error

    def _transport_ingest(self, cfg, d, msgs, handler):
        with mock.patch.object(
                runner, "_enabled_transports",
                return_value=["file"]), \
                mock.patch.object(
                    runner._transports,
                    "fetch_channel_messages",
                    return_value=msgs), \
                mock.patch.object(
                    runner, "handle_v2_mail", handler):
            self._ingest(cfg, None, d)

    def test_the_transport_path_acks_only_what_it_consumed(self):
        cfg = self._cfg()
        consumed = self._Msg("[HOMING-PIGEON] answer a-1")
        left = self._Msg("[HOMING-PIGEON] answer a-2")
        plain = self._Msg("just a note")

        def handler(cfg_, box, smtp, seq, raw, subject,
                    secrets, opts, base_dir, seen=None):
            if subject == consumed.subject:
                box.store()  # consumed: the core marks it seen

        with tempfile.TemporaryDirectory() as d:
            self._transport_ingest(
                cfg, d, [consumed, left, plain], handler)
        self.assertTrue(consumed.acked)
        self.assertFalse(left.acked)
        self.assertFalse(plain.acked)

    def test_a_handler_failure_and_a_failed_ack_are_only_logged(self):
        cfg = self._cfg()
        boom = self._Msg("[HOMING-PIGEON] answer b-1")
        bad_ack = self._Msg("[HOMING-PIGEON] answer b-2",
                            ack_error=OSError("gone"))

        def handler(cfg_, box, smtp, seq, raw, subject,
                    secrets, opts, base_dir, seen=None):
            if subject == boom.subject:
                raise RuntimeError("handler down")
            box.store()

        with tempfile.TemporaryDirectory() as d:
            with _captured_log() as buf:
                self._transport_ingest(cfg, d, [boom, bad_ack],
                                       handler)
        logs = buf.getvalue()
        self.assertIn("version 2 ingest message failed", logs)
        self.assertIn("version 2 ingest ack failed", logs)
        self.assertFalse(boom.acked)
        self.assertTrue(bad_ack.acked)


class Version2HandOffFallbacksTest(unittest.TestCase):
    """Queue A refill: _v2_hand_off's failure legs
    (coverage run 40189608702: 5 lines on both
    platforms). The hand-off's docstring fixes the
    contract: a captured send is written to the
    channel now, per enabled transport; a transport
    list that cannot be read, and a channel write
    that fails, each degrade to the ordinary send --
    the message still goes out, the failure is
    logged, and nothing is written twice.
    """

    SUBJECT = "[HOMING-PIGEON] determination d-1"

    def _hand_off(self, enabled, write):
        sent = []
        with mock.patch.object(
                runner, "_enabled_transports", enabled), \
                mock.patch.object(
                    runner._transports,
                    "write_channel_result", write), \
                mock.patch.object(
                    runner, "send_mail",
                    lambda *a, **kw: sent.append((a, kw))), \
                mock.patch.object(runner, "log",
                                  lambda *a, **kw: None):
            out = runner._v2_hand_off(
                {}, runner._CaptureSMTP(), "/base",
                self.SUBJECT, "BODY", "target@example.org")
        return out, sent

    def test_an_unreadable_transport_list_falls_back_to_send(self):
        out, sent = self._hand_off(
            mock.Mock(side_effect=RuntimeError("cfg gone")),
            mock.Mock())
        self.assertEqual(out, [])
        self.assertEqual(len(sent), 1)

    def test_a_failing_channel_write_falls_back_to_send(self):
        out, sent = self._hand_off(
            lambda cfg: ["file"],
            mock.Mock(side_effect=RuntimeError("disk")))
        self.assertEqual(out, [])
        self.assertEqual(len(sent), 1)

    def test_a_written_channel_is_not_sent_again(self):
        out, sent = self._hand_off(
            lambda cfg: ["file"],
            mock.Mock(return_value="/chan/out.eml"))
        self.assertEqual(out, ["/chan/out.eml"])
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
