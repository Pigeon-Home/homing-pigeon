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


class TestHugeSensorWeightDefaultsToOne(unittest.TestCase):
    """Divergence: a sensor weight that is a huge integer (a
    JSON number with hundreds of digits) raises OverflowError
    out of alert_score, instead of falling back to the
    documented default weight of 1.0.

    (a) Doc claim (docs/senses.md, line 254):
        "`weight` (number >= 0, default 1.0): the Oracle's
        weighting for this source."
        The scoring path states the same arithmetic
        (docs/senses.md, line 325): alerts are ranked by
        "score = weight x severity", and alert_score's own
        fallback for an unparseable weight is the default
        1.0 (runner/senses.py, lines 407-410).

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 06:41 PDT tick) exercised
        runner.senses.alert_score with the weight left unset
        and varied around it -- key omitted via the callers'
        rec.get("weight", 1.0), explicit None, a non-numeric
        string ("bogus"), a numeric string ("2"), 0, -1,
        float("inf"), NaN, and huge integers (10**400 and
        10**1000). The huge forms are reachable from real
        data: a stored sensor alert is sensor-supplied JSON,
        Python's json parses a several-hundred-digit number
        into an arbitrary-precision int, and the DRI fused
        score path passes a stored record's own weight
        straight in (runner/dri.py: rec.get("weight", 1.0)).

    (c) Behavior actually observed: omitted, None, and
        "bogus" all read as the documented default (an info
        alert scores 0.5, i.e. 1.0 x 0.5), "2" is honored
        (1.0), and 0 / -1 / inf / NaN pass through the float
        conversion. A huge int does not: float(10**400)
        raises OverflowError, and alert_score guards its
        conversion with `except (TypeError, ValueError)`
        only, so the error escapes the scorer entirely.
        Downstream it escapes further: the DRI fused-score
        loop and its top-alert sorter catch only
        (TypeError, ValueError) around alert_score, so one
        stored alert carrying such a weight aborts the
        whole trigger evaluation instead of scoring at the
        default weight. Sibling readers include
        OverflowError in their fallback guard: parse_sensors
        reads this very weight key with
        `except (TypeError, ValueError, OverflowError)`,
        gate_alert's cooldown / cap readers do the same in
        the same module, and promote_after's missing
        OverflowError guard is the sibling divergence
        recorded above. This reader is the outlier.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_huge_int_weight_defaults_to_one(self):
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, 10**400), 0.5)

    def test_huge_int_weight_from_json_defaults_to_one(self):
        from runner.senses import alert_score
        record = json.loads(
            '{"severity": "high", "weight": 1' + "0" * 400 + "}")
        self.assertEqual(
            alert_score(record, record.get("weight", 1.0)), 3.0)


class TestHugeResourcesValueIsConfigError(unittest.TestCase):
    """Divergence: a resources threshold or cooldown that is
    a huge integer (a JSON number with hundreds of digits)
    raises a raw OverflowError out of the config reader,
    instead of the startup config error every other
    malformed resources value gets.

    (a) Doc claim (docs/configuring-oracle.md, line 72):
        "`resources` -- the built-in resource monitor
        (`runner/resources.py`) ... `enabled` (default
        true), `threshold` (default 0.95; the CPU, memory,
        or disk fraction whose crossing files a
        `resource_pressure` security event; must be in
        (0, 1]), `cooldown_sec` (default 900; minimum
        seconds between repeat events for the same
        resource). A malformed block is a startup config
        error."
        The reader's own contract matches: every other
        malformed form -- a non-numeric string, infinity,
        an out-of-range fraction, a negative or non-finite
        cooldown, a non-boolean enabled -- raises
        RuntimeError("config error: resources...."), and
        check_resources treats that RuntimeError as
        monitor-off (returns None).

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 07:01 PDT tick) exercised
        runner.resources.parse_resources with the block
        left unset and varied around it -- block omitted,
        explicit None, keys omitted, a non-numeric string
        ("bogus"), infinity, and huge integers (10**400)
        for each of threshold and cooldown_sec. The huge
        forms are reachable from a real config file: the
        runner's load_config uses a plain json.load, which
        parses a several-hundred-digit JSON number into
        an arbitrary-precision int.

    (c) Behavior actually observed: omitted, None, and
        omitted keys read as the documented defaults
        (threshold 0.95, cooldown 900); "bogus" and
        infinity raise the documented RuntimeError config
        error. A huge int does not: float(10**400) raises
        OverflowError, and parse_resources guards its
        float() conversions with
        `except (TypeError, ValueError)` only
        (runner/resources.py lines 45-46 and 51-52), so
        the error escapes the reader raw. It escapes the
        next layer too: check_resources catches only
        (RuntimeError, AttributeError, TypeError) around
        parse_resources, so the OverflowError propagates
        to the poll loop, which logs "resource monitor
        failed: int too large to convert to float" on
        every poll -- the monitor never runs and the
        failure repeats forever instead of being handled
        once as the config error the docs promise.
        Sibling float readers include OverflowError in
        their fallback guard: parse_sensors and
        gate_alert (runner/senses.py) and _cfg_size
        (runner/runner.py) all catch it; this reader is
        the outlier.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def test_huge_threshold_is_config_error(self):
        from runner.resources import parse_resources
        with self.assertRaises(RuntimeError):
            parse_resources({"resources": {"threshold": 10**400}})

    def test_huge_cooldown_is_config_error(self):
        from runner.resources import parse_resources
        with self.assertRaises(RuntimeError):
            parse_resources(
                {"resources": {"cooldown_sec": 10**400}})

    def test_huge_threshold_check_resources_returns_none(self):
        from runner.resources import check_resources
        with tempfile.TemporaryDirectory() as base:
            self.assertIsNone(check_resources(
                {"resources": {"threshold": 10**400}}, base))


class _BodyRecordingOpener:
    """Fake inference opener: records request-body JSON."""

    def __init__(self):
        self.bodies = []

    def __call__(self, req, timeout=None):
        self.bodies.append(json.loads(req.data.decode("utf-8")))

        class _Resp:
            def read(self, n=-1):
                return (b'{"choices":[{"message":'
                        b'{"content":"ok answer"}}]}')

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _Resp()


class TestAskModelKeepAliveDefaultsTo30mOnOllama(unittest.TestCase):
    """Divergence: ask_model never sends keep_alive, so the
    documented Ollama default (30m on a :11434 endpoint when
    keep_alive is unset) -- and any explicit keep_alive --
    is lost on the plain ask path.

    (a) Doc claim (docs/configuring-oracle.md, line 70):
        "`keep_alive` (passed to the model server so it
        keeps the model loaded between questions; unset by
        default, except that an endpoint on `:11434` gets
        \"30m\" so Ollama does not cold-start every ask)."
        The key is listed as an `inference` sub-key, with
        no restriction to one call path.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 07:11 PDT tick) exercised
        runner.runner.ask_model and runner.runner.ask_model_agent
        with keep_alive left unset and varied around it --
        key omitted on a :11434 endpoint, explicit
        "10m", and a non-Ollama endpoint -- using a
        recording opener to observe the exact request-body
        JSON each call sent, the same direct-call surface
        the repo's own ask tests use.

    (c) Behavior actually observed: ask_model_agent, which
        builds its payload through _inference_chat
        (runner/runner.py lines 2476-2481), sends
        keep_alive "30m" when the key is unset and the
        endpoint contains :11434, and sends an explicit
        value verbatim. ask_model (runner/runner.py,
        def at line 1782) does neither: it builds its
        payload as only {model, messages} and contains no
        keep_alive handling at all, so on 2026-10-23 a
        :11434 ask with the key unset sent a body with no
        keep_alive member, and an explicit "10m" was also
        dropped -- Ollama cold-starts the next ask, the
        exact outcome the documented default exists to
        avoid, on the main query-answer path.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    _BASE = {"endpoint": "http://127.0.0.1:11434/v1",
             "model": "m"}

    def _ask_body(self, extra):
        from runner.runner import ask_model
        opener = _BodyRecordingOpener()
        cfg = dict(self._BASE)
        cfg.update(extra)
        ask_model(cfg, "why?", "some output", 100, opener=opener)
        self.assertEqual(len(opener.bodies), 1)
        return opener.bodies[0]

    def test_unset_keep_alive_defaults_to_30m_on_ollama(self):
        body = self._ask_body({})
        self.assertEqual(body.get("keep_alive"), "30m")

    def test_explicit_keep_alive_is_sent(self):
        body = self._ask_body({"keep_alive": "10m"})
        self.assertEqual(body.get("keep_alive"), "10m")


class TestBooleanReviewScanBytesDefaultsTo65536(unittest.TestCase):
    """Divergence: review_scan_bytes set to the boolean true
    makes the job reviewer scan a single byte of the script
    instead of the documented 65536-byte default.

    (a) Doc claim (docs/configuring-oracle.md, line 67):
        "`review_scan_bytes` -- how many bytes of the script
        the job reviewer (`docs/job-review.md`) scans for
        file-name references. Default 65536."

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 07:16 PDT tick) exercised
        runner.review._review_scan_bytes with the key left
        unset and varied around it -- key omitted, explicit
        None, False, a non-numeric string ("bogus"), 0, a
        negative value (-5), float("inf"), a valid value
        (123), and the boolean True -- checking the scan
        bound each call returned.

    (c) Behavior actually observed: omitted, None, False,
        "bogus", 0, -5, and infinity all return the
        documented default 65536, and 123 is honored. True
        does not: _review_scan_bytes (runner/review.py)
        computes int(cfg.get("review_scan_bytes", 65536))
        with no boolean guard, int(True) is 1, and 1 passes
        its `n > 0` check, so the reviewer scans exactly
        one byte of the script and its file-name-reference
        check is effectively switched off by a boolean typo.
        Sibling size/count readers in the same codebase
        exclude booleans explicitly -- runner.runner._cfg_size
        ("Booleans are not sizes") and
        runner.remediation._pos_int both return the default
        for a boolean -- only this reader lets one through
        as the number 1. Observed on 2026-10-23:
        _review_scan_bytes({"review_scan_bytes": True})
        returned 1.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    def test_true_review_scan_bytes_defaults_to_65536(self):
        from runner.review import _review_scan_bytes
        self.assertEqual(
            _review_scan_bytes({"review_scan_bytes": True}), 65536)


class TestBooleanRetentionDaysDefaultsTo7(unittest.TestCase):
    """Divergence: output_retention_days set to a boolean reads
    as 1 day (true) or as indefinite retention (false) instead
    of the documented 7-day default.

    (a) Doc claim (docs/configuring-oracle.md, line 33):
        "`output_retention_days` -- how long retained outputs
        are kept for later queries. Default 7. Zero (or
        negative) keeps them indefinitely: nothing is pruned
        and no retained output is reported expired."
        The reader's own docstring (runner.runner
        _retention_days) states the fallback contract the
        claim implies: "Absent, None, or unparseable values
        fall back to 7."

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 07:26 PDT tick) exercised
        runner.runner._retention_days -- the single reader
        every retention consumer takes the window from --
        with the key left unset and varied around it --
        omitted, explicit None, a non-numeric string
        ("bogus"), float("inf"), 0, -3, 30, "30", 2.5, and
        the booleans True and False -- checking the window
        each call returned.

    (c) Behavior actually observed: omitted, None, "bogus",
        and infinity all return the documented default 7;
        0 and -3 return as-is (indefinite, as documented);
        30, "30", and 2.5 return 30, 30, and 2. The booleans
        do not fall back: _retention_days computes int(raw)
        with no boolean guard, so True returns 1 -- retained
        outputs older than a single day are pruned and
        reported expired, a week early -- and False returns
        0, which the doc reserves for an explicit zero:
        indefinite retention and unbounded growth of the
        retained-output store from a boolean typo. Sibling
        readers exclude booleans explicitly --
        runner.runner._cfg_size ("Booleans are not sizes"),
        runner.remediation._pos_int, and the inference
        config validator's `is True` refusal -- only this
        reader lets one through as a number. Observed on
        2026-10-23: _retention_days({"output_retention_days":
        True}) returned 1 and _retention_days(
        {"output_retention_days": False}) returned 0.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_retention_days_defaults_to_7(self):
        from runner.runner import _retention_days
        self.assertEqual(
            _retention_days({"output_retention_days": True}), 7)

    def test_false_retention_days_defaults_to_7(self):
        from runner.runner import _retention_days
        self.assertEqual(
            _retention_days({"output_retention_days": False}), 7)


class TestBooleanV2AnswerDeadlineDefaultsTo0(unittest.TestCase):
    """Divergence: v2_answer_deadline_sec set to boolean true
    reads as a 1-second wait instead of the documented
    default of 0 (one look, no wait).

    (a) Doc claim (docs/configuring-oracle.md, line 45):
        "`v2_answer_deadline_sec` is how long to look
        (0 to 30, default 0 -- one look, no wait)."

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 08:01 PDT tick) exercised
        runner.protocol_v2.deadline_of -- the reader for
        this config key -- with the key left unset and
        varied around it -- omitted, explicit None, a
        non-numeric string ("bogus"), float("inf"),
        float("nan"), 0, -5, 5, "5", and the boolean True
        -- checking the deadline each call returned.

    (c) Behavior actually observed: omitted, None,
        "bogus", infinity, and NaN all return the
        documented default 0; negative values return 0
        and values above 30 clamp to 30, as documented.
        True does not fall back: deadline_of computes
        int(raw) with no boolean guard, so True returns
        1 -- a one-second wait the operator never asked
        for, instead of the documented one-look-no-wait
        default. The same module excludes booleans for
        this very concept elsewhere: the wait loop
        (runner/protocol_v2.py line 482) reads a deadline
        with `not isinstance(deadline, int) or
        isinstance(deadline, bool)` and falls back to 0,
        and validate (line 263) rejects a boolean
        deadline outright; sibling config readers
        (runner.runner._cfg_size, runner.remediation
        ._pos_int) likewise exclude booleans. Only this
        reader lets one through as a number. Observed on
        2026-10-23: deadline_of({"v2_answer_deadline_sec":
        True}) returned 1. (False returns 0, which
        coincides with the default, so only True is
        asserted here.)

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_v2_answer_deadline_defaults_to_0(self):
        from runner.protocol_v2 import deadline_of
        self.assertEqual(
            deadline_of({"v2_answer_deadline_sec": True}), 0)


