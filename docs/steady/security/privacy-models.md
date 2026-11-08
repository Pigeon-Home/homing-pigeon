# Privacy models: a survey of the options

This document surveys the privacy models and mentalities an
operator of this suite could adopt, each documented on its own
terms from the published literature. It is a reference, kept so
the options are on record in one place.

**The operator of this project takes no position among these
models.** They are presented as open options. The design that
lets an operator's chosen mentality be expressed as
configuration rather than as a code change is
`privacy-design.md`.

The survey text follows, as written from its sources
(literature checked 2026-11-08; a survey of the literature, not
an audit of any product).

---

# Privacy Models and Mentalities for a Self-Hosted Automation Runner — A Neutral Survey

**Date context:** November 2026  
**Status of sources:** All sources below were found and checked through the web index on 2026-11-08. No source was verified by running the runner software itself; this is a literature survey, not a product audit.

---

## Summary

This document surveys the distinct *models* (formal or semi-formal frameworks with rules) and *mentalities* (stances, values, and habits of thought) of privacy that the operator of a particular kind of system could adopt:

> **The system in question:** a **self-hosted automation runner** — software that runs jobs on the operator's own machines, can in principle read local files and messages, and reports results to a remote AI service.

Eleven positions are documented, each on its own terms:

1. Privacy by Design and privacy-by-default
2. Data minimisation / collection limitation
3. Contextual integrity
4. Threat-model-driven privacy — LINDDUN, and the adversary-first / OPSEC mentality
5. Local-first / data sovereignty, with attestation, zero-knowledge-flavoured and capability-based variants
6. Confidentiality and compartment models from information security — Bell–LaPadula, classification-and-clearance, Chinese walls
7. Consent-and-control — privacy as a dial, including sheltering personal material before a run
8. Radical transparency / the nothing-to-hide counter-mentality
9. Privacy as dignity and autonomy, and the post-Snowden engineering positions of the IETF (RFC 6973, RFC 7258)
10. Obfuscation — privacy by noise and plausible deniability
11. Privacy as a collective and social good

A comparison table follows the sections, and the document closes with an explicit note that **it takes no position on which model is best**.

### A framing note that applies to every model

Three features of this system recur in every section, because different models handle them very differently:

- **Operator ≠ the only data subject.** The operator owns the machine, but local files and messages normally contain other people's information — correspondents, family members, clients, colleagues. The operator can consent for themselves; they cannot, in the same way, consent for those third parties.
- **Capability ≠ use.** A runner that *can* read everything does not have to read, retain, or transmit everything on every job. Most models below are, in different vocabularies, ways of deciding which of those three verbs — read, retain, transmit — is allowed, for what, and by whom.
- **The remote service is a distinct party.** Even a trusted remote AI service is a separate recipient, with its own logs, retention, staff, subprocessors, legal obligations, and breach risk. Models differ sharply in whether they treat that party as a partner, a processor under contract, an untrusted verifier, or an adversary.

---

## Findings

### 1. Privacy by Design (PbD) and Privacy-by-Default

**Core idea.** Privacy should be built into a system's architecture and business practices from the outset, not added after a complaint or a breach, and not traded away against other goals. Ann Cavoukian, Information and Privacy Commissioner of Ontario, formalised this in the 1990s–2000s as seven foundational principles: (1) proactive not reactive, preventative not remedial; (2) privacy as the default setting; (3) privacy embedded into design; (4) full functionality — positive-sum, not zero-sum; (5) end-to-end security — full lifecycle protection; (6) visibility and transparency — keep it open; (7) respect for user privacy — keep it user-centric. Principle 2 is the source of *privacy-by-default*: if the person does nothing, the maximum protection applies automatically.

**What it would mean for this runner.**
- The shipped default configuration is the most protective one: narrowest file scope, shortest retention, no telemetry or transcript-sharing unless the operator turns it on.
- Privacy decisions are made at design time and recorded — e.g. a data inventory, a stated purpose for every category of file the runner can touch, retention and deletion rules for logs and job artefacts — rather than improvised per incident.
- Lifecycle thinking: protection covers collection, use in the job, transmission to the remote service, storage there and locally, and deletion, not just the moment of sending.
- Verifiability (principle 6): the operator — and, in the original formulation, outside reviewers — can inspect what the runner actually does, e.g. open code, published data-flow descriptions, auditable logs of accesses.
- In law, GDPR Article 25 crystallises a version of this as “data protection by design and by default”: Article 25(1) requires measures at the time the means of processing are determined and during processing itself; Article 25(2) requires that by default only personal data necessary for each specific purpose is processed, covering amount collected, extent of processing, storage period, and accessibility.

**Costs and failure modes.**
- It is a philosophy, not a checklist: the seven principles do not by themselves specify, for example, which files are in scope, so two systems can both claim PbD and behave very differently. Critics in the literature describe a resulting risk of “privacy-by-design” as a label rather than an engineering constraint.
- Positive-sum framing (principle 4) can obscure real trade-offs where they do exist — e.g. where richer context sent to a remote model genuinely produces a better result — by treating every trade-off as a design failure to be dissolved.
- Defaults protect people who do nothing, but they also decide for people: a protective default that is hard to understand or change can become paternalistic, and a default is only as good as the designer's model of the operator's situation.
- Cost is front-loaded: threat and data-flow analysis, deletion machinery, and auditability must be built before they are visibly needed.

**Canonical sources.**
- Cavoukian, A., *Privacy by Design: The 7 Foundational Principles* (Information and Privacy Commissioner of Ontario, 2011 revision) — summary and principle list: https://en.wikipedia.org/wiki/Privacy_by_design
- Cavoukian presentation of the seven principles (IPC Ontario): https://www.ipc.on.ca/en/media/1369/download?attachment
- GDPR Article 25 as the legal form, explained: https://www.legiscope.com/blog/implementing-privacy-by-design.html

---

### 2. Data Minimisation / Collection Limitation

