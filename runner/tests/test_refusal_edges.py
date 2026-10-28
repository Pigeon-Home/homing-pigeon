# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""Refusal edges a local line-coverage pass found unrun.

Each test makes one guarded path run and holds it to what it is
there to say: the sender's verifier keeps its own shape and walk
checks, a hosted queue's refusal and a result output whose bytes do
not match their digest both end the command with 1, a file entry
whose url is not a string and a stage that cannot be written are
refused as poison, an extension manifest that is not text or not an
object is named and skipped, a config blob merges over a config that
is not an object, a first-key name is refused over additional_secrets
that is not an object, and the installed home on Windows is found
under the system drive.
"""
import argparse
import base64
import builtins
import contextlib
import hashlib
import io
import json
import os
import secrets
import sys
import tempfile
import unittest
from unittest import mock

from runner import runner as R  # noqa: E402
from runner.cloud import send_job as SJ  # noqa: E402
from runner.ops import extensions as EXT  # noqa: E402
from runner.ops import install as INS  # noqa: E402
from runner.ops import main as MAIN  # noqa: E402

SECRET = secrets.token_hex(32)


def _quiet():
    stack = contextlib.ExitStack()
    out, err = io.StringIO(), io.StringIO()
    stack.enter_context(contextlib.redirect_stdout(out))
    stack.enter_context(contextlib.redirect_stderr(err))
    return stack, out, err


class SenderVerifierTest(unittest.TestCase):
    def test_a_scalar_root_nests_nowhere(self):
        for value in (5, "text", None, 2.5):
            with self.subTest(value=value):
                self.assertFalse(SJ._nests_deeper_than(value, 1))

    def test_a_cycle_is_walked_once_and_carries_no_surrogate(self):
        loop = ["fine"]
        loop.append(loop)
        self.assertFalse(SJ._has_lone_surrogate(loop))
        loop.append("\ud800")
        self.assertTrue(SJ._has_lone_surrogate(loop))

    def test_the_shape_check_holds_whatever_the_extractor_hands_on(self):
        # The extractor yields text rooted at a root object today; the
        # verifier's own check is the last word if that ever changes.
        raw = "[1, 2, 3]"
        sig = SJ.hmac.new(SECRET.encode(), raw.encode(),
                          hashlib.sha384).hexdigest()
        with mock.patch.object(SJ, "_extract_signed",
                               return_value=(raw, sig)):
            with self.assertRaises(ValueError) as cm:
                SJ.verify_body("anything", SECRET)
        self.assertIn("not a JSON object", str(cm.exception))


class SenderCommandsTest(unittest.TestCase):
    def _new_args(self, **over):
        args = argparse.Namespace(
            job_id="edge-queue-1", kind="note", key_id=None, aud=None,
            reply_to=None, script_url=None, script_sha384=None,
            script_file=None, file=None, arg=None, env=None,
            interpreter=None, timeout=None, secret=SECRET, cleartext=True,
            to_queue="https://queue.example.test/t/x", queue_token_env=None)
        for key, value in over.items():
            setattr(args, key, value)
        return args

    def test_a_queue_that_refuses_the_job_ends_the_command_with_1(self):
        stack, _out, err = _quiet()
        with stack, mock.patch.object(SJ, "post_to_queue",
                                      return_value=(503, "busy " * 100)):
            rc = SJ.cmd_new(self._new_args())
        self.assertEqual(rc, 1)
        line = err.getvalue()
        self.assertIn("queue refused job edge-queue-1: HTTP 503: busy", line)
        self.assertLess(len(line), 300)

    def test_verify_with_an_outputs_dir_stops_on_a_bad_digest(self):
        good, bad = b"kept bytes\n", b"tampered\n"
        result = {"job_id": "edge-out-1", "type": "result",
                  "outputs": [
                      {"name": "ok.txt",
                       "content_b64": base64.b64encode(good).decode(),
                       "sha384": hashlib.sha384(good).hexdigest()},
                      {"name": "bad.txt",
                       "content_b64": base64.b64encode(bad).decode(),
                       "sha384": "0" * 96}]}
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "result.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(SJ.sign_payload(result, SECRET))
            dest = os.path.join(td, "out")
            args = argparse.Namespace(file=path, job_id=None, key_id=None,
                                      secret=SECRET, outputs_dir=dest)
            stack, out, err = _quiet()
            with stack:
                rc = SJ.cmd_verify(args)
            self.assertEqual(rc, 1)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("'bad.txt': bytes do not match their sha384",
                          err.getvalue())
            with open(os.path.join(dest, "ok.txt"), "rb") as fh:
                self.assertEqual(fh.read(), good)
            self.assertFalse(os.path.exists(os.path.join(dest, "bad.txt")))

    def test_outputs_that_are_not_a_list_write_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            dest = os.path.join(td, "never")
            for outs in ({"name": "a"}, "a.txt", 7):
                with self.subTest(outputs=outs):
                    self.assertEqual(SJ.write_outputs({"outputs": outs},
                                                      dest), 0)
            self.assertFalse(os.path.exists(dest))


def _exec_job(**extra):
    job = {"v": 1, "type": "job", "job_id": "edge-files-1", "kind": "exec",
           "interpreter": [sys.executable], "script": "pass"}
    job.update(extra)
    return job


class StagingTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.base = self.td.name

    def tearDown(self):
        self.td.cleanup()

    def test_a_file_url_that_is_not_a_string_is_poison(self):
        for url in (7, ["https://x/a"], {"href": "https://x/a"}, None):
            with self.subTest(url=url), \
                    self.assertRaises(R.JobRejected) as cm:
                R.execute_job({}, _exec_job(files=[{"name": "a", "url": url}]),
                              self.base)
            self.assertIn("'url' must be a string", str(cm.exception))

    def test_a_stage_that_cannot_be_written_is_poison(self):
        data = b"inline bytes"
        job = _exec_job(files=[{
            "name": "in/a.bin", "content_b64": base64.b64encode(data).decode(),
            "sha384": hashlib.sha384(data).hexdigest()}])
        real_open = builtins.open

        def refusing(file, mode="r", *a, **kw):
            if mode == "xb":
                raise PermissionError(13, "Permission denied", str(file))
            return real_open(file, mode, *a, **kw)

        with mock.patch("builtins.open", refusing), \
                self.assertRaises(R.JobRejected) as cm:
            R.execute_job({}, job, self.base)
        self.assertIn("cannot stage 'in/a.bin'", str(cm.exception))
        self.assertIn("Permission denied", str(cm.exception))


class ExtensionManifestTest(unittest.TestCase):
    def test_a_manifest_that_is_not_an_object_has_no_api_version(self):
        for manifest in (["api_version", 1], "api_version: 1", 1, None):
            with self.subTest(manifest=manifest):
                self.assertEqual(EXT.api_refusal(manifest),
                                 "manifest is not an object")

    def test_a_manifest_that_is_not_text_is_named_and_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            folder = os.path.join(td, "garbled")
            os.makedirs(folder)
            with open(os.path.join(folder, EXT.MANIFEST_FILE), "wb") as fh:
                fh.write(b'{"name": "garbled", "kind": "sense"\xff\xfe}')
            registry, problems = EXT.load_extensions(td)
        self.assertEqual(registry, {})
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith(
            "extension folder 'garbled': cannot read %s:" % EXT.MANIFEST_FILE),
            problems[0])


class InstallConfigTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.td.name, "config.json")

    def tearDown(self):
        self.td.cleanup()

    def _merge(self, existing):
        with open(self.cfg, "w", encoding="utf-8") as fh:
            fh.write(existing)
        stack, out, _err = _quiet()
        with stack:
            INS.merge_config_blob(self.cfg, json.dumps({"runner_id": "edge"}))
        with open(self.cfg, encoding="utf-8") as fh:
            return json.load(fh), out.getvalue()

    def test_a_blob_merges_over_a_config_that_does_not_parse(self):
        cfg, said = self._merge("{not json")
        self.assertEqual(cfg, {"runner_id": "edge"})
        self.assertIn("config blob: wrote runner_id", said)

    def test_a_blob_merges_over_a_config_that_is_not_an_object(self):
        cfg, _said = self._merge('["shared_secret", "x"]')
        self.assertEqual(cfg, {"runner_id": "edge"})

    def test_a_first_key_name_over_a_non_object_keyring_is_refused(self):
        with open(self.cfg, "w", encoding="utf-8") as fh:
            json.dump({"shared_secret": SECRET,
                       "additional_secrets": ["not", "an", "object"]}, fh)
        stack, _out, err = _quiet()
        with stack, self.assertRaises(SystemExit) as cm:
            INS._name_first_key(self.cfg, SECRET, "laptop")
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("additional_secrets in config is not an object",
                      err.getvalue())


class InstalledHomeTest(unittest.TestCase):
    def test_windows_finds_the_home_under_the_system_drive(self):
        with tempfile.TemporaryDirectory() as td:
            drive = os.path.join(td, "C")
            home = os.path.join(drive, "homing-pigeon")
            with mock.patch.object(sys, "platform", "win32"), \
                    mock.patch.dict(os.environ, {"SystemDrive": drive}):
                self.assertIsNone(MAIN._installed_config())
                os.makedirs(home)
                cfg = os.path.join(home, "config.json")
                with open(cfg, "w", encoding="utf-8") as fh:
                    fh.write("{}")
                found = MAIN._installed_config()
        self.assertEqual(os.path.normpath(found), os.path.normpath(cfg))


if __name__ == "__main__":
    unittest.main()
