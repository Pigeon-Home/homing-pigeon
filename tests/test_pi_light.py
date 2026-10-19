"""Pi Light: the deterministic Oracle and the no-model install.

Andrew's recovered original requirement: an extremely light
Raspberry Pi package a cloud SI can ping into with signed jobs --
the full runner and protocol, but the Oracle runs
deterministically, with no LLM on the box at all. These tests pin
the two halves of that stance:

- Runner: config oracle_mode "deterministic" means no inference
  endpoint is ever called, even when one is configured and even
  when the wake gate fires. The wake brief is the labeled
  deterministic text, assembled from the alert itself. Answers at
  the interactive doors are the deterministic substrate (job
  index, retained records, notable lines) under an honest header.
  The default llm path is unchanged.
- Install: the pi-light profile (auto-detected on a Pi, or named
  with --profile) writes oracle_mode deterministic into the
  config and the installer never touches the Ollama/model path --
  no Ollama install, no model pull, nothing downloaded. Not
  merely "no model selected": the download function is not
  called at all.
"""
import json
import os
import sys
import tempfile
import time
import types
import unittest
import unittest.mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner import install as I  # noqa: E402

INF = {"endpoint": "http://127.0.0.1:11434/v1", "model": "qwen3:1.7b"}


def _record(severity="critical", sensor="host_ids", signal="canary_down",
            title="canary file changed"):
    return {"sensor": sensor, "signal": signal, "severity": severity,
            "title": title}


def _det_cfg(**kw):
    cfg = {"oracle_mode": "deterministic", "inference": dict(INF)}
    cfg.update(kw)
    return cfg


class OracleModeTest(unittest.TestCase):
    def test_mode_parsing(self):
        self.assertEqual(R._oracle_mode({"oracle_mode": "deterministic"}),
                         "deterministic")
        self.assertEqual(R._oracle_mode({"oracle_mode": "llm"}), "llm")
        self.assertEqual(R._oracle_mode({}), "llm")
        self.assertEqual(R._oracle_mode({"oracle_mode": "Deterministic"}),
                         "llm")
        self.assertEqual(R._oracle_mode({"oracle_mode": 7}), "llm")
        self.assertEqual(R._oracle_mode(None), "llm")
        self.assertEqual(R._oracle_mode("deterministic"), "llm")

    def test_inference_config_is_none_in_deterministic_mode(self):
        # Even with a fully configured loopback endpoint, the mode
        # wins: no model path can obtain a config to call with.
        self.assertIsNone(R.inference_config(_det_cfg()))

    def test_inference_config_unchanged_in_llm_mode(self):
        inf = R.inference_config({"inference": dict(INF)})
        self.assertIsNotNone(inf)
        self.assertEqual(inf["model"], "qwen3:1.7b")
        self.assertEqual(inf["endpoint"], "http://127.0.0.1:11434/v1")

    def test_ask_paths_reject_without_a_model_call(self):
        # answer_queries' ask op resolves its config through
        # inference_config, so in deterministic mode it rejects as
        # unconfigured and ask_model is never reached.
        with unittest.mock.patch.object(
                R, "ask_model",
                side_effect=AssertionError("model called")) as ask:
            answers, _spent = R.answer_queries(
                [{"op": "ask", "question": "what ran?"}],
                {"stdout": "x"}, [], 8, cfg=_det_cfg(), base_dir="/none")
        self.assertEqual(answers,
                         [{"op": "ask", "rejected": "inference_unconfigured"}])
        ask.assert_not_called()

    def test_mode_flip_is_a_live_config_key(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            cfg = {"oracle_mode": "llm"}
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh)
            state = {"mtime": 0}
            changed = R.reload_hot_config(cfg, path, state)
            self.assertNotIn("oracle_mode", changed)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"oracle_mode": "deterministic"}, fh)
            bumped = os.path.getmtime(path) + 5
            os.utime(path, (bumped, bumped))
            changed = R.reload_hot_config(cfg, path, state)
            self.assertIn("oracle_mode", changed)
            self.assertEqual(cfg["oracle_mode"], "deterministic")
            self.assertIsNone(R.inference_config(
                dict(cfg, inference=dict(INF))))

    def test_invalid_mode_value_is_not_reloaded(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"oracle_mode": 42}, fh)
            cfg = {}
            changed = R.reload_hot_config(cfg, path, {"mtime": 0})
            self.assertNotIn("oracle_mode", changed)
            self.assertNotIn("oracle_mode", cfg)


class StartupReportTest(unittest.TestCase):
    def test_one_line_in_deterministic_mode_none_in_llm_mode(self):
        lines = []
        with unittest.mock.patch.object(R, "log",
                                        lambda msg, *a, **k: lines.append(msg)):
            R._report_oracle_mode(_det_cfg())
            R._report_oracle_mode({"inference": dict(INF)})
            R._report_oracle_mode({})
        self.assertEqual(len(lines), 1)
        self.assertIn("deterministic mode (Pi Light)", lines[0])
        self.assertIn("no local model", lines[0])


class DeterministicBriefTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = self._tmp.name
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)

    def _brief_lines(self):
        path = os.path.join(self.base, "oracle-briefs.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln.strip()]

    def _no_model_patches(self):
        boom = AssertionError("inference layer called in Pi Light mode")
        return (
            unittest.mock.patch.object(R, "ask_model_agent",
                                       side_effect=boom),
            unittest.mock.patch.object(R, "ask_model", side_effect=boom),
            unittest.mock.patch.object(R, "_inference_chat",
                                       side_effect=boom),
            unittest.mock.patch.object(R, "_default_inference_open",
                                       side_effect=boom),
        )

    def test_wake_brief_is_labeled_deterministic_and_calls_no_model(self):
        patches = self._no_model_patches()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        brief = R._oracle_brief(_det_cfg(), self.base, _record())
        self.assertEqual(brief["status"], "deterministic")
        self.assertEqual(brief["mode"], "deterministic")
        self.assertIn("Deterministic brief (Pi Light)",
                      brief["assessment"])
        # Assembled from the alert itself: severity, sensor, signal,
        # title all ride along.
        for fact in ("critical", "host_ids", "canary_down",
                     "canary file changed"):
            self.assertIn(fact, brief["assessment"])
        for p in patches:
            p.stop()
        lines = self._brief_lines()
        self.assertEqual(len(lines), 1)
        filed = json.loads(lines[0])
        self.assertEqual(filed["status"], "deterministic")
        self.assertEqual(filed["assessment"], brief["assessment"])

    def test_wake_gate_fires_and_still_calls_no_model(self):
        patches = self._no_model_patches()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        def run_sync(cfg, base_dir, record):
            try:
                R._oracle_brief(cfg, base_dir, record)
            finally:
                R._wake_gate_release()
            return None

        with unittest.mock.patch.object(R, "_start_brief_thread",
                                        run_sync):
            self.assertTrue(R._maybe_wake_oracle(
                _det_cfg(local_wake_cooldown_sec=900), self.base,
                _record()))
        for p in patches:
            p.stop()
        lines = self._brief_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["status"], "deterministic")

    def test_llm_mode_still_assesses_with_the_model(self):
        # The default path is untouched: configured inference in
        # llm mode assesses as before.
        def fake_ask(inf, question, context, max_chars, patterns=None,
                     opener=None, instructions=None, base_dir=None,
                     progress=None):
            return {"answer": "Assessment from the model."}

        with unittest.mock.patch.object(R, "ask_model_agent", fake_ask):
            brief = R._oracle_brief({"inference": dict(INF)}, self.base,
                                    _record())
        self.assertEqual(brief["status"], "assessed")
        self.assertEqual(brief["assessment"], "Assessment from the model.")
        self.assertNotIn("mode", brief)


class DeterministicAnswerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = self._tmp.name

    def test_empty_box_answer_is_the_record(self):
        text = R._deterministic_oracle_answer(_det_cfg(), self.base)
        self.assertIn("Deterministic Oracle (Pi Light)", text)
        self.assertIn("no local model", text)
        self.assertIn("(no job output retained yet)", text)

    def test_answer_carries_index_and_notable_lines(self):
        retained = os.path.join(self.base, "retained")
        os.makedirs(retained)
        rec = {
            "kind": "exec",
            "exit_code": 0,
            "saved_at": 1760000000,
            "script": "cat /etc/shadow",
            "stdout": "job output here",
            "stderr": "",
        }
        with open(os.path.join(retained, "job123.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(rec, fh)
        text = R._deterministic_oracle_answer(_det_cfg(), self.base)
        self.assertIn("Job index", text)
        self.assertIn("job job123 (exec, exit code 0", text)
        # The deterministic notable finding survives un-narrated.
        self.assertIn("notable: SUSPICIOUS ACCESS -- job job123", text)

    def test_cli_answers_deterministically(self):
        cfg = {"oracle_mode": "deterministic", "base_dir": self.base}
        asked = iter(["what ran?", "/quit"])
        printed = []
        with unittest.mock.patch.object(
                R, "ask_model_agent",
                side_effect=AssertionError("model called")):
            rc = R.oracle_cli(cfg, cfg_path=os.path.join(self.base,
                                                         "config.json"),
                              input_fn=lambda prompt="": next(asked),
                              print_fn=printed.append)
        self.assertEqual(rc, 0)
        blob = "\n".join(printed)
        self.assertIn("Oracle mode: deterministic (Pi Light)", blob)
        self.assertIn("Deterministic Oracle (Pi Light)", blob)


def _fake_args(**kw):
    args = types.SimpleNamespace(
        shared_secret=None, additional_secret=[], profile=None,
        no_profile=False, inference_model=None, faster=False,
        no_inference=False, instructions=None, instructions_add=None)
    for k, v in kw.items():
        setattr(args, k, v)
    return args


class InstallPiLightTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cfg_path = os.path.join(self._tmp.name, "config.json")

    def _seed_cfg(self, data=None):
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(data or {}, fh)

    def _read_cfg(self):
        with open(self.cfg_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_profile_writes_deterministic_mode(self):
        self._seed_cfg()
        I.apply_profile(self.cfg_path, "pi-light")
        cfg = self._read_cfg()
        self.assertEqual(cfg["oracle_mode"], "deterministic")
        self.assertEqual(cfg["profile"], "pi-light")
        self.assertIn("/etc/shadow", cfg["protected_paths"])
        self.assertNotIn("inference", cfg)

    def test_former_name_is_the_same_light_profile(self):
        self._seed_cfg()
        I.apply_profile(self.cfg_path, "raspberry-pi-home")
        cfg = self._read_cfg()
        self.assertEqual(cfg["oracle_mode"], "deterministic")
        self.assertEqual(I.profile_oracle_mode("raspberry-pi-home"),
                         "deterministic")
        self.assertEqual(I.profile_oracle_mode("pi-light"),
                         "deterministic")
        self.assertIsNone(I.profile_oracle_mode("password-only"))
        self.assertIsNone(I.profile_oracle_mode("no-such-profile"))

    def test_pi_profiles_select_no_model(self):
        for name in ("pi-light", "raspberry-pi-home"):
            spec = I.BUILTIN_PROFILES[name]
            self.assertNotIn("inference_model", spec)
            self.assertNotEqual(I.inference_model_for(name),
                                "llama3.2:1b")
            self.assertEqual(I.inference_model_for(name),
                             I.DEFAULT_INFERENCE_MODEL)

    def test_skip_logic(self):
        self.assertTrue(I._pi_light_skip(_fake_args(), "pi-light"))
        self.assertTrue(I._pi_light_skip(_fake_args(),
                                         "raspberry-pi-home"))
        self.assertFalse(I._pi_light_skip(_fake_args(), "password-only"))
        # The owner's explicit choices override the light default.
        self.assertFalse(I._pi_light_skip(
            _fake_args(inference_model="qwen3:1.7b"), "pi-light"))
        self.assertFalse(I._pi_light_skip(
            _fake_args(faster=True), "pi-light"))

    def _fresh(self, args):
        with unittest.mock.patch.object(
                I, "install_ollama_and_model",
                return_value=True) as ollama, \
             unittest.mock.patch.object(sys.stdin, "isatty",
                                        return_value=False):
            result = I._setup_fresh_config(args, self.cfg_path)
        return result, ollama

    def test_fresh_pi_install_downloads_nothing(self):
        self._seed_cfg()
        (ok, model, light), ollama = self._fresh(
            _fake_args(profile="pi-light"))
        # The whole point: the download path is never invoked.
        ollama.assert_not_called()
        self.assertFalse(ok)
        self.assertIsNone(model)
        self.assertTrue(light)
        cfg = self._read_cfg()
        self.assertEqual(cfg["oracle_mode"], "deterministic")
        self.assertNotIn("inference", cfg)

    def test_fresh_detected_pi_also_downloads_nothing(self):
        self._seed_cfg()
        with unittest.mock.patch.object(
                I, "detect_default_profile", return_value="pi-light"):
            (ok, model, light), ollama = self._fresh(_fake_args())
        ollama.assert_not_called()
        self.assertTrue(light)
        self.assertEqual(self._read_cfg()["oracle_mode"],
                         "deterministic")

    def test_fresh_default_install_still_sets_up_a_model(self):
        self._seed_cfg()
        (ok, model, light), ollama = self._fresh(
            _fake_args(profile="password-only"))
        ollama.assert_called_once()
        self.assertEqual(ollama.call_args[0][1],
                         I.DEFAULT_INFERENCE_MODEL)
        self.assertFalse(ollama.call_args[0][2])
        self.assertTrue(ok)
        self.assertFalse(light)
        self.assertNotEqual(self._read_cfg().get("oracle_mode"),
                            "deterministic")

    def test_inference_only_short_circuits_for_pi_light(self):
        self._seed_cfg()
        argv = ["install", "--dir", self._tmp.name,
                "--config", self.cfg_path, "--inference-only",
                "--profile", "pi-light"]
        with unittest.mock.patch.object(
                I, "install_ollama_and_model", return_value=True) as ollama, \
             unittest.mock.patch.object(sys, "argv", argv):
            rc = I.main()
        self.assertEqual(rc, 0)
        ollama.assert_not_called()

    def test_example_config_documents_the_mode(self):
        path = os.path.join(REPO, "runner", "config.example.json")
        with open(path, encoding="utf-8") as fh:
            example = json.load(fh)
        self.assertEqual(example["oracle_mode"], "llm")
        note = example["_oracle_mode"]
        self.assertIn("deterministic", note)
        self.assertIn("Pi Light", note)
        self.assertIn("no model is installed or ever called", note)


if __name__ == "__main__":
    unittest.main()