**Core idea.** Do not collect, use, retain, or disclose more personal data than a specified purpose requires — and specify the purpose first, because “necessary” is meaningless without it. This is the oldest internationally agreed privacy principle: the OECD *Guidelines on the Protection of Privacy and Transborder Flows of Personal Data* (1980, revised 2013) put **collection limitation** first among eight principles (followed by data quality, purpose specification, use limitation, security safeguards, openness, individual participation, and accountability). GDPR Article 5(1) is a legal crystallisation: personal data shall be processed lawfully, fairly and transparently (a); collected for specified, explicit and legitimate purposes and not further processed incompatibly (b, purpose limitation); “adequate, relevant and limited to what is necessary in relation to the purposes” (c, **data minimisation**); accurate (d); kept identifiable no longer than necessary (e, storage limitation); and processed securely (f, integrity and confidentiality), with the controller accountable for demonstrating all of it (Art. 5(2)).

**What it would mean for this runner.**
- Per-job scoping: a job declares what it needs (a directory, a date range, a message thread, a document type), and the runner reads only that — not the whole home directory or mailbox as a standing condition.
- Transmission minimisation, which is distinct from collection minimisation: even where local reading is needed, only a summary, excerpt, embedding-free result, or redacted version leaves the machine. The IETF's later data-minimisation work makes the same point about protocol participants: minimise what you share *with the other party*, not only what you shield from outsiders.
- Retention limits: job inputs, intermediate files, prompts, transcripts, and logs expire on a schedule tied to the purpose (debugging, audit), rather than being kept “just in case.”
- No secondary use by default: material gathered to complete one job is not reused to train, profile, improve a service, or seed another job without a new purpose and basis.

**Costs and failure modes.**
- “Necessary” is contestable, especially for a general-purpose AI runner: it is often genuinely unknown in advance which file will turn out to be relevant, so strict minimisation can degrade results or require repeated operator intervention.
- Minimisation at collection does not address inference: a small, “minimal” dataset can still reveal a great deal when combined with other data (the aggregation problem discussed in §7), and minimised data can be re-identified.
- It says little, on its own, about flows that *are* necessary: a minimal but highly sensitive transmission is still a transmission. That is the gap contextual integrity (§3) and compartment models (§6) aim at.
- Purpose specification can become formalism — purposes written so broadly (“to provide and improve the service”) that they limit nothing.

**Canonical sources.**
- OECD, *Guidelines Governing the Protection of Privacy and Transborder Flows of Personal Data*, OECD/LEGAL/0188 (1980, revised 11 July 2013) — eight principles: https://legalinstruments.oecd.org/api/print?ids=114&lang=en
- GDPR (Regulation (EU) 2016/679), Article 5, full text: https://gdpr-info.eu/art-5-gdpr/
- Cooper et al., RFC 6973, §6.1 on data minimisation as a protocol-design mitigation: https://datatracker.ietf.org/doc/html/rfc6973

---

### 3. Contextual Integrity

**Core idea.** Privacy is not secrecy, and it is not simply control or minimisation: privacy is *appropriate flow*. Helen Nissenbaum argues that an information flow is privacy-respecting when it conforms to the informational norms of the context it occurs in, and a violation when it does not — even if the information was never secret and even if someone clicked “agree.” A flow is analysed through five parameters, all of which must be specified before a judgement can be made: **data subject, sender, recipient, information type, and transmission principle** (the condition on the flow — consent, confidentiality, reciprocity, legal compulsion, purchase, and so on). Contexts — healthcare, family, work, friendship, commerce — have different norms, and the same datum can flow appropriately in one and not another.

**What it would mean for this runner.**
- The governing question per job is not “is this data sensitive in the abstract?” but “would this flow be appropriate given where this information came from?” A message sent to the operator in confidence, a client's file shared for one purpose, and the operator's own notes have different norms attached, even if they sit in the same folder.
- Recipient change is treated as a privacy event in itself: information given to the operator is not thereby information given to a remote AI service, its subprocessors, or its training pipeline. Forwarding is a new flow needing its own transmission principle.
- Design work becomes norm-mapping: for each data type the runner touches, documenting who it is about, where it originated, who may receive it, and under what conditions — and flagging flows that break the originating context's norms for explicit operator decision, rather than silently normalising them.
- Third parties are central, not an edge case: the correspondents in a mailbox never entered any relationship with the runner or the remote service at all.

**Costs and failure modes.**
- Norms are contested, plural, and change over time; reasonable people disagree about what a context's norms are, and a system must still encode *someone's* reading of them. The literature notes this as the main objection to using contextual integrity directly as regulation or as code.
- It is an evaluative framework, not an algorithm: it tells the designer what questions to answer, not what the answers are, so implementation requires judgement, user research, or both.
- It can entrench existing norms: if the prevailing norm in a context is already exploitative, “conform to the norm” is a conservative instruction — a criticism Nissenbaum's own framework handles by evaluating novel flows against a context's purposes and values, but which a mechanical implementation would miss.
- Labelling flows at scale is expensive: real mailboxes and filesystems do not arrive pre-tagged with context, subject, and transmission principle.

**Canonical sources.**
- Nissenbaum, H., “Privacy as Contextual Integrity,” *Washington Law Review* 79 (2004); and *Privacy in Context: Technology, Policy, and the Integrity of Social Life* (Stanford University Press, 2010). Overview and five parameters: https://en.wikipedia.org/wiki/Contextual_integrity

---

### 4. Threat-Model-Driven Privacy: LINDDUN and the Adversary-First / OPSEC Mentality

**Core idea.** Start from adversaries and concrete failure scenarios, not from principles in the abstract: name who might obtain the data, how, and with what effect, then design so that specific, enumerated threats fail or do limited damage. **LINDDUN**, developed at KU Leuven and first published in 2010, is the privacy-specific form of this: a systematic threat-modelling framework whose acronym names seven privacy threat types — **L**inking, **I**dentifying, **N**on-repudiation, **D**etecting, **D**ata disclosure, **U**nawareness, **N**on-compliance — applied to a data-flow diagram of the system, in three flavours of increasing depth (GO, a card-deck workshop method; PRO, a systematic per-interaction analysis; MAESTRO, an enriched-model variant). Alongside formal frameworks sits an older, less formal mentality from operations security (OPSEC) and, in modern enterprise form, zero trust: *assume breach* — assume a device, account, network, or counterparty will eventually be compromised, grant access only on need-to-know, compartment so a single compromise has a small blast radius, and verify each access rather than trusting anything by position.

