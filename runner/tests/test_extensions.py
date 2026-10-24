#!/usr/bin/env python3
"""Tests for user extensions (runner/extensions.py + the wiring).

The contract under test, end to end:

- a manifest (extension.json) is validated strictly: missing and
  unknown fields and bad types are refused by name, so a typo
  never silently does nothing;
- api_version follows the additive-only promise: the current
  version loads, a newer one is refused with a readable reason,
  an older one still loads (the rule is exercised by moving the
  module constant, because while the API is v1 no older exists);
- an extension-backed sense files DECLARED signals only: an
  undeclared signal (or none) is rejected at ingest and logged,
  never stored;
- a declared signal reaches the senses answer with its declared
  description attached, and the answer carries the declaration
  itself as a glossary -- the declaration is the context the
  Oracle receives;
- the extension is bound to its own sensor identity through the
  senses key binding, like every sense;
- a broken extension is refused and reported; the agent and the
  other senses are unaffected;
- the shipped example (Lab Results) loads clean and its watcher
  diffs a results folder into declared signals.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402
from runner import senses as S  # noqa: E402
from runner import runner as R  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions", "lab-results")
EXAMPLE_PARENT = os.path.join(REPO, "runner", "extensions")


def _manifest(**kw):
    m = {
        "name": "lab_results",
        "version": "0.3.0",
        "api_version": 1,
        "kind": "sense",
        "signals": [
            {"name": "experiment_finished",
             "description": "A run reached a finished state."},
            {"name": "metric_threshold_crossed",
             "description": "The headline metric crossed the threshold."},
        ],
    }
    m.update(kw)
    return m


def _write_folder(root, folder, payload):
    d = os.path.join(root, folder)
    os.makedirs(d, exist_ok=True)
    if payload is not None:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        with open(os.path.join(d, "extension.json"), "w",
                  encoding="utf-8") as fh:
            fh.write(text)
    return d


class ManifestValidationTest(unittest.TestCase):
    def test_valid_minimal(self):
        m = E.parse_manifest(_manifest())
        self.assertEqual(m["name"], "lab_results")
        self.assertEqual(m["description"], "")
        self.assertEqual(m["tunables"], {})
        self.assertEqual(len(m["signals"]), 2)

    def test_valid_with_optionals(self):
        m = E.parse_manifest(_manifest(
            description="Watches the lab.",
            tunables={"metric": "accuracy", "threshold": 0.9}))
        self.assertEqual(m["description"], "Watches the lab.")
        self.assertEqual(m["tunables"]["threshold"], 0.9)

    def test_not_an_object(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(["not", "a", "manifest"])

    def test_unknown_field_refused_by_name(self):
        with self.assertRaises(ValueError) as cm:
            E.parse_manifest(_manifest(singals=[]))
        self.assertIn("singals", str(cm.exception))

    def test_missing_field(self):
        m = _manifest()
        del m["signals"]
        with self.assertRaises(ValueError) as cm:
            E.parse_manifest(m)
        self.assertIn("signals", str(cm.exception))

    def test_bad_name(self):
        for bad in ("", "has space", "a/b", 7, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                E.parse_manifest(_manifest(name=bad))

    def test_bad_version(self):
        for bad in ("1.0", "v1.0.0", "latest", 3, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                E.parse_manifest(_manifest(version=bad))

    def test_semver_suffixes_ok(self):
        m = E.parse_manifest(_manifest(version="1.0.0-rc.1+lab"))
        self.assertEqual(m["version"], "1.0.0-rc.1+lab")

    def test_bad_api_version(self):
        for bad in ("1", True, 0, -2, 1.0, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                E.parse_manifest(_manifest(api_version=bad))

    def test_bad_kind(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(kind="actuator"))

    def test_signals_must_be_nonempty_list(self):
        for bad in ([], "experiment_finished", None, 3):
            with self.assertRaises(ValueError, msg=repr(bad)):
                E.parse_manifest(_manifest(signals=bad))

    def test_signal_entry_needs_both_fields(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(
                signals=[{"name": "experiment_finished"}]))

    def test_signal_entry_unknown_field(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(signals=[
                {"name": "s", "description": "d", "loudness": 3}]))

    def test_duplicate_signal_names(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(signals=[
                {"name": "s", "description": "one"},
                {"name": "s", "description": "two"}]))

    def test_signal_description_must_be_one_line(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(signals=[
                {"name": "s", "description": "two\nlines"}]))
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(signals=[
                {"name": "s", "description": "x" * 201}]))
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(signals=[
                {"name": "s", "description": "  "}]))

    def test_bad_tunables(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(tunables=["metric"]))

    def test_a_description_with_a_newline_is_refused(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(description="two\nlines"))

    def test_a_signal_that_is_not_an_object_is_refused(self):
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(signals=["experiment_finished"]))
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(signals=[
                {"name": "has space", "description": "d"}]))

    def test_too_many_signals(self):
        sigs = [{"name": "s%d" % i, "description": "d"} for i in range(65)]
        with self.assertRaises(ValueError):
            E.parse_manifest(_manifest(signals=sigs))


class ApiVersionMatrixTest(unittest.TestCase):
    def test_current_version_accepted(self):
        self.assertIsNone(E.api_refusal(_manifest(api_version=1)))
        self.assertEqual(E.EXTENSION_API_VERSION, 1)

    def test_newer_refused_with_reason(self):
        reason = E.api_refusal(_manifest(api_version=2))
        self.assertIn("requires extension API v2", reason)
        self.assertIn("update the agent", reason)

    def test_additive_promise_older_still_loads(self):
        # While the API is v1 no older manifest exists, so move the
        # constant: a v1 manifest must still load when the agent's
        # API is v2 -- fields are added, never removed or
        # reinterpreted. A v3 manifest is still refused.
        old = E.EXTENSION_API_VERSION
        E.EXTENSION_API_VERSION = 2
        try:
            self.assertIsNone(E.api_refusal(_manifest(api_version=1)))
            self.assertIsNone(E.api_refusal(_manifest(api_version=2)))
            self.assertIsNotNone(E.api_refusal(_manifest(api_version=3)))
            with tempfile.TemporaryDirectory() as d:
                _write_folder(d, "lab", _manifest(api_version=1))
                registry, problems = E.load_extensions(d)
                self.assertIn("lab_results", registry)
                self.assertEqual(problems, [])
        finally:
            E.EXTENSION_API_VERSION = old

    def test_loader_refuses_newer(self):
        with tempfile.TemporaryDirectory() as d:
            _write_folder(d, "future", _manifest(api_version=99))
            registry, problems = E.load_extensions(d)
            self.assertEqual(registry, {})
            self.assertEqual(len(problems), 1)
            self.assertIn("refused: extension requires extension "
                          "API v99", problems[0])


class ExtensionsDirForTest(unittest.TestCase):
    def test_default_is_base_dir_extensions(self):
        self.assertEqual(E.extensions_dir_for({}, "/base"),
                         os.path.join("/base", "extensions"))

    def test_explicit_absolute_wins(self):
        self.assertEqual(
            E.extensions_dir_for({"extensions_dir": "/elsewhere"}, "/base"),
            "/elsewhere")

    def test_relative_resolves_against_base(self):
        self.assertEqual(
            E.extensions_dir_for({"extensions_dir": "exts"}, "/base"),
            os.path.join("/base", "exts"))

    def test_nowhere_to_look(self):
        self.assertEqual(E.extensions_dir_for({}, ""), "")
        self.assertEqual(E.extensions_dir_for(None, None), "")


class LoaderTest(unittest.TestCase):
    def test_missing_dir_is_empty_and_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            registry, problems = E.load_extensions(
                os.path.join(d, "nope"))
            self.assertEqual(registry, {})
            self.assertEqual(problems, [])

    def test_a_folder_that_cannot_be_stated_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "cloudy"))
            real = os.path.isdir

            def boom(path):
                if str(path).endswith("cloudy"):
                    raise OSError("stat")
                return real(path)

            with mock.patch("os.path.isdir", boom):
                registry, problems = E.load_extensions(d)
            self.assertEqual(registry, {})
            self.assertEqual(problems, [])

    def test_loads_and_indexes_signals(self):
        with tempfile.TemporaryDirectory() as d:
            _write_folder(d, "lab", _manifest())
            registry, problems = E.load_extensions(d)
            self.assertEqual(problems, [])
            m = registry["lab_results"]
            self.assertEqual(m["version"], "0.3.0")
            self.assertEqual(
                E.signal_description(m, "experiment_finished"),
                "A run reached a finished state.")
            self.assertIsNone(E.signal_description(m, "explosion"))
            self.assertIsNone(E.signal_description(None, "x"))
            self.assertIsNone(E.signal_description({}, "x"))

    def test_broken_json_refused_not_raised(self):
        with tempfile.TemporaryDirectory() as d:
            _write_folder(d, "broken", "{not json")
            registry, problems = E.load_extensions(d)
            self.assertEqual(registry, {})
            self.assertEqual(len(problems), 1)
            self.assertIn("broken", problems[0])

    def test_invalid_manifest_refused_with_reason(self):
        with tempfile.TemporaryDirectory() as d:
            _write_folder(d, "bad", _manifest(kind="actuator"))
            registry, problems = E.load_extensions(d)
            self.assertEqual(registry, {})
            self.assertIn("kind", problems[0])

    def test_folder_without_manifest_reported(self):
        with tempfile.TemporaryDirectory() as d:
            _write_folder(d, "stray", None)
            registry, problems = E.load_extensions(d)
            self.assertEqual(registry, {})
            self.assertEqual(len(problems), 1)
            self.assertIn("extension.json", problems[0])

    def test_duplicate_name_first_wins(self):
        with tempfile.TemporaryDirectory() as d:
            _write_folder(d, "aaa", _manifest(version="0.1.0"))
            _write_folder(d, "zzz", _manifest(version="0.2.0"))
            registry, problems = E.load_extensions(d)
            self.assertEqual(registry["lab_results"]["version"], "0.1.0")
            self.assertEqual(len(problems), 1)
            self.assertIn("duplicate", problems[0])

    def test_files_and_dotfolders_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "README.txt"), "w") as fh:
                fh.write("not an extension")
            _write_folder(d, ".hidden", "{not json")
            registry, problems = E.load_extensions(d)
            self.assertEqual(registry, {})
            self.assertEqual(problems, [])

    def test_symlinked_manifest_refused(self):
        with tempfile.TemporaryDirectory() as d:
            real = _write_folder(d, "real", _manifest())
            linkdir = os.path.join(d, "linked")
            os.makedirs(linkdir)
            try:
                os.symlink(os.path.join(real, "extension.json"),
                           os.path.join(linkdir, "extension.json"))
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            registry, problems = E.load_extensions(d)
            self.assertIn("lab_results", registry)  # the real one
            self.assertTrue(any("symlink" in p for p in problems))

    def test_a_broken_set_never_raises(self):
        with tempfile.TemporaryDirectory() as d:
            _write_folder(d, "a", "{")
            _write_folder(d, "b", _manifest(api_version=42))
            _write_folder(d, "c", None)
            _write_folder(d, "ok", _manifest(name="fine"))
            registry, problems = E.load_extensions(d)
            self.assertEqual(sorted(registry), ["fine"])
            self.assertEqual(len(problems), 3)


class FakeIMAP:
    def __init__(self):
        self.flagged = []

    def store(self, seq, _op, _flags):
        self.flagged.append(seq)
        return ("OK", [])


def _alert(sensor="lab_results", severity="info", title="t", **kw):
    a = {
        "v": 1, "type": "job", "kind": "sensor_alert",
        "job_id": "a1", "issued_at": "2026-10-15T12:00:00Z",
        "sensor": sensor, "severity": severity, "title": title,
    }
    a.update(kw)
    return a


class IngestGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "lab-results"))
        self.cfg = {
            "extensions_dir": self.ext_root,
            "sensors": {
                "lab_results": {"enabled": True, "key_id": "lab-key",
                                "weight": 1.0, "profile": {}},
                "host_ids": {"enabled": True, "key_id": "ids-key",
                             "weight": 1.0, "profile": {}},
            },
        }

    def _ingest(self, job, key_id, cfg=None, opts=None):
        imap = FakeIMAP()
        seen = {}
        R._ingest_sensor_alert(cfg or self.cfg, imap, "1",
                               job.get("job_id", "a1"), job, key_id,
                               {}, opts, self.base, seen)
        return imap, seen

    def test_declared_signal_stored_with_description(self):
        self._ingest(_alert(signal="experiment_finished",
                            title="experiment exp-041 finished"),
                     "lab-key")
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["signal"], "experiment_finished")
        self.assertEqual(
            rec["signal_description"],
            "A run in the watched folder reached a finished state.")
        self.assertEqual(rec["extension"], "lab_results")
        self.assertEqual(rec["extension_version"], "0.3.0")
        self.assertEqual(rec["key_id"], "lab-key")

    def test_undeclared_signal_rejected_and_seen(self):
        _imap, seen = self._ingest(
            _alert(signal="total_explosion"), "lab-key")
        self.assertEqual(S.load_alerts(self.base), [])
        self.assertIn("a1", seen)  # rejected once, not retried

    def test_missing_signal_rejected(self):
        _imap, seen = self._ingest(_alert(), "lab-key")
        self.assertEqual(S.load_alerts(self.base), [])
        self.assertIn("a1", seen)

    def test_nonstring_signal_rejected_by_shape(self):
        self._ingest(_alert(signal=7), "lab-key")
        self.assertEqual(S.load_alerts(self.base), [])

    def test_extension_sensor_bound_to_its_own_key(self):
        # ids-key belongs to host_ids; it cannot file as lab_results
        # even with a declared signal.
        self._ingest(_alert(signal="experiment_finished"), "ids-key")
        self.assertEqual(S.load_alerts(self.base), [])

    def test_plain_sensor_needs_no_signal(self):
        self._ingest(_alert(sensor="host_ids", title="ids event"),
                     "ids-key")
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        self.assertNotIn("signal", recs[0])

    def test_plain_sensor_signal_carried_without_description(self):
        self._ingest(_alert(sensor="host_ids", signal="ad_hoc_note"),
                     "ids-key")
        rec = S.load_alerts(self.base)[0]
        self.assertEqual(rec["signal"], "ad_hoc_note")
        self.assertNotIn("signal_description", rec)

    def test_broken_extension_folder_does_not_block_other_senses(self):
        _write_folder(self.ext_root, "broken", "{nope")
        self._ingest(_alert(sensor="host_ids", title="still fine"),
                     "ids-key")
        self.assertEqual(len(S.load_alerts(self.base)), 1)

    def test_refused_extension_falls_back_to_plain_sensor(self):
        # The only lab-results folder requires a newer API: the
        # loader refuses it, so lab_results is a plain sense here
        # and the declared-signal gate does not apply.
        shutil.rmtree(os.path.join(self.ext_root, "lab-results"))
        _write_folder(self.ext_root, "future",
                      _manifest(api_version=99))
        self._ingest(_alert(signal="anything_goes"), "lab-key")
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        self.assertNotIn("signal_description", recs[0])

    def test_dry_run_with_declared_signal_stores_nothing(self):
        class Opts:
            dry_run = True
        _imap, seen = self._ingest(
            _alert(signal="experiment_finished"), "lab-key", opts=Opts())
        self.assertEqual(S.load_alerts(self.base), [])
        self.assertNotIn("a1", seen)


class SensesQueryContextTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(EXAMPLE_DIR,
                        os.path.join(self.ext_root, "lab-results"))
        self.cfg = {
            "extensions_dir": self.ext_root,
            "sensors": {
                "lab_results": {"enabled": True, "key_id": "lab-key",
                                "weight": 1.0, "profile": {}},
                "host_ids": {"enabled": True, "key_id": "ids-key",
                             "weight": 1.0, "profile": {}},
            },
        }
        imap = FakeIMAP()
        R._ingest_sensor_alert(
            self.cfg, imap, "1", "a1",
            _alert(signal="metric_threshold_crossed", severity="medium",
                   title="experiment exp-041: accuracy crossed"),
            "lab-key", {}, None, self.base, {})
        R._ingest_sensor_alert(
            self.cfg, imap, "2", "a2",
            _alert(sensor="host_ids", job_id="a2", title="ids event"),
            "ids-key", {}, None, self.base, {})

    def test_alert_carries_signal_and_declared_description(self):
        answers, _ = R.answer_queries(
            [{"op": "senses", "sensor": "lab_results"}], {}, {}, 8,
            cfg=self.cfg, base_dir=self.base)
        ans = answers[0]
        self.assertEqual(ans["count"], 1)
        item = ans["alerts"][0]
        self.assertEqual(item["signal"], "metric_threshold_crossed")
        self.assertEqual(
            item["signal_description"],
            "A finished run's headline metric crossed the threshold "
            "declared in this extension's tunables.")
        self.assertEqual(item["extension_version"], "0.3.0")

    def test_answer_carries_the_declaration_as_glossary(self):
        answers, _ = R.answer_queries(
            [{"op": "senses", "sensor": "lab_results"}], {}, {}, 8,
            cfg=self.cfg, base_dir=self.base)
        gloss = answers[0]["declared_signals"]["lab_results"]
        self.assertEqual(gloss["extension"], "lab_results")
        self.assertEqual(gloss["extension_version"], "0.3.0")
        names = [s["name"] for s in gloss["signals"]]
        self.assertEqual(names, ["experiment_finished",
                                 "metric_threshold_crossed",
                                 "result_anomaly"])
        for s in gloss["signals"]:
            self.assertTrue(s["description"])

    def test_no_glossary_for_plain_sensors(self):
        answers, _ = R.answer_queries(
            [{"op": "senses", "sensor": "host_ids"}], {}, {}, 8,
            cfg=self.cfg, base_dir=self.base)
        self.assertEqual(answers[0]["count"], 1)
        self.assertNotIn("declared_signals", answers[0])
        self.assertIsNone(answers[0]["alerts"][0]["signal"])


class StartupReportTest(unittest.TestCase):
    def test_report_names_loaded_and_refused(self):
        with tempfile.TemporaryDirectory() as d:
            ext_root = os.path.join(d, "exts")
            os.makedirs(ext_root)
            _write_folder(ext_root, "lab", _manifest())
            _write_folder(ext_root, "broken", "{nah")
            cfg = {"extensions_dir": ext_root}
            # log() rate-limits INFO per minute; reset the budget so
            # the lines are not suppressed by earlier tests.
            R._LOG_MINUTE = 0.0
            R._LOG_COUNT = 0
            R._LOG_DROPPED = 0
            buf = StringIO()
            with redirect_stdout(buf):
                R._report_extensions(cfg, d)
            out = buf.getvalue()
            self.assertIn("extension loaded: lab_results v0.3.0", out)
            self.assertIn("extension API v1", out)
            self.assertIn("broken", out)


def _load_example_module():
    path = os.path.join(EXAMPLE_DIR, "lab_results.py")
    spec = importlib.util.spec_from_file_location("lab_results_example",
                                                  path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ExampleExtensionTest(unittest.TestCase):
    def test_shipped_manifest_is_valid_and_loads(self):
        with open(os.path.join(EXAMPLE_DIR, "extension.json"),
                  encoding="utf-8") as fh:
            manifest = E.parse_manifest(json.load(fh))
        self.assertEqual(manifest["name"], "lab_results")
        self.assertEqual(manifest["api_version"], E.EXTENSION_API_VERSION)
        registry, problems = E.load_extensions(EXAMPLE_PARENT)
        self.assertEqual(problems, [])
        self.assertIn("lab_results", registry)

    def _results_dir(self, runs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for fname, rec in runs.items():
            with open(os.path.join(tmp.name, fname), "w",
                      encoding="utf-8") as fh:
                if isinstance(rec, str):
                    fh.write(rec)
                else:
                    json.dump(rec, fh)
        return tmp.name

    def _manifest(self):
        with open(os.path.join(EXAMPLE_DIR, "extension.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)

    def test_finished_run_files_finished_and_threshold(self):
        mod = _load_example_module()
        d = self._results_dir({
            "exp-041.json": {"run": "exp-041", "status": "finished",
                             "metrics": {"accuracy": 0.95}},
        })
        alerts, state = mod.scan(d, self._manifest(), None)
        signals = [a["signal"] for a in alerts]
        self.assertEqual(signals, ["experiment_finished",
                                   "metric_threshold_crossed"])
        self.assertTrue(all(a["sensor"] == "lab_results" for a in alerts))
        # Second pass over the same folder files nothing new.
        again, _ = mod.scan(d, self._manifest(), state)
        self.assertEqual(again, [])

    def test_quiet_run_files_finished_only(self):
        mod = _load_example_module()
        d = self._results_dir({
            "exp-001.json": {"run": "exp-001", "status": "finished",
                             "metrics": {"accuracy": 0.5}},
        })
        alerts, _state = mod.scan(d, self._manifest(), None)
        self.assertEqual([a["signal"] for a in alerts],
                         ["experiment_finished"])

    def test_anomaly_against_folder_history(self):
        mod = _load_example_module()
        runs = {}
        for i, acc in enumerate((0.80, 0.82, 0.79)):
            runs["exp-%03d.json" % i] = {
                "run": "exp-%03d" % i, "status": "finished",
                "metrics": {"accuracy": acc}}
        state = None
        d = self._results_dir(runs)
        _alerts, state = mod.scan(d, self._manifest(), state)
        with open(os.path.join(d, "exp-099.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"run": "exp-099", "status": "finished",
                       "metrics": {"accuracy": 0.40}}, fh)
        alerts, _state = mod.scan(d, self._manifest(), state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["experiment_finished", "result_anomaly"])
        self.assertEqual(alerts[-1]["severity"], "high")

    def test_unfinished_and_halfwritten_file_nothing(self):
        mod = _load_example_module()
        d = self._results_dir({
            "exp-001.json": {"run": "exp-001", "status": "running",
                             "metrics": {"accuracy": 0.99}},
            "exp-002.json": "{\"run\": \"exp-002\", \"status\": \"fin",
        })
        alerts, state = mod.scan(d, self._manifest(), None)
        self.assertEqual(alerts, [])
        # The unfinished run lands later and is picked up then.
        with open(os.path.join(d, "exp-001.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"run": "exp-001", "status": "finished",
                       "metrics": {"accuracy": 0.5}}, fh)
        alerts, _state = mod.scan(d, self._manifest(), state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["experiment_finished"])

    def test_edited_result_is_rereported(self):
        mod = _load_example_module()
        d = self._results_dir({
            "exp-001.json": {"run": "exp-001", "status": "finished",
                             "metrics": {"accuracy": 0.5}},
        })
        _a, state = mod.scan(d, self._manifest(), None)
        with open(os.path.join(d, "exp-001.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"run": "exp-001", "status": "finished",
                       "metrics": {"accuracy": 0.6}}, fh)
        alerts, _state = mod.scan(d, self._manifest(), state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["experiment_finished"])


class DocsTest(unittest.TestCase):
    def test_extensions_doc_exists_and_states_the_contract(self):
        path = os.path.join(REPO, "docs", "extensions.md")
        self.assertTrue(os.path.exists(path), "docs/extensions.md missing")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        for anchor in ("extension.json", "api_version",
                       "undeclared", "extensions_dir"):
            self.assertIn(anchor, text)


class TransportAndEnvelopeTest(unittest.TestCase):
    def _transport(self, **kw):
        m = _manifest(
            kind="transport",
            entry=["python3", "-m", "ext"],
            publisher="A lab publisher.")
        m.pop("signals", None)
        m.update(kw)
        return m

    def test_a_transport_without_an_entry_is_refused(self):
        m = self._transport()
        del m["entry"]
        with self.assertRaises(ValueError) as ctx:
            E.parse_manifest(m)
        self.assertIn("entry", str(ctx.exception))
        with self.assertRaises(ValueError):
            E.parse_manifest(self._transport(entry=["ok", "x" * 501]))
        with self.assertRaises(ValueError):
            E.parse_manifest(self._transport(publisher="two\nlines"))
        with self.assertRaises(ValueError):
            E.parse_manifest(self._transport(startup_settle_ms=9000))
        parsed = E.parse_manifest(self._transport())
        self.assertEqual(parsed["kind"], "transport")
        self.assertEqual(parsed["entry"][0], "python3")

    def test_a_description_is_looked_up_from_the_signal_list(self):
        manifest = _manifest()
        self.assertIsNone(E.signal_description(manifest, 5))
        self.assertEqual(
            E.signal_description(manifest, "experiment_finished"),
            "A run reached a finished state.")
        self.assertIsNone(E.signal_description(
            {"signals": [{"name": "s", "description": 5}]}, "s"))

    def test_the_loader_skips_what_is_not_its_business(self):
        reg, problems = E.load_extensions("")
        self.assertEqual((reg, problems), ({}, []))
        with tempfile.TemporaryDirectory() as root:
            os.symlink("/tmp", os.path.join(root, "link.json"))
            _write_folder(root, "gone", "{")
            _write_folder(root, "transport", self._transport(name="wire"))
            reg, problems = E.load_extensions(root, kinds=("sense",))
            self.assertEqual(reg, {})
            self.assertTrue(any("not valid JSON" in p for p in problems))
            self.assertFalse(any("wire" in p for p in problems))

    def test_an_envelope_needs_an_object_and_a_secret(self):
        with self.assertRaises(ValueError):
            E.sign_envelope(["nope"], "secret")
        with self.assertRaises(ValueError):
            E.sign_envelope({"v": 1}, "")
        payload = E.build_sensor_alert(
            "lab", "high", "done", observed_at="2026-10-22T00:00:00Z")
        self.assertEqual(payload["observed_at"], "2026-10-22T00:00:00Z")
        with self.assertRaises(ValueError):
            E.drop_local_signal("", payload, "secret")


if __name__ == "__main__":
    unittest.main(verbosity=2)
