# draft-homing-pigeon-v2-00

Homing Pigeon Message Protocol, Version 2: the DTLS Session Binding

Workgroup: Individual
Intended status: Informational
Expires: 19 April 2027
Author: Pigeon-Home (editor)

This document is not an IETF standard and is not the product of a working group. Publication as an RFC, if it happens, would be on the Independent Stream.

This revision specifies a direct session binding for the messages that draft-homing-pigeon-v1-00 specifies. The living implementation notes are in `PROTOCOL.md` in the homing-pigeon repository. Product release numbers are not protocol versions.

## Abstract

Version 1 of the Homing Pigeon message protocol (draft-homing-pigeon-v1-00) binds signed job and result objects to store-and-forward transports: email, watched files, and a message broker. This document specifies version 2, which changes the binding and not the messages: the same signed objects travel inside a direct DTLS 1.3 session between the submitter and the runner. The shared secret is the session's external pre-shared key; key exchange is ephemeral-only, so sessions have perfect forward secrecy; and once the handshake has authenticated the submitter, the runner opens the session with a greeting that discloses a tiered, responder-chosen summary of its platform. Version 2 is an addition, never a replacement: the version 1 bindings remain the ones every submitter can reach.

## Status of This Memo

This Internet-Draft is submitted in full conformance with the provisions of BCP 78 and BCP 79.

Internet-Drafts are working documents of the Internet Engineering Task Force (IETF). Note that other groups may also distribute working documents as Internet-Drafts. The list of current Internet-Drafts is at https://datatracker.ietf.org/drafts/current/.

Internet-Drafts are draft documents valid for a maximum of six months and may be updated, replaced, or obsoleted by other documents at any time. It is inappropriate to use Internet-Drafts as reference material or to cite them other than as "work in progress."

This Internet-Draft will expire on 19 April 2027.

## 1. Introduction

Version 1 of the Homing Pigeon message protocol is specified in [HP-V1] (draft-homing-pigeon-v1-00): the signed job and result objects, and their bindings to email and other store-and-forward transports. This document specifies version 2. The delta is one binding and one behavior on it: a direct DTLS 1.3 session between submitter and runner, with the shared secret as the session's pre-shared key (Section 4), and the session greeting the runner sends once the handshake has authenticated the submitter (Section 5). The messages do not change; everything in [HP-V1] that this document does not explicitly take up applies unchanged.

Version 1 needs no path between submitter and runner: a mailbox both can reach is enough, and the runner opens no listener. That is the right default, and it is also a ceiling. Where a direct path does exist -- the submitter can open a UDP flow to the runner's host -- a session buys three things the mailbox cannot: latency measured in round trips instead of poll cycles, confidentiality of the job and result objects themselves (not merely of one mail hop), and that confidentiality with forward secrecy.

Version 2 is exactly that trade, and nothing else. The job and result objects are the version 1 objects, byte for byte; their `v` member remains 1, and a receiver MUST NOT reject a session-carried object for carrying `v` = 1. What versions here is the binding. A receiver that implements only version 1 is not non-conformant; it simply does not offer this binding.

The cost is real, and it falls on the submitter. The version 1 bindings ask the submitter only to produce a signed object and hand it to a store-and-forward system it already speaks. This binding asks the submitter to terminate DTLS itself: the handshake, retransmission timers, connection IDs, session resumption -- a network stack obligation, discharged in the submitter's own environment. Many submitter environments cannot open a UDP socket at all. That is why this binding is version 2 and optional, why the greeting (Section 5) hangs on the session existing rather than on anything version 1 does, and why the email binding of version 1 remains the binding every submitter reaches. Section 6 states the conformance burden plainly.

Two consequences of a direct binding deserve emphasis up front. First, the runner listens: enabling this binding opens an inbound UDP listener on the runner's host, a posture version 1 deliberately never takes. The binding is therefore off unless an owner enables it; nothing about installing or running version 1 opens it. Second, channel security is not delivery. A session protects what crosses it while it lives; it acknowledges nothing at the protocol layer. Delivery, retry, and deduplication remain the protocol's own machinery (Sections 4.3 and 7.5).

## 2. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 3. Terminology

The terms of draft-homing-pigeon-v1-00 apply. In addition:

Session: one DTLS association between a submitter (the initiator, in the DTLS client role) and a runner (the responder, in the DTLS server role).

Greeting: the first application message of a session, sent by the runner after authentication completes (Section 5).

PSK identity: the `pre_shared_key` identity under which a secret is offered. The default secret's identity is `homing-pigeon`; an additional secret's is `homing-pigeon:` followed by its `key_id`.

