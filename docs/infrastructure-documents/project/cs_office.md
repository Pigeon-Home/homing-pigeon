# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# cs_office — the vulnerability-research workstream

cs_office is the vulnerability-research workstream of the Homing
Pigeon suite: the part of the project that looks for defects in
software, this suite's own surfaces included, and reports what it
finds through the channels the software's owners provide. The name
is the workstream's settled public name — lowercase, with the
underscore, named for the Counter-Strike map. Its tagline is the
question [What is a bug bounty program?](../../../ENTERPRISE.md)
carries, and the README's links list points at the same page.

The workstream lives inside the suite rather than beside it. The
research runs on the suite's own machinery — jobs, runners, and
the record-keeping the rest of the project uses — and where the
research needs a capability the suite lacks, the capability is
built as a small extension into Homing Pigeon itself, reviewed and
tested like any other part of the tree. The workstream is not an
orphan tool bolted on the side; it is one of the things the suite
is for.

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
