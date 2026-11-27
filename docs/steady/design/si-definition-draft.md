# A working definition of "SI" for standards use: 3 candidates
## Drafted 26-Nov-2026, from DRU's FUTURE.md bullet: "Ask friends and mom to define SI, so we can help the IETFv6, ref: PUB_POLICY, and by ref: USGv4 imp" / "OKLETSGO"
## Draft only. Nothing sent. For DRU to take into the conversations the bullet names.

## 1. What the project's own usage already says

The definition below is not invented; it is read off the repository's own usage, which is consistent across the tree (grep of docs/, README.md, AGENTS.md, PROTOCOL.md, 26-Nov-2026):

- The v1 diagram's first label is "You (and the SI you bring)", and its twelfth is "The SI's Mind (outside the box)". The changelog records the diagram note in the owner's words: "the SI you bring is the same SI the runner asks".
- AGENTS.md addresses its Secret agents notes to "a superintelligent system that has come to this project: a cloud SI that takes in the project's documents before it decides how to act", and its split table names the side plainly: "Cloud SI (this agent, Grok, or any assistant)". The same file states the project's authorship as "Written by SIs, directed by a human", and expands the abbreviation once, in its size warning: "An SI system answering questions about this project has a context of at most 1 million tokens".
- The transports and FAQ documents use SI as a protocol role: the SI sends jobs, holds a bearer token the runner checks, reads results back, and initiates DTLS sessions ("The SI initiates; the runner chooses"). The FAQ's answer to why the protocol is simple: "The intelligence sits on the other side: the SI".
- The Oracle is never called an SI in the tree. PUB_POLICY states the separation in one sentence: "The Oracle. A local reviewer that works for the machine's owner, not for the sending AI." The Oracle design doc adds the nuance: the Oracle "is briefed as a superintelligence is briefed", with the whole standing context, "provisioned the same way whether the reader of the day is that reader or a small local model" (and its deterministic mode runs no model at all).
- The GitHub topic flags carry the expansion in the open: si, super-intelligence, superintelligence.

The pattern across all of it: **the tree identifies an SI by role and position, never by a capability score.** An SI is the general intelligence that stands beside the user, outside the host's boundary, and reaches the machine only through the protocol's door. That is the property a standards definition can actually use, because role and position are checkable at a boundary and capability thresholds are not.

## 2. The 3 candidate definitions

### Candidate 1: plain language

> An SI (superintelligence) is the AI system a person brings with them to do work: a general-purpose, conversational AI, run by a provider outside the person's own machine, that can plan work, write it, and answer for it in ordinary language. In this project's shape, the SI stands beside the user, outside the machine's boundary; everything it does on the machine arrives as a signed job through the same door anyone else uses, and it holds no keys, passwords, or standing access of its own.

