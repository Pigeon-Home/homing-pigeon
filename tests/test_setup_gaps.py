"""Branch gaps for runner.setup. No network and no real IMAP."""

import importlib
import io
import json
import os
import runpy
import sys
import tempfile
import threading
import types
import unittest
from contextlib import chdir, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import setup as SU  # noqa: E402


def go(path, cfg, inputs, probe=None, gp=None, consent="tok"):
    err = io.StringIO()
    ck = {"new": None} if consent is None else {"return_value": consent}
    gk = {"side_effect": gp} if gp else {"return_value": "pw"}
    with mock.patch("builtins.input", side_effect=inputs), \
            mock.patch("getpass.getpass", **gk), \
            mock.patch.object(SU, "browser_consent", **ck), \
            mock.patch.object(SU, "_mailbox_probe", return_value=probe), \
            redirect_stdout(io.StringIO()), redirect_stderr(err):
        return SU.run_setup_wizard(path, cfg), err.getvalue()


class SetupGapsTest(unittest.TestCase):
    def test_gaps(self):
        with mock.patch("builtins.input",
                        side_effect=["", "yes", "no", EOFError]):
            self.assertTrue(SU.prompt_yes_no("q") and SU.prompt_yes_no("q"))
            self.assertFalse(
                SU.prompt_yes_no("q") or SU.prompt_yes_no("q", False))
        for secret in (None, "", "todo", "zz", "ab" * 20):
            SU._secret_is_real(secret)
        with mock.patch.object(SU, "_placeholder", None), \
                mock.patch.object(SU, "_patterned", None):
            self.assertTrue(SU._secret_is_real("ab" * 20))
        SU.is_tty()
        hosts = {"imap_host": "mine", "smtp_port": 0}
        SU._ensure_mail_hosts(hosts)
        self.assertEqual(
            (hosts["imap_host"], hosts["smtp_port"], hosts["imap_port"]),
            ("mine", 587, 993))
        with tempfile.TemporaryDirectory() as d:
            bad, arr, good = [
                os.path.join(d, n) for n in ("b.json", "a.json", "g.json")]
            Path(bad).write_text("{")
            Path(arr).write_text("[]")
            Path(good).write_text(json.dumps({
                "imap_host": "H", "shared_secret": "s",
                "mailbox_user": "u", "mailbox_password": "p",
                "oauth_refresh_token": "t"}))
            mei, exe = os.path.join(d, "m"), os.path.join(d, "e.exe")
            with mock.patch.object(sys, "_MEIPASS", mei, create=True), \
                    mock.patch.object(sys, "executable", exe):
                found = SU._example_candidates()
            with mock.patch.object(sys, "executable", ""):
                bare = SU._example_candidates()
            self.assertIn(
                os.path.join(mei, "runner", "config.example.json"), found)
            self.assertIn(os.path.join(d, "config.example.json"), found)
            self.assertNotIn(os.path.join(d, "config.example.json"), bare)
            with mock.patch.object(
                    SU, "_example_candidates", return_value=[bad, arr, good]):
                blank = SU._blank_config()
            self.assertEqual(blank["imap_host"], "H")
            self.assertFalse(
                {"shared_secret", "mailbox_user", "mailbox_password",
                 "oauth_refresh_token"} & set(blank))
            with mock.patch.object(
                    SU, "_example_candidates", return_value=[bad, arr]):
                self.assertEqual(
                    SU._load_example()["imap_host"], "imap.gmail.com")
            path = os.path.join(d, "n", "c.json")
            self.assertRaises(TypeError, SU._write_config, path, [])
            SU._write_config(path, {"a": 0})
            with mock.patch("os.path.abspath", return_value="x.json"):
                SU._write_config(path, {"a": 1})
            Path(path + ".tmp." + str(threading.get_ident())).write_text("")
            SU._write_config(path, {"a": 2})
            with mock.patch("os.chmod", side_effect=OSError):
                SU._write_config(path, {"a": 3})
            had = hasattr(os, "O_NOFOLLOW")
            saved = getattr(os, "O_NOFOLLOW", 0)
            if had:
                del os.O_NOFOLLOW
            os.O_BINARY = 0
            try:
                SU._write_config(path, {"a": 4})
            finally:
                if had:
                    setattr(os, "O_NOFOLLOW", saved)
                del os.O_BINARY
            for name in ("os.fdopen", "os.replace"):
                with mock.patch(name, side_effect=OSError("x")), \
                        self.assertRaises(OSError):
                    SU._write_config(path, {"a": 5})
            real, n = os.unlink, {"u": 0}

            def unlink(p):
                n["u"] += 1
                if n["u"] > 1:
                    raise OSError("u")
                return real(p)

            real_open, real_close = os.open, os.close
            opened = []

            def tracking_open(*args, **kwargs):
                fd = real_open(*args, **kwargs)
                opened.append(fd)
                return fd

            with mock.patch("os.open", tracking_open), \
                    mock.patch("os.fdopen", side_effect=OSError("f")), \
                    mock.patch("os.close", side_effect=OSError("c")), \
                    mock.patch("os.unlink", side_effect=unlink), \
                    self.assertRaises(OSError):
                SU._write_config(path, {"a": 6})
            # close() was simulated as broken, so the fd is still
            # open. Windows refuses to delete an open file
            # (WinError 32): the next write and TemporaryDirectory
            # both fail.
            for fd in opened:
                try:
                    real_close(fd)
                except OSError:
                    pass
            n["u"] = 0
            with mock.patch("os.open", side_effect=OSError("o")), \
                    mock.patch("os.unlink", side_effect=unlink), \
                    self.assertRaises(OSError):
                SU._write_config(path, {"a": 7})
            sec = "c0ffee" + "ab" * 29
            signed = {
                "mailbox_user": "a@b.c", "auth": "oauth",
                "oauth_client_id": "cid", "oauth_refresh_token": "old",
                "shared_secret": sec, "runner_id": "rid"}
            self.assertEqual(
                go(path, dict(signed), ["n", "n"])[0]["shared_secret"], sec)
            self.assertNotEqual(
                go(path, dict(signed), ["n", "yes", "y"])[0]["shared_secret"],
                sec)
            self.assertEqual(
                go(path, dict(signed), ["y", ""])[0]["oauth_refresh_token"],
                "tok")
            with self.assertRaises(SystemExit):
                go(path, {}, ["a@b.c", "2"], gp=EOFError)
            self.assertIn(
                "warning",
                go(path, {"mailbox_user": " "},
                   ["a@b.c", "", "", "cid", "y"], probe="nope")[1])
            kept = {
                "mailbox_user": "a@b.c", "auth": "password",
                "mailbox_password": "p", "oauth_client_id": "cid"}
            self.assertNotIn("warning", go(path, kept, ["", "y"])[1])
            with self.assertRaises(SystemExit):
                go(path, {}, ["x"], consent=None)
            Path(path).write_text("{")
            go(path, None, ["a@b.c", "2", "y"])
            Path(path).write_text(json.dumps({
                "mailbox_user": "a@b.c", "auth": "password",
                "mailbox_password": "p"}))
            self.assertEqual(go(path, None, ["2", "y"])[0]["auth"], "password")
            with mock.patch.object(
                    SU, "browser_consent",
                    side_effect=[SystemExit(1), SystemExit(1)]), \
                    mock.patch("builtins.input", side_effect=["y", "n"]), \
                    redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as caught:
                SU._browser_login_loop({})
            self.assertEqual(caught.exception.code, 2)
            with mock.patch("builtins.input", side_effect=["n", "yes"]), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(len(SU._accept_secret()), 64)
            with mock.patch(
                    "builtins.input", side_effect=["a@b.c", "2", "y"] * 2), \
                    mock.patch("getpass.getpass", return_value="pw"), \
                    redirect_stdout(io.StringIO()):
                with mock.patch.object(
                        sys, "argv",
                        ["setup.py", os.path.join(d, "z.json")]):
                    runpy.run_path(SU.__file__, run_name="__main__")
                with chdir(d), mock.patch.object(sys, "argv", ["setup.py"]):
                    runpy.run_path(SU.__file__, run_name="__main__")
            self.assertTrue(
                os.path.isfile(os.path.join(d, "z.json"))
                and os.path.isfile(os.path.join(d, "config.json")))
        self._imports()

    def _imports(self):
        import builtins
        real = builtins.__import__

        def wrapped(name, g=None, loc=None, frm=(), level=0, fail=False):
            blocked = ("runner.oauth", "runner.install")
            if name in blocked or (fail and name in ("oauth", "install")):
                raise ImportError(name)
            if name not in ("oauth", "install"):
                return real(name, g, loc, frm, level)
            mod = sys.modules.setdefault(name, types.ModuleType(name))
            mod.browser_consent = lambda c: "t"
            mod.refresh_access_token = lambda c: "t"
            mod.xoauth2_raw = lambda u, t: "a"
            mod._looks_like_placeholder = lambda s: False
            mod._looks_patterned = lambda s: False
            return mod

        try:
            for fail in (False, True):
                def importer(*a, _f=fail, **k):
                    return wrapped(*a, fail=_f, **k)
                with mock.patch("builtins.__import__", importer):
                    importlib.reload(SU)
            self.assertIsNone(SU.browser_consent)
            self.assertIsNone(SU._placeholder)
        finally:
            sys.modules.pop("oauth", None)
            sys.modules.pop("install", None)
            importlib.reload(SU)

        def blocked(name, g=None, loc=None, frm=(), level=0):
            if name in ("runner.oauth", "oauth"):
                raise ImportError(name)
            return real(name, g, loc, frm, level)

        class Ok:
            def __init__(self, *a, **k):
                return None

            def authenticate(self, *a, **k):
                return None

            def logout(self, *a, **k):
                return None

        with mock.patch("builtins.__import__", blocked), \
                mock.patch.object(SU, "refresh_access_token",
                                  return_value="t"), \
                mock.patch.object(SU.imaplib, "IMAP4_SSL", Ok):
            self.assertIn(
                "IMAP", SU._mailbox_probe({"mailbox_user": "a@b.c"}))


if __name__ == "__main__":
    unittest.main()
