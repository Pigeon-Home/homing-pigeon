# Connector round-trip cases

Captured from the Gmail connector on 2026-10-13. The connected account is
a personal inbox and is **not** the runner mailbox. These messages only
exercise the cloud side: sign, send through the connector, read back,
verify. No IMAP login, no job execution on a host.

All messages are from `slutsky@gmail.com` to itself. Safe to delete.

## Happy path

| Field | Value |
|-------|--------|
| Message | `1a1380ce30ccfbfb` |
| Subject | `[HOMING-PIGEON] TEST job c142d598-261a-4000-8a41-b8cb7d28bf38` |
| Kind | `ping` |
| Secret used | `test-shared-secret` (not a mailbox password) |
| Outcome | `verify_body` on the JSON line returned the job. Signature matched. |

The body as returned by `gmail_get_message` (`body_text`):

```
Homing Pigeon connector pipeline test. Safe to ignore or delete.

{"v":1,"type":"job","job_id":"c142d598-261a-4000-8a41-b8cb7d28bf38","issued_at":"2026-10-14T01:35:25Z","kind":"ping","sig":"3e175d607fe637e5ba40bf0e104dd402253cc1a76869de6ef09d921e3dd13f6b68673b1719edf84025a19562fd8c876f"}
```

Notes:

- The JSON line alone verifies. The full `body_text` (preamble included) does **not** — `verify_body` signs the whole body. The protocol requires a pure JSON body.
- The subject contains `TEST` between the prefix and `job`, so the runner's subject regex (`[HOMING-PIGEON] job <id>`) would not match. This case proves the connector and the signature, not a full runner cycle.

## Other cases from the same session

These were sent the same way. Outcomes are from running the returned body through `verify_body` / `execute_job`.

| Subject | Message | What it probed | Outcome |
|---------|---------|----------------|---------|
| `NEG-sigin` | `1a1380e84018aa6a` | `,"sig":"` inside the script string | Verified (last marker wins) and executed |
| `NEG-upper` | `1a1380e8aa70b40a` | Uppercase hex signature | Rejected: malformed signature tail |
| `NEG-path` | `1a1380e91cf58eef` | `job_id` `../evil` | Signature OK; `_safe_job_id` rejects |
| `NEG-naive` | `1a1380e97ac687a9` | `issued_at` with no timezone | Signature OK; `handle_mail` rejects |
| `NEG-strint` | `1a1380e9d9d74822` | `interpreter` as a string | Signature OK; rejected as poison |
| `NEG-tamper` | `1a1380ea1d8c28d9` | Flipped signature bytes | Rejected |
| `NEG-long` | `1a1380e3be3907b0` | Long-line wrap | Placeholder only; not a real case |

## How to replay

```
python3 cloud/send_job.py verify --secret test-shared-secret
```

Paste the JSON line from the happy-path body. Unit tests that replay the
captured bodies live in `tests/test_connector_captures.py`.
