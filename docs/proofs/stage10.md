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

## First-hand verification

Re-checked first-hand after it landed; the shared half
of the verdict is in the stage 7 appendix
(`stage7.md`). This stage's harness had not been run
before this pass.

- **The tests were re-run — and one of them failed as
  landed.** `runner/tests/test_proof_content_cap.py`
  on the machine that ran this pass: the three gate
  tests pass in every run, the boundary re-measured
  each time — three scripts of exactly 1048576 UTF-8
  bytes admitted under the default cap, two of
  1048577 bytes refused, the refusal naming
  `max_script_bytes` and the number 1048577, as the
  record claims. The fourth test, the `bash -n`
  syntax check, failed as landed, twice, in full
  runs of the file: `bash -n` died with SIGSEGV
  (return code -11) on the chain script. Finding F3
  records the cause and the correction that landed
  for it; with that correction in place the file
  passes whole on this machine, 4 tests in about
  136 seconds. (The record says the four tests took
  about 85 seconds on the machine that landed the
  stage; the full runs here took between 131 and
  183 seconds. The counts are the claim; the times
  are the machines'.)
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
- **F3. As landed, the syntax check could not
  complete on this machine.** The chain script is
  one line of about 209,000 commands, and bash's
  parser stacks a frame per command: under this
  machine's default 8 MB stack limit, `bash -n`
  segfaults on it — reproduced outside the test,
  three times in three, return code -11, empty
  stderr. With a 64 MB stack the same script parses,
  return code 0. The script is therefore valid
  syntax, and the failure is a resource limit of the
  checking process — not a syntax verdict, and not
  a gate behaviour: the gate never runs `bash -n`,
  and the file's three gate tests passed in every
  run. Whether the check passed at all depended on
  the stack a neighbouring test happened to leave
  behind, which is how it could pass in one run and
  crash in the next. The correction landed on main
  while this pass was in flight, in the 3.15.36
  release line: the chain at every rung was
  reshaped to one command per line — `true` plus a
  newline is the same length as `true;`, so the
  scripts keep their exact lengths — and in that
  shape the file passes whole on this machine. (In
  this pass the same script was also parsed
  successfully with the checker's stack raised to
  64 MB, which is what identifies the limit, not
  the script, as the failure.) The observation
  stands in its own right: a script at the cap
  written as one long list needs more than the
  default stack for bash even to parse it, which is
  a fact about executing such scripts on machines
  carrying that limit, recorded here because this
  stage is where it was measured.

Verdict for this rung: the gate's boundary holds
exactly, as stated, in every run. The record's
syntax claim holds for the scripts, but as landed
the harness could not demonstrate it on this
machine (F3); with the stated correction it does.
The challenge's enumeration, and PowerShell, remain
open — `stage7.md`, findings F1 and F3.
