"""Oracle opinion (PROTOCOL 3.2): latitude, tier-1 checks, repair.

runner/oracle/opinion.py is pure; the tier-1 tests stage a box through
gather_facts' injected probes. The wire tests run a signed job
through poll_once with fake IMAP/SMTP in the style of
runner/tests/test_protocol_and_edges.py, with only execute_job stubbed.
"""
import hashlib
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner.wire import jobcrypto
from runner.oracle import opinion as op
from runner import runner


# ------------------------------------------------------------- staging

def staged_facts(job, interpreter, platform, os_name="posix",
                 which_map=None, exists_map=None):
    which_map = which_map or {}
    exists_map = exists_map or {}
    return op.gather_facts(
        job, interpreter, platform,
        which=lambda name: which_map.get(name),
        exists=lambda path: exists_map.get(path, False),
        os_name=os_name)


def everything_present(name):
    return "/usr/bin/" + name


# ------------------------------------------------------------- latitude

class ModeMatrixTests(unittest.TestCase):
    """Ceiling x request: the job's request is clamped to the
    configured ceiling; no request means the ceiling itself."""

    CASES = [
        # (ceiling, request, effective)
        ("off", None, "off"), ("off", "off", "off"),
        ("off", "diagnose", "off"), ("off", "repair", "off"),
        ("diagnose", None, "diagnose"), ("diagnose", "off", "off"),
        ("diagnose", "diagnose", "diagnose"),
        ("diagnose", "advise", "diagnose"),
        ("diagnose", "repair", "diagnose"),
        ("advise", None, "advise"), ("advise", "diagnose", "diagnose"),
        ("advise", "advise", "advise"), ("advise", "repair", "advise"),
        ("repair", None, "repair"), ("repair", "off", "off"),
        ("repair", "advise", "advise"), ("repair", "repair", "repair"),
    ]

    def test_matrix(self):
        for ceiling, request, want in self.CASES:
            with self.subTest(ceiling=ceiling, request=request):
                cfg = {"oracle_opinion_mode": ceiling}
                job = {} if request is None else {"oracle_opinion": request}
                self.assertEqual(op.effective_mode(cfg, job), want)

    def test_default_ceiling_is_repair(self):
        self.assertEqual(op.ceiling_mode({}), "repair")
        self.assertEqual(op.effective_mode({}, {}), "repair")

    def test_invalid_values_fall_back(self):
        self.assertEqual(op.ceiling_mode({"oracle_opinion_mode": "max"}),
                         "repair")
        self.assertEqual(op.ceiling_mode({"oracle_opinion_mode": 3}),
                         "repair")
        self.assertEqual(op.requested_mode({"oracle_opinion": "max"}), None)
        self.assertEqual(op.requested_mode({"oracle_opinion": 3}), None)
        self.assertEqual(op.requested_mode({}), None)

    def test_settings_defaults_and_cleaning(self):
        self.assertEqual(op.predict_setting({}), "requested")
        self.assertEqual(op.predict_setting(
            {"oracle_opinion_predict": "always"}), "always")
        self.assertEqual(op.predict_setting(
            {"oracle_opinion_predict": "sometimes"}), "requested")
        self.assertEqual(op.repair_setting({}), "rejudge")
        self.assertEqual(op.repair_setting(
            {"oracle_opinion_repair": "refuse"}), "refuse")
        self.assertEqual(op.repair_setting(
            {"oracle_opinion_repair": "maybe"}), "rejudge")

    def test_model_flag(self):
        self.assertFalse(op.model_enabled({}))
        self.assertFalse(op.model_enabled({"oracle_opinion_model": False}))
        self.assertTrue(op.model_enabled({"oracle_opinion_model": True}))
        self.assertTrue(op.model_enabled({"oracle_opinion_model": "true"}))
        self.assertFalse(op.model_enabled({"oracle_opinion_model": "yes-ish"}))


