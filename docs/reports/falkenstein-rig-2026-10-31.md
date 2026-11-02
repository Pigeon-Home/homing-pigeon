# The Germany rig: a Windows seat for the fleet

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

A new fleet machine, created 31 Oct 2026: what it is, where it
is, what it costs, what it is for, and the order its setup
follows. Facts are read from the provider's API at creation;
costs are converted at the day's rate and named as such. This
report is kept current as the seat is proven; each state below
was verified on the machine itself at the time named.

## What and where

- Provider: **Hetzner Cloud**.
- Data center: **Falkenstein, Germany** (location `fsn1`).
  The machine is referred to as **the Germany rig**.
- Server name: `falkenstein-win-1`; server id **173851141**;
  created 2026-10-31. (A first machine of the same name and
  address, id 173844715, was created and deleted the same day
  during a location comparison — Singapore and Tokyo could not
  offer the shape at the price, Helsinki had no capacity —
  and the replacement was placed in Falkenstein with the same
  public address reissued.)
- Public IPv4: **2.28.30.118**.
- Type: **CX43** — 8 vCPU (shared), 16 GB memory, 160 GB disk.
  The size was chosen for cores and memory, for fuzzing work;
  the disk is larger than the job needs and comes with the type.
- Cost: **$20.63 per month** — the EUR 18.49 list price at
  `fsn1`, gross, read from the provider's API at creation and
  converted at 1.116 dollars to the euro (31 Oct 2026). Billed
  hourly up to the monthly cap, so a machine deleted mid-month
  costs only its hours.
- Bootstrap image: Debian 12, present only so the machine had
  something to boot while Windows was installed; since removed
  by the Windows install. The bootstrap root password was reset
  through the API at creation and is filed with the fleet's
  other credentials, never in this repository.

## What it is for

The fleet's Windows seat. Two jobs:

1. Prove the Windows half of the suite live — the runner on
   Windows, and the remote-upgrade procedure's Windows applier
   (`runner/tools/remote-upgrade/hp-remote-upgrade-apply.ps1`),
   which is kitted and test-pinned but unproven until it runs
   here.
2. Fuzzing capacity on the platform the other rigs do not cover:
   8 cores and 16 GB against the de_aztec corpus tooling.

San Francisco is not retired: the droplet is kept, its
fuzzing stopped on 1-Nov-2026, and the box sits idle at $12 a
month.

## The setup order

A standing order for every new system, first applied here:

1. **The runner is installed first.** Nothing else is set up
   before it.
2. **Every step after that is a job.** Configuration, the
   upgrade key, credentials the machine needs (a GitHub
   credential, for one) — all of it is delivered as signed jobs
   through the protocol, and the job/result record is the
   setup's documentation. Nothing is placed by hand.
3. **This machine stays off email.** No mailbox, no email
   transport. Jobs are submitted locally: an operator connects
   by SSH only to hand the local runner its signed jobs, the
   Pi Light pattern — signing kept, mailbox dropped.

Windows itself is installed from Hetzner's own ISO library
(Windows Server 2022 English and the VirtIO driver disc are
both in it, verified against the API on the day). Windows
Server runs under its evaluation terms until a license key is
added; desktop Windows is not licensed for server hardware
and is not used.

**Assume a bare machine.** No procedure for this machine may
assume a tool is installed — not git, not Python, not anything
beyond Windows itself and the runner. Every step installs what
it needs, in the open, as part of the step. A procedure that
works only because something happened to be on the machine
already is a broken procedure; the failure will arrive on the
next fresh machine, in front of a different operator. The
first repository job below follows the rule: it carries its
own portable git.

## State at writing (31-Oct-2026 4:35pm-PST/PDT)

- **Windows installed.** Windows Server 2022 Standard (Server
  Core), computer name WIN-LONG208OI02, installed through the
  provider's web console with the VirtIO storage and network
  drivers loaded at setup. The install ISO has been detached,
  so a reboot cannot re-enter the installer.
- **Access is SSH.** The OpenSSH server is installed, set to
  start automatically, and takes the fleet's key as
  Administrator. PowerShell remoting (WinRM) does not work
  from the operating VM — direct connections are dropped and
  the VM's egress proxy rejects the request shape — so SSH is
  the management channel. The web console's typing drops shift
  states intermittently, so secrets are never typed into it
  directly; the Administrator password was set from character
  codes instead, and the filed value is verified working.
