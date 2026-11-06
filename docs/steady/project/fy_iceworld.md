# Campaign fy_iceworld: fuzzing the RFC 10024 hybrid key agreement

<!-- Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026 -->

fy_iceworld is the fuzzing campaign for the post-quantum
hybrid key agreement Homing Pigeon carries in its version 3
DTLS profile: the group X25519MLKEM768 (RFC 10024, code
point 4588), ML-KEM-768 combined with X25519, implemented in
`runner/wire/mlkem.py` and the hybrid share handling in
`runner/wire/dtlsproto.py`. The name is the campaign's name
in prose and records; the tool, the corpus fixtures and the
tests keep their own names (`runner/tools/hybrid_fuzz.py`,
`runner/tools/hybrid_timing.py`,
`runner/tests/test_hybrid_fuzz.py`, fixtures under
`runner/tests/fixtures/`), as this project's campaigns do.
The campaign record — suppositions, measured timings, the
seam as built, and the run log as it grows — is
`docs/infrastructure-documents/proofs/hybrid-fuzz-10024.md`.
This file is the plan the campaign runs by.

## 1. Why this code, why now

The hybrid path is the newest cryptography in the tree and
the least fuzzed. The ML-KEM implementation is pure Python,
written for this project; it is not constant-time, and its
authors say so in the code. The DTLS hybrid profile wrapped
around it parses peer-controlled bytes — a client's key
share is 1,216 bytes of attacker-supplied input on any
handshake that offers the group — and the composition
rules (fixed sizes, concatenation order, which check runs
first) come from RFC 10024, a 9-page specification whose
whole normative content is geometry and a handful of MUSTs.
That combination — hand-written lattice cryptography,
a strict external geometry, and a parser in front of both —
is exactly where in-memory fuzzing pays.

## 2. Timing first, suppositions before measurement

The campaign's first step is measurement, not mutation.
The direction that set this campaign also carried a guess:
that some of these operations take about half a second, a
second, or a few seconds each, and that the fuzz loop would
have to be designed around that. Guesses are not design
input. Under this project's supposition-first convention,
the timing suppositions were written into the campaign
record BEFORE any measurement ran (record section
"Suppositions", ST1–ST5), and the same place now carries
the measured conclusions beside them.

The instrument is `runner/tools/hybrid_timing.py`: every
operation in the hybrid path timed separately, adaptively
repeated, reported as median and minimum — ML-KEM key
generation, encapsulation, decapsulation of a genuine
ciphertext, decapsulation of a corrupted ciphertext (the
implicit-rejection path), the FIPS 203 section 7.2 and 7.3
key checks, X25519 public-key and ECDH operations, the two
composed responder/client crypto paths, and a full
in-memory hybrid handshake.

Measured result, in one paragraph (the tables are in the
record): on the rig's dedicated core the dearest single
operation is decapsulation at about 38 ms; nothing reaches
0.5 s, composed or alone; a full handshake is about
234 ms. The direction's guess does not hold for CPU time —
where seconds appear in live use they are mail-carriage
latency, not computation. The suppositions missed their
ranges on the high side while getting the ordering right
(decapsulation dearest, the section 7.3 check nearly free,
implicit rejection costing the same as genuine
decapsulation). That measured shape, not the guess, is
what the run design below is built on: real cryptography
is cheap enough to fuzz directly for an hour, and the
abstraction seam exists to buy round count, not to make
fuzzing possible at all.

## 3. The abstraction seam

After timing, the expensive operations are abstracted so
the fuzz loop can run at speed without them.
`runner/tools/hybrid_fuzz.py` carries two implementations
of one contract. `RealOps` delegates to the production
ML-KEM. `AbstractOps` replaces the KEM internals with
deterministic, size-faithful stand-ins: the encapsulation
key is a SHAKE-256 expansion of the keygen seed; the
decapsulation key keeps the production byte layout, so the
production section 7.3 check passes on abstract keys
unchanged; encapsulation masks the message with a
keystream drawn from the encapsulation key;
decapsulation recovers it; a wrong ciphertext yields a
different secret, never an error — the implicit-rejection
shape is preserved.

