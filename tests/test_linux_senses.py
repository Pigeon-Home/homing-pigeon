"""Linux senses store. A symlink is not read as alerts.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not opened.
"""
import json
import os
import random
import tempfile
import unittest

from runner.senses import load_alerts, store_alert


def _mode(path):
    return os.stat(path).st_mode & 0o777


class SensesReadTest(unittest.TestCase):
    def test_a_stored_alert_loads_and_a_symlink_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            store_alert(d, {"sensor": "host", "severity": "low", "title": "ok"})
            store_alert(d, {"sensor": "auth", "severity": "high", "title": "sudo"})
            rows = load_alerts(d)
            self.assertEqual([row["title"] for row in rows], ["ok", "sudo"])
            path = os.path.join(d, "senses.jsonl")
            self.assertEqual(_mode(path), 0o600)
            self.assertFalse(os.path.islink(path))
            self.assertEqual(load_alerts(d, sensor="auth")[0]["title"], "sudo")
            self.assertEqual(load_alerts(d, limit=1)[0]["title"], "sudo")

            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"sensor": "host", "title": "secret"}\n')
            os.remove(path)
            os.symlink(target, path)
            self.assertEqual(load_alerts(d), [])
            store_alert(d, {"sensor": "host", "title": "pwned"})
            with open(target, encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("secret", body)
            self.assertNotIn("pwned", body)
            self.assertTrue(os.path.islink(path))


class SensesMutations(unittest.TestCase):
    def test_bad_records_and_a_bad_file_do_not_raise(self):
        self.assertEqual(load_alerts(""), [])
        self.assertEqual(load_alerts(None), [])
        store_alert("", {"sensor": "host"})
        store_alert(None, {"sensor": "host"})
        with tempfile.TemporaryDirectory() as d:
            store_alert(d, None)
            store_alert(d, ["nope"])
            store_alert(d, {"sensor": "host", "bag": {1}})
            rows = load_alerts(d)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["bag"], [1])
            path = os.path.join(d, "senses.jsonl")
            with open(path, "wb") as fh:
                fh.write(b"\xff\n{\"sensor\": \"host\", \"title\": \"ok\"}\n")
            rows = load_alerts(d)
            self.assertTrue(rows == [] or rows[0].get("title") == "ok")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("not json\n")
                fh.write('{"sensor": "host", "title": "kept"}\n')
            self.assertEqual(load_alerts(d)[0]["title"], "kept")
            self.assertEqual(load_alerts(d, sensor="other"), [])


class SensesFuzzTest(unittest.TestCase):
    def test_random_records_do_not_read_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(80):
                record = rng.choice([
                    {"sensor": rng.choice(["host", "auth", ""]), "n": i},
                    {"sensor": "host", "title": "t%d" % i},
                    None,
                    ["x"],
                    {"bag": {1}},
                ])
                try:
                    store_alert(d, record)
                    rows = load_alerts(d, sensor="host", limit=rng.choice([1, 5, 50]))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(rows, list):
                    crashes.append(type(rows).__name__)
                    break
                path = os.path.join(d, "senses.jsonl")
                if os.path.isfile(path) and not os.path.islink(path):
                    if _mode(path) != 0o600:
                        crashes.append(oct(_mode(path)))
                        break
            path = os.path.join(d, "senses.jsonl")
            if os.path.lexists(path):
                os.remove(path)
            os.symlink(target, path)
            try:
                if load_alerts(d) != []:
                    crashes.append("read")
                store_alert(d, {"sensor": "host", "title": "nope"})
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
            if not os.path.islink(path):
                crashes.append("replaced")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
