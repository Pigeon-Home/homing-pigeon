"""The extension review: the Oracle reads an extension against its
manifest before the runner loads it (runner/guard/extreview.py).

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

What the review must do: find code that contradicts the manifest
(a capability used and not declared, a signal filed and not
declared, a transport entry that leaves the folder, a symlink, a
file that does not compile, a bidi control character, a reference
to the runner's own state), refuse under `enforce` the way the
loader refuses a bad manifest, load-and-say under `advisory`, stay
out of the way under `off`, and never take the agent down over
extension data. And what it must not do: refuse the shipped
extensions, or re-read a folder nothing changed in.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner.guard import extreview as X  # noqa: E402
from runner.ops import extensions as E  # noqa: E402
from runner.wire import transports  # noqa: E402
from runner import runner as R  # noqa: E402


SENSE = {"name": "probe", "version": "0.1.0", "api_version": 1,
         "kind": "sense",
         "signals": [{"name": "seen_it", "description": "x"}]}
TRANSPORT = {"name": "smoke", "kind": "transport", "api_version": 1,
             "version": "0.1.0", "publisher": "Test Harness",
             "entry": ["{python}", "smoke.py", "{channel_dir}",
                       "{runtime_config}"]}


def _drop(root, folder, manifest, files=None):
    path = os.path.join(root, folder)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "extension.json"), "w",
              encoding="utf-8") as fh:
        json.dump(manifest, fh)
    for name, text in (files or {}).items():
        full = os.path.join(path, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text)
    return path


def _clean(manifest):
    return E.parse_manifest(dict(manifest))


def _codes(result, severity=None):
    return sorted(f["code"] for f in result["findings"]
                  if severity is None or f["severity"] == severity)


class ReviewFolderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-extreview-")
        X.forget()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        X.forget()

    def _review(self, manifest, files, **kw):
        folder = _drop(self.tmp, manifest["name"], manifest, files)
        return X.review_folder(_clean(manifest), folder, **kw)

    def test_a_quiet_sense_has_no_findings_but_the_notes(self):
        r = self._review(SENSE, {"probe.py":
                                 'ALERT = {"signal": "seen_it"}\n'})
        self.assertEqual(_codes(r, "high"), [])
        self.assertEqual(_codes(r, "warn"), [])
        self.assertEqual(r["capabilities"]["observed"], {})

    def test_an_undeclared_capability_is_high_and_names_the_remedy(self):
        r = self._review(SENSE, {"probe.py":
                                 "import subprocess\nimport socket\n"})
        high = [f for f in r["findings"] if f["severity"] == "high"]
        self.assertEqual(sorted(f["code"] for f in high),
                         ["capability.undeclared", "capability.undeclared"])
        details = " ".join(f["detail"] for f in high)
        self.assertIn('"capabilities": ["network"]', details)
        self.assertIn('"capabilities": ["subprocess"]', details)
        self.assertEqual(sorted(r["capabilities"]["observed"]),
                         ["network", "subprocess"])

    def test_a_declared_capability_is_not_a_finding(self):
        m = dict(SENSE, capabilities=["subprocess"])
        r = self._review(m, {"probe.py": "import subprocess\n"})
        self.assertEqual(_codes(r, "high"), [])
        self.assertEqual(r["capabilities"]["declared"], ["subprocess"])

    def test_an_unused_declared_capability_is_a_note(self):
        m = dict(SENSE, capabilities=["native"])
        r = self._review(m, {"probe.py": "x = 1\n"})
        self.assertEqual(_codes(r, "note"), ["capability.unused",
                                             "signal.unused"])

    def test_every_capability_has_a_marker(self):
        cases = {
            "listen": "import socket\ns = socket.socket()\ns.bind(('', 0))\n",
            "network": "import urllib.request\n",
            "subprocess": "import os\nos.system('true')\n",
            "native": "import ctypes\n",
        }
        for cap, code in cases.items():
            r = self._review(dict(SENSE, name=f"c_{cap}"),
                             {"c.py": code})
            self.assertIn(cap, r["capabilities"]["observed"], cap)

    def test_loopback_delivery_through_the_shipped_helper_is_not_network(self):
        # A sense that files through runner.ops.extensions uses the
        # sense contract, not a capability of its own.
        r = self._review(SENSE, {"probe.py":
                                 "from runner.ops import extensions as hp\n"
                                 'hp.send_local_signal({"signal": "seen_it"}, "k")\n'})
        self.assertNotIn("network", r["capabilities"]["observed"])

    def test_shell_files_count_for_network(self):
        r = self._review(SENSE, {"fetch.sh": "#!/bin/sh\ncurl http://x\n"})
        self.assertIn("network", r["capabilities"]["observed"])

    def test_a_signal_filed_and_not_declared_is_a_warning(self):
        r = self._review(SENSE, {"probe.py":
                                 'a = {"signal": "seen_it"}\n'
                                 'b = dict(signal="surprise")\n'})
        self.assertEqual(_codes(r, "warn"), ["signal.undeclared"])
        self.assertEqual(_codes(r, "high"), [])

    def test_a_declared_signal_never_filed_is_a_note(self):
        r = self._review(SENSE, {"probe.py": "x = 1\n"})
        self.assertEqual(_codes(r, "note"), ["signal.unused"])

    def test_a_file_that_does_not_compile_is_high(self):
        r = self._review(SENSE, {"probe.py": "def (:\n"})
        self.assertEqual(_codes(r, "high"), ["syntax"])
        f = r["findings"][0]
        self.assertEqual((f["path"], f["line"]), ("probe.py", 1))

    def test_a_bidi_control_character_is_high(self):
        r = self._review(SENSE, {"probe.py":
                                 "# access_level = user‮ ⁦// check\n"})
        self.assertEqual(_codes(r, "high"), ["text.control"])
        self.assertIn("U+202E", r["findings"][0]["detail"])

    def test_the_runners_own_state_is_high(self):
        r = self._review(SENSE, {"probe.py":
                                 'p = os.path.join(base, "seen.json")\n'})
        self.assertEqual(_codes(r, "high"), ["state.reference"])

    def test_a_sense_naming_the_mailbox_password_is_high(self):
        r = self._review(SENSE, {"probe.py":
                                 'pw = cfg["mailbox_password"]\n'})
        self.assertEqual(_codes(r, "high"), ["state.reference"])

    def test_a_transport_may_name_the_secret_material_it_is_handed(self):
        # dtls authenticates the PSK; the runtime config carries it.
        m = dict(TRANSPORT, entry=["{python}", "-m", "x"])
        r = self._review(m, {"x.py": 'k = cfg["shared_secret"]\n'
                                     'e = cfg.get("additional_secrets")\n'})
        self.assertEqual(_codes(r, "high"), [])

    def test_a_symlink_inside_the_folder_is_high(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        folder = _drop(self.tmp, "probe", SENSE, {"probe.py": "x = 1\n"})
        try:
            os.symlink(os.path.join(ROOT, "README.md"),
                       os.path.join(folder, "elsewhere.md"))
        except (OSError, NotImplementedError):
            self.skipTest("cannot create a symlink here")
        r = X.review_folder(_clean(SENSE), folder)
        self.assertEqual(_codes(r, "high"), ["symlink"])

    def test_a_file_too_large_to_read_is_unreviewed_and_high(self):
        folder = _drop(self.tmp, "probe", SENSE, {"probe.py": "x = 1\n"})
        with mock.patch.object(X, "MAX_CODE_BYTES", 4):
            r = X.review_folder(_clean(SENSE), folder)
        # The manifest is read as text too, so it is unreviewed as well.
        self.assertEqual(_codes(r, "high"), ["unreviewed", "unreviewed"])
        self.assertEqual(sorted(f["path"] for f in r["findings"]
                                if f["severity"] == "high"),
                         ["extension.json", "probe.py"])

    def test_a_binary_file_with_a_code_suffix_is_unreviewed(self):
        folder = _drop(self.tmp, "probe", SENSE)
        with open(os.path.join(folder, "blob.py"), "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01")
        r = X.review_folder(_clean(SENSE), folder)
        self.assertEqual(_codes(r, "high"), ["unreviewed"])

    def test_dynamic_code_is_a_warning_and_literal_eval_is_not(self):
        r = self._review(SENSE, {"probe.py":
                                 "import ast\nv = ast.literal_eval(s)\n"})
        self.assertEqual(_codes(r, "warn"), [])
        r = self._review(dict(SENSE, name="dyn"),
                         {"d.py": "exec(open(p).read())\n"})
        self.assertEqual(_codes(r, "warn"), ["dynamic"])

    def test_non_code_files_are_not_scanned_for_capabilities(self):
        r = self._review(SENSE, {"README.md":
                                 "import subprocess\ncurl http://x\n",
                                 "notes.txt": "os.system('x')\n"})
        self.assertEqual(r["capabilities"]["observed"], {})
        self.assertEqual(_codes(r, "high"), [])

    # -- transports -------------------------------------------------

    def test_an_entry_inside_the_folder_is_fine(self):
        r = self._review(TRANSPORT, {"smoke.py": "x = 1\n"})
        self.assertEqual(_codes(r, "high"), [])

    def test_an_entry_that_steps_out_with_dotdot_is_high(self):
        m = dict(TRANSPORT, entry=["{python}", "../other.py"])
        r = self._review(m, {"smoke.py": "x = 1\n"})
        self.assertEqual(_codes(r, "high"), ["entry.outside"])

    def test_an_extension_dir_token_that_escapes_is_high(self):
        m = dict(TRANSPORT, entry=["{python}", "{extension_dir}/../x.py"])
        r = self._review(m, {"smoke.py": "x = 1\n"})
        self.assertEqual(_codes(r, "high"), ["entry.outside"])

    def test_an_absolute_path_outside_the_folder_is_high(self):
        outside = os.path.join(self.tmp, "outside.py")
        with open(outside, "w") as fh:
            fh.write("x = 1\n")
        m = dict(TRANSPORT, entry=["{python}", outside])
        r = self._review(m, {"smoke.py": "x = 1\n"})
        self.assertEqual(_codes(r, "high"), ["entry.outside"])

    def test_an_interpreter_outside_the_folder_is_only_a_note(self):
        m = dict(TRANSPORT, entry=[sys.executable, "smoke.py"])
        r = self._review(m, {"smoke.py": "x = 1\n"})
        self.assertEqual(_codes(r, "high"), [])
        self.assertEqual(_codes(r, "note"), ["entry.program"])

    def test_a_drop_in_running_shipped_code_is_a_note(self):
        m = dict(TRANSPORT, entry=["{python}", "-m",
                                   "runner.transport_extensions.email"])
        r = self._review(m, {}, shipped=False)
        self.assertEqual(_codes(r, "note"), ["entry.program"])
        r = self._review(dict(m, name="shipped"), {}, shipped=True)
        self.assertEqual(_codes(r), [])

    def test_a_shadow_is_a_warning_never_high(self):
        m = dict(TRANSPORT, name="email")
        r = self._review(m, {"smoke.py": "x = 1\n"}, shadows={"email"})
        self.assertEqual(_codes(r, "warn"), ["shadow"])
        self.assertEqual(X.verdict(r, "enforce"), "loaded")


class VerdictAndModeTest(unittest.TestCase):
    def test_the_default_posture_is_enforce(self):
        self.assertEqual(X.mode_of({}), ("enforce", None))
        self.assertEqual(X.mode_of(None), ("enforce", None))
        self.assertEqual(X.DEFAULT_MODE, "enforce")

    def test_the_three_modes_and_the_booleans(self):
        for raw, want in (("off", "off"), ("advisory", "advisory"),
                          ("enforce", "enforce"), (" Enforce ", "enforce"),
                          (True, "enforce"), (False, "off")):
            self.assertEqual(X.mode_of({"extension_review": raw}),
                             (want, None), raw)

    def test_a_wrong_value_is_a_config_problem_not_a_default(self):
        mode, problem = X.mode_of({"extension_review": "loud"})
        self.assertEqual(mode, "enforce")
        self.assertIn("extension_review", problem)
        self.assertIn("'loud'", problem)
        self.assertIn(problem, R._validate_size_caps(
            {"extension_review": "loud"}) or "")

    def test_verdicts(self):
        high = {"findings": [{"code": "syntax", "severity": "high"}]}
        warn = {"findings": [{"code": "shadow", "severity": "warn"}]}
        self.assertEqual(X.verdict(high, "enforce"), "refused")
        self.assertEqual(X.verdict(warn, "enforce"), "loaded")
        self.assertEqual(X.verdict(high, "advisory"), "loaded")
        self.assertEqual(X.verdict(high, "off"), "off")


class ManifestCapabilitiesTest(unittest.TestCase):
    def test_the_field_is_optional_and_cleaned(self):
        m = E.parse_manifest(dict(SENSE))
        self.assertEqual(m["capabilities"], [])
        m = E.parse_manifest(dict(SENSE, capabilities=["subprocess",
                                                        "network",
                                                        "network"]))
        self.assertEqual(m["capabilities"], ["network", "subprocess"])

    def test_the_vocabulary_is_closed(self):
        for bad in ("network", ["root"], [1], ["network", None]):
            with self.assertRaises(ValueError) as cm:
                E.parse_manifest(dict(SENSE, capabilities=bad))
            self.assertIn("capabilities", str(cm.exception))
        self.assertEqual(E.CAPABILITIES, X.CAPABILITIES)


class ApplyTest(unittest.TestCase):
    """The gate as the loaders see it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-extreview-")
        self.ext = os.path.join(self.tmp, "extensions")
        self.lines = []
        self.events = []
        X.forget()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        X.forget()

    def _log(self, msg, level="INFO"):
        self.lines.append((level, msg))

    def _apply(self, cfg, kind="sense", **kw):
        registry, problems = E.load_extensions(
            self.ext, kinds=(kind,))
        self.assertEqual(problems, [])
        return X.apply(cfg, self.tmp, registry, kind=kind, log=self._log,
                       event_sink=self.events.append, **kw)

    def test_enforce_refuses_in_the_loaders_vocabulary(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "import subprocess\n"})
        registry, problems, report = self._apply({})
        self.assertEqual(registry, {})
        self.assertEqual(len(problems), 1)
        self.assertIn("refused by the extension review", problems[0])
        self.assertIn("capability.undeclared", problems[0])
        self.assertIn('set extension_review to "advisory"', problems[0])
        self.assertEqual(report["extensions"]["probe"]["verdict"],
                         "refused")
        self.assertEqual([e["type"] for e in self.events],
                         ["extension_refused"])
        self.assertEqual(self.events[0]["findings"],
                         ["capability.undeclared"])
        self.assertTrue(any("capability.undeclared" in m
                            for _l, m in self.lines))

    def test_advisory_loads_and_says_so(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "import subprocess\n"})
        registry, problems, report = self._apply(
            {"extension_review": "advisory"})
        self.assertEqual(sorted(registry), ["probe"])
        self.assertEqual(problems, [])
        self.assertEqual(report["extensions"]["probe"]["verdict"], "loaded")
        self.assertEqual(self.events, [])
        self.assertTrue(any("capability.undeclared" in m
                            for _l, m in self.lines))

    def test_off_reads_nothing(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "def (:\n"})
        registry, problems, report = self._apply({"extension_review": "off"})
        self.assertEqual(sorted(registry), ["probe"])
        self.assertEqual(problems, [])
        self.assertEqual(report, {"mode": "off", "extensions": {}})
        self.assertEqual(self.lines, [])
        self.assertFalse(os.path.exists(X.report_path(self.tmp)))

    def test_notes_are_in_the_report_not_the_log(self):
        _drop(self.ext, "probe", dict(SENSE, capabilities=["native"]),
              {"probe.py": "x = 1\n"})
        registry, problems, report = self._apply({})
        self.assertEqual(sorted(registry), ["probe"])
        codes = [f["code"] for f in report["extensions"]["probe"]["findings"]]
        self.assertEqual(codes, ["capability.unused", "signal.unused"])
        self.assertEqual(self.lines, [])

    def test_the_report_is_written_and_merged_per_kind(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "x = 1\n"})
        self._apply({})
        data = X.load_report(self.tmp)
        self.assertEqual(data["mode"], "enforce")
        self.assertEqual(sorted(data["senses"]), ["probe"])
        self.assertTrue(data["reviewed_at"].endswith("Z"))
        # The transport side lands beside it without disturbing it.
        X.apply({}, self.tmp, {}, kind="transport")
        data = X.load_report(self.tmp)
        self.assertEqual(sorted(data["senses"]), ["probe"])
        self.assertEqual(data["transports"], {})
        self.assertEqual(X.last_report(self.tmp, "sense")["extensions"]
                         ["probe"]["verdict"], "loaded")

    def test_an_unchanged_folder_is_not_re_read(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "import subprocess\n"})
        self._apply({"extension_review": "advisory"})
        n = len(self.lines)
        self.assertGreater(n, 0)
        with mock.patch.object(X, "review_folder",
                               side_effect=AssertionError("re-read")):
            self._apply({"extension_review": "advisory"})
        self.assertEqual(len(self.lines), n)   # said once

    def test_a_changed_file_is_reviewed_again(self):
        folder = _drop(self.ext, "probe", SENSE, {"probe.py": "x = 1\n"})
        registry, _p, _r = self._apply({})
        self.assertEqual(sorted(registry), ["probe"])
        with open(os.path.join(folder, "probe.py"), "w") as fh:
            fh.write("import ctypes\n" + "#" * 40 + "\n")
        st = os.stat(os.path.join(folder, "probe.py"))
        os.utime(os.path.join(folder, "probe.py"),
                 ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        registry, problems, _r = self._apply({})
        self.assertEqual(registry, {})
        self.assertIn("capability.undeclared", problems[0])

    def test_a_review_that_blows_up_refuses_rather_than_passes(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "x = 1\n"})
        with mock.patch.object(X, "_cached_review",
                               side_effect=RuntimeError("boom")):
            registry, problems, report = self._apply({})
        self.assertEqual(registry, {})
        self.assertIn("unreviewed", problems[0])

    def test_the_event_sink_may_fail_quietly(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "import subprocess\n"})
        registry, problems = E.load_extensions(self.ext)
        out, probs, _r = X.apply(
            {}, self.tmp, registry, kind="sense",
            event_sink=lambda ev: (_ for _ in ()).throw(OSError("full")))
        self.assertEqual(out, {})
        self.assertEqual(len(probs), 1)


