"""Linux Oracle context. A retained symlink is not job output.

Unit cases, one-field mutations, and a deterministic fuzz.
watch is off, so no canary plant and no log scan. Nothing here
starts a process. A planted symlink is not opened.
"""
import json
import os
import random
import tempfile
import unittest

from runner.runner import oracle_context


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


class OracleReadTest(unittest.TestCase):
    def test_a_real_job_is_shown_and_a_symlink_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            retained = os.path.join(d, "retained")
            os.makedirs(retained)
            _write(os.path.join(retained, "job-1.json"), {
                "job_id": "job-1",
                "kind": "exec",
                "status": "ok",
                "stdout": "hello",
            })
            text = oracle_context(d, watch=False)
            self.assertIn("job-1", text)
            self.assertIn("hello", text)
            target = os.path.join(d, "target")
            _write(target, {
                "job_id": "job-2",
                "kind": "exec",
                "status": "ok",
                "stdout": "secret-output",
            })
            os.symlink(target, os.path.join(retained, "job-2.json"))
            text = oracle_context(d, watch=False)
            self.assertIn("job-1", text)
            self.assertNotIn("job-2", text)
            self.assertNotIn("secret-output", text)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret-output", fh.read())


class OracleMutations(unittest.TestCase):
    def test_bad_inputs_do_not_raise(self):
        self.assertEqual(oracle_context(None, watch=False), "")
        self.assertEqual(oracle_context("", watch=False), "(no job output retained yet)")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(oracle_context(d, watch=False),
                             "(no job output retained yet)")
            retained = os.path.join(d, "retained")
            os.makedirs(retained)
            with open(os.path.join(retained, "job-1.json"), "w", encoding="utf-8") as fh:
                fh.write("not json")
            with open(os.path.join(retained, "../nope.json"), "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            with open(os.path.join(retained, "bad id.json"), "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            text = oracle_context(d, watch=False, limit=True, max_chars=0)
            self.assertNotIn("secret", text)
            self.assertIsInstance(text, str)
            text = oracle_context(d, watch=False, limit=-1, max_chars="n")
            self.assertIsInstance(text, str)


class OracleFuzzTest(unittest.TestCase):
    def test_random_files_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            retained = os.path.join(d, "retained")
            os.makedirs(retained)
            target = os.path.join(d, "target")
            _write(target, {"stdout": "secret-output", "job_id": "job-x"})
            for i in range(60):
                name = rng.choice(["job-%d.json" % i, "bad id.json", "a.json"])
                body = rng.choice([
                    json.dumps({"job_id": "job-%d" % i, "stdout": "ok", "kind": "exec"}),
                    "nope",
                    "[]",
                    json.dumps(["x"]),
                ])
                try:
                    with open(os.path.join(retained, name), "w", encoding="utf-8") as fh:
                        fh.write(body)
                    text = oracle_context(
                        d, watch=False,
                        limit=rng.choice([1, 6, None, True, -1]),
                        max_chars=rng.choice([0, 20, 8000, "n"]))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(text, str):
                    crashes.append(type(text).__name__)
                    break
                if "secret-output" in text:
                    crashes.append("leaked")
                    break
            os.symlink(target, os.path.join(retained, "job-link.json"))
            try:
                text = oracle_context(d, watch=False)
            except Exception as exc:
                crashes.append(type(exc).__name__)
                text = ""
            if "secret-output" in text or "job-x" in text:
                crashes.append("read")
            with open(target, encoding="utf-8") as fh:
                if "secret-output" not in fh.read():
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
