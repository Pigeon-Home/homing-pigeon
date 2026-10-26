# Agent-Stamp: 40000e00-1234-4abc-9def-0123456789ab
"""Every parser that reads input the runner did not write, held to its contract.

PROPERTY_ROSTER below is the audit record: each untrusted-input parser,
the promise it makes, and the property test that proves it on generated
input. RosterTest fails if a parser on the roster disappears, if its
named test is missing, or if that test is not a Hypothesis property, so
the roster cannot quietly rot. Earlier property suites cover the job
signature core (test_properties), DTLS (test_dtls_fuzz), Oracle intake
(test_oracle_intake_fuzz) and the eight feed decoders
(test_feed_decoder_properties); they are listed in ELSEWHERE.

What the first pass of these properties found (2026-10-25), each now a
regression test below:
- A signed job whose JSON escapes an unpaired surrogate ("\\ud800")
  was never answered and never marked seen: the size check, the
  script file and the result all raised UnicodeEncodeError, and the
  job was retried on every poll. It is refused once at intake.
- extsources.extract_archive let a truncated gzip's EOFError (and the
  other decompressor errors) escape instead of SourceError.
- extsources.version_tuple raised ValueError on a tag with a number
  past the interpreter's 4,300-digit int-string limit.
"""
import ast
import importlib
import io
import json
import math
import os
import shutil
import tarfile
import tempfile
import unittest
import zipfile

try:
    from hypothesis import given, settings, strategies as st
except ImportError:  # pragma: no cover - hypothesis is a test-only dep
    given = None

from runner.cloud import send_job as SJ  # noqa: E402
from runner.guard import confval as CV  # noqa: E402
from runner.guard import textutil as TU  # noqa: E402
from runner.ops import extensions as EX  # noqa: E402
from runner.ops import extsources as ES  # noqa: E402
from runner.wire import mailbox as MB  # noqa: E402
from runner.wire import platformcard as PC  # noqa: E402
from runner.wire import protocol_v2 as P2  # noqa: E402
from runner.wire import verify as V  # noqa: E402

SECRET = "5e0f3c2a9b8d7e6f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7081"
DEEP = "[" * 200000

# parser -> (its promise, the property test in this file that proves it)
PROPERTY_ROSTER = {
    "runner.wire.protocol_v2.subject_kind":
        ("any subject: None or (kind, msg_id), never raises",
         "WireProperties.test_v2_subject_kind"),
    "runner.wire.protocol_v2.validate":
        ("any value: returns or raises ValueError",
         "WireProperties.test_v2_validate"),
    "runner.wire.protocol_v2.clean_pass":
        ("any plan: a bool, never raises", "WireProperties.test_v2_clean_pass"),
    "runner.wire.verify.verify_body":
        ("any body: a payload or ValueError; deep nesting included",
         "WireProperties.test_verify_body_refuses_only_with_valueerror"),
    "runner.wire.verify.verify_body_keyed":
        ("any body and key map: (payload, key_id) or ValueError",
         "WireProperties.test_verify_body_keyed"),
    "runner.wire.verify.check_audience":
        ("any cfg and payload: None or a reason, never raises",
         "WireProperties.test_check_audience"),
    "runner.cloud.send_job.verify_body":
        ("the SI-side verifier agrees with the runner's, both ways",
         "WireProperties.test_two_signers_agree"),
    "runner.wire.mailbox._valid_reply_to":
        ("any job: None or one address with no CR or LF",
         "WireProperties.test_reply_to"),
    "runner.wire.platformcard.build_card":
        ("any tier and cfg: a card, None, or ValueError",
         "WireProperties.test_platform_card"),
    "runner.ops.extensions.parse_manifest":
        ("any value or text: a manifest or ValueError",
         "ExtensionProperties.test_parse_manifest"),
    "runner.ops.extsources.parse_declaration":
        ("any value or text: a declaration or ValueError",
         "ExtensionProperties.test_parse_declaration"),
    "runner.ops.extsources._clean_rel_path":
        ("a relative forward-slash path with no '.', '..' or root, or ValueError",
         "ExtensionProperties.test_clean_rel_path"),
    "runner.ops.extsources._https_url":
        ("an https URL or ValueError", "ExtensionProperties.test_https_url"),
    "runner.ops.extsources.version_tuple":
        ("None or a tuple of ints, never raises",
         "ExtensionProperties.test_version_tuple"),
    "runner.ops.extsources._safe_member":
        ("None or portable path parts", "ExtensionProperties.test_safe_member"),
    "runner.ops.extsources.extract_archive":
        ("stats or SourceError; nothing written outside dest",
         "ExtensionProperties.test_extract_archive"),
    "runner.guard.confval.number":
        ("the default or a finite number inside [lo, hi]",
         "ConfigProperties.test_number_and_integer"),
    "runner.guard.confval.integer":
        ("the default or an int inside [lo, hi]",
         "ConfigProperties.test_number_and_integer"),
    "runner.guard.confval.port":
        ("the default or 1..65535", "ConfigProperties.test_port_and_choice"),
    "runner.guard.confval.choice":
        ("the default or one of the choices",
         "ConfigProperties.test_port_and_choice"),
    "runner.guard.textutil._json_safe":
        ("strict JSON for any value, cycles included",
         "ConfigProperties.test_json_safe"),
    "runner.guard.textutil._fromiso":
        ("a datetime or ValueError", "ConfigProperties.test_fromiso"),
    "runner.guard.textutil._lone_surrogate":
        ("True exactly when some string in the value cannot be UTF-8",
         "ConfigProperties.test_lone_surrogate"),
}

