# The DTLS record layer against RFC 9147, and application messages that survive reordering

This is the record of a review of the three Internet-Drafts
(version 1 -04, version 2 -04 and version 3 -00) read against the
code that implements them, the defects the reading found, the
measurement that proved the largest one, and what landed. The
drafts' own text follows the code in a later revision; this file
is the statement of what the code now does, so the drafts have one
fixed thing to describe.

## Suppositions, written before the measurement

1. The application framing cannot survive what DTLS permits. Both
   bindings framed an application message as a 4-octet length
   prefix followed by the message, cut into records of at most
   1,200 octets, and the receiver concatenated record contents in
   arrival order. DTLS gives application data no order and no
   reliability (RFC 9147 Section 11). On the datagram binding a
   reordered or lost record should therefore misalign the stream;
   on the mail carriage, which sent one record per flight mail and
   assumes no order between mails (its own Section 7.3), the same
   should happen to any message larger than one record.
2. The record layer is not the RFC 9147 record layer. Reading
   `_RecordSealer` found the sequence number written to the wire
   in the clear (RFC 9147 Section 4.2.3 encrypts it in every
   protected record), no anti-replay window (Section 4.5.1), and an
   ACK body of 2-octet epochs and 6-octet sequence numbers where
   the RFC's RecordNumber is a uint64 pair (Section 7, Appendix
   A.1). A conforming DTLS 1.3 stack could not have opened a record
   this code sealed.
3. The external PSK was the shared secret's own octets. The same
   octets are the HMAC key of every job and the input keying
   material of the per-job encryption. RFC 9257's guidance for
   external PSKs is single-purpose keys.
4. Smaller disagreements between draft and code: the envelope's
   `key_id` match was a string comparison in the runner and a
   same-secret comparison in `send_job`; `issued_at` was parsed by
   whatever the box's Python `fromisoformat` accepted; the version
   2 question disclosed host facts at no tier while the version 1
   disclosure is tiered; the DTLS disclosure omitted
   `runner_version` at the `standard` tier the draft says carries
   it; the flight frame's media type was an unregistered
   standards-tree name; the answerer under `--dry-run` still spent
   a model call.

## The measurement (2026-11-06, before any change)

A probe established a version 3 session in process, sent one
5,000-octet application message, and handed the resulting flight
mails to the responder in three orders. The probe's output:

```
[in-order] 5000-byte message -> 5 flight mails
[in-order] delivered whole and intact: True; messages drained: 1
[in-order] follow-up 'after' delivered: True
[reversed] 5000-byte message -> 5 flight mails
[reversed] delivered whole and intact: False; messages drained: 0
[reversed] follow-up 'after' delivered: False
[one-lost] 5000-byte message -> 5 flight mails
[one-lost] delivered whole and intact: False; messages drained: 0
[one-lost] follow-up 'after' delivered: False
```

Supposition 1 held in full: reversed delivery lost the message and
every later message on the session; one lost mail did the same. On
a mailbox, reversed delivery is an ordinary day.

## What landed

### Application framing (both bindings)

Each application record's plaintext now begins with one flag
octet: 1 on the first record of a message, 0 on every later one.
The 4-octet length prefix follows the flag of the first record.
The records of one message carry consecutive record sequence
numbers, and the sender never interleaves two messages' records.
The receiver reassembles by sequence number: a message is
delivered the moment its last record is held, whatever order the
records arrived in; a continuation record whose first record has
not arrived is held for it; a message with a record missing is
delivered never and in part never, and is dropped whole once the
missing record has fallen outside the replay window (where the
record layer would refuse it anyway). Held octets are bounded at
twice the application message cap; past that the oldest pending
message goes. A later message is never blocked behind an earlier
incomplete one.

On the mail carriage, one application message is exactly one
datagram: every record of the message, and nothing else, in one
transfer. The carriage already reassembles a transfer's parts in
any order and drops duplicates, so a message needs no order between
datagrams at all. The carriage datagram ceiling rose from 262,144
octets to 4,390,912 (the application message cap of 4,259,840
plus 131,072 for record overhead): a message at the cap is 3,553
records and a 4,359,328-octet datagram, which is 179 parts at the
default chunk of 32,768 base64 characters, under the 1,024-part
bound. A 100 KB job is 5 parts. Incomplete reassembly state is now
bounded as a whole as well as per transfer: two datagrams' worth
across all pending transfers, oldest evicted first.

