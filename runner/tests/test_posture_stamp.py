# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Q137: the disclosure posture stamp producer.

The desk's supposition, pinned: the runner resolves the
deployment's assignment at startup from runner-side state
alone, and at the completion seam -- where it assembles an
executed job's result and writes its audit row, after the
job has exited -- stamps both with format_stamp over that
resolution. A stamp field arriving on a job is never read;
a deployment with no assignment is recorded unstamped,
plainly, with no invented default; an assignment naming a
retired posture refuses startup as a configuration problem.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

from runner import runner
from runner.runner import handle_mail, sign_payload
from runner.wire import jobcrypto

SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)

REGISTRY = {
    "format": "hp-posture-registry",
    "version": 1,
    "postures": [
        {"id": "named-only", "tag": "C",
         "say": "The project may be named in public writing.",
         "shelf": "Public shelf."},
        {"id": "nothing-said", "tag": "A",
         "say": "Nothing may be said about the project.",
         "shelf": "Private shelf only."},
        {"id": "old-posture", "tag": "Z",
         "say": "The project could once be described.",
         "shelf": "Private shelf only.",
         "status": "retired", "successor": "named-only"},
    ],
}

TAGGING = {
    "format": "hp-posture-tagging",
    "version": 1,
    "projects": [
        {"project": "bookend", "posture": "C"},
        {"project": "legacy", "posture": "Z"},
    ],
}

STAMP = "hp-posture-1-named-only"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


def _encrypted_body_for(job):
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
    no_send = False
    inspect = False
    oracle = False
    pdb = False


@contextlib.contextmanager
def _captured_log():
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


class _PostureGuard(unittest.TestCase):
    """Save and restore the process posture state (and the
    cleartext flag) around every test: the state is per-process
    by design, and no test here may leak its resolution into
    the next."""

    def setUp(self):
        self._saved = (runner._POSTURE_DECLARED, runner._POSTURE_PROJECT,
                       runner._POSTURE_STAMP)
        self._saved_cleartext = runner._ALLOW_CLEARTEXT_JOBS

    def tearDown(self):
        runner._set_posture_resolution(*self._saved)
        runner._set_allow_cleartext_jobs(self._saved_cleartext)


def _write_posture_files(d, registry=REGISTRY, tagging=TAGGING):
    reg = os.path.join(d, "registry.json")
    tag = os.path.join(d, "tagging.json")
    with open(reg, "w", encoding="utf-8") as fh:
        json.dump(registry, fh)
    with open(tag, "w", encoding="utf-8") as fh:
        json.dump(tagging, fh)
    return reg, tag


def _block(d, project, registry=None, tagging=None):
    reg, tag = _write_posture_files(d)
    return {"registry": registry if registry is not None else reg,
            "tagging": tagging if tagging is not None else tag,
            "project": project}


