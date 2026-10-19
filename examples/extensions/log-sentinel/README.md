# Log Sentinel — an example Homing Pigeon extension

A sense for people who have read a sick machine's logs at
3 a.m. and know the kernel usually says what is wrong before
anything else notices. It tails the kernel and system logs
for the lines that mean the machine is hurting — an OOM kill,
a panic, a BUG, a segfault, a filesystem error — and files
them as Oracle signals, at most a few per hour no matter how
loud the log gets.

The watcher files two declared signals:

| Signal | Fires when |
|--------|------------|
| `kernel_distress` | A line matches one of the enabled built-in groups — `oom`, `panic`, `fs`, `segfault`, `bug` (all high severity) |
| `log_pattern_hit` | A line matches a pattern configured in the `patterns` tunable; the severity comes from the pattern entry — `medium` unless the entry declares `high` |

A configured pattern entry looks like:

```json
{"name": "auth_failures", "regex": "authentication failure",
 "severity": "medium"}
```

Filing is deliberately coarse. Each group (or pattern) is a
single cooldown subject: the first matching line files, and
further matches of the same subject inside `cooldown_sec`
(default 3600) are suppressed without refreshing the
timestamp. Identical hits are deduped within a pass, and at
most `max_alerts_per_pass` alerts (default 10) file per pass;
hits past the cap are dropped without being marked fired, so
they can still file on a later pass.

The reader works the way `tail -f` does, but in passes: the
state file carries a `_reader` record of each file's inode
and offset. A file seen for the first time starts at its end
minus `tail_bytes`, so a huge log's ancient history never
floods the first pass; after that each pass reads from the
recorded offset, never more than `tail_bytes` per file, and
advances only past what it read. An inode change or a shrink
(log rotation, truncation) restarts that file from the
beginning.

Run one pass:

```bash
python3 log_sentinel.py
# reads the manifest's log_paths (default /var/log/kern.log
# and /var/log/syslog); one alert payload per line on stdout;
# state in .log-sentinel-state.json next to the script
```

Or try it anywhere by feeding it fixture input instead of
live logs:

```bash
python3 log_sentinel.py --readings readings.json
python3 log_sentinel.py --log-file fixture.log
# --readings takes {"now": 1792375113.0, "lines": ["…", "…"]};
# --log-file reads a whole fixture log as the lines.
# Neither mode touches the _reader offsets.
```

Platform coverage: the default log paths and the built-in
groups are Linux — that is where kernel logs live in files
like these, and on other platforms the configured files
usually will not exist, which reads as no lines and files
nothing (never an error). The code itself is plain
standard-library file I/O, so on macOS, the BSDs, or Windows
it works as a general log tailer as soon as `log_paths` and
`patterns` point at that platform's logs; there is no Event
Log or syslog-socket source.

## Light mode

For a low-power install (a Pi, a small VPS, a box doing other
work), turn the knobs the manifest actually implements:

- `tail_bytes` down — 65536 by default, 8192 in light mode.
  The per-pass cost is bounded by the bytes tailed per pass,
  not by log size: a pass reads at most `tail_bytes` per
  configured file, however many gigabytes the log has grown
  to on disk.
- `groups` down to a subset — only `["oom", "panic"]`, say,
  for the two that always mean stop.
- `patterns` fewer — every configured pattern is a regex run
  over every tailed line, so drop the ones nobody acts on.
- `poll_interval_sec` up — 60 by default; 300 or 900 loses
  little for logs whose cooldown is an hour anyway.

The honest limit: it cannot watch less than the tail it
reads. The knobs bound that tail — `tail_bytes` per file per
pass, on the cadence `poll_interval_sec` sets — and within
the tail every line pays its regexes. There is no setting
that watches a whole fast-growing log cheaply; there is only
a smaller tail, checked less often.

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extensions.md](../../../docs/extensions.md).
