# draft-homing-pigeon-00

Homing Pigeon Message Protocol, Version 1

Workgroup: Individual
Intended status: Informational
Expires: 19 April 2027
Author: Pigeon-Home (editor)

This document is not an IETF standard and is not the product of a working group. Publication as an RFC, if it happens, would be on the Independent Stream.

This revision specifies the on-wire messages and the receiver checks. It replaces the shorter narrative that was first committed in this file. The living implementation notes remain `PROTOCOL.md` in `github.com/Pigeon-Home/homing-pigeon` at commit `205f74e`. Product release numbers are not protocol versions.

## Abstract

This document specifies version 1 of the Homing Pigeon message protocol. A submitter places one HMAC-SHA-384 signed JSON object in an email to a mailbox. A runner polls that mailbox, verifies the signature, executes the job, and returns a signed result. The signature is the only authorization. The message is not encrypted. There is no inbound listener on the host that runs the job.

## Status of This Memo

This Internet-Draft is submitted in full conformance with the provisions of BCP 78 and BCP 79.

Internet-Drafts are working documents of the Internet Engineering Task Force (IETF). Note that other groups may also distribute working documents as Internet-Drafts. The list of current Internet-Drafts is at https://datatracker.ietf.org/drafts/current/.

Internet-Drafts are draft documents valid for a maximum of six months and may be updated, replaced, or obsoleted by other documents at any time. It is inappropriate to use Internet-Drafts as reference material or to cite them other than as "work in progress."

This Internet-Draft will expire on 19 April 2027.

## 1. Introduction

Some hosts cannot accept inbound connections. This protocol uses a store-and-forward mailbox as the only queue. The submitter does not open a connection to the runner. The runner does not open a connection to the submitter except to read and write that mailbox.

The exchange is two messages:

```
Submitter                         Mailbox                         Runner
    |                                 |                               |
    |  job email (signed JSON)        |                               |
    |-------------------------------->|                               |
    |                                 |  poll (IMAP)                  |
    |                                 |<------------------------------|
    |                                 |  result email (signed JSON)   |
    |                                 |<------------------------------|
    |  result (same mailbox, or       |                               |
    |   signed reply_to)              |                               |
    |<--------------------------------|                               |
```

Version negotiation is not a handshake. The message carries `v`. This document defines `v` = 1 only. A receiver that does not implement version 1 MUST reject the message.

## 2. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 3. Terminology

Job: a signed request that the runner execute work, or answer a liveness check.

Result: a signed report of what the runner did with one job.

Shared secret: an octet string known to the submitter and the runner. It is the HMAC key. It is not sent on the wire.

Default secret: the shared secret selected when `key_id` is absent.

Key identifier: the string in `key_id`. It is a label, not a secret.

Seen-set: the runner's record of `job_id` values already processed. It is local state. It is not a message.

Freshness window: how far `issued_at` may be from the runner's clock before the job is rejected.

Preamble: text in the mail body before the signed JSON object. It is not signed.

LOCAL: a parameter or a check this document allows a receiver to set for itself. It is not negotiated.

## 4. Scope

This document specifies subjects, the signed object, the MAC, `key_id`, `reply_to`, replay, freshness, the `job` message, and the `result` message.

This document does not specify disclosure policy, queries, attestations, task boards, sensors, confinement, installers, or local models. A job MAY carry extra members for those uses. Receivers that do not implement them MUST ignore unknown members (Section 8) and MUST still reject an unknown `v` or an unknown job `kind` (Section 12).

## 5. Transport

The runner reads the mailbox with IMAP and writes with SMTP. Mail authentication is out of band. The signature check does not change with the mail credential.

IMAP and SMTP SHOULD be used over TLS. TLS protects a hop. It does not hide the message from the mailbox provider (Section 16.2).

The body is UTF-8 text in a `text/plain` part. This document does not register a media type. If the message is multipart, the receiver uses the first `text/plain` part that is not an attachment.

The message MUST be rejected before the MAC if the raw RFC822 object exceeds the receiver's size cap. The RECOMMENDED cap is 4194304 octets. A cap of 0 means no limit. This cap is LOCAL.

## 6. Subjects

Subjects are matched case-insensitively. A preamble such as `Re:` MAY appear before the marker. The marker need not be the first character of the subject.

A job subject matches this pattern, in the sense of a search, not a full-string match:

```
[HOMING-PIGEON] (SP word)* SP job SP job-id
```

`word` is one or more visible characters. `job-id` is one or more visible characters with no space, further constrained below. The words between the marker and `job` are decoration. `TEST` is a legal decoration.

