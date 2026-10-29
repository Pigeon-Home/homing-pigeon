#!/bin/sh
# Bank this rig's de_dust corpus into main (section M item 7).
# Lives in the repo so a rig's own fetch of main delivers it;
# the only things a rig keeps outside the checkout are its PAT
# file and the cron line that calls this script. The PAT path
# is this rig's (the Nuremberg rig); a rig with a different path
# sets RIG_PAT_FILE.
set -e
cd "$(dirname "$0")/../.."
exec python3 runner/tools/rig_bank.py \
    --rig "Nuremberg" \
    --corpus runner/tests/de_dust \
    --pat-file "${RIG_PAT_FILE:-/opt/hp-rig/github-pat.txt}" \
    >> /var/lib/hp-dedust/bank.log 2>&1
