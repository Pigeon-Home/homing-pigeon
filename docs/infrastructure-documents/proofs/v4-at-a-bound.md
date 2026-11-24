# Version 4 at a bound: lock a size, then prove at that size

The owner's direction of 2026-11-19, in this seat's words.
Bind the software by a constraint in the specification
itself: a script is at most 50 bytes. At that size the fuzz
data is at its densest, and each single operation is small
enough to prove with mathematics. Then 500 bytes, where a
script starts to be useful. Then 5,000. The real cap in the
code does not change.

This page takes that direction up at the first rung. It says
where the idea already stood in this directory, what the
earlier work left out, what is claimed at the first rung,
and what was supposed before anything was measured.

## Where the idea stood

The proof work began with this bound. `readme.md` has "The
starting bound: scripts under 50 characters". `goals.md`,
stage 6, has the ladder: under 50, then 500, 5,000, 50,000,
500,000, and the cap's own number, 1,048,576.

**What the ladder proved.** P1(B), the gate, on a model that
reads a script as 3 numbers: its character count, its byte
length and its digest. The searched set is the same at every
rung, and the record says the counts at the cap match the
first rung. So the bound did no work in the model. A proof
at 50 was the same proof as at 1,048,576.

**What the challenge asked.** `thinking.md` records it:
every script that the shell's atomic operations can build at
the bound, run against the real gate. Not every string,
every script that can be built.

**What the record did.** `content-rung-49.md`: 22 atoms and
4 joiners, every atom, every pair, and the triples of the
short atoms. 3,682 scripts. The record says itself that the
closure is not enumerated, and that the scripts were checked
for syntax and given to the gate. They were not run.

**How large the closure is.** It was not counted. Counted
now, from the record's own 22 atoms and 4 joiners: there are
74,072,330,493 scripts of at most 49 characters. The 3,682
are 1 in 20 million of them.

| At most this many characters | Scripts the atoms build |
|-----------------------------:|------------------------:|
| 10 | 95 |
| 15 | 1,325 |
| 20 | 18,337 |
| 25 | 252,747 |
| 30 | 3,481,245 |
| 40 | 660,089,747 |
| 49 | 74,072,330,493 |

By the number of atoms in a script: 22 of 1 atom, 1,932 of
2, and 162,404 of 3. With up to 3 atoms: 164,358.

So no machine runs the closure through the gate 1 script at
a time. At 5 thousandths of a second for each, 74 billion
take 11 years. The closure is reached by mathematics, or it
is not reached.

## What the owner's direction changes

1. **The bound is a constraint of the specification**, and
   not only the scope of a proof. The software can hold it
   today. `max_script_bytes` is a configuration value, and
   the startup check asks only that it is a whole number
   that is not negative. A runner set to 50 is inside the
   proven size. The default stays 1,048,576.
2. **The script's meaning is inside the proof.** The gate's
   model is blind to what a script says, by design. That is
   right for the gate, and it is why the bound did no work.
   Each atomic operation has an exact result, and a script
   built from the operations has the result they give it.
   That is the part a small bound makes provable.
3. **The fuzz data stands beside the proof, at the same
   size.**

## The claim at the first rung

For a runner set to a bound of B bytes, and the atom list:

- **B1. The door.** With the rest of the gate passing, a
   script is admitted when it is at most B bytes, and
   refused when it is 1 byte more.
- **B2. The operations.** Every script the atoms build has
   exactly the result that a small machine, M, gives it:
   its exit status and its output.
- **B3. The answer.** The runner returns that result: the
   exit code, and the digest of the output.
- **B4. The evidence.** The fuzz data at that size, counted.

B2 is the new part. M is below.

## Characters and bytes: the conversion at each rung

The rungs of P1 are counted in characters. The caps of C1
and C2 are counted in bytes. The 2 counts are not the same
count, and this section is the conversion between them,
stated once and used at every rung.

Every character of a script takes at least 1 UTF-8 byte
and at most 4. So for any script, its character count is
at most its byte count, and its byte count is at most 4
times its character count. 3 consequences follow.

1. **A byte cap joins the character rung of its own
   number.** A script admitted under a byte cap of N has
   at most N bytes, and so at most N characters. So the
   rung a byte cap can join is the character rung of its
   own number, and not the rung 1 lower. A byte cap of 50
   joins P1(50), and not P1(49). A script of 50 ASCII
   characters is 50 bytes: inside a byte cap of 50, and
   outside P1(49). The production cap of 1,048,576 bytes
   joins P1(1048576), which is the last rung argument of
   `properties.md` stated from the other side.
