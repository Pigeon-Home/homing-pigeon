# Future, section A as of 2026-10-25: the decisions behind what shipped

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

Historical record. `docs/project/future.md` lists only work that is
not built; the owner asked for the finished items to leave it. These
are the entries as they stood, kept for the decisions they carry (the
hard requirements, placements and defaults DRU set). The live docs
describe the shipped state.

**A1. Per-job encryption, over the existing email binding.** Chosen
direction (DRU, over the DTLS-session alternative): encrypt the job
object itself to the runner, an AEAD under a key derived from the
shared secret, so confidentiality rides every pipe an SI can reach,
with no session, no listener and no new burden on the SI. Honest
scope: end-to-end across store-and-forward hops, which hop TLS never
gives; it does not create a session and has no forward secrecy.
Decisions of record (DRU): specified in the current draft (Section
16) as a protocol requirement, no second document, neither version
axis moves; and encryption is ON by default, with `--cleartext` as
the explicit, never silent, way down for an older runner. Built:
`runner/wire/jobcrypto.py` (AES-256-GCM, HKDF-SHA-384, stdlib only),
`send_job.py` encrypts by default, results mirror the job's form with
`job_encryption` as the override. Live docs describe the shipped
state; this entry is the decision.

**A2. DTLS 1.3 with the shared secret as the external PSK.** A direct
binding of protocol version 1 where the channel gives confidentiality
and authentication and the HMAC becomes defense in depth. An addition,
never a replacement: many SI environments cannot open a UDP socket,
and the SI would have to terminate DTLS itself. Hard requirement
(DRU): perfect forward secrecy, `psk_dhe_ke` only, `psk_ke` never
offered; a DTLS extension without it is not worth building. Built as
the dtls transport extension: `runner/wire/dtlsproto.py` (one
ciphersuite, stateless cookies, Connection IDs), `runner/transport_extensions/dtls/`,
client `runner/cloud/send_dtls.py`, draft Sections 19 to 22. The
follow-on is C13.

**A3. The session's first acknowledgment carries the platform.** The
DTLS session gives a real first message, so the runner greets with
what the SI needs before the first job: OS family at the tightest
posture, versions and PATH tools at the open ones, chosen by the
responder, sent only after authentication. Built with A2: the
`dtls_greeting` tiers (none, family, standard, full), re-run on
resumption, draft Section 20. The same card now rides a ping's result
(B6).

**A4. The Oracle's opinion as a result member.** Built (DRU):
`docs/design/oracle-opinion-design.md`, PROTOCOL 3.1 and 3.2,
`runner/oracle/opinion.py`: diagnose, advise and repair latitudes
under the `oracle_opinion_mode` ceiling, deterministic tier-1 checks,
an optional labeled model note, and the one mechanical repair (absent
interpreter to platform default), re-judged before it runs. What
remains is E1 and C11.

**A5. One declaration, not three.** Resolved 2026-10-22, the day it
was filed: the manifest's `upstream` block is the one declaration.
`fetch_upstream.py` keeps the pinned files for the build and the
drift tests, `extsources.py` hands the same files to the Oracle as
`pinned` under the recorded digests, and a `sources.json` entry says
`"upstream": true` to fetch more. `upstream.json`, the provenance
bundles and `vendor_upstreams.py` were retired. A pin bump touches
one file.

**A6. Job review once bodies are encrypted.** Built:
`runner/oracle/review.py`, and bodies are encrypted by default. The
separate Oracle signing key the same entry asked for is C11.

**A7. The local test chat.** The whole exchange on one box, acting as
the cloud SI in-process and reading the result directly; no mail is
sent. `--local-test`; `docs/archive/handoff-local-si.md`.

**A8. The firewall posture line.** On or off, with the T1562.004
change alert, shipped. The ruleset hash and the cage-held check are
C12.

