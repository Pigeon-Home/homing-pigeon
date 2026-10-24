"""Coverage-guided fuzz of the parsers a bad mail or a bad config hits.

test_fuzz_surfaces runs blind campaigns: fixed rounds, fixed seeds, no
signal about whether a mutation reached new code. This module closes
that gap with the libFuzzer loop, in stdlib: exercise each candidate
under a line tracer, keep it in the corpus only if it adds coverage
inside runner/ that no earlier input reached, mutate from the corpus.

Design choices, pinned by the tests below:

- Coverage mechanism: sys.settrace, on every Python the project
  supports (3.9+). sys.monitoring (PEP 669) is 3.12-only; two
  mechanisms would risk the two interpreters disagreeing about the
  coverage set, and with it the corpus. One mechanism, line events,
  identical semantics everywhere. Only frames whose file lives in
  the runner package are traced; the previous trace function is
  restored after every input, whatever it was.
- Per-input environment pin: runner.runner.log() keeps a minute
  budget in module globals (_LOG_MINUTE/_LOG_COUNT/_LOG_DROPPED),
  and its rollover branch is wall-clock gated -- the same input
  covers different lines depending on when in the minute it runs.
  The harness pins those globals to a cold start for each input and
  restores them afterwards, the same way it pins the exercise rng.
  That pin is not sufficient on its own: the Windows build (Python
  3.12, two campaigns in one process) still recorded the rollover
  body on the first campaign and not the second, so the coverage
  sets disagreed and nothing else did. The tracer therefore does
  not record runner.runner.log at all. An input's coverage depends
  only on its bytes.
- Determinism: one master Random for mutation and base selection,
  pinned per-round Randoms for the exercise harness, length-prefixed
  hashing for the corpus. Same seed, same corpus, same coverage,
  every run. Corpus growth is capped; past the cap a new-coverage
  input evicts the oldest non-seed member (coverage knowledge is
  cumulative -- eviction frees a slot, it does not unlearn a line).
- Platform-relative pins: coverage is a set of (file, line) pairs
  inside runner/, and runner/ carries platform-conditional branches
  (POSIX confinement, Windows paths), so the exact set a campaign
  reaches is a property of the platform it runs on -- as is the
  case of a frame's filename, which on Windows follows however the
  module happened to be imported. The tests therefore pin the
  relationships that hold by construction on any platform (the
  guided coverage includes the seeds-only baseline measured in the
  same process; a seated seed is never evicted, so the corpus
  never drops below the retained seeds; two campaigns at one seed
  in one process are identical) and gate the strict growth claims
  -- guidance reaching PAST the baseline -- to Linux, where they
  were measured. The first Windows CI run of this module (commit
  9d8cdac) is why: growth there is an empirical property of a
  different reachable line set, not a contract.

The in-suite campaign is bounded (150 rounds, a second or so). A
longer one runs standalone, not under the suite:

    python -m runner.tests.test_fuzz_guided [rounds] [seed]

Nothing here starts a process, a sandbox, or a mailbox; the exercise
harness is test_fuzz_surfaces._exercise, unchanged.
"""
import hashlib
import json
import os
import random
import sys
import threading
import unittest

from runner.tests.test_fuzz_surfaces import SEEDS, _exercise, _mutate, _nest

MASTER_SEED = 20261018
SUITE_ROUNDS = 150
MAX_CORPUS = 64

# Pinned harness rng bases. A candidate's exercise rng depends only
# on its position, never on campaign history, so the same bytes earn
# the same coverage whenever they are exercised.
_SEED_RNG_BASE = 1000
_ROUND_RNG_BASE = 5000


def _runner_dir():
    """Absolute path of the runner package, with a trailing separator."""
    import runner

    return os.path.dirname(os.path.abspath(runner.__file__)) + os.sep


