# Privacy research: the Fremont Derby inventory

This document records a study of the privacy work in another
project's repository, made so the learnings can be applied here.
It states what was found, where, and in what state. The design
that applies it is `privacy-design.md`; the survey of privacy
models is `privacy-models.md`.

The learnings come from the Fremont Derby project, a fantasy
pool league web application (Node/JavaScript, Supabase,
Cloudflare). The privacy thinking there is principally the work
of Jason Lambert (JFL), the project's owner, whose concerns are
written as issue cards in the repository; the implementation
work is his and, on a fork, this project's author's. The fork is
`ctf-gooo-003/fremontderby`; the upstream is
`Fremont-Derby/fremontderby`. Both are public. The study was
made on 2026-11-08 against upstream `main` at `6f4e6468`, the
full branch set (1,735 branches), and the issue record.

## 1. Which branches are which

The study was asked to find a "host branch" carrying the fork
author's changes and an "archive branch" implementing much of
the privacy work. The evidence:

**The host branch is `fremontderby-dru`.** It holds 312 commits
not on `main`, 310 of them by the fork author's own identity
(`ctf-gooo-003`, the fork account), spanning 2026-08-18 to
2026-10-10, changing 551 files (+36,940 lines). The name is also
literal: `main`'s `wrangler.jsonc` defines `env.dru` as the
deployed host `dru.fremontderby.com` with `ENVIRONMENT=dru` and
`SUPABASE_SCHEMA=dru`. The branch is the author's hosted lane.
(The 45 branches named `dru/issue-*-host-*` are not it: they are
hostname-to-environment lockstep tests around
`src/hostEnvironment.js`, authored in one early wave, with no
privacy content.) The peer lane branch `fremontderby-jfl` is
larger (+66,711 lines) and newer, but 454 of its 456 unique
commits are by `subiki` -- Jason Lambert's account -- and its
subjects are uniformly the JFL lane. `fremontderby-gamma` is a
promotion target for the author's work, not a separate source.

**No archive branch implements the privacy work.** The branch
named for archiving, `dru/issue-3223-fake-archive`, does the
opposite: its only unique commits (by Andrew Slutsky) *remove* a
made-up archive line from the season page -- "fake archive"
means the archive text was fabricated, not that the branch is
an archive. The one genuine archive, `dru-backup-6-october-2026`,
is a dated snapshot of the author's lane (an ancestor of
`fremontderby-dru`, later restored from), and its privacy
content is inherited and sentence-level (section 4.3). An
exhaustive scan of all 1,735 branch tips and of all history
found only 11 files ever added anywhere with privacy, scrub,
redact, vault, retention or personal in the name; every
mechanism among them is on `main` or is recorded in section 4.
The substantive privacy implementation beyond `main` is on the
JFL lane (section 4.1).

## 2. The issues: 77 privacy cards

158 issues mention "privacy" and 377 mention "private"; the 77
below are the ones substantively about personal-data handling,
consent, exposure, redaction, retention or session isolation.
61 were authored by `subiki` (Jason Lambert -- the repository
"is owned by the personal `subiki` account", issue 1173, and the
cards are written in a product-owner voice); 16 are
implementation and tracking cards by the fork author's agent
accounts (`ctf-gooo-001`, `ctf-gooo-003`) that state the rule
they implement. 25 are open, 52 closed. Issue numbers are the
upstream repository's.

### 2.1 Consent and social messaging

The flagship programme. The governing principle, stated as
product-owner direction in 3295: participation in the league
does **not** imply consent to social communication.

