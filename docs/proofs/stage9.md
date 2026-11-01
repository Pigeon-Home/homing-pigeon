# Stage 9 — content-independence at 500,000 characters

Stage 8 showed the gate's decision at 50,000 characters.
The next figure the ladder names is 500,000. It is a bound
of the claim. It is not a limit in the code. The code
refuses a script at 1048576 UTF-8 bytes and not before, so
a script of 500,000 characters is inside the cap, and a
script of one character past this rung is still inside it.

## The scripts

Three scripts of exactly 500,000 characters, each accepted
by `bash -n`:

- a chain of `true;`, 100,000 times
- `echo` of a quoted run of the letter `a`
- `echo` of a quoted run of the words `allowed_interpreters`

The three texts are different. A fourth script is the
chain plus one character, 500,001.

## What the gate does

`handle_mail` admits all four. The text does not change
the decision, and passing the rung by one character does
not either. Under a cap of 100 bytes the three scripts are
refused, and the refusal names `max_script_bytes` for each
of them.

The harness is `runner/tests/test_proof_content_500k.py`.
The scripts are syntax-checked, not executed. The four
tests took about 55 seconds.

## What this does not say

This is not every construct that fits in 500,000
characters. It is three texts and one past the rung.

PowerShell is still not installed here. That half is not
claimed.

The rung at 5,000 was not given its own scripts. It sits
inside what stage 8 already showed. The last rung, the
production cap of 1048576 bytes, was not generated here.
500,000 characters is under that cap. A script of the
cap's own size is a different stage, because the cap is
measured in bytes and a script of exactly 1048576 bytes
is the boundary the code itself enforces.
