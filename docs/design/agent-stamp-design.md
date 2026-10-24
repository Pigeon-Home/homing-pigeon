<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->
# Agent-Stamp: tracing work back to the agent chat that did it

Status: draft / idea capture. Not yet enforced anywhere.

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

- `# agent-ident: ...` in `vendor_upstreams.py` and
  `runner/tests/test_vendor_upstreams.py` (both files since retired with
  the provenance bundles; the upstream is declared once, in the
  manifest)
- an `Agent-Chat-Stamp:` commit trailer (one commit)

Proposal: rewrite the two file headers to `Agent-Stamp`. Leave history
alone, and have the search tooling accept the old spellings.

## Idea: runtime stamping (open question)

Static stamps record which agent *edited* something. They say nothing about
which agent *drove the runner*. Possible runtime surfaces:

1. **Protocol header**: an optional `X-Agent-Stamp` field on requests the SI
   sends, which the runner logs verbatim and never acts on.
2. **Structured log field**: `agent_stamp` on every job record, so job
   review (`docs/job-review.md`) can filter by agent.
3. **Snapshot manifest**: release snapshots list the stamps present in the
   tree, so the Oracle can map unfamiliar code back to an agent.

Questions to settle before any of this goes into `PROTOCOL.md`:

- Is the stamp ever trusted for anything? Proposed answer: no, it is
  advisory only. A spoofed stamp misattributes work but must never grant
  access.
- Should the runner reject malformed stamps or just log them as given?
  Proposed answer: log as given, cap the length, and strip control
  characters.

## Idea: lint

A small `.github/tools/stamp_check.py`, run in CI, that:

- lists every stamp in the tree and in recent history
- flags spellings other than `Agent-Stamp`
- flags stamps that are missing from `RESEARCHER_IDENT.md`

It should report only, never fail the build, so it can't add friction.
