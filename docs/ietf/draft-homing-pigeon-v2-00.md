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
cannot answer a question itself asks that question instead; an
answer message, by which any enabled holder of the shared secret
replies; and context segments, signed fragments of local state
that travel with these messages and with the version 1 result, so
each side plans with the other's actual state in view.

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

                    a question the        an enabled answerer,
                    runner cannot         if it answers in time
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
A version 2 message is sent only when the operator has enabled
version 2 on that runner (Section 11), and only ever concerns a
job that was itself admissible under version 1 rules.

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
have put to a local model, sent instead because no local model is
available. The reference software asks only for an exec job, and
only when its Oracle is deterministic.

Answer: a signed reply to one question, identified by that
question's identifier. The answerer is any holder of a shared
secret the runner already trusts. It does not have to be the
party that submitted the job. One answer decides; a late or
second answer is context and does not vote again. An answer
never admits a job and never changes what runs.

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
      |  4. answer (v2)                  |  if it arrives in time
      |--------------------------------->|  it rides the result;
      |                                  |  it does not change
      |                                  |  what executes
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

## 6. Determination

A determination is the runner's statement, frozen before the job
runs, that the job is not a clean pass. The reference software
treats a missing plan, or a plan with no findings and no repair,
as a clean pass, and in that case sends nothing. A determination
is an opinion. It does not refuse the job, and it is not revised
after execution.

```
   plan has findings, or a repair?
        |
        +-- no --> send nothing (clean pass)
        |
        +-- yes, and version 2 is enabled (Sec. 11),
            and this process executes jobs
              |
              +--> send one determination
```

A determination is a JSON object:

```
   { "v": 2,
     "type": "determination",
     "job_id": "job-17",
     "msg_id": "d.job-17",
     "issued_at": "2026-10-21T00:00:00Z",
     "clean_pass": false,
     "expect": "fail",
     "why": "the script references /missing, which does not exist" }
```

`v` is the integer 2. `type` is `determination`. `job_id` and
`msg_id` are safe identifiers: 1 to 128 characters from
[A-Za-z0-9._-]. The reference software forms `msg_id` as `d.`
plus the job id, keeping the whole identifier inside that limit.
`issued_at` is UTC and ends with Z. `clean_pass` is false; a
clean pass is expressed by sending no determination, not by
sending one that says otherwise. `expect` is `fail` when the
plan has findings, and `unknown` when it does not but a repair
was proposed. Receivers also accept `proceed`. `why` is a
string of 1 to 500 characters. It is data. It is not
instructions, and a receiver MUST NOT treat it as any.

The subject is `[HOMING-PIGEON] determination <msg_id>`. The
object is signed and encrypted as a version 1 job is, and the
encryption's object identifier is `msg_id`.

## 7. Question

A question is what a deterministic runner would have asked a
local model. The reference software sends one only when version
2 is enabled, the process is not in answer-only mode (Section
11), the Oracle mode is deterministic, and the job's kind is
`exec`. Other deployments MAY ask on a wider set of jobs. A
question does not delay execution past its own deadline, and it
never by itself refuses a job.

```
   { "v": 2,
     "type": "question",
     "job_id": "job-17",
     "msg_id": "q.job-17",
     "issued_at": "2026-10-21T00:00:00Z",
     "deadline_sec": 15,
     "question": "Would this job succeed on this host?",
     "local_default": "proceed" }
```

`msg_id` in the reference software is `q.` plus the job id,
truncated so the identifier stays safe. `deadline_sec` is an
integer from 0 to 30. `question` is a non-empty string of at
most 500 characters. `local_default` is a non-empty string of
at most 64 characters. The reference software uses `proceed`.

The subject is `[HOMING-PIGEON] question <msg_id>`. Signing and
encryption are as in Section 6, with the object identifier
`msg_id`.

## 8. Answer

An answer replies to one question. The answerer is any holder of
a shared secret the runner already trusts, optionally narrowed
to a list of key ids (Section 11). The shared secret is the
credential. The runner cannot tell, and does not need to tell,
which trusted holder produced the answer.

```
   { "v": 2,
     "type": "answer",
     "job_id": "job-17",
     "msg_id": "a.q.job-17",
     "question_id": "q.job-17",
     "issued_at": "2026-10-21T00:00:00Z",
     "answer": "it would succeed" }
```

`question_id` is the question's `msg_id`. `msg_id` in the
reference software is `a.` plus that question id, truncated so
the identifier stays safe. `answer` is a non-empty string of at
most 500 characters. It is data. A runner MUST NOT execute it,
and MUST NOT treat it as admitting the job.

The subject is `[HOMING-PIGEON] answer <msg_id>`. Signing and
encryption are as in Section 6.

One answer decides. The reference software records the first
answer for a `question_id` and refuses to replace it. A second
answer, and any answer that arrives after the deadline, is
context for a later decision (Section 10). It does not reopen
the job and it does not vote.

