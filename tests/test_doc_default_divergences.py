"""Documented-default divergences found by the VM campaign.

Each test in this file FAILS against the current code on purpose: it
asserts a behavior the documentation promises, that the code does not
deliver when the relevant key is left unset. Do not make a test here
pass by editing the test. It passes only when the bug described in
its docstring is fixed in the code.
"""
import tempfile
import unittest

from runner.senses import load_alerts, store_alert

NOW = "2026-10-23T05:50:22Z"


def _store(base, record):
    store_alert(base, record)
    return record


class TestMissingSeverityDefaultsToInfoOnReadBack(unittest.TestCase):
    """Divergence: a stored alert with no severity is dropped by an
    info severity floor, instead of being read as severity info.

    (a) Doc claim (docs/senses.md, "Alert format", line 293):
        "`severity`: critical/high/medium/low/info. Missing defaults
        to info."
        The same section's profile defaults give `severity_floor` a
        "Default info (keep all)", and the "senses" query op reads
        stored alerts back through load_alerts(severity_floor=...).

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-22 22:51 PDT tick) exercised runner/senses.py with
        the severity key omitted and varied -- omitted key, explicit
        None, the ingest gate, and the score function -- then stored
        a severity-less record with the module's own store_alert and
        read it back with load_alerts(severity_floor="info"), the
        read path the senses query op uses.

    (c) Behavior actually observed: validate_sensor_alert, gate_alert
        and alert_score all honor the documented default (a missing
        severity is accepted, kept at the info floor, and scored 0.5,
        the info score). load_alerts does not: its floor filter uses
        SEVERITY_SCORES.get(rec.get("severity"), 0), so a record with
        no severity scores 0 -- below info's 0.5 -- and
        load_alerts(severity_floor="info") silently drops a record
        that every other path in the same module treats as an info
        alert. Observed on 2026-10-22: of three stored records
        (severity omitted, "info", "low"), the floor="info" read-back
        returned only the latter two.

    (d) Do not make this test pass by editing the test. It passes
        only when the bug described above is fixed in the code.
    """

    def test_omitted_severity_survives_info_floor(self):
        with tempfile.TemporaryDirectory() as base:
            _store(base, {"sensor": "s", "title": "no-severity",
                          "received_at": NOW})
            _store(base, {"sensor": "s", "title": "explicit-info",
                          "severity": "info", "received_at": NOW})
            titles = [r.get("title")
                      for r in load_alerts(base, severity_floor="info")]
            self.assertEqual(titles, ["no-severity", "explicit-info"])

    def test_none_severity_survives_info_floor(self):
        with tempfile.TemporaryDirectory() as base:
            _store(base, {"sensor": "s", "title": "none-severity",
                          "severity": None, "received_at": NOW})
            titles = [r.get("title")
                      for r in load_alerts(base, severity_floor="info")]
            self.assertEqual(titles, ["none-severity"])


class TestUnrecognisedViewDefaultsToFull(unittest.TestCase):
    """Divergence: an unrecognised result view string is treated
    as the narrowest (attested) view instead of the default full.

    (a) Doc claim (PROTOCOL.md, section 9, lines 492-493):
        "`view`: one of `full` (stdout and stderr), `redacted`,
        `summary`, `attested`. Default: `full` (backward
        compatible)."
        The same default is stated for the owner's ceiling in
        docs/configuring-oracle.md ("`max_result_view` -- the
        narrowest view the runner will ever return (`full`,
        `redacted`, `summary`, or `attested`)") and in the
        runner's --help ("--max-result-view MODE ... (default:
        full)"). The code's own handling of a non-string view
        states the same intent (tests/test_extension_poison.py,
        ViewShapeFaultTest: "A non-string view is full.").

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-22 23:01 PDT tick) exercised
        runner.runner.apply_result_policy with the view left
        unset and varied around it -- omitted result_policy,
        view omitted, None, empty string, a non-string (123),
        and unrecognised strings ("sideways", "bogus", and the
        uppercase "FULL") -- with no max_result_view ceiling
        configured, checking the returned view, stdout/stderr,
        and retain flag for each.

    (c) Behavior actually observed: omitted, None, empty, and
        non-string views all read as the documented default:
        view "full", stdout/stderr carried, retain False. An
        unrecognised string does not: apply_result_policy ranks
        it with VIEW_ORDER.get(requested, 3) -- full's rank -- so
        it survives as the effective view verbatim, then falls
        into the final else branch reserved for attested, so the
        result carries view "sideways" (resp. "FULL"/"bogus"),
        stdout and stderr blanked to "", an attestations member,
        and retain True. Observed on 2026-10-22 with stdout
        "hello-out"/stderr "hello-err": every unrecognised
        string above returned blanked output and retain True,
        while every unset form returned the full output.

    (d) Do not make this test pass by editing the test. It passes
        only when the bug described above is fixed in the code.
    """

    def _apply(self, job):
        from runner.runner import apply_result_policy
        exec_result = {"stdout": "hello-out", "stderr": "hello-err",
                       "exit_code": 0, "stdout_truncated": False,
                       "stderr_truncated": False}
        return apply_result_policy({}, job, exec_result, {}, False)

    def test_unrecognised_view_string_defaults_to_full(self):
        result, retain = self._apply(
            {"result_policy": {"view": "sideways"}})
        self.assertEqual(result.get("view"), "full")
        self.assertEqual(result.get("stdout"), "hello-out")
        self.assertEqual(result.get("stderr"), "hello-err")
        self.assertFalse(retain)

    def test_uppercase_view_defaults_to_full(self):
        result, retain = self._apply(
            {"result_policy": {"view": "FULL"}})
        self.assertEqual(result.get("view"), "full")
        self.assertEqual(result.get("stdout"), "hello-out")
        self.assertEqual(result.get("stderr"), "hello-err")
        self.assertFalse(retain)


