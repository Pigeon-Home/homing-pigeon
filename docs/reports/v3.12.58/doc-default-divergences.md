# Documented defaults: the 72 divergences and the fix
<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c -->
This report belongs to package 3.12.58. It is the record of the
first VM campaign's documented-default hunt (2026-10-22 to 23): every
place the documentation promised a default and the code, handed a
value that was present but not usable, delivered something else.
Each finding is a test class in `tests/test_doc_default_divergences.py`
that fails until the code is fixed and was not edited to pass; the
table below is generated from those classes' docstrings, so the
module is the primary record and this page is its index. The
campaign's method and the plan for running it again are in the
3.12.58 CHANGELOG entry and the campaign record-and-reuse plan.

Numbers at the release: 72 classes, 226 tests, 46 against the runner's
own readers and 26 against the standalone example extensions. All
226 pass on main from 40c428f.

## Three shapes and six bugs

The 72 classes are 27 boolean cases, 32 non-finite cases and 13
present-but-unusable cases; six of them (marked * below) were their
own bugs on top of the shape.

1. **A JSON boolean read as a number.** Python's `bool` is an `int`,
   so `true` was 1 and `false` 0 wherever a value met `int()` or
   `float()`: `poll_interval_sec: true` polled every second,
   `max_output_bytes: true` cut every result to one byte,
   `task_timeout: true` stripped claims in a second, `imap_port:
   false` was port 0.
2. **A huge integer, `inf` or `NaN` escaping as a raw exception.**
   The value reached `time.sleep`, `range`, `int()` or `float()`
   and left as `OverflowError` or `ValueError`, killing the loop or
   the extension that read it. The example extensions carry most of
   these: a `cooldown_sec` of `inf` was a quiet that never ended, a
   300-digit `corpus_max_age_days` crashed job-fuzz's `decide()`.
3. **A key present as `null`, a non-numeric string, zero or a
   negative number, used as is.** `cfg.get(key, default)` defaults
   only when the key is absent: `task_timeout: null` wedged claimed
   tasks forever, `default_timeout_sec: null` rejected every
   timeout-less job, `max_job_age_sec: 0` rejected everything, a
   null DTLS port killed the extension at startup.

The six bugs of their own:

- `TestMissingSeverityDefaultsToInfoOnReadBack`: a stored alert with no severity was dropped by the info floor on read-back.
- `TestUnrecognisedViewDefaultsToFull`: an unrecognised result view was echoed verbatim instead of reading as full.
- `TestBogusInferenceTimeoutDefaultsTo180`: the inference timeout fell back to 60 where the docs say 180.
- `TestAskModelKeepAliveDefaultsTo30mOnOllama`: ask_model never sent keep_alive (the agent path did).
- `TestBadNatsPortDefaultsTo4222`: urlparse().port raised out of the NATS client before its reconnect loop.
- `TestNullDtlsGreetingDefaultsToFamily`: a null or unknown dtls_greeting refused to start instead of reading as family.

## The fix

`runner/confval.py` (586dfab, in 3.12.58) is the one answer to "is
this a usable number, and if not, what do I use": `number`,
`integer`, `port` and `choice` return the documented default for
anything not usable, and `is_number` is the gate where a module
documents a startup config error instead (resources, DRI, mailbox
ports, key policies). A boolean is never a number there, a number
must be finite, and bounds decide what is usable. Every runner
reader goes through it. `senses.py` and the transport channel keep
their import-free posture with the same rule written locally, and
all 28 example extensions carry it in their own `_is_number`
(job-fuzz's arrived in 40c428f, the one reader the first pass
missed, found by the two classes that landed after it).

