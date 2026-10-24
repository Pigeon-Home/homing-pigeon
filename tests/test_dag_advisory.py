#!/usr/bin/env python3
"""dag_mode: advisory (PROTOCOL 13.1) — the mode the audit kept.

Under enforce a task whose requires are incomplete is withheld.
Under advisory the same task is handed out, and the offer carries
a dag_warning naming the incomplete requires. These tests pin
both modes against the same boards, at the Board layer where the
enforce pins live, plus one signed-mail end-to-end through
poll_once where the warning is read out of the task_offer body.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "cloud"))

from runner import jobcrypto  # noqa: E402
from runner.runner import Board, poll_once  # noqa: E402
from send_job import sign_payload  # noqa: E402
from tests.test_runner import SECRET, SENDER, FakeIMAP, FakeSMTP  # noqa: E402


def _task(tid, requires=(), state="open", priority=0, submitted="0"):
    return {"task_id": tid, "state": state, "requires": list(requires),
            "capabilities": [], "compartments": [], "priority": priority,
            "submitted_at": submitted}


class DagAdvisoryBoardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.b = Board(os.path.join(self.tmp, "board.json"))

    def _board_with(self, tasks):
        self.b.tasks = {t["task_id"]: t for t in tasks}
        return self.b

    def test_blocked_task_is_offered_with_warning(self):
        self._board_with([
            _task("dep", state="open"),
            _task("main", requires=["dep"], priority=9),
        ])
        chosen = self.b.offer("w", [], "", {"dag_mode": "advisory"})
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["task_id"], "main")
        self.assertEqual(chosen["dag_warning"],
                         {"incomplete_requires": ["dep"]})
        self.assertEqual(chosen["state"], "claimed")
        self.assertEqual(chosen["claimed_by"], "w")

    def test_same_board_under_enforce_withholds(self):
        # The dep is claimed by someone else, so it is not itself a
        # candidate: the blocked task is the only possible offer.
        dep = _task("dep", state="claimed")
        dep["claimed_by"] = "other"
        self._board_with([dep, _task("main", requires=["dep"])])
        self.assertIsNone(self.b.offer("w", [], "", {"dag_mode": "enforce"}))

    def test_warning_names_only_the_incomplete_requires(self):
        self._board_with([
            _task("done-dep", state="done"),
            _task("open-dep", state="open"),
            _task("main", requires=["done-dep", "open-dep", "ghost"], priority=9),
        ])
        chosen = self.b.offer("w", [], "", {"dag_mode": "advisory"})
        self.assertEqual(chosen["dag_warning"],
                         {"incomplete_requires": ["open-dep", "ghost"]})

    def test_complete_dependencies_carry_no_warning(self):
        self._board_with([
            _task("dep", state="done"),
            _task("main", requires=["dep"], priority=9),
        ])
        chosen = self.b.offer("w", [], "", {"dag_mode": "advisory"})
        self.assertEqual(chosen["task_id"], "main")
        self.assertNotIn("dag_warning", chosen)

    def test_off_and_missing_mode_offer_without_warning(self):
        for cfg in ({"dag_mode": "off"}, {}, {"dag_mode": None}):
            self._board_with([
                _task("dep", state="open"),
                _task("main", requires=["dep"], priority=9),
            ])
            chosen = self.b.offer("w", [], "", cfg)
            self.assertEqual(chosen["task_id"], "main")
            self.assertNotIn("dag_warning", chosen)

    def test_unknown_mode_behaves_as_off(self):
        # The sibling judge key resolves unknown values to off;
        # dag_mode does the same rather than inventing a behavior.
        self._board_with([
            _task("dep", state="open"),
            _task("main", requires=["dep"], priority=9),
        ])
        chosen = self.b.offer("w", [], "", {"dag_mode": "strict"})
        self.assertEqual(chosen["task_id"], "main")
        self.assertNotIn("dag_warning", chosen)

    def test_warning_lands_only_on_the_chosen_task(self):
        self._board_with([
            _task("dep", state="open"),
            _task("blocked", requires=["dep"], priority=1),
            _task("clean", priority=9),
        ])
        chosen = self.b.offer("w", [], "", {"dag_mode": "advisory"})
        self.assertEqual(chosen["task_id"], "clean")
        self.assertNotIn("dag_warning", chosen)
        self.assertNotIn("dag_warning", self.b.tasks["blocked"])
        nxt = self.b.offer("w2", [], "", {"dag_mode": "advisory"})
        self.assertEqual(nxt["task_id"], "blocked")
        self.assertEqual(nxt["dag_warning"],
                         {"incomplete_requires": ["dep"]})

    def test_warning_persists_on_the_board_record(self):
        self._board_with([
            _task("dep", state="open"),
            _task("main", requires=["dep"], priority=9),
        ])
        self.b.offer("w", [], "", {"dag_mode": "advisory"})
        reloaded = Board(os.path.join(self.tmp, "board.json"))
        self.assertEqual(reloaded.tasks["main"]["dag_warning"],
                         {"incomplete_requires": ["dep"]})

    def test_stale_warning_clears_once_dependencies_complete(self):
        self._board_with([
            _task("dep", state="open"),
            _task("main", requires=["dep"], priority=9),
        ])
        chosen = self.b.offer("w", [], "", {"dag_mode": "advisory"})
        self.assertIn("dag_warning", chosen)
        # The dependency completes and the claim lapses unworked.
        self.b.tasks["dep"]["state"] = "done"
        self.b.tasks["main"]["state"] = "open"
        del self.b.tasks["main"]["claimed_by"]
        again = self.b.offer("w", [], "", {"dag_mode": "advisory"})
        self.assertEqual(again["task_id"], "main")
        self.assertNotIn("dag_warning", again)

    def test_corrupt_requires_warns_instead_of_crashing(self):
        # The poison shape from the enforce pins: a dict inside
        # requires. Enforce withholds; advisory hands out with the
        # warning attached (the corrupt entry has no name to list).
        self._board_with([
            {"task_id": "t", "state": "open",
             "requires": [{"not": "a string"}],
             "capabilities": [], "compartments": [], "priority": 0,
             "submitted_at": "0"},
        ])
        chosen = self.b.offer("w", [], "", {"dag_mode": "advisory"})
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["task_id"], "t")
        self.assertEqual(chosen["dag_warning"], {"incomplete_requires": []})
        self._board_with([
            {"task_id": "t", "state": "open",
             "requires": [{"not": "a string"}],
             "capabilities": [], "compartments": [], "priority": 0,
             "submitted_at": "0"},
        ])
        self.assertIsNone(self.b.offer("w", [], "", {"dag_mode": "enforce"}))

    def test_incomplete_agrees_with_enforce(self):
        # The two modes share one definition of incomplete: for
        # every board shape, advisory warns exactly when enforce
        # would have withheld.
        shapes = [
            [_task("a", state="done"), _task("t", requires=["a"])],
            [_task("a", state="open"), _task("t", requires=["a"])],
            [_task("a", state="claimed"), _task("t", requires=["a"])],
            [_task("t", requires=["missing"])],
            [_task("t", requires=[])],
            [_task("t")],
        ]
        for tasks in shapes:
            self._board_with([dict(t) for t in tasks])
            advised = self.b.offer("w", [], "", {"dag_mode": "advisory"})
            self._board_with([dict(t) for t in tasks])
            enforced = self.b.offer("w", [], "", {"dag_mode": "enforce"})
            if enforced is None:
                self.assertIn("dag_warning", advised)
            else:
                self.assertNotIn("dag_warning", advised)


def _board_mail(subject, payload):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = subject
    signed = sign_payload(payload, SECRET)
    ident = subject.rsplit(" ", 1)[-1]
    key_id = payload.get("key_id") if isinstance(payload, dict) else ""
    wire = jobcrypto.encrypt_body(
        signed, SECRET, job_id=ident, key_id=key_id or "",
        sign=sign_payload)
    msg.set_content(wire)
    return msg.as_bytes()


class DagAdvisoryE2ETest(unittest.TestCase):
    """Signed mail in, task_offer out: the warning rides the offer."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-dag-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": "test-gmail-password",
            "shared_secret": SECRET,
            "base_dir": self.tmp,
            "workers": 1,
            "dag_mode": "advisory",
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def _run(self, cfg):
        issued = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mails = [
            _board_mail("[HOMING-PIGEON] task_submit dep", {
                "v": 1, "type": "task_submit", "task_id": "dep",
                "issued_at": issued, "capabilities": ["py"],
                "payload": {"kind": "ping"},
            }),
            _board_mail("[HOMING-PIGEON] task_submit main", {
                "v": 1, "type": "task_submit", "task_id": "main",
                "issued_at": issued, "capabilities": ["py"],
                "priority": 5,
                "requires": ["dep"], "payload": {"kind": "ping"},
            }),
            _board_mail("[HOMING-PIGEON] task_request w1", {
                "v": 1, "type": "task_request", "issued_at": issued,
                "capabilities": ["py"],
            }),
        ]
        smtp = FakeSMTP()
        poll_once(cfg, self.tmp, {}, self.seen_path,
                  imap=FakeIMAP(mails), smtp=smtp)
        offers = []
        for m in smtp.sent:
            if "task_offer" in m["Subject"]:
                outer = json.loads(m.get_content())
                if isinstance(outer, dict) and "hp_enc" in outer:
                    from runner.runner import verify_body
                    opened = verify_body(m.get_content(), SECRET)
                    ident = str(m["Subject"]).rsplit(" ", 1)[-1]
                    inner = jobcrypto.decrypt_body(
                        opened, SECRET, ident,
                        opened.get("key_id") or "")
                    outer = json.loads(inner)
                offers.append(outer)
        return offers

    def test_offer_body_carries_the_warning(self):
        offers = self._run(self.cfg)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["task"]["task_id"], "main")
        self.assertEqual(offers[0]["task"]["dag_warning"],
                         {"incomplete_requires": ["dep"]})

    def test_same_flow_under_enforce_offers_the_dependency_first(self):
        cfg = dict(self.cfg, dag_mode="enforce")
        offers = self._run(cfg)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["task"]["task_id"], "dep")
        self.assertNotIn("dag_warning", offers[0]["task"])


if __name__ == "__main__":
    unittest.main()
