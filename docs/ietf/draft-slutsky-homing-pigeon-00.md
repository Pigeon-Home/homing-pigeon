# draft-slutsky-homing-pigeon-00

Homing Pigeon Message Protocol, Version 1

Workgroup: Individual
Intended status: Informational
Expires: 19 April 2027
Author: Andrew Slutsky (editor)

This document is not an IETF standard and is not the product of a working group. It describes an existing protocol. Publication as an RFC, if it happens, would be on the Independent Stream.

Extracted from `PROTOCOL.md` in `github.com/Pigeon-Home/homing-pigeon` at commit `205f74e` (16 October 2026). That file remains the living spec for the implementation. This draft does not track product release numbers.

## Abstract

This document specifies version 1 of the Homing Pigeon message protocol. A submitter sends a job to a mailbox. A runner on a host that has no inbound listener polls that mailbox, checks an HMAC-SHA-384 signature, runs the job, and sends a signed result. The signature is the only authorization. The message is not encrypted.

## Status of This Memo

This Internet-Draft is submitted in full conformance with the provisions of BCP 78 and BCP 79.

Internet-Drafts are working documents of the Internet Engineering Task Force (IETF). Note that other groups may also distribute working documents as Internet-Drafts. The list of current Internet-Drafts is at https://datatracker.ietf.org/drafts/current/.

Internet-Drafts are draft documents valid for a maximum of six months and may be updated, replaced, or obsoleted by other documents at any time. It is inappropriate to use Internet-Drafts as reference material or to cite them other than as "work in progress."

This Internet-Draft will expire on 19 April 2027.

## 1. Introduction

Some hosts cannot accept inbound connections. This protocol uses a mailbox as the queue. The submitter writes a signed JSON object into an email. The runner reads the mailbox, verifies the signature, and writes a signed result back.

The originating project calls the submitter an SI. This document says "submitter". The name does not appear on the wire.

The integer `v` inside a message is the protocol version. It is 1. Product release numbers are a different series and are out of scope.

## 2. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 3. Scope

This document specifies:

* the email subject lines that identify a job and a result
* one signed JSON object carried in a text body
* HMAC-SHA-384 over that object, using the UTF-8 bytes of a shared secret and no key derivation
* the optional `key_id` and `reply_to` fields
* replay and freshness checks
* the job message and the result message

This document does not specify local disclosure policy, result views, queries, attestations, task boards, sensors, confinement, installers, or any local model. Those are properties of one implementation. A job that adds fields for them still uses `"v": 1`. Receivers that do not understand those fields ignore them (Section 6).

## 4. Actors

Submitter: builds a signed job and sends it to the mailbox. Reads the signed result.

Runner: polls the mailbox, verifies the job, executes it, and sends the result.

Either side may hold the work. The message format does not change if the runner is the side that composes jobs.

## 5. Transport

One dedicated mailbox carries both directions. The submitter sends jobs to that mailbox. By default the runner sends results to that same mailbox.

Access from the runner is IMAP for reading and SMTP for sending. Authentication to the mail provider is out of scope. The signature check is the same whichever mail credential is used.

Messages are ordinary email. This protocol does not define a new media type. The body is UTF-8 text.

IMAP and SMTP SHOULD be used over TLS. TLS protects a hop. It does not hide the message from the mailbox provider (Section 14).

### 5.1. Subjects

A job subject contains the literal `[HOMING-PIGEON]`, then zero or more words, then the literal `job`, then the `job_id`. A `Re:` prefix or an extra word such as `TEST` is allowed. Matching of this pattern is case-insensitive.

A result subject is:

```
[HOMING-PIGEON] result <job_id>
```

`job_id` contains no spaces. The `job_id` in the subject MUST equal the `job_id` in the signed body. A mismatch is rejected.

## 6. Message Format

The body is UTF-8 text. It contains one JSON object. Text around that object is ignored. The object that ends with the signature is the one that is verified.