class DigestTests(unittest.TestCase):
    def test_digest_definition(self):
        job = {"id": "J1", "script": "echo hi", "sig": "x"}
        raw = json.dumps({"id": "J1", "script": "echo hi"},
                         sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
        self.assertEqual(op.received_digest(job),
                         hashlib.sha384(raw).hexdigest())

    def test_digest_ignores_sig_and_key_order(self):
        a = {"id": "J1", "script": "echo hi", "sig": "one"}
        b = {"sig": "two", "script": "echo hi", "id": "J1"}
        self.assertEqual(op.received_digest(a), op.received_digest(b))

    def test_digest_changes_with_content(self):
        a = {"id": "J1", "script": "echo hi"}
        b = {"id": "J1", "script": "echo bye"}
        self.assertNotEqual(op.received_digest(a), op.received_digest(b))


# ------------------------------------------------------------- script hints

class ScriptHintTests(unittest.TestCase):
    def test_powershell_tells(self):
        self.assertEqual(op.script_shape("Get-ChildItem C:\\"), "powershell")
        self.assertEqual(op.script_shape("echo $env:PATH"), "powershell")
        self.assertEqual(op.script_shape("Write-Host hi"), "powershell")
        self.assertEqual(op.script_shape("#!/usr/bin/env pwsh\n$x = 1"),
                         "powershell")

    def test_posix_tells(self):
        self.assertEqual(op.script_shape("#!/bin/sh\necho hi"), "posix")
        self.assertEqual(op.script_shape("#!/bin/bash\necho hi"), "posix")
        self.assertEqual(op.script_shape("export FOO=1\necho $FOO"), "posix")
        # A bash shebang with no bashisms runs on sh -- still posix.
        self.assertEqual(op.script_shape("#!/bin/bash\necho hi"), "posix")

    def test_bash_only_tells(self):
        # Syntax no dash/ash can run: shape is "bash", which does
        # not fit the sh default, so repair leaves it alone.
        self.assertEqual(op.script_shape("a=(1 2 3)\necho ${a[0]}"), "bash")
        self.assertEqual(op.script_shape("#!/bin/bash\nx+=(y)"), "bash")
        self.assertEqual(op.script_shape("cat <<< \"$x\""), "bash")
        self.assertEqual(op.script_shape("declare -A m\nm[k]=v"), "bash")
        self.assertEqual(op.script_shape("readarray -t L < f"), "bash")
        self.assertEqual(op.script_shape("echo ${#arr[@]}"), "bash")
        self.assertEqual(op.script_shape("cat <(echo hi)"), "bash")
        self.assertEqual(op.script_shape('echo "${x:0:1}"'), "bash")
        self.assertFalse(op._shape_fits("bash", "posix-shell"))
        self.assertFalse(op._shape_fits("bash", "powershell"))

    def test_bash_tells_do_not_catch_plain_posix(self):
        # Command substitution and arithmetic look like `=(` / `[`
        # but are not arrays: they must stay out of the bash tell.
        self.assertEqual(op.script_shape("x=$(date)\necho $x"), "neutral")
        self.assertEqual(op.script_shape("n=$((1 + 2))"), "neutral")
        self.assertEqual(op.script_shape("echo $(ls)"), "neutral")
        self.assertEqual(op.script_shape("echo ${x:-default}"), "neutral")

    def test_neutral(self):
        self.assertEqual(op.script_shape("echo hello"), "neutral")
        self.assertEqual(op.script_shape(""), "neutral")
        self.assertEqual(op.script_shape(None), "neutral")
        self.assertEqual(op.script_shape("print('hi')"), "neutral")

    def test_tools_skip_builtins_and_assignments(self):
        hints = op.script_hints("FOO=1\nls /tmp\necho done\nfrobnicate --x")
        self.assertEqual(hints["tools"], ["ls", "frobnicate"])

    def test_tools_skip_interpreter_prefix_noise(self):
        hints = op.script_hints("sudo frobnicate now")
        self.assertEqual(hints["tools"], ["frobnicate"])

    def test_paths(self):
        hints = op.script_hints("cat /etc/hosts\nls C:\\Users\\a")
        self.assertIn("/etc/hosts", hints["paths"])
        self.assertIn("C:\\Users\\a", hints["paths"])

    def test_url_is_not_a_path(self):
        hints = op.script_hints("curl https://example.com/x")
        self.assertFalse(any("example.com" in p for p in hints["paths"]))

    def test_interpreter_family(self):
        self.assertEqual(op.interpreter_family(["powershell", "-Command"]),
                         "powershell")
        self.assertEqual(op.interpreter_family(["sh"]), "posix-shell")
        self.assertEqual(op.interpreter_family(["/bin/bash", "-c"]),
                         "posix-shell")
        self.assertEqual(op.interpreter_family(["python3"]), "python")
        self.assertEqual(op.interpreter_family(["cobol"]), "other")
        self.assertEqual(op.interpreter_family([]), "other")


# ------------------------------------------------------------- tier 1 findings

class Tier1FindingsTests(unittest.TestCase):
    def test_wrong_interpreter_absent_is_repairable(self):
        job = {"script": "echo hi"}
        facts = staged_facts(job, ["cobol"], ["sh"], which_map={})
        findings = op.tier1_findings(job, facts)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["kind"], "interpreter_absent")
        self.assertIsNotNone(findings[0]["repair"])
        self.assertIn("platform default", findings[0]["repair"]["description"])

    def test_absent_interpreter_shape_mismatch_not_repairable(self):
        # PowerShell script, pwsh absent, platform default is sh:
        # swapping the interpreter cannot fix the shape, so no repair.
        job = {"script": "Get-ChildItem"}
        facts = staged_facts(job, ["pwsh"], ["sh"], which_map={})
        kinds = [f["kind"] for f in op.tier1_findings(job, facts)]
        self.assertIn("interpreter_absent", kinds)
        absent = [f for f in op.tier1_findings(job, facts)
                  if f["kind"] == "interpreter_absent"][0]
        self.assertIsNone(absent["repair"])

    def test_bashism_absent_interpreter_is_not_repairable(self):
        job = {"script": "#!/bin/bash\nnums=(4 2)\n"}
        facts = staged_facts(job, ["bash"], ["sh"], which_map={})
        findings = op.tier1_findings(job, facts)
        absent = [f for f in findings
                  if f["kind"] == "interpreter_absent"][0]
        self.assertIsNone(absent["repair"])
        self.assertIn("['bash']", absent["detail"])

    def test_the_repair_log_is_one_sentence(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "runner", "runner.py")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        needle_a = "oracle opinion repaired the "
        needle_b = "interpreter to the platform default"
        self.assertEqual(text.count(needle_a), 1)
        self.assertEqual(text.count(needle_b), 1)

    def test_missing_tool(self):
        job = {"script": "frobnicate --all\nls /tmp"}
        facts = staged_facts(job, ["sh"], ["sh"],
                             which_map={"sh": "/bin/sh", "ls": "/bin/ls"},
                             exists_map={"/tmp": True})
        kinds = [f["kind"] for f in op.tier1_findings(job, facts)]
        self.assertEqual(kinds, ["tool_missing"])

    def test_clean_job_no_findings(self):
        job = {"script": "ls /tmp"}
        facts = staged_facts(job, ["sh"], ["sh"],
                             which_map={"sh": "/bin/sh", "ls": "/bin/ls"},
                             exists_map={"/tmp": True})
        self.assertEqual(op.tier1_findings(job, facts), [])

    def test_powershell_script_under_sh(self):
        job = {"script": "Get-ChildItem\nWrite-Host done"}
        facts = staged_facts(job, ["sh"], ["sh"],
                             which_map={"sh": "/bin/sh"})
        kinds = [f["kind"] for f in op.tier1_findings(job, facts)]
        self.assertEqual(kinds, ["script_shape_mismatch"])

    def test_posix_script_under_powershell(self):
        job = {"script": "#!/bin/sh\nexport X=1"}
        facts = staged_facts(job, ["powershell"], ["powershell"],
                             os_name="nt",
                             which_map={"powershell": "C:\\pwsh.exe"})
        kinds = [f["kind"] for f in op.tier1_findings(job, facts)]
        self.assertEqual(kinds, ["script_shape_mismatch"])

    def test_windows_path_on_posix_is_shape_finding(self):
        job = {"script": r"type C:\data\report.txt"}
        facts = staged_facts(job, ["sh"], ["sh"],
                             which_map={"sh": "/bin/sh"})
        kinds = [f["kind"] for f in op.tier1_findings(job, facts)]
        self.assertEqual(kinds, ["path_shape"])

    def test_missing_path(self):
        job = {"script": "cat /nope/missing.txt"}
        facts = staged_facts(job, ["sh"], ["sh"],
                             which_map={"sh": "/bin/sh", "cat": "/bin/cat"},
                             exists_map={})
        kinds = [f["kind"] for f in op.tier1_findings(job, facts)]
        self.assertEqual(kinds, ["path_missing"])

    def test_powershell_interpreter_skips_tool_lookup(self):
        # Get-ChildItem is a cmdlet, not a PATH tool; under a
        # PowerShell interpreter the tool check must not fire.
        job = {"script": "Get-ChildItem"}
        facts = staged_facts(job, ["powershell"], ["powershell"],
                             os_name="nt",
                             which_map={"powershell": "C:\\pwsh.exe"})
        self.assertEqual(op.tier1_findings(job, facts), [])

    def test_absolute_interpreter_uses_exists(self):
        job = {"script": "echo hi"}
        facts = staged_facts(job, ["/opt/weird/run"], ["sh"],
                             exists_map={"/opt/weird/run": True})
        self.assertTrue(facts["interpreter_present"])
        self.assertEqual(op.tier1_findings(job, facts), [])


