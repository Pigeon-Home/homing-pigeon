# The completion theorem, hypothetical: B2 and B3 at one frozen grammar and environment

This page is mine, written in my own voice from the proof
shelf's own record, and it is the page checklist item 22 of
23 November 2026 asked for. It states the completion theorem
for B2 and B3 as a hypothetical: a conditional statement
whose every conclusion names the premises it rests on, with
a ledger that gives each unresolved premise one row and one
label. It proves nothing new. It gathers what the shelf
already holds, names what the shelf still assumes or has not
done, and says exactly what would follow if every row of the
ledger were discharged, and what would still not follow.

Scope, stated before anything else. The theorem is about
one frozen grammar and one frozen environment, defined in
the next section, and about two claims only: B2, the
operations, and B3, the answer, as `v4-at-a-bound.md` states
them. It is not about the shell in general, not about every
string the size door admits, and not about any script
outside the frozen grammar. Nothing on this page states or
implies a proved result about P versus NP, in either
direction. The P versus NP material on this shelf stands on
its own pages with its own scope, and no premise is carried
between that discussion and this theorem in either
direction.

Assumptions, stated before the theorem. The theorem rests
on the ledger in full: 19 premises, each labelled proved,
checked, tested, assumed, or open. A conclusion drawn on
this page names the ledger rows it uses, every time it is
drawn. A reader who does not accept a named row does not
get the conclusion that names it, and the page offers no
conclusion with its premises left unnamed.

The finite parts are held by
`runner/tests/test_v4_the_completion.py`: the ledger's rows
and labels, the frozen counts the theorem uses, the entry
for this page in this folder's `readme.md`, and the wording
guards that keep this page conditional.

## The frozen grammar and the frozen environment

The grammar G is the grammar of `v4-the-grammar.md`, frozen
as it stands: the 22 atoms in `BASH_ATOMS`, exactly, and the
4 joiners, exactly, which are ` && `, ` || `, `; ` and
` | `. A program of G is one atom, or a program of G, one
joiner, and one atom, and nothing else. The pilot bound is
the first rung: a program of at most 49 characters. Every
atom and every joiner is ASCII, so a program's character
count and its UTF-8 byte count are the same number, and the
pilot programs pass a byte cap of 50 with one byte to spare.

The environment E is frozen as the first rung froze it:
bash 5.2.21 as the shell, each program run in a subshell of
its own, in an empty folder, with `HOME` set to a fixed
text. For the runs through the runner, the interpreter is
bash, confinement is set to off, and the job sees the
runner's own `HOME`. The observation O is the exit status
and the output: the output itself for the shell runs, and
for the runner runs the exit code and the digest of the
output left at the default view, as the bound page records.
Any other channel, a file written, a trace, a timing, is
outside O, and no conclusion on this page speaks about it.

The machine M is the machine of `v4-at-a-bound.md`: its
state between two atoms is two facts, the status so far and
whether the pipeline in hand is running, and it has at most
4 times 4 times 22, which is 352, steps.

## Supposition, written before the test ran

The test for this page was expected to find all of the
following, and the section near the end records what it
found.

- The ledger below holds 19 rows, and every row carries
  exactly one of the five labels: 1 proved, 4 checked,
  7 tested, 3 assumed, and 4 open.
- The frozen counts agree with the shelf: 22 atoms,
  4 joiners, and 352 steps of M.
- No sentence on this page states a conclusion without
  naming at least one ledger row in the same section, and
  the page carries its P versus NP disclaimer in words.

## The premise ledger

The labels mean this, and only this. **Proved** means a
proof or a piece of arithmetic stands on the shelf and can
be rederived from what is written there. **Checked** means
a finite check over the whole of a named finite object
stands in the suite and passes. **Tested** means the real
shell or the real runner was run on the cases the row
names, and agreed; it speaks for those cases and for the
build and environment they ran under. **Assumed** means the
theorem takes the row as a premise and the shelf offers no
proof, check, or run that discharges it. **Open** means the
work the row names has not been done, or the question it
names has not been settled, and the row is a debt the page
carries openly.

