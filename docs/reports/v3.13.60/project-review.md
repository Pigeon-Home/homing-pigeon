# Project review — homing-pigeon @ 3.13.60

<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->

> **Status:** a dated record, at the conductor's word (2026-10-26).
> Every finding below was either fixed in the commits named or is
> listed under "Still open" with who holds it. Later edits on main
> move things; read the current tree before acting on a line here.

**Baseline:** main at `2642bb02` (version 3.13.60, 2026-10-26).
**Scope:** every living document checked against the code it
describes: the six root manuals, PROTOCOL.md and the two
Internet-Drafts, `docs/use/`, `docs/oracle/`, `docs/extend/` with
the 28 sense READMEs, `docs/security/` with the hardening templates,
`docs/design/`, `docs/project/`; the 19 workflows and the suite's
health; the coordination files (questions, stamps, branches). Not
re-audited, by standing rule (AGENTS.md rule 6): `ENTERPRISE.md`,
`docs/CHANGELOG.md`, `docs/reports/**`, `docs/archive/**`.
**Method:** six readers, one per slice, each holding every sentence
that states a current fact to the code line that makes it true
(paths, config keys, CLI flags, numbers, status banners), with the
findings verified again against the files before any edit; a
mechanical pass over every relative link, backticked repository path
and GitHub tree URL in the 83 living documents; the suite and the
workflows read as facts.

## The numbers

About 1,300 claims were checked; about 1,180 held as written. The
118 that did not, by class:

| Class | Count | Meaning |
|---|---:|---|
| WRONG | 15 | the code does something else |
| STALE | 28 | was true, the code moved on |
| BROKEN COMMAND | 6 | a documented command, flag or key the code does not accept |
| DEAD LINK | 14 | a pointer at a file, section or list entry that does not exist |
| MISLEADING | 24 | true as written, read wrong |
| NIT | 31 | a count, a name, a missing row |

Every link, path and GitHub URL in the living docs resolves (three
names of retired files are inside sentences that say so). The
coordination files are in order: three questions open (Q56 for the
conductor, since closed; Q54 and Q57 for Grok), every stamp in the
tree on the record, and the remote carries one branch, `main`.

## What the review found in the code

Four of the findings were not documentation.

1. **An allowlisted key could run arbitrary remote code.** Under
   `key_policies.<id>.allowed_script_sha384` the policy refused a
   job with no inline script, but a job carrying an allowlisted
   `script` *and* a `script_url` passed, and the executor stages the
   URL first. PROTOCOL.md section 14 already said `script_url` is
   not permitted under such a policy; the code says so now
   (`runner/wire/verify.py:check_key_policy`, pinned in
   `test_multi_secret`). Fixed in `ea3168e7`.
2. **`send_dtls.py` sent cleartext by default.** `--encrypt`
   (store_false) and `--cleartext` (store_true) share one dest, and
   argparse's default for the group was the last action registered,
   so a bare invocation parsed `cleartext=True` and skipped the
   envelope. The default is pinned to encrypt; a test drives `main()`
   with no flag. Fixed in `ea3168e7`.
3. **The wheel shipped the build tools and the sense extensions.**
   `pyproject.toml` excluded only `runner.tests*`; namespace
   discovery carried `runner/tools/` and `runner/extensions/*/*.py`
   (57 packages, no manifests, nothing that could load) into the
   published wheel, against AGENTS.md. Excluded now, the transports
   kept. Fixed in `ea3168e7`.
4. **Main was red, and the release train stopped on it.** A fuzz
   corpus arc map was committed with its last row out of order, and
   `test_bluemonday_corpus` asserts the map sorted, on every leg.
   Rewritten through the tool's own writer; the 3.13.60 tag could
   proceed. Fixed in `850a2d99`.

Two more in CI, found by the readers and fixed the same day: a
private-module import the type gate could not resolve (the desk's
fix landed first), and a shape test using 3.11-only regex syntax
that the 3.9 and 3.10 legs could not compile (`b36df387`).

## What the documents said that the code did not

The headline corrections, by area. The commits carry the full
list; each batch's message names every line.

**Security and design** (`79a78b47`). `safeguards.md` and the
README said a missing `bwrap` under `enforce` let the job run
unsandboxed and audited the fallback; since Q9 the runner refuses
to start, and the posture line said "would run unsandboxed" too.
The SELinux template commented with `!` and named a build command
(`checkmodule`) that cannot expand the reference-policy interfaces
it uses: comments are `#` now and the README gives the refpolicy
Makefile. The hardened systemd unit set `RestrictNamespaces=true`,
which stops the very confinement the README promised beside it: the
unit now allows the five namespaces bwrap needs, with the AppArmor
profile's limits stated instead of papered over. `ci-runtime.md`
described a mutation job on tags, a weekly seeded run and a build
that cancels its predecessor; none of the three holds. The stamp
design note said nothing enforced it; `test_agent_stamps` does.
Four pointers into `future.md` named entries that were not there
(the approval gate is listed now; the others are redirected).