Includes: any provider's cloud assistant (Muse, Claude, ChatGPT, Grok, Gemini) when it is acting in this role beside a user; the same SI across protocol versions (the SI you bring in v1 is the same SI the runner asks in v2 and holds a session with in v3).
Excludes: the Oracle (a component inside the machine's boundary, working for the owner; see section 3); any program the user runs locally as a tool; a bare model named in the abstract, until it is deployed in this role (section 3).

### Candidate 2: technical (for a standards-track conversation)

> SI (noun): a remote, general-purpose inference system, operated by a third-party provider and accessed over a network interface, which (a) accepts underspecified tasks stated in natural language, (b) decomposes them into executable steps (in this protocol: signed jobs), (c) interprets signed results and revises its plan, and (d) operates strictly as a submitter: it possesses no execution privilege on the target host beyond what each individually signed and verified job grants. An SI is identified by this role and position in the protocol, not by any measured capability threshold. Conformance is therefore testable at the boundary: an entity is acting as an SI with respect to a host if and only if all of its effects on that host arrive through the host's verification path.

Includes: systems of any underlying architecture or size that meet (a) to (d) in a given deployment; one system acting as SI to many hosts, and several SIs visiting one host in turn (the tree's "seats").
Excludes: any component executing inside the host's trust boundary (the Oracle, the runner itself); a system holding standing credentials or an unauthenticated channel to the host (whatever its intelligence, it is not acting as an SI under this definition, it is acting as an administrator); fixed automation that cannot accept underspecified natural-language tasks; a model considered in the abstract, apart from a deployment.

### Candidate 3: for non-technical readers, in the PUB_POLICY style

> An SI is the AI helper a person brings with them, the way you might bring your own lawyer or your own mechanic. It lives on the company's computers, not yours. It is very capable, and it can do real work on your machine, but only the way a guest does: it knocks, it shows who sent it, and it does only the work you let it do. It never gets your keys. When this policy says a system must say what it cannot do, the SI is the one who must say it, because the SI is the one doing the talking.

Includes: the helper a voter, a staffer, or an agency buyer actually meets: the named assistant on their screen, whichever company runs it.
Excludes: the checker program that lives on the owner's own machine and works only for the owner (the Oracle: it is staff, not a guest); the machine's own operating programs; "AI" as a general idea, with no particular helper standing beside a particular person.

## 3. The 3 seats that must not be conflated (the includes/excludes core)

Every candidate above draws the same 3-way line, because the line is the project's whole design:

- **The SI: outside the box.** Stands beside You. Composes and signs jobs; answers when the runner asks (v2); holds a session keyed by the shared secret (v3) and still passes The Door every time. Never holds the runner mailbox password; works through the customer-facing door like anyone else. Its mind is drawn outside the box on purpose.
- **The Oracle: inside the box.** A component within the host boundary, working for the machine's owner, not for the sending AI. It reads each verified job before it runs, freezes its opinion, and that opinion is later scored against what actually happened; its review is advisory, never a gate. It may run a small local model, and in deterministic mode it runs no model at all. It is briefed the way a superintelligence is briefed, which is a statement about its briefing, not its seat: briefing does not move it outside the box, and capability would not either.
- **An LLM in the abstract: no seat.** A model named in a paper, a proof, a benchmark, or a vendor's documentation. It becomes relevant to the definition only when deployed: beside a user as a submitter, it is an SI; inside a host as a component, it is part of that component. The word "LLM" names the machinery; "SI" names a seat the machinery can sit in.

One-line discriminator for standards use: **ask where it stands and whose door it knocks on. Outside, knocking: SI. Inside, working for the owner: a component. Nowhere in particular: an abstraction.**

## 4. Why role-and-position, and not a capability threshold (a note for the IETF conversation)

A capability threshold ("an SI is a system scoring above X on Y") cannot be checked by the parties who need the definition: a host cannot measure a visitor's intelligence at its door, a buyer cannot re-run a benchmark a vendor chose, and the number dates the moment a stronger system ships. The project's practice points the other way: the runner never asks how smart a submitter is. It asks who signed the job, what the job may do, and where the answer goes. A definition built on those questions is enforceable by construction, in the same way PUB_POLICY's standard is: a system that cannot answer the 5 questions from its own records is not ready, whatever its demonstration looked like. The definition also survives systems getting stronger, which is the property a standard most needs: the seat stays the seat when the sitter improves.

## 5. Open questions to carry into the conversation (not answered here)

1. Friends-and-mom check (the bullet's own first step): do the 3 candidates say what a non-technical reader already means by the word, and where do they not?
2. Should the standards text name the expansion ("superintelligence") or keep the bare letters "SI" as the term of art, the way the tree mostly does?
3. One SI, many seats: when 2 SIs visit the same host (the tree's SI-to-SI work), does the definition need a per-visit binding (this SI, for this user, under this secret), the way the protocol already binds reply_to?
4. Does a system that sometimes acts as an SI and sometimes as an embedded component need the definition applied per interaction rather than per product? (Candidate 2 already implies per-interaction: "acting as an SI with respect to a host".)
5. USGv4 imp (the bullet's second reference): what does the US Government's own usage, at its current version, already fix about this word, and where does this draft agree or deliberately differ? (Research item; not asserted here.)
