# Stage 8 — content-independence at 50,000 characters

Stage 7 showed the gate's decision at the first rung, 49
characters. The figure for this stage is 50,000 characters,
the rung the ladder names between 5,000 and 500,000. It is
a bound of the claim. It is not a limit in the code. The
code refuses a script at 1048576 UTF-8 bytes and not before.

## The scripts

Three scripts of exactly 50,000 characters, each accepted
by `bash -n`:

- a chain of `true`, one command per line, 10,000 times
- `echo` of a quoted run of the letter `a`
- `echo` of a quoted run of the words `allowed_interpreters`

The three texts are different. A fourth script is the
chain plus one character, 50,001, which is past the rung
and still inside the byte cap.

## What the gate does

`handle_mail` admits all four. The text does not change
the decision, and passing the rung by one character does
not either. Under a cap of 100 bytes the three scripts of
50,000 characters are refused, and the refusal names
`max_script_bytes` for each of them.

The harness is `runner/tests/test_proof_content_50k.py`.
The scripts are syntax-checked, not executed.

## What this does not say

This is not the closure of every bash construct that fits
in 50,000 characters. At this size that closure is not a
list. It is three texts and one past the rung, chosen so
the texts differ and one of them names a policy field.

PowerShell is still not installed here. That half is not
claimed.

The rungs at 5,000 and at 500,000 were not given their own
generated scripts. 5,000 is inside what 50,000 already
shows, in the sense that the gate has no content check
that appears between them. 500,000 remains a larger rung.
The code's own cap, 1048576 bytes, remains the last one.

## First-hand verification

Re-checked first-hand after it landed. The shared half
of the verdict — the walk of the gate code, the
configuration the decisions were measured under (no key
policies, the opinion off, `judge` unset), and the
harness correction — is recorded in the stage 7
appendix (`stage7.md`). What is specific to this rung:

- **The tests were re-run.**
  `runner/tests/test_proof_content_50k.py` as landed:
  4 tests, all passing (about 9 seconds). After the
  harness correction, 4 passing again. The lengths the
  record claims were re-measured by the tests
  themselves: the three scripts are exactly 50,000
  characters and 50,000 UTF-8 bytes, the fourth is
  exactly 50,001, and the three texts differ.
- **The verdict at this rung.** The gate admitted all
  four texts, and refused the three rung scripts under
  a cap of 100 bytes, the refusal naming
  `max_script_bytes`. That holds as stated — for these
  texts.
- **F1. The three texts are one atom repeated.** A
  chain of the one command `true`, a quoted run of one letter, a
  quoted run of one policy-field word. No construct of
  the grammar is combined with another at this bound,
  so the rung shows the size decision ignoring the
  text of three long padding shapes; it does not
  sample the grammar at 50,000 characters. The
  record's own closing section already declines the
  closure; this finding adds that it does not sample
  constructs either.
- **F2. The 5,000 rung has no generated scripts.** The
  series steps from 49 to 50,000. The reason the
  record gives — that no content check appears
  between them — is the argument from reading the
  code, which is what this series exists to replace
  with demonstration. The 5,000 bound is covered by
  the model (`stage7-5000.md`) but by no content
  test.

Verdict for this rung: holds for the texts generated.
The challenge's enumeration remains open, and so does
PowerShell — `stage7.md`, findings F1 and F3.
