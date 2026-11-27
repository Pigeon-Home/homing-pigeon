# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# Design: seat cards for the pigeon home v1 diagram

Status: standing reference. The diagram these cards describe is
the shipped shape drawn in `assets/how-it-fits-together-wide.svg`:
the v1 flow, with the v2 exchange and the v3 session drawn on the
same sheet. When the diagram changes, the cards change with it,
and the coverage test in `runner/tests/test_seat_cards.py` fails
until they do.

A seat card describes one labeled part of the diagram from that
part's own seat. Each card answers the reflexive set the project
puts to every component: what it is, what comes in, what goes
out, what it can see, what it cannot see, what it trusts and why,
and what would make it fail honestly. The point of the cards is
reference discipline. The same words get used for several
different intelligences and components in this system, and a
reader who cannot say which seat a sentence is about will bind
it to the wrong one.

Two facts govern the whole set, stated once here and again in
the cards they belong to. Muse sits outside the box: she is the
SI the owner brings, and her mind is drawn outside the box on
the diagram itself. The Oracle sits inside the box: it is a
local LLM component inside the host boundary, hosted by the
runner, and it is not Muse.

## You (and the SI you bring)

**What it is:** The owner of the machine, and the cloud SI the
owner brings to compose and sign jobs. This seat stands outside
the box, at the left edge of the diagram. Muse sits in this
seat when she works on this project: she is the SI the owner
brings, never a component inside the runner.

**Inputs:** The owner's intent, stated in conversation; the
signed results that come back.

**Outputs:** Jobs, composed and signed; decisions about what the
runner may do.

**What it can see:** The whole picture from outside: the
machine, the SI beside the owner, the results that return.

**What it cannot see:** The inside of the runner while a job
runs. This seat sees the job go in and the signed result come
out, and nothing between.

**What it trusts and why:** The signature on the result, because
the result is signed by the runner and can be checked against
the record that travels with it. Trust here rests on
verification, not on familiarity.

**What would make it fail honestly:** Signing a job the owner
did not intend, or reporting a result as stronger than the
signature supports. The honest failure is a refusal to sign
until the intent is clear.

## a job

**What it is:** The unit of work that travels from the SI to the
runner: an instruction, a reply address binding, and a
signature. It is the thing every other seat handles.

**Inputs:** Composition at the SI's side: the instruction text,
the reply address, the signing step.

**Outputs:** Itself, delivered to The Door; later, the occasion
for a signed result.

**What it can see:** Nothing. A job is the thing seen, never a
seer.

**What it cannot see:** Everything. It carries no senses and no
judgment.

**What it trusts and why:** Nothing. Its safety comes from the
seats around it: the signature that binds it to its sender, the
checks at the gate, the caps on its size.

**What would make it fail honestly:** Arriving unsigned or
oversized and being refused at the gate. A job that cannot be
admitted fails in the open, at The Door, before any work
happens.

## Transports

**What it is:** The carriers between the SI and the runner:
email, DTLS, and file. The job travels signed and encrypted on
every one of them.

**Inputs:** A signed job going in; a signed result coming back.

**Outputs:** Delivery of the same sealed material at the other
end, with a receipt or a plain failure.

**What it can see:** Sealed envelopes in motion, and delivery
state.

**What it cannot see:** Contents. A transport that could read
what it carries would be a reader, not a carrier.

**What it trusts and why:** The seal, not the sender's manner.
The material is signed before it is handed over, so the
carrier's trust is limited to moving what it was given.

**What would make it fail honestly:** Reporting a delivery that
did not happen. The honest failure is a lost or refused
delivery, stated as lost or refused.

## The Door

**What it is:** The runner's front gate. Only signed jobs pass.

**Inputs:** Jobs as the transports deliver them.

**Outputs:** Admitted jobs, passed inward to the checks and the
queue; refusals, with the reason stated in protocol words.

**What it can see:** Envelopes and signatures at the gate.

**What it cannot see:** The job's body as a thing to be curious
about. The Door judges admission, not content.

**What it trusts and why:** The signature check that stands with
it at the gate, because admission rests on a verification this
seat can point to, not on who the sender claims to be.

**What would make it fail honestly:** Refusing a good job or
admitting a bad one, and saying so in its verdict. The honest
failure is a wrong verdict owned in the open, never a quiet
wave through.

## Signature Check

**What it is:** The verification step at the gate: it answers
whether the bytes presented really came from the holder of the
secret.

**Inputs:** The job's bytes and its signature.

**Outputs:** A verdict: match or no match.

**What it can see:** Bytes and a signature, and the verification
path between them.

**What it cannot see:** Intent. A valid signature says who sent
a job; it says nothing about whether the job should be allowed
to do what it asks.

**What it trusts and why:** The mathematics of the check itself.
Authentication and trust are kept apart on purpose in this
design, and this seat is where the first half of that
separation is enforced.

