"""The campaign canary: the campaign's planted pretend
credential, as a workspace-boundary test.

Origin: the overnight campaign's flagread shape (2026-10-23)
planted a pretend credential beside the job and asserted it
came back verbatim -- a canary for reach. The eight campaign
shapes live on in runner/tests/test_campaign_core.py and
runner/tests/test_campaign_loop_variants.py; this file lifts
the flagread shape itself into a boundary test before the
archived per-cycle record (runner/tests/archive/, 13,321
generated tests) was removed on 2026-11-01, so the canary
survives the archive.

Not the phase-2 canary: runner/tests/test_credential_canary.py
plants a different marker and proves the RUNNER never copies
a credential into its own outputs. This file's question is
the older one -- what a JOB can reach -- asked of the
campaign's own pretend credential, across a workspace
boundary, under each posture the executor offers.

What is pinned here, all through the real executor
(runner.runner.execute_job):

- Control: a job in the workspace that holds the canary reads
  it and the marker returns whole -- the canary is live. The
  marker is whole in the output stream a canary scan reads
  even when it was assembled from pieces: in the planted file
  the credential value is built by string concatenation, and
  one job below prints the marker itself in two fragments.
- Confinement off: a job in a DIFFERENT workspace, reaching
  for the canary by its outside path, reads it and the marker
  comes back. That is the recorded behavior, not a hope: with
  the fence stated off, the executor runs jobs as the runner's
  own uid with no filesystem fence. (Unstated, the mode now
  reads enforce -- the lockdown default -- so the off leg
  states it.)
  Same-uid reach is the design fact test_confinement.py's
  negative control pins for a generic host file; here it is
  pinned for the canary.
- The owner's fence: under security.modes.confinement =
  enforce, where the sandbox can engage, the same reach fails
  and the marker never reaches the output. Where the sandbox
  cannot engage, enforce falls back to running unsandboxed,
  logs a warning, and writes a "fallback" audit row -- the
  degradation is on the record. Both arms are pinned, each
  gated on the startup probe like test_confinement's enforce
  classes.

protected_paths is not a read fence and this file does not
pretend otherwise: the mail layer snapshots the listed paths
around a job and reports CHANGES (runner/ops/mail.py); a read
changes nothing and trips nothing. The read boundary is
confinement, above.

POSIX only: the jobs are `sh` scripts, matching the campaign.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from runner import runner as R  # noqa: E402
from runner.guard import sandbox as SB  # noqa: E402
from runner.guard import security as S  # noqa: E402

# The archive's pretend credential, verbatim: obviously fake,
# and the credential-shaped values are assembled by
# concatenation in the source so the file itself is the
# split-shape instance.
FLAG_TEXT = (
    "PRETEND CREDENTIAL FLAG FILE - test fixture, not a real secret\n"
    "aws_access_key_id = " + "AKIA" "IOSFODNN7EXAMPLE" + "\n"
    "password = flag-hunter2-pretend\n"
    "api_token = <MASKED_SECRET_001>\n"
    "FLAG{pretend-credential-flag-7f3a}\n"
)
MARKER = "FLAG{pretend-credential-flag-7f3a}"

# The startup probe, as in test_confinement: the enforce arms
# gate on whether bwrap can actually confine a job here.
ENGAGES = SB.startup_problem() is None


def _job(jid, script):
    return {"v": 1, "type": "job", "job_id": jid,
            "issued_at": "2026-11-01T00:00:00Z", "kind": "exec",
            "interpreter": ["sh"], "script": script, "env": {}}


def _plant(base):
    flag = os.path.join(base, "flag-credential.txt")
    with open(flag, "w", encoding="utf-8") as fh:
        fh.write(FLAG_TEXT)
    return flag


def _reach(flag):
    return f"cat {flag}\necho cat-exit=$?\n"


def _run(base, job, cfg_extra=None):
    # The control and off legs state confinement off: unstated
    # it reads enforce under the lockdown default and the
    # canary's reach would be the sandbox's doing, not the
    # executor's. A cfg_extra security block replaces this one
    # wholesale, as in the enforce legs below.
    cfg = {"base_dir": base,
           "security": {"modes": {"confinement": "off"}}}
    cfg.update(cfg_extra or {})
    return R.execute_job(cfg, job, base)


def _audit(base):
    path = os.path.join(base, S.AUDIT_FILE)
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"),
                     "canary scripts are POSIX sh scripts")
class CanaryControlTests(unittest.TestCase):
    """The canary is live in the workspace that legitimately
    holds it."""

    def test_own_workspace_read_returns_the_marker_verbatim(self):
        base = tempfile.mkdtemp(prefix="hp-canary-own-")
        flag = _plant(base)
        result = _run(base, _job("canary-own", _reach(flag)))
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["timed_out"])
        self.assertIn("cat-exit=0", result["stdout"])
        for line in FLAG_TEXT.splitlines():
            self.assertIn(line, result["stdout"])
        # The credential value was assembled by concatenation
        # in FLAG_TEXT's source; it is whole in the file, whole
        # in the output, and a scan for the whole value finds
        # it.
        self.assertIn("aws_access_key_id = AKIAIOSFODNN7EXAMPLE",
                      result["stdout"])
        self.assertIn(MARKER, result["stdout"])

    def test_marker_printed_in_fragments_is_whole_in_the_output(self):
        base = tempfile.mkdtemp(prefix="hp-canary-frag-")
        script = ("printf 'FLAG{pretend-'\n"
                  "printf 'credential-flag-7f3a}\\n'\n")
        self.assertNotIn(MARKER, script)
        result = _run(base, _job("canary-frag", script))
        self.assertEqual(result["exit_code"], 0)
        self.assertIn(MARKER, result["stdout"])


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"),
                     "canary scripts are POSIX sh scripts")
class CanaryCrossWorkspaceTests(unittest.TestCase):
    """The canary sits in workspace A; the job runs in
    workspace B and reaches for it by its outside path."""

    def _two_workspaces(self):
        home = tempfile.mkdtemp(prefix="hp-canary-home-")
        away = tempfile.mkdtemp(prefix="hp-canary-away-")
        return _plant(home), away

    def test_cross_workspace_read_succeeds_with_confinement_off(self):
        # Confinement stated off (the _run default): the job
        # runs as the runner's uid with no fence, and the reach
        # succeeds. Pinned as the recorded behavior -- the
        # fence is owner config, not the executor (module
        # docstring). Unstated, the mode reads enforce under
        # the lockdown default; that leg is the enforce test
        # below.
        flag, away = self._two_workspaces()
        result = _run(away, _job("canary-default", _reach(flag)))
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("cat-exit=0", result["stdout"])
        self.assertIn(MARKER, result["stdout"])

    @unittest.skipUnless(ENGAGES,
                         "sandbox cannot engage on this machine "
                         "(startup probe)")
    def test_cross_workspace_read_is_refused_under_enforce(self):
        flag, away = self._two_workspaces()
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        result = _run(away, _job("canary-enforce", _reach(flag)),
                      cfg)
        self.assertEqual(result["exit_code"], 0)
        self.assertNotIn(MARKER, result["stdout"])
        self.assertNotIn("cat-exit=0", result["stdout"])
        # The denial is the sandbox's: an audit row says the
        # job ran sandboxed, so the missing marker is
        # confinement's doing and not an accident of the
        # environment.
        rows = [r for r in _audit(away)
                if r.get("decision") == "sandboxed"]
        self.assertTrue(rows, _audit(away))

    @unittest.skipIf(ENGAGES,
                     "sandbox engages on this machine "
                     "(startup probe)")
    def test_enforce_falls_back_loudly_where_the_sandbox_cannot_engage(self):
        # Enforce was asked for and cannot be delivered here,
        # so the job runs unsandboxed -- the reach succeeds --
        # and the audit log carries a fallback row saying so.
        flag, away = self._two_workspaces()
        cfg = {"security": {"modes": {"confinement": "enforce"}}}
        result = _run(away, _job("canary-fallback", _reach(flag)),
                      cfg)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("cat-exit=0", result["stdout"])
        self.assertIn(MARKER, result["stdout"])
        rows = [r for r in _audit(away)
                if r.get("decision") == "fallback"]
        self.assertTrue(rows, _audit(away))


if __name__ == "__main__":
    unittest.main(verbosity=2)
