# Findings — docs/steady/extensions.md

Source: docs/steady/extensions.md, reviewed at main 1f5a6baf.
Sentence units: 402. Flagged: 21. Categories: pre-release 402, post-release 0.

The sense-extension manual: packaging, the manifest field by field, upstream pins, the 3 versions, the declared-signal gate, delivery styles, the review, sources, and a catalog of the shipped senses. A reference manual's prose is staccato by design — field rows and list items — and the rows are recorded as flowing where the table or list is the connection. The flags are table structure and 1 free-standing label. Everything here describes the shipped system: all pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "An extension is a way to teach the…" | pre-release | flows |  |
| 2 | "You package your work as a folder with…" | pre-release | flows |  |
| 3 | "Because the package is only a folder and…" | pre-release | flows |  |
| 4 | "A researcher who teaches the agent to watch…" | pre-release | flows |  |
| 5 | "Packs can circulate the way editor themes and…" | pre-release | flows |  |
| 6 | "The agent does not care whose sense it…" | pre-release | flows |  |
| 7 | "That indifference is what makes an ecosystem possible:…" | pre-release | flows |  |
| 8 | "This document covers one of the two extension…" | pre-release | flows |  |
| 9 | "A sense files signed alerts with the Oracle,…" | pre-release | flows |  |
| 10 | "The plumbing underneath — alert shape, ingest gates,…" | pre-release | flows |  |
| 11 | "This document covers the packaging layer: packaging, versioning,…" | pre-release | flows |  |
| 12 | "The agent never imports or executes sense code." | pre-release | flows |  |
| 13 | "The whole surface the agent consumes is:" | pre-release | flows |  |
| 14 | "your manifest (`extension.json`), read at startup and on…" | pre-release | flows |  |
| 15 | "the signed `sensor_alert` envelope your daemon sends ([docs/extend/senses.md](senses.md),…" | pre-release | flows |  |
| 16 | "the `senses` query answer, where your declared signals…" | pre-release | flows |  |
| 17 | "your optional `sources.json`, read when your extension first…" | pre-release | flows |  |
| 18 | "It is data too." | pre-release | flows |  |
| 19 | "Your daemon — the watcher, collector, or bridge…" | pre-release | flows |  |
| 20 | "There is no plugin API to chase because…" | pre-release | flows |  |
| 21 | "Each extension is one subfolder of the extensions…" | pre-release | flows |  |
| 22 | "default: an `extensions/` folder inside the agent's base…" | pre-release | flows |  |
| 23 | "override: the `extensions_dir` key in `config.json` (a relative…" | pre-release | flows |  |
| 24 | "The folder name is yours." | pre-release | flows |  |
| 25 | "The identity of the extension is the `name`…" | pre-release | flows |  |
| 26 | "Two folders may not declare the same name:…" | pre-release | flows |  |
| 27 | "`extension.json`, one per extension folder:" | pre-release | flows |  |
| 28 | "| Field | Required | Type | Rules…" | pre-release | flagged | A table header row — structure, not a sentence |
| 29 | "|-------|----------|------|-------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 30 | "| `name` | yes | string | The…" | pre-release | flows |  |
| 31 | "Letters, digits, `.`, `_`, `-`; starts with a…" | pre-release | flows |  |
| 32 | "| `version` | yes | string | The…" | pre-release | flows |  |
| 33 | "Yours to rev. |" | pre-release | flows |  |
| 34 | "| `api_version` | yes | integer | The…" | pre-release | flows |  |
| 35 | "Must be a whole number, 1 or more." | pre-release | flows |  |
| 36 | "See the compatibility promise below. |" | pre-release | flows |  |
| 37 | "| `kind` | yes | string | `"sense"`…" | pre-release | flows |  |
| 38 | "| `signals` | yes (sense) | list |…" | pre-release | flows |  |
| 39 | "Names unique within the manifest." | pre-release | flows |  |
| 40 | "This list is the contract; see "Signals are…" | pre-release | flows |  |
| 41 | "| `description` | no | string | One…" | pre-release | flows |  |
| 42 | "| `tunables` | no | object | Your…" | pre-release | flows |  |
| 43 | "Your daemon reads them from its own manifest." | pre-release | flows |  |
| 44 | "The sense's ingest gates (severity floor, cooldown, caps)…" | pre-release | flows |  |
| 45 | "| `upstream` | no | object | The…" | pre-release | flows |  |
| 46 | "The agent validates the shape and never fetches." | pre-release | flows |  |
| 47 | "See "Upstream: carrying the format you parse". |" | pre-release | flows |  |
| 48 | "| `capabilities` | no | list | What…" | pre-release | flows |  |
| 49 | "Absent means none." | pre-release | flows |  |
| 50 | "The review holds the code to this list…" | pre-release | flows |  |
| 51 | "Validation is strict in both directions." | pre-release | flows |  |
| 52 | "A missing required field, a bad type, an…" | pre-release | flows |  |
| 53 | "Unknown fields are refused **by name**: if you…" | pre-release | flows |  |
| 54 | "A signal's `description` must be one non-empty line…" | pre-release | flows |  |
| 55 | "A feed sense reads what another program writes…" | pre-release | flows |  |
| 56 | "The adapter is only as right as its…" | pre-release | flows |  |
| 57 | "The `upstream` manifest field names the few files…" | pre-release | flows |  |
| 58 | "`pin` is the commit the files were taken…" | pre-release | flows |  |
| 59 | "The fetch is plain git -- a blobless,…" | pre-release | flows |  |
| 60 | "Full upstream source does not fit on purpose:…" | pre-release | flows |  |
| 61 | "Three things are checked, and none needs the…" | pre-release | flows |  |
| 62 | "**The tree is whole.** `runner/tools/fetch_upstream.py --check` (and `runner/tests/test_upstream_pins.py`)…" | pre-release | flows |  |
| 63 | "The build runs the check." | pre-release | flows |  |
| 64 | "**The reading still holds.** For each feed sense…" | pre-release | flows |  |
| 65 | "An upstream rename shows up as a red…" | pre-release | flows |  |
| 66 | "**The pins move on a schedule, not by…" | pre-release | flows |  |
| 67 | "When they do not, nothing is committed and…" | pre-release | flows |  |
| 68 | "Which upstream each shipped feed carries:" | pre-release | flows |  |
| 69 | "| Sense | Repository | Files |" | pre-release | flagged | A table header row — structure, not a sentence |
| 70 | "|-------|------------|-------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 71 | "| `suricata_feed` | OISF/suricata | `etc/schema.json` (the eve.json…" | pre-release | flows |  |
| 72 | "| `zeek_feed` | zeek/zeek | `scripts/base/protocols/{conn,dns}/main.zeek` (the `Conn::Info`…" | pre-release | flows |  |
| 73 | "| `osquery_feed` | osquery/osquery | `specs/{processes,users,listening_ports}.table` |" | pre-release | flows |  |
| 74 | "| `falco_feed` | falcosecurity/rules | `rules/falco_rules.yaml` (the rule…" | pre-release | flows |  |
| 75 | "| `wazuh_feed` | wazuh/wazuh at `v4.14.9` | `src/analysisd/format/to_json.c`…" | pre-release | flows |  |
| 76 | "| `aide_feed` | aide/aide | `src/report.c`, `src/report_plain.c` |" | pre-release | flows |  |
| 77 | "| `sysmon_feed` | Sysinternals/SysmonCommon | `manifest.xml` (the event…" | pre-release | flows |  |
| 78 | "| `softflowd_feed` | irino/softflowd | `softflowd.h`, `compat/netflow{5,9}.c` |" | pre-release | flows |  |
| 79 | "Your own extension may name an upstream the…" | pre-release | flows |  |
| 80 | "A manifest without the field is unchanged, and…" | pre-release | flows |  |
| 81 | "The changelog names the release that added it." | pre-release | flows |  |
| 82 | "The block is the one place an extension…" | pre-release | flows |  |
| 83 | "It is read three ways from that one…" | pre-release | flows |  |
| 84 | "`license` in the block is the upstream's SPDX…" | pre-release | flows |  |
| 85 | "Confusing these is the classic way extension systems…" | pre-release | flows |  |
| 86 | "**The agent version** — the release number of…" | pre-release | flows |  |
| 87 | "Not yours, and your manifest never mentions it." | pre-release | flows |  |
| 88 | "**Your extension's `version`** — your package's semver." | pre-release | flows |  |
| 89 | "Rev it as often as your research loop…" | pre-release | flows |  |
| 90 | "It changes nothing about loading." | pre-release | flows |  |
| 91 | "It rides along in the startup report, in…" | pre-release | flows |  |
| 92 | "**`api_version`** — the version of the manifest contract…" | pre-release | flows |  |
| 93 | "It is 1, and it is designed to…" | pre-release | flows |  |
| 94 | "The loader's rule:" | pre-release | flows |  |
| 95 | "`api_version` equal to the agent's extension API version:…" | pre-release | flows |  |
| 96 | "`api_version` **newer** than the agent provides: refused, with…" | pre-release | flows |  |
| 97 | "`api_version` **older**: accepted for a sense." | pre-release | flows |  |
| 98 | "The transport loader is strict: anything other than…" | pre-release | flows |  |
| 99 | "The third line is a promise about how…" | pre-release | flows |  |
| 100 | "The intent is that you write `api_version: 1`…" | pre-release | flows |  |
| 101 | "The `signals` list is not documentation garnish." | pre-release | flows |  |
| 102 | "It is the context the Oracle receives about…" | pre-release | flows |  |
| 103 | "Your alerts name a signal in the alert's…" | pre-release | flows |  |
| 104 | "If the signal is declared, the alert is…" | pre-release | flows |  |
| 105 | "If the signal is **not declared** — or…" | pre-release | flows |  |
| 106 | "Nothing is stored, nothing is passed through quietly." | pre-release | flows |  |
| 107 | "Every `senses` answer that touches your sense carries…" | pre-release | flows |  |
| 108 | "Why this strict: the Oracle is a model…" | pre-release | flows |  |
| 109 | "A signal it has never seen defined is…" | pre-release | flows |  |
| 110 | "Declaring the signal set up front means every…" | pre-release | flows |  |
| 111 | "Senses that are not backed by an extension…" | pre-release | flows |  |
| 112 | "The declared-signal gate applies to extension-backed senses, because…" | pre-release | flows |  |
| 113 | "An extension does not get a new trust…" | pre-release | flows |  |
| 114 | "It files alerts through the senses path, bound…" | pre-release | flows |  |
| 115 | "The binding rule is the senses rule: the…" | pre-release | flows |  |
| 116 | "Weights, severity floors, cooldowns, and hourly caps tune…" | pre-release | flows |  |
| 117 | "Everything above describes the envelope and the contract." | pre-release | flows |  |
| 118 | "How the envelope travels is a separate choice,…" | pre-release | flows |  |
| 119 | "The default path is the mail path: your…" | pre-release | flows |  |
| 120 | "That path works from any machine and needs…" | pre-release | flows |  |
| 121 | "When your daemon runs on the **same machine**…" | pre-release | flows |  |
| 122 | "Both carry the identical envelope — same fields,…" | pre-release | flows |  |
| 123 | "A transport is replaceable plumbing under the contract,…" | pre-release | flows |  |
| 124 | "The envelope carries its `api_version` for exactly this…" | pre-release | flows |  |
| 125 | "**Periodic style — file drop.** Your producer writes…" | pre-release | flows |  |
| 126 | "A watcher in the runner scans the inbox…" | pre-release | flows |  |
| 127 | "This style serves producers that already work in…" | pre-release | flows |  |
| 128 | "The producer helper writes the file atomically under…" | pre-release | flows |  |
| 129 | "**Direct style — socket push.** Your producer opens…" | pre-release | flows |  |
| 130 | "One envelope per connection, size-capped, read with a…" | pre-release | flows |  |
| 131 | "This style serves extensions with their own event…" | pre-release | flows |  |
| 132 | "The listener binds loopback only — it is…" | pre-release | flows |  |
| 133 | "The producer helpers live in `runner/ops/extensions.py`: `build_sensor_alert(...)` composes…" | pre-release | flows |  |
| 134 | "The Lab Results example drives both styles: run…" | pre-release | flows |  |
| 135 | "Config keys (all read at startup):" | pre-release | flows |  |
| 136 | "| Key | Default | Meaning |" | pre-release | flagged | A table header row — structure, not a sentence |
| 137 | "|-----|---------|---------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 138 | "| `local_signals` | `true` | Master switch for…" | pre-release | flows |  |
| 139 | "`false` starts neither. |" | pre-release | flows |  |
| 140 | "| `local_signal_port` | `39271` | Loopback port for…" | pre-release | flows |  |
| 141 | "`0` or `false` turns the listener off; the…" | pre-release | flows |  |
| 142 | "| `local_wake_cooldown_sec` | `900` | Minimum seconds between…" | pre-release | flows |  |
| 143 | "Local delivery changes latency, not trust." | pre-release | flows |  |
| 144 | "A bad signature is a rejection exactly as…" | pre-release | flows |  |
| 145 | "What local delivery removes is the mailbox, not…" | pre-release | flows |  |
| 146 | "A locally filed alert does one thing a…" | pre-release | flows |  |
| 147 | "The gate is deterministic — no model judgment…" | pre-release | flows |  |
| 148 | "the alert's severity is `high` or `critical`," | pre-release | flows |  |
| 149 | "no other briefing is currently in flight, and" | pre-release | flows |  |
| 150 | "this sensor + signal pair has not woken…" | pre-release | flows |  |
| 151 | "When the gate fires, a briefing thread asks…" | pre-release | flows |  |
| 152 | "The assessment is appended to `oracle-briefs.jsonl` in the…" | pre-release | flows |  |
| 153 | "If no local model is configured, the brief…" | pre-release | flows |  |
| 154 | "The briefing never blocks ingest, and a sense…" | pre-release | flows |  |
| 155 | "Nothing signs an extension's code." | pre-release | flows |  |
| 156 | "Until something does, the manifest is your statement…" | pre-release | flows |  |
| 157 | "The review is deterministic, needs no model, and…" | pre-release | flows |  |
| 158 | "What it finds, by weight:" | pre-release | flows |  |
| 159 | "**High** — refused under `enforce`: a `.py` file…" | pre-release | flows |  |
| 160 | "**Warn** — logged, never refused: a signal filed…" | pre-release | flows |  |
| 161 | "**Note** — in the report only: a declared…" | pre-release | flows |  |
| 162 | "Capability detection reads imports from the parsed source…" | pre-release | flows |  |
| 163 | "Filing through the shipped helper (`runner.ops.extensions.send_local_signal`, loopback only)…" | pre-release | flows |  |
| 164 | "Shell files count for `network` when they call…" | pre-release | flows |  |
| 165 | "Non-code files (`README.md`, data) are not scanned for…" | pre-release | flows |  |
| 166 | "The posture is one key in `config.json`:" | pre-release | flows |  |
| 167 | "`enforce` (the default) refuses an extension with a…" | pre-release | flows |  |
| 168 | "`advisory` loads everything and logs what it found." | pre-release | flows |  |
| 169 | "`off` skips the review." | pre-release | flows |  |
| 170 | "A value outside those three is a config…" | pre-release | flows |  |
| 171 | "Every verdict is written to `<base_dir>/extension-review.json` (mode, time,…" | pre-release | flows |  |
| 172 | "When your own extension is refused, the log…" | pre-release | flows |  |
| 173 | "The shipped extensions all declare what they use…" | pre-release | flows |  |
| 174 | "Extensions fail closed and fail quiet:" | pre-release | flows |  |
| 175 | "At startup the agent logs one line per…" | pre-release | flows |  |
| 176 | "A refused extension changes nothing else: the agent…" | pre-release | flows |  |
| 177 | "A folder whose manifest is missing, unreadable, malformed…" | pre-release | flows |  |
| 178 | "If an extension is refused, its sensor name…" | pre-release | flows |  |
| 179 | "The startup report is where you learn that…" | pre-release | flows |  |
| 180 | "This section applies to both kinds, `sense` and…" | pre-release | flows |  |
| 181 | "An extension names its upstream once, in the…" | pre-release | flows |  |
| 182 | "`sources.json` (here) names what else the box should…" | pre-release | flows |  |
| 183 | "An entry that says `"upstream": true` draws on…" | pre-release | flows |  |
| 184 | "The Oracle reasons better about a signal, a…" | pre-release | flows |  |
| 185 | "So on a box where a local model…" | pre-release | flows |  |
| 186 | "**Its installed code.** Your extension folder as installed,…" | pre-release | flows |  |
| 187 | "A folder inside the state dir (the default…" | pre-release | flows |  |
| 188 | "A folder outside it is copied into the…" | pre-release | flows |  |
| 189 | "**What your `sources.json` declares.** An optional file next…" | pre-release | flows |  |
| 190 | "A daemon that runs on another machine (the…" | pre-release | flows |  |
| 191 | "Declare a `self` entry pointing at the published…" | pre-release | flows |  |
| 192 | "Nothing fetched ships." | pre-release | flows |  |
| 193 | "A release carries the declarations (a few kilobytes);…" | pre-release | flows |  |
| 194 | "A second run fetches nothing: an entry is…" | pre-release | flows |  |
| 195 | "The manifest is untouched — `sources.json` is a…" | pre-release | flows |  |
| 196 | "| Field | Rules |" | pre-release | flagged | A table header row — structure, not a sentence |
| 197 | "|-------|-------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 198 | "| `sources_version` | Required; `1`." | pre-release | flows |  |
| 199 | "Newer than the agent reads: refused." | pre-release | flows |  |
| 200 | "Older: accepted." | pre-release | flows |  |
| 201 | "The manifest's promise, kept the same way. |" | pre-release | flows |  |
| 202 | "| `oracle` | Optional, top level: `"provide"` or…" | pre-release | flows |  |
| 203 | "| `sources` | Up to 16 entries. |" | pre-release | flows |  |
| 204 | "| `id` | Required." | pre-release | flows |  |
| 205 | "Letters, digits, `.`, `_`, `-`; unique without regard…" | pre-release | flows |  |
| 206 | "| `role` | Required: `self`, `upstream`, `spec`, `schema`,…" | pre-release | flows |  |
| 207 | "Context for the Oracle. |" | pre-release | flows |  |
| 208 | "| `description`, `license` | Optional, one line each…" | pre-release | flows |  |
| 209 | "| `github` / `url` / `project` / `upstream`…" | pre-release | flows |  |
| 210 | "| `ref` | GitHub only." | pre-release | flows |  |
| 211 | "`"latest"` (the default, below), or a tag, a…" | pre-release | flows |  |
| 212 | "| `tag_match`, `asset_match` | `"latest"` only." | pre-release | flows |  |
| 213 | "A regular expression the release tag must match;…" | pre-release | flows |  |
| 214 | "| `files` | GitHub only." | pre-release | flows |  |
| 215 | "Up to 32 repository paths, each fetched alone…" | pre-release | flows |  |
| 216 | "| `archive` | GitHub or URL: fetch the…" | pre-release | flows |  |
| 217 | "A GitHub entry asks for its archive, its…" | pre-release | flows |  |
| 218 | "| `max_mb` | Default 64, at most 512:…" | pre-release | flows |  |
| 219 | "| `oracle` | Optional, per entry: `"provide"` or…" | pre-release | flows |  |
| 220 | "Validation is the manifest's: unknown fields are refused…" | pre-release | flows |  |
| 221 | "A refused declaration does not refuse the extension…" | pre-release | flows |  |
| 222 | "**"latest"** is the highest-versioned release that is not…" | pre-release | flows |  |
| 223 | "Highest version, not newest: a project that patches…" | pre-release | flows |  |
| 224 | "The release this picks can differ from the…" | pre-release | flows |  |
| 225 | ""latest" is resolved when Homing Pigeon is built." | pre-release | flows |  |
| 226 | "The release job runs `runner/tools/pin_extension_sources.py`: every declared upstream…" | pre-release | flows |  |
| 227 | "A box fetches exactly what its build pinned…" | pre-release | flows |  |
| 228 | "A pin vouches for bytes only: every URL…" | pre-release | flows |  |
| 229 | "An extension author pins the same way and…" | pre-release | flows |  |
| 230 | "The extension's own `sources.lock.json` is consulted first, then…" | pre-release | flows |  |
| 231 | "With no pin — a source checkout, a…" | pre-release | flows |  |
| 232 | "Only then does the box resolve the declaration…" | pre-release | flows |  |
| 233 | "The rule is the same one the `ask`…" | pre-release | flows |  |
| 234 | "Fetched material is data." | pre-release | flows |  |
| 235 | "Nothing fetched is ever executed or imported." | pre-release | flows |  |
| 236 | "Every request is https, redirects included; the GitHub…" | pre-release | flows |  |
| 237 | "Archives unpack as plain files only — no…" | pre-release | flows |  |
| 238 | "Small things go first for every extension (single…" | pre-release | flows |  |
| 239 | "An offline box records each failure and retries…" | pre-release | flows |  |
| 240 | "Nothing here blocks the agent or the extension." | pre-release | flows |  |
| 241 | "Every piece an extension brings is either **provided**…" | pre-release | flows |  |
| 242 | "For one piece, the first of these that…" | pre-release | flows |  |
| 243 | "the owner, for this extension: `extension_sources.extensions.<name>.oracle` in `config.json`;" | pre-release | flows |  |
| 244 | "the owner, for every extension: `extension_sources.oracle` — only…" | pre-release | flows |  |
| 245 | "the author, for this entry: the entry's `oracle`…" | pre-release | flows |  |
| 246 | "the author, for the extension: the top-level `oracle`;" | pre-release | flows |  |
| 247 | "otherwise: provide." | pre-release | flows |  |
| 248 | "Provided material is listed in `extension-sources/INDEX.md`, named in…" | pre-release | flows |  |
| 249 | "Withheld material is never listed or named, and…" | pre-release | flows |  |
| 250 | "The Oracle's `run` tool is a shell on…" | pre-release | flows |  |
| 251 | "A malformed `extension_sources` setting fails closed: nothing is…" | pre-release | flows |  |
| 252 | "The Oracle is local by construction — the…" | pre-release | flows |  |
| 253 | "Nothing here sends source anywhere." | pre-release | flows |  |
| 254 | "`extension_sources` in `config.json`, read live (an edit runs…" | pre-release | flows |  |
| 255 | "| Value | Meaning |" | pre-release | flagged | A table header row — structure, not a sentence |
| 256 | "|-------|---------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 257 | "| `"auto"` (default) | Fetch only when a…" | pre-release | flows |  |
| 258 | "A deterministic box has nothing that reads the…" | pre-release | flows |  |
| 259 | "| `true` | Fetch on every box." | pre-release | flows |  |
| 260 | "A Pi Light box with no model fetches…" | pre-release | flows |  |
| 261 | "| `false` | Never fetch. |" | pre-release | flows |  |
| 262 | "| an object | `{"fetch": "auto" / true…" | pre-release | flows |  |
| 263 | "An entry's status in `SOURCES.json` and the index…" | pre-release | flows |  |
| 264 | "`homing-pigeon --inspect sources` prints the recorded state, with…" | pre-release | flows |  |
| 265 | "`homing-pigeon --fetch-sources` runs a pass in the foreground…" | pre-release | flows |  |
| 266 | "Asking counts as wanting it: even `"auto"` fetches…" | pre-release | flows |  |
| 267 | "To refetch one entry, delete its folder." | pre-release | flows |  |
| 268 | "A box with no way out can be…" | pre-release | flows |  |
| 269 | "The eight IDS adapters declare their upstream project:…" | pre-release | flows |  |
| 270 | "All five shipped transports declare their own code…" | pre-release | flows |  |
| 271 | "Any extension can do the same with one…" | pre-release | flows |  |
| 272 | "Starting from a clone of this repository:" | pre-release | flows |  |
| 273 | "Copy the example: `cp -r runner/extensions/lab-results <base_dir>/extensions/my-sense` (any…" | pre-release | flows |  |
| 274 | "Edit `extension.json`: set `name` to your sensor name,…" | pre-release | flows |  |
| 275 | "Add the sensor, key policy, and secret entries…" | pre-release | flows |  |
| 276 | "Pick a fresh key id; do not share…" | pre-release | flows |  |
| 277 | "Start the agent and read the startup report:…" | pre-release | flows |  |
| 278 | "Write your daemon next to the manifest: any…" | pre-release | flows |  |
| 279 | "The example's `lab_results.py` is a complete, readable instance…" | pre-release | flows |  |
| 280 | "Watch it land: send a `senses` query for…" | pre-release | flows |  |
| 281 | "Your alerts come back with `signal`, `signal_description`, and…" | pre-release | flows |  |
| 282 | "Testing: the contract this document states is the…" | pre-release | flows |  |
| 283 | "Run it while you develop:" | pre-release | flows |  |
| 284 | "The agent's `--dry-run` flag also describes incoming alerts…" | pre-release | flows |  |
| 285 | "`runner/extensions/lab-results/` is a working sense for people who…" | pre-release | flows |  |
| 286 | "Training and evaluation harnesses drop result files; Lab…" | pre-release | flows |  |
| 287 | "`extension.json` — the manifest." | pre-release | flows |  |
| 288 | "Name `lab_results`, three declared signals, tunables: `watch_dir`, `metric`,…" | pre-release | flows |  |
| 289 | "`lab_results.py` — the watcher daemon." | pre-release | flows |  |
| 290 | "One pass scans the results folder, diffs it…" | pre-release | flows |  |
| 291 | "Signing and delivery are the standard senses flow…" | pre-release | flows |  |
| 292 | "`README.md` — the short version, with the result-file…" | pre-release | flows |  |
| 293 | "A result file is one JSON object per…" | pre-release | flows |  |
| 294 | "The declared signals:" | pre-release | flows |  |
| 295 | "| Signal | Fires when | Severity |" | pre-release | flagged | A table header row — structure, not a sentence |
| 296 | "|--------|------------|----------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 297 | "| `experiment_finished` | A run's file reaches `"status":…" | pre-release | flows |  |
| 298 | "| `metric_threshold_crossed` | A finished run's `metric` value…" | pre-release | flows |  |
| 299 | "| `result_anomaly` | A finished run's `metric` value…" | pre-release | flows |  |
| 300 | "Diffing rules: files are compared by content." | pre-release | flows |  |
| 301 | "A file that does not parse yet (a…" | pre-release | flows |  |
| 302 | "Editing a finished result re-reports it: the content…" | pre-release | flows |  |
| 303 | "State lives in `.lab-results-state.json` inside the results folder;…" | pre-release | flows |  |
| 304 | "`runner/extensions/pi-health/` is a working sense for the health…" | pre-release | flows |  |
| 305 | "The watcher reads the machine's vitals and files…" | pre-release | flows |  |
| 306 | "Run it on a Pi Light install and…" | pre-release | flows |  |
| 307 | "`extension.json` — the manifest." | pre-release | flows |  |
| 308 | "Name `pi_health`, four declared signals, tunables: `temp_high_c`, `disk_high_pct`,…" | pre-release | flows |  |
| 309 | "`pi_health.py` — the watcher daemon." | pre-release | flows |  |
| 310 | "`read_board()` is the only function that touches the…" | pre-release | flows |  |
| 311 | "Every source is optional and capability-based — a…" | pre-release | flows |  |
| 312 | "Temperature comes from the Linux thermal sysfs, preferring…" | pre-release | flows |  |
| 313 | "`--readings FILE` feeds a readings dict from JSON…" | pre-release | flows |  |
| 314 | "`README.md` — the short version, with the readings…" | pre-release | flows |  |
| 315 | "The declared signals:" | pre-release | flows |  |
| 316 | "| Signal | Fires when | Severity |" | pre-release | flagged | A table header row — structure, not a sentence |
| 317 | "|--------|------------|----------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 318 | "| `board_overheating` | CPU/SoC temperature reaches `temp_high_c` (default…" | pre-release | flows |  |
| 319 | "| `undervoltage_detected` | The Pi firmware throttled bitmask…" | pre-release | flows |  |
| 320 | "| `disk_pressure` | The `disk_mount` mount reaches `disk_high_pct`…" | pre-release | flows |  |
| 321 | "| `memory_pressure` | Available memory falls to `mem_avail_low_pct`…" | pre-release | flows |  |
| 322 | "The two high signals are the point of…" | pre-release | flows |  |
| 323 | "`runner/extensions/airwaves/` is the Pi's wireless neighborhood watch, and…" | pre-release | flows |  |
| 324 | "The watcher reads the scan results the platform…" | pre-release | flows |  |
| 325 | "It is a read-only consumer: it never associates…" | pre-release | flows |  |
| 326 | "`extension.json` — the manifest." | pre-release | flows |  |
| 327 | "Name `airwaves`, four declared signals, tunables: `poll_interval_sec`, `gone_after_scans`,…" | pre-release | flows |  |
| 328 | "`airwaves.py` — the watcher." | pre-release | flows |  |
| 329 | "`read_live()` is the only function that touches the…" | pre-release | flows |  |
| 330 | "`--readings FILE` feeds a scan from JSON instead." | pre-release | flows |  |
| 331 | "`README.md` — the short version, including why BLE…" | pre-release | flows |  |
| 332 | "The declared signals:" | pre-release | flows |  |
| 333 | "| Signal | Fires when | Severity |" | pre-release | flagged | A table header row — structure, not a sentence |
| 334 | "|--------|------------|----------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 335 | "| `new_access_point` | A BSSID never seen before…" | pre-release | flows |  |
| 336 | "| `evil_twin_suspect` | A known SSID appears from…" | pre-release | flows |  |
| 337 | "| `access_point_gone` | A long-known AP is missing…" | pre-release | flows |  |
| 338 | "| `link_degraded` | The box's own link signal…" | pre-release | flows |  |
| 339 | "The evil-twin signal is the point of the…" | pre-release | flows |  |
| 340 | "On a Pi Light install the high signal…" | pre-release | flows |  |
| 341 | "`runner/extensions/sky-watcher/` is a working sense for people who…" | pre-release | flows |  |
| 342 | "It polls the International Space Station's position from…" | pre-release | flows |  |
| 343 | "`extension.json` — the manifest." | pre-release | flows |  |
| 344 | "Name `sky_watcher`, three declared signals, tunables: `observer_lat`, `observer_lon`…" | pre-release | flows |  |
| 345 | "`sky_watcher.py` — the producer." | pre-release | flows |  |
| 346 | "One invocation takes one position sample; a one-minute…" | pre-release | flows |  |
| 347 | "`fetch_position()` is the only network code; the pass…" | pre-release | flows |  |
| 348 | "`README.md` — the short version, with the cron…" | pre-release | flows |  |
| 349 | "The declared signals:" | pre-release | flows |  |
| 350 | "| Signal | Fires when | Severity |" | pre-release | flagged | A table header row — structure, not a sentence |
| 351 | "|--------|------------|----------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 352 | "| `station_approaching` | The station enters the approach…" | pre-release | flows |  |
| 353 | "| `visible_pass_starting` | A sunlit pass over a…" | pre-release | flows |  |
| 354 | "| `bright_pass` | That pass culminates at or…" | pre-release | flows |  |
| 355 | "How a pass is read, in brief." | pre-release | flagged | A label standing alone ("How a pass is read, in brief."); the reading it heads arrives in the next units without a hand-off |
| 356 | "The central angle between the observer and the…" | pre-release | flows |  |
| 357 | "The station being sunlit is the feed's own…" | pre-release | flows |  |
| 358 | "A pass walks out → approaching → visible…" | pre-release | flows |  |
| 359 | "A feed outage is a quiet no-op: nothing…" | pre-release | flows |  |
| 360 | "(The sample output is a replayed zenith pass…" | pre-release | flows |  |
| 361 | "Twenty-eight extension folders ship in all; this catalog…" | pre-release | flows |  |
| 362 | "`lab-results`, `pi-health`, and `sky-watcher` are standalone examples outside…" | pre-release | flows |  |
| 363 | "Sixteen more working senses (the table has seventeen…" | pre-release | flows |  |
| 364 | "Thirteen watch what a trade watches: fuzzing, PKI,…" | pre-release | flows |  |
| 365 | "Powerful-desktop senses are the center of gravity; every…" | pre-release | flows |  |
| 366 | "`poll_interval_sec` there is the one advisory knob: it…" | pre-release | flows |  |
| 367 | "Eight more adapters follow the same producer shape…" | pre-release | flows |  |
| 368 | "Each feed's README carries its collector's measured footprint;…" | pre-release | flows |  |
| 369 | "| Extension | Watches | Light mode, in…" | pre-release | flagged | A table header row — structure, not a sentence |
| 370 | "|-----------|---------|-------------------------|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 371 | "| `crash-watch` | Crash/core dump folders: a new…" | pre-release | flows |  |
| 372 | "| `release-drop` | A drop folder: each artifact…" | pre-release | flows |  |
| 373 | "| `cert-sentinel` | Certificate files and TLS endpoints:…" | pre-release | flows |  |
| 374 | "| `wire-arrivals` | The ARP/neighbor table: a MAC…" | pre-release | flows |  |
| 375 | "| `latency-post` | Gateway and target latency by…" | pre-release | flows |  |
| 376 | "| `port-watch` | Listening sockets: a new listener…" | pre-release | flows |  |
| 377 | "| `failed-login-watch` | Auth logs: a failure burst…" | pre-release | flows |  |
| 378 | "| `tripwire` | A file tree's SHA-384 baseline:…" | pre-release | flows |  |
| 379 | "| `log-sentinel` | Kernel/system log tails: OOM, panic,…" | pre-release | flows |  |
| 380 | "| `service-watch` | Named processes: an expected one…" | pre-release | flows |  |
| 381 | "| `backup-freshness` | A backup folder's newest artifact:…" | pre-release | flows |  |
| 382 | "| `usb-arrivals` | USB/serial device arrivals: a new…" | pre-release | flows |  |
| 383 | "| `airwaves` | The Pi's wireless neighborhood (full…" | pre-release | flows |  |
| 384 | "| `resource-sentinel` | The machine's counters, judged as…" | pre-release | flows |  |
| 385 | "| `job-watcher` | The runner's retained job history:…" | pre-release | flows |  |
| 386 | "| `training-watch` | An ML training run: its…" | pre-release | flows |  |
| 387 | "| `job-fuzz` | The runner's retained jobs, fuzzed:…" | pre-release | flows |  |
| 388 | "| `falco-feed` | Falco's JSON alert file: Emergency/Alert/Critical/Error…" | pre-release | flows |  |
| 389 | "No footprint claimed for Falco itself: it did…" | pre-release | flows |  |
| 390 | "| `suricata-feed` | Suricata's eve.json: alert signatures at…" | pre-release | flows |  |
| 391 | "| `zeek-feed` | Zeek's conn.log and dns.log: a…" | pre-release | flows |  |
| 392 | "| `osquery-feed` | osqueryd's results log for the…" | pre-release | flows |  |
| 393 | "| `sysmon-feed` | Sysmon process-create events, Linux syslog…" | pre-release | flows |  |
| 394 | "No footprint claimed: Sysmon for Linux did not…" | pre-release | flows |  |
| 395 | "| `aide-feed` | AIDE check reports: entries changed…" | pre-release | flows |  |
| 396 | "No daemon: 0 MB between scans, ~21 MB…" | pre-release | flows |  |
| 397 | "| `softflowd-feed` | NetFlow/IPFIX from softflowd — softflowd…" | pre-release | flows |  |
| 398 | "| `wazuh-feed` | A Wazuh `alerts.json` where one…" | pre-release | flows |  |
| 399 | "A missing file is a quiet no-op, forever…" | pre-release | flows |  |
| 400 | "Two honest limits, stated once for the whole…" | pre-release | flows |  |
| 401 | "Tripwire over a huge tree cannot be made…" | pre-release | flows |  |
| 402 | "And log-sentinel cannot watch less than the tail…" | pre-release | flows |  |