The seam is a context manager that patches the operations
into the DTLS engine's view of the `mlkem` module
(`keygen`, `encaps_internal`, `decaps`,
`encapsulation_key_check`) and restores the module on
exit. Everything around the KEM — share parsing, the
length discipline, the RFC 10024 combiner, the handshake
state machines — runs for real in both modes.

What the seam deliberately does NOT preserve, stated
plainly because the plan's honesty depends on it: the NTT
arithmetic and the section 7.2 modulus check. The abstract
encapsulation-key check is the length only. Any contract
whose refusal depends on section 7.2 content (a malformed
encapsulation key of exactly the right size; the
order-swapped share below) is a real-mode contract; behind
the seam those inputs are held to the framing contract
(refusal, or a well-shaped result). The unit tests pin
both behaviours, each in its own mode. One coupling is
preserved on purpose: production `encaps_internal` calls
the section 7.2 check itself before it hashes, and
`AbstractOps.encaps_internal` likewise calls the seam's
check first and refuses with `MlkemError` — so behind the
seam an encapsulation key of the wrong length is refused
exactly as in production, and only the modulus content of
a right-length key goes unchecked.

## 4. Run shape

1. **Phase A — 1 hour against the real cryptography.**
   `--mode real --duration 3600`, seed 10024, every target
   in rotation, standards corpus live throughout. This is
   the phase that exercises the expensive operations the
   timing step measured, on real inputs.
2. **Phase B — the abstracted continuation.** Repeated
   passes of `--mode abstract --duration 3300` with
   rotating seeds, indefinitely, on the same corpus. The
   standards vectors stay in rotation behind the seam too:
   they are the inputs that pin the shapes the seam must
   preserve, and a seam drift shows up first as a vector
   that stops agreeing.
3. **A finding stops the campaign.** Exit code 3 from the
   harness (a contract break) writes the finding and the
   offending input to the findings file, marks the lane
   stopped, and the lane heartbeats instead of starting
   another pass. Findings are reviewed by a human-facing
   seat before any restart; a fuzz-found defect then gets
   the shotgun treatment this project gives such bugs: a
   family of tests around the failure, never a single
   regression test.
4. **Resource floors are part of the run, not an
   afterthought.** The harness aborts (exit 4) if
   MemAvailable falls under 128 MB, and the lane checks
   memory at every pass boundary. On a 1-core box the lane
   owns the core; on the 8-core machine the campaign takes
   a share of cores and leaves the rest to the fleet's
   other tasking.

Status at the time this plan was written: phase A has
completed on the fallback machine (227,470 rounds, 0
findings, the full hour) and phase B is running there with
the enriched corpus of section 5. The Germany deployment
(section 7) is staged the moment the rig answers.

## 5. Corpus: seeded from the standards, provenance visible

The corpus is seeded up front with everything the public
standards already fix, so the fuzzing does not spend
rounds rediscovering it. Provenance is recorded per
source, in the fixtures and in the campaign record:

- **RFC 10024 itself** (harvested 2026-11-05 from the RFC
  text, sections 4.1, 4.2, 4.3, 6 and 7.1–7.4, into
  `runner/tests/fixtures/rfc10024_groups.json`): the RFC
  publishes no test vectors and no worked examples; what
  it fixes is the geometry, and the geometry is what was
  taken — all three groups' code points (4588, 4587,
  4589), client and server share sizes per group
  (1216/1120, 1249/1153, 1665/1665), each group's
  concatenation order (ML-KEM first for X25519MLKEM768;
  ECDHE first for the two NIST-curve groups — the RFC's
  own note that the X25519 group's order reverses the
  RFC 9954 convention), shared-secret sizes (64, 64, 80),
  the obsoleted pre-standard code points (25497, 25498),
  and the checks of sections 4.2 and 4.3 (the section 7.2
  encapsulation-key check, the ciphertext-length check,
  the ECDHE validity checks, the all-zero X25519 check).