class ResolvePostureStampTest(_PostureGuard):
    def test_no_block_is_undeclared(self):
        self.assertEqual(runner._resolve_posture_stamp({}, "/nonexistent"),
                         (False, "", None))
        self.assertEqual(
            runner._resolve_posture_stamp({"disclosure_posture": {}}, "/x"),
            (False, "", None))

    def test_a_block_that_is_not_an_object_is_a_config_error(self):
        with self.assertRaises(RuntimeError):
            runner._resolve_posture_stamp(
                {"disclosure_posture": "named-only"}, "/x")

    def test_a_half_filled_block_names_the_missing_key(self):
        with tempfile.TemporaryDirectory() as d:
            block = _block(d, "bookend")
            del block["tagging"]
            with self.assertRaises(RuntimeError) as cm:
                runner._resolve_posture_stamp(
                    {"disclosure_posture": block}, d)
            self.assertIn("tagging", str(cm.exception))
            block = _block(d, "bookend")
            block["project"] = "  "
            with self.assertRaises(RuntimeError) as cm:
                runner._resolve_posture_stamp(
                    {"disclosure_posture": block}, d)
            self.assertIn("project", str(cm.exception))

    def test_an_active_assignment_resolves_to_its_stamp(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"disclosure_posture": _block(d, "bookend")}
            self.assertEqual(runner._resolve_posture_stamp(cfg, d),
                             (True, "bookend", STAMP))

    def test_relative_paths_resolve_against_base_dir(self):
        with tempfile.TemporaryDirectory() as d:
            _write_posture_files(d)
            block = {"registry": "registry.json",
                     "tagging": "tagging.json", "project": "bookend"}
            self.assertEqual(
                runner._resolve_posture_stamp(
                    {"disclosure_posture": block}, d),
                (True, "bookend", STAMP))

    def test_no_assignment_for_the_project_is_unstamped_not_invented(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"disclosure_posture": _block(d, "ghost")}
            self.assertEqual(runner._resolve_posture_stamp(cfg, d),
                             (True, "ghost", None))

    def test_a_retired_assignment_is_format_stamps_own_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"disclosure_posture": _block(d, "legacy")}
            with self.assertRaises(RuntimeError) as cm:
                runner._resolve_posture_stamp(cfg, d)
            self.assertIn("retired", str(cm.exception))

    def test_an_undeclared_tag_is_a_config_error_naming_it(self):
        with tempfile.TemporaryDirectory() as d:
            tagging = {"format": "hp-posture-tagging", "version": 1,
                       "projects": [{"project": "mystery",
                                     "posture": "Q"}]}
            reg, tag = _write_posture_files(d, tagging=tagging)
            cfg = {"disclosure_posture": {
                "registry": reg, "tagging": tag, "project": "mystery"}}
            with self.assertRaises(RuntimeError) as cm:
                runner._resolve_posture_stamp(cfg, d)
            self.assertIn("'Q'", str(cm.exception))

    def test_unreadable_and_malformed_files_are_config_errors(self):
        with tempfile.TemporaryDirectory() as d:
            reg, tag = _write_posture_files(d)
            cfg = {"disclosure_posture": {
                "registry": os.path.join(d, "absent.json"),
                "tagging": tag, "project": "bookend"}}
            with self.assertRaises(RuntimeError):
                runner._resolve_posture_stamp(cfg, d)
            with open(reg, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            cfg = {"disclosure_posture": {
                "registry": reg, "tagging": tag, "project": "bookend"}}
            with self.assertRaises(RuntimeError):
                runner._resolve_posture_stamp(cfg, d)

    def test_a_build_without_the_module_refuses_a_declared_block(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"disclosure_posture": _block(d, "bookend")}
            with mock.patch.object(runner, "_disclosure", None):
                with self.assertRaises(RuntimeError):
                    runner._resolve_posture_stamp(cfg, d)
                # Undeclared is untouched by the missing module.
                self.assertEqual(runner._resolve_posture_stamp({}, d),
                                 (False, "", None))


def _read_result(body, secrets, job_id):
    """The receiver's read of a result body: verify, decrypt,
    verify -- the same path _record_payload walks."""
    payload = runner.verify_body_keyed(body, secrets)
    if isinstance(payload, tuple):
        payload = payload[0]
    if jobcrypto.is_envelope(payload):
        inner = jobcrypto.decrypt_body(payload, SECRET, job_id, "")
        payload = runner.verify_body(inner, SECRET)
    return payload


def _posture_rows(base_dir):
    path = os.path.join(base_dir, "security-audit.jsonl")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            entry = json.loads(line)
            if entry.get("feature") == "posture":
                rows.append(entry)
    return rows


class StampSeamTest(_PostureGuard):
    def _run(self, d, job, cfg=None):
        cfg = cfg if cfg is not None else {
            "mailbox_user": "t@example.com", "shared_secret": SECRET}
        sent = []

        def fake_send(smtp, c, subject, body, to=None):
            sent.append((subject, body))

        raw = _mail("[HOMING-PIGEON] job " + job["job_id"],
                    _encrypted_body_for(job))
        with mock.patch.object(runner, "send_mail", fake_send):
            with _captured_log():
                handle_mail(cfg, _IMAP(), _SMTP(), 7, raw, d, {},
                            runner.build_secrets(cfg), _Opts())
        self.assertEqual(len(sent), 1, sent)
        return _read_result(sent[0][1], runner.build_secrets(cfg),
                            job["job_id"])

    def _ping(self, job_id, **extra):
        job = {"v": 1, "type": "job", "job_id": job_id,
               "issued_at": _now(), "kind": "ping"}
        job.update(extra)
        return job

    def test_an_assigned_deployment_stamps_result_and_audit_row(self):
        runner._set_posture_resolution(True, "bookend", STAMP)
        with tempfile.TemporaryDirectory() as d:
            result = self._run(d, self._ping("stamp1"))
            self.assertEqual(result["posture_stamp"], STAMP)
            rows = _posture_rows(d)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["decision"], "stamped")
            self.assertEqual(rows[0]["detail"], STAMP)
            self.assertEqual(rows[0]["job_id"], "stamp1")

    def test_a_job_cannot_move_the_stamp_in_either_direction(self):
        # Assigned: the job's own stamp-shaped member, naming a
        # different posture, is never read -- the runner's
        # resolution is what the result carries.
        runner._set_posture_resolution(True, "bookend", STAMP)
        with tempfile.TemporaryDirectory() as d:
            result = self._run(d, self._ping(
                "stamp2", posture_stamp="hp-posture-1-nothing-said"))
            self.assertEqual(result["posture_stamp"], STAMP)
        # Undeclared: a job cannot stamp itself into existence.
        runner._set_posture_resolution(False, "", None)
        with tempfile.TemporaryDirectory() as d:
            result = self._run(d, self._ping(
                "stamp3", posture_stamp=STAMP))
            self.assertNotIn("posture_stamp", result)
            self.assertEqual(_posture_rows(d), [])

    def test_a_declared_unassigned_deployment_records_unstamped(self):
        runner._set_posture_resolution(True, "ghost", None)
        with tempfile.TemporaryDirectory() as d:
            result = self._run(d, self._ping("stamp4"))
            self.assertNotIn("posture_stamp", result)
            rows = _posture_rows(d)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["decision"], "unstamped")
            self.assertEqual(rows[0]["detail"], "ghost")
            self.assertEqual(rows[0]["job_id"], "stamp4")

    def test_an_undeclared_deployment_leaves_no_trace(self):
        runner._set_posture_resolution(False, "", None)
        with tempfile.TemporaryDirectory() as d:
            result = self._run(d, self._ping("stamp5"))
            self.assertNotIn("posture_stamp", result)
            self.assertEqual(_posture_rows(d), [])

    def test_a_real_exec_run_is_stamped_after_it_exits(self):
        runner._set_posture_resolution(True, "bookend", STAMP)
        cfg = {"mailbox_user": "t@example.com", "shared_secret": SECRET,
               "security": {"modes": {"confinement": "off",
                                      "job_user": "off",
                                      "audience": "off"}}}
        job = {"v": 1, "type": "job", "job_id": "stamp6",
               "issued_at": _now(), "kind": "exec",
               "script": "print('hp-stamp-ok')",
               "interpreter": [sys.executable]}
        with tempfile.TemporaryDirectory() as d:
            result = self._run(d, job, cfg=cfg)
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["posture_stamp"], STAMP)
            rows = _posture_rows(d)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["decision"], "stamped")

    def test_a_rejected_job_carries_no_stamp_and_no_row(self):
        # The rejection result records no run: stamping it would
        # put the posture of a run that never happened on it.
        runner._set_posture_resolution(True, "bookend", STAMP)
        job = {"v": 1, "type": "job", "job_id": "stamp7",
               "issued_at": _now(), "kind": "exec"}
        with tempfile.TemporaryDirectory() as d:
            result = self._run(d, job)
            self.assertEqual(result["exit_code"], -2)
            self.assertNotIn("posture_stamp", result)
            self.assertEqual(_posture_rows(d), [])

    def test_the_stamp_rides_inside_what_the_runner_signs(self):
        runner._set_posture_resolution(True, "bookend", STAMP)
        runner._set_allow_cleartext_jobs(True)
        cfg = {"mailbox_user": "t@example.com", "shared_secret": SECRET}
        job = self._ping("stamp8")
        sent = []

        def fake_send(smtp, c, subject, body, to=None):
            sent.append(body)

        raw = _mail("[HOMING-PIGEON] job stamp8",
                    sign_payload(job, SECRET))
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(runner, "send_mail", fake_send):
                with _captured_log():
                    handle_mail(cfg, _IMAP(), _SMTP(), 7, raw, d, {},
                                runner.build_secrets(cfg), _Opts())
        self.assertEqual(len(sent), 1)
        body = sent[0]
        self.assertIn(STAMP, body)
        self.assertEqual(runner.verify_body(body, SECRET)["posture_stamp"],
                         STAMP)
        forged = body.replace(STAMP, "hp-posture-1-nothing-said")
        self.assertNotEqual(forged, body)
        with self.assertRaises(ValueError):
            runner.verify_body(forged, SECRET)


