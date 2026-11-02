# Stage 10 — content-independence at the production cap

The ladder's last figure is the code's own script cap.
`max_script_bytes` defaults to 1048576, and the code
refuses a script whose UTF-8 length is greater than that
number. A script of exactly 1048576 bytes is admitted. A
script of 1048577 bytes is refused. The text does not
change either decision.

The scripts are ASCII, so the character count and the
byte count are the same number. The check counts bytes.
That is the difference this stage exists to keep visible:
the earlier rungs were character bounds of the claim, and
this one is the byte boundary the runner enforces.

## The scripts

Three scripts of exactly 1048576 bytes, each accepted by
`bash -n`:

- a chain of `true;` filled out with one `:`, because
  1048576 is not divisible by the length of `true;`
- `echo` of a quoted run of the letter `a`
- `echo` of a quoted run of the words `allowed_interpreters`

Two scripts of 1048577 bytes: the chain plus one more `:`,
and the letter script plus one more `a`.

## What the gate does

With the cap left at its default, `handle_mail` admits the
three scripts of exactly 1048576 bytes. It refuses both
scripts of 1048577 bytes, and the refusal names
`max_script_bytes` and the number 1048577. The three
admitted texts differ. The two refused texts differ.

The harness is `runner/tests/test_proof_content_cap.py`.
The scripts are syntax-checked, not executed. The four
tests took about 85 seconds.

## What this does not say

This is not every script of a mebibyte. It is three texts
on the boundary and two one byte past it.

PowerShell is still not installed here. That half is not
claimed.

A script of 1048576 characters that is not ASCII would be
more than 1048576 bytes, and the code would refuse it for
the byte cap. That case was not generated. The check is
on bytes, and these scripts were built so the two counts
coincide.

## First-hand verification

Re-checked first-hand after it landed; the shared half
of the verdict is in the stage 7 appendix
(`stage7.md`). This stage's harness had not been run
before this pass.

- **The tests were re-run.**
  `runner/tests/test_proof_content_cap.py` as landed:
  4 tests, all passing. The record says the four tests
  took about 85 seconds; on the machine that ran this
  pass the run took 140 seconds — the counts agree and
  the time is the machine's. After the harness
  correction recorded in `stage7.md`, 4 passing again.
  The boundary was re-measured by the tests
  themselves: three scripts of exactly 1048576 UTF-8
  bytes admitted under the default cap, two of
  1048577 bytes refused, and the refusal names
  `max_script_bytes` and the number 1048577, as the
  record claims.
- **The verdict at this rung.** This is the one rung
  where the bound is the code's own, so the claim is
  the boundary itself, and it holds exactly:
  admission at the cap, refusal one byte past it, and
  the decision unchanged across three different texts
  at the cap and two different texts past it.
- **F1. The texts are ASCII by construction.** The
  character count and the byte count coincide because
  the scripts were built so they would. A script of
  1048576 characters that is not ASCII would be
  refused for its byte length, and that case was not
  generated — the record above says so itself. The
  stage therefore demonstrates the byte boundary; the
  character-count claim at this rung rests on the
  ASCII construction together with the model's
  argument that a character is at least one UTF-8
  byte (`goals.md`, stage 10).
- **F2. The texts are the same three padding shapes
  as the lower rungs.** At the cap as at 50,000, no
  construct is combined with another. The
  demonstration is of the boundary, not of the
  grammar at this size.

Verdict for this rung: holds at the boundary, as
stated. The challenge's enumeration, and PowerShell,
remain open — `stage7.md`, findings F1 and F3.
