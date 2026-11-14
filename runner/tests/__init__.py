"""The suite drives the installer and the setup wizard on machines
it is not installing.

On FreeBSD their seed puts questions to the machine it runs on: a
jail built for the probe, a trial job run in one, an account made
for the jobs. A test run is not an install, so the questions are
switched off here for the whole run -- in the environment, where
every copy of the installer a test loads and every process a test
starts reads the same word. The tests of the questions themselves
switch them on by name (runner/tests/test_freebsd_confine.py).

The word is left alone where the environment already carries one.
"""
import os

os.environ.setdefault("HP_SEED_ASKS_MACHINE", "0")
