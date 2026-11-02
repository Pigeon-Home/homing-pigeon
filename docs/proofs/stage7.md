# Stage 7 — content-independence, at the first rung

`thinking.md` leaves one challenge open. The gate model
treats a script as a length and a digest. The argument that
the gate never reads the script's text was a reading of the
check order. This stage presents the text to the real gate.

## The inventory

Twenty-two scripts, each of at most 49 characters, each a
construct a default bash has: a simple command, a pipeline,
`&&` and `||` and `;`, a conditional, a loop, a function,
grouping, brace expansion, a parameter, a command
substitution, arithmetic, a redirection, three quoting
forms, and one script whose text is the name of a policy
field. The list is `SCRIPTS` in
`runner/tests/test_proof_content.py`.

`bash -n` accepts every one of them. That is a syntax
check. The scripts are not run.

## What the gate does with them

Each script is a signed, encrypted execution job, fresh,
with no key policy, and the opinion feature off. `handle_mail`
reaches `execute_job` for every one of them. The decision
does not change with the text. The script that names
`allowed_interpreters` is admitted on the same terms as
`echo ok`.

The cap is the part that does change the decision, and it
changes it by length. A cap of 0 means unlimited, so the
tightest refusing cap is 1 byte. `:` and `Z` are one byte,
so both are admitted at that cap. Every longer construct is
refused, and the refusal names `max_script_bytes`. The
one-byte builtin and the one-byte name that is not a
builtin are treated the same. The longer scripts are
treated the same as each other.

## What this does not say

This is not every string of 49 characters. The space of
strings is not the space of scripts, and the challenge
asked for the grammar. The grammar here is a sample of
each construct, not the closure of every way those
constructs can nest inside 49 characters. A nest that
fits and was not listed is not a checked case.

PowerShell is not installed on the machine that ran this.
The PowerShell half of the challenge is not claimed.

Nothing above the first rung was generated. The same
argument the ladder already uses applies: the gate does
not grow a content check as the script gets longer. This
stage does not re-prove that at 500 or at the cap. It
shows the prediction at the rung where the grammar is
small enough to list.

No runner behaviour changed.

## First-hand verification

This record was re-checked first-hand after it landed,
the same standard the earlier stages were held to: every
test in the series re-run, the inventory re-counted, and
the gate's code re-walked while the claim was in hand.
Nothing above was taken on its author's word.

- **The tests were re-run.** All four files of the
  series were run on the tree as landed: this stage's
  harness (`runner/tests/test_proof_content.py`), 4
  tests, all passing; the 50,000 file, 4 passing; the
  500,000 file, 4 passing; and the production-cap file,
  4 passing — that file had not been run before this
  pass, and it passes as landed. The series is 16 tests,
  all green, counted per file rather than in total. The
  full proof family was then run on the final tree: 269
  tests, all passing (the constraints file, the
  conformance family, the skip registry, and this
  series; the two slow files counted from their runs on
  the same test code).
- **The inventory was re-counted.** `SCRIPTS` holds 22
  scripts; the longest is 28 characters; every one is
  inside the 49 bound, as the record says. `bash -n`
  accepts each one — the test performs that check, and
  it passed.
- **The gate code was re-walked.** In `handle_mail`
  (`runner/ops/mail.py`), on the path these tests
  exercise, no step before `execute_job` branches on
  the script's text beyond three things, each of them
  in the model's own statement of the order
  (`properties.md`): whether the job's text has a UTF-8
  encoding at all (step 6, encodability — the
  precondition for a byte length to exist, not a branch
  inside the abstraction); the script's UTF-8 byte
  length (step 7); and, when a key's policy pins
  scripts, the script's SHA-384 digest (step 10). Two
  further text reads exist in the code and are already
  on record: the judge's denylist, which can refuse
  only under `judge: enforce` (stage 3, gap G2), and
  the opinion's script-shape read, which can only
  substitute an interpreter, with the result re-judged
  before it runs (stage 3, F2). Both are inert in the
  configuration these tests run: no key policies, the
  opinion mode `off`, and `judge` unset. With the
  opinion off, `plan_before` returns no repair, so the
  job that reaches `execute_job` is the job as
  received.

Findings:

- **F1. The challenge's enumeration was not performed
  — here or at any rung.** `thinking.md` asks for every
  script the grammar can construct at the bound. What
  this stage ran is one sample per construct, and the
  record above says so in its own words. The nesting
  closure — the constructs combined every way they fit
  in 49 characters — was not generated. The verdict
  for this rung is therefore narrower than the
  challenge: the gate's prediction held on a construct
  sample, and the challenge itself stays open in its
  stated form.
- **F2. The sample omits constructs the challenge's
  own inventory names.** Checked against the grammar
  list in `thinking.md`, the 22 scripts contain no
  pathname expansion (a glob), no process
  substitution, no `case`, no `while` or `until`, no
  `[[ ]]`, and no here-document. The record's framing
  is one sample of each construct; on the challenge's
  list, the sample is partial even at that strength.
- **F3. PowerShell is unclaimed, and remains so.** The
  challenge names PowerShell alongside bash. It is not
  installed on the machine that ran this (checked
  again in this pass), and no rung of the series
  claims it.
- **F4. The harness's stub, as landed, recorded the
  test's own script variable rather than the job
  `execute_job` was actually called with.** The tests
  therefore proved that `execute_job` was reached;
  that the job executed was the job as received
  followed from the opinion-off configuration, not
  from the stub's record. In this pass the stub in
  each of the series' four files was changed,
  mechanically, to record the script of the job
  argument it receives; no assertion changed. All 16
  tests were re-run after the change and pass, so the
  identity is now recorded by the harness itself.

Two numbering defects in the series' own records
were found in this pass. The renumbering note in
`goals.md`, as this pass first read it, said the four
content-independence sections landed numbered as
stages 7 to 9; the git record shows four sections,
numbered 7, 8, 9, and 10, and the note in the tree as
this pass lands reads 7 to 10. And the paragraphs
this series appended to `thinking.md` used those
same numbers for the series while the plan's stage
numbers belong to the ladder — one set of numbers
naming two different sequences. In the tree as this
pass lands, `thinking.md` cites the series by its
name and the numbers name the ladder alone. The
statements in `goals.md`, `thinking.md`, and the
summary document that a first-hand verification pass
over this series was still owed are updated by the
same landing: the pass they named is this one.

Verdict for this rung: the gate's prediction holds on
the sample as landed and re-run. The enumeration the
challenge asks for does not hold — it was not
attempted — and the challenge stays open.
