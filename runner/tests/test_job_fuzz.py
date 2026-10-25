"""The Job Fuzz example: a sense that fuzzes retained jobs.

Pins runner/extensions/job-fuzz/: the manifest through
the real extension loader, the mutation engine's
determinism, the pure decide() core over fixture readings
(divergence, hard failures, coverage novelty, triage
dedupe and cooldown, the alert cap, corpus bounds), and
read_live() against a fixture retained store with a fake
runner command standing in for the core's --run-variant
door (plus one pass through the real door).

No live network, no live runner daemon: the campaign's
runner is a fixture script or a single --run-variant call.
"""
import importlib.util
import io
import random
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.ops import extensions as E  # noqa: E402

JF_DIR = os.path.join(REPO, "runner", "extensions", "job-fuzz")

T0 = 1_700_000_000.0


def _load():
    spec = importlib.util.spec_from_file_location(
        "job_fuzz_example",
        os.path.join(JF_DIR, "job_fuzz.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


JF = _load()


def _manifest():
    with open(os.path.join(JF_DIR, "extension.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _seed(job_id="job-a", script="echo hello\nexit 0",
          exit_code=0, timed_out=False, saved_at=T0):
    return {"job_id": job_id, "kind": "exec", "script": script,
            "exit_code": exit_code, "timed_out": timed_out,
            "digest": "d-" + job_id, "saved_at": saved_at}


def _outcome(job_id="job-a", mutator="truncate", stage="ran",
             exit_code=0, timed_out=False, orig_exit_code=0,
             orig_timed_out=False, **kw):
    o = {"job_id": job_id, "mutator": mutator, "stage": stage,
         "exit_code": exit_code, "timed_out": timed_out,
         "orig_exit_code": orig_exit_code,
         "orig_timed_out": orig_timed_out,
         "variant_file": "fuzz-x.json"}
    o.update(kw)
    return o


def _readings(outcomes=(), seeds=(), idle=True, now=T0):
    return {"now": now, "idle": idle,
            "seeds": list(seeds), "outcomes": list(outcomes),
            "campaign_seed": 7}


class ManifestTest(unittest.TestCase):
    def test_manifest_loads_and_declares_the_three_signals(self):
        registry, problems = E.load_extensions(
            os.path.dirname(JF_DIR), kinds=("sense",))
        self.assertIn("job_fuzz", registry)
        self.assertFalse([p for p in problems
                          if "job-fuzz" in p])
        names = [s["name"] for s in
                 registry["job_fuzz"]["signals"]]
        self.assertEqual(names, ["variant_hard_failure",
                                 "variant_divergence",
                                 "coverage_novelty"])

    def test_manifest_is_a_sense_with_the_cost_knob(self):
        m = _manifest()
        self.assertEqual(m["kind"], "sense")
        self.assertEqual(m["api_version"], 1)
        self.assertIn("poll_interval_sec", m["tunables"])
        # Off by default is a wiring fact: nothing in the
        # shipped manifest points at a runner or a command.
        self.assertEqual(m["tunables"]["runner_cmd"], "")
        self.assertEqual(m["tunables"]["runner_base_dir"], "")


class MutatorTest(unittest.TestCase):
    SEED = {"job_id": "job-a",
            "script": "echo start\nsleep 5\necho done"}

    def test_variants_are_deterministic(self):
        a = JF.build_variant(self.SEED, "truncate", 42)
        b = JF.build_variant(self.SEED, "truncate", 42)
        self.assertEqual(a, b)
        c = JF.build_variant(self.SEED, "truncate", 43)
        self.assertNotEqual(a["script"], c["script"])

    def test_variant_job_ids_are_safe_and_stable(self):
        v = JF.build_variant(self.SEED, "drop_line", 1)
        self.assertTrue(v["job_id"].startswith("fuzz-"))
        self.assertEqual(v["kind"], "exec")
        self.assertEqual(v["mutator"], "drop_line")

    def test_truncate_shortens_at_a_line_boundary(self):
        v = JF.build_variant(self.SEED, "truncate", 3)
        self.assertLess(len(v["script"]), len(self.SEED["script"]))
        self.assertTrue(self.SEED["script"].startswith(
            v["script"]))

    def test_boundary_number_replaces_a_literal(self):
        v = JF.build_variant(self.SEED, "boundary_number", 5)
        self.assertNotIn("sleep 5", v["script"])
        self.assertTrue(any(n in v["script"] for n in
                            JF._BOUNDARY_NUMBERS))

    def test_boundary_number_needs_a_number(self):
        seed = {"job_id": "j", "script": "echo plain"}
        self.assertIsNone(
            JF.build_variant(seed, "boundary_number", 5))

    def test_interpreter_string_is_the_classic_bad_shape(self):
        v = JF.build_variant(self.SEED, "interpreter_string", 0)
        self.assertEqual(v["interpreter"], "sh")
        self.assertIsInstance(v["interpreter"], str)

    def test_empty_script_and_null_byte(self):
        v = JF.build_variant(self.SEED, "empty_script", 0)
        self.assertEqual(v["script"], "")
        v = JF.build_variant(self.SEED, "null_byte", 0)
        self.assertIn("\x00", v["script"])

    def test_unknown_mutator_and_unbiteable_seed(self):
        self.assertIsNone(JF.build_variant(self.SEED, "nope", 0))
        self.assertIsNone(JF.build_variant(
            {"job_id": "j", "script": ""}, "empty_script", 0))


class DecideTest(unittest.TestCase):
    def test_divergence_fires_on_class_change(self):
        alerts, _state = JF.decide(
            _readings([_outcome(exit_code=3)]), _manifest(), {})
        signals = [a["signal"] for a in alerts]
        self.assertIn("variant_divergence", signals)
        dv = [a for a in alerts
              if a["signal"] == "variant_divergence"][0]
        self.assertEqual(dv["severity"], "medium")
        self.assertEqual(dv["detail"]["original_class"], "exit0")
        self.assertEqual(dv["detail"]["variant_class"], "nonzero")

    def test_same_class_is_quiet_but_still_novel(self):
        alerts, _state = JF.decide(
            _readings([_outcome(exit_code=0)]), _manifest(), {})
        signals = [a["signal"] for a in alerts]
        self.assertNotIn("variant_divergence", signals)
        self.assertIn("coverage_novelty", signals)

    def test_refusal_of_a_ran_job_is_divergence(self):
        alerts, _state = JF.decide(
            _readings([_outcome(stage="refused",
                                reason="bad shape")]),
            _manifest(), {})
        dv = [a for a in alerts
              if a["signal"] == "variant_divergence"]
        self.assertEqual(len(dv), 1)
        self.assertEqual(dv[0]["detail"]["variant_class"],
                         "refused")

    def test_hard_failure_suppresses_divergence(self):
        alerts, _state = JF.decide(
            _readings([_outcome(stage="error",
                                reason="runner gone")]),
            _manifest(), {})
        signals = [a["signal"] for a in alerts]
        self.assertIn("variant_hard_failure", signals)
        self.assertNotIn("variant_divergence", signals)
        hf = [a for a in alerts
              if a["signal"] == "variant_hard_failure"][0]
        self.assertEqual(hf["severity"], "high")
        self.assertEqual(hf["detail"]["reason"], "runner gone")

    def test_timeout_is_a_hard_failure(self):
        alerts, _state = JF.decide(
            _readings([_outcome(timed_out=True)]),
            _manifest(), {})
        self.assertIn("variant_hard_failure",
                      [a["signal"] for a in alerts])

    def test_novelty_files_once_ever(self):
        readings = _readings([_outcome(exit_code=0)])
        _a1, state = JF.decide(readings, _manifest(), {})
        alerts2, _s = JF.decide(readings, _manifest(), state)
        self.assertNotIn("coverage_novelty",
                         [a["signal"] for a in alerts2])

    def test_divergence_dedupes_within_cooldown(self):
        readings = _readings([_outcome(exit_code=3)])
        _a1, state = JF.decide(readings, _manifest(), {})
        alerts2, _s = JF.decide(readings, _manifest(), state)
        self.assertNotIn("variant_divergence",
                         [a["signal"] for a in alerts2])

    def test_divergence_refires_after_cooldown(self):
        readings = _readings([_outcome(exit_code=3)])
        _a1, state = JF.decide(readings, _manifest(), {})
        later = _readings([_outcome(exit_code=3)],
                          now=T0 + 8 * 86400)
        alerts2, _s = JF.decide(later, _manifest(), state)
        self.assertIn("variant_divergence",
                      [a["signal"] for a in alerts2])

    def test_not_idle_files_nothing(self):
        alerts, _state = JF.decide(
            _readings([_outcome(exit_code=3)], idle=False),
            _manifest(), {})
        self.assertEqual(alerts, [])

    def test_alert_cap_prioritizes_hard_failures(self):
        outcomes = [_outcome(job_id=f"j{i}", mutator="truncate",
                             exit_code=3) for i in range(15)]
        outcomes.append(_outcome(job_id="boom",
                                 mutator="truncate",
                                 stage="error", reason="x"))
        m = _manifest()
        m["tunables"]["max_alerts_per_pass"] = 5
        alerts, state = JF.decide(
            _readings(outcomes), m, {})
        self.assertEqual(len(alerts), 5)
        self.assertEqual(alerts[0]["signal"],
                         "variant_hard_failure")
        # 32 candidates (16 divergence/novelty pairs plus
        # the hard failure's own pair), 5 filed, rest dropped
        # by the cap and counted, not lost.
        self.assertEqual(state["dropped_total"], 27)

    def test_campaign_counter_and_seed_advance(self):
        _a, state = JF.decide(
            _readings([_outcome()]), _manifest(), {})
        self.assertEqual(state["campaigns"], 1)
        self.assertEqual(state["campaign_seed"], 8)


class CorpusTest(unittest.TestCase):
    def test_corpus_folds_seeds_with_classes(self):
        _a, state = JF.decide(
            _readings(seeds=[_seed(),
                             _seed("job-b", exit_code=2)]),
            _manifest(), {})
        self.assertEqual(state["corpus"]["job-a"]["exit_class"],
                         "exit0")
        self.assertEqual(state["corpus"]["job-b"]["exit_class"],
                         "nonzero")

    def test_corpus_evicts_by_age(self):
        old = _seed("job-old", saved_at=T0 - 40 * 86400)
        _a, state = JF.decide(
            _readings(seeds=[old, _seed()]), _manifest(), {})
        self.assertNotIn("job-old", state["corpus"])
        self.assertIn("job-a", state["corpus"])

    def test_corpus_evicts_oldest_by_count(self):
        m = _manifest()
        m["tunables"]["corpus_max_jobs"] = 2
        seeds = [_seed("j1", saved_at=T0 - 300),
                 _seed("j2", saved_at=T0 - 200),
                 _seed("j3", saved_at=T0 - 100)]
        _a, state = JF.decide(_readings(seeds=seeds), m, {})
        self.assertEqual(sorted(state["corpus"]), ["j2", "j3"])

    def test_garbage_state_and_readings_are_tolerated(self):
        alerts, state = JF.decide(
            {"now": T0, "idle": True, "outcomes": "junk"},
            _manifest(), {"corpus": [1, 2], "filed": "x"})
        self.assertEqual(alerts, [])
        self.assertIsInstance(state["corpus"], dict)


class DecideGuardBranchesTest(unittest.TestCase):
    """Queue A: the guard branches of decide() that the
    shape hunts never produced (coverage run 40183585961:
    12 lines on both platforms) -- a readings value that
    is not an object, a manifest with no usable name,
    tunables at or below zero, junk inside the seeds and
    outcomes lists, an unrecognized stage, and the filed
    log's own cap. The discipline under test is the
    module's own: unusable input reads as the documented
    default or is skipped, never fatal, and the books
    stay bounded.
    """

    def test_non_dict_readings_read_as_an_empty_pass(self):
        for readings in (None, "junk", [1, 2]):
            with self.subTest(readings=readings):
                alerts, state = JF.decide(readings, _manifest(), {})
                self.assertEqual(alerts, [])
                self.assertEqual(state["campaigns"], 0)

    def test_a_nameless_manifest_files_as_job_fuzz(self):
        outcome = _outcome(stage="error", reason="boom")
        for manifest in ({}, {"name": ""}, {"name": 7}, "junk"):
            with self.subTest(manifest=manifest):
                alerts, _state = JF.decide(
                    _readings(outcomes=[outcome]), manifest, {})
                self.assertTrue(alerts)
                self.assertTrue(all(
                    a["sensor"] == "job_fuzz" for a in alerts))
                self.assertIn("variant_hard_failure",
                              [a["signal"] for a in alerts])
        named = _manifest()
        alerts, _state = JF.decide(
            _readings(outcomes=[outcome]), named, {})
        self.assertTrue(all(
            a["sensor"] == named["name"] for a in alerts))

    def test_unusable_caps_read_as_the_defaults(self):
        # max_alerts_per_pass at zero must read as the
        # default 20, not as "file nothing": 25 hard
        # outcomes in distinct buckets make 25 hard
        # candidates plus 25 novelty candidates (one per
        # outcome -- a same-pass duplicate key is only
        # suppressed when its first filing actually
        # lands, and the cap falls first) -- 20 filed,
        # 30 dropped and counted.
        m = _manifest()
        m["tunables"]["corpus_max_jobs"] = 0
        m["tunables"]["distilled_max_jobs"] = -1
        m["tunables"]["max_alerts_per_pass"] = 0
        # Distinct buckets need distinct reason shapes:
        # _normalize_reason flattens digit runs, so the
        # reasons differ in letters, not numbers.
        words = ["alpha", "bravo", "charlie", "delta", "echo",
                 "foxtrot", "golf", "hotel", "india", "juliet",
                 "kilo", "lima", "mike", "november", "oscar",
                 "papa", "quebec", "romeo", "sierra", "tango",
                 "uniform", "victor", "whiskey", "xray", "yankee"]
        outcomes = [
            _outcome(job_id="j-" + w, stage="error",
                     reason="boom " + w)
            for w in words]
        alerts, state = JF.decide(
            _readings(outcomes=outcomes), m, {})
        self.assertEqual(len(alerts), 20)
        self.assertTrue(all(
            a["signal"] == "variant_hard_failure" for a in alerts))
        self.assertEqual(state["dropped_total"], 30)

    def test_junk_seeds_are_skipped_and_good_ones_land(self):
        seeds = ["junk",
                 {"job_id": 5, "saved_at": T0},
                 {"job_id": "x", "saved_at": "soon"},
                 _seed("job-a")]
        _a, state = JF.decide(_readings(seeds=seeds),
                              _manifest(), {})
        self.assertEqual(sorted(state["corpus"]), ["job-a"])

    def test_junk_outcomes_are_skipped_and_a_bogus_stage_is_an_error(self):
        outcomes = ["junk",
                    {"job_id": "", "mutator": "truncate"},
                    {"job_id": "j", "mutator": ""},
                    _outcome(job_id="j2", stage="bogus")]
        alerts, state = JF.decide(
            _readings(outcomes=outcomes), _manifest(), {})
        self.assertEqual(sorted(state["energy"]), ["j2"])
        hard = [a for a in alerts
                if a["signal"] == "variant_hard_failure"]
        self.assertEqual(len(hard), 1)
        self.assertEqual(hard[0]["detail"]["stage"], "error")

    def test_the_filed_log_trims_to_its_cap_on_a_new_filing(self):
        # _clean_state already trims the log it is handed;
        # decide's own trim is for a log that grows past
        # the cap during the pass: a full log plus one new
        # divergence filing evicts the oldest entry.
        filed = {"dv|old-%d|m|c" % i: float(i)
                 for i in range(JF._FILER_CAP)}
        outcome = _outcome(job_id="new-job", exit_code=0,
                           orig_exit_code=3)
        _a, state = JF.decide(
            _readings(outcomes=[outcome]), _manifest(),
            {"filed": filed})
        self.assertEqual(len(state["filed"]), JF._FILER_CAP)
        self.assertNotIn("dv|old-0|m|c", state["filed"])
        self.assertTrue(any(
            k.startswith("dv|new-job|") for k in state["filed"]))


class RunOneVariantBranchesTest(unittest.TestCase):
    """Queue A: the _run_one_variant failure shapes the
    campaign tests never produced (coverage run
    40183585961: 11 lines on both platforms). The
    docstring's contract: never raises -- every failure
    shape is itself an outcome, stage "error", with the
    reason and the variant file named.
    """

    def _script(self, d, name, body):
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return path

    def test_a_variant_that_cannot_be_archived_is_an_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            got = JF._run_one_variant(
                "whatever {variant}",
                {"job_id": "a/b"}, d, 5)
        self.assertEqual(got["stage"], "error")
        self.assertIn("cannot archive variant", got["reason"])
        self.assertEqual(got["variant_file"], "a/b.json")

    def test_a_bad_runner_command_is_an_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            got = JF._run_one_variant(
                'run "unbalanced {variant}',
                {"job_id": "v1"}, d, 5)
        self.assertEqual(got["stage"], "error")
        self.assertIn("bad runner_cmd", got["reason"])
        self.assertEqual(got["variant_file"], "v1.json")

    def test_a_command_without_a_placeholder_gets_the_path_appended(self):
        with tempfile.TemporaryDirectory() as d:
            script = self._script(d, "echo_argv.py", (
                "import json, sys\n"
                "print(json.dumps({'stage': 'ran',\n"
                "                  'seen': sys.argv[-1]}))\n"))
            got = JF._run_one_variant(
                "%s %s" % (sys.executable, script),
                {"job_id": "v2"}, d, 10)
            self.assertEqual(got["stage"], "ran")
            self.assertEqual(
                got["seen"], os.path.join(d, "v2.json"))
            self.assertEqual(got["variant_file"], "v2.json")

    def test_a_missing_runner_is_an_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            got = JF._run_one_variant(
                "/nonexistent/hp-runner {variant}",
                {"job_id": "v3"}, d, 5)
        self.assertEqual(got["stage"], "error")
        self.assertIn("cannot run runner_cmd", got["reason"])

    def test_a_runner_that_prints_no_outcome_is_an_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            script = self._script(d, "junk.py", (
                "import sys\n"
                "print('noise, not an outcome')\n"
                "print('{not json')\n"
                "print('{}')\n"
                "sys.exit(3)\n"))
            got = JF._run_one_variant(
                "%s %s {variant}" % (sys.executable, script),
                {"job_id": "v4"}, d, 10)
        self.assertEqual(got["stage"], "error")
        self.assertIn("no outcome", got["reason"])
        self.assertIn("exit 3", got["reason"])
        self.assertEqual(got["variant_file"], "v4.json")


class RecordSeedBranchesTest(unittest.TestCase):
    """Queue A: the _record_seed rejections and fallbacks
    the corpus tests never produced (coverage run
    40183585961: 10 lines on both platforms). The
    docstring's contract is tolerant by design: only an
    exec record with a script and a recorded exit code
    seeds the corpus -- anything else is None, never an
    exception -- a missing saved_at falls back to the
    file's mtime, and a missing job_id falls back to the
    file's name.
    """

    def _write(self, d, name, text):
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def _record(self, **kw):
        rec = {"kind": "exec", "script": "echo hi",
               "exit_code": 0, "saved_at": T0,
               "job_id": "job-a"}
        rec.update(kw)
        return json.dumps(rec)

    def test_an_oversize_record_is_not_a_seed(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, "big.json", self._record())
            with mock.patch.object(JF, "_MAX_RECORD_BYTES", 8):
                self.assertIsNone(JF._record_seed(path, T0))

    def test_an_unreadable_and_an_unparseable_record_are_not_seeds(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(JF._record_seed(
                os.path.join(d, "missing.json"), T0))
            path = self._write(d, "junk.json", "{not json")
            self.assertIsNone(JF._record_seed(path, T0))

    def test_a_non_object_record_is_not_a_seed(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(d, "list.json", "[1, 2, 3]")
            self.assertIsNone(JF._record_seed(path, T0))

    def test_a_record_without_a_script_is_not_a_seed(self):
        with tempfile.TemporaryDirectory() as d:
            for i, script in enumerate((None, "", 42)):
                path = self._write(
                    d, "s%d.json" % i, self._record(script=script))
                with self.subTest(script=script):
                    self.assertIsNone(JF._record_seed(path, T0))
            path = self._write(d, "s9.json", json.dumps(
                {"kind": "exec", "exit_code": 0}))
            self.assertIsNone(JF._record_seed(path, T0))

    def test_a_missing_saved_at_falls_back_to_the_mtime(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(
                d, "job-a.json", self._record(saved_at="soon"))
            seed = JF._record_seed(path, T0 - 50)
            self.assertEqual(seed["saved_at"], T0 - 50)
            self.assertEqual(seed["job_id"], "job-a")

    def test_no_time_at_all_is_not_a_seed(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(
                d, "job-a.json", self._record(saved_at=None))
            self.assertIsNone(JF._record_seed(path, "no mtime"))

    def test_a_missing_job_id_falls_back_to_the_file_name(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._write(
                d, "retained-9.json", self._record(job_id=None))
            seed = JF._record_seed(path, T0)
            self.assertEqual(seed["job_id"], "retained-9")
            path = self._write(
                d, "retained-10.json", self._record(job_id=""))
            seed = JF._record_seed(path, T0)
            self.assertEqual(seed["job_id"], "retained-10")


FAKE_RUNNER = """\
import json, sys
v = json.load(open(sys.argv[-1]))
if isinstance(v.get("interpreter"), str):
    print(json.dumps({"stage": "refused",
                      "reason": "interpreter shape"}))
elif v.get("script", "").startswith("hang"):
    import time; time.sleep(30)
elif "exit 0" in v.get("script", ""):
    print(json.dumps({"stage": "ran", "exit_code": 0,
                      "timed_out": False, "duration_sec": 0.01,
                      "stdout_bytes": 1, "stderr_bytes": 0,
                      "digest": "x"}))
else:
    print(json.dumps({"stage": "ran", "exit_code": 3,
                      "timed_out": False, "duration_sec": 0.01,
                      "stdout_bytes": 0, "stderr_bytes": 0,
                      "digest": "y"}))
"""


class ReadLiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-jf-")
        self.base = os.path.join(self.tmp, "state")
        self.retained = os.path.join(self.base, "retained")
        os.makedirs(self.retained)
        self.fake = os.path.join(self.tmp, "fake.py")
        with open(self.fake, "w", encoding="utf-8") as fh:
            fh.write(FAKE_RUNNER)

    def _retain(self, record, age_sec=3600):
        path = os.path.join(
            self.retained, record["job_id"] + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh)
        old = time.time() - age_sec
        os.utime(path, (old, old))
        return path

    def _manifest_with(self, **tunables):
        m = _manifest()
        # The load vote is neutralized here: these tests judge
        # the campaign machinery, and a host under load (a CI
        # runner, a gate next door) must not starve them. The
        # vote itself is pinned in IdleVoteTest.
        m["tunables"]["idle_load_max"] = 1e9
        m["tunables"].update(tunables)
        m["tunables"]["runner_base_dir"] = self.base
        m["tunables"]["work_dir"] = os.path.join(self.tmp, "work")
        return m

    def test_scan_seeds_only_exec_records_with_outcomes(self):
        self._retain(_seed(saved_at=time.time() - 3600))
        self._retain({"job_id": "q", "kind": "query",
                      "script": "x", "exit_code": 0,
                      "saved_at": time.time() - 3600})
        self._retain({"job_id": "noexit", "kind": "exec",
                      "script": "echo x",
                      "saved_at": time.time() - 3600})
        seeds, _newest = JF._scan_retained(self.base, 500)
        self.assertEqual([s["job_id"] for s in seeds], ["job-a"])

    def test_missing_store_reads_empty(self):
        seeds, newest = JF._scan_retained(
            os.path.join(self.tmp, "nope"), 500)
        self.assertEqual(seeds, [])
        self.assertEqual(newest, 0.0)

    def test_fresh_job_means_not_idle_and_no_campaign(self):
        self._retain(_seed(saved_at=time.time() - 3600),
                     age_sec=5)
        m = self._manifest_with(
            runner_cmd=f"{sys.executable} {self.fake} {{variant}}")
        readings = JF.read_live(m, {"campaign_seed": 0})
        self.assertFalse(readings["idle"])
        self.assertEqual(readings["outcomes"], [])

    def test_campaign_runs_and_archives_variants(self):
        self._retain(_seed(saved_at=time.time() - 3600))
        m = self._manifest_with(
            runner_cmd=f"{sys.executable} {self.fake} {{variant}}")
        # Seed 4 rotates the mutator order onto
        # interpreter_string, whose variant must be refused.
        readings = JF.read_live(m, {"campaign_seed": 4})
        self.assertTrue(readings["idle"])
        self.assertTrue(readings["outcomes"])
        for outcome in readings["outcomes"]:
            self.assertEqual(outcome["job_id"], "job-a")
            self.assertIn(outcome["stage"],
                          ("ran", "refused", "error"))
            archived = os.path.join(
                self.tmp, "work", outcome["variant_file"])
            self.assertTrue(os.path.isfile(archived))
        refusals = [o for o in readings["outcomes"]
                    if o["stage"] == "refused"]
        self.assertTrue(refusals)  # interpreter_string bit

    def test_no_runner_cmd_no_campaign(self):
        self._retain(_seed(saved_at=time.time() - 3600))
        readings = JF.read_live(self._manifest_with(),
                                {"campaign_seed": 0})
        self.assertEqual(readings["outcomes"], [])
        self.assertEqual(len(readings["seeds"]), 1)

    def test_hanging_runner_becomes_an_error_outcome(self):
        self._retain(_seed(script="hang 1\nnow",
                           saved_at=time.time() - 3600))
        m = self._manifest_with(
            runner_cmd=f"{sys.executable} {self.fake} {{variant}}",
            variant_timeout_sec=1, max_variants_per_pass=2,
            variants_per_seed=2)
        readings = JF.read_live(m, {"campaign_seed": 0})
        errors = [o for o in readings["outcomes"]
                  if o["stage"] == "error"]
        self.assertTrue(errors)
        self.assertIn("timed out", errors[0]["reason"])


class IdleVoteTest(unittest.TestCase):
    def test_fresh_job_is_never_idle(self):
        self.assertFalse(JF._box_idle(1000.0, 999.0, 600.0))
        self.assertTrue(JF._box_idle(1000.0, 399.0, 600.0))
        self.assertTrue(JF._box_idle(1000.0, 0.0, 600.0))

    def test_load_vote_bounds(self):
        if hasattr(os, "getloadavg"):
            # A zero ceiling quiets nothing (load is never
            # negative); an unbounded ceiling quiets all.
            self.assertFalse(JF._load_quiet(0.0))
        else:
            # This platform offers no load average (Windows):
            # there is no vote, and "quiet" is its only
            # answer -- the sense must still campaign there.
            self.assertTrue(JF._load_quiet(0.0))
        self.assertTrue(JF._load_quiet(1e18))

    def test_windows_split_keeps_backslash_paths(self):
        # POSIX shlex would eat the backslashes out of
        # every path; the Windows split must not, and must
        # take the quotes off a quoted program path.
        parts = JF._split_cmd_windows(
            r'"C:\Program Files\py.exe" C:\x\fake.py {variant}')
        self.assertEqual(parts, [r"C:\Program Files\py.exe",
                                 r"C:\x\fake.py", "{variant}"])
        parts = JF._split_cmd_windows(
            r"C:\tools\python.exe {variant}")
        self.assertEqual(parts, [r"C:\tools\python.exe",
                                 "{variant}"])


class SpliceDictionaryTest(unittest.TestCase):
    SEED = {"job_id": "job-a",
            "script": "echo start\nsleep 5\necho done"}
    DONOR = {"job_id": "job-b",
             "script": "curl example.test\ndeploy --prod"}

    def test_splice_needs_and_uses_a_donor(self):
        self.assertIsNone(
            JF.build_variant(self.SEED, "splice", 1))
        v = JF.build_variant(self.SEED, "splice", 1,
                             donor_job=self.DONOR)
        self.assertIsNotNone(v)
        donor_lines = set(self.DONOR["script"].split("\n"))
        self.assertTrue(donor_lines & set(
            v["script"].split("\n")))

    def test_splice_is_deterministic_in_the_triple(self):
        a = JF.build_variant(self.SEED, "splice", 7,
                             donor_job=self.DONOR)
        b = JF.build_variant(self.SEED, "splice", 7,
                             donor_job=self.DONOR)
        self.assertEqual(a, b)

    def test_dictionary_needs_tokens_and_injects_one(self):
        self.assertIsNone(
            JF.build_variant(self.SEED, "dictionary", 1))
        v = JF.build_variant(
            self.SEED, "dictionary", 1,
            dictionary=["systemctl", "restart", "nginx"])
        self.assertTrue(any(t in v["script"] for t in
                            ("systemctl", "restart", "nginx")))

    def test_dictionary_harvests_the_corpus_vocabulary(self):
        tokens = JF._build_dictionary(
            [{"script": "systemctl restart nginx\n"
                        "curl -s example.test"}])
        self.assertIn("systemctl", tokens)
        self.assertIn("nginx", tokens)
        self.assertNotIn("-s", tokens)  # too short
        self.assertEqual(tokens, sorted(tokens))


class RelationTest(unittest.TestCase):
    def test_digest_change_under_a_probe_is_divergence(self):
        alerts, _s = JF.decide(
            _readings([_outcome(mutator="trailing_blank",
                                exit_code=0, digest="changed",
                                orig_digest="d-job-a")]),
            _manifest(), {})
        dv = [a for a in alerts
              if a["signal"] == "variant_divergence"]
        self.assertEqual(len(dv), 1)
        self.assertEqual(dv[0]["detail"]["relation"],
                         "identity")
        self.assertIn("digest",
                      dv[0]["detail"]["relation_violation"])

    def test_kept_relation_is_quiet(self):
        alerts, _s = JF.decide(
            _readings([_outcome(mutator="trailing_blank",
                                exit_code=0, digest="d-job-a",
                                orig_digest="d-job-a")]),
            _manifest(), {})
        self.assertNotIn("variant_divergence",
                         [a["signal"] for a in alerts])

    def test_class_change_under_a_probe_names_the_relation(self):
        alerts, _s = JF.decide(
            _readings([_outcome(mutator="blank_line",
                                exit_code=2)]),
            _manifest(), {})
        dv = [a for a in alerts
              if a["signal"] == "variant_divergence"][0]
        self.assertIn("class",
                      dv["detail"]["relation_violation"])


class BucketTest(unittest.TestCase):
    def test_same_reason_across_seeds_files_once(self):
        outcomes = [
            _outcome(job_id="job-a", stage="error",
                     reason="runner exploded 42 times",
                     variant_file="va.json"),
            _outcome(job_id="job-b", stage="error",
                     reason="Runner exploded 7 times",
                     variant_file="vb.json")]
        alerts, state = JF.decide(
            _readings(outcomes), _manifest(), {})
        hf = [a for a in alerts
              if a["signal"] == "variant_hard_failure"]
        self.assertEqual(len(hf), 1)
        self.assertEqual(hf[0]["detail"]["bucket_count"], 1)
        bucket = state["buckets"]["runner exploded # times"]
        self.assertEqual(bucket["count"], 2)
        self.assertEqual(bucket["examples"],
                         ["va.json", "vb.json"])

    def test_different_reasons_file_separately(self):
        outcomes = [
            _outcome(job_id="job-a", stage="error",
                     reason="disk gone"),
            _outcome(job_id="job-b", stage="error",
                     reason="permission denied")]
        alerts, _s = JF.decide(
            _readings(outcomes), _manifest(), {})
        self.assertEqual(len([a for a in alerts if a["signal"]
                              == "variant_hard_failure"]), 2)

    def test_bucket_refiles_after_cooldown_with_its_count(self):
        readings = _readings([_outcome(
            stage="error", reason="runner exploded 1 time")])
        _a, state = JF.decide(readings, _manifest(), {})
        later = _readings([_outcome(
            stage="error", reason="runner exploded 2 time")],
            now=T0 + 8 * 86400)
        alerts, state = JF.decide(later, _manifest(), state)
        hf = [a for a in alerts
              if a["signal"] == "variant_hard_failure"]
        self.assertEqual(len(hf), 1)
        self.assertEqual(hf[0]["detail"]["bucket_count"], 2)


class PromotionTest(unittest.TestCase):
    def test_novel_variant_joins_the_distilled_corpus(self):
        outcome = _outcome(exit_code=3, variant_id="fuzz-v1",
                           variant_script="echo boom\nexit 3",
                           digest="vd")
        _a, state = JF.decide(
            _readings([outcome]), _manifest(), {})
        entry = state["distilled"]["fuzz-v1"]
        self.assertEqual(entry["script"], "echo boom\nexit 3")
        self.assertEqual(entry["exit_class"], "nonzero")
        self.assertEqual(entry["exit_code"], 3)

    def test_known_coverage_promotes_nothing(self):
        outcome = _outcome(exit_code=0, variant_id="fuzz-v1",
                           variant_script="echo hi")
        _a1, state = JF.decide(
            _readings([outcome]), _manifest(), {})
        other = _outcome(exit_code=0, variant_id="fuzz-v2",
                         variant_script="echo other")
        _a2, state = JF.decide(
            _readings([other]), _manifest(), state)
        self.assertNotIn("fuzz-v2", state["distilled"])

    def test_distilled_tier_is_capped_oldest_first(self):
        m = _manifest()
        m["tunables"]["distilled_max_jobs"] = 1
        o1 = _outcome(mutator="truncate", exit_code=3,
                      variant_id="fuzz-v1",
                      variant_script="echo one")
        _a, state = JF.decide(_readings([o1]), m, {})
        o2 = _outcome(mutator="drop_line", exit_code=3,
                      variant_id="fuzz-v2",
                      variant_script="echo two")
        later = _readings([o2], now=T0 + 60)
        _a, state = JF.decide(later, m, state)
        self.assertEqual(sorted(state["distilled"]),
                         ["fuzz-v2"])

    def test_distilled_baseline_class_is_authoritative(self):
        outcome = _outcome(stage="ran", exit_code=0,
                           orig_class="refused")
        alerts, _s = JF.decide(
            _readings([outcome]), _manifest(), {})
        dv = [a for a in alerts
              if a["signal"] == "variant_divergence"]
        self.assertEqual(len(dv), 1)
        self.assertEqual(dv[0]["detail"]["original_class"],
                         "refused")


class EnergyTest(unittest.TestCase):
    def test_decide_counts_runs_and_yield_per_seed(self):
        outcomes = [_outcome(exit_code=3),
                    _outcome(job_id="job-b", stage="error",
                             reason="x")]
        _a, state = JF.decide(
            _readings(outcomes), _manifest(), {})
        a = state["energy"]["job-a"]
        self.assertEqual((a["runs"], a["novel"], a["hard"],
                          a["diverged"]), (1, 1, 0, 1))
        b = state["energy"]["job-b"]
        self.assertEqual((b["runs"], b["hard"]), (1, 1))

    def test_untried_seed_scores_mid_pack(self):
        self.assertEqual(JF._seed_score(None), 0.5)
        self.assertGreater(
            JF._seed_score({"runs": 4, "novel": 3, "hard": 1,
                            "diverged": 0}),
            JF._seed_score({"runs": 4, "novel": 0, "hard": 0,
                            "diverged": 0}))


MINIM_RUNNER = """\
import json, sys
v = json.load(open(sys.argv[-1]))
code = 3 if "boom" in v.get("script", "") else 0
print(json.dumps({"stage": "ran", "exit_code": code,
                  "timed_out": False, "duration_sec": 0.01,
                  "stdout_bytes": 0, "stderr_bytes": 0,
                  "digest": "z"}))
"""


class MinimizeTest(unittest.TestCase):
    def test_minimizer_shrinks_to_the_essential_line(self):
        with tempfile.TemporaryDirectory() as td:
            runner = os.path.join(td, "minim.py")
            with open(runner, "w", encoding="utf-8") as fh:
                fh.write(MINIM_RUNNER)
            cmd = f"{sys.executable} {runner} {{variant}}"
            variant = {"job_id": "fuzz-min1", "kind": "exec",
                       "mutator": "truncate",
                       "script": "junk one\njunk two\n"
                                 "boom here\ntrailing junk"}
            report = {"stage": "ran", "exit_code": 3,
                      "timed_out": False, "digest": "z",
                      "variant_file": "fuzz-min1.json"}
            variant, report, steps = JF._minimize_variant(
                cmd, variant, report, td, 5, 12)
            self.assertEqual(variant["script"], "boom here")
            self.assertEqual(steps, 4)
            with open(os.path.join(td, "fuzz-min1.json"),
                      encoding="utf-8") as fh:
                archived = json.load(fh)
            self.assertEqual(archived["script"], "boom here")

    def test_minimizer_leaves_a_single_line_alone(self):
        variant = {"job_id": "fuzz-min2", "script": "boom"}
        _v, _r, steps = JF._minimize_variant(
            "unused", variant, {"stage": "ran", "exit_code": 3,
                                "timed_out": False},
            "/nonexistent", 5, 12)
        self.assertEqual(steps, 0)


class CampaignPoolTest(ReadLiveTest):
    def test_distilled_seed_campaigns_without_retained(self):
        reader = {"campaign_seed": 0,
                  "idle_load_max": None,
                  "distilled": {"fuzz-d1": {
                      "script": "echo distilled\nexit 0",
                      "exit_code": 0, "timed_out": False,
                      "exit_class": "exit0", "digest": "dd",
                      "saved_at": time.time() - 3600}}}
        m = self._manifest_with(
            runner_cmd=f"{sys.executable} {self.fake} {{variant}}")
        readings = JF.read_live(m, reader)
        self.assertTrue(readings["outcomes"])
        self.assertEqual({o["job_id"]
                          for o in readings["outcomes"]},
                         {"fuzz-d1"})

    def test_energy_beats_recency_in_seed_choice(self):
        self._retain(_seed("job-old",
                           saved_at=time.time() - 7200),
                     age_sec=7200)
        self._retain(_seed("job-new",
                           saved_at=time.time() - 3600),
                     age_sec=3600)
        m = self._manifest_with(
            runner_cmd=f"{sys.executable} {self.fake} {{variant}}",
            max_seeds_per_pass=1)
        fresh = JF.read_live(m, {"campaign_seed": 0})
        self.assertEqual({o["job_id"]
                          for o in fresh["outcomes"]},
                         {"job-new"})
        seasoned = JF.read_live(
            m, {"campaign_seed": 0,
                "energy": {"job-old": {"runs": 2, "novel": 5,
                                       "hard": 0,
                                       "diverged": 0}}})
        self.assertEqual({o["job_id"]
                          for o in seasoned["outcomes"]},
                         {"job-old"})


class MainSamplesTest(unittest.TestCase):
    def test_samples_mode_prints_alerts_and_writes_state(self):
        readings = _readings([_outcome(exit_code=3)])
        with tempfile.TemporaryDirectory() as td:
            samples = os.path.join(td, "samples.json")
            with open(samples, "w", encoding="utf-8") as fh:
                json.dump(readings, fh)
            state = os.path.join(td, "state.json")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = JF.main(["--samples", samples,
                              "--state", state])
            self.assertEqual(rc, 0)
            lines = [json.loads(x) for x in
                     out.getvalue().splitlines() if x.strip()]
            self.assertIn("variant_divergence",
                          [a["signal"] for a in lines])
            with open(state, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["campaigns"], 1)


class MainTest(unittest.TestCase):
    """Queue A: `main()` never ran anywhere (coverage run
    40180268696: 23 lines on both platforms) -- the suite
    drove decide() and read_live() directly and left the
    command itself, the one a runner actually launches,
    unexercised. Driven here through its own arguments:
    --samples stands in for the machine read, --state and
    --manifest point into a temp dir, and the local
    delivery branches end in a real local inbox. The
    contract under test is main()'s own: unreadable inputs
    are a named refusal (exit 2), a failed or partial
    delivery saves no state so the next pass retries, and
    a saved state makes the next pass remember what it
    filed.
    """

    SECRET_ENV = "HP_JF_MAIN_SECRET"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-jf-main-")
        self.state = os.path.join(self.tmp, "state.json")
        self.samples = os.path.join(self.tmp, "samples.json")
        with open(self.samples, "w", encoding="utf-8") as fh:
            json.dump(_readings([_outcome(exit_code=3)]), fh)

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = JF.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_prints_alerts_and_the_saved_state_dedupes(self):
        rc, out, _err = self._run(
            ["--samples", self.samples, "--state", self.state])
        self.assertEqual(rc, 0)
        printed = [json.loads(line) for line in out.splitlines()
                   if line.strip()]
        self.assertIn("variant_divergence",
                      [a["signal"] for a in printed])
        self.assertTrue(os.path.isfile(self.state))
        rc, out, _err = self._run(
            ["--samples", self.samples, "--state", self.state])
        self.assertEqual(rc, 0)
        printed = [json.loads(line) for line in out.splitlines()
                   if line.strip()]
        self.assertNotIn("variant_divergence",
                         [a["signal"] for a in printed])

    def test_an_unreadable_manifest_is_a_named_refusal(self):
        rc, out, err = self._run(
            ["--manifest", os.path.join(self.tmp, "nope.json"),
             "--samples", self.samples, "--state", self.state])
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("cannot read manifest", err)
        self.assertFalse(os.path.exists(self.state))

    def test_an_unreadable_samples_file_is_a_named_refusal(self):
        rc, _out, err = self._run(
            ["--samples", os.path.join(self.tmp, "nope.json"),
             "--state", self.state])
        self.assertEqual(rc, 2)
        self.assertIn("cannot read samples", err)

    def test_a_garbage_state_file_reads_as_fresh(self):
        with open(self.state, "w", encoding="utf-8") as fh:
            fh.write("not json{")
        rc, out, _err = self._run(
            ["--samples", self.samples, "--state", self.state])
        self.assertEqual(rc, 0)
        self.assertIn("variant_divergence", out)

    def test_runner_overrides_run_and_the_live_read_files(self):
        base = os.path.join(self.tmp, "runner-base")
        retained = os.path.join(base, "retained")
        os.makedirs(retained)
        with open(os.path.join(retained, "job-a.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(_seed(saved_at=time.time() - 3600), fh)
        fake = os.path.join(self.tmp, "fake.py")
        with open(fake, "w", encoding="utf-8") as fh:
            fh.write(FAKE_RUNNER)
        manifest = os.path.join(self.tmp, "extension.json")
        m = _manifest()
        m["tunables"]["idle_load_max"] = 1e9
        m["tunables"]["work_dir"] = os.path.join(self.tmp, "work")
        with open(manifest, "w", encoding="utf-8") as fh:
            json.dump(m, fh)
        old = time.time() - 3600
        os.utime(os.path.join(retained, "job-a.json"), (old, old))
        rc, _out, err = self._run(
            ["--manifest", manifest, "--state", self.state,
             "--runner-dir", base,
             "--runner-cmd",
             "%s %s {variant}" % (sys.executable, fake)])
        self.assertEqual(rc, 0, err)
        self.assertTrue(os.path.isfile(self.state))

    def test_local_delivery_files_the_alert(self):
        base = os.path.join(self.tmp, "runner-base")
        env = {self.SECRET_ENV: "jf-main-secret"}
        with mock.patch.dict(os.environ, env):
            rc, _out, err = self._run(
                ["--samples", self.samples, "--state", self.state,
                 "--local-dir", base,
                 "--secret-env", self.SECRET_ENV])
        self.assertEqual(rc, 0, err)
        inbox = os.path.join(base, "local-inbox")
        # One envelope per alert: the divergence readings
        # file variant_divergence and coverage_novelty.
        self.assertEqual(len(os.listdir(inbox)), 2)
        self.assertTrue(os.path.isfile(self.state))

    def test_local_delivery_without_a_secret_refuses(self):
        base = os.path.join(self.tmp, "runner-base")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(self.SECRET_ENV, None)
            rc, _out, _err = self._run(
                ["--samples", self.samples, "--state", self.state,
                 "--local-dir", base,
                 "--secret-env", self.SECRET_ENV])
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(self.state))

    def test_a_failed_delivery_saves_no_state(self):
        base = os.path.join(self.tmp, "runner-base")
        os.makedirs(base)
        with open(os.path.join(base, "local-inbox"), "w",
                  encoding="utf-8") as fh:
            fh.write("not a directory")
        env = {self.SECRET_ENV: "jf-main-secret"}
        with mock.patch.dict(os.environ, env):
            rc, _out, err = self._run(
                ["--samples", self.samples, "--state", self.state,
                 "--local-dir", base,
                 "--secret-env", self.SECRET_ENV])
        self.assertEqual(rc, 2)
        self.assertIn("not delivered", err)
        self.assertFalse(os.path.exists(self.state))

    def test_an_unwritable_state_is_a_named_refusal(self):
        state = os.path.join(self.tmp, "no-such-dir", "state.json")
        rc, _out, err = self._run(
            ["--samples", self.samples, "--state", state])
        self.assertEqual(rc, 2)
        self.assertIn("cannot write state", err)


class QuoteBreakMutatorTest(unittest.TestCase):
    """Queue A refill: the quote_break mutator had never
    run in the suite (coverage run 40187685363: the whole
    function, both platforms) -- no test's variant stream
    ever selected it. Its contract, from the mutator
    itself: a script with quotes gets exactly one quote
    character flipped to the other kind, nothing else
    touched; a script without quotes gets an unterminated
    echo line appended, so the variant's quoting is broken
    either way. Driven through the MUTATORS table with a
    seeded rng, the way decide() reaches it.
    """

    def _mutate(self, script, seed=7):
        return JF.MUTATORS["quote_break"](
            {"script": script}, random.Random(seed), None)

    def test_one_quote_flips_and_nothing_else_moves(self):
        script = 'echo "hello" && echo \'bye\''
        for seed in range(8):
            out = self._mutate(script, seed)["script"]
            self.assertEqual(len(out), len(script))
            diffs = [i for i, (a, b) in enumerate(
                zip(script, out)) if a != b]
            self.assertEqual(len(diffs), 1)
            i = diffs[0]
            self.assertIn(script[i], "\"'")
            self.assertEqual(out[i],
                             "'" if script[i] == '"' else '"')

    def test_no_quotes_appends_the_unterminated_line(self):
        out = self._mutate("run it")["script"]
        self.assertEqual(out, 'run it\necho "unterminated')

    def test_no_script_still_breaks_quoting(self):
        out = JF.MUTATORS["quote_break"](
            {}, random.Random(3), None)["script"]
        self.assertTrue(out.endswith('echo "unterminated'))


if __name__ == "__main__":
    unittest.main()
