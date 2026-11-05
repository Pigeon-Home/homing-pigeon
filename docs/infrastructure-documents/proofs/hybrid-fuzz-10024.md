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

## Measured timing conclusions

(To be filled in after the timing runs, in this same place,
from `runner/tools/hybrid_timing.py` output on the rig and
on the build machine.)

## The abstraction seam

(Design as built, recorded with the harness landing.)

## Run record

(Rounds, verdicts and any findings, per phase: 1 hour
against the real cryptography, then the abstracted
continuation. Corpus and harness:
`runner/tools/hybrid_fuzz.py`; unit tests:
`runner/tests/test_hybrid_fuzz.py`.)
