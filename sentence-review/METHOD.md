# Sentence review — method

This folder holds a sentence-by-sentence review of the project's
documentation, carried out on the intermediate-modown branch. The
branch's own statement of purpose is in BRANCH-PURPOSE.md at the
repository root; this note is the working method for the pass.

## The review

Every single sentence in every in-scope document gets scrutiny for
sense and flow:

- Does the sentence before lead into it?
- Does it lead into the sentence after?
- Does the idea it conveys connect to its neighbours?

This is a coherence pass over the prose itself. It is not a code-flow
pass and not a code-truth pass: whether a sentence is accurate about
the code is a different review, and no verdict here speaks to it.

Each sentence is also categorized as one of two kinds:

- **pre-release** — a statement about the project before its first
  release. The first release is 4.0. Statements of how things stand —
  current behavior, shipped features, history, measurements, warnings
  about the present state — are pre-release, whenever they are read.
- **post-release** — a statement about the project after its first
  release: future work, plans, sketches of things to build, promises
  or contingencies that belong to the time after 4.0.

## Scope

In scope: every markdown document under docs/, plus the root
README.md, PROTOCOL.md and AGENTS.md.

Out of scope: docs/archive/ — excluded, except when archive material
is needed as research to judge whether another statement holds.

The documents themselves are not edited by this pass. Findings only.

## The record

INDEX.md lists every in-scope document with a status: not started,
in progress, or done. One findings file per completed document lives
in findings/, named for its document with the path's slashes turned
into double underscores (docs/FUTURE.md -> findings/docs__FUTURE.md).

A findings file records, for every sentence: its number in the
document, its opening words, its category, and a coherence verdict —
"flows", or "flagged" with a one-line note saying what breaks (no
lead-in from the previous sentence, no hand-off to the next, or the
idea disconnected).

Sentence units are the prose sentences of the document, counted in
reading order. Headings, code blocks and link targets are structure,
not sentences. Where the document's own formatting merges several
list items into one prose run, the run is one unit and the findings
say so.

## Working order

1. The root front door: README.md, PROTOCOL.md, AGENTS.md.
2. The top of docs/: FUTURE.md and its neighbours.
3. The steady core documents and the steady guide.
4. The infrastructure documents.
5. The steady drawers, by kind.
6. The IETF folder.

## Phase 1 state

Phase 1 set this project up and completed the first documents:
README.md, docs/FUTURE.md and docs/PROTOCOL.md. Every other document
in the index stands at not started, and the pass continues from
there in later sittings.
