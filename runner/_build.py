"""Build identity for this runner tree.

Written by the build tooling (runner/tools/build_stamp.py) when a
tree is packaged -- a release build, a preview build, or a rig
test deployment -- with the source commit the tree was built
from (__build__) and a single SHA-384 checksum over the runner
tree's manifest (__checksum__), from which the exact tree that
ran can be derived. A plain source checkout carries "unknown"
for both, and the identity banner (runner/ops/identity.py) prints
the version, platform and Python in full beside those unknowns.
The runner never shells out to git at runtime to discover this:
what is stamped here is what was built, and a log reader can tell
at a glance which code is executing.
"""

__build__ = "unknown"
__checksum__ = "unknown"
