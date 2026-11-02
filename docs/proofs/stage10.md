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

- a chain of `true`, one command per line, filled out
  with one `:`, because 1048576 is not divisible by the
  length of `true` plus its newline. (The chain was first
  written as one line of `true;` repeated; `bash -n`
  crashes on that single list at the usual stack limit,
  so the one-per-line form is the one the record stands
  on.)
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
