"""Documented-default divergences found by the VM campaign.

Each test in this file FAILS against the current code on purpose: it
asserts a behavior the documentation promises, that the code does not
deliver when the relevant key is left unset. Do not make a test here
pass by editing the test. It passes only when the bug described in
its docstring is fixed in the code.
"""
import json
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


class _RecordingOpener:
    """A fake inference opener: records the timeout it was
    called with and returns one canned chat completion."""

    def __init__(self):
        self.timeouts = []

    def __call__(self, req, timeout=None):
        self.timeouts.append(timeout)

        class _Resp:
            def read(self, n=-1):
                return (b'{"choices":[{"message":'
                        b'{"content":"ok answer"}}]}')

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _Resp()


class TestBogusInferenceTimeoutDefaultsTo180(unittest.TestCase):
    """Divergence: an unparseable or out-of-range inference
    timeout_sec falls back to 60 seconds in the ask paths,
    instead of the documented 180-second default.

    (a) Doc claim (PROTOCOL.md, section 10.1, line 678):
        "`max_answer_chars` (default 2000), `timeout_sec`
        (default 180)."
        The same default is stated in
        docs/configuring-oracle.md (line 43): "`timeout_sec`
        (default 180, per-question model timeout; a cold model
        on a laptop often needs more than 60, and the default
        model thinks before answering, so long questions can
        need the full budget)" -- 60 is named there as the
        value the 180 default exists to avoid.

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-22 23:21 PDT tick) exercised
        runner.runner.ask_model and runner.runner.ask_model_agent
        with the inference timeout left unset and varied around
        it -- key omitted, explicit None, 0, a valid 42, a
        non-numeric string ("hour"), a negative value (-5),
        and float("inf") -- using a recording opener to observe
        the timeout each call actually used, the same direct-call
        surface the repo's own ask_model tests use.

    (c) Behavior actually observed: omitted, None, and 0 all
        use the documented default (the opener receives
        timeout 180), and 42 is honored. A non-numeric string,
        a negative value, and infinity do not: both ask_model
        (runner/runner.py lines 1859-1863) and ask_model_agent
        (lines 2748-2752) compute
        int(cfg.get("timeout_sec") or 180) but their except /
        below-1 fallback is a hardcoded 60, so the opener
        receives timeout 60 -- one third of the documented
        default, and exactly the too-short budget the
        configuring-oracle rationale warns about. The sibling
        readers disagree with that fallback: inference_config
        uses 180 as its only fallback value (and disables
        inference rather than inventing another budget), and
        the max_answer_chars fallback in the very same
        functions uses the documented default 2000 in both
        its try and its except path.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    _BASE = {"endpoint": "http://127.0.0.1:11434/v1",
             "model": "m"}

    def _ask_timeout(self, extra):
        from runner.runner import ask_model
        opener = _RecordingOpener()
        cfg = dict(self._BASE)
        cfg.update(extra)
        ask_model(cfg, "why?", "some output", 100, opener=opener)
        return opener.timeouts

    def _agent_timeout(self, extra):
        from runner.runner import ask_model_agent
        opener = _RecordingOpener()
        cfg = dict(self._BASE)
        cfg.update(extra)
        ask_model_agent(cfg, "why?", "some output", 100,
                        opener=opener)
        return opener.timeouts

    def test_bogus_ask_timeout_defaults_to_180(self):
        self.assertEqual(
            self._ask_timeout({"timeout_sec": "hour"}), [180])

    def test_negative_ask_timeout_defaults_to_180(self):
        self.assertEqual(
            self._ask_timeout({"timeout_sec": -5}), [180])

    def test_infinite_ask_timeout_defaults_to_180(self):
        self.assertEqual(
            self._ask_timeout({"timeout_sec": float("inf")}),
            [180])

    def test_bogus_agent_timeout_defaults_to_180(self):
        timeouts = self._agent_timeout({"timeout_sec": "hour"})
        self.assertTrue(timeouts)
        self.assertEqual(timeouts[0], 180)

    def test_negative_agent_timeout_defaults_to_180(self):
        timeouts = self._agent_timeout({"timeout_sec": -5})
        self.assertTrue(timeouts)
        self.assertEqual(timeouts[0], 180)


class TestNullDefaultTimeoutSecDefaultsTo300(unittest.TestCase):
    """Divergence: a default_timeout_sec present in config as
    null (or a non-numeric string) rejects every job that omits
    its own timeout_sec, instead of falling back to the
    documented 300-second default.

    (a) Doc claim (PROTOCOL.md, section 3.1, line 136):
        "`timeout_sec`: default 300, maximum 3600."
        The runner's --help states the same default for the
        config key that supplies it ("--timeout SECONDS --
        default per-job timeout in seconds (default: 300)"),
        and docs/configuring-oracle.md (flag-to-key map,
        line 83) maps that flag to the config key:
        "`--timeout SECONDS` | `default_timeout_sec`".

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-22 23:56 PDT tick) exercised
        runner.runner.execute_job with a job that omits
        timeout_sec and varied the config around it -- key
        omitted, explicit 300, explicit None (JSON null), a
        non-numeric string ("bogus"), and a numeric string
        ("42") -- running a trivial python3 script
        (print('hi-probe')) each time, the same direct-call
        surface the repo's own execute_job tests use.

    (c) Behavior actually observed: omitted, explicit 300,
        and "42" all run the job (exit 0, stdout 'hi-probe').
        None and "bogus" do not: execute_job computes
        int(job.get("timeout_sec") or
        cfg.get("default_timeout_sec", 300)) -- the .get
        default fires only when the key is absent -- int(None)
        / int("bogus") raises, and the except path raises
        JobRejected("timeout_sec must be a number"), so a
        single bad config value rejects every timeout-less
        job rather than supplying the documented default.
        Sibling default readers in the same function and file
        (max_output_bytes in execute_job, max_job_age_sec,
        poll_interval_sec, output_retention_days) all treat a
        null or unparseable value as the documented default;
        only this one turns it into a rejection. The same
        expression in check_key_policy's max_timeout_sec path
        has the same shape.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    def _run(self, cfg_extra):
        from runner.runner import execute_job
        with tempfile.TemporaryDirectory() as base:
            cfg = {"base_dir": base}
            cfg.update(cfg_extra)
            job = {"v": 1, "type": "job", "job_id": "docdef-to",
                   "issued_at": "2026-10-23T00:00:00Z",
                   "kind": "exec", "interpreter": ["python3"],
                   "script": "print('hi-probe')"}
            return execute_job(cfg, job, base)

    def test_null_default_timeout_defaults_to_300(self):
        result = self._run({"default_timeout_sec": None})
        self.assertEqual(result.get("exit_code"), 0)
        self.assertIn("hi-probe", result.get("stdout", ""))

    def test_bogus_default_timeout_defaults_to_300(self):
        result = self._run({"default_timeout_sec": "bogus"})
        self.assertEqual(result.get("exit_code"), 0)
        self.assertIn("hi-probe", result.get("stdout", ""))