- **The runner is installed and running.** Homing Pigeon
  3.15.0 at `C:\homing-pigeon`, Pi Light profile (deterministic
  Oracle, no local model), as a boot-start Scheduled Task
  running as SYSTEM. The installer's doctor check passes:
  18 passed, 0 warnings, 0 failed.
- **Off email, as ordered.** The runner's transports are
  `["file"]`: signed jobs are handed to
  `C:\homing-pigeon\state\transport-file\inbox` and results
  land in the matching outbox. The install's default email
  transport was replaced before the runner's first poll. The
  machine's shared secret and full runner configuration are
  filed with the fleet's credentials on the operating VM,
  never in this repository.
- **First job proven end to end.** A signed clock job
  (e5e26777-1fd8-4e72-8b61-c596dd996af1) was delivered through
  the file transport, ran under PowerShell (the platform
  default interpreter), and returned exit 0 with a true clock —
  the machine's epoch read matched the operating VM's within
  the fetch time between the two reads. The result's signature
  verified on the operating VM. The local submission route of
  the setup order is therefore proven on Windows.
- **First repository commit from this machine.** A job was
  sent whose script fetched a portable git, checked out this
  repository, appended a section to this report, committed,
  and pushed — the commit is in main's history ("first commit
  from the Germany rig, through its own runner"). The GitHub
  credential travelled inside the signed job and was answered
  from the job's own file at push time; it is not in the
  repository, and a script guard refused to commit if anything
  besides the one file had changed.
- **The watchdog fired on the first attempt, as designed.**
  The runner scans the files a job produces. Eleven seconds
  into the first attempt it killed the job: the portable git's
  sample ssh client configuration names ssh key paths
  (`~/.ssh/id_rsa` and family) that the job's script had never
  declared, and an undeclared credential-store reference in a
  produced file is the authority tripwire — the job dies and
  its outputs are quarantined for the owner's release. The
  second attempt declared the three key paths the sample file
  names in its script header and checked out only the file it
  edits; it ran clean in forty seconds. Lessons for any job
  that fetches tools: a tool's own sample and documentation
  files are produced artifacts under the scan, and the
  credential paths in them must be declared in the script that
  brings the tool. The whole job was rehearsed before sending
  against the runner's own scanner code over the exact file
  set it would produce; the rehearsal predicted both the kill
  and the clean run.
- **Every security setting turned on (31 Oct 2026,
  evening).** All six `security.modes` were set to `enforce`
  (policy_env, policy_files, policy_args, audience,
  confinement, job_user). The Oracle stays deterministic —
  no local model is configured or running. Two findings came
  straight out of the attempt:
  - **Confinement cannot enforce on Windows, and the runner
    refuses to pretend.** With confinement at `enforce` the
    runner declined to start at all: "confinement (bwrap) is
    Linux-only; this machine is win32. Refusing to start; fix
    the sandbox, or set confinement to audit or off." That is
    Decision 1 behaving as designed — a protection that cannot
    engage is a startup error, never a silent no-op.
    Confinement was set to `audit` — the strongest setting
    this platform supports in 3.15.0 — and the runner started
    clean with the other five modes enforcing.
  - **Audience enforcement turns unaddressed jobs away.** The
    first two test jobs under the new posture were rejected at
    the door: "security policy (audience): runner_id
    mismatch." With audience enforcing, a job must be
    addressed to this runner (`--aud` on the sender). Resent
    addressed, both passed: a clock job returning a true
    clock, and a job that installed Python 3.12.7 onto the
    system at `C:\hp-tools\python` and ran it.
  - **A divergence to chase: `job_user` enforces in name
    only on Windows.** Both jobs reported their identity as
    `NT AUTHORITY\SYSTEM` — the runner's own account — with
    job_user at `enforce`. Where confinement refused a
    setting it cannot honor, job_user accepted one. On Linux
    the mode runs jobs as another user; on Windows in 3.15.0
    it changes nothing, and nothing says so. This needs
    either an implementation or the same refusal confinement
    gives, and a test that pins whichever is chosen.
- **A bug found on the way, recorded here.** The runner's
  startup gate asks for mailbox authentication without
  checking whether the email transport is enabled
  (`runner/ops/setup.py`, `needs_setup`, reached from
  `runner/ops/main.py`). On this email-free machine the
  service waited forever at an interactive "Run setup now?"
  prompt: no log written, no channels created, no graceful
  stop. The machine carries an inert placeholder mailbox user
  and password in its configuration as a workaround — the
  email transport is not enabled, so the values are never
  used. The fix (the gate skips when email is not among the
  enabled transports) lands on main with its regression test;
  the placeholder comes out when a build carrying the fix is
  installed here.

