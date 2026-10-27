"""The Worker's signature gate and the core, on the same bytes.

The edge accepts a signature the core accepts raw, and refuses one
the core refuses. The core's control-character retry is not the
edge's job: both refusing is agreement.
"""
import unittest

from runner.tools import de_dust_corpus as dust
from runner.wire import verify as V

SECRET = dust.SECRET


class EdgeGateTest(unittest.TestCase):
    def test_a_signed_body_agrees(self):
        body = V.sign_payload(
            {"v": 1, "type": "job", "job_id": "bm-edge-1", "kind": "exec"},
            SECRET)
        self.assertEqual(dust._sig_verdict(body, SECRET), "accept")
        self.assertIsNone(dust._edge_agrees(body, SECRET))
        self.assertEqual(dust._Edge.verdict(body, SECRET), "accept")

    def test_a_flipped_signature_is_refused_by_both(self):
        body = V.sign_payload(
            {"v": 1, "type": "job", "job_id": "bm-edge-2", "kind": "exec"},
            SECRET)
        flipped = body[:-4] + ("0" if body[-4] != "0" else "1") + body[-3:]
        self.assertNotEqual(dust._sig_verdict(flipped, SECRET), "accept")
        self.assertIsNone(dust._edge_agrees(flipped, SECRET))
        self.assertNotEqual(dust._Edge.verdict(flipped, SECRET), "accept")

    def test_no_signature_is_refused_by_both(self):
        text = '{"v":1,"type":"job","job_id":"bm-edge-3"}'
        self.assertEqual(dust._sig_verdict(text, SECRET), "no-sig")
        self.assertIsNone(dust._edge_agrees(text, SECRET))
        self.assertEqual(dust._Edge.verdict(text, SECRET), "no-sig")

    def test_the_edge_losing_a_job_is_a_crash(self):
        body = V.sign_payload(
            {"v": 1, "type": "job", "job_id": "bm-edge-4", "kind": "exec"},
            SECRET)
        # A preamble the core skips and the edge hashes in.
        text = "note " + body
        self.assertEqual(dust._sig_verdict(text, SECRET), "accept")
        with self.assertRaises(dust.Crash) as caught:
            dust._edge_agrees(text, SECRET)
        self.assertIn("edge refuses", str(caught.exception))

    def test_node_answered(self):
        # The skip path is for a box with no node. This box has one,
        # and a silent skip would hide a broken gate.
        body = V.sign_payload({"v": 1, "job_id": "bm-edge-5"}, SECRET)
        self.assertIn(dust._Edge.verdict(body, SECRET),
                      ("accept", "no-sig", "mismatch"))
        self.assertFalse(dust._Edge.skip)


if __name__ == "__main__":
    unittest.main()
