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
        # The FreeBSD row stands at the level its proofs earned:
        # above Experimental since its hosted verdict and field
        # proof, and out of the reduced-confinement level since
        # the jail was rebuilt to hold what the Linux sandbox
        # holds and the hosted live proof of that shape passed
        # (2026-11-14). Neither earlier level may come back on
        # its row. (The words for them still stand in this
        # file's level definitions, so the pin reads the row
        # itself.)
        row = _row("FreeBSD")
        self.assertTrue(row.startswith("| FreeBSD | **Supported** |"),
                        row[:60])
        self.assertNotIn("reduced confinement", row)
        self.assertNotIn("Experimental", row)

    def test_the_reduced_level_names_the_platforms_it_fits(self):
        # The level's definition says, platform by platform, why
        # confinement there is weaker than the Linux sandbox. It
        # must go on naming macOS and Windows, and must not go
        # on describing a FreeBSD jail as one of them.
        flat = _flat()
        start = flat.index("- **Supported, reduced confinement**")
        end = flat.index("- **Experimental**")
        definition = flat[start:end]
        self.assertIn("on macOS", definition)
        self.assertIn("on Windows", definition)
        self.assertNotIn("on FreeBSD the backend applies", definition)

    def test_the_freebsd_row_s_numbers_and_names_match_the_code(self):
        # The row states the jail's ceilings and the record's
        # floor; both are read out of the backend, not copied.
        from runner.guard import freebsd_confine as FC
        row = _row("FreeBSD")
        mib = 1024 * 1024
        self.assertEqual(FC.DEFAULT_PROCESS_MEMORY_BYTES % mib, 0)
        self.assertIn(
            "%d MiB per-process memory ceiling"
            % (FC.DEFAULT_PROCESS_MEMORY_BYTES // mib), row)
        self.assertIn(
            "bounded `/tmp` (%d MiB)" % (FC.DEFAULT_TMP_BYTES // mib),
            row)
        self.assertIn("%d processes" % FC.DEFAULT_JOB_PROCESSES, row)
        self.assertIn(
            "%d GiB of address space"
            % (FC.DEFAULT_JOB_MEMORY_BYTES // (1024 * mib)), row)
        self.assertIn('"%s"' % FC.STATUS_CONFINEMENT, row)
        for name in ("no_superuser", "rctl_resource_limits",
                     "private_loopback"):
            self.assertIn(name, FC.CONTROL_ORDER)

    def test_the_freebsd_row_keeps_its_honesty_lines(self):
        # What the jail is not stays on the row beside what it
        # is: it needs root, it is not Capsicum, the jail-wide
        # ceilings need RACCT, and the node has run its live
        # classes but not the battery.
        row = _row("FreeBSD")
        self.assertIn("The backend needs root", row)
        self.assertIn("there is no Capsicum", row)
        self.assertIn("named only where RACCT is enabled", row)
        self.assertIn("refuses when it cannot engage", row)
        self.assertIn("the full battery has not been run against "
                      "this shape", row)
        self.assertIn("the suite itself is not green", row)

    def test_the_freebsd_row_states_what_a_fresh_install_does(self):
        # The seed asks the probe: enforce where it passes, audit
        # with the reason where it does not -- and the row keeps
        # the common reason beside the claim.
        row = _row("FreeBSD")
        self.assertIn("A fresh install asks the same probe", row)
        self.assertIn("stays at `enforce` where the probe passes",
                      row)
        self.assertIn("stated at `audit`, with the reason printed",
                      row)
        self.assertIn("an ordinary user's install", row)

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