Every signed message ends with a `sig` member. `sig` is lowercase hexadecimal. Receivers MUST ignore object members they do not recognize. They MUST NOT ignore an unrecognized `v` or an unrecognized `type` on a message they intend to execute: `v` other than 1 is rejected, and a job `type` other than those in Section 8 is rejected.

JSON key order is the sender's choice, except that `sig` is last on the wire (Section 7).

### 6.1. Common members

`v`: integer. This document specifies only the value 1. Any other value MUST be rejected.

`type`: string. This document specifies `job` and `result`.

`job_id`: string, 1 to 128 characters from the set `A-Z`, `a-z`, `0-9`, `.`, `_`, and `-`. The values `.` and `..` MUST be rejected. A UUID is RECOMMENDED.

`key_id`: OPTIONAL string. Names which shared secret verifies this message. Absent means the default secret. The member is inside the signed object. Key identifiers are labels. They are not secret, and they MAY be written to logs. An unknown `key_id` MUST be rejected before any MAC is computed.

`runner_id`: OPTIONAL string. An audience claim. Whether a receiver enforces it is local policy. If the receiver enforces it, the expected value comes from the receiver's own configuration, not from the message. The member is covered by the signature when present.

`sig`: string. 96 lowercase hexadecimal characters (48 bytes), the HMAC-SHA-384 output (Section 7).

## 7. Signatures

The MAC is HMAC-SHA-384 [RFC2104] with SHA-384 [FIPS180-4]. The key is the UTF-8 bytes of the shared secret. There is no hash, salt, or other derivation. The secret is not sent in the message.

The construction avoids a canonical JSON encoding by appending the signature:

1. Serialize the object without `sig`. Compact or pretty, any key order.
2. Normalize line endings to LF: replace CRLF with LF, then replace remaining CR with LF.
3. Compute HMAC-SHA-384 over those octets. Encode the 48-byte result as 96 lowercase hex digits. That is `sig`.
4. Transmit the serialized object with its final `}` replaced by `,"sig":"<sig>"}`.

Verification:

1. Normalize line endings to LF.
2. Find the last occurrence of the ASCII sequence `,"sig":"`. The bytes after that marker MUST match 96 lowercase hex digits, a quote, and a closing brace. Otherwise reject.
3. The signed octets are everything before that marker, plus one `}`.
4. Recompute the HMAC and compare with `sig` in constant time.

A sender MUST NOT emit a payload whose normalized text contains `,"sig":"` except as the real signature marker. The receiver uses the last occurrence.

## 8. Jobs

A job is a message with `"type": "job"`.

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
  "sig": "<96 lowercase hex digits>"
}
```

`issued_at`: UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ`. The receiver MUST reject a job whose `issued_at` is missing, unparseable, or further from the receiver's clock than its freshness window. The RECOMMENDED window is 3600 seconds.

`kind`: `exec` or `ping`.

`reply_to`: OPTIONAL. A single mailbox address, at most 254 characters, matching a conventional `local@domain` form with no display name and no comma. When it is valid, the result is sent there instead of to the runner mailbox. When it is absent or invalid, the result is sent to the runner mailbox. The address is taken only from this signed member. The email `From` header MUST NOT select the result destination. An invalid signature MUST NOT cause a result to be sent to anyone.

### 8.1. ping

A `ping` job carries no script. The runner does not execute a script. It returns a result whose `kind` is `ping`. This is a liveness check.

### 8.2. exec

An `exec` job carries work for the host.

`script`: OPTIONAL inline script text.

`script_url`: OPTIONAL https URL whose body is the script.

Exactly one of `script` or `script_url` is REQUIRED. If both are present, `script_url` is used.

`script_sha384`: OPTIONAL. When present, 96 lowercase hex digits. The receiver MUST reject the job if the script octets do not match.

`interpreter`: OPTIONAL array of strings. The first element is the program. The rest are its arguments. If absent, the runner chooses a local default.

