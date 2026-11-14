# CS_canoe — design notes

Working notes for the hosted service, opened by the conductor on
2026-11-14. In conversation the project is called Canoe; in
documentation it is CS_canoe.

## Shape

Two components:

- **Component A — transport and identity.** A transport service with
  fast, simple login (a Google/Gmail-style sign-in, or a provider login
  of the same shape), authentication, and a database-backed account
  layer that can hold keys for customers who want that. Cloudflare was
  the first sketch for the transport; it is set aside for the first
  cut (see the first flow below).
- **Component B — hosting and approval.** The conductor hosts the
  infrastructure himself, under a company he sets up, inside a hard
  spend ceiling he sets (the shape discussed: $1000 to $5000). Every
  customer is approved manually by the conductor. The conductor is his
  own first customer.

## The first flow: the owner as the first customer

1. The owner has a Gmail account.
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
  account's email address — the Gmail login, in the first case — and
  pulls it.
- Naming: it is "the secret", or "the private secret". It is never
  called a master secret.

## Process

These notes live on the cs_canoe branch so the other seats can comment
and work against them. When the design has been flushed out further,
the conductor syncs back with Muse and the work is reconciled.
