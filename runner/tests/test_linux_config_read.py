"""Linux config read. A symlink is not the config.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not opened.
"""
import json
import os
import random
import tempfile
import unittest

from runner.runner import load_config, reload_hot_config


class ConfigReadTest(unittest.TestCase):
    def test_a_regular_config_loads_and_a_symlink_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"mailbox_user": "a@b.c", "workers": 2}, fh)
            self.assertEqual(load_config(path)["mailbox_user"], "a@b.c")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                json.dump({
                    "mailbox_user": "root@evil",
                    "shared_secret": "secret-value",
                    "workers": 9,
                }, fh)
            os.remove(path)
            os.symlink(target, path)
            with self.assertRaises(RuntimeError) as caught:
                load_config(path)
            self.assertIn("symlink", str(caught.exception))
            self.assertNotIn("secret-value", str(caught.exception))
            cfg = {"workers": 1, "mailbox_user": "keep-me"}
            changed = reload_hot_config(cfg, path, {"mtime": 0})
            self.assertEqual(changed, [])
            self.assertEqual(cfg["workers"], 1)
            self.assertEqual(cfg["mailbox_user"], "keep-me")
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret-value", fh.read())
            self.assertTrue(os.path.islink(path))


class ConfigReadMutations(unittest.TestCase):
    def test_non_objects_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            for body in ("[]", "null", "1", "\"x\"", "not json", ""):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(body)
                with self.assertRaises((RuntimeError, ValueError)):
                    load_config(path)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({}, fh)
            self.assertEqual(load_config(path), {})
            missing = os.path.join(d, "missing.json")
            with self.assertRaises(OSError):
                load_config(missing)


class ConfigReadFuzzTest(unittest.TestCase):
    def test_random_files_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"shared_secret": "secret-value", "workers": 9}')
            for i in range(80):
                body = rng.choice([
                    json.dumps({"workers": i, "mailbox_user": "a@b.c"}),
                    "[]",
                    "null",
                    "nope",
                    json.dumps(["x"]),
                    "",
                ])
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(body)
                    loaded = load_config(path)
                except (RuntimeError, ValueError):
                    continue
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(loaded, dict):
                    crashes.append(type(loaded).__name__)
                    break
            os.remove(path)
            os.symlink(target, path)
            cfg = {"workers": 1}
            try:
                with self.assertRaises(RuntimeError):
                    load_config(path)
                if reload_hot_config(cfg, path, {"mtime": 0}) != []:
                    crashes.append("reloaded")
                if cfg.get("workers") != 1:
                    crashes.append(cfg.get("workers"))
            except AssertionError:
                crashes.append("no-raise")
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if "secret-value" not in fh.read():
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