class _LineTracer:
    """Collect (relative path, line) hits for frames in runner/ only."""

    def __init__(self, root):
        self.root = root
        # The "is this frame ours" test compares case-insensitively:
        # on Windows the case of a frame's filename follows however
        # the module happened to be imported, while the root comes
        # from runner.__file__, and the two need not agree -- a
        # mismatch would silently trace nothing there. normcase
        # folds case on Windows and is the identity on POSIX, so
        # the lower() makes the comparison uniform everywhere; the
        # root is the imported package's own directory, so treating
        # a case variant of it as the same directory is the intent.
        self.root_key = os.path.normcase(root).lower()
        # The suite and the operator-side cloud scripts live under
        # runner/ but are not the surfaces being measured. A script
        # imported lazily mid-campaign would also fire its import-time
        # lines once per process, so two campaigns would disagree.
        self.skip_keys = tuple(
            os.path.normcase(root + sub + os.sep).lower()
            for sub in ("tests", "cloud"))
        self.hits = set()
        self._rel = {}

    def __call__(self, frame, event, arg):
        if event == "call":
            name = os.path.normcase(frame.f_code.co_filename).lower()
            if name.startswith(self.root_key) and not name.startswith(
                    self.skip_keys):
                return self
            return None
        if event == "line":
            code = frame.f_code
            # runner.runner.log is wall-clock gated (the minute
            # budget above). Recording it makes two campaigns in
            # one process disagree on Windows. It is not parser
            # coverage. mailbox.log is a different function and
            # stays visible until the runner replaces it.
            if code.co_name == "log" and os.path.normcase(
                    code.co_filename).lower().endswith(
                        os.path.normcase(os.sep.join(
                            ("runner", "runner.py")))):
                return self
            rel = self._rel.get(code)
            if rel is None:
                rel = os.path.relpath(code.co_filename, self.root)
                self._rel[code] = rel
            self.hits.add((rel, frame.f_lineno))
        return self


def _exercise_traced(blob, rng):
    """One input against every surface, with coverage and hygiene.

    Returns (crashes, coverage) with the crash contract of
    test_fuzz_surfaces. The trace function and the runner log budget
    are exactly as found when this returns, whatever happened inside.
    """
    import runner.runner as runner_module

    tracer = _LineTracer(_runner_dir())
    saved_trace = sys.gettrace()
    saved_budget = (
        runner_module._LOG_MINUTE,
        runner_module._LOG_COUNT,
        runner_module._LOG_DROPPED,
    )
    runner_module._LOG_MINUTE = 0
    runner_module._LOG_COUNT = 0
    runner_module._LOG_DROPPED = 0
    sys.settrace(tracer)
    try:
        crashes = _exercise(rng, blob)
    finally:
        sys.settrace(saved_trace)
        (
            runner_module._LOG_MINUTE,
            runner_module._LOG_COUNT,
            runner_module._LOG_DROPPED,
        ) = saved_budget
    return crashes, frozenset(tracer.hits)


def seeds_baseline(seed=MASTER_SEED):
    """Coverage the seeds alone reach, exercised once each, no growth."""
    seen = set()
    for i, blob in enumerate(SEEDS):
        _, coverage = _exercise_traced(blob, random.Random(_SEED_RNG_BASE + i))
        seen |= coverage
    return frozenset(seen)


class Corpus:
    """The libFuzzer merge rule, deterministic: new coverage or no seat.

    Members are kept in the order they earned their seat. Past the
    cap, a new-coverage input evicts the oldest non-seed member; if
    every member is a seed the input is refused. Coverage knowledge
    (``seen``) is the union of everything ever seated and never
    shrinks when a member is evicted.
    """

    def __init__(self, max_size=MAX_CORPUS):
        self.max_size = max_size
        self._members = []  # [(blob, is_seed)] in seat order
        self.seen = set()

    def __len__(self):
        return len(self._members)

    @property
    def members(self):
        return [blob for blob, _ in self._members]

    def consider(self, blob, coverage, is_seed=False):
        """Seat ``blob`` iff ``coverage`` adds a line. Returns the verdict."""
        if not (coverage - self.seen):
            return False
        if len(self._members) >= self.max_size:
            victim = None
            for index, (_, seeded) in enumerate(self._members):
                if not seeded:
                    victim = index
                    break
            if victim is None:
                return False
            del self._members[victim]
        self._members.append((bytes(blob), is_seed))
        self.seen |= coverage
        return True


def corpus_hash(members):
    """A stable digest of a corpus: length-prefixed blobs, in order."""
    digest = hashlib.sha256()
    for blob in members:
        digest.update(len(blob).to_bytes(4, "big"))
        digest.update(blob)
    return digest.hexdigest()


