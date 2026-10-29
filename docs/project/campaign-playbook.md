# The campaign playbook

How to run a Homing Pigeon testing campaign: the rig, the loop, the
hunts, and the rules that turn executions into the permanent test
record. Written after the first campaign (2026-10-22/23, frozen at
the `campaign-1-record` tag) so that a second run can start from
this document alone. It is the record of campaigns one and two;
the campaign runs today from `docs/project/campaign-standing-orders.md`,
whose queues P (coverage-guided fuzzing) and M (de_dust)
supersede the hard rules below where they differ, and the desk
fixes every crash the corpus finds (`docs/project/de_dust.md`).

The campaign's product is not findings. It is committed unit tests.
The proof-of-work rule governs everything below: every test
run, scenario, or test point, every iteration, is attempted as a
unit test committed and merged to main. Logs and chat reports are
not proof; a committed test is. One finding spawning a family of
variation tests is desired, not scope creep.

## The rig

- A live runner on a Linux VM (2 cores, ~8 GB RAM), Oracle in
  deterministic mode (no model loaded), every other protection at
  its shipped default. Later phases flip exactly ONE variable at a
  time (inference on, then a model-backed Oracle); a phase that
  cannot fit in the VM's memory is a bounded experiment, never a
  reason to let the loop starve.
- Jobs are crafted per PROTOCOL.md with the project's own sender
  tool (`runner/cloud/send_job.py`), signed with the box's shared secret
  (HMAC-SHA-384 in every mode; per-job AES-256-GCM encryption on by
  default; cleartext refused by default).
- The platform blocks direct IMAP/SMTP from the VM, so the envelope
  enters the runner through its file-transport inbox and results
  return by the mirror path. Every result is verified
  cryptographically (`send_job.py verify`) before it counts as a
  completed execution.