A result subject matches:

```
[HOMING-PIGEON] SP result SP job-id
```

ABNF [RFC5234] for the identifier only:

```
job-id      = 1*128 job-id-char
job-id-char = ALPHA / DIGIT / "." / "_" / "-"
```

The `job_id` in the subject MUST equal the `job_id` member. A mismatch MUST be rejected (Section 14).

`job-id` MUST NOT be `.` or `..`.

A UUID [RFC9562] is RECOMMENDED as the `job_id`.

A message whose subject is not a job subject is not a job. The receiver MUST NOT execute it. The receiver MAY mark it seen so that a later poll skips it. Result messages use the result pattern above and are produced by the runner. They are not jobs.

## 7. Body and Signature Marker

The signed object is one JSON object [RFC8259]. The receiver ignores preamble and trailer. Verification uses the object that ends in the signature marker.

Line endings are normalized before both signing and verifying: every CRLF becomes LF, then every remaining CR becomes LF. Trailing whitespace after that normalization is not part of the signed octets.

The sender builds the object without `sig`, serializes it, normalizes line endings, computes the MAC over those octets (Section 7.1), and replaces the final `}` with:

```
,"sig":"<96 hex digits>"}
```

JSON member order before `sig` is the sender's choice. `sig` MUST be last. Senders SHOULD serialize with no insignificant whitespace. Receivers MUST accept insignificant whitespace inside the object, because the MAC covers the octets the sender actually produced, not a re-encoding.

The receiver finds the signature as follows:

1. Normalize line endings and remove trailing whitespace.
2. Let `marker` be the last occurrence of the eight characters `,` `"` `s` `i` `g` `"` `:` `"`.
3. If `marker` is absent, the message is malformed.
4. The 96 characters after `marker` MUST be hexadecimal. The two characters after those MUST be `"` and `}`.
5. The signed octets are the bytes from the `{` that opens this object through the character before `marker`, plus one `}`.
6. That `{` is the start of the object that contains the marker, not a `{` inside a string. If no such `{` exists, the message is malformed.

A sender MUST NOT place the character sequence `,"sig":"` inside any string value. The receiver uses the last occurrence.

### 7.1. MAC

The MAC is HMAC-SHA-384 [RFC2104] using SHA-384 [FIPS180-4].

The HMAC key is the UTF-8 octets of the shared secret. Implementations MUST NOT hash, stretch, or otherwise derive that key. The secret is a string of characters. Two sides that disagree on the characters disagree on the key.

`sig` is the 48-octet HMAC value encoded as 96 hexadecimal digits. Senders MUST use lowercase digits. Receivers MUST compare in constant time after mapping ASCII `A-F` to `a-f`.

Receivers MUST reject a malformed tail. Receivers MUST reject a MAC mismatch. A mismatch produces no result email (Section 14).

### 7.2. Constant-time compare

The compare covers all 96 digits. It MUST NOT stop at the first differing digit in a way that a network observer can time. A local reject log MAY record that the MAC failed. It SHOULD NOT record the expected digest.

## 8. Unknown Members

A receiver MUST ignore object members it does not implement, except:

* `v` other than 1 MUST be rejected
* `type` other than `job`, on a message the receiver is executing as a job, MUST be rejected
* `kind` other than `exec` or `ping` MUST be rejected and MUST NOT be executed

Ignoring a member means the member is still covered by the MAC and has no effect on version 1 processing.

## 9. Common Members

| Member | JSON type | Presence | Rule |
|---|---|---|---|
| `v` | number | REQUIRED | Integer 1. No other value is defined. |
| `type` | string | REQUIRED | `job` or `result`. |
| `job_id` | string | REQUIRED | Section 6. |
| `key_id` | string | OPTIONAL | Selects the HMAC key. Absent selects the default secret. |
| `runner_id` | string | OPTIONAL | Audience claim. Enforcement is LOCAL. |
| `sig` | string | REQUIRED | Section 7. Not part of the signed octets. |

`key_id` is covered by the MAC. Key identifiers MAY appear in logs. An unknown `key_id` MUST be rejected before the MAC is computed. The receiver MUST NOT try another secret.

If a receiver enforces `runner_id`, the expected value MUST come from the receiver's configuration. The signed value is what the submitter claimed. It is not the source of the expected value.

## 10. Key Selection

The receiver holds a map from `key_id` to secret. The empty identifier names the default secret.

Selection, before the MAC:

1. If `key_id` is absent, select the default secret.
2. If `key_id` is present and is a string in the map, select that secret.
3. Otherwise reject. Do not compute a MAC.