class TestNullDtlsPortBindDefaults(unittest.TestCase):
    """Divergence: a transport_dtls port present as null (or a
    non-numeric string), or a bind present as null, kills the
    DTLS transport extension instead of falling back to the
    documented defaults (port 20220, bind 0.0.0.0).

    (a) Doc claim (docs/configuring-oracle.md, line 64):
        "`transport_dtls` -- the DTLS session binding ...
        handed to the DTLS extension: `port` (default 20220)
        and `bind` (default `0.0.0.0`)."
        The extension's own module docstring states the same
        (runner/transport_extensions/dtls/__main__.py, lines
        5-9): "port    UDP port to listen on (default 20220)
        bind    local address to bind (default "0.0.0.0" ...)".

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 00:11 PDT tick) exercised
        runner.transport_extensions.dtls DtlsPipe construction
        (the object the extension's main builds at startup)
        with the transport_dtls block left unset and varied
        around it -- port omitted, explicit None (JSON null),
        a non-numeric string ("bogus"), a numeric string
        ("0"), and bind omitted / None / empty string -- the
        same direct-construction surface the repo's own DTLS
        pipe tests use (tests/test_dtls.py, PipeSocketTest).

    (c) Behavior actually observed: port omitted reads as
        the documented default (pipe.port == 20220, listener
        bound), a numeric string is accepted, bind omitted
        reads as "0.0.0.0", and an empty bind binds every
        interface. None of the null/unparseable forms do:
        DtlsPipe.__init__ computes int(cfg.get("port",
        DEFAULT_PORT)) with no guard, so port None raises
        TypeError and "bogus" raises ValueError; bind is
        str(cfg.get("bind", "0.0.0.0")), so bind None becomes
        the literal address "None" and the socket bind raises
        OSError (Errno 99). The extension's main catches
        exactly those exceptions around construction, logs
        "cannot listen", and exits with status 2, so the
        supervisor restarts a permanently dead transport --
        the one listening binding never comes up. Sibling
        readers do fall back: the NATS extension reads its
        url/subject/prefix with `cfg.get(...) or <default>`
        (null lands on the documented default), and the
        core's poll-interval / max-job-age / wake-cooldown
        readers all treat a null or unparseable value as
        the documented default.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    _SECRET = "docdef-dtls-probe-0123456789abcdef0123456789abcdef"

    def _pipe(self, extra):
        import importlib
        import os
        dtls_ext = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        cfg = {"shared_secret": self._SECRET, "port": 0,
               "bind": "127.0.0.1"}
        cfg.update(extra)
        with tempfile.TemporaryDirectory() as tmp:
            pipe = dtls_ext.DtlsPipe(
                cfg, os.path.join(tmp, "channel"))
        self.addCleanup(pipe.sock.close)
        return pipe

    def test_null_port_defaults_to_20220(self):
        pipe = self._pipe({"port": None})
        self.assertEqual(pipe.port, 20220)

    def test_bogus_port_defaults_to_20220(self):
        pipe = self._pipe({"port": "bogus"})
        self.assertEqual(pipe.port, 20220)

    def test_null_bind_defaults_to_all_interfaces(self):
        pipe = self._pipe({"bind": None})
        self.assertEqual(pipe.bind, "0.0.0.0")


class TestNullDtlsGreetingDefaultsToFamily(unittest.TestCase):
    """Divergence: a dtls_greeting present as null (or an
    unrecognised string) kills the DTLS transport extension at
    startup -- or passes the bogus tier through into the
    greeting verbatim -- instead of falling back to the
    documented default tier, family.

    (a) Doc claim (docs/configuring-oracle.md, line 65):
        "`dtls_greeting` -- the DTLS session greeting's
        disclosure tier: `none`, `family` (default: OS family
        only), `standard` (plus OS release and Python version),
        or `full` (plus a bounded PATH-tools summary)."
        The extension's own module docstring states the same
        (runner/transport_extensions/dtls/__main__.py, lines
        10-12): the greeting disclosure tier is
        "none / family (default) / standard / full".

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 01:41 PDT tick) exercised
        runner.transport_extensions.dtls DtlsPipe construction
        and build_greeting with dtls_greeting left unset and
        varied around it -- key omitted, explicit "family",
        explicit None (JSON null), a non-tier string
        ("bogus"), the uppercase "FAMILY", and the empty
        string -- the same direct-construction surface the
        DTLS port/bind divergence tests above use, plus the
        extension main's startup validation of the tier.

    (c) Behavior actually observed: omitted and explicit
        "family" read as the documented default: pipe.tier is
        "family" and the greeting carries disclosure "family"
        with the OS family only. The unset-in-value forms do
        not: DtlsPipe stores cfg.get("dtls_greeting",
        "family") verbatim, so None stays None (the greeting
        goes out with disclosure null), and "bogus" / "FAMILY"
        / "" pass through as the tier and into the greeting's
        disclosure field unchanged. Worse, the extension's
        main validates the tier before constructing the pipe
        -- `if not isinstance(tier, str) or tier not in
        GREETING_TIERS: ... return 2` -- so a config carrying
        dtls_greeting as null or any unrecognised string makes
        the one listening transport refuse to start at all,
        and the supervisor restarts a permanently dead
        extension, instead of the tier reading as the
        documented family default. Sibling readers treat an
        unset-in-value key as the default: the NATS extension
        reads url/subject/prefix with `cfg.get(...) or
        <default>`, and the senses ingest gate reads an
        unrecognised severity_floor as info.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    _SECRET = "docdef-greeting-fixture-secret-0123456789abcdef"

    def _pipe(self, extra):
        import importlib
        import os
        dtls_ext = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        cfg = {"shared_secret": self._SECRET, "port": 0,
               "bind": "127.0.0.1"}
        cfg.update(extra)
        with tempfile.TemporaryDirectory() as tmp:
            pipe = dtls_ext.DtlsPipe(
                cfg, os.path.join(tmp, "channel"))
        self.addCleanup(pipe.sock.close)
        return dtls_ext, pipe

    def test_null_greeting_tier_defaults_to_family(self):
        dtls_ext, pipe = self._pipe({"dtls_greeting": None})
        self.assertEqual(pipe.tier, "family")
        greeting = json.loads(dtls_ext.build_greeting(pipe.tier))
        self.assertEqual(greeting.get("disclosure"), "family")

    def test_bogus_greeting_tier_defaults_to_family(self):
        dtls_ext, pipe = self._pipe({"dtls_greeting": "bogus"})
        self.assertEqual(pipe.tier, "family")
        greeting = json.loads(dtls_ext.build_greeting(pipe.tier))
        self.assertEqual(greeting.get("disclosure"), "family")