- **FIPS 203, via the NIST ACVP ML-KEM-768 vector set**
  (`runner/tests/fixtures/mlkem768_acvp.json`, in the tree
  before this campaign): key generation, encapsulation and
  decapsulation known-answer rows — including the modified
  ciphertext whose expected secret is the implicit
  rejection value — and both key-check groups.
- **RFC 7748** (sections 5.2 and 6.1, transcribed in
  `runner/tests/test_dtls.py`): the X25519 vectors,
  including the Alice/Bob pair whose shared secret is
  known.
- **The hybrid vector**, constructed from the two sources
  above: the first ACVP key-generation entry (its
  encapsulation and decapsulation keys pinned byte-exact
  by the standard), encapsulated to with the first ACVP
  encapsulation entry's message through the production
  function (itself pinned byte-exact by the ACVP
  encapsulation rows in the unit tests), with RFC 7748's
  Alice as the client share's X25519 half and Bob as the
  server's — giving a full RFC 10024 section 4 client
  share, server share and 64-byte secret, all known.
- **The existing unit tests** (`runner/tests/test_mlkem.py`,
  `runner/tests/test_dtls_hybrid.py`,
  `runner/tests/test_dtls_fuzz.py`) are the corpus's
  regression floor: their vectors and shapes are the
  harness's positive controls, run before any mutation in
  every pass — the ACVP round trip through the ops in use,
  the hybrid vector's decapsulation, and the RFC 7748
  handshake must all agree before a single mutated input
  is fed, or the run is measuring a broken harness.

## 6. Targets and contracts

Seven mutation targets and one geometry target, in
rotation, every round drawn from the corpus:

- **decaps** — mutated ACVP ciphertexts against genuine
  keys: a 1,088-octet ciphertext never raises and returns
  32 octets; any other size is `MlkemError` or nothing.
  (The contract is conditioned on the genuine key: a
  decapsulation key that fails its own section 7.3 check
  is likewise a `MlkemError` refusal — `mlkem.decaps`
  checks it before it touches the ciphertext.)
- **encaps** — mutated encapsulation keys: `MlkemError`
  only; success returns exact sizes.
- **key_checks** — mutated keys against both FIPS 203
  checks: a boolean, never a raise, on any byte-string
  input (the mutators produce byte strings only; the
  checks' `len()` guards are not a type discipline for
  exotic objects, and none is claimed).
- **keygen** — mutated seeds: `MlkemError` only for
  mis-shaped seeds; a produced pair passes both checks.
- **client_shared** — mutated server shares against a
  primed hybrid client, with a positive control each
  round: `DtlsError` only, or a 64-octet secret.
