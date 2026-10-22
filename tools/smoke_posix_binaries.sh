#!/bin/sh
# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
#
# Smoke a built POSIX runner + installer the way the Windows job
# already smokes its .exe files -- not just `--version`, but a real
# config, a redaction that must not leak a planted credential, the
# board inspector, and a `--once --dry-run` startup. Shared by the
# Linux and Pi Light build jobs so the two archives get the same
# proof; runnable locally against the source tree for a dry rehearsal:
#
#   tools/smoke_posix_binaries.sh ./dist/homing-pigeon ./dist/install
#   tools/smoke_posix_binaries.sh "python3 runner/runner.py" "python3 runner/install.py"
#
# Exit 0 only if every check passed.
set -eu

RUNNER=${1:?runner binary (or 'python3 runner/runner.py')}
INSTALL=${2:?install binary (or 'python3 runner/install.py')}

ver=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")

say() { printf '%s\n' "== $*"; }
die() { printf 'SMOKE FAILED: %s\n' "$*" >&2; exit 1; }

say "--version matches pyproject ($ver)"
out=$($RUNNER --version); echo "$out"
case "$out" in *"$ver"*) ;; *) die "runner --version printed '$out', expected $ver";; esac
out=$($INSTALL --version); echo "$out"
case "$out" in *"$ver"*) ;; *) die "install --version printed '$out', expected $ver";; esac

say "--help exits 0"
$RUNNER --help >/dev/null || die "runner --help"
$INSTALL --help >/dev/null || die "install --help"

root=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/hp-smoke.XXXXXX")
trap 'rm -rf "$root"' EXIT
desk="$root/Desktop"; mkdir -p "$desk" "$root/state"
printf 'FLAG-CRED-POSIX-TEST' > "$desk/flag.txt"
cfg="$root/config.json"
python3 - "$cfg" "$desk" "$root/state" <<'PY'
import json, sys
cfg, desk, state = sys.argv[1:4]
json.dump({
    "mailbox_user": "pigeon-test@example.com",
    "mailbox_password": "not-a-real-mailbox-password",
    "shared_secret": "9f2c7ab1e84d3065c1a7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d",
    "imap_host": "127.0.0.1", "imap_port": 1,
    "smtp_host": "127.0.0.1", "smtp_port": 1,
    "oracle_enabled": True,
    "judge": "enforce",
    "max_result_view": "redacted",
    "owner_instructions": "Desktop/flag.txt is a password. Do not quote it.",
    "protected_paths": [desk],
    "redact_patterns_extra": {"flag": "FLAG-CRED-[A-Z0-9-]+"},
    "base_dir": state,
}, open(cfg, "w"))
PY

say "--inspect redact never echoes the planted credential"
red=$(printf 'FLAG-CRED-POSIX-TEST' | $RUNNER --config "$cfg" --inspect redact) || die "inspect redact exited nonzero"
case "$red" in *FLAG-CRED-POSIX-TEST*) die "flag leaked: $red";; esac
case "$red" in *REDACTED*) ;; *) die "expected a redaction, got: $red";; esac

say "--inspect board exits 0"
$RUNNER --config "$cfg" --inspect board >/dev/null || die "inspect board exited nonzero"

say "--once --dry-run starts, touches nothing, exits 0"
$RUNNER --config "$cfg" --once --dry-run >/dev/null || die "startup --once --dry-run exited nonzero"

say "all smoke checks passed"