class TestBooleanQueryBudgetDefaultsTo8(unittest.TestCase):
    """Divergence: a query_budget (job) or max_query_budget
    (config) set to a boolean reads as 1 (true) or 0 (false)
    instead of the documented default of 8.

    (a) Doc claim (PROTOCOL.md, lines 499-501):
        "`query_budget`: maximum queries answerable for this
        job (default 8). The runner owner's config caps it
        with `max_query_budget` (default 8); the effective
        budget is the smaller of the job's value and the
        cap"

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 08:06 PDT tick) exercised
        runner.runner.query_budget -- the reader that
        computes the effective budget from the job's
        result_policy and the config cap -- with both keys
        left unset and varied around them -- omitted,
        explicit None, a non-numeric string ("bogus"),
        float("inf"), 0, 3, 8, "5", and the booleans True
        and False on each side independently -- checking
        the effective budget each call returned.

    (c) Behavior actually observed: omitted, None,
        "bogus", and infinity on either side all fall back
        to the documented default 8 (effective 8, or the
        other side's smaller value); explicit 0 returns 0
        and 3 returns 3, as the min() contract implies.
        The booleans do not fall back: query_budget
        computes int(raw) with no boolean guard on either
        reader, so True returns 1 -- a job or cap that
        silently allows only a single query -- and False
        returns 0 -- a job that can answer no queries at
        all -- instead of the documented default 8.
        Sibling readers exclude booleans explicitly --
        runner.runner._cfg_size ("Booleans are not
        sizes"), runner.runner._query_limit (True is -1,
        never 1), runner.remediation._pos_int, and the
        inference config validator's `is True` refusal --
        only this reader lets one through as a number on
        both of its inputs. Observed on 2026-10-23:
        query_budget({}, {"result_policy":
        {"query_budget": True}}) returned 1,
        query_budget({}, {"result_policy":
        {"query_budget": False}}) returned 0,
        query_budget({"max_query_budget": True}, {})
        returned 1, and query_budget(
        {"max_query_budget": False}, {}) returned 0.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_job_query_budget_defaults_to_8(self):
        from runner.runner import query_budget
        self.assertEqual(
            query_budget({}, {"result_policy": {"query_budget": True}}), 8)

    def test_false_job_query_budget_defaults_to_8(self):
        from runner.runner import query_budget
        self.assertEqual(
            query_budget({}, {"result_policy": {"query_budget": False}}), 8)

    def test_true_max_query_budget_defaults_to_8(self):
        from runner.runner import query_budget
        self.assertEqual(
            query_budget({"max_query_budget": True}, {}), 8)

    def test_false_max_query_budget_defaults_to_8(self):
        from runner.runner import query_budget
        self.assertEqual(
            query_budget({"max_query_budget": False}, {}), 8)



class TestBooleanWakeCooldownDefaultsTo900(unittest.TestCase):
    """Divergence: local_wake_cooldown_sec set to a boolean
    reads as 1 second (true) or 0 seconds (false) instead
    of the documented 900-second default.

    (a) Doc claim (docs/extensions.md, line 276, config
        table): "`local_wake_cooldown_sec` | `900` |
        Minimum seconds between Oracle briefings for the
        same sensor + signal."
        The reader's own docstring states the same
        (runner/runner.py, _local_wake_cooldown):
        "Seconds between wakes for one (sensor, signal).
        Default 900."
        No document gives a boolean a special meaning for
        this key (unlike the neighbouring local_signal_port,
        where the same table states "`0` or `false` turns
        the listener off").

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 08:11 PDT tick) exercised
        runner.runner._local_wake_cooldown -- the single
        reader the local-signals wake gate takes the
        cooldown from -- with the key left unset and
        varied around it -- omitted, explicit None, a
        non-numeric string ("bogus"), float("inf"),
        float("nan"), 0, -5, 42, "42", and the booleans
        True and False -- checking the cooldown each
        call returned.

    (c) Behavior actually observed: omitted, None,
        "bogus", infinity, NaN, and -5 all return the
        documented default 900.0; 42 and "42" are honored.
        The booleans do not fall back: _local_wake_cooldown
        computes float(raw) with no boolean guard, so
        True returns 1.0 -- briefings throttled to one
        second instead of fifteen minutes -- and False
        returns 0.0 -- no cooldown at all, a briefing on
        every signal -- instead of the documented 900.
        The neighbouring reader in the same section
        handles booleans deliberately:
        _local_signal_port returns the documented default
        for True and the documented off value for False;
        sibling config readers likewise exclude booleans
        explicitly -- runner.runner._cfg_size ("Booleans
        are not sizes"), runner.remediation._pos_int, and
        runner.runner._retention_days' sibling readers
        recorded above -- only this reader lets one
        through as a number. Observed on 2026-10-23:
        _local_wake_cooldown({"local_wake_cooldown_sec":
        True}) returned 1.0 and _local_wake_cooldown(
        {"local_wake_cooldown_sec": False}) returned 0.0.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_wake_cooldown_defaults_to_900(self):
        from runner.runner import _local_wake_cooldown
        self.assertEqual(
            _local_wake_cooldown(
                {"local_wake_cooldown_sec": True}), 900.0)

    def test_false_wake_cooldown_defaults_to_900(self):
        from runner.runner import _local_wake_cooldown
        self.assertEqual(
            _local_wake_cooldown(
                {"local_wake_cooldown_sec": False}), 900.0)


class TestBooleanMaxOutputBytesDefaultsTo100000(unittest.TestCase):
    """Divergence: max_output_bytes set to the boolean true
    truncates every job's output to a single byte instead
    of the documented 100000-byte default.

    (a) Doc claim (PROTOCOL.md, section 3, lines 183-184):
        "`stdout`/`stderr` are truncated at a configurable
        byte limit (default 100_000); the `*_truncated`
        flags say so."
        The runner's --help states the same default for the
        flag that supplies the key ("--max-output-bytes
        BYTES -- truncate stdout/stderr beyond this many
        bytes (default: 100000)"), and
        docs/configuring-oracle.md (flag-to-key map,
        line 84) maps that flag to the config key:
        "`--max-output-bytes BYTES` | `max_output_bytes`".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 08:16 PDT tick) exercised
        runner.runner.execute_job -- the single reader of
        this key -- with the key left unset and varied
        around it -- key omitted, explicit 100000, explicit
        None (JSON null), a non-numeric string ("bogus"),
        0, -5, float("inf"), a valid small cap (5), and the
        booleans True and False -- running a trivial
        python3 script (print('hello-probe-output')) each
        time, the same direct-call surface the repo's own
        execute_job tests and this file's timeout tests
        use.

    (c) Behavior actually observed: omitted, explicit
        100000, None, "bogus", 0, -5, and infinity all
        return the full output untruncated (the reader's
        unparseable fallback and its below-1 fallback both
        supply the documented default), a valid cap of 5
        truncates to 5 bytes with the flag set, and False
        reads as 0 and so also lands on the default. True
        does not: execute_job computes
        int(cfg.get("max_output_bytes", 100000)) with no
        boolean guard, int(True) is 1, and 1 passes its
        `max_out < 1` check, so the job's stdout is
        truncated to exactly one byte ('h') with
        stdout_truncated True -- every job's output is
        effectively destroyed by a boolean typo. Sibling
        readers exclude booleans explicitly --
        runner.runner._cfg_size ("Booleans are not
        sizes"), runner.remediation._pos_int, and the
        inference config validator's `is True` refusal --
        only this reader lets one through as a number.
        Observed on 2026-10-23: execute_job with
        {"max_output_bytes": True} returned stdout 'h'
        and stdout_truncated True for a script printing
        'hello-probe-output'.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def _run(self, cfg_extra):
        from runner.runner import execute_job
        with tempfile.TemporaryDirectory() as base:
            cfg = {"base_dir": base}
            cfg.update(cfg_extra)
            job = {"v": 1, "type": "job", "job_id": "docdef-maxout",
                   "issued_at": "2026-10-23T00:00:00Z",
                   "kind": "exec", "interpreter": ["python3"],
                   "script": "print('hello-probe-output')"}
            return execute_job(cfg, job, base)

    def test_true_max_output_bytes_defaults_to_100000(self):
        result = self._run({"max_output_bytes": True})
        self.assertEqual(result.get("exit_code"), 0)
        self.assertIn("hello-probe-output",
                      result.get("stdout", ""))
        self.assertFalse(result.get("stdout_truncated"))


class TestBooleanPlanBudgetDefaults(unittest.TestCase):
    """Divergence: a max_plan_steps or max_plan_timeout_sec
    present in config as a boolean reads as 1 (true) or 0
    (false) instead of the documented defaults (8 steps,
    600 seconds).

    (a) Doc claim (docs/configuring-oracle.md, line 68):
        "`max_plan_steps` / `max_plan_timeout_sec` -- caps
        the detection layer (`runner/detection.py`) applies
        to a multi-step plan: at most this many steps
        (default 8) and this much total timeout in seconds
        (default 600)."
        The function's own docstring states the same
        (runner/detection.py, lines 104-105): "cfg may
        contain max_plan_steps (default 8) and
        max_plan_timeout_sec (default 600)."
        No document gives a boolean a special meaning for
        these keys. The zero/negative forms of this same
        divergence are recorded in
        TestZeroOrNegativePlanBudgetDefaults above; this
        class is the boolean form.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 08:21 PDT tick) exercised
        runner.detection.check_plan_budget with the caps
        left unset and varied around them -- keys omitted,
        explicit 8 / 600, explicit None (JSON null), a
        non-numeric string ("bogus"), 0, -5, and the
        booleans True and False -- each against a two-step
        plan with 10-second step timeouts (well inside
        both documented defaults).

    (c) Behavior actually observed: omitted, explicit
        defaults, None, and "bogus" all allow the plan.
        The booleans do not: check_plan_budget computes
        int(cfg.get(...)) with no boolean guard, so True
        reads as a cap of 1 -- the two-step plan is
        rejected as "plan has 2 steps (max 1)" and the
        10-second plan as "plan timeout 10s exceeds 1s"
        -- and False reads as a cap of 0, rejecting every
        plan outright. Sibling readers exclude booleans
        explicitly -- runner.runner._cfg_size ("Booleans
        are not sizes"), runner.remediation._pos_int, and
        the inference config validator's `is True`
        refusal -- only this reader lets one through as
        a number on both of its inputs. Observed on
        2026-10-23: check_plan_budget with
        {"max_plan_steps": True} rejected a two-step
        plan, and with {"max_plan_timeout_sec": True}
        rejected a 10-second plan.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    _PLAN = [{"timeout_sec": 10}, {"timeout_sec": 10}]

    def test_true_max_plan_steps_defaults_to_8(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            self._PLAN, {"max_plan_steps": True})
        self.assertTrue(ok, reason)

    def test_false_max_plan_steps_defaults_to_8(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            self._PLAN, {"max_plan_steps": False})
        self.assertTrue(ok, reason)

    def test_true_max_plan_timeout_defaults_to_600(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            self._PLAN, {"max_plan_timeout_sec": True})
        self.assertTrue(ok, reason)

    def test_false_max_plan_timeout_defaults_to_600(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            self._PLAN, {"max_plan_timeout_sec": False})
        self.assertTrue(ok, reason)


class TestBooleanResourcesValuesAreConfigErrors(unittest.TestCase):
    """Divergence: a resources threshold or cooldown_sec set
    to a boolean reads as the number 1 or 0 instead of the
    startup config error every other malformed resources
    value gets.

    (a) Doc claim (docs/configuring-oracle.md, line 72):
        "`resources` -- the built-in resource monitor
        (`runner/resources.py`) ... `enabled` (default
        true), `threshold` (default 0.95; the CPU, memory,
        or disk fraction whose crossing files a
        `resource_pressure` security event; must be in
        (0, 1]), `cooldown_sec` (default 900; minimum
        seconds between repeat events for the same
        resource). A malformed block is a startup config
        error."
        The reader's own error strings state the same
        contract (runner/resources.py): a threshold that
        is not a number raises "config error:
        resources.threshold must be a number", a cooldown
        that is not a number raises "config error:
        resources.cooldown_sec must be a number", and a
        non-boolean `enabled` raises a config error --
        booleans are a distinct type in this block, never
        numbers. No document gives a boolean a numeric
        meaning for threshold or cooldown_sec.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 08:56 PDT tick) exercised
        runner.resources.parse_resources -- the single
        reader that validates the resources block -- with
        the block left unset and varied around it: block
        omitted, empty block, explicit documented defaults
        (0.95 / 900), explicit None, a non-numeric string
        ("bogus"), 0, 42, and the booleans True and False
        on each of threshold and cooldown_sec.

    (c) Behavior actually observed: omitted and empty
        read as the documented defaults (threshold 0.95,
        cooldown 900.0); None and "bogus" raise the
        documented RuntimeError config error on both keys.
        The booleans do not: parse_resources converts with
        float(raw) and no boolean guard, so threshold True
        reads as 1.0 -- the monitor then fires only at
        total saturation instead of the documented 0.95 --
        and cooldown_sec True reads as 1.0 second and
        False as 0.0 seconds instead of the documented
        900 -- repeat resource_pressure events on nearly
        every poll. (Threshold False happens to raise, but
        only because float(False) is 0.0 and 0 fails the
        range check, not because the boolean was refused.)
        Sibling readers exclude booleans explicitly --
        runner.runner._cfg_size ("Booleans are not
        sizes"), runner.remediation._pos_int, this same
        reader's own `enabled` check, and the inference
        config validator's `is True` refusal -- only these
        two float() conversions let one through as a
        number. Observed on 2026-10-23:
        parse_resources({"resources": {"threshold": True}})
        returned threshold 1.0, parse_resources(
        {"resources": {"cooldown_sec": True}}) returned
        cooldown_sec 1.0, and parse_resources({"resources":
        {"cooldown_sec": False}}) returned cooldown_sec
        0.0, none of them raising.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_threshold_is_config_error(self):
        from runner.resources import parse_resources
        with self.assertRaises(RuntimeError):
            parse_resources({"resources": {"threshold": True}})

    def test_true_cooldown_is_config_error(self):
        from runner.resources import parse_resources
        with self.assertRaises(RuntimeError):
            parse_resources({"resources": {"cooldown_sec": True}})

    def test_false_cooldown_is_config_error(self):
        from runner.resources import parse_resources
        with self.assertRaises(RuntimeError):
            parse_resources({"resources": {"cooldown_sec": False}})


class TestBooleanPromoteAfterDefaultsTo2(unittest.TestCase):
    """Divergence: oracle_learning_promote_after set to
    boolean true reads as 1 corroboration instead of the
    documented default of 2.

    (a) Doc claim (docs/configuring-oracle.md, line 53):
        "`oracle_learning_promote_after` -- how many verified
        corroborating outcomes a model candidate needs before
        it is treated as corroborated and may select among
        the existing mechanical repairs ... Default `2`."
        The same default is stated in the reader's own
        docstring (runner/learning.py, promote_after:
        "Default 2").

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 09:01 PDT tick) exercised
        runner.learning.promote_after -- the single reader
        for this config key -- with the key left unset and
        varied around it: omitted, explicit None, a
        non-numeric string ("bogus"), 0, -5, NaN, a valid
        3, a numeric string ("4"), and the booleans True
        and False.

    (c) Behavior actually observed: omitted, None,
        "bogus", 0, -5, and NaN all read as the documented
        default 2, and 3 / "4" are honored. True does not
        fall back: promote_after computes
        int(cfg.get("oracle_learning_promote_after")) with
        no boolean guard, so int(True) is 1, which passes
        the reader's >= 1 check and returns 1 -- a model
        candidate is then treated as corroborated after a
        single verified outcome instead of the documented
        two. False returns 0 and so reaches the default
        only through the below-1 fallback, not because the
        boolean was refused. Sibling numeric readers
        exclude booleans explicitly (runner.runner
        ._cfg_size: "Booleans are not sizes";
        runner.remediation._pos_int;
        runner.protocol_v2.deadline_of's sibling wait
        reader); this reader is the outlier for this key.
        Observed on 2026-10-23: promote_after(
        {"oracle_learning_promote_after": True})
        returned 1.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_promote_after_defaults_to_2(self):
        from runner.learning import promote_after
        self.assertEqual(
            promote_after({"oracle_learning_promote_after": True}), 2)


