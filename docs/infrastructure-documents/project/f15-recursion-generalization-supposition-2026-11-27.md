# F15 generalized: supposition

Written 2026-11-27, before the measurements below were run.
Finding F15 closed 3 shapes of a mail whose deep nesting made
the gate raise and leave the message unmarked: colons in the
sender, comments nested in the sender, and parts nested
inside parts. The recorded next step for F15's kind stands
in v4-the-ladder.md, in Grok's words: the same sentence for
every reader in front of the signature; it returns an answer
on every text, and the message is marked. This record states
what the gate's readers look like now, what is supposed
about the one reader left over, and what change the
measurements support.

## The census

Every place the gate or its dispatcher reads a mail's shape
was read for this record.

- The gate's first parse is decided: a RecursionError there
  gets the F15 answer, 1 line and marked, and a stopped box
  leaves the mail as it is.
- The sender read is decided twice over: the bars count
  colons and comment depth in 1 pass in front of the library,
  and a RecursionError from the library read itself is
  caught, so a deep sender is unread and the job goes on.
- The subject's encoded words are decoded under a byte bound
  and a catch.
- The signed body is read by loads_signed, which counts raw
  bracket depth in front of the parser and refuses a body
  past 200 levels as a ValueError. Every door's admission
  goes through it.
- The cancel, query, board and version 2 doors each read the
  body under a catch of Exception, so a shape that raises
  there is refused and marked in the door's own words.
- The bounce reader and the version 2 ingest reader catch
  Exception around their second parses.

## S1

One reader has no answer. The chain door reads the body
under a catch of JobCryptoError and ValueError only, and
inside that catch sits a second parse of the same raw mail.
The gate's first parse runs a few calls shallower than the
chain door's parse: the gate calls the dispatcher, the
dispatcher calls the door, the door calls the library. The
supposition is that a mail whose parts nest in the narrow
band where the shallow parse just succeeds and the deeper
parse crosses the call limit raises RecursionError out of
the chain door, out of the dispatcher and out of the gate,
and the message is never marked. The band is expected to be
narrow, a few levels wide, somewhere just under the count
where the first parse itself begins to raise (983 on the
ladder's measure). Checked by driving the real gate with
chain mails at every count across the band and watching for
a raise and an unmarked message.

## S2

Every other door decides such a mail at every count: chain
counts aside, a cancel mail, a query mail and a board mail
with parts nested at the same counts come back decided and
marked, and a job mail comes back decided at the first
parse. Checked with the same driver and the same counts.

## S3

If S1 holds, the change the numbers support has 2 parts.
The chain door's catch is widened to the shape its sibling
doors already carry, so the door gives its own answer. And
the dispatcher's call in the gate is guarded with the F15
answer itself, a stopped box leaving the mail and otherwise
1 line and marked, so any reader the dispatcher reaches,
present or future, is decided at the gate even when its own
catch is narrow. If the band in S1 measures empty, the
conclusions will say so plainly, and the widening stands
only as the consistency its siblings already have, with the
gate guard as the sentence for any future reader.
