"""The Worker's signature gate and the core, on the same bytes.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

The edge accepts a signature the core accepts raw, and refuses one
the core refuses. The core's control-character retry is not the
edge's job: both refusing is agreement.
"""
import json
import os
import unittest
from unittest import mock

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

    def test_a_preamble_the_core_skips_the_edge_skips(self):
        body = V.sign_payload(
            {"v": 1, "type": "job", "job_id": "bm-edge-4", "kind": "exec"},
            SECRET)
        text = "note " + body
        self.assertEqual(dust._sig_verdict(text, SECRET), "accept")
        self.assertEqual(dust._Edge.verdict(text, SECRET), "accept")
        self.assertIsNone(dust._edge_agrees(text, SECRET))

    def test_the_edge_losing_a_job_is_a_crash(self):
        body = V.sign_payload(
            {"v": 1, "type": "job", "job_id": "bm-edge-6", "kind": "exec"},
            SECRET)
        with mock.patch.object(dust._Edge, "verdict", return_value="no-sig"):
            with self.assertRaises(dust.Crash) as caught:
                dust._edge_agrees(body, SECRET)
        self.assertIn("edge refuses", str(caught.exception))
        with mock.patch.object(dust._Edge, "verdict", return_value="accept"):
            with self.assertRaises(dust.Crash) as caught:
                dust._edge_agrees(body[:-3] + 'x"}', SECRET)
        self.assertIn("edge accepts", str(caught.exception))

    def test_a_cr_before_a_crlf_is_read_once_on_both_sides(self):
        # The queue channel and fetch each take one CRLF pass before
        # the verifier normalizes; the differential frames both alike.
        body = V.sign_payload({"v": 1, "job_id": "bm-edge-7"}, SECRET)
        text = body.replace(',"job_id"', '\r\r\n,"job_id"')
        self.assertIsNone(dust._edge_agrees(text, SECRET))

    def test_the_wire_seeds_agree(self):
        # The trailer, quoted, two-object, BOM, tail, lone-CR, CRLF
        # and signed-not-JSON seeds once split the two; the gate now
        # runs the core's extractor.
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "de_dust", "wire.jsonl")
        with open(path, encoding="utf-8") as fh:
            seeds = [json.loads(l) for l in fh if l.strip()][1:]
        seeds = [e for e in seeds if e.get("from", "").startswith("seed:")
                 and e.get("kind") == "text"]
        self.assertGreaterEqual(len(seeds), 8)
        for e in seeds:
            with self.subTest(seed=e["from"]):
                self.assertIsNone(dust._edge_agrees(e["data"], SECRET))

    def test_node_answered(self):
        # The skip path is for a box with no node. This box has one,
        # and a silent skip would hide a broken gate.
        body = V.sign_payload({"v": 1, "job_id": "bm-edge-5"}, SECRET)
        self.assertIn(dust._Edge.verdict(body, SECRET),
                      ("accept", "no-sig", "mismatch"))
        self.assertFalse(dust._Edge.skip)


if __name__ == "__main__":
    unittest.main()
