"""Linux page inputs. A symlink is not an event source.

Unit cases, one-field mutations, and a deterministic fuzz.
Nothing here sends a page or starts a process. A planted symlink
is not opened.
"""
import json
import os
import random
import tempfile
import unittest

from runner.dri import EVENTS_FILE, evaluate_page_triggers


def _cfg():
    return {"triggers": {
        "resource_pressure": True,
        "confinement_violation": True,
    }}


def _event_line():
    return json.dumps({
        "type": "resource_pressure",
        "at": 1000,
        "resources": {"cpu": 0.99},
        "threshold": 0.9,
    }) + "\n"


class PageInputTest(unittest.TestCase):
    def test_a_real_event_pages_and_a_symlink_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, EVENTS_FILE)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_event_line())
            events = evaluate_page_triggers(_cfg(), d, 0, now=2000)
            self.assertEqual([ev["trigger"] for ev in events], ["resource_pressure"])
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(_event_line().replace("cpu", "secret"))
            os.remove(path)
            os.symlink(target, path)
            self.assertEqual(evaluate_page_triggers(_cfg(), d, 0, now=2000), [])
            with open(target, encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("secret", body)

    def test_a_retained_symlink_is_not_a_violation(self):
        with tempfile.TemporaryDirectory() as d:
            retained = os.path.join(d, "retained")
            os.makedirs(retained)
            path = os.path.join(retained, "job-1.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"job_id": "job-1", "saved_at": 1000, "confined": False}, fh)
            events = evaluate_page_triggers(_cfg(), d, 0, now=2000)
            self.assertEqual(events[0]["trigger"], "confinement_violation")
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write('{"job_id": "job-2", "saved_at": 1000, "confined": false, "secret": true}\n')
            os.remove(path)
            os.symlink(target, os.path.join(retained, "job-2.json"))
            events = evaluate_page_triggers(_cfg(), d, 0, now=2000)
            self.assertEqual(events, [])
            with open(target, encoding="utf-8") as fh:
                self.assertIn("secret", fh.read())


class PageMutations(unittest.TestCase):
    def test_bad_lines_do_not_page(self):
        self.assertEqual(evaluate_page_triggers(None, "x", 0), [])
        self.assertEqual(evaluate_page_triggers({}, "", 0), [])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, EVENTS_FILE)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("not json\n")
                fh.write("[1]\n")
                fh.write(json.dumps({"type": "resource_pressure"}) + "\n")
                fh.write(_event_line())
            events = evaluate_page_triggers(_cfg(), d, 0, now=2000)
            self.assertEqual(len(events), 1)
            self.assertEqual(evaluate_page_triggers(_cfg(), d, 5000, now=9000), [])
            os.remove(path)
            self.assertEqual(evaluate_page_triggers(_cfg(), d, 0, now=2000), [])


class PageFuzzTest(unittest.TestCase):
    def test_random_lines_do_not_follow_a_symlink(self):
        rng = random.Random(20261017)
        crashes = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, EVENTS_FILE)
            target = os.path.join(d, "target")
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("keep")
            for i in range(80):
                line = rng.choice([
                    _event_line(),
                    "nope\n",
                    json.dumps({"type": "other", "at": i}) + "\n",
                    json.dumps({"type": "resource_pressure", "at": "today"}) + "\n",
                    "",
                ])
                try:
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(line)
                    events = evaluate_page_triggers(
                        _cfg(), d, rng.choice([0, 5000]), now=2000)
                except Exception as exc:
                    crashes.append(type(exc).__name__)
                    break
                if not isinstance(events, list):
                    crashes.append(type(events).__name__)
                    break
                if any(not isinstance(ev, dict) or not isinstance(ev.get("trigger"), str)
                       for ev in events):
                    crashes.append("shape")
                    break
            os.remove(path)
            os.symlink(target, path)
            try:
                if evaluate_page_triggers(_cfg(), d, 0, now=2000) != []:
                    crashes.append("read")
            except Exception as exc:
                crashes.append(type(exc).__name__)
            with open(target, encoding="utf-8") as fh:
                if fh.read() != "keep":
                    crashes.append("followed")
        self.assertEqual(crashes, [])


if __name__ == "__main__":
    unittest.main()
