"""Linux audit report. A symlink is not an audit source.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here starts a process. A planted symlink is not opened.
"""
import json
import os
import random
import tempfile
import time
import unittest

from runner.auditreport import _read_counts, _read_entries, build_report


def _ts():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _line(feature="env", decision="would_deny"):
    return json.dumps({
        "ts": _ts(),
        "feature": feature,
        "mode": "audit",
        "decision": decision,
        "reason": "env_not_allowed",
        "detail": "env 'LANG'",
        "key_id": "ops",
    })


class AuditReportReadTest(unittest.TestCase):
    def test_a_real_entry_is_counted_and_a_symlink_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "security-audit.jsonl")
            counts = os.path.join(d, "security-audit-counts.json")
            with open(log, "w", encoding="utf-8") as fh:
                fh.write(_line() + "\n")
            with open(counts, "w", encoding="utf-8") as fh:
                json.dump({"env": {"evaluated": 3}}, fh)
            rows, _suggestions, _refused, _fragments = build_report({}, d, 3600)
            self.assertEqual(rows[0][0], "env")
            self.assertEqual(rows[0][2], 3)
            self.assertEqual(rows[0][3], 1)

            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(_line(feature="secret") + "\n")
            count_target = os.path.join(d, "count-target")
            with open(count_target, "w", encoding="utf-8") as fh:
                json.dump({"secret": {"evaluated": 99}}, fh)
            os.remove(log)
            os.remove(counts)
            os.symlink(target, log)
            os.symlink(count_target, counts)
            self.assertEqual(_read_entries(d), [])
            self.assertEqual(_read_counts(d), {})
            rows, suggestions, refused, fragments = build_report({}, d, 3600)
            blob = repr((rows, suggestions, refused, fragments))
            self.assertNotIn("secret", blob)
            self.assertEqual(rows, [])
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            with open(count_target, encoding="utf-8") as fh:
                self.assertIn("99", fh.read())


class AuditReportMutations(unittest.TestCase):
    def test_bad_lines_and_bad_counts_are_empty(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "security-audit.jsonl")
            counts = os.path.join(d, "security-audit-counts.json")
            with open(log, "w", encoding="utf-8") as fh:
                fh.write("not json\n")
                fh.write("[1]\n")
                fh.write(_line() + "\n")
            with open(counts, "w", encoding="utf-8") as fh:
                fh.write("[]")
            rows, _s, _r, _f = build_report({}, d, 3600)
            self.assertEqual(rows[0][0], "env")
            self.assertEqual(rows[0][2], 0)
            self.assertEqual(_read_counts(d), {})
            os.remove(log)
            self.assertEqual(build_report({}, d, 3600)[0], [])
            self.assertEqual(build_report({}, d, 0)[0], [])


class AuditReportFuzzTest(unittest.TestCase):
    def test_random_lines_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "security-audit.jsonl")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(_line(feature="secret") + "\n")
            for i in range(60):
                body = rng.choice([
                    _line(feature="env") + "\n",
                    "nope\n",
                    "[1]\n",
                    _line(decision="allowed") + "\n",
                    "",
                ])
                try:
                    with open(log, "w", encoding="utf-8") as fh:
                        fh.write(body)
                    rows, suggestions, refused, fragments = build_report(
                        {}, d, rng.choice([0, 3600]))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(rows, list) or not isinstance(suggestions, list):
                    crashes.append("shape")
                    break
                if "secret" in repr((rows, suggestions, refused, fragments)):
                    crashes.append("leaked")
                    break
            os.remove(log)
            os.symlink(target, log)
            try:
                rows, suggestions, refused, fragments = build_report({}, d, 3600)
            except Exception as exc:
                crashes.append(type(exc).__name__)
                rows = suggestions = refused = fragments = None
            if "secret" in repr((rows, suggestions, refused, fragments)):
                crashes.append("read")
            with open(target, encoding="utf-8") as fh:
                if "secret" not in fh.read():
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
