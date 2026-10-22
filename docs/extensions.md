# User extensions

An extension is a way to teach the agent a new sense — a new
source of signals for the Oracle. You package your work as a folder with one manifest file, develop it
in your own loop at your own pace, and the agent loads the
manifest and holds your package to it.

Because the package is only a folder and a manifest, extensions
travel well — and that is the larger point. A researcher who
teaches the agent to watch a telescope, a fermenter, or a
rooftop weather station can hand that folder to anyone, and a
lab, a network crew, or an observatory can assemble the folders
that fit its work into a pack: a bench pack, a network pack, a
sky pack. Packs can circulate the way editor themes and rulesets
do — small, inspectable, and held to exactly the signals they
declared in advance. The agent does not care whose sense it is;
it cares that the manifest said what the sense would do and that
the sense did that. That indifference is what makes an ecosystem
possible: anyone can publish a sense, anyone can run one, and
the Oracle's trust never has to stretch past the envelope.

This document covers one of the two extension kinds that exist
today: `sense`. (The other, `transport`, carries the job pipes
and is covered in [docs/TRANSPORTS.md](TRANSPORTS.md).) A sense
files signed alerts with the Oracle, which fuses them with job activity. The
plumbing underneath — alert shape, ingest gates, storage, the
`senses` query — is the senses system, specified in
[docs/senses.md](senses.md). This document covers the packaging layer: packaging,
versioning, and the declared signal contract.

## The shape of the thing

The agent never imports or executes sense code. The whole
surface the agent consumes is:

1. your manifest (`extension.json`), read at startup and on the
   alert path,
2. the signed `sensor_alert` envelope your daemon sends
   ([docs/senses.md](senses.md), "Alert format"),
3. the `senses` query answer, where your declared signals are
   surfaced back as context,
4. your optional `sources.json`, read when your extension first
   runs: where your code and the projects it wraps live, so the
   Oracle can read them (see "Sources" below). It is data too.

Your daemon — the watcher, collector, or bridge that produces
alerts — is an ordinary process you run yourself, under your own
supervision, signing with its own restricted key. There is no
plugin API to chase because there is no in-process plugin.

## Where extensions live

Each extension is one subfolder of the extensions directory:

- default: an `extensions/` folder inside the agent's base dir,
- override: the `extensions_dir` key in `config.json` (a relative
  path resolves against the base dir).

```
<base_dir>/extensions/
    lab-results/
        extension.json
        lab_results.py        <- your daemon; the agent never runs it
        README.md
    your-package/
        extension.json
        ...
```

The folder name is yours. The identity of the extension is the
`name` in its manifest, which is also the sensor name it files
as. Two folders may not declare the same name: the first one in
sorted order loads, the second is refused and the refusal is
logged.

## The manifest

`extension.json`, one per extension folder:

```json
{
  "name": "lab_results",
  "version": "0.3.0",
  "api_version": 1,
  "kind": "sense",
  "description": "Watches a folder of experiment result files and files lab events as Oracle signals.",
  "signals": [
    {"name": "experiment_finished",
     "description": "A run in the watched folder reached a finished state."},
    {"name": "metric_threshold_crossed",
     "description": "A finished run's headline metric crossed the threshold declared in this extension's tunables."},
    {"name": "result_anomaly",
     "description": "A finished run's headline metric sits far outside this folder's earlier results."}
  ],
  "tunables": {"watch_dir": "results", "metric": "accuracy",
               "threshold": 0.9, "anomaly_band": 0.25,
               "anomaly_min_history": 3}
}
```

| Field | Required | Type | Rules |
|-------|----------|------|-------|
| `name` | yes | string | The sensor name this extension files as. Letters, digits, `.`, `_`, `-`; starts with a letter or digit; at most 64 characters. |
| `version` | yes | string | The extension's own version, semver-shaped (`0.3.0`, suffixes like `-rc.1` allowed). Yours to rev. |
| `api_version` | yes | integer | The extension API the manifest was written against. Must be a whole number, 1 or more. See the compatibility promise below. |
| `kind` | yes | string | `"sense"` (this document) or `"transport"` (docs/TRANSPORTS.md). |
| `signals` | yes | list | 1 to 64 entries, each an object with `name` and `description`. Names unique within the manifest. This list is the contract; see "Signals are the contract". |
| `description` | no | string | One line, at most 200 characters: what the extension is, for humans reading the logs and docs. |
| `tunables` | no | object | Your knobs, carried through unread by the agent. Your daemon reads them from its own manifest. The sense's ingest gates (severity floor, cooldown, caps) are separate: those live in the sensor's `profile` in `config.json`, as for every sense. |

Validation is strict in both directions. A missing required
field, a bad type, an unknown signal shape — refused, with the
reason in the startup report. Unknown fields are refused **by
name**: if you type `singals` instead of `signals`, the loader
says so, instead of loading a manifest that silently declares
nothing. A signal's `description` must be one non-empty line of
at most 200 characters; it is Oracle context, and context is a
budget.

## Three version numbers

Confusing these is the classic way extension systems rot, so the
design keeps them apart on purpose:

1. **The agent version** — the release number of Homing Pigeon
   itself (in `pyproject.toml` and the changelog). Not yours, and
   your manifest never mentions it.
