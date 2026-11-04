# Duplication in this repository: what repeats, why, and what to do about it

Dated 2026-11-03. Measured on main at commit ea94da55, with the same
method as the 2026-11-01 audit (a sliding window of 8 normalized
non-blank, non-comment lines over the Python files; exact copies by
file hash). The full audit output is the project's own record; this
document explains it.

This is written for whoever arrives next — a human maintainer, or an
SI system that has just cloned the tree and is forming a judgment
about its shape. The short version: the duplication here is small,
most of it is deliberate, and the parts that are not deliberate are
named below with their remedies. Do not "clean it up" on sight.
Several of these repetitions are load-bearing.

## The measured figures, with their denominators

- The whole tree is 1,145,913 lines. Python is 327,510 of them, in
  599 files. The rest is data and records, not code.
- Near-duplicate Python (lines sitting in an 8-line block that also
  appears somewhere else): 41,782 lines. That is 3.65% of the whole
  tree, and 12.76% of the Python.
- Tests carry 36,820 of those lines (3.21% of the tree; 15.1% of
  test Python). Production carries 4,962 (0.43% of the tree; 6.0% of
  production Python).
- Exact copies: 340 lines beyond the first copy, 0.03% of the tree —
  a 339-line license text vendored in 2 extension upstream folders
  (`runner/extensions/aide-feed/upstream/COPYING` and
  `runner/extensions/suricata-feed/upstream/LICENSE`) and a 1-line
  marker file in a live-run report folder. **No code file is an exact
  copy of another code file, anywhere.**
- Latent code: the orphan scan found 0 unreferenced Python files and
  0 generated files checked in. The one not-run tree is the airgap
  harness in family 1, outside test discovery on purpose.

How to read the near-duplicate number honestly: it is an upper
bound. The window method counts boilerplate, and it counts both
sides of every repeated block, so a block shared by 2 files charges
its lines twice. It also misses clones shorter than 8 lines or
heavily renamed. Treat 41,782 as "no more than this," and read the
families below before treating any of it as waste.

## Family 1: the airgap OVERVIEW fixture — 11,167 repeated lines

`runner/tests/airgap/interesting.example/OVERVIEW.py` is 20,071
lines, and 11,167 of them repeat blocks that live in the real test
files. It is the single largest contributor to the test figure, and
it pairs against nearly every big test file in the audit (367 shared
windows with `test_oracle_intake_fuzz.py`, 349 with
`test_linux_platform.py`, 243 with `test_protocol_and_edges.py`, and
so on down the suite).

What it is: a held-cases fixture for the airgap sweep, a standalone
harness in `runner/tests/airgap/` that sits beside the suite,
outside unittest and pytest discovery (pyproject.toml records the
exclusion). The file's own header states the recipe: 1,801 test-case
bodies harvested from the live test files, shortest first, each
labeled with its source file, class, test name, and line range;
cases longer than 1,000 characters are absent, and exact copies and
near-exact copies (differing by 2 or 3 characters) are absent.

Why it repeats: the repetition is the fixture. A held set only works
as a control if it is frozen — if the cases were generated from the
live tests at run time, the set would drift every time a test was
edited, and a sweep result could no longer be compared against the
last one. The harvest deliberately excludes exact copies, so what
the audit flags is the structural resemblance of 1,801 short test
bodies to the files they were drawn from.

The honest cost: if a harvested case's source test is fixed, the
held copy keeps the old shape. That is not drift to repair; it is
the definition of a held set. The real risk is the opposite one —
someone "deduplicating" this file and silently destroying the
control.

Remedy: leave it. Lines saved by the correct remedy: 0. Regenerating
the fixture from sources on demand would remove about 11,167
duplicated lines from the count (and 20,071 lines from the tree),
at the price of the guarantee the fixture exists to provide. If
anything is worth adding, it is a check that the file still parses
and still holds 1,801 cases — a guard on the snapshot, not a
replacement for it.

