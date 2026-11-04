# Findings — docs/steady/reports/doc-default-divergences.md

Source: docs/steady/reports/doc-default-divergences.md, reviewed at main 7247c1f0.
Sentence units: 154. Flagged: 4. Categories: pre-release 154, post-release 0.

The record of the defaults-divergence hunt: the reader table, the 72 divergence classes in a long table, and the fixes. The prose and the legend connect; the table structure is the only flag. All pre-release.

| # | Sentence (opening words) | Category | Verdict | Note |
|---|---|---|---|---|
| 1 | "<!-- Agent-Stamp: 10000c2a-1d4e-4f7b-8a2c-9e5d6f7a8b9c --> This report belongs to…" | pre-release | flows |  |
| 2 | "It is the record of the first VM…" | pre-release | flows |  |
| 3 | "Each finding is a test class in `tests/test_doc_default_divergences.py`…" | pre-release | flows |  |
| 4 | "The campaign's method and the plan for running…" | pre-release | flows |  |
| 5 | "Numbers at the release: 72 classes, 226 tests,…" | pre-release | flows |  |
| 6 | "All 226 pass on main from 40c428f." | pre-release | flows |  |
| 7 | "The 72 classes are 27 boolean cases, 32…" | pre-release | flows |  |
| 8 | "**A JSON boolean read as a number.** Python's…" | pre-release | flows |  |
| 9 | "**A huge integer, `inf` or `NaN` escaping as…" | pre-release | flows |  |
| 10 | "The example extensions carry most of these: a…" | pre-release | flows |  |
| 11 | "**A key present as `null`, a non-numeric string,…" | pre-release | flows |  |
| 12 | "The six bugs of their own:" | pre-release | flows |  |
| 13 | "`TestMissingSeverityDefaultsToInfoOnReadBack`: a stored alert with no severity was…" | pre-release | flows |  |
| 14 | "`TestUnrecognisedViewDefaultsToFull`: an unrecognised result view was echoed verbatim…" | pre-release | flows |  |
| 15 | "`TestBogusInferenceTimeoutDefaultsTo180`: the inference timeout fell back to 60…" | pre-release | flows |  |
| 16 | "`TestAskModelKeepAliveDefaultsTo30mOnOllama`: ask_model never sent keep_alive (the agent path…" | pre-release | flows |  |
| 17 | "`TestBadNatsPortDefaultsTo4222`: urlparse().port raised out of the NATS client…" | pre-release | flows |  |
| 18 | "`TestNullDtlsGreetingDefaultsToFamily`: a null or unknown dtls_greeting refused to…" | pre-release | flows |  |
| 19 | "`runner/confval.py` (586dfab, in 3.12.58) is the one answer…" | pre-release | flows |  |
| 20 | "A boolean is never a number there, a…" | pre-release | flows |  |
| 21 | "Every runner reader goes through it." | pre-release | flows |  |
| 22 | "`senses.py` and the transport channel keep their import-free…" | pre-release | flows |  |
| 23 | "| Reader | Classes |" | pre-release | flagged | A table header row — structure, not a sentence |
| 24 | "|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 25 | "| `runner/runner.py` | 16 |" | pre-release | flows |  |
| 26 | "| `runner/senses.py` | 5 |" | pre-release | flows |  |
| 27 | "| `runner/transport_extensions/dtls/__main__.py` | 4 |" | pre-release | flows |  |
| 28 | "| `examples/extensions/sky-watcher/sky_watcher.py` | 3 |" | pre-release | flows |  |
| 29 | "| `runner/detection.py` | 3 |" | pre-release | flows |  |
| 30 | "| `examples/extensions/latency-post/latency_post.py` | 2 |" | pre-release | flows |  |
| 31 | "| `runner/board.py` | 2 |" | pre-release | flows |  |
| 32 | "| `runner/dri.py` | 2 |" | pre-release | flows |  |
| 33 | "| `runner/learning.py` | 2 |" | pre-release | flows |  |
| 34 | "| `runner/resources.py` | 2 |" | pre-release | flows |  |
| 35 | "| `runner/transport_extensions/channel.py` | 2 |" | pre-release | flows |  |
| 36 | "| `runner/transport_extensions/email/__main__.py` | 2 |" | pre-release | flows |  |
| 37 | "| `runner/verify.py` | 2 |" | pre-release | flows |  |
| 38 | "| `examples/extensions/airwaves/airwaves.py` | 1 |" | pre-release | flows |  |
| 39 | "| `examples/extensions/backup-freshness/backup_freshness.py` | 1 |" | pre-release | flows |  |
| 40 | "| `examples/extensions/cert-sentinel/cert_sentinel.py` | 1 |" | pre-release | flows |  |
| 41 | "| `examples/extensions/crash-watch/crash_watch.py` | 1 |" | pre-release | flows |  |
| 42 | "| `examples/extensions/failed-login-watch/failed_login_watch.py` | 1 |" | pre-release | flows |  |
| 43 | "| `examples/extensions/falco-feed/falco_feed.py` | 1 |" | pre-release | flows |  |
| 44 | "| `examples/extensions/job-fuzz/job_fuzz.py` | 1 |" | pre-release | flows |  |
| 45 | "| `examples/extensions/job-watcher/job_watcher.py` | 1 |" | pre-release | flows |  |
| 46 | "| `examples/extensions/lab-results/lab_results.py` | 1 |" | pre-release | flows |  |
| 47 | "| `examples/extensions/log-sentinel/log_sentinel.py` | 1 |" | pre-release | flows |  |
| 48 | "| `examples/extensions/osquery-feed/osquery_feed.py` | 1 |" | pre-release | flows |  |
| 49 | "| `examples/extensions/pi-health/pi_health.py` | 1 |" | pre-release | flows |  |
| 50 | "| `examples/extensions/release-drop/release_drop.py` | 1 |" | pre-release | flows |  |
| 51 | "| `examples/extensions/resource-sentinel/resource_sentinel.py` | 1 |" | pre-release | flows |  |
| 52 | "| `examples/extensions/service-watch/service_watch.py` | 1 |" | pre-release | flows |  |
| 53 | "| `examples/extensions/softflowd-feed/softflowd_feed.py` | 1 |" | pre-release | flows |  |
| 54 | "| `examples/extensions/suricata-feed/suricata_feed.py` | 1 |" | pre-release | flows |  |
| 55 | "| `examples/extensions/training-watch/training_watch.py` | 1 |" | pre-release | flows |  |
| 56 | "| `examples/extensions/tripwire/tripwire.py` | 1 |" | pre-release | flows |  |
| 57 | "| `examples/extensions/wazuh-feed/wazuh_feed.py` | 1 |" | pre-release | flows |  |
| 58 | "| `examples/extensions/zeek-feed/zeek_feed.py` | 1 |" | pre-release | flows |  |
| 59 | "| `runner/mailbox.py` | 1 |" | pre-release | flows |  |
| 60 | "| `runner/protocol_v2.py` | 1 |" | pre-release | flows |  |
| 61 | "| `runner/review.py` | 1 |" | pre-release | flows |  |
| 62 | "| `runner/transport_extensions/nats/__main__.py` | 1 |" | pre-release | flows |  |
| 63 | "Shape: the value the hunt handed the reader." | pre-release | flows |  |
| 64 | "Doc: where the default is promised (first two…" | pre-release | flows |  |
| 65 | "Reader: the module the fix landed in." | pre-release | flows |  |
| 66 | "Tests: the class's test count." | pre-release | flows |  |
| 67 | "Fix: the commit." | pre-release | flows |  |
| 68 | "Every docstring carries the four parts the campaign…" | pre-release | flows |  |
| 69 | "| # | Class | Shape | Doc…" | pre-release | flagged | A table header row — structure, not a sentence |
| 70 | "|---|---|---|---|---|---|---|" | pre-release | flagged | A table separator row — pure structure, no prose at all |
| 71 | "| 1 | `TestMissingSeverityDefaultsToInfoOnReadBack` | present, not usable…" | pre-release | flows |  |
| 72 | "| 2 | `TestUnrecognisedViewDefaultsToFull` | present, not usable…" | pre-release | flows |  |
| 73 | "| 3 | `TestNullTaskTimeoutDefaultsTo86400` | present, not usable…" | pre-release | flows |  |
| 74 | "| 4 | `TestBogusInferenceTimeoutDefaultsTo180` | present, not usable…" | pre-release | flows |  |
| 75 | "| 5 | `TestNullDefaultTimeoutSecDefaultsTo300` | present, not usable…" | pre-release | flows |  |
| 76 | "| 6 | `TestNullDtlsPortBindDefaults` | present, not usable…" | pre-release | flows |  |
| 77 | "| 7 | `TestNullDtlsGreetingDefaultsToFamily` | present, not usable…" | pre-release | flows |  |
| 78 | "| 8 | `TestZeroOrNegativeMaxJobAgeDefaultsTo3600` | present, not usable…" | pre-release | flows |  |
| 79 | "| 9 | `TestZeroOrNegativePlanBudgetDefaults` | present, not usable…" | pre-release | flows |  |
| 80 | "| 10 | `TestNullDefaultTimeoutSecPassesKeyPolicy` | present, not usable…" | pre-release | flows |  |
| 81 | "| 11 | `TestInfinitePromoteAfterDefaultsTo2` | non-finite | `docs/configuring-oracle.md`,…" | pre-release | flows |  |
| 82 | "| 12 | `TestHugeSensorWeightDefaultsToOne` | non-finite | `docs/senses.md`…" | pre-release | flows |  |
| 83 | "| 13 | `TestHugeResourcesValueIsConfigError` | non-finite | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 84 | "| 14 | `TestAskModelKeepAliveDefaultsTo30mOnOllama` | semantic * |…" | pre-release | flows |  |
| 85 | "| 15 | `TestBooleanReviewScanBytesDefaultsTo65536` | boolean | `docs/configuring-oracle.md`,…" | pre-release | flows |  |
| 86 | "| 16 | `TestBooleanRetentionDaysDefaultsTo7` | boolean | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 87 | "| 17 | `TestBooleanV2AnswerDeadlineDefaultsTo0` | boolean | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 88 | "| 18 | `TestBooleanQueryBudgetDefaultsTo8` | boolean | `PROTOCOL.md`…" | pre-release | flows |  |
| 89 | "| 19 | `TestBooleanWakeCooldownDefaultsTo900` | boolean | `docs/extensions.md`…" | pre-release | flows |  |
| 90 | "| 20 | `TestBooleanMaxOutputBytesDefaultsTo100000` | boolean | `PROTOCOL.md`,…" | pre-release | flows |  |
| 91 | "| 21 | `TestBooleanPlanBudgetDefaults` | boolean | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 92 | "| 22 | `TestBooleanResourcesValuesAreConfigErrors` | boolean | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 93 | "| 23 | `TestBooleanPromoteAfterDefaultsTo2` | boolean | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 94 | "| 24 | `TestBooleanSensorCooldownDefaultsToZero` | boolean | `docs/senses.md`…" | pre-release | flows |  |
| 95 | "| 25 | `TestBooleanSensorMaxPerHourDefaultsToZero` | boolean | `docs/senses.md`…" | pre-release | flows |  |
| 96 | "| 26 | `TestBooleanDriValuesAreConfigErrors` | boolean | `docs/dri-playbook.md`…" | pre-release | flows |  |
| 97 | "| 27 | `TestBooleanMailboxPortIsConfigError` | boolean | `PROTOCOL.md`…" | pre-release | flows |  |
| 98 | "| 28 | `TestBooleanAgentWallClockDefaultsTo300` | boolean | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 99 | "| 29 | `TestBooleanTaskTimeoutDefaultsTo86400` | boolean | `docs/configuring-oracle.md`,…" | pre-release | flows |  |
| 100 | "| 30 | `TestBooleanPollIntervalDefaultsTo20` | boolean | `docs/FAQs.md`…" | pre-release | flows |  |
| 101 | "| 31 | `TestBooleanDtlsPortDefaultsTo20220` | boolean | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 102 | "| 32 | `TestBooleanMaxJobAgeDefaultsTo3600` | boolean | `PROTOCOL.md`…" | pre-release | flows |  |
| 103 | "| 33 | `TestBooleanDriWindowSecIsConfigError` | boolean | `docs/dri-playbook.md`…" | pre-release | flows |  |
| 104 | "| 34 | `TestHugeEmailPollIntervalDefaultsTo20` | non-finite | `docs/FAQs.md`,…" | pre-release | flows |  |
| 105 | "| 35 | `TestBadNatsPortDefaultsTo4222` | present, not usable…" | pre-release | flows |  |
| 106 | "| 36 | `TestBooleanDefaultTimeoutDefaultsTo300` | boolean | `PROTOCOL.md`,…" | pre-release | flows |  |
| 107 | "| 37 | `TestBadDtlsPortDefaultsTo20220` | present, not usable…" | pre-release | flows |  |
| 108 | "| 38 | `TestHugeExtensionPollIntervalDefaultsTo2` | non-finite | (docstring)…" | pre-release | flows |  |
| 109 | "| 39 | `TestBooleanExtensionPollIntervalDefaultsTo2` | boolean | (docstring)…" | pre-release | flows |  |
| 110 | "| 40 | `TestBooleanKeyPolicyMaxTimeoutIsConfigError` | boolean | `PROTOCOL.md`…" | pre-release | flows |  |
| 111 | "| 41 | `TestBooleanGrepMaxMatchesDefaultsTo10` | boolean | `PROTOCOL.md`,…" | pre-release | flows |  |
| 112 | "| 42 | `TestBooleanTailLinesDefaultsTo20` | boolean | `PROTOCOL.md`,…" | pre-release | flows |  |
| 113 | "| 43 | `TestBooleanSensesLimitDefaultsTo20` | boolean | `docs/senses.md`…" | pre-release | flows |  |
| 114 | "| 44 | `TestBooleanAskMaxCharsDefaultsTo2000` | boolean | `PROTOCOL.md`,…" | pre-release | flows |  |
| 115 | "| 45 | `TestBooleanPlanStepTimeoutCountsAs60` | boolean | `docs/configuring-oracle.md`…" | pre-release | flows |  |
| 116 | "| 46 | `TestNegativeOrNonFiniteSensorWeightDefaultsToOne` | non-finite | `docs/senses.md`…" | pre-release | flows |  |
| 117 | "| 47 | `TestNonFinitePiHealthTunableDefaults` | non-finite | `docs/extensions.md`…" | pre-release | flows |  |
| 118 | "| 48 | `TestNonFiniteAirwavesGoneAfterScansDefaultsTo3` | non-finite | `docs/extensions.md`…" | pre-release | flows |  |
| 119 | "| 49 | `TestNonFiniteSkyWatcherApproachRadiusDefaultsTo5000` | non-finite | `docs/extensions.md`…" | pre-release | flows |  |
| 120 | "| 50 | `TestNonFiniteSkyWatcherDarkThresholdDefaultsToMinus6` | non-finite | `docs/extensions.md`…" | pre-release | flows |  |
| 121 | "| 51 | `TestInfiniteCertSentinelDaysDefaults` | non-finite | `extension.json`,…" | pre-release | flows |  |
| 122 | "| 52 | `TestInfiniteLogSentinelTunablesCrashInsteadOfDefault` | non-finite | `examples/extensions/log-sentinel/README.md`,…" | pre-release | flows |  |
| 123 | "| 53 | `TestInfiniteTripwireTunablesCrashInsteadOfDefault` | non-finite | `examples/extensions/tripwire/README.md`,…" | pre-release | flows |  |
| 124 | "| 54 | `TestNonFiniteSkyWatcherLeadAndBrightDefaults` | non-finite | `docs/extensions.md`…" | pre-release | flows |  |
| 125 | "| 55 | `TestInfiniteBackupStaleAfterDefaultsTo90000` | non-finite | `examples/extensions/backup-freshness/README.md`,…" | pre-release | flows |  |
| 126 | "| 56 | `TestInfiniteCrashWatchRepeatWindowDefaultsTo3600` | non-finite | `examples/extensions/crash-watch/README.md`,…" | pre-release | flows |  |
| 127 | "| 57 | `TestInfiniteFailedLoginBurstCountDefaultsTo5` | non-finite | `examples/extensions/failed-login-watch/README.md`,…" | pre-release | flows |  |
| 128 | "| 58 | `TestInfiniteServiceWatchFlapCountDefaultsTo4` | non-finite | `examples/extensions/service-watch/README.md`,…" | pre-release | flows |  |
| 129 | "| 59 | `TestInfiniteJobWatcherRepeatFailuresDefaultsTo3` | non-finite | `examples/extensions/job-watcher/README.md`,…" | pre-release | flows |  |
| 130 | "| 60 | `TestNonFiniteResourceSentinelSampleCountsCrashInsteadOfDefault` | non-finite | `examples/extensions/resource-sentinel/README.md`,…" | pre-release | flows |  |
| 131 | "| 61 | `TestNonFiniteLabResultsTunablesDefaultInsteadOfCrashOrSilence` | non-finite | `examples/extensions/lab-results/README.md`,…" | pre-release | flows |  |
| 132 | "| 62 | `TestNonFiniteLatencyPostTunablesDefaultInsteadOfSilence` | non-finite | `examples/extensions/latency-post/README.md`,…" | pre-release | flows |  |
| 133 | "| 63 | `TestNonFiniteTrainingWatchTunablesDefaultInsteadOfSilenceOrCrash` | non-finite | `examples/extensions/training-watch/README.md`,…" | pre-release | flows |  |
| 134 | "| 64 | `TestInfiniteReleaseDropMaxHashDefaultsTo512` | non-finite | `examples/extensions/release-drop/README.md`,…" | pre-release | flows |  |
| 135 | "| 65 | `TestNonFiniteZeekFeedTunablesDefaultInsteadOfCrashOrBoundlessWindow` | non-finite | `examples/extensions/zeek-feed/README.md`,…" | pre-release | flows |  |
| 136 | "| 66 | `TestInfiniteFalcoCooldownDefaultsTo3600` | non-finite | `examples/extensions/falco-feed/README.md`,…" | pre-release | flows |  |
| 137 | "| 67 | `TestInfiniteSuricataCooldownDefaultsTo3600` | non-finite | `examples/extensions/suricata-feed/README.md`,…" | pre-release | flows |  |
| 138 | "| 68 | `TestInfiniteWazuhQuietDefaultsTo3600` | non-finite | `examples/extensions/wazuh-feed/README.md`,…" | pre-release | flows |  |
| 139 | "| 69 | `TestInfiniteOsqueryFiledCapCrashesInsteadOfDefault` | non-finite | `examples/extensions/osquery-feed/README.md`,…" | pre-release | flows |  |
| 140 | "| 70 | `TestNonFiniteSoftflowdTunablesDefaultInsteadOfCrashOrSilence` | non-finite | `examples/extensions/softflowd-feed/README.md`,…" | pre-release | flows |  |
| 141 | "| 71 | `TestHugeIntJobFuzzFloatTunablesCrashInsteadOfDefault` | non-finite | `examples/extensions/job-fuzz/README.md`,…" | pre-release | flows |  |
| 142 | "| 72 | `TestHugeIntLatencyPostTunablesCrashInsteadOfDefault` | non-finite | `examples/extensions/latency-post/README.md`,…" | pre-release | flows |  |
| 143 | "Three things stood between the fix and a…" | pre-release | flows |  |
| 144 | "**A test that ran a daemon in-process.** `tests/test_oracle_intake_fuzz.py`…" | pre-release | flows |  |
| 145 | "Once a bad tier read as the default…" | pre-release | flows |  |
| 146 | "Both CI suites sat past 80 minutes with…" | pre-release | flows |  |
| 147 | "Fixed in 4e4d117 (the test now checks that…" | pre-release | flows |  |
| 148 | "**A reader the first pass missed.** job-fuzz had…" | pre-release | flows |  |
| 149 | "40c428f." | pre-release | flows |  |
| 150 | "**A type annotation.** `runner/platformcard.py` (from the 3.12.57 queue)…" | pre-release | flows |  |
| 151 | "79c2bb7." | pre-release | flows |  |
| 152 | "The shapes are the reusable part: omitted; `null`;…" | pre-release | flows |  |
| 153 | "Every one of the 72 was one of…" | pre-release | flows |  |
| 154 | "A defaults registry (one row per documented key:…" | pre-release | flows |  |