Ticket: the opaque resumption identity a runner issues in a NewSessionTicket message.

LOCAL: as in version 1, a parameter a receiver sets for itself; it is not negotiated.

## 4. The DTLS Binding

### 4.1. Shape

The submitter initiates. The runner listens on a UDP port (LOCAL; the reference default is 20220, which is not registered -- see Section 8) only when the binding is enabled. One session carries any number of job and result messages in each direction while it lives. Roles do not reverse: the runner never initiates a session to a submitter.

### 4.2. The Profile

This binding is a bounded profile of DTLS 1.3 [RFC9147]. An implementation of this binding implements exactly this profile; a peer proposing anything outside it is refused, and the refusal ends that handshake, not the listener.

- Transport: DTLS 1.3 [RFC9147] over UDP. DTLS 1.2 MUST NOT be negotiated.
- Ciphersuite: TLS_CHACHA20_POLY1305_SHA256 [RFC8446] only. No other suite is offered or accepted.
- Authentication: pre-shared key only. The external PSK is the shared secret of version 1, under the identities of Section 3. Certificates are not part of this profile, in either direction. The shared secret MUST meet the minimum-entropy floor of version 1 (Section 16.3 of draft-homing-pigeon-v1-00); a secret below the floor MUST NOT be offered as a PSK.
- Key exchange: `psk_dhe_ke` only. The `psk_key_exchange_modes` extension MUST offer mode 1 and MUST NOT offer mode 0 (`psk_ke`); a responder MUST refuse a handshake that does not offer `psk_dhe_ke`. An ephemeral X25519 [RFC7748] key share MUST ride every handshake, full or resumed. Section 7.1 gives the reason: this is the profile's perfect-forward-secrecy requirement, and it is not negotiable within the profile.
- Address validation: the responder MUST perform the HelloRetryRequest cookie exchange of [RFC9147] before allocating session state, and MUST NOT send any flight larger than the retry itself before the cookie returns. The cookie is stateless and is bound to the initiator's address.
- Connection ID: both sides MUST negotiate the `connection_id` extension [RFC9146] and MUST accept records under the negotiated IDs from a changed source address, so that a NAT rebinding does not kill a session.
- Retransmission: handshake flights are retransmitted on the timers [RFC9147] specifies. Duplicate or retransmitted handshake messages are consumed exactly once per handshake; a duplicate MUST NOT corrupt the transcript or the session.
- Early data: none. 0-RTT MUST NOT be offered, sent, or accepted; epoch 1 keys are never derived.
- Resumption: a responder MAY issue a NewSessionTicket. A resumed session MUST use a fresh ephemeral key share (the `psk_dhe_ke` rule admits no exception for resumption), MUST be treated as a new session for greeting purposes (Section 5), and the ticket SHOULD be single-use.
- KeyUpdate: an implementation MUST NOT initiate KeyUpdate. An implementation that receives a KeyUpdate with `update_requested` set SHOULD answer it as [RFC9147] requires; an implementation MAY instead ignore KeyUpdate, and peers MUST NOT depend on it, as this profile never initiates one.
- Malformed input: a malformed or undecryptable datagram is dropped and logged. It MUST NOT be fatal to the listener or to any session but, at most, its own.

### 4.3. Carrying the Messages

Inside a session, application data is a stream of messages, each framed by a four-octet big-endian length prefix. Each message is one protocol envelope in the version 1 form: the subject line, a blank line, then the signed body, exactly as the email binding carries it. A job message is answered, in due course, by its result message on the same session.

Acknowledgement and deduplication are the protocol's own, unchanged: the runner's seen-set governs whether a job executes (Section 14 of draft-homing-pigeon-v1-00), the submitter retries per Section 15 of that document, and DTLS record protection contributes neither an acknowledgement nor a duplicate suppression at the protocol layer. A result produced after its session has died cannot be delivered on that session; the submitter learns of the loss by timeout, re-asks on a fresh session, and the seen-set makes the repeat safe.

### 4.4. Composition with Per-Job Encryption

The per-job encryption extension of version 1 (the `hp_enc` envelope) composes with this binding unchanged. A cleartext signed job inside a session and an encrypted job inside a session are both conforming; the layers are independent -- the envelope protects the object end to end including at rest, the session protects it in transit and adds forward secrecy to that transit. Neither layer's presence relaxes the other's checks: the envelope signature is verified before decryption, and the object signature is verified before execution, session or no session.

## 5. The Session Greeting

When a session's handshake completes -- the responder has verified the initiator's Finished and the session keys are live -- the RUNNER sends the session's first application message: the greeting. Three properties are normative.