| Reader | Classes |
|---|---|
| `runner/runner.py` | 16 |
| `runner/senses.py` | 5 |
| `runner/transport_extensions/dtls/__main__.py` | 4 |
| `examples/extensions/sky-watcher/sky_watcher.py` | 3 |
| `runner/detection.py` | 3 |
| `examples/extensions/latency-post/latency_post.py` | 2 |
| `runner/board.py` | 2 |
| `runner/dri.py` | 2 |
| `runner/learning.py` | 2 |
| `runner/resources.py` | 2 |
| `runner/transport_extensions/channel.py` | 2 |
| `runner/transport_extensions/email/__main__.py` | 2 |
| `runner/verify.py` | 2 |
| `examples/extensions/airwaves/airwaves.py` | 1 |
| `examples/extensions/backup-freshness/backup_freshness.py` | 1 |
| `examples/extensions/cert-sentinel/cert_sentinel.py` | 1 |
| `examples/extensions/crash-watch/crash_watch.py` | 1 |
| `examples/extensions/failed-login-watch/failed_login_watch.py` | 1 |
| `examples/extensions/falco-feed/falco_feed.py` | 1 |
| `examples/extensions/job-fuzz/job_fuzz.py` | 1 |
| `examples/extensions/job-watcher/job_watcher.py` | 1 |
| `examples/extensions/lab-results/lab_results.py` | 1 |
| `examples/extensions/log-sentinel/log_sentinel.py` | 1 |
| `examples/extensions/osquery-feed/osquery_feed.py` | 1 |
| `examples/extensions/pi-health/pi_health.py` | 1 |
| `examples/extensions/release-drop/release_drop.py` | 1 |
| `examples/extensions/resource-sentinel/resource_sentinel.py` | 1 |
| `examples/extensions/service-watch/service_watch.py` | 1 |
| `examples/extensions/softflowd-feed/softflowd_feed.py` | 1 |
| `examples/extensions/suricata-feed/suricata_feed.py` | 1 |
| `examples/extensions/training-watch/training_watch.py` | 1 |
| `examples/extensions/tripwire/tripwire.py` | 1 |
| `examples/extensions/wazuh-feed/wazuh_feed.py` | 1 |
| `examples/extensions/zeek-feed/zeek_feed.py` | 1 |
| `runner/mailbox.py` | 1 |
| `runner/protocol_v2.py` | 1 |
| `runner/review.py` | 1 |
| `runner/transport_extensions/nats/__main__.py` | 1 |

## The 72 classes

Shape: the value the hunt handed the reader. Doc: where the default
is promised (first two sources named by the docstring). Reader: the
module the fix landed in. Tests: the class's test count. Fix: the
commit. Every docstring carries the four parts the campaign used:
the claim with its location, how it was found, what was observed,
and that the test passes only when the code is fixed.

