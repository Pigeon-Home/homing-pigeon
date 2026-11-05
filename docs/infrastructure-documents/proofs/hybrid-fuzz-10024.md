# Hybrid fuzzing: X25519MLKEM768 (RFC 10024) — suppositions, measurements, run record

This record covers a directed in-memory fuzzing effort against
the hybrid key agreement the version 3 carriage profile adds
to the DTLS engine: the X25519MLKEM768 group (RFC 10024,
value 4588), implemented in `runner/wire/mlkem.py` (ML-KEM-768,
FIPS 203, pure Python) and the hybrid share paths of
`runner/wire/dtlsproto.py`. The effort runs on the San
Francisco rig (1 vCPU, 2 GB), whose campaign lane is repointed
to it for the duration.

Method, fixed in advance: time the cryptography first, then
abstract the expensive operations behind a seam so the fuzz
loop can run at speed, run 1 hour against the real
cryptography first, then pull the abstraction in and keep
fuzzing. The standards vectors — the NIST ACVP ML-KEM-768
vectors in `runner/tests/fixtures/mlkem768_acvp.json`, the
RFC 7748 section 5.2 and 6.1 X25519 vectors, and a hybrid
vector constructed from those two sources — seed the corpus
throughout, in both modes, because they exercise the
expensive paths. Mutations follow the bookend rule: every
ASCII symbol, plus NUL, tab, CR and LF, at the front and the
back, alongside truncation, extension, bit flips and swapped
halves.

## Suppositions, written before any measurement (2026-11-05)

The only timings on record before this effort are the build
machine's, from the hybrid proof record in
`dtls-over-email-v3.md`: ML-KEM key generation about 7 ms,
encapsulation about 12 ms, decapsulation about 14 ms, a full
hybrid handshake about 70 ms against about 23 ms for X25519
only. The direction for this effort carries the expectation
that some of the cryptography described by RFC 10024 takes
0.5 seconds, a second, or a few seconds per operation. The
measurements below are the arbiter. Suppositions:

- ST1. No single ML-KEM operation reaches 0.5 s on the San
  Francisco rig. Expected: key generation 30–150 ms,
  encapsulation 50–250 ms, decapsulation 60–300 ms —
  decapsulation dearest, because it decrypts, re-encapsulates
  and compares. The rig's single vCPU is several times slower
  than the build machine, not seventy times slower.
- ST2. The X25519 operations scale the same way:
  `x25519_public` and the ECDH each land at 5–40 ms.
- ST3. The FIPS 203 checks are the cheap end.
  `encapsulation_key_check` (section 7.2: decode and
  re-encode, no NTT) lands under 25 ms;
  `decapsulation_key_check` (section 7.3: one SHA3-256 over
  the stored encapsulation key) lands under 5 ms.
- ST4. The composed paths are where a half-second could
  appear: the responder's hybrid answer (key check +
  encapsulation + ECDH) at 0.1–0.6 s, the client's hybrid
  shared secret (decapsulation + ECDH) at 0.1–0.4 s, both
  worsened by contention from other work on the 1 core.
- ST5. A full in-memory hybrid handshake (both cores, no
  mail) lands under 1 s on the rig. The seconds the carriage
  shows in live use are mail latency, not CPU.

Fuzz-shape suppositions:

- SF1. The ML-KEM primitive contracts hold under bookended
  mutation: decapsulation never raises on a 1088-octet
  ciphertext (implicit rejection), raises `MlkemError` only,
  and only on a wrong length; encapsulation raises
  `MlkemError` only; both key checks return a boolean and
  never raise, on any input.
- SF2. The wire paths refuse mutated hybrid shares and leave
  nothing behind: the responder length-checks the client
  share (1216 octets) before answering, the client
  length-checks the server share (1120 octets) before
  decapsulating, and the X25519 function length-checks both
  of its inputs — so no mutated share reaches a primitive at
  a wrong size, and a refused handshake leaves no session.
  The fuzz is expected to confirm this; any escape — an
  exception of another type, a session left registered, a
  crash — is a defect.
- SF3. The live defect surface, if any, is content, not
  size: a 1184-octet encapsulation key that fails the
  FIPS 203 section 7.2 check must abort the responder's
  answer, and a garbage key of exactly the right size is
  what exercises it.
- SF4. Behind the abstraction seam, the share parsing and
  the combiner behave the same on the corpus as against the
  real cryptography — the same accept and refuse pattern at
  the framing level — because the seam swaps only the KEM
  internals, at identical byte sizes.

## Measured timing conclusions (2026-11-05)

Measured with `runner/tools/hybrid_timing.py` (adaptive
repetitions, median of the runs). Two machines: the San
Francisco rig on its own dedicated core (the lane stopped,
nothing else running — the conditions the fuzzing itself
gets), and the build machine under its normal campaign
load, where the medians carry contention and the minima are
the cleaner figures.

San Francisco rig, median ms per operation:

| Operation | median ms | min ms |
|---|---|---|
| ML-KEM key generation | 20.81 | 16.38 |
| ML-KEM encapsulation | 33.52 | 25.68 |
| ML-KEM decapsulation, genuine ciphertext | 37.58 | 30.39 |
| ML-KEM decapsulation, corrupted ciphertext | 39.33 | 30.35 |
| Encapsulation key check (FIPS 203 7.2) | 7.88 | 5.65 |
| Decapsulation key check (FIPS 203 7.3) | 0.01 | 0.01 |
| X25519 public key | 3.92 | 2.81 |
| X25519 ECDH | 4.39 | 2.96 |
| Composed: responder hybrid answer crypto | 52.80 | 38.22 |
| Composed: client hybrid shared crypto | 42.11 | 33.61 |
| Full in-memory hybrid handshake | 233.80 | 177.86 |

