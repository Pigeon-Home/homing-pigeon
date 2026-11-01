# Constraint inventory

Every constraint below was read from the code at commit
`6d6288c5` (release 3.15.28), the commit the `testing` branch was
cut from. No value here was taken from another document or assumed
from memory. Where another document states a different value, the
code is the authority and the difference is noted in place.

Each entry names four things: the constraint, its exact value or
default, the file and function where the code declares it, and its
class under Decision 1.

## How the Decision 1 class is recorded

Decision 1 (`docs/design/present-but-invalid-config.md`) splits a
present-but-unusable configuration value by what a wrong value
changes:

- **Refuse class.** The runner MUST refuse to start and MUST name
  the setting, when a wrong value changes who can reach the box,
  what it will execute, or what it protects. Ports and bind
  addresses, key policies, the thresholds that page a human,
  secrets and their floors, and security modes are in this class.
- **Default class.** Every other present-but-unusable setting
  reads as its documented default, and the fallback is named in
  the startup warning and in the full-tier platform card. Live
  reload reads a bad value as the default and names it; a
  refuse-class change takes effect only at the next start.
- **Not a configuration setting.** Some constraints are constants
  or per-process state with no configuration key at all. Those are
  marked as such: there is no present-but-unusable value to
  classify, and changing them means changing code or a command
  line, both of which are visible acts.

Two layers in the code are easy to confuse, so they are recorded
separately wherever both exist. A runtime reader often falls back
to a default when it meets an unusable value, defensively, so the
poll loop cannot be crashed by one bad read. The startup validator
runs first and is the layer that enforces the class: for a
refuse-class setting it stops the runner before any job is read.

## C1. Maximum job size — `max_job_bytes`

- **Constraint:** a raw protocol mail that is marked as this
  project's mail MUST be refused before any signature work when
  its length exceeds the cap. A cap of 0 means unlimited.
- **Value:** default `4194304` bytes (4 MiB).
- **Where:** `runner/ops/mail.py`, `handle_mail`, line 64 —
  `int(cfg.get("max_job_bytes", 4194304))`, with the same value as
  the fallback at line 66 when the conversion fails. The check
  itself is at lines 67 to 70, and it applies only when the
  subject carries the `[HOMING-PIGEON]` marker; unmarked mail is
  not a job message and is left to the dispatcher.
- **Class:** refuse class at startup, with a defensive default at
  runtime. `runner/runner.py`, `_validate_size_caps`, line 4707,
  requires the value, when present, to be a non-negative integer —
  a boolean, a string, or a negative value returns a
  configuration error — and `runner/ops/main.py`, `main`, line
  127, prints that error and returns exit code 2 before the runner
  starts. The registry in `runner/tests/defaults_registry.py`
  records the same row with policy `refuse`, default `4194304`.

## C2. Maximum script size — `max_script_bytes`

- **Constraint:** a script inside a signed job body MUST be
  refused when its UTF-8 encoded length exceeds the cap. The
  check runs after the signature verifies, because the script
  lives inside the signed body. A cap of 0 means unlimited.
- **Value:** default `1048576` bytes (1 MiB).
- **Where:** `runner/ops/mail.py`, `handle_mail`, line 147 —
  `int(cfg.get("max_script_bytes", 1048576))`, fallback at line
  149, check at lines 151 to 154 measuring
  `len(script.encode("utf-8"))`.
- **Class:** refuse class at startup, on the same terms as C1:
  the same `_validate_size_caps` validator covers this key, and
  the registry row records policy `refuse`, default `1048576`.
- **Measure note:** the production cap measures UTF-8 **bytes**.
  The proof work measures **characters** for its own starting
  bound (scripts under 50 characters; see `README.md`). The two
  measures are different things and are never interchanged in
  these files: a 49-character script of multi-byte characters is
  inside the proof bound and can still be many more than 49 bytes,
  though it remains far inside this 1 MiB cap.