class TestZeroOrNegativeMaxJobAgeDefaultsTo3600(unittest.TestCase):
    """Divergence: a max_job_age_sec present in config as 0 (or
    a negative value) rejects every job as stale, instead of
    falling back to the documented 3600-second default.

    (a) Doc claim (PROTOCOL.md, section 5, lines 323-325):
        "`issued_at` parses, carries a timezone, and is within
        `max_job_age_sec` (default 3600) of the runner's clock
        (replay / stale protection)."
        The runner's --help states the same default for the
        flag that supplies the key ("--max-job-age ... reject
        jobs older than this many seconds (default: 3600)").

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 02:36 PDT tick) exercised
        runner.runner._issued_at_ok -- the freshness check the
        verification list names -- with max_job_age_sec left
        unset and varied around it -- key omitted, explicit
        3600, explicit None (JSON null), a non-numeric string
        ("bogus"), a numeric string ("42"), 0, and -5 -- each
        against a just-issued timestamp and a years-old one.

    (c) Behavior actually observed: omitted, explicit 3600,
        None, "bogus", and "42" all read as the documented
        default (fresh accepted, stale rejected). 0 and -5 do
        not: _issued_at_ok computes
        int(cfg.get("max_job_age_sec", 3600)) with a fallback
        only for unparseable values and no range check, so a
        0 or negative window is used literally and a job
        issued seconds ago is rejected as "issued_at outside
        allowed window" -- every real job is, since its age is
        always greater than the window. The same unguarded
        expression is duplicated at the local-signals and
        mail handlers' freshness checks. Sibling readers in
        the same file treat a sub-1 value as the documented
        default: the poll-interval reader (below 1 reads as
        20), _cfg_size (below 1 reads as the default), the
        execute_job output cap (below 1 reads as 100000),
        and the agent wall clock (below 1 reads as its
        default).

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    def _fresh(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

    def test_zero_max_job_age_defaults_to_3600(self):
        from runner.runner import _issued_at_ok
        ok, reason = _issued_at_ok(
            self._fresh(), {"max_job_age_sec": 0})
        self.assertTrue(ok, reason)

    def test_negative_max_job_age_defaults_to_3600(self):
        from runner.runner import _issued_at_ok
        ok, reason = _issued_at_ok(
            self._fresh(), {"max_job_age_sec": -5})
        self.assertTrue(ok, reason)


class TestZeroOrNegativePlanBudgetDefaults(unittest.TestCase):
    """Divergence: a max_plan_steps or max_plan_timeout_sec
    present in config as 0 (or a negative value) rejects every
    multi-step plan, instead of falling back to the documented
    defaults (8 steps, 600 seconds).

    (a) Doc claim (docs/configuring-oracle.md, line 68):
        "`max_plan_steps` / `max_plan_timeout_sec` -- caps the
        detection layer (`runner/detection.py`) applies to a
        multi-step plan: at most this many steps (default 8)
        and this much total timeout in seconds (default 600)."
        The function's own docstring states the same
        (runner/detection.py, lines 104-105): "cfg may contain
        max_plan_steps (default 8) and max_plan_timeout_sec
        (default 600)."
        Neither document gives 0 a special meaning for these
        keys (unlike max_job_bytes / output_retention_days /
        max_queries_per_hour, where 0's meaning is stated).

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 03:36 PDT tick) exercised
        runner.detection.check_plan_budget with the caps left
        unset and varied around them -- keys omitted, explicit
        8 / 600, explicit None (JSON null), a non-numeric
        string ("bogus"), 0, and -5 -- each against a one-step
        plan with a 10-second step timeout.

    (c) Behavior actually observed: omitted, explicit
        defaults, None, and "bogus" all allow the plan.
        0 and -5 do not: check_plan_budget guards only the
        unparseable case (its except falls back to 8 / 600)
        and uses the parsed value literally with no range
        check, so max_plan_steps 0 / -5 reject the plan as
        "plan has 1 steps (max 0)" and max_plan_timeout_sec
        0 / -5 reject it as "plan timeout 10s exceeds 0s" --
        every plan is over a zero or negative budget, so the
        detection layer's plan path is dead. Sibling readers
        treat a below-1 value as the documented default:
        _review_scan_bytes (review.py), _cfg_size (log
        bounds), the execute_job output cap, the poll delay,
        promote_after (learning.py), and remediation's
        _pos_int all read below-1 as their default.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    _PLAN = [{"timeout_sec": 10}]

    def test_zero_max_plan_steps_defaults_to_8(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            self._PLAN, {"max_plan_steps": 0})
        self.assertTrue(ok, reason)

    def test_negative_max_plan_steps_defaults_to_8(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            self._PLAN, {"max_plan_steps": -5})
        self.assertTrue(ok, reason)

    def test_zero_max_plan_timeout_defaults_to_600(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            self._PLAN, {"max_plan_timeout_sec": 0})
        self.assertTrue(ok, reason)

    def test_negative_max_plan_timeout_defaults_to_600(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            self._PLAN, {"max_plan_timeout_sec": -5})
        self.assertTrue(ok, reason)