# ------------------------------------------------------------- planning

class PlanTests(unittest.TestCase):
    def setUp(self):
        self.bad_job = {"script": "echo hi"}
        self.bad_facts = staged_facts(self.bad_job, ["cobol"], ["sh"],
                                      which_map={})
        self.good_facts = staged_facts(self.bad_job, ["sh"], ["sh"],
                                       which_map={"sh": "/bin/sh"})

    def test_off_is_inactive(self):
        plan = op.plan_before({"oracle_opinion_mode": "off"},
                              self.bad_job, self.bad_facts)
        self.assertFalse(plan["active"])
        self.assertFalse(plan["checks_run"])
        self.assertIsNone(plan["attach"])

    def test_default_plan_is_repair(self):
        # A fresh config defaults to the repair latitude: tier-1
        # checks run before the job and the one mechanical fix is
        # planned without the job having to ask.
        plan = op.plan_before({}, self.bad_job, self.bad_facts)
        self.assertEqual(plan["mode"], "repair")
        self.assertTrue(plan["active"])
        self.assertTrue(plan["checks_run"])
        self.assertIsNotNone(plan["repair_action"])
        self.assertIsNone(plan["attach"])

    def test_diagnose_ceiling_runs_no_prediction(self):
        plan = op.plan_before({"oracle_opinion_mode": "diagnose"},
                              self.bad_job, self.bad_facts)
        self.assertEqual(plan["mode"], "diagnose")
        self.assertTrue(plan["active"])
        self.assertFalse(plan["checks_run"])
        self.assertIsNone(plan["attach"])

    def test_advise_requested_predicts(self):
        job = dict(self.bad_job, oracle_opinion="advise")
        cfg = {"oracle_opinion_mode": "advise"}
        plan = op.plan_before(cfg, job, self.bad_facts)
        self.assertTrue(plan["checks_run"])
        self.assertEqual(plan["attach"]["verdict"], "likely_failure")
        self.assertEqual(plan["attach"]["mode"], "advise")

    def test_advise_not_requested_stays_silent(self):
        cfg = {"oracle_opinion_mode": "advise"}
        plan = op.plan_before(cfg, self.bad_job, self.bad_facts)
        self.assertIsNone(plan["attach"])
        self.assertFalse(plan["checks_run"])

    def test_predict_always(self):
        cfg = {"oracle_opinion_mode": "advise",
               "oracle_opinion_predict": "always"}
        plan = op.plan_before(cfg, self.bad_job, self.good_facts)
        self.assertEqual(plan["attach"]["verdict"], "likely_success")

    def test_predict_never(self):
        cfg = {"oracle_opinion_mode": "advise",
               "oracle_opinion_predict": "never"}
        job = dict(self.bad_job, oracle_opinion="advise")
        plan = op.plan_before(cfg, job, self.bad_facts)
        self.assertIsNone(plan["attach"])
        self.assertFalse(plan["checks_run"])

    def test_repair_plan(self):
        cfg = {"oracle_opinion_mode": "repair"}
        job = dict(self.bad_job, oracle_opinion="repair")
        plan = op.plan_before(cfg, job, self.bad_facts)
        self.assertIsNotNone(plan["repair_action"])
        self.assertIsNone(plan["attach"])

    def test_repair_runs_without_job_request(self):
        # The ceiling itself is the latitude when the job is silent:
        # repair mode repairs, it does not wait to be asked.
        cfg = {"oracle_opinion_mode": "repair"}
        plan = op.plan_before(cfg, self.bad_job, self.bad_facts)
        self.assertIsNotNone(plan["repair_action"])

    def test_repair_refuse_degrades_to_advise(self):
        cfg = {"oracle_opinion_mode": "repair",
               "oracle_opinion_repair": "refuse"}
        job = dict(self.bad_job, oracle_opinion="repair")
        plan = op.plan_before(cfg, job, self.bad_facts)
        self.assertIsNone(plan["repair_action"])
        self.assertEqual(plan["attach"]["mode"], "advise")
        self.assertEqual(plan["attach"]["verdict"], "likely_failure")
        self.assertIn("Proposed fix", plan["attach"]["note"])

    def test_repair_unfixable_is_likely_failure_no_repair(self):
        job = {"script": "Get-ChildItem"}
        facts = staged_facts(job, ["pwsh"], ["sh"], which_map={})
        cfg = {"oracle_opinion_mode": "repair"}
        plan = op.plan_before(cfg, dict(job, oracle_opinion="repair"),
                              facts)
        self.assertIsNone(plan["repair_action"])
        self.assertEqual(plan["attach"]["verdict"], "likely_failure")

    def test_repair_clean_job_predicts_success(self):
        cfg = {"oracle_opinion_mode": "repair"}
        job = dict(self.bad_job, oracle_opinion="repair")
        plan = op.plan_before(cfg, job, self.good_facts)
        self.assertEqual(plan["attach"]["verdict"], "likely_success")


