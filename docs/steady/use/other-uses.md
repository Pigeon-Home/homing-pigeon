# Other uses

A survey of uses for this suite beyond the ones it was first
built for: who would run it, what job they would send and get
back, why this shape fits them better than a cloud service or a
remote-desktop tool, and what the suite would have to grow
before the use is real. The survey was made in November 2026
from documented practice in adjacent fields — every use below
is grounded in an existing product or practice, cited where it
stands — and it records the gaps as plainly as the fits.

The shape the survey takes as given: jobs are plain signed
files transported by ordinary email or cloud mailboxes — no
inbound ports, working through NAT and intermittent
connectivity; a runner on the operator's own Windows or Linux
machine executes them and returns signed results; an
attestation layer governs exactly what information about a run
the remote requester may learn; strong local configuration
gates decide what may run; and the whole suite is open source
and free.

That combination — not any single feature — is the
differentiator. Email alone is the territory of parsed-email
automation services; self-hosted runners alone are the
territory of continuous-integration tools; remote desktop
alone is TeamViewer and RustDesk territory. The cell this
suite occupies is: asynchronous, signed, locally gated, and
attestation-limited in what it discloses, on hardware the
operator already owns, reachable only through a mailbox.

The pattern has a long history. UUCP was explicitly "a generic
file copy and command execution protocol" whose X-files told a
remote system what to execute, and whose store-and-forward
design was resilient "in the complete absence of a working
end-to-end path" —
http://www.cs.cmu.edu/~dga/15-849/store_and_forward.html .
FidoNet, DakNet, KioskNet, Winlink and Saildocs (below) are
the same bet, repeatedly re-validated.

How far to trust this page: the survey did not inspect this
suite. Its name in the survey, its feature completeness, its
attestation mechanism, its job formats and its mailbox polling
model were taken from the description above, and every "fits"
below is architectural inference from that description,
grounded in the cited adjacent practice. No use below is
evidence that this suite has been deployed for it. The closing
section states the survey's open questions in full.

## In short

- 16 distinct uses are documented below, each with its user,
  the job sent and returned, why this shape fits, and the
  honest gaps.
- 4 of them are flagged ★: the survey judges these the least
  likely to have been considered already — (14) data-stays-put
  analysis for mutually distrusting parties, (15) digital
  estate execution with catalogue-versus-content attestation,
  (16) time-locked and dead-man's-switch jobs, and, inside use
  8, attested proof-of-care for insurers and caretakers
  without camera access.
- Cross-cutting limits apply to almost every use: email is
  slow, size-capped and unsealed by default; there is no
  real-time control, no live video, and no guarantee the host
  is awake; and a job file needs a safe template library,
  sandboxing, scheduling and queueing, and a non-technical
  consent and onboarding path before non-hobbyist audiences
  can use it. A job runner is, as the self-hosted CI
  literature puts it, "remote code execution by design" —
  https://www.ssdnodes.com/learn/self-hosted-github-actions-runner
  — so the local gates and the signing are not features; they
  are the safety case.
- The 5 uses the survey judges most promising for broadening
  the audience stand at the end, with its reasons: 1)
  trusted-circle family tech support and accessibility
  delegation, 2) ham, disaster-response and off-grid
  communities, 3) makerspace, library and school fabrication
  and remote-lab queues, 4) bookkeeper-led small-business
  back-office on the business's own PC, 5) data-stays-put
  attested analysis for clinics, law firms and auditors.

## The 16 uses

### 1. Trusted-circle family tech support — without handing over the desktop

- **Who:** The de-facto family sysadmin; an elderly or
  non-technical parent or relative who owns the machine (the
  operator).
- **Job sent / returned:** Signed maintenance jobs — "run
  disk-health + backup check," "apply the pre-approved update
  set," "collect a redacted diagnostic bundle," "fix printer
  queue with script X." Returned: signed success or failure,
  log excerpts the attestation policy permits, and a
  plain-language summary.
- **Why this shape fits:** Today's default is TeamViewer,
  AnyDesk or Chrome Remote Desktop — live, all-seeing,
  all-powerful, and a classic scammer vector; guides stress
  helpers can "see and control your parent's device" —
  https://divplanet.com/blog/how-to-help-your-parents-with-their-tech-over-the-holidays/ .
  Self-hosted RustDesk exists precisely because people "didn't
  want to expose my family's devices to tools like
  TeamViewer… no real guarantee personal data stays safe" —
  https://www.xda-developers.com/self-hosted-tool-makes-remote-tech-support-family-painless/ .
  This suite is narrower on purpose: no screen, no banking
  session, no free browsing of photos — the parent sees in
  local config exactly which named jobs which named relative
  may trigger, and attestation limits what comes back. It also
  works when the parent can't coordinate a live session, and
  needs no inbound port on a home router.
