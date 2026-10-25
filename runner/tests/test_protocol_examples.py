"""Queue D, item 3: PROTOCOL.md's examples and AGENTS.md's
"Do not emit" table, run as written.

Three parts:

1. Every ```json block in PROTOCOL.md still parses -- as a whole
   object, or as the fragment it is printed as (a quoted key and
   its value, wrapped in braces). An example that stops being
   valid JSON is a doc bug a reader hits on page one.

2. The section 3.1 job sketch and the section 3.2 result sketch,
   instantiated faithfully (placeholders filled with real values,
   optional members the sketch itself marks optional left to the
   ones a live job needs), signed, and run: the job through a
   full poll cycle, the result through the runner's own result
   verification. The canonical examples must be working shapes.

3. The "Do not emit" table from AGENTS.md, one test per row,
   through the poll cycle. Individual rows also live elsewhere
   (the URL rows in test_protocol_and_edges, the uppercase
   signature in test_connector_captures); this is the table run
   as a table, keyed to the doc's rows in the doc's order.
"""
import json
import os
import re
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from runner.runner import poll_once, sign_payload, verify_body  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402
from runner.tests.test_protocol_and_edges import (  # noqa: E402
    FakeIMAP, FakeSMTP, SECRET, SENDER, base_job, job_email,
    now_iso, read_result)

WRONG_KEY = "wrong" + "-secret-" + "for-tests"


def _protocol_blocks():
    with open(os.path.join(REPO, "PROTOCOL.md"), encoding="utf-8") as fh:
        text = fh.read()
    return re.findall(r"```json\n(.*?)```", text, re.DOTALL)


def _parse_block(block):
    try:
        return json.loads(block)
    except ValueError:
        return json.loads("{" + block + "}")


class ProtocolBlocksParseTest(unittest.TestCase):
    def test_every_json_block_in_protocol_md_parses(self):
        blocks = _protocol_blocks()
        self.assertGreaterEqual(len(blocks), 10)
        for i, block in enumerate(blocks):
            try:
                _parse_block(block)
            except ValueError as e:
                self.fail(f"PROTOCOL.md json block {i} does not parse: {e}")

    def test_the_job_and_result_sketches_are_among_the_blocks(self):
        kinds = set()
        for block in _protocol_blocks():
            try:
                obj = _parse_block(block)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("type") in ("job", "result"):
                kinds.add(obj["type"])
        self.assertEqual(kinds, {"job", "result"})


class _CycleRig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-d3-")
        self.cfg = {
            "mailbox_user": SENDER,
            "mailbox_password": SECRET,
            "shared_secret": SECRET,
            "imap_host": "fake", "imap_port": 993,
            "smtp_host": "fake", "smtp_port": 587,
            "max_job_age_sec": 3600,
            "max_output_bytes": 100000,
            "default_timeout_sec": 300,
        }
        self.seen_path = os.path.join(self.tmp, "seen.json")

    def cycle(self, mails):
        seen = {}
        imap, smtp = FakeIMAP(mails), FakeSMTP()
        poll_once(self.cfg, self.tmp, seen, self.seen_path,
                  imap=imap, smtp=smtp)
        return imap, smtp, seen

    def results(self, smtp):
        return [read_result(m) for m in smtp.sent]


class JobSketchAsWrittenTest(_CycleRig):
    def test_the_section_3_1_job_sketch_runs(self):
        sketch = None
        for block in _protocol_blocks():
            obj = _parse_block(block)
            if isinstance(obj, dict) and obj.get("type") == "job":
                sketch = obj
                break
        self.assertIsNotNone(sketch)
        jid = str(uuid.uuid4())
        job = {
            "v": sketch["v"],
            "type": "job",
            "job_id": jid,
            "issued_at": now_iso(),
            "kind": sketch["kind"],
            "script": "print('sketch-ok')\n",
            "interpreter": [sys.executable],
            "args": sketch["args"],
            "env": sketch["env"],
            "timeout_sec": sketch["timeout_sec"],
        }
        _, smtp, seen = self.cycle([job_email(job)])
        self.assertIn(jid, seen)
        results = self.results(smtp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["exit_code"], 0)
        self.assertIn("sketch-ok", results[0]["stdout"])


