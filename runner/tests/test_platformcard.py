"""The platform card a ping's result carries (PROTOCOL 3.2).

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

A sender learns what box it is talking to from the pong, at the tier
the owner set with `pong_platform`: `family` (the default) names the
OS family, the default interpreter, and the protocol versions the
runner speaks; `standard` adds release, Python, and runner version;
`full` adds which of a fixed tool list is on PATH; `none` says
nothing. The card never leaves on anything but a verified ping, and
an exec result never carries one.
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runner", "cloud"))

from runner.wire import platformcard as PC  # noqa: E402
from runner import runner as R  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (not `from`: the harness
#                                       class must not be re-collected here)


class OsFamilyLegsTest(unittest.TestCase):
    """Queue A refill: os_family's non-host legs
    (coverage run 40189711740: lines 47, 49, 52).
    The card names the family from sys.platform:
    win* is windows, darwin is macos, and anything
    unrecognized is other -- the three answers a
    Linux or Windows CI host never gives for itself.
    """

    def test_the_other_platform_names(self):
        for given, want in (("win32", "windows"),
                            ("darwin", "macos"),
                            ("freebsd13", "other"),
                            ("linux", "linux")):
            with mock.patch.object(sys, "platform", given):
                self.assertEqual(PC.os_family(), want)


class CardTest(unittest.TestCase):
    def test_none_is_no_card(self):
        self.assertIsNone(PC.build_card("none"))
        self.assertIsNone(PC.build_card("bogus"))

    def test_family_is_what_a_sender_needs_and_no_more(self):
        card = PC.build_card("family")
        self.assertEqual(set(card), {"disclosure", "os_family",
                                     "default_interpreter",
                                     "protocol_versions"})
        self.assertEqual(card["disclosure"], "family")
        self.assertIn(card["os_family"], ("windows", "macos", "linux", "other"))
        self.assertEqual(card["default_interpreter"], PC.platform_interpreter())
        self.assertEqual(card["protocol_versions"], [1])

    def test_the_config_names_the_interpreter_and_the_versions(self):
        card = PC.build_card("family", {"default_interpreter": ["bash"]},
                             protocol_versions=[2, 1, 1])
        self.assertEqual(card["default_interpreter"], ["bash"])
        self.assertEqual(card["protocol_versions"], [1, 2])
        # A malformed interpreter setting is not echoed; the platform
        # default stands. Non-integer versions are dropped.
        card = PC.build_card("family", {"default_interpreter": "bash"},
                             protocol_versions=["2", True])
        self.assertEqual(card["default_interpreter"], PC.platform_interpreter())
        self.assertEqual(card["protocol_versions"], [1])

    def test_standard_and_full_add_in_order(self):
        std = PC.build_card("standard", runner_version="3.12.57")
        self.assertEqual(set(std) - {"disclosure", "os_family",
                                     "default_interpreter",
                                     "protocol_versions"},
                         {"os_release", "python_version", "runner_version"})
        self.assertEqual(std["runner_version"], "3.12.57")
        full = PC.build_card("full")
        self.assertEqual(set(full["path_tools"]), set(PC.PATH_TOOLS))
        self.assertTrue(all(isinstance(v, bool)
                            for v in full["path_tools"].values()))
        self.assertNotIn("runner_version", full)  # none was given

    def test_tier_of_reads_the_key_and_refuses_the_rest(self):
        self.assertEqual(PC.tier_of({}, "pong_platform"), ("family", None))
        self.assertEqual(PC.tier_of({"pong_platform": "none"}, "pong_platform"),
                         ("none", None))
        for bad in ("FAMILY", "", 1, ["family"], {"tier": "full"}):
            tier, problem = PC.tier_of({"pong_platform": bad}, "pong_platform")
            self.assertIsNone(tier, bad)
            self.assertIn("pong_platform must be one of", problem)


class PongTest(unittest.TestCase):
    # Composition, not inheritance: subclassing the harness would run
    # its own tests a second time under this module's name.
    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.run_cycle = self.h.run_cycle

    def tearDown(self):
        import shutil
        shutil.rmtree(self.h.tmp, ignore_errors=True)

    def _pong(self, **cfg):
        import uuid
        self.cfg.update(cfg)
        jid = str(uuid.uuid4())
        _, smtp, _ = self.run_cycle([TR.job_email(TR.job_payload(jid))])
        return TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)

    def test_the_default_pong_carries_the_family_card(self):
        result = self._pong()
        self.assertEqual(result["stdout"], "pong")
        card = result["platform"]
        self.assertEqual(card["disclosure"], "family")
        self.assertEqual(set(card), {"disclosure", "os_family",
                                     "default_interpreter",
                                     "protocol_versions"})
        self.assertEqual(card["protocol_versions"], [1])

    def test_none_sends_the_bare_pong(self):
        result = self._pong(pong_platform="none")
        self.assertEqual(result["stdout"], "pong")
        self.assertNotIn("platform", result)

    def test_the_card_names_version_2_when_it_is_on(self):
        result = self._pong(protocol_v2=True, default_interpreter=["sh"])
        self.assertEqual(result["platform"]["protocol_versions"], [1, 2])
        self.assertEqual(result["platform"]["default_interpreter"], ["sh"])

    def test_full_carries_the_runner_version_and_tools(self):
        result = self._pong(pong_platform="full")
        card = result["platform"]
        self.assertEqual(card["runner_version"], R.__version__)
        self.assertIn("path_tools", card)

    def test_an_exec_result_carries_no_card(self):
        import uuid
        jid = str(uuid.uuid4())
        p = TR.job_payload(jid, kind="exec", script="echo x", interpreter=["sh"])
        _, smtp, _ = self.run_cycle([TR.job_email(p)])
        result = TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET)
        self.assertNotIn("platform", result)

    def test_a_bad_tier_is_a_startup_config_error(self):
        self.cfg["pong_platform"] = "everything"
        self.assertIn("pong_platform must be one of",
                      R._validate_size_caps(self.cfg))
        self.cfg["pong_platform"] = "standard"
        self.assertIsNone(R._validate_size_caps(self.cfg))

    def test_pong_platform_without_the_module_is_silent(self):
        with mock.patch.object(R, "_platformcard", None):
            self.assertIsNone(R.pong_platform({"pong_platform": "full"}))
            self.assertIsNone(R._validate_size_caps(
                {"pong_platform": "everything"}))


if __name__ == "__main__":
    unittest.main()
