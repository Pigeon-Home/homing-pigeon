# Wazuh Feed — an example Homing Pigeon extension

This feed is only as real as the file feed the owner
arranges. Wazuh evaluates its rules on the **manager** — a
separate server stack — and the alerts live on the manager,
in its `alerts.json`. The Wazuh agent on a box is a
forwarder: standalone, it produces no consumable detection
stream on the box at all. So this adapter does not pretend
to read the agent. It consumes an `alerts.json` file *where
the owner places one*: a manager export copied over, an API
pull that lands on the box, a mounted share — or the
manager's own file, when this box is co-located with a
manager, which is why the `log_paths` tunable defaults to
the manager's own path, `/var/ossec/logs/alerts/alerts.json`.

**If this file never appears, you have an agent without a
manager; see docs/extend/senses.md.** That absence is the normal
standalone-agent case, and the feed treats it exactly that
way: a missing file is a quiet no-op on every pass, forever
— never an error, never a state complaint, nothing filed.
The feed files its first alert on the first pass a real
`alerts.json` is actually there to tail.

The file is tailed incrementally, not re-read: the state
carries reader offsets per path (`{"inode", "offset"}`), and
an inode change or a file that shrank (rotation, truncation)
restarts that file from 0.

Each line is one alert in the manager's documented shape:

```json
{"timestamp": "2026-10-18T12:00:00.000+0000",
 "rule": {"id": "5710", "level": 5, "description": "...",
          "groups": ["sshd", "authentication_failed"]},
 "agent": {"id": "001", "name": "web-1"},
 "decoder": {"name": "sshd"}, "data": {},
 "full_log": "...", "location": "..."}
```

(The example lines in this project's tests are synthetic,
built from this documented shape — no manager existed in the
measurement sandbox, so no real `alerts.json` was captured.)

## Signals

| Signal | Fires when |
|--------|------------|
| `wazuh_alert_high` | An alert's `rule.level` is at least 10 (high severity) |
| `wazuh_alert` | An alert's `rule.level` is from 5 to 9 (medium severity) |

Levels below 5 are parsed and never filed, on purpose: at
manager volume they are the background hum, and a sense that
filed them would train the operator to ignore it.

An episode is one (`rule.id`, `agent.name`) pair. The first
alert of an episode files — with the rule id, description,
and groups, and the agent name, in its detail — repeats are
suppressed while the episode is active, and the episode
re-arms once `episode_quiet_sec` has passed with no further
alert for that pair, so a rule that fires again next week
files again.

## Tunables

| Tunable | Default | What it does |
|---------|---------|--------------|
| `log_paths` | `["/var/ossec/logs/alerts/alerts.json"]` | The alerts.json file(s) to tail — point it wherever the owner's manager export, API pull, or share actually lands |
| `poll_interval_sec` | 60 | The cost knob: how often a pass runs |
| `episode_quiet_sec` | 3600 | How long a (rule, agent) pair must stay quiet before its next alert files as a new episode |

Run one pass:

```bash
python3 wazuh_feed.py
# one alert payload per line on stdout; state (including the
# reader offsets) in .wazuh-feed-state.json next to the
# script. With no alerts.json in place: no output, no
# error, exit 0 -- see the top of this README.
```

Or try it anywhere against fixtures, with no live file at
all — a readings file is `{"now": ..., "events": [...]}`,
with events in the shape `parse_event` produces:

```bash
python3 wazuh_feed.py --readings readings.json
{"detail": {"agent": "web-1", "agent_id": "001", "description": "sshd: authentication failed", "groups": ["sshd"], "level": 10, "rule_id": "5715"}, "sensor": "wazuh_feed", "severity": "high", "signal": "wazuh_alert_high", "title": "Wazuh rule 5715 (level 10) on web-1: sshd: authentication failed"}
```

Alert payloads are unsigned sense alerts; signing and
delivery follow the standard senses flow. The full extension
walkthrough — manifest fields, the versioning contract,
sensor binding, and how to turn this example into your own
package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

Footprint: the Wazuh agent itself measured ~26 MB settled
in the collector comparison, but it is not a standalone
supplier at any weight — without a manager there is nothing
to measure it supplying. This feed adds no footprint claim
beyond what it is: a file tailer.

## Light mode

A file tailer is already light, and this one tunes down the
same way the other tailers do: raise `poll_interval_sec`
from 60 to 600, and raise `episode_quiet_sec` — at 21600
(six hours), a Pi Light install hears about a repeating rule
at most four times a day per agent, which is the right
cadence for a box whose operator reads a brief, not a
ticker.
