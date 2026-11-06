# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1's paging thresholds refuse at the startup gate (PF-1).

docs/steady/present-but-invalid-config.md puts the resources
and DRI readers in the refuse class -- a wrong threshold changes
what the box protects, because those thresholds page a human --
and parse_resources / parse_dri raise RuntimeError naming the
key, in parse_resources' own words "a startup config error, the
documented posture for this block". test_decision1_startup.py's
RefuseReaderTest pins the readers, on the stated basis that main
calls them at startup.

It did not. Nothing in main() called either reader: the only
callers were check_resources and maybe_page in the poll loop,
and both swallow the RuntimeError and return None / 0 with no
log line naming anything. A box configured with
resources.threshold "high" started cleanly, polled forever,
and its resource monitor and DRI paging were silently dead.

The gate now validates both blocks beside the key policies and
the mailbox ports, under main()'s own comment for that block:
checked here so the poll loop is not the thing that discovers
it. The poll-loop readers keep their fail-closed contract
(Decision 1 point 4: the refuse class cannot refuse mid-run) --
a bad value written live returns None / 0 there, is named by
the next start's refusal, and never kills a poll cycle.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as RR  # noqa: E402
from runner.oracle import dri, resources  # noqa: E402

STRONG_SECRET = ("unit-test-only-strong-secret-"
                 "a3bf4f1b2b0b822cd15d6c15b0f00a08")
BASE = {"mailbox_user": "a@b.c", "mailbox_password": "p",
        "shared_secret": STRONG_SECRET,
        "security": {"modes": {"confinement": "off",
                               "job_user": "off"}}}


def run_main(extra):
    """One real startup through main() with --audit-report, the
    read-only one-shot that returns after the config gates, so a
    startup that proceeds touches no mailbox or model."""
    tmpdir = tempfile.mkdtemp(prefix="hp-pf1-")
    cfg = dict(BASE, base_dir=tmpdir)
    cfg.update(extra)
    cfg_path = os.path.join(tmpdir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    out, err = io.StringIO(), io.StringIO()
    argv = ["runner", "--config", cfg_path, "--audit-report"]
    with mock.patch.object(sys, "argv", argv):
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = RR.main()
    return rc, out.getvalue(), err.getvalue()


class PagingGateRefusalTest(unittest.TestCase):
    """One test per refuse-class field of the 2 paging blocks:
    a real startup exits 2 with the key named on stderr."""

    def assert_refused(self, extra, *needles):
        rc, _out, err = run_main(extra)
        self.assertEqual(rc, 2, err)
        for needle in needles:
            self.assertIn(needle, err)

    # -- resources --
    def test_resources_threshold_not_a_number(self):
        self.assert_refused(
            {"resources": {"threshold": "high"}},
            "resources.threshold")

    def test_resources_threshold_out_of_range(self):
        self.assert_refused(
            {"resources": {"threshold": 1.5}}, "resources.threshold")

    def test_resources_threshold_zero(self):
        self.assert_refused(
            {"resources": {"threshold": 0}}, "resources.threshold")

    def test_resources_cooldown_not_a_number(self):
        self.assert_refused(
            {"resources": {"cooldown_sec": "soon"}},
            "resources.cooldown_sec")

    def test_resources_enabled_not_a_boolean(self):
        self.assert_refused(
            {"resources": {"enabled": "yes"}}, "resources.enabled")

    def test_resources_block_not_an_object(self):
        self.assert_refused({"resources": "bad"}, "resources")

    # -- dri --
    def test_dri_sensor_fused_score_threshold_boolean(self):
        self.assert_refused(
            {"dri": {"triggers": {
                "sensor_fused_score": {"threshold": True}}}},
            "dri.triggers.sensor_fused_score")

    def test_dri_key_probe_threshold_not_a_number(self):
        self.assert_refused(
            {"dri": {"triggers": {
                "key_probe": {"threshold": "many"}}}},
            "dri.triggers.key_probe")

    def test_dri_cooldown_not_a_number(self):
        self.assert_refused(
            {"dri": {"cooldown_sec": "soon"}}, "dri", "cooldown")

    def test_dri_channel_not_offered(self):
        self.assert_refused(
            {"dri": {"channel": "signal"}}, "dri.channel")

    def test_dri_enabled_not_a_boolean(self):
        self.assert_refused(
            {"dri": {"enabled": "yes"}}, "dri.enabled")

    def test_dri_block_not_an_object(self):
        self.assert_refused({"dri": "bad"}, "dri")


class PagingGateProceedsTest(unittest.TestCase):
    """The gate refuses only the refuse class: absent blocks and
    usable values start exactly as before."""

    def test_no_paging_blocks_starts(self):
        rc, _out, err = run_main({})
        self.assertEqual(rc, 0, err)

    def test_usable_paging_blocks_start(self):
        rc, _out, err = run_main({
            "resources": {"enabled": True, "threshold": 0.9,
                          "cooldown_sec": 60},
            "dri": {"enabled": False,
                    "triggers": {"sensor_fused_score":
                                 {"threshold": 6.0,
                                  "window_sec": 600}}}})
        self.assertEqual(rc, 0, err)

    def test_disabled_blocks_with_usable_values_start(self):
        rc, _out, err = run_main({
            "resources": {"enabled": False},
            "dri": {"enabled": False}})
        self.assertEqual(rc, 0, err)


class PollLoopFailClosedTest(unittest.TestCase):
    """The mid-run half of Decision 1 point 4, unchanged by the
    gate: handed a bad block directly (the live-reload shape),
    the poll-loop readers fail closed and do not raise, so one
    bad edit cannot kill the cycle -- and the same values are
    the ones the gate refuses at the next start, above."""

    def test_check_resources_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(resources.check_resources(
                {"resources": {"threshold": "high"}}, d))

    def test_maybe_page_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(dri.maybe_page(
                {"dri": {"enabled": True, "triggers": {
                    "sensor_fused_score": {"threshold": "high"}}}},
                d), 0)


if __name__ == "__main__":
    unittest.main()