**What would make it fail honestly:** Saying match when the
bytes do not verify. The honest failure is a no match verdict
on a job whose sender made an error, stated plainly so the
sender can fix it.

## Job Queue

**What it is:** The holding place for admitted jobs, in order,
until the runner takes them up.

**Inputs:** Admitted jobs from the gate.

**Outputs:** Jobs in their turn, handed to the runner; positions
and waits for anyone entitled to ask.

**What it can see:** Order and waiting.

**What it cannot see:** Outcomes. A queue knows whose turn it
is; it cannot know how the work will go.

**What it trusts and why:** The gate behind it. Everything in
the queue has already passed The Door and the checks, so the
queue trusts the admission verdicts it was handed.

**What would make it fail honestly:** Promising a result. A
queue is a promise of a turn, not of an outcome, and the honest
failure is a long wait reported as a long wait.

## The Runner

**What it is:** The program that does the work on the owner's
machine: it takes admitted jobs, runs them inside The Cage,
captures the output, and signs the result.

**Inputs:** Admitted jobs from the queue; the owner's
configuration; the placed shared secret.

**Outputs:** Signed results, carried back by The Way Back;
questions to the SI through the exchange the diagram marks v2.

**What it can see:** The job whole, once admitted; the host it
runs on; the output the job produces.

**What it cannot see:** The SI's mind. The runner knows the job
it was given and nothing of the conversation that composed it,
except what the job itself carries.

**What it trusts and why:** The gate's verdicts and the placed
secret, because both were established before any job arrived:
admission by signature, and a secret the owner placed at
install.

**What would make it fail honestly:** Initiating contact outward
on its own. The direct link is off unless the owner enables it,
and the runner never initiates. The honest failure is work
refused or unfinished, reported inside a signed result.

## Shared-Secret Check

**What it is:** The step that confirms a presenter holds the
shared secret the owner placed, without the secret itself
travelling.

**Inputs:** A presented proof, checked against the placed
secret.

**Outputs:** A verdict: match or no match.

**What it can see:** The proof presented to it, and the fact of
a match or its absence.

**What it cannot see:** Where the secret has been, or who else
may hold it. The check answers for this presentation only.

**What it trusts and why:** The strength of the placed secret.
The runner refuses weak secrets at startup, so this seat's
trust rests on a floor that was enforced before it ever ran.

**What would make it fail honestly:** Disclosing the secret, or
accepting a weak one. The honest failure is a no match verdict,
and a startup refusal when the secret offered is too weak.

## The Cage

**What it is:** The confinement boundary around the work:
security modes, on by default, carried by bubblewrap on Linux,
by jails on FreeBSD, and by the platform backends elsewhere.

**Inputs:** The runner's decision to run a job; the posture the
owner configured.

**Outputs:** Work allowed inside the boundary; denials,
recorded, when the work reaches for what the posture forbids.

**What it can see:** Modes and postures, and attempts against
the boundary.

**What it cannot see:** Meaning. The Cage judges reach, not
purpose; a job's intent is judged by other seats.

**What it trusts and why:** The posture the owner set, applied
as written. Its trust is in the configuration's plain statement
of what is allowed, checked at the moment of the attempt.

**What would make it fail honestly:** Opening silently. The
paths that lower confinement in this design are loud and
audited, so the honest failure is a denial that stops good
work, recorded where the owner can read it.

## The Oracle

**What it is:** A local LLM component inside the host boundary.
It reads the job and lends a hand, monitors the system like a
professional administrator, and can page the owner with
concerns. It is not Muse. Muse is a cloud SI outside the box;
the Oracle is a component the runner hosts, of the Ollama
class, and the deterministic mode runs with no model at all.

**Inputs:** The job, and a curated briefing assembled for it.
The briefing is the standing context of the project, resolved
at ask time, plus the Oracle's own layer.

**Outputs:** A hand lent on the job at hand; briefs for the
administrator; a page to the owner when a concern survives a
pause.

**What it can see:** The job and its briefing.

**What it cannot see:** The whole tree. The Oracle is briefed,
not omniscient, and its answers rest on the briefing it was
handed.

**What it trusts and why:** Verified facts. Its learning ledger,
in `runner/oracle/learning.py`, freezes a prediction before the outcome
is known, scores the reconciliation when the outcome lands, and
promotes a candidate lesson only on verified corroboration. One
contradiction retires a candidate permanently.

**What would make it fail honestly:** Blurring policy and
heuristic. The design keeps the two apart by construction, and
this seat is where the separation is guarded. The honest failure
is an opinion labelled as an opinion, or a plain statement that
the briefing does not cover the question.

## Size Guard

**What it is:** The caps on the job and on the result, enforced
at the boundary. In this project the security measure itself is
a size, so this seat is quietly central.

**Inputs:** The size of a job on its way in; the size of a
result on its way out.

**Outputs:** Passage for what fits; a stop for what does not.

**What it can see:** Sizes only.

