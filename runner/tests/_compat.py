# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Stand-ins for test helpers newer than the 3.9 floor.

The runner promises Python 3.9 (pyproject requires-python), and the
python-floor CI leg runs the whole suite there. These keep the tests
on that promise without each one carrying its own fallback.
"""
import contextlib
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


@contextlib.contextmanager
def lenient_tempdir(**kwargs):
    """TemporaryDirectory(ignore_cleanup_errors=True) on any Python."""
    if sys.version_info >= (3, 10):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True,
                                         **kwargs) as d:
            yield d
        return
    d = tempfile.mkdtemp(**kwargs)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@contextlib.contextmanager
def chdir(path):
    """contextlib.chdir (3.11) on any Python."""
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def project_version():
    """[project] version from pyproject.toml, without tomllib (3.11)."""
    path = os.path.join(ROOT, "pyproject.toml")
    try:
        import tomllib
    except ImportError:
        tomllib = None
    if tomllib is not None:
        with open(path, "rb") as fh:
            return tomllib.load(fh)["project"]["version"]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    section = re.search(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    m = re.search(r'^version\s*=\s*"([^"]+)"', section.group(1), re.M)
    return m.group(1)


def filename_punctuation():
    """The string.punctuation characters a file name can hold
    on this platform, as one string in punctuation order.

    Everywhere: all of string.punctuation except "/", the path
    separator no single file name can contain. On Windows the
    Win32 namespace also refuses < > : " | ? * in a name and
    treats "\\" as a separator, so a name carrying one of those
    cannot exist there at all. The bookend sweeps that create
    files iterate this set: the full sweep runs in the Linux
    and macOS jobs, and the Windows job runs every character
    its file names can hold.
    """
    import string
    chars = string.punctuation.replace("/", "")
    if os.name == "nt":
        chars = "".join(c for c in chars if c not in '<>:"|?*\\')
    return chars


def require_hypothesis():
    """Skip the calling module when hypothesis is absent off CI.

    The property and fuzz modules need hypothesis, which every CI leg
    installs from .github/requirements-ci.txt. An air-gapped box or a
    rig with no package index cannot install it, and there the suite
    should still finish green. Under CI (GITHUB_ACTIONS or CI set) the
    import is left to fail loudly, so a leg that lost the pin goes red.
    """
    import importlib.util
    import unittest
    if importlib.util.find_spec("hypothesis") is not None:
        return
    if os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"):
        return
    raise unittest.SkipTest("hypothesis is not installed on this box")