| # | State | Card |
|---|-------|------|
| 3295 | open | Social messaging off by default; exactly 3 channels (General, Team, DMs), each independently opt-in and reversible; no 4th channel without a new product-owner decision. Parent of the family. |
| 3301 | closed | Enforce explicit DM consent: both parties' *current* consent required, for new and existing threads, stale clients and direct table writes alike. |
| 3302 | closed | Implementation of 3301: default-off preference, atomic storage gates, sorted account locks serialising sends against opt-out. |
| 3304 | closed | Independent General and Team chat opt-in: membership never implies social consent; opt-out blocks reads and sends at the storage level. |
| 3305 | closed | Implementation of 3304. Enabling one channel never enables another, or DMs. |
| 3307 | open | Retire free-form matchup chat: a 4th surface outside the consent model is removed rather than consent-managed; coordination moves to structured actions and narrow Notices; history retained read-only. Verified; awaiting independent adversarial sign-off (3311). |
| 3310 | closed | Implementation of 3307. |
| 3311 | open | Adversarial verification of the consent boundaries by the *other* lane: the owner's own tests explicitly cannot satisfy acceptance. |
| 3575 | closed | Prove live three-channel consent persistence and restoration through the real UI, then restore original values; no real users or messages. |
| 3577 | closed | A throttled (HTTP 429) privacy save could fail while the saved value stayed on, and the UI could not say so: distinguish throttling, show the wait, never report an unconfirmed save as success. |
| 3578 | closed | Implementation of 3577. |
| 77 | closed | Direct player messaging without exposing contact details: in-app messaging so phone and email are never required or exposed. |
| 148 | closed | Implementation of 77, with two-way blocking. |
| 78 | closed | Private team chat scoped to effective membership, so teammates need not exchange personal contact details; explicitly no per-matchup chat (the early statement of 3307). |
| 176 | closed | Communication engagement without exposing private messages: admin metrics as counts and timestamps only; unreported message bodies never returned by analytics. |

### 2.2 Phone numbers and contact data

| # | State | Card |
|---|-------|------|
| 335 | closed | Private captain phone contact: required only of captains, private league-administration data, never a directory field; broad surfaces expose only `has_phone`; audits must not copy historical values. |
| 401 | closed | Implementation of 335: the `private.player_contacts` boundary, admin-only single-player detail, all contact RPCs service-role only. |
| 1706 | open | Prove captain phones are admin-only, as anonymous/player/captain/admin, across UI *and* direct API; the number must not appear in public HTML, payloads, logs or unrelated exports. |
| 751 | closed | Mask phone by default (last 4 only), full number only on explicit reveal, save responses stay masked, contact URLs excluded from caches, sign-out clears contact caches. |
| 2886 | open | Reconcile an admin phone-save migration that exists in the repository but was never applied live and targets the wrong schemas; do not blindly apply. |
| 792 | closed | Privacy-aware autocomplete: suggestions only after 2+ characters, capped results, so search cannot enumerate the player directory. |
| 3113 | closed | State the contract on the Profile page, locked by test: "Privacy: phone is stored as a label, not a value." |

### 2.3 Inventory, logs, telemetry and machine-learning data