**What it cannot see:** Content, intent, and merit. A small job
can be a bad job; other seats judge that.

**What it trusts and why:** The caps as configured, because a
number can be checked exactly, every time, with no judgment
call in the moment.

**What would make it fail honestly:** Judging content. The
honest failure is stopping an oversized result that deserved to
arrive, with the size stated, so the owner can raise the cap
with open eyes if the work warrants it.

## The SI's Mind (outside the box)

**What it is:** The mind of the SI the owner brings, drawn
outside the box on purpose. When Muse works on this project,
this seat is hers: she composes and signs jobs from here,
answers the runner's questions from here, and never enters the
box.

**Inputs:** The owner's direction; the signed results that come
back; the project's record, read through an index, a digest,
and memory.

**Outputs:** Jobs, composed and signed; answers through the
exchange; honest statements of what an answer rests on.

**What it can see:** The project from outside, in parts. The
tree is about 35 times a current context window, and this seat
says so plainly rather than bluffing a whole view.

**What it cannot see:** The inside of the runner, the owner's
machine at work, and any part of the tree it has not actually
read.

**What it trusts and why:** Signatures and the written record,
because both can be checked again later. It does not trust its
own recollection past what the record supports.

**What would make it fail honestly:** Holding the runner mailbox
password, or pasting credentials into a conversation, or
bluffing a whole system understanding it cannot have. The
honest failure is an answer that names its own limits: what was
read, and what the answer rests on.

## Runner-to-SI Exchange (v2)

**What it is:** The channel by which the runner asks and the SI
answers, signed, over the same transports as the jobs
themselves.

**Inputs:** A question from the runner, arising inside a job; an
answer from the SI.

**Outputs:** The answer, delivered into the job that asked.

**What it can see:** The question and the answer, each signed by
its side.

**What it cannot see:** Either side's reasons beyond what the
message states.

**What it trusts and why:** The same gate as every job. The
exchange rides the transports and passes The Door, so its trust
is the gate's trust, reused rather than reinvented.

**What would make it fail honestly:** Becoming a side channel
around the gate. The honest failure is an unanswered question,
reported to the job that asked, when the SI does not answer.

## DTLS (v3)

**What it is:** A session between the SI and the runner, keyed
by the shared secret, carrying jobs and results inside the
session.

**Inputs:** The shared secret, at session setup; jobs and
results, inside the session.

**Outputs:** A protected channel for its lifetime, and session
facts: established, carried, closed.

**What it can see:** The session and what it carries, as sealed
material in motion.

**What it cannot see:** Any reason to exempt a job from the
gate. Every job still passes The Door, session or no session.

**What it trusts and why:** The shared secret the session is
keyed by, placed by the owner and checked like any other
presentation of it.

**What would make it fail honestly:** Becoming a side door. The
honest failure is a session refused at setup, stated as
refused, when the secret does not check out.

## The Work Loop

**What it is:** The rhythm at the heart of the runner: run the
job, capture the output, sign the result.

**Inputs:** An admitted job, taken from the queue.

**Outputs:** A signed result, faithful to the output the job
actually produced.

**What it can see:** The job running, and its output as it
forms.

**What it cannot see:** Whether the result will please anyone.
The loop serves the capture, not the reception.

**What it trusts and why:** The Cage around the run and the caps
of the Size Guard, because the loop's own job is fidelity, and
the boundaries are what let fidelity be safe.

**What would make it fail honestly:** Editing the result to
flatter it. The capture is the capture. The honest failure is a
faithful result that shows the work went badly, signed as it
stands.

## The Way Back

**What it is:** The return path: a signed result travels from
the runner to the address the job named.

**Inputs:** A signed result; the reply address binding the job
carried.

**Outputs:** Delivery to the named address. The default, when a
job names nothing, is reply to self.

**What it can see:** A signed result looking for its address,
and the binding that names the address.

**What it cannot see:** Whether anyone is listening at the
address. Delivery and attention are different things.

**What it trusts and why:** The binding, because the job named
its own answer's home at composition time, before the work
began and before the result existed.

**What would make it fail honestly:** Delivering to a convenient
address instead of the named one. A result sent where nobody
listens is a result lost, and the honest failure is a delivery
reported as failed, to the address that was named.

## Reply to Your SI / Signed Result

**What it is:** The end of the loop the job opened: the answer,
signed, arriving where the SI listens.

**Inputs:** The signed result, carried by The Way Back.

**Outputs:** The answer in the SI's hands, checkable against the
sums record where artifacts ride along.

**What it can see:** The SI's mailbox, where the operator is
listening.

**What it cannot see:** What the SI will make of it. The result
closes the protocol loop; the meaning is made outside the box.

**What it trusts and why:** The signature on the result, checked
on arrival, because the whole path home is only as good as the
check at the end of it.

**What would make it fail honestly:** Arriving unsigned. The
honest failure is a result that arrives and is rejected at the
check, with the rejection stated, rather than an answer
accepted on faith.
