"""The Training Watch example: a sense for ML training runs.

Pins runner/extensions/training-watch/ the way
test_watchers.py pins the watcher examples: the manifest
through the real extension loader, the pure decide() core
over fixture readings (every declared signal firing, its
restraint cases staying quiet, the checkpoint stabilization
rule, the crash-episode dedupe, both stall evidences),
read_live() against fixture files, and one end-to-end --
producer into the local inbox, the real ingest files the
alert, and the high-severity crash signal wakes the gate
and files a brief.

No live network, no live GPU: readings are fixtures, and
the end-to-end config has no inference, so the wake brief
is the deterministic fallback.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner.oracle import senses as S  # noqa: E402
from runner.ops import extensions as E  # noqa: E402

TW_DIR = os.path.join(REPO, "runner", "extensions", "training-watch")

DEFAULT_SECRET = "b109f3bbbc244eb82441917ed06d618b" + \
    "9008dd09b3befd1b078a64781ac2f3e5"
TW_SECRET = "2b3c4d5e6f708192a3b4c5d6e7f8091a" + \
    "3b4c5d6e7f8091a2b3c4d5e6f708192a3"

T0 = 1_700_000_000.0


def _load():
    spec = importlib.util.spec_from_file_location(
        "training_watch_example",
        os.path.join(TW_DIR, "training_watch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TW = _load()


def _manifest():
    with open(os.path.join(TW_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _gpu(temp=None, used=None, total=1000.0, util=99.0):
    if temp is None and used is None:
        return None
    return {"temp_c": 40.0 if temp is None else temp,
            "mem_used_mb": 100.0 if used is None else used,
            "mem_total_mb": total, "util_pct": util}


def _readings(now, gpu=None, lines=(), alive=None, ckpts=()):
    return {"now": now, "gpu": gpu, "run_alive": alive,
            "log_lines": [{"ts": ts, "line": text}
                          for ts, text in lines],
            "checkpoints": list(ckpts)}


def _run(passes, manifest=None):
    """Feed readings through decide, threading state."""
    manifest = manifest or _manifest()
    state = {}
    alerts = []
    for readings in passes:
        fired, state = TW.decide(readings, manifest, state)
        alerts.extend(fired)
    return alerts, state


def _ckpt(name="checkpoint-400", size=1000, mtime=T0):
    return {"name": name, "size": size, "mtime": mtime}


def _signals(alerts):
    return [a["signal"] for a in alerts]


class TrainingWatchManifestTest(unittest.TestCase):
    def test_manifest_is_valid_through_the_real_loader(self):
        clean = E.parse_manifest(_manifest())
        self.assertEqual(clean["name"], "training_watch")
        self.assertEqual(clean["kind"], "sense")
        self.assertEqual(clean["api_version"], 1)
        self.assertIsNone(E.api_refusal(clean))
        self.assertEqual(
            [s["name"] for s in clean["signals"]],
            ["checkpoint_arrived", "training_stalled", "run_crashed",
             "gpu_overheating", "gpu_memory_pressure"])
        self.assertIn("poll_interval_sec", clean["tunables"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(TW_DIR, os.path.join(d, "training-watch"))
            registry, problems = E.load_extensions(d)
        self.assertEqual(problems, [])
        self.assertIn("training_watch", registry)


class CheckpointTest(unittest.TestCase):
    def test_checkpoint_files_once_when_it_settles(self):
        alerts, _state = _run([
            _readings(T0, ckpts=[_ckpt()]),
            _readings(T0 + 300, ckpts=[_ckpt()]),
            _readings(T0 + 600, ckpts=[_ckpt()]),
        ])
        self.assertEqual(_signals(alerts), ["checkpoint_arrived"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "info")
        self.assertEqual(alert["sensor"], "training_watch")
        self.assertEqual(alert["detail"]["name"], "checkpoint-400")
        self.assertEqual(alert["detail"]["size_bytes"], 1000)

    def test_growing_checkpoint_never_files_until_it_stops(self):
        alerts, _state = _run([
            _readings(T0, ckpts=[_ckpt(size=1000, mtime=T0)]),
            _readings(T0 + 300, ckpts=[_ckpt(size=2000, mtime=T0 + 300)]),
            _readings(T0 + 600, ckpts=[_ckpt(size=2000, mtime=T0 + 300)]),
        ])
        # Recorded, still growing, then settled: exactly one
        # alert, on the settling pass.
        self.assertEqual(_signals(alerts), ["checkpoint_arrived"])

    def test_overwritten_checkpoint_must_settle_again(self):
        alerts, _state = _run([
            _readings(T0, ckpts=[_ckpt()]),
            _readings(T0 + 300, ckpts=[_ckpt()]),          # files
            _readings(T0 + 600, ckpts=[_ckpt(size=4000,
                                             mtime=T0 + 600)]),
            _readings(T0 + 900, ckpts=[_ckpt(size=4000,
                                             mtime=T0 + 600)]),
        ])
        self.assertEqual(_signals(alerts),
                         ["checkpoint_arrived", "checkpoint_arrived"])
        self.assertEqual(alerts[1]["detail"]["size_bytes"], 4000)

    def test_vanished_checkpoint_is_dropped_quietly(self):
        alerts, state = _run([
            _readings(T0, ckpts=[_ckpt(), _ckpt("model.pt", 50, T0)]),
            _readings(T0 + 300, ckpts=[_ckpt("model.pt", 50, T0)]),
        ])
        self.assertEqual(_signals(alerts), ["checkpoint_arrived"])
        self.assertEqual(alerts[0]["detail"]["name"], "model.pt")
        self.assertNotIn("checkpoint-400", state["checkpoints"])


class GpuTest(unittest.TestCase):
    def test_overheating_fires_high_once_and_refires_after_clear(self):
        alerts, _state = _run([
            _readings(T0, gpu=_gpu(temp=91.0)),
            _readings(T0 + 300, gpu=_gpu(temp=91.0)),
            _readings(T0 + 600, gpu=_gpu(temp=60.0)),
            _readings(T0 + 900, gpu=_gpu(temp=92.0)),
        ])
        self.assertEqual(_signals(alerts),
                         ["gpu_overheating", "gpu_overheating"])
        self.assertEqual(alerts[0]["severity"], "high")
        self.assertEqual(alerts[0]["detail"]["temp_c"], 91.0)

    def test_gpu_threshold_boundaries(self):
        alerts, _state = _run([_readings(T0, gpu=_gpu(temp=84.9))])
        self.assertEqual(alerts, [])
        alerts, _state = _run([_readings(T0, gpu=_gpu(temp=85.0))])
        self.assertEqual(_signals(alerts), ["gpu_overheating"])

    def test_memory_pressure_fires_medium_at_the_limit(self):
        alerts, _state = _run([
            _readings(T0, gpu=_gpu(used=949.0)),
            _readings(T0 + 300, gpu=_gpu(used=949.0)),
        ])
        self.assertEqual(alerts, [])
        # At the limit it fires; the same reading stays
        # quiet; a moved reading files again (the pi-health
        # discipline: once per distinct reading).
        alerts, _state = _run([
            _readings(T0, gpu=_gpu(used=950.0)),
            _readings(T0 + 300, gpu=_gpu(used=950.0)),
            _readings(T0 + 600, gpu=_gpu(used=960.0)),
        ])
        self.assertEqual(_signals(alerts),
                         ["gpu_memory_pressure",
                          "gpu_memory_pressure"])
        self.assertEqual(alerts[0]["severity"], "medium")
        self.assertEqual(alerts[0]["detail"]["mem_used_pct"], 95.0)
        self.assertEqual(alerts[1]["detail"]["mem_used_pct"], 96.0)

    def test_no_gpu_source_never_votes(self):
        alerts, _state = _run([
            _readings(T0 + i * 300) for i in range(4)])
        self.assertEqual(alerts, [])


class CrashTest(unittest.TestCase):
    def test_traceback_fires_high_with_marker_and_last_line(self):
        alerts, _state = _run([_readings(T0, lines=[
            (T0, "step 10 loss: 1.0"),
            (T0, "Traceback (most recent call last):"),
            (T0, '  File "train.py", line 9, in <module>'),
            (T0, "ValueError: bad batch"),
        ])])
        self.assertEqual(_signals(alerts), ["run_crashed"])
        alert = alerts[0]
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["detail"]["marker"], "Traceback")
        self.assertEqual(alert["detail"]["last_line"],
                         "ValueError: bad batch")

    def test_each_marker_fires(self):
        cases = [
            ("CUDA out of memory",
             "RuntimeError: CUDA out of memory. Tried to allocate"),
            # The line above carries two markers; use distinct
            # lines per case below instead.
        ]
        del cases
        for marker, line in [
                ("CUDA out of memory",
                 "torch.OutOfMemoryError: CUDA out of memory"),
                ("NCCL error",
                 "NCCL error: unhandled system error, timeout"),
                ("RuntimeError",
                 "RuntimeError: expected scalar type Float")]:
            with self.subTest(marker=marker):
                alerts, _state = _run([_readings(T0, lines=[
                    (T0, "step 3 loss: 2.0"), (T0, line)])])
                crashed = [a for a in alerts
                           if a["signal"] == "run_crashed"]
                self.assertTrue(crashed)
                self.assertEqual(crashed[0]["detail"]["marker"],
                                 marker)

    def test_repeated_dump_in_one_window_files_once(self):
        dump = [(T0, "Traceback (most recent call last):")] * 30
        alerts, _state = _run([_readings(T0, lines=dump)])
        self.assertEqual(_signals(alerts), ["run_crashed"])

    def test_same_marker_in_a_later_window_files_again(self):
        passes = [_readings(T0, lines=[
            (T0, "Traceback (most recent call last):")])]
        filler = [(T0, f"step {i} ok") for i in range(120)]
        passes.append(_readings(T0 + 300, lines=filler))
        passes.append(_readings(T0 + 600, lines=[
            (T0 + 600, "Traceback (most recent call last):")]))
        alerts, _state = _run(passes)
        self.assertEqual(_signals(alerts),
                         ["run_crashed", "run_crashed"])

    def test_benign_log_never_files_a_crash(self):
        alerts, _state = _run([_readings(T0, lines=[
            (T0, "step 1 loss: 2.31"),
            (T0, "saved checkpoint, no traceback in this run"),
            (T0, "epoch done, runtime nominal"),
        ])])
        # "runtime" lowercase and "no traceback" lowercase do
        # not match the case-sensitive markers.
        self.assertNotIn("run_crashed", _signals(alerts))


class StallTest(unittest.TestCase):
    def test_quiet_after_growth_fires_once_per_episode(self):
        alerts, _state = _run([
            _readings(T0, lines=[(T0, "step 1 loss: 2.3")]),
            _readings(T0 + 1801),
            _readings(T0 + 3600),
            _readings(T0 + 3601, lines=[(T0 + 3600,
                                          "step 2 loss: 2.1")]),
            _readings(T0 + 3601 + 1801),
        ])
        stalled = [a for a in alerts
                   if a["signal"] == "training_stalled"]
        self.assertEqual(len(stalled), 2)
        self.assertEqual(stalled[0]["severity"], "medium")
        self.assertEqual(stalled[0]["detail"]["evidence"],
                         "no_log_growth")
        self.assertEqual(stalled[0]["detail"]["silent_sec"], 1801)

    def test_never_started_log_never_fires(self):
        alerts, _state = _run([
            _readings(T0 + i * 3600) for i in range(4)])
        self.assertEqual(alerts, [])

    def test_first_sight_of_an_old_log_does_not_fire(self):
        alerts, _state = _run([
            _readings(T0, lines=[(T0 - 7200, "step 9 loss: 0.4")]),
        ])
        self.assertEqual(alerts, [])
        # Once the watcher has a pass of history with that
        # log, its silence is judged like any other.
        alerts, _state = _run([
            _readings(T0, lines=[(T0 - 7200, "step 9 loss: 0.4")]),
            _readings(T0 + 60),
        ])
        self.assertEqual(_signals(alerts), ["training_stalled"])

    def test_growing_log_never_stalls(self):
        passes = [_readings(T0 + i * 3600,
                            lines=[(T0 + i * 3600,
                                    f"step {i} loss: 1.0")])
                  for i in range(3)]
        alerts, _state = _run(passes)
        self.assertEqual(
            [a for a in alerts
             if a["detail"].get("evidence") == "no_log_growth"], [])

    def test_finished_run_is_not_a_stall(self):
        alerts, _state = _run([
            _readings(T0, alive=False,
                      lines=[(T0, "step 1 loss: 2.3")]),
            _readings(T0 + 7200, alive=False),
        ])
        self.assertEqual(alerts, [])


class LossStallTest(unittest.TestCase):
    def _loss_pass(self, now, values):
        return _readings(now, lines=[
            (now, f"step loss: {v}") for v in values])

    def test_flat_losses_fire_once_labeled_parsed(self):
        alerts, _state = _run([
            self._loss_pass(T0, [0.50, 0.50, 0.51, 0.50, 0.50]),
            self._loss_pass(T0 + 300, [0.50]),
            self._loss_pass(T0 + 600, [0.49]),
        ])
        stalled = [a for a in alerts
                   if a["signal"] == "training_stalled"]
        self.assertEqual(len(stalled), 1)
        detail = stalled[0]["detail"]
        self.assertEqual(detail["evidence"], "loss_flat")
        self.assertEqual(detail["source"], "parsed_from_log")
        self.assertEqual(detail["points"], 5)

    def test_worsening_losses_fire(self):
        alerts, _state = _run([
            self._loss_pass(T0, [0.40, 0.42, 0.45, 0.47, 0.50])])
        self.assertEqual(_signals(alerts), ["training_stalled"])

    def test_improving_losses_never_fire_and_rearm(self):
        alerts, _state = _run([
            self._loss_pass(T0, [1.0, 1.0, 1.0, 1.0, 1.0]),
            self._loss_pass(T0 + 300, [0.5]),
            self._loss_pass(T0 + 600, [0.5, 0.5, 0.5, 0.5]),
        ])
        stalled = [a for a in alerts
                   if a["signal"] == "training_stalled"]
        # Flat window fires; the improving point re-arms; the
        # new flat window at the lower loss fires again.
        self.assertEqual(len(stalled), 2)

    def test_too_few_losses_and_unparseable_logs_never_fire(self):
        alerts, _state = _run([
            self._loss_pass(T0, [0.5, 0.5, 0.5])])
        self.assertEqual(alerts, [])
        alerts, _state = _run([_readings(T0, lines=[
            (T0, "epoch 1 | acc 0.91 | lr 0.001"),
            (T0, "epoch 2 | acc 0.91 | lr 0.001"),
            (T0, "epoch 3 | acc 0.91 | lr 0.001"),
            (T0, "epoch 4 | acc 0.91 | lr 0.001"),
            (T0, "epoch 5 | acc 0.91 | lr 0.001"),
        ])])
        self.assertEqual(
            [a for a in alerts
             if a["detail"].get("evidence") == "loss_flat"], [])

    def test_loss_shapes_parsed_and_val_loss_ignored(self):
        _alerts, state = _run([_readings(T0, lines=[
            (T0, "loss: 0.5"),
            (T0, "step 2 loss=0.25"),
            (T0, "train_loss: 1.2e-3 done"),
            (T0, "val_loss: 9.9"),
            (T0, "no numbers here"),
        ])])
        self.assertEqual(state["losses"], [0.5, 0.25, 0.0012])


class ReadLiveTest(unittest.TestCase):
    def _manifest_for(self, log=None, run_dir=None):
        manifest = _manifest()
        tunables = dict(manifest["tunables"])
        if log is not None:
            tunables["log_path"] = log
        if run_dir is not None:
            tunables["run_dir"] = run_dir
        manifest["tunables"] = tunables
        return manifest

    def test_tails_incrementally_and_scans_checkpoints(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "train.log")
            with open(log, "w", encoding="utf-8") as fh:
                fh.write("step 1 loss: 2.0\nstep 2 loss: 1.9\n")
            run_dir = os.path.join(d, "run")
            os.makedirs(os.path.join(run_dir, "checkpoints"))
            for rel, size in (("checkpoint-100", 10),
                              ("notes.txt", 5),
                              (os.path.join("checkpoints",
                                            "model.pt"), 20)):
                with open(os.path.join(run_dir, rel), "wb") as fh:
                    fh.write(b"x" * size)
            manifest = self._manifest_for(log, run_dir)
            first = TW.read_live(manifest)
            texts = [ln["line"] for ln in first["log_lines"]]
            self.assertEqual(texts, ["step 1 loss: 2.0",
                                     "step 2 loss: 1.9"])
            names = sorted(c["name"] for c in first["checkpoints"])
            self.assertEqual(names, ["checkpoint-100",
                                     os.path.join("checkpoints",
                                                  "model.pt")])
            with open(log, "a", encoding="utf-8") as fh:
                fh.write("step 3 loss: 1.8\n")
            second = TW.read_live(manifest, first["_reader"])
            self.assertEqual([ln["line"] for ln in
                              second["log_lines"]],
                             ["step 3 loss: 1.8"])
            self.assertIsInstance(second["gpu"], (dict, type(None)))

    def test_missing_sources_read_empty(self):
        manifest = self._manifest_for(
            log=os.path.join(tempfile.gettempdir(),
                             "training-watch-no-such.log"),
            run_dir=os.path.join(tempfile.gettempdir(),
                                 "training-watch-no-such-dir"))
        readings = TW.read_live(manifest)
        self.assertEqual(readings["log_lines"], [])
        self.assertEqual(readings["checkpoints"], [])
        self.assertIsNone(readings["run_alive"])

    def test_status_command_reports_liveness(self):
        manifest = _manifest()
        manifest["tunables"] = dict(manifest["tunables"],
                                    log_path="", run_dir="")
        manifest["tunables"]["status_cmd"] = \
            f'"{sys.executable}" -c "pass"'
        self.assertTrue(TW.read_live(manifest)["run_alive"])
        manifest["tunables"]["status_cmd"] = \
            f'"{sys.executable}" -c "import sys; sys.exit(3)"'
        self.assertFalse(TW.read_live(manifest)["run_alive"])


class ProducerMainTest(unittest.TestCase):
    def test_samples_mode_files_the_settling_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            state = os.path.join(d, "state.json")
            out_text = []
            for i, now in enumerate((T0, T0 + 300)):
                path = os.path.join(d, f"s{i}.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(_readings(now, ckpts=[_ckpt()]), fh)
                out = io.StringIO()
                with redirect_stdout(out):
                    rc = TW.main(["--samples", path,
                                  "--state", state])
                self.assertEqual(rc, 0)
                out_text.append(out.getvalue())
            self.assertEqual(out_text[0], "")
            printed = [json.loads(ln) for ln in
                       out_text[1].splitlines() if ln.strip()]
            self.assertEqual([p["signal"] for p in printed],
                             ["checkpoint_arrived"])

    def test_unreadable_manifest_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                TW.main(["--manifest", os.path.join(d, "nope.json"),
                         "--state", os.path.join(d, "s.json")]), 2)

    def test_garbage_never_raises(self):
        alerts, _state = TW.decide(None, _manifest(),
                                   {"checkpoints": [], "losses": "x"})
        self.assertEqual(alerts, [])
        alerts, _state = TW.decide(
            _readings(T0, gpu={"temp_c": "hot"},
                      lines=[(T0, None)],
                      ckpts=[{"name": 5}, "junk"]),
            _manifest(), None)
        self.assertEqual(alerts, [])


# ---------------------------------------------------------------------
# End to end

class TrainingWatchEndToEndTest(unittest.TestCase):
    folder = "training-watch"
    sensor = "training_watch"
    secret = TW_SECRET
    key_id = "train-key"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self._tmp.name, "base")
        os.makedirs(self.base)
        self.ext_root = os.path.join(self._tmp.name, "exts")
        os.makedirs(self.ext_root)
        shutil.copytree(os.path.join(REPO, "runner", "extensions",
                                     self.folder),
                        os.path.join(self.ext_root, self.folder))
        self.cfg = {
            "shared_secret": DEFAULT_SECRET,
            "additional_secrets": {self.key_id: self.secret},
            "key_policies": {
                self.key_id: {"allowed_kinds": ["sensor_alert"]},
            },
            "sensors": {
                self.sensor: {"enabled": True, "key_id": self.key_id,
                              "weight": 1.0, "profile": {}},
            },
            "extensions_dir": self.ext_root,
        }
        R._LOCAL_WAKE_LAST.clear()
        R._wake_gate_release()
        self.addCleanup(R._LOCAL_WAKE_LAST.clear)
        self.addCleanup(R._wake_gate_release)
        self.state_path = os.path.join(self._tmp.name, "state.json")

    def tearDown(self):
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

    def brief_lines(self):
        path = os.path.join(self.base, "oracle-briefs.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [ln for ln in fh.read().splitlines() if ln.strip()]

    def test_crash_files_and_wakes_a_brief(self):
        samples = os.path.join(self._tmp.name, "samples.json")
        with open(samples, "w", encoding="utf-8") as fh:
            json.dump(_readings(T0, lines=[
                (T0, "step 10 loss: 1.0"),
                (T0, "Traceback (most recent call last):"),
                (T0, "ValueError: bad batch"),
            ]), fh)
        env = {"HOMING_PIGEON_SENSOR_SECRET": self.secret}
        with unittest.mock.patch.dict(os.environ, env):
            rc = TW.main(["--samples", samples,
                          "--local-dir", self.base,
                          "--key-id", self.key_id,
                          "--state", self.state_path])
        self.assertEqual(rc, 0)
        inbox = os.path.join(self.base, "local-inbox")
        self.assertEqual(len(os.listdir(inbox)), 1)
        self.assertEqual(R._scan_local_inbox(self.cfg, self.base), 1)
        recs = S.load_alerts(self.base)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["sensor"], "training_watch")
        self.assertEqual(rec["source"], "local")
        self.assertEqual(rec["extension"], "training_watch")
        self.assertEqual(rec["signal"], "run_crashed")
        self.assertEqual(rec["severity"], "high")
        deadline = time.time() + 5.0
        lines = self.brief_lines()
        while len(lines) < 1 and time.time() < deadline:
            time.sleep(0.05)
            lines = self.brief_lines()
        self.assertEqual(len(lines), 1)
        brief = json.loads(lines[0])
        self.assertEqual(brief["signal"], "run_crashed")
        self.assertEqual(brief["status"], "no_inference")


class ScanCheckpointsRacesTest(unittest.TestCase):
    """Queue A refill: _scan_checkpoints' OSError guards
    (coverage run 40187685363: 8 lines on both platforms).
    The scan runs against a live training directory, so
    its contract is race-shaped: an entry that vanishes
    or turns unreadable mid-scan is skipped, a folder
    that cannot be listed is skipped, and a run dir that
    cannot be listed at all scans as empty -- never an
    exception into the watcher. Each guard is driven by
    the real filesystem plus one wrapped os call that
    raises for exactly one path.
    """

    GLOBS = ["checkpoint-*", "*.pt"]

    def _tree(self, d):
        run = os.path.join(d, "run")
        os.makedirs(os.path.join(run, "sub"))
        for rel in ("checkpoint-1", os.path.join("sub", "a.pt"),
                    os.path.join("sub", "b.pt")):
            with open(os.path.join(run, rel), "w") as fh:
                fh.write("x")
        return run

    def _guarded(self, fn, target):
        real = fn

        def wrapped(path, *a, **kw):
            if os.path.abspath(os.fspath(path)) == \
                    os.path.abspath(target):
                raise OSError("gone mid-scan")
            return real(path, *a, **kw)
        return wrapped

    def test_an_unlistable_run_dir_scans_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._tree(d)
            with unittest.mock.patch.object(
                    os, "listdir",
                    self._guarded(os.listdir, run)):
                self.assertEqual(
                    TW._scan_checkpoints(run, self.GLOBS), [])

    def test_an_unlistable_subdir_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._tree(d)
            sub = os.path.join(run, "sub")
            with unittest.mock.patch.object(
                    os, "listdir",
                    self._guarded(os.listdir, sub)):
                found = TW._scan_checkpoints(run, self.GLOBS)
            self.assertEqual([f["name"] for f in found],
                             ["checkpoint-1"])

    def test_an_entry_that_raises_on_probe_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._tree(d)
            sub = os.path.join(run, "sub")
            with unittest.mock.patch.object(
                    os.path, "isdir",
                    self._guarded(os.path.isdir, sub)):
                found = TW._scan_checkpoints(run, self.GLOBS)
            self.assertEqual([f["name"] for f in found],
                             ["checkpoint-1"])

    def test_a_file_that_raises_on_stat_is_skipped(self):
        # The race the guard exists for: the probe says
        # the file is there, the scan's stat a moment
        # later fails (the file vanished between the
        # two). The probe is stubbed for the target
        # (whether isfile stats through os.stat at all
        # differs by platform and Python version, so
        # counting stat calls is not portable); the
        # scan's own stat raises for it by construction.
        with tempfile.TemporaryDirectory() as d:
            run = self._tree(d)
            bad = os.path.abspath(os.path.join(run, "sub", "b.pt"))
            real_stat = os.stat
            real_isfile = os.path.isfile

            def flaky(path, *a, **kw):
                if os.path.abspath(os.fspath(path)) == bad:
                    raise OSError("gone mid-scan")
                return real_stat(path, *a, **kw)

            def probe(path, *a, **kw):
                if os.path.abspath(os.fspath(path)) == bad:
                    return True
                return real_isfile(path, *a, **kw)

            with unittest.mock.patch.object(os, "stat", flaky), \
                    unittest.mock.patch.object(
                        os.path, "isfile", probe):
                found = TW._scan_checkpoints(run, self.GLOBS)
            self.assertEqual(
                sorted(f["name"] for f in found),
                ["checkpoint-1", os.path.join("sub", "a.pt")])


if __name__ == "__main__":
    unittest.main()
