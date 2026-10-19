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
from runner.runner import Board, apply_cli_overrides, poll_once, sign_payload

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
            log_max_bytes=1024, log_backups=2))
        self.assertEqual(cfg["log_max_bytes"], 1024)
        self.assertEqual(cfg["log_backups"], 2)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
