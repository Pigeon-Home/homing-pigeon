#!/bin/sh
# hp-remote-upgrade-apply-macos.sh -- host half of the remote upgrade
# procedure on macOS. A signed job stages a release tarball in its
# work directory (the one place a confined job can write that
# persists) and leaves a trigger file beside it. This applier, fired
# every minute by the com.homing-pigeon.remote-upgrade LaunchAgent,
# re-verifies the staged tarball against a freshly fetched
# SHA384SUMS before it swaps anything, then stops the runner agent,
# runs the release's own installer, and starts the runner again.
# Same contract as the Linux applier (hp-remote-upgrade-apply); only
# the service control, the hash tool and the temp dir differ, and
# there is no CA drop-in: the macOS runner uses the platform store.
set -u
HOME_DIR="$HOME/.homing-pigeon"
WORK="$HOME_DIR/work"
LOG="$HOME_DIR/remote-upgrade-applier.log"
exec >>"$LOG" 2>&1
echo "=== applier $(date -u +%FT%TZ)"
PAYLOAD=""
for d in $(ls -td "$WORK"/*/remote-upgrade 2>/dev/null); do
  if [ -f "$d/trigger" ]; then PAYLOAD="$d"; break; fi
done
[ -n "$PAYLOAD" ] || { echo "no triggered payload"; exit 0; }
rm -f "$PAYLOAD/trigger"
fail() { echo "FAILED: $1" > "$PAYLOAD/outcome.txt"; echo "applier FAILED: $1"; exit 0; }
TARBALL=$(ls "$PAYLOAD"/homing-pigeon-macos-*-*.tar.gz 2>/dev/null | head -1)
[ -n "$TARBALL" ] || fail "no tarball staged"
BASE=$(basename "$TARBALL")
VER=$(echo "$BASE" | sed -E 's/^homing-pigeon-macos-[^-]+-(.*)\.tar\.gz$/\1/')
[ -n "$VER" ] || fail "cannot read the version from $BASE"
cd "$PAYLOAD" || fail "cannot enter payload dir"
curl -fsSL -o SHA384SUMS.fresh "https://github.com/Pigeon-Home/homing-pigeon/releases/download/v$VER/SHA384SUMS" || fail "cannot fetch SHA384SUMS for v$VER"
grep "$BASE" SHA384SUMS.fresh > fresh.sum || fail "no sums line for $BASE"
# macOS shasum prints the same digest sha384sum does; the sums file
# is verified line by line through it.
WANT=$(awk '{print $1}' fresh.sum)
GOT=$(shasum -a 384 "$TARBALL" | awk '{print $1}')
[ "$WANT" = "$GOT" ] || fail "staged tarball fails the fresh SHA384SUMS check"
EX=$(mktemp -d "$HOME_DIR/extract.XXXXXX")
tar -xzf "$TARBALL" -C "$EX" || fail "extract failed"
DIR=$(ls -d "$EX"/homing-pigeon-macos-*-*/ 2>/dev/null | head -1)
[ -n "$DIR" ] || fail "no release directory in the tarball"
cd "$DIR" || fail "cannot enter release dir"
PROFILE_BEFORE=$(/usr/bin/python3 -c "import json; print(json.load(open('$HOME_DIR/config.json')).get('profile',''))" 2>/dev/null)
LABEL="com.homing-pigeon.runner"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
# The running runner holds its own program file open, and replacing
# an executing file fails. Stop the runner agent before the install;
# if the install fails, start it again on the previous version so a
# bad upgrade never leaves the machine without its runner.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
if timeout 600 ./install; then
  echo "applier: install ok"
else
  launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null
  fail "the installer failed (runner restarted on the previous version)"
fi
PROFILE_NOW=$(/usr/bin/python3 -c "import json; print(json.load(open('$HOME_DIR/config.json')).get('profile',''))" 2>/dev/null)
if [ -n "$PROFILE_BEFORE" ] && [ "$PROFILE_BEFORE" != "$PROFILE_NOW" ]; then
  /usr/bin/python3 -c "
import json, os
p = '$HOME_DIR/config.json'
c = json.load(open(p)); c['profile'] = '$PROFILE_BEFORE'
json.dump(c, open(p, 'w'), indent=1); os.chmod(p, 0o600)
"
  echo "applier: restored profile $PROFILE_BEFORE (installer had stamped $PROFILE_NOW)"
fi
launchctl kickstart -k "gui/$(id -u)/$LABEL" || fail "the runner restart failed"
sleep 5
V=$("$HOME_DIR/homing-pigeon" --version 2>&1 | head -1)
echo "upgraded: $V" > "$PAYLOAD/outcome.txt"
echo "applier done: $V"
