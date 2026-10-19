"""The fifteen career-and-watchers examples: catalog-level pins.

Per-extension behavior lives in tests/test_<name>.py (decide()
fixtures, state discipline, and the end-to-ends). This module
pins the slate AS a slate -- the thing a reader of
docs/extensions.md is promised:

- every one of the fifteen folders loads through the real
  extension loader under its declared sensor name,
- the declared signal names match this catalog table exactly
  (a signal renamed in a manifest without updating the catalog
  fails here, and vice versa),
- every producer exposes the uniform contract (read_live,
  decide, main) and imports nothing outside the standard
  library plus the runner's own producer helpers,
- every manifest declares the poll_interval_sec cost knob,
- every README carries a "## Light mode" section (Andrew's
  rule: an example either tunes down for a Pi Light install
  through knobs its code implements, or documents plainly
  why it cannot).

No live network, no live hardware: manifests, sources, and
READMEs only.
"""
import ast
import importlib.util
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLES_DIR = os.path.join(REPO, "examples", "extensions")

# folder, producer file, sensor name, declared signals in
# manifest order. This table is the catalog; docs/extensions.md
# tells the same story in prose.
CATALOG = [
    ("crash-watch", "crash_watch.py", "crash_watch",
     ["crash_dumped", "crash_repeated"]),
    ("release-drop", "release_drop.py", "release_drop",
     ["artifact_arrived", "artifact_changed"]),
    ("cert-sentinel", "cert_sentinel.py", "cert_sentinel",
     ["cert_expiring", "cert_critical", "cert_changed"]),
    ("wire-arrivals", "wire_arrivals.py", "wire_arrivals",
     ["new_neighbor", "mac_moved"]),
    ("latency-post", "latency_post.py", "latency_post",
     ["target_down", "latency_spike"]),
    ("port-watch", "port_watch.py", "port_watch",
     ["exposed_listener", "new_listener"]),
    ("failed-login-watch", "failed_login_watch.py", "failed_login_watch",
     ["login_failure_burst", "login_success_after_burst"]),
    ("tripwire", "tripwire.py", "tripwire",
     ["file_appeared", "file_vanished", "file_changed"]),
    ("log-sentinel", "log_sentinel.py", "log_sentinel",
     ["kernel_distress", "log_pattern_hit"]),
    ("service-watch", "service_watch.py", "service_watch",
     ["service_down", "service_recovered", "service_flapping"]),
    ("backup-freshness", "backup_freshness.py", "backup_freshness",
     ["backup_arrived", "backup_stale", "backup_critical"]),
    ("usb-arrivals", "usb_arrivals.py", "usb_arrivals",
     ["device_arrived", "storage_arrived"]),
    ("airwaves", "airwaves.py", "airwaves",
     ["new_access_point", "evil_twin_suspect", "access_point_gone",
      "link_degraded"]),
    ("resource-sentinel", "resource_sentinel.py", "resource_sentinel",
     ["cpu_saturation_sustained", "disk_fill_velocity",
      "process_storm", "memory_exhaustion_trend"]),
    ("job-watcher", "job_watcher.py", "job_watcher",
     ["job_failing_repeatedly", "job_flaky",
      "job_duration_anomaly", "failure_cluster"]),
]


def _manifest(folder):
    with open(os.path.join(EXAMPLES_DIR, folder, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _load_producer(folder, filename):
    spec = importlib.util.spec_from_file_location(
        f"catalog_{folder.replace('-', '_')}",
        os.path.join(EXAMPLES_DIR, folder, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CatalogManifestTest(unittest.TestCase):
    def test_all_fifteen_load_through_the_real_loader(self):
        registry, problems = E.load_extensions(EXAMPLES_DIR)
        for folder, _fname, sensor, _signals in CATALOG:
            with self.subTest(sensor=sensor):
                self.assertIn(sensor, registry)
                self.assertEqual(registry[sensor]["dir"],
                                 os.path.join(EXAMPLES_DIR, folder))
        for line in problems:
            for folder, _f, _s, _sig in CATALOG:
                self.assertNotIn(folder, line)

    def test_declared_signals_match_the_catalog(self):
        for folder, _fname, sensor, signals in CATALOG:
            with self.subTest(sensor=sensor):
                manifest = E.parse_manifest(_manifest(folder))
                self.assertEqual(manifest["name"], sensor)
                self.assertEqual(manifest["kind"], "sense")
                self.assertEqual(manifest["api_version"], 1)
                self.assertIsNone(E.api_refusal(manifest))
                self.assertEqual(
                    [s["name"] for s in manifest["signals"]], signals)

    def test_every_manifest_declares_its_cost_knob(self):
        for folder, _fname, sensor, _signals in CATALOG:
            with self.subTest(sensor=sensor):
                tunables = _manifest(folder).get("tunables") or {}
                self.assertIn("poll_interval_sec", tunables)
                self.assertIsInstance(tunables["poll_interval_sec"],
                                      (int, float))


# The one documented exception to the read_live entry point:
# failed-login-watch is a log tailer whose offsets live in the
# producer state, so its reading step takes the reader state --
# read_new_events(paths, reader_state) -- instead of a bare
# read_live(manifest). decide() and main() are uniform.
READER_PLUMBING = {"failed-login-watch": ("read_new_events",
                                          "parse_event")}


class CatalogProducerTest(unittest.TestCase):
    def test_producers_expose_the_uniform_contract(self):
        for folder, fname, sensor, _signals in CATALOG:
            with self.subTest(sensor=sensor):
                mod = _load_producer(folder, fname)
                for entry in ("decide", "main"):
                    self.assertTrue(callable(getattr(mod, entry, None)),
                                    f"{folder}: missing {entry}")
                if folder in READER_PLUMBING:
                    for entry in READER_PLUMBING[folder]:
                        self.assertTrue(
                            callable(getattr(mod, entry, None)),
                            f"{folder}: missing {entry}")
                else:
                    self.assertTrue(
                        callable(getattr(mod, "read_live", None)),
                        f"{folder}: missing read_live")

    def test_producers_import_stdlib_only(self):
        stdlib = getattr(sys, "stdlib_module_names", None)
        self.assertIsNotNone(stdlib)
        for folder, fname, sensor, _signals in CATALOG:
            with self.subTest(sensor=sensor):
                path = os.path.join(EXAMPLES_DIR, folder, fname)
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=path)
                roots = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        roots.update(a.name.split(".")[0]
                                     for a in node.names)
                    elif isinstance(node, ast.ImportFrom):
                        if node.level == 0 and node.module:
                            roots.add(node.module.split(".")[0])
                # "runner" is the one sanctioned non-stdlib
                # import: the producer helpers in
                # runner/extensions.py, imported lazily by the
                # delivery path.
                outsiders = roots - set(stdlib) - {"runner"}
                self.assertEqual(outsiders, set(),
                                 f"{folder} imports {sorted(outsiders)}")


class CatalogReadmeTest(unittest.TestCase):
    def test_every_readme_documents_light_mode(self):
        for folder, _fname, sensor, _signals in CATALOG:
            with self.subTest(sensor=sensor):
                path = os.path.join(EXAMPLES_DIR, folder, "README.md")
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                self.assertIn("## Light mode", text,
                              f"{folder}: README has no Light mode "
                              f"section (Andrew's rule: tune down "
                              f"through implemented knobs, or say "
                              f"plainly why it cannot)")


if __name__ == "__main__":
    unittest.main()
