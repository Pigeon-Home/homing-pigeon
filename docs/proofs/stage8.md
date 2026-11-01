# Stage 8 — content-independence at 50,000 characters

Stage 7 showed the gate's decision at the first rung, 49
characters. The figure for this stage is 50,000 characters,
the rung the ladder names between 5,000 and 500,000. It is
a bound of the claim. It is not a limit in the code. The
code refuses a script at 1048576 UTF-8 bytes and not before.

## The scripts

Three scripts of exactly 50,000 characters, each accepted
by `bash -n`:

- a chain of `true;`, 10,000 times
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
