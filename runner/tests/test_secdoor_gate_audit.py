#!/usr/bin/env python3
"""D-1-2 caller audit: the startup security gate covers every caller.

Lane D finding D-1-2 (Gemini, guard subsystem) observed that
runner/guard/security.py's sec_mode returns "off" for malformed
security shapes -- a non-dict security block, a non-dict modes
block, an unknown-or-invalid mode value -- and for a non-dict cfg.
That fail-open return is deliberate (see sec_mode's docstring):
validate_security_config refuses the same shapes at startup.
What the finding left open was the caller audit, done first-hand
before this file was written:

- Production callers of sec_mode / sec_decide: guard/security.py
  itself (effective_modes, sec_decide), guard/panic.py
  (protection -- an install-time doctor sentence, not a gate),
  ops/main.py (the startup gates, after validation), ops/mail.py
  (the M2 policy-constraints leg of job handling), ops/
  remediation_ops.py (job_user preexec + startup problem),
  ops/posture.py (the read-only posture report), wire/verify.py
  (check_audience / audience_allows / check_door_policy, called
  from ops/mail.py, ops/queries.py, ops/handlers.py,
  ops/cancel.py, ops/startup.py -- all job handling), and
  runner.py's _confinement_argv. Every one of those runs inside
  the single runner process whose only entry is ops/main.py's
  main(), and main() calls validate_security_config (ops/main.py)
  before the poll loop AND before every one-shot branch
  (--inspect, --fetch-sources, --audit-report, --posture,
  --run-variant, --remediation-release, --diagnose, --oracle,
  --local-test).
- The other processes never consult the helpers at all: the five
  transport extension mains (email, file, dtls, nats, queues) are
  channel pipes that move envelopes to the gated process; the
  sense extensions under runner/extensions/ and the cloud-side
  helpers under runner/cloud/ make no security-mode decision;
  the --query-worker re-entry (ops/queries.py worker_main) is a
  stdin/stdout pattern matcher that never sees a config.
- A non-dict cfg cannot reach a running runner: load_config
  refuses a config file whose top level is not a JSON object,
  the setup wizard builds dicts and never writes a security
  block, and reload_hot_config copies only HOT_KEYS / LIVE_KEYS
  / registered default-class keys from a re-read file -- the
  security block is in none of them (the reload half is also
  pinned for valid blocks in test_security_md_claims.py).
- validate_security_config's silent return for a non-dict cfg
  is therefore unreachable through the runner's own loader.

Verdict: NOT a defect. This file pins the gate so the audit's
conclusion cannot silently rot: every one-shot branch refuses a
malformed security block before the branch runs, a non-object
config file refuses at load, a malformed security block in a
hot-reloaded file never reaches the running cfg, and the pipe /
helper processes stay free of security-mode consultations.
The per-shape startup refusals themselves are pinned in
test_decision1_startup.py (RefuseMainTest) and
test_security_config.py (ValidateTest, StartupHookTest); the
helper's malformed-reads-off behaviour is pinned there too
(SecModeTest, DefaultFlipTest) -- it is the gate, not the
helper, that keeps it unreachable, and the gate is what the
tests below hold.
"""
import contextlib
import inspect as _inspect
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import runner.runner as RR  # noqa: E402
from runner.guard import security as S  # noqa: E402

STRONG_SECRET = "ab" * 32

# A config whose only malformed element is one mode value --
# exactly the shape sec_mode reads as "off" when it is reached
# without the gate. confinement and job_user are off so a valid
# twin of this config starts cleanly on any platform.
BAD_MODES = {"modes": {"confinement": "off", "job_user": "off",
                       "audience": "bogus"}}
GOOD_MODES = {"modes": {"confinement": "off", "job_user": "off"}}


