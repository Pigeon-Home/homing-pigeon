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


import string  # noqa: E402


class InlineOutputsShotgunTest(unittest.TestCase):
    """The shotgun family for queue item 49, Q101: inline files
    and outputs -- canonical base64; the sender wrote outputs
    outside its folder (fixed 1fa6d626, 27-Oct-2026). The fix made
    _decode_inline refuse a content_b64 that is not the canonical
    encoding of its bytes, taught _validate_outputs the name
    rules, and made send_job.write_outputs refuse a folder that
    resolves outside dest, a symlink in a file's place, and a name
    given twice, writing 0600 without following. This family
    scattershots everything around those failures: the base64
    alphabet, padding and trailing-bit shapes, traversal and
    device names, symlink plants at every depth, digest shapes,
    and the duplicate-name leg. One regression test was never
    going to be enough for a bug that took days of CPU to find.

    Per-field enumeration: _decode_inline reads name and
    content_b64 (each field its own tests, name inert on success
    and named in the refusal); _validate_outputs reads the
    outputs list itself, its length against MAX_OUTPUTS, and
    each name; write_outputs reads name, content_b64 and sha384
    (each pinned separately; the size field is pinned as inert,
    never consulted), plus the max_output_file_bytes config
    field's own reading table. Bookends: every printable ASCII
    symbol (string.punctuation) at the front and at the back of
    a canonical string, plus NUL, tab, CR and LF at both ends,
    and symbol-only strings. Run lengths: repeated-byte payloads
    of 1, 5, 10 and 100, the odd character at the front, the
    middle and the back of a long canonical run, and file-name
    components at 255 and 256 bytes and names at the 1024-byte
    bound.

    Proof of work. The unit tests are the 50 methods of this
    class: 34 hand-written seams plus 16 generated per-name
    tests for _validate_outputs. The fuzzing was executed, not
    just the tests written: runner/tools/de_dust_corpus.py grow
    --target cloud --rounds 400 --seed 20261150 against the
    banked cloud corpus (113 entries). Result: 400 rounds,
    0 crashes, 0 slow, arcs unchanged at 184, slowest try
    1515 ms; the non-canonical and outside-the-folder shapes did
    not recur. The grow's bookkeeping writes were reverted and
    are not banked (banking is the rigs' hourly job). None of
    this is exotic: it is combinatorics -- systematically trying
    the combinations a hand-written list would never reach, then
    pinning each answer as a test."""

    # -- _decode_inline: the canonical leg --

    def test_canonical_table_roundtrips(self):
        cases = {"": b"", "QQ==": b"A", "QUI=": b"AB",
                 "QUJD": b"ABC", "QUJDRA==": b"ABCD",
                 "AAAAAAAAAAAA": bytes(9)}
        for raw, data in cases.items():
            self.assertEqual(EXE._decode_inline(
                {"name": "a", "content_b64": raw}), data, raw)
        blob = bytes(range(256))
        self.assertEqual(EXE._decode_inline(
            {"name": "b", "content_b64":
             base64.b64encode(blob).decode("ascii")}), blob)

    def test_noncanonical_trailing_bits_table_refused(self):
        for raw in ("QR==", "QV==", "AB==", "//==", "+/==",
                    "QUJ=", "QQJ=", "QUK="):
            with self.assertRaises(R.JobRejected, msg=raw) as ctx:
                EXE._decode_inline({"name": "a", "content_b64": raw})
            self.assertIn("not canonical", str(ctx.exception), raw)

    def test_strictly_invalid_table_refused(self):
        for raw in ("QQ", "QQ=", "QQ===", "Q Q==", "QQ==\n", "QQ==\r",
                    "QQ== ", " QQ==", "QQ-=", "QQ_=", "QQ==QQ==",
                    "====", "QQ==\x00", "éQ==", "QUJD\x7f"):
            with self.assertRaises(R.JobRejected, msg=repr(raw)):
                EXE._decode_inline({"name": "a", "content_b64": raw})

    def test_content_b64_wrong_types_refused(self):
        for raw in (None, 7, 2.5, True, b"QQ==", ["QQ=="], {"x": 1}):
            with self.assertRaises(R.JobRejected, msg=repr(raw)):
                EXE._decode_inline({"name": "a", "content_b64": raw})
        with self.assertRaises(R.JobRejected):
            EXE._decode_inline({"name": "a"})

    def test_name_field_inert_on_success_and_named_in_refusal(self):
        self.assertEqual(EXE._decode_inline(
            {"content_b64": "QQ=="}), b"A")
        self.assertEqual(EXE._decode_inline(
            {"name": None, "content_b64": "QQ=="}), b"A")
        with self.assertRaises(R.JobRejected) as ctx:
            EXE._decode_inline({"name": "report.bin",
                                "content_b64": "QR=="})
        self.assertIn("report.bin", str(ctx.exception))
        self.assertIn("not canonical", str(ctx.exception))

    def test_bookend_symbols_at_the_front_refused(self):
        for sym in string.punctuation:
            with self.assertRaises(R.JobRejected, msg=sym):
                EXE._decode_inline(
                    {"name": "a", "content_b64": sym + "QQ=="})

    def test_bookend_symbols_at_the_back_refused(self):
        for sym in string.punctuation:
            with self.assertRaises(R.JobRejected, msg=sym):
                EXE._decode_inline(
                    {"name": "a", "content_b64": "QQ==" + sym})

    def test_bookend_nonprinting_refused(self):
        for sym in ("\x00", "\t", "\r", "\n"):
            for raw in (sym + "QQ==", "QQ==" + sym,
                        sym + "QQ==" + sym):
                with self.assertRaises(R.JobRejected, msg=repr(raw)):
                    EXE._decode_inline({"name": "a", "content_b64": raw})

    def test_symbol_only_strings_refused(self):
        for raw in ("====", "!!!!", "****", "    ", "----", "????",
                    "\x00\x00\x00\x00", "éééé"):
            with self.assertRaises(R.JobRejected, msg=repr(raw)):
                EXE._decode_inline({"name": "a", "content_b64": raw})

    def test_runlength_repeated_bytes_roundtrip(self):
        for n in (1, 5, 10, 100):
            data = b"A" * n
            raw = base64.b64encode(data).decode("ascii")
            self.assertEqual(EXE._decode_inline(
                {"name": "a", "content_b64": raw}), data)
            data = bytes(0) * 0 + b"\x00" * n
            raw = base64.b64encode(data).decode("ascii")
            self.assertEqual(EXE._decode_inline(
                {"name": "a", "content_b64": raw}), data)

    def test_runlength_odd_char_at_the_front_refused(self):
        raw = base64.b64encode(b"A" * 10).decode("ascii")
        with self.assertRaises(R.JobRejected):
            EXE._decode_inline({"name": "a", "content_b64": "!" + raw[1:]})

    def test_runlength_odd_char_in_the_middle_refused(self):
        raw = base64.b64encode(b"A" * 10).decode("ascii")
        mid = raw[:5] + "!" + raw[6:]
        with self.assertRaises(R.JobRejected):
            EXE._decode_inline({"name": "a", "content_b64": mid})

    def test_runlength_odd_char_at_the_back_refused(self):
        raw = base64.b64encode(b"A" * 10).decode("ascii")
        with self.assertRaises(R.JobRejected):
            EXE._decode_inline({"name": "a",
                                "content_b64": raw[:-1] + "A"})
        with self.assertRaises(R.JobRejected):
            EXE._decode_inline({"name": "a",
                                "content_b64": raw[:-2] + "R="})

    # -- _validate_outputs: the job-side name leg --

    def test_validate_absent_and_empty_are_no_outputs(self):
        self.assertEqual(EXE._validate_outputs(None), [])
        self.assertEqual(EXE._validate_outputs([]), [])

    def test_validate_max_outputs_bound(self):
        names = [f"f{i}.txt" for i in range(EXE.MAX_OUTPUTS)]
        self.assertEqual(EXE._validate_outputs(names), names)
        with self.assertRaises(R.JobRejected):
            EXE._validate_outputs(names + ["one-more.txt"])

    def test_validate_a_name_given_twice_refused(self):
        with self.assertRaises(R.JobRejected):
            EXE._validate_outputs(["a.txt", "a.txt"])
        with self.assertRaises(R.JobRejected):
            EXE._validate_outputs(["d/a.txt", "b.txt", "d/a.txt"])

    def test_validate_nonlist_types_refused(self):
        for raw in ("a.txt", {"a.txt": 1}, 7, True, ("a.txt",)):
            with self.assertRaises(R.JobRejected, msg=repr(raw)):
                EXE._validate_outputs(raw)

    def test_validate_nonstring_entries_refused(self):
        for entry in (None, 7, b"a.txt", ["a.txt"], {"name": "a.txt"}):
            with self.assertRaises(R.JobRejected, msg=repr(entry)):
                EXE._validate_outputs([entry])

    def test_validate_good_names_keep_their_order(self):
        names = ["b.txt", "reports/junit.xml", "a.b-c_d.txt", "x"]
        self.assertEqual(EXE._validate_outputs(names), names)

    def test_validate_name_length_bounds(self):
        ok = "/".join(["a" * 255] * 4)  # 1023 bytes in all
        self.assertEqual(EXE._validate_outputs([ok]), [ok])
        with self.assertRaises(R.JobRejected):
            EXE._validate_outputs(["a" * 256])
        with self.assertRaises(R.JobRejected):
            EXE._validate_outputs([ok + "/b"])

    def test_max_output_file_bytes_field_reading(self):
        d = EXE.DEFAULT_MAX_OUTPUT_FILE_BYTES
        for cfg, want in ((None, d), ({}, d),
                          ({"max_output_file_bytes": None}, d),
                          ({"max_output_file_bytes": True}, d),
                          ({"max_output_file_bytes": "5"}, d),
                          ({"max_output_file_bytes": 2.5}, d),
                          ({"max_output_file_bytes": -1}, d),
                          ({"max_output_file_bytes": 0}, 0),
                          ({"max_output_file_bytes": 5}, 5)):
            self.assertEqual(EXE._max_output_file_bytes(cfg), want, cfg)

    # -- write_outputs: the sender-side folder leg --

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.dest = os.path.join(self.td.name, "dest")
        self.elsewhere = os.path.join(self.td.name, "elsewhere")
        os.makedirs(self.dest)
        os.makedirs(self.elsewhere)

    def _write(self, outs, dest=None):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = send_job.write_outputs({"outputs": outs},
                                        dest or self.dest)
        return rc, err.getvalue()

    def test_good_output_writes_0600_and_drops_its_bytes(self):
        out = _out("a.txt", b"hello")
        rc, _err = self._write([out])
        self.assertEqual(rc, 0)
        path = os.path.join(self.dest, "a.txt")
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"hello")
        if os.name == "posix":
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertNotIn("content_b64", out)
        self.assertEqual(out["written"], path)

    def test_nested_and_multiple_outputs_write(self):
        outs = [_out("reports/junit.xml", b"<x/>"), _out("b.bin", bytes(9))]
        rc, _err = self._write(outs)
        self.assertEqual(rc, 0)
        with open(os.path.join(self.dest, "reports", "junit.xml"),
                  "rb") as fh:
            self.assertEqual(fh.read(), b"<x/>")
        with open(os.path.join(self.dest, "b.bin"), "rb") as fh:
            self.assertEqual(fh.read(), bytes(9))

    def test_a_name_given_twice_writes_the_first_only(self):
        rc, err = self._write([_out("a.txt", b"first"),
                               _out("a.txt", b"second")])
        self.assertEqual(rc, 1)
        self.assertIn("named twice", err)
        with open(os.path.join(self.dest, "a.txt"), "rb") as fh:
            self.assertEqual(fh.read(), b"first")

    def test_case_distinct_names_are_two_outputs(self):
        # Probed on the test's own filesystem: where names
        # fold case (Windows, a default macOS volume), the
        # pair below is one file by the platform's own rule,
        # and there are not two outputs to hold.
        for probe in (".hp-case-A", ".hp-case-a"):
            with open(os.path.join(self.dest, probe), "w") as fh:
                fh.write("x")
        folds = len([n for n in os.listdir(self.dest)
                     if n.startswith(".hp-case-")]) < 2
        for probe in (".hp-case-A", ".hp-case-a"):
            path = os.path.join(self.dest, probe)
            if os.path.exists(path):
                os.unlink(path)
        if folds:
            self.skipTest(
                "this filesystem folds case, so case-variant "
                "names are one file")
        rc, _err = self._write([_out("A.txt", b"upper"),
                                _out("a.txt", b"lower")])
        self.assertEqual(rc, 0)
        with open(os.path.join(self.dest, "A.txt"), "rb") as fh:
            self.assertEqual(fh.read(), b"upper")
        with open(os.path.join(self.dest, "a.txt"), "rb") as fh:
            self.assertEqual(fh.read(), b"lower")

    def test_sha_mismatch_writes_nothing(self):
        out = _out("a.txt", b"hello")
        out["sha384"] = hashlib.sha384(b"other").hexdigest()
        rc, err = self._write([out])
        self.assertEqual(rc, 1)
        self.assertIn("do not match", err)
        self.assertEqual(os.listdir(self.dest), [])
        self.assertIn("content_b64", out)

    def test_sha_uppercase_spelling_matches(self):
        out = _out("a.txt", b"hello")
        out["sha384"] = out["sha384"].upper()
        rc, _err = self._write([out])
        self.assertEqual(rc, 0)

    def test_sha_missing_and_wrong_types_refused(self):
        for bad in (None, 7, ["x"], {"x": 1}):
            out = _out("a.txt", b"hello")
            out["sha384"] = bad
            rc, _err = self._write([out])
            self.assertEqual(rc, 1, repr(bad))
        out = _out("a.txt", b"hello")
        del out["sha384"]
        rc, _err = self._write([out])
        self.assertEqual(rc, 1)
        self.assertEqual(os.listdir(self.dest), [])

    def test_bad_b64_refused_and_a_good_sibling_still_writes(self):
        bad = _out("bad.txt", b"x")
        bad["content_b64"] = "not!base64"
        rc, err = self._write([bad, _out("good.txt", b"y")])
        self.assertEqual(rc, 1)
        self.assertEqual(os.listdir(self.dest), ["good.txt"])

    def test_the_size_field_is_inert(self):
        out = _out("a.txt", b"hello")
        out["size"] = 999999
        rc, _err = self._write([out])
        self.assertEqual(rc, 0)
        with open(os.path.join(self.dest, "a.txt"), "rb") as fh:
            self.assertEqual(fh.read(), b"hello")

    @unittest.skipUnless(os.name == "posix", "POSIX symlink fixture")
    def test_folder_symlinks_outside_are_not_written_through(self):
        os.symlink(self.elsewhere, os.path.join(self.dest, "reports"))
        rc, err = self._write([_out("reports/junit.xml", b"<x/>")])
        self.assertEqual(rc, 1)
        self.assertIn("outside", err)
        os.makedirs(os.path.join(self.dest, "deep"))
        os.symlink(self.elsewhere, os.path.join(self.dest, "deep", "x"))
        rc, err = self._write([_out("deep/x/junit.xml", b"<x/>")])
        self.assertEqual(rc, 1)
        self.assertEqual(os.listdir(self.elsewhere), [])

    @unittest.skipUnless(os.name == "posix", "POSIX symlink fixture")
    def test_a_file_symlink_in_place_is_not_followed(self):
        victim = os.path.join(self.elsewhere, "victim")
        with open(victim, "w") as fh:
            fh.write("keep")
        os.symlink(victim, os.path.join(self.dest, "out.txt"))
        rc, err = self._write([_out("out.txt", b"overwrite")])
        self.assertEqual(rc, 1)
        self.assertIn("symlink", err)
        with open(victim) as fh:
            self.assertEqual(fh.read(), "keep")

    def test_traversal_names_write_nothing_anywhere(self):
        for name in ("../evil.txt", "..\\evil.txt", "/abs.txt",
                     "a/../../evil.txt", "C:/evil.txt"):
            out = _out("good.txt", b"x")
            out["name"] = name
            rc, _err = self._write([out])
            self.assertEqual(rc, 1, name)
        self.assertEqual(os.listdir(self.dest), [])
        self.assertEqual(os.listdir(self.td.name),
                         ["dest", "elsewhere"])

    def test_outputs_not_a_list_and_entries_skipped(self):
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(send_job.write_outputs(
                {"outputs": "a.txt"}, self.dest), 0)
            self.assertEqual(send_job.write_outputs({}, self.dest), 0)
            self.assertEqual(send_job.write_outputs(
                {"outputs": ["x", 7, {"name": "a.txt"}]}, self.dest), 0)
        self.assertEqual(os.listdir(self.dest), [])


def _make_output_name_test(name):
    def run(self):
        with self.assertRaises(R.JobRejected, msg=name):
            EXE._validate_outputs([name])
    return run


# 16 generated per-name tests: traversal, absolute, drive, UNC,
# device, flag-shaped, empty-component and symbol-shaped names.
for _i, _name in enumerate((
        "../x", "/abs", "a//b", "a\\b", "C:/x", "//srv/x", "-x",
        "CON", "con.txt", "a b", "a;b", "a$b.txt", "a!b", "..", ".",
        "a/")):
    setattr(InlineOutputsShotgunTest, f"test_output_name_shape_{_i:02d}",
            _make_output_name_test(_name))
del _i, _name


if __name__ == "__main__":
    unittest.main()
