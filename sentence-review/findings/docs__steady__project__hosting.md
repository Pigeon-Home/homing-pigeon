# Findings — docs/steady/project/hosting.md

Source: docs/steady/project/hosting.md, reviewed at main c25c86d6.
Sentence units: 59. Flagged: 6. Categories: pre-release 52, post-release 7.

A status page for the hosting provisioner: what it is, the phase table, what is live and what is not, then the components 1 by 1 (the blob, the profile, the bootstrap, the provisioner, the queue, ephemeral targets, billing), the custody rules, and a closing not-yet list. The component run chains by bolded lead-ins and each part hands to the next. The closing list (units 51 to 59) is future work and is the document's post-release run, except its 2 standing-policy lines (units 57 and 59). Flagged: the stamp comment (unit 1), 2 thesis fragments doing a heading's job (units 2 and 46), the phase table's header row (unit 8), and 2 bare file pointers standing as their own units (units 18 and 32), on the same ground as the pointer flagged in the FUTURE findings.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f -->" | pre-release | flagged | An HTML stamp comment, not a sentence; it stands ahead of the document's first line |
| 2 | "A provisioner, not a dispatcher." | pre-release | flagged | Fragment with no verb; it states the thesis the next sentence then expands |
| 3 | "The hosting code puts a configured runner into…" | pre-release | flows |  |
| 4 | "For Windows and macOS nothing runs until a…" | pre-release | flows |  |
| 5 | "This page is the part the code points…" | pre-release | flows |  |
| 6 | "Pricing, providers and the business plan live outside…" | pre-release | flows |  |
| 7 | "The seat that owns this code (stamp `70000a51`)…" | pre-release | flows |  |
| 8 | "Phase \| What \| Where \| Proof" | pre-release | flagged | Table header row, structure rather than a sentence |
| 9 | "0 \| the `hosted` install profile; the one-blob…" | pre-release | flows |  |
| 10 | "1 \| the provider interface and adapters (Fly…" | pre-release | flows |  |
| 11 | "2 \| the hosted queue: Worker plus one…" | pre-release | flows |  |
| 12 | "3 \| ephemeral targets on GitHub Actions: `homing-pigeon-host…" | pre-release | flows |  |
| 13 | "4 \| metering and prepaid billing: the price…" | pre-release | flows |  |
| 14 | "Nothing in the runner core, the protocol or…" | pre-release | flows |  |
| 15 | "**The hosted queue** since 2026-10-27: a one-tenant Worker…" | pre-release | flows |  |
| 16 | "Its first ping is `docs/reports/queues-2026-10-27.md`; since then it…" | pre-release | flows |  |
| 17 | "**The `hosted` profile** on that rig, a one-core…" | pre-release | flows |  |
| 18 | "`docs/reports/germany-rig-2026-10-28.md`." | pre-release | flagged | A bare file pointer standing as its own list item; no sentence and no hand-off |
| 19 | "**Not yet live:** `homing-pigeon-host` itself." | pre-release | flows |  |
| 20 | "The Germany runner was installed by hand, so…" | pre-release | flows |  |
| 21 | "**The blob.** One JSON object carries everything a…" | pre-release | flows |  |
| 22 | "`homing-pigeon-install --config-json JSON\|@file\|env:NAME` writes it before the profile;…" | pre-release | flows |  |
| 23 | "The profile owns those." | pre-release | flows |  |
| 24 | "**The `hosted` profile.** `password-only` (attested results, advisory judge,…" | pre-release | flows |  |
| 25 | "`apply_profile` merges `security.modes` one mode at a time,…" | pre-release | flows |  |
| 26 | "**The bootstrap.** `runner/hosting/bootstrap.py` renders the same install three…" | pre-release | flows |  |
| 27 | "No provider token is ever embedded." | pre-release | flows |  |
| 28 | "**The provisioner.** `homing-pigeon-host up --provider fly --token-env FLY_API_TOKEN…" | pre-release | flows |  |
| 29 | "The token is read from the named environment…" | pre-release | flows |  |
| 30 | "`redeploy` creates the replacement first and destroys the…" | pre-release | flows |  |
| 31 | "The inventory (`~/.homing-pigeon/hosting.json`, mode 0600) refuses a second…" | pre-release | flows |  |
| 32 | "**The hosted queue.** `docs/extend/transports.md`, "Queues"." | pre-release | flagged | A label plus a bare file pointer; the queue's substance arrives in the next unit instead |
| 33 | "The Worker is where the per-tenant quota lives,…" | pre-release | flows |  |
| 34 | "**Ephemeral targets.** `homing-pigeon-host dispatch --target macos-ephemeral ...` fires…" | pre-release | flows |  |
| 35 | "The run boots a fresh GitHub-hosted VM, installs…" | pre-release | flows |  |
| 36 | "**Billing.** Cents, prepaid only." | pre-release | flows |  |
| 37 | "`PRICES` carries the per-target unit rates (the values…" | pre-release | flows |  |
| 38 | "`handle_stripe_event` verifies `Stripe-Signature` (HMAC-SHA-256, 300 s tolerance), applies…" | pre-release | flows |  |
| 39 | "Nothing here charges a card after the fact." | pre-release | flows |  |
| 40 | "**Token custody.** The provisioner runs where the token…" | pre-release | flows |  |
| 41 | "The service holds inventory state and never a…" | pre-release | flows |  |
| 42 | "**Isolation unit.** One VM or microVM per tenant,…" | pre-release | flows |  |
| 43 | "Tenants never share a kernel; a shared Docker…" | pre-release | flows |  |
| 44 | "**Hosted defaults.** The `hosted` profile above." | pre-release | flows |  |
| 45 | "A tenant may loosen it in their own…" | pre-release | flows |  |
| 46 | "As a feature, not a service." | pre-release | flagged | Fragment with no verb; it states the closing section's thesis the following sentences expand |
| 47 | "`docs/use/own-cloud.md` is the user's page: one command puts…" | pre-release | flows |  |
| 48 | "The hosted queue runs on an operator's own…" | pre-release | flows |  |
| 49 | "The ephemeral workflow is a template for a…" | pre-release | flows |  |
| 50 | "Billing stays dormant until someone asks to pay." | pre-release | flows |  |
| 51 | "A live `up`." | post-release | flows |  |
| 52 | "Every provider adapter is tested against recorded exchanges…" | post-release | flows |  |
| 53 | "Hetzner is the natural first, since the operator's…" | post-release | flows |  |
| 54 | "Accounts and a usage page." | post-release | flows |  |
| 55 | "The inventory and the ledger are JSON files…" | post-release | flows |  |
| 56 | "Heartbeat over the transport." | post-release | flows |  |
| 57 | "`host status` reads the inventory; the runner's posture…" | pre-release | flows |  |
| 58 | "Per-minute Mac and Windows runners sold as a…" | post-release | flows |  |
| 59 | "GitHub-hosted runners are a user's own call on…" | pre-release | flows |  |