class ResultSketchVerifiesTest(unittest.TestCase):
    def test_the_section_3_2_result_sketch_verifies(self):
        sketch = None
        for block in _protocol_blocks():
            obj = _parse_block(block)
            if isinstance(obj, dict) and obj.get("type") == "result":
                sketch = obj
                break
        self.assertIsNotNone(sketch)
        result = dict(sketch)
        result["job_id"] = str(uuid.uuid4())
        result["remediation"] = dict(result["remediation"])
        result["remediation"]["received_digest"] = "ab" * 48
        del result["sig"]
        text = sign_payload(result, SECRET)
        back = verify_body(text, SECRET)
        self.assertEqual(back["job_id"], result["job_id"])
        self.assertEqual(back["exit_code"], 0)
        self.assertEqual(back["platform"]["protocol_versions"], [1])
        # Negative control: the same text under another secret fails.
        with self.assertRaises(ValueError):
            verify_body(text, WRONG_KEY)


def _mail_with_subject(payload, subject, secret=None):
    if secret is None:
        secret = SECRET
    jid = payload.get("job_id", "x")
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = subject
    wire = jobcrypto.encrypt_body(
        sign_payload(payload, secret), secret, job_id=jid,
        key_id=payload.get("key_id") or "", sign=sign_payload)
    msg.set_content(wire)
    return msg.as_bytes()


class DoNotEmitTableTest(_CycleRig):
    """AGENTS.md's table, row by row, in the table's order."""

    def test_issued_at_without_z_or_offset_is_rejected(self):
        jid = str(uuid.uuid4())
        naive = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        p = base_job(jid, issued_at=naive)
        _, smtp, _ = self.cycle([job_email(p)])
        self.assertEqual(len(smtp.sent), 0)

    def test_interpreter_as_a_string_is_rejected(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo SHOULD_NOT_RUN",
                     interpreter="sh")
        _, smtp, _ = self.cycle([job_email(p)])
        for r in self.results(smtp):
            self.assertNotEqual(r.get("exit_code"), 0)

    def test_missing_binary_interpreter_is_rejected_below_repair(self):
        # The row as it holds below repair latitude: at advise the
        # job is rejected, exit -2, "cannot start interpreter".
        # At the default (repair) latitude the runner repairs --
        # PROTOCOL.md section 3.2 -- which is the Q21 divergence
        # probed below against this table's unqualified row.
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo SHOULD_NOT_RUN",
                     interpreter=["/nonexistent/hp-no-such-binary"],
                     oracle_opinion="advise")
        _, smtp, _ = self.cycle([job_email(p)])
        results = self.results(smtp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["exit_code"], -2)
        self.assertIn("cannot start interpreter",
                      results[0]["stderr"])

    def test_unsafe_job_ids_are_rejected(self):
        for bad in ("../evil", ".", ".."):
            with self.subTest(job_id=bad):
                p = base_job(bad, kind="ping")
                mail = _mail_with_subject(
                    p, f"[HOMING-PIGEON] job {bad}")
                _, smtp, _ = self.cycle([mail])
                for r in self.results(smtp):
                    self.assertNotEqual(r.get("exit_code"), 0)

    def test_uppercase_hex_signature_is_accepted(self):
        payload = {"v": 1, "type": "job", "job_id": "upper-1",
                   "issued_at": now_iso(), "kind": "ping"}
        text = sign_payload(payload, SECRET)
        marker = ',"sig":"'
        i = text.rfind(marker)
        self.assertGreater(i, 0)
        upper = (text[:i + len(marker)]
                 + text[i + len(marker):i + len(marker) + 96].upper()
                 + text[i + len(marker) + 96:])
        back = verify_body(upper, SECRET)
        self.assertEqual(back["job_id"], "upper-1")

    def test_subject_with_extra_words_is_accepted(self):
        for subject_tpl in ("[HOMING-PIGEON] TEST job {jid}",
                            "Re: [HOMING-PIGEON] job {jid}"):
            with self.subTest(subject=subject_tpl):
                jid = str(uuid.uuid4())
                p = base_job(jid, kind="ping")
                mail = _mail_with_subject(p, subject_tpl.format(jid=jid))
                _, smtp, seen = self.cycle([mail])
                self.assertIn(jid, seen)
                self.assertEqual(len(smtp.sent), 1)

    def test_a_signature_that_does_not_match_is_rejected(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="ping")
        _, smtp, _ = self.cycle([job_email(p, secret=WRONG_KEY)])
        self.assertEqual(len(smtp.sent), 0)

    def test_non_https_urls_are_rejected(self):
        for url in ("file:///etc/passwd", "http://example.com/x.bin"):
            with self.subTest(url=url):
                jid = str(uuid.uuid4())
                p = base_job(jid, kind="exec", script="echo hi",
                             files=[{"name": "x.bin", "url": url}])
                _, smtp, _ = self.cycle([job_email(p)])
                results = self.results(smtp)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["exit_code"], -2)

    def test_an_unresolvable_download_host_is_rejected(self):
        from urllib.error import URLError
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec",
                     script_url="https://no-such-host.invalid/s")
        with patch("runner.runner._open_download",
                   side_effect=URLError("Name or service not known")):
            _, smtp, _ = self.cycle([job_email(p)])
        results = self.results(smtp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["exit_code"], -2)
        self.assertIn("does not resolve", results[0]["stderr"])

    def test_a_download_404_is_rejected(self):
        from urllib.error import HTTPError
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec",
                     script_url="https://example.com/missing")
        with patch("runner.runner._open_download",
                   side_effect=HTTPError(
                       "https://example.com/missing", 404,
                       "Not Found", None, None)):
            _, smtp, _ = self.cycle([job_email(p)])
        results = self.results(smtp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["exit_code"], -2)