| Row | Premise | Label | What stands behind the label |
|-----|---------|-------|------------------------------|
| L1 | Parsing a pilot program's bytes yields its intended atom and joiner tree, with the intended precedence, and the cut is unique. | checked | The grammar test cuts every program of one and of two atoms back to its atoms and joiners, and the uniqueness is a finite check over the 22 atom texts and the 4 joiner texts. |
| L2 | Each atom has the result M gives it, the place reading atoms apart: `false` exits 1, the other 21 exit 0, and `pwd` and the two `HOME` atoms print what E gives them. | tested | Every atom was run in the real shell under E, and the place page ran all 22 atoms with confinement on and off. |
| L3 | The atoms keep no state: none sets a variable, changes the directory, or leaves a file open. This is premise P-a of the bound page. | checked | A fact about 22 short texts, read off the texts and pinned in the suite as a fact about the atoms. |
| L4 | No atom reads what is piped to it, so a pipeline's output is its last command's output, and output deltas compose across a program in order. | checked | Read off the same 22 texts, in the grammar page's list of what an atom is forbidden to do. |
| L5 | The shell reads a longer row as it reads a shorter one: what follows a part of a row depends on that part only through its exit status. This is premise P-b of the bound page. | assumed | The shell's own definition of a list, taken as a premise. The runs behind L6 disagreed with it nowhere, and a run is not a proof of it. |
| L6 | Every step of M is what the real shell does. | tested | All 352 steps were taken by the 858,319 pilot scripts run in the real shell, with 0 disagreements, and rows on the two rungs above the pilot agreed as well. |
| L7 | The concrete and abstract initial states are related as M needs: an empty folder, the fixed `HOME` of E, and the working folder the place atoms read. | tested | The shell runs of the bound page ran in an empty folder with `HOME` set to a fixed text, and the place page measured what the place atoms print, on and off. |
| L8 | The closing step of an execution preserves the status M predicts, for a program that completes normally. | tested | The runner runs behind L14 returned M's exit code on every case they cover. |
| L9 | The closing step preserves the output under the observation O, which records a digest of the output for a runner run. | tested | The same runner runs returned M's output digest on every case they cover. |
| L10 | The closing step preserves the output byte for byte, as a literal equality claim about the bytes themselves. | open | No argument about the literal bytes stands on the shelf. The pilot makes no such claim: O records a digest, and L9 is the strongest output row the pilot uses. |
| L11 | At the pilot bound, a program of G completes normally: no bar the limit page numbers is reached at 49 characters, so completion needs no separate resource condition at this bound. | checked | The limit page numbers each bar as a number, the lowest first bar stands at 13,332 characters or at the output cap's number, and 49 is under both, by arithmetic on the stated numbers. |
| L12 | A timeout and a clipping are outcomes of their own, distinct from normal completion, with their own conditions. | open | The limit page states them as separate outcomes above the pilot bound. No row of the pilot discharges them, and the pilot theorem excludes them by L11 rather than settling them. |
| L13 | The runner hands an admitted pilot program to this execution path unchanged, with no text added, removed, or rewritten on the way. | tested | Programs of up to two atoms, and each of the 352 steps and each of the 22 atoms, went through the real gate and the real execution on every suite run. |
| L14 | The runner's result map is the one O names: the recorded runner observation is the exit code and the digest of the output. | tested | The same runs read the result at the default view, and the exit code and the digest were M's on every case. |
| L15 | If the runner applies a repair to a result, the repair preserves the result M predicts. | open | No repair stands in the frozen mode of the pilot, and no preservation argument stands on the shelf. The pilot theorem is scoped to the mode with no repair, and says nothing about any other mode. |
| L16 | The cryptography the gate rests on behaves as `readme.md` assumes: the signature is unforgeable without the shared secret, and the cipher keeps a sealed body confidential and unmodified under a key the attacker does not hold. | assumed | Stated once in `readme.md` and carried through every property on this shelf. Proving anything about it belongs to cryptography and to other people's checked work. |
| L17 | The frozen environment holds as frozen: the bash 5.2.21 build and its options, and the operating system, the Python runtime, and the hardware doing what their own specifications say. | assumed | The bars and the step counts are this build's, as the limit page says of its own numbers. Another build is another environment, and this theorem does not travel to it on its own. |
| L18 | A complete corpus of pilot programs, with a trusted oracle giving the expected result of each, exists and can be consulted. | open | No such corpus and no such oracle stands on the shelf. The pilot uses no row of this kind: its evidence is the finite runs and checks the other rows name. |
| L19 | The counts the theorem uses are right: at most 352 steps of M, and 74,072,330,493 programs of G at the pilot bound. | proved | Arithmetic, stated on the bound page: 4 states, 4 joiners, and 22 atoms give the step count, and the closure count is counted there rung by rung. |