class GuidedResult:
    def __init__(self, corpus, coverage, baseline, crashes, retained_seeds):
        self.corpus = corpus
        self.coverage = coverage
        self.baseline = baseline
        self.crashes = crashes
        self.retained_seeds = retained_seeds


def guided_campaign(rounds=SUITE_ROUNDS, seed=MASTER_SEED, max_corpus=MAX_CORPUS):
    """Grow a corpus from the seeds, guided by runner/ line coverage."""
    rng = random.Random(seed)
    corpus = Corpus(max_corpus)
    crashes = []
    baseline = set()
    for i, blob in enumerate(SEEDS):
        found, coverage = _exercise_traced(
            blob, random.Random(_SEED_RNG_BASE + i))
        baseline |= coverage
        corpus.consider(blob, coverage, is_seed=True)
        if found:
            crashes.append((blob[:80], found))
    retained_seeds = len(corpus)
    for i in range(rounds):
        if len(crashes) >= 5:
            break
        base = corpus.members[rng.randrange(len(corpus))]
        blob = _mutate(rng, base)
        if i % 17 == 0:
            blob = json.dumps(_nest(rng, rng.randint(1, 40))).encode()
        found, coverage = _exercise_traced(
            blob, random.Random(_ROUND_RNG_BASE + i))
        if found:
            crashes.append((blob[:80], found))
        corpus.consider(blob, coverage)
    return GuidedResult(
        corpus=corpus.members,
        coverage=frozenset(corpus.seen),
        baseline=frozenset(baseline),
        crashes=crashes,
        retained_seeds=retained_seeds,
    )


class CorpusRuleTest(unittest.TestCase):
    """The merge rule, pinned at unit level with synthetic coverage."""

    def test_no_new_coverage_is_not_retained(self):
        corpus = Corpus()
        self.assertTrue(corpus.consider(b"a", {("x.py", 1)}))
        self.assertFalse(corpus.consider(b"b", {("x.py", 1)}))
        self.assertEqual(corpus.members, [b"a"])

    def test_one_new_line_is_retained(self):
        corpus = Corpus()
        corpus.consider(b"a", {("x.py", 1)})
        self.assertTrue(corpus.consider(b"b", {("x.py", 1), ("x.py", 2)}))
        self.assertEqual(corpus.members, [b"a", b"b"])
        self.assertEqual(corpus.seen, {("x.py", 1), ("x.py", 2)})

    def test_empty_coverage_is_not_retained(self):
        corpus = Corpus()
        self.assertFalse(corpus.consider(b"a", set()))
        self.assertEqual(len(corpus), 0)

    def test_subset_coverage_is_not_retained(self):
        corpus = Corpus()
        corpus.consider(b"a", {("x.py", 1), ("x.py", 2)})
        self.assertFalse(corpus.consider(b"b", {("x.py", 2)}))
        self.assertEqual(corpus.members, [b"a"])

    def test_the_same_blob_twice_seats_once(self):
        corpus = Corpus()
        corpus.consider(b"a", {("x.py", 1)})
        self.assertFalse(corpus.consider(b"a", {("x.py", 1)}))
        self.assertEqual(corpus.members, [b"a"])

    def test_refused_input_does_not_teach_coverage(self):
        corpus = Corpus()
        corpus.consider(b"a", {("x.py", 1)})
        corpus.consider(b"b", {("x.py", 1)})
        self.assertNotIn(("x.py", 2), corpus.seen)

    def test_at_cap_a_new_line_evicts_the_oldest_non_seed(self):
        corpus = Corpus(max_size=2)
        corpus.consider(b"seed", {("x.py", 1)}, is_seed=True)
        corpus.consider(b"m1", {("x.py", 2)})
        self.assertTrue(corpus.consider(b"m2", {("x.py", 3)}))
        self.assertEqual(corpus.members, [b"seed", b"m2"])

    def test_at_cap_all_seeds_refuses(self):
        corpus = Corpus(max_size=1)
        corpus.consider(b"seed", {("x.py", 1)}, is_seed=True)
        self.assertFalse(corpus.consider(b"m", {("x.py", 2)}))
        self.assertEqual(corpus.members, [b"seed"])

    def test_evicted_coverage_stays_known(self):
        corpus = Corpus(max_size=2)
        corpus.consider(b"seed", {("x.py", 1)}, is_seed=True)
        corpus.consider(b"m1", {("x.py", 2)})
        corpus.consider(b"m2", {("x.py", 3)})
        # m1 is evicted, but its line is still known: no new seat for it.
        self.assertFalse(corpus.consider(b"m3", {("x.py", 2)}))

    def test_eviction_never_touches_a_seed_while_a_mutant_sits(self):
        corpus = Corpus(max_size=3)
        corpus.consider(b"s1", {("x.py", 1)}, is_seed=True)
        corpus.consider(b"m1", {("x.py", 2)})
        corpus.consider(b"s2", {("x.py", 3)}, is_seed=True)
        corpus.consider(b"m2", {("x.py", 4)})
        self.assertEqual(corpus.members, [b"s1", b"s2", b"m2"])

    def test_corpus_hash_is_order_and_length_sensitive(self):
        self.assertNotEqual(
            corpus_hash([b"ab", b"c"]), corpus_hash([b"c", b"ab"]))
        self.assertNotEqual(
            corpus_hash([b"ab", b"c"]), corpus_hash([b"a", b"bc"]))
        self.assertEqual(corpus_hash([b"a"]), corpus_hash([b"a"]))


