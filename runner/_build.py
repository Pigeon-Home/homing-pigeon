"""Build identity for this runner tree.

Written by the build tooling (runner/tools/build_stamp.py) when a
tree is packaged -- a release build, a preview build, or a rig
test deployment -- with the source commit the tree was built
from. A plain source checkout carries "unknown", and the startup
log then prints the version alone, with no build parenthetical.
The runner never shells out to git at runtime to discover this:
what is stamped here is what was built, and a log reader can tell
at a glance which code is executing.
"""

__build__ = "unknown"