2. **Your extension's `version`** — your package's semver. Rev
   it as often as your research loop wants: daily, hourly. It
   changes nothing about loading. It rides along in the startup
   report, in every stored alert (`extension_version`), and in
   the `senses` answer, so a reader can always tell which build
   of your extension filed a given signal.
3. **`api_version`** — the version of the manifest contract
   itself. It is 1, and it is designed to stay 1.

### The api_version promise

The loader's rule:

- `api_version` equal to the agent's extension API version:
  loads.
- `api_version` **newer** than the agent provides: refused, with
  a log line saying the extension requires a newer agent.
- `api_version` **older**: accepted.

The third line is a promise about how the API evolves: fields
may be added, never removed or reinterpreted, so a manifest
written against an older contract keeps loading and keeps
meaning what it meant. The intent is that you write
`api_version: 1` once and never think about it again; your inner
loop revs your `version`, and the contract holds still
underneath it.

## Signals are the contract

The `signals` list is not documentation garnish. It is the
context the Oracle receives about your extension, and it is
enforced at ingest:

- Your alerts name a signal in the alert's `signal` field.
- If the signal is declared, the alert is stored with the
  signal's declared description attached
  (`signal_description`), and your extension's name and version
  beside it.
- If the signal is **not declared** — or the alert names no
  signal at all — the alert is rejected at ingest and the
  rejection is logged with the list of what is declared. Nothing
  is stored, nothing is passed through quietly.
- Every `senses` answer that touches your sense carries a
  `declared_signals` glossary: your extension's name and
  version, and each declared signal with its description.

Why this strict: the Oracle is a model reading context. A signal
it has never seen defined is a string it would have to guess at,
and guessed-at signals become invented findings. Declaring the
signal set up front means every signal the Oracle ever weighs
arrived with its definition attached, written by the person who
knows what it means.

Senses that are not backed by an extension (the built-in style:
`host_ids`, `netmon`, configured directly in `config.json`)
keep the older, looser behavior: no signal field required. The
declared-signal gate applies to extension-backed senses, because
the manifest exists to gate on.

## Binding: an extension files as its own sensor

An extension does not get a new trust path. It files alerts
through the senses path, bound to a sensor of the same name, so
the manifest's `name` needs the matching entries in
`config.json` — the same three every sense needs:

```json
"sensors": {
  "lab_results": {"enabled": true, "key_id": "lab-key",
                  "weight": 1.0, "profile": {}}
},
"key_policies": {
  "lab-key": {"allowed_kinds": ["sensor_alert"]}
},
"additional_secrets": {
  "lab-key": "<the secret your daemon signs with>"
}
```

The binding rule is the senses rule: the key that signs an alert
must be the key bound to that sensor (`sensors.<name>.key_id`),
so one extension cannot file as another sense, and a stolen
low-privilege key can file alerts and nothing else — it cannot
run jobs. Weights, severity floors, cooldowns, and hourly caps
tune per sense in the sensor's `profile`, exactly as
[docs/senses.md](senses.md) describes.

## Local delivery: two transports, one envelope

Everything above describes the envelope and the contract. How
the envelope travels is a separate choice, and it is yours.

The default path is the mail path: your daemon signs the
envelope and sends it as a job to the runner's mailbox, and the
runner files it on its next poll. That path works from any
machine and needs nothing else running.

When your daemon runs on the **same machine** as the runner,
the mailbox round trip buys nothing, and two local front-ends
are built in. Both carry the identical envelope — same fields,
same `api_version` statement, same signature, verified by the
same chain, gated by the same declared-signal contract, stored
in the same senses store (with `source: "local"` on the record).
A transport is replaceable plumbing under the contract, never a
new contract: you code against the envelope, and you can switch
pipes without touching your signal code. The envelope carries
its `api_version` for exactly this reason — the statement rides
with the message, so any transport, present or future, is
validated against the same promise as the manifest.

**Periodic style — file drop.** Your producer writes one signed
envelope per signal into `<base_dir>/local-inbox/`, one `.json`
file per envelope. A watcher in the runner scans the inbox
about once a second, files what verifies, and removes each file
either way (a rejected envelope is logged, never retried
forever). This style serves producers that already work in
passes — a watcher diffing a folder, a cron-driven collector.
The producer helper writes the file atomically under the
envelope's job_id as its name, so re-dropping an envelope
rewrites the same file: the producer keeps no delivery state
beyond its key, and each pass builds fresh envelopes and drops
them.

**Direct style — socket push.** Your producer opens a TCP
connection to `127.0.0.1` on the runner's local signal port
(default `39271`), sends the signed envelope text, and closes
its write side. One envelope per connection, size-capped, read
with a short timeout, the connection closed after ingest. This
style serves extensions with their own event machinery that
fires and sends at once; no file is involved. The listener
binds loopback only — it is not a network service — and an
unsigned or malformed connection is logged and dropped without
disturbing the listener.

