"""The key directory: a file the runner reads, and what each state does.

One entry per key id holds the fingerprint, the state, not_before
and not_after. Never the secret. in_use verifies. superseded
verifies until its not_after. Everything else is refused at every
door. compromised is refused at once.
"""
import json
import os
import tempfile
import time
import unittest

from runner.wire import verify


class DirectoryVerdictTest(unittest.TestCase):
    def setUp(self):
        self.secrets = {"": "s" * 48, "ops": "o" * 48}
        self.now = 1_000_000.0

    def test_no_directory_admits(self):
        self.assertIsNone(verify.key_directory_verdict(
            None, self.secrets, "ops", self.now))

    def test_in_use_admits(self):
        directory = {"ops": {"state": "in_use"}}
        self.assertIsNone(verify.key_directory_verdict(
            directory, self.secrets, "ops", self.now))

    def test_superseded_admits_until_its_window_closes(self):
        directory = {"ops": {"state": "superseded",
                             "not_after": self.now + 10}}
        self.assertIsNone(verify.key_directory_verdict(
            directory, self.secrets, "ops", self.now))
        directory["ops"]["not_after"] = self.now - 1
        self.assertIn("window has closed", verify.key_directory_verdict(
            directory, self.secrets, "ops", self.now))

    def test_superseded_with_no_window_admits(self):
        directory = {"ops": {"state": "superseded"}}
        self.assertIsNone(verify.key_directory_verdict(
            directory, self.secrets, "ops", self.now))

    def test_compromised_is_refused_at_once(self):
        directory = {"ops": {"state": "compromised",
                             "not_after": self.now + 10_000}}
        self.assertEqual("key is compromised",
                         verify.key_directory_verdict(
                             directory, self.secrets, "ops", self.now))

    def test_every_other_state_is_refused(self):
        for state in ("ordered", "generated", "distributed", "destroyed"):
            with self.subTest(state=state):
                directory = {"ops": {"state": state}}
                why = verify.key_directory_verdict(
                    directory, self.secrets, "ops", self.now)
                self.assertIn(state, why)

    def test_a_key_with_no_entry_is_refused(self):
        directory = {"other": {"state": "in_use"}}
        self.assertIn("no key directory entry",
                      verify.key_directory_verdict(
                          directory, self.secrets, "ops", self.now))

    def test_an_unknown_state_is_refused(self):
        directory = {"ops": {"state": "maybe"}}
        self.assertIn("invalid", verify.key_directory_verdict(
            directory, self.secrets, "ops", self.now))


class DirectoryLoadTest(unittest.TestCase):
    def test_inline_and_file_are_mutually_exclusive(self):
        with self.assertRaises(RuntimeError):
            verify.load_key_directory(
                {"key_directory": {}, "key_directory_file": "x"})

    def test_a_file_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "keys.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"ops": {"state": "in_use"}}, fh)
            got = verify.load_key_directory({"key_directory_file": path})
            self.assertEqual("in_use", got["ops"]["state"])

    def test_none_when_unset(self):
        self.assertIsNone(verify.load_key_directory({}))


class DirectoryAtTheDoorTest(unittest.TestCase):
    def test_the_door_refuses_a_compromised_key(self):
        cfg = {"key_directory": {"ops": {"state": "compromised"}}}
        secrets = {"": "s" * 48, "ops": "o" * 48}
        why = verify.check_door_policy(cfg, secrets, "ops", "query")
        self.assertEqual("key is compromised", why)

    def test_the_door_admits_an_in_use_key(self):
        cfg = {"key_directory": {"ops": {"state": "in_use"}}}
        secrets = {"": "s" * 48, "ops": "o" * 48}
        self.assertIsNone(verify.check_door_policy(
            cfg, secrets, "ops", "query"))


if __name__ == "__main__":
    unittest.main()