How keys are stored is LOCAL. Two values MUST NOT be assigned to one `key_id`. The default identifier has one slot.

## 11. Job Message

`type` is `job`.

```json
{
  "v": 1,
  "type": "job",
  "job_id": "3f9a1c2e-7b14-4e0a-9c2d-6f0a1b2c3d4e",
  "issued_at": "2026-10-13T12:00:00Z",
  "kind": "exec",
  "script": "date\n",
  "timeout_sec": 60,
  "key_id": "submitter-a",
  "reply_to": "submitter@example.com",
  "sig": "001122...eeff"
}
```

The `sig` line above is abbreviated. On the wire it is 96 hex digits.

| Member | JSON type | Presence | Rule |
|---|---|---|---|
| `issued_at` | string | REQUIRED | Section 11.1. |
| `kind` | string | REQUIRED | `exec` or `ping`. |
| `reply_to` | string | OPTIONAL | Section 11.2. |
| `script` | string | see 11.3 | Inline script. `exec` only. |
| `script_url` | string | see 11.3 | `https` URL of the script. `exec` only. |
| `script_sha384` | string | OPTIONAL | 96 lowercase hex digits over the script octets. |
| `interpreter` | array of strings | OPTIONAL | Program, then its arguments. |
| `args` | array of strings | OPTIONAL | Appended after the script path. |
| `env` | object | OPTIONAL | String values merged into the environment. |
| `files` | array | OPTIONAL | Section 11.4. |
| `timeout_sec` | number | OPTIONAL | Positive integer. RECOMMENDED default 300. RECOMMENDED maximum 3600. |

### 11.1. issued_at

`issued_at` is UTC, `YYYY-MM-DDTHH:MM:SSZ`. A missing timezone MUST be rejected. A value that does not parse MUST be rejected.

Let `age` be the runner's clock minus `issued_at`, in seconds.

The receiver MUST reject the job if `age` is greater than its past window. The RECOMMENDED past window is 3600 seconds. That window is LOCAL.

The receiver MUST reject the job if `issued_at` is too far in the future. The RECOMMENDED future allowance is 300 seconds.

### 11.2. reply_to

`reply_to` is a single address, at most 254 characters, of the form `local@domain`, with no display name, no angle brackets, and no comma. The domain contains a dot.

If the member is absent, or present but invalid, the result goes to the runner's own mailbox. The job is not rejected for an invalid `reply_to`.

The receiver MUST take the result address only from this member. The email `From` header and the email `Reply-To` header MUST NOT select it.

### 11.3. ping and exec

`kind` `ping` carries no script. The runner MUST NOT start a script. The result has `kind` `ping`.

`kind` `exec` requires exactly one of `script` or `script_url`. If both are present, the receiver MUST use `script_url` and MUST ignore `script`.

If `script_sha384` is present, the receiver MUST hash the script octets with SHA-384 and MUST reject the job if the digest differs. The digest is 96 lowercase hex digits.

If `interpreter` is absent, the runner uses a LOCAL default.

The script is written to a new file in a fresh directory for this `job_id` and run as:

```
<interpreter...> <script-file> <args...>
```

The working directory is that job directory. On timeout the receiver MUST kill the process tree. `timeout_sec` above the receiver's maximum MUST be reduced to that maximum or the job MUST be rejected. The receiver MUST document which it does. The RECOMMENDED maximum is 3600.

### 11.4. files

Each element is an object:

| Member | JSON type | Presence | Rule |
|---|---|---|---|
| `name` | string | REQUIRED | File name inside the job directory. |
| `url` | string | REQUIRED | `https` URL. |
| `sha384` | string | OPTIONAL | 96 lowercase hex digits. |

`name` MUST NOT be absolute, MUST NOT contain `..` as a path segment, and MUST NOT escape the job directory. A violation MUST be rejected before the file is used.

Downloads MUST use HTTPS. If `sha384` is present, a digest mismatch MUST be rejected.

## 12. Kind and Type Failures

Unknown `kind` MUST NOT be executed.

A job the receiver rejects after the MAC has verified, because the kind, the script hash, the file name, or a similar check failed, MUST produce a result (Section 13) with `exit_code` -2 and a short reason in `stderr`. That job MUST be marked seen and MUST NOT be retried.

A job rejected before the MAC verifies produces no result. See Section 14.

## 13. Result Message

The result is signed with the same secret that verified the job. `key_id` on the result, if the sender includes it, MUST name that secret.

`type` is `result`. The subject is the result pattern in Section 6.

