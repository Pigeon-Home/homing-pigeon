# FAQs

## How often does the Oracle refresh what's happening on the system? Does it poll, or does a signal wake it up?

Short answer: it polls -- and a local signal can also wake the
model. The base rhythm is polling: nothing interrupts the runner,
and the model is not running all the time. The deterministic code
around the model does the watching on the runner's poll cycle --
every 20 seconds by default (`poll_interval_sec`). The model
itself only runs when it is asked a question, when a configured
trigger decides a human gets paged, or when a local signal passes
the wake gate described below.

How it works, in order:

1. **Every poll cycle**, the runner takes one cheap look at the
   box (unless the operator turned it off with
   `inference.watch_system=false`; on by default): canary tripwire
   files are re-hashed and diffed against their snapshot; on
   Windows, a bounded tail of the Event Log and a diff of the
   registry persistence locations (autorun keys, services); on
   any platform, firewall posture and antivirus posture; plus a
   built-in resource monitor whose threshold crossings become
   security events.
2. **If something tripped, the watch files the alert itself** --
   it lands in the same senses store as external sensor alerts.
   It does not need the model awake to notice, and it is filed
   before the page check runs, so a trip since the last poll can
   page on that same cycle.
3. **Paging is deterministic, not the model's idea.** A trigger
   evaluation runs once per poll (the DRI playbook: e.g. a fused
   sensor score crossing a threshold, a high-severity alert).
   If a trigger fires and a channel is configured, it pages the
   operator. This is off by default and entirely rule-based.
4. **Signals arrive two ways, and one of them can wake the
   model.** A remote sensor sends its alert as a signed email
   job: it lands in the runner's mailbox and is picked up on the
   next poll, verified like any other job, and filed. A sensor
   on the *same box* -- a built-in sense or an owner's
   extension -- skips the mailbox: its signed envelope goes
   straight to the runner's local inbox (a watched folder, or a
   loopback socket) and through the same ingest core, usually
   within about a second. Either way the alert is filed; the
   local path adds the **wake gate**: a deterministic check
   (severity at least high, first occurrence of that sensor +
   signal inside the cooldown -- `local_wake_cooldown_sec`,
   default 900 -- and only one wake at a time) that may start
   the model to write a short assessment, appended to
   `oracle-briefs.jsonl`. The wake never takes an action; it
   writes a brief. With no inference configured the brief is
   the deterministic fallback, and in deterministic (Pi Light)
   mode no model is ever loaded: the gate files its brief from
   the record alone.
5. **When the owner asks the Oracle a question** (the loopback
   chat or a signed query by email), the context handed to the
   model is assembled at that moment: recent retained jobs, the
   runner's log tail, and a fresh run of the same watches --
   canary state, Event Log tail, registry diff -- so the answer
   describes the box as of the ask, not as of some older
   snapshot. The watch sections tell the model what changed
   and, just as importantly, say "unreadable" when something
   cannot be read, rather than reporting it clean.

One sentence version, for when someone asks quickly:

> "It polls every 20 seconds, and a serious local signal can
> also wake it -- the watching is ordinary deterministic code,
> the model only runs when you ask it something, a rule pages
> you, or the wake gate lets a signal through, and that's
> deliberate: a watcher that only runs when an LLM feels like
> it isn't a watcher."