- **What is missing:** A curated, jargon-free job library (no
  raw scripts for this audience); one-click pairing and key
  exchange; an "explain what this job will do" preview and a
  local approve/deny prompt; wake-on-LAN or scheduled windows
  for machines that sleep; safe rollback.

### 2. Accessibility delegation: operating a machine on someone's behalf, with bounded sight

- **Who:** Blind or low-vision, motor-impaired or chronically
  ill computer owners (operators and requesters in either
  direction), and their trusted sighted or able helpers,
  volunteers, or support workers.
- **Job sent / returned:** "Convert this inaccessible PDF
  statement to tagged text using my local tools," "run the
  screen-reader configuration check," "batch-rename and OCR my
  scanned post," "install this pre-vetted accessibility
  update." Returned: only the converted artefact and an
  attested completion note — not a view of the whole drive.
- **Why this shape fits:** Be My Eyes connects "more than half
  a million" blind users to sighted volunteers for tasks
  including "reading digital displays or computer screens" and
  "sorting and dealing with paper mail" —
  https://play.google.com/store/apps/details?id=com.bemyeyes.bemyeyes
  — and Aira sells live visual interpreters. Both are
  synchronous and visually total: the helper sees what the
  camera or screen shows. Many computer tasks are not visual
  at all, are recurring, and are private (bank letters,
  medical portals' exports). An asynchronous, pre-authorised
  job with attestation-limited output preserves autonomy — the
  owner defines the task catalogue in advance, when they are
  rested and unhurried, rather than narrating passwords live.
- **What is missing:** Screen-reader-first requester and
  operator UX; a voice or compose-by-email job builder; strict
  output-only attestation templates; a safeguarding model for
  volunteer helpers (vetting is social, not cryptographic);
  and, presumably, no support today for interactive GUI tasks —
  anything needing judgement mid-task still needs a human
  call.

### 3. Disaster-response and grid-down outposts

- **Who:** ARES/RACES and NGO relief teams, ham operators, a
  household, clinic or shelter whose local connectivity is
  destroyed but which can occasionally reach a mailbox (or a
  radio-email gateway).
- **Job sent / returned:** From an intact home base to a field
  laptop, or vice versa: "run the shelter-bed inventory script
  and return counts," "compress and return today's ICS-style
  situation log," "execute the pre-staged water-pump
  controller check." Returned: small signed structured reports
  that can queue for hours.
- **Why this shape fits:** Winlink is a "worldwide radio
  messaging system" providing "email with attachments,
  position reporting, weather bulletins, emergency and relief
  communications," built for "emergency and contingency
  communications" and used by the Red Cross and DHS SHARES —
  https://en.wikipedia.org/wiki/Winlink . That community
  already thinks in store-and-forward email. A cloud dashboard
  dies with the backhaul; remote desktop needs a continuous
  session. A signed job file rides the same mailbox Winlink or
  SailMail already delivers, executes locally when power is
  available, and its signed result is provable when it finally
  reaches HQ — which matters when multiple relays handled it.
- **What is missing:** Hard attachment-size discipline and
  chunking/resume; integration HOWTOs for Winlink and SailMail
  gateways; power-aware deferral (run when battery > X%);
  priority and pre-emption; field testing — this use is
  plausible by analogy, not demonstrated for this suite.

### 4. Rural, maritime, polar and other intermittently connected field stations

- **Who:** Research stations, ships' crews, remote farms and
  mines, aid posts — and the shore or home colleagues who
  support them.
- **Job sent / returned:** Shore → station: "re-run the
  instrument calibration script," "reprocess last week's
  sensor files with model v2." Station → shore is the classic
  direction, but the inverted one is valuable too: a sailor
  emails a job to their own shore machine — "fetch and
  compress these GRIB/weather and web pages, OCR this document
  with the big model on my desk PC" — and collects a
  kilobyte-scale signed reply on the next satellite pass.
- **Why this shape fits:** Saildocs has offered exactly
  email-as-compute since the 1990s: "weather forecasts,
  documents, and web content via email — perfect for
  low-bandwidth satellite connections (Iridium, Sailmail,
  Winlink)" — http://saildocs.com ; a 2026 email-AI service
  for sailors makes the same point, keeping Winlink/SailMail
  replies to "a few kilobytes" of plain text —
  https://www.askpenpal.com/sailing . NASA's DTN programme
  formalises store-and-forward for "disconnections… delays…
  data rate mismatches," demonstrated from McMurdo Station,
  Antarctica, to the ISS —
  https://www.nasa.gov/technology/space-comms/dtn-overview-benefits-successstories-learningresources .
  No inbound port survives a ship's NAT or satellite terminal;
  no cloud account is reachable at 2.4 kbps.
- **What is missing:** Aggressive result-size budgets and
  summarisation jobs; delay-tolerant retry semantics (days,
  not minutes); cost warnings per kilobyte for satellite mail;
  time-zone and clock-skew tolerance in signature validation.

### 5. Store-and-forward rural health clinics — diagnostics support, not telemedicine video

- **Who:** A rural clinic (operator, owns patient data and a
  diagnostic device or PC) and a distant specialist service,
  NGO or district hospital (requester).
- **Job sent / returned:** "Run the locally approved
  image-classification / ECG-analysis / lab-device export job
  on today's (locally stored) cases; return de-identified
  measurements and flags." Or the reverse: the specialist
  sends a signed formulary or report-generation job. Returned:
  attested aggregates and flagged case IDs — not the patient
  record, unless local policy says so.
- **Why this shape fits:** Store-and-forward telemedicine is
  established precisely because it needs "no need to
  synchronize the referring and consulting providers' time, low
  bandwidth requirements, minimal technical support," and
  works with "poor or intermittent connectivity" (Alaska
  AFHCAN tConsult) —
  https://entokey.com/the-alaska-experience-using-store-and-forward-telemedicine-for-ent-care-in-alaska/ .
  In Cambodia, "motomen" ferried email to village clinics and
  store-and-forward cut referrals ~51% —
  https://www.nucamp.co/blog/coding-bootcamp-cambodia-khm-healthcare-how-ai-is-helping-healthcare-companies-in-cambodia-cut-costs-and-improve-efficiency .
  Cloud PACS and video fail on those links and export
  regulated data; this keeps data on the clinic PC and lets
  attestation enforce the de-identification boundary.
- **What is missing — large and honest:** This is regulated
  territory. It needs validated, clinical-grade job packages,
  audit trails acceptable to health authorities, encryption at
  rest, consent workflows, and probably professional
  deployment. Not a hobbyist rollout; listed because the
  architectural fit is proven by tConsult-style practice, not
  because the suite is near-ready.

### 6. Shared scientific instruments and remote laboratories

- **Who:** Universities, schools and citizen-science labs
  (operators of scarce instruments) and remote students and
  researchers (requesters).
- **Job sent / returned:** Batch-shaped experiments: "run this
  spectrometer/centrifuge/telescope sequence with these
  parameters tonight; return measurements + instrument-state
  attestation." Telescope queues and radiochemistry
  RoboLab-style work are naturally batch, unlike joystick
  teleoperation.
- **Why this shape fits:** Remote labs exist to give "real
  experiments without being physically present" and TeleopLab
  shows phone teleoperation of a robotic arm for hands-on
  learning — https://arxiv.org/html/2509.05547v1 ; RoboLab
  enables "real radiochemistry experiments without being
  physically present in a laboratory" via a web/cloud template —
  https://repo.uni-hannover.de/items/3b3f6e6a-629a-4ca9-9e83-257abcdc9fd1 .
  Cloud and web teleoperation assumes continuous connectivity
  and a public endpoint, and gives the requester broad live
  access. For the large subset of experiments that are
  submit-and-wait, email jobs remove the public attack
  surface, let a school firewall stay closed, and attestation
  can prove which parameters and instrument state produced a
  result — a reproducibility feature, not just privacy.
- **What is missing:** Instrument drivers and safety
  interlocks per device class; queueing, scheduling and
  fair-share quotas; large-result handling (spectra and images
  exceed mail limits — needs local link-out or chunking); and,
  explicitly, not real-time teleoperation — TeleopLab-style
  interactive control is out of scope.

### 7. Small farms and environmental / wildlife monitoring stations

- **Who:** Small farmers, conservation projects, watershed and
  weather volunteers — the operator is a farm or field PC; the
  requesters are the farmer when away, an agronomist, or a
  research partner.
- **Job sent / returned:** "Summarise this week's
  soil-moisture/irrigation logs and flag anomalies," "re-run
  camera-trap species classification on the SD-card batch with
  the new model; return counts, not images," "apply the
  pre-approved irrigation schedule calculation." Returned:
  small signed summaries.
- **Why this shape fits:** Offline-first is a stated design
  requirement in ag-tech: edge irrigation platforms stress
  that the device "keeps measuring, deciding within the local
  rules you defined… and buffers the data" when the internet
  is down, with grower-set limits and approval —
  https://u2aiagro.com/ . Camera-trap research likewise
  targets sites "without access to stationary power" and with
  no network infrastructure, minimising site visits —
  https://www.mdpi.com/2079-9292/14/21/4266 . A cloud IoT
  platform demands always-on backhaul and a vendor account per
  sensor network; remote desktop to a barn PC is absurd. Email
  tolerates a weekly drive to coverage.
- **What is missing:** Sensor and actuator integrations
  (MQTT/LoRa bridges), solar and power scheduling, model-update
  distribution by mail, and a hard safety rule: actuation jobs
  (valves, gates, heaters) need local limits and fail-safes the
  suite cannot supply by itself.

### 8. Homes, second homes, homelabs and creators' heavy jobs — including ★ attested proof-of-care

- **Who:** Travellers, second-home owners, homelabbers,
  podcasters and video creators (often both operator and
  requester, but also caretakers, house-sitters, co-owners and
  family).
- **Job sent / returned:** To one's own home machine: "verify
  last night's backup and return a signed integrity
  attestation," "transcode/render this project on the home GPU
  and return proxies," "run the house-check: furnace runtime,
  freeze sensors, disk health — return yes/no + readings." ★
  **Proof-of-care variant (flagged ★):** a caretaker or
  house-sitter is the requester and an insurer, landlord or
  co-owner accepts an attested house-check — they learn "heat
  stayed above 7 °C, no water sensor tripped" and nothing
  else: no camera feed, no entry codes, no remote desktop into
  a home.
- **Why this shape fits:** Second homes "often [have] no
  internet on site," are empty for months, and the likeliest
  loss is water or freeze damage, undiscovered —
  https://www.home-securityguide.com/home-alarms/guides/monitoring-vacation-home-remotely/ .
  Home Assistant's appeal is the same local-first logic —
  automations on your own hardware, working when the internet
  drops — https://selfhosting.sh/apps/home-assistant/ . Cloud
  rendering and transcoding charges by the minute and uploads
  masters; a home GPU sits idle. Remote desktop exposes the
  whole home network to prove a boiler ran.
- **What is missing:** Wake/sleep orchestration, GPU and
  driver job templates (Blender, ffmpeg), a result-size
  strategy for media (return proxies and receipts, not
  masters), sensor integrations; and, for proof-of-care, a
  tamper-evidence story an insurer would actually accept —
  currently speculative.

### 9. Makerspaces, libraries and community fabrication queues

- **Who:** A library or makerspace (operator) and its patrons
  and members (requesters); also small "print bureau"
  side-businesses in someone's workshop.
- **Job sent / returned:** "Print this STL with profile
  PLA-standard," "laser-etch this SVG after staff load
  material," "CNC this file in the approved-material list."
  Returned: signed completion, duration and material used, and
  (if policy allows) a completion photo hash or link.
- **Why this shape fits:** This workflow already exists by
  email: one library makerspace requires patrons to "submit
  their 3D print jobs as a .STL file either in person via USB
  drive, or via email," with staff running "jobs… in the order
  they were submitted" —
  https://c2ae1c79-f5a6-4835-b863-87ce796cb903.filesusr.com/ugd/376e70_c5ea67c528ac40e1ba8689388a77b42b.pdf .
  OctoPrint-style browser control —
  https://sourceforge.net/software/compare/OctoPrint-vs-Ultimaker-Cura-vs-ideaMaker/
  — assumes LAN or public exposure and live supervision.
  Signed email jobs add authentication, an audit trail and a
  queue to a practice currently run on trust and a shared
  inbox, with no port opened on a library network.
- **What is missing — safety-critical:** Lasers and CNC must
  never run unattended; the suite would need a two-stage model
  (job accepted by mail, released only by a staff member
  physically present), approved-material allowlists,
  slicer-profile templates, and payment and quota hooks. 3D
  printing is the only near-term-safe subset.

### 10. Small-business back-office on the business's own PC — via its bookkeeper

- **Who:** A shop, trades firm, café or clinic (operator; its
  PC holds the accounting, POS and local files) and its
  external bookkeeper, accountant or franchise HQ (requester).
- **Job sent / returned:** A month-end job: "export and
  reconcile the local accounting package, produce a
  VAT/sales-tax summary, list invoices that don't match POs."
  Returned: a signed summary pack. The underlying ledgers
  never leave the premises.
- **Why this shape fits:** Small-business document automation
  today means emailing invoices to a cloud parser — Parseur's
  model is documents arriving by email, extracted, and pushed
  to QuickBooks, Xero or Sheets —
  https://parseur.com/blog/document-automation-small-business
  — that is, financial data leaves to a SaaS, priced per
  document. Many micro-businesses run desktop accounting or a
  local POS, or simply refuse cloud bookkeeping. Remote
  desktop for a bookkeeper (a common real practice) gives them
  the whole desktop, passwords and all, at a scheduled live
  hour. A gated job catalogue plus attestation gives the
  bookkeeper exactly the month-end outputs and the owner a log
  of exactly what was accessed.
- **What is missing:** Templates for specific accounting and
  POS packages, an accountant-friendly (non-CLI) job composer,
  engagement and consent records, retention rules. The
  realistic first audience is the bookkeepers, who can
  standardise one job pack across dozens of client PCs — a
  distribution channel, not just a use.

### 11. Trusted-circle community computation — a private, personal BOINC

- **Who:** A classroom, research group, film club, open-science
  team or extended friend group pooling machines they own.
- **Job sent / returned:** "Render frames 120–240 of this
  Blender scene," "run this protein/prime/climate work-unit,"
  "transcribe this oral-history batch with the local speech
  model." Returned: results plus attestation of binary and
  input hashes, so the coordinator of the pool can spot bad
  runs.
- **Why this shape fits:** BOINC proves volunteers will donate
  idle cycles at scale — open-source middleware where
  "researchers [utilise] processing resources of personal
  computers… around the world," with redundant computing
  because "volunteer computers can't be trusted" —
  https://en.wikipedia.org/wiki/Berkeley_Open_Infrastructure_for_Network_Computing .
  But BOINC is for public projects run by institutions with
  servers. There is no equivalent for private jobs among 5–50
  people who trust each other socially but not with open
  access: cloud GPUs cost money and take the data; this suite
  needs no server at all — the pool coordinator's mailbox is
  the queue, local gates cap CPU and hours per contributor,
  and attestation plus spot-replication substitutes for
  BOINC's validator.
- **What is missing:** Work-unit splitting and merging,
  redundancy and verification helpers, credit and fairness
  accounting, checkpointing for long jobs, contributor
  resource caps in the UI. Also an honest limit: mail latency
  makes this useless for tightly-coupled parallel computing —
  it suits embarrassingly-parallel batches only.

### 12. Offline, quasi-air-gapped and high-security site administration

- **Who:** Small organisations with a segregated machine or
  room — a law office evidence PC, a factory OT-adjacent PC, a
  clinic records PC, a place of worship or NGO finance PC —
  and their external IT provider or auditor.
- **Job sent / returned:** The provider emails a signed job
  through the organisation's normal mailbox (the one
  sanctioned channel that is occasionally connected):
  "inventory patch level," "verify backup image hashes,"
  "extract and redact these logs," "run the vendor's
  diagnostic." Returned: a signed, attestation-redacted
  report. The machine opens no listening service, ever.
