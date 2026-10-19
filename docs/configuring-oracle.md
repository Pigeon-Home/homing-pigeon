# Configuring the Oracle

The Oracle is controlled entirely by `config.json`. The dashboard
is listed in FUTURE.md. `--oracle` opens a loopback chat. It does not edit
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
- `output_retention_days` — how long retained outputs are kept for later queries. Default 7. Zero (or negative) keeps them indefinitely: nothing is pruned and no retained output is reported expired.
- `judge` — `off` (default), `advisory` (attach reasons, still run), or `enforce` (block denylisted jobs before execution).
- `workspace_root` — directory the confinement snapshot treats as the job's allowed workspace. Empty means the snapshot is unconfigured. That snapshot does not stop a write. Linux bubblewrap is a separate switch, `security.modes.confinement`, off by default. See SECURITY.md.
- `protected_paths` — list of absolute paths the confinement snapshot watches closely. Any create/modify/delete under these paths is reported in the attestation detail even if the overall `confined_to_workspace` verdict is unchanged. Default empty (least restrictive).
- `redact_patterns_extra` — additional named regexes treated as secrets in the `redacted` view and in sanitization. Built-in families (`aws_key`, `private_key`, `bearer_token`) are always present.
- `worker_allowlist` — worker IDs allowed to pull tasks. Empty means any signed worker.
- `worker_compartments` — map of worker ID to compartment tags. A task with compartments is visible only to workers that share at least one tag (or when no compartments are configured).
- `dag_mode` — `off` (default), `advisory`, or `enforce`. When enforce, a task is offered only after all of its `requires` are done. When advisory, the task is offered anyway and the offer carries a `dag_warning` naming the incomplete `requires` (the hand-out is also logged as a warning). When off, dependencies are listed in the task description and the worker is trusted. Any other value behaves as `off`.
- `task_timeout` — seconds before a claimed task is returned to open. Default 86400.
- `require_review` — when true, completed tasks go to `pending_review` instead of `done` until approved.
- `inference` — endpoint and model for the `ask` op. The endpoint must be loopback or the op stays off. A non-loopback host is refused and `ask` stays disabled. The installer sets this up by default (Ollama + a model); pass `--no-inference` to skip. The default model is `qwen3:1.7b`. The `pi-light` profile (the Raspberry Pi install) sets up no inference at all — see `oracle_mode` below. `--faster` uses `qwen2.5:3b`, a faster model. `--inference-model` overrides either. On the runner, `--faster` uses `qwen2.5:3b` for one process and does not rewrite config.json. Sub-keys: `endpoint` (loopback URL, required), `model` (tag, required), `max_answer_chars` (default 2000 — answers are truncated past this), `timeout_sec` (default 180, per-question model timeout; a cold model on a laptop often needs more than 60, and the default model thinks before answering, so long questions can need the full budget).
- `oracle_mode` — `llm` (default) or `deterministic`. Deterministic is the Pi Light mode: no local model is installed or ever called, and the Oracle's duties still run — the watch, the wake gate, briefs, answers — with briefs and answers assembled from the box's own records (the job index, retained jobs, notable lines, the log tail) instead of a model's narration. The `ask` op stays off in this mode. Read live: editing `config.json` flips the mode without a restart, which is the upgrade path when a box gains a model worth running.
- `oracle_opinion_mode` — `off`, `diagnose`, `advise`, or `repair` (default). The Oracle's opinion on each result (PROTOCOL 3.2): the Oracle reads the job against this box — interpreter presence, script shape, tools on PATH, referenced paths — and the opinion rides the result as the `oracle_opinion` member. This key is both the default latitude for jobs that grant none and the owner's ceiling; a job may request a latitude with its own `oracle_opinion` member, never above this. `diagnose` speaks only after a failure, with the obvious cause; `advise` adds a prediction before the run; `repair` may also replace an absent interpreter with the platform default, never silently — the result states what changed and carries the received job's digest. The runner flag `--oracle-opinion <mode>` overrides this key for one process.
- `oracle_opinion_predict` — `requested` (default), `always`, or `never`. When tier-1 predictions are computed: only when the job requests advise or repair within the ceiling, for every job under advise semantics, or never. Diagnose needs no prediction and runs on any failure at diagnose latitude or higher, whatever this says.
- `oracle_opinion_model` — when true and inference is configured, the local model may add a note to an opinion the deterministic checks had nothing to say about; the note rides in the member prefixed `Model-formed note:` so the tiers are never blended. Default false. Deterministic `oracle_mode` never calls a model, so tier-1 opinions still file on a Pi Light box and the model tier stays dark.
- `oracle_opinion_repair` — `rejudge` (default) or `refuse`. How a repair is authorized: the repaired job goes back through the judge and the key policy exactly as a received job would, and if it is refused the original job's failure result is returned with the opinion explaining; or repairs are never executed and the opinion degrades to advise, describing the proposed fix.
- `oracle_learning` — the Oracle's self-learning loop (design: `docs/oracle-opinion-design.md`). Every opinion call is frozen before the job runs, scored against the verified outcome the moment the job finishes, and written to `oracle-learning.jsonl` in the base dir; the next job's opinion evaluation reads the ledger fresh, so lessons are in view with no restart. A lesson never authorizes anything by itself: repairs still require the repair latitude, a precondition re-verified on the current job, and re-judgment. Default `true`; `false` turns the loop off entirely (nothing recorded, nothing used). At `oracle_opinion_mode` `off`, nothing is recorded or used either.
- `oracle_learning_model` — the model channel of the learning loop: when `true` AND `oracle_opinion_model` is `true` AND inference is configured, the local model may distill one schema-validated candidate lesson from a failed or mispredicted job's outcome and output. Candidates are hypotheses — labeled uncorroborated wherever they surface — until verified outcomes corroborate them (next key). Default `false`. Deterministic `oracle_mode` never calls a model, so a Pi Light box learns verified facts only.
- `oracle_learning_promote_after` — how many verified corroborating outcomes a model candidate needs before it is treated as corroborated and may select among the existing mechanical repairs (it still never drives one alone: the repair's preconditions are re-verified on the current job and the repaired job is re-judged). A single verified contradiction retires a candidate as negative evidence. Default `2`.
- `log_max_bytes` — size at which `runner.log` rotates. Default 33554432 (32 MiB). An invalid value falls back to the default.
- `log_backups` — rotated `runner.log` files kept (`runner.log.1` … `runner.log.N`, oldest dropped). Default 4; a value below 1 falls back to the default rather than clamping up to 1, and valid values are clamped at 10.
- `oracle_log` — when true, every inference exchange is recorded in full in `oracle.log` in the state dir (request payload, reply, error bodies, elapsed time), and a spawned inference daemon writes its output there too. A debugging aid; off by default, and no `oracle.log` is created while off.
- `oracle_log_max_bytes` — size at which `oracle.log` rotates. Default 536870912 (512 MiB); with the default backups the file family stays under roughly 2.5 GiB.
- `oracle_log_backups` — rotated `oracle.log` files kept. Default 4; a value below 1 falls back to the default, and valid values are clamped at 10.
- `verbose` — `true` turns on the verbose decision lines in `runner.log` (poll cycles, ingest accepts and rejects with reasons, wake-gate scores against the threshold, judge verdicts, board offers), the same lines `-v` adds for one process; `false` quiets the log the way `--quiet` does. The command line (`-v` / `--quiet`) wins over the key, and editing the key live takes effect on the next poll cycle.
- `transports` — job transports serviced each poll cycle: a list drawn from `email`, `file`, `nats`. Default `["email"]` — email is the default and the project's test transport, which here does not mean most secure (see `transport_nats`). The runner flag `--transports` replaces the list for one process. An unknown name is a startup error. See TRANSPORTS.md.
- `transport_file` — the file transport's folders: `inbox_dir`, `outbox_dir`. Empty means `<base_dir>/transport-file/inbox` and `<base_dir>/transport-file/outbox`; relative paths resolve against `base_dir`. A job envelope dropped in the inbox is processed once and moved to its `done/` subfolder; results are written to the outbox as `<job_id>.result.txt`. The inbox folder's OS access control is this transport's first gate — only principals the owner grants write access can submit — and the signature is the second.
- `transport_nats` — core NATS: `url` (default `nats://127.0.0.1:4222`), `subject` (default `homing-pigeon.jobs`), `result_subject_prefix` (default `homing-pigeon.results`). Broker credentials — `user`/`password` or `token`; the config keys win over any userinfo in the URL — are REQUIRED by default: with none configured the transport refuses to start, because broker authentication is this transport's first gate and the HMAC signature its second. Configured in that default posture, it is the more secure option over email, whose only gate is the signature. `allow_unauthenticated: true` explicitly waives the first gate — the startup log warns that the signature is then the only gate — and a deployment using it does not carry the two-gate property.

## Command-line overrides

Every flag below replaces one config value for that process only. `config.json` is never rewritten, and a flag beats a later config edit: the key is pinned for the life of the process. `runner.py --help` is the full document; this is the map.

| Flag | Config key |
|------|------------|
| `--poll-interval SECONDS` | `poll_interval_sec` |
| `--timeout SECONDS` | `default_timeout_sec` |
| `--max-output-bytes BYTES` | `max_output_bytes` |
| `--max-job-age SECONDS` | `max_job_age_sec` |
| `--retention-days DAYS` | `output_retention_days` |
| `--task-timeout SECONDS` | `task_timeout` |
| `--max-query-budget COUNT` | `max_query_budget` |
| `--max-queries-per-hour COUNT` | `max_queries_per_hour` |
| `--max-result-view MODE` | `max_result_view` |
| `--judge MODE` | `judge` |
| `--dag-mode MODE` | `dag_mode` |
| `--oracle-mode MODE` | `oracle_mode` |
| `--require-review` / `--no-require-review` | `require_review` |
| `--local-signals` / `--no-local-signals` | `local_signals` |
| `--local-signal-port PORT` | `local_signal_port` |
| `--wake-cooldown SECONDS` | `local_wake_cooldown_sec` |
| `--log-max-bytes BYTES` | `log_max_bytes` |
| `--log-backups COUNT` | `log_backups` |
| `--oracle-log` / `--no-oracle-log` | `oracle_log` |
| `--oracle-log-max-bytes BYTES` | `oracle_log_max_bytes` |
| `--oracle-log-backups COUNT` | `oracle_log_backups` |
| `-v` / `--quiet` | `verbose` |

`--workers COUNT` and `--faster` are the two older one-process switches of the same kind: workers is read from the command line first, and `--faster` swaps the inference model for the process without touching the file.

## Deployment profiles

A profile is an ordinary config bundle that captures what matters on a particular box.

Worked example: a Raspberry Pi running a VS Code server. The owner wants the Oracle to treat VS Code repo credentials and the root password hash as secrets, to watch `~/docs/manuals` closely, and to return only attestations.

```json
{
  "profile": "pi-light",
  "description": "Pi running VS Code server; watch repo creds and root hash",
  "redact_patterns_extra": {
    "vscode_token": "ghp_[A-Za-z0-9]{36}",
    "shadow_hash": "\\$[0-9a-z]+\\$[A-Za-z0-9./]{20,}"
  },
  "protected_paths": ["/home/pi/docs/manuals"],
  "max_result_view": "attested",
  "judge": "advisory",
  "oracle_mode": "deterministic"
}
```

The result is a normal config file. It can be edited by hand; there is no dashboard to load it through (a dashboard is listed in FUTURE.md).

## Applying a profile

The installer applies a profile automatically. On a Raspberry Pi it selects `pi-light`; everywhere else it selects `password-only` (watch the password hash, attested view). Pass `--profile NAME` to override, or `--no-profile` to skip.

You can still name one explicitly:

```
homing-pigeon-install --profile password-only
homing-pigeon-install --profile pi-light
homing-pigeon-install --profile ./my-box.json
```

Built-in profiles:

- `password-only` — treats password hashes and `password=` style assignments as secrets, watches `/etc/shadow`, sets `max_result_view` to `attested`. Inference stays on the default model, `qwen3:1.7b`.
- `pi-light` — same password-hash watch, plus `/home/pi/docs/manuals` as a protected path. This is the Pi-specific install: the device tree or `/proc/cpuinfo` selects it automatically. It is the light package — it sets `oracle_mode` to `deterministic` and installs no model at all: no Ollama, no download. Naming `--inference-model` or `--faster` by hand overrides that and installs a model as usual. (`raspberry-pi-home` is this profile's former name and still works.)

A profile JSON file uses the same keys. Extra redact patterns and worker compartments are merged with what is already in the file. A profile entry wins when the name clashes. Beyond the merged dicts, only a fixed whitelist of keys is copied from a profile (`protected_paths`, `max_result_view`, `judge`, `workspace_root`, `max_query_budget`, `output_retention_days`, `worker_allowlist`, `dag_mode`, `require_review`, `oracle_mode`); any other profile key is ignored, not applied. Mailbox credentials and `shared_secret` are never written by a profile. The runner already honors `redact_patterns_extra`, `protected_paths`, and `max_result_view` from `config.json`, so the profile takes effect on the next start. `owner_instructions` and `inference` are re-read when the file changes, without a restart.

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
