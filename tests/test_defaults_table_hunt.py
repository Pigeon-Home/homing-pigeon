"""The table-driven hunt: step 5 of the campaign plan.

One parameterized walk over tests/defaults_registry.py. Every row
is probed with the fifteen shapes the campaign found its bugs
with -- omitted; null; the empty string; true; false; zero; a
negative number; the documented default written explicitly; a
numeric string; a non-numeric string; a several-hundred-digit integer
(10**400, the campaign's huge shape); inf;
-inf; NaN; the wrong container type -- and the row's policy is
asserted:

- probe "confval": the value goes through runner/confval.py, the
  reader the row's code uses, with the row's default and bounds.
  An unusable shape must read as the documented default; a usable
  one must come through. (At the reader, "omitted" and "null"
  are the same input -- cfg.get returns None for both -- so the
  omitted shape is probed as None and the identity is noted
  here, not hidden.)
- probe "refuse": the value is placed at the key's path in a
  config and handed to the refusing reader itself
  (resources.parse_resources, dri.parse_dri, mailbox._port,
  verify.build_key_policies). A present-but-unusable value must
  raise the reader's RuntimeError config error; an omitted key
  must parse. Which middle shapes are usable is a property of
  the reader family (a confval gate parses numeric strings, the
  DRI isinstance gate does not; mailbox._port does not range
  check), and the tables below say so per row rather than
  pretending uniformity.
- probe "handwritten": the row's coverage is the named class in
  tests/test_doc_default_divergences.py; the hunt asserts the
  class exists. The 226 hand-written tests stay untouched as
  the record.
- probe "policy-conflict": Decision 1 puts the key in the
  refuse class, but the shipped reader still reads it as the
  default. Those rows are NOT probed as defaults and NOT
  skipped: they are recorded below as failing-by-design
  divergence tests (PolicyConflictDivergenceTests), in the
  campaign's four-part format. They pass only when the readers
  move -- docs first, per the decision's adoption cost.

The registry guards (doc drift, confval coverage, shape) are
imported from tests.defaults_registry so default discovery runs
them here; defaults_registry.py is not itself a test_*.py file.
"""
import ast
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from runner import confval  # noqa: E402
from runner import dri as _dri  # noqa: E402
from runner import mailbox as _mailbox  # noqa: E402
from runner import resources as _resources  # noqa: E402
from runner import verify as _verify  # noqa: E402
from tests.defaults_registry import ROWS  # noqa: E402
from tests.defaults_registry import (  # noqa: E402,F401
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
        self.assertEqual({"confval", "refuse", "policy-conflict",
                          "handwritten"}, probes)
        self.assertEqual(len(ROWS), sum(
            1 for r in ROWS if r["probe"] in probes))


class PolicyConflictDivergenceTests(unittest.TestCase):
    """Divergence: Decision 1 puts the DTLS port, the DTLS bind
    address, and the NATS URL port in the refuse class, but the
    shipped readers still read an unusable value as the default.

    (a) The claim (Decision 1, Andrew via Claude, 2026-10-23,
        stamped by Muse; the normative sentence for PROTOCOL.md
        and docs/configuring-oracle.md): "a setting that is
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

    (c) Behavior actually observed: DtlsPipe constructs and
        binds with port "2O220" read as 20220 and with a
        non-string bind read as 0.0.0.0; NatsClient resolves
        "nats://127.0.0.1:2O220" and "...:99999" to port 4222.
        No error is raised by any of the three.

    (d) Do not make this test pass by editing the test. It
        passes only when the bug described above is fixed in
        the code. Per the decision's adoption cost, the two doc
        lines change FIRST and these tests change with the docs,
        not before; the production reader moves belong to the
        adopting release lane, not to this campaign pass.
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
