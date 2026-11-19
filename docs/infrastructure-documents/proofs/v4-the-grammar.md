# The grammar of the rung

The induction on `v4-at-a-bound.md` says every script the
atoms can build has the result the machine M gives it. That
is a proof for one grammar. It is not a proof for the shell,
and it is not a proof for every string the size door admits.
This page is that grammar. It adds no constraint.

## What a script of the rung is

A script of the rung is an atom, or a script of the rung, then
one joiner, then an atom. Nothing else.

The atoms are the 22 texts in `BASH_ATOMS`, exactly, and the
joiners are the 4 texts in `BASH_JOINERS`, exactly: ` && `,
` || `, `; ` and ` | `.

One atom begins another. `echo a` is the start of
`echo a > /dev/null`, and `if true; then echo a; fi` has a
joiner's text, `; `, inside it. A cut still exists, and there
is only one. The atom taken is the only one that leaves either
nothing or a joiner after it.

## What an atom is forbidden to do

Read off the 22 texts. None of them:

- assigns a variable, or expands one it has set;
- changes the directory;
- reads its input, so a pipe's left side is discarded;
- redirects, except the one atom `echo a > /dev/null`;
- loops, or calls `eval`, `source`, `exec`, `set` or `trap`.

Three atoms read the place the job runs, and do not change
it: `pwd`, `echo $HOME` and `echo ${HOME}`. `false` is the
one atom whose status is not 0.

This is premise P-a of the bound page, stated as the
grammar. Because an atom cannot change what the next atom
sees, the next step depends on two facts only: the status so
far, and whether the pipeline in hand is running. That is
premise P-b, and it is a fact about this grammar. It is not
a fact about bash.

## What was asked

- Each of the 22 atoms is one script, and it cuts as itself.
- No atom is a second way to start another atom, or to start
  another atom followed by a joiner. That finite check is
  why every longer script of the rung has one cut, at every
  length, not only under 50 characters.
- Every script of 1 atom and of 2 atoms cuts back to the
  atoms and the joiners it was built from.
- These are not scripts of the rung: `x=1`, `cd /`,
  `echo a > /tmp/x`, `while true; do :; done`, `read x`,
  and `true &&`.

`runner/tests/test_v4_the_grammar.py` holds this on every
suite run.

## What this is not

The size door, C2, admits any script of at most N bytes. The
induction does not follow those scripts out of this grammar.
A script that writes a file, or loops, or sets a variable, is
outside the proof, whatever its length. Those atoms are the
ones that bring confinement in, and they are not added here.
The default cap stays 1,048,576.
