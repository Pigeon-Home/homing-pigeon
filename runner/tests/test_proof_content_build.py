#!/usr/bin/env python3
"""Pins for the content-series script builder, proof_content_build.compose.

Supposition, written before the fix (2026-11-01): the builder as
shipped rebuilds the whole script on every catalog line
("\\n".join(lines + [line]) inside the loop), so its cost grows
with the square of the rung. Measured on this machine before the
fix: 50,000 characters in 0.095 seconds, 200,000 in 2.049
seconds, 300,000 in 3.83 seconds -- the cap rung, 1,048,576,
extrapolates to roughly 47 seconds for a single script, and the
suite builds dozens of them (the cap redo alone builds 8, the
macOS shell module builds 4 cap scripts and 4 at 500,000 in its
setUpClass even on machines where every test then skips). That
is what pushed the tag build's test job over its 20 minute wall
clock twice on 3.15.101 (exit 124, no assertion failure, main
thread in compose from test_proof_sh_macos.setUpClass), while
the same commit's main test job passed in 16 minutes 56 seconds.

The conclusion the numbers support: track the joined length as
the lines accumulate and join once at the end. The builder must
then produce byte-for-byte the same scripts as the original
algorithm -- the reference implementation below is that
algorithm, kept verbatim -- and a cap script must compose in
well under 5 seconds.

Measured after the fix, same machine: the pre-fix timing pin
failed at 38.97 seconds for one cap script; the linear builder
composes that script in 0.031 seconds, and the eight large
scripts of the macOS module's setUpClass shape in 0.217 seconds.
The full pin file runs in 2.6 seconds.
"""
import os
import sys
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from runner.tests.proof_content_build import (  # noqa: E402
    BASH, POWERSHELL, bash_script, compose, ps_script)
from runner.tests.proof_sh_build import ATOMS, at_length  # noqa: E402
from runner.tests.test_proof_content_rung5000 import (  # noqa: E402
    compose as rung5000_compose)


def reference_compose(n, catalog, start, pad_open, pad_close,
                      limit=1000000):
    """The original builder, verbatim, as the equivalence oracle."""
    min_pad = 1 + len(pad_open) + 1 + len(pad_close)
    lines = []
    i = start
    while i - start < limit:
        line = catalog[i % len(catalog)]
        trial = "\n".join(lines + [line])
        if len(trial) + min_pad > n:
            break
        lines.append(line)
        i += 1
    if not lines:
        raise AssertionError("catalog line longer than the rung")
    body = "\n".join(lines)
    payload = "p" * (
        n - len(body) - len("\n") - len(pad_open) - len(pad_close))
    script = body + "\n" + pad_open + payload + pad_close
    if len(script) != n:
        raise AssertionError("%s != %s" % (len(script), n))
    return script


CATALOGS = (BASH, POWERSHELL, ATOMS)
PAD_PAIRS = (("echo '", "'"), ("Write-Output '", "'"), ("<'", "'>"))


class ComposeEquivalenceTest(unittest.TestCase):
    def test_matches_reference_across_rungs_starts_and_catalogs(self):
        for catalog in CATALOGS:
            for pad_open, pad_close in PAD_PAIRS:
                for start in (0, 1, 5, 11, 23):
                    for n in (64, 100, 499, 500, 5000, 5001):
                        got = compose(n, catalog, start,
                                      pad_open, pad_close)
                        want = reference_compose(
                            n, catalog, start, pad_open, pad_close)
                        self.assertEqual(got, want, (n, start))
                        self.assertEqual(len(got), n)

    def test_matches_reference_for_symbol_heavy_catalogs(self):
        # Bookends and troublemakers: entries that start or end
        # with a symbol, and symbol-only entries.
        catalogs = (
            ("-n", ";", "'", '"', "#", "a;b", "- ", " ;"),
            ("$", "${HOME}", "$((1))", "`true`", "\\", "a\\b"),
            ("x",),
            ("ab", "a", "abc"),
        )
        for catalog in catalogs:
            for start in (0, 2, 7):
                for n in (32, 97, 1000, 4097):
                    got = compose(n, catalog, start, "echo '", "'")
                    want = reference_compose(
                        n, catalog, start, "echo '", "'")
                    self.assertEqual(got, want, (catalog, n, start))

    def test_wrappers_match_reference(self):
        for start in (0, 5, 11):
            self.assertEqual(
                bash_script(50000, start),
                reference_compose(50000, BASH, start, "echo '", "'"))
            self.assertEqual(
                ps_script(50000, start),
                reference_compose(
                    50000, POWERSHELL, start, "Write-Output '", "'"))
            self.assertEqual(
                at_length(50000, start),
                reference_compose(50000, ATOMS, start, "echo '", "'"))

    def test_rung5000_local_copy_matches_reference(self):
        for start in (0, 3, 9):
            got = rung5000_compose(5000, BASH, start, "echo '", "'")
            want = reference_compose(
                5000, BASH, start, "echo '", "'", limit=100000)
            self.assertEqual(got, want)

    def test_exact_lengths_at_the_large_rungs(self):
        for n in (500000, 1048576, 1048577):
            for start in (0, 5, 11):
                self.assertEqual(len(bash_script(n, start)), n)
                self.assertEqual(len(ps_script(n, start)), n)
                self.assertEqual(len(at_length(n, start)), n)

    def test_pad_line_shape_at_the_large_rungs(self):
        script = bash_script(500000, 0)
        body, pad = script.rsplit("\n", 1)
        self.assertTrue(pad.startswith("echo '"))
        self.assertTrue(pad.endswith("'"))
        self.assertEqual(set(pad[len("echo '"):-1]), {"p"})
        self.assertTrue(all(
            line in BASH for line in body.split("\n")))

    def test_catalog_line_longer_than_the_rung_is_an_error(self):
        with self.assertRaises(AssertionError):
            compose(8, ("a much longer catalog line",), 0,
                    "echo '", "'")
        with self.assertRaises(AssertionError):
            reference_compose(8, ("a much longer catalog line",), 0,
                              "echo '", "'")


class ComposeSpeedTest(unittest.TestCase):
    def test_a_cap_script_composes_well_under_the_old_cost(self):
        # The original builder needs roughly 47 seconds for this
        # one script on the measuring machine; the bound leaves a
        # wide margin for a slower runner and still fails it.
        started = time.monotonic()
        script = bash_script(1048576, 0)
        elapsed = time.monotonic() - started
        self.assertEqual(len(script), 1048576)
        self.assertLess(elapsed, 5.0,
                        "compose took %.2f seconds" % elapsed)

    def test_the_macos_setUpClass_shape_is_cheap(self):
        # The four cap variants test_proof_sh_macos builds in its
        # setUpClass, plus its four 500,000 variants.
        started = time.monotonic()
        for n in (500000, 1048576):
            for start in (0, 5, 11):
                self.assertEqual(len(at_length(n, start)), n)
            self.assertEqual(len(at_length(n + 1, 0)), n + 1)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 5.0,
                        "setUpClass shape took %.2f seconds" % elapsed)


if __name__ == "__main__":
    unittest.main()
