"""Time the cryptography of the RFC 10024 hybrid path.

Measures every cryptographic operation in the X25519MLKEM768
hybrid key agreement (runner/wire/mlkem.py and the hybrid
share paths of runner/wire/dtlsproto.py), one operation at a
time, and prints a table of milliseconds per operation
(median, min, max over the repetitions run).

This tool exists because the hybrid fuzzing effort
(docs/infrastructure-documents/proofs/hybrid-fuzz-10024.md)
times the cryptography before abstracting any of it: the
suppositions recorded there are checked against this tool's
output, on the build machine and on the rig the fuzzing runs
on. Repetitions adapt to the measured cost, so a genuinely
slow operation is measured a few times rather than for
minutes: each operation gets a budget of about 4 seconds of
measurement in total.

Stdlib only. Run from the repository root:

    python3 runner/tools/hybrid_timing.py [--json]
"""

import argparse
import json
import os
import statistics
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.wire import dtlsproto, mlkem  # noqa: E402

BUDGET_S = 4.0
MAX_REPS = 200


def _time_op(fn, budget_s=BUDGET_S):
    """Time fn() adaptively; return (median_ms, min_ms,
    max_ms, reps). At least 3 repetitions, so the median is a
    measured value even for a slow operation."""
    samples = []
    start = time.perf_counter()
    while len(samples) < 3 or (
            time.perf_counter() - start < budget_s
            and len(samples) < MAX_REPS):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
        if len(samples) >= 3 and \
                time.perf_counter() - start >= budget_s:
            break
    return (statistics.median(samples), min(samples),
            max(samples), len(samples))


def benchmark(budget_s=BUDGET_S):
    """Run every measurement; return a list of row dicts:
    {op, median_ms, min_ms, max_ms, reps}. budget_s caps the
    measurement time per operation (the tests pass a small
    one; the command line takes the default)."""
    rows = []

    def row(name, fn):
        med, lo, hi, reps = _time_op(fn, budget_s)
        rows.append({"op": name, "median_ms": med,
                     "min_ms": lo, "max_ms": hi, "reps": reps})

    d = bytes(range(32))
    z = bytes(range(32, 64))
    ek, dk = mlkem.keygen_internal(d, z)
    m = bytes(range(64, 96))
    secret, ct = mlkem.encaps_internal(ek, m)
    bad_ct = bytes([ct[0] ^ 1]) + ct[1:]
    priv = bytes(range(96, 128))
    pub = dtlsproto.x25519_public(priv)

    row("mlkem.keygen_internal", lambda: mlkem.keygen_internal(d, z))
    row("mlkem.encaps_internal", lambda: mlkem.encaps_internal(ek, m))
    row("mlkem.decaps (genuine ct)", lambda: mlkem.decaps(dk, ct))
    row("mlkem.decaps (corrupted ct, implicit rejection)",
        lambda: mlkem.decaps(dk, bad_ct))
    row("mlkem.encapsulation_key_check",
        lambda: mlkem.encapsulation_key_check(ek))
    row("mlkem.decapsulation_key_check",
        lambda: mlkem.decapsulation_key_check(dk))
    row("dtlsproto.x25519_public",
        lambda: dtlsproto.x25519_public(priv))
    row("dtlsproto._ecdh", lambda: dtlsproto._ecdh(priv, pub))

    def composed_answer():
        # What the responder's hybrid answer spends on
        # cryptography: the FIPS 203 check, an encapsulation,
        # and the X25519 half (dtlsproto._hybrid_answer).
        assert mlkem.encapsulation_key_check(ek)
        mlkem.encaps_internal(ek, m)
        dtlsproto._ecdh(priv, pub)

    def composed_shared():
        # What the client's hybrid shared secret spends:
        # decapsulation plus the X25519 half
        # (dtlsproto._hybrid_shared).
        mlkem.decaps(dk, ct)
        dtlsproto._ecdh(priv, pub)

    row("composed: responder hybrid answer crypto", composed_answer)
    row("composed: client hybrid shared crypto", composed_shared)

    def full_handshake():
        server = dtlsproto.DtlsServerCore(
            secret_lookup=dtlsproto.make_secret_lookup("timing"),
            hybrid=True)
        client = dtlsproto.DtlsClientCore("timing", hybrid=True)
        out = client.start(1000.0)
        for _ in range(60):
            if not out:
                break
            nxt = []
            for dg in out:
                nxt += server.feed(dg, ("127.0.0.1", 50001), 1000.0)
            out = []
            for dg in nxt:
                out += client.feed(dg, 1000.0)
        assert client.state == "established", client.state

    row("full in-memory hybrid handshake (both cores)",
        full_handshake)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="print the table as JSON")
    args = parser.parse_args(argv)
    rows = benchmark()
    if args.json:
        print(json.dumps({"rows": rows}, indent=2))
        return 0
    print("op | median ms | min ms | max ms | reps")
    for r in rows:
        print("{op} | {median_ms:.2f} | {min_ms:.2f} | "
              "{max_ms:.2f} | {reps}".format(**r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