**What it would mean for this runner.**
- A written threat model for the runner itself, before features: adversaries would explicitly include a compromised or curious remote service, a stolen laptop, malware running as the operator, a malicious or prompt-injected document the runner reads, another job on the same machine, and legal compulsion served on the remote party — alongside the conventional outside attacker.
- LINDDUN-style enumeration applied to the runner's data-flow diagram: e.g. can job outputs be *linked* across runs to build a profile? Can the remote service *identify* third parties in transcripts? Does logging create *non-repudiation* the operator never wanted (an indelible record that a file existed or a message was sent)? Is the mere *detectability* of a job — its timing, size, destination — itself revealing?
- OPSEC habits in operation: separate identities, accounts, and workspaces for sensitive and routine work; per-job credentials and sandboxes; short-lived access; no standing access to the whole filesystem for any single component; encryption and monitoring premised on eventual compromise (the NIST SP 800-207 zero-trust tenets: verify explicitly, least privilege, assume breach).
- The remote service, and the runner's own plug-ins and dependencies, are inside the threat model — a point LINDDUN makes generally: the authorised first party and its own pipelines can be the privacy threat, not only an intruder.

**Costs and failure modes.**
- Threat models are only as good as their enumeration: an unlisted adversary or flow is an unmitigated one, and the method can produce false confidence in proportion to how thorough the document *looks*.
- Adversary-first thinking has no natural stopping point. Taken far, it makes ordinary use cumbersome (separate devices, constant verification, refusal to use convenient channels) and can crowd out usability, collaboration, and the operator's own access to their data.
- It frames privacy as a contest with attackers, which fits some harms (breach, surveillance) and fits others poorly: a flow can be fully “secure” against every adversary and still be inappropriate, excessive, or non-compliant — LINDDUN's inclusion of Unawareness and Non-compliance is an attempt to cover exactly that remainder.
- Compartmentation fails at the joins: a single shared element — an account, an IP address, a writing style, a timestamp — can relink compartments that were carefully separated.

**Canonical sources.**
- LINDDUN project (KU Leuven, DistriNet) — framework, threat types, GO / PRO / MAESTRO: https://linddun.org and https://linddun.org/methods/
- Deng, Wuyts, Scandariato, Preneel & Joosen, “A privacy threat analysis framework,” *Requirements Engineering* 16 (2011) — cited via the LINDDUN site above.
- NIST SP 800-207, *Zero Trust Architecture* (2020) — “never trust, always verify,” assume breach; summary: https://cyberdefenders.org/cybersecurity-glossary/zero-trust-security/

---

### 5. Local-First / Data-Sovereignty Mentality

**Core idea.** The primary copy of the data, and the primary locus of computation and control, is the operator's own machine; the network and the remote party are optional, secondary, and should learn as little as the job strictly requires. The **local-first** movement, named by Martin Kleppmann, Adam Wiggins, Peter van Hardenberg and Mark McGranaghan at Ink & Switch in their 2019 essay *Local-first software: You own your data, in spite of the cloud*, proposes swapping the cloud roles: the local copy is primary, servers hold secondary copies to help with sync and collaboration. Its seven ideals include: no spinners (work at your fingertips), your work is not trapped on one device, the network is optional, seamless collaboration, the Long Now (data outlives the service), security and privacy by default, and “you retain ultimate ownership and control.” In its strongest form for a runner, the mentality is *nothing leaves the machine unless explicitly sent*.

**What it would mean for this runner.**
- Jobs run locally by default; the runner works offline and degrades gracefully rather than failing or quietly uploading more when disconnected.
- What leaves is an explicit, inspectable act: the operator can see the exact payload — prompt, context, attachments — before or as it is sent, per job or per data type, rather than authorising a standing stream.
- Local models, local indexing, local redaction and summarisation are preferred where they are adequate; the remote service is invoked for what local computation cannot do, with the minimum context (§2) rather than the raw corpus.
- Data formats are open and files remain usable without the service, so exit is real: cancelling the remote service loses a capability, not the archive.

