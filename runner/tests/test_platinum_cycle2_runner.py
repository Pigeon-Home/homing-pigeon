# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Project Platinum, cycle 2 (scoring lane): the next ranked gap
tests for runner/runner.py, from the fresh cycle-2 coverage
measurement at 06e974c1 (statements 3,955 covered of 3,992, 37
missed; the record sits in docs/steady/reports/).

Ranked by runner/tools/coverage_targets.py on that measurement,
top-down (logic, then guard, then except), starting with the
channel-refusal sweep the lane was aimed at first:

  _sweep_channel_refusals -- zero missing statements at this head
      (the cycle-1 gap of 13 was closed by test_platinum_runner,
      test_delivery_edges and test_result_size). What remains
      unpinned is its behaviour ACROSS channels in one sweep:
      mixed outcomes per channel, a channel whose paths raise,
      a channel with no failed/ dir, transports absent, and a
      second sweep answering nothing twice. Those are pinned
      here as deterministic multi-channel cases.
  logic  _env_salt (2574, 2588-2589, 2593, 2594-2595, 2600) --
      no base, a salt that cannot be removed, a creation that
      fails, a creation race lost twice.
  logic  env_fingerprint (2615, 2618, 2621-2622) -- no salt, the
      protocol v2 version joining the list, a card that raises.
  logic  _learning_freeze (4526, 4532-4535) -- a corroborated
      lesson recorded on the frozen record; a freeze that blows
      up inside reads as None, never as a raise.
  logic  save_seen merge (5090) -- a non-dict disk value merges
      as an empty dict. (Through _with_seen_file the value is
      pre-guarded, so this pins merge's own contract at its seam.)
  guard  ask_model (812) -- a re-ask that reports a format
      problem through .get(\"answer\") but carries no \"answer\"
      key (a rejection shape) passes through as the answer; the
      clean re-ask beside it is pinned too.
  guard  _deliver_stash_held (1799) -- a claim move that fails
      sends nothing.
  guard  load_retained (2477) -- a stored path that escapes the
      retained dir reads as no record.
  guard  _model_oracle_configured (3748) -- blank or non-string
      endpoint/model is not a configured model.
  guard  ensure_inference_ready (5517) -- an endpoint with no
      host is not dialled. (inference_config guarantees a host,
      so this pins the guard at its seam.)
  except _unclaim_stash (1783-1786) -- a write that fails puts
      nothing back and says False.
  except _deliver_stash_held (1806) -- a send that fails whose
      unclaim also fails is given up, False.
  except result_digest (2014-2015) -- a result whose mapping
      raises while it is read cannot be signed, so no digest.
  except chain_commit (2059) -- an unsignable result commits
      no link.
  except declare_ps1_utf8 (2675-2676) -- a .ps1 that cannot be
      read (missing, or a directory) is left as it arrived.

Two missed arms are deliberately not chased here, with the
reason recorded in the cycle-2 record: the __main__ dispatch
lines and the sibling-import guard run only when the file is
executed as a script (the suite imports it), and
_oracle_instruction_kind's post-prefix empty-clause continue
(1369) cannot be reached with the current polite-prefix table:
every prefix ends in a space, and the lead it is stripped from
is a single-space join of words, so a lead can never equal a
prefix and a successful strip never leaves zero words. The
observable behaviour of a prefix-only owner message is pinned
below anyway.

No production code is touched by this module.
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from runner import runner as R
from runner.wire import transports as T

TESTKEY = "Cycle2" + "Key-9d4c" + "2b7eA1f0" + "C3d5e6B8" + "a9F0e1D2"


def _cfg():
    return {"shared_secret": TESTKEY}


def _payload(job_id, marker="payload"):
    return {"job_id": job_id, "exit_code": 0, "stdout": marker,
            "stderr": "", "truncated": False}


def _plant_sent_record(base, cfg, job_id, stubbed=False):
    """A genuine record in sent/, built through the runner's own
    stash path so its body is a real signed one."""
    body = R._outgoing_result_body(_payload(job_id), TESTKEY, False,
                                   job_id, "")
    skey = R._seen_key(cfg, job_id)
    job = {"job_id": job_id}
    subject = f"[HOMING-PIGEON] result {job_id}"
    assert R.stash_result(base, skey, job, subject, body, key_id="",
                          encrypted=False)
    if stubbed:
        rec = R._read_record(R._stash_path(base, skey))
        rec["stubbed"] = True
        R._atomicio.write_json(R._stash_path(base, skey), rec)
    assert R._stash_move(base, skey, os.path.join(base, "sent"))
    return skey


def _plant_stash(base, cfg, job_id):
    """A genuine record waiting in the outbox stash."""
    body = R._outgoing_result_body(_payload(job_id), TESTKEY, False,
                                   job_id, "")
    skey = R._seen_key(cfg, job_id)
    job = {"job_id": job_id}
    subject = f"[HOMING-PIGEON] result {job_id}"
    assert R.stash_result(base, skey, job, subject, body, key_id="",
                          encrypted=False)
    return skey


def _plant_refusal(base, name, stem, reason_text, result_text):
    paths = T.ensure_channel_dirs(base, name)
    failed = os.path.join(paths["outbox"], "failed")
    os.makedirs(failed, exist_ok=True)
    with open(os.path.join(failed, stem + ".refused.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(reason_text)
    if result_text is not None:
        with open(os.path.join(failed, stem + ".result.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(result_text)
    return paths


def _result_text(job_id):
    return T.format_envelope(f"[HOMING-PIGEON] result {job_id}",
                             "the refused body")


class SweepAcrossChannelsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-c2-sweep-")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.cfg = _cfg()

    def test_refusals_across_channels_in_one_sweep(self):
        names = ["queues", "file", "nats"]
        for i, name in enumerate(names):
            job_id = f"job-multi-{i}"
            _plant_sent_record(self.base, self.cfg, job_id)
            _plant_refusal(self.base, name, f"stem{i}",
                           "refused for good", _result_text(job_id))
        handled = R._sweep_channel_refusals(self.base, self.cfg, names)
        self.assertEqual(handled, 3)
        for i, name in enumerate(names):
            job_id = f"job-multi-{i}"
            paths = T.channel_paths(self.base, name)
            stub = os.path.join(paths["outbox"], f"stem{i}.result.txt")
            self.assertTrue(os.path.isfile(stub),
                            f"no stub written to {name}")
            with open(stub, encoding="utf-8") as fh:
                self.assertIn(f"result {job_id}", fh.read())
            self.assertTrue(os.path.isfile(os.path.join(
                paths["outbox_done"], f"stem{i}.refused.txt")))
            self.assertTrue(os.path.isfile(os.path.join(
                self.base, "work", job_id, "result.json")),
                "the original result was not kept")
            rec = R._read_record(R._sent_path(
                self.base, R._seen_key(self.cfg, job_id)))
            self.assertTrue(rec.get("stubbed"))

    def test_one_sweep_with_mixed_outcomes_per_channel(self):
        # live record: the stub goes back out (handled)
        _plant_sent_record(self.base, self.cfg, "job-live")
        _plant_refusal(self.base, "live-chan", "stem-live",
                       "refused", _result_text("job-live"))
        # already-stubbed record: given up (handled)
        _plant_sent_record(self.base, self.cfg, "job-twice",
                           stubbed=True)
        _plant_refusal(self.base, "twice-chan", "stem-twice",
                       "refused again", _result_text("job-twice"))
        # no record, but a result file: stays in failed/ (not handled)
        _plant_refusal(self.base, "wait-chan", "stem-wait",
                       "refused", _result_text("job-late"))
        # no record and no result file: filed to done/ (handled)
        _plant_refusal(self.base, "bare-chan", "stem-bare",
                       "refused", None)
        names = ["live-chan", "twice-chan", "wait-chan", "bare-chan"]
        handled = R._sweep_channel_refusals(self.base, self.cfg, names)
        self.assertEqual(handled, 3)
        wait = T.channel_paths(self.base, "wait-chan")
        self.assertTrue(os.path.isfile(os.path.join(
            wait["outbox"], "failed", "stem-wait.refused.txt")))
        self.assertFalse(os.path.exists(os.path.join(
            wait["outbox_done"], "stem-wait.refused.txt")))
        bare = T.channel_paths(self.base, "bare-chan")
        self.assertTrue(os.path.isfile(os.path.join(
            bare["outbox_done"], "stem-bare.refused.txt")))
        # the given-up record left sent/ for the runner's own failed/
        skey = R._seen_key(self.cfg, "job-twice")
        self.assertFalse(os.path.exists(R._sent_path(self.base, skey)))
        self.assertTrue(os.path.isfile(os.path.join(
            self.base, "outbox", "failed", R._record_name(skey))))

    def test_a_channel_that_raises_does_not_stop_the_sweep(self):
        _plant_sent_record(self.base, self.cfg, "job-good")
        _plant_refusal(self.base, "good-chan", "stem-good",
                       "refused", _result_text("job-good"))
        real_paths = T.channel_paths

        def flaky(base_dir, name):
            if name == "boom-chan":
                raise RuntimeError("channel exploded")
            return real_paths(base_dir, name)

        with mock.patch.object(T, "channel_paths", flaky):
            handled = R._sweep_channel_refusals(
                self.base, self.cfg, ["boom-chan", "good-chan"])
        self.assertEqual(handled, 1)

    def test_a_channel_with_no_failed_dir_is_skipped(self):
        _plant_sent_record(self.base, self.cfg, "job-good")
        _plant_refusal(self.base, "good-chan", "stem-good",
                       "refused", _result_text("job-good"))
        handled = R._sweep_channel_refusals(
            self.base, self.cfg, ["never-planted", "good-chan"])
        self.assertEqual(handled, 1)

    def test_no_transports_returns_zero(self):
        _plant_refusal(self.base, "queues", "stem", "refused",
                       _result_text("job-x"))
        with mock.patch.object(R, "_transports", None):
            self.assertEqual(
                R._sweep_channel_refusals(self.base, self.cfg,
                                          ["queues"]), 0)

    def test_a_second_sweep_answers_nothing_twice(self):
        _plant_sent_record(self.base, self.cfg, "job-once")
        _plant_refusal(self.base, "queues", "stem-once",
                       "refused", _result_text("job-once"))
        _plant_refusal(self.base, "queues", "stem-wait",
                       "refused", _result_text("job-late"))
        first = R._sweep_channel_refusals(self.base, self.cfg,
                                          ["queues"])
        second = R._sweep_channel_refusals(self.base, self.cfg,
                                           ["queues"])
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)

    def test_repeated_and_empty_names_count_once(self):
        _plant_sent_record(self.base, self.cfg, "job-dup")
        _plant_refusal(self.base, "queues", "stem-dup",
                       "refused", _result_text("job-dup"))
        handled = R._sweep_channel_refusals(
            self.base, self.cfg, ["queues", "queues"])
        self.assertEqual(handled, 1)
        self.assertEqual(
            R._sweep_channel_refusals(self.base, self.cfg, []), 0)
        self.assertEqual(
            R._sweep_channel_refusals(self.base, self.cfg, None), 0)


class EnvSaltGapsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-c2-salt-")
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_no_base_no_salt(self):
        self.assertIsNone(R._env_salt(""))
        self.assertIsNone(R._env_salt(None))

    def test_a_salt_that_cannot_be_removed_reads_as_none(self):
        # A directory where the salt file belongs: the read fails
        # with an OSError that is not FileNotFoundError, and the
        # remove that should clear it fails the same way.
        os.mkdir(os.path.join(self.base, R.ENV_SALT_FILE))
        self.assertIsNone(R._env_salt(self.base))

    @unittest.skipUnless(os.name == "posix", "POSIX only")
    def test_a_dangling_salt_symlink_loses_the_race_twice(self):
        # The read sees no file (the link's target is missing) and
        # the exclusive create refuses because the link is there:
        # both attempts are lost and there is no salt.
        link = os.path.join(self.base, R.ENV_SALT_FILE)
        os.symlink(os.path.join(self.base, "missing-target"), link)
        self.assertIsNone(R._env_salt(self.base))
        self.assertTrue(os.path.islink(link))

    def test_a_failed_salt_creation_reads_as_none(self):
        real_open = os.open

        def fake_open(path, flags, mode=0o777, **kw):
            if str(path).endswith(R.ENV_SALT_FILE):
                raise OSError("no space left on device")
            return real_open(path, flags, mode, **kw)

        with mock.patch.object(os, "open", fake_open):
            self.assertIsNone(R._env_salt(self.base))


class EnvFingerprintGapsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-c2-fp-")
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_no_salt_no_fingerprint(self):
        missing = os.path.join(self.base, "missing")
        self.assertIsNone(
            R.env_fingerprint({"pong_platform": "full"}, missing))

    def test_protocol_v2_joins_the_version_list(self):
        # The card builder itself is test_env_fingerprint's
        # subject; here the versions list runner.py hands it is
        # the subject, so the card is a recording fake. (Driving
        # the real builder under the Windows simulation also hits
        # the sim's missing _winapi, an artifact of the surface,
        # not of either function.)
        cfg = {"pong_platform": "full", "protocol_v2": True}
        seen = {}

        def fake_fingerprint(salt, cfg_arg, versions, version):
            seen["versions"] = list(versions)
            seen["salt"] = salt
            return "fp-sentinel"

        with mock.patch.object(R._platformcard, "env_fingerprint",
                               fake_fingerprint):
            got = R.env_fingerprint(cfg, self.base)
        self.assertEqual(got, "fp-sentinel")
        self.assertEqual(seen["versions"], [R.PROTOCOL_VERSION, 2])
        self.assertEqual(seen["salt"], R._env_salt(self.base))

    def test_a_card_that_raises_reads_as_no_fingerprint(self):
        with mock.patch.object(R._platformcard, "env_fingerprint",
                               side_effect=RuntimeError("card down")):
            self.assertIsNone(R.env_fingerprint(
                {"pong_platform": "full"}, self.base))


class AskModelReaskTest(unittest.TestCase):
    def test_a_clean_reask_is_the_answer(self):
        bad = '{"name": "run", "parameters": {"command": "ls"}}'
        good = {"answer": "The job finished cleanly."}
        with mock.patch.object(
                R, "_ask_model_once",
                side_effect=[{"answer": bad}, good]) as once:
            out = R.ask_model({}, "what happened?", "output", 2000)
        self.assertIs(out, good)
        self.assertEqual(once.call_count, 2)
        reask_question = once.call_args_list[1].args[1]
        self.assertTrue(reask_question.startswith("what happened?"))

    def test_a_rejection_shaped_reask_passes_through(self):
        # The arm at 812 is reached only by a retry whose
        # .get("answer") reports a format problem while the
        # mapping carries no "answer" key at all -- a rejection
        # shape. A plain dict cannot do both (an absent key reads
        # back as None, which is no problem), so the mapping here
        # is one whose get and contains disagree, the hostile
        # shape this codebase's other readers are written for.
        bad = '{"name": "run", "parameters": {"command": "ls"}}'

        class DisagreeingDict(dict):
            def get(self, key, default=None):
                return bad

        retry = DisagreeingDict()
        self.assertNotIn("answer", retry)
        with mock.patch.object(
                R, "_ask_model_once",
                side_effect=[{"answer": bad}, retry]):
            out = R.ask_model({}, "what happened?", "output", 2000)
        self.assertIs(out, retry)


class OracleInstructionKindBehaviourTest(unittest.TestCase):
    def test_a_prefix_only_message_is_a_question(self):
        # The observable contract around the post-prefix arm: a
        # message that is nothing but a politeness prefix (plus
        # its punctuation) dispatches nothing.
        self.assertEqual(R._oracle_instruction_kind("please."),
                         "question")
        self.assertEqual(R._oracle_instruction_kind("Can you?"),
                         "question")

    def test_a_prefix_before_an_action_still_dispatches(self):
        self.assertEqual(
            R._oracle_instruction_kind("please restart the runner"),
            "action")


class UnclaimStashGapsTest(unittest.TestCase):
    def test_a_failed_write_puts_nothing_back(self):
        base = tempfile.mkdtemp(prefix="hp-c2-unclaim-")
        self.addCleanup(shutil.rmtree, base, True)
        with mock.patch.object(R._atomicio, "write_json",
                               side_effect=OSError("disk full")):
            self.assertFalse(
                R._unclaim_stash(base, "skey", {"job_id": "j1"}))


class DeliverStashHeldGapsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-c2-deliver-")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.cfg = _cfg()

    def test_a_failed_claim_move_sends_nothing(self):
        skey = _plant_stash(self.base, self.cfg, "job-claim")
        sender = mock.Mock()
        with mock.patch.object(R, "_stash_move", return_value=False):
            self.assertFalse(
                R._deliver_stash_held(self.base, skey, sender,
                                      self.cfg))
        sender.assert_not_called()

    def test_a_failed_send_with_a_failed_unclaim_is_given_up(self):
        skey = _plant_stash(self.base, self.cfg, "job-stuck")
        sender = mock.Mock(side_effect=RuntimeError("smtp down"))
        with mock.patch.object(R, "_unclaim_stash", return_value=False):
            self.assertFalse(
                R._deliver_stash_held(self.base, skey, sender,
                                      self.cfg))
        sender.assert_called_once()


class HostileMapping(dict):
    """A mapping that raises while it is being read: a result of
    this shape cannot be serialized, so it cannot be signed."""

    def items(self):
        raise ValueError("hostile items")


class ResultDigestGapsTest(unittest.TestCase):
    def test_a_result_that_raises_while_read_has_no_digest(self):
        self.assertIsNone(R.result_digest(HostileMapping(a=1)))

    def test_an_ordinary_result_still_digests(self):
        digest = R.result_digest({"a": 1})
        self.assertEqual(len(digest), 96)
        int(digest, 16)


class ChainCommitGapsTest(unittest.TestCase):
    def test_an_unsignable_result_commits_no_link(self):
        base = tempfile.mkdtemp(prefix="hp-c2-chain-")
        self.addCleanup(shutil.rmtree, base, True)
        self.assertIsNone(
            R.chain_commit(base, "owner", 1, HostileMapping(a=1)))
        self.assertFalse(
            os.path.exists(os.path.join(base, R.CHAIN_FILE)))

    def test_a_signable_result_commits_its_link(self):
        base = tempfile.mkdtemp(prefix="hp-c2-chain-")
        self.addCleanup(shutil.rmtree, base, True)
        result = {"job_id": "j1", "exit_code": 0}
        R.chain_commit(base, "owner", 3, result)
        state = R._chain_state(base)
        self.assertEqual(state["owner"]["seq"], 3)
        self.assertEqual(state["owner"]["last"],
                         R.result_digest(result))


class LoadRetainedGapsTest(unittest.TestCase):
    def test_a_stored_path_outside_the_retained_dir_reads_as_none(self):
        base = tempfile.mkdtemp(prefix="hp-c2-retained-")
        self.addCleanup(shutil.rmtree, base, True)
        retained = os.path.join(base, "retained")
        os.makedirs(retained)
        with open(os.path.join(retained, "job1.json"), "w",
                  encoding="utf-8") as fh:
            fh.write('{"job_id": "job1"}')
        self.assertEqual(R.load_retained(base, "job1"),
                         {"job_id": "job1"})
        with mock.patch.object(os.path, "commonpath",
                               return_value="/somewhere/else"):
            self.assertIsNone(R.load_retained(base, "job1"))


class DeclarePs1Utf8GapsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-c2-ps1-")
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_a_missing_ps1_is_left_alone(self):
        path = os.path.join(self.base, "nope.ps1")
        self.assertIsNone(R.declare_ps1_utf8(path))
        self.assertFalse(os.path.exists(path))

    def test_a_directory_named_ps1_is_left_alone(self):
        path = os.path.join(self.base, "dir.ps1")
        os.mkdir(path)
        self.assertIsNone(R.declare_ps1_utf8(path))
        self.assertTrue(os.path.isdir(path))
        self.assertEqual(os.listdir(path), [])


class ModelOracleConfiguredGapsTest(unittest.TestCase):
    def test_blank_or_nonstring_endpoint_or_model_is_not_configured(self):
        for inf in ({"endpoint": "", "model": "m"},
                    {"endpoint": "http://127.0.0.1:11434",
                     "model": "  "},
                    {"endpoint": 7, "model": "m"},
                    {"endpoint": "http://127.0.0.1:11434",
                     "model": None}):
            with self.subTest(inf=inf):
                self.assertFalse(
                    R._model_oracle_configured({"inference": inf}))

    def test_a_loopback_endpoint_with_a_model_is_configured(self):
        self.assertTrue(R._model_oracle_configured(
            {"inference": {"endpoint": "http://127.0.0.1:11434",
                           "model": "m"}}))


class LearningFreezeGapsTest(unittest.TestCase):
    PLAN = {"active": True, "mode": "advisory", "findings": [],
            "checks_run": True,
            "repair_action": {"action": "restart",
                              "description": "restart it"}}

    def _gates(self, record):
        return (
            mock.patch.object(R._learning, "learning_enabled",
                              return_value=True),
            mock.patch.object(R._opinion, "verdict_of",
                              return_value="pass"),
            mock.patch.object(R._learning, "feature_keys",
                              return_value=["tool:sh"]),
            mock.patch.object(R._opinion, "received_digest",
                              return_value="d"),
            mock.patch.object(R._learning, "prediction_record",
                              return_value=record),
            mock.patch.object(R._learning, "freeze", return_value=True),
        )

    def test_a_corroborated_lesson_is_recorded_on_the_freeze(self):
        record = {"id": "job-lesson"}
        relevant = {"corroborated": [
            {"claim_key": "claim-1", "features": ["tool:sh"]}]}
        gates = self._gates(record)
        for gate in gates:
            gate.start()
        try:
            out = R._learning_freeze({}, "/tmp", "job-lesson", {},
                                     dict(self.PLAN), {}, relevant)
        finally:
            for gate in reversed(gates):
                gate.stop()
        self.assertIs(out, record)
        self.assertEqual(out["lesson_selected"], "claim-1")

    def test_a_freeze_that_blows_up_inside_reads_as_none(self):
        plan = {"active": True, "mode": "advisory", "findings": [],
                "checks_run": True}
        with mock.patch.object(R._learning, "learning_enabled",
                               return_value=True), \
                mock.patch.object(R._opinion, "verdict_of",
                                  return_value="pass"), \
                mock.patch.object(R._learning, "feature_keys",
                                  return_value=[]), \
                mock.patch.object(R._opinion, "received_digest",
                                  return_value="d"), \
                mock.patch.object(R._learning, "prediction_record",
                                  side_effect=RuntimeError("boom")):
            self.assertIsNone(R._learning_freeze(
                {}, "/tmp", "job-boom", {}, plan, {}, None))


class SaveSeenMergeGapsTest(unittest.TestCase):
    def test_a_non_dict_disk_value_merges_as_empty(self):
        captured = {}

        def fake_with_seen_file(path, mutator):
            captured["merged"] = mutator(["not", "a", "dict"])
            return captured["merged"]

        seen = {"k1": True}
        with mock.patch.object(R, "_with_seen_file",
                               fake_with_seen_file):
            R.save_seen("/tmp/cycle2-seen.json", seen)
        self.assertEqual(captured["merged"], {"k1": True})
        self.assertEqual(seen, {"k1": True})


class EnsureInferenceReadyGapsTest(unittest.TestCase):
    def test_an_endpoint_with_no_host_is_not_dialled(self):
        with mock.patch.object(
                R, "inference_config",
                return_value={"endpoint": "no-host-in-this-string"}), \
                mock.patch.object(
                    R.socket, "create_connection",
                    side_effect=AssertionError("dialled")) as dial:
            self.assertIsNone(R.ensure_inference_ready({}))
        dial.assert_not_called()


if __name__ == "__main__":
    unittest.main()