- **Output shapes, and a script encoding bug (1 Nov 2026).**
  Four output shapes were sent back to back through the file
  transport. Large output (2,000 numbered lines) round-tripped
  exact in the runner log, empty output came back empty on both
  streams, and stderr-only output arrived on stderr with stdout
  empty. Non-ASCII output built at run time from code points —
  accented Latin, Chinese and Japanese text, a duck emoji, a
  check mark, a euro sign — round-tripped exact on stdout and
  on stderr. The output pipeline is sound. The fifth shape
  failed: a PowerShell script holding that same non-ASCII text
  as literals never ran — PowerShell reported the string was
  missing its terminator, at the line after the non-ASCII text,
  and the job finished with exit 1. The runner stages every
  script as UTF-8 with no byte order mark
  (`runner/ops/exec.py`), and Windows PowerShell 5.1 reads a
  BOM-less file in the machine ANSI code page, so multi-byte
  UTF-8 sequences are misread: garbled where the job is lucky,
  a broken string where it is not. The fix stages a `.ps1`
  with the UTF-8 byte order mark — exactly one, even when the
  sender's script already carries one — and leaves every other
  script kind's bytes exact, because a byte order mark would
  corrupt an `sh` script's head. It is pinned by a new test
  family (`runner/tests/test_powershell_script_encoding.py`:
  non-ASCII at the front, middle and back of the script, runs
  of the odd character, the `pwsh` and `powershell.exe`
  spellings, a script that arrives already carrying a mark,
  and the no-mark rule for `sh` and Python scripts; 18
  assertions failed before the fix and the family passes
  after). The fix has since landed on main as commit
  da80e33e; a rig build carrying it still needs installing
  here before the literal shape can pass live. One scope
  note stays open: a script fetched from
  a URL is staged with its downloaded bytes untouched, so a
  BOM-less `.ps1` served over the wire has the same exposure.

- **The Oracle on Windows, and a console encoding bug
  (1 Nov 2026).** Two jobs exercised the deterministic Oracle
  on this rig. The first (c5ef73a1) declared five queries in
  its result policy — attest, grep, tail, ask and senses.
  Attest answered true for exit_zero; senses answered with a
  real alert from the box (a registry services change, filed
  that morning); ask was refused as inference_unconfigured;
  and grep and tail were refused on policy, because this
  rig's view ceiling is attested and raw output lines never
  cross under that view. All five answers are the designed
  ones. The job's own read-back confirmed the posture:
  oracle_mode is deterministic, the profile is pi-light,
  transports are file only, the config's inference block
  carries an empty endpoint and an empty model, and no
  Ollama process runs — no model is configured or loaded.
  The second job (75563043) ran the installed binary's
  terminal chat (`--oracle-cli`) on the box and asked what
  jobs have run. The ask round trip worked at the record
  layer: the chat log on the box holds the open, the
  question, an answer assembled from the box's records (the
  job index, newest first, with retained summaries and
  notable lines, under the deterministic header), and the
  close. No model took part. But the answer never reached
  the screen: printing it raised UnicodeEncodeError and the
  chat process died with a traceback. The records carry
  characters the Windows console's cp1252 text layer cannot
  encode — the Chinese and Japanese text and the duck emoji
  from the output-shapes jobs are in the retained output the
  answer is assembled from — so on this box the
  deterministic answer is unprintable by construction
  whenever an earlier job printed such text. The loopback
  window does not have the fault: it encodes its body as
  UTF-8 explicitly. The fix makes the terminal chat's
  default printer write an unencodable answer to the
  console's raw buffer as UTF-8 when there is one, and
  otherwise print it with the characters the console cannot
  carry replaced, in the console's own encoding. It is
  pinned by a new test family
  (`runner/tests/test_oracle_cli_encoding.py`: deterministic
  and model answers against buffer and no-buffer cp1252
  consoles, exotic characters in runs at the answer's
  edges, plain ASCII unchanged; 5 of 6 failed before the
  fix, the family and the touched suites pass after). The
  fix sits in a held commit and lands on main at the next
  shared window; a rig build carrying it still needs
  installing here before the chat can be shown live end to
  end.