class TestBooleanSensorCooldownDefaultsToZero(unittest.TestCase):
    """Divergence: a sensor profile cooldown_sec set to boolean
    true reads as a 1-second dedup window instead of the
    documented default of 0 (no dedup), so a repeat alert is
    dropped.

    (a) Doc claim (docs/senses.md, lines 260-261):
        "`cooldown_sec`: drop repeats of the same sensor+title
        within this window. Default 0 (no dedup)."

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 09:06 PDT tick) exercised
        runner.senses.gate_alert -- the ingest gate that reads
        this profile knob -- with the key left unset and varied
        around it: omitted, explicit None, a non-numeric string
        ("bogus"), 0, a valid 300, and the booleans True and
        False, each time with one recent stored alert carrying
        the same title at the same instant.

    (c) Behavior actually observed: omitted, None, "bogus",
        0, and False all keep the alert (gate_alert returns
        None, the documented no-dedup default), and 300 drops
        it as a cooldown repeat. True does not fall back:
        gate_alert computes float(profile.get("cooldown_sec")
        or 0) with no boolean guard, so float(True) is 1.0,
        the > 0 check passes, and the same-title alert at the
        same instant is dropped as "cooldown: same title
        within 1s". The config validator shares the shape:
        parse_sensors likewise converts a boolean
        cooldown_sec to 1.0 instead of refusing it or reading
        the default. Sibling numeric readers exclude booleans
        explicitly (runner.runner._cfg_size: "Booleans are
        not sizes"; runner.remediation._pos_int;
        runner.security.audit_max_lines); this reader is the
        outlier. Observed on 2026-10-23: gate_alert(
        {"profile": {"cooldown_sec": True}},
        {"severity": "info", "title": "same"},
        [{"title": "same", "received_at": NOW}], now=<NOW as
        a timestamp>) returned "cooldown: same title within
        1s" instead of None.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_cooldown_defaults_to_zero_no_dedup(self):
        from datetime import datetime, timezone

        from runner.senses import gate_alert
        now = datetime(2026, 10, 23, 5, 50, 22,
                       tzinfo=timezone.utc).timestamp()
        self.assertIsNone(gate_alert(
            {"profile": {"cooldown_sec": True}},
            {"severity": "info", "title": "same"},
            [{"title": "same", "received_at": NOW}], now=now))


class TestBooleanSensorMaxPerHourDefaultsToZero(unittest.TestCase):
    """Divergence: a sensor profile max_per_hour set to boolean
    true reads as a cap of 1 alert per hour instead of the
    documented default of 0 (unlimited), so a second alert in
    the hour is dropped.

    (a) Doc claim (docs/senses.md, lines 262-263):
        "`max_per_hour`: sliding-window cap per sense; over-cap
        alerts are dropped. Default 0 (unlimited)."

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 09:16 PDT tick) exercised
        runner.senses.gate_alert -- the ingest gate that reads
        this profile knob -- with the key left unset and varied
        around it: omitted, explicit None, a non-numeric string
        ("bogus"), 0, a valid 60, a huge integer (10**400), and
        the booleans True and False, each time with one recent
        stored alert inside the hour window and a new alert of
        a different title (so the separate cooldown gate could
        not be the cause).

    (c) Behavior actually observed: omitted, None, "bogus",
        0, False, 60, and the huge integer all keep the new
        alert (gate_alert returns None, the documented
        unlimited default or a cap not yet reached). True does
        not fall back: gate_alert computes
        float(profile.get("max_per_hour") or 0) with no boolean
        guard (runner/senses.py line 221), so float(True) is
        1.0, the > 0 check passes, the one recent alert counts
        as n=1 >= cap=1, and the new alert is dropped as
        "over max_per_hour 1". The config validator shares the
        shape: parse_sensors likewise converts a boolean
        max_per_hour to 1.0 (runner/senses.py lines 93-103)
        instead of refusing it or reading the default.
        Sibling numeric readers exclude booleans explicitly
        (runner.runner._cfg_size: "Booleans are not sizes";
        runner.remediation._pos_int; runner.resources'
        enabled check); this reader is the outlier. Observed
        on 2026-10-23: gate_alert(
        {"profile": {"max_per_hour": True}},
        {"severity": "info", "title": "new"},
        [{"title": "other", "received_at": NOW}], now=<NOW as
        a timestamp>) returned "over max_per_hour 1" instead
        of None.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_max_per_hour_defaults_to_zero_unlimited(self):
        from datetime import datetime, timezone

        from runner.senses import gate_alert
        now = datetime(2026, 10, 23, 5, 50, 22,
                       tzinfo=timezone.utc).timestamp()
        self.assertIsNone(gate_alert(
            {"profile": {"max_per_hour": True}},
            {"severity": "info", "title": "new"},
            [{"title": "other", "received_at": NOW}], now=now))


class TestBooleanDriValuesAreConfigErrors(unittest.TestCase):
    """Divergence: a DRI cooldown, digest window, or trigger
    threshold/window set to a boolean reads as the number 1
    or 0 instead of the startup config error every other
    malformed DRI number gets.

    (a) Doc claim (docs/dri-playbook.md, "Config sketch",
        lines 127-142): the documented configuration is
        "sensor_fused_score": {"threshold": 6.0,
        "window_sec": 600}, "key_probe": {"threshold": 5,
        "window_sec": 3600}, "cooldown_sec": 3600,
        "digest_window_sec": 300 -- and those are exactly
        the values the reader returns when the keys are
        omitted, i.e. they are the defaults. The reader's
        own contract states the rest (runner/dri.py,
        parse_dri): it validates cfg["dri"] and raises
        RuntimeError on a config error; a threshold or
        window that is not a number raises "config error:
        dri.triggers... must be numbers", a cooldown or
        digest that is not a number raises "config error:
        dri cooldown/digest must be numbers", and a
        non-boolean `enabled` raises a config error --
        booleans are a distinct type in this block, never
        numbers. No document gives a boolean a numeric
        meaning for any of these keys.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 09:21 PDT tick) exercised
        runner.dri.parse_dri -- the single reader that
        validates the dri block -- with the block left
        unset and varied around it: block omitted, empty
        block, explicit documented defaults (6.0/600,
        5/3600, 3600, 300), explicit None, a non-numeric
        string ("bogus"), a huge integer (10**400), and
        the booleans True and False on each of
        cooldown_sec, digest_window_sec, the
        sensor_fused_score threshold and window_sec, and
        the key_probe threshold and window_sec.

    (c) Behavior actually observed: omitted and empty
        read as the documented defaults (threshold 6.0 /
        window 600, key_probe 5 / 3600, cooldown 3600.0,
        digest 300.0); "bogus" and the huge integer raise
        the documented RuntimeError config error.
        The booleans do not: parse_dri converts with
        float()/int() and no boolean guard (runner/dri.py
        lines 80-81, 98-99, and 106-107), so
        cooldown_sec True reads as 1.0 second and False
        as 0.0 instead of the documented 3600,
        digest_window_sec True reads as 1.0 instead of
        300, sensor_fused_score threshold True reads as
        1.0 instead of 6.0 (a far more sensitive page
        trigger), and key_probe threshold True reads as
        1 instead of 5. Sibling readers exclude booleans
        explicitly -- runner.runner._cfg_size ("Booleans
        are not sizes"), runner.remediation._pos_int,
        runner.security.audit_max_lines, and this same
        reader's own `enabled` check; these float()/int()
        conversions are the outliers. Observed on
        2026-10-23: parse_dri({"dri": {"cooldown_sec":
        True}}) returned cooldown_sec 1.0,
        parse_dri({"dri": {"cooldown_sec": False}})
        returned 0.0, and parse_dri({"dri": {"triggers":
        {"key_probe": {"threshold": True}}}}) returned
        threshold 1, none of them raising.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_cooldown_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"cooldown_sec": True}})

    def test_false_cooldown_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"cooldown_sec": False}})

    def test_true_digest_window_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"digest_window_sec": True}})

    def test_true_sensor_fused_threshold_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"triggers": {
                "sensor_fused_score": {"threshold": True}}}})

    def test_true_key_probe_threshold_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"triggers": {
                "key_probe": {"threshold": True}}}})


class TestBooleanMailboxPortIsConfigError(unittest.TestCase):
    """Divergence: an imap_port or smtp_port set to a boolean
    reads as port 1 or port 0 instead of the startup config
    error every other non-numeric port value gets.

    (a) Doc claim (PROTOCOL.md line 41): "Runner access:
        IMAP (read, port 993) + SMTP (send, port 587)" --
        repeated at PROTOCOL.md line 379, "IMAP/SMTP over
        TLS (993/587)" -- and those are exactly the values
        the reader returns when the keys are omitted, i.e.
        they are the defaults. The reader's own contract
        states the rest (runner/mailbox.py, _port, lines
        80-87): "A missing or non-numeric port is a config
        error, not a crash", raising RuntimeError
        "config error: <key> must be a number". The
        runner's startup validation relies on that
        (runner/runner.py: a bad port is a config error,
        checked at startup so the poll loop is not the
        thing that discovers it). No document gives a
        boolean a numeric meaning as a port; sibling
        readers exclude booleans explicitly (for example
        runner.runner._cfg_size, "Booleans are not
        sizes", and runner.dri.parse_dri's own `enabled`
        check, where booleans are a distinct type, never
        numbers).

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 09:31 PDT tick) exercised
        runner.mailbox._port -- the single reader that
        validates imap_port and smtp_port, called from
        connect_imap, connect_smtp, and the runner's
        startup validation -- with each key left unset
        and varied around it: omitted, the explicit
        documented defaults (993, 587), explicit None,
        a non-numeric string ("bogus"), a huge integer
        (10**400), and the booleans True and False on
        both keys.

    (c) Behavior actually observed: omitted reads as
        the documented defaults (993, 587); "bogus" and
        None raise the documented RuntimeError config
        error. The booleans do not: _port converts with
        int() and no boolean guard (runner/mailbox.py
        line 85), so imap_port True reads as port 1 and
        False as port 0 instead of raising, and
        smtp_port True reads as port 1 and False as
        port 0 instead of raising -- a silently wrong
        mail port rather than the config error the
        startup check exists to surface. Observed on
        2026-10-23: _port({"imap_port": True},
        "imap_port", 993) returned 1, _port(
        {"imap_port": False}, "imap_port", 993)
        returned 0, and _port({"smtp_port": True},
        "smtp_port", 587) returned 1, none of them
        raising.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_imap_port_is_config_error(self):
        from runner.mailbox import _port
        with self.assertRaises(RuntimeError):
            _port({"imap_port": True}, "imap_port", 993)

    def test_false_imap_port_is_config_error(self):
        from runner.mailbox import _port
        with self.assertRaises(RuntimeError):
            _port({"imap_port": False}, "imap_port", 993)

    def test_true_smtp_port_is_config_error(self):
        from runner.mailbox import _port
        with self.assertRaises(RuntimeError):
            _port({"smtp_port": True}, "smtp_port", 587)

    def test_false_smtp_port_is_config_error(self):
        from runner.mailbox import _port
        with self.assertRaises(RuntimeError):
            _port({"smtp_port": False}, "smtp_port", 587)


