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
import re
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
        # the jail was rebuilt (a read-only root, no privilege
        # inside, ceilings the job cannot raise) and the hosted
        # live proof of that shape passed
        # (2026-11-14). Neither earlier level may come back on
        # its row. (The words for them still stand in this
        # file's level definitions, so the pin reads the row
        # itself.)
        row = _row("FreeBSD")
        self.assertTrue(row.startswith("| FreeBSD | **Supported** |"),
                        row[:60])
        self.assertNotIn("reduced confinement", row)
        self.assertNotIn("Experimental", row)

    def test_the_reduced_level_records_its_departures(self):
        # No platform carries the reduced-confinement level in
        # the present tense now. Its definition stands as the
        # record of a step three platforms took and left:
        # FreeBSD left it on 2026-11-14 when its jail was
        # rebuilt, macOS left it on 2026-11-21 on the owner's
        # call, and Windows left it on 2026-11-21 on the
        # owner's call the same evening, each name now
        # following its backend's enforce posture. None of the
        # three may come back as a present-tense example of
        # the level.
        flat = _flat()
        start = flat.index("- **Supported, reduced confinement**")
        end = flat.index("- **Experimental**")
        definition = flat[start:end]
        self.assertIn("No row in the table below stands at "
                      "this level today", definition)
        self.assertIn("FreeBSD stood at this level until "
                      "2026-11-14", definition)
        self.assertIn("macOS stood at this level until "
                      "2026-11-21", definition)
        self.assertIn("Windows stood at this level until "
                      "2026-11-21", definition)
        self.assertNotIn("on Windows the backend", definition)
        self.assertNotIn("on macOS the backend applies",
                         definition)
        self.assertNotIn("on FreeBSD the backend applies",
                         definition)

    def test_the_macos_row_carries_its_landed_level(self):
        # The macOS row stands at Supported since the owner's
        # call of 2026-11-21: the backend has enforced at
        # enforce, fail-closed, since the flip of 2026-11-14,
        # and the level's name follows that posture. The
        # reduced-confinement level may not come back on its
        # row. (The words for it still stand in this file's
        # level definitions, as the record of the departures,
        # so the pin reads the row itself.)
        row = _row("macOS (Intel and Apple silicon)")
        self.assertTrue(
            row.startswith(
                "| macOS (Intel and Apple silicon) | "
                "**Supported** |"),
            row[:70])
        self.assertNotIn("reduced confinement", row)

    def test_the_windows_rows_carry_their_landed_level(self):
        # The Windows rows stand at Supported since the owner's
        # call of 2026-11-21: the AppContainer control has
        # enforced at enforce where its trial proves since it
        # landed that day, and the level's name follows that
        # posture, as the macOS row's did the same evening.
        # The reduced-confinement level may not come back on
        # either row. (The words for it still stand in this
        # file's level definitions, as the record of the
        # departures, so the pin reads the rows themselves.)
        for name in ("Windows x86-64", "Windows ARM64"):
            row = _row(name)
            self.assertTrue(
                row.startswith("| %s | **Supported** |" % name),
                row[:60])
            self.assertNotIn("reduced confinement", row)
        # The shape limits stay stated on the x86-64 row
        # itself: the whole job ceiling beside the per
        # process one, the floor's open network where the
        # trial does not prove, and no processor ceiling in
        # either shape.
        row = _row("Windows x86-64")
        self.assertIn("for the job as a whole", row)
        self.assertIn("The floor isolates no network", row)
        self.assertIn("Neither shape sets a processor ceiling",
                      row)

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
        # The ceiling a job user brings, and that it asks
        # nothing of the host.
        self.assertIn(
            "a job that goes in as a job user is also held to %d "
            "processes of that user across the host, by a limit "
            "set at the jail door that needs no RACCT"
            % FC.DEFAULT_JOB_USER_PROCESSES, row)
        # The cores a job runs on, and that this limit asks
        # nothing of the host either.
        self.assertIn(
            "On a host with more than one core the jail is pinned "
            "to all but one of the cores the runner may run on, "
            "the lowest-numbered never a job's, by a cpuset the "
            "job cannot widen that needs no RACCT either", row)
        self.assertIn('"%s"' % FC.STATUS_CONFINEMENT, row)
        for name in ("no_superuser", "rctl_resource_limits",
                     "cpuset_cpu_limit", "private_loopback"):
            self.assertIn(name, FC.CONTROL_ORDER)
        self.assertIn("job_cpus", FC.FREEBSD_KEYS)

    def test_the_freebsd_row_keeps_its_honesty_lines(self):
        # What the jail is not stays on the row beside what it
        # is: it needs root, it is not Capsicum, the jail-wide
        # ceilings need RACCT, the node has run its live classes
        # but not the battery, and the hosted suite, green on the
        # record, is a signal no release waits for.
        row = _row("FreeBSD")
        self.assertIn("The backend needs root", row)
        # What root's uid still reads, and what closes it.
        self.assertIn("still the owner of what root owns", row)
        self.assertIn("until `security.job_user` names a user", row)
        # What a fresh install does about it, and what an
        # earlier one does not.
        self.assertIn("A fresh install whose probe passes makes an "
                      "account for the jobs alone (`pigeon-jobs`",
                      row)
        self.assertIn("`nobody` stands in on the same trial", row)
        self.assertIn("an install seeded before that names none",
                      row)
        self.assertIn("there is no Capsicum", row)
        self.assertIn("named only where RACCT is enabled", row)
        self.assertIn("a job with no job user has no ceiling on its "
                      "processes there", row)
        self.assertIn("the limit on cores is a set of cores, not a "
                      "share of time, shared by the jobs that run at "
                      "once, and a host with one core holds none "
                      "back", row)
        self.assertIn("refuses when it cannot engage", row)
        self.assertIn("the full battery has not been run against "
                      "this shape", row)
        self.assertIn("The workflow is a signal, not a gate: it "
                      "runs after a release is out, and no release "
                      "waits for it", row)

    def test_the_freebsd_row_states_the_suite_s_hosted_record(self):
        # The suite's first whole green run on a hosted FreeBSD
        # guest, by its run, and what the 30-minute clock did to
        # the runs around it.
        row = _row("FreeBSD")
        self.assertIn(
            "The suite first ran whole and green there on the "
            "v3.16.26.6 tag (run 43612998944, 2026-11-14)", row)
        self.assertIn("13,294 tests, 167 skipped by name and none "
                      "red, in 1,683 seconds", row)
        self.assertIn(
            "seven finished, in 1,360 to 1,683 seconds, and seven "
            "were stopped at 1,800, each in the last third of the "
            "suite", row)
        # The first run under the 45-minute clock: one the clock
        # before it would have stopped.
        self.assertIn(
            "The first run under it (run 43663671470, 2026-11-15) "
            "was a slow one, and it finished: 13,331 tests, 174 "
            "skipped by name and none red, in 1,969 seconds", row)
        # And the run after it, on another guest: the same tests
        # in three fifths of the time.
        self.assertIn(
            "ran the same 13,331 tests green in 1,178 seconds", row)

    def test_the_freebsd_row_names_the_clock_the_workflow_runs(self):
        # The row's minutes are the workflow's own: the number
        # is read out of freebsd.yml, not copied from the page.
        with open(os.path.join(REPO, ".github", "workflows",
                               "freebsd.yml"),
                  encoding="utf-8") as fh:
            live = "\n".join(
                ln for ln in fh.read().splitlines()
                if not ln.lstrip().startswith("#"))
        found = re.findall(
            r"suite_wall_clock\.py --minutes (\d+) ", live)
        self.assertEqual(len(found), 1, found)
        self.assertIn("the clock is %s minutes" % found[0],
                      _row("FreeBSD"))

    def test_the_stale_freebsd_suite_sentences_are_absent(self):
        # The matrix once said no hosted run of the FreeBSD
        # suite had completed green. One has, and those
        # sentences may not return.
        flat = _flat()
        for stale in ("the suite itself is not green",
                      "no hosted run has completed green",
                      "No green hosted FreeBSD suite run",
                      "so there is no release guarantee yet"):
            self.assertNotIn(stale, flat)

    def test_no_release_waits_for_a_freebsd_run(self):
        # The list of what is not yet true keeps the other half:
        # the hosted FreeBSD runs gate nothing.
        flat = _flat()
        self.assertIn("No release waits for a FreeBSD run", flat)
        self.assertIn(
            "a release can go out with that suite red or stopped "
            "at its clock", flat)
        self.assertIn(
            "one was green, six finished red and seven were "
            "stopped at the 30-minute clock it then had", flat)

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

    def test_the_macos_row_says_what_the_backend_does(self):
        # The row's words against the code they describe: the
        # ceiling's default and its setting, the launcher, the
        # services of the session a job may look up, the seed
        # that asks, and what the profile leaves a job able to
        # reach.
        from runner.guard import macos_confine as MC
        flat = _flat()
        self.assertEqual(MC.DEFAULT_PROCESS_MEMORY_BYTES,
                         512 * 1024 * 1024)
        self.assertIn("512 MiB above the size a bare process "
                      "starts at on that Mac", flat)
        self.assertEqual(MC.MACOS_KEYS,
                         ("process_memory_bytes", "mach_services"))
        for key in MC.MACOS_KEYS:
            self.assertIn("`security.confinement.macos.%s`" % key,
                          flat)
        self.assertEqual(MC.SHELL_BIN, "/bin/sh")
        self.assertIn("launcher shim, the system shell", flat)
        self.assertIn("set soft and hard, so it is not the job's "
                      "to raise unless the job is root", flat)
        self.assertIn("frozen macOS binaries engage it", flat)
        self.assertIn("A fresh install asks the same probe on the "
                      "Mac it installs on", flat)
        self.assertIn("of the session's services the user database "
                      "alone", flat)
        self.assertIn("the clipboard is refused to a job, to a read "
                      "and to a write", flat)
        self.assertNotIn("the clipboard was read from inside a job",
                         flat)
        self.assertNotIn("can reach the session's services", flat)
        self.assertEqual(
            [ln for ln in MC.build_profile("/work/j").splitlines()
             if "mach" in ln],
            ['(allow mach-lookup (global-name "com.apple.system.'
             'opendirectoryd.libinfo") (global-name "com.apple.'
             'system.opendirectoryd.membership"))'])
        self.assertIn("a job can list the host's processes and read "
                      "the hardware's properties", flat)
        self.assertIn("no ceiling on a job as a whole", flat)

    def test_the_macos_proof_workflow_is_the_one_named(self):
        flat = _flat()
        self.assertIn("(macos-confinement)", flat)
        self.assertIn("completed green on both Macs the same day "
                      "(run 43688324966)", flat)
        self.assertIn("The profile that names the services a job "
                      "may look up was read there the same day "
                      "(runs 43768512227 and 43769143056)", flat)
        self.assertTrue(os.path.isfile(os.path.join(
            REPO, ".github", "workflows", "macos-confinement.yml")))
        # The doubling ladder's own sentences are the first
        # backend's, and its record stands on the macOS page.
        self.assertNotIn(
            "The data-size refusal that once stood as the live "
            "word on the spawn limits is closed", flat)

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