2. **A character bound alone gives no equal-sized
   byte cap.** A
   character bound of B, for scripts in general, allows
   as many as 4B UTF-8 bytes. 26 copies of é are 26
   characters and 52 UTF-8 bytes: inside the character
   scope of the first rung, and refused at a byte cap of
   50. That refusal is C2 doing its own work. It is not a
   gap in the proof at the rung, whose claim is about the
   scripts the atoms build.
3. **In the closure the 2 counts agree.** Every atom and
   every joiner is ASCII, so in the closure a script's
   character count and its UTF-8 byte count are the same
   number. The 74,072,330,493 scripts of at most 49
   characters are scripts of at most 49 bytes, and they
   pass a byte cap of 50 with 1 byte to spare. The rows
   run at the upper rungs, of 498 to 500 characters and of
   4,998 to 5,000 characters, are likewise rows of that
   many bytes. The conversion the closure needs is this
   identity, and the suite checks it on every atom, every
   joiner, and every row of up to 2 atoms.

A configured cap of 0 means unlimited for C1 and for C2
alike: it is not a bound of 0 bytes, and it joins no
finite rung by itself. A runner with a script cap of 0
admits scripts of any size the rest of the gate allows,
and no P1(B) covers its scripts on the strength of the
cap.

## The machine M

A script here is a row of atoms with a joiner between each 2:
`&&`, `||`, `;` or a pipe. The shell reads the row in 3
layers. Semicolons split it into lists. `&&` and `||` split
a list into pipelines, read from the left. Pipes split a
pipeline into commands.

- **An atom** has a fixed output and a fixed exit status.
  `false` exits 1 and the other 21 exit 0. 3 atoms depend on
  where the job runs: `pwd` prints the working directory,
  and the 2 atoms with `$HOME` print the home.
- **A pipeline** runs every command in it. Its output is the
  output of the last command, because no atom reads what is
  piped to it. Its status is the last command's status.
- **A list** runs its first pipeline. After `&&` the next
  pipeline runs when the status so far is 0. After `||` it
  runs when the status so far is not 0. A pipeline that does
  not run prints nothing and leaves the status as it was.
- **A script** prints its lists' outputs in order, and its
  status is the last list's.

M's state between 2 atoms is 2 facts: the status so far (0
or 1), and whether the pipeline in hand is running. That is
4 states. A step is 1 joiner and 1 atom. So M has at most
4 × 4 × 22 = 352 steps, and every script in the closure is
a walk through them.

**What carries the claim from the scripts that are run to
the 74 billion.** 2 premises, said here so they can be
attacked.

- **P-a. The atoms keep no state.** None sets a variable,
  changes the directory, or leaves a file open. This is a
  fact about 22 short texts, checked by reading them.
- **P-b. The shell reads a longer row as it reads a shorter
  one.** What follows a part of a row depends on that part
  only through its exit status. This is the shell's own
  definition of a list.

With P-a and P-b, a script's result is its walk through M's
steps. So what must be checked by running is that every
step of M is what the real shell does.

## Suppositions, written before the measure

The closure was counted before these were written, and it is
what prompted them. Nothing else was measured first, but for
1 job run end to end to learn the shape of a result.

- **R1. The shell agrees with M.** On every script of up to
  3 atoms (164,358), and on every script of at most 25
  characters (252,747): the same output and the same exit
  status, with 0 disagreements.
- **R2. Those scripts take every step of M.** All 352, or
  every step M can reach.
- **R3. The runner returns M's result.** Every script of up
  to 2 atoms (1,954), through the real gate and the real
  execution: the exit code and the output digest are M's.
  Supposed to hold with confinement set to off. On this
  machine the confinement cannot engage, and under the
  default the runner refuses to run the job at all. That
  refusal is the default doing its work, and it is recorded
  as such.
- **R4. The door at 3 bounds.** At 50, 500 and 5,000 bytes:
  every length from 1 to the bound is admitted and the
  bound plus 1 is refused, and where characters are more
  than 1 byte, the bytes decide.
- **R5. The fuzz data is densest at the first rung.** Of the
  corpus entries that carry a script, more than half carry
  a script of at most 50 bytes, and fewer than 1 in 20 carry
  a script of more than 500.

## The measure

**The shell, on M.** bash 5.2.21. Each script ran in a
subshell of its own, in an empty folder, with HOME set to a
fixed text.

