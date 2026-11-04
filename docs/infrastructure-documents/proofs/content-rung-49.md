# Content redo — the first rung, 49 characters

The earlier series listed twenty-two scripts here. This
replaces that sample with a generated set. It does not
reuse a stage number. The old record, `stage7.md`, stays
as history.

## How the set was generated

Bash. Twenty-two atoms: simple commands, quoting, a
parameter expansion, a command substitution, arithmetic,
a brace expansion, a group, a redirection, a conditional.
Every atom is kept. Every pair of atoms joined by `&&`,
`||`, `;`, or a pipe is kept when the result is at most
49 characters. Every triple of the atoms that are
themselves at most 8 characters, joined by `;`, is kept
on the same rule. That is 3,682 scripts. The longest is
46 characters.

PowerShell. Ten atoms in its own syntax, the same two
shapes: pairs joined by `;` or a pipe, and triples of the
shorter atoms. That produced 521 candidates. The real
parser rejected 10 of them. Those 10 were not given to
the gate. 511 survived, each at most 49 characters.
PowerShell's constructs are longer than bash's, so 49
characters does not hold thousands of them. The record
says so. 511 is the set the bound can hold, not a sample
cut down from a larger one.

## What the checkers did

`bash -n` was run once on the 3,682 scripts joined by
newlines. Exit code 0. A syntax error in any script
would have failed that file. No checker crashed.

PowerShell 7.5.4 parsed the 521 candidates in one
process, through `ParseInput`, and the 511 survivors are
the ones it accepted. The binary was a stock 7.5.4
linux-x64 build. The test looks for `pwsh` on `PATH` and
then `/workspace/pwsh/pwsh`. Where neither exists, the
PowerShell cases skip and the skip says the half was not
run. On the machine that produced this record, they ran.

## What the gate did

`handle_mail` admitted all 3,682 bash scripts and all 511
PowerShell scripts. The decision did not depend on which
constructs were in the script.

The cap check is a sample, and it is named as one. Twenty
bash scripts longer than one byte were refused at a cap
of 1 byte, and the refusal named `max_script_bytes`. The
one-byte script `:` was admitted at that cap. The
admission of the whole set is not a sample. The cap check
is.

The harness is `runner/tests/test_proof_content_rung49.py`.
The scripts were syntax-checked, not executed. The five
tests passed in about 50 seconds.

## What this does not say

This is not every string of 49 characters. It is the
combinations of this atom list, at this depth: pairs, and
triples of the short atoms. Deeper nesting is not in the
set. The rungs above 49 are not claimed here.

## Verification

This record was re-checked first-hand after it landed,
the same standard the stage 6 verification applied:
nothing in the record above was taken on the author's
word.

- **The generation was recomputed independently**, outside
  the test harness: 22 bash atoms give 3,682 scripts, the
  longest 46 characters, all distinct; 10 PowerShell atoms
  give 521 candidates. Both numbers match the record.
- **The tests were re-run.** The harness's 5 tests passed
  with no skips, with a stock PowerShell 7.5.4 on `PATH`
  (a fresh download for this check; the first run on this
  machine skipped the PowerShell leg, and that run was not
  counted). The PowerShell parser dropped exactly 10
  candidates and the 511 survivors were all admitted, as
  recorded. `bash -n` accepted the whole bash set as one
  file, exit code 0, and `handle_mail` admitted all 3,682
  bash scripts one by one.
- **The code was re-read.** The gate's only length step on
  current main is in `runner/ops/mail.py`:
  `len(script.encode("utf-8"))` against `max_script_bytes`,
  default 1048576, and the refusal names
  `max_script_bytes`. No step branches on a script's text.