- **Script size in practice:** a typical script a cloud SI sends
  is on the order of 500 lines; a large one is about 1000 lines.
  Those figures describe what arrives in practice, and they are
  recorded here for scale only — neither is the measure anything
  binds on. The binding measure is the script's character count:
  a one-liner can be extremely long, and obfuscation stuffs
  characters onto few lines, so a line count can be made to say
  almost anything about the same script, while the character
  count says how much script there is. The proof states its
  gate property as a family over that count, P1(B) in
  `properties.md`, and the ladder of bounds it climbs is
  recorded in `GOALS.md`, stage 6.

## C3. Maximum result size — `max_result_bytes`

- **Constraint:** a result body MUST be fitted to the cap before
  it is signed, by cutting the output streams to head and tail
  with a marker naming how much was dropped. The signature always
  covers what is actually sent. A cap of 0 means unlimited.
- **Value:** default `5242880` bytes (5 MiB). The cap is **not**
  unlimited by default.
- **Where:** `runner/runner.py`, line 2025 —
  `MAX_RESULT_BYTES = 5 * 1024 * 1024` — and `_max_result_bytes`,
  line 2028, which returns `MAX_RESULT_BYTES` when the key is
  absent, and also when the value is `None`, a boolean, not an
  integer, or negative. `_fit_result_body`, line 2052, performs
  the fitting.
- **Class:** refuse class at startup, on the same terms as C1:
  `_validate_size_caps` covers this key too, so a present boolean,
  string, or negative value stops startup, even though the
  runtime reader would defensively read such a value as the
  5 MiB default if it ever reached it. The registry row records
  policy `refuse`, default `5242880`.
- **Difference from earlier accounts:** an earlier description of
  this work named the result cap as the one soft spot that
  defaulted to unlimited. The code does not say that. Unlimited
  is reached only by setting the cap to 0 on purpose. The default
  is 5 MiB, and the existing test `runner/tests/test_result_size.py`
  already pins `_max_result_bytes({})` to `5242880`. The soft
  spot, as described before, does not exist at this commit.

## C4. Maximum local envelope size — `_LOCAL_ENVELOPE_MAX_BYTES`

- **Constraint:** a locally delivered envelope (the local-signals
  path, delivered by file or by the loopback socket) MUST be
  refused when its UTF-8 length exceeds the cap, before its
  signature is verified.
- **Value:** `262144` bytes (256 KiB). A constant, not a
  configuration key.
- **Where:** `runner/runner.py`, line 3884 —
  `_LOCAL_ENVELOPE_MAX_BYTES = 262144` — enforced in
  `_ingest_local_envelope_inner` at line 3948, and used by the
  local inbox readers at lines 4172, 4244, and 4255.
- **Class:** not a configuration setting. There is no key to
  present badly; the value changes only with the code.

## C5. The signature — HMAC-SHA-384

- **Constraint:** nothing is executed, answered, or acted on
  before the signature verifies. The signature on a job body MUST
  be HMAC-SHA-384 over the body's exact text, keyed with the
  shared secret the body's key id selects, and the comparison
  MUST be the constant-time `hmac.compare_digest`. A body with no
  signature marker, a malformed signature tail, or a mismatching
  signature MUST be refused. Key selection happens before any MAC
  is computed: an absent `key_id` selects the default secret; a
  present `key_id` MUST be a string naming a secret in the map —
  anything else, including `null`, a boolean, a number, or an
  unknown string, is refused, never silently mapped to the
  default.
- **Value:** hash SHA-384; signature 96 lowercase hex characters
  in the body's `sig` member (comparison lowercases the presented
  signature first, so hex case is not significant).
- **Where:** `runner/wire/verify.py` — `sign_payload`, line 71,
  computes `hmac.new(secret.encode("utf-8"), body.encode("utf-8"),
  hashlib.sha384)`; `verify_body`, line 245, and the keyed path
  `verify_body_keyed`, line 1175, perform the verification with
  `hmac.compare_digest`. `runner/runner.py`,
  `_verify_and_decrypt`, line 4604, is the mail path's entry: it
  verifies the outer body, and for an encrypted envelope it
  decrypts and then verifies the inner body under the same key,
  refusing when the inner key id differs from the outer one.
