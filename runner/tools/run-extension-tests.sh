#!/bin/sh
# Fast harness for the job-fuzz extension: its own suites plus
# the collateral surfaces a catalog change touches (extension
# loader, catalog pin, local-signal ingest). Seconds, not the
# full gate. Re-run after any change to the extension, the
# --run-variant door, or the catalog.
# Usage: ./run-extension-tests.sh [extra pytest args]
set -e
cd "$(dirname "$0")/../.."
PY="${PYTHON:-$HOME/workspace/.pfvenv/bin/python}"
exec "$PY" -m pytest \
    runner/tests/test_job_fuzz.py \
    runner/tests/test_run_variant.py \
    runner/tests/test_dozen_extensions.py \
    runner/tests/test_extensions.py \
    runner/tests/test_local_signals.py \
    -q "$@"