class TestBooleanAgentWallClockDefaultsTo300(unittest.TestCase):
    """Divergence: an inference agent_wall_clock_sec set to the
    boolean true becomes a 1-second wall clock for the Oracle
    agent loop, instead of the documented 300-second default.

    (a) Doc claim (docs/configuring-oracle.md, line 70):
        "`agent_wall_clock_sec` (default 300; the
        whole-conversation wall clock for the `--oracle` agent
        loop, on top of the per-call `timeout_sec`)".
        The constant the docs describe is
        _ORACLE_AGENT_WALL_CLOCK_SEC = 300 (runner/runner.py
        line 2026).

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 09:36 PDT tick) exercised
        runner.runner.ask_model_agent -- the same direct-call
        surface the repo's own agent tests use -- with the
        inference config's agent_wall_clock_sec varied around
        the documented default: omitted, the string "bogus",
        a valid 42, boolean false, and boolean true. The
        clock was controlled by patching time.monotonic so
        the loop starts at 0 and stands at 10 seconds elapsed
        on every later reading (well inside the documented
        300), _inference_chat was faked to answer the first
        round with one read_file tool call and later rounds
        with a plain answer, and _run_oracle_tool was stubbed.
        Whether the agent was forced into its
        out-of-investigation-time wrap-up (a final chat call
        with tools=None and the "out of investigation time"
        note appended) is the observable signal of what wall
        clock the code actually used.

    (c) Behavior actually observed: omitted, "bogus", and 42
        all behave as documented -- no wrap-up at 10 seconds
        elapsed. Boolean false also lands on the default
        (False is falsy, so `or` yields 300). Boolean true
        does not: ask_model_agent (runner/runner.py lines
        2753-2759) computes
        int(cfg.get("agent_wall_clock_sec") or 300); True is
        truthy, int(True) is 1, and 1 is not below the
        code's < 1 guard, so the wall clock becomes 1 second.
        At 10 seconds elapsed the second chat call arrives
        with tools=None and the out-of-investigation-time
        note, cutting off an investigation the documented
        default would have allowed for another 290 seconds.
        Python's bool is a subclass of int, and the sibling
        parsers in this codebase refuse booleans explicitly
        (_cfg_size for the log bounds, _pos_int in
        remediation, the `is True` rejection in
        inference_config); this read site has no such guard.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    _BASE = {"endpoint": "http://127.0.0.1:9/v1", "model": "m"}

    def _run_agent(self, extra):
        from unittest import mock

        from runner import runner
        cfg = dict(self._BASE)
        cfg.update(extra)
        seq = {"n": 0}

        def mono():
            seq["n"] += 1
            return 0 if seq["n"] == 1 else 10

        seen = {"tools": [], "out_of_time": False}

        def chat(cfg, messages, tools, opener, timeout):
            seen["tools"].append(tools)
            for m in messages:
                if "out of investigation time" in (m.get("content") or ""):
                    seen["out_of_time"] = True
            if len(seen["tools"]) == 1:
                return {"role": "assistant", "content": "",
                        "tool_calls": [{
                            "id": "c1",
                            "function": {"name": "read_file",
                                         "arguments":
                                             {"path": "/no/such/hp-gap"}}}]}
            return {"role": "assistant", "content": "final answer"}

        with mock.patch.object(runner.time, "monotonic",
                               side_effect=mono), \
             mock.patch.object(runner, "_inference_chat",
                               side_effect=chat), \
             mock.patch.object(runner, "_run_oracle_tool",
                               return_value="(no output)"):
            runner.ask_model_agent(cfg, "why?", "some output", 100)
        return seen

    def test_true_agent_wall_clock_defaults_to_300(self):
        seen = self._run_agent({"agent_wall_clock_sec": True})
        self.assertFalse(seen["out_of_time"])
        self.assertNotIn(None, seen["tools"])

    def test_false_agent_wall_clock_defaults_to_300(self):
        # Control: false already lands on the documented
        # default today (falsy, so `or` yields 300); it must
        # keep doing so after the true case is fixed.
        seen = self._run_agent({"agent_wall_clock_sec": False})
        self.assertFalse(seen["out_of_time"])
        self.assertNotIn(None, seen["tools"])


class TestBooleanTaskTimeoutDefaultsTo86400(unittest.TestCase):
    """Divergence: a task_timeout set to a JSON boolean (true or
    false) strips a board claim after at most one second, instead
    of falling back to the documented 86400-second default.

    (a) Doc claim (docs/configuring-oracle.md, line 41):
        "`task_timeout` -- seconds before a claimed task is
        returned to open. Default 86400."
        The same default is stated in docs/SAFEGUARDS.md
        line 132 ("`task_timeout` (default 86400): a claim lapses
        after this many [seconds]") and in PROTOCOL.md
        section 13.6 ("A claim lapses after `task_timeout`
        (config, default 24h) with no result, and the task
        returns to open.").

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 09:41 PDT tick) exercised the board reoffer
        path in runner/runner.py with task_timeout varied
        around the documented default -- key omitted, explicit
        86400, explicit 3600, boolean true, and boolean false --
        using the exact caller expression the board-mail
        handler uses,
        board.reoffer_expired(cfg.get("task_timeout", 86400)),
        on a task claimed one hour earlier (well inside the
        documented 86400-second default, so a correct read
        leaves the claim in place).

    (c) Behavior actually observed: omitted, explicit 86400,
        and a claim read with the documented default all leave
        the one-hour-old claim claimed (reoffer count 0).
        Explicit 3600 reoffers it, as a valid one-hour timeout
        should. Boolean true and boolean false do not land on
        the default: the .get default fires only when the key
        is absent, so Board._reoffer_expired_unlocked compares
        the claim age with `> task_timeout` where task_timeout
        is the boolean itself -- True compares as 1 and False
        as 0 (Python's bool is a subclass of int), so both
        reoffer the claim immediately (count 1, state returns
        to open), stripping a live worker's lease 23 hours
        early. The sibling boolean hunts in this file show the
        codebase's other default readers reject booleans or
        fall back to the documented default; this read site
        has no such guard. This extends the null/bogus-string
        task_timeout divergence recorded above: those wedge a
        claim forever, these strip it at once.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    def _reoffer_via_config(self, cfg, age_hours=1):
        # The exact caller expression in handle_board_mail
        # (runner/runner.py): the .get default fires only when
        # the key is absent, not when it holds a boolean.
        import os
        from datetime import datetime, timedelta, timezone

        from runner.runner import Board
        with tempfile.TemporaryDirectory() as base:
            board = Board(os.path.join(base, "board.json"))
            board.submit({"task_id": "t1"})
            old = (datetime.now(timezone.utc)
                   - timedelta(hours=age_hours)).isoformat()
            board.tasks["t1"]["state"] = "claimed"
            board.tasks["t1"]["claimed_at"] = old
            board.tasks["t1"]["claimed_by"] = "w1"
            count = board.reoffer_expired(
                cfg.get("task_timeout", 86400))
            return count, board.tasks["t1"]["state"]

    def test_true_task_timeout_defaults_to_86400(self):
        count, state = self._reoffer_via_config(
            {"task_timeout": True})
        self.assertEqual(count, 0)
        self.assertEqual(state, "claimed")

    def test_false_task_timeout_defaults_to_86400(self):
        count, state = self._reoffer_via_config(
            {"task_timeout": False})
        self.assertEqual(count, 0)
        self.assertEqual(state, "claimed")

    def test_explicit_3600_still_reoffers_at_one_hour(self):
        # Control: a valid one-hour timeout reoffers a claim
        # aged just over one hour; the fix must keep genuine
        # integer timeouts working, not freeze every claim.
        count, state = self._reoffer_via_config(
            {"task_timeout": 3600}, age_hours=2)
        self.assertEqual(count, 1)
        self.assertEqual(state, "open")


class TestBooleanPollIntervalDefaultsTo20(unittest.TestCase):
    """Divergence: a poll_interval_sec set to the boolean true
    becomes a 1-second poll instead of the documented
    20-second default.

    (a) Doc claim (docs/FAQs.md, line 9):
        "The deterministic code around the model does the
        watching on the runner's poll cycle -- every 20 seconds
        by default (`poll_interval_sec`)."
        The same 20 is the value in runner/config.example.json
        and runner/setup.py's generated config, and the core
        loop's own fallback for an unreadable value is 20
        (runner/runner.py, the poll delay read in main()).

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 10:11 PDT tick) exercised the email
        transport extension's run loop -- the extension the
        core hands poll_interval_sec to verbatim via
        runner/transports.py's _runtime_config -- with the
        key varied around the documented default: omitted,
        explicit None, 0, boolean false, the string "bogus",
        a valid 42, and boolean true. EmailPipe.run computes
        its interval once, then naps that long after each
        pass; pass_once was stubbed out and channel.nap was
        replaced with a recorder that breaks the loop, so the
        interval each config actually used is observed
        directly, the same direct-call surface the repo's own
        transport tests use.

    (c) Behavior actually observed: omitted, None, 0, false,
        and "bogus" all poll at the documented default
        (nap 20.0), and 42 is honored (nap 42.0). Boolean
        true does not: EmailPipe.run
        (runner/transport_extensions/email/__main__.py)
        computes max(1.0, float(cfg.get("poll_interval_sec")
        or 20)); True is truthy, so the `or 20` default never
        fires, float(True) is 1.0, and the transport polls
        every 1 second -- twenty times the documented
        cadence, spending mailbox quota the default exists
        to pace. The core's own reader has the same shape:
        int(cfg.get("poll_interval_sec", 20)) in main() is 1
        for true and its below-1 fallback rescues only
        false. Python's bool is a subclass of int, and the
        sibling parsers in this codebase refuse booleans
        explicitly (_cfg_size for the log bounds, _pos_int in
        remediation, audit_max_lines in security); these
        read sites have no such guard. This is the known
        boolean-as-number family.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    def _run_interval(self, extra):
        import importlib
        from unittest import mock

        mod = importlib.import_module(
            "runner.transport_extensions.email.__main__")
        cfg = {"mailbox_user": "a@b.c"}
        cfg.update(extra)
        pipe = mod.EmailPipe(cfg, "/tmp/hp-no-such-channel")
        seen = []

        class _Done(Exception):
            pass

        def nap(sec):
            seen.append(sec)
            raise _Done()

        with mock.patch.object(pipe, "pass_once",
                               return_value=None), \
             mock.patch.object(mod.ch, "nap", side_effect=nap):
            try:
                pipe.run()
            except _Done:
                pass
        return seen

    def test_true_poll_interval_defaults_to_20(self):
        self.assertEqual(
            self._run_interval({"poll_interval_sec": True}),
            [20.0])

    def test_false_poll_interval_defaults_to_20(self):
        # Control: false already lands on the documented
        # default today (falsy, so `or` yields 20); it must
        # keep doing so after the true case is fixed.
        self.assertEqual(
            self._run_interval({"poll_interval_sec": False}),
            [20.0])

    def test_explicit_42_poll_interval_is_honored(self):
        # Control: a valid interval is used as given; the
        # fix must not flatten genuine values to the default.
        self.assertEqual(
            self._run_interval({"poll_interval_sec": 42}),
            [42.0])


class TestBooleanDtlsPortDefaultsTo20220(unittest.TestCase):
    """Divergence: transport_dtls port set to a boolean reads
    as port 1 (true) or port 0 (false) instead of the
    documented default 20220.

    (a) Doc claim (docs/configuring-oracle.md, line 64):
        "`transport_dtls` -- the DTLS session binding ...
        handed to the DTLS extension: `port` (default 20220)
        and `bind` (default `0.0.0.0`)."
        The extension's own module docstring states the same
        (runner/transport_extensions/dtls/__main__.py, lines
        5-9): "port    UDP port to listen on (default 20220)".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised
        runner.transport_extensions.dtls DtlsPipe construction
        with the transport_dtls block varied around the
        documented default -- port omitted, explicit None,
        a non-numeric string ("bogus"), 0, a valid 20220, and
        the booleans True and False -- checking the port the
        pipe actually bound. The null and bogus forms are
        already recorded in TestNullDtlsPortBindDefaults
        above; this class records the boolean forms of the
        same reader.

    (c) Behavior actually observed: omitted reads as the
        documented default 20220 and 0 binds an ephemeral
        port as constructed in the repo's own pipe tests.
        True does not fall back: DtlsPipe.__init__ computes
        int(cfg.get("port", DEFAULT_PORT)) with no boolean
        guard, so True returns 1 -- the pipe binds the
        privileged port 1 the operator never asked for --
        and False returns 0, an ephemeral port, instead of
        the documented 20220 either way. Sibling parsers in
        this codebase refuse booleans explicitly
        (_cfg_size for the log bounds, _pos_int in
        remediation, audit_max_lines in security, and
        _validate_size_caps for the size caps); this read
        site has no such guard. This is the known
        boolean-as-number family. Observed on 2026-10-23:
        DtlsPipe with port True bound port 1 and with port
        False bound port 0.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    def _pipe(self, extra):
        import importlib
        import os

        dtls_ext = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        cfg = {"shared_secret": "campaign-test-secret-0123456789",
               "port": 0, "bind": "127.0.0.1"}
        cfg.update(extra)
        with tempfile.TemporaryDirectory() as tmp:
            pipe = dtls_ext.DtlsPipe(
                cfg, os.path.join(tmp, "channel"))
        self.addCleanup(pipe.sock.close)
        return pipe

    def test_true_port_defaults_to_20220(self):
        pipe = self._pipe({"port": True})
        self.assertEqual(pipe.port, 20220)

    def test_false_port_defaults_to_20220(self):
        pipe = self._pipe({"port": False})
        self.assertEqual(pipe.port, 20220)


class TestBooleanMaxJobAgeDefaultsTo3600(unittest.TestCase):
    """Divergence: max_job_age_sec set to a boolean reads as a
    1-second (true) or 0-second (false) freshness window instead
    of the documented default 3600, so a job issued a minute ago
    is rejected as stale.

    (a) Doc claim (PROTOCOL.md, section 5, lines 323-325):
        "`issued_at` parses, carries a timezone, and is within
        `max_job_age_sec` (default 3600) of the runner's clock
        (replay / stale protection)."

    (b) How the bug was found: the campaign's doc-default hunt
        (2026-10-23 tick) exercised runner.runner._issued_at_ok
        -- the freshness check the verification list names --
        with max_job_age_sec varied around the documented
        default -- key omitted, explicit None, a non-numeric
        string ("bogus"), explicit 3600, and the booleans True
        and False -- each against a timestamp issued 60 seconds
        ago, well inside the documented 3600-second window.
        The zero/negative forms of this same reader are already
        recorded in TestZeroOrNegativeMaxJobAgeDefaultsTo3600
        above; this class records the boolean forms.

    (c) Behavior actually observed: omitted, explicit None,
        "bogus", and explicit 3600 all accept the 60-second-old
        timestamp. True and False do not fall back:
        _issued_at_ok computes int(cfg.get("max_job_age_sec",
        3600)) with a fallback only for unparseable values and
        no boolean guard, so True returns a 1-second window and
        False returns 0, and the 60-second-old job is rejected
        as "issued_at outside allowed window" either way. The
        same unguarded expression is duplicated at the
        local-signals and mail handlers' freshness checks.
        Sibling parsers in this codebase refuse booleans
        explicitly. This is the known boolean-as-number family.
        Observed on 2026-10-23: _issued_at_ok with an issued_at
        60 seconds ago returned (True, '') for omitted, None,
        "bogus", and 3600, and (False, 'issued_at outside
        allowed window') for True and for False.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    def _issued_60s_ago(self):
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc)
                - timedelta(seconds=60)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")

    def test_true_max_job_age_defaults_to_3600(self):
        from runner.runner import _issued_at_ok
        ok, reason = _issued_at_ok(
            self._issued_60s_ago(), {"max_job_age_sec": True})
        self.assertTrue(ok, reason)

    def test_false_max_job_age_defaults_to_3600(self):
        from runner.runner import _issued_at_ok
        ok, reason = _issued_at_ok(
            self._issued_60s_ago(), {"max_job_age_sec": False})
        self.assertTrue(ok, reason)


class TestBooleanDriWindowSecIsConfigError(unittest.TestCase):
    """Divergence: a DRI trigger window_sec set to a boolean
    reads as a 1-second (true) or 0-second (false) window
    instead of the startup config error every other malformed
    DRI trigger number gets.

    (a) Doc claim (docs/dri-playbook.md, "Config sketch",
        lines 133-136): the documented configuration is
        "sensor_fused_score": {"threshold": 6.0,
        "window_sec": 600} and "key_probe": {"threshold": 5,
        "window_sec": 3600} -- and those are exactly the
        values the reader returns when the keys are omitted,
        i.e. they are the defaults. The reader's own contract
        states the rest (runner/dri.py, parse_dri): a
        threshold or window that is not a number raises
        "config error: dri.triggers... threshold/window_sec
        must be numbers", and a non-boolean `enabled` raises
        a config error -- booleans are a distinct type in
        this block, never numbers. No document gives a
        boolean a numeric meaning for either window_sec.
        The threshold halves of these same two triggers are
        already recorded in TestBooleanDriValuesAreConfigErrors
        above, whose hunt exercised the windows but landed no
        test for them; this class records the window forms.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 10:36 PDT tick) exercised
        runner.dri.parse_dri -- the single reader that
        validates the dri block -- with each trigger's
        window_sec left unset and varied around the
        documented defaults: key omitted, the documented
        600 / 3600, a non-numeric string ("bogus"), and the
        booleans True and False.

    (c) Behavior actually observed: omitted reads as the
        documented defaults (sensor_fused_score window
        600.0, key_probe window 3600.0), the documented
        values are honored, and "bogus" raises the
        documented RuntimeError config error. The booleans
        do not: parse_dri converts with float() and no
        boolean guard (runner/dri.py lines 81 and 99), so
        sensor_fused_score window_sec True reads as 1.0
        second and False as 0.0 instead of raising, and
        key_probe window_sec True reads as 1.0 and False
        as 0.0 -- a fused score or key-probe count is then
        tallied over a one-second or empty window instead
        of the documented 600 / 3600 seconds. Sibling
        readers exclude booleans explicitly --
        runner.runner._cfg_size ("Booleans are not sizes"),
        runner.remediation._pos_int,
        runner.security.audit_max_lines, and this same
        reader's own `enabled` check; these float()
        conversions are the outliers. This is the known
        boolean-as-number family. Observed on 2026-10-23:
        parse_dri({"dri": {"triggers": {"sensor_fused_score":
        {"window_sec": True}}}}) returned window_sec 1.0 and
        with False returned 0.0, and parse_dri({"dri":
        {"triggers": {"key_probe": {"window_sec": True}}}})
        returned window_sec 1.0 and with False returned 0.0,
        none of them raising.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code.
    """

    def test_true_sensor_fused_window_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"triggers": {
                "sensor_fused_score": {"window_sec": True}}}})

    def test_false_sensor_fused_window_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"triggers": {
                "sensor_fused_score": {"window_sec": False}}}})

    def test_true_key_probe_window_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"triggers": {
                "key_probe": {"window_sec": True}}}})

    def test_false_key_probe_window_is_config_error(self):
        from runner.dri import parse_dri
        with self.assertRaises(RuntimeError):
            parse_dri({"dri": {"triggers": {
                "key_probe": {"window_sec": False}}}})

    def test_documented_windows_are_honored(self):
        # Control: the documented defaults pass validation
        # untouched; the fix must not flatten genuine
        # values into an error.
        from runner.dri import parse_dri
        out = parse_dri({"dri": {"triggers": {
            "sensor_fused_score": {"window_sec": 600},
            "key_probe": {"window_sec": 3600}}}})
        self.assertEqual(
            out["triggers"]["sensor_fused_score"]["window_sec"],
            600.0)
        self.assertEqual(
            out["triggers"]["key_probe"]["window_sec"], 3600.0)


class TestHugeEmailPollIntervalDefaultsTo20(unittest.TestCase):
    """Divergence: a poll_interval_sec that is a huge integer
    (a JSON number with hundreds of digits) raises a raw
    OverflowError out of the email transport extension's run
    loop, instead of falling back to the documented
    20-second default; an infinite value likewise becomes
    an infinite poll interval instead of the default.

    (a) Doc claim (docs/FAQs.md, line 9): the runner's poll
        cycle runs "every 20 seconds by default
        (`poll_interval_sec`)". docs/configuring-oracle.md
        (flag-to-key map, line 82) maps `--poll-interval
        SECONDS` to the same key. The core hands this key
        to every transport extension as its cadence
        (runner/transports.py, _runtime_config:
        "poll_interval_sec": cfg.get("poll_interval_sec",
        20)), and the email extension's own reader states
        the same fallback in code: an unparseable value
        lands on 20.0 (its except path).

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 10:41 PDT tick) exercised
        EmailPipe.run in
        runner/transport_extensions/email/__main__.py with
        poll_interval_sec left unset and varied around it
        -- key omitted, a non-numeric string ("bogus"), 0,
        False, a valid 42, the boolean True, a negative
        value, float("inf"), and a huge integer (10**400)
        -- recording the interval the run loop logged
        ("polling ... every Ns") with pass_once stubbed
        out and the channel nap stubbed to stop the loop
        after one pass. The huge form is reachable from a
        real config file: load_config uses a plain
        json.load, which parses a several-hundred-digit
        JSON number into an arbitrary-precision int, and
        _runtime_config hands the value to the extension
        verbatim.

    (c) Behavior actually observed: omitted, "bogus", 0,
        and False all poll every 20s, and 42 is honored.
        The huge int does not: run() computes
        float(cfg.get("poll_interval_sec") or 20) guarded
        by `except (TypeError, ValueError)` only, and
        float(10**400) raises OverflowError, which escapes
        run() before the first pass -- the default
        transport (email is the default transport) dies at
        startup and the supervisor restarts a permanently
        dead extension. Infinity does not crash there but
        is used literally: the loop logs "every infs" and
        naps forever, so the mailbox is polled once and
        never again, instead of every 20 seconds. Sibling
        float readers include OverflowError in their
        fallback guard: the core's poll-interval reader,
        parse_sensors and gate_alert (runner/senses.py),
        and _cfg_size (runner/runner.py) all catch it;
        this reader is the outlier.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    class _Stop(Exception):
        pass

    def _logged_interval(self, extra):
        import importlib
        em = importlib.import_module(
            "runner.transport_extensions.email.__main__")
        from runner.transport_extensions import channel as ch
        cfg = {"mailbox_user": "probe@example.invalid"}
        cfg.update(extra)
        pipe = em.EmailPipe(cfg, "/tmp/docdef-no-channel")
        logs = []
        orig_log, orig_nap = ch.log, ch.nap
        ch.log = lambda msg, *a, **k: logs.append(str(msg))
        pipe.pass_once = lambda: None

        def _nap(_seconds):
            raise self._Stop()
        ch.nap = _nap
        try:
            with self.assertRaises(self._Stop):
                pipe.run()
        finally:
            ch.log, ch.nap = orig_log, orig_nap
        self.assertTrue(logs, "run loop logged no interval")
        return logs[0]

    def test_huge_poll_interval_defaults_to_20(self):
        line = self._logged_interval(
            {"poll_interval_sec": 10**400})
        self.assertIn("every 20s", line)

    def test_infinite_poll_interval_defaults_to_20(self):
        line = self._logged_interval(
            {"poll_interval_sec": float("inf")})
        self.assertIn("every 20s", line)


