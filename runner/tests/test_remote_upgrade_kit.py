"""The remote-upgrade kit (runner/tools/remote-upgrade/) and its doc.

The procedure took a hosted runner from 3.14.2 to 3.15.0 on
31 Oct 2026, and every wall it hit is a line in the applier or the
units. These tests pin those lines so an edit that drops one fails
here instead of on a box at upgrade time. The live run itself is
not a unit test; the kit's shape is.
"""
import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
KIT = os.path.join(ROOT, "runner", "tools", "remote-upgrade")
SENDING = os.path.join(ROOT, "docs", "use", "sending.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class KitFilesTest(unittest.TestCase):
    def test_kit_is_complete(self):
        for name in ("hp-remote-upgrade-apply",
                     "hp-remote-upgrade.service",
                     "hp-remote-upgrade.path",
                     "hp-remote-upgrade.timer"):
            self.assertTrue(os.path.isfile(os.path.join(KIT, name)), name)

    def test_units_point_at_the_applier_and_the_trigger(self):
        service = _read(os.path.join(KIT, "hp-remote-upgrade.service"))
        self.assertIn("ExecStart=/usr/local/sbin/hp-remote-upgrade-apply",
                      service)
        path = _read(os.path.join(KIT, "hp-remote-upgrade.path"))
        self.assertIn(
            "PathExistsGlob=/root/.homing-pigeon/work/*/remote-upgrade/trigger",
            path)
        timer = _read(os.path.join(KIT, "hp-remote-upgrade.timer"))
        self.assertIn("OnUnitActiveSec=1min", timer)
        self.assertIn("Unit=hp-remote-upgrade.service", timer)


class ApplierLessonsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.applier = _read(os.path.join(KIT, "hp-remote-upgrade-apply"))

    def test_rechecks_against_a_fresh_sums(self):
        self.assertIn("SHA384SUMS.fresh", self.applier)
        self.assertIn("sha384sum -c fresh.sum", self.applier)

    def test_installs_with_system_scope(self):
        # Without --system the installer writes a user unit and dies
        # at systemctl --user daemon-reload from a service context.
        self.assertIn("./install --system", self.applier)

    def test_shims_the_children_the_installer_leaks_into(self):
        # The frozen installer's bundled OpenSSL leaks via
        # LD_LIBRARY_PATH and kills this platform's systemctl/curl.
        self.assertIn("unset LD_LIBRARY_PATH", self.applier)
        self.assertIn("for tool in systemctl curl", self.applier)

    def test_disk_backed_tmpdir(self):
        self.assertIn("TMPDIR=/root/.homing-pigeon/tmp", self.applier)
        self.assertIn("mktemp -d -p /root/.homing-pigeon", self.applier)

    def test_restores_the_profile_the_installer_restamps(self):
        self.assertIn("PROFILE_BEFORE", self.applier)
        self.assertIn("restored profile", self.applier)

    def test_leaves_the_ca_bundle_drop_in(self):
        self.assertIn("SSL_CERT_FILE=/etc/pki/ca-trust/extracted/pem/"
                      "tls-ca-bundle.pem", self.applier)
        self.assertIn("homing-pigeon.service.d/ca-bundle.conf", self.applier)

    def test_reports_the_outcome_beside_the_payload(self):
        self.assertIn("outcome.txt", self.applier)
        self.assertIn("homing-pigeon --version", self.applier)

    @unittest.skipUnless(os.name != "nt", "POSIX only")
    def test_applier_is_valid_sh(self):
        proc = subprocess.run(
            ["sh", "-n", os.path.join(KIT, "hp-remote-upgrade-apply")],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class DocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _read(SENDING)

    def test_remote_upgrade_is_documented_as_a_suite_procedure(self):
        self.assertIn("## Remote upgrade", self.doc)
        self.assertIn("deliberately not a part\nof the protocol "
                      "specification", self.doc)
        self.assertIn("who holds its shared\nsecret", self.doc)

    def test_the_job_script_fails_loud(self):
        # set -eu: a failed fetch or digest check must not print the
        # success line (the first attempt's unconditional "staged").
        self.assertIn("set -eu", self.doc)
        self.assertIn("remote-upgrade: staged and triggered", self.doc)
        self.assertIn("touch remote-upgrade/trigger", self.doc)


if __name__ == "__main__":
    unittest.main()