class StartupGateTest(_PostureGuard):
    def _main(self, d, cfg, *extra_argv):
        cfg_path = os.path.join(d, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        out, err = io.StringIO(), io.StringIO()
        argv = ["runner", "--config", cfg_path, "--audit-report",
                *extra_argv]
        # The startup announcement rides runner.log(), whose INFO
        # lines share one per-minute budget across the whole test
        # process; in a full-suite run earlier tests can spend it
        # and the line is suppressed before this test ever runs.
        # This class is about the announcement, not the flood cap:
        # start from a fresh budget window (the shape
        # test_build_stamp.py already uses) and restore it after.
        old_minute = runner._LOG_MINUTE
        old_count = runner._LOG_COUNT
        old_dropped = runner._LOG_DROPPED
        runner._LOG_MINUTE = 0.0
        runner._LOG_COUNT = 0
        runner._LOG_DROPPED = 0
        try:
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(out), redirect_stderr(err):
                    rc = runner.main()
        finally:
            runner._LOG_MINUTE = old_minute
            runner._LOG_COUNT = old_count
            runner._LOG_DROPPED = old_dropped
        return rc, out.getvalue(), err.getvalue()

    def _cfg(self, d, block=None):
        cfg = {"base_dir": d,
               "security": {"modes": {"confinement": "off",
                                      "job_user": "off",
                                      "audience": "off"}}}
        if block is not None:
            cfg["disclosure_posture"] = block
        return cfg

    def test_a_retired_assignment_refuses_startup(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _out, err = self._main(d, self._cfg(d, _block(d, "legacy")))
            self.assertEqual(rc, 2)
            self.assertIn("retired", err)

    def test_an_active_assignment_starts_and_announces_its_stamp(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, _err = self._main(
                d, self._cfg(d, _block(d, "bookend")))
            self.assertEqual(rc, 0)
            self.assertIn(STAMP, out)
            self.assertEqual(runner._posture_stamp(), STAMP)

    def test_no_block_starts_exactly_as_before(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _out, _err = self._main(d, self._cfg(d))
            self.assertEqual(rc, 0)
            self.assertIsNone(runner._posture_stamp())


if __name__ == "__main__":
    unittest.main()
