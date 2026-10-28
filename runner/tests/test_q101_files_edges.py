# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Q101's two readings, closed.

An inline file's `content_b64` is refused unless it is the canonical
encoding of its bytes (RFC 4648 section 3.5): `QR==` decodes to the
byte `A` as `QQ==` does, and only `QQ==` is staged, so a second
reader of the member never disagrees on which string stood for the
bytes. And the sender's `write_outputs` keeps the files it writes
inside the folder it was given: a symlink already there is not
written through, and a result that names one output twice writes it
once.
"""
import base64
import hashlib
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

from runner import runner as R
from runner.cloud import send_job
from runner.ops import exec as EXE


def _out(name, data):
    return {"name": name, "size": len(data),
            "sha384": hashlib.sha384(data).hexdigest(),
            "content_b64": base64.b64encode(data).decode("ascii")}


class CanonicalInlineTest(unittest.TestCase):

    def test_the_canonical_form_is_staged(self):
        self.assertEqual(b"A", EXE._decode_inline({"name": "a", "content_b64": "QQ=="}))
        self.assertEqual(b"", EXE._decode_inline({"name": "e", "content_b64": ""}))
        blob = bytes(range(256))
        self.assertEqual(blob, EXE._decode_inline(
            {"name": "b", "content_b64": base64.b64encode(blob).decode()}))

    def test_nonzero_trailing_bits_are_refused(self):
        for raw in ("QR==", "QUJ=", "QUJD/w=="[:-2] + "x="):
            with self.assertRaises(R.JobRejected) as ctx:
                EXE._decode_inline({"name": "a", "content_b64": raw})
            self.assertIn("base64", str(ctx.exception), raw)

    def test_the_refusal_names_canonical_for_a_decodable_string(self):
        with self.assertRaises(R.JobRejected) as ctx:
            EXE._decode_inline({"name": "a", "content_b64": "QR=="})
        self.assertIn("not canonical", str(ctx.exception))


@unittest.skipUnless(hasattr(os, "symlink") and os.name == "posix",
                     "POSIX symlink fixture")
class WriteOutputsTest(unittest.TestCase):

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.dest = os.path.join(self.td.name, "dest")
        self.elsewhere = os.path.join(self.td.name, "elsewhere")
        os.makedirs(self.dest)
        os.makedirs(self.elsewhere)

    def _write(self, outs):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = send_job.write_outputs({"outputs": outs}, self.dest)
        return rc, err.getvalue()

    def test_a_folder_symlink_in_dest_is_not_written_through(self):
        os.symlink(self.elsewhere, os.path.join(self.dest, "reports"))
        rc, err = self._write([_out("reports/junit.xml", b"<x/>")])
        self.assertEqual(1, rc)
        self.assertIn("outside", err)
        self.assertEqual([], os.listdir(self.elsewhere))

    def test_a_file_symlink_in_dest_is_not_followed(self):
        victim = os.path.join(self.elsewhere, "victim")
        with open(victim, "w") as fh:
            fh.write("keep")
        os.symlink(victim, os.path.join(self.dest, "out.txt"))
        rc, err = self._write([_out("out.txt", b"overwrite")])
        self.assertEqual(1, rc)
        self.assertIn("symlink", err)
        with open(victim) as fh:
            self.assertEqual("keep", fh.read())

    def test_a_name_given_twice_is_written_once(self):
        rc, err = self._write([_out("a.txt", b"first"), _out("a.txt", b"second")])
        self.assertEqual(1, rc)
        self.assertIn("named twice", err)
        with open(os.path.join(self.dest, "a.txt"), "rb") as fh:
            self.assertEqual(b"first", fh.read())

    def test_a_good_result_writes_owner_only_files_under_dest(self):
        outs = [_out("reports/junit.xml", b"<x/>"), _out("b.bin", bytes(9))]
        rc, _err = self._write(outs)
        self.assertEqual(0, rc)
        path = os.path.join(self.dest, "reports", "junit.xml")
        with open(path, "rb") as fh:
            self.assertEqual(b"<x/>", fh.read())
        self.assertEqual(0o600, os.stat(path).st_mode & 0o777)
        self.assertTrue(all("content_b64" not in o for o in outs))


if __name__ == "__main__":
    unittest.main()