class TracerTest(unittest.TestCase):
    """The coverage feed itself: scoped, stable, and fully removed."""

    def test_coverage_only_names_runner_files(self):
        _, coverage = _exercise_traced(SEEDS[6], random.Random(1))
        self.assertTrue(coverage)
        for rel, line in coverage:
            self.assertFalse(rel.startswith(".."), rel)
            self.assertTrue(rel.endswith(".py"), rel)
            self.assertIsInstance(line, int)

    def test_tracer_sees_a_frame_whose_path_case_differs(self):
        # A frame whose filename is a case variant of the runner
        # root (the Windows import artifact) must still be traced;
        # otherwise coverage there is silently empty and every
        # downstream campaign assertion fails for the wrong reason.
        root = _runner_dir()
        code = compile("a = 1\nb = 2\n",
                       root.swapcase() + "caseprobe.py", "exec")
        tracer = _LineTracer(root)
        saved = sys.gettrace()
        sys.settrace(tracer)
        try:
            exec(code, {})
        finally:
            sys.settrace(saved)
        self.assertTrue(tracer.hits)

    def test_the_same_input_earns_the_same_coverage_twice(self):
        _, first = _exercise_traced(SEEDS[7], random.Random(_SEED_RNG_BASE))
        _, second = _exercise_traced(SEEDS[7], random.Random(_SEED_RNG_BASE))
        self.assertEqual(first, second)

    def test_trace_function_is_restored_after_a_run(self):
        before = sys.gettrace()
        _exercise_traced(SEEDS[0], random.Random(1))
        self.assertIs(sys.gettrace(), before)

    def test_a_preexisting_trace_function_survives(self):
        saved = sys.gettrace()

        def dummy(frame, event, arg):
            return None

        sys.settrace(dummy)
        try:
            _exercise_traced(SEEDS[0], random.Random(1))
            self.assertIs(sys.gettrace(), dummy)
        finally:
            sys.settrace(saved)

    def test_threading_trace_is_untouched(self):
        if not hasattr(threading, "gettrace"):
            self.skipTest("threading.gettrace needs 3.10+")
        before = threading.gettrace()
        _exercise_traced(SEEDS[0], random.Random(1))
        self.assertIs(threading.gettrace(), before)

    def test_no_monitoring_tool_is_registered(self):
        if not hasattr(sys, "monitoring"):
            self.skipTest("sys.monitoring needs 3.12+")
        tool_ids = range(6)
        before = {i: sys.monitoring.get_tool(i) for i in tool_ids}
        _exercise_traced(SEEDS[0], random.Random(1))
        after = {i: sys.monitoring.get_tool(i) for i in tool_ids}
        self.assertEqual(before, after)

    def test_log_budget_globals_are_restored(self):
        import runner.runner as runner_module

        saved = (
            runner_module._LOG_MINUTE,
            runner_module._LOG_COUNT,
            runner_module._LOG_DROPPED,
        )
        runner_module._LOG_MINUTE = 424242.0
        runner_module._LOG_COUNT = 7
        runner_module._LOG_DROPPED = 3
        try:
            _exercise_traced(SEEDS[6], random.Random(1))
            self.assertEqual(
                (
                    runner_module._LOG_MINUTE,
                    runner_module._LOG_COUNT,
                    runner_module._LOG_DROPPED,
                ),
                (424242.0, 7, 3),
            )
        finally:
            (
                runner_module._LOG_MINUTE,
                runner_module._LOG_COUNT,
                runner_module._LOG_DROPPED,
            ) = saved