`args`: OPTIONAL array of strings, appended after the script path.

`env`: OPTIONAL object whose values are strings, merged into the process environment.

`files`: OPTIONAL array of objects with `name`, `url`, and OPTIONAL `sha384`. `url` is https. `name` MUST NOT escape the job directory. When `sha384` is present it MUST be checked.

`timeout_sec`: OPTIONAL positive integer. The RECOMMENDED default is 300. The RECOMMENDED maximum a receiver will honor is 3600.

Unknown `kind` values MUST be rejected and MUST NOT be executed.

## 9. Results

A result is a message with `"type": "result"`. It is signed with the same secret that verified the job.

```json
{
  "v": 1,
  "type": "result",
  "job_id": "3f9a1c2e-7b14-4e0a-9c2d-6f0a1b2c3d4e",
  "kind": "exec",
  "completed_at": "2026-10-13T12:01:23Z",
  "exit_code": 0,
  "timed_out": false,
  "stdout": "...",
  "stderr": "...",
  "stdout_truncated": false,
  "stderr_truncated": false,
  "duration_sec": 12.345,
  "runner": "host.example",
  "sig": "<96 lowercase hex digits>"
}
```

`completed_at` uses the same timestamp form as `issued_at`.

`exit_code` 0 is success. `timed_out` true means the process tree was killed; `exit_code` is then -1. `exit_code` -2 means the job was rejected before execution. The reason is in `stderr`. A rejected job is marked seen and MUST NOT be retried.

`stdout` and `stderr` MAY be truncated. The matching `*_truncated` boolean is true when that stream was cut. A receiver that needs a byte limit SHOULD document it. 100000 bytes is the RECOMMENDED default.

`runner` is a human-readable host label. It is not authenticated beyond the signature on the result.

`duration_sec` is a number of seconds.

## 10. Verification Order

The receiver performs these checks in order. Failure means the job is not executed. The message is marked seen so it is not retried, except for a result that could not be sent (Section 11).

1. Select the secret from `key_id`, or the default secret if `key_id` is absent. An unknown `key_id` fails here, before the MAC.
2. Check the signature (Section 7).
3. Check the subject (Section 5.1) and require the subject `job_id` to equal the body `job_id`.
4. Require `v` of 1 and `type` of `job`.
5. Check `issued_at` against the freshness window.
6. Reject a `job_id` already in the seen-set.
7. If the receiver enforces audience, require `runner_id` to equal the configured value.

The email `From` address is not a check. It MAY be logged. It MUST NOT authorize the job.

## 11. Replay, Freshness, and Retries

Two controls limit replay. `issued_at` rejects a stale message. The seen-set rejects a `job_id` already processed. The seen-set key SHOULD include the receiver's `runner_id` when one is configured, so two runners that share a mailbox do not treat each other's jobs as replays.

Delivery is at-least-once. If the result email is not sent, the job stays unseen and will be processed again. Submitters MUST treat execution as repeatable. A job that is not safe to run twice is a broken job, not a broken receiver.

A signature failure, a stale timestamp, a replay, or a rejected job is marked seen and is not executed again.

## 12. Multiple Secrets

A deployment MAY hold more than one secret. `key_id` selects among them. The default secret has no `key_id` on the wire.

Rotation does not need a new message version. The holder of a secret adds a new `key_id`, both keys verify during the overlap, submitters switch, and the old key is removed. Two values MUST NOT be assigned to one `key_id`. Retired secrets SHOULD NOT be reused.

How a deployment stores keys is out of scope. The wire requirement is only that the signed `key_id` selects the key, and that an unknown identifier verifies against nothing.

## 13. Execution

These requirements exist so two implementations agree on what a signed `exec` job did.

The receiver creates a fresh working directory for the `job_id`.

The script is written to a file in that directory and run as the interpreter, then that file, then `args`. The working directory is the job directory. `env` is merged into the environment.

On timeout the receiver kills the process tree.