class MemberTests(unittest.TestCase):
    def test_note_cap(self):
        member = op.form_member("advise", "likely_failure", "x" * 900)
        self.assertLessEqual(len(member["note"]), 500)

    def test_model_note_is_labeled(self):
        member = op.with_model_note(
            {"mode": "advise", "verdict": "likely_success", "note": "ok"},
            "the model thinks so")
        self.assertIn("Model-formed note: the model thinks so",
                      member["note"])

    def test_diagnosis_no_opinion_when_no_findings(self):
        member = op.diagnosis_member("diagnose", [])
        self.assertEqual(member["verdict"], "no_opinion")

    def test_diagnosis_with_findings(self):
        findings = [{"kind": "tool_missing", "detail": "no frobnicate",
                     "repair": None}]
        member = op.diagnosis_member("diagnose", findings)
        self.assertEqual(member["verdict"], "likely_failure")
        self.assertIn("no frobnicate", member["note"])

    def test_extend_wrong_success(self):
        member = {"mode": "advise", "verdict": "likely_success",
                  "note": "all good"}
        out = op.extend_member_outcome(member, [])
        self.assertEqual(out["verdict"], "likely_success")
        self.assertIn("failed anyway", out["note"])

    def test_extend_leaves_failure_member(self):
        member = {"mode": "advise", "verdict": "likely_failure",
                  "note": "bad"}
        self.assertIs(op.extend_member_outcome(member, []), member)


# ------------------------------------------------------------- runner wiring
#
# The wire path is driven exactly as runner/tests/test_protocol_and_edges.py
# drives it: a signed job in an EmailMessage through poll_once with
# fake IMAP/SMTP, the result read back with verify_body. Only
# execute_job is stubbed, so the opinion path runs for real.

import tempfile
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

SECRET = "c4e8b1a97d2f6053e8a1c7b9e2f4d8065a3c8e1b7d9f2a4c6e8b1d3f5a7c9e2b4d"
SECRET2 = "9f2b4d6a8c1e3f5a7b9d2c4e6f8a1b3d5c7e9f2a4b6d8c1e3f5a7b9d2c4e6f8a1b"
SENDER = "si@example.com"


class _FakeIMAP:
    def __init__(self, mails):
        self.mails = list(mails)
        self.flagged = []

    def select(self, box):
        return ("OK", [])

    def search(self, *args):
        nums = b" ".join(str(i + 1).encode() for i in range(len(self.mails)))
        return ("OK", [nums])

    def fetch(self, num, _spec):
        raw = self.mails[int(num) - 1]
        head = f"{num.decode()} (RFC822 {{{len(raw)}}}".encode()
        return ("OK", [(head, raw), b")"])

    def store(self, seq, _op, _flags):
        self.flagged.append(seq)
        return ("OK", [])

    def logout(self):
        return ("OK", [])


