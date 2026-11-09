# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# cs_office — the vulnerability-research workstream

Marking: hp0.

cs_office is the vulnerability-research workstream of the Homing
Pigeon suite: the part of the project that looks for defects in
software, this suite's own surfaces included, and reports what it
finds through the channels the software's owners provide. The name
is the workstream's settled public name — lowercase, with the
underscore, named for the Counter-Strike map. Its tagline is the
question [What is a bug bounty program?](../../../docs/ENTERPRISE.md)
carries, and the README's links list points at the same page.

The workstream lives inside the suite rather than beside it. The
research runs on the suite's own machinery — jobs, runners, and
the record-keeping the rest of the project uses — and where the
research needs a capability the suite lacks, the capability is
built as a small extension into Homing Pigeon itself, reviewed and
tested like any other part of the tree. The workstream is not an
orphan tool bolted on the side; it is one of the things the suite
is for.

cs_office keeps its own forum at
docs/infrastructure-documents/project/cs_office.com.chat,
beside this page. cs_office documentation and announcements
are posted to both that forum and the seats' forum
(docs/infrastructure-documents/seats/.com.chat).

## The method

The method is general practice, stated plainly:

- **Coverage-guided fuzzing.** Inputs are generated and mutated
  against instrumented builds, and the coverage each input reaches
  decides what the corpus keeps. The corpus is the asset: seeds
  that reach new code stay, and a crash is reproduced from the
  input that caused it before anything else is believed.
- **Regression fuzzing.** Published vulnerabilities and their
  patches are inputs. A patch states where a defect class lived;
  the patched code, and the code around it, is then tested for the
  class returning — in the same place, in a sibling path, or in
  the next version. A fix that holds is a result; a fix that does
  not is a finding.
- **Parsing-surface testing, read against the OWASP categories.**
  Every surface that parses untrusted input — paths, encodings,
  lengths, types — is read family by family against the OWASP
  lists this project keeps on its security shelf
  ([the OWASP reference](../security/owasp-reference.md)). The
  shelf names the categories; the testing applies them.
- **Crash triage.** Every crash the runs produce gets the same
  treatment: replay, automated classification, bucketing against
  earlier crashes, and minimization to the smallest input that
  still reproduces it. The triage record — what class of crash,
  how severe the classifiers rate it, whether it reproduces from
  the minimized input — is what a human reads to decide what a
  crash is worth. Counts and statistics are kept across runs, so
  the workstream states what it ran and what it found in numbers.

One counting convention is policy, stated once so every record
of the proving work reads the same way: where the workstream
sizes or sequences its proving runs by the Fibonacci numbers,
the sequence starts at 0 — F(0) = 0, F(1) = 1. Fibonacci
numbers in the workstream's records always use that indexing.

## Industry practice

The workstream follows the disclosure practice of the industry it
works in:

- Research runs only inside the rules of the relevant bug bounty
  program, or inside the license and terms of the software under
  examination. Where no program or permission covers a system, the
  workstream does not test that system.
- Testing stays on machines and accounts the workstream owns, or
  is authorized to use, under the program's stated scope.
- A finding is reported through the program's formal channels, to
  the software's owner, with the minimized reproducer and the
  triage record. Nothing is disclosed publicly until the owner has
  patched it and the disclosure is agreed.
- The work finds and reports defects. It does not develop
  exploits, and it does not weaponize findings — no proof is built
  past the minimized crash that demonstrates the defect.
- Enrollment in a bug bounty program is a legal agreement, and it
  is a human decision. No agent enrolls the project, or anyone, in
  a program; no agent submits a report. Agents find, triage, and
  draft; a human judges, enrolls, and submits.

One part of the work is public by declaration: an open-source
track. The workstream's operator is a security engineer with a
cryptography background, and the track is the ordinary work of
finding defects in public open-source code and helping to harden
it — GnuTLS is one of the projects it covers, and it is named
here because the track is meant to be visible. The testing
itself, and everything it produces, stays guarded under the
constraints this project documents — the two shelves set out on
this page and the spillage rules in SECURITY.md: findings and
crash data live on the private shelf, reports run through each
project's formal channels only, nothing about a finding is
public before it is patched, and anything examined under a bug
bounty program is never named, only carried by label. The
open-source track is the workstream's public face, and it is
the only one.

## Sensitivity markings and code names

A sensitivity marking is a short token that prefixes a
document, a forum entry, a work item, or a file name:

- hp0 = public, releasable anywhere, the zero-sensitivity
  floor.
- hp1 = the public repository, with care — method,
  principles, labels; reviewed before it lands.
- hp2 = the private shelf only — the label mapping, case
  material.
- hp3 = never written outside its case file — unfixed
  findings, crash data.

Work items are referenced by code name, in the form
hp<marking>-<guid>: the marking token, a hyphen, and a
GUID that carries no information. Sub-names append a
suffix, as -a, -b, and on, and name components of one work
item. A reference's meaning lives on the private shelf,
while the reference itself is safe to print at its
marking. New public writing uses code names for work items
instead of descriptive names where a description would
narrow anything.

## For agents working in this repository

This section is the boundary every agent in this repository works
inside. cs_office has two shelves, and an agent decides which shelf
a fact belongs on before writing it anywhere public.

**The public shelf** — what may live in this repository, in docs,
code, issues, pull requests, commit messages, and release notes:

- the name cs_office and the tagline;
- the method and the principles, as stated on this page;
- general techniques and general security material;
- counts and statistics — how many seeds, how many executions,
  how many crashes, stated as numbers.

**The private shelf** — what never goes in this repository, in any
form, including commit messages and release notes:

- the identity of anything being examined — no target named, no
  case named or numbered;
- case files, and anything that identifies a case;
- an unfixed finding, in any detail — its existence, its
  location, its severity;
- crash data and crash artifacts — the inputs, the dumps, the
  minimized reproducers, the triage records of a live case.

Public writing refers to anything under examination by label
only: Target A and Target B. The labels identify nothing — they
carry no name, no product, no company, no detail — and no public
writing attaches any of those to a label, or states anything that
narrows what a label points at. The mapping from a label to what
it labels sits on the private shelf, with the rest of the
private material.

The private shelf lives outside this repository, and this page
does not name where. When in doubt, the rule is: keep it out, and
put the question in the questions file
(`docs/steady/seats/questions.md`), where the conductor answers
it. A fact that turns out to belong on the public shelf can be
moved later; a fact published from the private shelf cannot be
unpublished.

If material crosses anyway, the crossing is spillage, and the
response defined in SECURITY.md — the section "Spillage: when
private material is published" — governs it end to end: the
crossing is declared on the alert path at once, the material is
contained and purged, whatever it exposed is rotated or notified
as its class requires, and the incident is put on the public
record in general terms. Removal alone is never the response, and
a crossing that is quietly deleted instead of declared is the one
failure this project ranks worse than the crossing itself.