def run_main(security, argv_extra):
    """One real startup through main(). Returns (rc, stdout, stderr)."""
    tmpdir = tempfile.mkdtemp(prefix="hp-secdoor-")
    cfg = {"mailbox_user": "a@b.c", "mailbox_password": "p",
           "shared_secret": STRONG_SECRET, "base_dir": tmpdir,
           "security": security}
    cfg_path = os.path.join(tmpdir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    out, err = io.StringIO(), io.StringIO()
    argv = ["runner", "--config", cfg_path, *argv_extra]
    with mock.patch.object(sys, "argv", argv):
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            try:
                rc = RR.main()
            except SystemExit as e:
                rc = e.code
    return rc, out.getvalue(), err.getvalue()


class BranchGateTest(unittest.TestCase):
    """The gate fires before every one-shot branch in main().

    Each test pairs the malformed config (refused, security key
    named, branch never runs) with the valid twin (the branch
    really runs), so the refusal cannot pass vacuously because
    a branch is broken.
    """

    def test_posture_refused_before_the_report(self):
        rc, out, err = run_main(BAD_MODES, ["--posture"])
        self.assertEqual(rc, 2)
        self.assertIn("security.modes.audience", err)
        self.assertNotIn("Security posture", out)
        rc, out, err = run_main(GOOD_MODES, ["--posture"])
        self.assertIn("Security posture", out)
        self.assertNotIn("security.modes.audience", err)

    def test_audit_report_refused_before_the_report(self):
        rc, out, err = run_main(BAD_MODES, ["--audit-report"])
        self.assertEqual(rc, 2)
        self.assertIn("security.modes.audience", err)
        rc, out, err = run_main(GOOD_MODES, ["--audit-report"])
        self.assertEqual(rc, 0, err)

    def test_inspect_refused_before_the_inspection(self):
        rc, out, err = run_main(BAD_MODES, ["--inspect", "outbox"])
        self.assertEqual(rc, 2)
        self.assertIn("security.modes.audience", err)
        self.assertNotIn('"waiting"', out)
        rc, out, err = run_main(GOOD_MODES, ["--inspect", "outbox"])
        self.assertEqual(rc, 0, err)
        self.assertIn('"waiting"', out)

    def test_fetch_sources_refused_before_any_fetch(self):
        rc, out, err = run_main(BAD_MODES, ["--fetch-sources"])
        self.assertEqual(rc, 2)
        self.assertIn("security.modes.audience", err)
        self.assertNotIn("extension sources:", out)

    def test_run_variant_refused_before_the_variant_is_read(self):
        missing = os.path.join(tempfile.gettempdir(),
                               "hp-secdoor-no-such-variant.json")
        rc, out, err = run_main(BAD_MODES, ["--run-variant", missing])
        self.assertEqual(rc, 2)
        self.assertIn("security.modes.audience", err)
        self.assertNotIn("run-variant:", err)
        rc, out, err = run_main(GOOD_MODES, ["--run-variant", missing])
        self.assertEqual(rc, 2)
        self.assertIn("run-variant: cannot read variant", err)

    def test_remediation_release_refused_before_the_release(self):
        rc, out, err = run_main(
            BAD_MODES, ["--remediation-release", "hp-secdoor-job"])
        self.assertEqual(rc, 2)
        self.assertIn("security.modes.audience", err)
        self.assertNotIn("no quarantined job", err)
        rc, out, err = run_main(
            GOOD_MODES, ["--remediation-release", "hp-secdoor-job"])
        self.assertEqual(rc, 1)
        self.assertIn("no quarantined job", err)


class NonDictConfigTest(unittest.TestCase):
    """A config file that is not a JSON object never becomes a cfg.

    This is what makes validate_security_config's silent return
    for a non-dict cfg (and sec_mode's "off" for one) unreachable
    in a running runner: the loader refuses first.
    """

    PAYLOADS = ["[1, 2]", '"just a string"', "42", "true", "null"]

    def test_load_config_refuses_non_object_json(self):
        for payload in self.PAYLOADS:
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as d:
                    path = os.path.join(d, "config.json")
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(payload)
                    with self.assertRaisesRegex(
                            RuntimeError, "must be a JSON object"):
                        RR.load_config(path)

    def test_main_refuses_a_non_object_config_file(self):
        for payload in self.PAYLOADS:
            with self.subTest(payload=payload):
                tmpdir = tempfile.mkdtemp(prefix="hp-secdoor-")
                cfg_path = os.path.join(tmpdir, "config.json")
                with open(cfg_path, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(
                        sys, "argv", ["runner", "--config", cfg_path]):
                    with contextlib.redirect_stdout(out), \
                            contextlib.redirect_stderr(err):
                        rc = RR.main()
                self.assertEqual(rc, 2)
                self.assertIn("must be a JSON object", err.getvalue())

    def test_load_config_accepts_an_object(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"security": GOOD_MODES}, fh)
            cfg = RR.load_config(path)
        self.assertIsInstance(cfg, dict)
        self.assertEqual(S.sec_mode(cfg, "audience"), "enforce")


class MalformedReloadTest(unittest.TestCase):
    """A malformed security block in a re-read config file never
    reaches the running cfg: reload copies only the hot, live and
    default-class keys, and the security block is none of them."""

    def _reload(self, fresh_security):
        running_security = {"modes": {"confinement": "off"}}
        cfg = {"poll_interval_sec": 20, "security": running_security}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"poll_interval_sec": 5,
                           "security": fresh_security}, fh)
            changed = RR.reload_hot_config(cfg, path, {"mtime": 0})
        return cfg, changed, running_security

    def test_non_object_modes_in_file_do_not_reach_running_cfg(self):
        cfg, changed, running_security = self._reload("off")
        # Positive control: the reload really ran.
        self.assertEqual(changed, ["poll_interval_sec"])
        self.assertIs(cfg["security"], running_security)
        self.assertEqual(S.sec_mode(cfg, "confinement"), "off")

    def test_bad_mode_value_in_file_does_not_reach_running_cfg(self):
        cfg, changed, running_security = self._reload(
            {"modes": {"audience": "bogus"}})
        self.assertEqual(changed, ["poll_interval_sec"])
        self.assertIs(cfg["security"], running_security)
        self.assertEqual(S.sec_mode(cfg, "audience"), "enforce")


