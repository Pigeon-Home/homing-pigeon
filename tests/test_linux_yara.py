"""Linux YARA rules file. A symlink is not the ruleset.

Unit cases, one-field mutations, and a deterministic fuzz.
yr and yara are not run. Nothing here starts a process.
A planted symlink is not opened.
"""
import os
import random
import string
import tempfile
import unittest

from runner.runner import _YARA_RULES, _yara_rules_text


def _cfg(path):
    return {"inference": {"yara_rules": path}}


class YaraRulesTest(unittest.TestCase):
    def test_a_regular_file_is_used_and_a_symlink_is_not(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "rules.yar")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("rule local { condition: true }\n")
            self.assertIn("rule local", _yara_rules_text(_cfg(path)))
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("rule secret { condition: true }\n")
            os.remove(path)
            os.symlink(target, path)
            text = _yara_rules_text(_cfg(path))
            self.assertIn("hp_encoded_exec", text)
            self.assertNotIn("secret", text)
            self.assertEqual(text, _YARA_RULES)
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())
            self.assertTrue(os.path.islink(path))


class YaraRulesMutations(unittest.TestCase):
    def test_bad_paths_fall_back(self):
        self.assertEqual(_yara_rules_text(None), _YARA_RULES)
        self.assertEqual(_yara_rules_text({}), _YARA_RULES)
        self.assertEqual(_yara_rules_text({"inference": None}), _YARA_RULES)
        self.assertEqual(_yara_rules_text({"inference": {"yara_rules": ""}}),
                         _YARA_RULES)
        self.assertEqual(_yara_rules_text({"inference": {"yara_rules": 1}}),
                         _YARA_RULES)
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "missing.yar")
            self.assertEqual(_yara_rules_text(_cfg(missing)), _YARA_RULES)
            empty = os.path.join(d, "empty.yar")
            with open(empty, "w", encoding="utf-8") as fh:
                fh.write("   \n")
            self.assertEqual(_yara_rules_text(_cfg(empty)), _YARA_RULES)
            self.assertEqual(_yara_rules_text(_cfg(d)), _YARA_RULES)


class YaraRulesFuzzTest(unittest.TestCase):
    def test_random_files_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        alphabet = string.ascii_letters + " {}:\n"
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "rules.yar")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("rule secret { condition: true }\n")
            for i in range(60):
                body = rng.choice([
                    "rule r%d { condition: true }\n" % i,
                    "   \n",
                    "",
                    "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 40))),
                ])
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(body)
                    text = _yara_rules_text(_cfg(path))
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(text, str) or not text:
                    crashes.append(type(text).__name__)
                    break
                if body.strip():
                    if text != body:
                        crashes.append("mismatch")
                        break
                elif text != _YARA_RULES:
                    crashes.append("fallback")
                    break
                if "secret" in text and "secret" not in body:
                    crashes.append("leaked")
                    break
            os.remove(path)
            os.symlink(target, path)
            try:
                text = _yara_rules_text(_cfg(path))
            except Exception as exc:
                crashes.append(type(exc).__name__)
                text = ""
            if text != _YARA_RULES or "secret" in text:
                crashes.append("read")
            with open(target, encoding="utf-8") as fh:
                if "secret" not in fh.read():
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