The producer helpers live in `runner/extensions.py`:
`build_sensor_alert(...)` composes the envelope,
`sign_envelope(payload, secret)` seals it, and
`drop_local_signal(base_dir, payload, secret)` /
`send_local_signal(payload, secret, port=...)` deliver it. The
Lab Results example drives both styles: run it with
`--local-dir <runner base dir> --key-id <its key id>` and the
signing secret in the environment variable named by
`--secret-env` (default `HOMING_PIGEON_SENSOR_SECRET`); add
`--local-port 39271` to push instead of dropping files.

Config keys (all read at startup):

| Key | Default | Meaning |
|-----|---------|---------|
| `local_signals` | `true` | Master switch for both local front-ends. `false` starts neither. |
| `local_signal_port` | `39271` | Loopback port for the direct style. `0` or `false` turns the listener off; the inbox still works. |
| `local_wake_cooldown_sec` | `900` | Minimum seconds between Oracle briefings for the same sensor + signal. |

Local delivery changes latency, not trust. A bad signature is
a rejection exactly as on the mail path; the signing key must
still be the key bound to the sensor, and its key policy must
still allow `sensor_alert` only. What local delivery removes is
the mailbox, not the checks.

### The wake

A locally filed alert does one thing a mailed alert does not:
it can wake the Oracle. The gate is deterministic — no model
judgment is involved in deciding:

- the alert's severity is `high` or `critical`,
- no other briefing is currently in flight, and
- this sensor + signal pair has not woken within
  `local_wake_cooldown_sec`.

When the gate fires, a briefing thread asks the Oracle — the
same local model path the interactive chat uses — to assess the
signal against the box's current context and state what
happened and what, if anything, the owner should do. The
assessment is appended to `oracle-briefs.jsonl` in the base dir
(one JSON object per brief: time, sensor, signal, severity,
title, status, assessment — plus `mode` in deterministic mode)
and written to the runner log, so a later question
to the Oracle reads it back as part of the log. If no local
model is configured, the brief is a deterministic note saying
so; if the model fails, the brief records the failure. The
briefing never blocks ingest, and a sense that fires constantly
wakes the Oracle at most once per cooldown per signal — the
gate exists so enthusiasm cannot spend the box.

## Failure posture

Extensions fail closed and fail quiet:

- At startup the agent logs one line per loaded extension
  (`extension loaded: lab_results v0.3.0 (extension API v1,
  kind sense, 3 declared signal(s)) from ...`) and one warning
  per refusal, with the reason (`extensions: extension folder
  'future': refused: extension requires extension API v99 ...`).
- A refused extension changes nothing else: the agent starts,
  other senses ingest, jobs run. A folder whose manifest is
  missing, unreadable, malformed JSON, a symlink, or a duplicate
  name is skipped and reported the same way.
- If an extension is refused, its sensor name is simply a plain
  sense as far as ingest is concerned (the declared-signal gate
  has no manifest to gate on). The startup report is where you
  learn that your packaging, not your daemon, needs the fix.

## Sources: every extension brings its own code

This section applies to both kinds, `sense` and `transport`.

The Oracle reasons better about a signal, a failure, or a pipe
when it can read the code behind it — and the upstream project
that code wraps, and the specification it speaks. So whenever a
local model runs the Oracle (the default; "Owner settings"
below), the first time the agent runs an extension (loads a
sense, starts a transport), it gives the Oracle that material:

- **Its installed code.** Your extension folder as installed,
  declared or not. A folder inside the state dir (the default
  `extensions/`) is referenced where it sits. A folder outside
  it is copied into the state dir — code and docs only: no
  dotfiles, nothing named like a secret (`*token*`, `*.key`,
  `.env`, and the like), no file over 1 MiB, 8 MiB in all — so
  the Oracle's file tools can reach it.
- **What your `sources.json` declares.** An optional file next
  to `extension.json`: your own published source, the upstream
  projects your extension wraps, the specifications it speaks,
  schemas, rule sets, docs.

A daemon that runs on another machine (the mail path) still has
its folder here, the manifest at least, and that folder is all
the agent can copy. Declare a `self` entry pointing at the
published code, so the Oracle reads what actually runs.

Nothing fetched ships. A release carries the declarations (a few
kilobytes); the fetching happens on the box, in the background,
the first time each extension runs. A second run fetches
nothing: an entry is fetched again only when its declaration
changes. The manifest is untouched — `sources.json` is a
separate file, so an agent that predates it loads the same
extension and never reads it.

### The declaration

```json
{
  "sources_version": 1,
  "sources": [
    {"id": "suricata", "role": "upstream",
     "description": "Suricata, the network IDS whose eve.json this sense reads.",
     "license": "GPL-2.0-only",
     "github": "OISF/suricata", "ref": "latest",
     "tag_match": "^suricata-\\d+\\.\\d+\\.\\d+$",
     "files": ["etc/schema.json", "LICENSE"],
     "archive": true, "max_mb": 96},
    {"id": "rfc7011", "role": "spec",
     "url": "https://www.rfc-editor.org/rfc/rfc7011.txt"},
    {"id": "self", "role": "self",
     "github": "you/your-extension", "ref": "v0.3.0", "archive": true}
  ]
}
```