class _FakeSMTP:
    def __init__(self):
        self.sent = []

    def starttls(self):
        pass

    def login(self, u, p):
        pass

    def send_message(self, msg):
        self.sent.append(msg)

    def quit(self):
        pass


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _job_email(payload, secret=SECRET):
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = SENDER
    msg["Subject"] = f"[HOMING-PIGEON] job {payload['job_id']}"
    wire = jobcrypto.encrypt_body(
        runner.sign_payload(payload, secret), secret,
        job_id=payload["job_id"],
        key_id=payload.get("key_id") or "",
        sign=runner.sign_payload)
    msg.set_content(wire)
    return msg.as_bytes()


def _read_result(msg, secret=SECRET):
    """Verify a result mail's body, unwrapping the hp_enc
    envelope the result mirrors from its (encrypted) job."""
    body = runner.verify_body(msg.get_content(), secret)
    if jobcrypto.is_envelope(body):
        jid = str(msg["Subject"]).rsplit(" ", 1)[-1]
        inner = jobcrypto.decrypt_body(
            body, secret, jid, body.get("key_id") or "")
        body = runner.verify_body(inner, secret)
    return body


def _exec_payload(script="echo hi", **kw):
    payload = {
        "v": 1, "type": "job", "job_id": str(uuid.uuid4()),
        "issued_at": _now_iso(), "kind": "exec",
        "interpreter": ["sh"], "script": script,
    }
    payload.update(kw)
    return payload


def _drive(cfg_over, payload, exit_code=0, timed_out=False, secret=SECRET):
    """One signed job through poll_once; returns (result, exec_calls)."""
    tmp = tempfile.mkdtemp(prefix="hp-opinion-")
    cfg = {
        "mailbox_user": SENDER,
        "mailbox_password": SECRET,
        "shared_secret": SECRET,
        "imap_host": "fake", "imap_port": 993,
        "smtp_host": "fake", "smtp_port": 587,
        "max_job_age_sec": 3600,
        "default_timeout_sec": 300,
    }
    cfg.update(cfg_over or {})
    calls = []

    def fake_exec(c, j, base_dir):
        calls.append(dict(j))
        return {"exit_code": exit_code, "stdout": "", "stderr": "",
                "stdout_truncated": False, "stderr_truncated": False,
                "timed_out": timed_out, "timeout_sec": 60,
                "sent_bytes": 0, "received_bytes": 0, "duration_sec": 0.01}

    smtp = _FakeSMTP()
    with mock.patch.object(runner, "execute_job", side_effect=fake_exec):
        runner.poll_once(cfg, tmp, {}, os.path.join(tmp, "seen.json"),
                         imap=_FakeIMAP([_job_email(payload, secret)]),
                         smtp=smtp)
    result = _read_result(smtp.sent[-1], secret)
    return result, calls


class HandleMailOpinionTests(unittest.TestCase):
    def test_member_absent_when_off(self):
        result, _ = _drive({"oracle_opinion_mode": "off"},
                           _exec_payload(), exit_code=1)
        self.assertNotIn("oracle_opinion", result)

    def test_member_absent_on_success(self):
        result, _ = _drive({}, _exec_payload(), exit_code=0)
        self.assertNotIn("oracle_opinion", result)

    def test_default_diagnosis_present_on_failure(self):
        result, _ = _drive({}, _exec_payload(), exit_code=3)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "repair")
        self.assertEqual(member["verdict"], "no_opinion")

    def test_failure_diagnosis_names_missing_tool(self):
        # A nonsense tool name is the fixture for "not on PATH".
        result, _ = _drive({}, _exec_payload("frobnicate-op-test --all"),
                           exit_code=1)
        member = result["oracle_opinion"]
        self.assertEqual(member["verdict"], "likely_failure")
        self.assertIn("frobnicate-op-test", member["note"])

    def test_advise_prediction_on_success(self):
        cfg = {"oracle_opinion_mode": "advise"}
        result, _ = _drive(cfg, _exec_payload(oracle_opinion="advise"),
                           exit_code=0)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "advise")
        self.assertEqual(member["verdict"], "likely_success")

    def test_advise_prediction_extended_on_failure(self):
        cfg = {"oracle_opinion_mode": "advise"}
        result, _ = _drive(cfg, _exec_payload(oracle_opinion="advise"),
                           exit_code=1)
        member = result["oracle_opinion"]
        self.assertEqual(member["verdict"], "likely_success")
        self.assertIn("failed anyway", member["note"])

    def test_job_request_honored_at_default_ceiling(self):
        # The default ceiling is repair: a job asking for repair
        # is formed at repair.
        result, _ = _drive({}, _exec_payload(oracle_opinion="repair"),
                           exit_code=1)
        self.assertEqual(result["oracle_opinion"]["mode"], "repair")

    def test_job_request_clamped_to_owner_ceiling(self):
        # The owner set the ceiling to diagnose: the job asks
        # repair and gets diagnose -- the member says so.
        result, _ = _drive({"oracle_opinion_mode": "diagnose"},
                           _exec_payload(oracle_opinion="repair"),
                           exit_code=1)
        self.assertEqual(result["oracle_opinion"]["mode"], "diagnose")

    def test_prediction_member_shape(self):
        cfg = {"oracle_opinion_mode": "advise"}
        result, _ = _drive(cfg, _exec_payload(oracle_opinion="advise"),
                           exit_code=0)
        self.assertEqual(set(result["oracle_opinion"]),
                         {"mode", "verdict", "note"})