class GuidedCampaignTest(unittest.TestCase):
    """The campaign as a whole, at the pinned master seed."""

    @classmethod
    def setUpClass(cls):
        cls.result = guided_campaign()

    def test_guided_campaign_finds_no_crashes(self):
        self.assertEqual(self.result.crashes, [])

    def test_coverage_includes_the_seed_baseline(self):
        # By construction, on any platform: the campaign exercises
        # every seed first and coverage knowledge only ever grows,
        # so the guided set includes the seeds-only baseline from
        # the same run.
        self.assertTrue(self.result.baseline)
        self.assertLessEqual(self.result.baseline, self.result.coverage)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "strict growth is measured on Linux; another platform "
        "reaches a different platform-conditional line set")
    def test_feedback_grows_coverage_past_the_seeds(self):
        # Strict growth is empirical, not a construction guarantee:
        # a mutant seats only if it reaches a line no seed reached,
        # and which lines exist to reach differs by platform
        # (runner/ has POSIX-only and Windows-only branches). On
        # Linux the measured campaign grows past the baseline; on
        # Windows only the inclusion contract above is promised.
        self.assertLess(self.result.baseline, self.result.coverage)

    def test_the_baseline_is_the_seeds_only_measure(self):
        self.assertEqual(self.result.baseline, seeds_baseline())

    def test_corpus_never_drops_below_the_retained_seeds(self):
        # By construction, on any platform: the merge rule evicts
        # the oldest NON-seed member and refuses when every member
        # is a seed, so a seated seed is never evicted -- the
        # corpus holds the retained seeds plus seated mutants,
        # never fewer than the seeds, never more than the cap.
        self.assertGreaterEqual(
            len(self.result.corpus), self.result.retained_seeds)
        self.assertLessEqual(len(self.result.corpus), MAX_CORPUS)

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "strict growth is measured on Linux; another platform "
        "reaches a different platform-conditional line set")
    def test_corpus_grows_beyond_the_seed_set(self):
        # The corpus-side form of the strict growth claim, gated
        # for the same reason: seating even one mutant requires a
        # new line, and the reachable new lines are platform-set.
        self.assertGreater(
            len(self.result.corpus), self.result.retained_seeds)

    def test_corpus_keeps_its_seeds_first(self):
        seeds_first = self.result.corpus[: self.result.retained_seeds]
        for blob in seeds_first:
            self.assertIn(blob, SEEDS)

    def test_determinism_same_seed_same_corpus_and_coverage(self):
        again = guided_campaign()
        self.assertEqual(self.result.corpus, again.corpus)
        self.assertEqual(
            corpus_hash(self.result.corpus), corpus_hash(again.corpus))
        self.assertEqual(self.result.coverage, again.coverage)
        self.assertEqual(self.result.baseline, again.baseline)

    def test_campaigns_do_not_share_state(self):
        again = guided_campaign(rounds=10)
        self.assertIsNot(self.result.corpus, again.corpus)
        again.corpus.append(b"intruder")
        self.assertNotIn(b"intruder", self.result.corpus)


if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else MASTER_SEED
    result = guided_campaign(rounds=rounds, seed=seed)
    print(
        "rounds=%d seed=%d corpus=%d (seeds kept=%d) coverage=%d "
        "baseline=%d growth=%d crashes=%d"
        % (
            rounds,
            seed,
            len(result.corpus),
            result.retained_seeds,
            len(result.coverage),
            len(result.baseline),
            len(result.coverage) - len(result.baseline),
            len(result.crashes),
        )
    )
    print("corpus sha256:", corpus_hash(result.corpus))
    if result.crashes:
        for blob, found in result.crashes:
            print(found, blob)
        raise SystemExit(1)
    print("guided campaign ok")
