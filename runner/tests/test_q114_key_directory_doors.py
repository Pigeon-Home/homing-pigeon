# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Q114: the key directory speaks at the job's door and the DTLS door.

3.14.32 shipped the directory (`key_directory` / `key_directory_file`,
one entry per key: fingerprint, state, not_before, not_after) with
its verdict wired at the query, board, v2 and cancel doors only. A
job signed by a key the directory called `compromised` still ran,
and a DTLS handshake under that key still authenticated. Now the
verdict comes first at the job's door (`check_key_policy`), the DTLS
pipe's PSK lookup answers None for a key the directory refuses (so a
fresh handshake and a resumption ticket under that key both fail),
an entry's `fingerprint` must be the key's own, and `not_before`
admits nothing before it.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner import runner as R  # noqa: E402
from runner.guard.security import key_fingerprint  # noqa: E402
from runner.transport_extensions.dtls import __main__ as pipe  # noqa: E402
from runner.wire import dtlsproto, verify  # noqa: E402
from runner.tests.test_runner import (  # noqa: E402
    SECRET as CURRENT, FakeIMAP, FakeSMTP, job_email, job_payload)

OLD = "9f8e7d6c5b4a39281706f5e4d3c2b1a0f9e8d7c6b5a4938271605f4e3d2c1b0a"
NOW = 1_000_000.0
JOB = {"job_id": "q114", "kind": "ping"}


def _cfg(directory=None, **over):
    cfg = {"shared_secret": CURRENT, "additional_secrets": {"old": OLD}}
    if directory is not None:
        cfg["key_directory"] = directory
    cfg.update(over)
    return cfg


