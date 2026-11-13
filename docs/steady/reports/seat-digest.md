# Seat digest: where the work went

A reading of the repository's own history, per author, one window
at a time: the commits, the lines, the files the lines went to and
their share, the commits by kind, the questions filed and who they
were addressed to, the longest chain of questions that each carry
the residual of the one before, and the hours a question one seat
asked another waited for the other seat's first commit naming it.

The tool is `runner/tools/seat_digest.py`:

    python3 runner/tools/seat_digest.py --hours 72 --until 2026-11-13T03:00:00Z --seat Muse --seat Claude

It is the release train's `clock` turned on the work itself. The
release cycle went from hours of attention to minutes once each
cycle's timeline was read from the hosted record instead of from
memory (docs/steady/reports/ci-failures.md); this page is the same
move for what a seat's hours go to. The digest decides nothing: it
prints what the history holds, so that a change of direction can
be read against the window before it and the window after it.

## The first two readings (13 Nov 2026)

The 72 hours to 10 Nov 03:00Z:

```
seat digest: 2026-11-07T03:00:00Z .. 2026-11-10T03:00:00Z
Muse: 157 commits, 48,873 lines added, 4,676 deleted
     10.9%      5,305  runner/tests/de_dust/dtls.arcs.json
      8.2%      4,003  runner/tests/de_dust/dtls_session.arcs.json
      7.0%      3,440  runner/tests/de_dust/runs.jsonl
      6.7%      3,273  runner/tests/de_dust/dtls_hostile.arcs.json
      3.1%      1,504  runner/tests/de_dust/v2_mail.arcs.json
      2.7%      1,316  runner/tests/de_dust/query.arcs.json
      1.7%        821  runner/tests/de_dust/keydir.arcs.json
      1.6%        763  runner/tests/test_disclosure.py
    by kind: docs 65, release 31, other 9, tools 7, fix 6, tests 5, proofs 5, chore 4
Claude: 2 commits, 1,842 lines added, 207 deleted
     25.0%        461  runner/tests/test_dtls_rfc9147_wire.py
     21.2%        390  runner/wire/dtlsproto.py
     11.2%        207  docs/infrastructure-documents/proofs/dtls-record-layer-and-framing.md
     10.2%        188  runner/tests/test_dtls_email_v3_messages.py
     10.0%        185  runner/tests/test_draft_alignment.py
      3.1%         57  runner/tests/test_dtls.py
      3.0%         55  runner/wire/dtls_mailbox.py
      2.2%         40  docs/infrastructure-documents/design/v3-dtls-over-email-plan.md
    by kind: tests 1, dtls 1
questions filed in the window: 13 (Muse -> self 13)
longest chain of residual questions: 2, Q143 .. Q144
```

The 72 hours to 13 Nov 03:00Z:

```
seat digest: 2026-11-10T03:00:00Z .. 2026-11-13T03:00:00Z
Muse: 409 commits, 161,089 lines added, 6,410 deleted
     51.7%     83,210  runner/tests/test_briefing_contradiction.py
     17.4%     27,975  docs/infrastructure-documents/project/desk.md
      7.3%     11,812  docs/steady/seats/questions.md
      4.0%      6,404  runner/tests/de_dust/runs.jsonl
      2.4%      3,929  runner/ops/briefing.py
      1.2%      1,942  runner/tools/windows_durations.json
      1.1%      1,780  runner/tests/test_macos_confine.py
      1.1%      1,693  docs/steady/security/macos.md
    by kind: desk 180, docs 40, figures 38, other 36, question fix 35, tests 29, release 12, ci 8
Claude: 99 commits, 11,237 lines added, 2,019 deleted
     31.6%      3,548  runner/ops/install.py
      8.7%        981  runner/tools/release_train.py
      5.6%        632  docs/steady/reports/ci-failures.md
      5.3%        594  runner/guard/macos_confine.py
      4.2%        476  runner/tests/test_release_train.py
      4.2%        474  .github/workflows/build.yml
      3.6%        400  runner/tools/run_tests_parallel.py
      2.7%        300  runner/tests/test_parallel_runner.py
    by kind: release 31, ci 24, docs 13, tools 11, tests 10, desk 4, other 3, figures 2
questions filed in the window: 35 (Claude -> seat 2, Muse -> self 33)
longest chain of residual questions: 23, Q143 .. Q167
Q168: named first by Claude; first named by Muse 0.2 hours later
Q166: named first by Claude; first named by Muse 0.3 hours later
```

What the two windows hold, side by side, with no verdict drawn:

- In the first window the largest shares of Muse's lines are the
  fuzz corpus's arcs and run records and a documentation pass
  (65 commits of docs); 13 questions were filed, all by Muse to
  the desk it carries.
- In the second window one test module holds 51.7 per cent of
  Muse's lines, the desk record 17.4 and the questions file 7.3;
  the corpus's run records hold 4.0. 35 questions were filed, 33
  of them by Muse to the desk, and 23 of the window's questions
  are one chain: Q143 and the 22 after it, each naming the guard
  the one before it left and carrying that guard's residual
  shapes.
- The two questions another seat filed in the second window (Q166
  and Q168) were named in a Muse commit 0.3 and 0.2 hours after
  they were filed.

The next reading is taken over the 48 hours after this page lands.