The same probe after the change: 1 flight mail for the 5,000-octet
message, delivered intact in every order, and the follow-up
delivered in every order. The unit tests that pin it are
`runner/tests/test_dtls_rfc9147_wire.py` (the datagram binding:
reversed, shuffled, lost, interleaved, orphaned) and
`runner/tests/test_dtls_email_v3_messages.py` (the carriage: one
transfer per message, parts reversed, duplicated, shuffled and
lost, two messages' mails interleaved, the ceiling arithmetic).

### The record layer (RFC 9147)

- Record number encryption (Section 4.2.3): each epoch and
  direction derives `sn_key = HKDF-Expand-Label(secret, "sn", "",
  32)`; the mask is AES-ECB under that key over the first 16
  octets of the record's ciphertext; the two leading mask octets
  are XORed into the 16-bit on-the-wire sequence number after the
  record is sealed, and the AEAD's additional data is the header
  with the plaintext sequence number. The ciphertext of this
  profile is never shorter than 17 octets (the content-type octet
  and the tag), so the RFC's padding rule for short plaintexts
  never applies. An opener written from the RFC text, not from the
  module, opens what the module seals (`test_dtls_rfc9147_wire.py`,
  `RecordNumberEncryptionTest`, and the live-handshake key
  schedule test in `test_dtls.py`).
- Anti-replay window (Section 4.5.1): 32,768 sequence numbers
  below the highest accepted, consulted after the record
  authenticates, so a forgery cannot move it. The width is the
  width the 16-bit sequence field allows a record to be
  reconstructed at all (Section 4.2.2: the receiver reads the
  closest candidate, so a record 2^15 or more behind the newest
  cannot be opened whatever the window says). That is 9 messages at
  the cap, or far more of ordinary size, arriving after a newer
  message on a store-and-forward path and still opening.
- The ACK message (Section 7, Appendix A.1): a 2-octet-length
  vector of RecordNumber, each a uint64 epoch and a uint64 sequence
  number. A body that does not parse as that does not end
  retransmission.
- KeyUpdate was already answered and never initiated; a received
  KeyUpdate installs the next epoch's keys, including its `sn` key.

### The PSK

The external PSK is `HKDF-Expand(HKDF-Extract(salt = empty, IKM =
UTF-8 octets of the secret), info = "homing-pigeon dtls psk v1",
L = 48)` with HMAC-SHA-384, at both ends, for the default secret
and every additional secret alike. PSK identities are unchanged. A
peer that offers the secret's own octets as the PSK, as the earlier
code did, fails its binder and is refused. The derivation is
recomputed from RFC 5869 alone in `test_dtls.py`'s
`KeyScheduleFromTheWireTest` and in `test_dtls_rfc9147_wire.py`.

### The rest

- The envelope's `key_id` and the inner body's `key_id` match when
  they name the same secret (the runner's `_admit_object` and
  `_verify_and_decrypt` now compare canonical names, as `send_job`'s
  verifier did), so the fingerprint on the envelope and the
  configured name inside is one key.
- `issued_at` must have the RFC 3339 `date-time` shape before
  Python's parser sees it: full date, `T`, full time, an optional
  fraction, `Z` or a numeric offset with its colon. Basic-format
  dates, a space separator, `+0000` offsets and week or ordinal
  dates are refused on every Python the same way. A date-time with
  no offset still fails later as "missing timezone", under its own
  name.
- The version 2 question's platform context is the platform card
  at the owner's `pong_platform` tier, the knob the ping card
  already uses; at `none` the question carries no platform segment.
- The DTLS disclosure carries `runner_version` at the `standard`
  and `full` tiers, as a ping does.
- The flight frame's media type is `application/vnd.homing-pigeon.dtls3`,
  a vendor-tree name (RFC 6838 Section 3.2) that a project can
  register through IANA's media-type process; the standards tree
  was never open to an Independent Submission.
- The answerer under `--dry-run` composes its answer from the local
  text and asks no model: a dry run spends nothing.
- Two tests that wrote secret files with the box's umask now write
  them owner-only, which is what the world-readable refusal of the
  secret-file reader requires and what the Linux and macOS legs had
  been failing on.

## What the drafts now have to say

Version 1 Section 19.2 and 19.3, version 3 Sections 5.3, 7.3 and
10.1, and both documents' security considerations describe the
code above when they state: the flag octet and the consecutive
sequence numbers of a message's records; reassembly by sequence
number and the drop-whole rule; one message per datagram on the
carriage with the new ceiling; the derived PSK and its info
string; the replay window and its width; the vendor-tree media type
and its registration template. The ACK encoding and the record
number encryption need no draft text of their own beyond the
citation of RFC 9147, which the code now earns.

## Limits stated plainly

- Both ends of every session are still this code. Interoperability
  with a second DTLS 1.3 implementation has not been tried; what
  changed is that the records, the ACKs and the sequence numbers
  now have the RFC's shape, checked against an opener written from
  the RFC rather than from the module.
- The replay window's width is also the carriage's reorder
  tolerance: a message more than 32,768 records older than the
  newest record accepted cannot be opened. On a mailbox that is 9
  messages at the cap, or thousands of ordinary ones.
- The derived PSK is a wire change for the DTLS binding and the
  carriage. Both ends must run this release or later.

## Ratification (2026-11-07)

Mixed-version DTLS interoperability is not supported across this
landing. Both ends must run the same side of it. Recorded as
accepted on 2026-11-07.
