# Failed Login Watch — an example Homing Pigeon extension

A sense for the shape a brute-force run leaves behind. It
watches the authentication logs for that shape — a burst of failures from one
source — and, the finding that matters, for a successful
login that follows one. A burst alone might be a forgotten
password or a scanner passing in the night; a burst and then
a success from the same source is an episode, and it closes
when it files.

The log files are tailed incrementally, not re-read: the
state carries reader offsets per path (`{"inode", "offset"}`),
a missing file yields no events and keeps its offset, and an
inode change or a file that shrank (rotation, truncation)
restarts that file from 0. Platform coverage is Linux auth
logs in the usual places — the `log_paths` tunable defaults
to `/var/log/auth.log` and `/var/log/secure` — and the sense
has nothing to say on a machine without them.

The patterns it understands, stated plainly:

| Pattern in the log | Becomes |
|--------------------|---------|
| `Failed password for [invalid user] USER from IP port N ssh2` (sshd) | a failure from IP for USER |
| `Accepted password` or `Accepted publickey` `for USER from IP` (sshd) | a success from IP for USER |
| `pam_unix(sshd:auth): authentication failure` | a failure from source `local`, user from the `user=` field if present, else empty |

Anything else parses to nothing and is ignored. auth.log
timestamps carry no year (`Mon D HH:MM:SS`); the parser takes
the year from the current time when it reads the line.

The watcher files two declared signals:

| Signal | Fires when |
|--------|------------|
| `login_failure_burst` | One source accumulates at least the `burst_count` tunable (default 5) failures inside the trailing `window_sec` (default 600) (medium severity) |
| `login_success_after_burst` | A success arrives from a source whose burst is active, or which has at least `burst_count` failures inside the trailing window at that moment (high severity; filing clears that source's failures and closes the episode) |

A burst files once; its flag clears when no failures from
that source remain inside the trailing window, so a later,
separate burst files again.

Run one pass:

```bash
python3 failed_login_watch.py
# one alert payload per line on stdout; state (including the
# reader offsets) in .failed-login-watch-state.json next to
# the script
```

Or try it anywhere against fixtures, with no live log at all:
a readings file (`{"now": ..., "events": [...]}`), or a whole
fixture log parsed from offset 0:

```bash
python3 failed_login_watch.py --readings readings.json
python3 failed_login_watch.py --log-file fixture-auth.log
{"detail": {"count": 5, "source": "192.0.2.10", "window_sec": 600}, "sensor": "failed_login_watch", "severity": "medium", "signal": "login_failure_burst", "title": "5 failed logins from 192.0.2.10 within 600s"}
```

Alert payloads are unsigned sense alerts; signing and delivery
follow the standard senses flow. The full extension walkthrough —
manifest fields, the versioning contract, sensor binding, and how
to turn this example into your own package — is in
[docs/extend/extensions.md](../../../docs/extend/extensions.md).

## Light mode

For a Pi Light install, tune it down with its tunables: raise `poll_interval_sec` from 60 to 600,
point `log_paths` at the single log the Pi actually keeps
(for example just `/var/log/auth.log`), and raise
`burst_count` — at 10, only bigger bursts file, and the small
background noise of a quiet box never wakes anyone.