Build machine under load, median ms (minima in brackets):
key generation 74.82 (12.44), encapsulation 91.50 (25.66),
decapsulation 102.35 (28.02), key checks 6.28 (3.10) and
0.01, X25519 3.24–4.29 (1.69–1.86), composed answer 100.69
(23.40), composed shared 164.52 (76.27), full handshake
397.31 (213.14). Against the quiet build machine figures
already on record (7 / 12 / 14 ms, handshake 70 ms), the
rig's single vCPU is about 3 times slower per operation,
and contention on a loaded machine costs more than the
machine difference does.

Verdicts on the suppositions:

- ST1 holds in its claim and misses in its ranges: no
  single operation is anywhere near 0.5 s — the dearest,
  decapsulation, is 37.58 ms — but the bands overshot:
  key generation 20.81 ms against 30–150 supposed,
  encapsulation 33.52 against 50–250, decapsulation 37.58
  against 60–300. Decapsulation is the dearest, as
  supposed, and a corrupted ciphertext costs the same as a
  genuine one (39.33 ms), as implicit rejection requires.
- ST2 near enough: the X25519 operations land at 3.92 and
  4.39 ms, just under the supposed 5–40 ms band.
- ST3 holds: the section 7.2 check is 7.88 ms (under 25
  supposed) and the section 7.3 check is 0.01 ms (under 5).
- ST4 misses low, in the safe direction: the composed
  paths land at 52.80 and 42.11 ms, under the supposed
  0.1–0.6 s and 0.1–0.4 s bands. On a dedicated core the
  half-second does not appear even composed. The direction
  that some of this cryptography takes 0.5 s to a few
  seconds per operation does not hold for CPU time on this
  rig; where seconds appear in live use they are carriage
  latency, as ST5 supposed.
- ST5 holds: a full in-memory hybrid handshake is
  233.80 ms on the rig, under the supposed 1 s.

## The abstraction seam

Built in `runner/tools/hybrid_fuzz.py`, as two
implementations of one contract. `RealOps` delegates to
`runner/wire/mlkem.py`. `AbstractOps` replaces the KEM
internals with deterministic, size-faithful stand-ins: the
encapsulation key is a SHAKE-256 expansion of the keygen
seed, the decapsulation key keeps the production byte
layout (so the production section 7.3 check passes on
abstract keys unchanged), encapsulation masks the message
with a keystream drawn from the encapsulation key and pads
deterministically, and decapsulation recovers the message
and derives the same secret — a wrong ciphertext yields a
different secret, never an error, keeping the implicit
rejection shape. Byte sizes, `MlkemError` discipline and
round-trip behaviour are identical at the seam; what is
abstracted away is the NTT arithmetic and the section 7.2
modulus check (the abstract key check is the length only).
The `apply_ops` context manager patches the ops into the
DTLS engine's view of the `mlkem` module — `keygen`,
`encaps_internal`, `decaps`, `encapsulation_key_check` —
so the share parsing, the length discipline and the RFC
10024 combiner in `dtlsproto.py` run for real in both
modes, and restores the module on exit. The unit tests pin
the seam: both ops satisfy the same contract suite, and a
full hybrid handshake completes behind `AbstractOps` with
the hybrid group negotiated.

## Run record

fy_iceworld is the campaign's name in prose; the tool and
test paths keep their own names, as the project's campaign
names do. Corpus, seeded up front so the fuzzing does not
spend rounds rediscovering what the standards already fix:
the ACVP ML-KEM-768 vectors (key generation,
encapsulation, decapsulation including the modified
ciphertext whose secret is the rejection value, and both
key-check groups), the RFC 7748 vectors, the RFC 10024
fixed sizes (client share 1216, server share 1120, secret
64) as the mutation lines, and the hybrid vector assembled
from the ACVP key-generation entry and the RFC 7748 pair.
22 unit tests in `runner/tests/test_hybrid_fuzz.py` pin the
corpus, the per-field mutation discipline, the seam and a
bounded run of each mode; they pass on the build machine
and on the rig (22 tests, OK, both).

Deployment, 2026-11-05: the rig's tree was synced to the
current code (its campaign checkout predated the hybrid),
the lane script was repointed (the previous script is kept
beside it as `lane.sh.pre-hybrid`), and the lane relaunched
detached. Phase A started 2026-11-05T23:36Z: 1 hour against
the real cryptography, seed 10024. First verdict lines:
round 2750 at 46 s elapsed, findings 0, MemAvailable
1523 MB against the 128 MB floor — a pace of about
60 rounds a second, about 215,000 rounds projected for the
hour. On phase A's clean exit the lane marks it done and
phase B begins automatically: abstract mode, passes of
3300 s with rotating seeds. A finding (exit 3) instead
stops the campaign: the lane heartbeats every 300 s and
the finding waits for review. The watchdog's own relaunch
of the lane during the swap is recorded here because it
shaped the start: it restarted the previous workload once,
which was stopped by hand before the repointed lane
launched; exactly 1 lane runs now (lane pid in
`/opt/hp-rig/cpu-pump/lane.pid`, fuzz child under it,
verified from the process table and the advancing logs,
`lane.log` and `hybrid-fuzz.log` in the same directory).

Phase A verdict and phase B rounds are appended here as
they land.