| Field | Rules |
|-------|-------|
| `sources_version` | Required; `1`. Newer than the agent reads: refused. Older: accepted. The manifest's promise, kept the same way. |
| `oracle` | Optional, top level: `"provide"` or `"withhold"`, the author's line for the whole extension in the disclosure rule below. |
| `sources` | Up to 16 entries. |
| `id` | Required. Letters, digits, `.`, `_`, `-`; unique without regard to case (it becomes a folder); `installed` is reserved. |
| `role` | Required: `self`, `upstream`, `spec`, `schema`, `rules`, or `docs`. Context for the Oracle. |
| `description`, `license` | Optional, one line each (at most 200 and 100 characters). |
| `github` / `url` / `project` | Exactly one location: a GitHub repository (`owner/repo`); one https URL; or paths inside Homing Pigeon's own tree (for the extensions that ship with it). |
| `ref` | GitHub only. `"latest"` (the default, below), or a tag, a branch, or a commit. |
| `tag_match`, `asset_match` | `"latest"` only. A regular expression the release tag must match; one that picks a release asset as the archive (a release tarball carries what GitHub's own archive does not, such as submodules). |
| `files` | GitHub only. Up to 32 repository paths, each fetched alone at the pinned commit. |
| `archive` | GitHub or URL: fetch the whole source archive and unpack it. A GitHub entry asks for its archive, its files, or both. |
| `max_mb` | Default 64, at most 512: the most this entry may download. |
| `oracle` | Optional, per entry: `"provide"` or `"withhold"`. |

Validation is the manifest's: unknown fields are refused by
name, and so is any path that could leave its folder or could not
exist on every platform. A refused declaration does not refuse
the extension — it loads and runs, its installed code still
reaches the Oracle, and the log says what to fix.

**"latest"** is the highest-versioned release that is not a draft
or a prerelease (and matches `tag_match`); with no such release,
the highest-versioned matching tag; with no tags, the default
branch's head. Highest version, not newest: a project that
patches two release lines publishes old-line patches after
new-line releases. The release this picks can differ from the
version installed on the box, and the index says so.

### Integrity: pinned by the build

"latest" is resolved when Homing Pigeon is built. The release job
runs `tools/pin_extension_sources.py`: every declared upstream
pinned to a commit, every file and archive downloaded and hashed
(SHA-384), all of it written to
`project/EXTENSION-SOURCES.lock.json` inside every release
archive. A box fetches exactly what its build pinned and refuses
bytes whose digest differs: nothing is stored, the entry reads
`mismatch`, and it is tried again a day later. A pin vouches for
bytes only: every URL is rebuilt from the declaration and the
pinned release (its commit, or its asset).

An extension author pins the same way and ships the result next
to the declaration:

```bash
python tools/pin_extension_sources.py --out my-ext/sources.lock.json my-ext
```

The extension's own `sources.lock.json` is consulted first, then
the build's, and either applies only to the exact declaration it
was made from. With no pin — a source checkout, a third-party
extension without a lock — the box resolves the declaration on
first run and records what it got (trust on first use).

### Safety

Fetched material is data. Nothing fetched is ever executed or
imported. Every request is https, redirects included; the GitHub
token the release job holds goes to api.github.com and nowhere
else. Archives unpack as plain files only — no links, no devices,
no execute bits, nothing outside the target; a name a Windows box
cannot hold is skipped — bounded per entry by `max_mb` (unpacked,
at most 20 times what was downloaded) and in all by the owner's
disk budget. Small things go first for every extension (single
files, project paths, installed code), then archives, smallest
cap first. An offline box records each failure and retries on
backoff, an hour doubling to a day; a server that answers 404 is
asked again a day later, and one missing file in an entry that
otherwise arrived is noted in the index instead of retried.
Nothing here blocks the agent or the extension.

### The disclosure rule

Every piece an extension brings is either **provided** to the
Oracle or **withheld** from it. For one piece, the first of these
that is set decides:

1. the owner, for this extension:
   `extension_sources.extensions.<name>.oracle` in `config.json`;
2. the owner, for every extension: `extension_sources.oracle` —
   only `"withhold"` acts here; the default `"provide"` defers to
   the author;
3. the author, for this entry: the entry's `oracle` in
   `sources.json`;
4. the author, for the extension: the top-level `oracle`;
5. otherwise: provide.

Provided material is listed in `extension-sources/INDEX.md`,
named in the Oracle's context, and readable with the Oracle's
file tools. Withheld material is never listed or named, and
`read_file`, `list_dir`, and `write_file` refuse it — a withheld
extension's own folder under the state dir included. The Oracle's
`run` tool is a shell on the box and is not a confidentiality
boundary: an owner who needs one sets `"fetch": false` for that
extension, and nothing is fetched or copied at all. A malformed
`extension_sources` setting fails closed: nothing is fetched,
everything is withheld, and one log line says why.

The Oracle is local by construction — the inference endpoint must
be loopback — so "provide" means this box's own model reads it.
Nothing here sends source anywhere.

### Owner settings

`extension_sources` in `config.json`, read live (an edit runs a
pass at once):

| Value | Meaning |
|-------|---------|
| `"auto"` (default) | Fetch when a local model runs the Oracle. A deterministic (Pi Light) box with no model fetches nothing and writes nothing. |
| `true` | Always fetch. |
| `false` | Never fetch. |
| an object | `{"fetch": "auto" / true / false, "oracle": "provide" / "withhold", "max_mb": 512, "extensions": {"<name>": {"fetch": true / false, "oracle": "provide" / "withhold"}}}` — the same switch, the owner's lines of the disclosure rule, the disk budget in megabytes (default 512), and per-extension overrides. |

### Where it lands, and how to look

```
<base_dir>/extension-sources/
    INDEX.md                      what the Oracle may read, with paths
    <kind>/<name>/SOURCES.json    everything recorded: status, pins, digests, retries
    <kind>/<name>/installed/      the installed code, when it lives outside the state dir
    <kind>/<name>/<id>/CARD.json  one entry's provenance
    <kind>/<name>/<id>/files/     its single files
    <kind>/<name>/<id>/source/    its unpacked archive
```

`homing-pigeon --inspect sources` prints the recorded state, with
no network. `homing-pigeon --fetch-sources` runs a pass in the
foreground now, retries what failed without waiting out its
backoff, and prints what happened. Asking counts as wanting it:
`"auto"` fetches there even with no model, and only `false`
(overall, or for that extension) stops it. To refetch one entry,
delete its folder. A box with no way out can be seeded: copy
`extension-sources/` from a connected box running the same
release and extensions, and its first pass keeps what arrived.

### What ships declared

The eight IDS adapters declare their upstream project: its source
archive, its license, and the files that define what the adapter
reads — Suricata's EVE schema and format guide, Zeek's conn and
dns scripts, osquery's table specs, Falco's default config and
rules, Sysmon for Linux with SysmonCommon; the softflowd adapter
adds NetFlow version 9 (RFC 3954) and IPFIX (RFC 7011). The four
shipped transports declare their own code in the project tree and
the specifications they speak: IMAP4rev1, SMTP, STARTTLS, and the
message format for email; DTLS 1.3, TLS 1.3, HKDF, and X25519 for
dtls; the NATS client protocol for nats. Any extension can do the
same with one file.

## Build your own

Starting from a clone of this repository:

1. Copy the example:
   `cp -r examples/extensions/lab-results <base_dir>/extensions/my-sense`
   (any folder name; the manifest is the identity).
2. Edit `extension.json`: set `name` to your sensor name, declare
   YOUR signals — names you will actually emit, each with the
   one line the Oracle should read it by — set `version` to
   `0.1.0`, leave `api_version` at 1, and put your knobs in
   `tunables`.
3. Add the sensor, key policy, and secret entries to
   `config.json` (previous section). Pick a fresh key id; do not
   share one with another sense.
4. Start the agent and read the startup report: one
   `extension loaded:` line with your name on it, or a refusal
   naming the field to fix.
5. Write your daemon next to the manifest: any process, any
   language, that reads its own `extension.json` (tunables
   included) and files signed `sensor_alert`s naming declared
   signals. The example's `lab_results.py` is a complete,
   readable instance of the pattern.
6. Watch it land: send a `senses` query for your sensor, or ask
   the Oracle. Your alerts come back with `signal`,
   `signal_description`, and `extension_version` attached, and
   the answer's `declared_signals` glossary carries your
   declaration as context.

Testing: the contract this document states is the contract
`tests/test_extensions.py` pins — manifest validation, the
api_version matrix, the undeclared-signal rejection, the
glossary in the answer, and the example loading clean. Run it
while you develop:

```bash
python3 -m unittest tests.test_extensions
```

The agent's `--dry-run` flag also describes incoming alerts
without storing them, which is the fast way to check a daemon's
envelope and signal names against a live config.

## The example: Lab Results

`examples/extensions/lab-results/` is a working sense for
people who run experiments. Training and evaluation harnesses
drop result files; Lab Results turns the folder into signals.

- `extension.json` — the manifest. Name `lab_results`, three
  declared signals, tunables: `watch_dir`, `metric`,
  `threshold`, `anomaly_band`, `anomaly_min_history`.
- `lab_results.py` — the watcher daemon. One pass scans the
  results folder, diffs it against a state file, and prints one
  alert payload per line on stdout. Signing and delivery are
  the standard senses flow from there.
- `README.md` — the short version, with the result-file shape.

A result file is one JSON object per run:

```json
{"run": "exp-041", "status": "finished",
 "metrics": {"accuracy": 0.93, "loss": 0.21}}
```

The declared signals:

| Signal | Fires when | Severity |
|--------|------------|----------|
| `experiment_finished` | A run's file reaches `"status": "finished"` | info |
| `metric_threshold_crossed` | A finished run's `metric` value reaches `threshold` | medium |
| `result_anomaly` | A finished run's `metric` value sits farther than `anomaly_band` (relative) from the mean of the folder's earlier finished runs, with at least `anomaly_min_history` of them | high |

Diffing rules: files are compared by content. A file that does
not parse yet (a run still writing it) files nothing and is
retried on the next pass; a run that has not finished files
nothing until it lands. Editing a finished result re-reports it:
the content changed, so the lab produced a new result. State
lives in `.lab-results-state.json` inside the results folder;
delete it and the next pass reports the folder's history as new.

```bash
python3 lab_results.py --watch-dir path/to/results
{"detail": {"metric": "accuracy", "run": "exp-041", "value": 0.95}, "sensor": "lab_results", "severity": "info", "signal": "experiment_finished", "title": "experiment exp-041 finished"}
{"detail": {"metric": "accuracy", "run": "exp-041", "threshold": 0.9, "value": 0.95}, "sensor": "lab_results", "severity": "medium", "signal": "metric_threshold_crossed", "title": "experiment exp-041: accuracy 0.95 crossed threshold 0.9"}
```

## The Pi Light example: Pi Health

`examples/extensions/pi-health/` is a working sense for the
health of the machine it runs on, and the Pi Light showcase:
on a Pi it runs with no local model anywhere in the loop, but
nothing about it is Pi-only — the same extension runs on a
laptop or any other box. The watcher reads the machine's
vitals and files what needs attention. Run it on a Pi Light
install and on a laptop install side by side and any
difference in behavior is the platform's exposed sensors and
the Oracle configuration, not the extension — a clean A/B
across the two architectures.

- `extension.json` — the manifest. Name `pi_health`, four
  declared signals, tunables: `temp_high_c`, `disk_high_pct`,
  `disk_mount`, `mem_avail_low_pct`.
- `pi_health.py` — the watcher daemon. `read_board()` is the
  only function that touches the machine; `decide()` turns
  one readings dict into alerts and is pure, so the decision
  surface is testable on any machine. Every source is
  optional and capability-based — a source the machine does
  not expose reports nothing, which never yields a signal
  and is never an error. Temperature comes from the Linux
  thermal sysfs, preferring the zone whose type names the
  SoC or CPU package (`cpu-thermal` on a Pi, `x86_pkg_temp`
  on Intel laptops); undervoltage comes from
  `vcgencmd get_throttled` and is Pi-only by nature; disk
  from the mount; memory from `/proc/meminfo` on Linux,
  `GlobalMemoryStatusEx` on Windows, `os.sysconf` page
  counts on other POSIX systems. `--readings FILE` feeds a
  readings dict from JSON instead of live reads.
- `README.md` — the short version, with the readings shape.

The declared signals:

| Signal | Fires when | Severity |
|--------|------------|----------|
| `board_overheating` | CPU/SoC temperature reaches `temp_high_c` (default 80) | high |
| `undervoltage_detected` | The Pi firmware throttled bitmask shows undervoltage or throttling, now or since boot | high |
| `disk_pressure` | The `disk_mount` mount reaches `disk_high_pct` (default 90) | medium |
| `memory_pressure` | Available memory falls to `mem_avail_low_pct` (default 10) | medium |

The two high signals are the point of the example: they cross
the local wake gate, so on a Pi Light install a hot or
power-starved board wakes the deterministic Oracle, which
files its brief from the alert itself — sensor, signal,
severity, title — with no inference involved at any step.

## The Pi Light example: Airwaves

`examples/extensions/airwaves/` is the Pi's wireless
neighborhood watch, and the second Pi Light showcase: a Pi
sits on a desk with its radio on anyway, so it may as well
keep the baseline of what the air around it normally looks
like. The watcher reads the scan results the platform
already has — cached `nmcli` output first, an `iw` scan dump
as the fallback — and the box's own connected link. It is a
read-only consumer: it never associates to a network, never
deauthenticates anyone, never injects frames.

- `extension.json` — the manifest. Name `airwaves`, four
  declared signals, tunables: `poll_interval_sec`,
  `gone_after_scans`, `link_drop_db`, `iface`,
  `learn_first_pass`.
- `airwaves.py` — the watcher. `read_live()` is the only
  function that touches the platform; the scan parsers and
  `decide()` are pure, and baselines (known BSSIDs per SSID,
  the best security each SSID advertises, the AP set, the
  link's reference signal) live in the state file.
  `--readings FILE` feeds a scan from JSON instead.
- `README.md` — the short version, including why BLE is
  out of scope: no clean standard-library source exists.

The declared signals:

| Signal | Fires when | Severity |
|--------|------------|----------|
| `new_access_point` | A BSSID never seen before broadcasts a network this box does not know | medium |
| `evil_twin_suspect` | A known SSID appears from a NEW BSSID, or a known network suddenly advertises weaker security than its baseline — the wireless form of the ARP-spoof tell | high |
| `access_point_gone` | A long-known AP is missing across `gone_after_scans` consecutive scans (default 3) | info |
| `link_degraded` | The box's own link signal drops by `link_drop_db` or more from its reference, or the link roams to another BSSID unexpectedly | medium |

The evil-twin signal is the point of the example, the same
way `mac_moved` is the point of Wire Arrivals below: an
identifier the baseline trusts is suddenly being answered
by different hardware. On a Pi Light install the high signal
wakes the deterministic Oracle exactly as Pi Health's does.

## The example: Sky Watcher

`examples/extensions/sky-watcher/` is a working sense for
people who like looking up. It polls the International Space
Station's position from the free wheretheiss.at feed (no API
key) and files the passes over one observer that are worth
stepping outside for — the fun counterpart to Lab Results'
earnestness, exercising the same contract in the open air.

- `extension.json` — the manifest. Name `sky_watcher`, three
  declared signals, tunables: `observer_lat`, `observer_lon`
  (unset by default — the watcher files nothing until they are
  set), `approach_radius_km`, `visible_min_elevation_deg`,
  `bright_min_elevation_deg`, `visible_lead_sec`,
  `dark_sun_elevation_deg`, `poll_interval_sec`.
- `sky_watcher.py` — the producer. One invocation takes one
  position sample; a one-minute timer (cron, systemd) drives
  the cadence. `fetch_position()` is the only network code;
  the pass logic is pure geometry plus a state machine, and
  `--samples FILE` replays recorded feed responses offline.
- `README.md` — the short version, with the cron line and the
  wheretheiss.at attribution.

The declared signals:

| Signal | Fires when | Severity |
|--------|------------|----------|
| `station_approaching` | The station enters the approach corridor (`approach_radius_km`, default 5000 km) around the observer — every pass, visible or not | info |
| `visible_pass_starting` | A sunlit pass over a dark sky begins within `visible_lead_sec` (default 600), culminating above `visible_min_elevation_deg` (default 10°) | medium |
| `bright_pass` | That pass culminates at or above `bright_min_elevation_deg` (default 65°) — near zenith | high |

How a pass is read, in brief. The central angle between the
observer and the station's sub-point gives the elevation
directly; two successive sub-points define the orbit plane,
so the pass's culmination is estimated before it happens and
the heads-up fires inside the lead time, never after the
fact. The station being sunlit is the feed's own `visibility`
field; the observer's sky being dark is a small solar
calculation (the NOAA approximation) against the
`dark_sun_elevation_deg` threshold, -6° by default. A pass
walks out → approaching → visible → out, each stage files
once per pass, and the state resets as the station leaves the
corridor. A feed outage is a quiet no-op: nothing files, the
state is untouched, the next minute retries.

```bash
python3 sky_watcher.py --samples recorded-passes.json
{"detail": {"culmination_deg": 90.0, "elevation_deg": -16.7, "ground_distance_km": 4748, "observer_lat": 0.0, "observer_lon": 0.0}, "sensor": "sky_watcher", "severity": "info", "signal": "station_approaching", "title": "ISS entering the approach corridor -- culmination ~90 deg"}
{"detail": {"culmination_deg": 90.0, "elevation_deg": -16.7, "starts_in_sec": 467}, "sensor": "sky_watcher", "severity": "medium", "signal": "visible_pass_starting", "title": "visible ISS pass starting in ~8 min -- culmination 90 deg"}
{"detail": {"culmination_deg": 90.0, "elevation_deg": -16.7, "starts_in_sec": 467}, "sensor": "sky_watcher", "severity": "high", "signal": "bright_pass", "title": "bright ISS pass overhead -- culmination 90 deg"}
```

(The sample output is a replayed zenith pass over an observer
on the equator at midnight: all three stages fire at corridor
entry, because the window opens inside the lead time.)

## The catalog: twenty-five examples from the workbench

Twenty-eight extension folders ship in all; this catalog pins
twenty-five. `lab-results`, `pi-health`, and `sky-watcher` are
standalone examples outside the pinned table, and `airwaves`
appears both as a full section above and as a row below.

Seventeen more working senses, each one a small diffing
watcher in the same shape as the four above — a manifest, a
boring producer with one platform-reading function and a
pure `decide()`, a state file, and a README. Thirteen are
rooted in trades their author practiced: fuzzing, PKI,
network engineering, penetration testing, kernel work,
code signing, operations; the last four watch the machine's
resource trends, the runner's own job history,
machine-learning training runs, and the neighborhood of
the jobs themselves.
Powerful-desktop senses are the center of
gravity; every one also declares how it tunes down for a Pi
Light install (its README's Light mode section has the
detail — only knobs the code implements).

Eight more adapters follow the same producer shape over a
different kind of source: the output artifact of a real IDS
collector the installer can set up (`docs/senses.md` has the
installer story, including which one is the default and why).
Each feed's README carries its collector's measured
footprint; where a number is environment-bound — a ruleset,
a kernel that denied BPF — the README says so instead of
quoting a number it cannot stand behind.

| Extension | Watches | Light mode, in one line |
|-----------|---------|-------------------------|
| `crash-watch` | Crash/core dump folders: a new dump (medium); the same binary crashing again inside the window (high) | Cadence to 600s, fewer folders, `max_files_per_pass` down |
| `release-drop` | A drop folder: each artifact arrives with its SHA-384 digest in the alert (info); the same name with a different digest (high) | `max_hash_mb` down (oversize artifacts wait), cadence up |
| `cert-sentinel` | Certificate files and TLS endpoints: expiry inside 30 days (medium), inside 7 or expired (high), issuer/subject/serial change (info) | Already daily; files-only means zero network probes |
| `wire-arrivals` | The ARP/neighbor table: a MAC never seen on this LAN (medium); a known IP answering from new hardware (high) | Cadence to 900s, one interface only |
| `latency-post` | Gateway and target latency by TCP probe: spike over the rolling median (medium), target unreachable (high) | Cadence to 600s, gateway only |
| `port-watch` | Listening sockets: a new listener (medium); one on a wildcard address or well-known port (high) | Cadence up; `high_only` files only the street-facing doors |
| `failed-login-watch` | Auth logs: a failure burst inside the window (medium); a success right after a burst (high) | Cadence up, one log file, `burst_count` up |
| `tripwire` | A file tree's SHA-384 baseline: file appeared or vanished (medium), content changed (high) | Narrower root and excludes, `max_file_mb` down — hashing still costs the bytes it reads |
| `log-sentinel` | Kernel/system log tails: OOM, panic, segfault, filesystem distress (high); configured patterns (medium) | `tail_bytes` bounds the cost per pass, not the log's size; fewer pattern groups |
| `service-watch` | Named processes: an expected one dies (high), restart flapping (medium), it comes back (info) | Cadence to 300s, fewer services, flap thresholds up |
| `backup-freshness` | A backup folder's newest artifact: stale past the threshold (medium), twice it (high), a fresh one lands (info) | Cadence to six hours; this sense is already nearly free |
| `usb-arrivals` | USB/serial device arrivals: a new device (info); a new storage-class device (medium) | Cadence to 1800s, USB kinds only |
| `airwaves` | The Pi's wireless neighborhood (full section above): new AP (medium), evil-twin suspect (high), AP gone (info), own link degraded (medium) | Cadence is the knob — 300s to 1800s; it only ever reads |
| `resource-sentinel` | The machine's counters, judged as rates and trends, never single samples: CPU held saturated across the window (high), disk free space shrinking too fast (high), process count storm (medium), memory falling steadily to the floor (medium) | Cadence to 300s, window down — the trends it hunts play out over minutes |
| `job-watcher` | The runner's retained job history: the same job failing repeatedly (medium), a job alternating pass/fail (info), a run far beyond the job's own duration baseline (medium, and never before a baseline exists), many distinct jobs failing at once (high) | Cadence to 900s; history does not move fast |
| `training-watch` | An ML training run: its log tail, checkpoint directory, and GPU — a checkpoint that has stopped changing (info), a log quiet past the stall limit or flat parsed losses (medium), crash markers: Traceback, CUDA out of memory, NCCL error, RuntimeError (high), GPU overheating (high), GPU memory pressure (medium) | Cadence to 900s; `tail_bytes` down; the parser half needs no GPU |
| `job-fuzz` | The runner's retained jobs, fuzzed: grammar-shaped mutations of real jobs run through the core's validation and confined execution (`--run-variant`) on idle cycles only — a variant that hangs or breaks the run (high), a variant whose outcome class diverges from the seed job's recorded class (medium), a first-seen (mutator, stage, class) combination (info) | Cadence to 900s; `max_variants_per_pass` down; the campaign spends idle cycles only |
| `falco-feed` | Falco's JSON alert file: Emergency/Alert/Critical rules (high); Warning/Notice rules (medium). No footprint claimed for Falco itself: it did not run in the measurement sandbox (the host denied BPF) — on a normal box the modern-eBPF driver is the zero-build path | Cadence up; the episode cooldown is the volume knob |
| `suricata-feed` | Suricata's eve.json: alert signatures at the source's own severity (1 high, 2 medium, 3 info); protocol anomalies (medium). ~52 MB with a minimal ruleset in the measurement container — a production ruleset is several hundred MB; the rules are the weight | A trimmed ruleset is the real light mode; cadence up |
| `zeek-feed` | Zeek's conn.log and dns.log: a burst of first-seen external peers (medium); DNS anomalies — long queries, odd qtypes, many labels (medium). ~230 MB idle measured: Zeek is never a default | Cadence up; conn.log only |
| `osquery-feed` | osqueryd's results log for the installer's light pack: users and listening ports added (medium), processes added (info), removals (info). ~27 MB and ~0.1% CPU measured — why osquery is the default collector | Cadence up; the pack is already three queries |
| `sysmon-feed` | Sysmon process-create events, Linux syslog XML and Windows text shapes: a process starting from a temp directory (medium); an encoded command line (medium). No footprint claimed: Sysmon for Linux did not run in the measurement sandbox (BPF denied) | Cadence up; Event ID 1 only, by design |
| `aide-feed` | AIDE check reports: entries changed (medium), removed (medium), added (info) — one alert per class per report. No daemon: 0 MB between scans, ~21 MB during a scoped scan | A longer schedule; a narrower tree in the scoped config |
| `softflowd-feed` | NetFlow/IPFIX from softflowd — softflowd has no file, so the adapter is the UDP listener and decoder (v5 complete; v9/IPFIX template-driven over a documented field subset): a first-seen external peer (info), a very large single flow (medium), a long-lived flow (info). softflowd itself measured ~7 MB at ~0% — the lightest of the set | A shorter collect window; higher thresholds |
| `wazuh-feed` | A Wazuh `alerts.json` where one exists on the box — a manager export or API pull; a standalone agent produces none: rule level 10 and up (high), 5–9 (medium). A missing file is a quiet no-op, forever | Cadence up; the episode quiet window up |

Two honest limits, stated once for the whole catalog.
Tripwire over a huge tree cannot be made cheap — hashing
costs the bytes it reads, so light mode there means a
narrower tree, not a faster one. And log-sentinel cannot
watch less than the tail it reads; its knobs bound that
tail (`tail_bytes`, the pattern groups), which is the real
cost either way.

