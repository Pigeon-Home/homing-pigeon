# Content redo — 500,000 characters

The earlier series at this length was a chain of one
command, repeated. This replaces that. It does not reuse
a stage number. `stage9.md` stays as history.

## How the scripts were built

The same catalogs as `content-rung-5000.md`, cycled one
command per line from three different starts, then one
pad line. Three bash scripts and three PowerShell
scripts, each exactly 500,000 characters. The three bash
texts differ. A fourth bash script is 500,001 characters.

The catalog repeats. 500,000 characters is far longer
than 22 lines. The record calls that a composed sample,
not an enumeration.

## What the checkers did

`bash -n` accepted every bash script, exit code 0. No
checker crashed. One command per line, which is the shape
that does not overflow the parser's stack.

PowerShell 7.5.4 parsed every PowerShell script through
`ParseInput`. The test skips that half, and says so,
where `pwsh` is not installed. On the machine that
produced this record, it ran.

## What the gate did

`handle_mail` admitted the three bash scripts, the three
PowerShell scripts, and the bash script of 500,001
characters. A cap of 100 bytes refused the three
500,000-character bash scripts, and the refusal named
`max_script_bytes`.

The harness is `runner/tests/test_proof_content_rung500000.py`.
The scripts were syntax-checked, not executed.

## What this does not say

500,000 is not a limit in the code. This is not every
construct that fits in 500,000 characters.