class TestBadNatsPortDefaultsTo4222(unittest.TestCase):
    """Divergence: a NATS broker URL whose port urlparse
    rejects (out of range, or not a number) raises a raw
    ValueError out of the NATS transport extension's
    reconnect loop, instead of falling back to the
    documented default port 4222.

    (a) Doc claim (docs/configuring-oracle.md, line 62):
        "`transport_nats` -- core NATS, handed to the NATS
        extension: `url` (default `nats://127.0.0.1:4222`),
        `subject` (default `homing-pigeon.jobs`),
        `result_subject_prefix` (default
        `homing-pigeon.results`)." The extension's own
        module docstring states the same default. The
        client's reader states the fallback in code:
        `self.port = parsed.port or 4222` -- a port that
        cannot be used lands on 4222.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 10:46 PDT tick) exercised
        NatsClient and NatsPipe in
        runner/transport_extensions/nats/__main__.py with
        the transport_nats url varied around the
        documented default -- key omitted, no port, port
        0, an explicit valid port, an out-of-range port
        (99999), and a non-numeric port (abc) -- recording
        the host/port the client resolved and whether
        NatsPipe.run() stayed inside its reconnect loop
        (channel nap stubbed to stop it after the first
        failed connect). The bad-port forms are reachable
        from a real config file: the transport_nats block
        is handed to the extension verbatim, and nothing
        between config.json and the client validates the
        URL's port.

    (c) Behavior actually observed: an omitted URL, a
        URL with no port, and port 0 all resolve to
        127.0.0.1:4222, and an explicit valid port is
        honored. The out-of-range and non-numeric ports
        do not: `urlparse(...).port` is a property that
        raises ValueError ("Port out of range 0-65535" /
        "Port could not be cast to integer value"), and
        NatsClient.__init__ reads it unguarded, so the
        ValueError escapes NatsPipe.run() -- whose
        reconnect loop catches TransportError only --
        and kills the extension process before any
        connection attempt; the supervisor restarts a
        permanently dead extension instead of the pipe
        connecting on the default port, or at worst
        retrying a clean TransportError.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    class _Stop(Exception):
        pass

    def _client(self, url):
        import importlib
        nm = importlib.import_module(
            "runner.transport_extensions.nats.__main__")
        return nm.NatsClient(url)

    def test_out_of_range_port_defaults_to_4222(self):
        client = self._client("nats://127.0.0.1:99999")
        self.assertEqual(client.port, 4222)

    def test_non_numeric_port_defaults_to_4222(self):
        client = self._client("nats://127.0.0.1:abc")
        self.assertEqual(client.port, 4222)

    def test_explicit_and_missing_ports_are_honored(self):
        # Controls: a valid port is used as given, and a
        # URL with no port already lands on the default --
        # proving the readers work, not that every URL is
        # forced to 4222.
        self.assertEqual(
            self._client("nats://broker.example:4223").port,
            4223)
        self.assertEqual(
            self._client("nats://127.0.0.1").port, 4222)

    def test_bad_port_stays_in_reconnect_loop(self):
        import importlib
        nm = importlib.import_module(
            "runner.transport_extensions.nats.__main__")
        from runner.transport_extensions import channel as ch
        pipe = nm.NatsPipe(
            {"url": "nats://127.0.0.1:99999",
             "allow_unauthenticated": True},
            "/tmp/docdef-no-channel", log=lambda *a, **k: None)
        orig_nap = ch.nap

        def _nap(_seconds):
            raise self._Stop()
        ch.nap = _nap
        try:
            with self.assertRaises(self._Stop):
                pipe.run()
        finally:
            ch.nap = orig_nap


class TestBooleanDefaultTimeoutDefaultsTo300(unittest.TestCase):
    """Divergence: default_timeout_sec set to a JSON boolean
    gives every timeout-less job a 1-second timeout instead
    of the documented 300-second default.

    (a) Doc claim (PROTOCOL.md, section 3.1, line 136):
        "`timeout_sec`: default 300, maximum 3600."
        docs/configuring-oracle.md (flag-to-key map,
        line 83) maps the flag that carries that default
        to this config key: "`--timeout SECONDS` |
        `default_timeout_sec`".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 10:56 PDT tick) exercised
        runner.runner.execute_job with a job that omits
        timeout_sec and a script that sleeps 2 seconds
        before printing 'hi-probe', varying
        default_timeout_sec around the documented
        default -- key omitted, explicit 300, explicit
        42 (with a fast script), "bogus", True, and
        False.

    (c) Behavior actually observed: omitted and explicit
        300 run the 2-second job to completion (exit 0,
        stdout 'hi-probe', timed_out False), and "bogus"
        is rejected as "timeout_sec must be a number"
        (the already-recorded null/bogus divergence).
        True and False do neither: execute_job computes
        int(job.get("timeout_sec") or
        cfg.get("default_timeout_sec", 300)) -- int(True)
        is 1, and int(False) is 0 which the following
        clamp lifts to 1 -- so both booleans silently
        become a 1-second timeout, the 2-second job is
        killed (exit -1, timed_out True, no stdout),
        instead of falling back to the documented 300.
        This is the known boolean-as-number family:
        numeric config getters accept a Python boolean
        as 1/0 instead of falling back to the documented
        default or raising the documented config error.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def _run(self, cfg_extra):
        from runner.runner import execute_job
        with tempfile.TemporaryDirectory() as base:
            cfg = {"base_dir": base}
            cfg.update(cfg_extra)
            job = {"v": 1, "type": "job", "job_id": "docdef-bto",
                   "issued_at": "2026-10-23T00:00:00Z",
                   "kind": "exec", "interpreter": ["python3"],
                   "script": "import time; time.sleep(2); "
                             "print('hi-probe')"}
            return execute_job(cfg, job, base)

    def test_true_default_timeout_defaults_to_300(self):
        result = self._run({"default_timeout_sec": True})
        self.assertEqual(result.get("exit_code"), 0)
        self.assertFalse(result.get("timed_out"))
        self.assertIn("hi-probe", result.get("stdout", ""))

    def test_false_default_timeout_defaults_to_300(self):
        result = self._run({"default_timeout_sec": False})
        self.assertEqual(result.get("exit_code"), 0)
        self.assertFalse(result.get("timed_out"))
        self.assertIn("hi-probe", result.get("stdout", ""))

    def test_omitted_default_timeout_runs_two_second_job(self):
        # Control: with the key omitted the documented
        # default really does let the same job finish --
        # proving the harness works, not that every
        # config is forced to a long timeout.
        result = self._run({})
        self.assertEqual(result.get("exit_code"), 0)
        self.assertIn("hi-probe", result.get("stdout", ""))