File downloads use HTTPS only.

## 14. Security Considerations

### 14.1. The signer owns the host

A valid signature is permission to run the job as the runner's account. Anyone who holds the secret can operate the host. This protocol does not provide a sandbox. Local confinement, if any, is outside this document and MUST NOT be assumed by the submitter.

### 14.2. There is no confidentiality

HMAC-SHA-384 authenticates the message. It does not encrypt it. The mailbox provider, and anyone who can read the mailbox, can read every job and every result. Operators who need confidentiality need a mechanism this document does not define.

### 14.3. One message is enough to test a guess

An observer who captures one signed message can test candidate secrets offline. Further messages do not reduce that work. HMAC-SHA-384 does not leak the key as more tags are collected.

The secret SHOULD be 32 bytes from a cryptographic random generator, used as UTF-8 (for example 64 hexadecimal characters). A secret an observer can guess from a phrase is not saved by a long length. The secret SHOULD be distinct from the mailbox password.

### 14.4. The envelope is not trusted

`From`, `Reply-To`, and any other email header MUST NOT choose the result address and MUST NOT satisfy authentication. `reply_to` is honored only as a signed member. Unsigned or invalid jobs produce no result mail.

### 14.5. Unknown key identifiers

An unknown `key_id` fails before the MAC. The receiver does not try other secrets. This stops a message from probing which identifiers exist by timing a MAC, and it stops a typo from verifying under the default secret.

### 14.6. Replay and duplicate execution

The freshness window assumes rough clock agreement. A receiver whose clock is wrong will accept stale jobs or reject fresh ones. The seen-set is local. An attacker who can clear it, on a receiver that also has a wide freshness window, can submit the same job again. Jobs MUST be safe to run more than once because a lost result already causes a second run.

### 14.7. Mailbox credential and signing key

The mailbox credential and the HMAC secret are different secrets. The mailbox credential can read and delete mail. The HMAC secret can authorize jobs. Holding only the mailbox credential does not create a valid `sig`. Holding only the HMAC secret does not, by itself, deliver a job to a runner that polls a mailbox the attacker cannot write to. A deployment that stores both in one file has lost both when that file is copied.

### 14.8. The signature marker

Verification splits on the last `,"sig":"`. A payload that contains that sequence will not verify as the sender intended. Senders MUST keep that sequence out of field values, or they MUST treat a failed verify as the expected outcome.

### 14.9. What this document does not hide

A result specified here includes `stdout` and `stderr`. Cutting, redacting, or replacing that output is a local policy. It is not part of version 1 interoperability. A submitter MUST NOT assume a receiver will withhold output unless that behavior is agreed out of band.

## 15. IANA Considerations

This document has no IANA actions.

## 16. References

### 16.1. Normative References

[RFC2104] Krawczyk, H., Bellare, M., and R. Canetti, "HMAC: Keyed-Hashing for Message Authentication", RFC 2104, DOI 10.17487/RFC2104, February 1997, <https://www.rfc-editor.org/info/rfc2104>.

[RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, DOI 10.17487/RFC2119, March 1997, <https://www.rfc-editor.org/info/rfc2119>.

[RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, DOI 10.17487/RFC8174, May 2017, <https://www.rfc-editor.org/info/rfc8174>.

[FIPS180-4] National Institute of Standards and Technology, "Secure Hash Standard (SHS)", FIPS PUB 180-4, DOI 10.6028/NIST.FIPS.180-4, August 2015, <https://doi.org/10.6028/NIST.FIPS.180-4>.

### 16.2. Informative References

[RFC3552] Rescorla, E. and B. Korver, "Guidelines for Writing RFC Text on Security Considerations", BCP 72, RFC 3552, DOI 10.17487/RFC3552, July 2003, <https://www.rfc-editor.org/info/rfc3552>.

## Author's Address

Andrew Slutsky
Editor
Pigeon-Home
<https://github.com/Pigeon-Home/homing-pigeon>
