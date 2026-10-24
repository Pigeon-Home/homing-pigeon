"""AIDE Feed: the example sense that reads AIDE check reports.

Pins the AIDE Feed example (extensions/aide-feed/):
the manifest through the real extension loader, the pure
parse_report() over the report sections, the batch reader
read_report_file() -- a report is new exactly when its
(inode, size, mtime) fingerprint differs -- and the pure
decide() discipline: one alert per entry class per new
report, a no-differences report quiet, and the same report
twice quiet via the fingerprint.

The report fixture is a trimmed copy of a real captured
AIDE check. No live AIDE, no root, no network.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(
    REPO, "extensions", "aide-feed")
FIXTURES = os.path.join(EXAMPLE_DIR, "fixtures")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "aide_feed_example",
        os.path.join(EXAMPLE_DIR, "aide_feed.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AF = _load_example_module()

REPORT = """Start timestamp: 2026-10-19 03:48:03 +0000 (AIDE 0.18.6)
AIDE found differences between database and filesystem!!

Summary:
  Total number of entries:\t2489
  Added entries:\t\t2
  Removed entries:\t\t1
  Changed entries:\t\t1

---------------------------------------------------
Added entries:
---------------------------------------------------

f+++++++++++++++++: /etc/probe-aide.txt
d+++++++++++++++++: /etc/newdir

---------------------------------------------------
Removed entries:
---------------------------------------------------

l+++++++++++++++++: /etc/old-link

---------------------------------------------------
Changed entries:
---------------------------------------------------

f   .       H     : /etc/adduser.conf

---------------------------------------------------
Detailed information about changes:
---------------------------------------------------

File: /etc/adduser.conf
 SHA256    : abc | def