class TestNullTaskTimeoutDefaultsTo86400(unittest.TestCase):
    """Divergence: a task_timeout present in config as null (or a
    non-numeric string) wedges claimed board tasks forever, instead
    of falling back to the documented 86400-second default.

    (a) Doc claim (docs/configuring-oracle.md, line 41):
        "`task_timeout` -- seconds before a claimed task is
        returned to open. Default 86400."
        The same default is stated in PROTOCOL.md section 13.5
        ("`task_timeout` (config, default 24h)"), in section 13.6
        ("A claim lapses after `task_timeout` (config, default
        24h) with no result, and the task returns to open. A
        crashed worker cannot wedge the board; it can only delay
        a task by one timeout."), and in the runner's --help
        ("--task-timeout ... (default: 86400)").

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-22 23:06 PDT tick) exercised the board reoffer
        path in runner/runner.py with task_timeout left unset
        and varied around it -- key omitted, explicit 86400,
        explicit None (JSON null), a non-numeric string
        ("bogus"), and 0 -- using the exact caller expression
        the board-mail handler uses,
        board.reoffer_expired(cfg.get("task_timeout", 86400)),
        on a task claimed two days earlier (older than the
        86400-second default).

    (c) Behavior actually observed: omitted and explicit 86400
        reoffer the stale claim (count 1, state returns to
        open), and 0 reoffers immediately, as expected. None
        and "bogus" do not: Board._reoffer_expired_unlocked
        compares the claim age with `> task_timeout`, the
        TypeError that raises is swallowed by the loop's blanket
        `except Exception: pass`, and the reoffer count stays 0
        with the task still claimed -- on every poll, forever.
        Sibling default readers in the same file (query_budget,
        _retention_days, _local_wake_cooldown, the max_job_age
        readers) all treat a null or unparseable value as the
        documented default; this one silently wedges the board,
        the exact outcome section 13.6 promises cannot happen.

    (d) Do not make this test pass by editing the test. It passes
        only when the bug described above is fixed in the code.
    """

    def _stale_board(self, base):
        import os
        from datetime import datetime, timedelta, timezone

        from runner.runner import Board
        board = Board(os.path.join(base, "board.json"))
        board.submit({"task_id": "t1"})
        old = (datetime.now(timezone.utc)
               - timedelta(days=2)).isoformat()
        board.tasks["t1"]["state"] = "claimed"
        board.tasks["t1"]["claimed_at"] = old
        board.tasks["t1"]["claimed_by"] = "w1"
        return board

    def _reoffer_via_config(self, cfg):
        # The exact caller expression in handle_board_mail
        # (runner/runner.py): the .get default fires only when
        # the key is absent, not when it is null or unparseable.
        with tempfile.TemporaryDirectory() as base:
            board = self._stale_board(base)
            count = board.reoffer_expired(cfg.get("task_timeout", 86400))
            return count, board.tasks["t1"]["state"]

    def test_null_task_timeout_defaults_to_86400(self):
        count, state = self._reoffer_via_config({"task_timeout": None})
        self.assertEqual(count, 1)
        self.assertEqual(state, "open")

    def test_bogus_task_timeout_defaults_to_86400(self):
        count, state = self._reoffer_via_config({"task_timeout": "bogus"})
        self.assertEqual(count, 1)
        self.assertEqual(state, "open")


if __name__ == "__main__":
    unittest.main()