class ShippedExtensionsTest(unittest.TestCase):
    """Every extension this project ships passes its own review."""

    def setUp(self):
        X.forget()

    def test_the_shipped_senses_are_clean_under_enforce(self):
        root = os.path.join(ROOT, "runner", "extensions")
        registry, problems = E.load_extensions(root)
        self.assertEqual(problems, [])
        self.assertGreater(len(registry), 20)
        out, refusals, report = X.apply({}, "", registry, kind="sense",
                                        shipped_dirs=[root])
        self.assertEqual(refusals, [])
        self.assertEqual(sorted(out), sorted(registry))
        for name, entry in report["extensions"].items():
            self.assertEqual(entry["verdict"], "loaded", name)
            self.assertEqual([f for f in entry["findings"]
                              if f["severity"] in ("high", "warn")], [],
                             name)

    def test_the_shipped_senses_declare_exactly_what_they_use(self):
        root = os.path.join(ROOT, "runner", "extensions")
        registry, _problems = E.load_extensions(root)
        for name, m in sorted(registry.items()):
            r = X.review_folder(m, m["dir"], shipped=True)
            self.assertEqual(sorted(r["capabilities"]["observed"]),
                             m["capabilities"], name)

    def test_the_shipped_transports_are_clean_under_enforce(self):
        registry, problems = transports.discover_transport_extensions(
            {}, tempfile.mkdtemp(prefix="hp-test-"))
        self.assertEqual(problems, [])
        self.assertEqual(sorted(registry), ["dtls", "email", "file", "nats"])
        self.assertEqual(registry["dtls"]["capabilities"],
                         ["listen", "network"])
        self.assertEqual(registry["email"]["capabilities"], ["network"])
        self.assertEqual(registry["file"]["capabilities"], [])
        self.assertEqual(registry["nats"]["capabilities"], ["network"])

    def test_no_shipped_source_carries_a_control_character(self):
        for root in (os.path.join(ROOT, "runner", "extensions"),
                     os.path.join(ROOT, "runner", "transport_extensions")):
            for dirpath, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in ("__pycache__",
                                                        "upstream")]
                for f in files:
                    if f.endswith(".py"):
                        with open(os.path.join(dirpath, f),
                                  encoding="utf-8") as fh:
                            self.assertIsNone(
                                X._CONTROL_CHARS.search(fh.read()),
                                os.path.join(dirpath, f))


class TransportDiscoveryGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-extreview-")
        self.ext = os.path.join(self.tmp, "extensions")
        self.lines = []
        self.events = []
        X.forget()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        X.forget()

    def _log(self, msg, level="INFO"):
        self.lines.append((level, msg))

    def test_a_drop_in_whose_entry_escapes_is_refused_and_not_replaced(self):
        _drop(self.ext, "myfile", dict(TRANSPORT, name="file",
                                       entry=["{python}", "../x.py"]),
              {"x.py": "x = 1\n"})
        registry, problems = transports.discover_transport_extensions(
            {"extensions_dir": self.ext}, self.tmp, log=self._log,
            event_sink=self.events.append)
        self.assertNotIn("file", registry)      # no silent substitution
        self.assertIn("email", registry)
        self.assertTrue(any("entry.outside" in p for p in problems), problems)
        self.assertEqual([e["type"] for e in self.events],
                         ["extension_refused"])

    def test_a_clean_drop_in_shadows_out_loud(self):
        mine = _drop(self.ext, "myfile", dict(TRANSPORT, name="file"),
                     {"smoke.py": "x = 1\n"})
        registry, problems = transports.discover_transport_extensions(
            {"extensions_dir": self.ext}, self.tmp, log=self._log,
            event_sink=self.events.append)
        self.assertEqual(registry["file"]["dir"], mine)
        self.assertEqual(problems, [])
        self.assertTrue(any("shadow" in m and "'file'" in m
                            for _l, m in self.lines), self.lines)
        self.assertEqual([e["type"] for e in self.events],
                         ["extension_shadow"])

    def test_advisory_loads_the_escaping_drop_in(self):
        mine = _drop(self.ext, "myfile", dict(TRANSPORT, name="file",
                                              entry=["{python}", "../x.py"]),
                     {"x.py": "x = 1\n"})
        registry, problems = transports.discover_transport_extensions(
            {"extensions_dir": self.ext, "extension_review": "advisory"},
            self.tmp, log=self._log)
        self.assertEqual(registry["file"]["dir"], mine)
        self.assertEqual(problems, [])

    def test_the_supervisor_carries_the_review_problem(self):
        _drop(self.ext, "bad", dict(TRANSPORT, name="bad",
                                    entry=["{python}", "../x.py"]),
              {"x.py": "x = 1\n"})
        sup = transports.TransportSupervisor(
            {"extensions_dir": self.ext, "transports": ["bad"]},
            self.tmp, log=self._log, popen=lambda *a, **k: None,
            event_sink=self.events.append)
        self.assertNotIn("bad", sup.registry)
        self.assertEqual(sup.missing, ["bad"])
        self.assertTrue(any("refused by the extension review" in p
                            for p in sup.problems), sup.problems)