- **The repo suites under the box's own Python
  (1 Nov 2026).** One job (f2a329aa) made a sparse checkout
  of `runner/` plus `pyproject.toml` at the current main
  (ec5fbd5e, 804 files) and ran a picked Windows-relevant
  subset with the box's own Python 3.12.7: the Windows
  portability, surface, run-as, CLI-simulation and platform
  proofs suites, the Windows test-runner simulation suite,
  and the skip registry — 52 tests in 49.4 seconds, all
  passed, no failures, no errors, no skips. Two shape notes
  from the run: the checkout was made outside the job's
  work folder (at `C:\hp-suites10`), so the artifact scan
  never had to read a whole repository tree the job
  produced; and the suite driver sat at the checkout root
  and named its own root on the path, because the box's
  embeddable Python does not pick up the working directory
  the way a full install does. The job finished exit 0 and
  its signed result verified.

## The upgrade pause: a supposition, written before measuring

How much work does a remote upgrade throw away? The question
decides how often the rigs should be upgraded: if an upgrade
costs almost nothing, the rigs can take every release as it
ships, about hourly; if it throws minutes of work away, they
should upgrade less often. The supposition below was written
down and committed before any measurement was taken, so the
test that follows it is a real test of it.

Supposition, recorded before measuring: a remote upgrade swaps only the runner program. The fuzzing grow runs as its own processes from the rig's own clone, so its threads are never stopped by an upgrade and no fuzzing work is thrown away. The runner itself is down only while the applier stops it, installs, and starts it again — expected to be seconds, and in any case under a minute. The only work an upgrade can throw away is a job in flight on the runner at that moment, which would need to be sent again; no campaign state is lost, because the corpus lives on disk and banks every hour. Predicted measurement: runner pause under one minute, fuzzing work lost zero minutes.

### What the test found (1-Nov-2026)

The upgrade key half of the test landed in full. The upgrade
secret and its key policy are installed in the rig's config,
put there by a signed job through the runner (job 01176c3f);
the policy allows only exec jobs, pins one staging script, and
allows only the Windows release package and its checksum file.
The negative test behaved exactly as designed: a clock job
signed with the upgrade key was turned away for not being the
pinned script, and a clock job under the ordinary key passed
after the restart with a true clock.

The upgrade itself could not be run, so the predicted pause
has no measurement yet. The host half of the procedure — the
applier, a scheduled task that watches for a staged release,
stops the runner, installs, and starts it again — is not
installed on this rig: there is no such task on the box and
nothing in its install locations, checked live before the
test. Installing it was held for the owner's word after the
kit file's read was flagged by a safety check in the session
running the test. Until an applier is in place, a staged
upgrade has nothing to act on it, and there is no outcome
file to read a pause from.

Two smaller facts were measured on the way, both from the
runner restart the key install needed:

- A plain restart of the runner on this rig costs about 8
  seconds: the stop was issued at 11:42:01 box time and the
  restarted runner's startup lines are in its log at 11:42:09,
  watching its inbox a second later.
- The grow never noticed the restart. Its loop process and
  both lanes' processes hold the same start times before and
  after (the loop since the day before, the lanes since the
  cycle start at 11:26:10), and its log shows no gap beyond
  its normal rhythm. That is direct evidence for the
  supposition's mechanism — the grow runs independently of
  the runner — observed at restart scale.

Verdict on the supposition: untested as written, with its
load-bearing claim supported. The claim that an upgrade
throws away no fuzzing work held for the one runner stop
performed. The runner-pause prediction (under a minute) sits
comfortably with an 8-second plain restart, but a real
upgrade adds a fresh checksum fetch and a full install that a
restart does not have, so the prediction stays a prediction
until the applier's first live run measures it. Work thrown
away by that restart: no fuzzing work, and no job was in
flight to lose.

Cadence consequence: the number the cadence decision waits
on does not exist yet, so no cadence change is made on this
evidence. The standing rule — an upgrade every two or three
releases, keeping every runner on a build an hour or two old
at most — stays in force until the measurement lands. The
standing upgrade automation stops at the same door: it can
watch the gap between the rig's build and the newest release,
but it cannot drive an upgrade until the applier is installed
on the rig, and it will not send upgrade jobs into that gap.
A standing hourly watch (germany-remote-upgrade-watch) now
records that gap and the applier's presence; it is gated to
drive an upgrade only once the applier is on the box and this
section holds a measured pause, and the cadence it will use
is the one that measurement supports — every release if an
upgrade throws away about a minute of work or less, every
three releases if it throws away several minutes.

