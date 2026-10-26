"""The live runner module, for the modules split out of runner.py.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854

`runner.runner` when the suite or a package import loaded it,
`__main__` when runner.py was started as a script (an install, the
one-file binaries), where `runner` is the file itself and
`from runner import runner` raises "'runner' is not a package".
Looked up at call time, never cached, so the suite's patches on the
runner module hold for every caller. One copy here instead of one
per module.
"""
import sys
from typing import Any


def _runner() -> Any:
    for name in ("runner.runner", "__main__"):
        m = sys.modules.get(name)
        if m is not None and callable(getattr(m, "_load_mod", None)):
            return m
    from runner import runner as R  # a host that imported us first
    return R