- **Class:** the signature itself is not a configuration setting.
  The secret behind it is refuse class: see C6.

## C6. The shared secret and its floor

- **Constraint:** a runner MUST refuse to start with no shared
  secret, or with a secret that is a placeholder, a repeating
  pattern, or below the entropy floor. Anyone holding one signed
  message can attack the key offline, so the floor is part of the
  gate, not a nicety.
- **Value:** estimated entropy at least 128 bits, estimated as
  length times log2 of the alphabet size, with patterned secrets
  refused outright regardless of the estimate.
- **Where:** `runner/guard/security.py`,
  `validate_shared_secret`, line 177, re-exported through
  `runner/wire/verify.py`. `build_secrets` in the same verify
  module passes every secret — the default and each additional
  one — through this gate.
- **Class:** refuse class. Secrets and their floors are named in
  Decision 1 itself, and this reader raises `RuntimeError`, which
  startup turns into a refusal to run.

## C7. Key identity — the `k-` fingerprint

- **Constraint:** every secret carries a public name, its
  fingerprint, and a message MAY name its key by that fingerprint
  instead of by a configured name. The fingerprint is a name, not
  a credential: anyone holding the secret can compute it, and
  holding the fingerprint alone authorizes nothing.
- **Value:** `k-` followed by the first 8 hex characters of a
  SHA-384 digest — computed **not** over the secret alone, but
  over a fixed label followed by the secret: the label is
  `homing-pigeon key id v1` plus a newline, as bytes.
- **Where:** `runner/guard/security.py`, line 155 —
  `KEY_ID_LABEL = b"homing-pigeon key id v1\n"` — and
  `key_fingerprint`, line 158, where line 173 computes
  `hashlib.sha384(KEY_ID_LABEL + secret.encode("utf-8"))` and
  returns `"k-" + digest[:8]`.
- **Class:** not a configuration setting; a derived name.
- **Difference from the brief this inventory was built under:**
  the key id was described there as the first 8 hex of SHA-384 of
  the secret. The code prepends the label first, deliberately, so
  nothing else the key derives starts from the same hash. A model
  that fingerprints a bare secret models a different runner.

## C8. Cleartext refused by default

- **Constraint:** a job whose body is the HMAC-only (cleartext)
  form MUST be refused unless the runner process was started with
  the `--allow-cleartext` command-line flag. The flag waives the
  encryption requirement only; the signature in C5 is required
  either way. There is no configuration key for this: a
  configuration file MUST NOT be able to turn cleartext acceptance
  on, and a hot reload MUST NOT be able to change it mid-run.
- **Value:** default refused. The per-process state
  `_ALLOW_CLEARTEXT_JOBS` starts as `False`.
- **Where:** `runner/runner.py`, line 3202 —
  `_ALLOW_CLEARTEXT_JOBS = False` — with `_set_allow_cleartext_jobs`
  at line 3204 and `_cleartext_jobs_allowed` at line 3208, and the
  comment at lines 3195 to 3201 stating the command-line-only
  rule. The only setter call in the startup path is
  `runner/ops/main.py`, line 298, fed from the `--allow-cleartext`
  argument declared in `runner/ops/cli.py`, line 286. The refusal
  itself is in `runner/ops/mail.py`, `handle_mail`, lines 96 to
  130, immediately after verification and decryption and before
  the audience check.
- **Class:** not a configuration setting, by design. That absence
  is the constraint: the decision lives on the command line of
  one process and nowhere else.

## C9. The one AEAD — AES-256-GCM

- **Constraint:** an encrypted job envelope MUST use the one
  declared algorithm. An envelope naming any other algorithm MUST
  be refused, as MUST an envelope whose nonce is not 12 octets or
  whose ciphertext is shorter than its 16-octet tag. No partial
  plaintext escapes a failed decryption. The envelope's signature
  is verified before decryption is attempted, and the recovered
  inner body is verified again (C5), so an encrypted job faces
  every check a cleartext job faces, plus this one.