class TestBadDtlsPortDefaultsTo20220(unittest.TestCase):
    """Divergence: transport_dtls port set to a non-numeric
    or out-of-range value kills the DTLS extension at
    startup instead of reading as the documented default
    port 20220.

    (a) Doc claims: docs/configuring-oracle.md line 64 --
        "`transport_dtls` ... `port` (default 20220) and
        `bind` (default `0.0.0.0`)"; docs/TRANSPORTS.md
        lines 273-274 -- "(`transport_dtls.port`, default
        20220; `transport_dtls.bind`, default `0.0.0.0`)";
        the extension's own module docstring in
        runner/transport_extensions/dtls/__main__.py --
        "port    UDP port to listen on (default 20220)".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) constructed
        runner.transport_extensions.dtls.__main__.DtlsPipe
        -- the listening pipe the supervisor starts when
        `dtls` is enabled -- with the port key omitted
        (control), explicit 0 (control), and set to
        "bogus", "99999", 99999, -1, None, 10**400, and
        float("inf"). The boolean forms of this same read
        site are already recorded in
        TestBooleanDtlsPortDefaultsTo20220 above; this
        class records the non-numeric / out-of-range
        forms, which fail differently -- by raising out
        of the constructor, not by binding a wrong port.

    (c) Behavior actually observed: omitted reads 20220
        and explicit 0 binds port 0, as documented.
        Every bad value raises out of DtlsPipe.__init__
        instead of falling back to 20220: "bogus" raises
        ValueError from the unguarded int(port) read;
        None raises TypeError the same way; float("inf")
        raises OverflowError there; and "99999", 99999,
        -1, and 10**400 pass int() and raise
        OverflowError from sock.bind ("port must be
        0-65535"). The extension process dies before it
        ever listens, so a typo'd port is a dead
        transport (supervisor restart loop), not the
        documented default.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _pipe(self, extra, omit_port=False):
        import importlib
        import os
        dtls_ext = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        cfg = {"shared_secret": "campaign-test-secret-0123456789",
               "bind": "127.0.0.1"}
        if not omit_port:
            cfg["port"] = 0
        cfg.update(extra)
        with tempfile.TemporaryDirectory() as tmp:
            pipe = dtls_ext.DtlsPipe(
                cfg, os.path.join(tmp, "channel"))
        self.addCleanup(pipe.sock.close)
        return pipe

    def test_bogus_port_defaults_to_20220(self):
        pipe = self._pipe({"port": "bogus"})
        self.assertEqual(pipe.port, 20220)

    def test_out_of_range_port_defaults_to_20220(self):
        pipe = self._pipe({"port": 99999})
        self.assertEqual(pipe.port, 20220)

    def test_none_port_defaults_to_20220(self):
        pipe = self._pipe({"port": None})
        self.assertEqual(pipe.port, 20220)

    def test_huge_port_defaults_to_20220(self):
        pipe = self._pipe({"port": 10**400})
        self.assertEqual(pipe.port, 20220)

    def test_omitted_port_is_20220(self):
        # Control: with the key omitted the documented
        # default really is used -- proving the harness
        # works, not that every config is forced to it.
        pipe = self._pipe({}, omit_port=True)
        self.assertEqual(pipe.port, 20220)


class TestHugeExtensionPollIntervalDefaultsTo2(unittest.TestCase):
    """Divergence: an extension_poll_interval_sec that is a
    huge integer (a JSON number with hundreds of digits)
    raises a raw OverflowError out of the shared transport
    channel's poll-interval reader, instead of falling back
    to its 2.0-second default -- the file transport, the
    reader's caller, dies at startup before its first pass.

    (a) The documented contract: runner/transport_extensions/
        channel.py's poll_interval(cfg, default=2.0) is the
        one reader every polling transport extension takes
        its cadence from (the file transport's main() calls
        it before its loop), and its contract -- stated by
        its signature default and pinned by the repo's own
        tests/test_transport_shells.py,
        test_poll_interval_clamps_and_rejects_garbage -- is
        that an unusable value falls back to the default
        2.0 and a usable one is clamped to [0.2, 60]:
        omitted -> 2.0, "nope" -> 2.0, 0 -> 0.2, 1000 ->
        60.0. A several-hundred-digit number is not a
        usable cadence, so by that contract it too must
        land on 2.0.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 11:06 PDT tick) exercised
        runner.transport_extensions.channel.poll_interval
        with the key left unset and varied around it --
        omitted, "nope", 0, 1000, True, False,
        float("inf"), float("nan"), and a huge integer
        (10**400) -- recording the interval or the
        exception each call produced. The huge form is
        reachable from a real config file: load_config
        uses a plain json.load, which parses a
        several-hundred-digit JSON number into an
        arbitrary-precision int, and transports.py's
        _runtime_config hands a transport block's keys to
        its extension verbatim, so
        transport_file.extension_poll_interval_sec reaches
        this reader exactly as written.

    (c) Behavior actually observed: omitted and "nope"
        return the default 2.0, 0 clamps to 0.2, 1000
        clamps to 60.0, and inf/nan clamp to 60.0. The
        huge int does not fall back: poll_interval
        computes float(raw) guarded by
        `except (TypeError, ValueError)` only, and
        float(10**400) raises OverflowError, which
        escapes the reader. The file transport's main()
        calls poll_interval before its pass loop, so the
        extension process dies at startup and the
        supervisor restarts a permanently dead transport.
        Sibling float readers include OverflowError in
        their fallback guard: the core's poll-interval
        reader, parse_sensors (runner/senses.py), and
        _cfg_size (runner/runner.py) all catch it; this
        reader is the outlier -- the same missing-
        OverflowError root cause already recorded for
        the email extension's poll_interval_sec reader in
        TestHugeEmailPollIntervalDefaultsTo20 above, in a
        second reader that family had not covered.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def test_huge_extension_poll_interval_defaults_to_2(self):
        from runner.transport_extensions import channel as ch
        self.assertEqual(
            ch.poll_interval(
                {"extension_poll_interval_sec": 10**400}),
            2.0)

    def test_garbage_extension_poll_interval_defaults_to_2(self):
        # Control: a non-numeric string already lands on
        # the documented default today; it must keep doing
        # so after the huge case is fixed.
        from runner.transport_extensions import channel as ch
        self.assertEqual(
            ch.poll_interval(
                {"extension_poll_interval_sec": "nope"}),
            2.0)


class TestBooleanExtensionPollIntervalDefaultsTo2(unittest.TestCase):
    """Divergence: an extension_poll_interval_sec present as a
    boolean is read as a number -- True becomes a 1.0-second
    cadence and False the 0.2-second clamp floor -- instead
    of falling back to the shared transport channel reader's
    2.0-second default.

    (a) The documented contract: runner/transport_extensions/
        channel.py's poll_interval(cfg, default=2.0) (lines
        151-156) is the one reader every polling transport
        extension takes its cadence from, and its contract --
        stated by its signature default and pinned by the
        repo's own tests/test_transport_shells.py,
        test_poll_interval_clamps_and_rejects_garbage (lines
        84-91) -- is that an unusable value falls back to
        the default 2.0 and a usable one is clamped to
        [0.2, 60]: omitted -> 2.0, "nope" -> 2.0, 0 -> 0.2,
        1000 -> 60.0. A boolean is not a usable cadence:
        every sibling numeric config reader in the codebase
        excludes booleans explicitly -- runner.runner
        ._cfg_size ("Booleans are not sizes"),
        runner.remediation._pos_int / _pos_float, and the
        core poll-interval reader whose boolean fallback to
        its documented default is already pinned in
        TestBooleanPollIntervalDefaultsTo20 above.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 11:16 PDT tick) exercised
        runner.transport_extensions.channel.poll_interval
        with the key left unset and varied around it --
        omitted, explicit None, "nope", 0, -5, 1000,
        float("inf"), float("nan"), a valid 2.5, and the
        booleans True and False -- recording the interval
        each call returned. The boolean forms are reachable
        from a real config file exactly as the huge-int
        form in the class above is: load_config's plain
        json.load parses true / false into Python booleans,
        and transports.py's _runtime_config hands a
        transport block's keys to its extension verbatim.

    (c) Behavior actually observed: omitted, None, and
        "nope" return the default 2.0; 0 and -5 clamp to
        0.2; 1000 and infinity clamp to 60.0; 2.5 is
        honored. The booleans do not fall back:
        poll_interval computes float(raw) with no boolean
        guard, so float(True) is 1.0 -- inside the clamp
        range, returned as a 1.0-second cadence -- and
        float(False) is 0.0, clamped up to the 0.2-second
        floor. Neither is the documented default 2.0: a
        boolean typo in a transport block silently runs
        that extension's poll loop at one second (true) or
        at the fastest cadence the clamp allows (false)
        instead of the default every unusable value gets.
        This is the campaign's known boolean-as-number
        family -- numeric config getters accepting a Python
        boolean as 1/0 instead of falling back to the
        documented default -- in the one reader the
        family's extension-poll coverage (the huge/garbage
        class above, a different root cause) had not
        covered for booleans. Observed on 2026-10-23:
        poll_interval({"extension_poll_interval_sec":
        True}) returned 1.0 and poll_interval(
        {"extension_poll_interval_sec": False}) returned
        0.2.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def test_true_extension_poll_interval_defaults_to_2(self):
        from runner.transport_extensions import channel as ch
        self.assertEqual(
            ch.poll_interval(
                {"extension_poll_interval_sec": True}),
            2.0)

    def test_false_extension_poll_interval_defaults_to_2(self):
        from runner.transport_extensions import channel as ch
        self.assertEqual(
            ch.poll_interval(
                {"extension_poll_interval_sec": False}),
            2.0)


class TestBooleanKeyPolicyMaxTimeoutIsConfigError(unittest.TestCase):
    """Divergence: a key_policies entry's max_timeout_sec
    present as boolean true silently becomes a 1-second
    timeout cap for that key, instead of the startup
    config error every other malformed value in that
    policy gets.

    (a) The documented contract: PROTOCOL.md section 14.1
        (lines 1019, 1034) defines max_timeout_sec as a
        numeric cap -- the example is 600 -- that "the
        job's effective timeout must not exceed".
        runner.runner.build_key_policies, the reader that
        validates these policies, states the rest in its
        own docstring: "Malformed policies fail closed at
        startup." Its error strings carry that contract:
        a value int() cannot parse raises RuntimeError
        "config error: key_policies[<id>].max_timeout_sec
        must be a number", and a parsed value below 1
        raises "... must be >= 1". In the very same
        function, the sibling max_args field refuses a
        boolean explicitly -- `isinstance(cap, bool) or
        not isinstance(cap, int)` raises "must be an
        integer >= 0" -- because in this config format a
        boolean is a distinct type, never a number. No
        document gives boolean true a meaning as a
        1-second cap.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 11:21 PDT tick) exercised
        runner.runner.build_key_policies with a policy
        carrying only max_timeout_sec, varied around the
        documented example -- omitted (no cap), explicit
        600, explicit None, a non-numeric string
        ("bogus"), 0, -5, float("inf"), a huge integer
        (10**400), and the booleans True and False -- and
        then fed the true-derived policy to
        check_key_policy with a job whose timeout_sec
        is 10, recording the cleaned policy or the
        exception each value produced.

    (c) Behavior actually observed: no cap when omitted;
        600 and the huge integer are honored as numbers;
        "bogus", None, and infinity raise the documented
        RuntimeError "must be a number"; 0 and -5 raise
        "must be >= 1". False also raises "must be >= 1"
        (it converts to 0 first, so it fails closed, if
        for the wrong stated reason). True does not
        raise at all: build_key_policies computes
        int(pol["max_timeout_sec"]) with no boolean
        guard (runner/runner.py, the max_timeout_sec
        branch of build_key_policies), so True cleans
        to the integer 1, and check_key_policy then
        rejects a 10-second job for that key with
        "timeout 10s exceeds this key's limit of 1s" --
        a boolean typo in a least-privilege policy
        silently throttles that key to one-second jobs
        instead of failing closed at startup like every
        other malformed value. This is the campaign's
        known boolean-as-number family -- numeric config
        getters accepting a Python boolean as 1/0 -- in a
        reader that family's key-policy coverage (the
        null/bogus default_timeout_sec class above,
        which exercises the separate check_key_policy
        consumer) had not covered. Observed on
        2026-10-23: build_key_policies({"key_policies":
        {"k1": {"max_timeout_sec": True}}}) returned
        {"k1": {"max_timeout_sec": 1}}.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def test_true_max_timeout_sec_is_config_error(self):
        from runner.runner import build_key_policies
        with self.assertRaises(RuntimeError):
            build_key_policies(
                {"key_policies": {"k1": {"max_timeout_sec": True}}})

    def test_false_max_timeout_sec_is_config_error(self):
        # Control: False already raises a RuntimeError
        # config error today (via the >= 1 check, after
        # converting to 0); it must keep raising after
        # the True case is fixed.
        from runner.runner import build_key_policies
        with self.assertRaises(RuntimeError):
            build_key_policies(
                {"key_policies": {"k1": {"max_timeout_sec": False}}})

    def test_explicit_600_max_timeout_sec_is_honored(self):
        # Control: the documented example value must keep
        # cleaning to itself after the boolean case is
        # fixed.
        from runner.runner import build_key_policies
        self.assertEqual(
            build_key_policies(
                {"key_policies": {"k1": {"max_timeout_sec": 600}}}),
            {"k1": {"max_timeout_sec": 600}})


