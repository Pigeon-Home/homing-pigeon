"""Project Platinum, cycle 2: the ops family.

Targets from the cycle-1 refreshed table
(`docs/reports/v3.13.21/coverage-gaps.md`), taken top-down:

  logic  ops/extsources.py:status (5) -- the operator's view of
         every extension's recorded state. Its docstring is the
         contract: never raises, and a member with the wrong shape
         is reported as absent, not a traceback (Q44).
  logic  ops/install.py:_import_atomicio (3) -- the frozen
         installer's bundled copy wins when it is there.
  logic  ops/install.py:merge_config_blob (3) -- a config file
         that does not parse, or parses to a non-object, is
         replaced by the blob, not fatal.
  guard  ops/cli.py:_transports_arg (3) -- the --transports
         argparse type: refusals surface as ArgumentTypeError,
         and the empty list is refused on every path.

The state corpus for `status` is written as real SOURCES.json
files under mutated directory shapes; the arms the disk cannot
produce (a `load_states` that raises, a key that is not a
(kind, name) pair) are driven through the module's own seam,
because the defensive code exists for exactly those shapes.

Agent-Stamp: 58316a92-3c4a-41cb-8a16-8c0c5a871e90
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from hypothesis import given, settings, strategies as st

from runner.ops import cli, extsources, install

_JSONISH = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=12)),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(st.text(max_size=8), children, max_size=3)),
    max_leaves=8)


def _write_state(base, kind, name, state):
    folder = os.path.join(extsources.state_root(base), kind, name)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, extsources.STATE_FILE), "w",
              encoding="utf-8") as fh:
        json.dump(state, fh)


class ExtsourcesStatusProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(member=st.dictionaries(
        st.sampled_from(["installed", "entries", "version", "active",
                         "fetch", "disclosure", "declaration_problem",
                         "other"]),
        _JSONISH, max_size=5))
    def test_a_state_of_any_shape_reports_without_raising(self, member):
        base = tempfile.mkdtemp(prefix="hp-plat-status-")
        try:
            state = dict(member)
            state["state_version"] = extsources.STATE_VERSION
            _write_state(base, "sense", "thermometer", state)
            out = extsources.status(base)
            self.assertEqual(out["state_dir"],
                             extsources.state_root(base))
            self.assertEqual(len(out["extensions"]), 1)
            (ext,) = out["extensions"]
            self.assertEqual((ext["kind"], ext["name"]),
                             ("sense", "thermometer"))
            installed = state.get("installed")
            self.assertEqual(
                ext["installed"],
                installed.get("path") if isinstance(installed, dict)
                else None)
            entries = state.get("entries")
            if isinstance(entries, dict):
                self.assertEqual(
                    set(ext["entries"]),
                    {str(k) for k, v in entries.items()
                     if isinstance(v, dict)})
                for rec in ext["entries"].values():
                    self.assertLessEqual(
                        set(rec), {"role", "status", "detail",
                                   "disclosure", "pinned_by", "bytes",
                                   "next_retry"})
            else:
                self.assertEqual(ext["entries"], {})
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_a_broken_state_root_is_an_empty_report(self):
        base = tempfile.mkdtemp(prefix="hp-plat-status-")
        try:
            with open(extsources.state_root(base), "w",
                      encoding="utf-8") as fh:
                fh.write("a file where the state dir belongs")
            with mock.patch.object(
                    extsources, "load_states",
                    side_effect=RuntimeError("state store is gone")):
                out = extsources.status(base)
            self.assertEqual(out["extensions"], [])
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_odd_keys_and_values_are_normalized_not_fatal(self):
        states = {
            ("sense",): {"state_version": 1},
            "a-bare-string-key": {"state_version": 1},
            42: ["not", "a", "dict"],
            ("transport", "wheel"): "not a dict either",
        }
        with mock.patch.object(extsources, "load_states",
                               return_value=states):
            out = extsources.status("/anywhere")
        self.assertEqual(len(out["extensions"]), 4)
        by_name = {e["name"]: e for e in out["extensions"]}
        self.assertEqual(by_name["('sense',)"]["kind"], "?")
        self.assertEqual(by_name["a-bare-string-key"]["kind"], "?")
        self.assertEqual(by_name["42"]["installed"], None)
        self.assertEqual(by_name["wheel"]["entries"], {})


class ImportAtomicioTest(unittest.TestCase):
    def test_the_frozen_bundle_wins_when_it_is_there(self):
        td = tempfile.mkdtemp(prefix="hp-plat-frozen-")
        try:
            bundle = os.path.join(td, "pigeon-guard")
            os.makedirs(bundle)
            src = os.path.join(os.path.dirname(install.__file__), "..",
                               "guard", "atomicio.py")
            shutil.copyfile(os.path.normpath(src),
                            os.path.join(bundle, "atomicio.py"))
            with mock.patch.object(sys, "_MEIPASS", td, create=True):
                mod = install._import_atomicio()
            self.assertTrue(callable(mod.write_json))
            self.assertEqual(os.path.basename(mod.__file__),
                             "atomicio.py")
            self.assertIn("pigeon-guard", mod.__file__)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_a_frozen_root_without_the_file_falls_through(self):
        td = tempfile.mkdtemp(prefix="hp-plat-frozen-")
        try:
            with mock.patch.object(sys, "_MEIPASS", td, create=True):
                mod = install._import_atomicio()
            self.assertTrue(callable(mod.write_json))
        finally:
            shutil.rmtree(td, ignore_errors=True)


class MergeConfigBlobProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(existing=st.sampled_from(
        ["absent", "garbage", "list", "scalar", "dict"]),
        blob=st.dictionaries(st.sampled_from(
            ["shared_secret", "runner_id", "workspace_root",
             "poll_interval_sec", "owner_instructions"]),
            st.text(max_size=10), max_size=3))
    def test_the_blob_lands_whatever_was_there(self, existing, blob):
        td = tempfile.mkdtemp(prefix="hp-plat-blob-")
        try:
            cfg_path = os.path.join(td, "config.json")
            if existing == "garbage":
                with open(cfg_path, "wb") as fh:
                    fh.write(b"{not json at all")
            elif existing == "list":
                with open(cfg_path, "w", encoding="utf-8") as fh:
                    json.dump([1, 2], fh)
            elif existing == "scalar":
                with open(cfg_path, "w", encoding="utf-8") as fh:
                    json.dump("just a string", fh)
            elif existing == "dict":
                with open(cfg_path, "w", encoding="utf-8") as fh:
                    json.dump({"keep": 1, "shared_secret": "old"}, fh)
            written = install.merge_config_blob(
                cfg_path, json.dumps(blob))
            self.assertEqual(written, blob)
            if not blob:
                # An empty blob is a no-op by design (`if not
                # data: return {}`): the file, whatever it held,
                # is left exactly as it was.
                if existing == "absent":
                    self.assertFalse(os.path.exists(cfg_path))
                elif existing == "garbage":
                    with open(cfg_path, "rb") as fh:
                        self.assertEqual(fh.read(),
                                         b"{not json at all")
                elif existing == "dict":
                    with open(cfg_path, encoding="utf-8") as fh:
                        self.assertEqual(
                            json.load(fh),
                            {"keep": 1, "shared_secret": "old"})
                return
            with open(cfg_path, encoding="utf-8") as fh:
                cfg = json.load(fh)
            self.assertIsInstance(cfg, dict)
            for key, value in blob.items():
                self.assertEqual(cfg[key], value)
            if existing == "dict" and "shared_secret" not in blob:
                self.assertEqual(cfg["keep"], 1)
        finally:
            shutil.rmtree(td, ignore_errors=True)


class TransportsArgProperties(unittest.TestCase):
    @settings(deadline=None)
    @given(text=st.one_of(
        st.text(max_size=30),
        st.sampled_from(["", " ", ",", "file", "file,nats",
                         " file , nats ", "file,,nats", "a,b,c"])))
    def test_names_or_an_argparse_refusal(self, text):
        try:
            names = cli._transports_arg(text)
        except argparse.ArgumentTypeError:
            return
        self.assertEqual(
            names, [p.strip() for p in str(text).split(",") if p.strip()])
        self.assertTrue(names)

    def test_an_empty_list_is_refused_with_the_module_gone(self):
        with mock.patch.object(cli, "_transports", None):
            with self.assertRaises(argparse.ArgumentTypeError):
                cli._transports_arg("")

    def test_an_empty_list_is_refused_after_a_lenient_check(self):
        lenient = mock.Mock()
        lenient.enabled_transports.return_value = ["file"]
        with mock.patch.object(cli, "_transports", lenient):
            with self.assertRaises(argparse.ArgumentTypeError):
                cli._transports_arg(" , ")

    def test_a_discovery_refusal_becomes_an_argparse_refusal(self):
        strict = mock.Mock()
        strict.enabled_transports.side_effect = ValueError("no such")
        with mock.patch.object(cli, "_transports", strict):
            with self.assertRaises(argparse.ArgumentTypeError):
                cli._transports_arg("nosuch")


if __name__ == "__main__":
    unittest.main()
