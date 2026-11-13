# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Core: the production runner, named as a set of files.

"Core" is a project feature with a fixed meaning: the stripped
production-runner code set — the code that runs, with no unit
tests, no test harnesses and nothing superfluous. When project
talk says "test core in this way", the set under test is the
set named here.

The set was first assembled on 2026-11-04 for a big-window
review (the Gemini conformance pass): the tree was cut down to
the runner alone so the whole of it fit 1 model window beside
the documentation. As assembled it held 133 files, zipped to
701,403 bytes, and the reviewing model's own counter (Gemini
countTokens) measured it at 619,845 tokens.

3 of those 133 files were the suite's own runners —
runner/tools/run_tests_parallel.py, run_tests_shuffled.py and
run_tests_windows_sim.py. Each exists only to run the unit
tests; none of them is runner code, and the definition of core
(no test harnesses) leaves them out. CORE_FILES below is
therefore the canonical list, at 130 files as first recorded;
the Oracle briefing work of 2026-11-08 added its 2 files
(runner/ops/briefing.py and runner/tools/make_briefing.py),
and the list stands at 132; the platform confinement backends
of 2026-11-09/10 added theirs (runner/guard/windows_confine.py
and runner/guard/freebsd_confine.py), and the list stands at
134; the disclosure posture module (runner/tools/disclosure.py)
joined it on 2026-11-10, when the posture stamp producer
wired the runner to load it at startup and at the result
seam — the first tools module the runner itself executes —
and the list stands at 135; the macOS confinement backend
(runner/guard/macos_confine.py) joined it on 2026-11-11,
and the list stands at 136, with the figures below
re-measured live by the CLI as always. This module itself
is not in the list either: the list names the set as assembled
for the 2026-11-04 pass, and this module is the tooling that
carries the list, written after that pass.

The token figures stay distinct and named, here and in the
CLI output:

- GEMINI_COUNT_TOKENS (619,845) is the Gemini countTokens
  measure of the set as assembled (133 files), 2026-11-04.
- The project estimator (runner/ops/version4.py's
  count_text_tokens) counts the canonical list (136 files as
  it now stands); the
  CLI prints its figure live. The estimator is not a BPE
  tokenizer, and the 2 figures are not interchangeable: the
  same estimator counts the as-assembled 133-file set at
  590,053, not 619,845.

Lines are counted live the same way, never recorded for the
canonical list: the as-assembled set runs to 65,992 lines,
59,822 of them non-blank (AS_ASSEMBLED_LINES and
AS_ASSEMBLED_NONBLANK_LINES below), and the CLI prints the
canonical list's own line count beside its token counts.

The headline inside those numbers: the runner proper,
runner/runner.py itself, is 7,152 lines; the core around it
is the rest. The as-assembled set's per-part line counts are
recorded in AS_ASSEMBLED_PART_LINES below; the CLI computes
and prints the canonical list's per-part counts live, and
the 2 breakdowns differ in exactly 1 part — runner/tools,
where the 3 excluded suite runners account for 847 lines.

Everything except main is a pure function of the tree at a
root. The zip build is deterministic — entries in list order,
a fixed timestamp (1980-01-01, the zip epoch), a fixed
compression level — so 2 builds of the same tree are
byte-identical. A listed file missing under the root is an
error (FileNotFoundError), never a silent skip: the list is
canonical, and drift between the list and the tree is a defect
to surface, not to paper over.

The CLI:

    python3 runner/ops/core.py [--root .]
        Print the core's file count, its line count (with the
        runner proper's own count and the per-part breakdown),
        its zip size in bytes and its token counts: the
        estimator's live count of the canonical list, and the
        recorded Gemini count of the set as assembled.

    python3 runner/ops/core.py build OUT.zip [--root .]
        Write the deterministic zip to OUT.zip, then print the
        same figures.