- **Why this shape fits:** Air-gapped practice already moves
  data by hand — "sneakernet" — because networks are
  "prohibitively expensive," high-security, or
  bandwidth-impractical —
  https://en.wikipedia.org/wiki/Sneakernet . The pain of
  sneakernet is the lack of an authentication standard and of
  proof of what ran. Signed jobs, gated local config and
  signed results formalise the courier step whether the
  "courier" is a USB stick or a mailbox sync. Cloud RMM agents
  (the normal SMB solution) require a persistent outbound
  agent with broad vendor trust — exactly what these sites
  reject.
- **What is missing:** A true air gap means no mailbox on the
  machine — this needs a documented two-machine or USB relay
  workflow and a malware-scanning kiosk step (Stuxnet is the
  standing warning); key custody and rotation for
  organisations; compliance-grade logging. This audience will
  demand an independent security review before any adoption.

### 13. Security-research detonation and test harnesses — by proxy, on a lab you trust

- **Who:** Students, CTF teams, small SOCs and independent
  researchers (requesters), and the owner of an isolated lab
  machine (operator — often the same group, different hat).
- **Job sent / returned:** "Detonate this suspicious attachment
  in the lab VM profile Win11-clean; return the behavioural
  report." "Run this fuzzing job overnight; return crashes."
  Returned: a signed report bundle (hashes, network
  indicators, screenshots if policy allows).
