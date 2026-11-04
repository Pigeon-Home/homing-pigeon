# Extension review — design

*Built. `runner/guard/extreview.py`; the owner's guide is
docs/extend/extensions.md, "The review: code held to the manifest".
This note records why it has the shape it has.*

Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f

## The problem

An extension is a folder of code the owner dropped in, with a
manifest that says what it is. The runner trusted the manifest and
never looked at the code: a sense's declared signal list gated
ingest, and a transport's `entry` was launched with a runtime config
that can carry the mailbox password (email) or the PSK material
(dtls). Nothing signed the code. A folder could declare three
signals and open a socket to anywhere; a drop-in named `email` could
shadow the shipped transport and be handed the mailbox.

Signing extension code is the eventual answer and it is not this
change: a signature says who made the folder, not what the folder
does, and there is no publisher to sign the owner's own
experiments, which are the point of extensions. What could ship now
is the thing a signature does not give: a check that the code does
what the manifest says.

## The shape

**The manifest states, the review checks.** A new optional manifest
field `capabilities` is the author's statement of what the code does
beyond reading files and filing signals, from a closed vocabulary:
`network`, `listen`, `subprocess`, `native`. The review reads every
code file and holds it to the statement. The vocabulary is small on
purpose: four words an owner can read at a glance in a startup line
(`capabilities: network`), not a permission system.

**Deterministic, stdlib, no model.** The Oracle's model-side reading
of extension code already exists (the sources pass,
`runner/ops/extsources.py`) and runs in the background when a local
model is configured. The gate before load cannot wait for a model
and must give the same answer on every box, a Pi Light included. So
the review is a parser and a few regular expressions: imports from
the AST (exact), call shapes from the text (`.bind(`, `os.system(`,
`urlopen(`; generous, because a false positive costs the author one
word in the manifest and a miss costs the owner).

**Findings carry weight, and only the heavy ones refuse.** `high`
is what a manifest cannot explain away: code that does not compile,
a symlink inside the folder, a file too large or not UTF-8 to read,
a bidi or zero-width control character (Trojan Source), an
undeclared capability, a reference to the runner's own state files
(`seen.json`, `board.json`, the security events; in a sense, also
the mailbox password and key material, which the runner never hands
a sense -- a transport may legitimately name what it is handed), a
transport `entry` that steps outside its folder. `warn` is worth a
line and never a refusal: a signal filed and not declared (ingest
refuses it anyway), `exec`/`eval` at run time, a drop-in shadowing a
shipped transport. `note` is for the report: a declared signal never
filed, a declared capability never used, an entry whose program is
an interpreter outside the folder.

**Enforce by default.** `extension_review` is `enforce` unless the
owner says otherwise. The alternatives were weighed: `advisory` by
default would have left the gate open on every install that never
reads its log, and a "missing `capabilities` is a note, present and
wrong is high" rule would have let a hostile folder pass by omitting
the field. The cost of `enforce` is that an owner's working sense
that imports `subprocess` is refused after this upgrade until its
manifest says `"capabilities": ["subprocess"]`. The refusal line
names the file and the exact line to add, the security event records
it, and `advisory` is one config word away. The shipped extensions
all declare what they use; `runner/tests/test_extreview.py` holds
them to it.

**Refuse like the loader.** A refused extension is absent from the
registry and its refusal rides in the loader's own `problems` list,
so every caller that already handled a bad manifest handles this
without new code: the startup report prints it, the supervisor logs
it, the sense's name is a plain sense as far as ingest is concerned.
A refused drop-in transport is not silently replaced by the shipped
transport it shadowed: the owner installed the drop-in, and running
a different pipe than the one picked is the wrong surprise. The
refusal and the "no loadable transport extension" line together say
what happened.

**Shadowing stays legal and gets loud.** The documented behavior --
a same-named folder in the owner's extensions directory runs instead
of the shipped transport -- is kept, because private forks of a
shipped transport are first-class. It is now a `warn` finding and a
security event at every start.

**Read once per change.** `_extension_registry` runs on every sensor
alert. The review caches per folder on a fingerprint of every path's
size and mtime, so the alert path pays for a directory listing and
the folder is re-read only when a file in it changed; log lines come
out once, the first time a folder is reviewed.

**One report, two kinds.** Both loaders write their verdicts into
`<base_dir>/extension-review.json` (`senses` and `transports`
merged under one `mode` and `reviewed_at`), written only when the
verdicts changed. `--inspect review` drops the cache, reads the
folders now, and prints the same structure plus the problems.

## What it does not do

- It does not read what a program does at run time. A transport that
  declares `network` may connect anywhere; the review says it
  connects, not where. Egress policy is the sandbox's business.
- It does not prove provenance. A folder written by an attacker who
  can write to the owner's extensions directory passes if its
  manifest tells the truth about it. That is the signature's job,
  and the identity fields (`name`, `publisher`, `version`) are
  carried so a future lockdown has something to pin.
- It does not scan non-code files for capabilities (a README that
  says `import subprocess` is prose), and it does not count filing
  through the shipped loopback helper as `network`: that is the
  sense contract itself.

## Upgrade path

The capability vocabulary is extensible without an API bump: a new
word is a new optional value, and a manifest that does not use it is
unchanged. If a signature scheme lands, the review stays as the check
that the signed statement is true of the signed code.
