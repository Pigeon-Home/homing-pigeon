#!/usr/bin/env python3
"""Queue S, roster ORACLE.no_widening: an Oracle answer cannot
widen a security decision made above it.

The promise, in the code's own shape (runner/runner.py): the
key-policy gate and the M2 constraints decide BEFORE the
Oracle's opinion is formed, the opinion is "advisory by
construction -- the opinion never blocks a job by itself", and
the one transformation it may make (repairing a missing
interpreter) sends the repaired job back through the same
gates -- "the repaired job goes back through the dealing path
exactly as a received job would" -- and is refused there if
the repair changed what a pinned key's policy allows.

Three pins, all through the real intake (poll_once):

1. A job a pinned key's policy_env denies in enforce mode is
   denied with the opinion machinery armed (repair latitude,
   a model that would approve it): the denial is audited, no
   result is sent, and the opinion is never even formed --
   the gate is upstream of it.
2. A repairable job (missing interpreter) whose repair would
   move it OUT of its pinned key's allowed_interpreters is
   refused on re-judgment and never runs; the same job under
   a policy that also allows the platform default is repaired
   and runs. A repair never changes what the policy allows;
   it only re-asks.
3. A tier-2 model note that says "do not run this job" is
   attached to the result of a clean job verbatim -- and the
   job runs exactly as it would have without the note. The
   model's say is a note, never a verdict.

The model is a fake throughout (a patched ask_model returning
a fixed answer): no live model is consulted, per the standing
orders for queue S.
"""
import json
import os
import secrets
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "runner", "tests"))

from runner import runner as RR  # noqa: E402
from runner.runner import platform_interpreter, poll_once  # noqa: E402
from runner.tests.security_parity import (  # noqa: E402
    SECRET,
    FakeIMAP,
    FakeSMTP,
    _email,
    _payload,
    base_config,
    normalize,
    read_audit_lines,
)

KEY = "k2"
KEY_SECRET = secrets.token_hex(32)
MISSING = "definitely-missing-binary-zz"


def drive(cfg_extra, payload, secret):
    tmpdir = tempfile.mkdtemp(prefix="hp-nw-")
    cfg = base_config(tmpdir)
    cfg.update(cfg_extra)
    mail = _email(payload, secret)
    imap = FakeIMAP([mail])
    smtp = FakeSMTP()
    poll_once(cfg, tmpdir, {}, os.path.join(tmpdir, "seen.json"),
              imap=imap, smtp=smtp)
    jid = payload["job_id"]
    executed = any(jid in (m["Subject"] or "") for m in smtp.sent)
    audit = [json.loads(line)
             for line in read_audit_lines(tmpdir) or []]
    sent = [(m["Subject"], normalize(m.get_content(), tmpdir,
                                     job_id=jid,
                                     extra_secrets=(KEY_SECRET,)))
            for m in smtp.sent]
    return executed, audit, sent, tmpdir


def key_cfg(**policy):
    base = {"allowed_kinds": ["exec"]}
    base.update(policy)
    return {"additional_secrets": {KEY: KEY_SECRET},
            "key_policies": {KEY: base}}


class NoWideningTest(unittest.TestCase):
    def test_a_policy_denial_never_reaches_the_opinion(self):
        cfg = key_cfg(denied_env=["EVIL_VAR"])
        cfg["security"] = {"modes": {"policy_env": "enforce",
                                     "policy_files": "off",
                                     "policy_args": "off"}}
        job = _payload("nw-deny", kind="exec", script="echo hi",
                       env={"EVIL_VAR": "x"}, key_id=KEY)
        approving_model = mock.Mock(
            return_value={"answer": "Approved. Run it."})
        with mock.patch.object(RR._opinion, "plan_before",
                               wraps=RR._opinion.plan_before) as plan, \
                mock.patch.object(RR, "ask_model", approving_model):
            executed, audit, _sent, _tmp = drive(cfg, job, KEY_SECRET)
        self.assertFalse(executed)
        self.assertFalse(plan.called,
                         "the opinion was formed for a job the "
                         "policy had already denied")
        self.assertFalse(approving_model.called)
        denied = [a for a in audit
                  if a.get("decision") == "denied"
                  and a.get("feature") == "policy_env"]
        self.assertTrue(denied, audit)

    def test_a_repair_never_launders_a_policy_denial(self):
        # The policy allows ONLY the (missing) interpreter the
        # job names. The first gate passes it; the repair would
        # substitute the platform default, which the policy
        # does not allow -- so the re-judgment must refuse it.
        cfg = key_cfg(allowed_interpreters=[[MISSING]])
        job = _payload("nw-repair", kind="exec",
                       script="echo ran > marker.txt",
                       interpreter=[MISSING], key_id=KEY)
        executed, _audit, sent, tmpdir = drive(cfg, job, KEY_SECRET)
        marker = os.path.join(tmpdir, "work", "nw-repair",
                              "marker.txt")
        self.assertFalse(os.path.exists(marker),
                         "the repaired job ran under a policy "
                         "that does not allow its interpreter")
        bodies = " ".join(body for _subj, body in sent)
        self.assertIn("re-judgment", bodies)
        # Control: a policy that also allows the platform
        # default repairs and runs the very same job.
        cfg2 = key_cfg(allowed_interpreters=[[MISSING],
                                             platform_interpreter()])
        job2 = _payload("nw-repair-ok", kind="exec",
                        script="echo ran > marker.txt",
                        interpreter=[MISSING], key_id=KEY)
        executed2, _a2, sent2, tmpdir2 = drive(cfg2, job2,
                                               KEY_SECRET)
        marker2 = os.path.join(tmpdir2, "work", "nw-repair-ok",
                               "marker.txt")
        self.assertTrue(os.path.exists(marker2),
                        "the control job was not repaired and run")
        bodies2 = " ".join(body for _subj, body in sent2)
        self.assertIn("repaired", bodies2)

    def test_a_model_note_never_changes_an_outcome(self):
        cfg = {"oracle_mode": "llm",
               "oracle_opinion_model": True,
               "oracle_opinion_predict": "always",
               "inference": {"endpoint": "http://127.0.0.1:9/v1",
                             "model": "fake-model"}}
        job = _payload("nw-note", kind="exec",
                       script="echo model-note-token")
        refusing_model = mock.Mock(return_value={
            "answer": "Do not run this job; it will fail."})
        with mock.patch.object(RR, "ask_model", refusing_model):
            executed, _audit, sent, _tmp = drive(
                cfg, job, SECRET)
        self.assertTrue(refusing_model.called,
                        "the model was never consulted, so the "
                        "note proves nothing")
        self.assertTrue(executed)
        bodies = " ".join(body for _subj, body in sent)
        self.assertIn("model-note-token", bodies)
        self.assertIn("Do not run this job", bodies)


if __name__ == "__main__":
    unittest.main(verbosity=2)