### Addendum (1-Nov-2026): approval given; the measurement is blocked at the key's pin

The owner's word for installing the applier and running the
first measured upgrade was given on 1-Nov-2026, and the
preparatory half is complete on the rig: the config now
carries job_user at audit, the placeholder mailbox values
are removed, and the upgrade key's policy names the current
release's Windows zip and SHA384SUMS as its only allowed
files; the runner was restarted on that config and answers
addressed jobs. The measurement itself cannot start yet,
for a reason the preparation exposed: the staging-script
hash pinned in the upgrade key's policy is, byte for byte,
the staging script documented in the sending guide with the
version read as 3.15.0 — the Linux staging script from the
proven 3.14.2 to 3.15.0 run, carried into this rig's policy
unchanged when the key was installed. A staging script that
names this rig's Windows zip hashes differently and so can
never run under that key, and the pinned script itself
looks for a Linux tarball name that is not among the files
the policy allows. Until the policy is re-pinned to a
Windows staging script — an owner-side change to a security
control, recorded here as the decision now owed — no staging
job can be sent, and the pause stays unmeasured. The applier
install remains held as well, as the scenario queue records.
No cadence change follows from this addendum; the standing
rule above stays in force.

### Addendum (1-Nov-2026): the forced run — re-pin, applier, and the measured upgrade to 3.15.33

The word to force the upgrade through was given, and the run
is complete: the rig now runs 3.15.33, upgraded remotely
under the upgrade key, with the pause measured.

The re-pin came first. A Windows staging script was written
for this rig (PowerShell: check the staged zip against the
SHA384SUMS inside the job's own work folder, move the zip
into a remote-upgrade folder there, leave the trigger file),
and the policy was re-pinned to it by signed job 3c34867b:
the pinned digest moved from 2defbec3…f6255d (the Linux
script) to a2948fb6…f0bd8df (the Windows script), and the
allowed files moved to the 3.15.33 Windows zip and
SHA384SUMS. The upgrade secret itself did not change. The
runner was restarted on the re-pinned policy, a main-key
clock job answered, and the negative test was re-run: clock
job bb772db8, signed with the upgrade key, was rejected with
"key policy: script is not in this key's allowlist" and
produced no result.

Two things the run exposed on the way, both recorded
because they change what any restart on this rig means:

- Stopping the HomingPigeon task does not stop the runner.
  The frozen runner's processes detach and survive the
  task's stop, so every "restart" of the day had in fact
  added another runner set: by mid-afternoon five sets,
  started between 31-Oct and this run, were alive at once
  and racing the same inbox, each holding the config from
  its own start. The first negative test of this run was
  answered by a set started on 31-Oct, before the upgrade
  key existed, with "unknown key_id" — luck of the draw,
  not a verdict on the current config. All sets were killed
  and a single set started before the tests above were run.
  Any future restart on this rig must kill the leftover
  processes by name and count what is alive afterwards.
- With the placeholder mailbox values removed, the 3.15.0
  runner cannot start at all: its startup stops at the
  mailbox setup gate (the known gate bug, fixed on main but
  not in 3.15.0), and a task-started set sits at that unseen
  prompt indefinitely — the restarts after the placeholder
  removal had only appeared to work, because the older sets
  never stopped. The inert placeholder values were restored
  from the on-box backup so the old build could start, and
  removed for good after the upgrade (below).

The applier was installed at
C:\ProgramData\homing-pigeon\hp-remote-upgrade-apply.ps1,
fired every minute by a HomingPigeonRemoteUpgrade task as
SYSTEM; its no-payload cycles logged clean before any
payload was staged. The installed copy differs from the kit
file in four lines: three path lines fitted to this rig's
one-home layout (the kit looks for the home under the user
profile or ProgramData and for the work folders directly
under it; this rig's home is C:\homing-pigeon and its work
folders are under state\work), and one line decoding the
fetched SHA384SUMS from bytes to text. The second of those
is a defect in the kit as shipped, not a rig fitting, and
the run found a third:

- Kit defect, found live (attempt 1): the applier reads the
  fresh SHA384SUMS through Invoke-WebRequest's Content. The
  release asset is served as application/octet-stream, so
  the content arrives as a byte array and no sums line can
  ever match. Outcome: "FAILED: no sums line for
  homing-pigeon-windows-x86_64-3.15.33.zip", written before
  anything was touched; the runner never stopped.
