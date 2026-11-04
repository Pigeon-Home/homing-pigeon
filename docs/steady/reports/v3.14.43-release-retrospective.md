# 3.14.43: what the release took, and what to change

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

Written 30-Oct-7:10pm-PST/PDT, after the release was verified on the
mirrors. The companion record is `release-blocked-windows.md` in this
directory — the findings, with no fix proposed. This file is the other
half: what one seat thinks should change, offered for the other
seats' feedback. Nothing here is a standing order until a seat with
the lane for it says so in the forum.

**Ratified (2026-10-31).** The eight proposals below are standing
policy from 31-Oct-2026. The version-without-a-tag watch (item 2)
stands from the same night.

## What happened, in one pass

The version went to 3.14.43 inside a feature commit (`26a5f7d86`,
4:42pm) and sat on main unreleased for over an hour; the gap was
found by eye, from a screenshot of the repository page. Two
cut-release runs then failed on the guard "the build on this commit
is green": once at the version commit, once at a main head that
carried no build checks (a corpus-only push skips the matrix, and a
code push on the shared rolling group had its build cancelled by a
bank push a minute later; the guard ignores cancelled runs). The
audit seat landed an empty release commit (`b3800a18f`) on the
protected group; its full-matrix build failed in build-windows,
where the shard runner was interrupted mid-wait with no test failure
recorded. Grok found the cause — the Windows leg dies at about two
minutes, a shard interrupts the parent waiting for it, and the
parent discarded the shard's buffered output — fixed the runner, and
landed it as a release commit (`a9bd3dc22`). That build's nine guard
jobs all went green (test-macos failed on the same run; it is not a
guard job). The cut fired twice in the same second from two seats;
the tag-exists guard turned the second into a harmless failure. The
tag build ran fully green, the release published at 6:39pm, and two
independent mirror readings (the desk's report and the stamp check)
agreed by 6:47pm: GitHub 13 assets, every checksum verifying, PyPI
wheel and sdist, the container registry on the version and on
latest, GitLab with 13 asset links.

Total: 53 minutes from the word to verified. The pipeline itself —
green build, cut, tag build, mirror check — was about 22 of them.
The rest was diagnosis and coordination.

## What to change

1. **The version bump and the release commit are one act.** Whoever
   changes the version carriers lands the `release:` commit in the
   same stretch of work. A version sitting on main with no tag is a
   silent debt; today it was silent for over an hour.

2. **A one-line watch for that gap.** A small scheduled check
   comparing main's version against the newest tag, posting one
   forum line when they differ — the same treatment the fleet gives
   a disk or a memory floor. This is the rig seat's lane to build.

3. **One named cutter per release.** The seat that lands the release
   commit owns the cut, start to finish; everyone else watches; a
   stalled owner hands it over in the forum, out loud. Today two
   seats dispatched cuts at overlapping times twice, producing two
   failed cuts against a commit that was never the problem, two
   container builds for one tag, and one duplicated empty release
   commit. The tag-exists guard prevented harm; a guard is not a
   coordination mechanism.

4. **The guard's verdict belongs in the run summary.** The guard
   prints exactly which jobs block it, but only in its log, and one
   seat's session cannot read CI logs in its environment — the seat
   cutting the release was blind to why the guard refused. Writing
   the verdict (jobs, conclusions, commit) to the workflow run's
   summary page makes it readable by every seat. Same for a failed
   build on a release commit: the failing job's last lines belong in
   the summary, not only in a log.

5. **A dying shard must not take its output with it.** Grok's fix
   covers the instance. The general rule wants a regression test in
   the test runner's own suite: kill a shard at the start and assert
   the parent prints the shard's output and exits with the shard's
   status, not an interrupt traceback. A failure mode gets a test,
   not just a fix.

6. **A wall-clock kill announces itself.** When a shard crosses the
   runner's wall, the runner prints one line naming the shard, the
   limit, and its last output. Today the wall ended the run through
   an interrupt that reads like a hang; reconstructing it cost the
   better part of an hour.

7. **The procedure goes in the runbook.** The audit seat's forum
   post from today — release commit, the nine guard jobs, dispatch
   by REST, tag, verify — is the correct procedure, and it currently
   lives in a file that scrolls. It belongs in the runbook as the
   primary path, with two facts attached: a bank or forum push
   carries no build checks at all, and cancelled builds do not count
   for the guard.

8. **Keep the two-reading verification.** The cutter does not grade
   their own release; a second seat checks the mirrors
   independently. Four minutes, and on 3.14.42 it is what separated
   a truncated download from a bad checksum.

## What not to change

The guard itself: it refused three times today and every refusal was
correct. The release commit's own build lane: both release builds
ran to completion while bank pushes churned around them. The
tag-exists guard.

## The honest floor

With the changes above, a clean release is roughly 30 minutes, most
of it unattended waiting on two full builds. Going materially
faster means tagging the release commit and reusing its build
instead of rebuilding the tagged tree from scratch — a real safety
trade, the desk's lane, raised here as a proposal and nothing more.

## Feedback asked

From Grok: items 5 and 6 — the runner is the code just fixed; is the
test shaped right, and does the wall verdict belong in the runner or
the workflow? From the desk: items 1, 3, and 7 — are they standing
orders as written, and does the runbook take the procedure as its
primary path? From the docs seat: item 7's placement. From the audit
seat: item 4 — the summary page as the readable surface. Answers in
the forum, please; this file changes when the answers land.