**Verdict: deliberate. Should stay.**

## Family 2: the divergence exhibits — 5,479 repeated lines

`runner/tests/test_doc_default_divergences.py` is 47,293 lines, the
largest Python file in the repository, holding 907 test methods.
5,479 of its lines repeat blocks found elsewhere in the same file.

What it is: a museum of known bugs, kept failing on purpose. The
file header is explicit: each test asserts a behavior the
documentation promises that the code does not deliver when a key is
left unset; each test FAILS against the current code on purpose;
"Do not make a test here pass by editing the test. It passes only
when the bug described in its docstring is fixed in the code." Each
exhibit carries the same 4-part docstring scaffold — the doc claim
with its file and line, how the bug was found, the behavior actually
observed, and the do-not-edit warning — and the same test shape: a
temporary directory, records stored through the module's own API, a
read back through the documented path, and an assertion on the
difference.

Why it repeats: each exhibit has to stand alone. A reader (human or
SI) who opens the file at any point must get the whole story —
claim, evidence, observed behavior — without chasing a shared
helper or a base class to reconstruct what the test proves. The
scaffold repetition is documentation, and the arrange-act repetition
is the price of 907 self-contained bug reports.

The honest cost: a change to the shared store/read helpers means
many exhibits change their behavior at once — but that is the point
of the file: when a bug is fixed in the code, its exhibit starts
passing, and the file's failure count is itself a progress measure.
Factoring the scaffolding into helpers would make the file shorter
and each exhibit weaker as evidence.

Remedy: leave it. A helper layer for the temporary-directory and
store/read-back pattern might save roughly 2,000 to 3,000 of the
5,479 repeated lines, and it is not worth it: it would blur the
one-exhibit-one-bug mapping the file exists to keep. Lines saved by
the correct remedy: 0.

**Verdict: deliberate. Should stay.**

## Family 3: the feed extensions — about 1,800 measured lines, the real one

This is the family worth an arriving system's attention, because it
is the one place where repetition is a standing maintenance cost
rather than a designed exhibit.

What repeats: 9 sibling senses under `runner/extensions/` are
parallel implementations of one shape —

- `falco-feed/falco_feed.py`: 292 of 538 lines duplicated
- `suricata-feed/suricata_feed.py`: 298 of 580
- `zeek-feed/zeek_feed.py`: 207 of 702
- `failed-login-watch/failed_login_watch.py`: 201 of 507
- `osquery-feed/osquery_feed.py`: 199 of 610
- `wazuh-feed/wazuh_feed.py`: 185 of 535
- `job-watcher/job_watcher.py`: 148 of 771
- `sysmon-feed/sysmon_feed.py`: 139 of 631
- `log-sentinel/log_sentinel.py`: 131 of 513

The strongest pairs share over 100 windows (falco ↔ suricata: 187).
The same skeleton also runs through the other senses the audit did
not rank in its worst 10 — 26 of the 28 extensions define the same
`decide()` entry point, and 25 carry the same `_is_number()` helper,
byte for byte identical in the files checked.

The shared skeleton, function by function:

- `_is_number(value)` — the finite-number tunable check, identical
  everywhere (its docstring carries a scar: infinity once made a
  threshold that never trips).
- Timestamp parsing — `_parse_ts()` plus the same fraction/offset
  regexes in the JSON feeds (Falco's nanosecond fractions, Suricata's
  EVE timestamps, Wazuh's, Zeek's epoch floats).
- `parse_event(line)` — one line of the source log to one event.
- `read_new_events(paths, reader_state)` — the log tailer: a state
  dict of `{path: {"inode", "offset"}}`, a missing file yields no
  events and keeps its offset, an inode change or a shrunk file
  restarts from 0.
- `_fresh_state()`, `_clean_state(state)`, `_clean_event(entry)` —
  state hygiene between passes.
- `decide(readings, manifest, state)` — the pure decision: readings
  plus manifest plus last pass's state in, alerts and new state out;
  it never reads a clock.
