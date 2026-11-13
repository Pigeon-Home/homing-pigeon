# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The support matrix (docs/support-matrix.md) is a living document,
and this file pins it to the tree it describes.

The matrix answers the two questions an operator asks before
deploying: what is supported on my platform, and what testing
stands behind that claim. A claim that drifts from the code is
worse than no claim, so the mechanical claims are checked here
against the code itself: the audit log's default bound is read
out of runner/guard/security.py, and the modes default is read
out of effective_modes, not copied from the document.
"""
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
MATRIX = os.path.join(REPO, "docs", "support-matrix.md")

# Every platform row the matrix carries, as the row is named in
# its table.
PLATFORMS = (
    "Linux x86-64",
    "Linux ARM64",
    "Linux, minimal userland",
    "Linux as root",
    "Raspberry Pi (Pi Light)",
    "macOS",
    "Windows x86-64",
    "Windows ARM64",
    "Docker (GHCR image)",
    "FreeBSD",
    "Not supported",
)


def _text():
    with open(MATRIX, encoding="utf-8") as fh:
        return fh.read()


def _flat():
    """The document with all whitespace runs collapsed, so a
    phrase wrapped across lines still matches."""
    return " ".join(_text().split())


def _row(platform):
    """The platform table's row for one platform, as one line."""
    for line in _text().splitlines():
        if line.startswith("| " + platform + " |"):
            return line
    raise AssertionError("no platform row for " + platform)


class SupportMatrixTest(unittest.TestCase):
    def test_the_matrix_exists_at_its_home(self):
        self.assertTrue(os.path.isfile(MATRIX),
                        "docs/support-matrix.md is missing")

    def test_it_is_landed_not_a_draft(self):
        flat = _flat()
        self.assertNotIn("DRAFT", flat)
        self.assertNotIn("not yet in the repository", flat)

    def test_every_platform_row_is_named(self):
        flat = _flat()
        for name in PLATFORMS:
            with self.subTest(platform=name):
                self.assertIn(name, flat)

    def test_confinement_honesty_lines_are_present(self):
        flat = _flat()
        # bwrap is Linux-only, and on every platform confinement
        # at enforce whose backend cannot engage refuses --
        # fail-closed, never a weaker run. Until the macOS
        # backend landed, the matrix's macOS row pinned that
        # refusal directly ("confinement at enforce refuses to
        # start -- fail-closed, never silent"); the row now
        # names the backend, and the pins below name its exact
        # controls and its probe-refusal in the same spirit.
        self.assertIn("bwrap is Linux-only", flat)
        self.assertIn("refuses when it cannot engage", flat)
        self.assertIn(
            "macos: seatbelt_profile + no_network + "
            "spawn_resource_limits", flat)
        # job_user at enforce no longer refuses on win32: the
        # Job Objects backend carries it, and the matrix must
        # keep saying so (this line pinned the refusal until
        # the backend landed).
        self.assertIn("Enforce available via a Job Objects backend",
                      flat)

    def test_the_audit_bound_matches_the_code(self):
        from runner.guard import security as S
        want = "{:,}".format(S.DEFAULT_AUDIT_MAX_LINES)
        self.assertIn(want + " lines by default", _flat(),
                      "the matrix's audit-log bound no longer "
                      "matches DEFAULT_AUDIT_MAX_LINES")

    def test_the_modes_default_matches_the_code(self):
        from runner.guard import security as S
        modes = S.effective_modes({})
        self.assertTrue(modes, "no security features at all")
        self.assertEqual(set(modes.values()), {"enforce"},
                         "an unset security.modes feature no "
                         "longer defaults to enforce")
        self.assertIn("every `security.modes` feature defaults to "
                      "enforce everywhere", _flat())

    def test_the_freebsd_row_carries_its_landed_level(self):
        # The FreeBSD row stands at the level its hosted verdict
        # and field proof earned; the level it carried before
        # that landing must not come back on its row. (The word
        # for the old level still stands in this file's level
        # definitions, so the pin reads the row itself.)
        row = _row("FreeBSD")
        self.assertIn("Supported, reduced confinement", row)
        self.assertNotIn("Experimental", row)

    def test_the_stale_macos_sentences_are_absent(self):
        # The matrix once named the launcher shim's data-size
        # refusal as the live word on the spawn limits and the
        # spawn memory ceiling as unproven on real macOS. Both
        # sentences are stale -- the refusal is closed and a
        # green test-macos build stands -- and neither may
        # return.
        flat = _flat()
        self.assertNotIn(
            "live word on the spawn limits is failure", flat)
        self.assertNotIn(
            "could not set the data-size limit: current limit "
            "exceeds maximum limit", flat)
        self.assertNotIn("unproven on real macOS", flat)
        self.assertNotIn(
            "Live proof of the macOS spawn memory ceiling", flat)

    def test_the_corrected_macos_word_is_present(self):
        flat = _flat()
        self.assertIn(
            "The data-size refusal that once stood as the live "
            "word on the spawn limits is closed", flat)
        self.assertIn(
            "the build on the 3.16.25.8 release head of "
            "2026-11-13 completed green", flat)

    def test_the_audit_chain_claim_matches_the_code(self):
        # The matrix states the audit log is tamper-evident; the
        # chain must actually be in the guard module, and the
        # verifier flag must be named, so the claim cannot
        # outlive the code.
        from runner.guard import security as S
        self.assertTrue(hasattr(S, "AUDIT_CHAIN_GENESIS_LABEL"),
                        "the audit hash chain is not in "
                        "runner.guard.security")
        flat = _flat()
        self.assertIn("The audit log is tamper-evident", flat)
        self.assertIn("--audit-verify", flat)
        self.assertNotIn("not yet tamper-evident", flat)


if __name__ == "__main__":
    unittest.main(verbosity=2)