```json
{
  "v": 1,
  "type": "result",
  "job_id": "3f9a1c2e-7b14-4e0a-9c2d-6f0a1b2c3d4e",
  "kind": "exec",
  "completed_at": "2026-10-13T12:01:23Z",
  "exit_code": 0,
  "timed_out": false,
  "stdout": "",
  "stderr": "",
  "stdout_truncated": false,
  "stderr_truncated": false,
  "duration_sec": 12.345,
  "runner": "host.example",
  "sig": "001122...eeff"
}
```

| Member | JSON type | Presence | Rule |
|---|---|---|---|
| `completed_at` | string | REQUIRED | Same form as `issued_at`. |
| `kind` | string | REQUIRED | The job's kind. |
| `exit_code` | number | REQUIRED | Section 13.1. |
| `timed_out` | boolean | REQUIRED | True if the process tree was killed for time. |
| `stdout` | string | REQUIRED | Captured standard output. May be empty. |
| `stderr` | string | REQUIRED | Captured standard error. May be empty. |
| `stdout_truncated` | boolean | REQUIRED | True if `stdout` was cut. |
| `stderr_truncated` | boolean | REQUIRED | True if `stderr` was cut. |
| `duration_sec` | number | REQUIRED | Seconds, as a JSON number. |
| `runner` | string | REQUIRED | Host label. Authenticated only by the result MAC. |

### 13.1. exit_code

| Value | Meaning |
|---|---|
| 0 | The process exited 0, or `ping` succeeded. |
| -1 | `timed_out` is true. The process tree was killed. |
| -2 | Rejected before execution. Reason in `stderr`. Not retried. |
| other | The process exit status. |

If `timed_out` is true, `exit_code` MUST be -1.

### 13.2. Truncation

Each stream MAY be cut at a LOCAL byte limit. The RECOMMENDED limit is 100000 octets. When a stream is cut, its `*_truncated` member MUST be true. When it is not cut, that member MUST be false.

A result specified here includes the output the receiver chose to send. Omitting output for a local privacy policy is outside version 1. A submitter MUST NOT assume output will be withheld.

## 14. Receiver Processing

The receiver maintains a seen-set. The key SHOULD be `job_id` prefixed by the receiver's configured `runner_id` when one is configured, so two runners sharing a mailbox do not treat each other's jobs as replays.

For each unseen message:

1. If the subject is not a job subject, do not execute. This is not an error. Stop.
2. If the seen-set already contains this `job_id`, do not execute. Stop.
3. If the raw message exceeds the size cap (Section 5), reject with no result. Mark seen. Stop.
4. Select the key (Section 10). On failure, reject with no result. Mark seen. Stop.
5. Verify the MAC (Section 7). On failure, reject with no result. Mark seen. Stop. The `From` header is not an input to this step.
6. Parse the signed octets as one JSON object. If it is not an object, reject with no result. Mark seen. Stop.
7. If `v` is not 1 or `type` is not `job`, reject with no result. Mark seen. Stop.
8. If the subject `job_id` and the member `job_id` differ, or `job_id` is illegal (Section 6), reject with no result. Mark seen. Stop.
9. Check `issued_at` (Section 11.1). On failure, reject with no result. Mark seen. Stop.
10. LOCAL checks (audience, per-key policy) MAY reject here. A reject at this step MUST NOT execute the job. Whether a result is sent is LOCAL. The reference receiver sends no result for an audience failure.
11. If `kind` is `ping`, go to step 13.
12. If `kind` is `exec`, resolve the script and files (Section 11). On failure, send a result with `exit_code` -2, mark seen, stop. If `kind` is anything else, send a result with `exit_code` -2, mark seen, stop.
13. Execute. Honor `timeout_sec`.
14. Build the result (Section 13) and sign it with the secret from step 4.
15. Send the result to `reply_to` if that member is valid, otherwise to the runner mailbox.
16. If the send succeeds, mark seen. If the send fails, leave the job unseen. A later poll will execute it again (Section 15).

The email `From` address MAY be logged after step 5. It MUST NOT authorize the job. It MUST NOT choose the result address.

## 15. Retry

Delivery of the result is at-least-once.

If step 16 fails, the receiver MUST leave the job out of the seen-set. The next poll MUST be allowed to run the job again.

Submitters MUST treat `exec` as repeatable. A job that is not safe to run twice is not a conforming job.

A job marked seen is not executed again, including `exit_code` -2 and every no-result reject in Section 14.

## 16. Security Considerations

### 16.1. The signer controls the host