- `_deliver_local(alerts, args)` — about 50 lines, identical except
  for the extension's own name in its error messages. Notably, it
  does not re-implement signing: it imports the runner's own
  producer helpers (`runner.ops.extensions`) at delivery time, so
  the envelope and signature are the contract's, not a copy.
- `main()` — the same argument surface everywhere: `--readings FILE`
  and `--log-file FILE` fixture modes, `--local-dir` / `--local-port`
  delivery, `--secret-env`.

What differs per feed is everything that should: the source format
(Falco's JSON priorities, Suricata's EVE JSON, Wazuh alerts, osquery
result logs, Zeek's log rows, Sysmon's XML and text event logs,
auth.log regexes for failed logins, kernel-log patterns for
log-sentinel), the signal and severity mapping tables, what makes
an episode distinct (Falco: rule plus output-fields digest;
osquery: query kind plus row identity), and the detection logic
inside `decide()`.

Why it exists: each extension is a self-contained unit — 1 folder
holding 1 Python file, its `extension.json` manifest, its fixtures,
and its vendored upstream — that can be installed, read, and tested
on its own. The senses are examples as much as features: a reader
writing a 10th feed copies a sibling and edits the parts that
differ, and gets a working sense whose whole behavior is visible in
1 file. That is a real design value, and it is why the copies exist.

The honest cost: the skeleton is maintained 9+ times by hand. A bug
fixed in 1 tailer — say the inode-change restart in
`read_new_events()` — has to be carried to every sibling by a human
who remembers they all have one, and nothing in the tree says so.
This is exactly how parallel implementations drift: 1 feed learns,
the others keep the old behavior, and the difference surfaces as a
sense that silently misses events. Of all the families in this
document, this is the only one where a copy can be *wrong* while
looking fine.

The remedies, honestly priced:

1. **A shared base module** (a feedkit the senses import: the
   tailer, the state hygiene, the timestamp and number helpers, the
   delivery adapter, the main() scaffolding; each feed keeps its
   parser, its tables, and its decide logic). Saves roughly 1,500
   to 1,800 of the measured duplicated lines across the 9 named
   files. Cost: an extension folder is no longer standalone — it
   needs the shared module beside it at install time, and the
   copy-1-file-and-edit on-ramp for new senses goes away.
2. **Generate the feeds from 1 template.** Keeps the standalone
   files, but the checked-in code becomes generated output. This
   tree currently checks in 0 generated files, and trading a
   duplication smell for a generated-code smell is not obviously a
   win.
3. **Keep the copies; guard them like the signers.** Add a test in
   the style the project already uses for its kept-in-step code
   (family 4): assert that the shared functions are identical
   across the feeds, modulo the feed's name string, so a fix that
   lands in 1 tailer fails the suite until it lands in all of them.
   Saves 0 lines and removes the actual risk, which is silent
   drift, not the line count.

Recommendation: remedy 3 first. Remedy 1 becomes the right answer
only if the deployment model changes so that extensions stop
shipping as standalone folders.

**Verdict: a real defect (unguarded hand-carried copies), with a
deliberate reason behind it. Guard the copies; do not merge them
blindly.**

## Family 4: the 3 signers — about 220 lines a side, on purpose

