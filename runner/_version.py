"""Runtime version for every homing-pigeon CLI.

The release version is declared in pyproject.toml, but a frozen
binary (PyInstaller) cannot read it, so every entry point reports the
constant below via --version. It MUST match pyproject.toml; a unit
test (tests/test_version.py) fails the build if the two drift. Bump
both together — see CONTRIBUTING.md "bump before tag".
"""

__version__ = "3.8.9"