- **Why this shape fits:** Cuckoo/CAPE established the pattern —
  a "self-hosted analysis platform that executes files inside
  disposable virtual machines, captures their behaviour, and
  turns [it] into a readable report," submitted via web UI or
  API — https://www.cuckoosandbox.com/ . Cloud sandboxes
  (ANY.RUN and its peers) take possibly-sensitive samples to a
  third party and cost money; running samples on your own
  laptop is dangerous. Email transport lets a lab with no
  public endpoint (deliberately — it detonates malware) accept
  work from teammates anywhere, with local gates restricting
  job types to lab profiles.
- **What is missing — serious:** The suite must never become a
  malware-delivery channel: it needs sample-handling
  conventions (password-zipped samples, as labs use), VM
  isolation outside the suite's scope, egress-killed lab
  networking, and an abuse policy. A runner executing signed
  jobs from a mailbox is itself an attractive target —
  signing-key compromise here is catastrophic, and that must
  be said in any write-up for this audience.

### 14. ★ Data-stays-put analysis for mutually distrusting parties — "bring the code to the data"

- **Who:** Pairs who need a computation but cannot share raw
  data: a university researcher and a small clinic, school or
  charity holding sensitive records; an external auditor and a
  firm; an insurer and a claimant's home system; two merging
  nonprofits' IT volunteers.