class TestNullDefaultTimeoutSecPassesKeyPolicy(unittest.TestCase):
    """Divergence: a default_timeout_sec present in config as
    null (or a non-numeric string) makes the key-policy gate
    reject every timeout-less job from a capped key, instead
    of falling back to the documented 300-second default.

    (a) Doc claim (PROTOCOL.md, section 3.1, line 136):
        "`timeout_sec`: default 300, maximum 3600."
        The runner's --help states the same default for the
        config key that supplies it ("--timeout SECONDS --
        default per-job timeout in seconds (default: 300)"),
        and docs/configuring-oracle.md (flag-to-key map,
        line 83) maps that flag to the config key:
        "`--timeout SECONDS` | `default_timeout_sec`".

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 05:31 PDT tick) exercised
        runner.runner.check_key_policy with a job that omits
        timeout_sec, a key policy carrying max_timeout_sec,
        and the config varied around the unset key -- key
        omitted, explicit 300, explicit None (JSON null), a
        non-numeric string ("bogus"), a numeric string
        ("42"), and float("inf") -- the same direct-call
        surface the repo's own key-policy tests use. The
        execute_job site of this same divergence is recorded
        in TestNullDefaultTimeoutSecDefaultsTo300 above,
        whose docstring already noted this second site had
        the same shape; this class is that site's own test.

    (c) Behavior actually observed: omitted, explicit 300,
        and "42" all pass the gate under a 600-second cap
        (check returns None), and with the cap lowered to
        200 the omitted form is refused with "timeout 300s
        exceeds this key's limit of 200s" -- proof the
        effective timeout reads as the documented 300 when
        the key is absent. None, "bogus", and infinity do
        not: check_key_policy computes int(job.get(
        "timeout_sec") or cfg.get("default_timeout_sec",
        300)) -- the .get default fires only when the key
        is absent -- int(None) / int("bogus") raises, and
        the except path returns "timeout_sec must be a
        number", so one bad config value refuses every
        timeout-less job from any key whose policy caps
        the timeout, before execution is ever reached.
        Sibling default readers in the same file
        (max_output_bytes in execute_job, max_job_age_sec,
        poll_interval_sec, output_retention_days) all treat
        a null or unparseable value as the documented
        default; only this gate turns it into a refusal.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    _POLICIES = {"k1": {"max_timeout_sec": 600}}
    _JOB = {"kind": "exec", "script": "print(1)"}

    def _check(self, cfg_extra):
        from runner.runner import check_key_policy
        cfg = {}
        cfg.update(cfg_extra)
        return check_key_policy(self._POLICIES, "k1", cfg, self._JOB)

    def test_null_default_timeout_passes_key_policy(self):
        self.assertIsNone(
            self._check({"default_timeout_sec": None}))

    def test_bogus_default_timeout_passes_key_policy(self):
        self.assertIsNone(
            self._check({"default_timeout_sec": "bogus"}))


class TestInfinitePromoteAfterDefaultsTo2(unittest.TestCase):
    """Divergence: an oracle_learning_promote_after present in
    config as infinity (or negative infinity) raises
    OverflowError out of the learning reader, instead of
    falling back to the documented default of 2.

    (a) Doc claim (docs/configuring-oracle.md, line 53):
        "`oracle_learning_promote_after` -- how many verified
        corroborating outcomes a model candidate needs before
        it is treated as corroborated and may select among
        the existing mechanical repairs ... Default `2`."
        The same default is stated in the learning module's
        own docstring (runner/learning.py, line 29:
        "(oracle_learning_promote_after, default 2, with no
        intervening contradiction)") and in
        docs/design/oracle-opinion-design.md (line 188).

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 06:21 PDT tick) exercised
        runner.learning.promote_after with the key left unset
        and varied around it -- key omitted, explicit None,
        a non-numeric string ("bogus"), 0, -5, NaN, a valid
        3, a numeric string ("4"), float("inf"), and
        float("-inf"). The infinite forms are reachable from
        a real config file: the runner's load_config uses a
        plain json.load, which parses the JSON literals
        Infinity / -Infinity into float infinity, so
        config.json can carry exactly this value.

    (c) Behavior actually observed: omitted, None, "bogus",
        0, -5, and NaN all read as the documented default
        (2) -- 0 and -5 through the reader's own below-1
        fallback, the rest through its unparseable fallback
        -- and 3 / "4" are honored. The infinite forms do
        not: promote_after (runner/learning.py lines
        137-139) guards int(cfg.get(...)) with
        `except (TypeError, ValueError)` only, and
        int(float("inf")) raises OverflowError, which
        escapes the reader entirely. Downstream, load_state
        and relevant_lessons call promote_after during every
        job's opinion evaluation; the runner's
        _learning_context catches the exception only as a
        generic failure, logs "oracle learning: context
        load failed", and returns an empty learning context
        -- so one config value silently disables candidate
        promotion for every job instead of reading as the
        default 2. Sibling numeric readers all include
        OverflowError in their fallback guard: query_budget
        and the ask-path timeouts (runner.py),
        _review_scan_bytes (review.py), and remediation's
        _pos_int; the wake-cooldown reader rejects
        infinities by an explicit range check. This reader
        is the outlier.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_infinite_promote_after_defaults_to_2(self):
        from runner.learning import promote_after
        self.assertEqual(
            promote_after(
                {"oracle_learning_promote_after": float("inf")}),
            2)

    def test_negative_infinite_promote_after_defaults_to_2(self):
        from runner.learning import promote_after
        self.assertEqual(
            promote_after(
                {"oracle_learning_promote_after": float("-inf")}),
            2)


if __name__ == "__main__":
    unittest.main()
