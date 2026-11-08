# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

# OWASP reference — the security shelf

This page gathers the OWASP material this project consults, in one
place: the risk lists used to name a finding, the verification
standard used to state what correct looks like, the testing guides
used to look for the flaw in the first place, and the cheat sheets
used to fix it. Each entry says what the source is, when to reach
for it, and the shape of its contents, with the canonical link.
The texts themselves live at OWASP; this page summarizes and
points, it does not reproduce them.

Editions were checked on 2026-11-07. OWASP revises these projects
on its own schedule, so confirm the current edition at the link
before citing one in a report.

## The risk lists

### OWASP Top 10:2025 — web application risks

What it is: OWASP's flagship awareness list, the ten web
application risk categories OWASP's data and community process
rank as most critical. The 2025 edition is the eighth, and the
current one; it renumbers and renames against the 2021 edition,
so a category ID means nothing without its year. It is an
awareness document, not a testable standard — ASVS, below, is
the standard.

Reach for it: to name and rank a web-facing finding in the
vocabulary every other security reader already shares.

- A01:2025 Broken Access Control — callers reach objects or
  actions that are not theirs; the 2025 edition folds
  server-side request forgery into this category.
- A02:2025 Security Misconfiguration — insecure defaults,
  leftover debug surface, verbose errors, missing hardening.
- A03:2025 Software Supply Chain Failures — compromised or
  vulnerable dependencies and build or distribution tooling;
  widens the old vulnerable-components category.
- A04:2025 Cryptographic Failures — missing, weak or misused
  cryptography; sensitive data exposed as a result.
- A05:2025 Injection — untrusted input reaches an interpreter
  (a query language, a shell, a template engine) unneutralized.
- A06:2025 Insecure Design — controls missing or ineffective at
  the design level, before any line of code is wrong.
- A07:2025 Authentication Failures — identity proofing and
  credential handling that let an attacker impersonate a user.
- A08:2025 Software or Data Integrity Failures — updates,
  serialized data and pipelines trusted without integrity
  checks.
- A09:2025 Security Logging and Alerting Failures — attacks
  happen unrecorded, or recorded and never alerted on.
- A10:2025 Mishandling of Exceptional Conditions — new in
  2025: errors, timeouts and resource exhaustion handled in
  ways that fail open or leak detail.

Project page: https://owasp.org/www-project-top-ten/

### OWASP API Security Top 10 2023

What it is: the API Security Project's ranked list of the risks
specific to APIs, which fail differently from web pages —
authorization is checked at the object, the property and the
function, and most APIs have no browser standing in front of
them. The 2023 edition is current.

Reach for it: whenever the surface under test is an API rather
than a page — including this project's own machine-facing
interfaces.

- API1:2023 Broken Object Level Authorization — an endpoint
  acts on a caller-supplied object ID with no ownership check.
- API2:2023 Broken Authentication — login, token and key
  handling that can be bypassed, replayed or brute-forced.
- API3:2023 Broken Object Property Level Authorization —
  callers read or write object fields they should not; merges
  the 2019 excessive-data-exposure and mass-assignment entries.
- API4:2023 Unrestricted Resource Consumption — no effective
  limits on request size, rate or cost.
- API5:2023 Broken Function Level Authorization — privileged
  functions reachable by ordinary callers.
- API6:2023 Unrestricted Access to Sensitive Business Flows —
  flows such as signup or recovery abused by automation at
  scale.
- API7:2023 Server Side Request Forgery — the API fetches
  caller-supplied URLs without validation.
- API8:2023 Security Misconfiguration — the API stack's own
  settings, headers and error handling.
- API9:2023 Improper Inventory Management — forgotten,
  undocumented or older API versions still live in production.
- API10:2023 Unsafe Consumption of APIs — data taken from
  upstream APIs trusted without validation or sanitization.

Project page: https://owasp.org/www-project-api-security/

### OWASP Top 10 for LLM Applications 2025

What it is: the OWASP GenAI Security Project's list of the ten
risks specific to applications built on large language models.
The 2025 edition is current.

Reach for it: for any feature where a model reads untrusted
input, produces output something else consumes, or can take
actions — the failure modes are not in the web list above.