| # | State | Card |
|---|-------|------|
| 1705 | open | Inventory stored personal data: per field, why stored, who may read/write, where it appears, retention/archive behaviour, whether it may enter logs or analytics. Documentation only. |
| 3058 | closed | Implementation slice of 1705: the inventory names fields, never values (its test asserts no phone-shaped value appears). |
| 3096 | closed | Same rule for the field list (name, phone, Fargo id named; values never shown). |
| 1707 | open | Keep PII and secrets out of application logs: exercise the sensitive paths with known test values and inspect the logs. |
| 173 | closed | Privacy-safe telemetry: an allowlisted event contract (environment, player ID, rotating session ID, event, outcome, normalised error code, broad device class); never message text, tokens, raw IP, exact location, query strings, full user-agent or arbitrary exception payloads; 90-day raw-event retention. |
| 1671 | closed | Regression-lock the telemetry helper: dimension keys matching phone/token/password/email/message/body/authorization are stripped; string values over 64 characters dropped. |
| 2262 | open | Telemetry, label and privacy contracts for QA collection and ML: versioned schemas, pseudonymous tester/session IDs, explicit rejection of sensitive categories, notes treated as sensitive, retention/deletion defined for raw events, notes, derived features and model datasets. |
| 2297 | closed | Implementation of 2262: a JSON Schema contract for QA evidence with executable privacy rejection; fails closed unless the lane is the test lane. |
| 2261 | open | The closed-loop learning epic: ML is legitimate only on privacy-contracted evidence (2262 family). |
| 2264 | open | Capture client errors and correlate safe server failures without broad session surveillance: allowlisted failures, semantic breadcrumbs rather than raw clicks or replay, redaction proven by tests. |
| 2268 | open | ML-ready dataset and leakage-safe evaluation: export only approved/redacted fields; group same-seed runs so they cannot leak across train/test splits. |
| 172 | closed | Feature-friction feedback without private-data leakage; no user can read another's friction history. |
| 1748 | open | Hesitation metrics as counts, timestamps and concise notes only; explicit pass line: "No keystroke surveillance, private message capture, or unnecessary personal data." |
| 1704 | open | Tester feedback shortcut prefilled with environment/SHA context, passing only if it includes no secrets, tokens, private message content or unnecessary PII. |
| 1722 | open | Admin diagnostic bundle: environment, SHA, route, safe aliases/IDs, reference IDs; excludes tokens, keys, phone numbers, private message bodies, service-role data. |
| 1738 | open | Scan repository history and generated artifacts for secret patterns; findings name file and path without printing the secret. |
| 1708 | open | Audit privileged changes with actor, time, reason and before/after, "without secret/PII overcapture"; users cannot alter audit history. |

### 2.4 Session isolation

One user's data must never surface in another's session. All
closed and verified unless noted.

| # | State | Card |
|---|-------|------|
| 3586 | closed | Discard message previews from an earlier browser session: a delayed account-A summary rendered after the tab switched to account B. |
| 3587 | closed | Implementation of 3586: per-request ownership, session checks after fetch *and* after body parsing. |
| 3604 | closed | Clear Messages history and drafts on session change: A's unsent draft remained, composer enabled -- a draft typed by A could have been sent under B's credentials. |
| 3605 | closed | Implementation of 3604. |
| 3606 | closed | Scope Notices to the current session: A's notice stayed visible under B, and Mark read issued a POST for A's notice using B's credentials (server refused; a UI isolation defect). |
| 3609 | closed | Implementation of 3606. |
| 3292 | closed | Keep delayed message history in its own conversation: a late "load older" response merged the previous conversation's messages into the newly selected thread. |
| 3618 | closed | Invalidate operator drafts and actions when sign-in changes: stale forms could dispatch a write using old data under replacement credentials. |

### 2.5 Notifications, row-level security, lane isolation

| # | State | Card |
|---|-------|------|
| 2545 | closed | Close public read access on notifications *before data lands*: `user_notifications` had RLS disabled with anonymous SELECT -- "do not rely on zero current rows as a security boundary." |
| 2300 | closed | Pin the notification trigger's search path and revoke direct execution from browser roles. |
| 2887 | open | The DRU-lane twin of 2545, worse: RLS disabled, anonymous SELECT granted, 56 rows already present. A test environment must not normalise insecure access patterns that could be copied toward production. |
| 2884 | open | Reconcile non-production hygiene findings deliberately (the same pattern in 3 places, plus stale lane binding secrets); explicitly not authorising broad cleanup. |
| 296 | closed | Enable RLS on 11 private operational tables, revoke all browser privileges, deliberately add no browser policies (deny by default), with a regression test locking the exact table set. |
| 1193 | open | Verify environment bindings after a regression in which test-lane domains reported `environment: production`: a lane resolving to production config can expose or mutate production data. Release-blocking. |
| 717 | closed | Prove JFL/DRU/Gamma data isolation on shared staging: writes in one lane's schema invisible through another lane's profile, including gamma not reading DRU private admin tables. |
| 577 | closed | Safe production-to-gamma refresh: one-way, fail-closed, production credentials never injected into the gamma Worker, scrub policy applied to the copy. |
| 1070 | closed | Implementation of 577: fail-closed preflight, scrub policy, dry-run default. |
| 1383 | closed | Test-lock that the scrub policy's statement list is non-empty, so a refresh never copies secrets/PII blindly. |
| 1173 | closed | Move the repository to an organisation and enforce separate JFL/DRU identities: separate dedicated actors that must not share a credential; branch rulesets per lane. |
| 874 | closed | Public contributor trust boundary: public visibility grants no product, agent, operational or deployment authority; untrusted PRs run without secrets or deploy rights. |
| 2310 | open | Admin-only recent QA survey results: aggregates only, never tester/session IDs, notes or raw events; fail-closed to the test schema. |
| 2311 | closed | Implementation of 2310, reusing the existing admin boundary rather than adding a second evidence-reading surface. |
| 3355 | closed | Regression-lock the aggregate QA-feedback projection so it cannot silently widen. |

