# DRI playbook ("presence of mind") — SPEC

Status: spec only. Nothing here is implemented.

## What it is

The Oracle's senses (host IDS, network monitor — see `docs/senses.md`)
bring signals in. The DRI playbook is the matching outbound
extension: when fused signals cross a threshold, the Oracle reaches
out to the owner directly, the way a good on-call engineer would
tap you on the shoulder. "Presence of mind" is the owner's name for
it: the system keeps watch so you don't have to, and speaks up when
it matters.

This is advisory by design. The Oracle pages; it never remediates.
It does not kill jobs, revoke keys, or touch the box on the basis
of a page. The human decides.

## Triggers (all adjustable)

A page fires when any trigger trips. Every threshold below is config,
not code, and every trigger can be disabled.

- **Fused sensor score.** The weighted scores from the `senses` query
  op (`score = weight x severity`, per `docs/senses.md`), summed per
  sensor over a sliding window. Pages when the sum crosses
  `triggers.sensor_fused_score.threshold` within
  `triggers.sensor_fused_score.window_sec`. This is where the sense
  weights pay off: turning a sensor's weight down quiets its paging
  without touching ingest.
- **Confinement violation.** A job wrote outside `workspace_root`
  (the Oracle already detects this; see PROTOCOL.md). Always page:
  this is the one signal that means the attested boundary broke.
- **Judge block.** The judge refused a job in enforce mode. Page;
  include the reasons.
- **Key probing.** Repeated key-policy or signature rejections from
  the mail flow within a window — someone is knocking. Adjustable
  threshold and window.

Future evaluation entry point (not implemented):

```python
evaluate_page_triggers(cfg, base_dir) -> list[PageEvent]
```

It consumes stored senses, retained job results, and the mail-flow
rejection counters, and returns page-worthy events. The messaging
layer below only renders and delivers what this returns.

## Channels

WhatsApp, Telegram, or Signal. Exactly one is configured.

- **Telegram (recommended first).** Bot API over HTTPS: one token,
  one chat id, no phone number, no app install on the box. A page
  is a single POST. Simplest to operate.
- **Signal.** `signal-cli` against a registered number. Stronger
  privacy story, heavier setup (registration, keys on disk).
- **WhatsApp.** Cloud API through a Meta business app, or a paired
  device bridge. Most setup friction of the three.

**Out of scope, by owner decision: SMS.** No text messaging. No
Twilio-style provider, no per-message cost, no carrier metadata.

## The page

One message per event, plain text, no secrets, redacted with the
Oracle's standard patterns before sending:

```
homing-pigeon: confinement violation
job 3fa8… (kind=exec) wrote outside workspace_root at 14:02:11Z
top signals: host_ids critical "unexpected setuid" (score 4.0),
             netmon high "outbound to 203.0.113.7" (score 2.1)
the Oracle took no action. ack with "ack 3fa8" or open the dashboard.
```

Pages include: what tripped, when, the top weighted signals behind
it, the job context if any, and an explicit statement of what the
Oracle did *not* do.

## Anti-spam

- **Cooldown per trigger** (`cooldown_sec`): a tripped trigger stays
  quiet until the cooldown elapses, even if the condition persists.
- **Digest mode** (`digest_window_sec`): within the window, further
  events are batched into one follow-up message instead of paging
  individually.
- **Owner contact is singular and explicit** (`dri.owner_contact`).
  Pages go to the owner and no one else. There is no multi-recipient
  mode in this spec.

## Config sketch

```json
"dri": {
  "enabled": false,
  "channel": "telegram",
  "owner_contact": {"telegram_chat_id": "..."},
  "triggers": {
    "sensor_fused_score": {"threshold": 6.0, "window_sec": 600},
    "confinement_violation": true,
    "judge_block": true,
    "key_probe": {"threshold": 5, "window_sec": 3600}
  },
  "cooldown_sec": 3600,
  "digest_window_sec": 300
}
```

`enabled` defaults false. Nothing pages until the owner turns it on
and configures a channel and contact.

## The human half

The machine config above is half the playbook. The other half is
the owner's runbook — what *you* do when paged — and it lives with
you, not in this repo. Template for when the time comes:

1. Ack the page (so the cooldown logic knows a human saw it).
2. Open the dashboard / pull the `senses` window around the event.
3. Correlate: which job, which sensor, fused score, confinement state.
4. Decide: benign (tune the profile/weight), suspicious (rotate the
   sensor key, quarantine the job's outputs), hostile (rotate all
   keys, take the box offline).
5. Write down what you changed, so the next page is smarter.

## Relationship to v4

The dashboard (v4) is the natural home for page history and ack:
a page deep-links to the relevant sense window and job, and acking
happens there instead of by reply keyword. The spec's message
format already reserves the "open the dashboard" line for it.