- The greeting is post-authentication, never before. A responder MUST NOT send it before the handshake completes, and an unauthenticated peer harvests nothing from this binding: before authentication the only thing a stranger can obtain is the cookie exchange of Section 4.2.
- The greeting precedes work. A runner MUST NOT accept a job on a session before it has sent the greeting on that session.
- The greeting is the responder's choice. Its disclosure tier is the runner's LOCAL configuration. The initiator cannot request, negotiate, or widen it; this document defines no mechanism by which it could.

The greeting is a JSON object [RFC8259] in the protocol's idiom:

```
{"disclosure": "family",
 "platform": {"os_family": "linux"},
 "transport": "dtls",
 "type": "greeting",
 "v": 2}
```

The members `type` (always `greeting`), `transport` (always `dtls`), `v` (the binding version, 2), and `disclosure` (the tier in force) are always present. The `platform` member is present unless the tier is `none`, and its members depend on the tier:

- `none`: no `platform` member. The greeting still goes out; it says the session exists and nothing about the host.
- `family`: `os_family` only -- one of `windows`, `macos`, `linux`, `other`. This is the reference default.
- `standard`: `family` plus `os_release` (the operating system's release string) and `python_version` (the runner runtime's version).
- `full`: `standard` plus `path_tools`, an object naming a fixed, bounded set of common tools and whether each is on the runner's PATH.

The disclosure is proportioned the way the protocol already proportions result content: a deployment that answers jobs with full output discloses more in results than one that answers with attestations, and the same owner's posture, expressed as a tier, governs the greeting. The information itself is of the kind any job the runner accepts could observe by running; the greeting gives it to the authenticated submitter up front, where it is useful for choosing what to send (an interpreter name, a script form), without spending a job to learn it.

A resumed session is a new session for this section: the greeting MUST be sent again, under the tier in force at that time.

## 6. The Submitter's Conformance Burden

This section is candid because the version 1 Introduction's promise -- that a submitter needs nothing but the specification and tools it already has -- does not survive contact with a session binding, and a specification that hides its costs invites broken deployments.

A conforming version 2 submitter implements DTLS 1.3 in the profile of Section 4.2 for itself: the handshake state machine, PSK binders, the cookie exchange, handshake retransmission timers (a UDP peer that cannot retransmit cannot finish a handshake on a lossy path), connection IDs, and resumption. It needs a UDP path to the runner, which is an environment property, not a code property: a submitter running inside a hosted tool that offers only HTTPS egress, or no raw sockets at all, cannot use this binding no matter how correct its implementation is.

None of this is required of a version 1 submitter. Version 1 conformance is untouched by this document, a version 1 runner is a complete deployment, and an owner enables version 2 as an additional door on a host they choose, for submitters that can reach it. The bindings coexist: the same runner, the same secrets, the same objects; the session is a faster, confidential carriage for submitters equipped for it, and the mailbox remains for those that are not.

## 7. Security Considerations

### 7.1. Forward secrecy is a requirement, not a property

The profile's load-bearing rule is that `psk_ke` is prohibited. In `psk_ke`, session keys derive from the pre-shared key alone; anyone who later obtains the secret and has recorded the session decrypts it in full. Because this protocol's shared secret is long-lived and is also the job-signing key, that failure mode would be catastrophic and silent. In `psk_dhe_ke`, every session -- full or resumed -- mixes a fresh ephemeral X25519 secret into its keys, so a later compromise of the shared secret yields the ability to impersonate going forward (which the version 1 analysis already grants a secret-holder) but decrypts no recorded session. An implementation MUST NOT offer, accept, or fall back to `psk_ke`, including on resumption and including when a peer insists.

### 7.2. One secret, two constructions