- **Value:** algorithm string `aes-256-gcm/hkdf-sha384`;
  AES-256-GCM (NIST SP 800-38D); per-job key 32 octets derived by
  HKDF (RFC 5869) over HMAC-SHA-384 from the shared secret, with
  the nonce as salt and the fixed info string
  `homing-pigeon job-encryption v1`; nonce 12 octets, fresh per
  message; tag 16 octets. Additional authenticated data binds the
  envelope to its job id, its key id, and the algorithm string,
  joined by single NUL octets, so an envelope replayed under a
  different subject does not decrypt.
- **Where:** `runner/wire/jobcrypto.py` — the construction is
  stated in the module text at lines 18 to 40; `ALG`, line 50;
  `_NONCE_LEN = 12`, line 52; `_TAG_LEN = 16`, line 53;
  `_KEY_LEN = 32`, line 54; the algorithm, nonce, and tag checks
  are in `decrypt_body`. The DTLS binding reuses the same AEAD in
  its one ciphersuite, TLS_AES_256_GCM_SHA384
  (`runner/wire/dtlsproto.py`, lines 10 to 13).
- **Class:** not a configuration setting. There is no second
  AEAD to select and no configuration key that selects one.
  ChaCha is not present in the construction.

## C10. Audience binding

- **Constraint:** when the audience feature is not `off` and a
  `runner_id` is configured, a job's claimed audience MUST equal
  the configured `runner_id`. The expected value always comes from
  the loaded configuration, never from the signed body. The body
  claims its audience in the `aud` member; the older `runner_id`
  member is also accepted, and when both are present, `aud` wins.
  In `enforce` mode a mismatch MUST be refused; in `audit` mode a
  mismatch is logged and the job proceeds; in `off` mode, or with
  no `runner_id` configured, the check does nothing.
- **Value:** the configured `runner_id` string, an opaque
  identifier generated at setup. It is a deployment value, not a
  protocol constant, so no deployment's actual value is recorded
  here. The default posture in a fresh configuration is the
  feature `off` until a mode is set (C11).
- **Where:** `runner/wire/verify.py` — `check_audience`, line
  1122, states the comparison; `audience_allows`, line 1149,
  applies the three-mode decision through `sec_decide`. The mail
  path calls it in `runner/ops/mail.py`, `handle_mail`, line 132,
  after the cleartext decision and before the script cap.
- **Class:** refuse class, as a security mode: a malformed
  security block, an unknown feature, or a mode outside
  `off | audit | enforce` stops startup (C11). The audience
  decision itself in `enforce` mode refuses the job, not the
  runner.

## C11. The six security modes

- **Constraint:** each of the six hardening features carries a
  mode, and the mode MUST be one of `off`, `audit`, or `enforce`.
  `off` does nothing. `audit` lets the job proceed exactly as
  `off` would and writes what `enforce` would have decided to the
  audit log. `enforce` refuses a violating job through the
  ordinary reject path. A missing security block leaves every
  feature `off`. Changing a mode requires a restart: the
  configuration is read once at startup.
- **Value:** features, in the order the code declares them —
  `policy_env`, `policy_files`, `policy_args`, `audience`,
  `confinement`, `job_user`. Modes — `off`, `audit`, `enforce`.
  Default for every feature: `off`.
- **Where:** `runner/guard/security.py` — `MODES`, line 33;
  `FEATURES`, line 38; `sec_mode`, line 281, which reads a missing
  or malformed value defensively as `off`; `sec_decide`, line
  532, the single decision point; `validate_security_config`,
  line 309, the startup validator.
- **Class:** refuse class. Security modes are named in Decision 1
  itself, and `validate_security_config` raises `RuntimeError` for
  a security block that is not an object, a feature name it does
  not know, or a mode outside the three — called from
  `runner/ops/main.py`, line 83, before any mailbox, model, or job
  work. Two features add their own startup refusals in the same
  class, both in `runner/ops/main.py`: `confinement` on `enforce`
  whose sandbox cannot engage on this platform (its sandbox is
  Linux-only) refuses to start, and `job_user` on `enforce` whose
  demotion mechanism cannot engage (on Windows, where it was once
  a silent no-op) refuses to start.

