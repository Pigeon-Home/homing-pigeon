# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# Feature tiers: what carries which promise

The suite ships more than its centre. This page sorts the
shipped features into three tiers by the promise each one
carries — the supported core, the advanced tier, and the
experimental tier — and shows the evidence each placement
rests on, so a reader can check the sorting instead of
trusting it.

## The supposition

Written before the inventory on this page was taken, so the
record shows what was expected against what was found:

1. Every feature the README names will already be sorted
   by the tree's own signals — a config gate in
   `runner/config.example.json`, an "(optional)" or
   "(opt-in)" marker in PROTOCOL.md, or a shipped /
   design-notes label in the transports document — and no
   placement will need a judgment the tree does not make
   itself.
2. The narrow core — the runner, job verification, one
   transport, key management, the audit log, confinement,
   the separate job user, simple result handling — will
   match what is on by default or ungated, with one split:
   parts of key management are marked opt-in in
   PROTOCOL.md's own section 14 headings, so key
   management will land in two tiers, not one.
3. At least one feature that sounds like research from its
   name will prove to be on by default in the example
   config; the Oracle's learning loop is the candidate
   (`oracle_learning` is expected to read true).
4. The transports document will name at least one
   transport that has no shipped code: a design-notes
   section with no folder in `runner/transport_extensions/`.
