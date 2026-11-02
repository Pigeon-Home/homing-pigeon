# Content redo — 50,000 characters

The earlier series at this length was three scripts, two of
them one quoted run. This replaces that. It does not reuse
a stage number. `stage8.md` stays as history.

## How the scripts were built

A catalog of 22 bash constructs and 16 PowerShell
constructs, the same kinds named in `content-rung-5000.md`.
Each script cycles that catalog, one command per line,
from a different start, then one pad line that makes the
length exact. Three bash scripts and three PowerShell
scripts, each exactly 50,000 characters. The three bash
texts differ. A fourth bash script is 50,001 characters.

The lines of each script are not all the same line. The
catalog repeats, because 50,000 characters is longer than
the catalog. The record calls that a composed sample, not
an enumeration.

## What the checkers did

`bash -n` accepted every bash script, exit code 0. No
checker crashed. The shape is one command per line.

PowerShell 7.5.4 parsed every PowerShell script through
`ParseInput` and reported no errors. The test skips that
half, and says so, where `pwsh` is not installed. On the
machine that produced this record, it ran.

## What the gate did

`handle_mail` admitted the three bash scripts, the three
PowerShell scripts, and the bash script of 50,001
characters. A cap of 100 bytes refused the three
50,000-character bash scripts and the three PowerShell
scripts, and the refusal named `max_script_bytes`.

The harness is `runner/tests/test_proof_content_rung50000.py`,
built by `runner/tests/proof_content_build.py`. The scripts
were syntax-checked, not executed. The four tests passed
in about 13 seconds.

## What this does not say

50,000 is not a limit in the code. The code's cap remains
1048576 bytes. This is not every construct that fits in
50,000 characters.

## Verification

This record was re-checked first-hand after the redo
landed, the same standard the stage 6 verification
applied.

- **The scripts were rebuilt independently**: 3 bash
  scripts and 3 PowerShell scripts of exactly 50,000
  characters, the 3 bash texts different, 23 distinct
  lines in a bash script, and a fourth bash script of
  exactly 50,001 characters. Every number matches the
  record.
- **The tests were re-run.** The harness's 4 tests passed,
  with no skips once a stock PowerShell 7.5.4 was on
  `PATH` (the first run on this machine skipped the
  PowerShell leg, and that run was not counted).
  PowerShell's parser accepted all 3 scripts, `bash -n`
  accepted every bash script with exit code 0 and no
  checker crashed, the gate admitted all 7 scripts, and a
  cap of 100 bytes refused the 50,000-character scripts
  with the refusal naming `max_script_bytes`.
- **The code was re-read.** The only length step on
  current main is the UTF-8 byte count against
  `max_script_bytes` in `runner/ops/mail.py`; 50,000
  appears nowhere in it.