**Extensions** (`79a78b47`). `docs/extend/transports.md` ended
mid-sentence: a commit had cut 184 lines, including the whole
"Writing a new transport" section, so the transport manifest,
the `{channel_dir}` tokens, the inbox/outbox channel and the
supervisor's backoff were documented nowhere. Restored, with the
two things it never had (`startup_settle_ms`, the `reply_to`
sidecar) and the hosted queue as the fifth shipped pipe in the
comparison. The Queues section described two named queues that
were never built where a Durable Object ships. Fifteen READMEs
presented `poll_interval_sec` as a knob "the code implements" or
"how often the runner wakes the sense"; the runner never runs
sense code and nothing reads the key, so it is named as the one
advisory knob everywhere. The catalog counted a sense twice; osquery
was called Pi Light's default collector (Pi Light installs none);
two READMEs promised wakes their medium signals cannot cause.

**Root manuals, docs/use, docs/oracle** (`65d4a405`). The README's
`--cleartext` was the sender's flag described as the runner's; the
installer was named at a path it no longer has; `--additional-secret`
was said to write a `key_policies` entry it does not; the host CLI's
`redeploy` and `rotate` lines were missing the required `--token-env`
(the docstring too); `--arg --verbose` fails argparse; `--local-test`
was said to hot-reload (it holds its config); Signal and WhatsApp
were "listed in future.md" (they are refused, not planned); the
profile whitelist, the override table, the review's built-in ids,
the release archive list and the hot-reload list were each short.

**Project docs and CI** (`e347e100`). `testing.md` said every
platform is proven on a real kernel; the FreeBSD leg has failed on
all nine of its runs, so its row says so. The campaign playbook's
hard rules were superseded by the standing orders' queues P and M.
Four workflows were outside the CI guard's registry, two of them
with write permissions at the top level; every workflow is
registered and the writes are granted per job under a default-deny
top.

**PROTOCOL.md and the drafts** (`e7d96f23`). The audience claim the
reference signs is `aud`, with `runner_id` its older spelling; the
spec named only the old one. `kind` has a third value. The
`attested` view was said to carry the summary's members (it carries
empty streams and no counts); `output_digest` was "untruncated" (it
is over the retained output); the confinement snapshot was said to
watch everything outside the workspace (it walks the workspace's
parent); the verdict's "writes outside the workspace" check is a
denylist; predicates are not extensible; `redact_patterns` on a job
is read nowhere. The draft still described a failed send as "run the
job again"; since the outbox stash, execution is at most once and
delivery at least once, and steps 15, 16, section 15 and the two
security considerations now say so. The DTLS greeting's family tier
carries three members, not one. The v2 draft's replay rule is kept
as the requirement, with an implementation-status note beneath it
and Q86 to the desk.

## Still open

Each with who holds it.

- **Q86, the desk:** version 2 messages keep no `msg_id` seen-set
  and no freshness window on `issued_at`; a replayed question is
  answered twice. The draft's requirement stands; the fix is small.
- **Q54, Q57, Grok:** the extraction rule and the GitHub release
  pre-creation, both pending since 2026-10-25.
- **The FreeBSD leg, 40000e00:** nine runs, nine failures at the VM
  step. The row in `testing.md` says so until it is green.
- **Coverage cadence, the conductor's call:** `coverage.yml` and
  `python-range.yml` keep one pending run per group and pushes land
  every few minutes, so the coverage run completes on about one
  commit in five. Either is fine; it is a choice between a figure
  per commit and a figure per quarter hour.
- **The hardened systemd unit, decided (the conductor, 2026-10-27):**
  `RestrictNamespaces` names the five namespaces bwrap needs, so the
  unit and the confinement feature work together. The strict value
  is one line to restore for a box that runs confinement at `audit`
  or `off`; the README says which.
- **The AppArmor profile, documented, not fixed:** it runs bwrap
  under the daemon's profile with no mount, `pivot_root` or `userns`
  rules, so confinement cannot engage under it. Extending it needs
  a box to `aa-logprof` on.
- **`hardware.yml`:** dispatch-only and never dispatched; nothing is
  known about the leg until it is.

## Health, as observed

- **Suite:** 3,456 tests on the reviewed tree (local run, Linux,
  Python 3.13), green apart from the modules that import Hypothesis,
  which is not installable on the review box and runs in CI.
  314 test modules; 0 TODO/FIXME in `runner/` outside tests; no
  shadowed (rebound) definitions in `runner/`; every skip reason in
  the skip registry; the three carriers of the version agree.
- **Workflows:** 118 `uses:` lines, all pinned by 40-hex SHA with a
  version comment; `timeout-minutes` only on the two scarce-runner
  jobs the guard allows; 19 of 19 registered.
- **CI on main:** green on every leg at the end of the review except
  the FreeBSD leg (above) and the coverage runs the cadence cancels.

## How to repeat this

The same pass, on any later tree: hold each sentence that states a
current fact to the line that makes it true, and run the guards
that pin documents to code before pushing: `test_design_docs`,
`test_doc_version_rot`, `test_hardening_templates`,
`defaults_registry` (the doc-line anchors), `test_layout`,
`test_build_config`, `test_dozen_extensions`,
`test_doc_default_divergences`, `test_doc_gmail_discipline`,
`live_capture.py --check-doc docs/use/live-examples.md`, and the
spec readers (`grep -l PROTOCOL.md runner/tests/test_*.py`).