| # | Class | Shape | Doc | Reader | Tests | Fix |
|---|---|---|---|---|---|---|
| 1 | `TestMissingSeverityDefaultsToInfoOnReadBack` | present, not usable * | `docs/senses.md` | `runner/senses.py` | 2 | 586dfab |
| 2 | `TestUnrecognisedViewDefaultsToFull` | present, not usable * | `PROTOCOL.md`, `docs/configuring-oracle.md` | `runner/runner.py` | 2 | 586dfab |
| 3 | `TestNullTaskTimeoutDefaultsTo86400` | present, not usable | `docs/configuring-oracle.md`, `PROTOCOL.md` | `runner/board.py` | 2 | 586dfab |
| 4 | `TestBogusInferenceTimeoutDefaultsTo180` | present, not usable * | `PROTOCOL.md`, `docs/configuring-oracle.md` | `runner/runner.py` | 5 | 586dfab |
| 5 | `TestNullDefaultTimeoutSecDefaultsTo300` | present, not usable | `PROTOCOL.md`, `docs/configuring-oracle.md` | `runner/runner.py` | 2 | 586dfab |
| 6 | `TestNullDtlsPortBindDefaults` | present, not usable | `docs/configuring-oracle.md` | `runner/transport_extensions/dtls/__main__.py` | 3 | 586dfab |
| 7 | `TestNullDtlsGreetingDefaultsToFamily` | present, not usable * | `docs/configuring-oracle.md` | `runner/transport_extensions/dtls/__main__.py` | 2 | 586dfab |
| 8 | `TestZeroOrNegativeMaxJobAgeDefaultsTo3600` | present, not usable | `PROTOCOL.md` | `runner/runner.py` | 2 | 586dfab |
| 9 | `TestZeroOrNegativePlanBudgetDefaults` | present, not usable | `docs/configuring-oracle.md` | `runner/detection.py` | 4 | 586dfab |
| 10 | `TestNullDefaultTimeoutSecPassesKeyPolicy` | present, not usable | `PROTOCOL.md`, `docs/configuring-oracle.md` | `runner/verify.py` | 2 | 586dfab |
| 11 | `TestInfinitePromoteAfterDefaultsTo2` | non-finite | `docs/configuring-oracle.md`, `docs/design/oracle-opinion-design.md` | `runner/learning.py` | 2 | 586dfab |
| 12 | `TestHugeSensorWeightDefaultsToOne` | non-finite | `docs/senses.md` | `runner/senses.py` | 2 | 586dfab |
| 13 | `TestHugeResourcesValueIsConfigError` | non-finite | `docs/configuring-oracle.md` | `runner/resources.py` | 3 | 586dfab |
| 14 | `TestAskModelKeepAliveDefaultsTo30mOnOllama` | semantic * | `docs/configuring-oracle.md` | `runner/runner.py` | 2 | 586dfab |
| 15 | `TestBooleanReviewScanBytesDefaultsTo65536` | boolean | `docs/configuring-oracle.md`, `docs/job-review.md` | `runner/review.py` | 1 | 586dfab |
| 16 | `TestBooleanRetentionDaysDefaultsTo7` | boolean | `docs/configuring-oracle.md` | `runner/runner.py` | 2 | 586dfab |
| 17 | `TestBooleanV2AnswerDeadlineDefaultsTo0` | boolean | `docs/configuring-oracle.md` | `runner/protocol_v2.py` | 1 | 586dfab |
| 18 | `TestBooleanQueryBudgetDefaultsTo8` | boolean | `PROTOCOL.md` | `runner/runner.py` | 4 | 586dfab |
| 19 | `TestBooleanWakeCooldownDefaultsTo900` | boolean | `docs/extensions.md` | `runner/runner.py` | 2 | 586dfab |
| 20 | `TestBooleanMaxOutputBytesDefaultsTo100000` | boolean | `PROTOCOL.md`, `docs/configuring-oracle.md` | `runner/runner.py` | 1 | 586dfab |
| 21 | `TestBooleanPlanBudgetDefaults` | boolean | `docs/configuring-oracle.md` | `runner/detection.py` | 4 | 586dfab |
| 22 | `TestBooleanResourcesValuesAreConfigErrors` | boolean | `docs/configuring-oracle.md` | `runner/resources.py` | 3 | 586dfab |
| 23 | `TestBooleanPromoteAfterDefaultsTo2` | boolean | `docs/configuring-oracle.md` | `runner/learning.py` | 1 | 586dfab |
| 24 | `TestBooleanSensorCooldownDefaultsToZero` | boolean | `docs/senses.md` | `runner/senses.py` | 1 | 586dfab |
| 25 | `TestBooleanSensorMaxPerHourDefaultsToZero` | boolean | `docs/senses.md` | `runner/senses.py` | 1 | 586dfab |
| 26 | `TestBooleanDriValuesAreConfigErrors` | boolean | `docs/dri-playbook.md` | `runner/dri.py` | 5 | 586dfab |
| 27 | `TestBooleanMailboxPortIsConfigError` | boolean | `PROTOCOL.md` | `runner/mailbox.py` | 4 | 586dfab |
| 28 | `TestBooleanAgentWallClockDefaultsTo300` | boolean | `docs/configuring-oracle.md` | `runner/runner.py` | 2 | 586dfab |
| 29 | `TestBooleanTaskTimeoutDefaultsTo86400` | boolean | `docs/configuring-oracle.md`, `docs/SAFEGUARDS.md` | `runner/board.py` | 3 | 586dfab |
| 30 | `TestBooleanPollIntervalDefaultsTo20` | boolean | `docs/FAQs.md` | `runner/transport_extensions/email/__main__.py` | 3 | 586dfab |
| 31 | `TestBooleanDtlsPortDefaultsTo20220` | boolean | `docs/configuring-oracle.md` | `runner/transport_extensions/dtls/__main__.py` | 2 | 586dfab |
| 32 | `TestBooleanMaxJobAgeDefaultsTo3600` | boolean | `PROTOCOL.md` | `runner/runner.py` | 2 | 586dfab |
| 33 | `TestBooleanDriWindowSecIsConfigError` | boolean | `docs/dri-playbook.md` | `runner/dri.py` | 5 | 586dfab |
| 34 | `TestHugeEmailPollIntervalDefaultsTo20` | non-finite | `docs/FAQs.md`, `docs/configuring-oracle.md` | `runner/transport_extensions/email/__main__.py` | 2 | 586dfab |
| 35 | `TestBadNatsPortDefaultsTo4222` | present, not usable * | `docs/configuring-oracle.md` | `runner/transport_extensions/nats/__main__.py` | 4 | 586dfab |
| 36 | `TestBooleanDefaultTimeoutDefaultsTo300` | boolean | `PROTOCOL.md`, `docs/configuring-oracle.md` | `runner/runner.py` | 3 | 586dfab |
| 37 | `TestBadDtlsPortDefaultsTo20220` | present, not usable | `docs/configuring-oracle.md`, `docs/TRANSPORTS.md` | `runner/transport_extensions/dtls/__main__.py` | 5 | 586dfab |
| 38 | `TestHugeExtensionPollIntervalDefaultsTo2` | non-finite | (docstring) | `runner/transport_extensions/channel.py` | 2 | 586dfab |
| 39 | `TestBooleanExtensionPollIntervalDefaultsTo2` | boolean | (docstring) | `runner/transport_extensions/channel.py` | 2 | 586dfab |
| 40 | `TestBooleanKeyPolicyMaxTimeoutIsConfigError` | boolean | `PROTOCOL.md` | `runner/verify.py` | 3 | 586dfab |
| 41 | `TestBooleanGrepMaxMatchesDefaultsTo10` | boolean | `PROTOCOL.md`, `docs/fuzzing.md` | `runner/runner.py` | 4 | 586dfab |
| 42 | `TestBooleanTailLinesDefaultsTo20` | boolean | `PROTOCOL.md`, `docs/fuzzing.md` | `runner/runner.py` | 4 | 586dfab |
| 43 | `TestBooleanSensesLimitDefaultsTo20` | boolean | `docs/senses.md` | `runner/runner.py` | 4 | 586dfab |
| 44 | `TestBooleanAskMaxCharsDefaultsTo2000` | boolean | `PROTOCOL.md`, `docs/configuring-oracle.md` | `runner/runner.py` | 4 | 586dfab |
| 45 | `TestBooleanPlanStepTimeoutCountsAs60` | boolean | `docs/configuring-oracle.md` | `runner/detection.py` | 5 | 586dfab |
| 46 | `TestNegativeOrNonFiniteSensorWeightDefaultsToOne` | non-finite | `docs/senses.md` | `runner/senses.py` | 8 | 586dfab |
| 47 | `TestNonFinitePiHealthTunableDefaults` | non-finite | `docs/extensions.md` | `examples/extensions/pi-health/pi_health.py` | 5 | 586dfab |
| 48 | `TestNonFiniteAirwavesGoneAfterScansDefaultsTo3` | non-finite | `docs/extensions.md` | `examples/extensions/airwaves/airwaves.py` | 5 | 586dfab |
| 49 | `TestNonFiniteSkyWatcherApproachRadiusDefaultsTo5000` | non-finite | `docs/extensions.md` | `examples/extensions/sky-watcher/sky_watcher.py` | 4 | 586dfab |
| 50 | `TestNonFiniteSkyWatcherDarkThresholdDefaultsToMinus6` | non-finite | `docs/extensions.md` | `examples/extensions/sky-watcher/sky_watcher.py` | 4 | 586dfab |
| 51 | `TestInfiniteCertSentinelDaysDefaults` | non-finite | `extension.json`, `docs/extensions.md` | `examples/extensions/cert-sentinel/cert_sentinel.py` | 3 | 586dfab |
| 52 | `TestInfiniteLogSentinelTunablesCrashInsteadOfDefault` | non-finite | `examples/extensions/log-sentinel/README.md`, `extension.json` | `examples/extensions/log-sentinel/log_sentinel.py` | 4 | 586dfab |
| 53 | `TestInfiniteTripwireTunablesCrashInsteadOfDefault` | non-finite | `examples/extensions/tripwire/README.md`, `extension.json` | `examples/extensions/tripwire/tripwire.py` | 3 | 586dfab |
| 54 | `TestNonFiniteSkyWatcherLeadAndBrightDefaults` | non-finite | `docs/extensions.md` | `examples/extensions/sky-watcher/sky_watcher.py` | 6 | 586dfab |
| 55 | `TestInfiniteBackupStaleAfterDefaultsTo90000` | non-finite | `examples/extensions/backup-freshness/README.md`, `extension.json` | `examples/extensions/backup-freshness/backup_freshness.py` | 2 | 586dfab |
| 56 | `TestInfiniteCrashWatchRepeatWindowDefaultsTo3600` | non-finite | `examples/extensions/crash-watch/README.md`, `extension.json` | `examples/extensions/crash-watch/crash_watch.py` | 2 | 586dfab |
| 57 | `TestInfiniteFailedLoginBurstCountDefaultsTo5` | non-finite | `examples/extensions/failed-login-watch/README.md`, `extension.json` | `examples/extensions/failed-login-watch/failed_login_watch.py` | 2 | 586dfab |
| 58 | `TestInfiniteServiceWatchFlapCountDefaultsTo4` | non-finite | `examples/extensions/service-watch/README.md`, `extension.json` | `examples/extensions/service-watch/service_watch.py` | 2 | 586dfab |
| 59 | `TestInfiniteJobWatcherRepeatFailuresDefaultsTo3` | non-finite | `examples/extensions/job-watcher/README.md`, `extension.json` | `examples/extensions/job-watcher/job_watcher.py` | 4 | 586dfab |
| 60 | `TestNonFiniteResourceSentinelSampleCountsCrashInsteadOfDefault` | non-finite | `examples/extensions/resource-sentinel/README.md`, `extension.json` | `examples/extensions/resource-sentinel/resource_sentinel.py` | 6 | 586dfab |
| 61 | `TestNonFiniteLabResultsTunablesDefaultInsteadOfCrashOrSilence` | non-finite | `examples/extensions/lab-results/README.md`, `extension.json` | `examples/extensions/lab-results/lab_results.py` | 3 | 586dfab |
| 62 | `TestNonFiniteLatencyPostTunablesDefaultInsteadOfSilence` | non-finite | `examples/extensions/latency-post/README.md`, `extension.json` | `examples/extensions/latency-post/latency_post.py` | 5 | 586dfab |
| 63 | `TestNonFiniteTrainingWatchTunablesDefaultInsteadOfSilenceOrCrash` | non-finite | `examples/extensions/training-watch/README.md`, `extension.json` | `examples/extensions/training-watch/training_watch.py` | 7 | 586dfab |
| 64 | `TestInfiniteReleaseDropMaxHashDefaultsTo512` | non-finite | `examples/extensions/release-drop/README.md`, `extension.json` | `examples/extensions/release-drop/release_drop.py` | 3 | 586dfab |
| 65 | `TestNonFiniteZeekFeedTunablesDefaultInsteadOfCrashOrBoundlessWindow` | non-finite | `examples/extensions/zeek-feed/README.md`, `extension.json` | `examples/extensions/zeek-feed/zeek_feed.py` | 5 | 586dfab |
| 66 | `TestInfiniteFalcoCooldownDefaultsTo3600` | non-finite | `examples/extensions/falco-feed/README.md`, `extension.json` | `examples/extensions/falco-feed/falco_feed.py` | 2 | 586dfab |
| 67 | `TestInfiniteSuricataCooldownDefaultsTo3600` | non-finite | `examples/extensions/suricata-feed/README.md`, `extension.json` | `examples/extensions/suricata-feed/suricata_feed.py` | 2 | 586dfab |
| 68 | `TestInfiniteWazuhQuietDefaultsTo3600` | non-finite | `examples/extensions/wazuh-feed/README.md`, `extension.json` | `examples/extensions/wazuh-feed/wazuh_feed.py` | 2 | 586dfab |
| 69 | `TestInfiniteOsqueryFiledCapCrashesInsteadOfDefault` | non-finite | `examples/extensions/osquery-feed/README.md`, `extension.json` | `examples/extensions/osquery-feed/osquery_feed.py` | 2 | 586dfab |
| 70 | `TestNonFiniteSoftflowdTunablesDefaultInsteadOfCrashOrSilence` | non-finite | `examples/extensions/softflowd-feed/README.md`, `extension.json` | `examples/extensions/softflowd-feed/softflowd_feed.py` | 5 | 586dfab |
| 71 | `TestHugeIntJobFuzzFloatTunablesCrashInsteadOfDefault` | non-finite | `examples/extensions/job-fuzz/README.md`, `extension.json` | `examples/extensions/job-fuzz/job_fuzz.py` | 3 | 40c428f |
| 72 | `TestHugeIntLatencyPostTunablesCrashInsteadOfDefault` | non-finite | `examples/extensions/latency-post/README.md`, `extension.json` | `examples/extensions/latency-post/latency_post.py` | 3 | 586dfab |

