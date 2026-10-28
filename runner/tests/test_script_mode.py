# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""Script mode and entry points: the lines only a by-path run takes.

Every module split out of runner.py carries a fallback for the day it
runs from inside runner/ (`python3 runner/runner.py`, the one-file
binaries): `from runner.ops.live import _runner` fails there and
`from ops.live import _runner` takes over. Every sense extension, the
transports, the cloud helpers and the hosting CLI end in an
`if __name__ == "__main__"` entry. The suite reaches both only in
child processes, which line coverage does not see, so a typo in a
fallback import would pass every in-process test.

Here each module is loaded by its file with the `runner` package
hidden and runner/ first on sys.path, as a by-path run sees the
tree, and each fallback is held to binding the same object under its
bare name. Each entry runs in process as `__main__` and is held to
its documented first answer: `--help` for the senses and the CLIs, a
refusal with exit 2 for a transport given no channel, a reply a line
for the queries worker.
"""
import contextlib
import glob
import importlib.util
import io
import json
import os
import re
import runpy
import sys
import types
import unittest
import warnings
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
RUNNER = os.path.join(ROOT, "runner")

from runner import _version  # noqa: E402
from runner import runner as R  # noqa: E402

# The bare names a by-path run imports runner/'s folders under.
_BARE = ("ops", "guard", "wire", "oracle", "hosting", "cloud",
         "transport_extensions", "_version")


def _ours(name):
    return name == "runner" or name.startswith("runner.") \
        or name.split(".")[0] in _BARE


@contextlib.contextmanager
def script_mode(block=()):
    """The interpreter as `python3 runner/<file>.py` leaves it: the
    `runner` package cannot be imported, runner/ is first on the
    path. `block` names further modules made unimportable. Every
    module entry and the path are put back afterwards."""
    saved = {k: v for k, v in sys.modules.items() if _ours(k)}
    blocked = {k: sys.modules.get(k) for k in block}
    path = list(sys.path)
    try:
        for k in saved:
            del sys.modules[k]
        sys.modules["runner"] = None
        for k in saved:
            if k.startswith("runner."):
                sys.modules[k] = None
        for k in block:
            sys.modules[k] = None
        sys.path.insert(0, RUNNER)
        yield
    finally:
        for k in [k for k in sys.modules if _ours(k) or k in block]:
            del sys.modules[k]
        sys.modules.update(saved)
        for k, v in blocked.items():
            if v is not None:
                sys.modules[k] = v
        sys.path[:] = path


def load(rel, tag):
    """Execute one file under a private name; the module object."""
    spec = importlib.util.spec_from_file_location(
        "hp_scriptmode_" + tag, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pyproject_version():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
        return re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.M).group(1)


_REAL_OPEN = open


def _pyproject_open(replacement):
    """builtins.open with pyproject.toml answered by `replacement`
    (an exception to raise, or text to read); everything else real."""
    def fake(file, *a, **kw):
        if str(file).endswith("pyproject.toml"):
            if isinstance(replacement, BaseException):
                raise replacement
            return io.StringIO(replacement)
        return _REAL_OPEN(file, *a, **kw)
    return mock.patch("builtins.open", fake)


# The modules split out of runner.py whose only by-path line is the
# live-module lookup's fallback.
_LIVE_LOOKUP = ("attest", "av", "context", "exec", "firewall", "handlers",
                "helpers", "mail", "main", "misc", "oracle_ops",
                "oracle_server", "paths", "policy", "poll", "queries",
                "remediation_ops", "sensors", "startup", "watch",
                "windows")


class OpsFallbacksTest(unittest.TestCase):
    def test_each_split_module_finds_the_live_runner_by_its_bare_path(self):
        for name in _LIVE_LOOKUP:
            with self.subTest(module=name), script_mode():
                mod = load("runner/ops/%s.py" % name, "ops_" + name)
                self.assertEqual(mod._runner.__module__, "ops.live")
                self.assertIs(mod._runner, sys.modules["ops.live"]._runner)

    def test_the_config_readers_come_from_the_bare_guard_folder(self):
        for name in ("exec", "mail", "queries"):
            with self.subTest(module=name), script_mode():
                mod = load("runner/ops/%s.py" % name, "cfg_" + name)
                self.assertEqual(mod._confval.__name__, "guard.confval")
        with script_mode():
            mod = load("runner/ops/queries.py", "sec_queries")
            self.assertEqual(mod._security.__name__, "guard.security")

    def test_the_state_writer_comes_from_the_bare_guard_folder(self):
        for rel in ("runner/ops/extensions.py", "runner/ops/extsources.py",
                    "runner/transport_extensions/channel.py"):
            with self.subTest(file=rel), script_mode():
                mod = load(rel, "io_" + os.path.basename(rel)[:-3])
                self.assertEqual(mod._atomicio.__name__, "guard.atomicio")
                self.assertTrue(callable(mod._atomicio.write_text)
                                or hasattr(mod._atomicio, "__file__"))

    def test_a_python_without_lzma_still_has_an_error_to_catch(self):
        with script_mode(block=("lzma",)):
            mod = load("runner/ops/extsources.py", "nolzma")
        self.assertTrue(issubclass(mod._LZMAError, Exception))
        self.assertEqual(mod._LZMAError.__module__, mod.__name__)
        with self.assertRaises(mod._LZMAError):
            raise mod._LZMAError("a truncated archive")

    def test_the_cli_reads_its_version_and_transports_by_bare_name(self):
        with script_mode():
            mod = load("runner/ops/cli.py", "cli")
        self.assertEqual(mod.__version__, _version.__version__)
        self.assertEqual(mod._transports.__name__, "wire.transports")

    def test_the_cli_without_version_or_transports_still_builds(self):
        with script_mode(block=("_version", "wire", "wire.transports")):
            mod = load("runner/ops/cli.py", "cli_bare")
        self.assertEqual(mod.__version__, "unknown")
        self.assertIsNone(mod._transports)

    def test_the_live_lookup_imports_the_runner_when_nothing_is_live(self):
        from runner.ops import live
        stub = types.SimpleNamespace()
        with mock.patch.dict(sys.modules, {"runner.runner": stub,
                                           "__main__": stub}):
            self.assertIs(live._runner(), R)


class CloudAndHostingFallbacksTest(unittest.TestCase):
    def test_send_job_by_path_loads_the_one_implementation_by_file(self):
        with script_mode():
            sj = load("runner/cloud/send_job.py", "sendjob")
        self.assertEqual(sj.jobcrypto.__name__, "hp_jobcrypto")
        self.assertEqual(sj._filenames.__name__, "hp_filenames")
        self.assertEqual(sj._atomicio.__name__, "hp_atomicio")
        self.assertEqual(sj.__version__, _version.__version__)
        # What the by-path copy signs, the package's verifier accepts.
        from runner.cloud import send_job as SJ
        secret = "a" * 8 + "Q7#kd93Lmz0vX1wB4nT8yR2pU5sE6hJ"
        body = sj.sign_payload({"job_id": "script-mode-1", "kind": "ping",
                                "issued_at": "2026-10-27T00:00:00Z"},
                               secret)
        self.assertEqual(SJ.verify_body(body, secret)["job_id"],
                         "script-mode-1")

    def test_send_job_without_a_version_module_reads_pyproject(self):
        with script_mode(block=("_version",)):
            sj = load("runner/cloud/send_job.py", "sendjob_pyproject")
        self.assertEqual(sj.__version__, _pyproject_version())

    def test_send_job_with_no_readable_version_says_unknown(self):
        with script_mode(block=("_version",)), \
                _pyproject_open(OSError("no tree here")):
            sj = load("runner/cloud/send_job.py", "sendjob_noread")
        self.assertEqual(sj.__version__, "unknown")
        with script_mode(block=("_version",)), \
                _pyproject_open("[project]\nname = \"x\"\n"):
            sj = load("runner/cloud/send_job.py", "sendjob_noline")
        self.assertEqual(sj.__version__, "unknown")

    def test_the_hosting_cli_by_path_binds_its_providers_by_bare_name(self):
        with script_mode():
            cli = load("runner/hosting/cli.py", "hostcli")
        self.assertEqual(cli.base.__name__, "hosting.base")
        self.assertEqual(cli.read_config_blob.__module__, "ops.install")
        self.assertEqual(set(cli.PROVIDERS),
                         {"fly", "hetzner", "digitalocean"})


def _sense_entries():
    out = []
    for path in sorted(glob.glob(os.path.join(RUNNER, "extensions", "*",
                                              "*.py"))):
        if os.path.basename(path).startswith("test_"):
            continue
        with open(path, encoding="utf-8") as fh:
            if 'if __name__ == "__main__":' in fh.read():
                out.append(path)
    return out


@contextlib.contextmanager
def _as_main(argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    path = list(sys.path)
    patches = [mock.patch.object(sys, "argv", list(argv))]
    if stdin is not None:
        patches.append(mock.patch.object(sys, "stdin", stdin))
    try:
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            stack.enter_context(warnings.catch_warnings())
            warnings.simplefilter("ignore", RuntimeWarning)
            yield out, err
    finally:
        sys.path[:] = path


class EntryPointsTest(unittest.TestCase):
    def _exit(self, run):
        with self.assertRaises(SystemExit) as cm:
            run()
        return cm.exception.code

    def test_every_sense_answers_help_as_a_script(self):
        entries = _sense_entries()
        self.assertGreaterEqual(len(entries), 28)
        for path in entries:
            name = os.path.basename(path)
            with self.subTest(sense=name), \
                    _as_main([path, "--help"]) as (out, _err):
                sys.path.insert(0, os.path.dirname(path))
                code = self._exit(lambda: runpy.run_path(
                    path, run_name="__main__"))
                self.assertIn(code, (0, None))
                self.assertTrue(out.getvalue().startswith(
                    "usage: %s" % name), out.getvalue()[:80])

    def test_the_cloud_helpers_and_the_host_cli_answer_help(self):
        for rel, prog in (("runner/cloud/send_job.py", "send_job.py"),
                          ("runner/cloud/send_dtls.py", "send_dtls.py"),
                          ("runner/hosting/cli.py", "homing-pigeon-host")):
            path = os.path.join(ROOT, rel)
            with self.subTest(file=rel), \
                    _as_main([path, "--help"]) as (out, _err):
                code = self._exit(lambda: runpy.run_path(
                    path, run_name="__main__"))
                self.assertIn(code, (0, None))
                self.assertTrue(out.getvalue().startswith(
                    "usage: %s" % prog), out.getvalue()[:80])

    def test_each_transport_refuses_to_start_without_a_channel(self):
        for name in ("dtls", "email", "file", "nats", "queues"):
            with self.subTest(transport=name), \
                    mock.patch.dict(os.environ, {}, clear=False), \
                    _as_main(["-m"]) as (_out, err):
                code = self._exit(lambda: runpy.run_module(
                    "runner.transport_extensions." + name,
                    run_name="__main__"))
                self.assertEqual(code, 2)
                self.assertIn("ERROR: %s transport: no channel directory "
                              "given" % name, err.getvalue())

    def test_the_queries_worker_answers_a_line_per_request(self):
        req = {"pattern": "b+", "lines": ["abc", "xyz", "bb"], "limit": 5}
        stdin = types.SimpleNamespace(buffer=io.BytesIO(
            (json.dumps(req) + "\nnot json\n").encode("utf-8")))
        stdout = types.SimpleNamespace(buffer=io.BytesIO())
        with _as_main(["-m"], stdin=stdin), \
                mock.patch.object(sys, "stdout", stdout):
            code = self._exit(lambda: runpy.run_module(
                "runner.ops.queries", run_name="__main__"))
        self.assertEqual(code, 0)
        lines = stdout.buffer.getvalue().decode("utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertNotIn("rejected", first)
        self.assertIn("abc", json.dumps(first))
        self.assertNotIn("xyz", json.dumps(first))
        self.assertEqual(json.loads(lines[1]), {"rejected": "bad_pattern"})


if __name__ == "__main__":
    unittest.main()