- **Job sent / returned:** The requester sends a signed
  analysis job (query or model version pinned by hash). The
  operator's local gates approve that job class once. Returned:
  only the attestation-permitted output — aggregate counts,
  model metrics, a yes/no compliance answer — with attestation
  that job-hash X ran over dataset-hash Y at time T, and that
  no other output channel was used.
- **Why this shape fits — and why it is the suite's most
  distinctive cell:** Cloud analytics requires uploading the
  dataset (often unlawful or reputationally impossible for a
  small holder). Remote desktop gives the outsider eyes on the
  data. The entire confidential-computing industry is building
  expensive hardware versions of this promise — remote
  attestation that "a specific algorithm has been executed on
  declared inputs… without exposing the underlying data" —
  https://iris.polito.it/retrieve/326c7593-414c-4746-b259-b752e0f42f28/2026_DLT__CameraReady.pdf .
  This suite offers a social-scale, software-only cousin: not
  hardware TEE assurance (it must not claim that — a malicious
  operator who controls the OS can lie in ways a TEE resists),
  but for low-to-moderate stakes — a charity impact evaluation,
  a school-district study, a cooperative's joint statistics —
  signed jobs, local gates and disclosure-limited attestation
  may be enough, at zero cost, on existing PCs.
- **What is missing:** Output-privacy review is on the operator
  (small aggregates can leak individuals — needs
  minimum-cell-size or differential-privacy job templates);
  reproducible job packaging; a plain-language "what this job
  can and cannot see" certificate for non-technical data
  holders; legal templates (data-processing agreements).
  Flagged ★: it inverts the usual direction — the requester is
  not the data owner, and less disclosure is the point.

