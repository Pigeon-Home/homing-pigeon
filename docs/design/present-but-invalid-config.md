# A setting that is present but not usable: default or refuse?

<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->

Status: decision record, written 2026-10-24 from the first VM
campaign's documented-default hunt (the report
`doc-default-divergences.md` under `docs/reports/`, in the release
that closed the campaign). The decision
line at the end is the owner's and is blank until he fills it; the
rest is the two policies the code already carries, what each costs,
and a recommendation. Nothing here changes what the runner does
until the decision is made and the rule below is applied.

## The question

Every numeric and enum setting in `config.json` has a documented
default: "`poll_interval_sec` (default 20)", "`dtls_greeting`:
`none`, `family` (default), `standard`, `full`". The docs are clear
about what happens when the key is absent. They are silent about a
key that is present and not usable: `null`, `true`, `"2O220"`,
`-5`, `1e400`, a list where a word belongs. The campaign handed
every reader those values and found two different answers already
living in the code, and in a few places a third that was nobody's
decision (the raw exception, the extension that died, the value
used as is).

## The two policies in the code today

**Policy A, read as the default.** The reader treats anything that
is not a usable value as if the key were absent: the documented
default applies, a warning names the key and the value it ignored,
and the process keeps running. `runner/confval.py` is this policy
written once (`number`, `integer`, `port`, `choice`), and after the
campaign every runner reader that documents a default goes through
it: poll intervals, timeouts, budgets, limits, retention, cooldowns,
the DTLS port and tier, the NATS port, the extension tunables. A
boolean is never a number there, a number must be finite, bounds
decide what is usable.

**Policy B, refuse to start.** The reader raises a config error
naming the key, and the runner (or the extension) does not come up
until the operator fixes the file. Four readers do this and did
before the campaign: `resources` (threshold, cooldown),
`dri` (thresholds, window, cooldown, digest), the mailbox ports
(`imap_port`, `smtp_port`) and `key_policies` (`max_timeout_sec`).
The campaign kept them that way: `confval.is_number` is the gate
and the module raises its own error.

Nothing in the docs says which keys get which. The split is the
history of who wrote each reader.

## What each costs

A reads the docs literally and keeps a daemon up: a typo in a
tunable costs the operator a warning line, never a transport. Its
failure is quiet by construction. `transport_dtls.port: "2O220"`
listens on 20220 and says so once, at startup, in a log the
operator may not be reading; an agent that edits config can write
a value that reads as the default and never learn it. The warning
is the whole safety net, and the campaign found readers that had
none.

B catches the typo while the operator is present and never runs on
a value nobody meant. Its failure is loud and total: a transport
extension that refuses to start is restarted by the supervisor into
a permanently dead loop (the null `dtls_greeting` did exactly that
before the fix), a live-reload key given a bad value takes the
running box down with it, and an Oracle or agent editing
`config.json` can brick the host it is meant to keep. B also
contradicts the docs for every key that says "default" today, and
the campaign's tests assert A for all of them; moving a key to B
means editing a test the campaign's rule says not to edit, with
the doc line changed first.

The job-supplied values are not part of this question. A query's
`max_matches`, `lines` or `max_chars` comes from an untrusted
sender, and an unusable one must read as the default with its bound
and never raise; that is settled and is what the readers do.

## Recommendation: a rule, not a side

Split by what a wrong value changes, and write the rule down so a
new key does not inherit a policy by accident.

- **Refuse (B)** when the wrong value changes who can reach the
  box, what it will execute, or what it protects: ports and bind
  addresses, key policies, the resource and DRI thresholds that
  page a human, secrets and their floors, security modes. These are
  the readers that already refuse, plus the DTLS and NATS ports,
  which today read as the default.
- **Default and say so (A)** for everything else: intervals,
  timeouts, budgets, limits, cooldowns, retention, disclosure
  tiers, extension tunables. The warning becomes visible: one line
  at startup, "config: N settings read as their default", listing
  the keys, and the same list in the platform card at the `full`
  tier so a sender can see a box running on defaults it did not
  ask for.

The rule for a new key, one sentence for `docs/configuring-oracle.md`
and PROTOCOL.md: *a setting that is present but not usable reads as
its documented default and is named in the startup warning, unless
the setting is a port, a bind address, a key policy, a paging
threshold or a secret, in which case the runner refuses to start
and names it.*

Under this rule the current code is right for every key but two:
`transport_dtls.port` and the NATS URL's port would move from A to
B, which is two readers, two doc lines and two campaign test classes
that change with the doc first.

## Decision

Decision (owner): ____________________________________________

Date: ____________

Applied in: ____________ (the commit that changes the two readers
and the two doc lines, or that records "A everywhere" and removes
the four refusals' special status from this note)