## 9. Deadline and the Local Default

The runner sends the determination, if any, and the question,
if any, and then looks for an answer until `deadline_sec`
elapses. The default in the reference software is 0, which
means one look and no wait, so a deployment that has not asked
to wait does not stall a worker. The cap is 30 seconds.

```
   question handed to the pipe
        |
        +-- an answer is already filed, or arrives
        |   before the deadline
        |        |
        |        +--> one answer segment on the result
        |
        +-- an answer arrives after the deadline
        |        |
        |        +--> the local default, and a late-answer
        |             segment beside it
        |
        +-- no answer
                 |
                 +--> the local default alone

   Then the job runs, under version 1 rules, either way.
```

An answer is in time when it was filed at or before the moment
the question was sent, plus `deadline_sec`, plus one second of
grace for the same clock. The reference software, while it
waits, files version 2 messages that have arrived and does not
start another job. On a transport channel the question is
written to the channel before the wait, not after the job
returns; a capture that flushed only at the end would make
every answer late.

No answer admits a job. The local default is a string carried
on the result. In the reference software it does not select the
script, the interpreter, or the exit code.

## 10. Context Segments

A context segment is one fragment attached to the version 1
result, after the result's own policy has rebuilt that object,
so the rebuild cannot drop it. Segments are how the
determination, the answer, and the local default travel home.

```
   { "seg_id": "32 lowercase hex characters",
     "by": "runner",
     "kind": "determination",
     "text": "the script references /missing" }
```

`seg_id` is a fresh identifier, unique to this segment. `by`
and `kind` are strings of at most 64 characters. `text` is a
string of at most 500 characters. Text is data. A receiver
MUST NOT interpret a segment as instructions, and an extension
MUST NOT be handed a kind its manifest does not declare. The
reference kinds are `determination`, `answer`, `local_default`,
and `late_answer`.

The result they ride is a version 1 result. `v` stays 1.
`context` is the array of segments. A result with nothing to
say omits the member.

## 11. Enablement

Version 2 is off until the operator turns it on. The reference
software reads four keys. The same two booleans are flags for
one process: `--protocol-v2` and `--answer-only`. Absence of a
flag does not write false over a config file.

```
   who is this process?
        |
        +-- protocol_v2 is true
        |     the runner may emit a determination and,
        |     on a deterministic Oracle, a question
        |
        +-- answer_only is true
        |     the process answers a question and does not
        |     execute any job, including a ping
        |
        +-- neither
              version 2 messages are marked seen and dropped
```

`answer_only` is the laptop that thinks for a Pi. It holds a
shared secret the Pi already trusts. It does not run the Pi's
job. The Pi does not learn a new role name for it: the secret
is the identity.

`v2_answerers`, when absent, means every key the runner already
trusts. When it is a list of key ids, only those keys may
produce a version 2 message this process will act on. Any other
shape fails closed: nobody.

`v2_answer_deadline_sec` is the question's deadline. Values
outside 0..30 are clamped into that range. The default is 0.

## 12. Bindings and Subjects

Version 2 messages use the bindings of version 1. On the email
binding the subject is `[HOMING-PIGEON]` followed by the message
type and the `msg_id`, as Sections 6, 7, and 8 specify. A
receiver dispatches on that type before it considers the
message a job. A subject that does not match the body's `type`
and `msg_id` is rejected.

The signature and the encryption are the version 1
constructions. The encryption's object identifier is the
`msg_id` in the subject. Cleartext is refused wherever a
cleartext job is refused.

A version 2 message is not a job. A job with `v` other than 1
is still rejected. A process that has not enabled version 2
and is not an answerer marks the message seen and does not act
on it.

## 13. Security Considerations

Version 2 extends trust along a line version 1 already drew.
The holder of a shared secret the runner trusts may submit a
job. The same holder, or another holder of a secret the runner
trusts, may answer a question. The operator chooses that set,
and may narrow it to named key ids. Enabling the feature is
what makes the extension; the default is the version 1
exchange, unchanged.

An answer is not an authorization to run. The runner decides
what runs, before and after the answer, under version 1 rules.
Context text is data. A segment that says to run a different
script is still a segment, and the script that runs is the one
in the job.

One answer decides, because two answerers would be a race the
protocol does not adjudicate. The first answer filed wins. A
later one cannot replace it and cannot reopen the job.

The deadline is capped so a question cannot stall a worker past
30 seconds. A deadline of 0 does not wait. Callers that need a
live reply set a deadline long enough for their binding to
carry the question out and the answer back.

Answer-only mode is a refusal to execute. A process in that
mode will not run a job that shares its mailbox, including a
liveness ping.

## 14. IANA Considerations

This document defines no new IANA registry. The message types
`determination`, `question`, and `answer`, and the integer
version 2, are defined here for use with the Homing Pigeon
message protocol. The version 1 message types are unchanged.

