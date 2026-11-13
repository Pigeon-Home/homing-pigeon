# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""One shared stand-aside for tests that measure the tree (Q170).

mutmut runs the suite inside a copy (`mutants/`): no git index,
the mutated file ballooned with one copy per mutant, sources
trampolined. A test that measures the tree it stands in -- a
tracked-tree scan, a live count held against a recorded figure
-- cannot hold there, and its failure in mutmut's stats pass
ends the run before any mutant is tested. Those tests stand
aside inside a mutant copy and run exactly as before outside
one, through this one helper:

- as a class decorator: ``@skip_in_mutant_copy`` over a
  ``unittest.TestCase`` subclass skips the whole class;
- as a call at the top of a test method:
  ``skip_in_mutant_copy(self)`` skips that test.

mutmut sets `MUTANT_UNDER_TEST` for the stats pass (to
``stats``) and for every mutant (to the mutant's id), so the
helper keys on the variable's presence, any value. The reason
is registered in `runner/tests/test_skip_registry.py`.
"""
import os
import unittest


def in_mutant_copy():
    """True when this process runs inside a mutmut copy."""
    return "MUTANT_UNDER_TEST" in os.environ


def skip_in_mutant_copy(target=None):
    """Skip the decorated class, or the calling test, inside a
    mutant copy; a no-op outside one."""
    if isinstance(target, type):
        return unittest.skipIf(
            "MUTANT_UNDER_TEST" in os.environ,
            "inside a mutant copy: this test measures the "
            "tracked tree, and mutmut's copy is not it")(target)
    if "MUTANT_UNDER_TEST" in os.environ:
        raise unittest.SkipTest(
            "inside a mutant copy: this test measures the "
            "tracked tree, and mutmut's copy is not it")
    return None
