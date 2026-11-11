#!/usr/bin/env python3
# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Decision 1 startup: the refusing readers for blocks
main's early path does not reach.

Split from runner/tests/test_decision1_startup.py in
the Q136 follow-on file split (2026-11-11); the tests
are moved verbatim, not rewritten. This piece carries
RefuseReaderTest: secrets and their floors, the
resources and DRI paging thresholds, and the DTLS /
NATS transport readers.
"""
import os
import sys
import importlib
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as RR  # noqa: E402
from runner.oracle.dri import parse_dri  # noqa: E402
from runner.oracle.resources import parse_resources  # noqa: E402
from runner.tests.decision1_startup_support import (  # noqa: E402
    STRONG_SECRET)


class RefuseReaderTest(unittest.TestCase):
    """The refusing readers for blocks main's early path does not
    reach: secrets, the paging thresholds, the transport ports
    and bind. Each raises RuntimeError naming its key."""

    def _refuses(self, fn, *needles):
        with self.assertRaises(RuntimeError) as cm:
            fn()
        for needle in needles:
            self.assertIn(needle, str(cm.exception))

    # -- secrets and their floors --
    def test_shared_secret_missing(self):
        self._refuses(lambda: RR.build_secrets({}), "shared_secret")

    def test_shared_secret_weak(self):
        self._refuses(
            lambda: RR.build_secrets({"shared_secret": "abc123"}),
            "shared_secret", "too weak")

    def test_shared_secret_and_file_both(self):
        self._refuses(
            lambda: RR.build_secrets(
                {"shared_secret": STRONG_SECRET,
                 "shared_secret_file": "/tmp/never-read"}),
            "shared_secret", "shared_secret_file")

    def test_additional_secrets_not_an_object(self):
        self._refuses(
            lambda: RR.build_secrets(
                {"shared_secret": STRONG_SECRET,
                 "additional_secrets": "nope"}),
            "additional_secrets")

    def test_additional_secret_weak(self):
        self._refuses(
            lambda: RR.build_secrets(
                {"shared_secret": STRONG_SECRET,
                 "additional_secrets": {"k2": "weak"}}),
            "shared_secret", "too weak")

    # -- resources: the paging threshold and its companions --
    def test_resources_threshold_not_a_number(self):
        self._refuses(
            lambda: parse_resources({"resources": {"threshold": "high"}}),
            "resources.threshold")

    def test_resources_threshold_out_of_range(self):
        self._refuses(
            lambda: parse_resources({"resources": {"threshold": 1.5}}),
            "resources.threshold")

    def test_resources_cooldown_not_a_number(self):
        self._refuses(
            lambda: parse_resources(
                {"resources": {"cooldown_sec": "soon"}}),
            "resources.cooldown_sec")

    def test_resources_enabled_not_a_boolean(self):
        self._refuses(
            lambda: parse_resources({"resources": {"enabled": "yes"}}),
            "resources.enabled")

    # -- DRI: the other paging thresholds --
    def test_dri_sensor_fused_score_threshold(self):
        self._refuses(
            lambda: parse_dri({"dri": {"triggers": {
                "sensor_fused_score": {"threshold": True}}}}),
            "dri.triggers.sensor_fused_score")

    def test_dri_key_probe_threshold(self):
        self._refuses(
            lambda: parse_dri({"dri": {"triggers": {
                "key_probe": {"threshold": "many"}}}}),
            "dri.triggers.key_probe")

    def test_dri_cooldown_not_a_number(self):
        self._refuses(
            lambda: parse_dri({"dri": {"cooldown_sec": "soon"}}),
            "dri", "cooldown")

    def test_dri_channel_not_offered(self):
        self._refuses(
            lambda: parse_dri({"dri": {"channel": "signal"}}),
            "dri.channel")

    # -- transports: the port and bind reads Q3 moved to refuse --
    def test_transport_dtls_port(self):
        dtls = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        self._refuses(lambda: dtls.listen_port({"port": "2O220"}),
                      "transport_dtls.port")
        self._refuses(lambda: dtls.listen_port({"port": 99999}),
                      "transport_dtls.port")
        self._refuses(lambda: dtls.listen_port({"port": True}),
                      "transport_dtls.port")
        # The documented defaults and a usable value still read.
        self.assertEqual(dtls.listen_port({}), 20220)
        self.assertEqual(dtls.listen_port({"port": 20221}), 20221)

    def test_transport_dtls_bind(self):
        dtls = importlib.import_module(
            "runner.transport_extensions.dtls.__main__")
        self._refuses(
            lambda: dtls.bind_address({"bind": "not-an-address"}),
            "transport_dtls.bind")
        self._refuses(lambda: dtls.bind_address({"bind": 42}),
                      "transport_dtls.bind")
        self.assertEqual(dtls.bind_address({}), "0.0.0.0")
        self.assertEqual(dtls.bind_address({"bind": "127.0.0.1"}),
                         "127.0.0.1")

    def test_transport_nats_url_port(self):
        nats = importlib.import_module(
            "runner.transport_extensions.nats.__main__")
        self._refuses(
            lambda: nats.url_port("nats://127.0.0.1:2O220"),
            "transport_nats.url")
        self._refuses(
            lambda: nats.url_port("nats://127.0.0.1:99999"),
            "transport_nats.url")
        self.assertEqual(nats.url_port("nats://127.0.0.1"), 4222)
        self.assertEqual(nats.url_port("nats://127.0.0.1:4223"), 4223)


if __name__ == "__main__":
    unittest.main(verbosity=2)