A valid MAC is permission to run as the runner's account. Anyone who holds the secret can operate the host. This protocol does not define a sandbox. LOCAL confinement MUST NOT be assumed by the submitter.

### 16.2. No confidentiality

HMAC authenticates. It does not encrypt. The mailbox provider can read every job and every result. An observer who can read the mailbox learns the script, the arguments, the environment, and the output. Confidentiality needs a mechanism this document does not define.

### 16.3. Offline guessing

One captured message is enough to test candidate secrets. More messages do not reduce that search. HMAC-SHA-384 does not yield the key from the tags.

The secret SHOULD be 32 octets from a cryptographic generator, stored as characters and used as UTF-8. Sixty-four hexadecimal characters are the usual form. A long human sentence is not a substitute. The secret SHOULD NOT be the mailbox password.

### 16.4. Headers are not authentication

`From`, `Reply-To`, `Sender`, and `To` MUST NOT satisfy the MAC and MUST NOT select `reply_to`. An invalid MAC MUST NOT cause any result to be sent.

### 16.5. Unknown key identifiers

Failing closed before the MAC stops a message from verifying under the default secret because of a typo, and it avoids using MAC time as a probe of which identifiers exist.

### 16.6. Replay

The past window rejects stale `issued_at`. The seen-set rejects a repeated `job_id`. A receiver with a wrong clock will accept stale jobs or reject fresh ones. A receiver whose seen-set is cleared will accept a replay that is still inside the past window. Jobs MUST be safe to repeat, because a lost result already causes a second execution.

### 16.7. Two secrets

The mailbox credential reads and deletes mail. The HMAC secret authorizes jobs. Neither substitutes for the other. A store that holds both has lost both when it is copied.

### 16.8. Marker collision

The splitter uses the last `,"sig":"`. A string value that contains that sequence will not verify as the sender intended. Senders MUST keep that sequence out of values.

### 16.9. Output

Version 1 results carry `stdout` and `stderr` up to the truncation limit. A receiver that wants to withhold output is implementing a different policy. That policy is not signaled by `v`.

### 16.10. At-least-once

An attacker who can drop the result mail can cause another execution. That is the same outcome as a failed send. Idempotent jobs bound the damage. This protocol does not add a separate ack.

## 17. IANA Considerations

This document has no IANA actions.

No new port, service name, media type, TLS extension, or object identifier is required. HMAC-SHA-384 is already named by [RFC2104] and [FIPS180-4]. The algorithm OID `hmacWithSHA384` (`1.2.840.113549.2.10`) already exists. This protocol identifies the algorithm by name, not by OID.

## 18. References

### 18.1. Normative References

[RFC2104] Krawczyk, H., Bellare, M., and R. Canetti, "HMAC: Keyed-Hashing for Message Authentication", RFC 2104, DOI 10.17487/RFC2104, February 1997, <https://www.rfc-editor.org/info/rfc2104>.

[RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, DOI 10.17487/RFC2119, March 1997, <https://www.rfc-editor.org/info/rfc2119>.

[RFC5234] Crocker, D., Ed., and P. Overell, "Augmented BNF for Syntax Specifications: ABNF", STD 68, RFC 5234, DOI 10.17487/RFC5234, January 2008, <https://www.rfc-editor.org/info/rfc5234>.

[RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, DOI 10.17487/RFC8174, May 2017, <https://www.rfc-editor.org/info/rfc8174>.

[RFC8259] Bray, T., Ed., "The JavaScript Object Notation (JSON) Data Interchange Format", STD 90, RFC 8259, DOI 10.17487/RFC8259, December 2017, <https://www.rfc-editor.org/info/rfc8259>.

[FIPS180-4] National Institute of Standards and Technology, "Secure Hash Standard (SHS)", FIPS PUB 180-4, DOI 10.6028/NIST.FIPS.180-4, August 2015, <https://doi.org/10.6028/NIST.FIPS.180-4>.

### 18.2. Informative References

[RFC3552] Rescorla, E. and B. Korver, "Guidelines for Writing RFC Text on Security Considerations", BCP 72, RFC 3552, DOI 10.17487/RFC3552, July 2003, <https://www.rfc-editor.org/info/rfc3552>.

[RFC9562] Davis, K., Peabody, B., and P. Leach, "Universally Unique IDentifiers (UUIDs)", RFC 9562, DOI 10.17487/RFC9562, May 2024, <https://www.rfc-editor.org/info/rfc9562>.

## Author's Address

Pigeon-Home
<https://github.com/Pigeon-Home/homing-pigeon>