| Scripts run in the real shell | How many | Disagreements with M |
|-------------------------------|---------:|---------------------:|
| Every script of up to 3 atoms | 164,358 | 0 |
| Every script of at most 25 characters | 252,747 | 0 |
| A sample of the longer rows: 4 to 9 atoms, 26 to 49 characters | 200,000 | 0 |
| A sample of the deep rows: 10 to 13 atoms | 100,000 | 0 |
| Every script of 15 atoms or more | 169,832 | 0 |
| In all, each script counted once | 858,319 | 0 |

28,618 scripts are in both of the first 2 sets. The family
of 15 atoms or more is whole: 168,533 scripts of 15 atoms,
1,298 of 16, and the 1 of 17, which is the deepest row the
bound holds.

So: 858,319 scripts, 0 disagreements. Between them the
scripts took all 352 of M's steps. 1,500 of them were run
again, each as a process of its own, and 500 as a staged
file with no line end: the same results.

**The runner, on M.** Every script of up to 2 atoms, 1,954
of them, went through the real gate and the real execution,
with bash as the interpreter and confinement set to off.
0 results differ from M, in exit code or in output digest.
Each result left at the default view: the exit code and the
digest of the output left, and the output stayed home. The
runner spent 5 thousandths of a second on each. The job saw
the runner's own HOME.

Under the default, on this machine, the runner did not run
the job at all. Confinement cannot engage here, and the
result said so: exit code -2, "confinement cannot engage
for this job".

**The door.** At bounds of 50, 500 and 5,000 bytes, every
length from 1 to the bound plus 1 was given to the gate:
51, 501 and 5,001 scripts. 0 wrong decisions. The refusal
names the constraint: "script exceeds max_script_bytes (51 >
50)". Characters of 2, 3 and 4 bytes at each edge, and a
script of as many characters as the bound and 1 byte more:
the bytes decided every one. An empty script passes the
size door, and the execution refuses it for being empty.

**The fuzz data.** The corpus on this branch is 2,634
entries in 30 files. 453 entries carry a script.

| The script is | Corpus entries |
|---------------|---------------:|
| At most 50 bytes | 452 |
| 51 to 500 bytes | 0 |
| 501 to 5,000 bytes | 1 |
| More | 0 |

The middle script is 5 bytes long. The 1 large script is
4,000 bytes. The run log counts the 620,457,512 inputs the
campaign tried, and not their sizes.

**The same atoms on the upper rungs.** At 500 characters
the atoms build a number of scripts that is 114 digits
long, and at 5,000 characters a number 1,139 digits long.
20,000 rows of 498 to 500 characters (32 to 54 atoms) and
2,000 rows of 4,998 to 5,000 characters (381 to 443 atoms)
ran in the real shell: 0 disagreements with M.

## Conclusions against R1 to R5

- **R1 stands, and it was run further than supposed.** 0
  disagreements on the 388,487 scripts R1 named, and 0 on
  469,832 more.
- **R2 stands.** 352 of 352 steps.
- **R3 stands, with confinement off.** 1,954 of 1,954. The
  default refused to run, as supposed.
- **R4 stands.** 0 wrong decisions on 5,553 lengths, and the
  bytes decide.
- **R5 stands, more sharply than supposed.** 452 of the 453
  scripts are at most 50 bytes. The second rung has none.

## What is proven at the first rung, and how

Each line says what kind of support it has.

1. **Counted.** The atoms build 74,072,330,493 scripts of
   at most 49 characters. This is arithmetic.
2. **Run, every case.** Each of M's 352 steps is what the
   real shell does. So is every script of up to 3 atoms,
   every script of at most 25 characters, and every script
   of 15 atoms or more.
3. **Carried by 2 premises.** Every script in the closure
   has the result M gives it. P-a is pinned in the suite as
   a fact about the 22 atoms. P-b is the shell's own
   definition of a list, and nothing that was run disagreed
   with it: 858,319 scripts at the first rung, and 22,000
   more on the 2 rungs above it.
4. **Run, every step.** The real runner returns M's result:
   the suite sends each of the 352 steps, and each of the 22
   atoms, through the real gate and the real execution on
   every suite run.
5. **Run, every length.** The door holds the bound, at 50,
   500 and 5,000 bytes.

What it rests on that it does not prove: the shell reads a
long row as it reads a short one (P-b); the signature and
the cipher, as `readme.md` assumes them; the machine under
the runner; and, for line 4, a run with confinement off.