class TestBooleanGrepMaxMatchesDefaultsTo10(unittest.TestCase):
    """Divergence: a grep query's max_matches present as a
    boolean caps the answer at 1 line (true) or 0 lines
    (false) instead of the default limit of 10 that an
    omitted or unparseable value gets.

    (a) Doc claim: PROTOCOL.md (line 486) shows the grep
        query in its section 10 example with
        "max_matches": 10, and line 655 defines the op as
        "grep (regex over retained stdout+stderr, up to
        `max_matches` lines)". docs/fuzzing.md (lines
        129-131) states the two ends of the contract: "A
        `max_matches` of zero returns no lines" -- an
        explicit numeric zero -- and "A later grep with
        the default limit still returns the canary" --
        a default limit exists and applies when the
        caller does not supply a usable number. The
        reader's own code carries that default twice:
        int(q.get("max_matches", 10)) and an except
        fallback of 10 (runner/runner.py line 3008 and
        the lines just below it). No document gives a
        boolean a meaning as a 1-line or 0-line cap.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 11:26 PDT tick) exercised
        runner.runner.answer_queries with one grep query
        over retained output holding 15 matching lines,
        varying only max_matches around the documented
        default -- omitted, explicit None, the string
        "bogus", explicit 2, explicit 0, a huge integer
        (10**400), and the booleans True and False --
        recording how many matches each answer carried.

    (c) Behavior actually observed: omitted, None, and
        "bogus" all return 10 matches (the documented
        default, truncated True); explicit 2 returns 2
        and explicit 0 returns 0, as documented; the
        huge integer clamps to the reader's 100 ceiling
        and returns all 15. True and False do not reach
        the default: the read is int(q.get("max_matches",
        10)) guarded only by (TypeError, ValueError,
        OverflowError), Python's bool is a subclass of
        int, so int(True) is 1 and int(False) is 0 --
        true silently caps the answer at a single line
        and false silently returns no lines at all, the
        behavior docs/fuzzing.md reserves for an
        explicit numeric zero. This is the campaign's
        known boolean-as-number family -- numeric
        getters accepting a Python boolean as 1/0
        instead of falling back to the documented
        default -- in the query-answer reader, which
        that family's config-key coverage had not
        exercised. Observed on 2026-10-23:
        answer_queries with max_matches True returned
        1 match and with False returned 0, against 15
        matching retained lines.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    _RES = {"stdout": "\n".join(
        "ERROR line %d" % i for i in range(15)) + "\n",
            "stderr": "", "exit_code": 0}

    def _grep_count(self, extra):
        from runner.runner import answer_queries
        q = {"op": "grep", "pattern": "ERROR"}
        q.update(extra)
        answers, _spent = answer_queries(
            [q], self._RES, None, 8, cfg=None, view="full")
        return len(answers[0].get("matches", []))

    def test_true_max_matches_defaults_to_10(self):
        self.assertEqual(
            self._grep_count({"max_matches": True}), 10)

    def test_false_max_matches_defaults_to_10(self):
        self.assertEqual(
            self._grep_count({"max_matches": False}), 10)

    def test_bogus_max_matches_defaults_to_10(self):
        # Control: an unparseable value already lands on
        # the documented default today; it must keep
        # doing so after the boolean cases are fixed.
        self.assertEqual(
            self._grep_count({"max_matches": "bogus"}), 10)

    def test_explicit_zero_max_matches_returns_no_lines(self):
        # Control: docs/fuzzing.md documents an explicit
        # numeric zero as returning no lines; the fix
        # must not flatten a genuine zero to the default.
        self.assertEqual(
            self._grep_count({"max_matches": 0}), 0)


class TestBooleanTailLinesDefaultsTo20(unittest.TestCase):
    """Divergence: a tail query's lines present as a
    boolean returns 1 line (true) or 0 lines (false)
    instead of the default 20 lines that an omitted or
    unparseable value gets.

    (a) Doc claim: PROTOCOL.md (line 655) defines the
        tail op as "`tail` (`lines`: last N lines)" over
        the retained output. The reader's own code
        carries the default twice: int(q.get("lines",
        20)) and an except fallback of 20
        (runner/runner.py, the tail branch of
        answer_queries, lines 3030-3034), and it treats
        an explicit numeric zero as a distinct value --
        the tail expression returns no lines only when
        n is zero, paralleling docs/fuzzing.md
        (lines 129-131), which reserves "returns no
        lines" for an explicit numeric zero in the
        sibling grep op and describes a default limit
        applying otherwise. No document gives a boolean
        a meaning as a 1-line or 0-line tail.

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 11:36 PDT tick)
        exercised runner.runner.answer_queries with one
        tail query over retained output holding 25
        lines, varying only lines around the default --
        omitted, explicit None, the string "bogus",
        float("inf"), a huge integer (10**400),
        explicit 2, explicit 0, and the booleans True
        and False -- recording how many lines each
        answer carried.

    (c) Behavior actually observed: omitted, None,
        "bogus", and infinity all return 20 lines (the
        default); explicit 2 returns 2 and explicit 0
        returns 0, as documented; the huge integer
        clamps to the reader's 200 ceiling and returns
        all 25. True and False do not reach the
        default: the read is int(q.get("lines", 20))
        guarded only by (TypeError, ValueError,
        OverflowError), Python's bool is a subclass of
        int, so int(True) is 1 and int(False) is 0 --
        true silently returns only the last line and
        false silently returns no lines at all, the
        behavior reserved for an explicit numeric
        zero. This is the campaign's known
        boolean-as-number family -- numeric getters
        accepting a Python boolean as 1/0 instead of
        falling back to the documented default -- in
        the tail branch of the query-answer reader,
        which the grep branch coverage in the class
        above had not exercised. Observed on
        2026-10-23: answer_queries with lines True
        returned 1 line and with False returned 0,
        against 25 retained lines.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    _RES = {"stdout": "\n".join(
        "line %d" % i for i in range(25)) + "\n",
            "stderr": "", "exit_code": 0}

    def _tail_count(self, extra):
        from runner.runner import answer_queries
        q = {"op": "tail"}
        q.update(extra)
        answers, _spent = answer_queries(
            [q], self._RES, None, 8, cfg=None, view="full")
        return len(answers[0].get("lines", []))

    def test_true_lines_defaults_to_20(self):
        self.assertEqual(
            self._tail_count({"lines": True}), 20)

    def test_false_lines_defaults_to_20(self):
        self.assertEqual(
            self._tail_count({"lines": False}), 20)

    def test_bogus_lines_defaults_to_20(self):
        # Control: an unparseable value already lands on
        # the default today; it must keep doing so after
        # the boolean cases are fixed.
        self.assertEqual(
            self._tail_count({"lines": "bogus"}), 20)

    def test_explicit_zero_lines_returns_no_lines(self):
        # Control: an explicit numeric zero already
        # returns no lines today (the tail expression
        # special-cases zero); the fix must not flatten
        # a genuine zero to the default.
        self.assertEqual(
            self._tail_count({"lines": 0}), 0)



class TestBooleanSensesLimitDefaultsTo20(unittest.TestCase):
    """Divergence: a senses query's limit present as a
    boolean returns 1 alert (true) or every stored alert
    (false) instead of the default limit of 20 that an
    omitted or unparseable value gets.

    (a) Doc claim: docs/senses.md (line 322, "Reading
        signals: the senses query op") shows the senses
        query with "limit": 20, the value the reader
        itself uses as its default: runner/runner.py,
        the senses branch of answer_queries, reads
        limit=q.get("limit") if isinstance(
        q.get("limit"), int) else 20 -- an omitted,
        null, or non-integer limit lands on 20. No
        document gives a boolean a meaning as a 1-alert
        cap or as an unlimited read.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 12:06 PDT tick) exercised
        runner.runner.answer_queries with one senses
        query over a store holding 25 alerts, varying
        only limit around the documented default --
        omitted, explicit None, the string "bogus", a
        huge integer (10**400), explicit 2, explicit 0,
        and the booleans True and False -- recording
        how many alerts each answer carried.

    (c) Behavior actually observed: omitted, None, and
        "bogus" all return 20 alerts (the documented
        default); explicit 2 returns 2, as documented;
        the huge integer returns all 25. True and False
        do not reach the default: the read is
        isinstance(q.get("limit"), int), Python's bool
        is a subclass of int, so True passes as the
        integer 1 and False passes as the integer 0 --
        and the store reader then treats 1 as a 1-alert
        cap and 0, via its out[-0:] slice, as no cap at
        all. True silently caps the answer at a single
        alert and False silently returns every stored
        alert. This is the campaign's known
        boolean-as-number family -- numeric getters
        accepting a Python boolean as 1/0 instead of
        falling back to the documented default -- in
        the senses branch of the query-answer reader,
        which that family's grep and tail coverage had
        not exercised. Observed on 2026-10-23:
        answer_queries with limit True returned 1
        alert and with False returned 25, against 25
        stored alerts.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    _RES = {"stdout": "", "stderr": "", "exit_code": 0}

    def _senses_count(self, extra):
        import os
        from runner.runner import answer_queries
        with tempfile.TemporaryDirectory() as base:
            with open(os.path.join(base, "senses.jsonl"),
                      "w", encoding="utf-8") as fh:
                for i in range(25):
                    fh.write(json.dumps({
                        "sensor": "host_ids",
                        "severity": "info",
                        "title": "alert %d" % i,
                        "detail": {},
                        "observed_at": "2026-10-23T00:00:00Z",
                        "received_at": "2026-10-23T00:00:00Z",
                    }) + "\n")
            q = {"op": "senses"}
            q.update(extra)
            answers, _spent = answer_queries(
                [q], self._RES, None, 8, cfg={}, view="full",
                base_dir=base)
            return len(answers[0].get("alerts", []))

    def test_true_limit_defaults_to_20(self):
        self.assertEqual(
            self._senses_count({"limit": True}), 20)

    def test_false_limit_defaults_to_20(self):
        self.assertEqual(
            self._senses_count({"limit": False}), 20)

    def test_bogus_limit_defaults_to_20(self):
        # Control: an unparseable value already lands on
        # the documented default today; it must keep
        # doing so after the boolean cases are fixed.
        self.assertEqual(
            self._senses_count({"limit": "bogus"}), 20)

    def test_explicit_two_limit_is_honored(self):
        # Control: an explicit numeric limit is honored
        # today; the fix must not flatten a genuine
        # small limit to the default.
        self.assertEqual(
            self._senses_count({"limit": 2}), 2)


class TestBooleanAskMaxCharsDefaultsTo2000(unittest.TestCase):
    """Divergence: an ask query's max_chars present as a
    boolean true truncates the answer to 1 character
    instead of the default 2000 that an omitted or
    unparseable value gets.

    (a) Doc claim: PROTOCOL.md (line 678) gives the
        inference config "`max_answer_chars` (default
        2000)", and docs/configuring-oracle.md (line 43)
        repeats "`max_answer_chars` (default 2000 --
        answers are truncated past this)". PROTOCOL.md
        (line 697) shows the ask query carrying
        "max_chars": 500, and (line 704) step 1 of its
        sanitization pipeline is "Truncate to
        `max_chars`." The reader's own code carries the
        default as its fallback: runner/runner.py, the
        ask branch of answer_queries (lines 3043-3046),
        reads int(q.get("max_chars") or
        inf["max_answer_chars"]) and on (TypeError,
        ValueError, OverflowError) falls back to
        inf["max_answer_chars"], which is 2000 unless
        configured otherwise. A sibling reader in the
        same file, _run_oracle_tool's read_file branch,
        explicitly rejects a boolean cap -- "if
        isinstance(raw_cap, bool): max_chars = 4000",
        its own default. No document gives a boolean a
        meaning as a 1-character cap.

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 12:11 PDT tick)
        exercised runner.runner.answer_queries with one
        ask query over retained output, with a loopback
        inference config whose max_answer_chars is the
        documented 2000, patching ask_model only to
        capture the max_chars it was handed, varying
        only max_chars around the default -- omitted,
        explicit None, the string "bogus",
        float("inf"), a huge integer (10**400),
        explicit 500, explicit 0, and the booleans True
        and False -- recording the cap each run used.

    (c) Behavior actually observed: omitted, None,
        "bogus", infinity, and explicit 0 all use 2000
        (the documented default -- zero goes through the
        same "or" fallback); explicit 500 is honored, as
        documented. True does not reach the default: the
        read is int(q.get("max_chars") or
        inf["max_answer_chars"]) guarded only by
        (TypeError, ValueError, OverflowError), Python's
        bool is a subclass of int, so int(True) is 1 --
        true silently truncates the answer to a single
        character. False happens to land on 2000 today
        only because the "or" treats it as missing. This
        is the campaign's known boolean-as-number
        family -- numeric getters accepting a Python
        boolean as 1/0 instead of falling back to the
        documented default -- in the ask branch of the
        query-answer reader, which that family's grep,
        tail, and senses coverage had not exercised.
        Observed on 2026-10-23: answer_queries with
        max_chars True handed ask_model a cap of 1,
        against the documented default of 2000.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    _CFG = {"inference": {
        "endpoint": "http://127.0.0.1:11434/v1",
        "model": "qwen3:1.7b"}}
    _RES = {"stdout": "hello\n", "stderr": "",
            "exit_code": 0}

    def _ask_cap(self, extra):
        from unittest import mock
        import runner.runner as runner_mod
        captured = {}

        def fake(inf, question, text, max_chars,
                 patterns, instructions=None):
            captured["max_chars"] = max_chars
            return {"op": "ask", "answer": "ok",
                    "model": inf["model"],
                    "sanitized": True}

        q = {"op": "ask", "question": "why?"}
        q.update(extra)
        with mock.patch.object(runner_mod, "ask_model",
                               fake):
            answers, _spent = runner_mod.answer_queries(
                [q], self._RES, None, 8, cfg=self._CFG,
                view="full")
        self.assertEqual(answers[0].get("op"), "ask")
        return captured["max_chars"]

    def test_true_max_chars_defaults_to_2000(self):
        self.assertEqual(
            self._ask_cap({"max_chars": True}), 2000)

    def test_false_max_chars_defaults_to_2000(self):
        self.assertEqual(
            self._ask_cap({"max_chars": False}), 2000)

    def test_bogus_max_chars_defaults_to_2000(self):
        # Control: an unparseable value already lands on
        # the documented default today; it must keep
        # doing so after the boolean case is fixed.
        self.assertEqual(
            self._ask_cap({"max_chars": "bogus"}), 2000)

    def test_explicit_500_max_chars_is_honored(self):
        # Control: PROTOCOL.md's own example value is
        # honored today; the fix must not flatten a
        # genuine explicit cap to the default.
        self.assertEqual(
            self._ask_cap({"max_chars": 500}), 500)