### 15. ★ Digital legacy and estate administration — the executor runs only what the deceased authorised

- **Who:** A person planning ahead (operator, while alive)
  and, later, their executor, digital executor or family
  (requesters).
- **Job sent / returned:** Pre-authorised, executor-triggered
  jobs on the deceased's home machine: "produce an inventory
  (catalogue) of accounts and files — names and dates only,"
  "export the photo library to the attached drive and return
  its hash manifest," "run the farewell-message dispatch
  list," "securely wipe the browser-profile folder and attest
  deletion." Returned: exactly the tier the deceased
  configured — catalogue or content, per folder or service.
- **Why this shape fits:** Estate law already thinks in
  attestation-like tiers. RUFADAA, adopted in "47 states plus
  DC" per one 2026 guide, splits a fiduciary's access to the
  catalogue of communications from their content, with content
  requiring the user's explicit consent —
  https://www.docsats.com/blog/digital-executor-explained/ .
  Platform tools do the same: Google's Inactive Account
  Manager lets you choose "which data each of them receives,"
  per person, after 3–18 months' inactivity —
  https://probate.help/archive/digital-legacy-tools/ . But
  platform tools stop at platform data; a lifetime of local
  files, self-hosted services, crypto-wallet metadata and home
  automation sits on a home PC that executors currently either
  crack open wholesale (total disclosure, plus the ToS and
  CFAA risks the estate guides note) or wipe blindly.
  Pre-signed local gates plus per-job attestation is, almost
  literally, RUFADAA's catalogue/content split implemented in
  software.
- **What is missing:** Triggering must not be mere possession
  of a signed job — this needs a death-certificate or
  multi-party (for example 2-of-3 family plus solicitor)
  release ceremony, long-delay and cancellation windows
  mirroring Inactive Account Manager's warnings, and
  jurisdiction-specific legal review. High sensitivity, slow
  trust-building; a long-horizon use, not a launch use.
  Flagged ★.

### 16. ★ Time-locked, embargoed and dead-man's-switch jobs

