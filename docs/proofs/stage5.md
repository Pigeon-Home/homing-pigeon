# Stage 5 — the clauses, named, and the mutation check

Stage 5 is done on the terms `GOALS.md` sets. Every clause of
P1 through P6 names at least one test that drives the real
code, the family passes, and a one-line change in a scratch
copy of each property was caught. The scratch copies were
restored. Nothing in the runner's behaviour changed.

## The family

`runner/tests/test_proof_conformance.py` drives `handle_mail`
and the NATS start. `runner/tests/test_proof_constraints.py`
drives the readers the later properties name: the policy
step, the result ceiling, the claim file, the record, and
the configuration split. A few refusal steps already had a
`handle_mail` test in `runner/tests/test_coverage_floor.py`;
those are named here rather than copied.

### P1, the gate

| Clause | Test |
|---|---|
| 1. Raw size | `test_an_over_cap_raw_message_does_not_execute` |
| 2. Signature | `test_an_unsigned_body_does_not_execute`, `test_c5_tampered_body_is_refused` |
| 3. Cleartext and the one AEAD | `test_cleartext_does_not_execute_or_consume_the_id`, `test_c9_encrypted_round_trip_and_wrong_alg_refused` |
| 4. Audience, enforce and off | `test_the_wrong_audience_is_refused_when_enforced`, `test_the_wrong_audience_executes_when_the_check_is_off` |
| 5. Script cap, over and at | `test_a_script_over_the_cap_does_not_execute`, `test_a_script_at_the_cap_does_execute` |
| 6. Version, type, identity | `test_a_bad_version_a_bad_type_and_a_mismatched_id_do_not_execute` |
| 7. Freshness | `test_a_stale_job_and_a_future_job_do_not_execute` |
| 8. Key policy and pinned constraints | `test_a_key_policy_forbids_the_kind`, `test_a_denied_environment_name_is_refused` |
| 9. The claim and the record | `test_an_id_already_seen_is_not_executed`, `test_a_job_another_worker_already_claimed_is_not_run`, `test_a_record_is_resent_and_not_executed` |

The check-order steps that are not one of those nine have a
test too. Panic: `test_the_panic_word_executes_nothing`.
Encodability: `test_a_lone_surrogate_in_the_job_is_refused`.
Sensor: `test_a_sensor_alert_is_not_script_execution`. Dry
run: `test_a_dry_run_does_not_execute`. A good encrypted ping
does execute: `test_a_good_encrypted_ping_does_execute`, so
the family is not a set of tests that pass by refusing
everything.

A refused cleartext job does not consume the id. That is
checked, not only the refusal.

### P2, confinement

| Clause | Test |
|---|---|
| 1. Sandbox decision is the owner's | `test_c18_no_job_field_names_a_confinement_setting` |
| 2. Writable set | `test_c18_work_mount_and_fixed_flags` |
| 3. The one prefix bind | `test_c18_interpreter_prefix_rule` |
| 4. Watched set | `test_c17_confined_attestation_reports_the_runners_value` |
| 5. View is the narrower | `test_c17_a_job_cannot_widen_past_the_ceiling`, `test_c17_narrowing_takes_effect` |
| 6. Budget is the smaller | `test_c17_query_budget_is_the_smaller_of_the_two` |
| 7. Redaction is the runner's | `test_c17_job_redact_patterns_are_never_read` |
| 8. Answers are runner-computed | `test_c17_confined_attestation_reports_the_runners_value` |
| 9. Named fields do nothing | `test_c18_no_job_field_names_a_confinement_setting` |

### P3, the transport gate

| Clause | Test |
|---|---|
| 1–3. Order, and neither gate alone | `test_c19_queues_edge_checks_bearer_before_signature` |
| 4. Email has no sender gate | `test_c20_channel_envelopes_face_the_core_gate` |
| 5. File is the operating system's | `test_c20_file_extension_has_no_credential_of_its_own` |
| 6. NATS | `test_nats_without_credentials_refuses_to_start` |
| 7. DTLS | `test_c20_dtls_no_secret_no_start_and_established_only` |
| 8. Queues | `test_c19_queues_extension_refuses_to_start_tokenless` |
| 9. A waived gate | `test_c20_nats_credentials_required_unless_literal_true` |

The file, DTLS, and queues pins read the code at the site.
They do not open a broker or a datagram. P3's own record
already says those gates are only as strong as the operating
system, the broker, and the edge. The new NATS test does
call the constructor, and a missing credential refuses the
start.

