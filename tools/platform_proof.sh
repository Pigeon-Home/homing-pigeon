#!/bin/sh
# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
#
# Run the portable proof (tests/test_platform_proof.py) on whatever
# box this is: install python3 with whichever package manager
# exists, copy the tree somewhere writable, apply one administrator
# fat-finger if asked, run, and fail unless every test ran and
# passed. Used by .github/workflows/platform-matrix.yml inside
# containers, QEMU-emulated containers, and BSD VMs; runnable by
# hand on any POSIX host:
#
#   tools/platform_proof.sh                   # this box, no mutation
#   HP_MUTATION=no-bash tools/platform_proof.sh
#
# HP_SRC   where the tree is (default: the directory above tools/)
# HP_WORK  a writable scratch dir (default: a fresh one under $TMPDIR)
# HP_MUTATION  none | no-bash | no-home | path-minimal | c-locale |
#              umask-077 | closed-stdin   (noexec-tmp and readonly-root
#              are container flags the workflow applies; the script
#              just runs under them)
set -eu

# Any failure before the verdict step still names itself.
trap 'rc=$?; [ $rc -ne 0 ] && printf "::error::platform_proof.sh failed (exit %s) at stage: %s\n" "$rc" "${STAGE:-start}"; exit $rc' EXIT

here=$(cd "$(dirname "$0")" && pwd)
SRC=${HP_SRC:-$(dirname "$here")}
MUT=${HP_MUTATION:-none}

say() { printf '== %s\n' "$*"; }

# ---- 1. python3 -------------------------------------------------------
STAGE="install python3"
if ! command -v python3 >/dev/null 2>&1; then
  say "installing python3"
  if   command -v apk      >/dev/null 2>&1; then apk add --no-cache python3
  elif command -v apt-get  >/dev/null 2>&1; then apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends python3 >/dev/null
  elif command -v microdnf >/dev/null 2>&1; then microdnf install -y python3 >/dev/null
  elif command -v dnf      >/dev/null 2>&1; then dnf install -y -q python3
  elif command -v yum      >/dev/null 2>&1; then yum install -y -q python3
  elif command -v zypper   >/dev/null 2>&1; then zypper -n -q install python3
  elif command -v pacman   >/dev/null 2>&1; then pacman -Sy --noconfirm --quiet python >/dev/null
  elif command -v pkg      >/dev/null 2>&1; then pkg install -y python3
  elif command -v pkg_add  >/dev/null 2>&1; then pkg_add -I python%3
  elif command -v pkgin    >/dev/null 2>&1; then pkgin -y install python312 || pkgin -y install python311
  else say "no package manager found and no python3"; exit 2; fi
fi
# BSD packages install a versioned binary; make python3 resolvable.
if ! command -v python3 >/dev/null 2>&1; then
  for cand in /usr/pkg/bin/python3.12 /usr/pkg/bin/python3.11 /usr/local/bin/python3.12 /usr/local/bin/python3.11; do
    [ -x "$cand" ] && ln -sf "$cand" /usr/local/bin/python3 && break
  done
fi
say "python3: $(command -v python3) $(python3 -c 'import platform;print(platform.python_version())')"

# ---- 2. FIPS (opt-in): force the OpenSSL FIPS provider ----------------
STAGE="fips"
if [ "${HP_FIPS:-0}" = 1 ]; then
  say "forcing OpenSSL FIPS mode"
  command -v microdnf >/dev/null 2>&1 && microdnf install -y openssl openssl-fips-provider >/dev/null 2>&1 || true
  export OPENSSL_FORCE_FIPS_MODE=1
  command -v openssl >/dev/null 2>&1 && openssl list -providers 2>&1 | sed 's/^/   /' || true
  python3 - <<'PY'
import hashlib, hmac
hmac.new(b"k", b"m", hashlib.sha384).hexdigest()
try:
    hashlib.md5(b"x").hexdigest(); print("   md5: allowed (FIPS mode is NOT active)")
except ValueError as e:
    print("   md5: refused -> FIPS mode active (%s)" % e)
PY
fi

# ---- 3. a writable copy of the tree ----------------------------------
STAGE="copy tree"
WORK=${HP_WORK:-$(mktemp -d "${TMPDIR:-/tmp}/hp-proof.XXXXXX")}
mkdir -p "$WORK"
cp -R "$SRC/runner" "$SRC/tests" "$SRC/tools" "$SRC/pyproject.toml" "$WORK"/
cd "$WORK"

# ---- 4. the fat-finger -----------------------------------------------
STAGE="mutation $MUT"
case "$MUT" in
  none) ;;
  no-bash)
    rm -f /bin/bash /usr/bin/bash /usr/local/bin/bash 2>/dev/null || true
    if command -v bash >/dev/null 2>&1; then say "bash still present at $(command -v bash)"; exit 3; fi ;;
  no-home)      unset HOME; export HOME=/nonexistent ;;
  path-minimal) export PATH=/usr/bin:/bin ;;
  c-locale)     export LANG=C LC_ALL=C; unset LANGUAGE 2>/dev/null || true ;;
  umask-077)    umask 077 ;;
  closed-stdin) exec </dev/null ;;
  *) say "unknown HP_MUTATION '$MUT'"; exit 4 ;;
esac
say "mutation: $MUT"

# ---- 5. run, and demand a full OK ------------------------------------
STAGE="proof"
export HP_PLATFORM_PROOF=1 HP_MUTATION="$MUT" PYTHONDONTWRITEBYTECODE=1
python3 -m unittest tests.test_platform_proof -v 2>&1 | tee "$WORK/proof.log" || true
python3 tools/skip_guard.py "$WORK/proof.log" --no-skips --require-ok --annotate