class MissingBinaryRowProbe(_CycleRig):
    """FAILING BY DESIGN -- the Q21 finding (docs/use/questions.md).

    (a) Claim: AGENTS.md, "Do not emit" table: "`interpreter`
    pointing at a missing binary | Rejected". No qualification.
    (b) Scenario: a signed exec job naming an interpreter that
    does not exist on the runner, sent under the default
    configuration (no oracle_opinion member in the job; the
    opinion's default ceiling is repair).
    (c) Observed: the job is NOT rejected. The opinion repairs
    the interpreter to the platform default and the job runs,
    exit 0, with the repair stated in the result's oracle_opinion
    member (repaired: true, received_digest present) -- exactly
    what PROTOCOL.md section 3.2 describes at repair latitude.
    The rejection the table states happens only below repair
    latitude (pinned in DoNotEmitTableTest) or under the
    runner's refuse setting.
    (d) Do not make this pass by editing the test to expect the
    repair. Either the table row (and the Windows note under it)
    is amended to state the repair behavior -- the asker's
    recommendation in Q21, since PROTOCOL.md is the spec of
    record and the repair is a shipped, stated-in-the-result
    feature -- or the default changes. The decider's commit
    closes Q21 and this probe with it.
    """

    def test_the_table_row_as_written(self):
        jid = str(uuid.uuid4())
        p = base_job(jid, kind="exec", script="echo PROBE",
                     interpreter=["/nonexistent/hp-no-such-binary"])
        _, smtp, _ = self.cycle([job_email(p)])
        results = self.results(smtp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["exit_code"], -2,
                         "AGENTS.md says a missing-binary interpreter "
                         "is rejected; the runner repaired and ran it")


if __name__ == "__main__":
    unittest.main()