class RepairHandleMailTests(unittest.TestCase):
    """The one mechanical fix: an absent interpreter replaced with
    the platform default, re-judged before it runs."""

    def _repairable(self, **kw):
        return _exec_payload(interpreter=["pwsh-op-test"], **kw)

    def test_repair_applied_and_digest_recorded(self):
        if runner.shutil.which("pwsh-op-test"):
            self.skipTest("fixture interpreter unexpectedly present")
        cfg = {"oracle_opinion_mode": "repair"}
        job = self._repairable(oracle_opinion="repair")
        result, calls = _drive(cfg, job, exit_code=0)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "repair")
        self.assertIs(member["repaired"], True)
        self.assertEqual(member["received_digest"],
                         op.received_digest(job))
        # What ran was the repaired job.
        self.assertEqual(calls[0]["interpreter"],
                         runner.platform_interpreter())

    def test_refuse_degrades_to_advise_and_job_runs_as_sent(self):
        if runner.shutil.which("pwsh-op-test"):
            self.skipTest("fixture interpreter unexpectedly present")
        cfg = {"oracle_opinion_mode": "repair",
               "oracle_opinion_repair": "refuse"}
        job = self._repairable(oracle_opinion="repair")
        result, calls = _drive(cfg, job, exit_code=0)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "advise")
        self.assertIn("Proposed fix", member["note"])
        self.assertNotIn("repaired", member)
        self.assertEqual(calls[0]["interpreter"], ["pwsh-op-test"])

    def test_rejudge_refusal_returns_original_failure(self):
        if runner.shutil.which("pwsh-op-test"):
            self.skipTest("fixture interpreter unexpectedly present")
        # The key's policy authorizes exactly the interpreter the
        # job named -- and not the platform default. The received
        # job passes policy; the repaired job is refused on
        # re-judgment, so the sender gets the original job's
        # failure result with the opinion explaining.
        cfg = {
            "oracle_opinion_mode": "repair",
            "additional_secrets": {"k": SECRET2},
            "key_policies": {"k": {"allowed_interpreters":
                                   [["pwsh-op-test"]]}},
        }
        job = self._repairable(oracle_opinion="repair", key_id="k")
        result, calls = _drive(cfg, job, exit_code=0, secret=SECRET2)
        member = result["oracle_opinion"]
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("re-judgment", result["stderr"])
        self.assertIs(member["repaired"], False)
        self.assertIn("re-judgment", member["note"])
        self.assertEqual(member["received_digest"],
                         op.received_digest(job))
        self.assertEqual(calls, [])  # nothing executed


class DefaultRepairTests(unittest.TestCase):
    """The default latitude is repair (raised from diagnose
    2026-10-19 at the owner's direction). A fresh config -- no
    oracle_opinion_mode key at all -- therefore repairs the one
    mechanical mismatch, because the config key is both the
    default latitude for jobs that grant none and the ceiling:
    a job that grants none is formed AT the ceiling, and in
    repair mode the repair does not wait to be asked (see
    PlanTests.test_repair_runs_without_job_request). A job may
    still narrow itself with its own member, and an owner who
    sets the ceiling back to diagnose restores the old behavior
    exactly. The model tier is untouched by the default: it
    stays gated by oracle_opinion_model, default false."""

    def _repairable(self, **kw):
        return _exec_payload(interpreter=["pwsh-op-test"], **kw)

    def test_fresh_config_repairs_a_requesting_job(self):
        if runner.shutil.which("pwsh-op-test"):
            self.skipTest("fixture interpreter unexpectedly present")
        job = self._repairable(oracle_opinion="repair")
        result, calls = _drive({}, job, exit_code=0)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "repair")
        self.assertIs(member["repaired"], True)
        self.assertEqual(member["received_digest"],
                         op.received_digest(job))
        self.assertEqual(calls[0]["interpreter"],
                         runner.platform_interpreter())

    def test_fresh_config_repairs_an_unrequested_job(self):
        # No oracle_opinion member at all: the default latitude
        # IS the job's latitude, so the certain fix still runs --
        # re-judged, executed, and recorded with the digest.
        if runner.shutil.which("pwsh-op-test"):
            self.skipTest("fixture interpreter unexpectedly present")
        job = self._repairable()
        self.assertNotIn("oracle_opinion", job)
        result, calls = _drive({}, job, exit_code=0)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "repair")
        self.assertIs(member["repaired"], True)
        self.assertEqual(member["received_digest"],
                         op.received_digest(job))
        self.assertEqual(calls[0]["interpreter"],
                         runner.platform_interpreter())

    def test_fresh_config_job_may_narrow_itself(self):
        # A job that grants only diagnose is never repaired,
        # even under the repair default: the member can only
        # narrow what the owner allows.
        if runner.shutil.which("pwsh-op-test"):
            self.skipTest("fixture interpreter unexpectedly present")
        job = self._repairable(oracle_opinion="diagnose")
        result, calls = _drive({}, job, exit_code=1)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "diagnose")
        self.assertNotIn("repaired", member)
        self.assertIn("pwsh-op-test", member["note"])
        self.assertEqual(calls[0]["interpreter"], ["pwsh-op-test"])

    def test_owner_diagnose_ceiling_restores_old_behavior(self):
        # Ceiling back at diagnose: a job asking for repair is
        # clamped, nothing is repaired, the job runs as sent,
        # and the opinion speaks at diagnose latitude.
        if runner.shutil.which("pwsh-op-test"):
            self.skipTest("fixture interpreter unexpectedly present")
        cfg = {"oracle_opinion_mode": "diagnose"}
        job = self._repairable(oracle_opinion="repair")
        result, calls = _drive(cfg, job, exit_code=1)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "diagnose")
        self.assertNotIn("repaired", member)
        self.assertEqual(calls[0]["interpreter"], ["pwsh-op-test"])

    def test_fresh_config_tier2_stays_dark(self):
        # Inference configured, but oracle_opinion_model still
        # defaults to false: the model is never consulted, on
        # either the prediction path or the repair path.
        cfg = {"inference": {"endpoint": "http://127.0.0.1:11434",
                             "model": "llama3.2:1b"}}
        ask = mock.Mock(side_effect=AssertionError("model called"))
        with mock.patch.object(runner, "ask_model", ask):
            result, _ = _drive(cfg,
                               _exec_payload(oracle_opinion="advise"),
                               exit_code=0)
            self.assertEqual(result["oracle_opinion"]["verdict"],
                             "likely_success")
            self.assertNotIn("Model-formed",
                             result["oracle_opinion"]["note"])
            if not runner.shutil.which("pwsh-op-test"):
                job = self._repairable(oracle_opinion="repair")
                result, _ = _drive(cfg, job, exit_code=0)
                self.assertIs(result["oracle_opinion"]["repaired"],
                              True)
        ask.assert_not_called()
        self.assertFalse(op.model_enabled({}))

    def test_unrecognized_request_is_no_request(self):
        # An unrecognized latitude is ignored as if the member
        # were absent (PROTOCOL 3.1), so the job is formed at
        # the default ceiling -- there is nothing above repair
        # to clamp to.
        job = {"oracle_opinion": "max"}
        self.assertIsNone(op.requested_mode(job))
        self.assertEqual(op.effective_mode({}, job), "repair")


