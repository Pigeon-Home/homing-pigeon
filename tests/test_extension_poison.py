#!/usr/bin/env python3
"""Negative cases from a working extension simulation.

The Oracle shares one poll with the board, the reviewer, the resource
monitor, the senses, and the DRI pager. The simulation wrote garbage
into those stores (a board file that was a JSON list, a numeric
capability list, a DRI cursor that was a word, a resource sample that
was a string, a sense record whose detail was the desktop flag) and
the poll raised. These tests are those inputs.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from runner import dri, resources, review  # noqa: E402
from runner.runner import (  # noqa: E402
    _redact_patterns,
    answer_queries,
    poll_once,
    query_budget,
    sign_payload,
)

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
FLAG = "FLAG-CRED-9f3c2a7e1b"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "si@example.com"
    msg.set_content(body)
    return msg.as_bytes()


class _IMAP:
    def __init__(self, raw):
        self.raw = raw

    def search(self, *args):
        return "OK", [b"1"]

    def fetch(self, num, what):
        return "OK", [(b"1 (RFC822)", self.raw)]

    def store(self, *args, **kwargs):
        return "OK", []


class _SMTP:
    def sendmail(self, *args, **kwargs):
        return None


class _Opts:
    dry_run = False
    no_send = True


class ExtensionPoisonTest(unittest.TestCase):
    def test_list_board_and_numeric_capabilities_do_not_crash_the_poll(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "board.json"), "w", encoding="utf-8") as fh:
                json.dump(["not", "a", "board"], fh)
            body = sign_payload({
                "v": 1, "type": "task_request", "issued_at": _now(),
                "capabilities": 5,
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] task_request worker-1", body)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "worker_compartments": {"worker-1": 5},
                "require_review": True,
                "dag_mode": "enforce",
            }
            poll_once(cfg, d, {}, os.path.join(d, "seen.json"),
                      imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())

    def test_review_accepts_a_job_whose_fields_are_the_wrong_type(self):
        notes = review.review_job({
            "review_patterns_extra": [{
                "id": "kf-flag",
                "pattern": "FLAG-CRED",
                "note": "script names the desktop flag",
                "severity": "warn",
            }],
        }, {
            "kind": "ping",
            "script": {"not": "text"},
            "files": "not-a-list",
            "interpreter": "bash",
            "timeout_sec": {"too": "big"},
        })
        self.assertIn("notes", notes)
        self.assertNotIn(FLAG, json.dumps(notes))

    def test_poisoned_dri_and_resource_state_do_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "dri-state.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "last_check": "not-a-time",
                    "last_page": {"key_probe": "never"},
                    "pending_digest": "nope",
                }, fh)
            with open(os.path.join(d, "resources.json"), "w", encoding="utf-8") as fh:
                json.dump({
                    "last_alert": {"disk": "yesterday", "cpu": []},
                    "cpu_prev": "nope",
                }, fh)
            with open(os.path.join(d, "security-events.jsonl"), "w", encoding="utf-8") as fh:
                fh.write("not json\n")
                fh.write(json.dumps({
                    "type": "resource_pressure",
                    "at": _now(),
                    "threshold": "high",
                    "resources": {"disk": "full", "cpu": None},
                }) + "\n")
            cfg = {
                "resources": {"enabled": True, "threshold": 0.0, "cooldown_sec": 0},
                "dri": {
                    "enabled": True,
                    "channel": "telegram",
                    "triggers": {
                        "resource_pressure": True,
                        "key_probe": {"threshold": 1, "window_sec": 3600},
                        "sensor_fused_score": {"threshold": 0.1, "window_sec": 3600},
                    },
                    "cooldown_sec": 0,
                    "digest_window_sec": 0,
                },
            }
            event = resources.check_resources(cfg, d)
            self.assertTrue(event is None or event.get("type") == "resource_pressure")
            with mock.patch.object(dri, "_send", return_value=False):
                # Bad cursor is a first run. The next cycle reads the
                # poisoned event and must still return, not raise.
                self.assertEqual(dri.maybe_page(cfg, d), 0)
                dri.maybe_page(cfg, d)
            with open(os.path.join(d, "dri-state.json"), encoding="utf-8") as fh:
                state = json.load(fh)
            self.assertIsInstance(state.get("last_check"), float)

    def test_senses_answer_redacts_a_string_detail(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "senses.jsonl"), "w", encoding="utf-8") as fh:
                fh.write(json.dumps([1, 2, 3]) + "\n")
                fh.write(json.dumps({
                    "sensor": "host_ids",
                    "severity": {"bad": True},
                    "title": {"not": "a string"},
                    "weight": "lots",
                    "detail": FLAG,
                    "received_at": _now(),
                }) + "\n")
            cfg = {"redact_patterns_extra": {"flag": r"FLAG-CRED-[0-9a-f]{10}"}}
            answers, spent = answer_queries(
                [{"op": "senses", "sensor": 1, "limit": "many"}],
                {"stdout": "", "stderr": "", "exit_code": 0},
                _redact_patterns(cfg),
                budget=2,
                cfg=cfg,
                view="attested",
                base_dir=d,
            )
        blob = json.dumps(answers)
        self.assertEqual(spent, 1)
        self.assertNotIn(FLAG, blob)
        self.assertIn("[REDACTED:flag]", blob)
        self.assertEqual(answers[0]["op"], "senses")


class MistypedConfigTest(unittest.TestCase):
    """Second simulation: the config and the job shape were the wrong types.

    output_retention_days was the word "week", protected_paths was the
    number 5, workspace_root was the number 5, and the job's
    result_policy was the string "attested". The retention word killed
    the poll before mail was read. The number 5 killed the job after
    the ping ran, and the runner scheduled it to run again.
    """

    def test_mistyped_retention_and_paths_do_not_retry_the_job(self):
        with tempfile.TemporaryDirectory() as d:
            body = sign_payload({
                "v": 1, "type": "job", "job_id": "job-shape",
                "issued_at": _now(), "kind": "ping",
                "result_policy": "attested",
            }, SECRET)
            raw = _mail("[HOMING-PIGEON] job job-shape", body)
            cfg = {
                "mailbox_user": "pigeon-test@example.com",
                "shared_secret": SECRET,
                "output_retention_days": "week",
                "max_query_budget": "eight",
                "protected_paths": 5,
                "workspace_root": 5,
                "judge": "off",
            }
            seen = {}
            poll_once(cfg, d, seen, os.path.join(d, "seen.json"),
                      imap=_IMAP(raw), smtp=_SMTP(), opts=_Opts())
            self.assertIn("job-shape", seen)
            self.assertEqual(query_budget(cfg, {"result_policy": "attested"}), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