**Variants documented in the literature.**
- **Attestation / zero-knowledge-flavoured:** instead of receiving the data, the remote party receives a *proof about* the data or the computation. A zero-knowledge proof lets a prover convince a verifier that a statement is true while the verifier learns nothing beyond the statement's validity (completeness, soundness, zero-knowledge). Applied here: the runner attests “this job ran on these inputs, under this policy, and produced this output hash” — or proves a property of a document (membership, age, a threshold, a match) — without transmitting the document. Costs: only some claims are practically provable this way today, proving is computationally expensive and engineering-heavy, and a proof of a badly chosen statement protects nothing.
- **Capability-based:** authority is not ambient. In the object-capability tradition (Dennis & van Horn 1966; Mark Miller's E language and the Principle of Least Authority, POLA), a component can affect only what it has been explicitly handed an unforgeable reference — a capability — to; there is no global “the process runs as the user, therefore it can read everything.” Applied here: the runner process starts with *no* file authority, and each job is handed capabilities to exactly the files, folders, mailboxes, and network destinations it needs, scoped, revocable, and ideally time-limited (the pattern visible in miniature in runtimes that require explicit `--allow-read` / `--allow-net` grants). Costs: legacy software assumes ambient authority and breaks; capability discipline must be maintained by every component, and a single over-broad capability quietly re-creates the original problem.

**Costs and failure modes (of the mentality as a whole).**
- Local is not automatically safe: the operator's machine becomes the high-value target, and the operator inherits backups, patching, disk encryption, and recovery. Local-first literature itself notes that with ownership comes responsibility for backups and data loss.
- Capability limits are real: the largest remote models cannot currently be run on typical local hardware, so a strict version of this mentality either accepts weaker local results, accepts some transmission, or does not do certain jobs at all.
- Sync and collaboration are the hard part the original essay flags: conflict-free replicated data types (CRDTs) and peer-to-peer sync remain more complex and less reliable than a central server for many uses.
- “Nothing leaves” can be defeated by side channels: outputs, error reports, crash dumps, update checks, and the job result itself all leave, and a result can encode much of what was read.

**Canonical sources.**
- Kleppmann, Wiggins, van Hardenberg & McGranaghan, “Local-first software: You own your data, in spite of the cloud,” Ink & Switch (2019), also at Onward! 2019 — seven ideals explained: https://www.offlineprotocol.com/learning/local-first/seven-ideals-of-local-first-software and https://docs.powersync.com/resources/local-first-software
- Mettler & Wagner, *The Joe-E Language Specification* (2009) — object capabilities, no ambient authority, POLA: https://people.eecs.berkeley.edu/~daw/joe-e/spec-20090918.pdf
- On zero-knowledge private attestation (definition and properties): https://encrypthos.com/term/private-attestations/

---

### 6. Confidentiality / Compartment Models from Information Security

**Core idea.** Label information and people (or processes), and let formal rules on the labels — not ad-hoc judgement — decide every read and write, so that information provably cannot flow from a more sensitive compartment to a less sensitive one, or across a wall it should not cross. The canonical model is **Bell–LaPadula** (Bell & LaPadula, MITRE for the US Department of Defense, 1973), a mandatory-access-control model for confidentiality with classification levels (e.g. Unclassified < Confidential < Secret < Top Secret) plus compartments enforcing need-to-know even at the same level. Its two famous properties are the Simple Security Property — **no read up** (a subject may read only at or below its clearance) — and the *-Property — **no write down** (a subject may write only at or above its level, so secrets cannot be copied into a lower-classified, more widely readable place). The **Brewer–Nash “Chinese wall” model** (1989) adapts the idea to conflicts of interest: datasets are grouped into conflict-of-interest classes, and access is *dynamic and history-dependent* — once a subject has read one company's dataset in a class, a wall rises and every rival dataset in that class becomes inaccessible to them; the write rule prevents laundering information across the wall, and sanitised (de-identified) information is exempt.

**What it would mean for this runner.**
- Everything the runner touches gets a label: e.g. Public / Personal / Confidential / Sealed, plus compartments (Work, Family, Client-A, Client-B, Health, Finance). Jobs, model endpoints, log stores, and output channels also get labels — crucially, the remote AI service has a label, and it is not the highest one.
- No-write-down becomes a concrete egress rule: a job that has read Sealed material cannot write to a channel cleared only for Personal — which, in practice, means it cannot send its transcript, summary, or logs to a less-cleared remote service, store, or collaborator. Declassification (deliberately lowering a label, e.g. by redaction or sanitisation) is a distinct, explicit, auditable act, not something a job does implicitly by summarising.
- Chinese walls between jobs and clients: a runner session that has accessed Client A's files is walled off from Client B's in the same conflict class, and its memory, caches, indexes, and fine-tuning data do not carry across the wall.
- Need-to-know within a level: being cleared for “Work” does not open every work compartment; each job's clearance is per-compartment as well as per-level.

**Costs and failure modes.**
- Rigidity is the design's point and its price: legitimate work constantly wants exceptions (share this one document downward, combine these two compartments), and each exception is either friction or a hole. Real multilevel systems historically struggled with usability and with *covert channels* — information leaking through timing, file existence, error messages, and other paths the label rules do not govern. Bell–LaPadula also addresses confidentiality only: it says nothing about integrity or availability, and a subject may still write *up* and corrupt a higher store.
- Labelling is the hard, unglamorous cost: someone or something must classify a lifetime of accumulated files, and misclassification in either direction breaks the model — too low, and protection fails; too high, and work stops and operators learn to route around the system.
- Summarisation by an AI job is a declassification problem the classic models predate: a “summary” of a Sealed document written to a Personal channel may carry the sealed substance in paraphrase, satisfying the letter of no-write-down while violating its purpose.
- Chinese walls assume conflicts can be enumerated in advance as classes; real conflicts (a friend who joins a rival firm, a client who becomes a competitor) change after access has already happened.

**Canonical sources.**
- Bell–LaPadula — properties, compartments, limitations: https://www.learnsecuritymanagement.com/cissp-bell-lapadula-model ; Cornell CS 5430 mandatory-access-control notes (Bell–LaPadula and Brewer–Nash formal conditions): http://www.cs.cornell.edu/courses/cs5430/2017sp/l/22-mac/notes.html
- Brewer, D.F.C. & Nash, M.J., “The Chinese Wall Security Policy,” *IEEE Symposium on Security and Privacy* (1989) — original paper text: http://www.gammassl.co.uk/topics/chinesewall.html ; summary: https://www.learnsecuritymanagement.com/cissp-brewer-nash-model

---

### 7. Consent-and-Control Models: Privacy as a Dial

**Core idea.** Privacy is, centrally, the individual's claim to determine for themselves when, how, and to what extent information about them is communicated — Alan Westin's 1967 definition in *Privacy and Freedom*, and the intellectual root of notice-and-choice law ever since. On this model the system's job is not to pick the right setting but to provide *meaningful, granular, revocable* settings and to honour them: privacy as a dial the operator turns, from carefree to locked-down, per app, per job, per data type. Westin's own survey research segmented people by where they set the dial — privacy *fundamentalists* (strong protection, opt-in), *pragmatists* (the largest group: they weigh benefit, safeguards, and trust), and the *unconcerned* — which designers cite as evidence that a single fixed posture fits nobody, and a configurable one might fit most.

**What it would mean for this runner.**
- Named modes, honestly described by what they *do*: e.g. **Carefree** (broad local access, full context sent, transcripts retained for convenience), **Standard** (scoped access, payload preview, short retention), **Locked-down** (allowlisted folders only, local processing preferred, no retention, per-job approval of every transmission) — with the ability to go finer-grained than the presets.
- Per-job and per-folder consent rather than a single global toggle: this run may read the project folder; it may not read mail; this one document is approved for the remote service, the rest of the directory is not.
- **Sheltering personal material before a run** — the physical-world pattern this model makes natural, and which operators in many domains already practise with sensitive papers before a visitor arrives: before a broad or carefree job, personal documents are *moved out of scope* — into a vault folder, an encrypted volume, a separate user account, or offline storage that the runner has no path to — so that protection does not depend on the job's software behaving. In dial terms, sheltering is the operator setting the dial for a *place* rather than trusting a setting on the *job*. Its strength is that it works even if every software control fails; its weakness, below, is that it must be remembered every time, and undone afterwards.
- Consent receipts and a legible history: what was approved, when, for which job, and what was actually sent, with revocation that has real effect (deletion, not just a flag).

**Costs and failure modes — including the model's own canonical critique.**
- Daniel Solove's “privacy self-management” critique (*Privacy Self-Management and the Consent Dilemma*, 2013) is directed at exactly this model and is part of its literature, not an external attack: consent does not provide meaningful control at scale, for *cognitive* reasons (people cannot read or understand every notice, or foresee downstream uses) and *structural* reasons (too many entities and decisions; harms arise from aggregation of individually innocuous disclosures over time, which no single consent decision can price). Even a perfectly informed, rational operator, Solove argues, cannot self-manage this way — and the apparent alternative, paternalistic fixed rules, denies the very freedom consent was meant to protect. He calls this the consent dilemma, and does not claim it has a clean solution.
- Dial fatigue and dark patterns: the more granular the controls, the more likely they are set once, in haste, and forgotten; and an interface can steer the dial (pre-ticked boxes, asymmetric friction) while formally offering choice.
- The dial only governs the operator's *own* information legitimately. Turning it to “carefree” also exposes correspondents and clients whose information is in scope and who were never offered a dial (§3's point, in this model's vocabulary: consent by the wrong subject).
- Modes leak at the edges: a locked-down job followed by a carefree one over the same index, cache, or transcript store can undo the first job's posture, unless modes also partition storage (§6's compartments are one way dials get teeth).