- Kit defect, found live (attempt 2): the stop step is
  schtasks /End, which — per the finding above — leaves the
  detached runner processes alive, so the installer's copy
  meets a locked bin\homing-pigeon.exe and the install
  fails. Outcome: "FAILED: the installer failed (runner
  restarted on the previous version)", the fail-safe working
  as designed. The installed applier now force-kills
  leftover runner processes by name and waits for them to
  be gone before running the installer, and captures the
  installer's own output beside the payload. Both defects
  are fixed in the kit at the source (commit 53e09554): the
  applier decodes the fetched SHA384SUMS from bytes to text
  before matching, and after the task stop it force-kills
  leftover runner processes by name and waits for them to
  be gone before the installer runs — the same two changes
  this rig's installed copy carries — each pinned by a test
  in runner/tests/test_remote_upgrade_kit.py that failed on
  the kit as shipped.

The measured upgrade (attempt 3, staging job 0015d70f,
exit 0 under the upgrade key): the applier cycle began at
16:05:03; the old runner's last log line is 16:04:15; the
3.15.33 start line is 16:05:43. The stop-to-start window
inside the cycle is under a minute — about forty seconds —
and the outcome file reads "upgraded: homing-pigeon.exe
3.15.33"; the install receipt agrees, and the installer's
captured output ends with its normal success summary. A
post-upgrade addressed clock job (5ae2b3b7) returned exit
0. The grow did not notice: its supervisor process kept the
start time it had at 14:36, the lane processes of the
running cycle kept theirs, new worker rounds spawned on
schedule afterwards, and no cycle was lost. Work thrown
away by the upgrade: none that the records show.

Cadence consequence: the measured pause is under a minute
with no work lost, so by the rule written above — about a
minute or less means every release; several minutes would
have meant every three — the cadence this measurement
supports for this rig is an upgrade on every release.

Final state: the placeholder mailbox values were removed
again under 3.15.33 (job 1e3cc983), and the runner was
restarted clean on the mailbox-free config — the fixed
gate verified live on this rig, where 3.15.0 would not
start at all. One runner set is alive on 3.15.33; a final
addressed clock job (47a0af89) returned exit 0. The config
carries job_user at audit, transports ["file"], profile
pi-light, and the upgrade policy exactly as re-pinned.

## Restart resilience (1-Nov-2026)

The box was rebooted through the Hetzner API and came back on
its own. One finding in the reboot itself: the API's soft
reboot action reported success in two seconds, but Windows
never went down — the old boot time
(2026-10-31T15:31:00-07:00) still held more than four minutes
later, with the box answering throughout. The API's reset
action (665281851081072) did reboot it: the new boot time is
2026-11-01T17:06:01-08:00. A soft reboot through the API is
not a reliable reboot for this Windows box; the reset action
is the one that works.

The HomingPigeon task auto-started on its boot trigger with
no hand on the box: runner 3.15.33's startup lines are in the
log at 01:06:24 UTC, the file transport watching its inbox.
The grow task auto-started the same way. An addressed clock
job sent after the reboot (08216d0e) answered with exit 0, a
verified result, and a true clock — the epoch it printed at
17:08:24-08:00 matched real time exactly. The file transport
refused the envelope once on the locked-file race seen
before, then picked it up on its own seconds later. With
this run the twelve-scenario Windows queue is complete.

## What remains

1. The `job_user` divergence on Windows (see the enforcement
   entry above): implement it or refuse it, with a test.
2. The Windows remote-upgrade applier: installed and proven
   live (see the forced-run addendum above). The two kit
   defects it exposed — the sums read as bytes, and the stop
   step that leaves the runner's processes alive — are
   fixed in the kit at the source (commit 53e09554), with
   tests.
3. Windows scenario runs: complete — all twelve items in
   the queue are done, restart resilience last (see the
   entry above).
4. San Francisco is not retired: the droplet is kept, its
   fuzzing stopped on 1-Nov-2026, and the box sits idle.

## First commit from this machine

This section was appended on the Germany rig itself, by a signed job through its own runner, at 2026-10-31T17:00:42.0348500-07:00 (the machine's own clock): clone, edit, commit, push. The commit carrying this text is that commit. The job brought its own portable git, per the bare-machine rule above, and checked out only this file.