class PipeProcessesDoNotConsultTest(unittest.TestCase):
    """The processes that run without main()'s gate -- transport
    pipes, sense extensions, cloud-side helpers -- never consult
    a security-mode or door-policy decision: they move envelopes
    and leave every decision to the gated runner process."""

    DECISIONS = ("sec_mode", "sec_decide", "validate_security_config",
                 "check_door_policy", "check_audience",
                 "audience_allows")

    def _scan(self, *parts):
        root = os.path.join(REPO, *parts)
        hits, files = [], []
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                files.append(path)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                for word in self.DECISIONS:
                    if word in text:
                        hits.append("%s: %s" % (path, word))
        return files, hits

    def test_transport_extensions_consult_nothing(self):
        files, hits = self._scan("runner", "transport_extensions")
        # Non-vacuous: all five shipped transport mains are scanned.
        for transport in ("email", "file", "dtls", "nats", "queues"):
            self.assertIn(
                os.path.join(REPO, "runner", "transport_extensions",
                             transport, "__main__.py"), files)
        self.assertEqual(hits, [])

    def test_sense_extensions_consult_nothing(self):
        files, hits = self._scan("runner", "extensions")
        self.assertGreater(len(files), 20)
        self.assertEqual(hits, [])

    def test_cloud_helpers_consult_nothing(self):
        files, hits = self._scan("runner", "cloud")
        self.assertGreater(len(files), 2)
        self.assertEqual(hits, [])

    def test_query_worker_consults_nothing(self):
        # The --query-worker re-entry is a separate process with no
        # gate of its own; its whole contract is pattern matching
        # over stdin lines, and it must stay that way.
        from runner.ops import queries
        src = _inspect.getsource(queries.worker_main)
        for word in self.DECISIONS + ("security", "load_config"):
            self.assertNotIn(word, src)


if __name__ == "__main__":
    unittest.main()