- LLM01:2025 Prompt Injection — crafted input, direct or
  carried in content the model reads, redirects its behavior.
- LLM02:2025 Sensitive Information Disclosure — the model
  reveals data it should not.
- LLM03:2025 Supply Chain — compromised models, data sets,
  plug-ins and dependencies around the model.
- LLM04:2025 Data and Model Poisoning — tampered training or
  retrieval data skews behavior.
- LLM05:2025 Improper Output Handling — model output flows
  into code, queries or pages unsanitized.
- LLM06:2025 Excessive Agency — the model holds more
  capability, permission or autonomy than the task needs.
- LLM07:2025 System Prompt Leakage — the hidden instructions
  can be extracted.
- LLM08:2025 Vector and Embedding Weaknesses — retrieval
  stores holding poisoned or leaking embeddings.
- LLM09:2025 Misinformation — plausible, wrong output
  presented as fact.
- LLM10:2025 Unbounded Consumption — no caps on model usage;
  denial of service and cost abuse.

Project site: https://genai.owasp.org/llm-top-10/

## The verification standard

### OWASP ASVS 5.0.0 — Application Security Verification Standard

What it is: OWASP's standard of verifiable security
requirements for web applications and services — roughly 350
requirements across 17 chapters, each assigned to one of three
verification levels (L1 baseline, L2 the standard target for
applications handling sensitive data, L3 the highest
assurance). Version 5.0.0, released 2025-05-30, is current; it
reorganized the chapters, so requirement IDs do not carry over
from 4.0.3 — cite a requirement with its version, in the form
v5.0.0-1.2.5.

Reach for it: to turn "this looks wrong" into a checkable
statement — the requirement a piece of code meets or misses —
and to verify a fix against the same wording that named the
flaw.

The 17 chapters:

- V1 Encoding and Sanitization
- V2 Validation and Business Logic
- V3 Web Frontend Security
- V4 API and Web Service
- V5 File Handling
- V6 Authentication
- V7 Session Management
- V8 Authorization
- V9 Self-contained Tokens
- V10 OAuth and OIDC
- V11 Cryptography
- V12 Secure Communication
- V13 Configuration
- V14 Data Protection
- V15 Secure Coding and Architecture
- V16 Logging and Error Handling
- V17 WebRTC

Project page:
https://owasp.org/www-project-application-security-verification-standard/
Source: https://github.com/OWASP/ASVS

## The testing guides

### OWASP WSTG — Web Security Testing Guide

What it is: OWASP's guide to testing web applications and web
services, organized as individually numbered test cases. The
stable release is v4.2; a v5.0 is in development, and the
project's site carries the latest working text.

Reach for it: when testing a web or HTTP surface by hand or
building a checklist for one — each test case states what to
look for and how. The input validation and fuzzing material
(see Fuzzing, below) is the part this project leans on most.

The twelve test categories:

- Information Gathering
- Configuration and Deployment Management Testing
- Identity Management Testing
- Authentication Testing
- Authorization Testing
- Session Management Testing
- Input Validation Testing
- Testing for Error Handling
- Testing for Weak Cryptography
- Business Logic Testing
- Client-side Testing
- API Testing

Project page:
https://owasp.org/www-project-web-security-testing-guide/

### OWASP MASVS 2.1.0 and MASTG v2 — mobile

What they are: the mobile pair. MASVS, the Mobile Application
Security Verification Standard (v2.1.0, current), states the
requirements in 24 controls across 8 groups; the MASTG, the
Mobile Application Security Testing Guide (v2.0.0, the first
stable release of its restructured second edition), carries
the tests, techniques and tooling that verify them, and holds
the MAS testing profiles (MAS-L1, MAS-L2, MAS-R, MAS-P). The
testing guide was called the MSTG before the MAS restructure;
MASTG is the current name.

Reach for them: when the code under review is a mobile
application rather than a service — a different storage,
platform and network world from the web guides above.

The eight MASVS groups:

- MASVS-STORAGE — data storage and privacy on the device
- MASVS-CRYPTO — cryptographic controls
- MASVS-AUTH — authentication and authorization
- MASVS-NETWORK — network communication
- MASVS-PLATFORM — interaction with the platform
- MASVS-CODE — code quality and build settings
- MASVS-RESILIENCE — resilience against reverse engineering
  and tampering
