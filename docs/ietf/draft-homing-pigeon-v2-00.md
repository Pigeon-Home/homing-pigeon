# draft-homing-pigeon-v2-00

Homing Pigeon Message Protocol, Version 2:
Determinations, Questions, and Shared Context

Workgroup: Individual
Intended status: Informational
Expires: 20 April 2027
Author: Pigeon-Home (editor)

## Abstract

This document specifies version 2 of the Homing Pigeon message
protocol. Version 2 is an addition to version 1
(draft-homing-pigeon-00), not a replacement for it: every version 1
message keeps its meaning, and version 2 adds three messages and one
mechanism on top of the version 1 exchange.

The additions are a determination message, by which the runner tells
the submitter what it expects a job to do before the job runs; a
question message, by which a runner whose local decision machinery
cannot answer a question itself asks the submitter that question
instead; an answer message, by which the submitter replies; and
context segments, signed fragments of local state that travel with
these messages and with the version 1 result, so each side plans
with the other's actual state in view.

Version 2 is backwards compatible. A version 1 runner never sends a
version 2 message and is unaffected by this document. A submitter
that implements this document adapts to the protocol version the
runner supports: faced with a version 1 runner, it submits version 1
jobs and expects version 1 results, exactly as before. There is no
version negotiation and no handshake; the messages carry `v`, as in
version 1, and each side acts on what it receives.

The deployment that motivates version 2 is the constrained runner: a
small host whose local decision machinery is deliberately
deterministic and carries no language model. Version 1 leaves such a
runner alone with every question its deterministic machinery cannot
answer. Version 2 lets it ask.

## Status of This Memo

This Internet-Draft is submitted in full conformance with the
provisions of BCP 78 and BCP 79.

Internet-Drafts are working documents of the Internet Engineering
Task Force (IETF). Note that other groups may also distribute
working documents as Internet-Drafts. The list of current
Internet-Drafts is at https://datatracker.ietf.org/drafts/current/.

Internet-Drafts are draft documents valid for a maximum of six
months and may be updated, replaced, or obsoleted by other documents
at any time. It is inappropriate to use Internet-Drafts as reference
material or to cite them other than as "work in progress."

This Internet-Draft will expire on 20 April 2027.

## 1. Introduction

Version 1 specifies two messages: a signed job object and a signed
result object, carried unchanged over any binding. The runner's
decisions in version 1 are local and silent: it verifies the
signature, forms whatever expectation its configuration gives it,
executes, and reports an exit code and output. The submitter learns
what happened, never what the runner thought would happen, and never
what the runner would have asked if it could.

Three gaps follow, and version 2 closes each with one message:

1. The submitter cannot see the runner's expectation before the
   run. A runner that expects a job to fail — because the box is
   hot, the disk is failing, or the same job failed an hour ago —
   has no way to say so until the result returns. The determination
   message (Section 6) is that statement, sent before execution.

2. A constrained runner cannot escalate. Where a full runner asks
   its local model and folds the reply into its decision, a
   deterministic runner has only its default. The question message
   (Section 7) carries the question the runner would have asked its
   own model to the submitter, and the answer message (Section 8)
   carries the reply back as a signed object.

3. Each side plans from a partial picture. The submitter sees exit
   codes; the runner sees one job at a time. Context segments
   (Section 10) are the shared remedy: signed, append-only fragments
   of state and reasoning that ride the messages both ways, so the
   submitter plans its next job from the runner's actual state, and
   the runner's components share what they observe with each other
   and with the submitter.

### 1.1. Who decides what

Every message in this document exists to move one decision to the
side that can make it. The figures in this document are normative in
intent if not in form: an implementation that moves a decision to
the wrong side of a figure has misunderstood the protocol.

```
                    DECISION              DECIDED BY
                    -------------------   -------------------
                    admit or refuse job   the runner, on the
                                          signature alone (v1)

                    what the job will     the runner, before
                    probably do           execution (determination)

                    a question the        the submitter, if it
                    runner cannot         answers in time
                    answer locally

                    the same question       the runner, by its
                    after the deadline    local default

                    what runs, finally    the runner, always;
                                          no answer admits a job

                    the next job          the submitter, with
                                          the runner's context
                                          in view
```

### 1.2. Backwards compatibility and adaptation

Version 2 changes no version 1 message. A version 2 runner MUST
accept version 1 jobs and MUST answer them with version 1 results.
A version 2 message is sent only to a submitter the operator has
enabled for it (Section 11), and only ever concerns a job that was
itself admissible under version 1 rules.

A submitter that implements this document will routinely face
runners that do not. Realizing a runner does not support version 2 —
because no version 2 message ever arrives from it, or because the
operator says so — is not an error and needs no machinery: the
submitter falls back to version 1 with that runner, submitting
version 1 jobs and reading version 1 results. The submitter adapts
to the protocol version the endpoint supports; the endpoint is never
asked to adapt, to negotiate, or to announce itself.

```
   Submitter (v2)                       Runner
        |                                  |
        |  job (v=1 object, as always)     |
        |--------------------------------->|
        |                                  |
        |        if the runner is v2 and   |
        |        the operator enabled it:  |
        |                                  |
        |  determination (v=2)             |
        |<---------------------------------|
        |  question (v=2)                  |
        |<---------------------------------|
        |  answer (v=2)                    |
        |--------------------------------->|
        |                                  |
        |  result (v=1 object, with        |
        |   context segments attached)     |
        |<---------------------------------|
        |                                  |
        |        if the runner is v1:      |
        |        none of the v2 lines      |
        |        above ever happen, and    |
        |        the exchange is exactly   |
        |        the version 1 exchange.   |
```

