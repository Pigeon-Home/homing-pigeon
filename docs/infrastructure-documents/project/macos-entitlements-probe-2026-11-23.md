# The Mac store entitlements probe: supposition, before the fix

Written 2026-11-23, before any code in this landing was written.
The conclusions section is appended after the tests run, in this
same place, and the change the numbers support follows it.

## What stands

An outside review of the store packaging (Grok, forwarded by the
owner on 2026-11-23) raised two points about the Mac App Store
bundle, and both are checkable against the tree as it stands.

The first point concerns outgoing network access. The entitlements
file at packaging/macos/entitlements.plist declares the App Sandbox
and nothing else. The runner earns its keep by initiating
connections: its mailbox transports poll and send, and its HTTPS
transports fetch and post. Under the App Sandbox, an app that holds
no outgoing network entitlement is refused the connections it tries
to open. The entitlement Apple documents for that case is
com.apple.security.network.client.

The second point concerns the application identifier. The first
carried out upload (version 3.17.33.3, 2026-11-22) came back with
TestFlight warning 90886: the bundle lacked an application
identifier in its signature, and that build stands unavailable for
TestFlight. The entitlement that carries the identifier is
com.apple.application-identifier, and its value joins the team ID
and the bundle ID: 3PH9A88USW.ai.pigeon-home.homing-pigeon for this
record. The provisioning profile embedded in the bundle was made
for exactly that application identifier, so the entitlements the
signing chain hands to codesign should name the same value.

## The supposition

S1. The entitlements file is the single place both fixes belong.
Every codesign step in the plan that runner/tools/apple_store.py
produces already names packaging/macos/entitlements.plist, so a
fix landed there reaches the two executables and the bundle itself
with no change to the signing commands.

S2. The parsed entitlements after the fix will equal exactly three
entries: the App Sandbox true, the outgoing network client
entitlement true, and the application identifier string above.
Nothing else joins the list; each further entitlement is a claim
App Review reads, and this landing claims only what the two
findings name.

S3. A pin written against the file as it stands today will fail:
the existing test that asserts the parsed entitlements equal the
sandbox alone will read the missing entries as a mismatch once the
expectation moves, and a new pin on the planner constant will fail
while the constant still derives nothing. Written first, both pins
go red before the fix and green after it.

S4. The planner can hold the expected entitlements in one place, as
a value derived from the team ID and bundle ID constants it already
carries, and the tests can pin the file against that value in both
directions: the file may neither lose an entry the planner expects
nor gain one it does not.

S5. What this landing cannot prove is the signed bundle itself.
No Mac and no signing material stand on this machine, so the proof
here is at the level of the file and the plan: the entitlements
parse, they carry the two missing entries, and every codesign step
in the planned chain signs under that same file. The TestFlight
warning clears only when the next store upload is carried out and
Apple answers it, and the record should say so plainly.

## Conclusions

Appended 2026-11-23, after the tests ran.

The pins went red first, as S3 supposed: with the new expectations
written and nothing else changed, the test file ran 56 tests and
failed with 6 errors, every one of them a missing planner value or
a missing entitlements entry. After the fix the same file runs
56 tests, all passing.

S1 held. No signing command changed: every codesign step in the
plan already names the one entitlements file, so the two new
entries reach the two executables and the bundle itself through
that file alone.

S2 held. The file now parses to exactly the three supposed
entries: the App Sandbox true, the outgoing network client
entitlement true, and the application identifier string
3PH9A88USW.ai.pigeon-home.homing-pigeon.

S4 held, and the planner now carries the guard the supposition
asked for: EXPECTED_ENTITLEMENTS stands in runner/tools/apple_store.py
derived from the team ID and bundle ID constants, check_entitlements
refuses any parsed set that differs from it in either direction,
and plan_upload returns a refusal naming the entitlements when the
file on disk has drifted, before it plans a single command. Five
drift shapes are pinned in the tests (each entry missing in turn,
a wrong identifier value, and an added entry), beside the pins on
the file itself.

S5 stands as written. This landing proves the file and the plan,
not the signed bundle: no Mac and no signing material stand on
this machine. Warning 90886 clears only when the next store
upload is carried out under these entitlements and Apple answers
it, and the first run experience of the signed store bundle on a
Mac remains untested here for the same reason.
