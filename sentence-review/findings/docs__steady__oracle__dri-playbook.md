# Findings — docs/steady/oracle/dri-playbook.md

Source: docs/steady/oracle/dri-playbook.md, reviewed at main cbb52068.
Sentence units: 62. Flagged: 0. Categories: pre-release 61, post-release 1.

Units 1-3 are the blockquote status banner, recorded as extracted.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "> **Status: implemented, off by default.** `runner/oracle/dri.py` >…" | pre-release | flows |  |
| 2 | "The only channel > the runner accepts is…" | pre-release | flows |  |
| 3 | "Nothing pages until the > owner turns it…" | pre-release | flows |  |
| 4 | "The Oracle's senses (host IDS, network monitor —…" | pre-release | flows |  |
| 5 | "The DRI playbook is the matching outbound extension:…" | pre-release | flows |  |
| 6 | ""Presence of mind" is the owner's name for…" | pre-release | flows |  |
| 7 | "The page itself is advisory: a page never…" | pre-release | flows |  |
| 8 | "Remediation is a separate, runner-side mechanism (docs/design/remediation-design.md): on…" | pre-release | flows |  |
| 9 | "Every remediation act is recorded on the job's…" | pre-release | flows |  |
| 10 | "A page fires when any trigger trips." | pre-release | flows |  |
| 11 | "Every threshold below is config, not code, and…" | pre-release | flows |  |
| 12 | "**Fused sensor score.** The weighted scores from the…" | pre-release | flows |  |
| 13 | "Pages when the sum crosses `triggers.sensor_fused_score.threshold` within `triggers.sensor_fused_score.window_sec`." | pre-release | flows |  |
| 14 | "This is where the sense weights pay off:…" | pre-release | flows |  |
| 15 | "**Confinement violation.** A job wrote outside `workspace_root` (the…" | pre-release | flows |  |
| 16 | "Pages on every occurrence the runner retained, which…" | pre-release | flows |  |
| 17 | "**Judge block.** The judge refused a job in…" | pre-release | flows |  |
| 18 | "Page; include the reasons." | pre-release | flows |  |
| 19 | "**Key probing.** Repeated key-policy or signature rejections from…" | pre-release | flows |  |
| 20 | "Adjustable threshold and window." | pre-release | flows |  |
| 21 | "**Resource pressure.** A resource event crossed its threshold…" | pre-release | flows |  |
| 22 | "Boolean trigger (`triggers.resource_pressure`)." | pre-release | flows |  |
| 23 | "**Remediation.** A remediation event was recorded: the page…" | pre-release | flows |  |
| 24 | "Boolean trigger (`triggers.remediation`)." | pre-release | flows |  |
| 25 | "`evaluate_page_triggers` is implemented in `runner/oracle/dri.py`." | pre-release | flows |  |
| 26 | "It consumes stored senses, retained job results, and…" | pre-release | flows |  |
| 27 | "The sketch below is not the live signature:" | pre-release | flows |  |
| 28 | "Telegram is the only channel the runner accepts." | pre-release | flows |  |
| 29 | "Signal and WhatsApp are spec-only names the runner…" | pre-release | flows |  |
| 30 | "Do not set `dri.channel` to anything but `"telegram"`." | pre-release | flows |  |
| 31 | "**Telegram.** This is the channel the runner implements." | pre-release | flows |  |
| 32 | "Bot API over HTTPS: one token, one chat…" | pre-release | flows |  |
| 33 | "A page is a single POST. `dri.channel` must…" | pre-release | flows |  |
| 34 | "**Signal.** The runner rejects it." | pre-release | flows |  |
| 35 | "**WhatsApp.** The runner rejects it." | pre-release | flows |  |
| 36 | "**Out of scope, by owner decision: SMS.** No…" | pre-release | flows |  |
| 37 | "No Twilio-style provider, no per-message cost, no carrier…" | pre-release | flows |  |
| 38 | "All pending events are batched into one plain-text…" | pre-release | flows |  |
| 39 | "The renderer applies no redaction step; the message…" | pre-release | flows |  |
| 40 | "The closing is always the same two lines." | pre-release | flows |  |
| 41 | "The first states what the Oracle did *not*…" | pre-release | flows |  |
| 42 | "The second line names where to read: the…" | pre-release | flows |  |
| 43 | "The dashboard listed in docs/project/future.md is not built,…" | pre-release | flows |  |
| 44 | "The rendered text has no timestamp line and…" | pre-release | flows |  |
| 45 | "**Cooldown per trigger** (`cooldown_sec`): a tripped trigger stays…" | pre-release | flows |  |
| 46 | "**Digest mode** (`digest_window_sec`): within the window, further events…" | pre-release | flows |  |
| 47 | "**The destination is singular by configuration.** Pages go…" | pre-release | flows |  |
| 48 | "There is no multi-recipient mode." | pre-release | flows |  |
| 49 | "`enabled` defaults false." | pre-release | flows |  |
| 50 | "Nothing pages until the owner turns it on…" | pre-release | flows |  |
| 51 | "The machine config above is half the playbook." | pre-release | flows |  |
| 52 | "The other half is the owner's runbook —…" | pre-release | flows |  |
| 53 | "Template for when the time comes:" | pre-release | flows |  |
| 54 | "Note the page." | pre-release | flows |  |
| 55 | "There is no ack input — nothing you…" | pre-release | flows |  |
| 56 | "Read the runner log and the senses around…" | pre-release | flows |  |
| 57 | "There is no dashboard and no headset to…" | pre-release | flows |  |
| 58 | "Correlate: which job, which sensor, fused score, confinement…" | pre-release | flows |  |
| 59 | "Decide: benign (tune the profile/weight), suspicious (rotate the…" | pre-release | flows |  |
| 60 | "Write down what you changed, so the next…" | pre-release | flows |  |
| 61 | "Listed in docs/project/future.md. `--oracle` is a loopback chat,…" | post-release | flows |  |
| 62 | "There is no ack path at all today:…" | pre-release | flows |  |