class PredictDisciplineTests(unittest.TestCase):
    """Claims audit round 2, B46: predictions ride only on an
    advise-or-repair EFFECTIVE latitude -- the job's request
    clamped to the owner's ceiling (docs/oracle/configuring-oracle.md:
    "only when the job requests advise or repair within the
    ceiling"). The leak: plan_before keyed want_attach off the
    raw request, so with the ceiling at diagnose a job asking
    for repair still got a prediction member -- the owner's
    deliberate narrowing was violated. Diagnose's post-run
    diagnosis is a different path and is untouched by this
    discipline."""

    def setUp(self):
        self.bad_job = {"script": "echo hi"}
        self.bad_facts = staged_facts(self.bad_job, ["cobol"], ["sh"],
                                      which_map={})
        self.good_facts = staged_facts(self.bad_job, ["sh"], ["sh"],
                                       which_map={"sh": "/bin/sh"})

    def test_diagnose_ceiling_repair_request_no_prediction(self):
        # The reproduction: ceiling diagnose, request repair,
        # predict at its default (requested).
        cfg = {"oracle_opinion_mode": "diagnose"}
        job = dict(self.bad_job, oracle_opinion="repair")
        plan = op.plan_before(cfg, job, self.bad_facts)
        self.assertEqual(plan["mode"], "diagnose")
        self.assertTrue(plan["active"])
        self.assertIsNone(plan["attach"])
        self.assertIsNone(plan["repair_action"])

    def test_diagnose_ceiling_predict_always_no_prediction(self):
        cfg = {"oracle_opinion_mode": "diagnose",
               "oracle_opinion_predict": "always"}
        job = dict(self.bad_job, oracle_opinion="repair")
        plan = op.plan_before(cfg, job, self.bad_facts)
        self.assertIsNone(plan["attach"])

    def test_request_narrowed_to_diagnose_no_prediction_even_always(self):
        # Effective latitude is diagnose (the job narrowed
        # itself under a repair ceiling): "always" means every
        # job under advise semantics, and this job is not.
        cfg = {"oracle_opinion_mode": "repair",
               "oracle_opinion_predict": "always"}
        job = dict(self.bad_job, oracle_opinion="diagnose")
        plan = op.plan_before(cfg, job, self.good_facts)
        self.assertEqual(plan["mode"], "diagnose")
        self.assertIsNone(plan["attach"])

    def test_effective_advise_predicts_under_always_without_request(self):
        cfg = {"oracle_opinion_mode": "advise",
               "oracle_opinion_predict": "always"}
        plan = op.plan_before(cfg, self.bad_job, self.bad_facts)
        self.assertEqual(plan["attach"]["verdict"], "likely_failure")
        self.assertEqual(plan["attach"]["mode"], "advise")

    def test_effective_repair_predicts_under_always_without_request(self):
        cfg = {"oracle_opinion_mode": "repair",
               "oracle_opinion_predict": "always"}
        plan = op.plan_before(cfg, self.bad_job, self.good_facts)
        self.assertEqual(plan["attach"]["verdict"], "likely_success")
        self.assertEqual(plan["attach"]["mode"], "repair")

    def test_predict_never_suppresses_prediction_but_not_repair(self):
        cfg = {"oracle_opinion_mode": "repair",
               "oracle_opinion_predict": "never"}
        job = dict(self.bad_job, oracle_opinion="repair")
        plan = op.plan_before(cfg, job, self.good_facts)
        self.assertIsNone(plan["attach"])
        # never governs predictions; the mechanical fix is not
        # a prediction and is still planned.
        plan = op.plan_before(cfg, job, self.bad_facts)
        self.assertIsNone(plan["attach"])
        self.assertIsNotNone(plan["repair_action"])

    def test_no_member_on_success_under_diagnose_ceiling(self):
        # Wire level: the leak left a likely_success prediction
        # riding a successful result on a diagnose-only box.
        # The discipline leaves no member at all -- diagnose
        # speaks only after a failure.
        result, _ = _drive({"oracle_opinion_mode": "diagnose"},
                           _exec_payload(oracle_opinion="repair"),
                           exit_code=0)
        self.assertNotIn("oracle_opinion", result)

    def test_failure_under_diagnose_ceiling_gets_diagnosis(self):
        # The hard constraint: the post-run diagnosis still
        # attaches on failure -- as a diagnosis (no_opinion on a
        # clean box), not as an extended prediction.
        result, _ = _drive({"oracle_opinion_mode": "diagnose"},
                           _exec_payload(oracle_opinion="repair"),
                           exit_code=1)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "diagnose")
        self.assertEqual(member["verdict"], "no_opinion")
        self.assertNotIn("failed anyway", member["note"])

    def test_failure_diagnosis_still_names_the_cause(self):
        result, _ = _drive(
            {"oracle_opinion_mode": "diagnose"},
            _exec_payload("frobnicate-op-test --all",
                          oracle_opinion="repair"),
            exit_code=1)
        member = result["oracle_opinion"]
        self.assertEqual(member["mode"], "diagnose")
        self.assertEqual(member["verdict"], "likely_failure")
        self.assertIn("frobnicate-op-test", member["note"])


