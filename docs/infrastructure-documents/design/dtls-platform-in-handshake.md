# DTLS platform disclosure in the handshake

## The problem

A sender needs the runner's platform before the first job:
the operating-system family determines the script form, and
the default interpreter and protocol versions determine how
the job is built. A separate greeting sent as the first
application message answers that need on a live datagram
path, but it leaves an avoidable gap in the session's shape.
The initiator has finished the handshake, yet before sending
work it must wait for one more message. On a store-and-forward
carriage that wait becomes another poll, with no local signal
that distinguishes "established, disclosure still in flight"
from "established, nothing more is coming."

## The mechanism

The platform disclosure now rides in the handshake itself.
The server places a configuration-style extension, type
`0xFFA0`, in its EncryptedExtensions. `0xFFA0` is an interim
Private Use value (RFC 8446, RFC 8447: first byte 255). It
is not an IANA assignment, and it is not `0xFE00`. The
extension value is the disclosure object: `disclosure` and,
except at the `none` tier, the `platform` member built by
`runner/wire/platformcard.py`. The old greeting members
(`type`, `transport`, `v`) are not sent, and the bytes have
no trailing newline.

The pattern is lifted from IKEv2's Configuration Payload
(RFC 7296, section 3.15). IKEv2 carries configuration
attributes inside its authenticated IKE_AUTH exchange rather
than in a message after the exchange; this design carries
platform attributes inside the final DTLS handshake flight
rather than in application data after it. The encoding is
not IKEv2's: the payload stays in this protocol's JSON idiom.

The extension is sent on every fresh handshake and on every
resumption, under the disclosure tier in force at that time.
The existing `dtls_greeting` tiers keep their names and
meanings. At `none`, the extension still rides, carrying the
tier and no `platform` member. At `family`, `standard` and
`full`, the `platform` member carries the corresponding card.

The extension is solicited, never unsolicited. The initiator
includes the extension type, empty, in its ClientHello: the
offer says only that it can receive the disclosure, and it
asks for nothing. The responder sends the extension only to
an initiator that offered it -- an extension the client did
not offer is not sent (RFC 8446, section 4.2). A peer that
does not offer still handshakes; it simply receives no
disclosure.

## Client behaviour

EncryptedExtensions arrives before the server's Finished in
the same flight. The client holds the extension's payload as
pending while the flight is processed and publishes it as
its `greeting` object when the server Finished verifies --
the point at which the initiator considers the connection
established. A sender therefore never has to choose between
sending its first job and waiting for a separate disclosure
message: by the time it may send, it already holds the
platform.

For interoperability, a current client also accepts the
older form: when no platform extension arrived, a legacy
runner's first application message is still surfaced as the
same `greeting` object.

## Security shape

EncryptedExtensions is encrypted under the handshake traffic
keys. Those keys are derived from the pre-shared key and a
fresh ephemeral exchange, so a party that does not hold the
PSK learns nothing from the platform payload. The server
builds the extension only after the peer's PSK binder has
verified. The client does not surface the payload until the
server Finished has verified.

Disclosure remains the responder's choice. The tier is local
configuration; the initiator cannot request, negotiate or
widen it. The payload names platform shape only -- operating
system, interpreter, protocol versions, and at the higher
tiers release, runtime and a bounded set of tool presences --
never hostnames, addresses, user names or secrets.

## What changed for jobs

Jobs are ordinary application messages once the session is
established. There is no greeting application message and no
application-layer rule that work must wait for one. The
handshake carriage itself is the ordering guarantee: the
disclosure is in the flight that establishes the session.
