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

    (e) Policy moved, 2026-10-24 (Decision 1,
        docs/design/present-but-invalid-config.md, docs first):
        this key is an addressing value, the refuse class. A value
        present but not usable is now a startup config error that
        names the key, never a substituted address; the documented
        default applies only when the key is absent. The assertions
        below changed with the doc lines (docs/configuring-oracle.md,
        docs/TRANSPORTS.md, the extension docstring), not before.
        (Agent-Stamp 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c)
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

    def test_null_port_is_a_config_error(self):
        with self.assertRaises(RuntimeError) as cm:
            self._pipe({"port": None})
        self.assertIn("transport_dtls.port", str(cm.exception))

    def test_bogus_port_is_a_config_error(self):
        with self.assertRaises(RuntimeError) as cm:
            self._pipe({"port": "bogus"})
        self.assertIn("transport_dtls.port", str(cm.exception))

    def test_null_bind_is_a_config_error(self):
        with self.assertRaises(RuntimeError) as cm:
            self._pipe({"bind": None})
        self.assertIn("transport_dtls.bind", str(cm.exception))

    def test_omitted_bind_is_all_interfaces(self):
        # Control: absent still means the documented default.
        import importlib
        import os
        dtls_ext = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        with tempfile.TemporaryDirectory() as tmp:
            pipe = dtls_ext.DtlsPipe(
                {"shared_secret": self._SECRET, "port": 0},
                os.path.join(tmp, "channel"))
        self.addCleanup(pipe.sock.close)
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

    (e) Policy moved, 2026-10-24 (Decision 1,
        docs/design/present-but-invalid-config.md, docs first):
        this key is an addressing value, the refuse class. A value
        present but not usable is now a startup config error that
        names the key, never a substituted address; the documented
        default applies only when the key is absent. The assertions
        below changed with the doc lines (docs/configuring-oracle.md,
        docs/TRANSPORTS.md, the extension docstring), not before.
        (Agent-Stamp 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c)
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

    def test_true_port_is_a_config_error(self):
        with self.assertRaises(RuntimeError) as cm:
            self._pipe({"port": True})
        self.assertIn("transport_dtls.port", str(cm.exception))

    def test_false_port_is_a_config_error(self):
        with self.assertRaises(RuntimeError) as cm:
            self._pipe({"port": False})
        self.assertIn("transport_dtls.port", str(cm.exception))


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

    (e) Policy moved, 2026-10-24 (Decision 1,
        docs/design/present-but-invalid-config.md, docs first):
        this key is an addressing value, the refuse class. A value
        present but not usable is now a startup config error that
        names the key, never a substituted address; the documented
        default applies only when the key is absent. The assertions
        below changed with the doc lines (docs/configuring-oracle.md,
        docs/TRANSPORTS.md, the extension docstring), not before.
        (Agent-Stamp 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c)
    """

    class _Stop(Exception):
        pass

    def _client(self, url):
        import importlib
        nm = importlib.import_module(
            "runner.transport_extensions.nats.__main__")
        return nm.NatsClient(url)

    def test_out_of_range_port_is_a_config_error(self):
        with self.assertRaises(RuntimeError) as cm:
            self._client("nats://127.0.0.1:99999")
        self.assertIn("transport_nats.url", str(cm.exception))

    def test_non_numeric_port_is_a_config_error(self):
        with self.assertRaises(RuntimeError) as cm:
            self._client("nats://127.0.0.1:abc")
        self.assertIn("transport_nats.url", str(cm.exception))

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

    def test_bad_port_refuses_to_start(self):
        # The pipe checks the broker address once, at construction,
        # where main() turns the error into exit 2; the reconnect
        # loop never meets an unusable URL.
        import importlib
        nm = importlib.import_module(
            "runner.transport_extensions.nats.__main__")
        with self.assertRaises(nm.TransportError) as cm:
            nm.NatsPipe(
                {"url": "nats://127.0.0.1:99999",
                 "allow_unauthenticated": True},
                "/tmp/docdef-no-channel", log=lambda *a, **k: None)
        self.assertIn("refuses to start", str(cm.exception))
        self.assertIn("transport_nats.url", str(cm.exception))


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

    (e) Policy moved, 2026-10-24 (Decision 1,
        docs/design/present-but-invalid-config.md, docs first):
        this key is an addressing value, the refuse class. A value
        present but not usable is now a startup config error that
        names the key, never a substituted address; the documented
        default applies only when the key is absent. The assertions
        below changed with the doc lines (docs/configuring-oracle.md,
        docs/TRANSPORTS.md, the extension docstring), not before.
        (Agent-Stamp 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c)
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

    def _refused(self, extra):
        with self.assertRaises(RuntimeError) as cm:
            self._pipe(extra)
        self.assertIn("transport_dtls.port", str(cm.exception))

    def test_bogus_port_is_a_config_error(self):
        self._refused({"port": "bogus"})

    def test_out_of_range_port_is_a_config_error(self):
        self._refused({"port": 99999})

    def test_none_port_is_a_config_error(self):
        self._refused({"port": None})

    def test_huge_port_is_a_config_error(self):
        self._refused({"port": 10**400})

    def test_numeric_string_port_is_read(self):
        # Control: "0" is a usable port written as a string, the
        # hand-written shape config files carry.
        pipe = self._pipe({"port": "0"})
        self.assertEqual(pipe.port, 0)

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




class TestNonFiniteAirwavesGoneAfterScansDefaultsTo3(unittest.TestCase):
    """Divergence: a non-finite airwaves ``gone_after_scans``
    tunable (inf / -inf / NaN) crashes decide() with an
    uncaught OverflowError / ValueError instead of falling
    back to the documented default of 3 scans.

    (a) Doc claim (docs/extensions.md, airwaves table):
        "`access_point_gone` | A long-known AP is missing
        across `gone_after_scans` consecutive scans
        (default 3)". The extension's own manifest repeats
        the same tunable.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the airwaves
        example extension's decide() -- the pure decision
        function -- with a learned baseline holding one
        known AP at 2 recorded misses and an empty scan,
        varying only the ``gone_after_scans`` tunable:
        omitted, a bogus string, an explicit 1, and
        float("inf"), float("-inf") and float("nan").

    (c) Behavior actually observed: omitted and bogus
        tunables file access_point_gone on this third
        consecutive miss, as documented, and an explicit
        1 is honored. The non-finite values never reach a
        decision at all: _gone_after_scans accepts them
        via _is_number (which excludes booleans but not
        non-finite floats) and then evaluates
        int(value), which raises OverflowError for inf /
        -inf and ValueError for NaN; decide() lets the
        exception propagate, so one bad tunable kills the
        whole watcher pass instead of reading as the
        documented default 3. Sibling readers in this
        codebase exclude non-finite values and fall back
        to their defaults (e.g. runner.remediation
        ._pos_float, runner.runner._local_wake_cooldown);
        this reader converts without guarding. Observed
        on 2026-10-23: decide() with tunables
        {"gone_after_scans": float("inf")} raised
        OverflowError ("cannot convert float infinity to
        integer") on a state where the omitted tunable
        returned ["access_point_gone"].

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    _STATE = {"learned": True,
              "aps": {"AA:BB:CC:DD:EE:FF": {
                  "ssid": "Home", "security": "WPA2",
                  "rank": 3, "misses": 2}},
              "ssids": {"Home": {
                  "bssids": ["AA:BB:CC:DD:EE:FF"], "rank": 3}},
              "link": None}

    def _decide(self, tunables):
        import copy
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "airwaves", "airwaves.py")
        spec = importlib.util.spec_from_file_location(
            "airwaves_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        alerts, _state = mod.decide(
            {"scan_ok": True, "scan": [], "link": None,
             "now": 0},
            {"tunables": tunables}, copy.deepcopy(self._STATE))
        return [a["signal"] for a in alerts]

    def test_infinite_gone_after_scans_defaults_to_3(self):
        self.assertEqual(
            self._decide({"gone_after_scans": float("inf")}),
            ["access_point_gone"])

    def test_negative_infinite_gone_after_scans_defaults_to_3(self):
        self.assertEqual(
            self._decide({"gone_after_scans": float("-inf")}),
            ["access_point_gone"])

    def test_nan_gone_after_scans_defaults_to_3(self):
        self.assertEqual(
            self._decide({"gone_after_scans": float("nan")}),
            ["access_point_gone"])

    def test_omitted_and_bogus_gone_after_scans_default_to_3(self):
        # Controls: the documented default and an
        # unparseable value already behave today and must
        # keep doing so after the non-finite cases are
        # fixed.
        self.assertEqual(self._decide({}), ["access_point_gone"])
        self.assertEqual(
            self._decide({"gone_after_scans": "bogus"}),
            ["access_point_gone"])

    def test_explicit_one_gone_after_scans_is_honored(self):
        # Control: a genuine in-domain value is used as
        # given; the fix must not flatten it to 3.
        import copy
        state = copy.deepcopy(self._STATE)
        state["aps"]["AA:BB:CC:DD:EE:FF"]["misses"] = 0
        orig = self._STATE
        try:
            self._STATE = state
            self.assertEqual(
                self._decide({"gone_after_scans": 1}),
                ["access_point_gone"])
        finally:
            self._STATE = orig




