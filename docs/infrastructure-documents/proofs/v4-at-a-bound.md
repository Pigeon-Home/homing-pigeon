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
