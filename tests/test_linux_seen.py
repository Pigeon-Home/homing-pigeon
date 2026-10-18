"""Linux replay cache: mode 0600, and the temp name is not a symlink.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not written
through.
"""
import json
import os
import random
import tempfile
import threading
import unittest
from unittest import mock

from runner.runner import SEEN_CAP, load_seen, save_seen


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _tmp_for(path):
    return path + ".tmp." + str(threading.get_ident())


import sys

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest(
        "Linux-only suite: it pins POSIX modes, nofollow opens, "
        "signals, and systemd units, and runs in the Linux test job")


class SeenFileTest(unittest.TestCase):
    def test_the_newest_keys_are_owner_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            seen = {"old-%d" % i: True for i in range(SEEN_CAP + 3)}
            seen["newest"] = True
            seen_flags = []
            real_open = os.open

            def spy(file_path, flags, *args, **kwargs):
                if str(file_path).endswith("seen.json.tmp." + str(threading.get_ident())):
                    seen_flags.append(flags)
                return real_open(file_path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=spy):
                save_seen(path, seen)
            loaded = load_seen(path)
            self.assertEqual(len(loaded), SEEN_CAP)
            self.assertNotIn("old-0", loaded)
            self.assertIn("newest", loaded)
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertFalse(os.path.exists(_tmp_for(path)))
            self.assertTrue(seen_flags)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen_flags))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen_flags))

    def test_a_symlink_at_the_temp_name_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            link = _tmp_for(path)
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            with mock.patch("os.unlink", side_effect=leave_the_link):
                save_seen(path, {"id-1": True})
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")
            self.assertTrue(os.path.islink(link))
            self.assertFalse(os.path.exists(path))

    def test_a_symlink_at_the_seen_path_is_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            os.symlink(target, path)
            save_seen(path, {"id-1": True})
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            self.assertEqual(load_seen(path), {"id-1": True})
            with open(target, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "keep")


class SeenMutations(unittest.TestCase):
    def test_bad_paths_and_bad_keys_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            for bad in (None, "", 5):
                save_seen(bad, {"a": True})
            save_seen(path, None)
            save_seen(path, "bad")
            save_seen(path, ["a"])
            self.assertEqual(load_seen(path), {})
            save_seen(path, {1: True, "ok": True, "a\x00b": True})
            loaded = load_seen(path)
            self.assertIn("ok", loaded)
            self.assertIn("1", loaded)
            self.assertNotIn("a\x00b", loaded)
            self.assertEqual(_mode(path), 0o600)

            class Boom:
                def __str__(self):
                    raise RuntimeError("no")

            save_seen(path, {Boom(): True, "kept": True})
            self.assertEqual(load_seen(path), {"kept": True})


class SeenReadTest(unittest.TestCase):
    def test_a_symlink_cache_is_not_the_replay_set(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(["id-1", "id-2"], fh)
            self.assertEqual(load_seen(path), {"id-1": True, "id-2": True})
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                json.dump(["secret-job", "id-9"], fh)
            os.remove(path)
            os.symlink(target, path)
            self.assertEqual(load_seen(path), {})
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret-job", fh.read())
            self.assertTrue(os.path.islink(path))

    def test_shapes_that_are_not_a_cache_are_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            for body in ("[]", "null", "1", "\"x\"", "not json"):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(body)
                self.assertEqual(load_seen(path), {})
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"1": True, "ok": 1}, fh)
            self.assertEqual(set(load_seen(path)), {"1", "ok"})
            self.assertEqual(load_seen(""), {})
            self.assertEqual(load_seen(None), {})
            self.assertEqual(load_seen(os.path.join(d, "missing.json")), {})


class SeenReadFuzzTest(unittest.TestCase):
    def test_random_json_does_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('["secret-job"]')
            for i in range(80):
                body = rng.choice([
                    json.dumps(["id-%d" % i, i]),
                    json.dumps({"id-%d" % i: True}),
                    "null",
                    "[]",
                    "nope",
                    json.dumps([None, "ok"]),
                ])
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(body)
                    loaded = load_seen(path)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(loaded, dict):
                    crashes.append(type(loaded).__name__)
                    break
                if any(not isinstance(key, str) for key in loaded):
                    crashes.append("key")
                    break
            os.remove(path)
            os.symlink(target, path)
            try:
                if load_seen(path) != {}:
                    crashes.append("read")
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if "secret-job" not in fh.read():
                    crashes.append("followed")
            if not os.path.islink(path):
                crashes.append("replaced")
        self.assertEqual(crashes, [])


class SeenFuzzTest(unittest.TestCase):
    def test_random_keys_stay_capped_and_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(200):
                seen = rng.choice([
                    {"id-%d" % i: True},
                    None,
                    "bad",
                    {i: True, "ok": True, "a\x00b": True},
                    {},
                ])
                try:
                    save_seen(path, seen)
                    loaded = load_seen(path)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(loaded, dict) or len(loaded) > SEEN_CAP:
                    crashes.append(len(loaded) if isinstance(loaded, dict) else type(loaded).__name__)
                    break
                if os.path.isfile(path) and not os.path.islink(path):
                    if _mode(path) != 0o600:
                        crashes.append(oct(_mode(path)))
                        break
                    with open(path, encoding="utf-8") as fh:
                        raw = json.loads(fh.read())
                    if not isinstance(raw, list):
                        crashes.append(type(raw).__name__)
                        break
            link = _tmp_for(path)
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(target, link)
            try:
                save_seen(path, {"tail": True})
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
