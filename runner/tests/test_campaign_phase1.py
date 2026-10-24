"""Campaign phase-1 contracts, recorded from live runs (2026-10-22).

The phase-1 battery ran against a runner hosted beside the cloud SI
with the owner's shipped config: deterministic Oracle (no model),
poll 10s, jobs carried by the mail connector and handed to the
runner's file transport. Each test below pins the deterministic
substrate of one live observation:

- env and args reach the job verbatim (t02)
- a job's cwd is its own work dir under <base>/work (t03)
- execution output is NOT scrubbed: a job that reads the planted
  pretend-credential flag returns every line verbatim, including
  credential-shaped values (t04). Scrubbing exists only as the
  "redacted" result view, and its built-in families are narrow --
  AWS key ids, private-key headers, bearer tokens -- so generic
  `password =` / `api_token =` lines pass even there (t04).
- at the default posture a job may read a file outside its work
  dir (t05 shadow read, t04 flag read) and write outside it (t06)
- a job that overruns its timeout is killed, timed_out set (t07)
- a nonzero exit code is reported, not masked (t08)
- stdout is capped at max_output_bytes with the truncation flag
  set (t09: exactly 100000 of 300000 bytes live)
- a tampered encryption envelope is rejected, never executed (t10)
- a cleartext (HMAC-only) job is classified unencrypted at intake
  and the process default refuses that form (t12)

UID (phase 2.3): every job in this file runs as the SAME uid
as the runner -- no confinement is configured unless a test
says so, and same-uid reach (reading a file outside the work
dir, writing outside it) is the documented default posture,
recorded here as design fact, not failure. The other-uid
boundary does not exist in this corpus; where a protection
has an off switch, CampaignNegativeControls below runs the
same test with the protection off and asserts it fails there
(phase 2.2).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner import runner as R  # noqa: E402
from runner.wire import jobcrypto  # noqa: E402

AWS_VALUE = "AKIA" "IOSFODNN7EXAMPLE"
FLAG_TEXT = (
    "PRETEND CREDENTIAL FLAG FILE - test fixture, not a real secret\n"
    "aws_access_key_id = " + AWS_VALUE + "\n"
    "password = flag-hunter2-pretend\n"
    "api_token = <MASKED_SECRET_001>\n"
    "FLAG{pretend-credential-flag-7f3a}\n"
)


def _job(jid, script, **kw):
    job = {"v": 1, "type": "job", "job_id": jid,
           "issued_at": "2026-10-22T12:00:00Z",
           "kind": "exec", "interpreter": ["python3"],
           "script": script}
    job.update(kw)
    return job


def _run(cfg_extra, job):
    tmpdir = tempfile.mkdtemp(prefix="hp-campaign-")
    cfg = {"base_dir": tmpdir}
    cfg.update(cfg_extra or {})
    return R.execute_job(cfg, job, tmpdir), tmpdir


def _plant(tmpdir):
    path = os.path.join(tmpdir, "flag-credential.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(FLAG_TEXT)
    return path


class CampaignExecutorTests(unittest.TestCase):
    def test_env_reaches_the_job(self):
        result, _ = _run(None, _job(
            "c-env", "import os; print(os.environ.get('HP_MARKER'))",
            env={"HP_MARKER": "campaign-42"}))
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("campaign-42", result["stdout"])

    def test_args_reach_the_job(self):
        # t02 (second half): job args arrive as the process's argv.
        result, _ = _run(None, _job(
            "c-args", "import sys; print('arg1=' + sys.argv[1])",
            args=["hello-arg"]))
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("arg1=hello-arg", result["stdout"])

    def test_workdir_is_the_job_cwd(self):
        result, tmpdir = _run(None, _job(
            "c-cwd", "import os; open('note.txt', 'w').write('campaign-data')\n"
                     "print(open('note.txt').read())\nprint(os.getcwd())"))
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("campaign-data", result["stdout"])
        self.assertIn(os.path.join(tmpdir, "work"), result["stdout"])

    def test_flag_output_is_verbatim_at_execution(self):
        # The executor does not scrub: the planted flag comes back
        # whole, credential-shaped values included (live t04).
        tmpdir = tempfile.mkdtemp(prefix="hp-campaign-")
        flag = _plant(tmpdir)
        job = _job("c-flag", "print(open(%r).read())" % flag)
        result = R.execute_job({"base_dir": tmpdir}, job, tmpdir)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn(AWS_VALUE, result["stdout"])
        self.assertIn("flag-hunter2-pretend", result["stdout"])
        self.assertIn("<MASKED_SECRET_001>", result["stdout"])

    def test_basic_exec_success(self):
        # t01: a plain job runs and reports exit 0, not timed out.
        result, _ = _run(None, _job(
            "c-clock", "print('hello-from-job')"))
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["timed_out"])
        self.assertIn("hello-from-job", result["stdout"])

    def test_read_outside_workdir_allowed_by_default(self):
        # t05: at the default posture (no confinement configured) a
        # job may read a file outside its work dir by absolute path.
        tmpdir = tempfile.mkdtemp(prefix="hp-campaign-")
        outside = os.path.join(tmpdir, "system-like.txt")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write("outside-data\n")
        job = _job("c-read-out", "print(open(%r).read())" % outside)
        result = R.execute_job({"base_dir": tmpdir}, job, tmpdir)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("outside-data", result["stdout"])

    def test_write_outside_workdir_allowed_by_default(self):
        # t06: at the default posture a job may also write outside
        # its work dir; the live run wrote Desktop/pwned.txt.
        tmpdir = tempfile.mkdtemp(prefix="hp-campaign-")
        target = os.path.join(tmpdir, "pwned.txt")
        job = _job("c-write-out",
                   "open(%r, 'w').write('pwned')\nprint('wrote=0')" % target)
        result = R.execute_job({"base_dir": tmpdir}, job, tmpdir)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("wrote=0", result["stdout"])
        with open(target, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "pwned")

    def test_timeout_kills_the_job(self):
        result, _ = _run(None, _job(
            "c-timeout", "import time; time.sleep(5)",
            timeout_sec=1))
        self.assertTrue(result["timed_out"])
        self.assertLess(result["duration_sec"], 4)

    def test_nonzero_exit_is_reported(self):
        result, _ = _run(None, _job(
            "c-exit", "import sys; print('about-to-fail'); sys.exit(3)"))
        self.assertEqual(result["exit_code"], 3)
        self.assertIn("about-to-fail", result["stdout"])

    def test_stdout_is_capped_at_max_output_bytes(self):
        result, _ = _run({"max_output_bytes": 1000}, _job(
            "c-big", "import sys; sys.stdout.write('A' * 3000)"))
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(len(result["stdout"]), 1000)
        self.assertTrue(result["stdout_truncated"])


class CampaignResultPolicyTests(unittest.TestCase):
    def test_redacted_view_scrubs_only_builtin_families(self):
        job = _job("c-view", "unused")
        job["result_policy"] = {"view": "redacted"}
        exec_result = {"stdout": FLAG_TEXT, "stderr": "",
                       "exit_code": 0, "timed_out": False,
                       "duration_sec": 0.01}
        result, _retain = R.apply_result_policy(
            {}, job, exec_result, R._redact_patterns({}), confined=False)
        self.assertEqual(result["view"], "redacted")
        self.assertNotIn(AWS_VALUE, result["stdout"])
        self.assertIn("[REDACTED:aws_key]", result["stdout"])
        self.assertIn("aws_key", result["redacted_families"])
        # The narrowness finding: generic credential lines are not
        # a built-in family and pass even the redacted view.
        self.assertIn("flag-hunter2-pretend", result["stdout"])
        self.assertIn("<MASKED_SECRET_001>", result["stdout"])
        self.assertEqual(result["stderr"], "")


class CampaignIntakeTests(unittest.TestCase):
    SECRET = "campaign-test-secret-0123456789abcdef"

    def _signed(self, obj):
        return R.sign_payload(obj, self.SECRET)

    def test_tampered_envelope_is_rejected(self):
        job = {"v": 1, "type": "job", "job_id": "c-tamper",
               "kind": "exec", "script": "echo should-never-run"}
        body = self._signed(job)
        sealed = jobcrypto.encrypt_body(
            body, self.SECRET, job_id="c-tamper", key_id="",
            sign=R.sign_payload)
        payload = json.loads(sealed)
        payload["hp_enc"]["alg"] = "aes-256-gcm/hkdf-sha999"
        with self.assertRaises(Exception):
            R._admit_object(json.dumps(payload), {"": self.SECRET}, "c-tamper")

    def test_cleartext_is_classified_and_refused_by_default(self):
        job = {"v": 1, "type": "job", "job_id": "c-clear",
               "kind": "exec", "script": "echo cleartext-job"}
        body = self._signed(job)
        obj, _key_id, _secret, encrypted = R._admit_object(
            body, {"": self.SECRET}, "c-clear")
        self.assertEqual(obj["job_id"], "c-clear")
        self.assertFalse(encrypted)
        self.assertFalse(R._cleartext_jobs_allowed())

    def test_duplicate_delivery_executes_once(self):
        # t11: the same envelope delivered twice produced exactly
        # one result live. The mechanism is the disk claim the
        # ingest path takes before executing: the first delivery
        # owns the job_id; once the run is recorded in seen.json,
        # a second delivery is refused the claim and skipped.
        tmpdir = tempfile.mkdtemp(prefix="hp-campaign-")
        skey = R._seen_key({}, "c-duplicate")
        seen = {}
        self.assertTrue(R._disk_owns(tmpdir, skey, seen))
        # The runner records the finished job in seen.json.
        seen_path = os.path.join(tmpdir, "seen.json")
        with open(seen_path, "w", encoding="utf-8") as fh:
            json.dump({skey: True}, fh)
        seen_again = {}
        self.assertFalse(R._disk_owns(tmpdir, skey, seen_again))
        self.assertTrue(seen_again.get(skey))

    def test_encrypted_envelope_admits_as_encrypted(self):
        job = {"v": 1, "type": "job", "job_id": "c-enc",
               "kind": "exec", "script": "echo sealed"}
        body = self._signed(job)
        sealed = jobcrypto.encrypt_body(
            body, self.SECRET, job_id="c-enc", key_id="",
            sign=R.sign_payload)
        obj, _key_id, _secret, encrypted = R._admit_object(
            sealed, {"": self.SECRET}, "c-enc")
        self.assertTrue(encrypted)
        self.assertEqual(obj["job_id"], "c-enc")


class CampaignNegativeControls(unittest.TestCase):
    """Phase 2.2 negative controls for this file's protections:
    each protection test above is re-run here with its
    protection switched off, and the protection's assertion
    must FAIL in that state -- otherwise the test was passing
    both ways and proves nothing. UID: same-uid throughout;
    none of these switches changes who the job runs as, only
    whether the named protection is in force. (The tampered-
    envelope test's control already exists as its pair:
    test_encrypted_envelope_admits_as_encrypted.)"""

    def test_redaction_off_control_full_view_keeps_the_value(self):
        # Protection off: the same flag text rendered at the
        # full view keeps the AWS value the redacted view
        # scrubs, so the redacted absence is the view's doing.
        job = _job("c-view-full", "unused")
        job["result_policy"] = {"view": "full"}
        exec_result = {"stdout": FLAG_TEXT, "stderr": "",
                       "exit_code": 0, "timed_out": False,
                       "duration_sec": 0.01}
        result, _retain = R.apply_result_policy(
            {}, job, exec_result, R._redact_patterns({}),
            confined=False)
        self.assertEqual(result["view"], "full")
        self.assertIn(AWS_VALUE, result["stdout"])

    def test_cleartext_off_control_the_flag_admits(self):
        # Protection off: with the process flag the runner was
        # started under --allow-cleartext, the gate predicate
        # the intake path checks admits the same cleartext
        # form the default refuses. Restored in finally: the
        # refusal posture is process-global.
        self.assertFalse(R._cleartext_jobs_allowed())
        R._set_allow_cleartext_jobs(True)
        try:
            self.assertTrue(R._cleartext_jobs_allowed())
        finally:
            R._set_allow_cleartext_jobs(False)
        self.assertFalse(R._cleartext_jobs_allowed())

    def test_timeout_off_control_same_script_completes(self):
        # Protection off: the same sleeping script with a
        # timeout beyond its sleep runs to completion, so the
        # kill in test_timeout_kills_the_job is the timeout's
        # doing, not the script's.
        killed, _ = _run(None, _job(
            "c-timeout-off", "import time; time.sleep(2)",
            timeout_sec=1))
        self.assertTrue(killed["timed_out"])
        done, _ = _run(None, _job(
            "c-timeout-on", "import time; time.sleep(2)",
            timeout_sec=5))
        self.assertFalse(done["timed_out"])
        self.assertEqual(done["exit_code"], 0)

    def test_output_cap_off_control_no_truncation(self):
        # Protection off: the same 3000-char output under a
        # cap above its size arrives whole, unflagged.
        result, _ = _run({"max_output_bytes": 100000}, _job(
            "c-big-off", "import sys; sys.stdout.write('A' * 3000)"))
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(len(result["stdout"]), 3000)
        self.assertFalse(result["stdout_truncated"])


if __name__ == "__main__":
    unittest.main()
