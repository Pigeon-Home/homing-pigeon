# DRI playbook ("presence of mind")

> **Status: implemented, off by default.** `runner/oracle/dri.py`
> evaluates triggers every poll cycle (`maybe_page`), with per-trigger
> cooldown and digest batching in `dri-state.json`. The only channel
> the runner accepts is Telegram (`send_telegram`, Bot API over HTTPS).
> Signal, WhatsApp, and the dashboard ack are not in the
> runner. `dri.enabled` defaults to false. Nothing pages until the
> owner turns it on and sets a bot token and chat id.

## What it is

The Oracle's senses (host IDS, network monitor — see `docs/extend/senses.md`)
bring signals in. The DRI playbook is the matching outbound
extension: when fused signals cross a threshold, the Oracle reaches
out to the owner directly, the way a good on-call engineer would
tap you on the shoulder. "Presence of mind" is the owner's name for
it: the system keeps watch so you don't have to, and speaks up when
it matters.

The page itself is advisory: a page never kills a job, revokes
a key, or touches the box -- the human decides what a page
means. Remediation is a separate, runner-side mechanism
(docs/design/remediation-design.md): on a closed list of tripwires
the runner's reflexes kill and quarantine without asking
anyone, and in oracle mode the Oracle may order a kill for a
divergence off the list. Every remediation act is recorded
on the job's result and paged after the fact; quarantine is
reversible by the owner's hand.

## Triggers (all adjustable)

A page fires when any trigger trips. Every threshold below is config,
not code, and every trigger can be disabled.

- **Fused sensor score.** The weighted scores from the `senses` query
  op (`score = weight x severity`, per `docs/extend/senses.md`), summed per
  sensor over a sliding window. Pages when the sum crosses
  `triggers.sensor_fused_score.threshold` within
  `triggers.sensor_fused_score.window_sec`. This is where the sense
  weights pay off: turning a sensor's weight down quiets its paging
  without touching ingest.
- **Confinement violation.** A job wrote outside `workspace_root`
  (the Oracle already detects this; see PROTOCOL.md). Pages on
  every occurrence: this is the one signal that means the
  attested boundary broke.
- **Judge block.** The judge refused a job in enforce mode. Page;
  include the reasons.
- **Key probing.** Repeated key-policy or signature rejections from
  the mail flow within a window — someone is knocking. Adjustable
  threshold and window.
- **Resource pressure.** A resource event crossed its threshold
  (CPU, memory, or disk as recorded by the built-in resource
  monitor). Boolean trigger (`triggers.resource_pressure`).
- **Remediation.** A remediation event was recorded: the page is
  the after-the-fact report of an act (divergence, authority, act,
  antivirus verdict, and the quarantine path when one was taken).
  Boolean trigger (`triggers.remediation`).

`evaluate_page_triggers` is implemented in `runner/oracle/dri.py`. It
consumes stored senses, retained job results, and the mail-flow
rejection counters, and returns page-worthy events. `maybe_page`
is what the poll loop calls. The sketch below is not the live
signature:

```python
evaluate_page_triggers(cfg, base_dir) -> list[PageEvent]
```

## Channels

Telegram is the only channel the runner accepts. Signal and
WhatsApp are listed in docs/project/future.md. Do not set `dri.channel` to
anything but `"telegram"`.

- **Telegram.** This is the channel the runner implements. Bot API
  over HTTPS: one token, one chat id. A page is a single POST.
  `dri.channel` must be `"telegram"`.
- **Signal.** The runner rejects it. See docs/project/future.md.
- **WhatsApp.** The runner rejects it. See docs/project/future.md.

**Out of scope, by owner decision: SMS.** No text messaging. No
Twilio-style provider, no per-message cost, no carrier metadata.

## The page

All pending events are batched into one plain-text message
(`format_page` in `runner/oracle/dri.py`). The renderer applies no
redaction step; the message carries only what the events carry —
per event a title line, a detail line, and one line per signal:

```
homing-pigeon: confinement violation in job 3fa8…
job wrote outside workspace_root

the Oracle took no action.
ack by investigating; open the dashboard for the full context.
```

The closing is always the same two lines. The first states what
the Oracle did *not* do — unless the batch contains a remediation
event that acted, in which case it reads instead: "remediation
acted as recorded above; the full record is in the audit log and
the job's result." The second line's dashboard is not built; the
page itself, plus the runner log, is the full context today.

The rendered text has no timestamp line and no separate
job-context field: a remediation event's detail line names the
job, divergence, authority, act, antivirus verdict, and
quarantine path when recorded.

## Anti-spam

- **Cooldown per trigger** (`cooldown_sec`): a tripped trigger stays
  quiet until the cooldown elapses, even if the condition persists.
- **Digest mode** (`digest_window_sec`): within the window, further
  events are batched into one follow-up message instead of paging
  individually.
- **The destination is singular by configuration.** Pages go to
  the one chat named by `dri.telegram_bot_token` and
  `dri.telegram_chat_id` — the owner and no one else. There is no
  multi-recipient mode.

## Config sketch

```json
"dri": {
  "enabled": false,
  "channel": "telegram",
  "telegram_bot_token": "",
  "telegram_chat_id": "",
  "triggers": {
    "sensor_fused_score": {"threshold": 6.0, "window_sec": 600},
    "confinement_violation": true,
    "judge_block": true,
    "key_probe": {"threshold": 5, "window_sec": 3600},
    "resource_pressure": true,
    "remediation": true
  },
  "cooldown_sec": 3600,
  "digest_window_sec": 300
}
```

`enabled` defaults false. Nothing pages until the owner turns it on
and sets a bot token and chat id.

## The human half

The machine config above is half the playbook. The other half is
the owner's runbook — what *you* do when paged — and it lives with
you, not in this repo. Template for when the time comes:

1. Note the page. There is no ack input — nothing you send back
   changes the runner's state; the per-trigger cooldown is purely
   time-based on the last page sent.
2. Read the runner log and the senses around the event. There is
   no dashboard and no headset to open.
3. Correlate: which job, which sensor, fused score, confinement state.
4. Decide: benign (tune the profile/weight), suspicious (rotate the
   sensor key, quarantine the job's outputs), hostile (rotate all
   keys, take the box offline).
5. Write down what you changed, so the next page is smarter.

## The dashboard

Listed in docs/project/future.md. `--oracle` is a loopback chat, not
a page history. There is no ack path at all today: no reply
keyword is read, and the page's "ack by investigating" line
means exactly that — the acknowledgement is the investigation
itself.
