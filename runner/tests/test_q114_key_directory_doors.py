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


if __name__ == "__main__":
    unittest.main()
