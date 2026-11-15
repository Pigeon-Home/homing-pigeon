# CS_canoe — design notes

Working notes for the hosted service, opened on
2026-11-14. In conversation the project is called Canoe; in
documentation it is CS_canoe.

## Shape

Two components:

- **Component A — transport and identity.** A transport service with
  fast, simple login (a Google sign-in, or a provider login
  of the same shape), authentication, and a database-backed account
  layer that can hold keys for customers who want that. Cloudflare was
  the first sketch for the transport; it is set aside for the first
  cut (see the first flow below).
- **Component B — hosting and approval.** The operator hosts the
  infrastructure himself, under a company he sets up, inside a hard
  spend ceiling he sets (the shape discussed: $1000 to $5000). Every
  customer is approved manually by the operator. The operator is his
  own first customer.

## The first flow: the owner as the first customer

1. The owner has a mail account.
2. He goes to the signup page (pigeonhome.ai, /signup) and signs in
   with Google.
3. On the back end — a hosted auth and database layer, Supabase or
   something of that shape — the sign-in automatically provisions the
   account and an inbox for the user. For the first cut, the user's
   own email inbox is the mailbox.
4. Cloudflare is ignored for the first cut.

## Runner linking

- When a user logs into the runner on their local system, they link
  the runner to their pigeonhome.ai account.
- The runner does not ask the user to paste their shared secret, and
  does not ask whether they want to generate a new one.
- Instead, the system looks up the secret associated with that
  account's email address — the provider login, in the first case — and
  pulls it.
- Naming: it is "the secret", or "the private secret". It is never
  called a master secret.

## Process

These notes are working notes, kept with the design pages so the
design can be worked against. When the design has been flushed out
further, the work is reconciled into the design of record.

## The secret is generated, not derived (later the same day)

- Considered and set aside: deriving the secret by hashing one of
  the OAuth login's ephemeral secrets. The operator's ruling: we
  are already running locally, so there is nothing to derive from —
  generate a local random secret through the proper random channels
  instead.
- The mailbox is already there when this runs: a browser (OAuth)
  login means the system can send and receive email through that
  mailbox, so a generated secret can be emailed to the user by the
  system itself.

## The third login option

- The login choices today are two: an app password, or a browser
  login (OAuth, the Thunderbird shape).
- CS_canoe adds a third: the browser login plus autogen shared
  secret — the browser login setting with "+autogen shared secret"
  added to it.
- The flow at first run: the system sees there is no shared secret
  and asks — you don't have a shared secret, do you want to generate
  one? The usual answer is yes. The secret is generated locally, at
  random, and emailed to the user.

## The inbox is the record

- The emailed secret arrives as a note: the Homing Pigeon shared
  secret was installed on this system, with the basic facts of that
  system — platform, hostname, IP address, memory, hard drive.
- The inbox then holds two things at once: full remote access
  control, configurable, and the record of what that mailbox was set
  up for — which system, which install, which facts.

## The alternative not taken, for now

- A database of our own (Supabase or something of that shape) where
  the operator gives people a free email address and the address
  looks up to a global shared secret. Workable, but it requires the
  operator to operate infrastructure.
- The inbox flow needs none of that: the user's own inbox doubles as
  the infrastructure the operator would otherwise have had to hold
  up himself.

## Big, small — the design principle

- The project is a million big-small solutions. Every time a small
  problem comes up, it can be solved with the big solution; every
  time a big problem comes up, it can be solved with two small
  problems.
- That is what makes things atomic. It is the same move as
  concurrency: the solution to concurrency is defining what an
  atomic operation is on the platform.

## The fourth option, future

- The first three options all ride the email inbox as the
  transport. A fourth option, for later: log in with Google, then
  authenticate to Cloudflare — and the transport becomes Cloudflare
  (queues) instead of the inbox.
- Same sign-in, same account; only the transport changes. The Google
  identity carries over, and the pairing stays super simple.