**Canonical sources.**
- Westin, A., *Privacy and Freedom* (1967) — definition, and the fundamentalist / pragmatist / unconcerned segmentation: https://iapp.org/news/a/2013-02-19-westins-privacy-scholarship-research-influenced-a-generation
- Solove, D.J., “Privacy Self-Management and the Consent Dilemma,” *Harvard Law Review* 126 (2013) 1880 — abstract and argument: https://scholarship.law.gwu.edu/faculty_publications/936/

---

### 8. Radical Transparency / The Nothing-to-Hide Counter-Mentality

**Core idea.** This is the counter-position, documented here on the same terms as the others because some operators genuinely choose it: secrecy is either unattainable, or a price not worth paying, or actively harmful — so openness is the better strategy. It has two related forms. The everyday form is the **“nothing to hide”** stance: a person who has done nothing wrong, the argument runs, has nothing to fear from observation or disclosure, and the convenience, safety, and quality gained by sharing freely outweigh a privacy interest that, on this view, mainly shelters wrongdoing. The systematic form is David Brin's **reciprocal transparency** in *The Transparent Society* (1998): surveillance technology is inevitable and the powerful will have it regardless; the real choice is between surveillance monopolised by elites and surveillance distributed to everyone — so freedom is better served if information flows openly in *both* directions, citizens can watch the watchers (*sousveillance*), and mutual accountability replaces mutual secrecy. Brin's formulation is explicitly not “only the powerless should be open”: its condition is reciprocity.

**What it would mean for this runner.**
- The operator runs the runner carefree by conviction, not by inattention: full local access, rich context sent to the remote service for better results, transcripts and logs retained and even published — e.g. public work logs, open job histories, shared prompts — on the reasoning that auditability and showing one's work are worth more than concealment, and that anyone may inspect the record.
- Transparency is applied to the *system* as well as the operator: the runner's code, data flows, and the remote service's handling are demanded open and inspectable, on Brin's logic that openness upward (toward the powerful party) is the point of openness downward.
- Practical corollaries: no effort spent on redaction, compartmentation, or local-only processing; security effort, if any, is redirected to integrity and authenticity (is this record accurate and untampered?) rather than confidentiality.

**Costs and failure modes — as documented by its critics and, in part, its proponents.**
- **Irreversibility and context collapse:** disclosed information cannot be undisclosed, and it travels to contexts and recipients its disclosure did not contemplate (§3); a posture that is safe under today's norms, employer, or government may not be under tomorrow's.
- **Asymmetry in practice:** Brin's version depends on reciprocity actually holding. Where the remote service, platform, or state remains opaque while the operator is transparent, the mentality delivers the exposure without the accountability that was its justification — its critics' central objection, and a condition Brin himself frames as the bad outcome.
- **Third parties again, in sharpest form:** the operator's openness discloses correspondents, clients, and family who did not choose it. “Nothing to hide” is a claim a person can make about their own life; the contents of a mailbox are partly other people's lives.
- **The critics' conceptual objection:** Solove's *Nothing to Hide* (2011) argues the stance rests on a narrow definition of privacy as concealing wrongdoing, and has nothing to say about harms that involve no secret and no wrongdoing — aggregation and profiling, misinterpretation and error, exclusion from decisions made about you, chilling effects on thought and association, and loss of autonomy under observation. Schneier and others add that privacy in this literature is treated as a precondition for dissent, intimacy, and experimentation, not only as a hiding place.
- **Chilling effects are empirically documented** in the post-2013 literature (e.g. measurable drops in readership of sensitive topics after surveillance revelations), which this mentality must either discount or accept as a cost.

**Canonical sources.**
- Brin, D., *The Transparent Society: Will Technology Force Us to Choose Between Privacy and Freedom?* (1998) — thesis and reciprocal transparency, panel summary: https://discourse.net/archives/2008/05/cfp_08_accepts_our_panel_on_the_transparent_society.html
- The nothing-to-hide argument and its principal critics (Solove, *Nothing to Hide: The False Tradeoff Between Privacy and Security*, Yale UP 2011; “Why Privacy Matters Even if You Have ‘Nothing to Hide’,” 2011): https://en.wikipedia.org/wiki/Nothing_to_hide_argument

---

### 9. Further Mentalities I: Privacy as Dignity and Autonomy, and the IETF Engineering Positions