# Untrusted-input parsers with property suites of their own.
ELSEWHERE = {
    "runner.runner.verify_body / sign_payload / redact_text": "test_properties",
    "runner.wire.dtlsproto": "test_dtls_fuzz",
    "runner.wire.jobcrypto": "test_oracle_intake_fuzz",
    "runner/extensions/*-feed decoders": "test_feed_decoder_properties",
    "runner.transport_extensions.channel": "test_result_stash",
    "file names a job stages": "test_workspace_isolation",
}


# --- the checks, plain so the regressions run without Hypothesis -----

def check_refuses_with(exc, fn, *args):
    try:
        return fn(*args)
    except exc:
        return None


def check_confval(value):
    for lo, hi in ((None, None), (0, 10), (-5, 5)):
        r = CV.number(value, 7, lo, hi) if lo is not None else CV.number(value, 7)
        assert r == 7 or (isinstance(r, (int, float))
                          and not isinstance(r, bool) and math.isfinite(r)
                          and (lo is None or lo <= r <= hi)), (value, r)
        i = CV.integer(value, 3, lo, hi) if lo is not None else CV.integer(value, 3)
        assert isinstance(i, int) and not isinstance(i, bool), (value, i)
        assert i == 3 or lo is None or lo <= i <= hi, (value, i)
    p = CV.port(value, 80)
    assert p == 80 or (isinstance(p, int) and 1 <= p <= 65535), (value, p)
    assert CV.choice(value, ("a", "b"), "a") in ("a", "b")


def check_rel_path(value):
    try:
        out = ES._clean_rel_path(value, "where")
    except ValueError:
        return
    assert isinstance(out, str) and out, out
    parts = out.split("/")
    assert "\\" not in out and not out.startswith("/"), out
    assert all(p not in ("", ".", "..") for p in parts), out


def check_safe_member(value):
    out = ES._safe_member(value)
    if out is None:
        return
    assert isinstance(out, list) and out, out
    for p in out:
        assert isinstance(p, str) and p not in ("", ".", "..")
        assert "/" not in p and "\\" not in p and ":" not in p, p


def check_archive(data):
    tmp = tempfile.mkdtemp(prefix="hp-archive-prop-")
    try:
        src = os.path.join(tmp, "a.bin")
        dest = os.path.join(tmp, "out")
        with open(src, "wb") as fh:
            fh.write(data)
        try:
            stats = ES.extract_archive(src, dest, 1 << 20)
            assert set(stats) >= {"files", "bytes", "skipped"}, stats
        except ES.SourceError:
            pass
        root = os.path.realpath(tmp)
        for dirpath, dirnames, filenames in os.walk(tmp):
            for name in dirnames + filenames:
                full = os.path.realpath(os.path.join(dirpath, name))
                assert full.startswith(root), full
                assert not os.path.islink(os.path.join(dirpath, name)), name
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _tar(names, gz=True, cut=None, kinds=None):
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz" if gz else "w") as t:
        for i, name in enumerate(names):
            ti = tarfile.TarInfo(name)
            kind = (kinds or [tarfile.REGTYPE] * len(names))[i]
            ti.type = kind
            ti.linkname = "../../../etc/passwd"
            body = b"hi" if kind == tarfile.REGTYPE else b""
            ti.size = len(body)
            t.addfile(ti, io.BytesIO(body) if body else None)
    data = b.getvalue()
    return data[:cut] if cut is not None else data