## C12. Freshness — `max_job_age_sec` and the future bound

- **Constraint:** a job's `issued_at` MUST parse, MUST carry a
  timezone, MUST NOT be older than the age cap, and MUST NOT be
  more than 300 seconds ahead of the runner's clock. A job that
  fails any part is refused once, not retried.
- **Value:** age cap default `3600` seconds; future bound `300`
  seconds, a literal in the check.
- **Where:** `runner/ops/mail.py`, `handle_mail`, lines 163 to
  176 — the cap is read as
  `_confval.integer(cfg.get("max_job_age_sec"), 3600, lo=1)` at
  line 174, and the refusal at line 175 fires when
  `age < -300 or age > max_age`.
- **Class:** default class for the age cap itself — the
  `confval` reader is the Decision 1 default-class reader, and an
  unusable value reads as 3600 and is named. The 300-second bound
  is a code literal, not a setting.

## C13. Protocol version and message type

- **Constraint:** a job's `v` MUST be the JSON integer 1 — the
  check is a type check as well as a value check, so JSON `true`
  and `1.0`, which compare equal to 1, are refused — and its
  `type` MUST be `job`, and the body's `job_id` MUST equal the
  subject's `job_id`.
- **Value:** `PROTOCOL_VERSION = 1`.
- **Where:** `runner/runner.py`, line 281, and `_version_ok`,
  line 283. The checks run in `runner/ops/mail.py`, `handle_mail`,
  lines 156 to 161, after the script cap and before freshness.
- **Class:** not a configuration setting. Protocol version 2 is a
  configuration-gated overlay on version 1 jobs (a separate
  surface, handled in its own dispatch before this path); it does
  not change this value.

## C14. Key policies and script pinning

- **Constraint:** a key with a policy entry may be limited in the
  kinds it can run, the interpreters it can name, the timeout it
  can ask for, and the exact scripts it can run. When
  `allowed_script_sha384` is present, a job from that key MUST
  carry an inline script whose SHA-384 digest is in the list; a
  `script_url` job is never permitted under such a policy, alone
  or beside an inline script. Keys without a policy entry are
  unrestricted unless `key_policies_default_deny` is set, and the
  default (owner) key is always unrestricted.
- **Value:** the upgrade key on a live deployment is the worked
  example of this constraint: its policy pins exactly one
  `allowed_script_sha384` value and execution only, so the key
  that stages an upgrade can run that one staging script and
  nothing else. The digest itself is a deployment value and is
  not recorded here.
- **Where:** `runner/wire/verify.py` — `check_key_policy`, line
  878; the script-pinning branch at lines 963 to 982 computes
  `hashlib.sha384(script.encode("utf-8")).hexdigest()` and
  refuses any digest not in the list. Policy construction
  (`build_key_policies`) validates the list's shape and lowercases
  its entries.
- **Class:** refuse class. Key policies are named in Decision 1
  itself; a malformed policy is a startup configuration error.

## C15. At-most-once execution, at-least-once delivery

- **Constraint:** a verified job MUST be executed at most once
  per runner state directory, and its result MUST be delivered at
  least once. The result is stashed on disk and the job committed
  as seen before the first send is attempted; a failed send is
  retried from the stash and MUST NOT be produced by a second
  run. A redelivered copy of a job whose result is on record is
  answered from the record and not run again.
- **Where:** `runner/ops/mail.py`, `handle_mail` — the claim is
  taken under `_MAIL_LOCK` at line 260: a job id already in the
  seen set or in `_IN_FLIGHT` is skipped at lines 261 to 278; the
  commit-and-deliver path at lines 295 to 318 stashes, commits,
  and only then sends; a cached result is resent without
  execution at lines 320 to 330. The protocol statement is
  PROTOCOL.md sections 5 and 6.
- **Class:** not a configuration setting; an execution semantic.
- **The named windows, recorded plainly:** the guarantee has two
  edges, and a model of it MUST carry both. First, a crash between
  execution and the stash write is a re-execution — the one window
  the code itself names. Second, a sent record ages out with
  `output_retention_days`, and a redelivery after that executes
  again. Inside those edges the guarantee holds; outside them it
  does not claim to.