class TestBooleanPlanStepTimeoutCountsAs60(unittest.TestCase):
    """Divergence: a plan step whose timeout_sec is
    boolean true is counted as 1 second toward the
    documented plan timeout cap, instead of the
    60 seconds an omitted or unparseable step
    timeout counts as.

    (a) Doc claim: docs/configuring-oracle.md
        (line 68) gives the detection layer's plan
        caps: "`max_plan_steps` /
        `max_plan_timeout_sec` -- caps the detection
        layer (`runner/detection.py`) applies to a
        multi-step plan: at most this many steps
        (default 8) and this much total timeout in
        seconds (default 600)." The total is a sum
        over steps, and the reader's own code states
        the per-step fallback: runner/detection.py,
        check_plan_budget (lines 122-129), computes
        int(step.get("timeout_sec") or 60) and, on
        (TypeError, ValueError, OverflowError), adds
        60 -- a step with no usable timeout counts
        as 60 seconds toward the cap. No document
        gives a boolean a meaning as a 1-second
        step timeout.

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 12:16 PDT tick)
        exercised runner.detection.check_plan_budget
        directly, varying only a step's timeout_sec
        around the reader's fallback -- omitted,
        explicit None, the string "bogus", an
        explicit 45, an explicit 10, and the
        booleans True and False -- against a
        30-second total cap, and again with eleven
        steps under a raised step cap and the
        documented 600-second total cap, recording
        whether each plan was allowed.

    (c) Behavior actually observed: omitted, None,
        and "bogus" all count as 60 (a single such
        step is refused under a 30-second cap, and
        eleven such steps total 660 and are refused
        under the 600 cap); explicit 45 is refused
        and explicit 10 allowed under the 30 cap,
        as given. False also counts as 60 today,
        because the "or 60" treats it as missing.
        True does not: int(step.get("timeout_sec")
        or 60) is int(True) -- Python's bool is a
        subclass of int -- so a true step counts as
        a single second: one true step is allowed
        under a 30-second cap that refuses the
        fallback step, and eleven true steps total
        11 seconds and pass under the documented
        600 cap that refuses eleven fallback steps.
        The plan budget's own config caps were
        hardened against booleans by earlier
        campaign classes; the per-step timeout read
        in the same function was not. This is the
        campaign's known boolean-as-number family.
        Observed on 2026-10-23: check_plan_budget(
        [{"timeout_sec": True}],
        {"max_plan_timeout_sec": 30}) returned
        (True, ""), where the omitted-timeout step
        returned (False, "plan timeout 60s exceeds
        30s").

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def test_true_step_timeout_counts_as_60(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            [{"timeout_sec": True}],
            {"max_plan_timeout_sec": 30})
        self.assertFalse(ok)
        self.assertIn("exceeds", reason)

    def test_true_steps_total_counts_as_60_each(self):
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            [{"timeout_sec": True}] * 11,
            {"max_plan_steps": 20,
             "max_plan_timeout_sec": 600})
        self.assertFalse(ok)
        self.assertIn("exceeds", reason)

    def test_false_step_timeout_counts_as_60(self):
        # Control: false already counts as the
        # 60-second fallback today (the "or" treats
        # it as missing); it must keep doing so after
        # the true case is fixed.
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            [{"timeout_sec": False}],
            {"max_plan_timeout_sec": 30})
        self.assertFalse(ok)
        self.assertIn("exceeds", reason)

    def test_bogus_step_timeout_counts_as_60(self):
        # Control: an unparseable step timeout already
        # counts as 60 today; it must keep doing so.
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            [{"timeout_sec": "bogus"}],
            {"max_plan_timeout_sec": 30})
        self.assertFalse(ok)
        self.assertIn("exceeds", reason)

    def test_explicit_10_step_timeout_is_honored(self):
        # Control: a genuine explicit step timeout is
        # counted as given; the fix must not flatten
        # it to the 60-second fallback.
        from runner.detection import check_plan_budget
        ok, reason = check_plan_budget(
            [{"timeout_sec": 10}],
            {"max_plan_timeout_sec": 30})
        self.assertTrue(ok)


class TestNegativeOrNonFiniteSensorWeightDefaultsToOne(unittest.TestCase):
    """Divergence: a stored sensor weight that is negative or
    non-finite (infinity or NaN) is used as-is by the alert
    scorer, instead of falling back to the documented
    default weight of 1.0.

    (a) Doc claim (docs/senses.md, line 254):
        "`weight` (number >= 0, default 1.0): the Oracle's
        weighting for this source. Turn a noisy sensor
        down, a trusted one up, or to 0 to mute it without
        disabling ingest."
        The config validator enforces exactly that domain
        (runner/senses.py, parse_sensors): a weight that
        is NaN, infinite, or below 0 raises a config error
        ("must be a finite number >= 0"). The scorer's own
        fallback for an unparseable weight is likewise the
        default 1.0 (runner/senses.py, alert_score), and
        the sibling senses-query reader in runner/runner.py
        (the answer_queries senses branch) explicitly
        resets a weight that is NaN, negative, or infinite
        to 1.0 before scoring with it.

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 12:56 PDT tick)
        exercised runner.senses.alert_score -- the scorer
        the DRI fused-score path calls with a stored
        record's own raw weight
        (runner/dri.py: rec.get("weight", 1.0)) -- with
        the weight left unset and varied around the
        documented domain: omitted via the caller's
        default, explicit None, a non-numeric string
        ("bogus"), a numeric string ("2"), explicit 0
        (the documented mute), 2, -1, -5, float("inf"),
        float("-inf"), and NaN, scoring an info alert
        (severity score 0.5) each time. The out-of-domain
        forms are reachable from real data: a stored
        sensor alert is sensor-supplied JSON, and the
        runner's JSON parsing admits Infinity / NaN
        literals and negative numbers, so a stored
        record can carry exactly these weights into the
        DRI path, which -- unlike the senses-query path --
        performs no range or finiteness reset before
        calling the scorer.

    (c) Behavior actually observed: omitted, None, and
        "bogus" all score at the documented default (an
        info alert scores 0.5, i.e. 1.0 x 0.5); explicit
        0 scores 0.0 (the documented mute) and 2 scores
        1.0, as given. The out-of-domain values do not
        fall back: alert_score converts with float() and
        checks nothing after the conversion
        (runner/senses.py, alert_score), so -1 scores
        -0.5 and -5 scores -2.5 -- a negative total that
        drags a sensor's fused score down and can keep
        it under the DRI paging threshold; float("inf")
        scores inf, so a single such alert crosses any
        finite fused-score threshold on its own; and
        NaN scores NaN, poisoning the fused total (every
        comparison against a NaN total is false, so the
        trigger silently never fires). Sibling readers
        reject or reset exactly these values --
        parse_sensors in the same module raises on them
        at config time, and the senses-query reader in
        runner.py resets them to 1.0 at read time; this
        scorer is the outlier, and its missing guard is
        a range/finiteness check after conversion, a
        different defect from the boolean and
        huge-integer guards recorded for other readers
        in this file. Observed on 2026-10-23:
        alert_score({"severity": "info"}, -1) returned
        -0.5, alert_score({"severity": "info"},
        float("inf")) returned inf, and
        alert_score({"severity": "info"}, float("nan"))
        returned nan, where the documented default
        weight scores 0.5.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def test_negative_weight_defaults_to_one(self):
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, -1), 0.5)

    def test_large_negative_weight_defaults_to_one(self):
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, -5), 0.5)

    def test_infinite_weight_defaults_to_one(self):
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, float("inf")), 0.5)

    def test_negative_infinite_weight_defaults_to_one(self):
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, float("-inf")), 0.5)

    def test_nan_weight_defaults_to_one(self):
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, float("nan")), 0.5)

    def test_explicit_zero_weight_still_mutes(self):
        # Control: 0 is the documented mute (weight >= 0
        # includes it); the fix must not flatten a
        # genuine zero to the default.
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, 0), 0.0)

    def test_explicit_two_weight_is_honored(self):
        # Control: a genuine in-domain weight is used as
        # given; the fix must not flatten it to 1.0.
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, 2), 1.0)

    def test_bogus_weight_defaults_to_one(self):
        # Control: an unparseable weight already falls
        # back to the documented default today; it must
        # keep doing so after the out-of-domain cases
        # are fixed.
        from runner.senses import alert_score
        self.assertEqual(
            alert_score({"severity": "info"}, "bogus"), 0.5)



class TestNonFinitePiHealthTunableDefaults(unittest.TestCase):
    """Divergence: a non-finite pi-health tunable (inf / NaN)
    silently disables its alert instead of falling back to the
    documented default threshold.

    (a) Doc claim (docs/extensions.md, pi-health table):
        "`board_overheating` | CPU/SoC temperature reaches
        `temp_high_c` (default 80)"; "`disk_pressure` | The
        `disk_mount` mount reaches `disk_high_pct` (default
        90)"; "`memory_pressure` | Available memory falls to
        `mem_avail_low_pct` (default 10)". The extension's own
        header repeats the same defaults.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the pi-health example
        extension's decide() -- the pure decision function --
        with each tunable omitted, set to a genuine value,
        and set to float("inf") and float("nan"), using
        readings that file under the documented defaults
        (temp_c 100, disk 95%, mem_avail 5%).

    (c) Behavior actually observed: omitted tunables file
        as documented and a genuine temp_high_c of 50 is
        honored, but _tunable accepts inf and NaN as numbers
        (_is_number excludes booleans but not non-finite
        floats), so an infinite threshold is never reached
        and every NaN comparison is false: decide() files
        nothing at all. A non-finite tunable therefore
        silences the alert instead of reading as the
        documented default. Sibling readers in this codebase
        exclude non-finite values and fall back to their
        defaults (e.g. runner.remediation._pos_float,
        runner.runner._local_wake_cooldown, the senses
        weight validation); this reader does not. Observed
        on 2026-10-23: decide({"temp_c": 100},
        {"tunables": {"temp_high_c": float("inf")}}, {})
        returned no alerts, where the omitted tunable
        returned board_overheating.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def _decide(self, readings, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "pi-health", "pi_health.py")
        spec = importlib.util.spec_from_file_location(
            "pi_health_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        alerts, _state = mod.decide(
            readings, {"tunables": tunables}, {})
        return [a["signal"] for a in alerts]

    def test_infinite_temp_threshold_defaults_to_80(self):
        self.assertEqual(
            self._decide({"temp_c": 100},
                         {"temp_high_c": float("inf")}),
            ["board_overheating"])

    def test_nan_temp_threshold_defaults_to_80(self):
        self.assertEqual(
            self._decide({"temp_c": 100},
                         {"temp_high_c": float("nan")}),
            ["board_overheating"])

    def test_infinite_disk_threshold_defaults_to_90(self):
        self.assertEqual(
            self._decide({"disk_pct": {"/": 95}},
                         {"disk_high_pct": float("inf")}),
            ["disk_pressure"])

    def test_nan_mem_threshold_defaults_to_10(self):
        self.assertEqual(
            self._decide({"mem_avail_pct": 5},
                         {"mem_avail_low_pct": float("nan")}),
            ["memory_pressure"])

    def test_omitted_and_explicit_thresholds_are_honored(self):
        # Controls: the documented default and a genuine
        # threshold both behave today and must keep doing
        # so after the non-finite cases are fixed.
        self.assertEqual(
            self._decide({"temp_c": 100}, {}),
            ["board_overheating"])
        self.assertEqual(
            self._decide({"temp_c": 60}, {"temp_high_c": 50}),
            ["board_overheating"])
        self.assertEqual(
            self._decide({"temp_c": 60}, {}), [])



if __name__ == "__main__":
    unittest.main()