- MASVS-PRIVACY — privacy controls

Project page: https://owasp.org/www-project-mobile-application-security/
MASVS and MASTG online: https://mas.owasp.org/

## The cheat sheets

### OWASP Cheat Sheet Series

What it is: OWASP's collection of short, prescriptive articles,
each on one defensive topic, written to be applied while coding
or reviewing rather than read as a standard.

Reach for it: at fix time. A finding names the flaw; the
matching sheet states the accepted shape of the fix. The full
series runs to dozens of sheets; the index below is the subset
that bears on testing and hardening input-handling code, which
is where this project's review attention concentrates.

Index: https://cheatsheetseries.owasp.org/

- Input Validation Cheat Sheet — allowlist-first validation
  design for every field a program accepts.
  https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- Injection Prevention Cheat Sheet — the general rule set:
  keep untrusted data out of interpreters, or neutralize it
  for the specific interpreter.
  https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html
- SQL Injection Prevention Cheat Sheet, with the Query
  Parameterization Cheat Sheet — the data-layer specifics.
  https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- OS Command Injection Defense Cheat Sheet — when input gets
  anywhere near a shell.
  https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html
- Cross Site Scripting Prevention Cheat Sheet — context-correct
  output encoding for anything rendered.
  https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- XML Security Cheat Sheet — parser settings that keep
  external entities and entity-expansion attacks off.
  https://cheatsheetseries.owasp.org/cheatsheets/XML_Security_Cheat_Sheet.html
- Deserialization Cheat Sheet — why untrusted data never goes
  through a native deserializer, and what to do instead.
  https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html
- Server Side Request Forgery Prevention Cheat Sheet —
  allowlists for any fetch of a caller-influenced URL.
  https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- Mass Assignment Cheat Sheet — bind only the fields a caller
  is allowed to set.
  https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html
- File Upload Cheat Sheet — type, size, storage and naming
  rules for uploaded content.
  https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- REST Security Cheat Sheet — the baseline for API endpoints:
  authentication, authorization, transport and content types.
  https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
- Error Handling Cheat Sheet and Logging Cheat Sheet — log
  the security event; leak nothing in the error.
  https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- HTTP Security Response Headers Cheat Sheet — the header set
  for anything served over HTTP.
  https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Security_Response_Headers_Cheat_Sheet.html
- Secrets Management Cheat Sheet — where keys live, how they
  are delivered, and how they rotate.
  https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- Authentication Cheat Sheet and Access Control Cheat Sheet —
  the baseline controls behind the identity checks.
  https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- LLM Prompt Injection Prevention Cheat Sheet — defensive
  design for model-backed features.
  https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

## Fuzzing and input validation

OWASP's own fuzzing material is spread across three places,
and all three are worth knowing:

- The community Fuzzing page states the discipline plainly:
  fuzz testing is a black-box technique that finds
  implementation bugs by injecting malformed or semi-malformed
  data in an automated fashion, on the working assumption that
  bugs are present and a systematic approach finds them sooner
  or later.
  https://owasp.org/www-community/Fuzzing
- The WSTG's Fuzz Vectors appendix collects ready-made vector
  sets by target category — cross-site scripting, buffer
  overflows and format strings, SQL injection, XML injection
  and more — usable with ZAP, Burp Suite or a fuzzer of one's
  own. It draws the distinction this project also uses:
  recursive fuzzing iterates the combinations of a set alphabet
  over part of a request; replacive fuzzing substitutes a known
  vector value. The appendix also names the standard public
  corpora and dictionaries it draws on, among them FuzzDB,
  SecLists and the Big List of Naughty Strings.
  https://wstg.owasp.org/v4.2/6-Appendix/C-Fuzz_Vectors/
- The WSTG's Input Validation Testing category turns the same
  ground into named test cases — one per injection class and
  per encoding or boundary mistake — which is the checklist a
  fuzz run's results get sorted against. The defense side of
  the same ground is ASVS V1 and V2 and the Input Validation
  Cheat Sheet above.

## How this maps to our work