The shared secret does two jobs in version 2: it is the DTLS external PSK, and it remains the HMAC key of the job and result objects. These are independent constructions (the TLS key schedule's HKDF derivation chain, and HMAC-SHA-384 over the object), and neither's outputs feed the other. The composition does not weaken the version 1 analysis: the session authenticates the channel, the signature authorizes the object, and a job's authority comes from the signature alone, so a job captured anywhere -- a mailbox, a session recording -- is exactly as powerful as it was in version 1, and replay is governed by the same seen-set and freshness rules. The offline-guessing analysis of Section 16.3 of draft-homing-pigeon-v1-00 applies to the PSK unchanged: the entropy floor is normative for the secret in both roles.

### 7.3. The greeting discloses

The greeting is a deliberate, bounded disclosure to an authenticated peer. Its bounds are its defenses: it is never sent before authentication, it contains no identifiers beyond platform shape (no hostname, no addresses, no user names, no filesystem paths beyond tool presence), its richest tier names a fixed tool set rather than enumerating the system, and its tier is set by the party being described. An owner who considers even the OS family sensitive sets `none` and the greeting still satisfies Section 5. What the greeting must never become is a negotiation: a future extension that lets the initiator ask for more would invert the design and MUST NOT be added compatibly.

### 7.4. Amplification and the listener

A UDP listener is a reflection surface. The cookie exchange is the mitigation this profile adopts: the responder is stateless and sends nothing larger than the retry flight until the initiator proves it can receive at its claimed address, so the binding cannot be used to amplify traffic at a third party beyond that small, fixed flight. The listener's other exposure is computational: handshakes cost more than datagrams. The stateless cookie keeps pre-authentication cost to one MAC verification per first hello; malformed datagrams are dropped at parse, and per-session failure is contained to the session.

Enabling this binding changes the host's posture from version 1's no-listener stance, and this document does not minimize that: the listener is off unless enabled, its port is LOCAL, and an owner who does not need the session binding should leave it off and lose nothing.

### 7.5. Channel security is not delivery

DTLS authenticates and encrypts records; it does not promise that a job arrived, ran, or was answered. This profile deliberately keeps the protocol's at-least-once semantics (Section 4.3) rather than letting a reliable-looking channel imply reliable delivery: sessions die (reboots, NAT timeouts past the connection ID's rescue, key exhaustion), and when one dies mid-exchange the loss is visible as a timeout, recoverable by a retry the seen-set makes safe. An implementation MUST NOT treat session establishment as job acceptance, nor session delivery of a result as its acknowledgement; the signed result message is the acknowledgement, as in version 1.

### 7.6. Termination in the middle

The confidentiality claim is end to end between the submitter and the runner process. A middlebox that terminates DTLS -- an inspecting proxy the path forces traffic through -- ends the claim at that box: the session is then confidential in two hops, and the operator of the middlebox can read job and result objects in clear, though the per-job encryption extension (Section 4.4) still protects an encrypted object past it. Deployments that route this binding through such a box should enable the object layer and understand which guarantee each layer is carrying.

## 8. IANA Considerations

This document has no IANA actions. The reference port, UDP 20220, is a LOCAL default of the reference implementation, not a registered assignment; deployments may use any port, and submitters learn the port out of band, with the address and the secret.

## 9. References

### 9.1. Normative References

[HP-V1] Pigeon-Home, "Homing Pigeon Message Protocol, Version 1", draft-homing-pigeon-v1-00, Work in Progress.

[RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, DOI 10.17487/RFC2119, March 1997, <https://www.rfc-editor.org/info/rfc2119>.

[RFC7748] Langley, A., Hamburg, M., and S. Turner, "Elliptic Curves for Security", RFC 7748, DOI 10.17487/RFC7748, January 2016, <https://www.rfc-editor.org/info/rfc7748>.

[RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, DOI 10.17487/RFC8174, May 2017, <https://www.rfc-editor.org/info/rfc8174>.

[RFC8259] Bray, T., Ed., "The JavaScript Object Notation (JSON) Data Interchange Format", STD 90, RFC 8259, DOI 10.17487/RFC8259, December 2017, <https://www.rfc-editor.org/info/rfc8259>.

[RFC8446] Rescorla, E., "The Transport Layer Security (TLS) Protocol Version 1.3", RFC 8446, DOI 10.17487/RFC8446, August 2018, <https://www.rfc-editor.org/info/rfc8446>.

[RFC9146] Thomson, M., Turner, S., and T. Reddy.K, "Connection Identifier for DTLS 1.2", RFC 9146, DOI 10.17487/RFC9146, April 2022, <https://www.rfc-editor.org/info/rfc9146>.

[RFC9147] Rescorla, E., Tschofenig, H., and N. Modadugu, "Datagram Transport Layer Security Version 1.3", RFC 9147, DOI 10.17487/RFC9147, April 2022, <https://www.rfc-editor.org/info/rfc9147>.

### 9.2. Informative References

[RFC3552] Rescorla, E. and B. Korver, "Guidelines for Writing RFC Text on Security Considerations", BCP 72, RFC 3552, DOI 10.17487/RFC3552, July 2003, <https://www.rfc-editor.org/info/rfc3552>.

[RFC8439] Nir, Y. and A. Langley, "ChaCha20 and Poly1305 for IETF Protocols", RFC 8439, DOI 10.17487/RFC8439, May 2018, <https://www.rfc-editor.org/info/rfc8439>.

## Author's Address

Pigeon-Home
<https://github.com/Pigeon-Home/homing-pigeon>
