# Content redo — 5,000 characters

This is the missing rung of the content-independence series.
`content-series-review.md` asked for it first. The earlier
series jumped from the first rung to 50,000 and never
recorded 5,000. This record does not reuse a stage number.
The ladder's own check at this bound is `stage7-5000.md`,
which is the model. This is the scripts, presented to the
gate.

## How the scripts were built

A catalog of 22 bash constructs and 16 PowerShell
constructs: a simple command, a pipeline, `&&` and `||`,
a conditional, a loop, a function, grouping, brace
expansion, parameter and command and arithmetic
expansion, a redirection, quoting, and a line whose text
is `allowed_interpreters`. The PowerShell catalog is the
same kinds of construct in PowerShell's own syntax.

Each script is the catalog cycled, one command per line,
starting at a different place in the catalog, then one
pad line (`echo` or `Write-Output` of a quoted run of the
letter `p`) that makes the character count exact. Three
bash scripts and three PowerShell scripts, each exactly
5,000 characters, and the three bash texts differ. A
fourth bash script is 5,001 characters.

This is a sample. It is the catalog, repeated, not every
way the constructs can nest. The record calls it a sample.

## What the checkers did

`bash -n` accepted every bash script, exit code 0. No
checker crashed. The chains are one command per line, so
this is not the one-line shape that overflowed the
parser's stack at the cap.

PowerShell 7.5.4 parsed every PowerShell script, through
`[System.Management.Automation.Language.Parser]::ParseInput`,
and reported no errors. The binary was not on the image.
It was a stock 7.5.4 linux-x64 build, run from
`/workspace/pwsh/pwsh` because `/tmp` is mounted noexec.
The test looks for `pwsh` on `PATH` and then that path.
Where neither exists, the PowerShell cases skip and the
skip says the half was not run. On the machine that
produced this record, they ran.

## What the gate did

`handle_mail` admitted all four bash scripts and all three
PowerShell scripts. The text did not change the decision,
and one character past the rung did not either. Under a
cap of 100 bytes every one of the 5,000-character scripts
was refused, and the refusal named `max_script_bytes`.

The harness is `runner/tests/test_proof_content_rung5000.py`.
The scripts were syntax-checked, not executed. The five
tests passed.

## What this does not say

5,000 is not a limit in the code. The code's cap remains
1048576 bytes. This rung does not enumerate the construct
space. The rungs above it are not claimed here.

## Verification

This record was re-checked first-hand after the redo
landed, the same standard the stage 6 verification
applied: nothing in the record above was taken on the
author's word. This is the rung the original series
skipped, so it was checked first among the redo rungs.

- **The scripts were rebuilt independently**, outside the
  test harness: catalogs of 22 bash constructs and 16
  PowerShell constructs, cycled one command per line. 3
  bash scripts of exactly 5,000 characters, all 3 texts
  different, 23 distinct lines in each (the 22 catalog
  lines and the pad line); 3 PowerShell scripts of exactly
  5,000 characters; a fourth bash script of exactly 5,001.
  Every number matches the record.
- **The tests were re-run.** The harness's 5 tests passed.
  The first run on this machine skipped the PowerShell
  test — `pwsh` was not installed — and that run was not
  counted. A stock PowerShell 7.5.4 build was then put on
  `PATH` and the rung re-ran with no skips: PowerShell's
  own parser accepted all 3 scripts, the gate admitted all
  4 bash scripts and all 3 PowerShell scripts, and a cap
  of 100 bytes refused every 5,000-character script with
  the refusal naming `max_script_bytes`. `bash -n`
  accepted every bash script, exit code 0; no checker
  crashed.
- **The code was re-read.** On current main the gate's
  only length step is in `runner/ops/mail.py`: the UTF-8
  byte count against `max_script_bytes`, default 1048576.
  5,000 appears nowhere in that step, which is why the
  5,001-character script is admitted, as recorded.