## C16. Transport credentials as a second gate

- **Constraint:** where a transport has credentials of its own,
  they are a required second gate beside the signature — in front
  of it, not a formality. A deployment that waives a transport's
  own authentication on purpose does not carry the two-gate
  property and MUST NOT claim it.
- **Where:** the pattern is stated where transports are described
  for extenders: `docs/extend/transports.md`, "Authorization
  gates" — a transport's own credentials are "a second, required
  gate in front of the signature." The NATS transport is the
  worked example in code: its broker credentials are required by
  default and the extension refuses to start with none configured;
  `allow_unauthenticated: true` waives the first gate explicitly.
  Email is the honest exception, also stated there: the mailbox
  login authorizes the runner's reading and says nothing about
  any sender, so email stands on the signature alone.
- **Class:** refuse class in the worked example — the NATS
  extension refuses to start without its credentials, which is
  the refuse-class shape applied to a transport's gate.

## C17. The result-policy ceiling — views and query budget

- **Constraint:** a job's `result_policy` may ask for a
  disclosure view and a query budget, and in both cases the
  effective value MUST be the narrower of the job's ask and the
  owner's ceiling (PROTOCOL.md section 9 and section 12,
  non-escalation). A job MUST NOT be able to raise either value
  past the owner's, and the redaction patterns a result is
  scanned with MUST come from the runner — the built-in set plus
  the owner's `redact_patterns_extra` — never from the job: the
  job's own `redact_patterns` member is reserved in the protocol
  and is read nowhere in the runner.
- **Value:** views, ordered narrowest first — `attested` (0),
  `summary` (1), `redacted` (2), `full` (3). A requested view
  that is absent or unrecognised reads as `full`; the ceiling,
  `max_result_view`, defaults to `full` when absent. The
  effective view is the requested view when its order is at most
  the ceiling's, and the ceiling otherwise. Query budget: the
  job's `query_budget` and the owner's `max_query_budget` each
  default to 8 when absent or unusable, and the effective budget
  is the smaller of the two.
- **Where:** `runner/runner.py`, line 445 —
  `VIEW_ORDER = {"attested": 0, "summary": 1, "redacted": 2,
  "full": 3}`. `runner/ops/policy.py`, `apply_result_policy`,
  line 19 — the requested view at line 33, the ceiling at line
  34, the unrecognised-view default at lines 41 to 42, and the
  narrower-of-the-two rule at line 45. `runner/runner.py`,
  `query_budget`, line 553 — both defaults and the `min` at
  lines 561 to 563. `runner/runner.py`, `_redact_patterns`,
  line 447 — built-ins plus the configured extras; no job input.
  The raw-line query operations (`grep`, `tail`) are answered
  only when the effective view allows raw lines:
  `runner/runner.py`, `_raw_lines_allowed`, line 1391 — `full`
  and `redacted` (and the empty view a non-mail caller may pass)
  allow them; `summary` and `attested` do not.
- **Class:** not a configuration setting of its own; the ceiling
  keys are the owner's configuration (`max_result_view` is a
  hot-reloadable default-class key, `max_query_budget` a plain
  config read), and the constraint is the direction of the
  combination rule, which lives in code.

## C18. The sandbox shape — its sources

- **Constraint:** when a job runs inside the bubblewrap sandbox,
  everything that decides the sandbox's shape MUST come from the
  owner's configuration or from code constants — the mode, the
  fixed flag set, the work mount, the owner's extra flags and
  extra read-only binds — with exactly one job-influenced
  addition, stated in the next bullet. No field in a job names a
  mount, a flag, or a path the sandbox exposes.
- **Value:** the fixed flag set is `DEFAULT_FLAGS` (user, IPC,
  network, and UTS namespaces; `/usr` read-only; `/proc`, `/dev`,
  a tmpfs `/tmp`; environment cleared); the job workdir is bound
  read-write at the work mount, default `/work`; inside the
  sandbox the job's writable set is that workdir alone.
