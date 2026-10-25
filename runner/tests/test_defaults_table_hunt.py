"""The table-driven hunt: step 5 of the campaign plan.

One parameterized walk over runner/tests/defaults_registry.py. Every row
is probed with the fifteen shapes the campaign found its bugs
with -- omitted; null; the empty string; true; false; zero; a
negative number; the documented default written explicitly; a
numeric string; a non-numeric string; a several-hundred-digit integer
(10**400, the campaign's huge shape); inf;
-inf; NaN; the wrong container type -- and the row's policy is
asserted:

- probe "confval": the value goes through runner/guard/confval.py, the
  reader the row's code uses, with the row's default and bounds.
  An unusable shape must read as the documented default; a usable
  one must come through. (At the reader, "omitted" and "null"
  are the same input -- cfg.get returns None for both -- so the
  omitted shape is probed as None and the identity is noted
  here, not hidden.)
- probe "refuse": the value is placed at the key's path in a
  config and handed to the refusing reader itself
  (resources.parse_resources, dri.parse_dri, mailbox._port,
  verify.build_key_policies, the DTLS pipe, NATS url_port).
  A present-but-unusable value must
  raise the reader's RuntimeError config error; an omitted key
  must parse. Which middle shapes are usable is a property of
  the reader family (a confval gate parses numeric strings, the
  DRI isinstance gate does not; mailbox._port does not range
  check), and the tables below say so per row rather than
  pretending uniformity.
- probe "handwritten": the row's coverage is the named class in
  runner/tests/test_doc_default_divergences.py; the hunt asserts the
  class exists. The 226 hand-written tests stay untouched as
  the record.
- probe "policy-conflict": retired (Q3, 2026-10-24). Decision 1
  put three keys in the refuse class while their shipped
  readers still read them as the default; while that lasted,
  those rows were NOT probed as defaults and NOT skipped: they
  were recorded below as failing-by-design divergence tests
  (PolicyConflictDivergenceTests), in the campaign's four-part
  format. The readers moved in 54dafe7, the class passes as
  written, and the three rows now probe "refuse" like every
  other refuse row. The class stays below as the record of
  the move, superseded as the rows' coverage.

The registry guards (doc drift, confval coverage, shape) are
imported from runner.tests.defaults_registry so default discovery runs
them here; defaults_registry.py is not itself a test_*.py file.
"""
import ast
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner.guard import confval  # noqa: E402
from runner.oracle import dri as _dri  # noqa: E402
from runner.wire import mailbox as _mailbox  # noqa: E402
from runner.oracle import resources as _resources  # noqa: E402
from runner.wire import verify as _verify  # noqa: E402
from runner.tests.defaults_registry import ROWS  # noqa: E402
from runner.tests.defaults_registry import (  # noqa: E402,F401
    ConfvalCoverageGuardTests, DocDriftGuardTests, RegistryShapeTests)

HUGE = 10 ** 400

ENUM_CHOICES = {
    "dtls_greeting": ("none", "family", "standard", "full"),
}


def _shapes(row):
    """The fifteen shapes, as (name, value) for this row."""
    d = row["default"]
    return [
        ("omitted", None),          # cfg.get's absent value: None
        ("null", None),
        ("empty-string", ""),
        ("true", True),
        ("false", False),
        ("zero", 0),
        ("negative", -5),
        ("default-explicit", d),
        ("numeric-string", str(d)),
        ("non-numeric-string", "bogus"),
        ("huge-int", HUGE),
        ("inf", float("inf")),
        ("neg-inf", float("-inf")),
        ("nan", float("nan")),
        ("wrong-container", ["x"]),
    ]