- Parser and intake code — envelopes, configuration files,
  wire formats, anything that reads bytes it did not produce:
  the WSTG input validation tests and fuzz vectors are the
  attack side; ASVS V1 and V2 state the defense; findings
  classify under Top 10 A05 (injection) or A10 (exceptional
  conditions) more often than anywhere else.
- Protocol implementations: ASVS V11 (cryptography) and V12
  (secure communication) carry the requirements; Top 10 A04
  names the failure when they are missed.
- Configuration handling: Top 10 A02 and ASVS V13 — a wrong or
  hostile value is an input like any other, and gets validated
  like one.
- API-shaped surfaces: the API Security Top 10 for the risks,
  ASVS V4 for the requirements.
- Model-backed components: the LLM Top 10, above all LLM01
  (what the model reads), LLM05 (where its output goes) and
  LLM06 (what it is allowed to do).
- Writing a finding up: give the OWASP category ID from the
  list it belongs to and the ASVS requirement ID it violates.
  That pairing — shared name, checkable requirement — is what
  makes a report readable by anyone outside this project.

## This project, read against the lists

A structured review, not a penetration test: the verdicts
below were read out of the code and the documents in this
repository, not produced by running attacks against a live
installation. Each verdict is one of three. Covered: a control
exists and is named. Partially covered: a control exists with
a stated limit. Not applicable: the category does not reach
this surface, with the reason. Where the project's own pages
state a control in more detail, SECURITY.md and the threat
model are the fuller texts.

### Signed-job intake and envelope parsing

- Authentication (Top 10 A07; API2) — Covered. A job is acted
  on only with a valid signature under a high-entropy shared
  secret; the runner refuses weak secrets at startup. The
  sender's address is never trusted — the signature is the
  credential.
- Cryptographic failures (A04) — Covered. Job bodies travel
  as AES-256-GCM envelopes by default. The signed-but-cleartext
  form is refused unless the operator starts the runner with
  `--allow-cleartext`, and there is deliberately no
  configuration key for that switch.
- Software and data integrity (A08) — Covered. A job is
  committed as seen before it runs, so execution is
  at-most-once; a stale `issued_at` is refused; and a key's
  policy can narrow what that key's jobs may do.
- Unrestricted resource consumption (API4) — Covered.
  `max_job_bytes` (4 MiB) bounds a raw job before its signature
  is checked, and the script and result sizes are capped too
  (1 MiB and 5 MiB by default).
- Injection (A05) — Partially covered. The unsigned surface is
  the envelope framing and headers, parsed by strict readers
  and exercised by the fuzzing work below. Past the signature,
  a job is a program by design — that is the next surface.

### Script handling

- Access control (A01) — Covered, at the signature and the key
  policy: a secret whose policy allows only sensor alerts
  cannot pull work or run scripts at all. What a fully trusted
  secret may run is the product's stated purpose, argued openly
  in the threat model.
- Secure coding and architecture (ASVS V15) — Covered. Jobs
  run confined, under sandbox profiles, and optionally as a
  dedicated job user; at `enforce`, startup refuses when the
  demotion cannot be applied, and the startup confinement trial
  runs the configured flags before the runner opens for work.
- Excessive agency (LLM06, read across to automation in
  general) — Partially covered. Opinion and judge tiers review
  jobs, remediation tripwires kill a diverging job's process
  tree and quarantine its outputs, and the panic word is the
  operator's emergency stop. A validly signed job inside its
  policy still runs as sent; that is the design, not an
  oversight.

### Configuration loading

- Security misconfiguration (A02; ASVS V13) — Covered. The
  security-relevant settings are read strictly: a
  present-but-invalid value that would change what the runner
  reaches, runs or enforces refuses startup instead of falling
  back to a default; an unknown field inside a key policy
  refuses; and a shared-secret file readable by everyone on
  the box refuses startup.
- Data protection (ASVS V14) — Partially covered. The secret
  itself is generated at install time at 256 bits and its file
  permissions are policed at startup. Settings that do not
  bear on security keep forgiving defaults, by the same
  written decision that makes the security ones strict.

### The transports, and the DTLS binding