End timestamp: 2026-10-19 03:48:05 +0000 (run time: 0m 2s)
"""


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _fixture_text(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def _readings(report, fingerprint="fp-1"):
    return {"now": 1792375201.0, "report": report,
            "fingerprint": fingerprint}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "aide_feed")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            [s["name"] for s in clean["signals"]],
            ["aide_changed", "aide_removed", "aide_added"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        self.assertIn("report_paths", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR, os.path.join(d, "aide-feed"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("aide_feed", registry)


class ParseReportTest(unittest.TestCase):
    def test_sections_counts_and_prefix_letters(self):
        report = AF.parse_report(REPORT)
        self.assertEqual(report["added"],
                         ["/etc/probe-aide.txt", "/etc/newdir"])
        self.assertEqual(report["removed"], ["/etc/old-link"])
        self.assertEqual(report["changed"], ["/etc/adduser.conf"])
        self.assertTrue(report["differences"])

    def test_detailed_section_entries_are_not_collected(self):
        report = AF.parse_report(REPORT)
        all_paths = (report["added"] + report["removed"]
                     + report["changed"])
        # "File: /etc/adduser.conf" in Detailed information is
        # not an entry line, and appears only once, as changed.
        self.assertEqual(all_paths.count("/etc/adduser.conf"), 1)

    def test_real_trimmed_fixture(self):
        report = AF.parse_report(_fixture_text("aide-check.txt"))
        self.assertEqual(report["added"], ["/etc/probe-aide.txt"])
        self.assertEqual(report["removed"], [])
        self.assertEqual(report["changed"], ["/etc/adduser.conf"])
        self.assertTrue(report["differences"])

    def test_no_differences_report(self):
        report = AF.parse_report(_fixture_text("aide-no-differences.txt"))
        self.assertEqual(report["added"], [])
        self.assertEqual(report["removed"], [])
        self.assertEqual(report["changed"], [])
        self.assertFalse(report["differences"])

    def test_unusable_input_answers_the_empty_report(self):
        empty = {"added": [], "removed": [], "changed": [],
                 "differences": False}
        self.assertEqual(AF.parse_report(None), empty)
        self.assertEqual(AF.parse_report(""), empty)
        self.assertEqual(AF.parse_report("random text\n"), empty)


class ReaderTest(unittest.TestCase):
    def test_new_report_reads_once_then_is_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "aide.log")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(REPORT)
            text, reader = AF.read_report_file([path], {})
            self.assertEqual(text, REPORT)
            fp = reader[path]
            self.assertEqual(fp["size"], len(REPORT))
            self.assertIn("inode", fp)
            self.assertIn("mtime", fp)
            # Same file, same fingerprint: no new report.
            text, reader2 = AF.read_report_file([path], reader)
            self.assertIsNone(text)
            self.assertEqual(reader2, reader)
            # A changed report (size differs) is new again.
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write("\n")
            text, _reader = AF.read_report_file([path], reader)
            self.assertIsNotNone(text)

    def test_missing_file_yields_nothing_and_keeps_fingerprint(self):
        kept = {"/nope/aide.log": {"inode": 7, "size": 10, "mtime": 1.5}}
        text, reader = AF.read_report_file(["/nope/aide.log"], kept)
        self.assertIsNone(text)
        self.assertEqual(reader["/nope/aide.log"], kept["/nope/aide.log"])
        text, reader = AF.read_report_file([], {})
        self.assertIsNone(text)
        self.assertEqual(reader, {})


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None):
        return AF.decide(readings, _manifest(),
                         state if state is not None else {})

    def test_one_alert_per_class_in_manifest_order(self):
        alerts, state = self.decide(_readings(AF.parse_report(REPORT)))
        self.assertEqual([a["signal"] for a in alerts],
                         ["aide_changed", "aide_removed", "aide_added"])
        self.assertEqual([a["severity"] for a in alerts],
                         ["medium", "medium", "info"])
        changed = alerts[0]
        self.assertEqual(changed["sensor"], "aide_feed")
        self.assertEqual(changed["detail"]["count"], 1)
        self.assertEqual(changed["detail"]["paths"],
                         ["/etc/adduser.conf"])
        self.assertEqual(changed["detail"]["fingerprint"], "fp-1")
        self.assertEqual(changed["detail"]["report_fingerprint"], "fp-1")
        self.assertEqual(alerts[2]["detail"]["count"], 2)
        self.assertEqual(alerts[2]["detail"]["paths"],
                         ["/etc/probe-aide.txt", "/etc/newdir"])
        self.assertEqual(state["last_fingerprint"], "fp-1")

    def test_detail_paths_are_capped_at_twenty(self):
        report = {"added": [f"/etc/f{i:02d}" for i in range(25)],
                  "removed": [], "changed": [], "differences": True}
        alerts, _s = self.decide(_readings(report))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["detail"]["count"], 25)
        self.assertEqual(len(alerts[0]["detail"]["paths"]), 20)
        self.assertEqual(alerts[0]["detail"]["paths"][0], "/etc/f00")

    def test_no_new_report_and_zero_differences_are_quiet(self):
        alerts, _s = self.decide({"now": 1.0, "report": None})
        self.assertEqual(alerts, [])
        alerts, _s = self.decide({"now": 1.0})
        self.assertEqual(alerts, [])
        report = AF.parse_report(_fixture_text("aide-no-differences.txt"))
        alerts, _s = self.decide(_readings(report))
        self.assertEqual(alerts, [])

    def test_same_report_twice_is_quiet_via_fingerprint(self):
        readings = _readings(AF.parse_report(REPORT))
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 3)
        alerts, _s = self.decide(readings, state=state)
        self.assertEqual(alerts, [])
        # A different fingerprint is a different report: files.
        alerts, _s = self.decide(_readings(AF.parse_report(REPORT),
                                           fingerprint="fp-2"),
                                 state=state)
        self.assertEqual(len(alerts), 3)

    def test_reader_subdict_is_preserved_and_ignored(self):
        state = {"last_fingerprint": None,
                 "_reader": {"/var/log/aide/aide.log":
                             {"inode": 7, "size": 3, "mtime": 1.0}}}
        alerts, new_state = self.decide(
            _readings(AF.parse_report(REPORT)), state=state)
        self.assertEqual(len(alerts), 3)
        self.assertEqual(new_state["_reader"], state["_reader"])

    def test_unusable_report_entries_are_ignored(self):
        report = {"added": ["/etc/ok", None, 42, ""],
                  "removed": "not-a-list", "changed": []}
        alerts, _s = self.decide(_readings(report))
        self.assertEqual([a["signal"] for a in alerts], ["aide_added"])
        self.assertEqual(alerts[0]["detail"]["paths"], ["/etc/ok"])


class MainTest(unittest.TestCase):
    def test_report_file_fixture_end_to_end_and_repeat_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            state_path = os.path.join(d, "state.json")
            fixture = os.path.join(FIXTURES, "aide-check.txt")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = AF.main(["--report-file", fixture,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["aide_changed", "aide_added"])
            self.assertEqual(
                AF.main(["--report-file", os.path.join(d, "missing.txt"),
                         "--state", state_path]), 2)

    def test_live_pass_files_once_then_quiet(self):
        with tempfile.TemporaryDirectory() as d:
            report_path = os.path.join(d, "aide.log")
            with open(report_path, "w", encoding="utf-8") as fh:
                fh.write(REPORT)
            manifest_path = os.path.join(d, "extension.json")
            manifest = _manifest()
            manifest["tunables"]["report_paths"] = [report_path]
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            state_path = os.path.join(d, "state.json")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = AF.main(["--manifest", manifest_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual(len(printed), 3)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = AF.main(["--manifest", manifest_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
