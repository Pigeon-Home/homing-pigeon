"""The v4 draft's named values, pinned so the draft cannot drift.

Step G of the v4 pass in
docs/infrastructure-documents/proofs/v4-working.md.
draft-slutsky-homing-pigeon-v4-00 binds versions 1, 2 and 3
to the provable model and states values: the size caps, the
caps and constants of C28 to C31, the hybrid group number,
the state counts of the 6 v4 models' checker runs, and the
conformance counts of the search records. Every one of
those values is pinned here against the code or against
the working papers that measured it, so a change to a value
the draft states turns this suite red before it turns the
draft wrong. The draft itself is a working draft, not
posted; its status lines are pinned too.
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from runner import runner as R  # noqa: E402
from runner.guard import security as S  # noqa: E402
from runner.oracle import resources as RES  # noqa: E402
from runner.wire import dtlsproto as DTLS  # noqa: E402
from runner.wire import jobcrypto as JC  # noqa: E402

IETF = os.path.join(ROOT, "docs", "ietf",
                    "draft-slutsky-homing-pigeon-v4")
PROOFS = os.path.join(ROOT, "docs", "infrastructure-documents",
                      "proofs")
DRAFT = os.path.join(IETF, "source",
                     "draft-slutsky-homing-pigeon-v4-00.md")
RENDER = os.path.join(IETF, "source",
                      "draft-slutsky-homing-pigeon-v4-00.txt")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _flat(path):
    return " ".join(_read(path).split())


def _mail_default(name):
    """The literal default handle_mail reads for a size cap,
    the shape test_proof_constraints.py reads them in."""
    text = _read(os.path.join(ROOT, "runner", "ops", "mail.py"))
    m = re.search(r'cfg\.get\("%s",\s*(\d+)\)' % re.escape(name),
                  text)
    assert m is not None, "no literal default for %s" % name
    return int(m.group(1))


DRAFT_TEXT = _flat(DRAFT)


class DraftIdentity(unittest.TestCase):
    """The draft is the v4 -00 working draft, and says so."""

    def test_docname_and_title(self):
        self.assertIn("docname: draft-slutsky-homing-pigeon-v4-00",
                      DRAFT_TEXT)
        self.assertIn("Homing Pigeon Message Protocol, Version 4: "
                      "The Provable Model", DRAFT_TEXT)
        render = _read(RENDER)
        self.assertIn("draft-slutsky-homing-pigeon-v4-00", render)
        self.assertIn("Homing Pigeon Message Protocol, Version 4",
                      render)

    def test_the_draft_is_a_working_draft_not_posted(self):
        self.assertIn("WORKING DRAFT, NOT POSTED", DRAFT_TEXT)
        self.assertIn("date: 2026-11-18", DRAFT_TEXT)
        status = _flat(os.path.join(IETF, "status.md"))
        self.assertIn("NOT POSTED", status)
        self.assertIn("nit-free, 0 errors, 0 warnings, 0 comments",
                      status)

    def test_the_draft_requests_no_iana_action(self):
        self.assertIn("This document requests no IANA action",
                      DRAFT_TEXT)

    def test_the_draft_binds_all_3_earlier_versions(self):
        for ref in ("I-D.slutsky-homing-pigeon:",
                    "I-D.slutsky-homing-pigeon-v2:",
                    "I-D.slutsky-homing-pigeon-v3:"):
            self.assertIn(ref, DRAFT_TEXT, ref)
        self.assertIn("draft-slutsky-homing-pigeon-04", DRAFT_TEXT)
        self.assertIn("draft-slutsky-homing-pigeon-v2-04", DRAFT_TEXT)
        self.assertIn("draft-slutsky-homing-pigeon-v3-00", DRAFT_TEXT)


class DraftStructure(unittest.TestCase):
    """Every property, and the findings, stand in the draft."""

    def test_all_13_properties_are_stated(self):
        for n in range(1, 14):
            self.assertIn("## P%d." % n, _read(DRAFT), "P%d" % n)

    def test_the_inventory_and_the_findings_are_named(self):
        self.assertIn("numbered C1 to C31", DRAFT_TEXT)
        for n in range(1, 8):
            self.assertIn("F%d:" % n, DRAFT_TEXT, "F%d" % n)
        self.assertIn("Finding F5", DRAFT_TEXT)
        self.assertIn("Finding F6", DRAFT_TEXT)
        self.assertIn("finding F7", DRAFT_TEXT)


class DraftValuesAgainstTheCode(unittest.TestCase):
    """The values the draft states, read off the code."""

    def test_the_size_caps(self):
        self.assertEqual(_mail_default("max_job_bytes"), 4194304)
        self.assertEqual(_mail_default("max_script_bytes"), 1048576)
        self.assertEqual(R._max_result_bytes({}), 5242880)
        for stated in ("4194304", "1048576", "5242880"):
            self.assertIn(stated, DRAFT_TEXT, stated)
        self.assertIn("with 0 meaning unlimited", DRAFT_TEXT)

    def test_the_local_envelope_cap(self):
        self.assertEqual(R._LOCAL_ENVELOPE_MAX_BYTES, 262144)
        self.assertIn("262144", DRAFT_TEXT)

    def test_the_signature_and_the_aead(self):
        verify = _read(os.path.join(ROOT, "runner", "wire",
                                    "verify.py"))
        self.assertIn("hmac.new(", verify)
        self.assertIn("hashlib.sha384", verify)
        self.assertIn("HMAC-SHA-384", DRAFT_TEXT)
        self.assertEqual(JC.ALG, "aes-256-gcm/hkdf-sha384")
        self.assertIn("AES-256-GCM", DRAFT_TEXT)

    def test_the_secret_floor(self):
        with self.assertRaises(RuntimeError):
            S.validate_shared_secret("ab" * 8)
        self.assertIn("at least 128 bits", DRAFT_TEXT)
        self.assertIn("128 bits of entropy", DRAFT_TEXT)

    def test_the_disk_guard_constants(self):
        self.assertEqual(RES.DISK_GUARD_THRESHOLD, 0.90)
        self.assertEqual(RES.DISK_GUARD_LOG_KEEP_BYTES, 65536)
        self.assertEqual(RES.DISK_GUARD_WORK_MIN_AGE_SEC, 3600)
        self.assertEqual(RES.DISK_GUARD_MAX_ACTIONS, 512)
        for stated in ("90 percent", "65536", "3600", "512"):
            self.assertIn(stated, DRAFT_TEXT, stated)

    def test_the_hybrid_group_and_the_replay_window(self):
        self.assertEqual(DTLS.GROUP_X25519MLKEM768, 4588)
        self.assertEqual(DTLS.GROUP_X25519, 29)
        self.assertEqual(DTLS.RECORD_REPLAY_WINDOW, 32768)
        for stated in ("4588", "group 29", "32768"):
            self.assertIn(stated, DRAFT_TEXT, stated)


class DraftCountsAgainstTheRecords(unittest.TestCase):
    """The checker counts and conformance counts the draft
    states, read off the records that measured them."""

    def test_the_6_models_checker_counts(self):
        working = _flat(os.path.join(PROOFS, "v4-working.md"))
        for cfg, count in (("diskguard", "1,086"), ("secretfloor", "67"),
                           ("probegate", "288"), ("hybridselect", "16"),
                           ("resultfit", "12"), ("localgate", "200")):
            self.assertIn("`%s.cfg` passes, %s states" % (cfg, count),
                          working, cfg)
            self.assertIn("%s distinct states" % count, DRAFT_TEXT,
                          cfg)

    def test_the_conformance_counts(self):
        search1 = _flat(os.path.join(PROOFS, "v4-search.md"))
        search2 = _flat(os.path.join(PROOFS, "v4-search-2.md"))
        self.assertIn("125 configurations", search1)
        self.assertIn("32 of the 107", search1)
        self.assertIn("125 configurations", DRAFT_TEXT)
        self.assertIn("32 of the 107", DRAFT_TEXT)
        self.assertIn("all 144 starts", DRAFT_TEXT)
        self.assertIn("144 initial states", search1)
        self.assertIn("4 handshakes", search2)
        self.assertIn("4 handshakes", DRAFT_TEXT)
        self.assertIn("112 arrivals, 140 runs", search1)
        self.assertIn("112 arrivals in 140 runs", DRAFT_TEXT)

    def test_the_fitting_floor(self):
        search2 = _flat(os.path.join(PROOFS, "v4-search-2.md"))
        self.assertIn("the floor is 4,625 bytes", search2)
        self.assertIn("that floor is 4625 bytes", DRAFT_TEXT)
        self.assertIn("40000 bytes on each stream", DRAFT_TEXT)

    def test_the_findings_stand_in_the_records(self):
        search1 = _flat(os.path.join(PROOFS, "v4-search.md"))
        search2 = _flat(os.path.join(PROOFS, "v4-search-2.md"))
        for n in range(1, 7):
            self.assertIn("F%d." % n, search1, "F%d" % n)
        self.assertIn("Finding F7", search2)


if __name__ == "__main__":
    unittest.main()
