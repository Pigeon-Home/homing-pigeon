#!/usr/bin/env python3
"""The three live-config findings.

A bad refuse-class value written while the runner is up is
named. A boolean written for a hot key reads as that key's
default and is named, rather than becoming 1. A misspelled
key-policy field refuses the policy build (Q129, 2026-11-06),
rather than vanishing out of the built policy.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.runner import (  # noqa: E402
    build_key_policies, reload_hot_config)


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    # A new mtime, so the reload does not treat the file as unchanged.
    now = os.path.getmtime(path)
    os.utime(path, (now + 2, now + 2))


class LiveFindingsTest(unittest.TestCase):
    def test_a_boolean_hot_key_reads_as_its_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            _write(path, {"poll_interval_sec": True})
            cfg = {"poll_interval_sec": 7}
            out = io.StringIO()
            with redirect_stdout(out):
                reload_hot_config(cfg, path, {})
            self.assertEqual(cfg["poll_interval_sec"], 20)
            text = out.getvalue()
            self.assertIn("poll_interval_sec", text)
            self.assertIn("True", text)
            self.assertNotIn("=1", text.replace("default 20", ""))

    def test_a_bad_refuse_class_port_is_named_and_not_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            _write(path, {"smtp_port": "nope"})
            cfg = {"smtp_port": 587}
            out = io.StringIO()
            with redirect_stdout(out):
                reload_hot_config(cfg, path, {})
            self.assertEqual(cfg["smtp_port"], 587)
            text = out.getvalue()
            self.assertIn("smtp_port", text)
            self.assertIn("not applied", text)

    def test_a_misspelled_policy_field_refuses_the_build(self):
        # Q129 (2026-11-06): key policies are in Decision 1's
        # refuse class, so a field the builder does not
        # recognise refuses the build, naming the key and the
        # field. Warn-and-drop (the 1-Nov-2026 disposition of
        # stage 4 P4 finding F1) left the key running with the
        # fence the typo removed -- possibly no fence at all.
        with self.assertRaises(RuntimeError) as caught:
            build_key_policies({
                "key_policies": {"k": {"alllowed_kinds": ["exec"]}},
            })
        self.assertIn("alllowed_kinds", str(caught.exception))
        self.assertIn("'k'", str(caught.exception))

    def test_a_real_policy_field_is_kept_and_quiet(self):
        built = build_key_policies({
            "key_policies": {"k": {"allowed_kinds": ["exec"]}},
        })
        self.assertEqual(built["k"]["allowed_kinds"], ["exec"])
        self.assertEqual(build_key_policies.last_warnings, [])


if __name__ == "__main__":
    unittest.main()
