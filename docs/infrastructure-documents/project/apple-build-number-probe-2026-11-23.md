# The Apple build number probe: supposition, before the fix

Written 2026-11-23, before any code in this landing was changed.
The conclusions section is appended after the tests run, in this
same place, and the change the numbers support follows it.

## What stands

An outside project review (Grok, forwarded by the owner on
2026-11-23) named a defect in the Mac App Store planner,
runner/tools/apple_store.py. Its store_build function maps the
release version into the bundle build number using only the
third and fourth components: 3.17.33.1 becomes 33.1. The review
checked the next transition by hand: the uploaded 3.17.33.3
carried build 33.3, while the latest release 3.18.33.1 would
carry build 33.1. The build number goes backwards at a minor
version transition, and Apple requires build numbers to keep
increasing. A submission built on the new line can be refused
for a number the planner chose, not for anything the app does.

The defect is wider than the one transition the review named.
Any change confined to the first or the second component is
invisible to the old mapping: 3.17.33.9 and 4.17.33.9 would
carry the same build, and 3.18.33.1 falls below 3.17.33.3.
Only the third and fourth components move the old number.

## The supposition

S1. The mapping is the whole defect. store_version already
carries the first three components into the short version,
which Apple compares as a version in its own right; nothing
else in the planner consumes the build number except the
rendered Info.plist, where render_info_plist checks the
rendered build against store_build. A search of the tree for
store_build callers will show the planner, its tests, and
documentation mentions only.

S2. A three component build of the form (major times 1000
plus minor, token millions, counter) rises strictly whenever
any one of the four release components rises and the rest
stand still, provided the minor stays below 1000. The first
build component packs the major and the minor at a fixed
width of three digits, so componentwise numeric comparison
of the build matches the release odometer order across all
four components: the counter, the token millions, the minor,
and the major.

S3. The packed shape clears the store history as well. Every
build uploaded under the old mapping began with the token
millions figure of its day, a number in the low thirties.
Every build under the packed mapping for the current lines
begins with a number above 3000, so the first build on the
new mapping stands above the highest build App Store Connect
has seen from this app, whichever upload that was.

S4. The packed shape stays inside the store limit the first
upload taught: at most three non negative integers in
CFBundleVersion. Three components, each a plain integer,
meets it with room to spare.

S5. Tests written against the packed mapping before the fix
will fail on the old code for exactly the transitions the
review named and for the first and second component changes,
and will pass once store_build packs the first two
components. Tests pinning the old 33.1 shape will need to
move to the new expected numbers; that move is part of the
fix, recorded here so it is not mistaken for thinning a pin.

## The plan the supposition calls for

Write the new tests first and run them against the standing
code, so the failure is measured rather than asserted. Then
change store_build to the packed mapping, refuse a minor of
1000 or more rather than packing it into a collision, update
the pins that named the old shape, and append the conclusions
below.
