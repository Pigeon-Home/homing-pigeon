# Live examples

<!-- Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab -->

What a real runner wrote, and what three days of real jobs came to.
Everything below is either a verbatim line from the scrubbed capture
in `docs/reports/live-2026-10-25/` (its README says what was
scrubbed and how) or a number computed from it. Each excerpt names
its file, and `runner/tests/test_live_capture.py` fails if a quoted
line stops matching that file; the numbers are written by
`runner/tools/live_capture.py` and checked the same way.

## The rig, and what it was not

The campaign rig is a two-core Linux VM, kernel 7.0, Python 3.12,
runner **3.12.51**. It ran as root with confinement off, every
security mode off, the Oracle in deterministic mode (Pi Light), and,
from its third start on 2026-10-22 onward, `judge=off` and
`max_result_view=full`, so the SI saw each job's whole output. Mail
carried jobs at first; after the mail-off of 2026-10-23 the file
transport carried them. The campaign sent the same eight scripts in
rotation, one at a time: the next job went out when the last result
had been read.

That is a test bench, deliberately wide open, not a recommended
setup. A real install starts with the `password-only` profile
(`max_result_view: attested`, `judge: advisory`), which is what the
rig's first two starts show.

## What 19,227 jobs came to

<!-- live-facts:begin -->
<!-- Written by runner/tools/live_capture.py --write-doc; edit the tool, not this block. -->

**19,227 jobs**, completed 2026-10-23T05:10:48Z to 2026-10-24T23:18:35Z. Every one came back: 19,227 results, 19,227 verified, 0 timed out, every result at view `full`.

| Job | Runs | Exit codes |
|-----|------|------------|
| `clock` | 2,404 | exit 0 x 2,404 |
| `envmark` | 2,404 | exit 0 x 2,404 |
| `exit3` | 2,403 | exit 3 x 2,403 |
| `flagread` | 2,404 | exit 0 x 2,404 |
| `hostinfo` | 2,404 | exit 0 x 2,404 |
| `shadow` | 2,403 | exit 0 x 2,403 |
| `sysstat` | 2,402 | exit 0 x 2,402 |
| `workdir` | 2,403 | exit 0 x 2,403 |

- **Time on the box** (the script itself): median 0.008 s, p95 0.028 s, longest 0.400 s.
- **Round trip** (signed job handed over to verified result read), file transport: median 4.0 s, p95 4.2 s, p99 4.7 s, longest 16.0 s. The 249 results that went back by mail, before the mail-off: median 12.1 s, longest 17.4 s.
- **Resource pressure**: 171 events (40 cpu, 131 mem), peaks cpu 99.6%, mem 98.7%.
- **Refused at the door**: 2 bad_signature, 1 cleartext_not_supported.
- **Oracle predictions** (deterministic mode): 2,247, all `likely_success` x 2,247. Of 2,248 reconciled, 1,967 were right (87.5%); that is the share of jobs that succeed (87.5%), and every miss was a failing job (exit 3 x 281). The ledger keeps its newest lines, so it covers the last 2,248 jobs, not all 19,227.
- **runner.log**: 33,525 lines kept (11,735 INFO, 1,936 DEBUG, 502 WARN).

<!-- live-facts:end -->

What the numbers say:

- **Nothing was lost.** Every job produced a result the SI could
  verify. Three messages were refused before anything ran (two bad
  signatures, one cleartext body); refusals write a security event
  and never a result.
- **The round trip is the waiting, not the work.** A script took a
  few milliseconds; the rest of the four seconds is the transport
  picking the job up and the SI picking the result up. By mail the
  same jobs took about three times as long.
- **The box ran hot and kept going.** The monitor fires at most once
  per 15 minutes, and it fired 171 times in the 45 hours from the
  first event to the last: the VM was over its threshold almost the
  whole time. Each event is a security event the DRI playbook can
  page on; no job failed or timed out because of it.
- **Deterministic predictions are a base rate.** With no model, the
  Oracle predicted `likely_success` for every job, so its accuracy
  is exactly the share of jobs that succeed, and it missed every
  failure. Use the prediction as a record, not as a signal, until an
  `llm` Oracle is running ([configuring-oracle.md](../oracle/configuring-oracle.md)).
- **`full` means full.** At `max_result_view: full` the result is
  what the script printed. The `flagread` job prints a planted fake
  credential file; `runner.log` redacts it, and the result does not
  (excerpt below). That is the reason the default ceiling is
  `attested`.

## Startup

The configuration the campaign ran under, from the rig's third start
(the first two show `judge=advisory ceiling=attested`):

<!-- source: runner.log -->
```
2026-10-22 20:21:39 [INFO] homing-pigeon 3.12.51 starting (base=/home/runner/workspace/runner-vm, platform=linux)
2026-10-22 20:21:39 [INFO] auth=oauth mailbox=runner@example.test poll=20s workers=1 timeout=300s
2026-10-22 20:21:39 [INFO] judge=off ceiling=full workspace=(none)
2026-10-22 20:21:39 [WARN] confinement is off; workspace_root is not set
2026-10-22 20:21:39 [INFO] oracle: deterministic mode (Pi Light) -- no local model; briefs and answers are assembled from the box's records
2026-10-22 20:21:39 [INFO] runner identity: runner@example.test -- accepting signed jobs from any sender
```

## A job, three ways

The last `flagread` of the run, as the log has it. The log
truncates stdout and redacts what it recognizes:

<!-- source: runner.log -->
```
2026-10-24 23:18:35 [INFO] job 4c352bce-e286-4cb1-be12-3faa4773166b process finished exit=0 stdout='PRETEND CREDENTIAL FLAG FILE - test fixture, not a real secret aws_access_key_id...'
```

<!-- source: runner.log -->
```
aws_access_key_id = [REDACTED:aws_key]
```

The same job as the SI received it, at view `full` (one line of
`campaign-results.jsonl.gz`):

<!-- source: campaign-results.jsonl.gz -->
```json
{"name":"loop-19229-flagread","started_at":1792883913.8808005,"job_id":"4c352bce-e286-4cb1-be12-3faa4773166b","job_email_sent":false,"mail_skipped":"probe-throttle","outcome":"result","verify_rc":0,"result":{"exit_code":0,"timed_out":false,"duration_sec":0.015,"stdout":"PRETEND CREDENTIAL FLAG FILE - test fixture, not a real secret\naws_access_key_id = AKIAIOSFODNN7EXAMPLE\npassword = flag-hunter2-pretend\napi_token = <MASKED_SECRET_001>\nFLAG{pretend-credential-flag-7f3a}\n","stderr":"","view":"full","completed_at":"2026-10-24T23:18:35Z","runner":"rig"},"result_email_sent":false,"elapsed_sec":3.7}
```

And on the wire, where nobody without the shared secret reads either
(ciphertext cut here with `…`; the file has it whole):

<!-- source: envelopes/result-campaign.txt -->
```
[HOMING-PIGEON] result 0008e0f2-1584-46df-896c-2111e3c7f90f
{"hp_enc":{"alg":"aes-256-gcm/hkdf-sha384","nonce":"A0izLV54psPXj9Fl","ct":"iwZN0I+6Y05Pou2iCry31owxr9z3WEhVeb…
```

A failing job finishes the same way; `exit3` exits 3 on purpose:

<!-- source: runner.log -->
```
2026-10-24 23:18:11 [INFO] job 668cb0ea-1944-470f-8dd9-c9c136280863 done (exit=3)
```

## What the Oracle recorded

A prediction and the reconciliation that graded one, from
`oracle-learning.jsonl`. This one is the `exit3` job above:

<!-- source: oracle-learning.jsonl -->
```json
{"type": "prediction", "at": "2026-10-24T23:18:39Z", "job_id": "e58455f8-cf14-43ac-81e2-d33a10733a51", "received_digest": "dcaefd28b7e915b214a2bac977f0f5125bc3f5712df3aa4efeeba4795c9e41c0508b71fc44e0145c305334ce2641ab60", "host": "c93749a2f819640ed7c2f43546ef810e", "mode": "repair", "verdict": "likely_success", "findings": [], "features": [], "repair": null}
{"type": "reconciliation", "at": "2026-10-24T23:18:11Z", "job_id": "668cb0ea-1944-470f-8dd9-c9c136280863", "host": "c93749a2f819640ed7c2f43546ef810e", "classification": "incorrect", "predicted_verdict": "likely_success", "outcome": {"exit_code": 3, "timed_out": false, "rejected": false, "repair_applied": false, "repair_succeeded": null}, "lesson_selected": null}
```

## Security events

Resource pressure, as the log says it and as the event records it:

<!-- source: runner.log -->
```
2026-10-22 19:14:42 [WARN] resource pressure over threshold (95%): mem=96%
```

<!-- source: security-events.jsonl -->
```json
{"type": "resource_pressure", "at": "2026-10-23T19:16:36Z", "threshold": 0.95, "resources": {"cpu": 0.9604}}
{"type": "resource_pressure", "at": "2026-10-24T23:11:14Z", "threshold": 0.95, "resources": {"mem": 0.9504}}
```

The three messages refused at the door, all of the run's
authentication rejections:

<!-- source: security-events.jsonl -->
```json
{"type": "auth_rejection", "at": "2026-10-23T04:43:15Z", "reason": "bad_signature"}
{"type": "auth_rejection", "at": "2026-10-23T05:02:28Z", "reason": "bad_signature"}
{"type": "auth_rejection", "at": "2026-10-23T05:07:08Z", "reason": "cleartext_not_supported"}
```

## A transport failing over

Mail broke before the mail-off; the runner kept polling and said why
on each pass:

<!-- source: runner.log -->
```
2026-10-22 19:09:02 [WARN] transport email: email transport: pass failed: SSLError(1, '[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1000)')
```

## Posture

`runner.py --posture` from the current tree (3.12.70) against a
staging copy of the rig's config and state, on 2026-10-25. Every
warning here is the rig's open setup, named:

<!-- source: posture.txt -->
```
[OK  ] privileges     running as root (uid 0)
[WARN] workspace      workspace_root unset (confinement attestations off)
[WARN] security modes audience is off (recommended: audit or enforce)
[WARN] confinement    bwrap not installed (confinement in enforce mode would run unsandboxed)
[OK  ] secrets        shared_secret: strong
[OK  ] audit log      no audit entries yet (nothing to protect)
```

The matching `--audit-report` is empty: with every mode off, the rig
never wrote `security-audit.jsonl`.

## Using the capture

- `python3 runner/tools/live_capture.py` prints every number above
  as JSON; `--markdown` prints the block.
- The campaign records are one JSON object per line in
  `campaign-results.jsonl.gz` (`zcat` or `gzip.open` reads them).
- The suite replays parts of the capture through the runner's own
  readers (`runner/tests/test_live_capture.py`): the learning ledger
  folds, the security events pass the remediation window reader,
  every result has the protocol's result fields, every log line has
  the log's shape. A change that would not read a real box's files
  fails there.