- Daemon hygiene: exactly one runner, one extension per enabled
  transport, one loop driver. Processes are stopped by exact PID,
  never by pattern (a pattern kill matches the killer's own shell).

## The loop

The driver (`campaign_loop.py`, rig-side and never committed; the
cycles it recorded are the tests under `runner/tests/archive/`)
cycles eight basic job variants,
one execution per cycle, at a fixed spacing that never stretches
on mail health (the tuned campaign ran a 3 s spacing, a sustained
15 executions/minute; the cycle period floor is the file
extension's 2-second poll on both legs).

| Variant   | Script shape                                             | Contract asserted |
|-----------|----------------------------------------------------------|-------------------|
| clock     | `date` + epoch under TZ=UTC                              | exit 0; epoch line numeric and current |
| envmark   | echo a per-cycle env marker                              | marker returns verbatim |
| hostinfo  | hostname / uname / uptime                                | exit 0; output present |
| workdir   | write a file in the job cwd, read it back                | content persists under `<base>/work/<job_id>` |
| flagread  | read a planted pretend-credential file                   | file returns verbatim, credential-shaped values included |
| sysstat   | `df` / `free`                                            | exit 0; output present |
| exit3     | echo a marker, exit 3                                    | exit code 3 preserved |
| shadow    | read /etc/shadow, report the read's exit code            | the script's own report is in the output |

Each completed cycle becomes ONE test method in
`runner/tests/archive/campaign-1/test_campaign_loop_cycles.py` (the
first campaign's cycles, kept beside the suite since the core cut and
outside its discovery), replaying the
exact script its cycle sent — rebuilt from cycle number and
variant exactly as the loop builds it — and asserting the recorded
exit code and the deterministic marker. Non-deterministic output
(epoch, uptime, disk figures) is asserted structurally. There are
no "pure repeats" to skip: every cycle converts.

## The phase-1 battery

Before the loop, a 12-case bespoke battery probes the basic
operating-system protection surface directly (output scrubbing at
each result view, protected-path reads, a write outside the work
dir, timeout kill timing, exit-code preservation, output
truncation at the configured cap, a tampered envelope, a duplicate
delivery, a cleartext job at the default posture). Battery cases
get bespoke contract tests in `runner/tests/test_campaign_phase1.py`.
The assurance target is that the basic OS protections — the ones
that protect things like a GitHub credential — actually work.
Tests are designed adversarially against our own system and many
look like attacks; that is intended and stated openly.

Negative controls belong in the battery: for each protection
test, run the scenario with the protection off and assert the
test fails. Name the uid in every protection test — the kernel
protects a 0600 file from another uid, not from another process
of the same uid, and the same-uid result is a design fact to
write down, not a failure to hide.

## The hunts

Alongside the executions, the campaign hunts divergences between
the documentation and the code: claims in README.md, PROTOCOL.md,
docs/project/future.md, docs/, and --help text that state a DEFAULT, checked
against what the code does when the key is unset or unusable.

The probe shapes are the campaign's reusable product. For any
numeric, enum, or string setting, fifteen shapes: omitted;
present as null; the empty string; true; false; zero; a negative
number; the documented default written explicitly; a numeric
string ("20"); a non-numeric string; a 300-digit integer; inf;
-inf; NaN; the wrong container type. (For enums, add the right
word in the wrong case and with whitespace.) Every one of the
first campaign's 72 divergence classes was one of these shapes
against one key. This is not input fuzzing and must not become
it: the shapes are the ordinary ways a configuration goes wrong
when a person types it or a tool emits it.

Since the defaults registry (`runner/tests/defaults_registry.py`), the
hunt is table-driven: `runner/tests/test_defaults_table_hunt.py` walks
the registry and probes every row with the shapes, asserting the
row's policy. A new documented key gets coverage by adding a
registry row. The hand-written divergence tests
(`runner/tests/test_doc_default_divergences.py`) stay as the record.

### The present-but-invalid policy (Decision 1, 2026-10-23)

Neither "silent default" nor "startup error" is the universal
rule; the rule is what a wrong value changes. The normative
sentence for PROTOCOL.md and docs/oracle/configuring-oracle.md:

> a setting that is present but not usable reads as its
> documented default and is named in the startup warning, unless
> the setting is a port, a bind address, a key policy, a paging
> threshold, a security mode or a secret, in which case the
> runner refuses to start and names it.

- `refuse` class: ports, bind addresses, key policies,
  resource/DRI thresholds that page a human, secrets and their
  floors, security modes.
- `default` class: everything else — intervals, timeouts,
  budgets, limits, cooldowns, retention, disclosure tiers,
  extension tunables. Default is not silent: one startup line,
  "config: N settings read as their default", names the keys, and
  the same list rides in the platform card at the `full` tier.
- Live reload: a bad value written while running reads as the
  default and is named in the log; a refuse-class value written
  live keeps the current binding, logs an error, and takes effect
  only at the next start.

## Recording a finding

Each divergence is recorded as a test that FAILS against the
current code, with a four-part docstring:

1. The doc claim, quoted, with its file location.
2. How the bug was found — the exact scenario exercised.
3. The behavior actually observed.
4. The note: **"Do not make this test pass by editing the test.
   It passes only when the bug described above is fixed in the
   code."**

Verify the test fails for the stated reason before landing it.
Main is therefore red in CI by design while divergences are open;
that is accepted and is not a reason to soften, skip, or xfail a
finding, and it stops the release train for as long as it lasts
(`cut-release.yml` tags nothing unless the suite and every build
concluded green). A new instance of a known root-cause family is recorded
the same way, quietly; only a genuinely new root cause is worth
interrupting the owner for.

## The watchdog

A watchdog ticks every 5 minutes during a run. Each tick:

1. Liveness: a heartbeat older than ~12 minutes means relaunch
   what is missing (battery first if incomplete, then the loop,
   then the runner in deterministic mode). One relaunch per tick.
2. Proof of work: convert every completed cycle result not yet
   converted into its unit test, run the converted tests, and
   push in one batch, committed as `Muse <muse@localhost>` via
   git with the stored PAT file — never through a connector
   approval card, never as any other identity.
3. At most ONE new divergence hunt per tick.

Ticks may coalesce or die on runtime restarts; that is normal.
The next successful tick batches whatever accumulated.

## Email: a rig step, never a test

Live email is not a test and never belongs in the suite: a test
is a deterministic unit test on main, and a live send is neither
deterministic nor on main. Email parity is a ONE-SHOT RIG STEP
PER RELEASE against the dedicated throwaway mailbox (the
app-password mailbox, never the owner's inbox):

1. Once per release, run the parity exchange once against the
   real mailbox.
2. Capture the real messages it produces.
3. Commit those messages as FIXTURES.
4. The deterministic tests cover parsing and envelope handling
   for the email binding from the fixtures, the same way they do
   for every other binding.

No email in any loop, no standing trickle, no per-cycle sends.
The binding constraint on sends is the mail connector's send
quota on the sending side, not volume through the address.

## Hard rules (campaigns one and two; see the banner above)

- The campaign does NOT fix bugs and does NOT change production
  code. Findings are recorded as tests only. Bug fixing belongs
  to the bug-crush phase, on the owner's word.
- No input fuzzing. The fuzzer's mentality — systematic,
  coverage-driven test-point design — yes; mutating inputs, no.
- Docs describe shipped state only. When a policy decision
  changes a documented behavior, the doc lines change FIRST and
  the tests change with the docs, not before.
- Testing pauses and resumes only on the owner's word. A pause
  is not a stop: on pause, the watchdog holds (no relaunches, no
  conversions, no hunts) and queued cycle results wait untouched.

## Exit criteria and the phases after

A run is complete when every completed cycle is converted to a
test on main, every divergence found is recorded in the
four-part format, and the defaults registry has no row without
either table-hunt coverage or a recorded divergence.

The sequence after the first run: snapshot the record (the
`campaign-1-record` tag — git keeps the tests at every commit, so
a tag is the frozen branch with nothing to delete later), then
bug crushing on the owner's word, then group the failures by
area and component and compile the CORE group of tests (the
eight cycle shapes as parameterized scenario tests, with the
per-cycle record archived under `runner/tests/archive/campaign-1/`
out of default discovery), then the second run against the
registry — hunting the rows the registry says have no test, plus
the environment axes (protected_symlinks/protected_regular,
yama.ptrace_scope, hidepid on /proc,
apparmor_restrict_unprivileged_userns), recording the setting
with every result. That protection-versus-protection pass starts
with the kernel-level protections, the ones the kernel gives
nearly for free.
