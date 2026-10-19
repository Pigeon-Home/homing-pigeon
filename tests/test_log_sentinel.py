"""Log Sentinel: the example sense that tails sick logs.

Pins the Log Sentinel example
(examples/extensions/log-sentinel/) the way
test_sky_watcher.py pins Sky Watcher: the manifest through
the real extension loader, the pure classify()/decide() pair
against fixture lines (every built-in group at high severity,
configured patterns at their declared severity, cooldown that
does not refresh, dedupe, and the cap that does not mark
dropped hits fired), the incremental reader plumbing
(read_new_lines: first sight tails, appends are incremental,
rotation restarts, a pass reads at most tail_bytes), and
producer passes over fixture input including the live _reader
path through main().

No live network, no live hardware, and no live system log:
every line is a fixture and every file is a temp file.
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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(REPO, "examples", "extensions",
                           "log-sentinel")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "log_sentinel_example",
        os.path.join(EXAMPLE_DIR, "log_sentinel.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LS = _load_example_module()


def _manifest(**overrides):
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    if overrides:
        manifest["tunables"] = dict(manifest["tunables"], **overrides)
    return manifest


def _readings(lines, now=1000.0):
    return {"now": now, "lines": lines}


OOM_LINE = "kernel: Out of memory: Killed process 482 (python3)"
PANIC_LINE = "kernel: Kernel panic - not syncing: VFS: boom"
BUG_LINE = "kernel: BUG: unable to handle page fault at ffff"
SEGFAULT_LINE = "app[91]: segfault at 0 ip 00007f sp 00007f error 14"
FS_LINE = "kernel: EXT4-fs error (device sda1): ext4_lookup: deleted"
BENIGN_LINE = "cron[1]: (root) CMD run-parts /etc/cron.hourly"


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "log_sentinel")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["kernel_distress", "log_pattern_hit"])
        # The pattern signal's description must say where its
        # severity comes from.
        by_name = {s["name"]: s["description"]
                   for s in clean["signals"]}
        self.assertIn("pattern entry",
                      by_name["log_pattern_hit"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR,
                            os.path.join(d, "log-sentinel"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("log_sentinel", registry)
        self.assertEqual(registry["log_sentinel"]["version"],
                         "0.1.0")

    def test_tunables_carry_the_cost_knobs(self):
        tunables = _manifest()["tunables"]
        for key in ("log_paths", "tail_bytes", "cooldown_sec",
                    "max_alerts_per_pass", "groups", "patterns",
                    "poll_interval_sec"):
            self.assertIn(key, tunables)
        self.assertEqual(tunables["poll_interval_sec"], 60)
        self.assertEqual(sorted(tunables["groups"]),
                         ["bug", "fs", "oom", "panic", "segfault"])


class ClassifyTest(unittest.TestCase):
    def test_each_builtin_group(self):
        cases = [
            ("oom", OOM_LINE),
            ("oom", "kernel: oom-kill:constraint=CONSTRAINT_NONE"),
            ("panic", PANIC_LINE),
            ("bug", BUG_LINE),
            ("bug", "kernel: kernel BUG at fs/namei.c:123!"),
            ("segfault", SEGFAULT_LINE),
            ("segfault", "app: segfault error 6 in libc.so"),
            ("fs", FS_LINE),
            ("fs", "kernel: Buffer I/O error on dev sda1"),
            ("fs", "kernel: blk_update_request: I/O error, dev sda"),
        ]
        for group, line in cases:
            with self.subTest(group=group, line=line):
                events = LS.classify([line], _manifest())
                self.assertEqual(len(events), 1)
                event = events[0]
                self.assertEqual(event["group"], group)
                self.assertEqual(event["severity"], "high")
                self.assertEqual(event["subject"], group)
                self.assertEqual(event["line"], line)

    def test_benign_lines_classify_to_nothing(self):
        self.assertEqual(LS.classify([BENIGN_LINE, "", "ok"],
                                     _manifest()), [])

    def test_disabled_group_never_classifies(self):
        manifest = _manifest(groups=["oom", "panic"])
        self.assertEqual(LS.classify([SEGFAULT_LINE], manifest), [])
        self.assertEqual(len(LS.classify([OOM_LINE], manifest)), 1)

    def test_pattern_subject_is_the_pattern_name(self):
        manifest = _manifest(patterns=[
            {"name": "auth_fail", "regex": "authentication failure"}])
        events = LS.classify(["sshd: authentication failure"],
                             manifest)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["pattern"], "auth_fail")
        self.assertEqual(events[0]["subject"], "auth_fail")
        self.assertEqual(events[0]["severity"], "medium")

    def test_bad_pattern_regex_is_skipped_not_raised(self):
        manifest = _manifest(patterns=[
            {"name": "broken", "regex": "([unclosed"},
            {"name": "fine", "regex": "boom"}])
        events = LS.classify(["boom happened"], manifest)
        self.assertEqual([e["pattern"] for e in events], ["fine"])


class DecideTest(unittest.TestCase):
    def test_each_builtin_fires_kernel_distress_high(self):
        cases = [("oom", OOM_LINE), ("panic", PANIC_LINE),
                 ("bug", BUG_LINE), ("segfault", SEGFAULT_LINE),
                 ("fs", FS_LINE)]
        for group, line in cases:
            with self.subTest(group=group):
                alerts, _s = LS.decide(_readings([line]),
                                       _manifest(), {})
                self.assertEqual(len(alerts), 1)
                alert = alerts[0]
                self.assertEqual(alert["sensor"], "log_sentinel")
                self.assertEqual(alert["signal"], "kernel_distress")
                self.assertEqual(alert["severity"], "high")
                self.assertEqual(alert["detail"],
                                 {"group": group, "line": line})
                self.assertIn(group, alert["title"])
                self.assertIn(line[:120], alert["title"])

    def test_quiet_case_files_nothing(self):
        alerts, _s = LS.decide(_readings([BENIGN_LINE]),
                               _manifest(), {})
        self.assertEqual(alerts, [])

    def test_pattern_hit_severity_comes_from_the_entry(self):
        manifest = _manifest(patterns=[
            {"name": "slow_io", "regex": "blocked for more than",
             "severity": "high"},
            {"name": "auth_fail", "regex": "authentication failure"}])
        lines = ["task kworker blocked for more than 120 seconds",
                 "sshd: authentication failure for user"]
        alerts, _s = LS.decide(_readings(lines), manifest, {})
        self.assertEqual(len(alerts), 2)
        by_signal = {a["detail"]["pattern"]: a for a in alerts}
        for a in alerts:
            self.assertEqual(a["signal"], "log_pattern_hit")
        self.assertEqual(by_signal["slow_io"]["severity"], "high")
        self.assertEqual(by_signal["slow_io"]["detail"],
                         {"pattern": "slow_io", "line": lines[0]})
        self.assertEqual(by_signal["auth_fail"]["severity"],
                         "medium")

    def test_dedupe_within_a_pass(self):
        alerts, _s = LS.decide(
            _readings([OOM_LINE, "other: Killed process 9 (x)",
                       PANIC_LINE]), _manifest(), {})
        self.assertEqual([a["detail"].get("group") for a in alerts],
                         ["oom", "panic"])

    def test_same_readings_twice_files_nothing_second_time(self):
        alerts, state = LS.decide(_readings([OOM_LINE]),
                                  _manifest(), {})
        self.assertEqual(len(alerts), 1)
        alerts, _s = LS.decide(_readings([OOM_LINE]),
                               _manifest(), state)
        self.assertEqual(alerts, [])

    def test_cooldown_hit_does_not_refresh_the_timestamp(self):
        manifest = _manifest()  # cooldown_sec 3600
        _a, state = LS.decide(_readings([OOM_LINE], now=1000.0),
                              manifest, {})
        alerts, state = LS.decide(_readings([OOM_LINE], now=2800.0),
                                  manifest, state)
        self.assertEqual(alerts, [])  # inside cooldown, suppressed
        # 3601 after the ORIGINAL firing: files again. Had the
        # suppressed hit refreshed the timestamp, it would not.
        alerts, _s = LS.decide(_readings([OOM_LINE], now=4601.0),
                               manifest, state)
        self.assertEqual(len(alerts), 1)

    def test_moved_reading_refiles_after_cooldown(self):
        manifest = _manifest()
        _a, state = LS.decide(_readings([OOM_LINE], now=1000.0),
                              manifest, {})
        # A different subject is not held by the oom cooldown:
        alerts, state = LS.decide(_readings([PANIC_LINE], now=1001.0),
                                  manifest, state)
        self.assertEqual(len(alerts), 1)
        # And the first subject files fresh once cooldown lapses.
        alerts, _s = LS.decide(_readings([OOM_LINE], now=5000.0),
                               manifest, state)
        self.assertEqual(len(alerts), 1)

    def test_cap_drops_without_marking_fired(self):
        manifest = _manifest(max_alerts_per_pass=2)
        lines = [OOM_LINE, PANIC_LINE, BUG_LINE]
        alerts, state = LS.decide(_readings(lines, now=1000.0),
                                  manifest, {})
        self.assertEqual(len(alerts), 2)
        self.assertNotIn("kernel_distress:bug",
                         state["last_fired"])
        # Next pass: the capped group can file; the filed two
        # are inside their cooldown.
        alerts, _s = LS.decide(_readings(lines, now=1001.0),
                               manifest, state)
        self.assertEqual([a["detail"]["group"] for a in alerts],
                         ["bug"])

    def test_title_line_is_trimmed_to_120_chars(self):
        line = "kernel: Kernel panic - not syncing: " + "x" * 300
        alerts, _s = LS.decide(_readings([line]), _manifest(), {})
        self.assertNotIn("x" * 121, alerts[0]["title"])
        self.assertEqual(alerts[0]["detail"]["line"], line)

    def test_reader_state_is_preserved_opaquely_and_ignored(self):
        reader = {"/var/log/kern.log": {"inode": 7, "offset": 42}}
        state = {"last_fired": {}, "_reader": reader}
        alerts, new_state = LS.decide(_readings([OOM_LINE]),
                                      _manifest(), state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(new_state["_reader"], reader)


class ReaderTest(unittest.TestCase):
    def _write(self, path, text):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_missing_file_is_no_lines_no_state(self):
        lines, reader = LS.read_new_lines(
            ["/nonexistent/kern.log"], {}, 65536)
        self.assertEqual(lines, [])
        self.assertEqual(reader, {})

    def test_first_sight_reads_the_whole_small_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kern.log")
            self._write(path, "one\ntwo\n")
            lines, reader = LS.read_new_lines([path], {}, 65536)
        self.assertEqual(lines, ["one", "two"])
        self.assertEqual(reader[path]["offset"], 8)

    def test_append_reads_only_the_new_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kern.log")
            self._write(path, "one\n")
            _lines, reader = LS.read_new_lines([path], {}, 65536)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("two\n")
            lines, reader = LS.read_new_lines([path], reader, 65536)
            self.assertEqual(lines, ["two"])
            lines, _r = LS.read_new_lines([path], reader, 65536)
            self.assertEqual(lines, [])

    def test_first_sight_of_a_huge_log_starts_at_the_tail(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kern.log")
            self._write(path, "a" * 100 + "\n" + "b" * 100 + "\n")
            lines, reader = LS.read_new_lines([path], {}, 50)
        # Only bytes from (size - 50) on are read; the offset
        # lands at the end of the file either way.
        self.assertEqual(reader[path]["offset"], 202)
        self.assertTrue(all("a" not in ln for ln in lines))

    def test_a_pass_never_reads_more_than_tail_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kern.log")
            self._write(path, "seed\n")
            _l, reader = LS.read_new_lines([path], {}, 10)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("x" * 25)
            first, reader = LS.read_new_lines([path], reader, 10)
            self.assertEqual(sum(len(ln) for ln in first), 10)
            self.assertEqual(reader[path]["offset"], 5 + 10)
            second, reader = LS.read_new_lines([path], reader, 10)
            self.assertEqual(sum(len(ln) for ln in second), 10)
            self.assertEqual(reader[path]["offset"], 5 + 20)

    def test_shrink_restarts_from_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kern.log")
            self._write(path, "a much longer first life\n")
            _l, reader = LS.read_new_lines([path], {}, 65536)
            self._write(path, "new\n")
            lines, _r = LS.read_new_lines([path], reader, 65536)
        self.assertEqual(lines, ["new"])

    def test_inode_change_restarts_from_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kern.log")
            self._write(path, "first inode's content here\n")
            _l, reader = LS.read_new_lines([path], {}, 65536)
            os.unlink(path)
            self._write(path, "second\n")
            lines, _r = LS.read_new_lines([path], reader, 65536)
        self.assertEqual(lines, ["second"])


class ProducerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_path = os.path.join(self._tmp.name, "state.json")

    def _file(self, name, payload):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            if isinstance(payload, str):
                fh.write(payload)
            else:
                json.dump(payload, fh)
        return path

    def test_readings_fixture_prints_and_cools_down(self):
        path = self._file("readings.json", _readings([OOM_LINE]))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = LS.main(["--readings", path,
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        printed = [json.loads(ln) for ln in
                   out.getvalue().splitlines() if ln.strip()]
        self.assertEqual([p["signal"] for p in printed],
                         ["kernel_distress"])
        # Second identical pass: the saved cooldown holds.
        out = io.StringIO()
        with redirect_stdout(out):
            rc = LS.main(["--readings", path,
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "")

    def test_log_file_fixture_reads_the_whole_log(self):
        path = self._file("fixture.log",
                          BENIGN_LINE + "\n" + PANIC_LINE + "\n")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = LS.main(["--log-file", path,
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        printed = [json.loads(ln) for ln in
                   out.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(printed), 1)
        self.assertEqual(printed[0]["detail"]["group"], "panic")
        with open(self.state_path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertNotIn("_reader", saved)

    def test_unreadable_inputs_are_exit_2(self):
        missing = os.path.join(self._tmp.name, "nope.json")
        self.assertEqual(LS.main(["--readings", missing,
                                  "--state", self.state_path]), 2)
        self.assertEqual(LS.main(["--log-file", missing,
                                  "--state", self.state_path]), 2)
        self.assertEqual(LS.main(["--manifest", missing,
                                  "--state", self.state_path]), 2)

    def test_live_pass_uses_and_advances_reader_offsets(self):
        log = os.path.join(self._tmp.name, "kern.log")
        with open(log, "w", encoding="utf-8") as fh:
            fh.write(OOM_LINE + "\n")
        # cooldown_sec 0: if the second pass re-read the first
        # line it WOULD file again -- offsets are what stop it.
        manifest = _manifest(log_paths=[log], cooldown_sec=0)
        mpath = self._file("manifest.json", manifest)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(LS.main(["--manifest", mpath,
                                      "--state", self.state_path]), 0)
        with open(self.state_path, encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertIn(log, saved["_reader"])
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(LS.main(["--manifest", mpath,
                                      "--state", self.state_path]), 0)
        self.assertEqual(out.getvalue(), "")
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(PANIC_LINE + "\n")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(LS.main(["--manifest", mpath,
                                      "--state", self.state_path]), 0)
        printed = [json.loads(ln) for ln in
                   out.getvalue().splitlines() if ln.strip()]
        self.assertEqual([p["detail"]["group"] for p in printed],
                         ["panic"])


if __name__ == "__main__":
    unittest.main()
