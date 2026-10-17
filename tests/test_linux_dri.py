"""Linux DRI state file: mode 0600, and a symlink is not followed.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process or sends a page. A planted symlink
is not written through.
"""
import json
import os
import random
import tempfile
import threading
import unittest
from unittest import mock

from runner import dri


def _mode(path):
    return os.stat(path).st_mode & 0o777


def _tmp_for(base):
    return os.path.join(base, dri.STATE_FILE) + ".tmp." + str(threading.get_ident())


class DriStateTest(unittest.TestCase):
    def test_the_first_look_is_owner_only_and_sends_nothing(self):
        cfg = {"dri": {"enabled": True, "channel": "telegram"}}
        with tempfile.TemporaryDirectory() as d:
            seen = []
            real_open = os.open

            def spy(path, flags, *args, **kwargs):
                if str(path).endswith(".tmp." + str(threading.get_ident())):
                    seen.append(flags)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch("os.open", side_effect=spy):
                sent = dri.maybe_page(cfg, d, now=1000)
            self.assertEqual(sent, 0)
            path = os.path.join(d, dri.STATE_FILE)
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertFalse(os.path.exists(_tmp_for(d)))
            with open(path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["last_check"], 1000)
            self.assertTrue(seen)
            self.assertTrue(all(flags & os.O_NOFOLLOW for flags in seen))
            self.assertTrue(all(flags & os.O_EXCL for flags in seen))

    def test_a_symlink_is_not_read_or_written_through(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"last_check": 1, "secret": true}\n')
            path = os.path.join(d, dri.STATE_FILE)
            os.symlink(target, path)
            self.assertEqual(dri._load_state(d), {})
            link = _tmp_for(d)
            os.symlink(target, link)
            real_unlink = os.unlink

            def leave_the_link(name):
                if name == link and os.path.islink(name):
                    return
                real_unlink(name)

            with mock.patch("os.unlink", side_effect=leave_the_link):
                dri._save_state(d, {"last_check": 9})
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            self.assertTrue(os.path.islink(path))
            self.assertTrue(os.path.islink(link))
            os.unlink(link)
            dri._save_state(d, {"last_check": 2})
            self.assertFalse(os.path.islink(path))
            self.assertEqual(_mode(path), 0o600)
            self.assertEqual(dri._load_state(d)["last_check"], 2)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())


class DriMutations(unittest.TestCase):
    def test_bad_bases_and_bad_keys_do_not_raise(self):
        for base in (None, "", 5):
            self.assertEqual(dri._load_state(base), {})
            dri._save_state(base, {"last_check": 1})
        with tempfile.TemporaryDirectory() as d:

            class Boom:
                def __str__(self):
                    raise RuntimeError("no")

            dri._save_state(d, {
                "last_check": 3,
                "bag": {1},
                Boom(): "skip",
                "ok": True,
            })
            loaded = dri._load_state(d)
            self.assertEqual(loaded["last_check"], 3)
            self.assertEqual(loaded["ok"], True)
            self.assertNotIn("secret", json.dumps(loaded))
            self.assertEqual(_mode(os.path.join(d, dri.STATE_FILE)), 0o600)
            dri._save_state(d, ["not", "a", "dict"])
            self.assertEqual(dri._load_state(d), {})
            self.assertEqual(dri.maybe_page(None, d), 0)
            self.assertEqual(dri.maybe_page({"dri": "nope"}, d), 0)


class DriFuzzTest(unittest.TestCase):
    def test_random_state_stays_owner_only(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(160):
                state = rng.choice([
                    {"last_check": i, "last_page": {"resource_pressure": i}},
                    {"bag": {1}, "n": float("nan")},
                    None,
                    {"pending_digest": [{"trigger": "judge_block"}]},
                    [],
                ])
                try:
                    dri._save_state(d, state)
                    loaded = dri._load_state(d)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(loaded, dict):
                    crashes.append(type(loaded).__name__)
                    break
            path = os.path.join(d, dri.STATE_FILE)
            if os.path.isfile(path) and not os.path.islink(path):
                if _mode(path) != 0o600:
                    crashes.append(oct(_mode(path)))
            link = _tmp_for(d)
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(target, link)
            try:
                dri._save_state(d, {"last_check": 1})
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