class DeterministicModeTests(unittest.TestCase):
    def test_tier1_files_without_a_model(self):
        # Pi Light: deterministic Oracle, no inference configured.
        # Tier-1 opinions still file; tier 2 has nothing to reach.
        cfg = {"oracle_mode": "deterministic"}
        result, _ = _drive(cfg, _exec_payload("frobnicate-op-test --all"),
                           exit_code=1)
        member = result["oracle_opinion"]
        self.assertEqual(member["verdict"], "likely_failure")
        self.assertNotIn("Model-formed", member["note"])

    def test_model_note_stays_dark_without_opt_in(self):
        # Even with inference configured, oracle_opinion_model
        # defaults to false.
        cfg = {"oracle_opinion_mode": "advise",
               "inference": {"endpoint": "http://127.0.0.1:11434",
                             "model": "llama3.2:1b"}}
        result, _ = _drive(cfg, _exec_payload(oracle_opinion="advise"),
                           exit_code=0)
        self.assertNotIn("Model-formed", result["oracle_opinion"]["note"])

    def test_model_note_labeled_when_opted_in(self):
        cfg = {"oracle_opinion_mode": "advise",
               "oracle_opinion_model": True,
               "inference": {"endpoint": "http://127.0.0.1:11434",
                             "model": "llama3.2:1b"}}
        with mock.patch.object(
                runner, "ask_model",
                return_value={"answer": "looks fine to me"}):
            result, _ = _drive(cfg, _exec_payload(oracle_opinion="advise"),
                               exit_code=0)
        self.assertIn("Model-formed note: looks fine to me",
                      result["oracle_opinion"]["note"])


class CliOverrideTests(unittest.TestCase):
    def test_flag_registered(self):
        import subprocess
        out = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(__file__), "..", "..",
                          "runner", "runner.py"), "--help"],
            capture_output=True, text=True, timeout=60)
        self.assertIn("--oracle-opinion", out.stdout)


class RepairSpecimenTests(unittest.TestCase):
    def test_specimens_match_the_code(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "docs", "specimens", "repair-results.json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        repaired = data["repaired"]
        member = repaired["result"]["oracle_opinion"]
        self.assertIs(member["repaired"], True)
        self.assertEqual(member["received_digest"],
                         op.received_digest(repaired["job"]))
        self.assertEqual(repaired["result"]["stdout"], "pigeon-42\n")
        refused = data["not_repaired"]
        note = refused["result"]["oracle_opinion"]["note"]
        self.assertNotIn("repaired", refused["result"]["oracle_opinion"])
        self.assertEqual(refused["result"]["exit_code"], -2)
        self.assertIn("['bash']", note)
        self.assertIn("not present", note)

    def test_verify_says_what_ran(self):
        from runner.cloud.send_job import repair_line
        digest = "ab" * 48
        self.assertEqual(
            repair_line({
                "stdout": "pigeon-42\n",
                "oracle_opinion": {
                    "repaired": True, "received_digest": digest},
            }),
            f"repair: received {digest}  ran: pigeon-42")
        self.assertEqual(
            repair_line({"oracle_opinion": {"repaired": False}}),
            "repair: refused; the job as received was not rewritten")
        self.assertIsNone(repair_line({"stdout": "pigeon-42\n"}))


if __name__ == "__main__":
    unittest.main()