These two belong together in the literature's own history — the second is, in large part, the first translated into engineering-community commitments after 2013 — but they are distinct mentalities and are documented separately.

#### 9a. Privacy as dignity, autonomy, and personhood

**Core idea.** Privacy protects something more fundamental than secrets or data flows: the “inviolate personality.” Warren & Brandeis's foundational “The Right to Privacy” (*Harvard Law Review*, 1890) argued for a “right to be let alone” grounded in dignity — the interest in determining for oneself how much of one's thoughts, feelings, and inner life is communicated — and later writers (Bloustein in 1964; the personhood strand in Solove's 2002 survey of six conceptions of privacy, alongside right-to-be-let-alone, limited access, secrecy, control, and intimacy) read all privacy invasions as sharing one wrong: a violation of human dignity and individuality. On this view privacy is a precondition for autonomy: for forming opinions, experimenting, associating, and dissenting without the deformation that being watched produces — regardless of whether any particular datum is sensitive, and regardless of consent forms signed.

**For this runner.** The test of a job is not only what it sends but what it *does to the operator's (and their correspondents') freedom to think and act*: does routine reading of drafts, journals, unsent messages, and private correspondence — even locally, even “only” by a model — create a standing sense of being observed that changes what gets written down at all? Design responses in this mentality include hard exclusions that are not the operator's to waive casually in the moment (diaries, unsent drafts, privileged correspondence treated as out-of-scope by the system's constitution, not by a per-job toggle), and scepticism toward any framing in which a single click legitimises unlimited reading.

**Costs and failure modes.** Dignity and autonomy are hard to operationalise or measure, so the mentality gives strong reasons and weak specifications: it rarely tells an engineer exactly which file may be read. Invoked without specification it can block useful work on the basis of an undefinable harm; and its strongest historical claims (a *right*) sit uneasily in a self-hosted, single-operator setting where the right-holder, the operator, and the would-be reader's owner are the same person — the live question becomes whether it binds the operator's present self against their future or hurried self, and third parties are where it retains clearest force.

**Sources.** Warren & Brandeis (1890) and the dignity/autonomy tradition: https://negd.gov.in/blog/the-right-to-privacy-history-philosophy-and-law/

#### 9b. The IETF positions: RFC 6973 and RFC 7258 (post-Snowden engineering culture)

**Core idea.** After the 2013 Snowden disclosures — discussed at the IETF's November 2013 technical plenary — the Internet's engineering community recorded two consensus positions. **RFC 7258** (Farrell & Tschofenig, May 2014, Best Current Practice 188) states it in its title: *“Pervasive Monitoring Is an Attack.”* Pervasive monitoring is defined as widespread, often covert, indiscriminate, large-scale gathering of protocol artefacts, including content and metadata; the IETF's technical assessment is that it is an attack on privacy that protocol design should mitigate where possible, by making it significantly more expensive or infeasible — without requiring proof of malicious intent by the monitor. **RFC 6973** (Cooper et al., IAB, July 2013) is the working companion: a *Privacy Considerations* method for protocol designers, with a shared vocabulary (anonymity, pseudonymity, identifiability, correlation, fingerprinting), a threat catalogue that goes beyond confidentiality (surveillance, stored-data compromise, intrusion, correlation, identification, secondary use, disclosure, exclusion), mitigations grouped as data minimisation, user participation, and security, and a set of design questions (§7) every specification should be able to answer about what it exposes, to whom, for how long, and why.

**For this runner.** Treat *metadata and artefacts* as first-class privacy material, not just file contents: job timing, sizes, destinations, file names, directory structure, and access patterns are exactly the “protocol artefacts” RFC 7258 names, and they leak to network observers and to the remote service even when contents are encrypted. Encrypt in transit by default, pad or batch where timing/size would identify the job, minimise persistent identifiers across jobs so runs cannot be correlated, and write a 6973-style Privacy Considerations section for the runner itself — who can observe what, which joins are possible, how long each artefact survives, and what the defaults do. The mentality is institutional rather than individual: privacy is defended by making collection expensive *at scale and by default in the protocol*, not by each operator's vigilance.

**Costs and failure modes.** These are consensus *positions and guidance*, not mechanisms: RFC 7258 declares an attack and a direction of work but specifies no protocol, and RFC 6973 is explicitly Informational and a questionnaire, not a score — a design can answer every question honestly and still expose a great deal. Encryption-by-default, the culture's main practical fruit, protects content in transit and does progressively less against an endpoint (the remote service itself) that is authorised to read the content — the two RFCs are aimed primarily at third-party pervasive monitors, and a runner whose recipient is the concern needs §5's or §6's tools as well. Making collection “more expensive” is also a deliberately modest goal: it accepts that a targeted, resourced adversary will succeed.

**Sources.** RFC 7258: https://datatracker.ietf.org/doc/html/rfc7258 and https://www.rfc-editor.org/info/rfc7258 ; RFC 6973: https://datatracker.ietf.org/doc/html/rfc6973

---

### 10. Further Mentalities II: Obfuscation

**Core idea.** When you cannot prevent observation — you lack the power to opt out, refuse the system, or win the argument — you can still degrade it: *obfuscation* is “the deliberate addition of ambiguous, confusing, or misleading information to interfere with surveillance and data collection.” Finn Brunton & Helen Nissenbaum's *Obfuscation: A User's Guide for Privacy and Protest* (MIT Press, 2015) frames it, following James C. Scott, as a *weapon of the weak*: incremental, subversive resistance for “the small players, the humble, the stuck,” intended to buy time, raise the observer's costs, create plausible deniability, or simply protest. Their own tool TrackMeNot, for example, issues decoy search queries so a query log does not cleanly reveal its user.

**For this runner.** A runner in this mentality might salt what it sends or logs: decoy files and decoy jobs mixed with real ones; noise added to telemetry and timestamps; query and context padding so that the remote service's log of requests does not cleanly reconstruct the operator's interests, projects, or correspondents; plausible alternative versions of summaries. The aim is explicitly *not* clean secrecy — it is to make the record unreliable enough that profiling, confident inference, and casual inspection fail or become expensive.

