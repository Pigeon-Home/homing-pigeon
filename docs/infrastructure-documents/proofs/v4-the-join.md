# The join: a bad signature never reaches the machine

`premac.tla` stops where the signature verifies. The proof at
a bound starts with a script already in hand, and gives that
script to a machine M. The two meet in one sentence. This
page is that sentence. It adds no constraint.

One turn of the motor, `v4-the-motor.md`.

## The sentence

Take a bound N. N is `max_script_bytes`, the bound the owner
locks. The default in the code stays 1,048,576.

- A message that fails C5 never reaches M. Nothing is
  executed.
- A message that passes C5, and whose script is longer than
  N bytes, never reaches M. C2 refuses it after the
  signature and before execution.
- A message that passes C5, and whose script is at most N
  bytes, reaches M once. The script M is given is that
  script, and its UTF-8 length is at most N.

C5 is the signature. C2 is the script cap. Both are already
defined.

## Where the code already does this

In `handle_mail`, in this order:

1. `_verify_and_decrypt` asks for the signature. A bad
   signature returns there.
2. The script's UTF-8 length is compared with
   `max_script_bytes`. Over the cap, the mail is refused
   and the function returns.
3. `execute_job` is later. Only a script that passed both
   steps is handed to it.

So a failure of C5 does not fall through into C2, and a
failure of C2 does not fall through into M.

## What was asked

One corpus job that runs when its signature is good. The
script was replaced, and the signature made again, so the
only things that change are the script and, where the row
says so, one digit of the signature. N is 50, then 500,
then 5,000.

| Arrival | Reaches M |
|---------|-----------|
| N bytes, signature turned | no |
| N + 1 bytes, signature turned | no |
| N + 1 bytes, signature good | no |
| N bytes, signature good | yes, that script |
| 25 copies of é, N = 50 (50 bytes) | yes |
| 26 copies of é, N = 50 (52 bytes) | no |

The turned rows are refused for the signature, not for the
size. The wide character is there so the bound is bytes, as
C2 says, and not characters.

`runner/tests/test_v4_the_join.py` holds this on every suite
run. The execution is a stub: the question is whether the
script is handed over, not what it prints.

## What this is not

This is not the proof that M's result is the shell's result.
That is the induction on `v4-at-a-bound.md`. This is not a
proof of confinement. The atoms that write inside the job's
folder wait until this sentence is the one the two proofs
share.
