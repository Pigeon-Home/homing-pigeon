# Tunnel chaining: the chain hop

A chain carries one job envelope across two or more runners in
sequence, where no single network path joins the sender to the
final runner. Each leg of the chain is a hop. Carried media move
each hop: on the file transport, the watched folders are the
pipe, and a person or a scheduled copy carries the envelope file
from one runner's outbox to the next runner's inbox. The
protocol gains no new cryptography from chaining. A chain is
built entirely from the envelope machinery that already carries
jobs: the signed body, the `hp_enc` envelope, and the key map.

## The chain hop, defined

A chain hop is one leg of a chain, and it is exactly this:

1. The sending side seals a chain body under the hop secret.
   The seal is the ordinary one: the chain body is signed, the
   signed body is encrypted into an `hp_enc` envelope, and the
   envelope is signed again, bound to the chain id the way an
   envelope is bound to its job id.
2. The chain body carries the next hop's envelope whole, as
   text: its subject line and its body, byte for byte what the
   next runner will receive. To the relay that carries it, that
   text is opaque.
3. The receiving runner verifies only its own hop, and then
   writes the carried envelope text to the outbox of the
   channel the chain envelope arrived on. It executes nothing.

The chain envelope's subject follows the standing subject
grammar, with the kind word `chain`:
`[HOMING-PIGEON] chain <chain_id>`. The chain id names the hop
the way a job id names a job: the envelope's decryption is
bound to it, and the replay cache keys on it.

## The chain body

The object inside the envelope is a chain body, a signed JSON
object with these members:

| Member | Meaning |
| --- | --- |
| `v` | The protocol version, as on a job. |
| `type` | The string `chain`. |
| `chain_id` | The chain id, equal to the id in the subject. |
| `issued_at` | The sealing time, UTC, held to the same freshness window as a job. |
| `to` | An optional routing label naming the next runner. It is advice for the operator's eye only; no check reads it. |
| `next_subject` | The subject line of the next hop's envelope. |
| `next_body` | The body of the next hop's envelope, whole and unmodified. |

## The rules

One shared secret per hop. A hop secret is an ordinary entry in
the runner's key map, named by its `key_id` like any other key.
The envelope and the chain body inside it verify under the
same key, the standing rule for every encrypted object this
suite admits.

The relay verifies only its own hop. It checks the outer
signature, decrypts the envelope, verifies the chain body's
own signature, and checks the body's type, its chain id
against the subject, and its freshness. It does not verify,
decrypt, or judge the next hop's envelope. That envelope
belongs to the next runner and the next hop's secret.

The relay forwards byte for byte. What lands in the outbox is
exactly the subject and body the chain body carried, so the
next runner receives the envelope its sender sealed for it,
untouched by the relay's hands.

The relay holds only its own hops' secrets. It never needs the
carried job's secret, and it cannot read the carried job: the
final hop's envelope is sealed under the final hop's secret,
which the relay does not hold. A relay that is handed a second
hop's secret by its operator can of course open what that
secret seals; the design asks the operator not to hand it one.

Replay is answered the standing way. The chain id enters the
runner's replay cache under the same namespacing as a job id.
A second copy of the same chain envelope is a replay: it is
logged, it is taken, and it is not forwarded again.

Refusal is answered the standing way. A chain envelope that
fails its signature, its decryption, its type, its chain id,
or its freshness is refused: the refusal is logged, an
`auth_rejection` event is recorded in the runner's security
events, the envelope is taken so it cannot wedge the channel,
and nothing is forwarded. The cleartext form of a chain body
is refused under the same rule as a cleartext job: the
signature only form is admitted only when the runner was
started with `--allow-cleartext`.

The final hop is an ordinary job envelope. The last runner in
the chain receives a job like any other job, verifies it under
the final hop's secret, and runs it. Nothing in the job says
it arrived by chain, and nothing in the result says so either.

## What a chain does not do

A chain gives no forward secrecy, here or anywhere this
construction is described: each hop's key derives from a
static shared secret, so compromise of a hop secret exposes
every recorded envelope that hop ever carried. That is the
stated price of confidentiality on a store and forward
binding with no session, and chaining inherits it per hop.

A chain is not a tunnel in the network sense. No connection
stays open, no packets flow, and no runner in the chain needs
a route to any other. Where a linked path does exist, the
version 3 carriage remains the way to use it; the chain is
for the gaps the carriage cannot cross.