## What the 3 rungs look like now

| | 50 bytes | 500 bytes | 5,000 bytes |
|---|---|---|---|
| The door | every length run | every length run | every length run |
| The operations, for the 22 atoms | proven as above | the same proof, and a sample of 20,000 | the same proof, and a sample of 2,000 |
| The answer | every step, through the runner | not run | not run |
| Fuzz scripts at this size | 452 | 0 | 1 |

M does not grow with the rung. A longer row is a longer
walk through the same 352 steps. So for these 22 atoms the
rung is not what limits the proof. What limits a rung's use
is the list of atoms: a script of 500 bytes is useful when
it can write a file, hold a value, or loop, and none of the
22 atoms does.

So the ladder that does work is a ladder of atoms as much
as of sizes, and the first rung is the place to add them.

`v4-at-a-limit.md` writes this page's claim with the size
left open, and finds what a row of these atoms meets above
the 3 rungs.

## What comes next, in order

1. **Atoms that write inside the job's own folder.** They
   keep state, so M's state grows from 2 facts to the facts
   and the files. This is where confinement enters the
   proof: an atom that tries to write outside, run in a
   real confinement, with the denial as its result.
2. **A fuzz target for B2.** Rows drawn from the atoms and
   run against M, in the campaign, so the run log holds
   evidence for the operations and not only for the door.
   The corpus has no script between 51 and 500 bytes, so
   the second rung has no evidence to stand beside a proof.
3. **Sizes in the run log.** It counts inputs and not their
   sizes, so the evidence cannot yet be offered at 50, 500
   and 5,000 bytes for the inputs tried, only for the
   entries kept.
4. **The bound in the specification.** Version 4's draft
   states the constraint C2 at its default. A line for the
   bound, with what is proven at it, is the owner's to
   order: the draft is not this seat's.

## What the wider world calls this, and who reads it

Read on 2026-11-19. Names are given so each can be looked
up, and nothing here is leaned on by the proof.

- **The small scope hypothesis** (Daniel Jackson, with the
  Alloy work): most faults show themselves on small inputs,
  so a check of every case inside a small bound finds what a
  sample of large cases misses. "Software assurance by
  bounded exhaustive testing" (Sullivan, Yang, Coppit,
  Khurshid and Jackson, 2004) is the same idea as a method.
  The owner's direction goes 1 step past both: the bound is
  put in the specification, so the software is held to the
  size at which every case was checked.
- **Language-theoretic security** (Sassaman, Patterson,
  Bratus and others): make the input language small enough
  to be recognised in full before anything acts on it. A
  list of atoms is such a language.
- **Residual risk in fuzzing** (Marcel Böhme and others,
  2018 to 2021): after n inputs, the share that were the
  only one of their kind estimates the chance that the next
  input shows something new. It is an estimate of discovery
  and not a proof of absence. It is the measure that would
  let the fuzz data stand beside a proof as a number.
- **Lightweight formal methods in industry**: reference
  models held to running code by tests and model checking,
  re-run as the code changes. This directory's method is of
  that family.
- **At the IETF.** Its formal analysis of protocols asks an
  author for a threat model, security goals with their
  conditions, and a protocol diagram, and then works in a
  symbolic or a computational model. The Usable Formal
  Methods Research Group of the IRTF is where methods like
  this one are discussed. A working group on agent
  communication protocols was chartered on 2026-10-08. An
  Independent Submission, the stream versions 1 and 2 are
  in, is judged by expert reviews and carries no IETF
  consensus.

What this suggests for the draft, and decides nothing: a
reader at the IETF will look first for the attacker the
claims are made against, and version 4's draft states its
claims about 1 implementation without naming that attacker.

## What this page does not claim

- That 22 atoms are the shell. They are the record's list:
  commands that do nothing, commands that print, 1 that
  fails, quoting, 3 expansions, arithmetic, a group, a
  redirection to nowhere and a conditional. No atom writes
  a file, changes state, or reaches a network. A wider list
  is a later rung, and an atom that keeps state breaks
  premise P-a and needs a larger M.
- That the result is safe. B2 says a script does what its
  operations say. What an operation is allowed to touch is
  confinement, which is its own property.
- That a size makes a script harmless. 9 bytes can ask to
  remove a home. What bounds a script's effects is the list
  of operations it may be built from, and the confinement
  under it. The size bounds the handling and the count.