- **Where:** `runner/guard/sandbox.py` — `WORK_MOUNT`, line 23;
  `DEFAULT_FLAGS`, lines 26 to 39; `_confinement_cfg`, line 98,
  which reads the confinement block from the configuration and
  from nowhere else; `build_bwrap_command`, line 213, which
  takes the configuration, validates the block (a malformed one
  is a startup refusal, C11's class), and assembles the argv.
  The decision to sandbox at all is `runner/runner.py`,
  `_confinement_argv`, line 340 — the mode from the
  configuration at line 345, `enforce` plus a working mechanism
  sandboxes, `audit` records `would_run_sandboxed` and runs
  normally, `off` never looks.
- **The one job-influenced addition:** the job's `interpreter`
  field (`runner/ops/exec.py`, line 497) selects the program
  that runs. When that program resolves outside `/usr`,
  `interpreter_binds` (`runner/guard/sandbox.py`, line 187)
  binds its own install prefix — its parent directory, or its
  grandparent when the parent is `bin`, never shallower than two
  components — read-only, so the interpreter can run at all. The
  rule is uniform (the owner's default interpreter gets the same
  treatment), the job names no path to bind, the bind is never
  writable, and each bind is appended to the caller's notes and
  written into the audit record. A job field therefore can
  change which interpreter prefix is visible read-only; it
  cannot widen the writable set, add a mount of its choosing, or
  disable the sandbox.
- **The snapshot side:** what a job is reported to have touched
  is computed the same way, from the owner's values alone —
  `workspace_root` and `protected_paths` from the configuration
  (`runner/ops/mail.py`, lines 427 to 437), the snapshot walk in
  `runner/ops/helpers.py`, `snapshot_outside`, line 13, which
  excludes the runner's own `base_dir` (the job's work tree
  lives inside it and never counts), and the verdict computed by
  `runner/runner.py`, `confinement_violated`, line 539. A query
  may ask for the `confined_to_workspace` attestation; the value
  it reports is the runner-computed one (`runner/ops/attest.py`,
  `build_attestations`, line 16), or `unconfigured` when no
  `workspace_root` is set.
- **Class:** the mode and the confinement block are refuse class
  at startup (C11); the flag set and the prefix rule are code
  constants, not settings.

## Summary table

| ID | Constraint | Default or value | Startup class |
|----|------------|------------------|---------------|
| C1 | `max_job_bytes` | 4194304 | refuse (bad type or negative) |
| C2 | `max_script_bytes` | 1048576, UTF-8 bytes | refuse (bad type or negative) |
| C3 | `max_result_bytes` | 5242880; 0 is unlimited | refuse (bad type or negative) |
| C4 | `_LOCAL_ENVELOPE_MAX_BYTES` | 262144, constant | not a setting |
| C5 | Signature | HMAC-SHA-384, `compare_digest` | secret is refuse class |
| C6 | Secret entropy floor | 128 bits estimated | refuse |
| C7 | Key fingerprint | `k-` + 8 hex of SHA-384(label + secret) | not a setting |
| C8 | Cleartext | refused; `--allow-cleartext` only | no config key exists |
| C9 | AEAD | AES-256-GCM, `aes-256-gcm/hkdf-sha384` | not a setting |
| C10 | Audience | configured `runner_id`; `aud` wins | refuse (as a security mode) |
| C11 | Six security modes | each `off` by default | refuse (malformed block) |
| C12 | `max_job_age_sec` | 3600; future bound 300 | default class |
| C13 | Protocol version | integer 1 only | not a setting |
| C14 | Key policies | per-key; script pin is SHA-384 | refuse (malformed policy) |
| C15 | Execution semantics | at most once; delivery at least once | not a setting |
| C16 | Transport credentials | required where a transport has them | refuse in the NATS example |
| C17 | Result-policy ceiling | views attested < summary < redacted < full; budget defaults 8 and 8, effective is the min | combination rule in code; ceilings are owner config |
| C18 | Sandbox shape | fixed flags; work mount `/work`; interpreter prefix bound read-only | mode and block refuse class; the rest is code |