- Secure communication (ASVS V12) — Covered. The DTLS binding
  offers a single AEAD cipher suite (TLS_AES_256_GCM_SHA384)
  with a pre-shared key plus X25519 key exchange, and a hybrid
  post-quantum exchange is implemented and off by default. The
  mail transports require TLS 1.2 or better with certificate
  verification by default.
- Cryptographic failures (A04) — Partially covered, with the
  limit written down where users read it: on the mail path,
  confidentiality is the job envelope rather than the hop, and
  there is no forward secrecy unless the transport layer
  provides it.

### The hosted face

- The web risk lists (Top 10, most of ASVS V3) — Mostly not
  applicable to the runner itself. The default and hosted
  installs serve no web interface and open no listening port;
  jobs arrive over mail, files, queues and the other
  transports, so there is no page surface for the browser-side
  categories to attach to. The hosting control plane drives
  cloud providers' APIs under the operator's own provider
  account; the web-facing risk there sits with the providers'
  consoles, not with code in this tree. The parts of the lists
  that do reach this surface — authentication and integrity of
  the job channel — are the intake verdicts above.

### File and path handling

- Path traversal (WSTG input validation testing) — Covered. A
  job_id outside `[A-Za-z0-9._-]{1,128}` is rejected, so a
  `..`-shaped id names nothing; results are stashed under the
  runner's own outbox, by validated id.
- File handling (ASVS V5) — Partially covered. Sizes are
  capped before work begins. The runner does not extract
  archives or render uploaded content, so most of V5 has
  nothing to attach to.

### The model-backed component

- Prompt injection (LLM01) — Partially covered, by
  architecture. The opinion a model contributes is advisory:
  it never blocks, holds or approves a job by itself, and the
  default opinion is deterministic machinery with no model in
  it. A local model joins only when the operator opts in.
- Improper output handling (LLM05) and excessive agency
  (LLM06) — Covered at the one place a model's word can affect
  a running job: in oracle remediation mode, anything short of
  an affirmative order is an abstention and never kills; the
  deterministic tripwire list acts without the model.

### Across all surfaces

- Security logging and alerting failures (A09) — Covered.
  Audit records are canonical JSON forming a tamper-evident
  hash chain, and a diverging job pages the owner under
  remediation.
- Insecure design (A06) — Covered as a practice: the threat
  model is written, public, and lists its own gaps beside its
  claims (the threat model and security-gaps pages shelved
  with this one).

## Suggested additions to the fuzzing work

Recommendations only. The project already fuzzes its intake
readers and keeps a persistent corpus for them
(docs/steady/fuzzing.md). The lines below name OWASP-shaped
checks that fit surfaces and corpora that already exist; each
is a suggestion for that work to take up or decline, and
nothing in this section changes any setup by itself.

- Injection-shaped values — the quote, comment and delimiter
  shapes from the WSTG fuzz vectors — at the envelope and
  header readers, joining the persistent corpus those readers
  already feed. Class: A05; WSTG input validation testing.
- Boundary and type-confused values at the numeric
  configuration readers: negatives, fractions, numeric
  strings, values past the stated ceiling, omitted keys.
  Class: ASVS V2 and V13.
- Truncated records, length fields that disagree with the
  body they head, and mixed-version records at the DTLS
  framing reader. Class: A10, mishandling of exceptional
  conditions.
- Separator, dot-segment and encoding variants at the job-id
  and path readers, beside the traversal shapes the tests
  already carry. Class: WSTG input validation testing.
- Encoding edge cases — byte-order marks, mixed line endings,
  embedded NUL bytes — at the script and configuration text
  readers. Class: A10; ASVS V1.
- Inputs sized just under, exactly at and just past each byte
  cap at the intake, including slow, partial deliveries.
  Class: API4, unrestricted resource consumption.

## Attribution and license

OWASP and the project names above belong to the Open Worldwide
Application Security Project (the OWASP Foundation). OWASP
publishes its material under Creative Commons
Attribution-ShareAlike licenses (CC BY-SA 4.0 for the current
projects). This page is an original summary written for this
repository, with links to the canonical sources; the category
names and requirement titles are OWASP's own, credited here.
Read and cite the originals at the links — where this page and
an original disagree, the original governs.
