# Sysmon Feed — an example Homing Pigeon extension

A sense that feeds Sysmon's ProcessCreate stream to the
Oracle. Sysmon records every process creation with its
full context — image, command line, parent, user, hashes —
and most of that stream is a machine going about its day.
This sense files the two shapes in it that are worth
waking anyone for: a process running out of a temp
directory, and a command line built to not be read.

The artifact has two shapes from one field model (Event
ID 1, ProcessCreate: `UtcTime`, `ProcessGuid`, `ProcessId`,
`Image`, `CommandLine`, `CurrentDirectory`, `User`,
`ParentProcessId`, `ParentImage`, `ParentCommandLine`,
`Hashes`):

- **Sysmon for Linux** writes one event per syslog/journal
  line, the event rendered as XML text on that line
  (`<Event><System><EventID>1</EventID>…<EventData><Data
  Name="Image">…</Data>…`).
- **Windows Sysmon** exported as text (wevtutil, or Event
  Viewer "Save as text") is multi-line blocks of
  `Field: value` lines with an `Event ID: 1` line per
  block, separated by blank lines or by a line starting
  `Log Name:` or `Event[`.

The files named by the `log_paths` tunable are tailed
incrementally: the state carries reader entries per path
(`{"inode", "offset", "partial"}`), a missing file yields
no events and keeps its entry, and an inode change or a
file that shrank restarts that file from 0. The `partial`
entry is the discipline that matters for the Windows
shape: a block that has not terminated yet — no blank
line, no next block header — is carried in the reader
state and prepended to the next chunk, so a block is
never split across a chunk boundary.

An episode is `(signal, image, parent_image,
rule-matched detail)` — the image for the temp rule, the
command line for the encoded rule — and an episode files
once; the filed set is the state.

**Honesty about the fixtures.** The fixtures under
`fixtures/` are SYNTHETIC: crafted from the documented
field layout, modeled on real Sysmon output conventions.
No captured sample exists — see the footprint note below
for why — and this README does not pretend otherwise.

## Signals

| Signal | Fires when |
|--------|------------|
| `sysmon_process_from_temp` | An Event ID 1 `Image` path is under `/tmp/`, `/dev/shm/`, or `/var/tmp/`, under a Windows per-user `C:\Users\*\AppData\Local\Temp\` folder, or contains `%TEMP%` (medium severity) |
| `sysmon_encoded_command` | An Event ID 1 `CommandLine` contains `-enc` or `-encodedcommand` (case-insensitive), or a base64-looking token of at least 100 characters from the `[A-Za-z0-9+/=]` alphabet (medium severity) |

Both signals are Event ID 1 only. Other Event IDs parse
to nothing in this version: NetworkConnect, FileCreate,
and the rest are future signals, named here as restraint
rather than dropped silently — they are not this sense's
contract yet, and no README line claims them.

## Tunables

| Tunable | Default | What it does |
|---------|---------|--------------|
| `log_paths` | `["/var/log/syslog", "/var/log/messages"]` | The Sysmon event text files to tail — the Linux syslog/journal export on Linux; on Windows, point it at the file the owner's export schedule refreshes |
| `poll_interval_sec` | 60 | How often the runner offers this sense a pass; the cost knob (see Light mode) |

Run one pass:

```bash
python3 sysmon_feed.py
# one alert payload per line on stdout; state (including
# the reader offsets and partial blocks) in
# .sysmon-feed-state.json next to the script
```

Or try it anywhere against fixtures, with no live Sysmon
at all: a readings file (`{"now": ..., "events": [...]}`,
events in the `parse_event()` shape), or a whole fixture
file parsed from offset 0, final block flushed:

```bash
python3 sysmon_feed.py --readings readings.json
python3 sysmon_feed.py --log-file fixtures/synthetic-windows-sysmon.txt
```

Footprint: Sysmon for Linux did not run in the measurement
environment (the host denied BPF) — **no footprint is
claimed** for it, and none should be quoted from this
README. The capability caveat, stated plainly: Sysmon's
install can succeed while its telemetry silently fails
where the kernel denies BPF — the service installs, the
config validates, and then telemetry fails to start. An
install check must probe that capability, not assume it.
The Windows sibling is the original Sysinternals tool
with the same event model; it is a different codebase,
not measured here either.

Alert payloads are unsigned sense alerts; signing and
delivery follow the standard senses flow. The full
extension walkthrough — manifest fields, the versioning
contract, sensor binding, and how to turn this example
into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).

## Light mode

For a Pi Light install, tune it down with the tunables
the code actually implements: raise `poll_interval_sec`
from 60 to 600 — the producer's own cost is one tail pass,
so cadence is the whole cost — and point `log_paths` at
the single file the box actually keeps. The honest limit
is upstream: whether Sysmon itself belongs on a small box
is the capability question above, not a knob this sense
owns; where the kernel denies BPF, no tuning makes the
telemetry exist.