**Costs and failure modes.** The book and its reviewers are candid that obfuscation is a weak, messy, temporary tool, not a replacement for governance or strong technical protection: determined analysis can often filter noise, noise must be statistically plausible to work and plausible noise about real people can create false records *about real people* (with reputational and, in a work setting, integrity consequences — a decoy file that a colleague or a future job treats as real is a hazard, not a shield). It can violate the terms or expectations of the counterparty, it pollutes the operator's own archive and search results, and its protection is hard to verify: you rarely learn whether it worked. Reviewers also note the political ambiguity its authors acknowledge — a tactic of the weak can be adopted by the strong, and normalising noisy records has costs for everyone's ability to trust records at all.

**Sources.** Brunton & Nissenbaum (2015), reviewed: https://issues.org/book-review-hiding-in-plain-sight/

---

### 11. Further Mentalities III: Privacy as a Collective and Social Good

**Core idea.** Privacy is not only an individual possession to be traded one consent at a time; it is a common, public, and collective value. Priscilla Regan's *Legislating Privacy* (1995), chapter “Privacy and the Common Good,” argues the philosophical basis of privacy policy overemphasises the individual: privacy is a *common* value (all individuals value some of it, in similar ways), a *public* value (democratic processes depend on it — on citizens who can read, meet, organise, and form views unobserved), and increasingly a *collective* value, because technology and markets make it hard for any one person to have privacy unless a similar minimum is available to all (one person's disclosures expose their contacts; one holdout's data still trains the model that profiles everyone).

**For this runner.** Decisions are evaluated at group level, not only per-operator: what happens if *every* operator of such runners sends full mailbox context to remote services by default? Defaults, norms, and shared infrastructure (open local models, shared redaction tools, community standards for what runners may read) become privacy interventions in themselves, and an operator's choice is understood to affect people who run nothing at all — correspondents whose messages are ingested by *other people's* runners. A corollary in this literature is scepticism that purely individual remedies (one person's settings, one person's lawsuit) can secure a collective good, and corresponding interest in collective remedies: regulation, professional norms, and platform-level defaults (§1 and §2 in their legal forms are partly this mentality institutionalised).

**Costs and failure modes.** Collective framings can override the individual in both directions: they can justify restricting an operator who genuinely wants to share (§8's operator has a claim here that this mentality must answer), and “society benefits” is as elastic a justification, in careless hands, for restricting privacy as “security” is in others'. The mechanism design is unresolved: if privacy is a public good, it is subject to free-riding, and the literature offers more diagnosis (why individual markets and consents under-produce it) than settled prescription for a single software project. For a lone operator it can also feel actionless — its clearest implications are about defaults and norms shared across many deployments, not about tonight's job.

**Sources.** Regan (1995), “Privacy and the Common Good,” revisited summary (Berkeley Law, PLSC 2013): https://sites.law.berkeley.edu/privacylaw/2013/05/28/priscilla-m-regan-privacy-and-the-common-good-revisited/

---

### A note on an engineering vocabulary that cuts across several models

Jaap-Henk Hoepman's eight **privacy design strategies** (2014) are not a separate mentality but a widely used bridge from the models above to architecture, and project documentation often cites them alongside Cavoukian: data-oriented strategies **MINIMISE, HIDE, SEPARATE, AGGREGATE** (abstract) and process-oriented strategies **INFORM, CONTROL, ENFORCE, DEMONSTRATE**. A runner described in this vocabulary might, for example, minimise its reads, hide transmissions with encryption, separate compartments' stores, aggregate results before sending, inform the operator of each payload, give them control, enforce the stated policy in code rather than in prose, and be able to demonstrate compliance from logs. Source: Hoepman, “Privacy Design Strategies,” https://arxiv.org/pdf/1210.6621

---

## Comparison Table

| # | Model / mentality | Optimises for | Sacrifices / deprioritises | What the runner does differently |
|---|---|---|---|---|
| 1 | Privacy by Design + by-default | Protection without operator effort; privacy built in from the start | Designer must choose for everyone; specific behaviour under-determined by the principles | Ships locked-down by default; documented data inventory, lifecycle and deletion rules; verifiable behaviour |
| 2 | Data minimisation / collection limitation (OECD, GDPR Art. 5) | Collecting/retaining/sending only what a stated purpose needs | Capability and serendipity; results that need broad context; ease of “just read everything” | Per-job scoped reads; sends summaries/redactions, not raw corpora; expiring logs and transcripts; no secondary use |
| 3 | Contextual integrity | Flows that match the norms of the context data came from | Simplicity and uniform rules; speed of automated decisions about novel flows | Treats change of recipient (esp. to the remote service) as a new flow needing justification; maps subject/sender/recipient/type/transmission principle per data type |
| 4 | Threat-model-driven (LINDDUN + OPSEC / assume-breach) | Resilience against named adversaries; small blast radius when (not if) something fails | Convenience; trust in any component, including the remote service and the runner itself | Written threat model incl. curious/compromised remote party and prompt-injected documents; compartments, per-job credentials, sandboxes, need-to-know |
| 5 | Local-first / data sovereignty (+ ZK attestation, capabilities) | Operator ownership; nothing leaves unless explicitly sent; exit without losing the archive | Access to the largest remote models; easy sync/collaboration; operator takes on backup/security burden | Local computation and storage primary; explicit, inspectable payloads; jobs handed scoped, revocable capabilities instead of ambient file access; proofs/attestations instead of data where feasible |
| 6 | Bell–LaPadula / classification + Chinese walls | Provable non-flow from sensitive to less-sensitive compartments; conflict-of-interest separation | Flexibility; ease of legitimate sharing and combining; labelling effort | Labels on data, jobs, stores and the remote endpoint; no-write-down egress rule; explicit auditable declassification (e.g. redaction); walls between clients/jobs |
| 7 | Consent-and-control (privacy as a dial) | Operator autonomy; fit to differing preferences (fundamentalist→unconcerned) | Protection for those who set the dial hastily, tiredly, or under steering; protection of third parties | Named modes carefree→locked-down, per-job/per-folder approvals, consent history and revocation; sheltering personal material out of scope before broad runs |
| 8 | Radical transparency / nothing-to-hide | Accountability, auditability, convenience, better results from full context; (Brin) checking the powerful | Confidentiality, reversibility, third parties' privacy; safety under changed future norms | Full access and rich transmission by conviction; open logs/records; demands reciprocal openness from the remote service; security effort goes to integrity, not secrecy |
| 9a | Dignity / autonomy | An unobserved inner life; freedom to form thoughts, associate, dissent | Operational precision; some useful processing of intimate material | Constitutional exclusions (diaries, drafts, privileged correspondence out of scope by default); asks what observation itself does to behaviour, not only what is sent |
| 9b | IETF engineering positions (RFC 6973, RFC 7258) | Making pervasive, indiscriminate collection expensive at scale; shared design discipline | Guarantees against a targeted adversary or an authorised recipient who reads content | Encrypts by default; treats metadata/artefacts (timing, size, names, identifiers) as privacy material; correlation-resistant identifiers; a written Privacy Considerations section for the runner |
| 10 | Obfuscation | Degrading unavoidable observation; deniability; protest; buying time | Record reliability and integrity; verifiability; cleanliness of one's own archive | Decoy files/jobs, padded/noisy telemetry and requests, so logs and profiles do not cleanly reconstruct interests or contacts |
| 11 | Privacy as collective / social good | A minimum level of privacy for everyone, incl. non-users; democratic preconditions | Pure individual freedom to waive or sell one's own (and, in effect, others') privacy | Evaluates defaults at population scale; invests in shared norms, standards and local tooling; counts effects on correspondents and on other operators' subjects |

