<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->
# Agent-Stamp: tracing work back to the agent chat that did it

Status: the record is enforced by `runner/tests/test_agent_stamps.py`
(every stamp in the tree is on `docs/archive/RESEARCHER_IDENT.md`,
every recycled stamp names an active carrier); the spelling lint is
not built. The rest is the design as captured.

## Problem

Several agent chats work on this repo. Each one has its own stamp, a
UUID-shaped tag listed in `docs/archive/RESEARCHER_IDENT.md`. The stamp
works like a software watermark. It is not a credential and grants nothing.
Its only job is to make "which agent did this?" answerable with `grep`.

## Rule: plain text, never hidden

A stamp only helps tracing if a person or a script can find it. So it is
always visible text: no zero-width characters, no steganography, no
encoding tricks.

## Where the stamp goes (static artifacts)

| Surface              | Form                                                    |
|----------------------|---------------------------------------------------------|
| Commit message       | trailer `Agent-Stamp: <uuid>`, next to Co-Authored-By   |
| PR description       | footer line `Agent-Stamp: <uuid>`                       |
| New source file      | first-line comment `# Agent-Stamp: <uuid>`              |
| New Markdown file    | `<!-- Agent-Stamp: <uuid> -->` at the top               |
| Chat deliverables    | short sign-off with the full stamp                      |

To find everything one agent touched:

```sh
git log --grep='Agent-Stamp: 40000e00' --format='%h %s'
git grep -n 'Agent-Stamp: 40000e00'
```

## Drift observed in the tree (to normalize)

The canonical spelling is `Agent-Stamp`. Variants seen so far:

- `# agent-ident: ...` in two files since retired with the provenance
  bundles (the upstream is declared once, in the manifest)
- an `Agent-Chat-Stamp:` trailer and file header, the spelling the
  questions desk (`50000c8e`) uses on its own commits and files; the
  record check below reads both spellings

Proposal: rewrite the two file headers to `Agent-Stamp`. Leave history
alone, and have the search tooling accept the old spellings.

## Idea: runtime stamping (open question)

Static stamps record which agent *edited* something. They say nothing about
which agent *drove the runner*. Possible runtime surfaces:

1. **Protocol header**: an optional `X-Agent-Stamp` field on requests the SI
   sends, which the runner logs verbatim and never acts on.
2. **Structured log field**: `agent_stamp` on every job record, so job
   review (`docs/oracle/job-review.md`) can filter by agent.
3. **Snapshot manifest**: release snapshots list the stamps present in the
   tree, so the Oracle can map unfamiliar code back to an agent.

Questions to settle before any of this goes into `PROTOCOL.md`:

- Is the stamp ever trusted for anything? Proposed answer: no, it is
  advisory only. A spoofed stamp misattributes work but must never grant
  access.
- Should the runner reject malformed stamps or just log them as given?
  Proposed answer: log as given, cap the length, and strip control
  characters.

## The lint, as built

`runner/tests/test_agent_stamps.py` (2026-10-26) lists every stamp
written after a stamp label anywhere in the tree and fails when one
is missing from `RESEARCHER_IDENT.md`, when a listed stamp has no
status row, or when a recycled stamp names no active carrier. It
runs with the suite, so a stamp the record does not know fails the
build; the original idea of a report-only `stamp_check.py` was
dropped for that, since a stamp outside the record is the one thing
the record exists to catch. It does not flag spellings: both
`Agent-Stamp` and `Agent-Chat-Stamp` are read, and history is not
scanned.

## Recycled stamps (2026-10-26)

A stamp outlives its chat. When a chat stops working on the project
its stamp is **recycled**: it stays in history and in the headers of
the files it wrote, new work never carries it, and its roles pass to
an active stamp. Researchers one to three (`10000c2a`, `200003d4`,
`30000f1a`) were the first; the status table in
`docs/archive/RESEARCHER_IDENT.md` names who carries each role, and
`runner/tests/test_agent_stamps.py` checks that every stamp in the
tree is on it and every recycled role has an active carrier.

