# Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c
"""The panic word (questions.md Q100, PROTOCOL.md section 14.3).

Pinned: only an exact match fires; a near miss changes nothing; the
check runs before any MAC work; a fired box takes no job on any
transport, sends nothing and stays stopped across a restart; a dry run
does not fire; only a local re-arm releases it, and no message does.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner import runner as R  # noqa: E402
from runner.guard import panic  # noqa: E402
from runner.ops import install  # noqa: E402


class _Imap:
    def __init__(self):
        self.stored = []

    def store(self, seq, op, flag):
        self.stored.append(seq)
        return "OK", []


class _Smtp:
    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _raw(subject, body="{}"):
    return ("Subject: " + subject + "\r\nFrom: someone@example.com\r\n"
            'Content-Type: text/plain; charset="utf-8"\r\n\r\n'
            + body).encode("utf-8")


class _Base(unittest.TestCase):
    def setUp(self):
        panic._reset_for_tests()
        self.base = tempfile.mkdtemp(prefix="hp-panic-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.addCleanup(panic._reset_for_tests)
        self.word = panic.arm(self.base)
        self.cfg = {"mailbox_user": "runner@example.com",
                    "shared_secret": "x" * 64}

    def handle(self, subject, opts=None):
        imap = _Imap()
        with mock.patch.object(R, "_early_dispatch",
                               return_value=None) as early:
            R.handle_mail(self.cfg, imap, _Smtp(), 7, _raw(subject),
                          self.base, {}, {}, opts, None)
        return imap, early


class WordTest(unittest.TestCase):
    def test_the_list_and_the_word(self):
        self.assertEqual(len(panic.WORDLIST), 6400)
        self.assertEqual(len(set(panic.WORDLIST)), 6400)
        word = panic.generate_word()
        self.assertEqual(len(word.split()), 6)
        self.assertEqual(panic.normalize(word), word)

    def test_what_a_phone_changes_does_not_change_the_word(self):
        word = "bako lumi seda rifo tavu zeno"
        for typed in ("Bako Lumi Seda Rifo Tavu Zeno",
                      "bako-lumi-seda-rifo-tavu-zeno",
                      "  bako  lumi seda,rifo tavu zeno ",
                      "BAKO_LUMI_SEDA_RIFO_TAVU_ZENO"):
            self.assertEqual(panic.normalize(typed), word, typed)

    def test_not_six_words_from_the_list(self):
        for typed in ("bako lumi seda rifo tavu",
                      "bako lumi seda rifo tavu zeno bako",
                      "bako lumi seda rifo tavu stop",
                      "", None, 7):
            self.assertIsNone(panic.normalize(typed), typed)

    def test_the_subject_shape(self):
        word = "bako lumi seda rifo tavu zeno"
        self.assertEqual(panic.word_in_subject(
            "[HOMING-PIGEON] panic " + word), word)
        self.assertEqual(panic.word_in_subject(
            "[homing-pigeon]   PANIC  " + word.upper()), word)
        for subject in ("Re: [HOMING-PIGEON] panic " + word,
                        "Fwd: [HOMING-PIGEON] panic " + word,
                        "[HOMING-PIGEON] job " + word,
                        "[HOMING-PIGEON] panic",
                        "panic " + word):
            self.assertIsNone(panic.word_in_subject(subject), subject)


class StoreTest(_Base):
    def test_only_the_digest_is_kept(self):
        with open(os.path.join(self.base, panic.STATE_FILE)) as fh:
            text = fh.read()
        for part in self.word.split():
            self.assertNotIn(part, text)
        data = json.loads(text)
        self.assertEqual(data["v"], 1)
        self.assertEqual(len(data["sha384"]), 96)
        if os.name != "nt":
            mode = os.stat(os.path.join(self.base, panic.STATE_FILE)).st_mode
            self.assertEqual(mode & 0o077, 0)

    def test_matches_only_the_armed_word(self):
        self.assertTrue(panic.matches(
            self.base, "[HOMING-PIGEON] panic " + self.word))
        other = panic.generate_word()
        while other == self.word:
            other = panic.generate_word()
        self.assertFalse(panic.matches(
            self.base, "[HOMING-PIGEON] panic " + other))

    def test_not_armed_never_matches(self):
        empty = tempfile.mkdtemp(prefix="hp-panic-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        self.assertEqual(panic.state(empty), "not armed")
        self.assertFalse(panic.matches(
            empty, "[HOMING-PIGEON] panic " + self.word))

    def test_a_damaged_state_file_is_not_armed(self):
        with open(os.path.join(self.base, panic.STATE_FILE), "w") as fh:
            fh.write('{"v": 1, "salt": "zz", "sha384": "00"}')
        self.assertEqual(panic.state(self.base), "not armed")
        self.assertFalse(panic.matches(
            self.base, "[HOMING-PIGEON] panic " + self.word))


class IntakeTest(_Base):
    def test_the_word_fires_before_any_mac_work(self):
        imap, early = self.handle("[HOMING-PIGEON] panic " + self.word)
        early.assert_not_called()
        self.assertEqual(imap.stored, [7])
        self.assertEqual(panic.state(self.base), "fired")
        self.assertEqual(panic.flag(self.base)["transport"], "mail")
        with open(os.path.join(self.base, "security-events.jsonl")) as fh:
            events = [json.loads(line) for line in fh]
        self.assertEqual([e["type"] for e in events], ["panic_fired"])

    def test_a_near_miss_changes_nothing(self):
        words = self.word.split()
        near = " ".join(words[:-1])
        for subject in ("[HOMING-PIGEON] panic " + near,
                        "Re: [HOMING-PIGEON] panic " + self.word,
                        "[HOMING-PIGEON] job " + self.word):
            imap, early = self.handle(subject)
            early.assert_called_once()
        self.assertEqual(panic.state(self.base), "armed")
        self.assertFalse(os.path.exists(
            os.path.join(self.base, "security-events.jsonl")))

    def test_a_fired_box_takes_no_message(self):
        self.handle("[HOMING-PIGEON] panic " + self.word)
        imap, early = self.handle("[HOMING-PIGEON] job abc")
        early.assert_not_called()
        self.assertEqual(imap.stored, [])

    def test_the_channel_path_is_the_same_gate(self):
        out = R.process_transport_message(
            self.cfg, self.base, {}, {}, None,
            "[HOMING-PIGEON] panic " + self.word, "{}", None,
            transport="file")
        self.assertEqual(panic.flag(self.base)["transport"], "channel")
        self.assertEqual(list(out), [])
        with mock.patch.object(R, "_early_dispatch") as early:
            out = R.process_transport_message(
                self.cfg, self.base, {}, {}, None,
                "[HOMING-PIGEON] job abc", "{}", None, transport="file")
        early.assert_not_called()
        self.assertFalse(out.consume)

    def test_a_dry_run_does_not_fire(self):
        imap, early = self.handle("[HOMING-PIGEON] panic " + self.word,
                                  opts=SimpleNamespace(dry_run=True))
        self.assertEqual(panic.state(self.base), "armed")
        self.assertEqual(imap.stored, [])

    def test_a_second_word_changes_nothing(self):
        self.handle("[HOMING-PIGEON] panic " + self.word)
        first = panic.flag(self.base)
        self.handle("[HOMING-PIGEON] panic " + self.word)
        self.assertEqual(panic.flag(self.base), first)
        with open(os.path.join(self.base, "security-events.jsonl")) as fh:
            self.assertEqual(len(fh.readlines()), 1)

    def test_no_message_rearms(self):
        self.handle("[HOMING-PIGEON] panic " + self.word)
        for subject in ("[HOMING-PIGEON] rearm", "[HOMING-PIGEON] unpanic "
                        + self.word, "[HOMING-PIGEON] panic " + self.word):
            self.handle(subject)
        self.assertEqual(panic.state(self.base), "fired")


class StoppedTest(_Base):
    def fire(self):
        panic.fire(self.base, transport="mail")

    def test_nothing_is_sent(self):
        smtp = _Smtp()
        R.send_mail(smtp, self.cfg, "s", "b")
        self.assertEqual(len(smtp.sent), 1)
        self.fire()
        R.send_mail(smtp, self.cfg, "s", "b")
        self.assertEqual(len(smtp.sent), 1)

    def test_live_jobs_are_killed(self):
        killed = []
        panic.set_kill(killed.append)
        running, late = object(), object()
        panic.register(running)
        self.fire()
        self.assertEqual(killed, [running])
        panic.register(late)
        self.assertEqual(killed, [running, late])

    def test_nothing_is_polled_and_the_transports_stop(self):
        self.fire()
        with mock.patch.object(R, "build_secrets") as secrets, \
                mock.patch.object(R._transports, "stop_supervisors") as stop:
            R.poll_once(self.cfg, self.base, {}, os.path.join(
                self.base, "seen.json"))
        secrets.assert_not_called()
        stop.assert_called_with(self.base)

    def test_a_restart_stays_stopped(self):
        self.fire()
        panic._reset_for_tests()  # a new process: nothing in memory
        self.assertTrue(panic.fired(self.base))
        imap, early = self.handle("[HOMING-PIGEON] job abc")
        early.assert_not_called()


class RearmTest(_Base):
    def test_rearm_releases_the_box_with_a_new_word(self):
        panic.fire(self.base, transport="mail")
        cfg_path = os.path.join(self.base, "config.json")
        with open(cfg_path, "w") as fh:
            json.dump({"base_dir": self.base}, fh)
        with mock.patch("builtins.print") as out:
            self.assertEqual(install.do_rearm(cfg_path), 0)
        printed = " ".join(str(c.args[0]) for c in out.call_args_list)
        self.assertEqual(panic.state(self.base), "armed")
        panic._reset_for_tests()
        self.assertFalse(panic.fired(self.base))
        self.assertFalse(panic.matches(
            self.base, "[HOMING-PIGEON] panic " + self.word))
        self.assertIn("[HOMING-PIGEON] panic ", printed)

    def test_a_fresh_install_arms_once(self):
        empty = tempfile.mkdtemp(prefix="hp-panic-")
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        cfg_path = os.path.join(empty, "config.json")
        with open(cfg_path, "w") as fh:
            json.dump({}, fh)
        with mock.patch("builtins.print"):
            install.ensure_panic_word(cfg_path)
        before = _read(os.path.join(empty, panic.STATE_FILE))
        with mock.patch("builtins.print") as out:
            install.ensure_panic_word(cfg_path)
        self.assertEqual(_read(os.path.join(empty, panic.STATE_FILE)), before)
        self.assertIn("armed", str(out.call_args_list[0].args[0]))


class ProtectionTest(unittest.TestCase):
    def test_the_doctor_says_which_case(self):
        self.assertIn("runner's user", panic.protection({}))
        enforced = {"security": {"modes": {"job_user": "enforce"},
                                 "job_user": {"user": "hpjob"}}}
        if os.name != "nt":
            self.assertIn("another user", panic.protection(enforced))
        audited = {"security": {"modes": {"job_user": "audit"},
                                "job_user": {"user": "hpjob"}}}
        self.assertIn("runner's user", panic.protection(audited))


if __name__ == "__main__":
    unittest.main()
