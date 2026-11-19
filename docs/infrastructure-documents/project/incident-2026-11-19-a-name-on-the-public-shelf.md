# Incident note, 2026-11-19: a working name on the public shelf

This is the written incident note that `SECURITY.md` calls
for, in its section "Spillage: when private material is
published". It says that a spill occurred, when, what class
of material crossed, and what was done. It does not give the
material, and it stays in the tree.

## What crossed

A working name. The owner gave it to a piece of work in
conversation, and Claude's seat wrote it into this
repository: in a file name, in a page's text, and in commit
messages. Another seat then repeated it from the tree, as
any reader of the tree would, and 1 release was cut from a
tree that held it.

The class is a protected term, a code name. No credential,
key, address or secret value crossed. Nothing under
examination was named. No finding, no crash data, and no
client's or other person's information crossed.

## The clock

Times are Pacific, 19-NOV.

| Time | What |
|------|------|
| 4:16 AM | Published: the first commit that carries the name reaches main |
| 4:38 AM | Detected, by the owner, who tells Claude's seat directly |
| 4:44 AM | The name is out of every file on main, and the seats are told in the forum |
| 5:27 AM | The name guard runs on the seat that wrote the name |
| 5:29 AM | Declared on the alert path: an email to the owner, outside the repository |

The name stood in the tree's files for 28 minutes.

## What was done, by the steps of the response

1. **Declare.** The owner found the spill himself. The
   declaration on the alert path went to him by email at
   5:29 AM: the class, where the name still sits, and the
   clock. The response makes detection and declaration 1
   step. Here the cleaning came first, and the email came
   51 minutes after the detection.
2. **Contain.** Done at 4:44 AM: the name is out of every
   file on main, and every release since is built from the
   cleaned tree. Not done: the history between 4:16 and
   4:44 AM still holds it, and so does what was built from
   that history, here and on the mirrors. The purge reaches
   every seat's clone and the mirrors together, and 1 merge
   from an old clone brings all of it back. So it runs with
   the seats held, at the owner's word.
3. **Assume exposure.** The repository is public. The name
   is treated as copied from 4:16 AM on, whatever the purge
   removes.
4. **Eradicate, by class.** A code name has nothing to
   rotate or revoke, and there is nobody outside the project
   to notify. The name is treated as known. It is not
   written in the tree again. Whether it is used at all is
   the owner's.
5. **Record.** This note.
6. **Close the mechanism.** The next section.

## The mechanism, and what changes

How it crossed: a name that lived only in conversation was
used as a title. The response's last step has a phrase for
it, a code name resolved in the wrong place. 3 things were
absent.

- **A shelf decision.** The new name got no shelf decision
  when it appeared. The shelf rule is that a doubtful item
  stays private, and that the doubt goes to the questions
  file.
- **A declaration in code.** The name stood in no registry,
  so no scan could know it.
- **A scan at the boundary.** The name guard
  (`runner/tools/nameguard.py`) was not on the push path of
  the seat that wrote the name. Wiring it is each
  operator's step.

What changed, as engineering, on Claude's seat:

- The name guard now reads every commit message before the
  commit is made, and every push before it leaves: the
  messages, the paths added or renamed to, and the added
  lines. A finding stops the push. A guard that cannot run
  stops it too.
- The registry is kept outside the repository, as the tool
  requires. The names the owner has given pieces of work in
  conversation are declared in it. A new name is declared
  there when it is first heard, before anything is written.
- It was tested both ways before this note was pushed. A
  term in a commit message, in a file name, in an added
  line and on a new branch was refused, 4 of 4, and a clean
  push passed. This note went out through it.

In public writing a piece of work is named by what it is, or
by a code-name reference in the form the shelf page gives
(`docs/infrastructure-documents/project/cs_office.md`),
never by its working name.

## What stays open

- The purge of the history, of what was built from it, and
  of the mirrors' copies: step 2, at the owner's word. This
  note is appended when it has run, or when the owner rules
  that the history stands.
- The request to the host to clear its cached views and to
  collect the unreachable objects is the owner's to send,
  after the purge.
- The guard on the other seats' push paths is each seat's to
  wire, with a registry of its own.

## The owner's ruling

2026-11-19. The owner has ruled that the history stands. The
purge is not run: no history is rewritten, no tag moves, and
no release is withdrawn. No seat holds for a purge, and no
request goes to the host.

What stays open is what does not depend on a purge. The
guard on this seat stays in force, and the guard on the
other seats' push paths is each seat's to wire, with a
registry of its own.
