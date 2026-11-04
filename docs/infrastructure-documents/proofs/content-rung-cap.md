# Content redo — the production cap, and the close of the series

The earlier series at this boundary used the same three
shapes as the rungs below it, and its first record claimed
a clean pass while `bash -n` had crashed. This replaces
that. It does not reuse a stage number. `stage10.md` stays
as history. The ladder's model check at this number is
`stage10-1048576.md`, which is a different artefact.

## How the scripts were built

The same catalogs, cycled one command per line from three
different starts, then one pad line. The scripts are
ASCII, so the character count and the byte count are the
same number. The check counts bytes.

Three bash scripts and three PowerShell scripts of exactly
1048576 bytes. One bash script and one PowerShell script
of 1048577 bytes. The three bash texts at the cap differ.
The lines of each script are not one command repeated.

## What the checkers did

`bash -n` accepted every bash script, including the one
byte over the cap, exit code 0. No checker crashed.

PowerShell 7.5.4 parsed every PowerShell script through
`ParseInput`, including the one byte over. The test skips
that half, and says so, where `pwsh` is not installed. On
the machine that produced this record, it ran.

## What the gate did

`handle_mail`, with the cap left at its default, admitted
every script of exactly 1048576 bytes, bash and
PowerShell. It refused both scripts of 1048577 bytes, and
the refusal named `max_script_bytes` and the number
1048577. The text did not change either decision.

The harness is `runner/tests/test_proof_content_rung_cap.py`.
The scripts were syntax-checked, not executed.

## The series is complete

This is the last rung the review asked for. The redo, in
the order it landed:

- the first rung, 3,682 bash scripts and 511 PowerShell
  scripts, each at most 49 characters: `content-rung-49.md`
- 5,000 characters, both shells: `content-rung-5000.md`
- 50,000 characters, both shells: `content-rung-50000.md`
- 500,000 characters, both shells: `content-rung-500000.md`
- the production cap, both shells: this record

The old records `stage7.md` through `stage10.md` stay as
history. This series supersedes them. It does not claim
every string, or every nesting, at any rung above the
first. The first rung is the combinations of its atom
list, not every string of 49 characters. Nothing here is
the first-hand verification. That follows separately, as
the review said it would.

## Verification

The first-hand verification this record pointed to is
done. It was carried out after the whole redo landed, to
the same standard the stage 6 verification applied, and
a Verification section is appended to each rung's record
(`content-rung-49.md`, `content-rung-5000.md`,
`content-rung-50000.md`, `content-rung-500000.md`, and
this one). The verdict for the series: every recorded
count, length, and gate outcome reproduced, and no claim
in any rung record was wrong.

- **The scripts at this rung were rebuilt independently**:
  3 bash scripts and 3 PowerShell scripts of exactly
  1048576 bytes, the 3 bash texts different, and scripts
  of 1048577 bytes past the cap. The scripts are ASCII, so
  the character count and the byte count are the same
  number, as recorded.
- **The tests were re-run.** Across the 5 redo rungs the
  harnesses run 22 tests. All 22 passed with no skips,
  once a stock PowerShell 7.5.4 build — downloaded for
  this check and put on `PATH` — was present: a first run
  without it skipped the 4 PowerShell legs of the rungs
  above the first, and that run was not counted as a pass
  for those legs. At this rung, `bash -n` accepted every
  bash script including the one past the cap, exit code
  0, no checker crashed; PowerShell's parser accepted
  every PowerShell script including the one past the cap;
  the gate at its default cap admitted every script of
  exactly 1048576 bytes and refused both scripts of
  1048577 bytes, the refusal naming `max_script_bytes` and
  the number 1048577. The builder module's 9 tests also
  passed: the linear builder produces the same scripts as
  the reference it is pinned against, at every rung.
- **The code was re-read.** On current main the gate's
  only length step is in `runner/ops/mail.py`:
  `len(script.encode("utf-8"))` against
  `max_script_bytes`, default 1048576, placed after the
  signature is verified. No step in the check order
  branches on a script's text, and no other length is
  measured.
- **Scope.** This verification covers the redo series:
  bash and PowerShell at the 5 rungs. The macOS and
  FreeBSD shell records (`content-sh-macos.md`,
  `content-sh-freebsd.md`) are a separate series and are
  not verified here; the FreeBSD record's own statement
  stands — that shell was not run, and a skip is not a
  pass.
