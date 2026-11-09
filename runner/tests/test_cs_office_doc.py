"""The cs_office public page and its posture note: standing claims.

These tests pin the public statements the cs_office document pass
settled, so a later edit cannot silently drop one: the open-source
track's one named project, the Fibonacci counting convention of
the proving work, and the posture note's four exemplar letters.
Everything asserted here is public-shelf material from the pages
themselves; no label is attached to anything it does not already
carry in print.
"""
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

PAGE = os.path.join(
    REPO, "docs", "infrastructure-documents", "project",
    "cs_office.md")
POSTURES = os.path.join(
    REPO, "docs", "infrastructure-documents", "project",
    "cs_office-postures.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestCsOfficePage(unittest.TestCase):
    def test_open_track_names_gnutls_once_as_public_face(self):
        text = _read(PAGE)
        self.assertIn("open-source\ntrack", text)
        self.assertIn("GnuTLS is one of the projects it covers", text)
        self.assertIn("the workstream's public face", text)

    def test_open_track_carries_the_shield(self):
        text = _read(PAGE)
        # Two shelves, formal channels only, nothing public
        # before it is patched, bounty work carried by label.
        self.assertIn("the two shelves set out on", text)
        self.assertIn("formal channels only", text)
        self.assertIn("nothing about a finding is\npublic before it is patched", text)
        self.assertIn("never named, only carried by label", text)

    def test_fibonacci_convention_starts_at_zero(self):
        text = _read(PAGE)
        self.assertIn("the sequence starts at 0 — F(0) = 0, F(1) = 1",
                      text)
        self.assertIn("Fibonacci\nnumbers in the workstream's records",
                      text)


class TestCsOfficePostures(unittest.TestCase):
    def test_exemplar_letters_map_onto_the_postures(self):
        text = _read(POSTURES)
        self.assertIn("A — the hidden posture", text)
        self.assertIn("B — the open posture", text)
        self.assertIn("C — BOOKEND, the hybrid posture", text)
        self.assertIn("D — DELTA, a documented example", text)

    def test_bookend_target_is_the_suite_itself(self):
        text = _read(POSTURES)
        self.assertIn("target is Homing Pigeon itself — this suite", text)

    def test_delta_is_example_only(self):
        text = _read(POSTURES)
        self.assertIn("The letter is example-only", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
