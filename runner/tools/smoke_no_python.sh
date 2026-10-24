#!/bin/sh
# Drop the frozen runner onto a machine that does not have Python.
#
# The common computer in that class is a Windows PC: it does not ship
# Python, and the Windows job starts homing-pigeon.exe with Python
# taken off PATH. This script is the Linux half of the same drop.
# Debian bookworm slim is a normal glibc machine with no python3
# package. That stands in for a PC or a board you own and did not
# install Python on. It is not a television. Tizen, webOS, Roku, and
# Apple TV still cannot exec a shell, and this binary is not for them.
#
# The frozen binary carries its own interpreter. If the image grows a
# python3, the proof is void and this script fails.
set -eu

BIN=${1:?path to the frozen runner}
IMAGE=debian:bookworm-slim

[ -f "$BIN" ] || { printf 'SMOKE FAILED: no such binary: %s\n' "$BIN" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { printf 'SMOKE FAILED: docker is required\n' >&2; exit 1; }

docker pull "$IMAGE" >/dev/null

if docker run --rm "$IMAGE" sh -c 'command -v python3 >/dev/null || command -v python >/dev/null'; then
    printf 'SMOKE FAILED: %s has Python; it is not a no-Python machine\n' "$IMAGE" >&2
    exit 1
fi

dir=$(CDPATH= cd "$(dirname "$BIN")" && pwd)
base=$(basename "$BIN")
out=$(docker run --rm -v "$dir":/drop:ro "$IMAGE" "/drop/$base" --version) || {
    printf 'SMOKE FAILED: frozen runner did not start with no Python\n' >&2
    exit 1
}
printf '%s\n' "$out"
[ -n "$out" ] || { printf 'SMOKE FAILED: empty --version\n' >&2; exit 1; }
printf 'no-python drop ok\n'