---

## Closing Note — No Position Taken

**This survey takes no position on which of these models or mentalities is best, and it should not be read as recommending any of them, singly or in combination.** Each section documents a position as its own literature presents it, including the costs and failure modes that literature itself records — several models (§§2–3, 5–7) contain internal critiques of other models in this survey, and §8 is included precisely because it contradicts most of the others; those disagreements are part of the record, not a problem this document resolves. Models are also not mutually exclusive in practice — real systems commonly combine, for example, minimisation with compartments, or local-first architecture with a consent dial — and the fact that a combination is common is reported here as an observation, not as an endorsement. Choosing among these positions, or weighting them, is a decision for the project's operators and documentation authors, in light of their own circumstances, obligations, and values.

---

## Could Not Verify

- **No product-specific claims were verified.** This survey is about published models and mentalities; it does not audit any actual runner implementation, remote AI service, or their current (November 2026) defaults, retention, or terms.
- **Book publication years vary by one year in some secondary listings** — e.g. Nissenbaum's *Privacy in Context* is listed as 2009 in some sources and 2010 in others (first publication / US edition difference). The report gives 2010 and notes the work originates in the 2004 article, on which sources agree.
- **Primary PDFs behind paywalls or legacy URLs** (notably Cavoukian's original IPC PDF and Brewer & Nash's 1989 paper as originally published) were verified through the texts and principle lists reproduced in multiple independent secondary sources and, for Brewer & Nash, a full-text reproduction; wording of individual principles was cross-checked across at least two sources in each case.
- **The mission's “sheltering” pattern** (moving personal documents out of scope before a run) has no single canonical named source in the privacy literature found; it is documented in §7 as an operator practice that the consent-and-control and compartment models both predict and describe in their own terms, rather than as a named framework.

---

## Sources

All URLs copied verbatim from search results, read 2026-11-08 via the web index.

**Privacy by Design / GDPR Art. 25**
- https://en.wikipedia.org/wiki/Privacy_by_design
- https://www.ipc.on.ca/en/media/1369/download?attachment
- https://www.thesedonaconference.org/sites/default/files/conference_papers/Recommended%20%5B08b%5D%20Privacy%20By%20Design_Cavoukian.pdf
- https://www.legiscope.com/blog/implementing-privacy-by-design.html

**Minimisation — OECD / GDPR Art. 5**
- https://legalinstruments.oecd.org/api/print?ids=114&lang=en
- https://gdpr-info.eu/art-5-gdpr/

**Contextual integrity**
- https://en.wikipedia.org/wiki/Contextual_integrity

**LINDDUN / zero trust**
- https://linddun.org
- https://linddun.org/methods/
- https://linddun.org/linddun/whyuselinddun/
- https://cyberdefenders.org/cybersecurity-glossary/zero-trust-security/

**Local-first / capabilities / zero-knowledge attestation**
- https://www.offlineprotocol.com/learning/local-first/seven-ideals-of-local-first-software
- https://docs.powersync.com/resources/local-first-software
- https://people.eecs.berkeley.edu/~daw/joe-e/spec-20090918.pdf
- https://encrypthos.com/term/private-attestations/

**Bell–LaPadula / Chinese wall**
- https://www.learnsecuritymanagement.com/cissp-bell-lapadula-model
- https://www.learnsecuritymanagement.com/cissp-brewer-nash-model
- http://www.cs.cornell.edu/courses/cs5430/2017sp/l/22-mac/notes.html
- http://www.gammassl.co.uk/topics/chinesewall.html

**Consent-and-control**
- https://iapp.org/news/a/2013-02-19-westins-privacy-scholarship-research-influenced-a-generation
- https://scholarship.law.gwu.edu/faculty_publications/936/

**Transparency / nothing-to-hide**
- https://en.wikipedia.org/wiki/Nothing_to_hide_argument
- https://discourse.net/archives/2008/05/cfp_08_accepts_our_panel_on_the_transparent_society.html

**Dignity/autonomy; IETF; Hoepman; obfuscation; collective good**
- https://negd.gov.in/blog/the-right-to-privacy-history-philosophy-and-law/
- https://datatracker.ietf.org/doc/html/rfc6973
- https://datatracker.ietf.org/doc/html/rfc7258
- https://www.rfc-editor.org/info/rfc7258
- https://arxiv.org/pdf/1210.6621
- https://issues.org/book-review-hiding-in-plain-sight/
- https://sites.law.berkeley.edu/privacylaw/2013/05/28/priscilla-m-regan-privacy-and-the-common-good-revisited/
