# The v4 binding: properties

This file is step B of the v4 work recorded in `v4-working.md`.
The v4 draft (a later step) binds protocol v1, v2 and v3 to a
provable security model. A binding is only as good as its
index: every constraint the software states must be stated as
a numbered property, or the gap must be named. This file is
that index, plus the properties the earlier list was missing.

Part 1 maps every constraint in the standing inventory
(`constraints.md`, C1 to C27) to the property in
`properties.md` that states it. Part 2 states the constraints
harvested at the 3.17.29.3 head that the inventory did not
carry (C28 to C31), each with its property. Part 3 states
properties for the three standing constraints that no
property in `properties.md` states (C3, C4, C6): the harvest
measured that gap rather than assuming it away, and the new
properties P11, P12 and P13 close it in this file.

New properties continue the numbering of `properties.md`:
P7 onward. Their claims are faithful to the sources named in
each statement; nothing here widens a claim beyond the code
or the draft record it cites.

## Part 1: the standing constraints, and where each is stated

| ID | Constraint | Stated by |
|----|------------|-----------|
| C1 | `max_job_bytes` | P1 clause 1 |
| C2 | `max_script_bytes` | P1 clause 5 |
| C3 | `max_result_bytes` | no property in `properties.md`; P11 below |
| C4 | `_LOCAL_ENVELOPE_MAX_BYTES` | no property in `properties.md`; P12 below |
| C5 | HMAC-SHA-384 signature | P1 clause 2 |
| C6 | Secret entropy floor | no property in `properties.md` (named among the model's assumptions in `readme.md`); P13 below |
| C7 | Key fingerprint | P1 clause 2; P4 clause 1 |
| C8 | Cleartext refused by default | P1 clause 3 |
| C9 | The one AEAD | P1 clause 3 |
| C10 | Audience binding | P1 clause 4 |
| C11 | Seven security modes | P1 clauses 4 and 8; P4 clause 11 |
| C12 | Freshness | P1 clause 7 |
| C13 | Protocol version and type | P1 clause 6 |
| C14 | Key policies and pinning | P1 clause 8; P4, the whole property |
| C15 | At most once, at least once | P1 clause 9; P5, the whole property |
| C16 | Transport credentials | P3, the whole property |
| C17 | Result-policy ceiling | P2 clauses 5, 6 and 8 |
| C18 | Sandbox shape | P2 clauses 1 to 4 |
| C19 | Queues edge gates | P3 clause 8 |
| C20 | Transport gate postures | P3 clauses 4 to 8 |
| C21 | Key directory precedence | P4 clauses 2 and 9 |
| C22 | Upgrade key arrangement | P4 clauses 5, 7, 8 and 11 |
| C23 | Replay-cache keep horizon | P5 clauses 5 and 8 |
| C24 | Claim stale rule | P5 clause 4 |
| C25 | Record retention and delivery window | P5 clauses 9 and 10 |
| C26 | Default-class reader | P6 clauses 1, 2, 3 and 5 |
| C27 | Refuse class at startup | P6 clauses 4 and 6 |

## Part 2: constraints harvested at the 3.17.29.3 head

### C28. The disk guard — the runner's own material, at 90 percent

`guard_disk` in `runner/oracle/resources.py`, called from the
poll cycle (`runner/ops/poll.py`, line 59). Constants in that
module: `DISK_GUARD_THRESHOLD` is 0.90;
`DISK_GUARD_LOG_KEEP_BYTES` is 65536;
`DISK_GUARD_WORK_MIN_AGE_SEC` is 3600;
`DISK_GUARD_MAX_ACTIONS` is 512. The guard is on by default;
the one opt out is the top level setting
`no_90_disk_truncation`, and only a literal `true` turns it
off (`disk_guard_enabled`: an absent key, `false`, or an
unusable value all leave it on). When the disk under the
runner's state directory measures at or over the threshold,
one pass acts in this order, re-measuring after every action
and stopping as soon as the disk is under the threshold:

1. Rolled log backups, oldest first, removed.
2. The live logs (`runner.log`, `oracle.log`,
   `oracle-chat.jsonl`) truncated, keeping the newest 65536
   bytes of each.
3. Recorded results and retained outputs (`sent/`,
   `retained/`, `outbox/failed/`), oldest first, removed.
4. Job workspaces untouched for at least 3600 seconds,
   removed.

A symlink is never followed. Nothing outside the state
directory is touched; the pending outbox, the configuration,
and `security-events.jsonl` are never touched. The pass
annotates what it did as an event of type `disk_truncation`
in `security-events.jsonl`, naming each action up to the 512
cap and whether the disk is still over. The function never
raises and never stops the runner; a pass that cannot get
under the threshold records `still_over` and the next pass is
held off for the resources cooldown.

### P7. The disk guard cannot stop the runner, and touches only its own material

For every poll cycle in a configuration where the guard is
enabled (C28), all of the following hold:

1. **The runner continues.** No outcome of a guard pass
   terminates the runner, raises out of the pass, or skips
   the rest of the poll cycle. A disk the guard cannot fix
   is an annotation, not an exit.
2. **Only the runner's own material, in the stated order.**
   A pass removes or truncates only the four classes of
   C28, only under the runner's state directory, and only
   in the order C28 states: a later class is touched only
   while the disk still measures at or over the threshold
   after every earlier action.
3. **Nothing protected is touched.** The pending outbox,
   the configuration, the seen records, and the security
   event log are never removed or truncated by a pass, and
   no path outside the state directory is ever acted on.
   A symlink is never followed to a target outside it.
4. **The act is recorded.** Every pass that acts leaves
   one `disk_truncation` event naming the actions taken
   (up to the 512 cap), the bytes freed, and whether the
   disk remains over the threshold.

In short form: at 90 percent full the runner gives up its
own material, oldest and least needed first, writes down
what it did, and keeps working. It never stops itself, and
it never reaches outside its own state directory.

A counterexample to P7 is a single guard pass in which the
runner stops, or a file outside the four classes of C28 is
removed or truncated, or a later class is acted on while an
earlier class still had material and the disk already
measured under the threshold, or an acting pass leaves no
`disk_truncation` event.

The first model of this property is `diskguard.tla`; the
start of that work, and what of it remains, is recorded in
`v4-working.md`.

### C29. The v3 hybrid key agreement group

Protocol v3's DTLS carries a hybrid key agreement group,
X25519MLKEM768 (RFC 10024): `GROUP_X25519MLKEM768` is 4588
(0x11EC) in `runner/wire/dtlsproto.py`, beside
`GROUP_X25519` (0x001D). The client offers the hybrid share
beside the X25519 share, and the server selects the hybrid
when it is offered (the addendum in
`dtls-over-email-v3.md`, implemented 2-Nov-2026).

### P8. A v3 session that can agree the hybrid group does so

For every v3 DTLS handshake in which the client offers the
hybrid group (C29) and the server supports it, the agreed
group is the hybrid group, 4588: the session's key agreement
is the X25519MLKEM768 hybrid, not the X25519 share alone.
A peer that offers no hybrid share is agreed on X25519, and
the property claims nothing for it beyond P1 and P3.

A counterexample to P8 is a completed v3 handshake, both
peers this code, in which the client offered the hybrid
share and the session was nevertheless agreed on X25519
alone.

### C30. DTLS framing: both ends run the same side

The record layer and framing record
(`dtls-record-layer-and-framing.md`) ratifies, as of
2026-11-07: mixed-version DTLS interoperability across that
landing is not supported; both ends of a session must run
the same side of the framing change, this release or later.
The derived PSK is part of the wire change. The replay
window's width, 32,768 records, is also the carriage's
reorder tolerance.

### P9. No session is claimed across the framing break

For every DTLS session the runner takes part in, both ends
run the same side of the framing change of C30. A peer on
the other side is not a supported configuration, and no
property in this file or in `properties.md` is stated for
such a pairing: the model's claims for v3 begin where both
ends run this release's framing or later.

A counterexample to P9 is a documented or tested
configuration in which a session across the break is
presented as supported, or a claim in the proof work that
silently assumes one.

### C31. macOS confinement refuses the start rather than running weaker

The macOS confinement backend (`runner/guard/macos_confine.py`;
the record in `docs/steady/security/macos.md`) gates the
start on a probe: the sandbox tool present, a generated
profile that parses, and a trial spawn under the full
controls that works. A host where the confined trial process
cannot work refuses at startup: fail-closed, never a weaker
run.

### P10. On macOS, enforce means the probe passed, or there is no run

For every runner start on macOS with confinement in
`enforce` mode, either the startup probe of C31 passed on
that host, or the runner does not start. There is no start
in which macOS confinement at `enforce` runs in a weaker
form because the mechanism was unavailable. This is P2
clause 1 stated for the platform whose mechanism is a probe:
the machine's half of the sandbox decision can refuse the
start, and on macOS it does.

A counterexample to P10 is a macOS start at `enforce` that
proceeds with confinement weakened, skipped, or replaced by
an audit-only run after the probe failed.

## Part 3: standing constraints no property stated

### P11. A result body leaves within `max_result_bytes`, down to the fitting's floor

C3, stated by no property until now. For every result the
runner delivers on the mail path, when `max_result_bytes`
is set to a non-zero value, the body that is signed and sent
is at most that many bytes, down to the fitting's floor: a
body over the cap has its streams cut to head and tail
before signing, is marked with `result_truncated` naming the
bytes dropped, and the cut is logged (`runner/ops/mail.py`,
the fit-before-signing step; `_fit_result_body` and
`_max_result_bytes` in `runner/runner.py`). The floor is the
result as the fitting's last pass leaves it, with both
streams at their first and last 2 KiB: the streams are all
the fitting cuts. A cap under a result's floor cannot be
kept by cutting, and the body then leaves at the floor, over
the cap and marked: the runner sends a marked result rather
than none. When the cap is 0, the property is vacuous and
says so: unlimited is the owner's stated choice.

A counterexample to P11 is a signed result body larger than
a non-zero `max_result_bytes` in the configuration the
handling loaded and larger than that result's floor, or an
over-cap body sent unmarked.

### P12. A local envelope over the cap is refused unread by the gate

C4, stated by no property until now. For every envelope
presented on the local-signals path, if its UTF-8 length is
over `_LOCAL_ENVELOPE_MAX_BYTES` (262144), it is refused
before any verification work: the file scan reads at most
one byte past the cap, a symlink is refused unread, and the
ingest check rejects an over-cap envelope with the reason
recorded (`runner/runner.py`, `_LOCAL_ENVELOPE_MAX_BYTES`
and `_ingest_local_envelope_inner`). The local path's bound
stands in front of the same gate the mail path faces; it is
not a second, weaker door.

A counterexample to P12 is a local envelope over the cap
that reaches signature verification, or a symlinked envelope
whose target is read.

### P13. The runner does not start on a secret under the entropy floor

C6, named among the model's assumptions in `readme.md` and
stated as a property here. For every runner start, the
shared secret's estimated entropy is at least 128 bits, or
the start refuses with a configuration error naming the
secret (`runner/guard/security.py`: `_estimate_secret_entropy`
and `validate_shared_secret`, which raises under 128 bits). The floor is a
refuse-class startup condition in the sense of P6 clause 4:
a weak secret costs the start, never a warning and a run.

A counterexample to P13 is a runner that starts and reads a
job while its shared secret estimates under 128 bits.
