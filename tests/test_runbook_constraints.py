"""Phases 2 to 4 of the constraint runbook, against the real functions.

Z3 looks for a budget or a size cap that can be bypassed. The models
it cannot find are then run on the runner. The oracle bridge is cut,
duplicated, and fed garbage. A torn audit log is the host-drift case.

No cluster, no proxy, no job is executed.
"""
import json
import os
import tempfile
import threading
import unittest
from unittest import mock

try:
    import z3
except ImportError:  # CI has no solver wheel; the runner checks still run
    z3 = None


SECRET = (
    "0123456789abcdef"
    "fedcba9876543210"
    "0011223344556677"
    "8899aabbccddeeff"
)


def _allow(limit, count):
    """The rate decision, as a Z3 term. True means the query proceeds."""
    return z3.If(limit < 0, False, z3.If(limit <= 0, True, count < limit))


@unittest.skipUnless(z3, "z3 is not installed")
class BudgetUnsatTest(unittest.TestCase):
    def test_no_negative_limit_lets_a_query_through(self):
        limit, count = z3.Ints("limit count")
        solver = z3.Solver()
        solver.add(limit < 0)
        solver.add(_allow(limit, count))
        self.assertEqual(solver.check(), z3.unsat)

    def test_no_full_window_lets_another_query_through(self):
        limit, count = z3.Ints("limit count")
        solver = z3.Solver()
        solver.add(limit > 0, count >= limit)
        solver.add(_allow(limit, count))
        self.assertEqual(solver.check(), z3.unsat)