## What the release cost that the hunt did not predict

Three things stood between the fix and a green build, and all three
are in the record because the next campaign will meet their kind
again.

- **A test that ran a daemon in-process.** `tests/test_oracle_intake_fuzz.py`
  called the DTLS extension's `main()` with a list for the tier and
  expected exit 2. Once a bad tier read as the default and the
  extension started, that call bound udp 20220 and looped forever.
  Both CI suites sat past 80 minutes with nothing in the log; the
  module imports hypothesis, which the diagnosing seat could not
  install, so the local suite skipped it. Fixed in 4e4d117 (the test
  now checks that `main()` reaches its loop on the default tier with
  the listener stood in for), and the suites now run under
  `tools/suite_wall_clock.py`, which stops a run at 20 minutes and
  names the test it was in.
- **A reader the first pass missed.** job-fuzz had its own
  `_is_number` without the huge-integer guard; two classes landed
  after the fix and said so. 40c428f.
- **A type annotation.** `runner/platformcard.py` (from the 3.12.57
  queue) declared `build_card -> dict` and returned `None` at tier
  `none`; typecheck had not run on main since that queue landed,
  because it waits on a green `test`. 79c2bb7.

## Reading this again

The shapes are the reusable part: omitted; `null`; the empty string;
`true` and `false`; zero; a negative number; the documented default
written explicitly; a numeric string; a non-numeric string; a
300-digit integer; `inf`, `-inf` and `NaN`; the wrong container type;
and for enums the right word in the wrong case or with whitespace.
Every one of the 72 was one of these against one key. A defaults
registry (one row per documented key: doc file and line, default,
reader, policy, bounds, test) is what makes the hunt table-driven
next time; until it exists, this table and the docstrings are that
registry by hand.