### 2.6 Moderation evidence, archive, retention, history

| # | State | Card |
|---|-------|------|
| 1733 | open | Preserve report evidence without exposing unrelated private messages: the moderator retains only the reported message snapshot needed; retention follows the 1705 inventory. |
| 2581 | closed | Implementation slice of 1733: the moderation page states a report keeps the reported message and does not open unrelated private messages; a test locks the sentence. |
| 1694 | open | The umbrella epic: data behaviours that must stay correct across seasons -- privacy boundaries, auditability, immutable competition history, archival, recoverability -- as small independently testable child cards. |
| 1714 | open | Archive invariants: an archived season leaves all active queues, sends no notifications, stays readable to authorised users, read-only except explicit restore. |
| 1740 | open | Prevent hard deletion of entities with competition history: archive/deactivate or reject, server-side. |
| 337 | closed | Close a completed season without destroying history: Close is not Cancel, Archive or Delete; closure stops mutation and preserves historical public read access. |
| 414 | closed | Cancel, archive and safe-delete lifecycle actions with distinct meanings: safe-delete only for demonstrably empty draft/test seasons, rejected at the database boundary otherwise. |
| 3223 | closed | Not a personal-data issue: the live season page displayed invented archive-rule lines. Removal card 3224; the fix removed the made-up lines, no database apply. |

### 2.7 Public surface, errors, accidental exposure

| # | State | Card |
|---|-------|------|
| 248 | closed | Public search/sharing metadata with an explicit privacy acceptance criterion: no player contact details, private application state, message content, payment status, auth identifiers or admin-only data in metadata or crawlable HTML. |
| 1701 | open | User-safe errors with recovery text and reference IDs: "UUIDs, stack traces, tokens, SQL, and provider internals are not shown." |
| 453 | closed | API returned raw database UUID errors to clients (duplicate of the canonical fix card 477). |
| 505 | closed | Internal test/war-game identities (bot names, lane persona names) visible on public registration standings: synthetic data bleeding into the public surface. |
| 2669 | closed | One tested slice grouping the privacy rules: phones/tokens out of logs (1707), the inventory (1705), public-safe error text (1701). |
| 2687 | closed | Tested slice including 1706: a captain's phone hidden from a player. |

## 3. The mechanisms on `main`

35 distinct privacy-relevant mechanisms were inventoried in the
code on `main`. The table gives each one's home and how it is
switched; the behaviours are stated in the design principles
that follow.