### P4, the key policy

| Clause | Test |
|---|---|
| 1. The key that verified | `test_c14_policy_is_the_keys_not_the_names` |
| 2. Directory first | `test_c21_directory_speaks_before_the_policy` |
| 3. No entry | `test_c14_no_entry_unrestricted_unless_default_deny` |
| 4. The policy is the key's | `test_c14_policy_is_the_keys_not_the_names` |
| 5. Kinds | `test_c14_kinds_fence_refuses_every_other_kind` |
| 6. Recipes and interpreters | `test_c14_recipes_and_interpreters_fences` |
| 7. Timeout | `test_c14_timeout_cap_binds_the_pinned_key` |
| 8. Script pinning | `test_c22_upgrade_key_accepts_only_the_pinned_script`, `test_c14_pinning_refuses_url_missing_and_beside` |
| 9. Other doors | `test_c14_door_policy_binds_the_other_doors` |
| 10. Repair re-judged | `test_a_repaired_interpreter_the_key_forbids_does_not_execute` |
| 11. Mode-gated surround | `test_a_denied_environment_name_is_refused` |
| 12. Malformed policy | `test_c14_build_validates_and_lowercases`, `test_c14_build_refuses_one_key_entered_twice` |

### P5, replay

| Clause | Test |
|---|---|
| 1. At most once | `test_a_record_is_resent_and_not_executed` |
| 2. Cache first | `test_an_id_already_seen_is_not_executed`, `test_c23_seen_write_drops_entries_past_the_horizon` |
| 3. Both halves of the claim | `test_a_job_another_worker_already_claimed_is_not_run`, `test_c24_disk_claim_live_dead_and_unreadable` |
| 4. A dead holder is stealable | `test_c24_disk_claim_live_dead_and_unreadable` |
| 5. The record answers | `test_c15_record_answers_only_its_own_job` |
| 6. A different job under the id | `test_c15_record_answers_only_its_own_job` |
| 7. The crash window | `test_c24_disk_claim_live_dead_and_unreadable` |
| 8. The cache outlasts freshness | `test_c23_seen_keep_horizon_outlasts_freshness` |
| 9. The record's window | `test_c25_retention_and_stash_window_defaults` |
| 10. Delivery inside the stash | `test_c15_record_answers_only_its_own_job` |
| 11. Restart | `test_c24_disk_claim_live_dead_and_unreadable` |

Clause 10's "eventually delivered" half is the code's stash
and the model's marker. No test here opens a transport and
waits. That limit is the one `stage4-p5.md` already states.

### P6, the configuration split

| Clause | Test |
|---|---|
| 1. Absent is not named | `test_a_bool_is_not_a_number_and_an_absent_key_is_not_named` |
| 2. Usable is used | `test_a_bool_is_not_a_number_and_an_absent_key_is_not_named` |
| 3. Unusable default class | `test_a_bool_is_not_a_number_and_an_absent_key_is_not_named` |
| 4. Unusable refuse class | `test_a_bad_size_cap_and_a_bad_port_name_themselves` |
| 5. Live reload of a default | `test_a_live_reload_defaults_a_tunable_and_leaves_a_port` |
| 6. Refuse class is not reloaded | `test_a_live_reload_defaults_a_tunable_and_leaves_a_port` |
| 7. A bad file is retried | `test_a_bad_file_is_retried_next_cycle` |

## The mutation check

One line was changed in a scratch copy, the named test was
run, and the file was restored. Each run exited 1. A family
that stayed green would have been decoration. None did.

| Property | The one line | The test that failed |
|---|---|---|
| P1 | the cleartext refusal skipped | `test_cleartext_does_not_execute_or_consume_the_id` |
| P2 | the view ceiling ignored, so the job's view wins | `test_c17_a_job_cannot_widen_past_the_ceiling` |
| P3 | the NATS missing-credential refusal skipped | `test_nats_without_credentials_refuses_to_start` |
| P4 | the kinds fence skipped | `test_c14_kinds_fence_refuses_every_other_kind` |
| P5 | the record's digest comparison skipped | `test_c15_record_answers_only_its_own_job` |
| P6 | a boolean accepted as a number | `test_a_bool_is_not_a_number_and_an_absent_key_is_not_named` |

The copies were not committed. `git diff` after the six runs
showed only this stage's tests.
