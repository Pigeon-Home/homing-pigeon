# 3.14.46: why the cut took seventy minutes

Written 31-Oct-9:15am-PST/PDT, after 3.14.46 was on the mirrors.
This is the record of that cut. It is not a standing order.

## The clock

From the first release commit (`a933f566`, 7:55am) to the mirror
check (about 9:06am) was seventy minutes. A clean cut is two
builds: the branch build, then the tag build that publishes.
This one ran five.

| When | What | Result |
|---|---|---|
| 7:55am | `a933f566`, version 3.14.45 | Branch build. `build-windows` and `test-macos` failed. |
| 8:06am | `822ff651`, the registry lines | Branch build green at 8:16am. The nine guard jobs passed. |
| 8:17am | Tag `v3.14.45` on `822ff651` | Tag build. `build-windows` failed. Nothing was published. The image workflow had already pushed `v3.14.45`. |
| 8:35am | `01bad44f`, version 3.14.46 | Branch build green in 11m7s. |
| 8:47am | Tag `v3.14.46` | Tag build. Release published at 9:00am. SourceForge and GitLab followed. Mirrors checked by 9:07am. |

The successful cut, from a green branch build to a published
release, was about twenty minutes. The other fifty were the two
failures.

## What failed

The first build failed on `DocDriftGuardTests`. Section 4 of
PROTOCOL.md gained one line, and eight rows in
`runner/tests/defaults_registry.py` still named the old line.
The test takes a few milliseconds. It was not run before the
push. `test-macos` failed on the same assertion. It is not one
of the nine guard jobs, and it was not why the cut was refused.

The second failure was the tag build of `822ff651`. The branch
`build-windows` on that same commit had passed. The tag's
Windows leg ran `test_the_filed_crashes_meet_the_contract` and
got `bm-stash-0001 delivered twice without an undeliver`. The
lock around send-then-move was not enough: a move that does not
land leaves the record in the outbox for the other caller.
3.14.46 takes the record out of the outbox before the send.
That second Windows run is why the tag build stays. Skipping it
to save the time would have published the bug.

## What the runbook had wrong

The release paragraph said the branch build must be green at
every job, and that the tag build includes mutation. The guard
is nine jobs: `test` and the eight `build-*` jobs. Mutation
does not run on a tag (the owner's call, 2026-10-22). The
paragraph now says both.

## What is still wrong, and not changed here

`cut-release` starts the image workflow in the same step as the
tag build. The image for `v3.14.45` was pushed, and the tests
then failed, so the registry has a version the release does not.
`latest` moved on when 3.14.46's image workflow ran. Holding
the image dispatch until `release` succeeds is the fix. It is
not in this cut: it does not make a release faster, and this
cut stays on the path that just published.