## The theorem, stated conditionally

Fix G, the UTF-8 encoding, the pilot bound, E, and O, as
the frozen section above fixes them. Then:

**B2, conditional.** Under premises L1, L2, L3, L4, L5, L6,
L7, and L19, a pilot program that completes normally under
E has the result M predicts under E: its exit status and
its output are M's. Under premise L11, every pilot program
is in the completing case at this bound, so under premises
L1 to L7, L11, and L19 together, the qualification about
completion does no work at the pilot bound, and it would do
work at any larger bound, where L12 is still open.

**B3, conditional.** Under premises L1 to L9, L11, L13,
L14, L16, L17, and L19, where the runner hands a pilot
program to this execution path, the recorded runner
observation under O is the result map of L14 applied to
the result M predicts: the exit code, and the digest of
the output. Under premise L10, which is open, nothing on
this page upgrades that digest statement to a statement
about the literal bytes, and under premise L15, which is
open, nothing on this page extends B3 to a mode in which
the runner repairs a result.

**The hypothetical completion.** If every row of the
ledger stood at proved, checked, or tested, with no row
assumed and no row open, then under that completed ledger
the two statements above would stand as theorems of the
frozen grammar and the frozen environment, with no premise
left to name because none would be left undischarged. That
sentence is the hypothetical this page exists to state. It
is not the state of the shelf today: 3 rows stand assumed
and 4 stand open, and until a row moves, every conclusion
on this page keeps naming it.

## The four strengths, and which of them the pilot uses

The ledger in `properties.md` sets a taxonomy for assuming
future data, at four strengths, and this page respects it
in full. Strength 1 is finite inputs: any finite test
inputs we want, which design experiments and falsify
proposed rules, and cover no unbounded lengths. Strength 2
is a scoped corpus with a trusted oracle: an ideal finite
corpus covering every input of a fixed, named domain, with
a trusted oracle giving the expected answers, where
exhaustive agreement establishes the scoped finite claim
and nothing outside the domain. Strength 3 is a full
oracle, answering every formula, where a solver can be
fast relative to that oracle and no ordinary conclusion
follows. Strength 4 is a uniform algorithm on arbitrarily
large inputs, which is equivalent to the result itself in
the discussion that taxonomy came from, and must never be
smuggled in as merely having a great deal of data.

The pilot stands at strength 1, and at no higher strength.
Its tested rows rest on finite inputs that were run, its
checked rows rest on finite checks over named finite
objects, and its one lift past the cases run, from the
steps of M to every program of G at the bound, is carried
by premises L3, L4, and L5, which are labelled checked,
checked, and assumed, and not by any corpus or oracle.
Premise L18 names the strength 2 object the pilot does not
have and does not use. If a future pass discharged a claim
at strength 2, with a corpus and an oracle, its conclusion
would be the scoped finite claim for that corpus's domain
and no more, and it would enter this ledger as its own row
at its own strength. No premise proved, checked, tested,
assumed, or open at one strength is exchanged for a premise
at another strength anywhere on this page, and the size,
the generation time, and the lookup time of any corpus or
table a future pass might use would be charged to that
pass's claim, as the honesty rules of `properties.md`
require.

## What was found

The test written for this page ran against the page as it
stands, and the supposition above held on every point it
named.

- The ledger holds 19 rows, with 1 proved, 4 checked,
  7 tested, 3 assumed, and 4 open, counted off the table
  itself.
- The frozen counts agree with the shelf: 22 atoms,
  4 joiners, and 352 steps.
- The page carries its conditional wording and its
  disclaimer, and no conclusion section stands without a
  ledger row named in it.

## What this page does not claim

- That B2 or B3 stands proved today. Three premises stand
  assumed and four stand open, and the theorem above is
  conditional on the ledger in full, row by row.
- That the theorem covers the shell, or any grammar wider
  than G, or any environment other than E, or any
  observation other than O. A wider grammar, a second
  build, or a literal byte observation is new work, with
  new rows.
- That a timeout, a clipping, or a repaired result is
  covered. Rows L12 and L15 are open, and the pilot
  excludes those outcomes by its bound and its mode
  rather than settling them.
- Anything at all about P versus NP. This page borrows
  only the taxonomy of strengths from that discussion,
  and it lends that discussion nothing.
