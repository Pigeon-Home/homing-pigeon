#!/usr/bin/env python3
"""Queue A: `training_watch.main`'s live and delivery
legs (coverage run 40183585961: 10 lines on Linux).

The samples-mode tests drive decide() from files; the
live path never ran: the reader state carried in the
state file, read_live against a real training log, and
the advanced reader stored back after the pass -- the
tail -f bookkeeping that keeps a long training run from
being re-read (and re-alerted) from the top on every
poll. The delivery legs are the senses' shared
discipline: not set up is exit 2, and a partial
delivery is exit 2 with the state deliberately NOT
saved.
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

EXT_DIR = os.path.join(REPO, "runner", "extensions",
                       "training-watch")
NOW = time.time()


def _load():
    spec = importlib.util.spec_from_file_location(
        "training_watch_main",
        os.path.join(EXT_DIR, "training_watch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TW = _load()


class MainLiveAndDeliveryTest(unittest.TestCase):
    def _main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = TW.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def _write(self, path, payload):
        mode = "w"
        with open(path, mode, encoding="utf-8") as fh:
            if isinstance(payload, str):
                fh.write(payload)
            else:
                json.dump(payload, fh)
        return path

    def _manifest(self, d):
        with open(os.path.join(EXT_DIR, "extension.json"),
                  encoding="utf-8") as fh:
            manifest = json.load(fh)
        return self._write(os.path.join(d, "extension.json"),
                           manifest)

    def test_the_live_read_advances_and_stores_the_reader(self):
        with tempfile.TemporaryDirectory() as d:
            log = self._write(
                os.path.join(d, "train.log"),
                "epoch 1 loss 2.50\n"
                "epoch 2 loss 2.10\n")
            manifest = self._manifest(d)
            state = os.path.join(d, "state.json")
            rc, out, _err = self._main(
                ["--manifest", manifest, "--state", state,
                 "--log", log])
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")
            with open(state, encoding="utf-8") as fh:
                saved = json.load(fh)
            reader = saved["_reader"][log]
            self.assertEqual(reader["offset"],
                             os.path.getsize(log))
            self.assertEqual(saved["lines_total"], 2)
            # A second pass over the same state reads
            # nothing new: the reader threaded through.
            rc, out, _err = self._main(
                ["--manifest", manifest, "--state", state,
                 "--log", log])
            self.assertEqual(rc, 0)
            with open(state, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["lines_total"], 2)

    def _crash_samples(self, d):
        return self._write(
            os.path.join(d, "samples.json"),
            {"now": NOW, "gpu": [], "run_alive": True,
             "checkpoints": [],
             "log_lines": [{"ts": NOW, "line":
                            "Traceback (most recent call "
                            "last):"}]})

    def test_local_delivery_not_set_up_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _out, err = self._main(
                ["--manifest", self._manifest(d),
                 "--state", os.path.join(d, "state.json"),
                 "--samples", self._crash_samples(d),
                 "--local-dir", d,
                 "--secret-env", "HP_TW_UNSET_SECRET"])
            self.assertEqual(rc, 2)
            self.assertIn("no signing secret", err)

    def test_a_partial_delivery_saves_no_state(self):
        with tempfile.TemporaryDirectory() as d:
            blocker = self._write(os.path.join(d, "blocker"),
                                  {"x": 1})
            state = os.path.join(d, "state.json")
            saved_env = os.environ.get(
                "HOMING_PIGEON_SENSOR_SECRET")
            os.environ["HOMING_PIGEON_SENSOR_SECRET"] = \
                "tw-test-secret-0123456789abcdef"
            try:
                rc, _out, err = self._main(
                    ["--manifest", self._manifest(d),
                     "--state", state,
                     "--samples", self._crash_samples(d),
                     "--local-dir", blocker])
            finally:
                if saved_env is None:
                    os.environ.pop(
                        "HOMING_PIGEON_SENSOR_SECRET", None)
                else:
                    os.environ["HOMING_PIGEON_SENSOR_SECRET"] = \
                        saved_env
            self.assertEqual(rc, 2)
            self.assertIn("not delivered; state not saved", err)
            self.assertFalse(os.path.exists(state))


if __name__ == "__main__":
    unittest.main(verbosity=2)
