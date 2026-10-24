"""The Oracle A/B: one sensor scenario, both Oracle configurations.

docs/extensions.md (the Pi Health section) says the same
extension on a Pi Light install and on a laptop install gives
"a clean A/B across the two architectures" -- the difference is
the platform's sensors and the Oracle configuration, not the
extension. These tests make that claim concrete for the one
axis this module controls: oracle_mode. The SAME signed
sensor_alert goes through the real local ingest and the real
wake gate twice -- once with oracle_mode "deterministic" (the
Pi Light configuration) and once in the default "llm" mode
with the inference layer replaced by a recording fake (no live
model anywhere in this file).

The comparison axis is the brief's SUBSTRATE -- the facts the
filed brief record carries: sensor, signal, severity, title --
plus the facts each path states on its way: the deterministic
brief's assessment is assembled from the alert, and the llm
path hands the model a question assembled from the same alert
(both also carry the extension's declared signal description,
which the deterministic note does not restate -- it rides the
filed alert record in both modes instead). The assessments'
prose is NOT compared: in llm mode it is the model's words,
here the fake's canned answer; in deterministic mode it is the
labeled note. What is pinned is that both briefs are about the
same event, carrying the same facts, and that the mode decides
exactly one thing: whether the inference layer is touched.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner import senses as S  # noqa: E402
from runner import extensions as E  # noqa: E402

PI_HEALTH_DIR = os.path.join(REPO, "extensions", "pi-health")
PI_SECRET = "c06e9f8a2b4d47f1a3e5b6c7d8f9a0b1" + "2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f"
INF = {"endpoint": "http://127.0.0.1:11434/v1", "model": "qwen3:1.7b"}
FAKE_ANSWER = "Fake model assessment: the board is hot."

# The substrate fields two briefs about the same event must
# agree on, whatever mode produced them.
SUBSTRATE = ("sensor", "signal", "severity", "title")

WAKE = {"signal": "board_overheating", "severity": "high",
        "title": "SoC temperature 87.3C reached the 80C threshold"}
BELOW_GATE = {"signal": "disk_pressure", "severity": "medium",
              "title": "disk / is 94% full (threshold 90%)"}


class _RecordingAsk:
    """ask_model_agent stand-in: records every call, answers canned."""

    def __init__(self):
        self.calls = []

    def __call__(self, inf, question, context, max_chars, patterns=None,
                 opener=None, instructions=None, base_dir=None,
                 progress=None):
        self.calls.append({"inf": inf, "question": question,
                           "context": context, "max_chars": max_chars})
        return {"answer": FAKE_ANSWER}


class OracleABFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._cleanup_tmp)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(PI_HEALTH_DIR,
                        os.path.join(self.ext_root, "pi-health"))
        self._legs = 0
        self._reset_wake()

    def _cleanup_tmp(self):
        # The brief runs on a daemon thread; join it before the
        # temp dir goes away (same discipline as the local-signals
        # fixture -- an open brief file breaks cleanup on Windows).
        for th in threading.enumerate():
            if th.name == "oracle-brief":
                th.join(timeout=5)
        last = None
        for _ in range(20):
            try:
                self._tmp.cleanup()
                return
            except OSError as exc:
                last = exc
                time.sleep(0.05)
        if last is not None:
            raise last

    def _reset_wake(self):
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)

    def _cfg(self, mode):
        cfg = {
            "shared_secret": "a11ce" + "0" * 59,
            # Configured in BOTH legs: the deterministic leg must
            # leave it dark, the llm leg must use it.
            "inference": dict(INF),
            "additional_secrets": {"pi-key": PI_SECRET},
            "key_policies": {
                "pi-key": {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                "pi_health": {"enabled": True, "key_id": "pi-key",
                              "weight": 1.0, "profile": {}},
            },
            "extensions_dir": self.ext_root,
        }
        if mode == "deterministic":
            cfg["oracle_mode"] = "deterministic"
        return cfg

    def _briefs(self, base):
        path = os.path.join(base, "oracle-briefs.jsonl")
        deadline = time.time() + 5
        while time.time() < deadline:
            if os.path.exists(path) and not R._LOCAL_WAKE_INFLIGHT:
                break
            time.sleep(0.02)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(ln) for ln in fh if ln.strip()]

    def run_leg(self, mode, scenario):
        """One scenario through ingest + wake under one mode.

        Returns the filed alerts, the filed briefs, the recording
        fake (llm leg), and the must-never-be-called mocks
        (deterministic leg).
        """
        self._reset_wake()
        self._legs += 1
        base = os.path.join(self._tmp.name, f"base-{mode}-{self._legs}")
        os.makedirs(base)
        cfg = self._cfg(mode)
        envelope = E.build_sensor_alert(
            "pi_health", scenario["severity"], scenario["title"],
            key_id="pi-key", signal=scenario["signal"])
        E.drop_local_signal(base, envelope, PI_SECRET)
        ask = _RecordingAsk()
        guarded = {}
        if mode == "deterministic":
            boom = AssertionError("inference layer called in "
                                  "deterministic mode")
            for name in ("ask_model_agent", "ask_model",
                         "_inference_chat", "_default_inference_open"):
                p = unittest.mock.patch.object(R, name, side_effect=boom)
                guarded[name] = p.start()
                self.addCleanup(p.stop)
        else:
            patch = unittest.mock.patch.object(R, "ask_model_agent", ask)
            patch.start()
            self.addCleanup(patch.stop)
        # The guards stay patched past the scan: the brief runs
        # on a daemon thread, and the assertions on their call
        # counts happen in the test, after the briefs are read.
        # addCleanup stops every patch (LIFO restores correctly
        # when the llm leg re-patches ask_model_agent).
        filed = R._scan_local_inbox(cfg, base)
        self.assertEqual(filed, 1)
        return {"alerts": S.load_alerts(base),
                "briefs": self._briefs(base),
                "ask": ask, "guarded": guarded}


class WakeBriefABTest(OracleABFixture):
    """A high-severity signal crosses the wake gate in both modes."""

    def test_briefs_agree_on_substrate(self):
        det = self.run_leg("deterministic", WAKE)
        llm = self.run_leg("llm", WAKE)

        # The ingest filed the identical alert in both modes --
        # the extension and the event are not the variable.
        for leg in (det, llm):
            self.assertEqual(len(leg["alerts"]), 1)
        a_det, a_llm = det["alerts"][0], llm["alerts"][0]
        for key in SUBSTRATE + ("signal_description", "source",
                                "extension"):
            self.assertEqual(a_det[key], a_llm[key], key)
        self.assertEqual(a_det["source"], "local")
        self.assertIn("temperature reached", a_det["signal_description"])

        # Both modes woke and filed exactly one brief.
        for leg in (det, llm):
            self.assertEqual(len(leg["briefs"]), 1)
        b_det, b_llm = det["briefs"][0], llm["briefs"][0]

        # The briefs are about the same event: the substrate the
        # brief record carries is identical across modes and
        # matches the alert both were briefed on.
        for key in SUBSTRATE:
            self.assertEqual(b_det[key], b_llm[key], key)
            self.assertEqual(b_det[key], a_det[key], key)

        # What the mode decided: status, labeling, and whether
        # the inference layer was touched -- nothing else.
        self.assertEqual(b_det["status"], "deterministic")
        self.assertEqual(b_det["mode"], "deterministic")
        for name, mock in det["guarded"].items():
            self.assertEqual(mock.call_count, 0, name)
        self.assertEqual(b_llm["status"], "assessed")
        self.assertNotIn("mode", b_llm)
        self.assertEqual(len(llm["ask"].calls), 1)
        call = llm["ask"].calls[0]
        self.assertEqual(call["inf"]["model"], INF["model"])

        # The facts each path stated on its way agree too: the
        # deterministic note is assembled from severity, sensor,
        # signal, title -- and the question handed to the model
        # in llm mode is assembled from the same facts, plus the
        # declared description both alert records carry.
        for fact in (WAKE["severity"], "pi_health", WAKE["signal"],
                     WAKE["title"]):
            self.assertIn(fact, b_det["assessment"])
            self.assertIn(fact, call["question"])
        self.assertIn(a_det["signal_description"], call["question"])

        # Prose is the model's own and is NOT parity-checked:
        # the llm brief carries the fake's words verbatim, the
        # deterministic brief carries the labeled note.
        self.assertEqual(b_llm["assessment"], FAKE_ANSWER)
        self.assertIn("Deterministic brief (Pi Light)",
                      b_det["assessment"])


class BelowGateABTest(OracleABFixture):
    """A medium signal files in both modes and wakes neither."""

    def test_no_brief_and_no_model_call_in_either_mode(self):
        det = self.run_leg("deterministic", BELOW_GATE)
        llm = self.run_leg("llm", BELOW_GATE)
        for leg in (det, llm):
            self.assertEqual(len(leg["alerts"]), 1)
            self.assertEqual(leg["briefs"], [])
        for key in SUBSTRATE + ("signal_description",):
            self.assertEqual(det["alerts"][0][key],
                             llm["alerts"][0][key], key)
        # Below the gate the llm path never reaches the model
        # either: the gate, not the mode, decides this one.
        self.assertEqual(llm["ask"].calls, [])
        for name, mock in det["guarded"].items():
            self.assertEqual(mock.call_count, 0, name)


if __name__ == "__main__":
    unittest.main()