- **Who:** Journalists and researchers (embargoed releases),
  teachers (exam and model-answer release), families
  (anniversary and future messages), whistleblowing-adjacent
  sources and small NGOs (dead-man's disclosure), event
  organisers (results reveals).
- **Job sent / returned:** A signed job deposited now, with the
  local gate "not before date D" or "not unless check-in
  missed": "on D, render and dispatch the embargoed report
  pack to list L," "if no signed check-in for 30 days, send
  the pre-written disclosure pack to the named newsroom."
  Returned (to a designated address): the pack, or an
  attestation that it fired.
- **Why this shape fits:** Cloud dead-man's-switch services and
  Google's Inactive Account Manager (above) work only inside
  one vendor's account and die if the subscription or account
  dies; schedulers (cron plus cloud functions) require an
  always-on, publicly managed endpoint. A runner on a machine
  the owner physically controls, fed by ordinary mail, keeps
  working through account churn, and local gates mean even the
  requester who deposited the job cannot silently alter the
  recipient list later — the signed original is the policy.
- **What is missing:** The obvious failure mode: the machine is
  off, sold or wiped at D — this needs heartbeat monitoring,
  escrowed copies with multiple independent operators (a
  "switch" held by one laptop is theatre), and honest UX about
  reliability; and legal and ethical review for disclosure
  switches. Flagged ★ (distinct from use 15: use 15 is
  executor-triggered after death; use 16 is time- or
  absence-triggered, often while the author lives).

### Also considered and set aside

- **Email-triggered home automation alone** (in the manner of
  Zapier's parsed-email triggers —
  https://help.zapier.com/hc/en-us/articles/8496292952973-Trigger-Zap-workflows-from-new-parsed-emails )
  is too shallow alone; it is a feature inside uses 1 and 8,
  not a use case of its own.
- **Censorship-circumvention and journalism source submission**
  (the SecureDrop model — open source, used by major
  newsrooms, https://blog.pwnsy.com/what-is-the-dark-web ) was
  deliberately not promoted to a numbered use: in a shutdown,
  email itself is usually the blocked or monitored channel,
  SecureDrop's Tor design solves a different (anonymity)
  problem this suite does not, and recommending a signed-job
  tool to at-risk sources without an anonymity layer could
  endanger them. At most, a low-risk variant exists (an NGO
  abroad processing documents a field worker emails out),
  which uses 3 and 4 cover.
- **Real-time robotics and teleoperation, live support and
  screen-sharing, video anything, and tightly-coupled HPC**
  were excluded: email latency and size caps disqualify them
  by construction.

## Cross-cutting gaps

These apply across nearly all of the uses above, stated once:

1. **A job-template library, not raw code.** Every
   non-hobbyist use above needs named, parameterised,
   human-readable jobs ("Backup Check," parameters: none) —
   raw script submission limits the audience to programmers.
2. **Sandboxing and resource caps.** CPU, RAM, disk, time and
   network-egress limits per job class; VM or container
   profiles for untrusted inputs (uses 13 and 14).
3. **Email mechanics.** Attachment limits of common mailboxes,
   chunking, compression, duplicate and retry handling, the
   distinction between SPF/DKIM results and the job signature,
   and mailbox-polling intervals against battery and power.
4. **Identity UX.** Key generation, pairing, revocation and
   recovery for non-technical operators and requesters; a lost
   key meaning lost access must be survivable for uses 1 and
   15.
5. **Scheduling, queueing and presence.** "Run when awake,
   plugged in, idle," fair queues (uses 9 and 11), and a
   requester-visible queue position — email gives no presence
   signal.
6. **Attestation ergonomics.** Policy templates ("summary
   only," "catalogue only," "full log") a lay operator can
   choose correctly. The attestation here is disclosure
   governance; nothing on this page claims hardware-TEE
   guarantees (see use 14).
7. **Safety interlocks for physical actuation.** Any job that
   moves the physical world (uses 6, 7 and 9) needs a local
   human release step and device-level fail-safes outside the
   suite.

## The 5 most promising

The survey's ranking, with its reasons:

| Rank | Use | Why this one |
|---|---|---|
| 1 | Trusted-circle family tech support and accessibility delegation (uses 1 and 2) | The largest reachable audience in the developed world — nearly every technical person is someone's unpaid helpdesk, and current tools force an all-or-nothing privacy trade they actively resent (RustDesk's rise is the market signal). The jobs are small, safe, recurring, and demonstrable in one sitting. The accessibility framing adds institutional partners (charities, libraries' digital-inclusion programmes) that no homelab tool reaches. |
| 2 | Ham, disaster-response and off-grid communities (uses 3 and 4) | The only audience that already runs its life by store-and-forward email (Winlink, SailMail, Saildocs) and already owns the radios, batteries and patience for latency. They need zero behaviour change, they test harshly and publicly, and a credible showing there is the suite's best possible reference deployment. A small audience with outsized credibility. |
| 3 | Makerspace, library and school fabrication and remote-lab queues (uses 9 and 6, print and batch subset only) | Institutions with a queue, a shared inbox and a closed firewall today — the email-submission practice already exists, un-tooled. One deployment serves hundreds of requesters, produces visible artefacts, and is fundable by education and library grants. Start with 3D printing only; laser and CNC stay staff-released. |
| 4 | Bookkeeper-led small-business back-office (use 10) | The only use with a built-in distribution channel: one bookkeeper standardises a job pack and installs it across dozens of client businesses that will never visit a project page. Recurring (monthly) jobs, clear money value against per-document SaaS parsing, and data-stays-on-premises is a property owners understand at once. |
| 5 | Data-stays-put attested analysis (use 14 ★) | The smallest near-term audience and the largest strategic value: it is the one use no cloud service, remote-desktop tool or self-hosted CI runner can copy without becoming a different product, because attestation-limited disclosure is the offering. Even a handful of charity, research or audit pilots would mark out what the suite is for — the tool used when the data must not move — and draw privacy-conscious users to every other use. |

Sequencing, as the survey gives it: ranks 1 and 2 are launch
audiences (low risk, existing behaviour, fast feedback). Rank
5 is a positioning bet — pursue one careful pilot, not a
launch effort, and never oversell its assurance level.

## The survey's limits

- The suite itself was not inspected: its current feature
  completeness, its attestation mechanism (policy- and
  log-based, cryptographic, or hardware), its supported job
  formats and its mailbox polling model were taken solely from
  the description this page opens with. Every fit above is
  architectural inference from that description.
- No use above is evidence that this suite has been deployed
  for it; the grounding is documented adjacent practice (each
  use cites its own), which proves the workflow pattern, not
  this implementation.
- Email attachment and size limits, Winlink gateway policies
  on non-amateur content, and health and estate regulatory
  requirements vary by provider and jurisdiction and were not
  exhaustively verified — flagged in place where they gate a
  use.
- Whether the ★ uses are in fact unconsidered cannot be
  verified from the web; "least likely to have been considered
  already" is the survey's judgment, by their distance from
  the suite's described first uses (own-machine remote
  execution).

## Sources

Consulted 2026-11-08, in the order the survey cites them:

- UUCP store-and-forward remote execution —
  http://www.cs.cmu.edu/~dga/15-849/store_and_forward.html
- Low-tech internet / DakNet / KioskNet / DTN —
  https://a-nourishing-network.radical-openness.org/how-to-build-a-low-tech-internet.html
- NASA DTN overview —
  https://www.nasa.gov/technology/space-comms/dtn-overview-benefits-successstories-learningresources
- Winlink — https://en.wikipedia.org/wiki/Winlink
- Saildocs — http://saildocs.com ; Penpal for sailors —
  https://www.askpenpal.com/sailing
- TeleopLab — https://arxiv.org/html/2509.05547v1 ; RoboLab —
  https://repo.uni-hannover.de/items/3b3f6e6a-629a-4ca9-9e83-257abcdc9fd1
- BOINC —
  https://en.wikipedia.org/wiki/Berkeley_Open_Infrastructure_for_Network_Computing
- Sneakernet / El Paquete —
  https://en.wikipedia.org/wiki/Sneakernet
- Store-and-forward telemedicine (Alaska) —
  https://entokey.com/the-alaska-experience-using-store-and-forward-telemedicine-for-ent-care-in-alaska/ ;
  (Cambodia) —
  https://www.nucamp.co/blog/coding-bootcamp-cambodia-khm-healthcare-how-ai-is-helping-healthcare-companies-in-cambodia-cut-costs-and-improve-efficiency
- Zapier email triggers —
  https://help.zapier.com/hc/en-us/articles/8496292952973-Trigger-Zap-workflows-from-new-parsed-emails ;
  Parseur — https://parseur.com/blog/document-automation-small-business
- Digital estate / RUFADAA —
  https://www.docsats.com/blog/digital-executor-explained/ ;
  legacy tools / Inactive Account Manager —
  https://probate.help/archive/digital-legacy-tools/
- OctoPrint comparison —
  https://sourceforge.net/software/compare/OctoPrint-vs-Ultimaker-Cura-vs-ideaMaker/ ;
  library makerspace email STL submission —
  https://c2ae1c79-f5a6-4835-b863-87ce796cb903.filesusr.com/ugd/376e70_c5ea67c528ac40e1ba8689388a77b42b.pdf
- Home Assistant (self-hosting guide) —
  https://selfhosting.sh/apps/home-assistant/ ; second-home
  monitoring —
  https://www.home-securityguide.com/home-alarms/guides/monitoring-vacation-home-remotely/
- Be My Eyes —
  https://play.google.com/store/apps/details?id=com.bemyeyes.bemyeyes ;
  family remote help —
  https://divplanet.com/blog/how-to-help-your-parents-with-their-tech-over-the-holidays/ ;
  RustDesk family support —
  https://www.xda-developers.com/self-hosted-tool-makes-remote-tech-support-family-painless/
- Self-hosted GitHub Actions runners (no inbound port;
  remote-code-execution-by-design warning) —
  https://www.ssdnodes.com/learn/self-hosted-github-actions-runner
- Cuckoo Sandbox — https://www.cuckoosandbox.com/
- Offline education / Project NOMAD —
  https://digitalmatters.me/it-infrastructure/what-is-project-nomad/
- Offline farm irrigation — https://u2aiagro.com/ ;
  camera-trap network — https://www.mdpi.com/2079-9292/14/21/4266
- Attested execution / TEE analogue —
  https://iris.polito.it/retrieve/326c7593-414c-4746-b259-b752e0f42f28/2026_DLT__CameraReady.pdf ;
  https://chain.link/article/secure-onchain-execution-environment
- SecureDrop context (a use considered and set aside) —
  https://blog.pwnsy.com/what-is-the-dark-web