"""

import io
import os
import sys
import zipfile
from typing import List, Optional, Sequence, Tuple

try:
    from . import version4  # package: runner.ops.core
except ImportError:  # plain script: python3 runner/ops/core.py
    import version4  # noqa: F401  # pyrefly: ignore[missing-import]  # sibling module, on sys.path only as a plain script

# The set as assembled for the 2026-11-04 big-window pass, as
# re-measured on 2026-11-05 after the Q-new runner fixes
# (Q-new-1, Q-new-12, Q-new-25, Q-new-26) grew 4 of its files,
# and re-measured again the same day after the CHECKLIST-04
# send_job fixes (N2, G6, and the G6 key-match correction)
# grew runner/cloud/send_job.py, and again on 2026-11-06
# after the fy_iceworld F-1 fix (a key_share presence check
# in _on_server_hello) grew runner/wire/dtlsproto.py by
# 2 lines. That re-measure also corrects the zip figure:
# the value recorded on 2026-11-05 was the canonical list's
# zip size, not the as-assembled set's; the deterministic
# build over the 133 files gives the figure below.
# Re-measured again on 2026-11-06 after the signed-body
# strictness fix (duplicate member names refused and a
# nesting pre-scan in loads_signed) grew
# runner/guard/textutil.py by 57 lines, and after the
# audit hash-chain fix grew runner/guard/security.py and
# runner/ops/auditreport.py on the same day. Re-measured
# once more the same day after the Oracle tool-mode work
# and the startup posture assertion switch grew
# runner/ops/oracle_ops.py, runner/ops/posture.py,
# runner/guard/security.py and runner/runner.py past the
# figures that re-measure recorded, and once more after
# the outbox stash took the per-key guard in
# runner/runner.py: the runner proper stands at 6,635
# lines. Re-measured again on 2026-11-06 after the
# send_job verifier took the shared strict reader
# (loads_signed) for its signed-body parse, shedding
# 1 line net in runner/cloud. Re-measured again
# the same day after the startup gate took the
# resources and DRI paging readers (PF-1), growing
# runner/ops/main.py by 11 lines. Re-measured again
# on 2026-11-06 after the fy_iceworld fragment-buffer
# caps grew runner/wire/dtlsproto.py, and after the
# temp-reaping work — execute_job reaping its
# workspace on every path and the bounded startup
# orphan sweep — grew runner/ops, runner/tools,
# runner/guard and runner/runner.py. Re-measured again
# on 2026-11-07 after the job_user startup gate took its
# POSIX branches (Q132) and the confinement startup trial
# took the configured extra_flags (Q133), growing
# runner/ops and runner/guard, and the stamp audit took
# its historical-signings acceptance, growing runner/tools.
# Re-measured again on 2026-11-08 after the personal-
# documents shelter marker grew runner/oracle/
# personal_docs.py and the shelter's security-mode feature
# grew runner/guard/security.py. Re-measured again on
# 2026-11-08 after the Oracle briefing (shape 4) landed:
# runner/ops/briefing.py and runner/tools/make_briefing.py
# joined the canonical list (130 to 132 files, the
# as-assembled set 133 to 135), and the briefing wiring grew
# runner/ops, runner/tools and the runner proper.
# Re-measured again on 2026-11-08 after the release cut
# took a fresh, uncached token measure at every cut —
# version4's --fresh recount, with the measure cache
# recording the measure a cut takes — growing
# runner/ops/version4.py. Re-measured again the same
# day after the typecheck fix narrowed version4's cache
# write under an explicit `fresh is not None` guard,
# changing runner/ops/version4.py without growing it:
# the line figures stand, the estimator counts move by
# the guard's 5 tokens, and the zip grows by 4 bytes.
# Re-measured again the same day after the approval
# guard's security mode (agent_state_guard) grew
# runner/guard by 8 lines. Re-measured again on
# 2026-11-09 after the default-posture measurement
# corrected a comment in runner/ops/main.py (a missing
# security block reads enforce, not off), growing
# runner/ops by 1 line. Re-measured again on 2026-11-10
# after the platform confinement backends joined the
# canonical list (132 to 134 files): runner/guard/
# windows_confine.py, registered at the desk's standing
# follow-up, and runner/guard/freebsd_confine.py grew
# runner/guard, their wiring grew runner/ops and the
# runner proper, and the whole set was re-measured over
# the current tree for this entry, which also takes up
# the growth earlier landings had left unrecorded in
# runner/ops. Re-measured again the same day after the
# FreeBSD backend's first field test fixed its mount
# pass (a child tree on its parent's filesystem is not
# mounted twice; nullfs refuses the cycle), growing
# runner/guard, and again after the same field test's
# demote fixes (the jail root traversable by the job
# user, the spawn's working directory and host-side
# user resolution), growing runner/guard again.
# Re-measured again the same day after the Windows
# backend's import-safety change grew
# runner/guard/windows_confine.py by 15 lines, with the
# recorded figures carried into the statistics record
# and the documents that quote them. Re-measured again
# the same day after the fresh-install platform
# statement took its missing-config seed in
# runner/ops/install.py and the first-ping bench took
# the seeded platform statement in
# runner/tools/first_ping.py, growing runner/ops and
# runner/tools. Re-measured again the same day after the
# Q134 confinement trial grew runner/guard, and corrected
# in the same pass: that entry's re-measure had recorded
# the set below the tree it stood on (runner/ops by 11
# lines, runner/guard by 5, the runner proper by 8), which
# the head build's test leg named as a breakdown mismatch.
# Re-measured again the same day after the Q134 trial's
# staging fix (the makedirs staging and the BUILTIN\Users
# grant in the trial) grew
# runner/guard/windows_confine.py.
# Re-measured again the same day after the briefing's
# contradiction mark (the Q138 build) grew
# runner/ops/briefing.py and runner/ops/startup.py and the
# ask seams and the runner proper took the wiring.
# Re-measured again the same day after the posture stamp
# producer (Q137) wired the runner to the disclosure
# module — the assignment resolved at startup in
# runner/ops/main.py, the stamp set on the signed result
# in runner/ops/mail.py, the producer itself in the
# runner proper — growing runner/ops and the runner
# proper, and runner/tools/disclosure.py joined the
# canonical list above, the whole set re-measured over
# the current tree.
# Re-measured again the same day after the job_user
# postspawn fix — the confinement spawn's Job Object
# recorded by the postspawn instead of a second one
# assigned — grew runner/ops/remediation_ops.py by 36
# lines, which that landing left unrecorded; the head
# build's test legs named the gap as a breakdown
# mismatch in runner/ops.
# Re-measured again the same day after the Q139 build
# (the determination decision point) grew the runner
# proper and runner/wire, runner/ops and runner/guard,
# and after the Windows duration-table mode's growth
# of the excluded suite runner was counted in the
# as-assembled tools part, the whole set re-measured
# over the current tree.
# Re-measured again the same day after the Q141/Q142
# fixes (the v2_off early return and the guarded
# consult dispatch) grew the runner proper by 15
# lines, the whole set re-measured over the current
# tree; and again over the Q140 remediation landing
# that arrived in parallel, which grew runner/oracle
# by 11 lines.
# Re-measured again the same day after the Q143 fix
# (the briefing contradiction mark's negation guard,
# option 1) grew runner/ops/briefing.py by 120 lines,
# the whole set re-measured over the current tree.
# Re-measured again the same day after the Q144 fix
# (the guard widened: the whole clause segment, the
# not-only idiom, the ledger's own complement, and the
# prohibitive forms) grew runner/ops/briefing.py by
# 92 lines, the whole set re-measured over the
# current tree.
# Re-measured again the same day after the Q145 fix
# (the guard widened again: the assertive idioms
# completed, the ledger's separators completed, the
# governed infinitive, and the prohibitive reach)
# grew runner/ops/briefing.py by 149 lines, the whole
# set re-measured over the current tree.
# Re-measured again the same day after the Q146 fix
# (the guard widened again: the long adverbial
# lead-in, the subject relative clause, and the
# ledger's dash) grew runner/ops/briefing.py by
# 126 lines, the whole set re-measured over the
# current tree.
# Re-measured again the same day after the Q147 fix
# (the guard widened again: the subject clause opened
# by "that", the relative clause judged by its own
# infinitive, and the ledger's run of hyphens) grew
# runner/ops/briefing.py by 42 lines, the whole set
# re-measured over the current tree.
# Re-measured again the same day after the Q148 fix
# (the guard widened again: the subject clause's
# comma read as a parenthetical, the relative clause
# judged by its verb phrase, and the ledger's
# remaining separators) grew runner/ops/briefing.py
# by 263 lines, the whole set re-measured over the
# current tree.
# Re-measured again the same day after the Q149 fix
# (the guard widened again: the clause-head
# parenthetical, the relative clause judged by its
# verb phrase generally, and the ledger's next
# separators) grew runner/ops/briefing.py
# by 175 lines, the whole set re-measured over the
# current tree.
# Re-measured again the same day after the Q150 fix
# (the guard widened again: the doubled clause-head
# parenthetical and its dropped-comma form, the
# governed noun phrase judged by its verb, the
# relative clause judged at the adjective, tailed
# by-phrase and base-form shapes, and the ledger's
# remaining separators) grew runner/ops/briefing.py
# by 185 lines, the whole set re-measured over the
# current tree.
# Re-measured again the same day after the Q151 fix
# (the guard widened again: the governed noun
# phrase judged in full -- determiner-led,
# adjective-led and plural noun complements -- and
# the ledger's last separators, its fold-erased
# whitespace shapes and the full stop) grew
# runner/ops/briefing.py by 124 lines, the whole
# set re-measured over the current tree.
# Re-measured again the same day after the Q152 fix
# (the guard widened again: the governed phrase
# judged by its place and its head's standing --
# the possessive "her" in the determiner place, a
# verb-form adjective, and a head outside the
# closed complement set -- every fold-erased
# whitespace shape read as a boundary, and the
# ledger's remaining punctuation separators) grew
# runner/ops/briefing.py by 150 lines, the whole
# set re-measured over the current tree.
# Re-measured again the same day after the Q153 fix
# (the guard widened again: the governed phrase's
# head judged by its place in the phrase -- a
# verb-form noun standing as its noun, a bare
# singular by its head's standing -- and by the
# standing of its governing verb, the format
# joiners read as boundaries, and the ledger's
# last punctuation separators) grew
# runner/ops/briefing.py by 106 lines, the whole
# set re-measured over the current tree.
# Re-measured again the same day after the Q154 fix
# (the guard widened again: a governed phrase
# judged by its own shape -- a common-noun phrase
# between the clause's verb and its infinitive is
# the clause's object phrase whatever verb governs
# it, a complement verb's phrase and a closed
# complement head still crossed -- the bidi and
# invisible characters read as boundaries, and the
# ledger's last punctuation separators) grew
# runner/ops/briefing.py by 138 lines, the whole
# set re-measured over the current tree.
# Re-measured again the same day after the Q155 fix
# (the guard widened again: a governed phrase
# judged by its own shape through a relative
# clause the phrase itself carries, the format
# characters standing past the fold's ranges read
# as boundaries, and the ledger's remaining
# punctuation separators) grew
# runner/ops/briefing.py by 77 lines, the whole
# set re-measured over the current tree.
# Re-measured again the same day after the macOS
# confinement backend joined the canonical list
# (135 to 136 files): runner/guard/macos_confine.py
# grew runner/guard, and its wiring grew runner/ops
# and the runner proper, the whole set re-measured
# over the current tree.
# Re-measured again the same day after the Q156 fix
# (the guard widened again: a governed phrase
# judged by its own shape through a "whose" clause
# the phrase itself carries, the Arabic-block
# format characters read as boundaries, and the
# ledger's remaining punctuation separators) grew
# runner/ops/briefing.py by 62 lines, the whole
# set re-measured over the current tree.
# Re-measured again the same day after the macOS
# confinement fix (the launcher shim's data-size-only
# limit, the profile's /private canonical twins and
# real-path work directory, and the spawn seam's
# single sys.platform signal) grew
# runner/guard/macos_confine.py and
# runner/ops/remediation_ops.py, the whole set
# re-measured over the current tree.
# Re-measured again the same day after the Q157 fix
# (the guard widened again: a governed phrase
# judged by its head's standing through a
# pied-piped relative clause the phrase itself
# carries, the Egyptian hieroglyph format controls
# read as boundaries, and the ledger's remaining
# punctuation separators) grew
# runner/ops/briefing.py by 95 lines, the whole
# set re-measured over the current tree.
# Re-measured again the same day after the macOS
# confinement second fix (the profile's root-listing
# grant and /private startup trees, and the live
# bisect in its test suite) grew
# runner/guard/macos_confine.py, and the Q158 fix
# (the briefing guard widened again) grew
# runner/ops/briefing.py, the whole set re-measured
# over the current tree.
# Re-measured again the same day after the Q160 fix
# (the guard widened again: a governed phrase
# judged by its head's standing through a
# pied-piped relative clause whatever its lead's
# shape, the Kaithi number signs and the
# variation-selector characters beyond the BMP
# read as boundaries, and the ledger's remaining
# general-punctuation and supplemental-punctuation
# separators) grew runner/ops/briefing.py by 114
# lines, the whole set re-measured over the
# current tree; this measure also takes up the
# Q136 shard-5 growth of runner/ops/av.py and the
# 3.16.20.6 release's pipeline repair in
# runner/ops, which the earlier records had not
# carried.
# Re-measured again the same day after the Q136
# shard-7 follow-on (the _run_text collect path
# abandons a held pipe unclosed, and the Windows
# registry and event-log probes read through
# _run_text instead of subprocess.run) grew
# runner/ops/av.py and runner/ops/windows.py,
# the whole set re-measured over the current
# tree; this measure also takes up the
# install.py split and the macOS confinement
# growth of runner/guard that landed in
# parallel, which the earlier records had not
# carried.
# Re-measured again the same day after the Q161 fix
# (the guard widened again: a governed phrase
# judged by its head's standing through a
# pied-piped relative clause whose lead carries a
# person head, the variation-selector characters
# of the BMP read as boundaries, and the ledger's
# supplemental-punctuation remainder and
# small-form separators) grew
# runner/ops/briefing.py by 91 lines, the whole
# set re-measured over the current tree; this
# measure also takes up the changes other lanes
# landed after the Q136 shard-7 measure -- the
# 3.16.20.7 release head and the macOS
# confinement fixes in runner/guard -- which the
# earlier records had not carried.
# Re-measured again the same day after the macOS
# confinement fourth fix (the launcher shim's
# data-size computation: the inherited hard limit
# kept, the soft request clamped to it, and a
# bounded ladder of attempts against the kernel's
# current-usage floor) grew
# runner/guard/macos_confine.py by 102 lines, the
# whole set re-measured over the current tree.
# Re-measured again on 2026-11-12 after the
# post-kill wait bound (a job that will not die
# after the tree kill cannot hold the shard) grew
# runner/ops/exec.py by 16 lines, the whole set
# re-measured over the current tree; this measure
# also takes up the desk-chain growth of
# runner/ops other lanes landed after the macOS
# confinement fourth-fix measure, which the
# earlier records had not carried.
# Re-measured again on 2026-11-12 after the macOS
# confinement fifth fix (the launcher shim's
# data-size ladder climbing to 2**62 for an
# unlimited inherited hard limit) grew
# runner/guard/macos_confine.py by 21 lines, the
# whole set re-measured over the current tree.
# Re-measured again on 2026-11-12 after the Q164
# fix (the briefing guard widened again: ledger
# segments open at the bracket-ornament and
# mathematical-bracket separators, the remainders
# of the filed blocks and their nearest
# neighbours, the remaining assigned punctuation
# of the Basic Multilingual Plane and the
# remaining assigned punctuation beyond it) grew
# runner/ops/briefing.py by 11 lines, the whole
# set re-measured over the current tree.
# Re-measured again on 2026-11-12 after the Q167
# fix (the briefing guard opens ledger segments
# at a spaced token of category L, Cc or Co -- the
# assigned letters of the BMP and beyond it, the
# assigned controls outside the fold's break and
# erased sets and the assigned private-use
# characters) grew runner/ops/briefing.py by 47
# lines, the whole set re-measured over the
# current tree.
# Recorded constants: they describe the as-assembled set (the
# canonical list as first recorded -- 132 files -- plus the 3 suite runners named in
# the module docstring; the list itself stands at 136 since
# the 2026-11-11 entry above), not the canonical list itself. The
# reviewing model's own token measure of the set (Gemini
# countTokens) is a measure of the 2026-11-04 assembly and is
# NOT re-recorded here: no re-count of the grown set has been
# run, so GEMINI_COUNT_TOKENS below still describes that
# assembly. The zip size and the estimator counts re-measured
# here come from this module's own deterministic build and
# counter over the current tree.
AS_ASSEMBLED_FILES = 139
AS_ASSEMBLED_ZIP_BYTES = 855207
AS_ASSEMBLED_LINES = 65992
AS_ASSEMBLED_NONBLANK_LINES = 59822
# The as-assembled set's lines, part by part; the parts sum
# to AS_ASSEMBLED_LINES. A part is a folder under runner/, or
# a file standing directly under runner/ as its own part.
AS_ASSEMBLED_PART_LINES = {
    "runner/ops": 22585,
    "runner/tools": 9999,
    "runner/wire": 9033,
    "runner/runner.py": 7179,
    "runner/oracle": 5055,
    "runner/transport_extensions": 2775,
    "runner/guard": 5580,
    "runner/cloud": 2049,
    "runner/hosting": 1704,
    "runner/__init__.py": 23,
    "runner/_version.py": 10,
}
GEMINI_COUNT_TOKENS = 619845
GEMINI_COUNT_DATE = "2026-11-04"

# The canonical core: the as-assembled set minus the 3 suite
# runners named in the module docstring. Sorted, duplicate-free,
# every path under runner/. Pinned by runner/tests/test_core.py.
CORE_FILES = (
    "runner/__init__.py",
    "runner/_version.py",
    "runner/cloud/__init__.py",
    "runner/cloud/send_dtls.py",
    "runner/cloud/send_job.py",
    "runner/guard/__init__.py",
    "runner/guard/atomicio.py",
    "runner/guard/confval.py",
    "runner/guard/defaulted.py",
    "runner/guard/extreview.py",
    "runner/guard/filenames.py",
    "runner/guard/freebsd_confine.py",
    "runner/guard/macos_confine.py",
    "runner/guard/panic.py",
    "runner/guard/sandbox.py",
    "runner/guard/security.py",
    "runner/guard/textutil.py",
    "runner/guard/windows_confine.py",
    "runner/hosting/__init__.py",
    "runner/hosting/base.py",
    "runner/hosting/billing.py",
    "runner/hosting/bootstrap.py",
    "runner/hosting/cli.py",
    "runner/hosting/digitalocean.py",
    "runner/hosting/fly.py",
    "runner/hosting/github_actions.py",
    "runner/hosting/hetzner.py",
    "runner/hosting/httpdoor.py",
    "runner/hosting/inventory.py",
    "runner/ops/__init__.py",
    "runner/ops/attest.py",
    "runner/ops/auditreport.py",
    "runner/ops/av.py",
    "runner/ops/briefing.py",
    "runner/ops/cancel.py",
    "runner/ops/changes.py",
    "runner/ops/cli.py",
    "runner/ops/context.py",
    "runner/ops/exec.py",
    "runner/ops/extensions.py",
    "runner/ops/extsources.py",
    "runner/ops/firewall.py",
    "runner/ops/handlers.py",
    "runner/ops/harness.py",
    "runner/ops/helpers.py",
    "runner/ops/install.py",
    "runner/ops/live.py",
    "runner/ops/local_test.py",
    "runner/ops/mail.py",
    "runner/ops/main.py",
    "runner/ops/misc.py",
    "runner/ops/oracle_ops.py",
    "runner/ops/oracle_page.py",
    "runner/ops/oracle_server.py",
    "runner/ops/oracle_tools.py",
    "runner/ops/paths.py",
    "runner/ops/policy.py",
    "runner/ops/poll.py",
    "runner/ops/posture.py",
    "runner/ops/queries.py",
    "runner/ops/recipes.py",
    "runner/ops/remediation_ops.py",
    "runner/ops/sensors.py",
    "runner/ops/setup.py",
    "runner/ops/startup.py",
    "runner/ops/tables.py",
    "runner/ops/version4.py",
    "runner/ops/watch.py",
    "runner/ops/windows.py",
    "runner/ops/winlog.py",
    "runner/oracle/__init__.py",
    "runner/oracle/detection.py",
    "runner/oracle/dri.py",
    "runner/oracle/learning.py",
    "runner/oracle/opinion.py",
    "runner/oracle/personal_docs.py",
    "runner/oracle/remediation.py",
    "runner/oracle/resources.py",
    "runner/oracle/review.py",
    "runner/oracle/senses.py",
    "runner/runner.py",
    "runner/tools/ci_run_report.py",
    "runner/tools/ci_scope.py",
    "runner/tools/coverage_gaps.py",
    "runner/tools/coverage_one.py",
    "runner/tools/coverage_targets.py",
    "runner/tools/disclosure.py",
    "runner/tools/fetch_upstream.py",
    "runner/tools/first_ping.py",
    "runner/tools/linecov.py",
    "runner/tools/live_capture.py",
    "runner/tools/make_briefing.py",
    "runner/tools/make_sbom.py",
    "runner/tools/make_snapshot.py",
    "runner/tools/mutation_floor.py",
    "runner/tools/pin_extension_sources.py",
    "runner/tools/platform_plan.py",
    "runner/tools/regression_guard.py",
    "runner/tools/regression_pass.py",
    "runner/tools/repair_script_imports.py",
    "runner/tools/rig_bank.py",
    "runner/tools/rig_resources.py",
    "runner/tools/skip_guard.py",
    "runner/tools/soak.py",
    "runner/tools/stamp_audit.py",
    "runner/tools/stamp_provenance.py",
    "runner/tools/stdlib_coverage.py",
    "runner/tools/suite_wall_clock.py",
    "runner/tools/switch_proofs.py",
    "runner/tools/upgrade_proof.py",
    "runner/tools/windows_surface.py",
    "runner/transport_extensions/__init__.py",
    "runner/transport_extensions/channel.py",
    "runner/transport_extensions/dtls/__init__.py",
    "runner/transport_extensions/dtls/__main__.py",
    "runner/transport_extensions/email/__init__.py",
    "runner/transport_extensions/email/__main__.py",
    "runner/transport_extensions/file/__init__.py",
    "runner/transport_extensions/file/__main__.py",
    "runner/transport_extensions/nats/__init__.py",
    "runner/transport_extensions/nats/__main__.py",
    "runner/transport_extensions/queues/__init__.py",
    "runner/transport_extensions/queues/__main__.py",
    "runner/wire/__init__.py",
    "runner/wire/board.py",
    "runner/wire/dtls_mailbox.py",
    "runner/wire/dtlsproto.py",
    "runner/wire/jobcrypto.py",
    "runner/wire/mailbox.py",
    "runner/wire/mlkem.py",
    "runner/wire/oauth.py",
    "runner/wire/platformcard.py",
    "runner/wire/protocol_v2.py",
    "runner/wire/subject.py",
    "runner/wire/transports.py",
    "runner/wire/verify.py",
)

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_ZIP_COMPRESSLEVEL = 9


def _read_core_file(root: str, name: str) -> bytes:
    """One listed file's bytes; a missing file is an error."""
    path = os.path.join(root, name)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        raise FileNotFoundError(
            "core file missing under %r: %s" % (root, name))