def _usable_number(row, value):
    """Independently: is this shape a usable number for the row?

    Mirrors the documented reader contract, not the reader's
    code: strings parse, bools never count, a number must be
    finite, and the row's bounds decide.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            value = float(text)
        except ValueError:
            return False
    if not isinstance(value, (int, float)):
        return False
    try:
        f = float(value)
    except (OverflowError, ValueError):
        return False
    if math.isnan(f) or math.isinf(f):
        return False
    if row["lo"] is not None and f < row["lo"]:
        return False
    if row["hi"] is not None and f > row["hi"]:
        return False
    return True


class ConfvalProbeTests(unittest.TestCase):
    """Rows whose reader is confval, probed through confval."""

    def test_confval_rows(self):
        rows = [r for r in ROWS if r["probe"] == "confval"]
        self.assertGreater(len(rows), 15)
        for row in rows:
            for name, value in _shapes(row):
                with self.subTest(key=row["key"], shape=name):
                    self._probe(row, value)

    def _probe(self, row, value):
        if row["kind"] == "enum":
            choices = ENUM_CHOICES[row["key"]]
            got = confval.choice(value, choices, row["default"])
            want = value if (isinstance(value, str)
                             and value in choices) else row["default"]
            self.assertEqual(want, got)
            return
        reader = confval.integer if row["kind"] == "integer" else confval.number
        got = reader(value, row["default"], lo=row["lo"], hi=row["hi"])
        if _usable_number(row, value):
            want = float(value) if isinstance(value, str) else value
            if row["kind"] == "integer":
                want = int(float(want))
            self.assertEqual(want, got)
        else:
            self.assertEqual(row["default"], got)


# --- refuse probes -------------------------------------------------
# Each builder places the value at the key's path; OMITTED means
# the key is left out entirely. OK shapes parse without error;
# every other listed shape must raise RuntimeError.

_OMITTED = object()


def _resources_cfg(block, key, value):
    inner = {} if value is _OMITTED else {key: value}
    return {"resources": inner}


def _dri_cfg(path, value):
    cfg = {}
    node = cfg.setdefault("dri", {})
    for part in path[:-1]:
        node = node.setdefault(part, {})
    if value is not _OMITTED:
        node[path[-1]] = value
    return cfg


def _key_policy_cfg(value):
    if value is _OMITTED:
        return {"key_policies": {"k1": {}}}
    return {"key_policies": {"k1": {"max_timeout_sec": value}}}


def _mailbox_port(key, value):
    cfg = {} if value is _OMITTED else {key: value}
    return _mailbox._port(cfg, key, 993 if key == "imap_port" else 587)


def _dtls_pipe(key, value):
    """Construct the DTLS pipe with the value at cfg[key].

    The base config binds port 0 (kernel-assigned) on loopback;
    the probed key replaces its entry, and _OMITTED removes it,
    which is the reader's documented absent case (port reads
    20220, bind reads 0.0.0.0). bind_address accepts any
    string, so an address string that cannot be bound fails at
    the socket with OSError instead of the reader's
    RuntimeError; it is still a startup refusal -- no address
    is ever substituted -- so the probe normalizes it to the
    table's error type, here rather than in the reader.
    """
    import importlib
    import tempfile
    dtls_ext = importlib.import_module(
        "runner.transport_extensions.dtls.__main__")
    cfg = {"shared_secret": "campaign-test-secret-0123456789",
           "bind": "127.0.0.1", "port": 0}
    if value is _OMITTED:
        cfg.pop(key, None)
    else:
        cfg[key] = value
    tmp = tempfile.mkdtemp(prefix="hp-table-hunt-dtls-")
    try:
        pipe = dtls_ext.DtlsPipe(cfg, os.path.join(tmp, "channel"))
    except OSError as e:
        raise RuntimeError(str(e)) from e
    pipe.sock.close()
    return pipe


def _nats_url_port(value):
    """url_port with the value written as the URL's port.

    A value that cannot be written into a URL at all (the
    wrong-container shape) makes urlparse itself raise
    ValueError before url_port's own check runs; the value is
    refused either way, so the probe normalizes that too.
    """
    import importlib
    nats_ext = importlib.import_module(
        "runner.transport_extensions.nats.__main__")
    if value is _OMITTED:
        return nats_ext.url_port("nats://127.0.0.1")
    try:
        return nats_ext.url_port("nats://127.0.0.1:%s" % (value,))
    except ValueError as e:
        raise RuntimeError(str(e)) from e


REFUSE_PROBES = {
    # key -> (call(value), shapes that parse without error)
    "resources.enabled": (
        lambda v: _resources.parse_resources(_resources_cfg("resources", "enabled", v)),
        {"omitted", "default-explicit", "true", "false"}),
    "resources.threshold": (
        lambda v: _resources.parse_resources(_resources_cfg("resources", "threshold", v)),
        {"omitted", "default-explicit", "numeric-string"}),
    "resources.cooldown_sec": (
        lambda v: _resources.parse_resources(_resources_cfg("resources", "cooldown_sec", v)),
        {"omitted", "default-explicit", "numeric-string", "zero"}),
    "dri.enabled": (
        lambda v: _dri.parse_dri(_dri_cfg(("enabled",), v)),
        {"omitted", "default-explicit", "true", "false"}),
    "dri.channel": (
        lambda v: _dri.parse_dri(_dri_cfg(("channel",), v)),
        {"omitted", "default-explicit", "numeric-string"}),
    "dri.cooldown_sec": (
        lambda v: _dri.parse_dri(_dri_cfg(("cooldown_sec",), v)),
        {"omitted", "default-explicit", "numeric-string", "zero"}),
    "dri.digest_window_sec": (
        lambda v: _dri.parse_dri(_dri_cfg(("digest_window_sec",), v)),
        {"omitted", "default-explicit", "numeric-string", "zero"}),
    "dri.triggers.sensor_fused_score.threshold": (
        lambda v: _dri.parse_dri(_dri_cfg(("triggers", "sensor_fused_score", "threshold"), v)),
        {"omitted", "default-explicit", "numeric-string", "zero", "negative"}),
    "dri.triggers.sensor_fused_score.window_sec": (
        lambda v: _dri.parse_dri(_dri_cfg(("triggers", "sensor_fused_score", "window_sec"), v)),
        {"omitted", "default-explicit", "numeric-string", "zero", "negative"}),
    "dri.triggers.key_probe.threshold": (
        lambda v: _dri.parse_dri(_dri_cfg(("triggers", "key_probe", "threshold"), v)),
        {"omitted", "default-explicit", "numeric-string", "zero", "negative"}),
    "dri.triggers.key_probe.window_sec": (
        lambda v: _dri.parse_dri(_dri_cfg(("triggers", "key_probe", "window_sec"), v)),
        {"omitted", "default-explicit", "numeric-string", "zero", "negative"}),
    "imap_port": (
        lambda v: _mailbox_port("imap_port", v),
        {"omitted", "default-explicit", "numeric-string", "zero",
         "negative", "huge-int"}),  # _port does not range-check
    "smtp_port": (
        lambda v: _mailbox_port("smtp_port", v),
        {"omitted", "default-explicit", "numeric-string", "zero",
         "negative", "huge-int"}),
    "key_policies.<key_id>.max_timeout_sec": (
        lambda v: _verify.build_key_policies(_key_policy_cfg(v)),
        # The gate is confval.is_number, which does not parse
        # strings: a numeric string refuses here, unlike the
        # resources gate (confval.number) above.
        {"omitted", "default-explicit"}),
    "transport_dtls.port": (
        lambda v: _dtls_pipe("port", v),
        # listen_port: 0 is usable (kernel-assigned) and a
        # numeric string is read; bounds are 0..65535.
        {"omitted", "zero", "default-explicit", "numeric-string"}),
    "transport_dtls.bind": (
        lambda v: _dtls_pipe("bind", v),
        # bind_address: any string is read, and the empty
        # string is every interface; a non-string refuses.
        {"omitted", "empty-string", "default-explicit",
         "numeric-string"}),
    "transport_nats.url (port component)": (
        _nats_url_port,
        # url_port: the port must be a whole number 1..65535 --
        # unlike the DTLS port, zero refuses here.
        {"omitted", "default-explicit", "numeric-string"}),
}


class RefuseProbeTests(unittest.TestCase):
    """Refuse-class rows, probed through the refusing readers."""

    def test_refuse_rows(self):
        rows = [r for r in ROWS if r["probe"] == "refuse"]
        self.assertEqual({r["key"] for r in rows}, set(REFUSE_PROBES))
        for row in rows:
            call, ok_shapes = REFUSE_PROBES[row["key"]]
            shapes = dict(_shapes(row))
            shapes["omitted"] = _OMITTED
            # key_policies has no default; its "default-explicit"
            # shape is the documented example value.
            if row["key"] == "key_policies.<key_id>.max_timeout_sec":
                shapes["default-explicit"] = 600
                shapes["numeric-string"] = "600"
            for name, value in shapes.items():
                with self.subTest(key=row["key"], shape=name):
                    if name in ok_shapes:
                        call(value)
                    else:
                        with self.assertRaises(RuntimeError):
                            call(value)


class HandwrittenCoverageTests(unittest.TestCase):
    """Handwritten rows: the named divergence class must exist."""

    def test_handwritten_rows_have_their_class(self):
        path = os.path.join(os.path.dirname(__file__),
                            "test_doc_default_divergences.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        rows = [r for r in ROWS if r["probe"] == "handwritten"]
        self.assertGreater(len(rows), 40)
        for row in rows:
            with self.subTest(key=row["key"]):
                self.assertIn(row["test"], classes)


class RegistryAccountingTests(unittest.TestCase):
    def test_every_row_is_probed_somewhere(self):
        probes = {r["probe"] for r in ROWS}
        # "policy-conflict" retired in Q3 (2026-10-24): its last
        # three rows moved to "refuse" when their readers moved
        # in 54dafe7, so no row carries it any more.
        self.assertEqual({"confval", "refuse", "handwritten"}, probes)
        self.assertEqual(len(ROWS), sum(
            1 for r in ROWS if r["probe"] in probes))


class PolicyConflictDivergenceTests(unittest.TestCase):
    """The record of the policy-conflict move, kept as written.

    SUPERSEDED as the three rows' coverage (Q3, 2026-10-24): the
    readers moved in 54dafe7, these tests pass as written, and
    the registry rows for transport_dtls.port,
    transport_dtls.bind, and transport_nats.url now probe
    "refuse" in RefuseProbeTests, where the fifteen shapes run
    against the refusing readers. This class stays as the
    four-part record of what the divergence was; its assertions
    now pin the refusing behavior they demanded.

    (a) The claim (Decision 1, Andrew via Claude, 2026-10-23,
        stamped by Muse; the normative sentence for PROTOCOL.md
        and docs/oracle/configuring-oracle.md): "a setting that is
        present but not usable reads as its documented default
        and is named in the startup warning, unless the setting
        is a port, a bind address, a key policy, a paging
        threshold, a security mode or a secret, in which case
        the runner refuses to start and names it." A substituted
        address is not the address the operator configured:
        `2O220` is exactly the typo this rule exists for.

    (b) How the bug was found: step 5 of the campaign plan made
        the hunt table-driven; the registry rows for
        transport_dtls.port, transport_dtls.bind, and
        transport_nats.url carry policy `refuse` per the
        decision, and probing the shipped readers with
        present-but-unusable values showed all three still
        falling back to the documented default (20220, 0.0.0.0,
        4222) instead of refusing.

    (c) Behavior observed at step 5, before the readers moved:
        DtlsPipe constructed and bound with port "2O220" read
        as 20220 and with a non-string bind read as 0.0.0.0;
        NatsClient resolved "nats://127.0.0.1:2O220" and
        "...:99999" to port 4222. No error was raised by any of
        the three. Since 54dafe7 each raises the RuntimeError
        config error these tests assert.

    (d) The note this class carried while the divergence
        stood: do not make this test pass by editing the test;
        it passes only when the bug described above is fixed
        in the code. It was fixed in the code (54dafe7), docs
        first, per the decision's adoption cost.
    """

    def _dtls_pipe(self, cfg):
        import importlib
        import tempfile
        dtls_ext = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        cfg = dict(cfg)
        cfg.setdefault("shared_secret", "campaign-test-secret-0123456789")
        cfg.setdefault("bind", "127.0.0.1")
        cfg.setdefault("port", 0)
        tmp = tempfile.mkdtemp(prefix="hp-table-hunt-dtls-")
        pipe = dtls_ext.DtlsPipe(cfg, os.path.join(tmp, "channel"))
        self.addCleanup(pipe.sock.close)
        return pipe

    def test_dtls_port_refuses_unusable_value(self):
        try:
            self._dtls_pipe({"port": "2O220"})
        except RuntimeError:
            return
        self.fail("transport_dtls.port '2O220' read as the default "
                  "20220 instead of refusing to start")

    def test_dtls_bind_refuses_unusable_value(self):
        try:
            self._dtls_pipe({"bind": 12345})
        except RuntimeError:
            return
        self.fail("transport_dtls.bind 12345 read as the default "
                  "0.0.0.0 instead of refusing to start")

    def test_nats_url_port_refuses_unusable_value(self):
        import importlib
        nats_ext = importlib.import_module(
            "runner.transport_extensions.nats.__main__")
        for url in ("nats://127.0.0.1:2O220", "nats://127.0.0.1:99999"):
            with self.subTest(url=url):
                try:
                    nats_ext.NatsClient(url)
                except RuntimeError:
                    continue
                self.fail("NATS URL port in %r read as the default "
                          "4222 instead of refusing to start" % url)

    def test_controls_still_construct(self):
        # Controls: the harness works -- an omitted port and a
        # valid URL construct today and must keep constructing
        # after the readers move (the port control binds port 0,
        # kernel-assigned, exactly as the shipped reader allows).
        pipe = self._dtls_pipe({})
        self.assertEqual(pipe.port, 0)
        import importlib
        nats_ext = importlib.import_module(
            "runner.transport_extensions.nats.__main__")
        self.assertEqual(nats_ext.NatsClient("nats://127.0.0.1").port, 4222)


class Decision1WarningLineProbes(unittest.TestCase):
    """Phase 2.5 (Q5): the Decision-1 warning line, as
    failing-by-design probes for Claude's lane to ship against.

    Decision 1 (2026-10-23), point 3 -- "Default, not silent":
    when a present-but-unusable setting reads as its documented
    default, startup prints one line, "config: N settings read
    as their default", naming the keys, and the same list rides
    in the platform card at the `full` tier. Point 4, default
    class half: a bad value written live reads as the default
    and is named in the log. Q5's answer (Claude, 2026-10-24):
    none of the three exists in the runner today; Claude's
    lane, next release; Muse writes the probes first.

    These three tests FAIL BY DESIGN until that code lands.
    Do not make them pass by editing the tests. Each carries a
    control that passes today and must keep passing, so a
    failure here is the missing feature, never the harness.
    The keys used are squarely default-class in the registry:
    poll_interval_sec (default 20) and output_retention_days
    (default 7). The live-reload probe uses
    output_retention_days because it is default-class but NOT
    one of the five HOT_KEYS whose reload naming already
    shipped (see its control).
    """

    _BAD = {"poll_interval_sec": "x", "output_retention_days": "many"}
    _CLEAN = {"poll_interval_sec": 30, "output_retention_days": 9}

    def _startup_output(self, cfg_extra):
        import io
        import json
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock
        from runner import runner as R
        td = tempfile.mkdtemp(prefix="hp-q5-")
        path = os.path.join(td, "config.json")
        cfg = dict(cfg_extra, base_dir=td)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        out = io.StringIO()
        argv = ["runner", "--config", path, "--inspect", "board"]
        with mock.patch.object(sys, "argv", argv):
            with redirect_stdout(out), redirect_stderr(out):
                rc = R.main()
        self.assertEqual(rc, 0)
        return out.getvalue()

    def test_startup_line_names_every_defaulted_key(self):
        text = self._startup_output(self._BAD)
        lines = [ln for ln in text.splitlines()
                 if "read as their default" in ln]
        self.assertTrue(
            lines,
            "no startup line names the defaulted keys; got: %r"
            % text[:400])
        joined = "\n".join(lines)
        self.assertIn("config:", joined)
        self.assertIn("2 settings", joined)
        self.assertIn("poll_interval_sec", joined)
        self.assertIn("output_retention_days", joined)

    def test_startup_line_control_clean_config_is_silent(self):
        # Control (passes today, must keep passing): a config
        # whose values are all usable prints no such line, so
        # the probe above cannot pass by printing it always.
        text = self._startup_output(self._CLEAN)
        self.assertNotIn("read as their default", text)

    def test_full_card_carries_the_defaulted_list(self):
        import json
        from runner import runner as R
        cfg = dict(self._BAD, pong_platform="full")
        card = R.pong_platform(cfg)
        self.assertIsNotNone(card)
        text = json.dumps(card)
        self.assertIn("poll_interval_sec", text)
        self.assertIn("output_retention_days", text)

    def test_full_card_control_clean_config_names_nothing(self):
        # Control: with every value usable, the full card must
        # not claim any setting defaulted.
        import json
        from runner import runner as R
        cfg = dict(self._CLEAN, pong_platform="full")
        card = R.pong_platform(cfg)
        self.assertIsNotNone(card)
        text = json.dumps(card)
        self.assertNotIn("poll_interval_sec", text)
        self.assertNotIn("output_retention_days", text)

    def test_live_reload_names_a_default_class_bad_value(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from runner import runner as R
        td = tempfile.mkdtemp(prefix="hp-q5-")
        path = os.path.join(td, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"output_retention_days": "many"}, fh)
        cfg, state = {}, {}
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            R.reload_hot_config(cfg, path, state)
        self.assertIn("output_retention_days", out.getvalue())
        self.assertEqual(cfg.get("output_retention_days"), 7)

    def test_live_reload_control_hot_key_already_named(self):
        # Control (passes today, must keep passing): the five
        # HOT_KEYS already read a live bad value as the default
        # and name it in the log; the probe above targets the
        # rest of the default class, not this shipped subset.
        import io
        import json
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from runner import runner as R
        td = tempfile.mkdtemp(prefix="hp-q5-")
        path = os.path.join(td, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"poll_interval_sec": "x"}, fh)
        cfg, state = {}, {}
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            R.reload_hot_config(cfg, path, state)
        self.assertIn("poll_interval_sec", out.getvalue())
        self.assertEqual(cfg.get("poll_interval_sec"), 20)


class DefaultedEnumLegsTest(unittest.TestCase):
    """Queue A refill: defaulted.py's enum legs
    (coverage run 40189711740: default_for lines
    74-76, is_defaulted lines 90-92). Decision 1's
    registry has one enum key today, dtls_greeting:
    its documented default answers for it, an
    unusable value for it is defaulted, a usable one
    is not, and a key in neither table has no
    default and is never defaulted.
    """

    def test_the_enum_key_and_the_unknown_key(self):
        from runner.guard import defaulted
        self.assertEqual(defaulted.default_for("dtls_greeting"),
                         "family")
        self.assertIsNone(defaulted.default_for("no_such_key"))
        self.assertTrue(
            defaulted.is_defaulted("dtls_greeting", "bogus"))
        self.assertTrue(
            defaulted.is_defaulted("dtls_greeting", 7))
        self.assertFalse(
            defaulted.is_defaulted("dtls_greeting", "full"))
        self.assertFalse(
            defaulted.is_defaulted("no_such_key", "bogus"))


class DefaultedTableMatchesRegistryTests(unittest.TestCase):
    """runner/guard/defaulted.py (the runtime table behind the
    Decision-1 warning line) must agree with the registry rows."""

    def test_every_core_numeric_confval_row_is_in_the_table(self):
        from runner.guard import defaulted
        want = {}
        for r in ROWS:
            if (r["policy"] == "default" and r["scope"] == "core"
                    and r["probe"] == "confval"
                    and r["key"].isidentifier()):
                want[r["key"]] = (r["default"], r["lo"], r["hi"])
        got = dict(defaulted.NUMERIC)
        for k, v in defaulted.ENUM.items():
            got[k] = (v[0], None, None)
        self.assertEqual(got, want)

    def test_unusable_shapes_are_named_and_usable_ones_are_not(self):
        from runner.guard import defaulted
        for bad in ("x", "", True, False, float("inf"), float("nan"),
                    10 ** 400, [1], {"a": 1}, -5):
            self.assertTrue(
                defaulted.is_defaulted("max_job_age_sec", bad), repr(bad))
        for good in (1, 3600, "45", 2.5):
            self.assertFalse(
                defaulted.is_defaulted("max_job_age_sec", good), repr(good))
        self.assertFalse(defaulted.is_defaulted("max_job_age_sec", None))
        self.assertIsNone(defaulted.summary_line([]))


@unittest.skipUnless(sys.platform.startswith("linux"),
                     "needs bwrap on Linux")
class SandboxStartupRefusalProbes(unittest.TestCase):
    """Q9 (phase 2, Muse's lane to probe, Claude's to build):
    a failing-by-design probe for the startup sandbox check.

    The first env-axes pair (run 40142317272) found that with
    apparmor_restrict_unprivileged_userns=1 -- what Ubuntu
    24.04 ships -- bwrap cannot set up its namespace, so every
    job under security.modes.confinement: enforce fails
    without running. Fail-closed is the safe side, but the
    failure is silent at startup: the operator learns the
    sandbox is unusable only when jobs start failing.

    Q9's proposal, under Decision 1's refuse rule (a security
    mode whose mechanism cannot engage changes what the box
    protects): at startup under confinement: enforce, the
    runner probes bwrap once and, if it cannot start, refuses
    to start and names the cause -- including the sysctl when
    it reads 1.

    These tests FAIL BY DESIGN until that check lands. Do not
    make them pass by editing the tests. The boot seam is
    main() in --inspect mode (the full startup sequence, no
    mailbox), with PATH controlled so bwrap is missing,
    present-but-failing, or present-and-working, which pins
    the behavior however the probe is implemented (a `which`
    check or a trial run). The two controls pass today and
    must keep passing: a working bwrap starts, and audit mode
    -- which falls back loudly by design -- starts without
    one. Where the sysctl reads 1 in the test environment,
    the refusal must name it; that assertion is conditional
    on the environment, not a skip.
    """

    def _boot(self, mode, path_dir):
        import io
        import json
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock
        from runner import runner as R
        td = tempfile.mkdtemp(prefix="hp-q9-")
        path = os.path.join(td, "config.json")
        cfg = {"security": {"modes": {"confinement": mode}},
               "base_dir": td}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        out = io.StringIO()
        argv = ["runner", "--config", path, "--inspect", "board"]
        with mock.patch.dict(os.environ, {"PATH": path_dir}):
            with mock.patch.object(sys, "argv", argv):
                with redirect_stdout(out), redirect_stderr(out):
                    rc = R.main()
        return rc, out.getvalue()

    def _fake_bwrap_dir(self, exit_code):
        import tempfile
        td = tempfile.mkdtemp(prefix="hp-q9-bin-")
        path = os.path.join(td, "bwrap")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit %d\n" % exit_code)
        os.chmod(path, 0o755)
        return td

    def _assert_refusal(self, rc, text, sysctl_cause=False):
        self.assertNotEqual(rc, 0)
        lowered = text.lower()
        self.assertTrue(
            any(name in lowered
                for name in ("confinement", "sandbox", "bwrap")),
            "refusal does not name the mechanism: %r" % text[:300])
        # The sysctl is named when it is the cause -- a trial
        # run that failed -- not when the binary is simply
        # absent (the shipped refusal in 48b38bb names what
        # actually failed; an earlier draft of this probe
        # demanded the sysctl in both cases and was wrong).
        if not sysctl_cause:
            return
        sysctl = "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"
        try:
            with open(sysctl, encoding="ascii") as fh:
                value = fh.read().strip()
        except OSError:
            value = None
        if value == "1":
            self.assertIn("apparmor_restrict_unprivileged_userns",
                          text)

    def test_refuses_when_bwrap_is_missing(self):
        import tempfile
        empty = tempfile.mkdtemp(prefix="hp-q9-empty-")
        rc, text = self._boot("enforce", empty)
        self._assert_refusal(rc, text)

    def test_refuses_when_bwrap_cannot_start(self):
        rc, text = self._boot("enforce", self._fake_bwrap_dir(1))
        self._assert_refusal(rc, text, sysctl_cause=True)

    @unittest.skipUnless(sys.platform.startswith("linux"),
                         "needs bwrap on Linux")
    def test_control_starts_when_bwrap_can_start(self):
        rc, _text = self._boot("enforce", self._fake_bwrap_dir(0))
        self.assertEqual(rc, 0)

    def test_control_audit_mode_starts_without_bwrap(self):
        import tempfile
        empty = tempfile.mkdtemp(prefix="hp-q9-empty-")
        rc, _text = self._boot("audit", empty)
        self.assertEqual(rc, 0)


class ReloadHotConfigEdgesTest(unittest.TestCase):
    """Queue A refill: reload_hot_config's guard legs
    (coverage run 40189608702: 5 lines on both
    platforms). The reload's docstring fixes the
    shape: state holds the last mtime, and anything
    unusable is left alone for the next cycle -- a
    state that is not a dict reads as fresh, a config
    file that cannot be statted changes nothing, and
    a hot verbose value that is neither a bool nor a
    string is ignored and named, never applied.
    """

    def _write(self, d, obj):
        import json
        path = os.path.join(d, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path

    def test_a_non_dict_state_reads_as_fresh(self):
        import tempfile
        from runner import runner as R
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, {"poll_interval_sec": 33})
            cfg = {}
            changed = R.reload_hot_config(cfg, path, "junk")
            self.assertEqual(changed, ["poll_interval_sec"])
            self.assertEqual(cfg["poll_interval_sec"], 33)

    def test_a_missing_config_file_changes_nothing(self):
        import tempfile
        from runner import runner as R
        with tempfile.TemporaryDirectory() as d:
            cfg = {"poll_interval_sec": 20}
            changed = R.reload_hot_config(
                cfg, os.path.join(d, "gone.json"), {})
            self.assertEqual(changed, [])
            self.assertEqual(cfg, {"poll_interval_sec": 20})

    def test_an_invalid_verbose_value_is_ignored_and_named(self):
        import io
        import tempfile
        from contextlib import redirect_stderr, redirect_stdout
        from runner import runner as R
        with tempfile.TemporaryDirectory() as d:
            path = self._write(
                d, {"verbose": 42, "poll_interval_sec": 33})
            cfg, state = {}, {}
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(out):
                changed = R.reload_hot_config(cfg, path, state)
            self.assertEqual(changed, ["poll_interval_sec"])
            self.assertNotIn("verbose", cfg)
            self.assertIn("ignoring invalid verbose",
                          out.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
