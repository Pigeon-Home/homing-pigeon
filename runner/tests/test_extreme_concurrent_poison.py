#!/usr/bin/env python3
"""Extreme concurrent poison: every major entry point under hostile data.

Finding: concurrent calls with object(), non-dict, binary garbage,
empty files, and nested poison do not raise out of the public
surfaces. Processing continues. Documented so a regression that
stops the agent or Oracle is caught.
"""
import os
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.oracle import dri, resources, review, senses  # noqa: E402
from runner.runner import (  # noqa: E402
    Board,
    _append_security_event,
    _redact_patterns,
    answer_queries,
    apply_result_policy,
    build_attestations,
    check_protected_paths,
    check_rate_limit,
    judge_job,
    load_retained,
    save_retained,
    snapshot_outside,
)


class ExtremeConcurrentPoisonTest(unittest.TestCase):
    def test_every_entry_point_under_hostile_data_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "retained"), exist_ok=True)
            with open(os.path.join(d, "retained", "empty.json"), "w") as f:
                f.write("")
            with open(os.path.join(d, "retained", "bin.json"), "wb") as f:
                f.write(b"\xff\xfe\x00\x01")
            with open(os.path.join(d, "senses.jsonl"), "wb") as f:
                f.write(b"\x00\x01\x02\n{not json\n")
            with open(os.path.join(d, "board.json"), "w") as f:
                f.write('{"t": {"state": "claimed", "claimed_by": null, "requires": "bad"}}')
            with open(os.path.join(d, "dri-state.json"), "w") as f:
                f.write('{"last": "not-a-ts", "counts": "string"}')
            with open(os.path.join(d, "resources.json"), "w") as f:
                f.write('{"cpu": [1,2], "mem": null}')
            with open(os.path.join(d, "security-events.jsonl"), "w") as f:
                f.write('{"type": null}\n[1,2]\n')

            errors = []

            def hammer(n):
                try:
                    Board(os.path.join(d, "board.json"))
                    senses.load_alerts(d, limit="bad")
                    senses.gate_alert(
                        {"profile": {"cooldown_sec": object(), "max_per_hour": []}},
                        {"severity": None},
                        [None, 1, "x"],
                    )
                    dri.maybe_page(
                        {"dri": {"enabled": True, "triggers": {
                            "sensor_fused_score": {"threshold": object()}}}},
                        d,
                    )
                    resources.check_resources(
                        {"resources": {"threshold": object(), "enabled": True}}, d)
                    review.review_job(
                        {"review_patterns_extra": object()},
                        {"script": object(), "files": object()},
                    )
                    answer_queries(object(), {"stdout": object()}, object(),
                                   object(), already_spent=object())
                    build_attestations(
                        [object(), {"op": "attest", "predicate": object()}], {})
                    apply_result_policy(object(), object(), object(), object(), object())
                    snapshot_outside(object(), exclude=object())
                    check_protected_paths(object(), object(), object())
                    judge_job(object(), object())
                    _redact_patterns(object())
                    save_retained(d, f"j{n}", {"stdout": object()})
                    load_retained(d, f"j{n}")
                    _append_security_event(d, {"bad": object()})
                    check_rate_limit(
                        object(), {"max_queries_per_hour": object()},
                        os.path.join(d, "q.json"))
                except Exception as e:
                    errors.append((n, type(e).__name__, str(e)))

            threads = [threading.Thread(target=hammer, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [], f"extreme concurrent poison raised: {errors}")


if __name__ == "__main__":
    unittest.main()
