# Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c
"""Small refusal paths a local line-coverage run found unrun.

Each is a branch that exists to turn bad input into a readable answer
instead of a traceback: a transport manifest on another API version,
a --transports value that names nothing, an SMTP refusal whose codes
are all 5xx, a parser that raises ValueError on an older interpreter,
and a sources report over state it cannot read.
"""
import argparse
import json
import os
import shutil
import smtplib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.guard import extreview  # noqa: E402
from runner.ops import cli  # noqa: E402
from runner.ops import extsources  # noqa: E402
from runner.transport_extensions.email import __main__ as email_ext  # noqa: E402
from runner.wire import transports  # noqa: E402


class TransportApiVersionTest(unittest.TestCase):
    def test_a_manifest_on_another_api_version_is_refused_by_name(self):
        base = tempfile.mkdtemp(prefix="hp-tapi-")
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        found = {"oldpipe": {"api_version": 0, "kind": "transport"}}
        with mock.patch.object(transports._extensions, "load_extensions",
                               return_value=(found, [])), \
                mock.patch.object(transports, "builtin_transport_roots",
                                  return_value=[base]):
            registry, problems = transports.discover_transport_extensions(
                {}, base)
        self.assertNotIn("oldpipe", registry)
        self.assertTrue(any("'oldpipe'" in p and "refused" in p
                            and f"v{transports.TRANSPORT_API_VERSION}" in p
                            for p in problems), problems)


class TransportsArgTest(unittest.TestCase):
    def test_names_split_and_strip(self):
        self.assertEqual(cli._transports_arg(" file , email "),
                         ["file", "email"])

    def test_nothing_named_is_an_argument_error(self):
        for text in ("", " , ,"):
            with self.assertRaises(argparse.ArgumentTypeError):
                cli._transports_arg(text)

    def test_a_shape_the_module_refuses_is_an_argument_error(self):
        with mock.patch.object(cli._transports, "enabled_transports",
                               side_effect=ValueError("bad name")):
            with self.assertRaisesRegex(argparse.ArgumentTypeError,
                                        "bad name"):
                cli._transports_arg("file")

    def test_without_the_module_empty_is_still_refused(self):
        with mock.patch.object(cli, "_transports", None):
            self.assertEqual(cli._transports_arg("file"), ["file"])
            with self.assertRaises(argparse.ArgumentTypeError):
                cli._transports_arg("")


class EmailPermanentTest(unittest.TestCase):
    def test_recipients_refused_is_permanent_only_when_every_code_is_5xx(self):
        every = smtplib.SMTPRecipientsRefused(
            {"a@example.com": (550, b"no"), "b@example.com": (553, b"no")})
        mixed = smtplib.SMTPRecipientsRefused(
            {"a@example.com": (550, b"no"), "b@example.com": (451, b"later")})
        empty = smtplib.SMTPRecipientsRefused({})
        odd = smtplib.SMTPRecipientsRefused({"a@example.com": "550"})
        self.assertTrue(email_ext._permanent(every))
        self.assertFalse(email_ext._permanent(mixed))
        self.assertFalse(email_ext._permanent(empty))
        self.assertFalse(email_ext._permanent(odd))

    def test_a_response_code_decides(self):
        self.assertTrue(email_ext._permanent(
            smtplib.SMTPDataError(552, b"too large")))
        self.assertFalse(email_ext._permanent(
            smtplib.SMTPDataError(421, b"try later")))


class OlderParserTest(unittest.TestCase):
    def test_value_error_from_the_parser_is_a_finding(self):
        for exc in (ValueError("source code string cannot contain null "
                               "bytes"), RecursionError("too deep")):
            findings = []
            with mock.patch.object(extreview.ast, "parse", side_effect=exc):
                extreview._scan_python("ext.py", "x = 1\n", {}, findings,
                                       set())
            self.assertTrue(any(f.get("code") == "syntax"
                                and "does not parse" in f.get("detail", "")
                                for f in findings), findings)


class SourcesStatusTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="hp-src-")
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

    def test_state_that_will_not_load_is_an_empty_report(self):
        with mock.patch.object(extsources, "load_states",
                               side_effect=OSError("denied")):
            out = extsources.status(self.base)
        self.assertEqual(out["extensions"], [])
        self.assertEqual(out["state_dir"], extsources.state_root(self.base))

    def test_odd_keys_and_odd_states_are_reported_not_raised(self):
        with mock.patch.object(extsources, "load_states", return_value={
                "lonely": ["not", "a", "dict"],
                ("sense", "ok"): {"installed": [], "entries": "x"}}):
            out = extsources.status(self.base)
        names = [(e.get("kind"), e.get("name")) for e in out["extensions"]]
        self.assertIn(("?", "lonely"), names)
        self.assertIn(("sense", "ok"), names)
        json.dumps(out)  # the report is plain data


class InstallerLoaderTest(unittest.TestCase):
    """The frozen installer carries atomicio.py and panic.py as data,
    and a copy started by path finds them beside ops/."""

    GUARD = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "guard")

    def test_the_frozen_copy_is_loaded_by_path(self):
        from runner.ops import install
        meipass = tempfile.mkdtemp(prefix="hp-frozen-")
        self.addCleanup(shutil.rmtree, meipass, ignore_errors=True)
        os.makedirs(os.path.join(meipass, "pigeon-guard"))
        for name in ("atomicio.py", "panic.py"):
            shutil.copy(os.path.join(self.GUARD, name),
                        os.path.join(meipass, "pigeon-guard", name))
        with mock.patch.object(sys, "_MEIPASS", meipass, create=True):
            atom = install._import_atomicio()
            panic = install._import_panic()
        self.assertTrue(atom.__file__.startswith(meipass))
        self.assertTrue(panic.__file__.startswith(meipass))
        self.assertEqual(len(panic.WORDLIST), 6400)

    def test_a_copy_without_the_package_falls_back_to_the_path(self):
        from runner.ops import install
        real_import = __import__

        def no_package(name, *a, **k):
            # `from runner.guard import x` and `from guard import x`
            # both ask for the package by that name.
            if name in ("runner.guard", "guard"):
                raise ImportError(name)
            return real_import(name, *a, **k)

        with mock.patch("builtins.__import__", side_effect=no_package):
            atom = install._import_atomicio()
            panic = install._import_panic()
        self.assertEqual(os.path.dirname(atom.__file__), self.GUARD)
        self.assertEqual(os.path.dirname(panic.__file__), self.GUARD)

    def test_a_path_that_cannot_load_is_an_import_error(self):
        from runner.ops import install
        with mock.patch("importlib.util.spec_from_file_location",
                        return_value=None):
            with self.assertRaises(ImportError):
                install._load_by_path("/nowhere/atomicio.py")

    def test_a_rearm_that_cannot_write_says_so(self):
        from runner.ops import install
        base = tempfile.mkdtemp(prefix="hp-rearm-")
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        cfg = os.path.join(base, "config.json")
        with open(cfg, "w") as fh:
            json.dump({"base_dir": base}, fh)
        with mock.patch.object(install, "_import_panic",
                               side_effect=ImportError("gone")), \
                mock.patch("sys.stderr"):
            self.assertEqual(install.do_rearm(cfg), 1)


if __name__ == "__main__":
    unittest.main()