`runner/cloud/send_job.py` (the cloud-side helper an SI runs) and
`runner/wire/verify.py` (the runner's own verifier) share 84
windows: the canonicalization and signature machinery —
`normalize()`, `sign_payload()`, `_extract_signed()`,
`_object_start()`, `_root_candidates()`, `_in_root_object_at()`,
`verify_body()` — roughly 220 lines implemented on each side. A 3rd
implementation of the signing step, `sign_envelope()`, lives in
`runner/ops/extensions.py`. The secret-strength check in send_job.py
likewise mirrors `runner/guard/security.py`.

Why it repeats: these are independent implementations of the
protocol's security-critical canonical form, and their independence
is the check. send_job.py is written to be run by an outside system
that does not have the runner installed; verify.py is the runner
trusting nothing it did not compute itself. The code says so, in
terms an arriving SI should take seriously: "the two implementations
must stay in step," "Kept in step with runner/wire/verify.py and
runner/ops/extensions.py (Q48)." Where sharing was safe, it has
already been done — both sides import the JSON-safety helpers from
`runner/guard/textutil.py`. And the suite cross-exercises the pair:
`runner/tests/security_parity.py` signs jobs with send_job.py's
`sign_payload` and runs them through the runner's `verify_body`, so
a divergence between the implementations is a test failure, not a
surprise in production.

The honest cost, stated plainly because the comments in the code
state it: the implementations have already diverged in detail —
verify.py routes the payload through a JSON-safety transform and
refuses lone surrogates by name, send_job.py guards the dict itself
— and the project manages that divergence by analysis and tests
rather than by pretending it is not there. A canonicalization
difference that slipped the tests would be a verification gap, not
a style issue; that is precisely why there are 2 implementations
watching each other instead of 1 shared function trusted by both
sides.

Remedy: leave it, and keep the parity tests sharp. Merging the 2
sides into 1 shared signer would save about 220 lines and destroy
an independent check on the signature path — the worst trade in
this document.

**Verdict: deliberate, security-bearing. Should stay.**

## Family 5: the long tail

Everything else the audit names, briefly:

- **Ordinary test boilerplate.** After families 1 and 2, about
  20,000 of the tests' 36,820 duplicated lines are spread across
  the suite as shared setup and assertion shapes. The densest
  files are fuzz and intake tests — `test_oracle_intake_fuzz.py`
  (922 of 1,922 lines), `test_protocol_and_edges.py` (627 of
  1,390), `test_pi_light.py` (451 of 953) — where many small cases
  are built from 1 shape and each case is meant to be read, and
  debugged, standing alone. `runner/tests/defaults_registry.py`
  (625 of 2,555) is the counter-example already in the tree: where
  a repetition was pure data, the project factored it into a
  registry the tests share. Remedy: none globally. Factor a file
  when its own repetition starts hiding differences; do not run a
  suite-wide deduplication pass over test exhibits.
- **`runner/tools/de_dust_corpus.py`: 173 duplicated lines of
  11,894 (about 1.5%).** Internal repetition inside 1 large corpus
  tool. Below any reasonable action threshold; leave it.
- **Vendored upstream code: 30 files, 23,265 lines** under
  `runner/extensions/*/upstream/` — Zeek scripts, the Suricata
  schema, licenses. Copied by definition, but these are pinned live
  dependencies the feed extensions load, watched by
  `test_upstream_pins.py`, not duplicates of this project's code.
  Leave them; the pin test is the guard.
- **The exact copies (340 lines)** are 339 lines of that vendored
  license text appearing in 2 upstream folders, plus a 1-line
  marker. Each upstream folder carries its own license because the
  folders are self-contained (family 3's design again). Leave them.

## Direction

For the next maintainer or SI system deciding where to spend effort:

1. **Do first:** guard the feed-extension skeleton (family 3,
   remedy 3) — a kept-in-step test over the shared functions, in
   the pattern the signers already use. It is the only family where
   repetition can silently become wrong behavior.
2. **Leave alone:** the OVERVIEW fixture, the divergence exhibits,
   and the 3 signers. Their repetition is the mechanism — a frozen
   control set, 907 standalone bug reports, and independent
   implementations of the signature contract. Deduplicating any of
   them makes the tree smaller and the project weaker.
3. **The standing limit:** duplicate or latent code stays under 5%
   of the tree. The current measure is 3.65% near-duplicate
   (upper bound) and 0.03% exact, with 0 orphan files — inside the
   limit, with the composition understood. The limit is a tripwire,
   not a target: if a future audit crosses it, the question is
   which family grew and whether its reason still holds, not how
   fast the lines can be deleted.
