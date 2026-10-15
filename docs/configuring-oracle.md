# Configuring the Oracle

The Oracle is controlled entirely by `config.json`. The future dashboard is a frontend over the same keys; nothing the dashboard can set is dashboard-only, and nothing in the config file is hidden from the dashboard.

## Parity rule

Everything the dashboard configures must be expressible in `config.json`, and everything in `config.json` must be configurable from the dashboard. No GUI-only settings, ever. The config file remains the source of truth.

## Config keys

- `max_result_view` — the narrowest view the runner will ever return (`full`, `redacted`, `summary`, or `attested`). A job can request a narrower view; it can never request a wider one.
- `max_query_budget` — the most queries that may be answered for any single job. The job's own `query_budget` can only lower this number.
- `max_queries_per_hour` — rate limit on query follow-ups. Zero means no limit.
- `output_retention_days` — how long retained outputs are kept for later queries. Default 7.
- `judge` — `off` (default), `advisory` (attach reasons, still run), or `enforce` (block denylisted jobs before execution).
- `workspace_root` — directory the confinement snapshot treats as the job's allowed workspace. Empty means confinement is unconfigured.
- `protected_paths` — list of absolute paths the confinement snapshot watches closely. Any create/modify/delete under these paths is reported in the attestation detail even if the overall `confined_to_workspace` verdict is unchanged. Default empty (least restrictive).
- `redact_patterns_extra` — additional named regexes treated as secrets in the `redacted` view and in sanitization. Built-in families (`aws_key`, `private_key`, `bearer_token`) are always present.
- `worker_allowlist` — worker IDs allowed to pull tasks. Empty means any signed worker.
- `worker_compartments` — map of worker ID to compartment tags. A task with compartments is visible only to workers that share at least one tag (or when no compartments are configured).
- `dag_mode` — `off` (default) or `enforce`. When enforce, a task is offered only after all of its `requires` are done.
- `task_timeout` — seconds before a claimed task is returned to open. Default 86400.
- `require_review` — when true, completed tasks go to `pending_review` instead of `done` until approved.
- `inference` — endpoint and model for the `ask` op (v3.1). The endpoint must be loopback or the op stays off. A non-loopback host is refused and `ask` stays disabled. The installer sets this up by default (Ollama + a model); pass `--no-inference` to skip.

## Deployment profiles

A profile is an ordinary config bundle that captures what matters on a particular box.

Worked example: a Raspberry Pi running a VS Code server. The owner wants the Oracle to treat VS Code repo credentials and the root password hash as secrets, to watch `~/docs/manuals` closely, and to return only attestations.

```json
{
  "profile": "raspberry-pi-home",
  "description": "Pi running VS Code server; watch repo creds and root hash",
  "redact_patterns_extra": {
    "vscode_token": "ghp_[A-Za-z0-9]{36}",
    "shadow_hash": "\\$[0-9a-z]+\\$[A-Za-z0-9./]{20,}"
  },
  "protected_paths": ["/home/pi/docs/manuals"],
  "max_result_view": "attested",
  "judge": "advisory"
}
```

The result is a normal config file. It can be edited by hand or loaded through the dashboard; both paths produce the same keys.

## Applying a profile

The installer can apply a profile so the runner watches what you said matters:

```
homing-pigeon-install --profile password-only
homing-pigeon-install --profile raspberry-pi-home
homing-pigeon-install --profile ./my-box.json
```

Built-in profiles:

- `password-only` — treats password hashes and `password=` style assignments as secrets, watches `/etc/shadow`, sets `max_result_view` to `attested`.
- `raspberry-pi-home` — same password-hash watch, plus `/home/pi/docs/manuals` as a protected path.

A profile JSON file uses the same keys. Mailbox credentials and `shared_secret` are never overwritten. The runner already honors `redact_patterns_extra`, `protected_paths`, and `max_result_view` from `config.json`, so the profile takes effect on the next start.
