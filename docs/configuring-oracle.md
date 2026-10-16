# Configuring the Oracle

The Oracle is controlled entirely by `config.json`. The v4 dashboard
is not built. `--oracle` opens a loopback chat. It does not edit
these keys, and it does not poll the mailbox: the chat is a local UI
only. Run the runner without `--oracle` (or the installed service) to
handle email jobs. When a dashboard exists, it must be a frontend over the
same file: nothing dashboard-only, and nothing in the file hidden
from it.

## Where the state lives

An explicit `base_dir` in the config wins. Otherwise the runner keeps
its state (retained job output, work dirs, the Oracle chat log) next
to the config file itself — not in the home folder of whoever happens
to run it. That way the installed service (which often runs as
SYSTEM, or another service account) and a manually started `--oracle`
chat using the same `--config` always see the same jobs. If you point
two runs at two different config files, they are two different
instances with two different states: that is the usual reason the
Oracle chat says it has no job output while the service is clearly
handling jobs.

## Parity rule

Everything the dashboard configures must be expressible in `config.json`, and everything in `config.json` must be configurable from the dashboard. No GUI-only settings, ever. The config file remains the source of truth.

## Config keys

- `max_result_view` — the narrowest view the runner will ever return (`full`, `redacted`, `summary`, or `attested`). A job can request a narrower view; it can never request a wider one.
- `max_query_budget` — the most queries that may be answered for any single job. The job's own `query_budget` can only lower this number.
- `max_queries_per_hour` — rate limit on query follow-ups. Zero means no limit.
- `output_retention_days` — how long retained outputs are kept for later queries. Default 7.
- `judge` — `off` (default), `advisory` (attach reasons, still run), or `enforce` (block denylisted jobs before execution).
- `workspace_root` — directory the confinement snapshot treats as the job's allowed workspace. Empty means the snapshot is unconfigured. That snapshot does not stop a write. Linux bubblewrap is a separate switch, `security.modes.confinement`, off by default. See SECURITY.md.
- `protected_paths` — list of absolute paths the confinement snapshot watches closely. Any create/modify/delete under these paths is reported in the attestation detail even if the overall `confined_to_workspace` verdict is unchanged. Default empty (least restrictive).
- `redact_patterns_extra` — additional named regexes treated as secrets in the `redacted` view and in sanitization. Built-in families (`aws_key`, `private_key`, `bearer_token`) are always present.
- `worker_allowlist` — worker IDs allowed to pull tasks. Empty means any signed worker.
- `worker_compartments` — map of worker ID to compartment tags. A task with compartments is visible only to workers that share at least one tag (or when no compartments are configured).
- `dag_mode` — `off` (default) or `enforce`. When enforce, a task is offered only after all of its `requires` are done.
- `task_timeout` — seconds before a claimed task is returned to open. Default 86400.
- `require_review` — when true, completed tasks go to `pending_review` instead of `done` until approved.
- `inference` — endpoint and model for the `ask` op (v3.0). The endpoint must be loopback or the op stays off. A non-loopback host is refused and `ask` stays disabled. The installer sets this up by default (Ollama + a model); pass `--no-inference` to skip. The default model is `llama3.2:3b`. The `raspberry-pi-home` profile uses `llama3.2:1b`, the lighter Llama that fits a Pi. `--inference-model` overrides either default. Sub-keys: `endpoint` (loopback URL, required), `model` (tag, required), `max_answer_chars` (default 2000 — answers are truncated past this), `timeout_sec` (default 60 — per-question model timeout).

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

The installer applies a profile automatically. On a Raspberry Pi it selects `raspberry-pi-home`; everywhere else it selects `password-only` (watch the password hash, attested view). Pass `--profile NAME` to override, or `--no-profile` to skip.

You can still name one explicitly:

```
homing-pigeon-install --profile password-only
homing-pigeon-install --profile raspberry-pi-home
homing-pigeon-install --profile ./my-box.json
```

Built-in profiles:

- `password-only` — treats password hashes and `password=` style assignments as secrets, watches `/etc/shadow`, sets `max_result_view` to `attested`. Inference stays on `llama3.2:3b`.
- `raspberry-pi-home` — same password-hash watch, plus `/home/pi/docs/manuals` as a protected path. This is the Pi-specific install: the device tree or `/proc/cpuinfo` selects it automatically, and it pulls `llama3.2:1b` instead of the 3B model. `--inference-model` still wins if you name a tag.

A profile JSON file uses the same keys. Extra redact patterns and worker compartments are merged with what is already in the file. A profile entry wins when the name clashes. Other profile keys replace the previous value. Mailbox credentials and `shared_secret` are never written by a profile. The runner already honors `redact_patterns_extra`, `protected_paths`, and `max_result_view` from `config.json`, so the profile takes effect on the next start. `owner_instructions` and `inference` are re-read when the file changes, without a restart.

## Owner instructions

A plain human-readable string describing this box. It is not a profile. The installer stores it in `config.json` as `owner_instructions`, and the Oracle includes it in the `ask` system prompt so the local model knows what matters here.

Replace the string:

```
homing-pigeon-install --instructions "This is a Raspberry Pi. The only thing that matters is the password."
```

Append a paragraph:

```
homing-pigeon-install --instructions-add "Also watch the docs folder under home."
```

Re-running the installer with `--instructions` replaces the whole string. `--instructions-add` appends. Mailbox credentials are untouched.