## 2. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and
"OPTIONAL" in this document are to be interpreted as described in
BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all
capitals, as shown here.

## 3. Terminology

The terms of draft-homing-pigeon-00 apply: submitter, runner,
binding, shared secret, key_id, and the message members defined
there. This document adds:

Determination: the runner's pre-execution statement of what it
expects a job to do, and why. A determination is an opinion, formed
from the runner's local state and history, frozen before the job
runs and never revised afterwards.

Question: a question the runner's local decision machinery would
have put to a local model, sent to the submitter instead because no
local model is available or because local policy prefers the
submitter's answer.

Answer: the submitter's signed reply to a question, identified by
the question's identifier.

Local default: the decision the runner makes when no answer has
arrived by the question's deadline. Every question has one; asking
never leaves a decision unmade.

Deadline: the time by which an answer must arrive to affect the
decision it was asked about. An answer that arrives after its
deadline is not discarded; it becomes context for the next decision
(Section 8).

Context segment: a signed, self-describing fragment of state or
reasoning, appended to a message by one component and readable by
the others, carrying its author's identity and a seen-once
identifier (Section 10).

Clean pass: a determination that the job is expected to proceed
without incident: no finding above the runner's lowest severity of
interest, no expected failure, nothing the submitter would act on.
The runner's local policy defines the threshold precisely; the
protocol defines only that the threshold exists (Section 6).

## 4. The Exchange at a Glance

```
   Submitter                          Runner
      |                                  |
      |  1. job (v1)                     |
      |--------------------------------->|  verify signature (v1 rules)
      |                                  |  form the determination
      |                                  |
      |  2. determination (v2)           |  ONLY if not a clean pass,
      |<---------------------------------|  ONLY if enabled (Sec. 11)
      |                                  |
      |                                  |  a question arises the
      |                                  |  runner cannot answer
      |  3. question (v2)                |
      |<---------------------------------|  deadline starts
      |                                  |
      |  4. answer (v2)                  |  if it arrives in time,
      |--------------------------------->|  fold it into the decision
      |                                  |
      |                                  |  deadline passes with no
      |                                  |  answer: local default
      |                                  |
      |                                  |  execute (v1 rules)
      |  5. result (v1 + segments)       |
      |<---------------------------------|
      |                                  |
   The numbers are the order of first transmission, not a lockstep:
   a determination and a question MAY travel in either order, and
   an answer NEVER delays execution past the deadline.
```

## 5. Common Form

A version 2 message is a JSON object carried on any binding that
carries version 1 messages, byte for byte the same treatment: the
subject conventions of draft-homing-pigeon-00 Section 6, with the
message type in the subject; the signature and MAC construction of
Section 7 of that document; the per-job encryption of its
Section 16 applied to the whole object; and the common members of
its Section 9, including `v`, which is 2 for the messages this
document defines.

A receiver that does not implement this document will reject a
message carrying `v` = 2, as version 1 requires it to; that
rejection is the correct and only interaction between a version 2
message and a version 1 receiver, and senders MUST NOT send a
version 2 message on a path where a version 1 receiver is expected
to process it as a job. Version 2 messages are addressed to the
job's `reply_to`, never to the mailbox a runner polls for jobs,
except where the deployment's bindings make the two the same and
the receiving implementation separates them by type before any
job processing.

Every version 2 message names the job it concerns (`job_id`) and
its own identifier (`msg_id`), and carries `issued_at` as in
version 1. Replay handling follows the seen-set discipline of
version 1: an identifier is recorded once the message has been
acted on, and a duplicate is dropped silently.

---

**Editor's note — state of this draft** (2026-10-20; this note is
removed as the sections land)

Sections 1 through 5 above are written. What remains, in order:

- Section 6, the determination message: members, the frozen
  pre-execution verdict, sent only when the determination is not
  a clean pass and only to an enabled sender.
- Section 7, the question message: the question the endpoint
  would have asked its own model, its context, its deadline.
- Section 8, the answer message: signed, keyed by question
  identifier; a late answer becomes context for the next
  decision and never reopens the decided job.
- Section 9, the decision timeline and the local default, with
  the timeline figure.
- Section 10, context segments: append-only, signed, carrying
  provenance and seen-once identifiers; extensions receive only
  the kinds their manifest declares; inbound context is data,
  never instructions.
- Section 11, enablement and local policy: per-sender operator
  enablement, the command-line option in the reference software.
- Section 12, bindings and subjects for the new message types.
- Section 13, security considerations, including the trust this
  version deliberately extends to the submitter and why.
- Section 14, IANA considerations.

Figures are part of the drafting contract: every decision point
gets one, as Sections 1.1, 1.2, and 4 illustrate.

Still to come from the author: the implementation details for
how this protocol is realized in the client software. They are
discussed with the author and folded into the sections above as
each one lands; this note is the placeholder that keeps them
from being lost. Implementation, when commissioned, is staged:
the determination and question messages and the receiver's
dispatch on message type first; the signed answer path, with
its deadline, second.
