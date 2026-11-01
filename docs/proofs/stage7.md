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
