# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""The result chain (PROTOCOL 3.2): each key's results, in order.

Every signed result carries `result_seq`, one more than the last
result this runner signed under the same key, and, from the second
on, `prev_result_sha384`, the SHA-384 of that previous result's
signed JSON. A sender that keeps the chain proves it saw every run in
order: a jump in the sequence is a result that never reached it, a
digest that does not match is a result it did not see. The chain is
per key, so a key learns nothing of another key's runs. A link is
recorded only once its result is stashed, so a run whose stash
failed (and runs again) does not leave a hole, and a delivery stub
names the result it replaced so the chain stays whole.
`send_job.py verify --chain FILE` keeps the sender's side.
"""
import io
import json
import os
import shutil
import tempfile
import unittest
import uuid
from contextlib import redirect_stderr
from unittest import mock

from runner import runner as R  # noqa: E402
from runner.cloud import send_job as SJ  # noqa: E402
import runner.tests.test_runner as TR  # noqa: E402  (not `from`: no re-collection)


class _Rig(unittest.TestCase):
    def setUp(self):
        self.h = TR.RunnerTest("test_ping_roundtrip")
        self.h.setUp()
        self.cfg = self.h.cfg
        self.base = self.h.tmp if not hasattr(self.h, "base") else self.h.base
        self.state = os.path.join(tempfile.mkdtemp(prefix="hp-chain-si-"), "chain.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(self.state), True)

    def tearDown(self):
        shutil.rmtree(self.h.tmp, ignore_errors=True)

    def run_jobs(self, n, kind="exec"):
        out = []
        for _ in range(n):
            jid = str(uuid.uuid4())
            p = TR.job_payload(jid, kind=kind, script="echo x", interpreter=["sh"]) \
                if kind == "exec" else TR.job_payload(jid, kind=kind)
            _, smtp, _ = self.h.run_cycle([TR.job_email(p)])
            out.append(TR.verify_body(TR.result_body(smtp.sent[0]), TR.SECRET))
        return out

    def check(self, payload):
        with redirect_stderr(io.StringIO()) as err:
            rc = SJ.check_chain(payload, self.state)
        return rc, err.getvalue()


class ChainTest(_Rig):
    def test_each_result_links_to_the_one_before(self):
        a, b, c = self.run_jobs(3)
        self.assertEqual([r["result_seq"] for r in (a, b, c)], [1, 2, 3])
        self.assertNotIn("prev_result_sha384", a)
        self.assertEqual(b["prev_result_sha384"], SJ.result_digest(a))
        self.assertEqual(c["prev_result_sha384"], SJ.result_digest(b))
        # the runner's digest and the sender's agree
        self.assertEqual(R.result_digest(a), SJ.result_digest(a))

    def test_rejections_and_pings_are_links_too(self):
        a, = self.run_jobs(1, kind="ping")
        b, = self.run_jobs(1, kind="bogus")
        self.assertEqual(b["exit_code"], -2)
        self.assertEqual(b["prev_result_sha384"], SJ.result_digest(a))

    def test_the_sender_sees_ok_a_gap_a_break_and_a_replay(self):
        a, b, c, d = self.run_jobs(4)
        self.assertEqual(self.check(a)[0], 0)
        rc, err = self.check(b)
        self.assertEqual((rc, "ok" in err), (0, True))
        rc, err = self.check(d)                       # c never arrived
        self.assertEqual(rc, 3)
        self.assertIn("gap", err)
        rc, err = self.check(dict(c, result_seq=5))   # a forged next link
        self.assertEqual(rc, 3)
        self.assertIn("break", err)
        rc, err = self.check(b)                       # an old copy
        self.assertEqual(rc, 3)
        self.assertIn("replay", err)

    def test_off_is_off(self):
        self.cfg["result_chain"] = False
        a, = self.run_jobs(1)
        self.assertNotIn("result_seq", a)
        self.assertFalse(os.path.exists(os.path.join(self.h.tmp, R.CHAIN_FILE))
                         and json.load(open(os.path.join(self.h.tmp, R.CHAIN_FILE))))

    def test_a_failed_stash_leaves_no_hole(self):
        with mock.patch.object(R, "stash_result", return_value=False):
            jid = str(uuid.uuid4())
            p = TR.job_payload(jid, kind="exec", script="echo x", interpreter=["sh"])
            self.h.run_cycle([TR.job_email(p)])
        a, = self.run_jobs(1)
        self.assertEqual(a["result_seq"], 1)


class StateTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-chain-")
        self.addCleanup(shutil.rmtree, self.base, True)

    def test_each_key_has_its_own_chain(self):
        R.chain_commit(self.base, "", 1, {"a": 1})
        self.assertEqual(R.chain_link(self.base, ""),
                         (2, R.result_digest({"a": 1})))
        self.assertEqual(R.chain_link(self.base, "ops"), (1, None))

    def test_an_unreadable_or_odd_file_starts_again(self):
        path = os.path.join(self.base, R.CHAIN_FILE)
        for text in ("not json", "[1]", json.dumps({"": {"seq": "two", "last": "x"}}),
                     json.dumps({"": {"seq": 3, "last": "short"}}),
                     json.dumps({"": {"seq": True, "last": "a" * 96}})):
            with self.subTest(text=text):
                with open(path, "w") as fh:
                    fh.write(text)
                with mock.patch.object(R, "log", lambda *a, **k: None):
                    self.assertEqual(R.chain_link(self.base, ""), (1, None))

    def test_no_base_no_chain(self):
        for base in (None, "", 7):
            with self.subTest(base=base):
                self.assertEqual(R.chain_link(base, ""), (None, None))
                R.chain_commit(base, "", 1, {})
                self.assertIsNone(R.chain_members({}, base, "", {}))

    def test_a_home_that_cannot_be_written_is_logged_not_raised(self):
        missing = os.path.join(self.base, "gone")
        logged = []
        with mock.patch.object(R, "log", lambda m, *a: logged.append(m)):
            R.chain_commit(missing, "", 1, {"a": 1})
        self.assertTrue(any("not recorded" in m for m in logged), logged)

    def test_the_digest_is_over_what_the_signer_signs(self):
        # the signer writes a non-finite number as null; so does the link
        self.assertEqual(R.result_digest({"x": float("nan")}),
                         R.result_digest({"x": None}))

    def test_a_stub_names_the_result_it_replaced(self):
        result = {"v": 1, "type": "result", "job_id": "j", "result_seq": 4,
                  "prev_result_sha384": "b" * 96, "exit_code": 0}
        meta = R._result_meta(result)
        self.assertEqual(meta["result_sha384"], R.result_digest(result))
        stub = R._stub_result("j", meta, "too big")
        self.assertEqual(stub["result_seq"], 4)
        self.assertEqual(stub["prev_result_sha384"], "b" * 96)
        self.assertEqual(stub["replaces_result_sha384"], R.result_digest(result))


class SenderStateTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="hp-chain-file-")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.path = os.path.join(self.d, "chain.json")

    def check(self, payload):
        with redirect_stderr(io.StringIO()) as err:
            return SJ.check_chain(payload, self.path), err.getvalue()

    def test_a_stub_stands_for_what_it_replaced(self):
        first = {"result_seq": 1, "key_id": "k-1", "exit_code": 0}
        replaced = {"result_seq": 2, "key_id": "k-1",
                    "prev_result_sha384": SJ.result_digest(first), "big": "x"}
        stub = {"result_seq": 2, "key_id": "k-1",
                "prev_result_sha384": SJ.result_digest(first),
                "replaces_result_sha384": SJ.result_digest(replaced)}
        nxt = {"result_seq": 3, "key_id": "k-1",
               "prev_result_sha384": SJ.result_digest(replaced)}
        self.assertEqual(self.check(first)[0], 0)
        self.assertEqual(self.check(stub)[0], 0)
        rc, err = self.check(nxt)
        self.assertEqual(rc, 0, err)

    def test_keys_are_kept_apart_and_no_seq_is_said(self):
        self.assertEqual(self.check({"result_seq": 7, "key_id": "a"})[0], 0)
        self.assertEqual(self.check({"result_seq": 1, "key_id": "b"})[0], 0)
        rc, err = self.check({"exit_code": 0})
        self.assertEqual(rc, 0)
        self.assertIn("no result_seq", err)
        with open(self.path) as fh:
            self.assertEqual(sorted(json.load(fh)), ["a", "b"])

    def test_an_unreadable_file_starts_again(self):
        with open(self.path, "w") as fh:
            fh.write("{broken")
        rc, err = self.check({"result_seq": 3, "key_id": "a"})
        self.assertEqual(rc, 0)
        self.assertIn("unreadable", err)


if __name__ == "__main__":
    unittest.main()
