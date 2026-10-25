"""Lab Results: the folder-watching sense's main legs.

Queue A refill pins for runner/extensions/lab-results/:
main's tunables guard and its two local-delivery refusals.
The scan itself is exercised elsewhere; here scan is
stubbed so the delivery legs are what is under test.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

EXAMPLE_DIR = os.path.join(REPO, "runner", "extensions",
                           "lab-results")


def _load_example_module():
    spec = importlib.util.spec_from_file_location(
        "lab_results", os.path.join(EXAMPLE_DIR,
                                    "lab_results.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LR = _load_example_module()


class MainDeliveryLegsTest(unittest.TestCase):
    """Queue A refill: main's tunables guard (line
    264) and its undeliverable and partial local
    deliveries (284, 288-291) on the local full-suite
    map at 93998ca. A manifest whose tunables are not
    an object reads as no tunables; both refusals are
    rc 2 with the state left unwritten."""

    def _drive(self, d, tunables, delivered):
        manifest_path = os.path.join(d, "extension.json")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump({"tunables": tunables}, fh)
        watch = os.path.join(d, "results")
        os.makedirs(watch)
        state_path = os.path.join(d, "state.json")
        err = io.StringIO()
        with mock.patch.object(
                LR, "scan",
                return_value=([{"signal": "lab_run_done"}], {})), \
                mock.patch.object(
                    LR, "_deliver_local", return_value=delivered), \
                redirect_stderr(err):
            rc = LR.main(["--manifest", manifest_path,
                          "--watch-dir", watch,
                          "--state", state_path,
                          "--local-dir", d])
        return rc, err.getvalue(), state_path

    def test_non_dict_tunables_and_undeliverable_is_rc2(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _err, state_path = self._drive(d, 42, None)
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(state_path))

    def test_partial_delivery_is_rc2_and_saves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            rc, err, state_path = self._drive(d, {}, 0)
            self.assertEqual(rc, 2)
            self.assertIn("1 of 1 alert(s) not delivered", err)
            self.assertFalse(os.path.exists(state_path))


if __name__ == "__main__":
    unittest.main()