def core_zip_bytes(root: str,
                   files: Sequence[str] = CORE_FILES) -> bytes:
    """The deterministic zip of the core files under root.

    Entries are written in the order of `files` (the canonical
    list is sorted), each with the fixed zip-epoch timestamp,
    so 2 builds over the same tree are byte-identical.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w",
                         compression=zipfile.ZIP_DEFLATED,
                         compresslevel=_ZIP_COMPRESSLEVEL) as zf:
        for name in files:
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o600 << 16
            zf.writestr(info, _read_core_file(root, name),
                        compresslevel=_ZIP_COMPRESSLEVEL)
    return buffer.getvalue()


def build_core_zip(root: str, out_path: str,
                   files: Sequence[str] = CORE_FILES) -> int:
    """Write the deterministic core zip to out_path; return its size."""
    data = core_zip_bytes(root, files)
    with open(out_path, "wb") as fh:
        fh.write(data)
    return len(data)


def measure_core_tokens(root: str,
                        files: Sequence[str] = CORE_FILES) -> int:
    """The project estimator's token count of the core under root.

    Sums runner/ops/version4.py's count_text_tokens over the
    listed files — the estimator, not a BPE tokenizer; see the
    module docstring for the recorded Gemini count and why the
    2 figures are kept distinct.
    """
    total = 0
    for name in files:
        data = _read_core_file(root, name)
        total += version4.count_text_tokens(data.decode("utf-8", "replace"))
    return total


def measure_core_lines(root: str,
                       files: Sequence[str] = CORE_FILES
                       ) -> Tuple[int, int]:
    """(total lines, non-blank lines) of the core under root.

    Counted live over the listed files, so the figure stays
    honest as the set changes; the recorded as-assembled
    figures are the constants above. A line is non-blank when
    it holds more than whitespace.
    """
    total = 0
    nonblank = 0
    for name in files:
        data = _read_core_file(root, name)
        lines = data.decode("utf-8", "replace").splitlines()
        total += len(lines)
        nonblank += sum(1 for line in lines if line.strip())
    return (total, nonblank)


def _part_of(name: str) -> str:
    """A core file's part: its folder under runner/, or the file
    itself when it stands directly under runner/."""
    rest = name[len("runner/"):]
    if "/" in rest:
        return "runner/" + rest.split("/")[0]
    return name


def measure_core_lines_by_part(root: str,
                               files: Sequence[str] = CORE_FILES
                               ) -> dict:
    """Line counts of the core under root, part by part.

    Computed live over the listed files, like the other
    measures; the recorded as-assembled breakdown is
    AS_ASSEMBLED_PART_LINES above. The parts sum to
    measure_core_lines' total.
    """
    parts = {}
    for name in files:
        data = _read_core_file(root, name)
        count = len(data.decode("utf-8", "replace").splitlines())
        part = _part_of(name)
        parts[part] = parts.get(part, 0) + count
    return parts


def _figures(root: str) -> List[str]:
    """The CLI's report lines for the tree at root."""
    zip_bytes = len(core_zip_bytes(root))
    total_lines, nonblank_lines = measure_core_lines(root)
    parts = measure_core_lines_by_part(root)
    lines = [
        "core files: %d" % (len(CORE_FILES),),
        "core lines: %d (%d non-blank)" % (total_lines, nonblank_lines),
        "core lines in runner/runner.py: %d"
        % (parts.get("runner/runner.py", 0),),
        "core lines by part:",
    ]
    for part in sorted(parts, key=lambda p: (-parts[p], p)):
        lines.append("  %s: %d" % (part, parts[part]))
    lines += [
        "core zip bytes: %d" % (zip_bytes,),
        "core tokens (project estimator): %d"
        % (measure_core_tokens(root),),
        "core tokens (Gemini countTokens, %s): %d"
        % (GEMINI_COUNT_DATE, GEMINI_COUNT_TOKENS),
    ]
    return lines


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: print the core's figures; `build` also writes the zip."""
    args = list(sys.argv[1:] if argv is None else argv)
    root = "."
    out = None
    positional = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--root" and i + 1 < len(args):
            root = args[i + 1]
            i += 2
        else:
            positional.append(arg)
            i += 1
    if positional:
        if positional[0] == "build" and len(positional) == 2:
            out = positional[1]
        else:
            print("usage: core.py [--root .] | build OUT.zip [--root .]",
                  file=sys.stderr)
            return 2
    try:
        if out is not None:
            build_core_zip(root, out)
        lines = _figures(root)
    except FileNotFoundError as exc:
        print("core.py: %s" % (exc,), file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