- **server_answer** — mutated client shares against a
  pumped, established server session: `DtlsError` only,
  or a well-shaped share and secret; a session half-built
  around a refused share must not survive (the ClientHello
  path's discipline, exercised through feed below).
- **server_feed** — mutated genuine ClientHello datagrams
  against a fresh server core: feed never raises at all.
- **geometry** — the RFC 10024 harvest as an attack: this
  group's genuine shares rebuilt at the other groups'
  fixed sizes (1249/1665 client, 1153/1665 server) and
  this group's parts in the RFC 9954 order at exactly
  1,216 bytes. All must be refused with `DtlsError`. The
  order-swapped refusal deserves its precision: what
  refuses it in real mode is the section 7.2 content
  check on bytes that are not an encapsulation key — a
  random 1,184-byte string passes that check with
  probability under (3329/4096)^768, so the refusal is
  overwhelming without being a logical certainty, and
  behind the seam (section 3) the swapped share is held
  to the framing contract instead. Both behaviours are
  pinned by tests, each in its own mode.
- **client_feed** — crafted ServerHello records against a
  client waiting for one: structural variants (each
  extension removed in turn; a foreign group — 4587,
  4589, 25497, 25498 — named in the key_share entry) plus
  byte mutations of the genuine article. The contract is
  a list back, or `DtlsError` only. This target exists
  because the plan review in section 11 found, and hand
  verification confirmed, that a ServerHello with no
  key_share extension raised an uncaught `KeyError` out
  of `DtlsClientCore.feed` — finding F-1 in the campaign
  record, fixed test-first in `_on_server_hello` (the
  presence check its sibling paths already had) and
  pinned by a family of tests around the shape.

Three further target families are named here with their
code basis, to enter the rotation as the campaign
continues (the review in section 11 proposed all three;
each basis was verified by hand before it was written
down):

- **Duplicate and competing key_share entries** in the
  ClientHello (`_key_share_entries`, and `begin`'s
  first-entry-wins `setdefault`): duplicate 4588 entries
  in both orders of valid and invalid, unknown groups
  mixed with known, and the X25519 fallback when the
  hybrid group is absent or disabled.
- **The version 3 carriage itself** (`dtls_mailbox.py`:
  `parse_message`, `FlightReassembler.offer`, the
  receive paths): this is the one place the hybrid
  profile is on by default, so its framing and
  reassembly deserve direct mutation, not only replay.
- **Handshake fragment reassembly**
  (`_FragmentBuffer.offer`): a fragment header's total
  length is trusted into a `bytearray(total)` allocation
  — up to 16 MB per (message type, sequence) key, with no
  cap on pending keys — a memory-pressure surface a
  hybrid-sized handshake makes worth fuzzing directly.

Every mutation family includes the **bookend rule**: each
symbol on the ASCII table, plus NUL, tab, CR and LF,
wrapped at the front AND the back of the input,
symbol-only strings, and symbol runs (10 deep) at the
front, the back and the middle — alongside bit flips, byte
sets, truncation, extension, half-swaps and insertion.
Per-field discipline holds throughout: each field of each
share (encapsulation key, ciphertext, each X25519 half,
each seed) has its own unit tests and its own mutation
line, enumerated in `runner/tests/test_hybrid_fuzz.py`,
and the boundary sizes around every fixed length
(0/1/±1/exact/double) are tested per field, not sampled.

The carriage is a target class of its own, one level up:
the same shares cross the version 3 mailbox carriage
(`runner/wire/dtls_mailbox.py`) in the live system, where
segmentation, reassembly deadlines and held-result binding
shape what an attacker can actually present. That layer
has its own fuzzing history in this tree; fy_iceworld's
in-memory contracts are written so a share-level finding
can be replayed through the carriage unchanged (the
findings file records the exact input bytes).

## 7. Machines

- **Primary: the Germany rig** — 8 vCPU, Windows Server
  2022, the fleet's grow tree at `C:\hp-rig`. The campaign
  is Windows-shaped work as much as Unix: the ML-KEM is
  platform-independent Python, but the lane discipline,
  the process supervision and the timing table all deserve
  a Windows column, and 8 cores run the real and abstract
  lanes side by side instead of in sequence. Deployment is
  staged locally and lands the moment the rig answers SSH;
  at the time this plan was written the rig had been
  unreachable over SSH on every check of the day (the
  egress proxy closes the connection), which is recorded
  here as the blocker it is, not worked around silently.
- **Fallback and current runner: the San Francisco rig** —
  1 vCPU, 2 GB. Its CPU-pump lane was repointed to this
  campaign (the previous lane script is kept beside the new
  one), the tree was synced to current code, and it runs
  the phases in sequence: phase A completed there, phase B
  continues there until Germany takes over or the campaign
  closes. Floors on this box: MemAvailable above 128 MB,
  disk under 90% — both held with wide margins so far
  (about 1,500 MB free, disk at 39%).
- **This build machine** runs the harness in-suite (the
  bounded smoke runs in the unit tests) and the timing
  comparisons; its numbers are contention-inflated and are
  labelled as such wherever they appear.
- Any long-lived process on any box launches detached
  (setsid/nohup); liveness is judged by log mtimes and
  verdict lines, never by process-name matching.

## 8. Proof of work

Every part of this campaign leaves its proof in the
repository, per the project's standing rule:

- The suppositions were committed before the measurements
  existed; the measured conclusions were posted in the
  same place; the timing tool that produced them is in
  the tree (`runner/tools/hybrid_timing.py`).
- The harness is in the tree with its contracts written
  down in its own docstring; the corpus fixtures carry
  their provenance in a `source` field.
- The unit tests (33 in `runner/tests/test_hybrid_fuzz.py`
  at this plan's writing) pin the corpus, the per-field
  discipline, the geometry refusals, the seam contract in
  both modes, the client-feed discipline of finding F-1,
  and bounded runs of the campaign itself;
  the guard suites (core measures, layout, skip registry,
  reader-docs, doc-version) run with them before any
  landing.
- The campaign record accumulates the run log: phases,
  rounds, verdicts, findings and the machine each ran on.
  A phase that ran and left no record did not happen.

## 9. Success criteria

The campaign succeeds, in order of weight:

1. **No silent acceptances.** Every malformed share the
   corpus and mutators can build is refused in the mode
   its contract promises, or the refusal gap is a filed
   finding with the input preserved. Zero findings across
   phase A's 227,470 real-mode rounds is the current
   state; the criterion is that the state stays earned as
   the corpus grows, not that it never changes.
2. **The geometry is exact.** The implemented group's
   sizes, order and code point match RFC 10024 as
   harvested, pinned by tests that would fail if either
   side moved; the unimplemented groups' code points and
   the obsoleted pair are provably absent from the engine.
3. **The seam is faithful.** Behind the abstraction, every
   framing-level contract behaves as it does against the
   real cryptography, and the two places the seam is known
   to differ (section 7.2 content, NTT internals) are
   named, tested around, and never silently relied on.
4. **Timing is knowledge, not folklore.** The per-operation
   table exists for a quiet dedicated core and is refreshed
   when the Germany column lands; any operation found
   drifting toward the half-second territory the original
   guess imagined would reopen the seam design.
5. **The record is complete.** A reader can reconstruct
   what ran, where, on which corpus, and what it found,
   from the repository alone.

## 10. Risks and open questions

- **The pure-Python ML-KEM is not constant-time.** This
  campaign measures correctness under mutation, not timing
  side channels; a timing-leak study is a different
  instrument and is not claimed here. The timing harness
  does record per-operation spread, and a spread anomaly
  that grows with secret content would be filed as a
  question, not silently absorbed.
- **Implicit rejection must stay indistinguishable in
  shape.** The contracts test that a corrupted ciphertext
  yields a secret, never an error; they do not test that
  the two decapsulation paths take the same time. On the
  rig they measured the same (about 38–39 ms); on other
  hardware that equality is an open check, listed here so
  it is not forgotten.
- **The corpus is standards-complete, not
  history-complete.** The de_dust corpus machinery has its
  own survivor shapes from other targets; promoting any of
  them into this corpus is a deliberate act with
  provenance noted, not a default.
- **Germany's silence.** If the rig stays unreachable, the
  campaign completes on the fallback and the Windows
  timing column stays an open item, recorded as such.
- **A latent asymmetry in the client's hybrid path**
  (found by the review in section 11, verified by hand):
  `_hybrid_shared` calls `mlkem.decaps` without
  translating a `MlkemError` into `DtlsError`, where
  `_hybrid_answer` on the responder side does translate.
  It is unreachable as the code stands — the share length
  is checked before the call, and the decapsulation key
  is the client's own, generated to pass its check — so
  it is recorded as a hardening proposal (translate, for
  symmetry and defence in depth), not as a defect.
- **Rejection sampling spreads decapsulation-adjacent
  timings.** `_sample_ntt` loops on a growing SHAKE stream
  until 256 coefficients land; the loop count varies with
  the seed, one more entry in the not-constant-time
  ledger this campaign already declares, noted so the
  timing tables are not misread as evidence of anything
  tighter.

## 11. The Argon review

This plan was reviewed by gemini-4-argon in one billed
sitting (2026-11-06), against the stripped production
core — the same assembly the Phase 1 pass used, whose two
hybrid files are byte-identical to the code at this
plan's writing. The packet was the plan plus the core:
620,736 tokens by the API's own count. The sitting's
manifest and the full response are kept with the pass
records (`~/workspace/token-index/gemini-pass/fy-iceworld-plan-review/`).

Argon's verdicts, in substance (Argon-generated text;
stamp 00000000-argon-26a0-ff29-7825440c1fb9):

- Sections 1 and 10: SOUND.
- Sections 2, 4, 5, 7, 8: UNJUDGED — their substance is
  the harness, the record and the fixtures, all stripped
  from the packet; Argon named those files as its
  requests, and they were not sent: the direction was one
  sitting against the core it already has.
- Section 3: GAP — `encaps_internal` calls the section
  7.2 check itself, so a seam that replaced it without a
  check would drop the length discipline behind the seam.
- Section 6: WRONG — two contracts said to contradict
  `mlkem.py`: the decaps contract (a failing
  decapsulation-key check raises even at the right
  ciphertext size, and `TypeError` on non-bytes inputs)
  and the key_checks contract (the same `TypeError`
  point); plus the order-swapped share "silently
  accepted" if the swapped bytes pass the modulus check,
  and accepted behind the seam.
- Section 9: GAP — criteria 1 and 3 said to overlook the
  order-swap's probabilistic, real-mode-only refusal.
- What it would fuzz that the plan did not: duplicate
  key_share entries and fallback negotiation;
  ServerHello/HelloRetryRequest parsing on the client —
  naming the missing-key_share `KeyError` directly;
  the version 3 mailbox framing and reassembly;
  handshake fragment reassembly with hybrid-sized
  messages and its uncapped allocation.

Verification and disposition, recorded by Muse (stamp
00000000-muse-7e57-d0c5-58316a922026) after checking every
code claim by hand:

- The missing-key_share `KeyError` is REAL: a crafted
  plaintext ServerHello with the extension removed, fed
  to a client waiting for one, raised `KeyError(51)` out
  of `feed()` where every sibling refusal is a
  `DtlsError`. It is finding F-1 in the campaign record;
  the fix (the presence check `begin` and the
  HelloRetryRequest branch already had), the `client_feed`
  target and the pinning tests landed with this plan's
  commit series. This alone repaid the sitting.
- The section 3 GAP is not a gap in the harness as built:
  `AbstractOps.encaps_internal` does call the seam's
  check first (Argon could not see the harness). The plan
  now says so explicitly in section 3, which is the
  improvement the point earns.
- The section 6 WRONG is a wording verdict, not a
  behaviour one: the decaps contract was already
  conditioned on genuine keys in the plan's own sentence,
  and the harness only ever feeds byte strings. The plan
  now states both conditions in the contract lines
  themselves. Argon's underlying code facts (the
  decapsulation-key check inside `decaps`, the `len()`
  guards) are accurate.
- The order-swap point is accurate in kind and was
  already the plan's stated seam difference; Argon's
  exponent was off (768 coefficients, not 256) and the
  plan now carries the precise statement in section 6.
- The remaining proposals (duplicate entries, the
  carriage, fragment reassembly) are adopted into
  section 6 as named target families with their verified
  code bases; the `_hybrid_shared` asymmetry and the
  fragment allocation are recorded in section 10.
- Nothing in the review touched the timing conclusions or
  the run shape; the UNJUDGED sections stand as Argon
  left them, their files unsent by design.
