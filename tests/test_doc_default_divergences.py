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


if __name__ == "__main__":
    unittest.main()