class BudgetRunnerTest(unittest.TestCase):
    def test_the_boundary_models_match_the_runner(self):
        from runner.runner import check_rate_limit

        # Z3 says these four are the corners. The runner must agree.
        corners = [
            (-1, False),
            (0, True),
            (1, True),   # empty window, one slot
            (2 ** 63, True),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for limit, first in corners:
                path = os.path.join(directory, "q-%s.json" % limit)
                got = check_rate_limit(
                    "k", {"max_queries_per_hour": limit}, path)
                self.assertEqual(got, first, limit)
            # The slot of 1 is now full. A second query is the bypass
            # Z3 said was unsat.
            path = os.path.join(directory, "q-1.json")
            self.assertFalse(check_rate_limit(
                "k", {"max_queries_per_hour": 1}, path))

    def test_a_typo_is_not_unlimited(self):
        from runner.runner import _query_limit, check_rate_limit

        self.assertEqual(_query_limit({"max_queries_per_hour": "nope"}), -1)
        self.assertFalse(check_rate_limit(
            "k", {"max_queries_per_hour": "nope"}))
        # JSON true is the integer 1, not unlimited. false is unlimited.
        self.assertEqual(_query_limit({"max_queries_per_hour": True}), 1)
        self.assertEqual(_query_limit({"max_queries_per_hour": False}), 0)


@unittest.skipUnless(z3, "z3 is not installed")
class SizeCapUnsatTest(unittest.TestCase):
    def test_no_oversize_payload_is_accepted(self):
        cap, length = z3.Ints("cap length")
        accept = z3.Or(cap == 0, length <= cap)
        solver = z3.Solver()
        solver.add(cap != 0, length > cap, accept)
        self.assertEqual(solver.check(), z3.unsat)

    def test_a_negative_cap_does_not_become_unlimited(self):
        cap, length = z3.Ints("cap length")
        # The mail check is `if cap and length > cap`. A negative cap
        # is truthy, and every real length is greater than it.
        accept = z3.Or(cap == 0, length <= cap)
        solver = z3.Solver()
        solver.add(cap < 0, length >= 0, accept)
        self.assertEqual(solver.check(), z3.unsat)


class SizeCapRunnerTest(unittest.TestCase):
    def test_the_mail_path_rejects_the_solver_boundary(self):
        from runner.runner import handle_mail

        subject = "Subject: [HOMING-PIGEON] job abc\r\n\r\n"
        raw = (subject + ("x" * 40)).encode()
        reasons = []

        class Imap:
            def store(self, *args):
                return None

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("runner.runner.log",
                            side_effect=lambda msg, *a, **k: reasons.append(msg)):
                handle_mail(
                    {"max_job_bytes": 20, "shared_secret": SECRET},
                    Imap(), None, "1", raw, directory, {},
                    {"": SECRET})
        self.assertTrue(any("max_job_bytes" in r for r in reasons), reasons)

        reasons.clear()
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("runner.runner.log",
                            side_effect=lambda msg, *a, **k: reasons.append(msg)):
                handle_mail(
                    {"max_job_bytes": -1, "shared_secret": SECRET},
                    Imap(), None, "1", raw, directory, {},
                    {"": SECRET})
        self.assertTrue(any("max_job_bytes" in r for r in reasons), reasons)


class OraclePartitionTest(unittest.TestCase):
    def _cfg(self):
        return {
            "endpoint": "http://127.0.0.1:9/v1",
            "model": "test",
            "timeout_sec": 1,
        }

    def test_a_cut_connection_is_a_rejection_not_a_crash(self):
        from urllib.error import URLError
        from runner.runner import ask_model

        def cut(req, timeout=60):
            raise URLError("partition")

        def reset(req, timeout=60):
            raise TimeoutError("dropped")

        def garbage(req, timeout=60):
            class Resp:
                def read(self, n):
                    return b"{not json"
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return Resp()

        for opener in (cut, reset, garbage):
            out = ask_model(self._cfg(), "when?", "12:00", 100, opener=opener)
            self.assertIsInstance(out, dict)
            self.assertIn("rejected", out)

    def test_two_callers_both_get_a_dict_when_the_bridge_is_down(self):
        from runner.runner import ask_model

        def cut(req, timeout=60):
            raise ConnectionError("reset")

        outs = []

        def go():
            outs.append(ask_model(
                self._cfg(), "when?", "12:00", 100, opener=cut))

        threads = [threading.Thread(target=go) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(len(outs), 8)
        self.assertTrue(all(isinstance(o, dict) and "rejected" in o
                            for o in outs))


class LastSlotRaceTest(unittest.TestCase):
    def test_thirty_two_callers_share_three_slots(self):
        from runner.runner import check_rate_limit

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "times.json")
            cfg = {"max_queries_per_hour": 3}
            results = []
            barrier = threading.Barrier(32)

            def go():
                barrier.wait(timeout=5)
                results.append(check_rate_limit("k", cfg, path))

            threads = [threading.Thread(target=go) for _ in range(32)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
        self.assertEqual(sum(1 for ok in results if ok), 3)
        self.assertEqual(len(results), 32)


class HostDriftTest(unittest.TestCase):
    def test_a_torn_audit_log_does_not_crash_the_report(self):
        from runner.auditreport import main as audit_main
        from runner.posture import main as posture_main

        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, "security-audit.jsonl"),
                      "w", encoding="utf-8") as fh:
                fh.write('{"feature":"audience","decision":"denied"}\n')
                fh.write('{"feature":"audience"')  # torn last line
            cfg = {
                "shared_secret": SECRET,
                "base_dir": directory,
            }
            code = audit_main(cfg, directory)
            self.assertIn(code, (0, 1, 2))
            path = os.path.join(directory, "config.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh)
            os.chmod(path, 0o644)
            code = posture_main(cfg, path, directory)
            self.assertIn(code, (0, 1, 2))


class PolicyPathTest(unittest.TestCase):
    """An interpreter that is not on the allowlist never gets a pass.

    This is the static half of the policy row. The mail handler must
    call check_key_policy, and it must not start a process itself.
    """

    def test_every_off_list_interpreter_is_denied(self):
        from runner.runner import check_key_policy

        allowed = [["pwsh", "-NoProfile"]]
        policies = {"k": {"allowed_interpreters": allowed}}
        cfg = {"default_interpreter": ["pwsh", "-NoProfile"]}
        off = [
            ["bash", "-c"],
            ["/bin/bash", "-c"],
            ["pwsh"],
            ["pwsh", "-NoProfile", "-Command"],
            ["python3"],
            ["cmd", "/c"],
        ]
        for interp in off:
            reason = check_key_policy(
                policies, "k", cfg, {"kind": "exec", "interpreter": interp})
            self.assertIsNotNone(reason, interp)
            self.assertIn("not allowed", reason)

        # The one listed shape is the only pass.
        self.assertIsNone(check_key_policy(
            policies, "k", cfg,
            {"kind": "exec", "interpreter": ["pwsh", "-NoProfile"]}))

    def test_an_empty_policy_object_is_not_an_allowlist(self):
        from runner.runner import check_key_policy

        # {} is falsy, so it is "no entry". default_deny is what
        # closes that. Without it the key stays loose, on purpose.
        self.assertIsNone(check_key_policy(
            {"k": {}}, "k", {}, {"kind": "exec", "interpreter": ["bash", "-c"]}))
        reason = check_key_policy(
            {"k": {}}, "k", {"key_policies_default_deny": True},
            {"kind": "exec", "interpreter": ["bash", "-c"]})
        self.assertIn("default_deny", reason)

    def test_handle_mail_checks_policy_and_does_not_spawn(self):
        import ast
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "runner", "runner.py")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        handle = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "handle_mail")
        names = [
            n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            for n in ast.walk(handle) if isinstance(n, ast.Call)
        ]
        self.assertIn("check_key_policy", names)
        self.assertNotIn("Popen", names)
        self.assertNotIn("system", names)


class HalfReadTest(unittest.TestCase):
    def test_a_reply_that_dies_mid_read_is_a_rejection(self):
        from runner.runner import ask_model

        def die(req, timeout=60):
            class Resp:
                def read(self, n):
                    raise ConnectionResetError("mid-stream")
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return Resp()

        out = ask_model(
            {"endpoint": "http://127.0.0.1:9/v1", "model": "test",
             "timeout_sec": 1},
            "when?", "12:00", 100, opener=die)
        self.assertEqual(out.get("rejected"), "inference_error")


if __name__ == "__main__":
    unittest.main()
