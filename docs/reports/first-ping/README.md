# First ping

<!-- Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854 -->

How long the README's first prompt takes to come back. Every
row is one batch from `runner/tools/first_ping.py`, kept in
[runs.jsonl](runs.jsonl); this table is rebuilt from that file
on every record and is not edited by hand.

`bench` rows are the runner's own leg on the named box: the
email code path from fetched message to sent result, with an
in-memory mailbox. `live` rows are the whole round trip timed
from the SI's mailbox over the named provider.

## The budget

An email round trip is the provider's delivery twice, the wait
for the runner's next poll, the runner's own work, and the SI's
own polling. The poll wait is the large term: 0 to
`poll_interval_sec`, 20 seconds by default, 10 on average. The
runner's work is milliseconds (the `bench` rows), so under the
default the two deliveries and the SI's read share the last 10
seconds in the worst case. A box that must hold the 30 seconds
every time sets `poll_interval_sec` lower.

## Runs

| When (UTC) | Mode | Provider | Kind | Runs | OK | p50 s | p95 s | max s | Version | Box |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 2026-10-28T01:38:22Z | bench | in-memory | ping | 50 | 50 | 0.015 | 0.024 | 0.031 | 3.14.6 | Linux x86_64 py3.13.16 |
| 2026-10-28T01:38:23Z | bench | in-memory | exec | 50 | 50 | 0.020 | 0.030 | 0.044 | 3.14.6 | Linux x86_64 py3.13.16 |

## Adding a row

```sh
python3 runner/tools/first_ping.py bench --runs 50
HP_SI_PASSWORD=... HP_SECRET=... python3 runner/tools/first_ping.py live \
    --runner-email runner@example.test --user si@example.test \
    --imap-host imap.example.test --smtp-host smtp.example.test --runs 5
```