class TestNonFiniteSkyWatcherApproachRadiusDefaultsTo5000(unittest.TestCase):
    """Divergence: a non-finite sky-watcher approach_radius_km
    (inf / -inf / NaN) makes the corridor boundless or empty
    instead of falling back to the documented 5000 km default.

    (a) Doc claim (docs/extensions.md, sky-watcher signal
        table, line 530): "`station_approaching` | The station
        enters the approach corridor (`approach_radius_km`,
        default 5000 km) around the observer -- every pass,
        visible or not".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the sky-watcher
        example extension's update() -- the pure pass state
        machine -- with an observer at (0, 0), the tunable
        omitted, set to genuine values, and set to
        float("inf"), float("-inf"), and float("nan"), using
        a far sample (station sub-point at (0, 90), about
        10,007 km away, outside the documented 5000 km
        corridor) and a near sample (sub-point at the
        observer, distance 0).

    (c) Behavior actually observed: the omitted tunable
        files as documented (far sample files nothing, near
        sample files station_approaching) and explicit radii
        are honored (100 km files nothing for a sample about
        111 km away; 20000 km files for the far sample), but
        _tunable accepts inf and NaN as numbers (_is_number
        excludes booleans but not non-finite floats): with
        inf or NaN no distance is ever greater than the
        radius, so the far sample files station_approaching
        from halfway around the planet, and with -inf every
        distance is greater, so even a station directly
        overhead files nothing. A non-finite radius therefore
        makes the corridor boundless or empty instead of
        reading as the documented default. Sibling readers
        in this codebase exclude non-finite values and fall
        back to their defaults (e.g.
        runner.remediation._pos_float,
        runner.runner._local_wake_cooldown); this reader
        does not. Observed on 2026-10-23: update() with
        approach_radius_km float("inf") and float("nan")
        returned ["station_approaching"] for the far sample
        where the omitted tunable returned [], and with
        float("-inf") returned [] for the near sample where
        the omitted tunable returned ["station_approaching"].

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def _signals(self, lat, lon, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "sky-watcher",
            "sky_watcher.py")
        spec = importlib.util.spec_from_file_location(
            "sky_watcher_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sample = {"lat": lat, "lon": lon, "alt_km": 420,
                  "velocity_kmh": 27576, "sunlit": False,
                  "ts": 1700000000}
        manifest = {"name": "sky_watcher",
                    "tunables": {"observer_lat": 0,
                                 "observer_lon": 0, **tunables}}
        alerts, _state = mod.update(sample, manifest, {})
        return [a["signal"] for a in alerts]

    def test_infinite_radius_defaults_to_5000(self):
        self.assertEqual(
            self._signals(0, 90,
                          {"approach_radius_km": float("inf")}),
            [])

    def test_nan_radius_defaults_to_5000(self):
        self.assertEqual(
            self._signals(0, 90,
                          {"approach_radius_km": float("nan")}),
            [])

    def test_negative_infinite_radius_defaults_to_5000(self):
        self.assertEqual(
            self._signals(0, 0,
                          {"approach_radius_km": float("-inf")}),
            ["station_approaching"])

    def test_omitted_and_explicit_radii_are_honored(self):
        # Controls: the documented default and genuine radii
        # already behave today and must keep doing so after
        # the non-finite cases are fixed.
        self.assertEqual(self._signals(0, 90, {}), [])
        self.assertEqual(
            self._signals(0, 0, {}), ["station_approaching"])
        self.assertEqual(
            self._signals(0, 1, {"approach_radius_km": 100}),
            [])
        self.assertEqual(
            self._signals(0, 90, {"approach_radius_km": 20000}),
            ["station_approaching"])




class TestNonFiniteSkyWatcherDarkThresholdDefaultsToMinus6(unittest.TestCase):
    """Divergence: a non-finite sky-watcher
    dark_sun_elevation_deg (inf / -inf / NaN) makes every sky
    "dark" or no sky ever "dark" instead of falling back to
    the documented -6 degree default.

    (a) Doc claim (docs/extensions.md, "The example: Sky
        Watcher", line 542): "the observer's sky being dark
        is a small solar calculation (the NOAA approximation)
        against the `dark_sun_elevation_deg` threshold, -6°
        by default."

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the sky-watcher
        example extension's update() -- the pure pass state
        machine -- with an observer at (0, 0), a sunlit
        equatorial zenith pass already inside the approach
        corridor (previous sub-point (0, -44), current
        sub-point (0, -43), alt 420 km, culmination 90 deg,
        window opening in about 470 s, inside the documented
        600 s lead), the tunable omitted, set to genuine
        values, and set to float("inf"), float("-inf"), and
        float("nan"), at a midnight epoch (sun elevation
        about -66.9 deg at the observer) and a midday epoch
        (sun elevation about +66.9 deg).

    (c) Behavior actually observed: the omitted tunable
        files as documented (midnight files
        visible_pass_starting and bright_pass; midday files
        neither) and explicit thresholds are honored (-70
        files nothing at midnight; 70 files both at midday),
        but _tunable accepts inf and NaN as numbers
        (_is_number excludes booleans but not non-finite
        floats) and update() compares the sun's elevation
        against the result directly: with NaN or -inf no
        sun elevation is ever below the threshold, so the
        midnight pass files nothing, and with inf every sun
        elevation is below it, so the midday pass files
        visible_pass_starting and bright_pass in full
        daylight. A non-finite threshold therefore makes
        the sky permanently dark or never dark instead of
        reading as the documented -6 degree default.
        Sibling readers in this codebase exclude non-finite
        values and fall back to their defaults (e.g.
        runner.remediation._pos_float,
        runner.runner._local_wake_cooldown); this reader
        does not. Observed on 2026-10-23: update() at
        midnight with dark_sun_elevation_deg float("nan")
        and float("-inf") returned [] where the omitted
        tunable returned ["visible_pass_starting",
        "bright_pass"], and at midday with float("inf")
        returned ["visible_pass_starting", "bright_pass"]
        where the omitted tunable returned [].

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    MIDNIGHT = 1704067200  # 2024-01-01T00:00Z, sun ~-66.9 deg
    MIDDAY = 1704110400  # 2024-01-01T12:00Z, sun ~+66.9 deg

    def _signals(self, ts, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "sky-watcher",
            "sky_watcher.py")
        spec = importlib.util.spec_from_file_location(
            "sky_watcher_dark_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        prev = {"lat": 0, "lon": -44, "alt_km": 420,
                "velocity_kmh": 27576, "sunlit": True,
                "ts": ts}
        sample = {"lat": 0, "lon": -43, "alt_km": 420,
                  "velocity_kmh": 27576, "sunlit": True,
                  "ts": ts + 60}
        state = {"stage": "approaching", "pass_id": 1,
                 "fired": ["station_approaching"],
                 "prev": prev, "culmination_deg": None,
                 "last_ts": ts}
        manifest = {"name": "sky_watcher",
                    "tunables": {"observer_lat": 0,
                                 "observer_lon": 0, **tunables}}
        alerts, _state = mod.update(sample, manifest, state)
        return [a["signal"] for a in alerts]

    def test_nan_dark_threshold_defaults_to_minus_6(self):
        self.assertEqual(
            self._signals(self.MIDNIGHT,
                          {"dark_sun_elevation_deg":
                           float("nan")}),
            ["visible_pass_starting", "bright_pass"])

    def test_negative_infinite_dark_threshold_defaults(self):
        self.assertEqual(
            self._signals(self.MIDNIGHT,
                          {"dark_sun_elevation_deg":
                           float("-inf")}),
            ["visible_pass_starting", "bright_pass"])

    def test_infinite_dark_threshold_defaults_to_minus_6(self):
        self.assertEqual(
            self._signals(self.MIDDAY,
                          {"dark_sun_elevation_deg":
                           float("inf")}),
            [])

    def test_omitted_and_explicit_thresholds_are_honored(self):
        # Controls: the documented default and genuine
        # thresholds already behave today and must keep
        # doing so after the non-finite cases are fixed.
        self.assertEqual(
            self._signals(self.MIDNIGHT, {}),
            ["visible_pass_starting", "bright_pass"])
        self.assertEqual(self._signals(self.MIDDAY, {}), [])
        self.assertEqual(
            self._signals(self.MIDNIGHT,
                          {"dark_sun_elevation_deg": -70}),
            [])
        self.assertEqual(
            self._signals(self.MIDDAY,
                          {"dark_sun_elevation_deg": 70}),
            ["visible_pass_starting", "bright_pass"])



class TestInfiniteCertSentinelDaysDefaults(unittest.TestCase):
    """Divergence: an infinite cert-sentinel day threshold
    (warn_days / critical_days = +inf) files expiry alerts
    for certificates a year from expiry instead of falling
    back to the documented defaults.

    (a) Doc claim (examples/extensions/cert-sentinel/
        cert_sentinel.py header, lines 13-16, repeated in
        the extension README lines 29-30, its extension.json
        tunables, and the docs/extensions.md table at line
        594): "cert_expiring  a certificate's remaining life
        fell to the warn_days tunable (default 30) or
        below"; "cert_critical  a certificate's remaining
        life fell to the critical_days tunable (default 7)
        or below, or it has already expired".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the cert-sentinel
        example extension's decide() -- the pure decision
        function -- with each day tunable omitted, set to a
        genuine value, and set to float("inf"),
        float("-inf") and float("nan"), using a certificate
        365 days from expiry (far outside both documented
        bands) plus in-band controls at 20 and 5 days.

    (c) Behavior actually observed: omitted tunables file
        nothing at 365 days and file as documented at 20
        (cert_expiring) and 5 days (cert_critical), and a
        genuine warn_days of 400 is honored. NaN and -inf
        also fall back, because the reader's `value >= 0`
        check is false for them. But _tunable_days accepts
        +inf as a number (_is_number excludes booleans but
        not non-finite floats, and inf >= 0 holds), so
        warn_days=inf puts every certificate in the warn
        band and critical_days=inf puts every certificate
        in the critical band: decide() files cert_expiring
        / cert_critical for a certificate with a year of
        life left instead of reading the tunable as the
        documented default. Sibling readers in this
        codebase exclude non-finite values and fall back
        to their defaults; this reader does not. Observed
        on 2026-10-23: decide() on a 365-day certificate
        with {"warn_days": float("inf")} returned
        ['cert_expiring'] and with {"critical_days":
        float("inf")} returned ['cert_critical'], where
        the omitted tunables returned no alerts.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    NOW = 1_800_000_000.0

    def _signals(self, tunables, days_left=365):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "cert-sentinel",
            "cert_sentinel.py")
        spec = importlib.util.spec_from_file_location(
            "cert_sentinel_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        readings = {"now": self.NOW, "certs": [{
            "source": "example.com",
            "subject": "CN=example.com", "issuer": "CN=CA",
            "serial": "01",
            "not_after": self.NOW + days_left * 86400.0}]}
        alerts, _state = mod.decide(
            readings, {"tunables": tunables}, {})
        return [a["signal"] for a in alerts]

    def test_infinite_warn_days_defaults_to_30(self):
        self.assertEqual(
            self._signals({"warn_days": float("inf")}), [])

    def test_infinite_critical_days_defaults_to_7(self):
        self.assertEqual(
            self._signals({"critical_days": float("inf")}),
            [])

    def test_omitted_and_explicit_thresholds_are_honored(self):
        # Controls: the documented defaults and a genuine
        # threshold already behave today and must keep
        # doing so after the non-finite cases are fixed.
        self.assertEqual(self._signals({}), [])
        self.assertEqual(
            self._signals({}, 20), ["cert_expiring"])
        self.assertEqual(
            self._signals({}, 5), ["cert_critical"])
        self.assertEqual(
            self._signals({"warn_days": 400}),
            ["cert_expiring"])
        self.assertEqual(
            self._signals({"warn_days": float("nan")}), [])
        self.assertEqual(
            self._signals({"critical_days": float("nan")}),
            [])


class TestInfiniteLogSentinelTunablesCrashInsteadOfDefault(unittest.TestCase):
    """Divergence: an infinite log-sentinel integer tunable
    (cooldown_sec / max_alerts_per_pass / tail_bytes = +inf)
    crashes the pass with OverflowError instead of falling
    back to the documented defaults.

    (a) Doc claim (examples/extensions/log-sentinel/README.md
        lines 27-30 and 79, repeated in the extension's
        extension.json tunables): "further matches of the
        same subject inside `cooldown_sec` (default 3600)
        are suppressed"; "at most `max_alerts_per_pass`
        alerts (default 10) file per pass"; "`tail_bytes`
        down \u2014 65536 by default".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the log-sentinel
        example extension's decide() -- the pure decision
        function -- and its read_new_lines() reader with
        each integer tunable omitted, set to a genuine
        value, and set to float("inf"), float("-inf") and
        float("nan"), using one OOM line (files under the
        omitted defaults), a prior firing 100 and 4000
        seconds before `now` (inside and outside the
        documented 3600 cooldown), and twelve distinct
        configured-pattern hits (past the documented cap
        of 10).

    (c) Behavior actually observed: omitted tunables file
        the OOM alert, suppress a refire 100 seconds later,
        file again at 4000 seconds, and cap twelve pattern
        hits at 10 alerts, and genuine values are honored.
        NaN and -inf also fall back, because the reader's
        `value >= minimum` check is false for them. But
        _int_tunable accepts +inf as a number (_is_number
        excludes booleans but not non-finite floats, and
        inf >= minimum holds) and then int(inf) raises
        OverflowError: decide() crashes outright on
        cooldown_sec=inf or max_alerts_per_pass=inf, and
        read_new_lines() crashes the same way on
        tail_bytes=inf, instead of reading the tunable as
        the documented default. Sibling readers in this
        codebase that guard with a range or comparison
        inf cannot satisfy fall back to their defaults;
        this reader converts first and crashes. Observed
        on 2026-10-23: decide() with {"cooldown_sec":
        float("inf")} and with {"max_alerts_per_pass":
        float("inf")} both raised "OverflowError: cannot
        convert float infinity to integer", as did
        read_new_lines([], {}, float("inf")) via the
        tail_bytes path.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    NOW = 100000.0
    OOM = "Out of memory: Killed process 42 (foo)"

    def _mod(self):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "log-sentinel",
            "log_sentinel.py")
        spec = importlib.util.spec_from_file_location(
            "log_sentinel_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _decide(self, tunables, state=None, lines=None):
        mod = self._mod()
        alerts, _state = mod.decide(
            {"now": self.NOW,
             "lines": [self.OOM] if lines is None else lines},
            {"tunables": tunables}, state or {})
        return alerts

    def test_infinite_cooldown_defaults_to_3600(self):
        # 100s after a firing is inside the documented
        # 3600s cooldown: suppressed, not a crash.
        state = {"last_fired": {
            "kernel_distress:oom": self.NOW - 100}}
        self.assertEqual(
            self._decide({"cooldown_sec": float("inf")}, state),
            [])
        # 4000s after a firing is past the documented
        # default cooldown: files again.
        state = {"last_fired": {
            "kernel_distress:oom": self.NOW - 4000}}
        self.assertEqual(
            len(self._decide(
                {"cooldown_sec": float("inf")}, state)), 1)

    def test_infinite_max_alerts_defaults_to_10(self):
        patterns = [{"name": f"p{i}", "regex": f"hit{i}"}
                    for i in range(12)]
        lines = [f"hit{i}" for i in range(12)]
        alerts = self._decide(
            {"max_alerts_per_pass": float("inf"),
             "patterns": patterns}, lines=lines)
        self.assertEqual(len(alerts), 10)

    def test_infinite_tail_bytes_defaults_to_65536(self):
        mod = self._mod()
        lines, _state = mod.read_new_lines(
            [], {}, float("inf"))
        self.assertEqual(lines, [])

    def test_omitted_and_explicit_tunables_are_honored(self):
        # Controls: the documented defaults and genuine
        # values already behave today and must keep doing
        # so after the non-finite cases are fixed.
        self.assertEqual(len(self._decide({})), 1)
        state = {"last_fired": {
            "kernel_distress:oom": self.NOW - 100}}
        self.assertEqual(self._decide({}, state), [])
        self.assertEqual(
            len(self._decide({"cooldown_sec": 0}, state)), 1)
        self.assertEqual(
            self._decide({"cooldown_sec": float("nan")}, state),
            [])
        self.assertEqual(
            self._decide({"cooldown_sec": float("-inf")}, state),
            [])



class TestInfiniteTripwireTunablesCrashInsteadOfDefault(unittest.TestCase):
    """Divergence: an infinite tripwire integer tunable
    (max_files / max_alerts_per_pass = +inf) crashes the
    pass with OverflowError instead of falling back to
    the documented defaults.

    (a) Doc claim (examples/extensions/tripwire/README.md
        lines 27 and 32-33, repeated in the extension's
        extension.json tunables): "At most `max_files`
        files (default 10000) are recorded per pass"; "At
        most `max_alerts_per_pass` alerts (default 100)
        are filed per pass".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the tripwire
        example extension's decide() -- the pure decision
        function -- and its read_live() reader with each
        integer tunable omitted, set to a genuine value,
        and set to float("inf"), float("-inf") and
        float("nan"), using 105 appeared files against a
        learned empty baseline (past the documented cap
        of 100 alerts) and a nonexistent watch root.

    (c) Behavior actually observed: omitted tunables cap
        105 appeared files at 100 alerts, and NaN and
        -inf also fall back to the defaults, because the
        reader's `value >= minimum` check is false for
        them. But _int_tunable accepts +inf as a number
        (_is_number excludes booleans but not non-finite
        floats, and inf >= minimum holds) and then
        int(inf) raises OverflowError: decide() crashes
        outright on max_alerts_per_pass=inf, and
        read_live() crashes the same way on
        max_files=inf (the tunable is converted before
        the root is even checked), instead of reading
        the tunable as the documented default. This is
        the same conversion pattern recorded for the
        log-sentinel extension above, at a site that class
        does not cover. Observed on 2026-10-23: both
        entry points raised "OverflowError: cannot
        convert float infinity to integer".

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    def _mod(self):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "tripwire",
            "tripwire.py")
        spec = importlib.util.spec_from_file_location(
            "tripwire_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _files(self, count=105):
        return {f"f{i:03d}.txt": {"sha384": "a" * 96, "size": 1}
                for i in range(count)}

    def _decide(self, tunables):
        mod = self._mod()
        alerts, _state = mod.decide(
            {"files": self._files()},
            {"tunables": tunables},
            {"learned": True, "files": {}})
        return alerts

    def test_infinite_max_alerts_defaults_to_100(self):
        self.assertEqual(
            len(self._decide(
                {"max_alerts_per_pass": float("inf")})), 100)

    def test_infinite_max_files_defaults_to_10000(self):
        mod = self._mod()
        readings = mod.read_live({"tunables": {
            "root": "/nonexistent-tripwire-probe",
            "max_files": float("inf")}})
        self.assertEqual(readings["files"], {})
        self.assertEqual(readings["truncated"], 0)

    def test_omitted_and_explicit_tunables_are_honored(self):
        # Controls: the documented defaults and genuine
        # values already behave today and must keep doing
        # so after the non-finite cases are fixed.
        self.assertEqual(len(self._decide({})), 100)
        self.assertEqual(
            len(self._decide({"max_alerts_per_pass": 3})), 3)
        self.assertEqual(
            len(self._decide(
                {"max_alerts_per_pass": float("nan")})), 100)
        self.assertEqual(
            len(self._decide(
                {"max_alerts_per_pass": float("-inf")})), 100)



class TestNonFiniteSkyWatcherLeadAndBrightDefaults(unittest.TestCase):
    """Divergence: non-finite sky-watcher visible_lead_sec,
    visible_min_elevation_deg, and bright_min_elevation_deg
    values suppress the visible-pass signals (or crash the
    update outright) instead of falling back to the
    documented defaults of 600, 10, and 65.

    (a) Doc claim (docs/extensions.md, sky-watcher signal
        table, lines 531-532): "`visible_pass_starting` | A
        sunlit pass over a dark sky begins within
        `visible_lead_sec` (default 600), culminating above
        `visible_min_elevation_deg` (default 10 deg)";
        "`bright_pass` | That pass culminates at or above
        `bright_min_elevation_deg` (default 65 deg) -- near
        zenith".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the sky-watcher
        example extension's update() -- the pure pass state
        machine -- with an observer at (0, 0), a sunlit
        equatorial zenith pass already inside the approach
        corridor at a midnight epoch (previous sub-point
        (0, -44), current sub-point (0, -43), alt 420 km,
        culmination 90 deg, window opening in about 470 s,
        inside the documented 600 s lead), the three
        tunables omitted, set to genuine values, and set to
        float("inf"), float("-inf"), and float("nan").

    (c) Behavior actually observed: the omitted tunables
        file as documented (both visible_pass_starting and
        bright_pass) and genuine values are honored
        (visible_lead_sec 10 files neither, 10000 files
        both; bright_min_elevation_deg 80 files both, 95
        files only visible_pass_starting), but _tunable
        accepts inf and NaN as numbers (_is_number excludes
        booleans but not non-finite floats): with
        visible_lead_sec NaN or -inf the starts_in <= lead
        comparison is never true, so neither signal files;
        with bright_min_elevation_deg inf or NaN the
        culmination >= bright_min comparison is never
        true, so bright_pass silently goes missing while
        visible_pass_starting still files; and with
        visible_min_elevation_deg inf, update() raises
        ValueError (math domain error) out of
        psi_for_elevation_deg instead of filing anything.
        Non-finite values therefore erase or crash the
        heads-up instead of reading as the documented
        defaults. Sibling readers in this codebase exclude
        non-finite values and fall back to their defaults
        (e.g. runner.remediation._pos_float,
        runner.runner._local_wake_cooldown); this reader
        does not. Observed on 2026-10-23: update() with
        visible_lead_sec float("nan") and float("-inf")
        returned [] where the omitted tunable returned
        ["visible_pass_starting", "bright_pass"]; with
        bright_min_elevation_deg float("inf") and
        float("nan") returned ["visible_pass_starting"]
        where the omitted tunable returned both; with
        visible_min_elevation_deg float("inf") raised
        ValueError: math domain error.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed
        in the code.
    """

    MIDNIGHT = 1704067200  # 2024-01-01T00:00Z, sun ~-66.9 deg

    def _signals(self, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "sky-watcher",
            "sky_watcher.py")
        spec = importlib.util.spec_from_file_location(
            "sky_watcher_lead_bright_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        prev = {"lat": 0, "lon": -44, "alt_km": 420,
                "velocity_kmh": 27576, "sunlit": True,
                "ts": self.MIDNIGHT}
        sample = {"lat": 0, "lon": -43, "alt_km": 420,
                  "velocity_kmh": 27576, "sunlit": True,
                  "ts": self.MIDNIGHT + 60}
        state = {"stage": "approaching", "pass_id": 1,
                 "fired": ["station_approaching"],
                 "prev": prev, "culmination_deg": None,
                 "last_ts": self.MIDNIGHT}
        manifest = {"name": "sky_watcher",
                    "tunables": {"observer_lat": 0,
                                 "observer_lon": 0, **tunables}}
        alerts, _state = mod.update(sample, manifest, state)
        return [a["signal"] for a in alerts]

    def test_nan_lead_defaults_to_600(self):
        self.assertEqual(
            self._signals({"visible_lead_sec": float("nan")}),
            ["visible_pass_starting", "bright_pass"])

    def test_negative_infinite_lead_defaults_to_600(self):
        self.assertEqual(
            self._signals({"visible_lead_sec": float("-inf")}),
            ["visible_pass_starting", "bright_pass"])

    def test_infinite_bright_min_defaults_to_65(self):
        self.assertEqual(
            self._signals(
                {"bright_min_elevation_deg": float("inf")}),
            ["visible_pass_starting", "bright_pass"])

    def test_nan_bright_min_defaults_to_65(self):
        self.assertEqual(
            self._signals(
                {"bright_min_elevation_deg": float("nan")}),
            ["visible_pass_starting", "bright_pass"])

    def test_infinite_visible_min_defaults_to_10(self):
        self.assertEqual(
            self._signals(
                {"visible_min_elevation_deg": float("inf")}),
            ["visible_pass_starting", "bright_pass"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented defaults and genuine
        # values already behave today and must keep doing
        # so after the non-finite cases are fixed.
        self.assertEqual(
            self._signals({}),
            ["visible_pass_starting", "bright_pass"])
        self.assertEqual(
            self._signals({"visible_lead_sec": 10}), [])
        self.assertEqual(
            self._signals({"visible_lead_sec": 10000}),
            ["visible_pass_starting", "bright_pass"])
        self.assertEqual(
            self._signals({"bright_min_elevation_deg": 80}),
            ["visible_pass_starting", "bright_pass"])
        self.assertEqual(
            self._signals({"bright_min_elevation_deg": 95}),
            ["visible_pass_starting"])



class TestInfiniteBackupStaleAfterDefaultsTo90000(unittest.TestCase):
    """Divergence: an infinite backup-freshness
    stale_after_sec (+inf) suppresses every staleness
    alert instead of falling back to the documented
    90000-second default.

    (a) Doc claim (examples/extensions/backup-freshness/
        README.md, lines 12-13): "`stale_after_sec` (how
        old is too old, default 90000 -- just over a
        day)". The manifest ships the same default
        (extension.json: "stale_after_sec": 90000), and
        the README signal table (lines 22-23) states
        backup_stale fires when the newest backup's age
        passes stale_after_sec and backup_critical when
        it passes twice that.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 14:41 PDT tick) exercised the
        backup-freshness example extension's decide() --
        the pure decision function -- with a backup
        already seen (so no arrival fires), aged
        1,000,000,000 seconds (far past twice even a
        generous threshold), the tunable omitted, set
        to genuine values, and set to float("inf"),
        float("-inf"), float("nan"), 0, -5, True, and
        "bogus".

    (c) Behavior actually observed: omitted, NaN,
        -inf, 0, -5, True, and "bogus" all file
        backup_critical, as the documented default
        requires (decide() reads a tunable that is not
        a positive number as 90000.0: float(x) if
        _is_number(x) and x > 0 else 90000.0, in
        backup_freshness.py lines 164-166). +inf does
        not: _is_number excludes booleans but not
        non-finite floats, and inf > 0 is true, so the
        threshold becomes infinite, no age is ever
        greater than it or twice it, and decide()
        returns no alerts at all -- a backup a billion
        seconds old files nothing. Sibling readers in
        this codebase exclude non-finite values and
        fall back to their defaults (e.g.
        runner.remediation._pos_float,
        runner.runner._local_wake_cooldown); this
        reader does not. This is the campaign's known
        non-finite-tunable root-cause family.
        Observed on 2026-10-23: decide() with
        stale_after_sec float("inf") returned []
        where the omitted tunable returned
        ["backup_critical"].

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "backup-freshness",
            "backup_freshness.py")
        spec = importlib.util.spec_from_file_location(
            "backup_freshness_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        manifest = {"name": "backup_freshness",
                    "tunables": dict(tunables)}
        readings = {"now": 2000000000.0,
                    "newest": {"name": "b.tar",
                               "mtime": 1000000000.0,
                               "size": 1}}
        state = {"last_seen_name": "b.tar",
                 "last_seen_mtime": 1000000000.0,
                 "tier": "ok"}
        alerts, _state = mod.decide(readings, manifest, state)
        return [a["signal"] for a in alerts]

    def test_infinite_stale_after_defaults_to_90000(self):
        self.assertEqual(
            self._signals({"stale_after_sec": float("inf")}),
            ["backup_critical"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        self.assertEqual(self._signals({}), ["backup_critical"])
        self.assertEqual(
            self._signals({"stale_after_sec": float("nan")}),
            ["backup_critical"])
        self.assertEqual(
            self._signals({"stale_after_sec": 2000000000}),
            [])
        self.assertEqual(
            self._signals({"stale_after_sec": 600000000}),
            ["backup_stale"])




class TestInfiniteCrashWatchRepeatWindowDefaultsTo3600(unittest.TestCase):
    """Divergence: an infinite crash-watch
    repeat_window_sec (+inf) keeps every prior crash
    inside the window forever instead of falling back
    to the documented 3600-second default.

    (a) Doc claim (examples/extensions/crash-watch/
        README.md, line 16): "`crash_repeated` | The
        same binary crashes again within
        `repeat_window_sec` (default 3600) -- filed
        instead of `crash_dumped`, with the count of
        that binary's crashes inside the window". The
        manifest ships the same default
        (extension.json: "repeat_window_sec": 3600),
        and the module docstring in crash_watch.py
        (lines 18-19) states the repeat_window_sec
        tunable is "(default one hour)".

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 14:46 PDT tick) exercised the
        crash-watch example extension's decide() -- the
        pure decision function -- with now=2000000.0,
        prior state events [["app", now-100000]] (a
        crash 100,000 seconds earlier, far outside a
        one-hour window), and a new readings file
        app2.dmp whose binary is "app", with the
        tunable omitted, set to genuine values (3600
        and 200000), and set to float("inf"),
        float("-inf"), and float("nan").

    (c) Behavior actually observed: omitted, 3600,
        -inf, and NaN all file crash_dumped and prune
        the old event, as the documented default
        requires. +inf does not: decide() reads the
        window as float(window) if _is_number(window)
        and window > 0 else 3600.0 (crash_watch.py
        lines 205-206); _is_number excludes booleans
        but not non-finite floats, and inf > 0 is
        true, so the window becomes infinite, the
        pruning test ts >= now - window keeps the
        100,000-second-old event, and decide()
        returns ["crash_repeated"] instead of
        ["crash_dumped"]. Sibling readers in this
        codebase exclude non-finite values and fall
        back to their defaults; this reader does not.
        This is the campaign's known non-finite-tunable
        root-cause family. Observed on 2026-10-23:
        decide() with repeat_window_sec float("inf")
        returned ["crash_repeated"] where the omitted
        tunable returned ["crash_dumped"].

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "crash-watch",
            "crash_watch.py")
        spec = importlib.util.spec_from_file_location(
            "crash_watch_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        now = 2000000.0
        manifest = {"name": "crash_watch",
                    "tunables": dict(tunables)}
        readings = {"now": now, "truncated": 0,
                    "files": [{"name": "app2.dmp",
                               "dir": "./crashes",
                               "size": 123,
                               "mtime": now,
                               "binary": "app"}]}
        state = {"seen": {},
                 "events": [["app", now - 100000]]}
        alerts, _state = mod.decide(readings, manifest, state)
        return [a["signal"] for a in alerts]

    def test_infinite_repeat_window_defaults_to_3600(self):
        self.assertEqual(
            self._signals({"repeat_window_sec": float("inf")}),
            ["crash_dumped"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        self.assertEqual(self._signals({}), ["crash_dumped"])
        self.assertEqual(
            self._signals({"repeat_window_sec": 3600}),
            ["crash_dumped"])
        self.assertEqual(
            self._signals({"repeat_window_sec": float("nan")}),
            ["crash_dumped"])
        self.assertEqual(
            self._signals({"repeat_window_sec": 200000}),
            ["crash_repeated"])




class TestInfiniteFailedLoginBurstCountDefaultsTo5(unittest.TestCase):
    """Divergence: an infinite failed-login-watch
    burst_count (+inf) crashes decide() with
    OverflowError instead of falling back to the
    documented 5-failure default.

    (a) Doc claim (examples/extensions/failed-login-watch/
        README.md, line 37): "`login_failure_burst` |
        One source accumulates at least the
        `burst_count` tunable (default 5) failures
        inside the trailing `window_sec` (default
        600)". The manifest ships the same default
        (extension.json: "burst_count": 5,
        "window_sec": 600).

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 14:51 PDT tick) exercised the
        failed-login-watch example extension's decide()
        -- the pure decision function -- with six
        failure events from one source inside the
        window, with the tunable omitted, set to
        genuine values (5 and 2), and set to
        float("inf"), float("nan"), True, and a huge
        integer.

    (c) Behavior actually observed: omitted, 5, NaN,
        and True all file one login_failure_burst at
        the fifth failure, as the documented default
        requires, and an explicit 2 files at the
        second failure. float("inf") does not:
        decide() computes burst_count as
        int(burst_count) if _is_number(burst_count)
        and burst_count >= 1 else 5
        (failed_login_watch.py lines 251-253);
        _is_number excludes booleans but not
        non-finite floats, and inf >= 1 is true, so
        int(float("inf")) raises OverflowError:
        cannot convert float infinity to integer,
        and decide() crashes outright instead of
        using the default. Sibling readers in this
        codebase exclude non-finite values and fall
        back to their defaults; this reader does not.
        This is the campaign's known non-finite-tunable
        root-cause family. Observed on 2026-10-23:
        decide() with burst_count float("inf") raised
        OverflowError where the omitted tunable
        returned ["login_failure_burst"].

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, count=6):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "failed-login-watch",
            "failed_login_watch.py")
        spec = importlib.util.spec_from_file_location(
            "failed_login_watch_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        now = 1000000.0
        manifest = {"name": "failed_login_watch",
                    "tunables": dict(tunables)}
        events = [{"ts": now + i, "kind": "fail",
                   "source": "192.0.2.10",
                   "user": "root"} for i in range(count)]
        readings = {"now": now + count, "events": events}
        alerts, _state = mod.decide(readings, manifest, {})
        return [a["signal"] for a in alerts]

    def test_infinite_burst_count_defaults_to_5(self):
        self.assertEqual(
            self._signals({"burst_count": float("inf")}),
            ["login_failure_burst"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        self.assertEqual(self._signals({}),
                         ["login_failure_burst"])
        self.assertEqual(
            self._signals({"burst_count": 5}),
            ["login_failure_burst"])
        self.assertEqual(
            self._signals({"burst_count": float("nan")}),
            ["login_failure_burst"])
        self.assertEqual(
            self._signals({"burst_count": 2}, count=3),
            ["login_failure_burst"])
        self.assertEqual(
            self._signals({"burst_count": 7}, count=6), [])


class TestFailedLoginWindowSecDefaultsTo600(unittest.TestCase):
    """Second-run hunt coverage: failed-login-watch
    window_sec itself, varied for the first time.

    (a) Doc claim (examples/extensions/failed-login-watch/
        README.md, line 37): "`login_failure_burst` |
        One source accumulates at least the
        `burst_count` tunable (default 5) failures
        inside the trailing `window_sec` (default
        600)". The manifest ships the same default
        (extension.json: "burst_count": 5,
        "window_sec": 600). Registry row
        "window_sec (failed-login-watch)": integer,
        default 600, policy default.

    (b) How it was hunted: step 8 Target 2 -- the
        row's named class
        (TestInfiniteFailedLoginBurstCountDefaultsTo5)
        varies burst_count only, so window_sec had
        never itself been varied. On 2026-10-23 this
        tick probed decide() -- the pure decision
        function -- with the table hunt's fifteen
        shapes for window_sec, each in two scenarios:
        five failures 700 seconds apart (a burst only
        if the window is wrongly read as far larger
        than 600) and five failures 100 seconds apart
        (a burst exactly when the effective window
        reaches across 400 seconds, as 600 does).

    (c) Behavior actually observed: NO divergence.
        Every unusable shape -- omitted, null, the
        empty string, true, false, zero, a negative
        number, a numeric string, a non-numeric
        string, a several-hundred-digit integer,
        inf, -inf, NaN, and a list -- read as the
        documented default 600 (no burst at 700-second
        spacing, a burst at 100-second spacing), and
        the explicit default 600 did the same. This
        reader's _is_number accepts only genuine
        finite numbers, so a numeric string reads as
        the default here (unlike the confval family,
        which parses numeric strings). Genuine values
        are honored: window_sec 60 and 1 file no
        burst at 100-second spacing, and 10000 files
        a burst at 700-second spacing.

    (d) This is a coverage record, not a divergence:
        it stays green as long as the reader keeps
        the documented default. If a shape above ever
        stops reading as 600, this test is the
        failing record of that change.
    """

    def _signals(self, tunables, offsets):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "failed-login-watch",
            "failed_login_watch.py")
        spec = importlib.util.spec_from_file_location(
            "failed_login_watch_window_hunt", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        now = 1000000.0
        manifest = {"name": "failed_login_watch",
                    "tunables": dict(tunables)}
        events = [{"ts": now + off, "kind": "fail",
                   "source": "192.0.2.10",
                   "user": "root"} for off in offsets]
        readings = {"now": now + 10000, "events": events}
        alerts, _state = mod.decide(readings, manifest, {})
        return [a["signal"] for a in alerts]

    SPACED = [0, 700, 1400, 2100, 2800]
    CLOSE = [0, 100, 200, 300, 400]

    def test_fifteen_shapes_read_as_default_600(self):
        shapes = [
            ("omitted", None), ("null", None),
            ("empty-string", ""), ("true", True),
            ("false", False), ("zero", 0),
            ("negative", -5), ("default-explicit", 600),
            ("numeric-string", "600"),
            ("non-numeric-string", "bogus"),
            ("huge-int", 10 ** 400), ("inf", float("inf")),
            ("neg-inf", float("-inf")), ("nan", float("nan")),
            ("wrong-container", ["x"]),
        ]
        for name, value in shapes:
            with self.subTest(shape=name):
                tunables = {} if name == "omitted" else {
                    "window_sec": value}
                self.assertEqual(
                    self._signals(tunables, self.SPACED), [])
                self.assertEqual(
                    self._signals(tunables, self.CLOSE),
                    ["login_failure_burst"])

    def test_genuine_window_values_are_honored(self):
        self.assertEqual(
            self._signals({"window_sec": 60}, self.CLOSE), [])
        self.assertEqual(
            self._signals({"window_sec": 1}, self.CLOSE), [])
        self.assertEqual(
            self._signals({"window_sec": 10000}, self.SPACED),
            ["login_failure_burst"])
        # A numeric string is not a number to this
        # reader: "10000" reads as the default 600,
        # so the spaced scenario files no burst.
        self.assertEqual(
            self._signals({"window_sec": "10000"}, self.SPACED),
            [])




class TestServiceWatchFlapWindowSecDefaultsTo600(unittest.TestCase):
    """Second-run hunt coverage: service-watch
    flap_window_sec itself, varied for the first time.

    (a) Doc claim (examples/extensions/service-watch/
        README.md, line 18): the example configuration
        ships "\"flap_window_sec\": 600,
        \"flap_count\": 4", and line 28 states
        service_flapping fires when a service's
        transitions inside flap_window_sec reach
        flap_count. The manifest ships the same
        default (extension.json: "flap_count": 4,
        "flap_window_sec": 600). Registry row
        "flap_window_sec (service-watch)": integer,
        default 600, policy default.

    (b) How it was hunted: step 8 Target 2 -- the
        row's named class
        (TestInfiniteServiceWatchFlapCountDefaultsTo4)
        varies flap_count only, so flap_window_sec had
        never itself been varied. On 2026-10-23 this
        tick probed decide() -- the pure decision
        function -- with the table hunt's fifteen
        shapes for flap_window_sec, each in two
        scenarios: four transitions 700 seconds apart
        (flapping only if the window is wrongly read
        as far larger than 600) and four transitions
        100 seconds apart (flapping exactly when the
        effective window reaches across 300 seconds,
        as 600 does), with flap_count at its
        documented default 4 throughout.

    (c) Behavior actually observed: NO divergence.
        Every unusable shape -- omitted, null, the
        empty string, true, false, zero, a negative
        number, a numeric string, a non-numeric
        string, a several-hundred-digit integer,
        inf, -inf, NaN, and a list -- read as the
        documented default 600 (no flapping at
        700-second spacing, flapping at 100-second
        spacing), and the explicit default 600 did
        the same. This reader's _is_number accepts
        only genuine finite numbers and the reader
        requires a value > 0, so a numeric string
        reads as the default here. Genuine values
        are honored: flap_window_sec 60 and 1 file
        no flapping at 100-second spacing, and
        10000 files flapping at 700-second spacing.

    (d) This is a coverage record, not a divergence:
        it stays green as long as the reader keeps
        the documented default. If a shape above ever
        stops reading as 600, this test is the
        failing record of that change.
    """

    def _signals(self, tunables, times):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "service-watch",
            "service_watch.py")
        spec = importlib.util.spec_from_file_location(
            "service_watch_flap_window_hunt", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        manifest = {"name": "service_watch",
                    "tunables": {
                        "services": [{"name": "sshd",
                                      "match": "exact"}],
                        **tunables}}
        state = {"learned": True,
                 "services": {"sshd": {
                     "up": True, "transitions": [],
                     "down_filed": False,
                     "flap_fired": False}}}
        signals = []
        proc = {"name": "sshd", "pid": 1,
                "cmdline": "/usr/sbin/sshd"}
        up = True
        for now in times:
            up = not up
            readings = {"now": float(now),
                        "processes": [proc] if up else []}
            alerts, state = mod.decide(readings, manifest, state)
            signals.extend(a["signal"] for a in alerts)
        return signals

    SPACED = [1000, 1700, 2400, 3100]
    CLOSE = [1000, 1100, 1200, 1300]

    def test_fifteen_shapes_read_as_default_600(self):
        shapes = [
            ("omitted", None), ("null", None),
            ("empty-string", ""), ("true", True),
            ("false", False), ("zero", 0),
            ("negative", -5), ("default-explicit", 600),
            ("numeric-string", "600"),
            ("non-numeric-string", "bogus"),
            ("huge-int", 10 ** 400), ("inf", float("inf")),
            ("neg-inf", float("-inf")), ("nan", float("nan")),
            ("wrong-container", ["x"]),
        ]
        for name, value in shapes:
            with self.subTest(shape=name):
                tunables = {} if name == "omitted" else {
                    "flap_window_sec": value}
                self.assertNotIn(
                    "service_flapping",
                    self._signals(tunables, self.SPACED))
                self.assertIn(
                    "service_flapping",
                    self._signals(tunables, self.CLOSE))

    def test_genuine_flap_window_values_are_honored(self):
        self.assertNotIn(
            "service_flapping",
            self._signals({"flap_window_sec": 60}, self.CLOSE))
        self.assertNotIn(
            "service_flapping",
            self._signals({"flap_window_sec": 1}, self.CLOSE))
        self.assertIn(
            "service_flapping",
            self._signals({"flap_window_sec": 10000}, self.SPACED))
        # A numeric string is not a number to this
        # reader: "10000" reads as the default 600,
        # so the spaced scenario files no flapping.
        self.assertNotIn(
            "service_flapping",
            self._signals({"flap_window_sec": "10000"}, self.SPACED))



class TestInfiniteServiceWatchFlapCountDefaultsTo4(unittest.TestCase):
    """Divergence: an infinite service-watch
    flap_count (+inf) crashes decide() with
    OverflowError instead of falling back to the
    documented 4-transition default.

    (a) Doc claim (examples/extensions/service-watch/
        README.md, line 18): the example configuration
        ships "\"flap_window_sec\": 600,
        \"flap_count\": 4", and line 28 states
        service_flapping fires when a service's
        transitions inside flap_window_sec reach
        flap_count. The manifest ships the same
        default (extension.json: "flap_count": 4,
        "flap_window_sec": 600).

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 14:56 PDT tick) exercised the
        service-watch example extension's decide() --
        the pure decision function -- with one watched
        service toggling down/up/down/up (four
        transitions inside the window), with the
        tunable omitted, set to genuine values (4, 2
        and 9), and set to float("inf"),
        float("-inf"), float("nan"), and True.

    (c) Behavior actually observed: omitted, 4, NaN,
        -inf, and True all file service_flapping at
        the fourth transition, as the documented
        default requires; an explicit 2 files it at
        the second transition and an explicit 9 does
        not file it within four transitions.
        float("inf") does not: decide() computes
        flap_count as int(flap_count) if
        _is_number(flap_count) and flap_count >= 1
        else 4 (service_watch.py lines 211-213);
        _is_number excludes booleans but not
        non-finite floats, and inf >= 1 is true, so
        int(float("inf")) raises OverflowError:
        cannot convert float infinity to integer, and
        decide() crashes on the first pass instead of
        using the default. Sibling readers in this
        codebase exclude non-finite values and fall
        back to their defaults; this reader does not.
        This is the campaign's known non-finite-tunable
        root-cause family. Observed on 2026-10-23:
        decide() with flap_count float("inf") raised
        OverflowError where the omitted tunable
        returned service_down / service_recovered /
        service_flapping across the four toggles.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "service-watch",
            "service_watch.py")
        spec = importlib.util.spec_from_file_location(
            "service_watch_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        manifest = {"name": "service_watch",
                    "tunables": {
                        "services": [{"name": "sshd",
                                      "match": "exact"}],
                        **tunables}}
        state = {"learned": True,
                 "services": {"sshd": {
                     "up": True, "transitions": [],
                     "down_filed": False,
                     "flap_fired": False}}}
        signals = []
        proc = {"name": "sshd", "pid": 1,
                "cmdline": "/usr/sbin/sshd"}
        for now, up in [(1000.0, False), (1010.0, True),
                        (1020.0, False), (1030.0, True)]:
            readings = {"now": now,
                        "processes": [proc] if up else []}
            alerts, state = mod.decide(readings, manifest, state)
            signals.extend(a["signal"] for a in alerts)
        return signals

    def test_infinite_flap_count_defaults_to_4(self):
        self.assertIn(
            "service_flapping",
            self._signals({"flap_count": float("inf")}))

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        self.assertIn("service_flapping", self._signals({}))
        self.assertIn(
            "service_flapping",
            self._signals({"flap_count": 4}))
        self.assertIn(
            "service_flapping",
            self._signals({"flap_count": float("nan")}))
        self.assertIn(
            "service_flapping",
            self._signals({"flap_count": 2}))
        self.assertNotIn(
            "service_flapping",
            self._signals({"flap_count": 9}))



class TestJobWatcherFailureWindowSecDefaultsTo86400(unittest.TestCase):
    """Divergence: a zero or negative job-watcher
    failure_window_sec is read literally instead
    of falling back to the documented 86400-second
    (a day) default, so no past failure is ever
    inside the window and job_failing_repeatedly
    never files.

    (a) Doc claim (examples/extensions/job-watcher/
        README.md, line 18): "`job_failing_repeatedly`
        | The same job -- same `kind` and script --
        failed at least `repeat_failures` times
        (default 3) inside `failure_window_sec`
        (default a day)". The extension header states
        the same default (job_watcher.py lines
        35-36), and the manifest ships the numeric
        default (extension.json:
        "failure_window_sec": 86400). Registry row
        "failure_window_sec (job-watcher)": integer,
        default 86400, policy default.

    (b) How the bug was found: step 8 Target 2 --
        the row's named class
        (TestInfiniteJobWatcherRepeatFailuresDefaultsTo3)
        varies repeat_failures only, so
        failure_window_sec had never itself been
        varied. On 2026-10-23 this tick probed
        decide() -- the pure decision function --
        with the table hunt's fifteen shapes for
        failure_window_sec, each in two scenarios:
        three failures 100, 99 and 98 seconds
        before now (inside a day, so a signal
        exactly when the effective window reaches
        across 100 seconds, as 86400 does) and
        three failures 90000, 89900 and 89800
        seconds before now (outside a day, so a
        signal only if the window is wrongly read
        as far larger than 86400), with
        repeat_failures at its documented
        default 3 throughout.

    (c) Behavior actually observed: thirteen
        shapes read as the documented default
        86400 (no signal at 90000-second spacing,
        a signal at 100-second spacing) --
        omitted, null, the empty string, true,
        false, the explicit default 86400, a
        numeric string, a non-numeric string, a
        several-hundred-digit integer, inf, -inf,
        NaN, and a list. Zero and a negative
        number do not: decide() computes
        failure_window as _tunable(tunables,
        "failure_window_sec", 86400.0)
        (job_watcher.py line 415), and _tunable
        (lines 131-133) returns float(value)
        whenever _is_number(value) holds, with
        no requirement that the value be
        positive, so 0 reads as 0.0 and -5 reads
        as -5.0 and the recent-failures test
        r[0] >= now - failure_window excludes
        every past failure. Sibling window
        readers in this codebase require a
        positive value before honoring it
        (failed-login-watch: window > 0 else
        600; service-watch: flap_window > 0
        else 600; crash-watch: window > 0 else
        3600); this reader has no such guard.
        Observed on 2026-10-23: decide() with
        failure_window_sec 0 and with -5
        returned [] in the 100-second scenario
        where the omitted tunable returned
        ["job_failing_repeatedly"].

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, offsets):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "job-watcher",
            "job_watcher.py")
        spec = importlib.util.spec_from_file_location(
            "job_watcher_failure_window_hunt", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        now = 1000000.0
        manifest = {"name": "job_watcher",
                    "tunables": dict(tunables)}
        records = [{"job_id": f"j{i}", "key": "k1",
                    "kind": "shell", "label": "job1",
                    "saved_at": now + off, "exit_code": 1,
                    "duration_sec": 1.0,
                    "error": "boom"}
                   for i, off in enumerate(offsets)]
        readings = {"now": now, "records": records}
        alerts, _state = mod.decide(readings, manifest, {})
        return [a["signal"] for a in alerts]

    SPACED = [-90000, -89900, -89800]
    CLOSE = [-100, -99, -98]

    def test_fifteen_shapes_read_as_default_86400(self):
        shapes = [
            ("omitted", None), ("null", None),
            ("empty-string", ""), ("true", True),
            ("false", False), ("zero", 0),
            ("negative", -5), ("default-explicit", 86400),
            ("numeric-string", "86400"),
            ("non-numeric-string", "bogus"),
            ("huge-int", 10 ** 400), ("inf", float("inf")),
            ("neg-inf", float("-inf")), ("nan", float("nan")),
            ("wrong-container", ["x"]),
        ]
        for name, value in shapes:
            with self.subTest(shape=name):
                tunables = {} if name == "omitted" else {
                    "failure_window_sec": value}
                self.assertEqual(
                    self._signals(tunables, self.SPACED), [])
                self.assertEqual(
                    self._signals(tunables, self.CLOSE),
                    ["job_failing_repeatedly"])

    def test_genuine_failure_window_values_are_honored(self):
        self.assertEqual(
            self._signals({"failure_window_sec": 60}, self.CLOSE), [])
        self.assertEqual(
            self._signals({"failure_window_sec": 1}, self.CLOSE), [])
        self.assertEqual(
            self._signals({"failure_window_sec": 100000}, self.SPACED),
            ["job_failing_repeatedly"])
        # A numeric string is not a number to this
        # reader: "100000" reads as the default 86400,
        # so the spaced scenario files no signal.
        self.assertEqual(
            self._signals({"failure_window_sec": "100000"}, self.SPACED),
            [])



class TestInfiniteJobWatcherRepeatFailuresDefaultsTo3(unittest.TestCase):
    """Divergence: a non-finite job-watcher
    repeat_failures (+inf, -inf, or NaN) crashes
    decide() instead of falling back to the
    documented 3-failure default.

    (a) Doc claim (examples/extensions/job-watcher/
        README.md, line 18): "`job_failing_repeatedly`
        | The same job -- same `kind` and script --
        failed at least `repeat_failures` times
        (default 3) inside `failure_window_sec`
        (default a day)". The extension header states
        the same default (job_watcher.py lines 35-36:
        "repeat_failures times (default 3)"), and the
        manifest ships it (extension.json:
        "repeat_failures": 3).

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 15:01 PDT tick)
        exercised the job-watcher example extension's
        decide() -- the pure decision function -- with
        three failure records for one job inside the
        failure window, with the tunable omitted, set
        to genuine values (3, 2, and 5), and set to
        float("inf"), float("-inf"), float("nan"),
        and True.

    (c) Behavior actually observed: omitted, 3, and
        True all file job_failing_repeatedly at the
        third failure, as the documented default
        requires; an explicit 2 files it at the
        second failure and an explicit 5 does not
        file it within three failures. The non-finite
        values do not fall back: decide() computes
        repeat_failures as int(_tunable(tunables,
        "repeat_failures", 3)) (job_watcher.py line
        400), and _tunable returns float(value) when
        _is_number(value) holds (lines 117-119);
        _is_number excludes booleans but not
        non-finite floats (lines 104-105), so
        int(float("inf")) and int(float("-inf"))
        raise OverflowError: cannot convert float
        infinity to integer, and int(float("nan"))
        raises ValueError: cannot convert float NaN
        to integer -- decide() crashes on the pass
        instead of using the default. Sibling readers
        in this codebase exclude non-finite values
        and fall back to their defaults; this reader
        does not. This is the campaign's known
        non-finite-tunable root-cause family.
        Observed on 2026-10-23: decide() with
        repeat_failures float("inf") raised
        OverflowError where the omitted tunable
        returned ["job_failing_repeatedly"].

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, count=3):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "job-watcher",
            "job_watcher.py")
        spec = importlib.util.spec_from_file_location(
            "job_watcher_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        now = 1000000.0
        manifest = {"name": "job_watcher",
                    "tunables": dict(tunables)}
        records = [{"job_id": f"j{i}", "key": "k1",
                    "kind": "shell", "label": "job1",
                    "saved_at": now + i, "exit_code": 1,
                    "duration_sec": 1.0,
                    "error": "boom"} for i in range(count)]
        readings = {"now": now + count,
                    "records": records}
        alerts, _state = mod.decide(readings, manifest, {})
        return [a["signal"] for a in alerts]

    def test_infinite_repeat_failures_defaults_to_3(self):
        self.assertEqual(
            self._signals({"repeat_failures": float("inf")}),
            ["job_failing_repeatedly"])

    def test_negative_infinite_repeat_failures_defaults_to_3(self):
        self.assertEqual(
            self._signals({"repeat_failures": float("-inf")}),
            ["job_failing_repeatedly"])

    def test_nan_repeat_failures_defaults_to_3(self):
        self.assertEqual(
            self._signals({"repeat_failures": float("nan")}),
            ["job_failing_repeatedly"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        self.assertEqual(self._signals({}),
                         ["job_failing_repeatedly"])
        self.assertEqual(
            self._signals({"repeat_failures": 3}),
            ["job_failing_repeatedly"])
        self.assertEqual(
            self._signals({"repeat_failures": True}),
            ["job_failing_repeatedly"])
        self.assertEqual(
            self._signals({"repeat_failures": 2}, count=2),
            ["job_failing_repeatedly"])
        self.assertEqual(
            self._signals({"repeat_failures": 5}), [])



class TestNonFiniteResourceSentinelSampleCountsCrashInsteadOfDefault(unittest.TestCase):
    """Divergence: a non-finite resource-sentinel
    min_samples or max_samples (+inf, -inf, or NaN)
    crashes decide() instead of falling back to the
    documented defaults (4 and 240).

    (a) Doc claim (examples/extensions/resource-sentinel/
        README.md, line 66): "`max_samples` (default 240)
        bounds how many samples the rolling window keeps,
        and is raised to the window's minimum if set
        lower". The manifest ships the same defaults
        (extension.json: "min_samples": 4,
        "max_samples": 240), the extension header states
        the trend defaults in the same shape, and
        README.md lines 29-31 state a signal needs at
        least `min_samples` samples spanning
        `min_span_sec` inside `window_sec` before it
        can fire at all.

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 15:06 PDT tick)
        exercised the resource-sentinel example
        extension's decide() -- the pure decision
        function -- with four seeded samples spanning
        600 seconds (CPU busy 97 percent, available
        memory falling 40 to 14 percent), with the
        tunables omitted, set to genuine values
        (min_samples 4, max_samples 240, and
        min_samples 2), and set to float("inf"),
        float("-inf"), float("nan"), and True for
        each of min_samples and max_samples.

    (c) Behavior actually observed: omitted, genuine,
        and True all file cpu_saturation_sustained and
        memory_exhaustion_trend, as the documented
        defaults require. The non-finite values do
        not fall back: decide() computes min_samples
        as int(_tunable(tunables, "min_samples", 4))
        and max_samples as int(_tunable(tunables,
        "max_samples", 240)) (resource_sentinel.py
        lines 246 and 249), and _tunable returns
        float(value) when _is_number(value) holds
        (lines 93-95); _is_number excludes booleans
        but not non-finite floats (lines 80-81), so
        int(float("inf")) and int(float("-inf"))
        raise OverflowError: cannot convert float
        infinity to integer, and int(float("nan"))
        raises ValueError: cannot convert float NaN
        to integer -- decide() crashes on the pass
        instead of using the defaults. Sibling readers
        in this codebase exclude non-finite values
        and fall back to their defaults; this reader
        does not. This is the campaign's known
        non-finite-tunable root-cause family.
        Observed on 2026-10-23: decide() with
        min_samples float("inf") raised OverflowError
        where the omitted tunable returned
        ["cpu_saturation_sustained",
        "memory_exhaustion_trend"].

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "resource-sentinel",
            "resource_sentinel.py")
        spec = importlib.util.spec_from_file_location(
            "resource_sentinel_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        gib = 1024.0 ** 3
        samples = [
            [1000000.0, 10000, 9000, 100 * gib, 100, 40.0],
            [1000200.0, 10333, 9010, 100 * gib, 100, 35.0],
            [1000400.0, 10666, 9020, 100 * gib, 100, 30.0],
            [1000600.0, 11000, 9030, 100 * gib, 100, 14.0],
        ]
        state = {"samples": samples, "fired": {}}
        manifest = {"name": "resource_sentinel",
                    "tunables": dict(tunables)}
        readings = {"now": 1000600.0, "cpu_total": 11000,
                    "cpu_idle": 9030,
                    "disk_free_bytes": 100 * gib,
                    "processes": 100, "mem_avail_pct": 14.0}
        alerts, _state = mod.decide(readings, manifest, state)
        return [a["signal"] for a in alerts]

    def test_infinite_min_samples_defaults_to_4(self):
        self.assertEqual(
            self._signals({"min_samples": float("inf")}),
            ["cpu_saturation_sustained",
             "memory_exhaustion_trend"])

    def test_negative_infinite_min_samples_defaults_to_4(self):
        self.assertEqual(
            self._signals({"min_samples": float("-inf")}),
            ["cpu_saturation_sustained",
             "memory_exhaustion_trend"])

    def test_nan_min_samples_defaults_to_4(self):
        self.assertEqual(
            self._signals({"min_samples": float("nan")}),
            ["cpu_saturation_sustained",
             "memory_exhaustion_trend"])

    def test_infinite_max_samples_defaults_to_240(self):
        self.assertEqual(
            self._signals({"max_samples": float("inf")}),
            ["cpu_saturation_sustained",
             "memory_exhaustion_trend"])

    def test_nan_max_samples_defaults_to_240(self):
        self.assertEqual(
            self._signals({"max_samples": float("nan")}),
            ["cpu_saturation_sustained",
             "memory_exhaustion_trend"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented defaults and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        expected = ["cpu_saturation_sustained",
                    "memory_exhaustion_trend"]
        self.assertEqual(self._signals({}), expected)
        self.assertEqual(
            self._signals({"min_samples": 4}), expected)
        self.assertEqual(
            self._signals({"max_samples": 240}), expected)
        self.assertEqual(
            self._signals({"min_samples": True}), expected)
        self.assertEqual(
            self._signals({"min_samples": 2}), expected)




class TestNonFiniteLabResultsTunablesDefaultInsteadOfCrashOrSilence(unittest.TestCase):
    """Divergence: non-finite lab-results tunables
    (+inf anomaly_min_history, +inf anomaly_band)
    crash scan() or silently suppress result_anomaly
    instead of falling back to the documented
    defaults (3 and 0.25).

    (a) Doc claim (examples/extensions/lab-results/
        README.md, line 37): "`anomaly_min_history`
        (default 3) is how many earlier finished runs
        the folder needs before `result_anomaly` is
        judged at all; with fewer, nothing is called
        an anomaly." The manifest ships the same
        defaults (extension.json: "anomaly_band":
        0.25, "anomaly_min_history": 3), the code's
        own fallback literals state them
        (lab_results.py lines 95 and 97-98: band
        falls back to 0.25, min_history to 3), and
        docs/extensions.md states the same contract
        (lines 93-94 ship the example tunables
        "anomaly_band": 0.25, "anomaly_min_history":
        3; line 399: "`result_anomaly` | A finished
        run's `metric` value sits farther than
        `anomaly_band` (relative) from the mean of
        the folder's earlier finished runs, with at
        least `anomaly_min_history` of them").

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 15:11 PDT tick)
        exercised the lab-results example
        extension's scan() -- the pure folder pass --
        over a folder holding one finished result
        (accuracy 2.0) with three earlier history
        values (1.0, 1.0, 1.0; mean 1.0), with the
        tunables omitted, set to genuine values
        (anomaly_band 0.25, anomaly_min_history 3
        and 2 and 5), and set to float("inf"),
        float("-inf"), float("nan"), and True for
        each of anomaly_band and
        anomaly_min_history.

    (c) Behavior actually observed: omitted,
        genuine, True, -inf, and NaN all behave as
        documented (the 2.0 value sits |2.0 - 1.0|
        = 1.0 from the mean, beyond 0.25 * 1.0, so
        scan() files experiment_finished and
        result_anomaly; anomaly_min_history 5
        correctly files only experiment_finished).
        The +inf values do not fall back:
        anomaly_min_history is computed as
        int(min_history) when _is_number holds
        (lab_results.py lines 96-98), and
        _is_number excludes booleans but not
        non-finite floats (line 49-50), so
        int(float("inf")) raises OverflowError:
        cannot convert float infinity to integer
        and scan() crashes on the pass instead of
        using the default 3. anomaly_band is
        computed as float(band) when _is_number
        holds and band > 0 (line 95); +inf passes
        both checks, so the band becomes infinite
        and abs(value - mean) > band * abs(mean)
        is never true -- result_anomaly is
        silently suppressed instead of using the
        default 0.25. Sibling readers in this
        codebase exclude non-finite values and
        fall back to their defaults; this reader
        does not. This is the campaign's known
        non-finite-tunable root-cause family.
        Observed on 2026-10-23: scan() with
        anomaly_min_history float("inf") raised
        OverflowError, and scan() with
        anomaly_band float("inf") returned only
        ["experiment_finished"], where the omitted
        tunables returned ["experiment_finished",
        "result_anomaly"].

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables):
        import importlib.util
        import json as _json
        import os
        import tempfile
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "lab-results",
            "lab_results.py")
        spec = importlib.util.spec_from_file_location(
            "lab_results_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "exp.json"),
                      "w", encoding="utf-8") as fh:
                _json.dump(
                    {"run": "exp-new", "status": "finished",
                     "metrics": {"accuracy": 2.0}}, fh)
            manifest = {"name": "lab_results",
                        "tunables": dict(tunables)}
            state = {"reported": {},
                     "history": [1.0, 1.0, 1.0]}
            alerts, _state = mod.scan(folder, manifest, state)
            return [a["signal"] for a in alerts]

    def test_infinite_min_history_defaults_to_3(self):
        self.assertEqual(
            self._signals(
                {"anomaly_min_history": float("inf")}),
            ["experiment_finished", "result_anomaly"])

    def test_infinite_band_defaults_to_0_25(self):
        self.assertEqual(
            self._signals({"anomaly_band": float("inf")}),
            ["experiment_finished", "result_anomaly"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented defaults and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        expected = ["experiment_finished", "result_anomaly"]
        self.assertEqual(self._signals({}), expected)
        self.assertEqual(
            self._signals({"anomaly_band": 0.25}), expected)
        self.assertEqual(
            self._signals({"anomaly_min_history": 3}),
            expected)
        self.assertEqual(
            self._signals({"anomaly_min_history": 2}),
            expected)
        self.assertEqual(
            self._signals({"anomaly_min_history": 5}),
            ["experiment_finished"])
        self.assertEqual(
            self._signals(
                {"anomaly_min_history": float("nan")}),
            expected)
        self.assertEqual(
            self._signals(
                {"anomaly_min_history": float("-inf")}),
            expected)
        self.assertEqual(
            self._signals({"anomaly_band": float("nan")}),
            expected)
        self.assertEqual(
            self._signals({"anomaly_band": True}), expected)



class TestNonFiniteLatencyPostTunablesDefaultInsteadOfSilence(unittest.TestCase):
    """Divergence: non-finite latency-post tunables
    (+inf / NaN / -inf spike_ms, +inf spike_factor)
    silently suppress latency_spike or drop its
    documented floor instead of falling back to the
    documented defaults (spike_ms 250, spike_factor 3).

    (a) Doc claim (examples/extensions/latency-post/
        README.md, line 30): "`latency_spike` | A
        probe's latency rises above both the
        `spike_ms` tunable (default 250) and
        `spike_factor` (default 3) times the median
        of the target's last samples, with at least
        3 prior samples". The manifest ships the
        same defaults (extension.json tunables:
        "spike_ms": 250, "spike_factor": 3), and
        the code's own fallback literals state them
        (latency_post.py lines 221 and 223-224:
        spike_ms falls back to 250.0, spike_factor
        to 3.0).

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 15:16 PDT tick)
        exercised the latency-post example
        extension's decide() -- the pure decision
        pass -- with a target holding three prior
        samples, with the tunables omitted, set to
        genuine values (spike_ms 250, spike_factor
        3), and set to float("inf"),
        float("-inf"), float("nan"), and True for
        each of spike_ms and spike_factor.

    (c) Behavior actually observed: omitted,
        genuine, and True all behave as documented
        (with prior samples [100, 100, 100], median
        100, the default threshold is
        max(250, 3 * 100) = 300, so a 1000 ms probe
        files latency_spike). The non-finite
        values do not fall back: spike_ms and
        spike_factor are computed as float(value)
        when _is_number holds (latency_post.py
        lines 220-224), and _is_number excludes
        booleans but not non-finite floats (line
        61), so +inf passes through and the spike
        test at line 261 (latency > max(spike_ms,
        spike_factor * median)) can never hold --
        latency_spike is silently suppressed
        instead of using the default 250 / 3.
        spike_ms NaN likewise poisons the max()
        to NaN, so the comparison is never true.
        spike_ms -inf drops the documented 250
        floor entirely: with prior samples
        [10, 10, 10] a 100 ms probe files
        latency_spike against max(-inf, 30) = 30,
        where the documented floor gives
        max(250, 30) = 250 and no spike. Sibling
        readers in this codebase exclude
        non-finite values and fall back to their
        defaults; this reader does not. This is
        the campaign's known non-finite-tunable
        root-cause family. Observed on 2026-10-23:
        decide() with spike_ms float("inf"),
        spike_factor float("inf"), or spike_ms
        float("nan") returned no alerts for the
        1000 ms probe where the omitted tunables
        returned ["latency_spike"], and decide()
        with spike_ms float("-inf") returned
        ["latency_spike"] for the 100 ms probe
        where the omitted tunables returned [].

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, samples, latency):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "latency-post",
            "latency_post.py")
        spec = importlib.util.spec_from_file_location(
            "latency_post_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        state = {"targets": {"t:443": {
            "samples": list(samples), "down": False,
            "spike_active": False}}}
        readings = {"now": 1792375113.0, "probes": [{
            "target": "t:443", "ok": True,
            "latency_ms": latency, "error": None}]}
        manifest = {"name": "latency_post",
                    "tunables": dict(tunables)}
        alerts, _state = mod.decide(readings, manifest, state)
        return [a["signal"] for a in alerts]

    def test_infinite_spike_ms_defaults_to_250(self):
        self.assertEqual(
            self._signals({"spike_ms": float("inf")},
                          [100.0, 100.0, 100.0], 1000.0),
            ["latency_spike"])

    def test_infinite_spike_factor_defaults_to_3(self):
        self.assertEqual(
            self._signals(
                {"spike_factor": float("inf")},
                [100.0, 100.0, 100.0], 1000.0),
            ["latency_spike"])

    def test_nan_spike_ms_defaults_to_250(self):
        self.assertEqual(
            self._signals({"spike_ms": float("nan")},
                          [100.0, 100.0, 100.0], 1000.0),
            ["latency_spike"])

    def test_negative_infinite_spike_ms_keeps_250_floor(self):
        self.assertEqual(
            self._signals({"spike_ms": float("-inf")},
                          [10.0, 10.0, 10.0], 100.0),
            [])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented defaults and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        spiked = ["latency_spike"]
        samples = [100.0, 100.0, 100.0]
        self.assertEqual(self._signals({}, samples, 1000.0),
                         spiked)
        self.assertEqual(
            self._signals(
                {"spike_ms": 250, "spike_factor": 3},
                samples, 1000.0),
            spiked)
        self.assertEqual(
            self._signals({"spike_ms": True},
                          samples, 1000.0),
            spiked)
        self.assertEqual(
            self._signals({"spike_factor": True},
                          samples, 1000.0),
            spiked)
        self.assertEqual(self._signals({}, samples, 100.0),
                         [])
        self.assertEqual(
            self._signals({"spike_ms": 2000},
                          samples, 1000.0),
            [])



