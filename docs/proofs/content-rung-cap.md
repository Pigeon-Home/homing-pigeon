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
