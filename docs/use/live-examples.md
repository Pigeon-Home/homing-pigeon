# Live examples

Real lines from a running system, captured 2026-10-22 to
2026-10-24 on the campaign rig (runner 3.12.51, Oracle
deterministic, confinement off, file transport after the
mail-off of 2026-10-23). The full capture is in
`docs/reports/live-2026-10-25/`. Emails are `runner@example.test`,
paths are `/home/runner`, and no credentials appear.

## Startup

What `runner.log` looks like when the runner comes up:

```
2026-10-22 19:09:02 [INFO] homing-pigeon 3.12.51 starting (base=/home/runner/workspace/runner-vm, platform=linux)
2026-10-22 19:09:02 [INFO] auth=oauth mailbox=runner@example.test poll=20s workers=1 timeout=300s
2026-10-22 19:09:02 [INFO] judge=advisory ceiling=attested workspace=(none)
2026-10-22 19:09:02 [INFO] expects: signed [HOMING-PIGEON] job messages. Signature is the only gate. Results return to this mailbox.
2026-10-22 19:09:02 [WARN] confinement is off; workspace_root is not set
2026-10-22 19:09:02 [INFO] oracle: deterministic mode (Pi Light) -- no local model; briefs and answers are assembled from the box's records
2026-10-22 19:09:02 [INFO] runner identity: runner@example.test -- accepting signed jobs from any sender
```

## A job finishing

```
2026-10-22 21:13:09 [INFO] job 0b434e29-97a0-4937-a76f-e17df2601004 process finished exit=0 stdout='Fri Oct 23 04:13:09 UTC 2026 1792728789'
```

## A transport warning

```
2026-10-22 19:09:02 [WARN] transport email: email transport: pass failed: SSLError(1, '[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1000)')
```

## An encrypted envelope

Jobs and results on the wire are `hp_enc` bodies. From
`docs/reports/live-2026-10-25/envelopes/job-campaign.txt`:

```
[HOMING-PIGEON] job 0008e0f2-1584-46df-896c-2111e3c7f90f

{"hp_enc":{"alg":"aes-256-gcm/hkdf-sha384","nonce":"...","ct":"..."}}
```

The ciphertext reveals nothing without the shared secret. The
rig's secret was rotated after this capture.

## Security posture

`python3 runner/runner.py --posture` against the rig's config
(modes off, bwrap missing, strong secret):

```
Security posture
============================================================
[OK  ] config         config file readable
[OK  ] privileges     running as root (uid 0)
[WARN] workspace      workspace_root unset (confinement attestations off)
[WARN] security modes audience is off (recommended: audit or enforce)
[WARN] confinement    bwrap not installed (confinement in enforce mode would run unsandboxed)
[OK  ] secrets        shared_secret: strong
[OK  ] audit log      no audit entries yet (nothing to protect)
```

The matching `--audit-report` is empty: this rig never wrote a
`security-audit.jsonl`.

## Oracle learning

Two shapes from `oracle-learning.jsonl`:

```json
{"type": "prediction", "at": "2026-10-24T20:48:02Z", "job_id": "6e1f5708-c330-4366-aada-709cd22fdfc1", "mode": "repair", "verdict": "likely_success", "findings": [], "features": [], "repair": null}
{"type": "reconciliation", "at": "2026-10-24T20:47:59Z", "job_id": "08a3f255-13af-48e7-84f8-bdc2ea9e62fa", "classification": "incorrect", "predicted_verdict": "likely_success", "outcome": {"exit_code": 3, "timed_out": false, "rejected": false}}
```

## Resource pressure

From `security-events.jsonl`:

```json
{"type": "resource_pressure", "at": "2026-10-23T02:14:42Z", "threshold": 0.95, "resources": {"mem": 0.9553}}
{"type": "auth_rejection", "at": "2026-10-23T04:43:15Z", "reason": "bad_signature"}
```