class JobDoorTest(unittest.TestCase):
    """`check_key_policy`, the job's door, under a directory."""

    def setUp(self):
        self.secrets = R.build_secrets(_cfg())

    def _verdict(self, directory, key_id="old", cfg=None):
        return verify.check_key_policy({}, key_id, cfg or _cfg(directory), JOB,
                                       secrets=self.secrets)

    def test_no_directory_leaves_the_door_as_it_was(self):
        self.assertIsNone(self._verdict(None))

    def test_a_compromised_key_runs_nothing(self):
        self.assertEqual("key is compromised",
                         self._verdict({"old": {"state": "compromised"},
                                        "": {"state": "in_use"}}))

    def test_a_key_with_no_entry_runs_nothing(self):
        self.assertIn("no key directory entry",
                      self._verdict({"": {"state": "in_use"}}))

    def test_in_use_and_an_open_superseded_run_and_no_other_state_does(self):
        for state in verify.KEY_STATES:
            got = self._verdict({"old": {"state": state}})
            if state in ("in_use", "superseded"):
                self.assertIsNone(got, state)
            else:
                self.assertIsNotNone(got, state)
        self.assertIn("invalid key directory state",
                      self._verdict({"old": {"state": "retired"}}))

    def test_the_owner_is_read_under_any_of_its_names(self):
        fp = key_fingerprint(CURRENT)
        self.assertIsNone(self._verdict({fp: {"state": "in_use"}}, key_id=""))
        self.assertIsNone(self._verdict({"": {"state": "in_use"}}, key_id=fp))
        self.assertIn("no key directory entry",
                      self._verdict({"old": {"state": "in_use"}}, key_id=""))

    def test_one_key_under_two_names_is_refused_under_either(self):
        # Q115 (the keydir target's first crash): an entry under "" and
        # one under the fingerprint read differently by the name used.
        fp = key_fingerprint(CURRENT)
        two = {"": "job", fp: {"state": "in_use"}, "old": {"state": "in_use"}}
        under_empty = self._verdict(two, key_id="")
        under_fp = self._verdict(two, key_id=fp)
        self.assertEqual(under_empty, under_fp)
        self.assertIn("under two ids", under_empty)
        with self.assertRaises(RuntimeError) as ctx:
            verify.validate_key_directory(_cfg(two), self.secrets)
        self.assertIn("one key under two ids", str(ctx.exception))

    def test_a_fingerprint_must_be_the_keys_own(self):
        self.assertIsNone(self._verdict(
            {"old": {"state": "in_use", "fingerprint": key_fingerprint(OLD)}}))
        self.assertIn("fingerprint does not match", self._verdict(
            {"old": {"state": "in_use", "fingerprint": key_fingerprint(CURRENT)}}))
        self.assertIn("fingerprint does not match", self._verdict(
            {"old": {"state": "in_use", "fingerprint": 7}}))

    def test_not_before_and_not_after_bound_the_key(self):
        import time
        now = time.time()
        self.assertIn("not yet valid", self._verdict(
            {"old": {"state": "in_use", "not_before": now + 3600}}))
        self.assertIsNone(self._verdict(
            {"old": {"state": "in_use", "not_before": now - 3600}}))
        self.assertIn("window has closed", self._verdict(
            {"old": {"state": "superseded", "not_after": now - 1}}))
        self.assertIsNone(self._verdict(
            {"old": {"state": "superseded", "not_after": now + 3600}}))
        self.assertIn("invalid key directory not_before", self._verdict(
            {"old": {"state": "in_use", "not_before": "soon"}}))
        self.assertIn("past its not_after", self._verdict(
            {"old": {"state": "in_use", "not_after": now - 1}}))
        self.assertIsNone(self._verdict(
            {"old": {"state": "in_use", "not_after": now + 3600}}))

    def test_the_directory_speaks_before_the_policy(self):
        cfg = _cfg({"old": {"state": "compromised"}},
                   key_policies={"old": {"allowed_kinds": ["ping"]}})
        self.assertEqual("key is compromised",
                         verify.check_key_policy(R.build_key_policies(cfg), "old",
                                                 cfg, JOB, secrets=self.secrets))

    def test_a_file_directory_is_read_and_an_unreadable_one_refuses(self):
        td = tempfile.mkdtemp(prefix="hp-q114-")
        self.addCleanup(shutil.rmtree, td, True)
        path = os.path.join(td, "keys.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"old": {"state": "in_use"}}, fh)
        self.assertIsNone(self._verdict(None, cfg=_cfg(key_directory_file=path)))
        os.remove(path)
        self.assertIn("key directory unreadable",
                      self._verdict(None, cfg=_cfg(key_directory_file=path)))
        self.assertIn("mutually exclusive", self._verdict(
            None, cfg=_cfg({"old": {"state": "in_use"}}, key_directory_file=path)))


class StartupCheckTest(unittest.TestCase):
    """A directory is checked whole at startup (`validate_key_directory`)."""

    def test_a_good_directory_passes_and_each_fault_names_its_entry(self):
        secrets = R.build_secrets(_cfg())
        good = {"old": {"state": "in_use", "fingerprint": key_fingerprint(OLD)},
                "": {"state": "superseded", "not_after": 1}}
        self.assertEqual(good, verify.validate_key_directory(_cfg(good), secrets))
        self.assertIsNone(verify.validate_key_directory(_cfg(), secrets))
        for bad, word in (({"old": "in_use"}, "is not an object"),
                          ({"old": {"state": "live"}}, "state must be one of"),
                          ({"old": {"state": "in_use", "not_after": "soon"}}, "not a number"),
                          ({"old": {"state": "in_use", "not_before": True}}, "not a number"),
                          ({"old": {"state": "in_use", "fingerprint": 1}}, "not a string"),
                          ({"old": {"state": "in_use", "fingerprint": key_fingerprint(CURRENT)}},
                           "not the fingerprint of the key named 'old'")):
            with self.assertRaises(RuntimeError) as ctx:
                verify.validate_key_directory(_cfg(bad), secrets)
            self.assertIn(word, str(ctx.exception), bad)
            self.assertIn("key_directory['old']", str(ctx.exception), bad)

    def test_an_unknown_keys_fingerprint_is_not_judged(self):
        # An entry for a key the runner does not hold yet (ordered,
        # generated) cannot be checked against a secret; it passes the
        # startup check and refuses at the doors as its state says.
        secrets = R.build_secrets(_cfg())
        entry = {"next": {"state": "generated", "fingerprint": "k-00000000"}}
        self.assertEqual(entry, verify.validate_key_directory(_cfg(entry), secrets))


class MailboxDoorTest(unittest.TestCase):
    """The same verdict through a poll cycle: a job under a
    compromised key is refused in silence; the control runs."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-q114-mail-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _cycle(self, directory):
        cfg = {
            "mailbox_user": "runner@example.com", "mailbox_password": "x",
            "shared_secret": CURRENT, "additional_secrets": {"old": OLD},
            "imap_host": "fake", "imap_port": 993, "smtp_host": "fake",
            "smtp_port": 587, "poll_interval_sec": 20, "max_job_age_sec": 3600,
            "max_output_bytes": 100000, "base_dir": self.tmp,
            "default_timeout_sec": 30, "workers": 1,
            "key_directory": directory,
        }
        jid = "q114-mail"
        smtp, seen = FakeSMTP(), {}
        R.poll_once(cfg, self.tmp, seen, os.path.join(self.tmp, "seen.json"),
                    imap=FakeIMAP([job_email(job_payload(jid, key_id="old"),
                                             secret=OLD)]),
                    smtp=smtp)
        return len(smtp.sent), jid in seen

    def test_compromised_is_silence_and_in_use_is_a_result(self):
        self.assertEqual((0, False), self._cycle(
            {"old": {"state": "compromised"}, "": {"state": "in_use"}}))
        self.assertEqual((1, True), self._cycle(
            {"old": {"state": "in_use"}, "": {"state": "in_use"}}))


class DtlsDoorTest(unittest.TestCase):
    """The DTLS pipe's lookup under the directory: a refused key
    neither handshakes nor resumes."""

    ADDR = ("127.0.0.1", 50003)

    def _lookup(self, directory):
        cfg = _cfg(directory)
        self.said = []
        return pipe.directory_lookup(
            cfg, dtlsproto.make_secret_lookup(CURRENT, {"old": OLD}),
            log=lambda m, level="INFO": self.said.append((level, m)),
            now=lambda: NOW)

    def test_the_lookup_answers_the_directory(self):
        look = self._lookup({"old": {"state": "compromised"}, "": {"state": "in_use"}})
        self.assertIsNone(look(dtlsproto.identity_for("old")))
        self.assertEqual(CURRENT, look(dtlsproto.identity_for("")))
        self.assertIsNone(look(b"t" * 24))
        self.assertEqual([("WARN", "dtls: key old refused by the key directory: "
                                   "key is compromised")], self.said)
        self.assertEqual(OLD, self._lookup(None)(dtlsproto.identity_for("old")))

    def _pump(self, client, server):
        out = client.start(NOW)
        for _ in range(60):
            if not out:
                break
            nxt = []
            for dg in out:
                nxt += server.feed(dg, self.ADDR, NOW)
            out = []
            for dg in nxt:
                out += client.feed(dg, NOW)

    def test_a_refused_key_neither_handshakes_nor_resumes(self):
        directory = {"old": {"state": "in_use"}, "": {"state": "in_use"}}
        cfg = _cfg(directory)
        server = dtlsproto.DtlsServerCore(
            secret_lookup=pipe.directory_lookup(
                cfg, dtlsproto.make_secret_lookup(CURRENT, {"old": OLD}),
                now=lambda: NOW),
            greeting_for=lambda s: b'{"type":"greeting","v":1}')
        first = dtlsproto.DtlsClientCore(OLD, key_id="old")
        self._pump(first, server)
        self.assertEqual("established", first.state)
        # The directory flips the key under the live pipe: no restart.
        directory["old"]["state"] = "compromised"
        before = len(server.events)
        resumed = dtlsproto.DtlsClientCore(OLD, ticket=first.ticket)
        self._pump(resumed, server)
        self.assertTrue(resumed.dead)
        fresh = dtlsproto.DtlsClientCore(OLD, key_id="old")
        self._pump(fresh, server)
        self.assertTrue(fresh.dead)
        self.assertEqual([], [e for e in server.events[before:] if e[0] == "established"])
        owner = dtlsproto.DtlsClientCore(CURRENT)
        self._pump(owner, server)
        self.assertEqual("established", owner.state)


class KeydirContractShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 46: Q115 -- a keydir
    contract crash in the sender (found f19bc40e, fixed 30119441,
    29-Oct-2026).

    The keydir target's first grow found a key with entries under
    two of its names read differently by the name the sender used:
    the directory carried the default key under "" with a
    non-object entry and under its fingerprint with an in_use one,
    and key_directory_verdict answered 'invalid key directory
    entry' under one name and None under the other. One key, one
    entry: the verdict now refuses such a key under either name
    with one sorted reason, and the startup check
    (validate_key_directory) makes it a config error.

    Per-field enumeration (the method section): the directory
    entry's fields each get their own tests -- state (every member
    of KEY_STATES and the shapes outside it), not_before,
    not_after, fingerprint -- and so do the verdict's other
    fields: the directory itself (None, empty, non-object entries,
    loaded inline, loaded from a file, inline-and-file together),
    the entry's name (the key under each of its names: "", its
    fingerprint, a second stored name), the key_id asked with
    (known, unknown, non-string), the secrets map (present, absent,
    not a dict), and now (both window bounds at, before and after
    the instant). The judging order is pinned too: fingerprint
    before state, compromised before the window, not_before
    before not_after. The fix's own doors are re-pinned where they
    live: the job door (check_key_policy) speaks the two-ids
    refusal, and the corpus checker (de_dust's keydir target)
    accepts a good directory and refuses the original banked
    record without crashing.

    The bookend rule and run lengths (standing rules,
    1-Nov-2026) are part of the family: key names are text, so
    every printable ASCII symbol at the front AND the back of a
    key name, NUL bookends, and run lengths (a run of the odd
    character, ordinary runs with the odd one at the front, the
    back and the middle) are pinned as plain unknown names that
    admit nothing and confuse nothing.

    Proof of work (6-Nov-2026). The unit tests are the 50 methods
    of this class.
    The fuzzing was executed, not just the tests written:
    runner/tools/de_dust_corpus.py grow --target keydir
    --rounds 400 --seed 20261147, run locally against the banked
    keydir corpus (38 entries). keydir is the target chosen for
    this item's fuzz job: it is the sender's key-directory target,
    the exact surface the crash came from, nearer than the cloud
    target that carries the sender's jobs. Result: 400 rounds,
    0 crashes, 0 slow, arcs unchanged at 242, slowest try 157 ms;
    the two-names contract crash did not recur. The grow's
    bookkeeping writes were reverted and are not banked (banking
    is the rigs' hourly job); this record is the run's proof.
    None of this is exotic: it is combinatorics -- systematically
    trying the combinations a hand-written list would never reach,
    then pinning each answer as a test."""

    def setUp(self):
        self.secrets = R.build_secrets(
            {"shared_secret": CURRENT,
             "additional_secrets": {"old": OLD, "alias": CURRENT}})
        self.fp = key_fingerprint(CURRENT)
        self.old_fp = key_fingerprint(OLD)

    def _verdict(self, directory, key_id="old", now=NOW, secrets="self"):
        return verify.key_directory_verdict(
            directory, self.secrets if secrets == "self" else secrets,
            key_id, now)

    def _cfg(self, directory):
        return {"shared_secret": CURRENT,
                "additional_secrets": {"old": OLD, "alias": CURRENT},
                "key_directory": directory}

    def _validate(self, directory, secrets=None):
        return verify.validate_key_directory(
            self._cfg(directory),
            self.secrets if secrets is None else secrets)

    # -- the directory field --

    def test_no_directory_admits_every_key(self):
        for key_id in ("", self.fp, "old", "ghost", 7):
            self.assertIsNone(self._verdict(None, key_id), repr(key_id))

    def test_an_empty_directory_refuses_every_key(self):
        for key_id in ("", self.fp, "old", "alias"):
            self.assertEqual("no key directory entry for this key",
                             self._verdict({}, key_id), key_id)

    def test_load_key_directory_reads_an_inline_directory(self):
        directory = {"old": {"state": "in_use"}}
        self.assertEqual(directory, verify.load_key_directory(
            {"key_directory": directory}))
        self.assertIsNone(verify.load_key_directory({}))
        self.assertIsNone(verify.load_key_directory(
            {"key_directory": None}))

    def test_load_key_directory_refuses_a_non_object(self):
        for bad in ([1], "x", 7):
            with self.assertRaises(RuntimeError) as ctx:
                verify.load_key_directory({"key_directory": bad})
            self.assertIn("must be an object", str(ctx.exception), bad)

    def test_load_key_directory_refuses_inline_and_file_together(self):
        with self.assertRaises(RuntimeError) as ctx:
            verify.load_key_directory(
                {"key_directory": {}, "key_directory_file": "/nope.json"})
        self.assertIn("mutually exclusive", str(ctx.exception))

    def test_a_file_directory_is_loaded_and_a_missing_one_raises(self):
        td = tempfile.mkdtemp(prefix="hp-q115-")
        self.addCleanup(shutil.rmtree, td, True)
        path = os.path.join(td, "keys.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"old": {"state": "in_use"}}, fh)
        self.assertEqual({"old": {"state": "in_use"}},
                         verify.load_key_directory(
                             {"key_directory_file": path}))
        with self.assertRaises(OSError):
            verify.load_key_directory(
                {"key_directory_file": os.path.join(td, "absent.json")})

    # -- the name field: one key, several names --

    def test_a_key_is_read_under_its_empty_name(self):
        directory = {"": {"state": "in_use"}}
        self.assertIsNone(self._verdict(directory, self.fp))
        self.assertIsNone(self._verdict(directory, "alias"))

    def test_a_key_is_read_under_its_fingerprint(self):
        directory = {self.fp: {"state": "in_use"}}
        self.assertIsNone(self._verdict(directory, ""))
        self.assertIsNone(self._verdict(directory, "alias"))

    def test_a_key_is_read_under_a_second_stored_name(self):
        directory = {"alias": {"state": "in_use"}}
        self.assertIsNone(self._verdict(directory, ""))
        self.assertIsNone(self._verdict(directory, self.fp))

    def test_secrets_not_a_dict_reads_the_asked_name_alone(self):
        self.assertEqual("no key directory entry for this key",
                         self._verdict({self.fp: {"state": "in_use"}},
                                       "", secrets=None))
        self.assertIsNone(self._verdict({"": {"state": "in_use"}},
                                        "", secrets=None))
        self.assertIsNone(self._verdict({"old": {"state": "in_use"}},
                                        "old", secrets=["not", "a", "dict"]))

    # -- Q115 itself: one key under two of its names --

    def test_the_q115_record_is_refused_under_the_empty_name(self):
        two = {"": "job", self.fp: {"state": "in_use"},
               "old": {"state": "in_use"}}
        self.assertIn("under two ids", self._verdict(two, ""))

    def test_the_q115_record_reads_the_same_under_the_fingerprint(self):
        two = {"": "job", self.fp: {"state": "in_use"},
               "old": {"state": "in_use"}}
        self.assertEqual(self._verdict(two, ""), self._verdict(two, self.fp))
        self.assertEqual(self._verdict(two, ""), self._verdict(two, "alias"))

    def test_two_entries_are_two_ids_even_when_the_entries_are_identical(self):
        two = {"": {"state": "in_use"}, self.fp: {"state": "in_use"}}
        self.assertIn("under two ids", self._verdict(two, "alias"))

    def test_the_two_ids_verdict_names_them_sorted_whichever_was_asked(self):
        two = {"alias": {"state": "in_use"}, self.fp: {"state": "in_use"}}
        a, b = sorted(["alias", self.fp])
        want = ("key directory names this key under two ids "
                "(%r and %r)" % (a, b))
        self.assertEqual(want, self._verdict(two, ""))
        self.assertEqual(want, self._verdict(two, self.fp))

    def test_the_startup_check_refuses_the_q115_directory(self):
        two = {"": "job", self.fp: {"state": "in_use"},
               "old": {"state": "in_use"}}
        with self.assertRaises(RuntimeError) as ctx:
            self._validate(two)
        self.assertIn("one key under two ids", str(ctx.exception))

    def test_the_startup_check_refuses_an_alias_duplication(self):
        two = {"": {"state": "in_use"}, "alias": {"state": "superseded"}}
        with self.assertRaises(RuntimeError) as ctx:
            self._validate(two)
        self.assertIn("one key under two ids", str(ctx.exception))
        self.assertIn("'alias'", str(ctx.exception))

    def test_the_startup_check_without_secrets_cannot_see_a_duplication(self):
        two = {"": {"state": "in_use"}, "alias": {"state": "in_use"}}
        self.assertEqual(two, self._validate(two, secrets={}))

    def test_the_job_door_speaks_the_two_ids_refusal(self):
        two = {"": "job", self.fp: {"state": "in_use"}}
        got = verify.check_key_policy({}, "", self._cfg(two), JOB,
                                      secrets=self.secrets)
        self.assertIn("under two ids", got)

    # -- the entry shape and the state field --

    def test_a_non_object_entry_is_invalid_at_the_door(self):
        for entry in ("job", 7, ["in_use"], None, True):
            self.assertEqual("invalid key directory entry",
                             self._verdict({"old": entry}), repr(entry))

    def test_a_missing_state_is_an_invalid_state(self):
        self.assertEqual("invalid key directory state",
                         self._verdict({"old": {}}))
        self.assertEqual("invalid key directory state",
                         self._verdict({"old": {"not_before": 1}}))

    def test_a_state_outside_the_set_is_an_invalid_state(self):
        for state in ("live", "", 7, None, "IN_USE", "in-use"):
            self.assertEqual("invalid key directory state",
                             self._verdict({"old": {"state": state}}),
                             repr(state))

    def test_the_refusing_states_each_say_key_is_that_state(self):
        for state in ("ordered", "generated", "distributed", "destroyed"):
            self.assertEqual("key is %s" % state,
                             self._verdict({"old": {"state": state}}),
                             state)

    def test_compromised_says_compromised_and_needs_no_window(self):
        self.assertEqual("key is compromised",
                         self._verdict({"old": {"state": "compromised"}}))

    def test_the_startup_check_names_the_faulty_entry(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._validate({"old": {"state": "live"}})
        self.assertIn("key_directory['old']", str(ctx.exception))
        self.assertIn("state must be one of", str(ctx.exception))

    def test_the_startup_check_refuses_a_nonstring_name(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._validate({7: {"state": "in_use"}})
        self.assertIn("not a string", str(ctx.exception))

    # -- the fingerprint field --

    def test_a_fingerprint_must_be_the_keys_own(self):
        entry = {"state": "in_use", "fingerprint": self.fp}
        self.assertEqual("key directory fingerprint does not match this key",
                         self._verdict({"old": entry}))

    def test_a_correct_fingerprint_admits(self):
        entry = {"state": "in_use", "fingerprint": self.old_fp}
        self.assertIsNone(self._verdict({"old": entry}))
        entry = {"state": "in_use", "fingerprint": self.fp}
        self.assertIsNone(self._verdict({"": entry}, ""))

    def test_a_nonstring_fingerprint_does_not_match(self):
        for fp in (7, ["k-00000000"], {"fp": 1}):
            entry = {"state": "in_use", "fingerprint": fp}
            self.assertEqual(
                "key directory fingerprint does not match this key",
                self._verdict({"old": entry}), repr(fp))

    def test_a_none_fingerprint_is_no_fingerprint(self):
        entry = {"state": "in_use", "fingerprint": None}
        self.assertIsNone(self._verdict({"old": entry}))

    def test_the_fingerprint_is_judged_before_the_state(self):
        entry = {"state": "compromised", "fingerprint": self.fp}
        self.assertEqual("key directory fingerprint does not match this key",
                         self._verdict({"old": entry}))

    # -- the window fields: not_before and not_after, and now --

    def test_not_before_in_the_future_refuses(self):
        entry = {"state": "in_use", "not_before": NOW + 1}
        self.assertEqual("key is not yet valid (not_before)",
                         self._verdict({"old": entry}))

    def test_not_before_at_now_admits(self):
        entry = {"state": "in_use", "not_before": NOW}
        self.assertIsNone(self._verdict({"old": entry}))

    def test_not_before_in_the_past_admits(self):
        entry = {"state": "in_use", "not_before": NOW - 1}
        self.assertIsNone(self._verdict({"old": entry}))

    def test_a_nonnumber_not_before_is_invalid_at_the_door(self):
        for bound in ("soon", {"x": 1}, [1]):
            entry = {"state": "in_use", "not_before": bound}
            self.assertEqual("invalid key directory not_before",
                             self._verdict({"old": entry}), repr(bound))

    def test_a_bool_not_before_reads_as_a_number_at_the_door(self):
        # float(True) is 1.0, long past at NOW: the door admits,
        # where the startup check (next test) refuses the shape.
        entry = {"state": "in_use", "not_before": True}
        self.assertIsNone(self._verdict({"old": entry}))

    def test_a_bool_bound_is_refused_at_startup(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._validate({"old": {"state": "in_use",
                                    "not_before": True}})
        self.assertIn("is not a number", str(ctx.exception))

    def test_a_numeric_string_not_before_reads_at_the_door(self):
        entry = {"state": "in_use", "not_before": "999999"}
        self.assertIsNone(self._verdict({"old": entry}))
        entry = {"state": "in_use", "not_before": "1000001"}
        self.assertEqual("key is not yet valid (not_before)",
                         self._verdict({"old": entry}))

    def test_not_after_ends_an_in_use_key(self):
        entry = {"state": "in_use", "not_after": NOW - 1}
        self.assertEqual("key is past its not_after",
                         self._verdict({"old": entry}))

    def test_not_after_at_now_admits(self):
        entry = {"state": "in_use", "not_after": NOW}
        self.assertIsNone(self._verdict({"old": entry}))

    def test_not_after_ends_a_superseded_key_with_its_own_words(self):
        entry = {"state": "superseded", "not_after": NOW - 1}
        self.assertEqual("key is superseded and its window has closed",
                         self._verdict({"old": entry}))

    def test_a_superseded_key_inside_its_window_admits(self):
        self.assertIsNone(self._verdict({"old": {"state": "superseded"}}))
        entry = {"state": "superseded", "not_after": NOW + 1}
        self.assertIsNone(self._verdict({"old": entry}))

    def test_a_nonnumber_not_after_is_invalid_at_the_door(self):
        for bound in ("soon", {"x": 1}):
            entry = {"state": "in_use", "not_after": bound}
            self.assertEqual("invalid key directory not_after",
                             self._verdict({"old": entry}), repr(bound))

    def test_compromised_beats_both_window_bounds(self):
        entry = {"state": "compromised", "not_before": NOW + 99,
                 "not_after": NOW - 1}
        self.assertEqual("key is compromised",
                         self._verdict({"old": entry}))

    def test_not_before_is_judged_before_not_after(self):
        entry = {"state": "in_use", "not_before": NOW + 99,
                 "not_after": NOW - 1}
        self.assertEqual("key is not yet valid (not_before)",
                         self._verdict({"old": entry}))

    # -- the key_id field --

    def test_a_nonstring_key_id_is_invalid(self):
        directory = {"old": {"state": "in_use"}}
        for key_id in (7, None, ["old"], {"id": "old"}):
            self.assertEqual("invalid key id",
                             self._verdict(directory, key_id), repr(key_id))

    def test_an_unknown_key_id_has_no_entry(self):
        directory = {"old": {"state": "in_use"}}
        self.assertEqual("no key directory entry for this key",
                         self._verdict(directory, "ghost"))

    def test_bookended_and_run_length_key_names_are_plain_unknown_names(self):
        import string as _string
        directory = {"old": {"state": "in_use"}}
        names = ["\x00old", "old\x00", "\told\n", "old" * 10,
                 "o" * 10 + "ld", "o" + "l" * 10 + "d"]
        for symbol in _string.punctuation:
            names.append(symbol + "old")
            names.append("old" + symbol)
            names.append(symbol * 10)
        for name in names:
            self.assertEqual("no key directory entry for this key",
                             self._verdict(directory, name), repr(name))
        # And a bookended entry name admits nothing under the plain one.
        self.assertEqual("no key directory entry for this key",
                         self._verdict({"!old!": {"state": "in_use"}},
                                       "old"))

    # -- the corpus checker, the target the crash came from --

    def test_the_corpus_checker_accepts_a_good_directory(self):
        from runner.tools import de_dust_corpus as B
        entry = B.make_entry(
            "payload", {"directory": {"old": {"state": "in_use"}},
                        "key_id": "old"}, "shotgun46", "shotgun46")
        self.assertEqual("accepted",
                         B._with_rig(lambda: B.check("keydir", entry)))

    def test_the_corpus_checker_refuses_the_q115_record_without_crashing(self):
        from runner.tools import de_dust_corpus as B
        record = {"directory": {"": "job",
                                "canary-key": {"state": "in_use"},
                                self.fp: {"state": "in_use"},
                                "ops": {"state": "in_use"}},
                  "key_id": ""}
        entry = B.make_entry("payload", record, "shotgun46", "shotgun46")
        self.assertEqual("refused",
                         B._with_rig(lambda: B.check("keydir", entry)))

    def test_the_corpus_checker_refuses_malformed_directories(self):
        from runner.tools import de_dust_corpus as B
        for data in ("hello", {"directory": [1, 2], "key_id": "old"},
                     {}):
            entry = B.make_entry("payload", data, "shotgun46", "shotgun46")
            self.assertEqual(
                "refused",
                B._with_rig(lambda e=entry: B.check("keydir", e)),
                repr(data))


if __name__ == "__main__":
    unittest.main()
