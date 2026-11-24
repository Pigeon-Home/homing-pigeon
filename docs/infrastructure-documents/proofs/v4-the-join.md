# The join: a bad signature never reaches the machine

`premac.tla` stops where the signature verifies. The proof at
a bound starts with a script already in hand, and gives that
script to a machine M. The two meet in one sentence. This
page is that sentence. It adds no constraint.

One turn of the motor, `v4-the-motor.md`.

## The sentence

Take a bound N. N is `max_script_bytes`, the bound the owner
locks. The default in the code stays 1,048,576. A bound of 0
is the exception: C2 is then switched off, and the size
clauses below are read with no bound in force.

- A message that fails C5 never reaches M. Nothing is
  executed.
- A message that passes C5, and whose script is longer than
  N bytes, never reaches M. C2 refuses it after the
  signature and before execution, and a refusal at an
  earlier gate ends the handling sooner still.
- A message that passes C5, and whose script is at most N
  bytes, does not reach M on those 2 facts alone. The
  signature and the size are necessary. They are not
  sufficient.
- A message reaches M in a handling when every other
  applicable gate of P1 passes as well, in the order
  `properties.md` records: the box is not stopped and the
  subject does not carry the panic word; the raw mail
  passes C1, or C1 is set to 0; the early dispatch routes
  the mail as this job and does not find its id already
  seen; an envelope decrypts and its inner body verifies
  under the same key, or the body is cleartext and this
  process was started with cleartext allowed; version,
  type and job id agree under C13; the audience decision
  under C10 passes in the mode in force; the body text
  carries no unpaired surrogate; the script is within C2;
  freshness under C12 holds; key policy under C14 allows
  the job, and the pinned key constraints under C11 allow
  it where they are in force; the job does not leave the
  path at the sensor alert branch, and the handling is not
  a dry run; and the claim under C15 is taken, with no
  result already on record to answer from, no cancellation
  recorded before arrival, no refusal from the judge in
  enforce mode, and no refusal of a repaired job when it
  is judged again.
- When all of that holds, the script M is given is that
  script, its UTF-8 length is at most N, and it is handed
  to M in that handling. Once in this handling means the
  script is handed to M at most once in that handling.
  This page makes no unconditional claim of exactly once
  across deliveries: across deliveries the claim rests on
  C15 and on the result record, and `handle_mail` itself
  names one window, in which a result that cannot be
  stashed leaves the job uncommitted and the next poll
  runs it again.
- The 2 propositions stay separate. The handoff, with
  its at most once bound inside one handling, is the
  claim of this page. That an eligible job eventually
  executes is a different proposition, about the poll
  loop running and the box staying up, and no sentence
  here carries it.

C5 is the signature. C2 is the script cap. Both are already
defined.

## Where the code already does this

In `handle_mail`, in this order:

1. The mail is parsed, the panic word is matched, C1 is
   checked, and the dispatcher routes the mail and asks
   the seen set. `v4-before-the-mac.md` is the record of
   this part.
2. `_verify_and_decrypt` asks for the signature. A bad
   signature returns there.
3. Behind the signature, in order: C13, the cleartext
   decision, the audience decision, the refusal of a body
   whose text carries an unpaired surrogate, the script's
   UTF-8 length compared with `max_script_bytes`, the
   freshness window, key policy, and the pinned key
   constraints where they are in force.
4. Under the mail lock, the claim is taken or the handling
   ends. A result already on record is answered from the
   record. A cancellation recorded before arrival, the
   judge in enforce mode, and a repaired job judged again
   can each still refuse the job.
5. `execute_job` is last. Only a script that passed every
   step above is handed to it.

So a failure of C5 does not fall through into C2, and a
failure at any gate does not fall through into M.

## What was asked

One corpus job that runs when its signature is good. The
script was replaced, and the signature made again, so the
things that change are the script and, where the row says
so, one digit of the signature, the job's date, the job's
audience, the key policy the handling is judged under, or
a first delivery that takes the claim. N is 50, then 500,
then 5,000.

| Arrival | Reaches M |
|---------|-----------|
| N bytes, signature turned | no |
| N + 1 bytes, signature turned | no |
| N + 1 bytes, signature good | no |
| N bytes, signature good | yes, that script |
| N bytes, signature good, stale under C12 | no |
| N bytes, signature good, wrong audience with C10 in enforce mode | no |
| N bytes, signature good, kind forbidden by C14 | no |
| N bytes, signature good, job id already claimed under C15 | no |
| 25 copies of é, N = 50 (50 bytes) | yes |
| 26 copies of é, N = 50 (52 bytes) | no |

The turned rows are refused for the signature, not for the
size. The wide character is there so the bound is bytes, as
C2 says, and not characters. The 4 added rows are the
sentence's correction made concrete: each is a correctly
signed message whose script is at the bound, refused by a
gate that is neither C5 nor C2.

`runner/tests/test_v4_the_join.py` holds this on every suite
run. The execution is a stub: the question is whether the
script is handed over, not what it prints.

## What this is not

This is not the proof that M's result is the shell's result.
That is the induction on `v4-at-a-bound.md`. This is not a
proof of confinement. The atoms that write inside the job's
folder wait until this sentence is the one the two proofs
share.
