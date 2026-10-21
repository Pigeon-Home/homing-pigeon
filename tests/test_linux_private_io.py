"""Linux private writes: mode 0600, O_NOFOLLOW, and the 5000-line cap.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not written
through.
"""
import json
import os
import random
import tempfile
import unittest
from unittest import mock

from runner.runner import _append_security_event
from runner.senses import MAX_STORED, store_alert


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _lines(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class PrivateWriteTest(unittest.TestCase):
    def test_the_cap_rewrite_uses_nofollow_and_keeps_the_tail(self):
        self.assertEqual(MAX_STORED, 5000)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "security-events.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for i in range(5000):
                    fh.write(json.dumps({"n": i}) + "\n")
            seen = []
            replaced = []
            real_open = os.open
            real_replace = os.replace

            def spy(spied, flags, *args, **kwargs):
                if os.path.basename(str(spied)).startswith(
                        "security-events.jsonl"):
                    seen.append((str(spied), flags))
                return real_open(spied, flags, *args, **kwargs)

            def replace_spy(src, dst, *args, **kwargs):
                replaced.append((str(src), str(dst)))
                return real_replace(src, dst, *args, **kwargs)

            with mock.patch("os.open", side_effect=spy), \
                    mock.patch("os.replace", side_effect=replace_spy):
                _append_security_event(d, {"n": 5000, "msg": "a\nb"})
            rows = [json.loads(line) for line in _lines(path)]
            self.assertEqual(len(rows), 5000)
            self.assertEqual(rows[0]["n"], 1)
            self.assertEqual(rows[-1]["n"], 5000)
            self.assertEqual(rows[-1]["msg"], "a\nb")
            self.assertNotIn("\n", _lines(path)[-1])
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            nofollow = os.O_NOFOLLOW
            self.assertTrue(seen)
            self.assertTrue(all(flags & nofollow for _, flags in seen))
            self.assertTrue(any(
                p == path and flags & os.O_APPEND for p, flags in seen))
            # The trim replaces the file instead of truncating it in
            # place: the live path is never opened with O_TRUNC. The
            # kept tail goes to a tmp sibling (O_EXCL, no O_APPEND)
            # and is renamed over the original, leaving no tmp behind.
            self.assertFalse(any(
                p == path and flags & os.O_TRUNC for p, flags in seen))
            tmp_opens = [(p, f) for p, f in seen if p != path]
            self.assertTrue(tmp_opens)
            self.assertTrue(all(f & os.O_EXCL for _, f in tmp_opens))
            self.assertTrue(all(not (f & os.O_APPEND) for _, f in tmp_opens))
            self.assertEqual(len(replaced), 1)
            self.assertTrue(replaced[0][0].startswith(path + ".tmp."))
            self.assertEqual(replaced[0][1], path)
            self.assertEqual(os.listdir(d), ["security-events.jsonl"])

    def test_an_alert_file_stops_at_the_same_cap(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "senses.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                for i in range(MAX_STORED):
                    fh.write(json.dumps({"sensor": "host", "n": i}) + "\n")
            store_alert(d, {"sensor": "host", "n": MAX_STORED})
            rows = [json.loads(line) for line in _lines(path)]
            self.assertEqual(len(rows), MAX_STORED)
            self.assertEqual(rows[0]["n"], 1)
            self.assertEqual(rows[-1]["n"], MAX_STORED)
            self.assertEqual(_mode(path), 0o600)


class PrivateWriteMutations(unittest.TestCase):
    def test_bad_events_do_not_raise_or_follow_a_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for base in (None, "", 5):
                _append_security_event(base, {"n": 1})
                store_alert(base, {"sensor": "host"})
            _append_security_event(d, {"bad": {1, 2}})
            store_alert(d, {"n": float("nan")})
            store_alert(d, ["not", "a", "dict"])
            path = os.path.join(d, "security-events.jsonl")
            if os.path.exists(path):
                self.assertEqual(_lines(path), [])

            _append_security_event(d, {"ok": True})
            os.remove(path)
            os.symlink(target, path)
            _append_security_event(d, {"ok": False})
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            self.assertTrue(os.path.islink(path))

            os.unlink(path)
            with mock.patch("os.chmod", side_effect=OSError("busy")):
                _append_security_event(d, {"chmod": True})
            self.assertEqual(_lines(path), [json.dumps({"chmod": True})])
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")


class PrivateWriteFuzzTest(unittest.TestCase):
    def test_random_events_stay_capped_and_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            events = os.path.join(d, "security-events.jsonl")
            alerts = os.path.join(d, "senses.jsonl")
            for i in range(120):
                event = rng.choice([
                    {"n": i, "msg": rng.choice(["ok", "a\nb", "", "ü"])},
                    {"bad": {1}},
                    None,
                    {"n": float("nan")},
                ])
                record = rng.choice([
                    {"sensor": "host", "n": i},
                    {"sensor": "host", "n": float("nan")},
                    None,
                    ["x"],
                ])
                try:
                    _append_security_event(d, event)
                    store_alert(d, record)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                for path in (events, alerts):
                    if os.path.isfile(path) and not os.path.islink(path):
                        if _mode(path) != 0o600:
                            crashes.append(oct(_mode(path)))
                            break
                        if len(_lines(path)) > 5000:
                            crashes.append(len(_lines(path)))
                            break
                if crashes:
                    break
            for name in ("security-events.jsonl", "senses.jsonl"):
                planted = os.path.join(d, "sub")
                os.makedirs(planted, exist_ok=True)
                link = os.path.join(planted, name)
                if os.path.lexists(link):
                    os.unlink(link)
                os.symlink(target, link)
            try:
                _append_security_event(os.path.join(d, "sub"), {"n": 1})
                store_alert(os.path.join(d, "sub"), {"sensor": "host"})
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