class RunnerGateTest(unittest.TestCase):
    """The sense loader in runner.py and --inspect review."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-extreview-")
        self.ext = os.path.join(self.tmp, "extensions")
        X.forget()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        X.forget()

    def test_a_refused_sense_is_absent_from_the_registry(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "import ctypes\n"})
        _drop(self.ext, "fine", dict(SENSE, name="fine"),
              {"fine.py": 'a = {"signal": "seen_it"}\n'})
        cfg = {"extensions_dir": self.ext}
        with mock.patch.object(R, "log", lambda msg, level="INFO": None):
            self.assertEqual(sorted(R._extension_registry(cfg, self.tmp)),
                             ["fine"])
        events = os.path.join(self.tmp, "security-events.jsonl")
        with open(events, encoding="utf-8") as fh:
            kinds = [json.loads(line)["type"] for line in fh if line.strip()]
        self.assertEqual(kinds, ["extension_refused"])
        self.assertEqual(R._extension_registry(
            dict(cfg, extension_review="advisory"), self.tmp).keys()
            & {"probe", "fine"}, {"probe", "fine"})

    def test_the_startup_report_names_capabilities_and_refusals(self):
        _drop(self.ext, "probe", dict(SENSE, capabilities=["subprocess"]),
              {"probe.py": 'import subprocess\na = {"signal": "seen_it"}\n'})
        _drop(self.ext, "bad", dict(SENSE, name="bad"),
              {"bad.py": "def (:\n"})
        lines = []
        with mock.patch.object(R, "log",
                               lambda msg, level="INFO": lines.append(msg)):
            R._report_extensions({"extensions_dir": self.ext}, self.tmp)
        loaded = [m for m in lines if m.startswith("extension loaded: probe")]
        self.assertEqual(len(loaded), 1)
        self.assertIn("capabilities: subprocess", loaded[0])
        self.assertTrue(any("'bad'" in m and "syntax" in m for m in lines),
                        lines)

    def test_inspect_review_reads_the_folders_now(self):
        _drop(self.ext, "probe", SENSE, {"probe.py": "import ctypes\n"})
        out = R._extension_review_now({"extensions_dir": self.ext}, self.tmp)
        self.assertEqual(out["mode"], "enforce")
        self.assertEqual(out["senses"]["probe"]["verdict"], "refused")
        self.assertEqual(sorted(out["transports"]),
                         ["dtls", "email", "file", "nats"])
        self.assertTrue(any("probe" in p for p in out["problems"]))

    def test_the_inspect_choice_exists(self):
        with open(os.path.join(ROOT, "runner", "runner.py"),
                  encoding="utf-8") as fh:
            parser_src = fh.read()
        self.assertIn('"review", "sources"]', parser_src)


if __name__ == "__main__":
    unittest.main()