class TestNonFiniteTrainingWatchTunablesDefaultInsteadOfSilenceOrCrash(unittest.TestCase):
    """Divergence: non-finite training-watch tunables
    (+inf / NaN gpu_temp_high_c and gpu_mem_high_pct,
    -inf gpu_temp_high_c, and +inf loss_points /
    loss_history / crash_window_lines /
    max_checkpoints) silently suppress or spuriously
    file the GPU signals, or crash decide() outright,
    instead of falling back to the documented
    defaults (gpu_temp_high_c 85, gpu_mem_high_pct
    95, loss_points 5, loss_history 200,
    crash_window_lines 100, max_checkpoints 200).

    (a) Doc claim (examples/extensions/training-watch/
        README.md, lines 21-22): "`gpu_overheating` |
        GPU temperature reaches `gpu_temp_high_c`
        (default 85)" and "`gpu_memory_pressure` |
        GPU memory reaches `gpu_mem_high_pct` of the
        card's total (default 95)". The same README
        states the remaining defaults: loss_points
        default 5 (line 56), crash_window_lines
        default 100 (line 68), loss_history default
        200 and max_checkpoints default 200
        (line 137). The manifest ships the same
        defaults (extension.json tunables), and the
        code's own fallback literals state them
        (training_watch.py lines 455-467).

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23) exercised the
        training-watch example extension's decide()
        -- the pure decision pass -- with a GPU
        reading of 90C and 96% memory (above both
        documented thresholds), a cool reading of
        50C and 50%, and empty readings, with the
        tunables omitted, set to genuine values,
        set to True, and set to float("inf"),
        float("-inf"), and float("nan").

    (c) Behavior actually observed: omitted, genuine,
        and True all behave as documented (the hot
        reading files both GPU signals; the cool
        reading files none). The non-finite values
        do not fall back: _tunable returns
        float(value) whenever _is_number holds
        (training_watch.py lines 177-179), and
        _is_number excludes booleans but not
        non-finite floats (lines 164-165), so +inf
        and NaN pass through as the GPU thresholds
        -- a 90C GPU never reaches an infinite
        threshold and a NaN comparison is never
        true, so gpu_overheating / gpu_memory_pressure
        are silently suppressed instead of using
        the defaults 85 / 95. gpu_temp_high_c -inf
        drops the documented 85 floor entirely: a
        cool 50C GPU files gpu_overheating against
        max threshold -inf. And the integer
        tunables are converted with int(_tunable(...))
        at lines 455, 459, 462, and 467, so +inf
        loss_points, loss_history,
        crash_window_lines, or max_checkpoints
        raises OverflowError ("cannot convert float
        infinity to integer") and decide() crashes
        instead of using the documented defaults.
        Sibling readers in this codebase exclude
        non-finite values and fall back to their
        defaults; this reader does not. This is the
        campaign's known non-finite-tunable
        root-cause family. Observed on 2026-10-23:
        decide() with gpu_temp_high_c float("inf")
        or float("nan") returned only
        ["gpu_memory_pressure"] for the hot reading,
        with gpu_mem_high_pct float("inf") or
        float("nan") only ["gpu_overheating"], with
        gpu_temp_high_c float("-inf")
        ["gpu_overheating"] for the cool reading,
        and with any of the four integer tunables
        float("inf") raised OverflowError, where
        the omitted tunables returned both GPU
        signals for the hot reading, [] for the
        cool reading, and [] without error for
        empty readings.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, gpu=None, readings_extra=None):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "training-watch",
            "training_watch.py")
        spec = importlib.util.spec_from_file_location(
            "training_watch_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        readings = {"now": 1792375113.0,
                    "checkpoints": [], "log_lines": [],
                    "run_alive": True}
        if gpu is not None:
            readings["gpu"] = gpu
        if readings_extra:
            readings.update(readings_extra)
        manifest = {"name": "training_watch",
                    "tunables": dict(tunables)}
        alerts, _state = mod.decide(readings, manifest, {})
        return [a["signal"] for a in alerts]

    _HOT = {"temp_c": 90.0, "mem_used_mb": 960,
            "mem_total_mb": 1000}
    _COOL = {"temp_c": 50.0, "mem_used_mb": 500,
             "mem_total_mb": 1000}
    _BOTH = ["gpu_memory_pressure", "gpu_overheating"]

    def test_infinite_temp_high_defaults_to_85(self):
        self.assertEqual(
            self._signals(
                {"gpu_temp_high_c": float("inf")}, self._HOT),
            self._BOTH)

    def test_nan_temp_high_defaults_to_85(self):
        self.assertEqual(
            self._signals(
                {"gpu_temp_high_c": float("nan")}, self._HOT),
            self._BOTH)

    def test_infinite_mem_high_defaults_to_95(self):
        self.assertEqual(
            self._signals(
                {"gpu_mem_high_pct": float("inf")}, self._HOT),
            self._BOTH)

    def test_nan_mem_high_defaults_to_95(self):
        self.assertEqual(
            self._signals(
                {"gpu_mem_high_pct": float("nan")}, self._HOT),
            self._BOTH)

    def test_negative_infinite_temp_high_keeps_85_floor(self):
        self.assertEqual(
            self._signals(
                {"gpu_temp_high_c": float("-inf")}, self._COOL),
            [])

    def test_infinite_int_tunables_default_instead_of_crash(self):
        for key in ("loss_points", "loss_history",
                    "crash_window_lines", "max_checkpoints"):
            with self.subTest(tunable=key):
                self.assertEqual(
                    self._signals({key: float("inf")}), [])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented defaults and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        self.assertEqual(self._signals({}, self._HOT),
                         self._BOTH)
        self.assertEqual(
            self._signals(
                {"gpu_temp_high_c": 85,
                 "gpu_mem_high_pct": 95}, self._HOT),
            self._BOTH)
        self.assertEqual(self._signals({}, self._COOL), [])
        self.assertEqual(
            self._signals(
                {"gpu_temp_high_c": True,
                 "gpu_mem_high_pct": True}, self._HOT),
            self._BOTH)
        self.assertEqual(
            self._signals(
                {"gpu_temp_high_c": 95}, self._HOT),
            ["gpu_memory_pressure"])
        self.assertEqual(self._signals({}), [])



class TestInfiniteReleaseDropMaxHashDefaultsTo512(unittest.TestCase):
    """Divergence: release-drop max_hash_mb float("inf")
    crashes read_live() with OverflowError instead of
    falling back to the documented default of 512.

    (a) Doc claim (examples/extensions/release-drop/
        README.md, line 21): "A file larger than
        `max_hash_mb` (default 512) is skipped entirely
        for the pass". The module docstring states the
        same (release_drop.py, line 26): "A file larger
        than the max_hash_mb tunable (default 512 MB) is
        SKIPPED entirely for the pass". The manifest
        ships the same default (extension.json tunables
        max_hash_mb 512), and the code's own fallback
        literal states it (release_drop.py line 89:
        512 * 1024 * 1024).

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23) exercised the
        release-drop example extension's read_live()
        -- the live folder pass -- over a temp drop
        folder holding one small file, with
        max_hash_mb omitted, set to genuine values,
        set to True, set to a bogus string, and set
        to float("inf"), float("-inf"), and
        float("nan"), and exercised the
        _max_hash_bytes() helper directly with the
        same values.

    (c) Behavior actually observed: omitted, genuine,
        True, bogus, zero, negative, -inf, and NaN
        all behave as documented (the small file is
        hashed and listed, or the helper returns the
        512 MB fallback). float("inf") does not fall
        back: _is_number excludes booleans but not
        non-finite floats (release_drop.py lines
        71-72), inf > 0 holds, and
        int(inf * 1024 * 1024) at line 88 raises
        OverflowError ("cannot convert float
        infinity to integer"), so read_live() crashes
        outright instead of using the documented
        default 512. Sibling readers in this codebase
        exclude non-finite values and fall back to
        their defaults; this reader does not. This is
        the campaign's known non-finite-tunable
        root-cause family. Observed on 2026-10-23:
        _max_hash_bytes({"max_hash_mb": float("inf")})
        raised OverflowError and read_live() over a
        one-file drop folder with that tunable raised
        the same error, where the omitted tunable
        listed the file with skipped_oversize 0.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _load(self):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "release-drop",
            "release_drop.py")
        spec = importlib.util.spec_from_file_location(
            "release_drop_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _read_live(self, tunables):
        import os
        import tempfile
        mod = self._load()
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "a.txt"),
                      "wb") as fh:
                fh.write(b"hello")
            full = {"watch_dir": td}
            full.update(tunables)
            manifest = {"name": "release_drop",
                        "tunables": full}
            return mod.read_live(manifest)

    def test_infinite_max_hash_bytes_defaults_to_512(self):
        mod = self._load()
        self.assertEqual(
            mod._max_hash_bytes(
                {"max_hash_mb": float("inf")}),
            512 * 1024 * 1024)

    def test_infinite_max_hash_read_live_lists_small_file(self):
        readings = self._read_live(
            {"max_hash_mb": float("inf")})
        self.assertEqual(readings["skipped_oversize"], 0)
        self.assertEqual(
            [f["name"] for f in readings["files"]],
            ["a.txt"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        mod = self._load()
        self.assertEqual(mod._max_hash_bytes({}),
                         512 * 1024 * 1024)
        self.assertEqual(
            mod._max_hash_bytes({"max_hash_mb": 512}),
            512 * 1024 * 1024)
        self.assertEqual(
            mod._max_hash_bytes({"max_hash_mb": 1}),
            1 * 1024 * 1024)
        for bogus in (True, False, "bogus", 0, -5,
                      float("-inf"), float("nan")):
            with self.subTest(max_hash_mb=bogus):
                self.assertEqual(
                    mod._max_hash_bytes(
                        {"max_hash_mb": bogus}),
                    512 * 1024 * 1024)
        readings = self._read_live({})
        self.assertEqual(
            [f["name"] for f in readings["files"]],
            ["a.txt"])




class TestNonFiniteZeekFeedTunablesDefaultInsteadOfCrashOrBoundlessWindow(unittest.TestCase):
    """Divergence: zeek-feed tunables float("inf")
    crash decide() with OverflowError or make the
    trailing window boundless instead of falling
    back to the documented defaults.

    (a) Doc claim (examples/extensions/zeek-feed/
        README.md, Tunables table lines 46-50):
        window_sec default 600 ("The trailing window
        first sightings accumulate in"),
        new_peer_threshold default 10 ("Distinct
        first-seen external responders inside the
        window that file"), query_length_threshold
        default 50 ("DNS query length that counts as
        anomalous"), and seen_peers_cap default 10000
        ("Bound on remembered peers (and filed DNS
        pairs)"). The Signals table states the same
        (lines 37-38), the manifest ships the same
        defaults (extension.json tunables), and the
        code's own fallback literals state them
        (zeek_feed.py lines 378, 380, 383-389).

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23) exercised the
        zeek-feed example extension's pure decide()
        with each tunable omitted, set to genuine
        values, set to float("nan"), and set to
        float("inf"): ten distinct external conn
        responders inside the window for the
        threshold and cap cases, the same ten spaced
        10,000 seconds apart for the window case,
        and one 72-character DNS query for the
        length case.

    (c) Behavior actually observed: omitted, genuine,
        and NaN values all behave as documented (NaN
        fails the >= 1 / > 0 guards and falls back).
        float("inf") does not fall back: _is_number
        excludes booleans but not non-finite floats
        (zeek_feed.py line 92), so inf passes the
        guards and int(inf) at lines 378, 385, and
        389 raises OverflowError ("cannot convert
        float infinity to integer"), crashing
        decide() for new_peer_threshold,
        query_length_threshold, and seen_peers_cap
        instead of using the documented defaults
        10, 50, and 10000. For window_sec, float(inf)
        at lines 380-381 becomes an infinite trailing
        window, so ten first-seen peers spaced
        10,000 seconds apart file
        zeek_new_external_peers, where the documented
        600-second window files nothing. This is the
        campaign's known non-finite-tunable
        root-cause family in a new reader.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _load(self):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "zeek-feed",
            "zeek_feed.py")
        spec = importlib.util.spec_from_file_location(
            "zeek_feed_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _conn_events(self, n, start_ts=1000.0,
                     spacing=10.0):
        return [{"ts": start_ts + i * spacing,
                 "kind": "conn",
                 "resp_h": f"8.8.{i // 250}.{i % 250 + 1}",
                 "orig_h": "192.168.1.5"}
                for i in range(n)]

    def _decide(self, tunables, events, now=2000.0):
        mod = self._load()
        manifest = {"name": "zeek_feed",
                    "tunables": tunables}
        alerts, _state = mod.decide(
            {"now": now, "events": events}, manifest, None)
        return alerts

    def test_infinite_new_peer_threshold_defaults_to_10(self):
        alerts = self._decide(
            {"new_peer_threshold": float("inf")},
            self._conn_events(10))
        self.assertEqual(
            [a["signal"] for a in alerts],
            ["zeek_new_external_peers"])
        self.assertEqual(
            alerts[0]["detail"]["threshold"], 10)

    def test_infinite_query_length_threshold_defaults_to_50(self):
        query = "a" * 60 + ".example.com"
        events = [{"ts": 1000.0, "kind": "dns",
                   "query": query, "qtype_name": "A",
                   "resp_h": "8.8.8.8",
                   "orig_h": "192.168.1.5"}]
        alerts = self._decide(
            {"query_length_threshold": float("inf")},
            events)
        self.assertEqual(
            [a["signal"] for a in alerts],
            ["zeek_dns_anomaly"])

    def test_infinite_seen_peers_cap_defaults_to_10000(self):
        alerts = self._decide(
            {"seen_peers_cap": float("inf")},
            self._conn_events(10))
        self.assertEqual(
            [a["signal"] for a in alerts],
            ["zeek_new_external_peers"])

    def test_infinite_window_defaults_to_600(self):
        # Ten peers spaced 10,000s apart are never
        # inside one 600s window, so nothing files.
        alerts = self._decide(
            {"window_sec": float("inf")},
            self._conn_events(10, spacing=10000.0),
            now=100000.0)
        self.assertEqual(alerts, [])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented defaults and genuine
        # values already behave today and must keep
        # doing so after the non-finite case is fixed.
        alerts = self._decide({}, self._conn_events(10))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(
            alerts[0]["detail"]["threshold"], 10)
        self.assertEqual(
            alerts[0]["detail"]["window_sec"], 600)
        self.assertEqual(
            self._decide({}, self._conn_events(9)), [])
        self.assertEqual(
            self._decide(
                {}, self._conn_events(10, spacing=10000.0),
                now=100000.0), [])
        alerts = self._decide(
            {"new_peer_threshold": 3},
            self._conn_events(3))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(
            alerts[0]["detail"]["threshold"], 3)
        # NaN already falls back today for every
        # tunable in this class.
        for key in ("new_peer_threshold",
                    "query_length_threshold",
                    "seen_peers_cap", "window_sec"):
            with self.subTest(tunable=key):
                alerts = self._decide(
                    {key: float("nan")},
                    self._conn_events(10))
                self.assertEqual(len(alerts), 1)




class TestInfiniteFalcoCooldownDefaultsTo3600(unittest.TestCase):
    """Divergence: an infinite falco-feed
    episode_cooldown_sec (+inf) suppresses re-filing
    forever instead of falling back to the documented
    3600-second default.

    (a) Doc claim (examples/extensions/falco-feed/
        README.md, tunable table, line 73):
        "episode_cooldown_sec | 3600 | An episode refiles
        after this long, and clears after this long
        quiet"; the same default is in the extension's
        extension.json tunables (3600) and in
        falco_feed.py's decide() docstring: an episode
        files again when episode_cooldown_sec has passed
        since it last filed.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the falco-feed
        example extension's decide() -- the pure decision
        function -- with episode_cooldown_sec omitted, set
        to a genuine value, and set to float("inf") and
        float("nan"), using one Warning episode firing at
        t=1000 and again at t=8200 (7200 seconds later,
        twice the documented cooldown).

    (c) Behavior actually observed: omitted, NaN, and an
        explicit 3600 all file twice (the second sighting
        is past the cooldown), and an explicit 10000 files
        once, as documented. But +inf is accepted as a
        number -- _is_number in falco_feed.py excludes
        booleans but not non-finite floats, and inf > 0
        holds -- so the cooldown becomes infinite: the
        t=8200 sighting only updates last_seen and never
        re-files, and the episode never clears. Sibling
        readers in this codebase exclude non-finite values
        and fall back to their defaults; this reader does
        not. Observed on 2026-10-23: decide() with
        {"episode_cooldown_sec": float("inf")} on events
        at 1000 and 8200 returned ['falco_warning'] once,
        where the omitted tunable returned it twice. This
        is the campaign's known non-finite-tunable
        root-cause family in a new reader.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, stamps=(1000.0, 8200.0)):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "falco-feed",
            "falco_feed.py")
        spec = importlib.util.spec_from_file_location(
            "falco_feed_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        events = [{
            "ts": ts, "rule": "Test Rule",
            "priority": "Warning",
            "output_fields": {"proc.name": "sh"},
            "fields_digest": "abc", "output": "x",
            "hostname": "h"} for ts in stamps]
        alerts, _state = mod.decide(
            {"now": stamps[-1], "events": events},
            {"name": "falco_feed", "tunables": tunables},
            {})
        return [a["signal"] for a in alerts]

    def test_infinite_cooldown_defaults_to_3600(self):
        self.assertEqual(
            self._signals(
                {"episode_cooldown_sec": float("inf")}),
            ["falco_warning", "falco_warning"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep doing
        # so after the non-finite case is fixed.
        self.assertEqual(
            self._signals({}),
            ["falco_warning", "falco_warning"])
        self.assertEqual(
            self._signals({"episode_cooldown_sec": 3600}),
            ["falco_warning", "falco_warning"])
        self.assertEqual(
            self._signals({"episode_cooldown_sec": 10000}),
            ["falco_warning"])
        self.assertEqual(
            self._signals({}, (1000.0, 2000.0)),
            ["falco_warning"])
        self.assertEqual(
            self._signals(
                {"episode_cooldown_sec": float("nan")}),
            ["falco_warning", "falco_warning"])



class TestInfiniteSuricataCooldownDefaultsTo3600(unittest.TestCase):
    """Divergence: an infinite suricata-feed
    episode_cooldown_sec (+inf) suppresses re-filing
    forever instead of falling back to the documented
    3600-second default.

    (a) Doc claim (examples/extensions/suricata-feed/
        README.md, tunable table, line 68):
        "episode_cooldown_sec | 3600 | An episode refiles
        after this long, and clears after this long
        quiet; also the anomaly dedup window"; the same
        default is in the extension's extension.json
        tunables (3600) and in suricata_feed.py's
        decide() docstring: an episode files again when
        episode_cooldown_sec has passed since it last
        filed.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the suricata-feed
        example extension's decide() -- the pure decision
        function -- with episode_cooldown_sec omitted, set
        to a genuine value, and set to float("inf") and
        float("nan"), using one alert episode (signature_id
        1, 1.2.3.4 -> 5.6.7.8) firing at t=1000 and again
        at t=8200 (7200 seconds later, twice the
        documented cooldown).

    (c) Behavior actually observed: omitted, NaN, and an
        explicit 3600 all file twice (the second sighting
        is past the cooldown), and an explicit 10000 files
        once, as documented. But +inf is accepted as a
        number -- _is_number in suricata_feed.py excludes
        booleans but not non-finite floats, and inf > 0
        holds -- so the cooldown becomes infinite: the
        t=8200 sighting only updates last_seen and never
        re-files, and the episode never clears. Sibling
        readers in this codebase exclude non-finite values
        and fall back to their defaults; this reader does
        not. Observed on 2026-10-23: decide() with
        {"episode_cooldown_sec": float("inf")} on events
        at 1000 and 8200 returned ['suricata_alert'] once,
        where the omitted tunable returned it twice. This
        is the campaign's known non-finite-tunable
        root-cause family in a new reader.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, stamps=(1000.0, 8200.0)):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "suricata-feed",
            "suricata_feed.py")
        spec = importlib.util.spec_from_file_location(
            "suricata_feed_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        events = [{
            "ts": ts, "kind": "alert", "signature_id": 1,
            "alert_severity": 1, "signature": "Test Sig",
            "category": "test", "src_ip": "1.2.3.4",
            "dest_ip": "5.6.7.8", "src_port": 1234,
            "dest_port": 80, "proto": "TCP"} for ts in stamps]
        alerts, _state = mod.decide(
            {"now": stamps[-1], "events": events},
            {"name": "suricata_feed", "tunables": tunables},
            {})
        return [a["signal"] for a in alerts]

    def test_infinite_cooldown_defaults_to_3600(self):
        self.assertEqual(
            self._signals(
                {"episode_cooldown_sec": float("inf")}),
            ["suricata_alert", "suricata_alert"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep doing
        # so after the non-finite case is fixed.
        self.assertEqual(
            self._signals({}),
            ["suricata_alert", "suricata_alert"])
        self.assertEqual(
            self._signals({"episode_cooldown_sec": 3600}),
            ["suricata_alert", "suricata_alert"])
        self.assertEqual(
            self._signals({"episode_cooldown_sec": 10000}),
            ["suricata_alert"])
        self.assertEqual(
            self._signals({}, (1000.0, 2000.0)),
            ["suricata_alert"])
        self.assertEqual(
            self._signals(
                {"episode_cooldown_sec": float("nan")}),
            ["suricata_alert", "suricata_alert"])

class TestInfiniteWazuhQuietDefaultsTo3600(unittest.TestCase):
    """Divergence: an infinite wazuh-feed
    episode_quiet_sec (+inf) suppresses re-filing
    forever instead of falling back to the documented
    3600-second default.

    (a) Doc claim (examples/extensions/wazuh-feed/
        README.md, tunable table, line 69):
        "episode_quiet_sec | 3600 | How long a (rule,
        agent) pair must stay quiet before its next
        alert files as a new episode"; the same
        default is in the extension's extension.json
        tunables (3600) and in wazuh_feed.py's module
        docstring: an episode re-arms once
        episode_quiet_sec has passed with no further
        alert for that pair.

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the wazuh-feed
        example extension's decide() -- the pure decision
        function -- with episode_quiet_sec omitted, set
        to a genuine value, and set to float("inf") and
        float("nan"), using one alert episode (rule_id
        5710, agent web-1, level 7) firing at t=1000 and
        again at t=8200 (7200 seconds later, twice the
        documented quiet period).

    (c) Behavior actually observed: omitted, NaN, and an
        explicit 3600 all file twice (the second sighting
        is past the quiet period), and an explicit 10000
        files once, as documented. But +inf is accepted as a
        number -- _is_number in wazuh_feed.py excludes
        booleans but not non-finite floats, and inf > 0
        holds -- so the quiet period becomes infinite: the
        t=8200 sighting only updates last_seen and never
        re-files. Sibling readers in this codebase exclude
        non-finite values and fall back to their defaults;
        this reader does not. Observed on 2026-10-23:
        decide() with {"episode_quiet_sec": float("inf")}
        on events at 1000 and 8200 returned
        ['wazuh_alert'] once, where the omitted tunable
        returned it twice. This is the campaign's known
        non-finite-tunable root-cause family in a new
        reader.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, stamps=(1000.0, 8200.0)):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "wazuh-feed",
            "wazuh_feed.py")
        spec = importlib.util.spec_from_file_location(
            "wazuh_feed_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        events = [{
            "ts": ts, "level": 7, "rule_id": "5710",
            "description": "Test alert", "groups": [],
            "agent_name": "web-1", "agent_id": "001"}
            for ts in stamps]
        alerts, _state = mod.decide(
            {"now": stamps[-1], "events": events},
            {"name": "wazuh_feed", "tunables": tunables},
            {})
        return [a["signal"] for a in alerts]

    def test_infinite_quiet_defaults_to_3600(self):
        self.assertEqual(
            self._signals(
                {"episode_quiet_sec": float("inf")}),
            ["wazuh_alert", "wazuh_alert"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep doing
        # so after the non-finite case is fixed.
        self.assertEqual(
            self._signals({}),
            ["wazuh_alert", "wazuh_alert"])
        self.assertEqual(
            self._signals({"episode_quiet_sec": 3600}),
            ["wazuh_alert", "wazuh_alert"])
        self.assertEqual(
            self._signals({"episode_quiet_sec": 10000}),
            ["wazuh_alert"])
        self.assertEqual(
            self._signals({}, (1000.0, 2000.0)),
            ["wazuh_alert"])
        self.assertEqual(
            self._signals(
                {"episode_quiet_sec": float("nan")}),
            ["wazuh_alert", "wazuh_alert"])


class TestInfiniteOsqueryFiledCapCrashesInsteadOfDefault(unittest.TestCase):
    """Divergence: an infinite osquery-feed filed_cap
    (+inf) crashes decide() with OverflowError instead
    of falling back to the documented 10000 default.

    (a) Doc claim (examples/extensions/osquery-feed/
        README.md, tunable table, line 46):
        "filed_cap | 10000 | Bound on remembered filed
        episodes; the oldest entries are evicted first";
        the same default is in the extension's
        extension.json tunables (10000).

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the osquery-feed
        example extension's decide() -- the pure decision
        function -- with filed_cap omitted, set to a
        genuine value, and set to float("inf"),
        float("-inf") and float("nan"), using one
        differential event (a user row reported added).

    (c) Behavior actually observed: omitted, NaN, -inf
        and an explicit 10000 all file the event once,
        as documented. But +inf is accepted as a number
        -- _is_number in osquery_feed.py excludes
        booleans but not non-finite floats, and
        inf >= 1 holds -- so decide() evaluates
        int(float("inf")) and raises OverflowError:
        cannot convert float infinity to integer. The
        whole pass crashes and no alert files, instead
        of the reader falling back to 10000 like its
        sibling readers do for non-finite values.
        Observed on 2026-10-23: decide() with
        {"filed_cap": float("inf")} raised OverflowError
        on a single added-user event, where the omitted
        tunable returned ['osquery_added']. This is the
        campaign's known non-finite-tunable root-cause
        family in a new reader.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables, events=None):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "osquery-feed",
            "osquery_feed.py")
        spec = importlib.util.spec_from_file_location(
            "osquery_feed_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if events is None:
            events = [{
                "ts": 1000, "action": "added",
                "kind": "user",
                "columns": {"username": "eve",
                            "uid": "1001", "gid": "1001"}}]
        alerts, _state = mod.decide(
            {"now": 1000, "events": events},
            {"name": "osquery_feed", "tunables": tunables},
            {})
        return [a["signal"] for a in alerts]

    def test_infinite_filed_cap_defaults_to_10000(self):
        self.assertEqual(
            self._signals({"filed_cap": float("inf")}),
            ["osquery_added"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep doing
        # so after the non-finite case is fixed.
        self.assertEqual(self._signals({}), ["osquery_added"])
        self.assertEqual(
            self._signals({"filed_cap": 10000}),
            ["osquery_added"])
        self.assertEqual(
            self._signals({"filed_cap": float("nan")}),
            ["osquery_added"])
        self.assertEqual(
            self._signals({"filed_cap": float("-inf")}),
            ["osquery_added"])
        # A genuine small cap is honored: with cap 1 the
        # first identity is evicted by the second, so its
        # repeat add files again (3 alerts), while the
        # default cap files each identity once (2).
        def _add(name):
            return {"ts": 1000, "action": "added",
                    "kind": "user",
                    "columns": {"username": name,
                                "uid": "1", "gid": "1"}}
        events = [_add("a"), _add("b"), _add("a")]
        self.assertEqual(
            len(self._signals({"filed_cap": 1}, events)), 3)
        self.assertEqual(len(self._signals({}, events)), 2)


class TestNonFiniteSoftflowdTunablesDefaultInsteadOfCrashOrSilence(unittest.TestCase):
    """Divergence: non-finite softflowd-feed tunables
    (+inf) crash decide() with OverflowError or suppress
    flow_long_lived instead of falling back to the
    documented defaults.

    (a) Doc claim (examples/extensions/softflowd-feed/
        README.md, Tunables table): "high_volume_bytes |
        50000000", "long_lived_sec | 3600",
        "max_known_peers | 1024", "max_filed_flows |
        1024"; the same defaults are in the extension's
        extension.json tunables (50000000 / 3600 / 1024 /
        1024).

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the softflowd-feed
        example extension's decide() -- the pure decision
        function -- with each tunable omitted, set to a
        genuine value, and set to float("inf") and
        float("nan"), using one flow (192.168.1.20 ->
        8.8.8.8:443, 60,000,000 bytes, first 1000, last
        8200, duration 7200s) that files all three signals
        under the defaults.

    (c) Behavior actually observed: omitted, NaN and
        explicit defaults all file
        ['flow_new_external_peer', 'flow_high_volume',
        'flow_long_lived'], as documented. But +inf is
        accepted as a number -- _is_number in
        softflowd_feed.py excludes booleans but not
        non-finite floats, and inf > 0 / inf >= 1 hold --
        so high_volume_bytes, max_known_peers and
        max_filed_flows evaluate int(float("inf")) and
        raise OverflowError: cannot convert float
        infinity to integer, crashing the whole pass;
        and long_lived_sec=float("inf") becomes an
        infinite threshold, so the 7200s flow files no
        flow_long_lived instead of falling back to 3600.
        This is the campaign's known non-finite-tunable
        root-cause family in a new reader.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    def _signals(self, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "softflowd-feed",
            "softflowd_feed.py")
        spec = importlib.util.spec_from_file_location(
            "softflowd_feed_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        flow = {"src": "192.168.1.20", "dst": "8.8.8.8",
                "src_port": 12345, "dst_port": 443,
                "proto": 6, "packets": 10,
                "bytes": 60_000_000,
                "first": 1000, "last": 8200}
        alerts, _state = mod.decide(
            {"now": 9000, "flows": [flow]},
            {"name": "softflowd_feed", "tunables": tunables},
            {})
        return [a["signal"] for a in alerts]

    _ALL = ["flow_new_external_peer", "flow_high_volume",
            "flow_long_lived"]

    def test_infinite_high_volume_defaults_to_50000000(self):
        self.assertEqual(
            self._signals({"high_volume_bytes": float("inf")}),
            self._ALL)

    def test_infinite_max_known_peers_defaults_to_1024(self):
        self.assertEqual(
            self._signals({"max_known_peers": float("inf")}),
            self._ALL)

    def test_infinite_max_filed_flows_defaults_to_1024(self):
        self.assertEqual(
            self._signals({"max_filed_flows": float("inf")}),
            self._ALL)

    def test_infinite_long_lived_defaults_to_3600(self):
        self.assertEqual(
            self._signals({"long_lived_sec": float("inf")}),
            self._ALL)

    def test_omitted_and_explicit_values_are_honored(self):
        self.assertEqual(self._signals({}), self._ALL)
        self.assertEqual(
            self._signals({"high_volume_bytes": 50000000,
                           "long_lived_sec": 3600,
                           "max_known_peers": 1024,
                           "max_filed_flows": 1024}),
            self._ALL)
        self.assertEqual(
            self._signals({"high_volume_bytes": float("nan"),
                           "long_lived_sec": float("nan")}),
            self._ALL)
        # A genuine larger threshold is honored: 61 MB
        # high-volume threshold files no flow_high_volume
        # for this 60 MB flow.
        self.assertEqual(
            self._signals({"high_volume_bytes": 61_000_000}),
            ["flow_new_external_peer", "flow_long_lived"])


class TestHugeIntJobFuzzFloatTunablesCrashInsteadOfDefault(unittest.TestCase):
    """Divergence: a huge-integer job-fuzz float tunable
    (corpus_max_age_days = 10**400, or filed_cooldown_sec
    = 10**400) crashes decide() with OverflowError instead
    of falling back to the documented defaults.

    (a) Doc claim (examples/extensions/job-fuzz/README.md,
        line 61): the corpus is bounded by age with
        "`corpus_max_age_days` (default 30)"; and (line 113):
        "`filed_cooldown_sec` (default 604800, a week) is
        how long a finding that was already filed stays
        quiet". The same defaults are in the module
        docstring in job_fuzz.py (lines 57-58: "by age
        (corpus_max_age_days, default 30)"; line 97: "may
        file again after filed_cooldown_sec (default a
        week)") and in extension.json tunables
        (corpus_max_age_days 30, filed_cooldown_sec
        604800).

    (b) How the bug was found: the campaign's doc-default
        hunt (2026-10-23 tick) exercised the job-fuzz
        example extension's decide() -- the pure decision
        function -- with each float tunable omitted, set
        to a genuine value, set to float("inf") and
        float("nan") (both already guarded in this reader),
        and set to the huge integer 10**400, a value JSON
        config carries as an ordinary number, using one
        seed job saved 40 days before the pass's "now".

    (c) Behavior actually observed: omitted, explicit 30,
        +inf and NaN all apply the documented 30-day age
        bound (the 40-day-old seed is evicted from the
        corpus), and explicit 60 retains it. But a huge
        integer is accepted as a number -- _is_number in
        job_fuzz.py (lines 201-204) excludes booleans and
        non-finite floats, not oversized ints -- so
        _tunable (line 220-222) evaluates float(10**400)
        and raises OverflowError: int too large to convert
        to float, at job_fuzz.py lines 1108 (age) and 1110
        (cooldown). The whole pass crashes and no state is
        returned, instead of the reader falling back to
        30 / 604800 like it does for non-finite values.
        Observed on 2026-10-23: decide() with
        {"corpus_max_age_days": 10**400} and with
        {"filed_cooldown_sec": 10**400} each raised that
        OverflowError on the seed above, where the omitted
        tunables returned an evicted corpus.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    NOW = 1000 + 40 * 86400

    def _corpus(self, tunables):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "job-fuzz",
            "job_fuzz.py")
        spec = importlib.util.spec_from_file_location(
            "job_fuzz_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        seeds = [{"job_id": "old-job", "saved_at": 1000,
                  "exit_code": 0}]
        alerts, state = mod.decide(
            {"now": self.NOW, "seeds": seeds,
             "outcomes": []},
            {"name": "job_fuzz", "tunables": tunables},
            {})
        return sorted(state["corpus"]), alerts

    def test_huge_corpus_max_age_days_defaults_to_30(self):
        corpus, _alerts = self._corpus(
            {"corpus_max_age_days": 10 ** 400})
        self.assertEqual(corpus, [])

    def test_huge_filed_cooldown_defaults_to_604800(self):
        corpus, alerts = self._corpus(
            {"filed_cooldown_sec": 10 ** 400})
        self.assertEqual(corpus, [])
        self.assertEqual(alerts, [])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep doing
        # so after the huge-int case is fixed.
        self.assertEqual(self._corpus({})[0], [])
        self.assertEqual(
            self._corpus({"corpus_max_age_days": 30})[0],
            [])
        self.assertEqual(
            self._corpus(
                {"corpus_max_age_days": float("inf")})[0],
            [])
        self.assertEqual(
            self._corpus(
                {"corpus_max_age_days": float("nan")})[0],
            [])
        # A genuine larger bound is honored: at 60 days
        # the 40-day-old seed is retained.
        self.assertEqual(
            self._corpus({"corpus_max_age_days": 60})[0],
            ["old-job"])



class TestHugeIntLatencyPostTunablesCrashInsteadOfDefault(unittest.TestCase):
    """Divergence: a huge-integer latency-post tunable
    (spike_ms = 10**400, or spike_factor = 10**400)
    crashes decide() with OverflowError instead of
    falling back to the documented defaults.

    (a) Doc claim (examples/extensions/latency-post/
        README.md, line 30): "`latency_spike` | A
        probe's latency rises above both the
        `spike_ms` tunable (default 250) and
        `spike_factor` (default 3) times the median
        of the target's last samples, with at least
        3 prior samples". The manifest ships the
        same defaults (extension.json tunables:
        "spike_ms": 250, "spike_factor": 3), and the
        code's own fallback literals state them
        (latency_post.py lines 221 and 223-224:
        spike_ms falls back to 250.0, spike_factor
        to 3.0).

    (b) How the bug was found: the campaign's
        doc-default hunt (2026-10-23 tick) exercised
        the latency-post example extension's
        decide() -- the pure decision pass -- with a
        target holding three prior samples
        [100, 100, 100] and a 1000 ms probe, with
        the tunables omitted, set to genuine values
        (spike_ms 250, spike_factor 3), set to True
        (already guarded in this reader), and set
        to the huge integer 10**400, a value JSON
        config carries as an ordinary number.

    (c) Behavior actually observed: omitted,
        genuine, and True all behave as documented
        (the default threshold is max(250, 3 * 100)
        = 300, so the 1000 ms probe files
        latency_spike). A huge integer is accepted
        as a number -- _is_number in latency_post.py
        (line 61) excludes booleans but imposes no
        magnitude bound -- so decide() evaluates
        float(10**400) at line 221 (spike_ms) and
        lines 223-224 (spike_factor) and raises
        OverflowError: int too large to convert to
        float. The whole pass crashes and no alerts
        are returned, instead of the reader falling
        back to 250 / 3. This is the campaign's
        known conversion-overflow input class, seen
        earlier in the job-fuzz reader. Observed on
        2026-10-23: decide() with
        {"spike_ms": 10**400} and with
        {"spike_factor": 10**400} each raised that
        OverflowError on the scenario above, where
        the omitted tunables returned
        ["latency_spike"].

    (d) Do not make this test pass by editing the
        test. It passes only when the bug described
        above is fixed in the code.
    """

    def _signals(self, tunables, samples, latency):
        import importlib.util
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "examples", "extensions", "latency-post",
            "latency_post.py")
        spec = importlib.util.spec_from_file_location(
            "latency_post_huge_divergence", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        state = {"targets": {"t:443": {
            "samples": list(samples), "down": False,
            "spike_active": False}}}
        readings = {"now": 1792375113.0, "probes": [{
            "target": "t:443", "ok": True,
            "latency_ms": latency, "error": None}]}
        manifest = {"name": "latency_post",
                    "tunables": dict(tunables)}
        alerts, _state = mod.decide(readings, manifest, state)
        return [a["signal"] for a in alerts]

    def test_huge_spike_ms_defaults_to_250(self):
        self.assertEqual(
            self._signals({"spike_ms": 10 ** 400},
                          [100.0, 100.0, 100.0], 1000.0),
            ["latency_spike"])

    def test_huge_spike_factor_defaults_to_3(self):
        self.assertEqual(
            self._signals({"spike_factor": 10 ** 400},
                          [100.0, 100.0, 100.0], 1000.0),
            ["latency_spike"])

    def test_omitted_and_explicit_values_are_honored(self):
        # Controls: the documented default and genuine
        # values already behave today and must keep
        # doing so after the huge-int case is fixed.
        self.assertEqual(
            self._signals({}, [100.0, 100.0, 100.0],
                          1000.0),
            ["latency_spike"])
        self.assertEqual(
            self._signals({"spike_ms": 250,
                           "spike_factor": 3},
                          [100.0, 100.0, 100.0], 1000.0),
            ["latency_spike"])
        self.assertEqual(
            self._signals({"spike_ms": True},
                          [100.0, 100.0, 100.0], 1000.0),
            ["latency_spike"])
        # A genuine higher floor is honored: at
        # spike_ms 2000 the 1000 ms probe is in band.
        self.assertEqual(
            self._signals({"spike_ms": 2000},
                          [100.0, 100.0, 100.0], 1000.0),
            [])


class TestPlanStepTimeoutSecDefaultsTo60(unittest.TestCase):
    """Second-run hunt coverage: the plan-step
    timeout_sec itself, varied with the fifteen
    shapes through its actual reader for the
    first time.

    (a) Claim: registry row "timeout_sec (plan
        step)": integer, default 60, policy
        default, doc_status unverified -- no
        prose document states this default. The
        only statement is the reader's own
        docstring (runner/detection.py,
        check_plan_budget, lines 113-114): "A
        step whose timeout_sec is omitted,
        unparseable, or a boolean counts as 60
        seconds." The prose doc for the same
        function (docs/configuring-oracle.md,
        line 80) states only the totals it sums
        toward: "`max_plan_steps` /
        `max_plan_timeout_sec` -- caps the
        detection layer (`runner/detection.py`)
        applies to a multi-step plan: at most
        this many steps (default 8) and this
        much total timeout in seconds (default
        600)." The step-8 Target 3 finding on
        provenance therefore stands: the 60
        default rests on the reader (line 130:
        _confval.integer(step.get("timeout_sec"),
        60, lo=1)) and this registry row, not on
        any documented line -- see
        KNOWN_UNDOCUMENTED in
        tests/defaults_registry.py. The row's
        named class
        (TestBooleanPlanStepTimeoutCountsAs60)
        varies the boolean shapes only, and the
        table hunt probes this row through
        confval, not through check_plan_budget.

    (b) How it was hunted: step 8 Target 3 --
        the first row with no documented
        default in any current doc. On
        2026-10-23 this tick probed
        check_plan_budget -- the actual reader
        -- with the table hunt's fifteen shapes
        for a single step's timeout_sec, each
        shape asserted exactly, not just by
        side: with the total cap at 59 a step
        counting as 60 is refused with "plan
        timeout 60s exceeds 59s", and with the
        cap at 60 the same step is allowed, so
        the effective value is pinned to 60
        from both sides.

    (c) Behavior actually observed: NO
        divergence in behavior. Every shape --
        omitted, null, the empty string, true,
        false, zero, a negative number, the
        explicit default 60, a numeric string,
        a non-numeric string, a
        several-hundred-digit integer, inf,
        -inf, NaN, and a list -- counted as
        exactly 60 seconds. This reader goes
        through runner/confval.integer, which
        never counts a boolean as a number,
        requires a finite value at least 1,
        and parses numeric strings, so a
        numeric string "100" counts as 100
        (a genuine value, honored below),
        unlike the extension readers that
        accept only genuine JSON numbers.
        Genuine values are honored exactly:
        1, 10, 45, 100 and "100" each count
        as themselves against a cap one
        second below them.

    (d) This is a coverage record, not a
        divergence: it stays green as long as
        the reader keeps the registry default.
        If a shape above ever stops counting
        as 60, this test is the failing record
        of that change. The documentation gap
        in (a) is recorded here and in the
        registry; no production code or doc
        was changed by this hunt.
    """

    def _check(self, step, cap):
        from runner.detection import check_plan_budget
        return check_plan_budget(
            [step], {"max_plan_timeout_sec": cap})

    def test_fifteen_shapes_count_as_default_60(self):
        shapes = [
            ("omitted", None), ("null", None),
            ("empty-string", ""), ("true", True),
            ("false", False), ("zero", 0),
            ("negative", -5), ("default-explicit", 60),
            ("numeric-string", "60"),
            ("non-numeric-string", "bogus"),
            ("huge-int", 10 ** 400), ("inf", float("inf")),
            ("neg-inf", float("-inf")), ("nan", float("nan")),
            ("wrong-container", ["x"]),
        ]
        for name, value in shapes:
            with self.subTest(shape=name):
                step = {} if name == "omitted" else {
                    "timeout_sec": value}
                self.assertEqual(
                    self._check(step, 59),
                    (False, "plan timeout 60s exceeds 59s"))
                self.assertEqual(
                    self._check(step, 60), (True, ""))

    def test_genuine_step_timeouts_are_honored(self):
        for value in (10, 45, 100, "100"):
            want = int(value)
            with self.subTest(value=value):
                self.assertEqual(
                    self._check({"timeout_sec": value}, want - 1),
                    (False,
                     f"plan timeout {want}s exceeds {want - 1}s"))
                self.assertEqual(
                    self._check({"timeout_sec": value}, want),
                    (True, ""))
        # 1 is pinned differently: a cap of 0 is
        # itself unusable and reads as the 600
        # default, so there is no usable cap one
        # below 1. One 1-second step passes at a
        # cap of 1 (it would fail if it counted
        # as the 60 default), and two of them
        # total exactly 2 against that cap.
        self.assertEqual(
            self._check({"timeout_sec": 1}, 1), (True, ""))
        from runner.detection import check_plan_budget
        self.assertEqual(
            check_plan_budget(
                [{"timeout_sec": 1}] * 2,
                {"max_plan_timeout_sec": 1}),
            (False, "plan timeout 2s exceeds 1s"))



class TestExtensionPollIntervalSecDefaultsTo2(unittest.TestCase):
    """Second-run hunt coverage: extension_poll_interval_sec
    itself, varied with the fifteen shapes through its
    actual reader for the first time.

    (a) Claim: registry row "extension_poll_interval_sec":
        core, number, default 2, policy default,
        doc_status unverified -- no prose document states
        this default; it is in KNOWN_UNDOCUMENTED in
        tests/defaults_registry.py. The statements are the
        reader's own docstring
        (runner/transport_extensions/channel.py,
        poll_interval): "Seconds between passes:
        extension_poll_interval_sec, default 2. A usable
        number is clamped to [0.2, 60]. A boolean, a huge
        integer, infinity, NaN, or a non-number is not an
        interval and reads as the default", and the repo's
        own tests/test_transport_shells.py pin (omitted ->
        2.0, 0 -> 0.2, 1000 -> 60.0, "nope" -> 2.0). The
        row's named classes covered only the huge-int
        shape (TestHugeExtensionPollIntervalDefaultsTo2)
        and the booleans
        (TestBooleanExtensionPollIntervalDefaultsTo2);
        this key had never itself been walked through all
        fifteen shapes. Provenance finding from the
        step-8 list, re-verified this tick: the runner's
        runtime-config projection
        (runner/transports.py, _runtime_config) never
        passes a TOP-LEVEL extension_poll_interval_sec to
        an extension -- with the key only at top level the
        projected config has no such key at all; only a
        copy inside a transport_<name> block reaches the
        reader verbatim (a block copy of 7 projected as 7
        while a top-level 9 was dropped).

    (b) How it was hunted: step 8 Target 3 -- the second
        row with no documented default in any current
        doc. On 2026-10-23 this tick called
        channel.poll_interval -- the actual reader every
        polling transport extension takes its cadence
        from -- with the table hunt's fifteen shapes,
        plus genuine values and both clamp ends.

    (c) Behavior actually observed: NO divergence in
        the reader. Every unusable shape -- omitted,
        null, the empty string, true, false, a
        non-numeric string, a several-hundred-digit
        integer, inf, -inf, NaN, and a list -- returned
        exactly 2.0. Zero and a negative number are
        usable numbers for this reader, so they do not
        read as the default: they clamp to the 0.2 floor,
        exactly as the documented clamp contract and the
        transport-shells pin say. The explicit default 2
        and the numeric string "2" returned 2.0, and a
        numeric string "10" counted as 10.0. Genuine
        values are honored exactly (0.5, 5, 10, 30) and
        the clamp ends hold (0.1 -> 0.2, 1000 -> 60.0).

    (d) This is a coverage record, not a divergence: it
        stays green as long as the reader keeps the
        registry default and clamp. If a shape above
        ever stops reading as stated, this test is the
        failing record of that change. The documentation
        and projection findings in (a) are recorded
        here and in the registry; no production code or
        doc was changed by this hunt.
    """

    def test_fifteen_shapes(self):
        from runner.transport_extensions import channel as ch
        shapes = [
            ("omitted", None, 2.0), ("null", None, 2.0),
            ("empty-string", "", 2.0), ("true", True, 2.0),
            ("false", False, 2.0), ("zero", 0, 0.2),
            ("negative", -5, 0.2),
            ("default-explicit", 2, 2.0),
            ("numeric-string", "2", 2.0),
            ("non-numeric-string", "bogus", 2.0),
            ("huge-int", 10 ** 400, 2.0),
            ("inf", float("inf"), 2.0),
            ("neg-inf", float("-inf"), 2.0),
            ("nan", float("nan"), 2.0),
            ("wrong-container", ["x"], 2.0),
        ]
        for name, value, want in shapes:
            with self.subTest(shape=name):
                cfg = {} if name == "omitted" else {
                    "extension_poll_interval_sec": value}
                self.assertEqual(ch.poll_interval(cfg), want)

    def test_genuine_values_and_clamps_are_honored(self):
        from runner.transport_extensions import channel as ch
        for value, want in ((0.5, 0.5), (5, 5.0), (10, 10.0),
                            ("10", 10.0), (30, 30.0),
                            (0.1, 0.2), (1000, 60.0)):
            with self.subTest(value=value):
                self.assertEqual(
                    ch.poll_interval(
                        {"extension_poll_interval_sec": value}),
                    want)

    def test_top_level_key_never_reaches_an_extension(self):
        # The projection finding in (a), pinned: only a
        # transport block's copy of the key is projected
        # into an extension's runtime config.
        from runner import transports
        paths = {"root": "/tmp/hp-projection-probe"}
        out = transports._runtime_config(
            {"extension_poll_interval_sec": 9},
            "file", "/tmp/hp-projection-probe", paths)
        self.assertNotIn("extension_poll_interval_sec", out)
        out = transports._runtime_config(
            {"transport_file":
             {"extension_poll_interval_sec": 7}},
            "file", "/tmp/hp-projection-probe", paths)
        self.assertEqual(out["extension_poll_interval_sec"], 7)




class TestGrepMaxMatchesDefaultsTo10(unittest.TestCase):
    """Second-run hunt coverage: max_matches (grep query)
    itself, varied with the fifteen shapes through its
    actual reader for the first time.

    (a) Claim: registry row "max_matches (grep query)":
        core, integer, default 10, policy default, lo 0,
        doc_status unverified -- no prose document states
        this default; it is in KNOWN_UNDOCUMENTED in
        tests/defaults_registry.py. The nearest statements
        are PROTOCOL.md (line 516), whose section 10
        example shows the grep query with
        "max_matches": 10, and (line 688) defining the op
        as "grep (regex over retained stdout+stderr, up
        to `max_matches` lines)"; and docs/fuzzing.md
        (lines 129-131): "A `max_matches` of zero returns
        no lines" and a default limit applies when the
        caller supplies no usable number. The reader's
        own comment (runner/runner.py, answer_queries,
        grep branch) states the contract directly:
        "Default 10 for an omitted, unparseable, or
        boolean max_matches; a usable number is clamped
        to [0, 100]", read as
        _confval.integer(q.get("max_matches"), 10, lo=0)
        followed by min(limit, 100). The row's named
        class (TestBooleanGrepMaxMatchesDefaultsTo10)
        covered only the booleans plus bogus and zero
        controls, and the table hunt probes this row
        through confval generically; the answer_queries
        reader itself -- including its extra 100 ceiling,
        which confval alone does not apply -- had never
        been walked through all fifteen shapes.

    (b) How it was hunted: step 8 Target 3 -- the third
        row with no documented default in any current
        doc, after timeout_sec and
        extension_poll_interval_sec. On 2026-10-23 this
        tick called runner.runner.answer_queries -- the
        actual reader -- with one grep query over
        retained output holding 120 matching lines, with
        the table hunt's fifteen shapes, plus genuine
        values, the 100 ceiling, and float shapes.

    (c) Behavior actually observed: NO divergence in
        the reader. Every unusable shape -- omitted,
        null, the empty string, true, false, a
        non-numeric string, a several-hundred-digit
        integer, inf, -inf, NaN, and a list -- returned
        exactly 10 matches. Zero is usable (lo 0) and
        returned 0, as docs/fuzzing.md documents. A
        negative number is below lo, so it is unusable
        under the confval contract and returned the
        default 10 rather than clamping. The explicit
        default 10 and the numeric string "10" returned
        10. Genuine values are honored exactly (1, 2, 5,
        50, 100) and the reader's ceiling holds (101,
        150, and 1000 all returned 100). Floats truncate
        toward zero through confval.integer (2.9 -> 2,
        "2.9" -> 2, 0.5 -> 0). One behavior change from
        the boolean class's 2026-10-23 record is noted:
        a huge integer then clamped to the old reader's
        100 ceiling and returned every line; through
        confval it is unusable and now reads as the
        default 10, which is the registry policy.

    (d) This is a coverage record, not a divergence: it
        stays green as long as the reader keeps the
        registry default and ceiling. If a shape above
        ever stops reading as stated, this test is the
        failing record of that change. The missing
        prose documentation in (a) is recorded here and
        in the registry; no production code or doc was
        changed by this hunt.
    """

    _RES = {"stdout": "\n".join(
        "ERROR line %d" % i for i in range(120)) + "\n",
            "stderr": "", "exit_code": 0}

    def _grep_count(self, extra, omit=False):
        from runner.runner import answer_queries
        q = {"op": "grep", "pattern": "ERROR"}
        if not omit:
            q.update(extra)
        answers, _spent = answer_queries(
            [q], self._RES, None, 8, cfg=None, view="full")
        return len(answers[0].get("matches", []))

    def test_fifteen_shapes(self):
        shapes = [
            ("omitted", {}, True, 10),
            ("null", {"max_matches": None}, False, 10),
            ("empty-string", {"max_matches": ""}, False, 10),
            ("true", {"max_matches": True}, False, 10),
            ("false", {"max_matches": False}, False, 10),
            ("zero", {"max_matches": 0}, False, 0),
            ("negative", {"max_matches": -5}, False, 10),
            ("default-explicit", {"max_matches": 10}, False, 10),
            ("numeric-string", {"max_matches": "10"}, False, 10),
            ("non-numeric-string", {"max_matches": "bogus"}, False, 10),
            ("huge-int", {"max_matches": 10 ** 400}, False, 10),
            ("inf", {"max_matches": float("inf")}, False, 10),
            ("neg-inf", {"max_matches": float("-inf")}, False, 10),
            ("nan", {"max_matches": float("nan")}, False, 10),
            ("wrong-container", {"max_matches": ["x"]}, False, 10),
        ]
        for name, extra, omit, want in shapes:
            with self.subTest(shape=name):
                self.assertEqual(self._grep_count(extra, omit=omit), want)

    def test_genuine_values_and_ceiling_are_honored(self):
        for value, want in ((1, 1), (2, 2), (5, 5), (50, 50),
                            (100, 100), (101, 100), (150, 100),
                            (1000, 100), ("2", 2), ("50", 50)):
            with self.subTest(value=value):
                self.assertEqual(
                    self._grep_count({"max_matches": value}), want)

    def test_floats_truncate_toward_zero(self):
        for value, want in ((2.9, 2), (2.0, 2), ("2.9", 2), (0.5, 0)):
            with self.subTest(value=value):
                self.assertEqual(
                    self._grep_count({"max_matches": value}), want)


class TestTailLinesDefaultsTo20(unittest.TestCase):
    """Second-run hunt coverage: lines (tail query) itself,
    varied with the fifteen shapes through its actual
    reader for the first time.

    (a) Claim: registry row "lines (tail query)": core,
        integer, default 20, policy default, lo 0,
        doc_status unverified -- no prose document states
        this default; it is in KNOWN_UNDOCUMENTED in
        tests/defaults_registry.py. The nearest statements
        are PROTOCOL.md (lines 688-689), defining the op
        as "`tail` (`lines`: last N lines)" over the
        retained output, and docs/fuzzing.md
        (lines 129-131), which reserves "returns no
        lines" for an explicit numeric zero in the sibling
        grep op and describes a default limit applying
        when the caller supplies no usable number. The
        reader itself (runner/runner.py, answer_queries,
        tail branch) reads
        min(_confval.integer(q.get("lines"), 20, lo=0), 200)
        and returns no lines only when that read is zero.
        The row's named class
        (TestBooleanTailLinesDefaultsTo20) covered only
        the booleans plus bogus and zero controls, and the
        table hunt probes this row through confval
        generically; the answer_queries reader itself --
        including its extra 200 ceiling, which confval
        alone does not apply -- had never been walked
        through all fifteen shapes.

    (b) How it was hunted: step 8 Target 3 -- the fourth
        row with no documented default in any current
        doc, after timeout_sec,
        extension_poll_interval_sec, and max_matches.
        On 2026-10-23 this tick called
        runner.runner.answer_queries -- the actual
        reader -- with one tail query over retained
        output holding 250 lines, with the table hunt's
        fifteen shapes, plus genuine values, the 200
        ceiling, and float shapes, and verified that a
        small tail returns the LAST lines in order.

    (c) Behavior actually observed: NO divergence in
        the reader. Every unusable shape -- omitted,
        null, the empty string, true, false, a
        non-numeric string, a several-hundred-digit
        integer, inf, -inf, NaN, and a list -- returned
        exactly 20 lines. Zero is usable (lo 0) and
        returned 0. A negative number is below lo, so it
        is unusable under the confval contract and
        returned the default 20 rather than clamping.
        The explicit default 20 and the numeric string
        "20" returned 20. Genuine values are honored
        exactly (1, 2, 5, 50, 100, 199, 200) and the
        reader's ceiling holds (201, 250, and 1000 all
        returned 200). Floats truncate toward zero
        through confval.integer (2.9 -> 2, "2.9" -> 2,
        0.5 -> 0). Two behavior changes from the boolean
        class's 2026-10-23 record are noted: booleans
        then read as 1/0 through int(); through confval
        they now read as the default 20, and a huge
        integer then clamped to the 200 ceiling; through
        confval it is unusable and now reads as the
        default 20, which is the registry policy.

    (d) This is a coverage record, not a divergence: it
        stays green as long as the reader keeps the
        registry default and ceiling. If a shape above
        ever stops reading as stated, this test is the
        failing record of that change. The missing
        prose documentation in (a) is recorded here and
        in the registry; no production code or doc was
        changed by this hunt.
    """

    _RES = {"stdout": "\n".join(
        "line %d" % i for i in range(250)) + "\n",
            "stderr": "", "exit_code": 0}

    def _tail_count(self, extra, omit=False):
        from runner.runner import answer_queries
        q = {"op": "tail"}
        if not omit:
            q.update(extra)
        answers, _spent = answer_queries(
            [q], self._RES, None, 8, cfg=None, view="full")
        return len(answers[0].get("lines", []))

    def test_fifteen_shapes(self):
        shapes = [
            ("omitted", {}, True, 20),
            ("null", {"lines": None}, False, 20),
            ("empty-string", {"lines": ""}, False, 20),
            ("true", {"lines": True}, False, 20),
            ("false", {"lines": False}, False, 20),
            ("zero", {"lines": 0}, False, 0),
            ("negative", {"lines": -5}, False, 20),
            ("default-explicit", {"lines": 20}, False, 20),
            ("numeric-string", {"lines": "20"}, False, 20),
            ("non-numeric-string", {"lines": "bogus"}, False, 20),
            ("huge-int", {"lines": 10 ** 400}, False, 20),
            ("inf", {"lines": float("inf")}, False, 20),
            ("neg-inf", {"lines": float("-inf")}, False, 20),
            ("nan", {"lines": float("nan")}, False, 20),
            ("wrong-container", {"lines": ["x"]}, False, 20),
        ]
        for name, extra, omit, want in shapes:
            with self.subTest(shape=name):
                self.assertEqual(self._tail_count(extra, omit=omit), want)

    def test_genuine_values_and_ceiling_are_honored(self):
        for value, want in ((1, 1), (2, 2), (5, 5), (50, 50),
                            (100, 100), (199, 199), (200, 200),
                            (201, 200), (250, 200), (1000, 200),
                            ("2", 2), ("50", 50)):
            with self.subTest(value=value):
                self.assertEqual(
                    self._tail_count({"lines": value}), want)

    def test_floats_truncate_toward_zero(self):
        for value, want in ((2.9, 2), (2.0, 2), ("2.9", 2), (0.5, 0)):
            with self.subTest(value=value):
                self.assertEqual(
                    self._tail_count({"lines": value}), want)

    def test_tail_returns_the_last_lines_in_order(self):
        from runner.runner import answer_queries
        answers, _spent = answer_queries(
            [{"op": "tail", "lines": 3}], self._RES, None, 8,
            cfg=None, view="full")
        self.assertEqual(answers[0].get("lines"),
                         ["line 247", "line 248", "line 249"])




class TestSensesLimitDefaultsTo20(unittest.TestCase):
    """Divergence: a senses query's limit of zero returns
    every stored alert instead of no alerts, because the
    store reader slices with out[-0:].

    (a) Claim: registry row "limit (senses query)":
        core, integer, default 20, policy default, lo 0,
        doc_status unverified -- no prose document states
        this default; it is in KNOWN_UNDOCUMENTED in
        tests/defaults_registry.py. The nearest statement
        is docs/senses.md (line 322, "Reading signals:
        the senses query op"), which shows the senses
        query with "limit": 20, the reader's own default.
        The reader (runner/runner.py, answer_queries,
        senses branch) reads
        limit=_confval.integer(q.get("limit"), 20, lo=0):
        under the confval contract lo 0 makes zero a
        usable value, not an unusable one. The sibling
        query ops honor a usable zero as zero: the grep
        branch's own comment states its limit is
        "clamped to [0, 100]" and docs/fuzzing.md
        (lines 129-131) records that a max_matches of
        zero returns no lines, and the tail branch reads
        its lines as "text.splitlines()[-n:] if n else
        []" -- an explicit zero guard. The store reader
        itself (runner/senses.py, load_alerts) treats
        limit None -- and only None -- as no cap: "if
        limit is not None: ... out = out[-n:]", so a
        zero limit is a real cap of zero alerts. The
        row's named class
        (TestBooleanSensesLimitDefaultsTo20) covered
        only the booleans plus bogus and explicit-2
        controls; it noted the same out[-0:] slice as
        the mechanism by which False once returned
        every alert, but no test ever asserted an
        explicit zero limit through either reader.

    (b) How it was hunted: step 8 Target 3 -- the
        fifth row with no documented default in any
        current doc, after timeout_sec,
        extension_poll_interval_sec, max_matches, and
        lines. On 2026-10-23 this tick called
        runner.runner.answer_queries -- the actual
        reader -- with one senses query over a store
        holding 30 alerts, with the table hunt's
        fifteen shapes, plus genuine values, a
        no-ceiling check, and float shapes, and also
        called runner.senses.load_alerts directly
        with limit 0.

    (c) Behavior actually observed: NO divergence for
        the default itself. Every unusable shape --
        omitted, null, the empty string, true, false,
        a non-numeric string, a several-hundred-digit
        integer, inf, -inf, NaN, and a list -- returned
        exactly 20 alerts; a negative number is below
        lo and also returned 20. The explicit default
        20 and the numeric string "20" returned 20.
        Genuine values are honored exactly (1, 2, 5,
        25) and there is no reader ceiling (100 and
        1000 returned all 30 stored alerts). Floats
        truncate toward zero through confval.integer
        (2.9 -> 2, "2.9" -> 2). But a usable zero does
        not return zero alerts: limit 0 returned all
        30 stored alerts, and 0.5 -- truncating to the
        usable zero -- also returned all 30. The cause
        is in the store reader: load_alerts computes
        n = int(limit) and then out = out[-n:]; in
        Python -0 is 0, so out[-0:] is out[0:], the
        whole list. The confval migration fixed the
        boolean shapes at the query reader (true and
        false now read as the default 20) but left
        this slice unguarded, so an explicit zero --
        the one value a caller uses to ask for no
        alerts -- silently reads as an unlimited read.
        load_alerts(base, limit=0) likewise returned
        all 30 records directly. Observed on
        2026-10-23: answer_queries with limit 0 and
        with limit 0.5 each returned 30 alerts against
        30 stored, where the registry contract (lo 0,
        zero usable) and both sibling ops require 0.

    (d) Do not make this test pass by editing the test.
        It passes only when the bug described above is
        fixed in the code.
    """

    _RES = {"stdout": "", "stderr": "", "exit_code": 0}

    def _write_store(self, base, count=30):
        import os
        with open(os.path.join(base, "senses.jsonl"),
                  "w", encoding="utf-8") as fh:
            for i in range(count):
                fh.write(json.dumps({
                    "sensor": "host_ids",
                    "severity": "info",
                    "title": "alert %d" % i,
                    "detail": {},
                    "observed_at": "2026-10-23T00:00:00Z",
                    "received_at": "2026-10-23T00:00:00Z",
                }) + "\n")

    def _senses_count(self, extra, omit=False):
        import os
        from runner.runner import answer_queries
        with tempfile.TemporaryDirectory() as base:
            self._write_store(base)
            q = {"op": "senses"}
            if not omit:
                q.update(extra)
            answers, _spent = answer_queries(
                [q], self._RES, None, 8, cfg={}, view="full",
                base_dir=base)
            return len(answers[0].get("alerts", []))

    def test_fifteen_shapes(self):
        shapes = [
            ("omitted", {}, True, 20),
            ("null", {"limit": None}, False, 20),
            ("empty-string", {"limit": ""}, False, 20),
            ("true", {"limit": True}, False, 20),
            ("false", {"limit": False}, False, 20),
            ("zero", {"limit": 0}, False, 0),
            ("negative", {"limit": -5}, False, 20),
            ("default-explicit", {"limit": 20}, False, 20),
            ("numeric-string", {"limit": "20"}, False, 20),
            ("non-numeric-string", {"limit": "bogus"}, False, 20),
            ("huge-int", {"limit": 10 ** 400}, False, 20),
            ("inf", {"limit": float("inf")}, False, 20),
            ("neg-inf", {"limit": float("-inf")}, False, 20),
            ("nan", {"limit": float("nan")}, False, 20),
            ("wrong-container", {"limit": ["x"]}, False, 20),
        ]
        for name, extra, omit, want in shapes:
            with self.subTest(shape=name):
                self.assertEqual(
                    self._senses_count(extra, omit=omit), want)

    def test_genuine_values_are_honored_with_no_ceiling(self):
        for value, want in ((1, 1), (2, 2), (5, 5), (25, 25),
                            (30, 30), (31, 30), (100, 30),
                            (1000, 30), ("2", 2), ("50", 30)):
            with self.subTest(value=value):
                self.assertEqual(
                    self._senses_count({"limit": value}), want)

    def test_floats_truncate_toward_zero(self):
        for value, want in ((2.9, 2), (2.0, 2), ("2.9", 2),
                            (0.5, 0)):
            with self.subTest(value=value):
                self.assertEqual(
                    self._senses_count({"limit": value}), want)

    def test_load_alerts_zero_limit_returns_no_alerts(self):
        from runner import senses as S
        with tempfile.TemporaryDirectory() as base:
            self._write_store(base)
            self.assertEqual(S.load_alerts(base, limit=0), [])



class TestAskMaxCharsDefaultsTo2000(unittest.TestCase):
    """Second-run hunt coverage: max_chars (ask query)
    itself, varied with the fifteen shapes through its
    actual reader for the first time.

    (a) Claim: registry row "max_chars (ask query)":
        core, integer, default 2000, policy default, lo 0,
        doc_status unverified -- no prose document states
        this query parameter's own default; it is in
        KNOWN_UNDOCUMENTED in tests/defaults_registry.py,
        and the registry notes record that it falls back
        to max_answer_chars. The fallback target is
        documented: PROTOCOL.md (line 711) gives the
        inference config "`max_answer_chars` (default
        2000)", docs/configuring-oracle.md (line 54)
        repeats "`max_answer_chars` (default 2000 --
        answers are truncated past this)", and
        PROTOCOL.md (line 730) shows the ask query
        itself carrying "max_chars": 500. The reader's
        own comment (runner/runner.py, answer_queries,
        ask branch) states the contract directly: "The
        inference block's max_answer_chars (default
        2000) for an omitted, unparseable, or boolean
        max_chars", read as
        _confval.integer(q.get("max_chars"),
        inf["max_answer_chars"], lo=0), with no reader
        ceiling applied afterwards. The row's named
        class (TestBooleanAskMaxCharsDefaultsTo2000)
        covered only the booleans plus bogus, explicit
        500, and explicit 0 controls -- and its boolean
        test was recorded when the pre-confval reader
        handed True to ask_model as a cap of 1; the
        answer_queries reader itself, including its
        fallback to a configured max_answer_chars and
        its lack of a ceiling, had never been walked
        through all fifteen shapes.

    (b) How it was hunted: step 8 Target 3 -- the
        sixth row with no documented default in any
        current doc, after timeout_sec,
        extension_poll_interval_sec, max_matches, lines,
        and limit. On 2026-10-23 this tick called
        runner.runner.answer_queries -- the actual
        reader -- with one ask query over retained
        output, with a loopback inference config whose
        max_answer_chars is the documented 2000,
        patching ask_model only to capture the
        max_chars it was handed, with the table hunt's
        fifteen shapes, plus genuine values, a
        no-ceiling check, float shapes, a configured
        fallback check (max_answer_chars 750), and a
        direct downstream zero-cap check through
        _sanitize_model_reply.

    (c) Behavior actually observed: NO divergence.
        Every unusable shape -- omitted, null, the
        empty string, true, false, a non-numeric
        string, a several-hundred-digit integer, inf,
        -inf, NaN, and a list -- was handed a cap of
        exactly 2000. Zero is usable (lo 0) and was
        handed 0, and the downstream sanitizer honors
        that zero as zero (_sanitize_model_reply with
        cap 0 returns an empty answer, not the whole
        reply -- unlike the senses store slice in
        TestSensesLimitDefaultsTo20). A negative
        number is below lo, so it is unusable under
        the confval contract and was handed the
        default 2000 rather than clamping. The
        explicit default 2000 and the numeric string
        "2000" were handed 2000. Genuine values are
        honored exactly (1, 2, 5, 500, 2001) and
        there is no reader ceiling (5000 and 100000
        were handed through unchanged). Floats
        truncate toward zero through confval.integer
        (2.9 -> 2, "2.9" -> 2, 0.5 -> 0, and -0.5 is
        below lo so it reads as the default). The
        fallback is genuinely the configured value,
        not a hard-coded 2000: with max_answer_chars
        configured to 750, omitted, bogus, and true
        were each handed 750, while a genuine 500
        and a usable zero still overrode it. Two
        behavior changes from the boolean class's
        2026-10-23 record are noted: true now reads
        as the default through confval instead of
        truncating to 1, and a huge integer now reads
        as the default instead of reaching int() in
        the old reader.

    (d) This is a coverage record, not a divergence: it
        stays green as long as the reader keeps the
        registry fallback and the no-ceiling contract.
        If a shape above ever stops reading as stated,
        this test is the failing record of that change.
        The missing prose documentation for the query
        parameter itself in (a) is recorded here and
        in the registry; no production code or doc was
        changed by this hunt.
    """

    _CFG = {"inference": {
        "endpoint": "http://127.0.0.1:11434/v1",
        "model": "qwen3:1.7b"}}
    _CFG750 = {"inference": {
        "endpoint": "http://127.0.0.1:11434/v1",
        "model": "qwen3:1.7b", "max_answer_chars": 750}}
    _RES = {"stdout": "hello\n", "stderr": "",
            "exit_code": 0}

    def _ask_cap(self, extra, omit=False, cfg=None):
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
        if not omit:
            q.update(extra)
        with mock.patch.object(runner_mod, "ask_model",
                               fake):
            answers, _spent = runner_mod.answer_queries(
                [q], self._RES, None, 8,
                cfg=self._CFG if cfg is None else cfg,
                view="full")
        self.assertEqual(answers[0].get("op"), "ask")
        return captured["max_chars"]

    def test_fifteen_shapes(self):
        shapes = [
            ("omitted", {}, True, 2000),
            ("null", {"max_chars": None}, False, 2000),
            ("empty-string", {"max_chars": ""}, False, 2000),
            ("true", {"max_chars": True}, False, 2000),
            ("false", {"max_chars": False}, False, 2000),
            ("zero", {"max_chars": 0}, False, 0),
            ("negative", {"max_chars": -5}, False, 2000),
            ("default-explicit", {"max_chars": 2000}, False, 2000),
            ("numeric-string", {"max_chars": "2000"}, False, 2000),
            ("non-numeric-string", {"max_chars": "bogus"}, False, 2000),
            ("huge-int", {"max_chars": 10 ** 400}, False, 2000),
            ("inf", {"max_chars": float("inf")}, False, 2000),
            ("neg-inf", {"max_chars": float("-inf")}, False, 2000),
            ("nan", {"max_chars": float("nan")}, False, 2000),
            ("wrong-container", {"max_chars": ["x"]}, False, 2000),
        ]
        for name, extra, omit, want in shapes:
            with self.subTest(shape=name):
                self.assertEqual(
                    self._ask_cap(extra, omit=omit), want)

    def test_genuine_values_are_honored_with_no_ceiling(self):
        for value, want in ((1, 1), (2, 2), (5, 5), (500, 500),
                            (2001, 2001), (5000, 5000),
                            (100000, 100000), ("2", 2),
                            ("500", 500)):
            with self.subTest(value=value):
                self.assertEqual(
                    self._ask_cap({"max_chars": value}), want)

    def test_floats_truncate_toward_zero(self):
        for value, want in ((2.9, 2), (2.0, 2), ("2.9", 2),
                            (0.5, 0), (-0.5, 2000)):
            with self.subTest(value=value):
                self.assertEqual(
                    self._ask_cap({"max_chars": value}), want)

    def test_fallback_is_the_configured_max_answer_chars(self):
        self.assertEqual(self._ask_cap({}, omit=True, cfg=self._CFG750), 750)
        self.assertEqual(
            self._ask_cap({"max_chars": "bogus"}, cfg=self._CFG750), 750)
        self.assertEqual(
            self._ask_cap({"max_chars": True}, cfg=self._CFG750), 750)
        self.assertEqual(
            self._ask_cap({"max_chars": 500}, cfg=self._CFG750), 500)
        self.assertEqual(
            self._ask_cap({"max_chars": 0}, cfg=self._CFG750), 0)

    def test_zero_cap_truncates_the_reply_to_empty(self):
        from runner.runner import _sanitize_model_reply
        result = _sanitize_model_reply(
            "hello world", 0, "hello\n", None, "m")
        self.assertEqual(result.get("answer"), "")

if __name__ == "__main__":
    unittest.main()