| # | Mechanism | Where | Switched by |
|---|-----------|-------|-------------|
| 1 | Privacy-safe telemetry: counters only, dimension keys matching phone/token/password/email/message/body/authorization dropped, string values over 64 chars dropped | `src/privacySafeTelemetry.js` | Always on when called. Note: defined and tested, no production caller found on `main`. |
| 2 | Engagement metrics as aggregates only (4 numbers; no content, no author IDs) | `src/engagementCounters.js` | Always on when called; likewise unused on `main`. |
| 3 | Gamma scrub policy: after a production import into the test schema, phone numbers are nulled before tester access; production service keys never copied | `scripts/gamma-refresh/scrub-policy.mjs` | Gamma refresh execute path only; dry-run (default) does not apply. In practice only phones are scrubbed; the synthetic-email line is a comment, not a statement. |
| 4 | Gamma refresh fail-closed preflight: refuses production, non-staging, source or wrong-schema targets | `scripts/gamma-refresh/preflight.mjs` | Dry-run default; execute needs explicit env flags. |
| 5 | Personal data segregated into a non-exposed `private` Postgres schema (contacts, payment status, admin list, audit events) | migrations `20260810001500`, `20260809235600` | Structural, always on. Browser roles get REVOKE ALL; service role only. |
| 6 | Phone masking: default response is `phone: null` plus a last-4 mask -- including the response after a save; full number only via explicit `?reveal=1` for owner/admin | `src/playerContactHttp.js`, `src/profileContactEnhancer.js` | Default masked for everyone. |
| 7 | Admin contact split: broad readiness RPC returns `has_phone` booleans only; a separate single-player RPC returns one number; phone audit rows record only `hasPhone` | migration `20260812080000_player_phone_contact.sql` | Always on; actor must be a league admin. |
| 8 | Private-schema RLS defence in depth: RLS on ~20 private tables, all grants revoked from browser roles, deliberately no permissive policy | migrations `20260811155000`, `20260816250000` | Structural. Rationale recorded in the migration: a second wall so future grant drift cannot silently expose the tables. |
| 9 | Browser-deny data plane for chat/DM/notification tables: deny-all RLS (`using(false)`), grants revoked, all access through service-role RPCs that re-check the actor in SQL | 27 migration files enable RLS; pattern from `20260810003800` on | Structural, no toggle. |
| 10 | Lane schema isolation: every PostgREST call's profile is forced to the Worker's own schema; a foreign lane profile is forced back (fail-closed); a schema/environment mismatch throws | `src/supabaseSchema.js` | `ENVIRONMENT` + `SUPABASE_SCHEMA` per lane. |
| 11 | Service-role authorisation checklist: 6 questions every endpoint must answer (actor from auth only, never the body; membership asserted in the command layer; non-leaky 401/403/404; a required unprivileged-actor-rejected test) | `docs/security-authorization-checklist.md` | Policy + convention for all endpoints. |
| 12 | Bearer-token authentication validated server-side; identity never from client-supplied IDs | `src/supabaseAuth.js` | Always on for non-public routes. |
| 13 | Test-lane auth bypass, hard-gated: fixed synthetic lane actor, only when no token is supplied (a supplied token is always validated); production never bypasses. The lane set is stated inconsistently across files (jfl/dru vs jfl/dru/gamma) -- a caveat, section 5 | `src/supabaseAuth.js`, `src/securityHeaders.js` | `ENVIRONMENT`, `BETA_AUTH_BYPASS`, actor env secrets. |
| 14 | Environment readiness: hard-coded expected project/schema/host per lane, HTTP 503 on mismatch; the public diagnostic returns presence booleans and refs, never credential values | `src/environmentReadiness.js`, `src/hostEnvironment.js` | Always on. |
| 15 | Secrets handling: secret names declared in git, values only in the platform secret store; deploy fails rather than publishing a lane whose required secrets are missing; the two key classes checked distinct | `wrangler.jsonc`, `config/env.example`, `scripts/put-wrangler-secret.mjs` | Always on. |
| 16 | Untrusted/public-PR isolation: PR CI runs with no deploy secrets and no deploy jobs; deploys only from trusted lane branches; forks cannot claim lane namespaces | `.github/workflows/ci.yml`, release-source policy scripts | Always on; `STRICT_RELEASE_SOURCE_POLICY=1` tightens further. |
| 17 | Secret redaction in diagnostics and break-glass scripts (Bearer tokens, platform keys, JWTs, secret-shaped pairs scrubbed before output can reach logs or issues) | `scripts/cloudflare-dru-build-diagnostic.mjs` and siblings | Always on inside those scripts. |
| 18 | Chat blocking, bidirectional: blocked pairs vanish from candidate lists and cannot start or continue a conversation, in both directions | migration `20260811023000`, `src/chatCommands.js` | User-controlled, off by default. |
| 19 | Chat reporting and moderation with soft removal: closed reason set (including "privacy"), duplicate reports de-duplicated, removal sets `removed_at` and every normal read filters it out, so the message vanishes for participants while the moderation record remains | `src/chatCommands.js`, migrations `20260811030000`, `20260811040000` | Always on; moderation is league-admin only. |
| 20 | Chat access scoped to participation *time windows*: membership must cover the message's timestamp, so leaving a team closes access to messages outside the tenure | migrations `20260811010000` family | Structural. |
| 21 | Sealed lineups: the opponent's lineup is returned only once both sides have committed | migration `20260811013000`, `src/blindLineupComponent.js` | Always on for lineup rounds. |
| 22 | Admin audit log: privileged actions recorded with actor, action, entity, reason, before/after; sensitive values kept out by convention (phone changes audit only `hasPhone`) | migration `20260814170000`, `src/adminAuditPage.js` | Always on for covered RPCs; reads admin-only. |
| 23 | Non-leaky client errors: thrown errors mapped to stable generic strings (240 chars max); anything smelling of schema/SQL/service-role collapses to a fixed message | `src/requestSanitize.js` | Always on in handlers that use it. |
| 24 | Request guards on all JSON input: 64 KiB body cap, depth/key/string limits, control characters stripped | `src/requestSanitize.js` | Always on for handlers using the shared reader. |
| 25 | HTML/JSON escaping plus a build lint that fails on dynamic `innerHTML` interpolation (XSS treated as session-compromising, because tokens live in browser storage) | `src/textEscape.js`, `scripts/lint-inner-html.mjs` | Always on; lint in CI. |
| 26 | Security headers: per-request CSP nonce, `no-referrer`, sensors/payment off, `no-store` | `src/securityHeaders.js` | Always on. |
| 27 | `no-store` as a named helper for authenticated/contact responses, against a separate public-cacheable helper -- the private choice is the easy choice | `src/httpJson.js` | Chosen per route by helper. |
| 28 | Browser-storage hygiene: the session body/ETag cache refuses contact and `reveal=` URLs; sign-out purges cached bodies so the next account on a shared device sees nothing. Caveat: a sibling module deliberately mirrors the two token keys to localStorage -- section 5 | `src/livePageRefresh.js`, `src/profilePage.js` | Always on. |
| 29 | OAuth callback hygiene: tokens read from the URL into storage and immediately stripped via `history.replaceState`; post-login `next` accepted only as a same-origin path | `src/profilePage.js`, `src/chatPage.js` | Always on. |
| 30 | Rate-limit policy for admin and PII endpoints (operator-applied WAF runbook: /api/admin/* 30/min, contact 20/min, /api/* 120/min) | `docs/security-rate-limits-cloudflare.md` | Manual operator step; documented, not code. |
| 31 | Short retention for CI artifacts and backups: failing-test output 1 day, browser-smoke artifacts 7 days; database backup window noted as platform-managed | workflow YAML, `docs/ops-backup-audit-recovery.md` | Fixed in workflows. The only retention rules in the project -- see the gaps, section 5. |
| 32 | Archive-instead-of-delete for seasons: hard delete succeeds only for a draft season with zero teams, memberships or matches; anything with history is cancelled (audited reason) or archived; a trigger reverts status changes that bypass the gated RPC | migration `20260816140000`, `src/seasonLifecycleCommands.js` | Always on; league-admin only. |
| 33 | Trade consent gates: completion requires the traded player's consent and both captains' approvals; any decline kills the trade, history preserved | migration `20260810123000` | Always on for trades. The codebase's only consent-shaped workflow outside messaging. |
| 34 | External-identity provenance: a self-entered external ID is labelled self-asserted, never silently upgraded; rating observations append-only with provenance | migration `20260816260000` | Always on; linking optional. |
| 35 | Public-surface minimisation: pickers show display name plus coarse context; a disambiguator appears only for duplicate names and is then only the ID's last 4 characters; autocomplete sourced from already-public data, 2+ characters, capped | `src/playerPickerLabel.js`, `src/safeAutocomplete.js` | Always on. |

## 4. The mechanisms beyond `main`

### 4.1 The JFL lane (`fremontderby-jfl`; consent files later synced byte-identical onto `fremontderby-dru`)

- **Direct-message consent** (`src/directMessageConsentHttp.js`,
  migration `20261004220514_jfl_direct_message_consent.sql`):
  a consent table with `enabled default false` -- an absent row
  is false -- RLS deny-all for browser roles, service-role only.
  A trigger requires *both* parties' current consent, under
  sorted advisory locks, before a conversation can be created.
  The HTTP route returns 404 unless `ENVIRONMENT=jfl`.
- **Social-chat consent** (`src/socialChatConsentHttp.js`,
  migration `20261004232538_jfl_social_chat_consent.sql`): the
  same shape per channel (`general`, `team`), independently
  persisted, default off, checked in the chat send/read paths.
- **Profile consent UI** (`src/profileDirectMessageConsentEnhancer.js`,
  `src/profileSocialChatConsentEnhancer.js`), with the
  throttled-save recovery flow of cards 3577/3578.
- **Cross-session isolation**: private Messages state
  (`src/chatPage.js`, #3605), Notices (`src/jflNotificationsPage.js`,
  #3615) and the message indicator (`src/appShell.js`, #3587) are
  bound to the current session and cleared on change; a family of
  ~15 further commits applies the same binding to moderation,
  lineups, scores and admin surfaces.
- **QA-evidence privacy contract** (`docs/qa-evidence-contract-v1.md`,
  #2297): no auth data, cookies, tokens, email, phone, unrelated
  messages or page text in evidence; tester/session IDs are
  pseudonymous opaque IDs, not hashes of identifiers; error
  fingerprints strip query values, UUIDs and stack coordinates
  before hashing; free-form notes are warned about and redacted
  server-side; raw evidence retention 90 days.

### 4.2 The author's lane only (`fremontderby-dru`)

- **Synthetic phone substitution** (`src/druFakePhone.js`):
  deterministic `555…` numbers derived from the player ID,
  written into the private contacts table for captains so the
  lane can exercise phone flows with no real numbers. Hard-gated:
  a no-op unless `ENVIRONMENT=dru`.
- **Guarded test personas** (`src/testPersona.js`): impersonation
  only in allowlisted environments, only for an allowlisted
  operator, and tokenless automation is never allowed to
  impersonate.

### 4.3 Sentence-level modules (the pile branches)

On ~124 of the author's working branches (and on the gamma and
backup tips) sit two 8-line modules: `src/privacyList.js`
("Stored personal data is the player name, phone, and Fargo id.
A captain sees the name only.") and `src/privacyCampaign.js`
("Privacy: phone is stored as a label, not a value."), plus a
test locking the moderation page's sentence that a report does
not open unrelated private messages. These state the rules on
the page, locked by tests; they do not implement them. They are
the most visible form of the card-driven privacy work -- the
rules called out where a user can read them -- and the
mechanisms stand behind them in sections 3 and 4.1.

## 5. Gaps and caveats in the source

Recorded so nothing is copied blindly:

- **No erasure flow.** No player- or user-level delete, export or
  forget-me flow exists in code, migrations or docs.
- **No personal-data retention schedule.** Nothing purges chat
  messages, DMs, notifications, audit events or contact records
  by age. Retention limits exist only for CI artifacts and
  platform backups (mechanism 31).
- **No anonymisation layer.** Identifiers are not hashed or
  tokenised for analytics or testing; the gamma scrub nulls
  phones rather than substituting synthetic values (contrast
  4.2), and its email handling is a comment, not code.
- **No application-level encryption.** Personal data relies on
  platform encryption at rest and in transit.
- **A thin `SECURITY.md`** (9 lines): disclosure is a public
  GitHub issue; no private reporting channel is documented.
- **Two internal inconsistencies**: the test-lane bypass scope
  (mechanism 13) and token storage (mechanism 28) are stated
  differently in different files.

## 6. The principles the work adds up to

From the cards and the code together:

1. **Participation is not consent.** Joining grants no social
   reachability. Every social channel is off by default, opt-in
   is per-channel and independent, opt-out is effective
   immediately -- against stale clients, deep links, existing
   threads and direct writes -- and the core duties remain fully
   doable with every channel off.
2. **Fewer surfaces, deliberately.** A fourth chat surface was
   retired rather than consent-managed. Required coordination
   belongs in structured actions and narrow notices.
3. **Deny by default at the data plane; mediate through one
   trusted path.** Sensitive tables are structurally unreachable
   from the browser; access funnels through server-side functions
   that re-check the actor. Where a bypass key exists, the
   authorisation is re-implemented explicitly, against a written
   checklist, with a required rejection test.
4. **Segregate personal data physically.** Contacts, payment
   state and admin authority live in a separate schema from
   public profile data, so generous public read models cannot
   join the sensitive tables by accident.
5. **Split "does it exist?" from "what is it?"** Broad surfaces
   carry the boolean (`has_phone`); the value sits behind a
   narrow, single-subject, explicitly gated read. Audits record
   the boolean, never the value. "Stored as a label, not a value."
6. **Mask by default; reveal is a separate, explicit action** --
   at every layer at once: API shape, UI gesture, cache rules.
7. **Name fields, never values.** The rule applies to privacy
   tooling itself: the inventory, the diagnostic bundle, the
   scanner finding and the error message all describe data
   without reproducing it.
8. **Allowlist, and fail closed.** Telemetry, QA evidence, error
   capture and ML datasets may contain only enumerated safe
   fields; sensitive categories are rejected at the contract
   layer; free text is treated as sensitive by default; retention
   and deletion are defined up front; ML eligibility is a
   per-field decision. No keystroke surveillance, no raw replay,
   no message capture.
9. **Isolation is a privacy property at every layer**: between
   users (session-change clearing, including after body parsing),
   between conversations (late responses bound to their thread),
   between environments (lane schemas, forced profiles,
   environment identity checks, scrubbed one-way copies), and
   between test and public surfaces (synthetic identities kept
   off public standings; an RLS-off table treated as an exposure
   before any data lands in it).
10. **Preserve history, minimise exposure.** Evidence and history
    are retained and auditable, scoped to the reported item and
    to authorised readers; archive or deactivate instead of
    hard-deleting; engagement is measured in counts, never by
    reading private messages.
11. **Time and condition are access dimensions.** Access is
    checked against membership windows, and information is
    hidden until a condition (both sides committed) is met.
12. **Keep policy next to the mechanism, in testable form.** The
    scrub policy describes itself in code; the authorisation
    checklist is a document every endpoint must answer; and the
    strongest technique in the repository is a *boundary test*:
    a test that greps the whole codebase to prove a sensitive
    value appears only in an allowlist of files.
13. **Privacy claims require adversarial, independent proof.**
    Cards are written as testable pass criteria (role by role,
    UI and API, stale-client and direct-write bypasses), and the
    flagship consent programme is not done until the other lane
    has tried to break it.
