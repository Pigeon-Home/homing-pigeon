#!/usr/bin/env python3
"""M3 tests: --audit-report is read-only and never suggests the
dangerous things."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import auditreport as AR  # noqa: E402
from runner.guard import security as S  # noqa: E402


def _write_audit(base_dir, entries):
    path = os.path.join(base_dir, S.AUDIT_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")


def _entry(feature, decision, reason, key_id="k1", detail=""):
    return {"ts": "2026-10-15T12:00:00Z", "feature": feature,
            "decision": decision, "reason": reason, "key_id": key_id,
            "job_id": "j1", "detail": detail}


class ParseSinceTest(unittest.TestCase):
    def test_days(self):
        self.assertEqual(AR.parse_since("14d"), 14 * 86400)

    def test_hours(self):
        self.assertEqual(AR.parse_since("48h"), 48 * 3600)

    def test_default(self):
        self.assertEqual(AR.parse_since(None), 30 * 86400)

    def test_bad(self):
        for bad in ("yesterday", "14", "d14", "", "1w"):
            with self.assertRaises(ValueError, msg=bad):
                AR.parse_since(bad)


class ReportTest(unittest.TestCase):
    def test_table_and_suggestions(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                _entry("policy_env", "would_deny", "denied_env"),
                _entry("policy_env", "would_deny", "denied_env"),
                _entry("policy_args", "denied", "arg_too_long"),
            ])
            cfg = {"additional_secrets": {"loose": "x" * 64},
                   "key_policies": {}}
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = AR.main(cfg, d, since="30d")
            out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("policy_env", out)
        self.assertIn("denied_env", out)
        # unrestricted extra key is suggested a policy entry
        self.assertIn('key "loose"', out)
        self.assertIn("Refused to suggest", out)

    def test_dangerous_names_never_suggested(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                _entry("policy_env", "would_deny", "dangerous_env",
                       detail="env 'BASH_ENV' can subvert execution"),
            ])
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main({}, d, since="30d")
            out = buf.getvalue()
        refused = out.split("Refused to suggest")[1]
        self.assertIn("BASH_ENV", refused)
        # ...but not as a suggestion to allow it
        suggested = out.split("Refused to suggest")[0]
        self.assertNotIn("BASH_ENV", suggested)

    def test_url_file_sources_never_suggested(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                _entry("policy_files", "would_deny", "file_not_allowed",
                       detail="https://evil.invalid/x.sh"),
            ])
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main({}, d, since="30d")
            out = buf.getvalue()
        refused = out.split("Refused to suggest")[1]
        self.assertIn("URL file sources are never suggested", refused)

    def test_empty_log(self):
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = AR.main({}, d, since="14d")
            self.assertEqual(rc, 0)
            self.assertIn("no audit entries", buf.getvalue())

    def test_fragments_suggest_policy(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                _entry("policy_env", "would_deny", "env_not_allowed",
                       key_id="svc",
                       detail="env 'CI' is not in allowed_env"),
                _entry("policy_env", "would_deny", "env_not_allowed",
                       key_id="svc",
                       detail="env 'CI' is not in allowed_env"),
                _entry("policy_files", "would_deny", "file_not_allowed",
                       key_id="svc",
                       detail="file 'data.csv' is not in allowed_files"),
                _entry("policy_args", "would_deny", "args_too_many",
                       key_id="svc", detail="more than 2 args"),
            ])
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main({}, d, since="30d")
            out = buf.getvalue()
        frag = out.split("Suggested key_policies fragments")[1]
        frag = frag.split("Refused to suggest")[0]
        self.assertIn("KEY: svc", frag)
        self.assertIn('"allowed_env"', frag)
        self.assertIn('"CI"', frag)
        self.assertIn('"allowed_files"', frag)
        self.assertIn('"data.csv"', frag)
        self.assertIn("args_too_many", frag)

    def test_fragments_exclude_dangerous_names(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                _entry("policy_env", "would_deny", "dangerous_env",
                       key_id="svc",
                       detail="env 'LD_PRELOAD' can subvert execution"),
            ])
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main({}, d, since="30d")
            out = buf.getvalue()
        frag = out.split("Suggested key_policies fragments")[1]
        frag = frag.split("Refused to suggest")[0]
        self.assertNotIn("LD_PRELOAD", frag)
        self.assertIn("LD_PRELOAD", out.split("Refused to suggest")[1])

    def test_key_filter(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                _entry("policy_env", "would_deny", "denied_env",
                       key_id="aaa"),
                _entry("policy_env", "would_deny", "denied_env",
                       key_id="bbb"),
            ])
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main({}, d, since="30d", key="aaa")
            out = buf.getvalue()
        self.assertIn('key "aaa"', out)
        self.assertNotIn('key "bbb"', out)

    def test_feature_filter(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                _entry("policy_env", "would_deny", "denied_env"),
                _entry("policy_args", "would_deny", "arg_too_long"),
            ])
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main({}, d, since="30d", feature="policy_args")
            out = buf.getvalue()
        self.assertIn("policy_args", out)
        self.assertNotIn("policy_env", out)

    def test_table_shows_mode_evaluated_would_deny(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                _entry("policy_env", "would_deny", "denied_env",
                       detail="env 'CI' is not in allowed_env"),
                _entry("policy_env", "would_deny", "denied_env",
                       detail="env 'CI' is not in allowed_env"),
            ])
            # evaluated counts come from the counts file
            counts_path = os.path.join(d, S.COUNTS_FILE)
            with open(counts_path, "w") as fh:
                json.dump({"policy_env": {"evaluated": 412,
                                          "would_deny": 2}}, fh)
            cfg = {"security": {"modes": {"policy_env": "audit"}}}
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main(cfg, d, since="30d")
            out = buf.getvalue()
        self.assertIn("evaluated", out)
        self.assertIn("would-deny", out)
        self.assertIn("412", out)
        self.assertIn("denied_env(2)", out)
        self.assertIn("audit", out)

    def test_since_window_filters(self):
        with tempfile.TemporaryDirectory() as d:
            _write_audit(d, [
                {"ts": "2020-01-01T00:00:00Z", "feature": "policy_env",
                 "decision": "would_deny", "reason": "old",
                 "key_id": "k", "job_id": "j"},
            ])
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main({}, d, since="14d")
            self.assertIn("no audit entries", buf.getvalue())

    def test_bad_since_returns_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(AR.main({}, d, since="yesterday"), 2)

    def test_never_writes_config(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = os.path.join(d, "config.json")
            cfg = {"base_dir": d, "shared_secret": "ab" * 32}
            with open(cfg_path, "w") as fh:
                json.dump(cfg, fh)
            before = (os.path.getmtime(cfg_path),
                      hashlib.sha256(open(cfg_path, "rb").read())
                      .hexdigest())
            buf = io.StringIO()
            with redirect_stdout(buf):
                AR.main(cfg, d, since="14d")
            after = (os.path.getmtime(cfg_path),
                     hashlib.sha256(open(cfg_path, "rb").read())
                     .hexdigest())
            self.assertEqual(before, after)

    def test_no_mailbox_credentials_needed(self):
        # A config with no mailbox keys at all still reports.
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = AR.main({"base_dir": d}, d, since="14d")
            self.assertEqual(rc, 0)


class FlagIntegrationTest(unittest.TestCase):
    def test_flag_via_main(self):
        from runner.runner import main
        with tempfile.TemporaryDirectory() as d:
            cfg_path = os.path.join(d, "config.json")
            json.dump({"base_dir": d}, open(cfg_path, "w"))
            buf = io.StringIO()
            with mock.patch.object(sys, "argv", ["runner", "--config",
                                                 cfg_path, "--audit-report",
                                                 "--since", "14d"]):
                with redirect_stdout(buf):
                    rc = main()
            self.assertEqual(rc, 0)
            self.assertIn("Security audit report", buf.getvalue())


class DangerousFallbackTest(unittest.TestCase):
    """Queue A refill: _is_dangerous' fallback (coverage
    run 40189711740: 4 lines). The report tool asks the
    security module's own check first; when that call
    raises -- a damaged or mismatched install, the same
    condition the import seam above exists for -- the
    answer falls back to the module's name list rather
    than failing the report or guessing clean.
    """

    def test_a_raising_delegate_falls_back_to_the_list(self):
        import types

        def boom(_name):
            raise RuntimeError("delegate unavailable")

        stub = types.SimpleNamespace(
            is_dangerous_env_name=boom,
            DANGEROUS_ENV_NAMES=frozenset({"LD_PRELOAD"}))
        with mock.patch.object(AR, "_security", stub):
            self.assertTrue(AR._is_dangerous("ld_preload"))
            self.assertFalse(AR._is_dangerous("HARMLESS_NAME"))
            self.assertFalse(AR._is_dangerous(None))


class EntryTsLegsTest(unittest.TestCase):
    """Queue A refill: auditreport._entry_ts'
    unparsable leg (coverage run 40189711740: lines
    77-78). An entry timestamp that does not parse
    reads as epoch 0 -- outside every report window
    -- rather than breaking the report.
    """

    def test_an_unparsable_timestamp_is_epoch(self):
        self.assertEqual(AR._entry_ts({"ts": "not a timestamp"}), 0)
        self.assertEqual(AR._entry_ts({"ts": ""}), 0)
        self.assertEqual(AR._entry_ts({}), 0)
        self.assertGreater(
            AR._entry_ts({"ts": "2026-10-25T00:00:00Z"}), 0)


class ImportSeamTest(unittest.TestCase):
    """Queue A refill: auditreport's import seam (coverage
    run 40189711740: the fallback block, 5 lines, never ran
    on either platform -- the suite always imports the
    package, so the package branch answers first). The
    module's shape, shared with the other role-folder
    tools: imported as a package it takes runner.guard's
    security; run from inside runner/ it takes the sibling
    guard package; with neither importable it still loads,
    with _security None, and its readers degrade to empty
    rather than fail -- the report tool must answer on a
    box whose install is damaged, because that is when it
    gets run.
    """

    def _fresh(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "auditreport_seam", AR.__file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _blocked_package(self):
        """A runner.guard stand-in with no security under it, so
        the package import fails the way it does on a damaged
        install (the already-imported real package would
        otherwise answer from its attribute cache)."""
        import types
        stub = types.ModuleType("runner.guard")
        stub.__path__ = []
        return stub

    def test_the_script_mode_sibling_answers(self):
        import types
        sentinel = types.SimpleNamespace(
            AUDIT_FILE="security-audit.jsonl",
            AUDIT_ROLLED_FILE="security-audit.jsonl.1")
        guard_pkg = types.ModuleType("guard")
        guard_pkg.security = sentinel
        keys = ("runner.guard", "runner.guard.security",
                "guard", "guard.security")
        saved = {k: sys.modules.get(k) for k in keys}
        sys.modules["runner.guard"] = self._blocked_package()
        sys.modules["runner.guard.security"] = None
        sys.modules["guard"] = guard_pkg
        sys.modules["guard.security"] = sentinel
        try:
            mod = self._fresh()
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        self.assertIs(mod._security, sentinel)

    def test_with_no_security_module_the_readers_are_empty(self):
        keys = ("runner.guard", "runner.guard.security", "guard")
        saved = {k: sys.modules.get(k) for k in keys}
        sys.modules["runner.guard"] = self._blocked_package()
        sys.modules["runner.guard.security"] = None
        sys.modules["guard"] = None
        try:
            mod = self._fresh()
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        self.assertIsNone(mod._security)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(mod._read_entries(d), [])


class ReadEntriesNoSecurityLegTest(unittest.TestCase):
    """Queue A refill: _read_entries without
    the security module (coverage run
    40189711740: auditreport.py line 44).
    Where the audit module itself is
    unavailable the report reads as no
    entries -- the audit report degrades, it
    does not crash the caller.
    """

    def test_no_security_module_no_entries(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(AR, "_security", None):
                self.assertEqual(AR._read_entries(d), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
