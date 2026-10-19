"""Failed Login Watch: the example sense that tails auth logs.

Pins the Failed Login Watch example
(examples/extensions/failed-login-watch/): the manifest
through the real extension loader, the pure parse_event() and
read_new_events() reader plumbing, and the pure decide()
episode machine -- a burst files once, a success after a
burst files high and closes the episode, and a burst whose
failures age out of the window can file again.

No live logs anywhere: decide() is driven with fixture event
readings, and the reader is driven with a temp file.
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
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import extensions as E  # noqa: E402

EXAMPLE_DIR = os.path.join(
    REPO, "examples", "extensions", "failed-login-watch")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "failed_login_watch_example",
        os.path.join(EXAMPLE_DIR, "failed_login_watch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FL = _load_example_module()

T0 = datetime(2026, 10, 18, 12, 0, 0).timestamp()
SRC = "192.0.2.10"


def _manifest():
    with open(os.path.join(EXAMPLE_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _fail(ts, source=SRC, user="bob"):
    return {"ts": ts, "kind": "fail", "source": source, "user": user}


def _success(ts, source=SRC, user="bob"):
    return {"ts": ts, "kind": "success", "source": source, "user": user}


def _burst(ts0=T0, count=5, source=SRC):
    return [_fail(ts0 + i * 10, source=source) for i in range(count)]


def _readings(events, now=None):
    events = list(events)
    return {"now": events[-1]["ts"] if now is None and events else now,
            "events": events}


class ManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "failed_login_watch")
        self.assertEqual(clean["version"], "0.1.0")
        self.assertEqual(clean["api_version"], 1)
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(
            sorted(s["name"] for s in clean["signals"]),
            ["login_failure_burst", "login_success_after_burst"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(EXAMPLE_DIR,
                            os.path.join(d, "failed-login-watch"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("failed_login_watch", registry)
        self.assertEqual(registry["failed_login_watch"]["version"],
                         "0.1.0")


class ParseEventTest(unittest.TestCase):
    def test_sshd_failed_password_invalid_user(self):
        ev = FL.parse_event(
            "Oct 18 12:00:01 host sshd[11]: Failed password for "
            "invalid user admin from 192.0.2.10 port 51234 ssh2", T0)
        self.assertEqual(ev["kind"], "fail")
        self.assertEqual(ev["source"], "192.0.2.10")
        self.assertEqual(ev["user"], "admin")
        self.assertEqual(ev["ts"], datetime(2026, 10, 18, 12, 0, 1)
                         .timestamp())

    def test_sshd_failed_and_accepted(self):
        ev = FL.parse_event(
            "Oct 18 12:00:01 host sshd[11]: Failed password for bob "
            "from 192.0.2.10 port 51234 ssh2", T0)
        self.assertEqual((ev["kind"], ev["user"]), ("fail", "bob"))
        ev = FL.parse_event(
            "Oct 18 12:05:01 host sshd[11]: Accepted publickey for "
            "bob from 192.0.2.10 port 51235 ssh2", T0)
        self.assertEqual((ev["kind"], ev["source"], ev["user"]),
                         ("success", "192.0.2.10", "bob"))

    def test_pam_failure_is_local_with_user_field(self):
        ev = FL.parse_event(
            "Oct 18 12:00:01 host sshd[11]: pam_unix(sshd:auth): "
            "authentication failure; logname= uid=0 euid=0 tty=ssh "
            "ruser= rhost=192.0.2.10 user=carol", T0)
        self.assertEqual((ev["kind"], ev["source"], ev["user"]),
                         ("fail", "local", "carol"))
        ev = FL.parse_event(
            "Oct 18 12:00:01 host sshd[11]: pam_unix(sshd:auth): "
            "authentication failure; logname= uid=0", T0)
        self.assertEqual((ev["kind"], ev["source"], ev["user"]),
                         ("fail", "local", ""))

    def test_unparseable_lines_answer_none(self):
        for line in ("", "hello world",
                     "Oct 18 12:00:01 host cron[1]: job ran",
                     "Failed password for bob from 192.0.2.10"):
            self.assertIsNone(FL.parse_event(line, T0), line)


class ReaderTest(unittest.TestCase):
    LINE = ("Oct 18 12:00:0%d host sshd[11]: Failed password for "
            "bob from 192.0.2.10 port 51234 ssh2\n")

    def test_tails_incrementally_and_keeps_missing_offsets(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "auth.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.LINE % 1)
                fh.write(self.LINE % 2)
            events, reader = FL.read_new_events([path], {})
            self.assertEqual(len(events), 2)
            self.assertEqual(reader[path]["offset"],
                             os.path.getsize(path))
            # Nothing new: no events, offset unchanged.
            events, reader = FL.read_new_events([path], reader)
            self.assertEqual(events, [])
            # An appended line is the only new event.
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(self.LINE % 3)
            events, reader = FL.read_new_events([path], reader)
            self.assertEqual(len(events), 1)
            # A missing file yields nothing and keeps its offset.
            missing = os.path.join(d, "nope.log")
            kept = {missing: {"inode": 4242, "offset": 99}}
            events, new_reader = FL.read_new_events([missing], kept)
            self.assertEqual(events, [])
            self.assertEqual(new_reader[missing],
                             {"inode": 4242, "offset": 99})

    def test_shrunk_file_restarts_from_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "auth.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.LINE % 1)
                fh.write(self.LINE % 2)
            _events, reader = FL.read_new_events([path], {})
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.LINE % 9)  # truncated / rotated in place
            events, _reader = FL.read_new_events([path], reader)
            self.assertEqual(len(events), 1)


class DecideTest(unittest.TestCase):
    def decide(self, readings, state=None, manifest=None):
        return FL.decide(readings, manifest or _manifest(),
                         state if state is not None else {})

    def test_failure_burst_fires_medium_with_key_details(self):
        alerts, state = self.decide(_readings(_burst()))
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["sensor"], "failed_login_watch")
        self.assertEqual(alert["signal"], "login_failure_burst")
        self.assertEqual(alert["severity"], "medium")
        self.assertEqual(alert["detail"]["source"], SRC)
        self.assertEqual(alert["detail"]["count"], 5)
        self.assertEqual(alert["detail"]["window_sec"], 600)
        self.assertTrue(state["sources"][SRC]["burst_active"])

    def test_success_after_burst_fires_high_and_closes_episode(self):
        events = _burst() + [_success(T0 + 60)]
        alerts, state = self.decide(_readings(events))
        self.assertEqual([a["signal"] for a in alerts],
                         ["login_failure_burst",
                          "login_success_after_burst"])
        alert = alerts[1]
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"]["source"], SRC)
        self.assertEqual(alert["detail"]["user"], "bob")
        self.assertEqual(alert["detail"]["recent_failures"], 5)
        src = state["sources"][SRC]
        self.assertEqual(src["fails"], [])
        self.assertFalse(src["burst_active"])

    def test_success_alone_and_few_failures_are_quiet(self):
        alerts, _state = self.decide(_readings([_success(T0)]))
        self.assertEqual(alerts, [])
        alerts, _state = self.decide(_readings(_burst(count=4)))
        self.assertEqual(alerts, [])

    def test_failures_spread_beyond_the_window_never_burst(self):
        events = [_fail(T0 + i * 300) for i in range(5)]  # 1200s span
        alerts, _state = self.decide(_readings(events))
        self.assertEqual(alerts, [])

    def test_bursts_are_per_source(self):
        events = _burst(count=3) + _burst(count=3, source="198.51.100.7")
        alerts, _state = self.decide(_readings(events))
        self.assertEqual(alerts, [])

    def test_events_are_processed_in_timestamp_order(self):
        events = list(reversed(_burst() + [_success(T0 + 60)]))
        alerts, _state = self.decide(_readings(events))
        self.assertEqual([a["signal"] for a in alerts],
                         ["login_failure_burst",
                          "login_success_after_burst"])

    def test_same_readings_twice_files_nothing_second_time(self):
        readings = _readings(_burst())
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        alerts, _state = self.decide(readings, state=state)
        self.assertEqual(alerts, [])

    def test_moved_reading_refiles_after_the_window_passes(self):
        readings = _readings(_burst())
        alerts, state = self.decide(readings)
        self.assertEqual(len(alerts), 1)
        # Time moves past the window with no new events: the
        # burst flag clears quietly.
        later = T0 + 5000
        alerts, state = self.decide({"now": later, "events": []},
                                    state=state)
        self.assertEqual(alerts, [])
        self.assertFalse(state["sources"][SRC]["burst_active"])
        # A fresh burst at the moved time files again.
        alerts, _state = self.decide(_readings(_burst(ts0=later),
                                               now=later + 40),
                                     state=state)
        self.assertEqual([a["signal"] for a in alerts],
                         ["login_failure_burst"])

    def test_reader_subdict_is_preserved_and_ignored(self):
        state = {"sources": {}, "_reader": {"/var/log/auth.log":
                                             {"inode": 7, "offset": 42}}}
        alerts, new_state = self.decide(_readings(_burst()), state=state)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(new_state["_reader"],
                         {"/var/log/auth.log": {"inode": 7, "offset": 42}})

    def test_unusable_events_are_ignored(self):
        readings = {"now": T0, "events": [
            None, {}, {"ts": "x", "kind": "fail", "source": SRC},
            {"ts": T0, "kind": "maybe", "source": SRC},
            {"ts": T0, "kind": "fail", "source": ""}]}
        alerts, _state = self.decide(readings)
        self.assertEqual(alerts, [])


class MainTest(unittest.TestCase):
    def test_log_file_fixture_files_the_episode(self):
        lines = []
        for i in range(5):
            lines.append(
                f"Oct 18 12:00:0{i} host sshd[11]: Failed password "
                f"for bob from 192.0.2.10 port 51234 ssh2")
        lines.append(
            "Oct 18 12:01:00 host sshd[11]: Accepted password for "
            "bob from 192.0.2.10 port 51235 ssh2")
        with tempfile.TemporaryDirectory() as d:
            log_path = os.path.join(d, "auth.log")
            state_path = os.path.join(d, "state.json")
            with open(log_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = FL.main(["--log-file", log_path,
                              "--state", state_path])
            self.assertEqual(rc, 0)
            printed = [json.loads(ln) for ln in
                       out.getvalue().splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["login_failure_burst",
                              "login_success_after_burst"])
            self.assertEqual(
                FL.main(["--log-file", os.path.join(d, "missing.log"),
                         "--state", state_path]), 2)
            with open(os.path.join(d, "bad.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("not json")
            self.assertEqual(
                FL.main(["--readings", os.path.join(d, "bad.json"),
                         "--state", state_path]), 2)


if __name__ == "__main__":
    unittest.main()