# --- regressions --------------------------------------------------------

class FoundTodayTest(unittest.TestCase):
    def test_a_surrogate_job_is_refused_once_and_marked_seen(self):
        import hashlib
        import hmac
        import io as _io
        from contextlib import redirect_stderr, redirect_stdout
        from email.message import EmailMessage
        import runner.tests.test_runner as TR
        from runner import runner as R
        from runner.wire import jobcrypto
        h = TR.RunnerTest("test_ping_roundtrip")
        h.setUp()
        try:
            for field in ('"note":"x\\ud800y"', '"script":"echo #\\ud800"',
                          '"\\udfff":1'):
                with self.subTest(field=field):
                    jid = "sur-%d" % abs(hash(field))
                    p = TR.job_payload(jid, kind="exec", script="echo hi")
                    p.pop("script") if "script" in field else None
                    text = json.dumps(p, separators=(",", ":"))[:-1] + "," \
                        + field + "}"
                    sig = hmac.new(TR.SECRET.encode(), text.encode(),
                                   hashlib.sha384).hexdigest()
                    signed = text[:-1] + ',"sig":"' + sig + '"}'
                    wire = jobcrypto.encrypt_body(
                        signed, TR.SECRET, job_id=jid, key_id="",
                        sign=R.sign_payload)
                    msg = EmailMessage()
                    msg["From"] = msg["To"] = TR.SENDER
                    msg["Subject"] = "[HOMING-PIGEON] job " + jid
                    msg.set_content(wire)
                    imap = TR.FakeIMAP([msg.as_bytes()])
                    smtp = TR.FakeSMTP()
                    out = _io.StringIO()
                    with redirect_stdout(out), redirect_stderr(out):
                        R.poll_once(h.cfg, h.tmp, {},
                                    os.path.join(h.tmp, "seen.json"),
                                    imap=imap, smtp=smtp)
                    self.assertEqual([str(s) for s in imap.flagged], ["1"])
                    self.assertIn("unpaired UTF-16 surrogate", out.getvalue())
                    self.assertNotIn("will retry", out.getvalue())
        finally:
            h.tearDown()

    def test_a_damaged_archive_is_a_source_error(self):
        full = _tar(["pkg/a", "pkg/b"])
        for cut in (12, len(full) // 2, len(full) - 9):
            with self.subTest(cut=cut):
                check_archive(full[:cut])
        bad_zip = io.BytesIO()
        with zipfile.ZipFile(bad_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("pkg/a", b"x" * 5000)
        data = bytearray(bad_zip.getvalue())
        data[60:80] = b"\xff" * 20
        check_archive(bytes(data))

    def test_a_tag_past_the_int_digit_limit_is_no_version(self):
        self.assertIsNone(ES.version_tuple("x-" + "9" * 5000 + ".1"))
        self.assertEqual(ES.version_tuple("suricata-8.0.1"), (8, 0, 1))

    def test_links_and_escapes_never_leave_the_target(self):
        check_archive(_tar(["../evil", "/abs", "pkg/../../b", "pkg/ok",
                            "pkg/ln", "pkg/hard"],
                           kinds=[tarfile.REGTYPE] * 4
                           + [tarfile.SYMTYPE, tarfile.LNKTYPE]))

    def test_deep_nesting_is_refused_not_crashed(self):
        for fn in (V.verify_body, SJ.verify_body):
            check_refuses_with(ValueError, fn, DEEP, SECRET)
        check_refuses_with(ValueError, EX.parse_manifest, DEEP)
        check_refuses_with(ValueError, ES.parse_declaration, DEEP)


class RosterTest(unittest.TestCase):
    def test_every_parser_on_the_roster_exists(self):
        for dotted in PROPERTY_ROSTER:
            mod, _, name = dotted.rpartition(".")
            with self.subTest(parser=dotted):
                self.assertTrue(callable(getattr(importlib.import_module(mod),
                                                 name, None)))

    def test_every_roster_test_is_a_property(self):
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        given_tests = set()
        for cls in ast.walk(tree):
            if isinstance(cls, ast.ClassDef):
                for fn in cls.body:
                    if isinstance(fn, ast.FunctionDef) and any(
                            "given" in ast.unparse(d) for d in fn.decorator_list):
                        given_tests.add("%s.%s" % (cls.name, fn.name))
        for dotted, (_promise, test) in PROPERTY_ROSTER.items():
            with self.subTest(parser=dotted):
                self.assertIn(test, given_tests)

    def test_the_other_suites_are_still_there(self):
        here = os.path.dirname(os.path.abspath(__file__))
        for what, module in ELSEWHERE.items():
            with self.subTest(what=what):
                path = os.path.join(here, module + ".py")
                with open(path, encoding="utf-8") as fh:
                    self.assertIn("@given", fh.read())


# --- properties ---------------------------------------------------------

if given is not None:
    _key = st.sampled_from([
        "v", "type", "job_id", "msg_id", "issued_at", "expect", "why",
        "question", "deadline_sec", "plan", "findings", "name", "kind",
        "entry", "api_version", "version", "publisher", "description",
        "capabilities", "sources", "upstream", "url", "ref", "commit",
        "paths", "files", "reply_to", "runner_id", "key_id", "sig",
        "default_interpreter", "repo", "path", "sha256", "license",
        "github", "location", "tag_match", "asset_match"])
    _text = st.text(max_size=60)
    _scalar = st.one_of(
        st.none(), st.booleans(), st.integers(),
        st.integers(min_value=10 ** 20, max_value=10 ** 400),
        st.floats(), _text,
        st.sampled_from(["2026-10-25T12:00:00Z", "https://example.com/x",
                         "../x", "/abs", "a\\b", "C:x", "latest",
                         "sense", "transport", "question", "answer",
                         "determination", "proceed"]))
    _value = st.recursive(
        _scalar,
        lambda c: st.one_of(st.lists(c, max_size=5),
                            st.dictionaries(st.one_of(_key, _text), c,
                                            max_size=8)),
        max_leaves=24)
    _obj = st.dictionaries(_key, _value, max_size=12)
    _quick = settings(max_examples=150, deadline=None)

    class WireProperties(unittest.TestCase):
        @_quick
        @given(s=st.one_of(_text, st.builds(
            lambda k, i: "[HOMING-PIGEON] %s %s" % (k, i),
            st.sampled_from(["question", "answer", "determination", "job",
                             "query"]), _text)))
        def test_v2_subject_kind(self, s):
            r = P2.subject_kind(s)
            self.assertTrue(r is None or isinstance(r, tuple))

        @_quick
        @given(v=st.one_of(_value, _obj, st.builds(
            lambda o, k: dict(o, v=2, type=k), _obj,
            st.sampled_from(["question", "answer", "determination"]))))
        def test_v2_validate(self, v):
            check_refuses_with(ValueError, P2.validate, v)

        @_quick
        @given(v=_value)
        def test_v2_clean_pass(self, v):
            self.assertIsInstance(P2.clean_pass(v), bool)

        @_quick
        @given(body=st.one_of(_text, _value.map(
            lambda v: json.dumps(v, default=str))), secret=_text)
        def test_verify_body_refuses_only_with_valueerror(self, body, secret):
            check_refuses_with(ValueError, V.verify_body, body, secret or "x")
            check_refuses_with(ValueError, SJ.verify_body, body, secret or "x")

        @_quick
        @given(body=st.one_of(_text, _obj.map(
            lambda o: V.sign_payload(TU._json_safe(o), SECRET)
            if not TU._lone_surrogate(o) else "x")),
            keys=st.one_of(_value, st.just({"default": SECRET})))
        def test_verify_body_keyed(self, body, keys):
            r = check_refuses_with(ValueError, V.verify_body_keyed, body, keys)
            self.assertTrue(r is None or (isinstance(r, tuple) and len(r) == 2))

        @_quick
        @given(cfg=_value, payload=_value)
        def test_check_audience(self, cfg, payload):
            r = V.check_audience(cfg if isinstance(cfg, dict) else {}, payload)
            self.assertTrue(r is None or isinstance(r, str))

        @_quick
        @given(payload=_obj)
        def test_two_signers_agree(self, payload):
            payload = TU._json_safe(payload)
            if TU._lone_surrogate(payload):
                return
            try:
                body = V.sign_payload(payload, SECRET)
            except ValueError:
                return
            self.assertEqual(SJ.verify_body(body, SECRET),
                             V.verify_body(body, SECRET))
            self.assertEqual(V.verify_body(SJ.sign_payload(payload, SECRET),
                                           SECRET),
                             V.verify_body(body, SECRET))

        @_quick
        @given(job=st.one_of(_value, st.builds(
            lambda r: {"reply_to": r}, st.one_of(
                _text, _value, st.builds(lambda a, b: "%s@%s" % (a, b),
                                         _text, _text),
                st.just("a@b.c\r\nBcc: x@y.z")))))
        def test_reply_to(self, job):
            r = MB._valid_reply_to(job)
            self.assertTrue(r is None or (isinstance(r, str) and "@" in r
                                          and "\r" not in r and "\n" not in r))

        @_quick
        @given(tier=st.one_of(_text, _value, st.sampled_from(
            ["full", "minimal", "none"])), cfg=st.one_of(st.none(), _obj))
        def test_platform_card(self, tier, cfg):
            check_refuses_with(ValueError, PC.build_card, tier, cfg)

    class ExtensionProperties(unittest.TestCase):
        @_quick
        @given(v=st.one_of(_value, _obj, _value.map(
            lambda v: json.dumps(v, default=str)), _text))
        def test_parse_manifest(self, v):
            check_refuses_with(ValueError, EX.parse_manifest, v)

        @_quick
        @given(v=st.one_of(_value, _obj, _value.map(
            lambda v: json.dumps(v, default=str)), _text))
        def test_parse_declaration(self, v):
            check_refuses_with(ValueError, ES.parse_declaration, v)

        @_quick
        @given(v=st.one_of(_text, _value, st.lists(st.sampled_from(
            ["a", "..", ".", "", "b", "\\", "C:"]), max_size=6).map("/".join)))
        def test_clean_rel_path(self, v):
            check_rel_path(v)

        @_quick
        @given(v=st.one_of(_text, _value, _text.map(lambda t: "https://" + t)))
        def test_https_url(self, v):
            r = check_refuses_with(ValueError, ES._https_url, v, "where")
            self.assertTrue(r is None or str(r).startswith("https://"))

        @_quick
        @given(v=st.one_of(_text, _value, st.builds(
            lambda a, k: "%s-%s.1" % (a, "9" * k), _text,
            st.integers(min_value=1, max_value=6000))))
        def test_version_tuple(self, v):
            r = ES.version_tuple(v)
            self.assertTrue(r is None or (isinstance(r, tuple) and all(
                isinstance(x, int) for x in r)))

        @_quick
        @given(v=st.one_of(_text, _value))
        def test_safe_member(self, v):
            check_safe_member(v)

        @settings(max_examples=60, deadline=None)
        @given(data=st.one_of(
            st.binary(max_size=600),
            st.builds(lambda names, cut: _tar(names, cut=cut),
                      st.lists(st.one_of(
                          st.sampled_from(["../e", "/a", "p/f", "p/../../b",
                                           "C:\\w", "p/" + "x" * 300]),
                          st.text(alphabet="abc./", min_size=1, max_size=20)),
                          max_size=5),
                      st.one_of(st.none(), st.integers(0, 600)))))
        def test_extract_archive(self, data):
            check_archive(data)

    class ConfigProperties(unittest.TestCase):
        @_quick
        @given(v=_value)
        def test_number_and_integer(self, v):
            check_confval(v)

        @_quick
        @given(v=st.one_of(_value, st.integers(-70000, 70000).map(str)))
        def test_port_and_choice(self, v):
            check_confval(v)

        @_quick
        @given(v=_value)
        def test_json_safe(self, v):
            if isinstance(v, list):
                v.append(v)  # a cycle
            json.dumps(TU._json_safe(v), allow_nan=False, default=str)

        @_quick
        @given(v=st.one_of(_text, _value, st.datetimes().map(
            lambda d: d.isoformat() + "Z")))
        def test_fromiso(self, v):
            check_refuses_with(ValueError, TU._fromiso, v)

        @_quick
        @given(v=_value)
        def test_lone_surrogate(self, v):
            try:
                json.dumps(v, ensure_ascii=False, default=str).encode("utf-8")
                encodable = True
            except UnicodeEncodeError:
                encodable = False
            except (TypeError, ValueError, RecursionError):
                return
            self.assertEqual(TU._lone_surrogate(v), not encodable)


if __name__ == "__main__":
    unittest.main()
