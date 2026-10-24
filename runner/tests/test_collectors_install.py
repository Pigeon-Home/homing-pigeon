#!/usr/bin/env python3
"""Installer collector support: the flag family, the default
logic, the light pack the installer writes, and the --check
health rows judged from fake facts.

No network, no root, no real machine probes: install_collectors
is driven with its per-platform dispatch mocked, and
collector_health_rows() is pure by construction -- it judges a
facts dict, which is the whole reason the facts/rows split
exists (Falco and Sysmon install fine and collect nothing
where the kernel denies BPF; the rows are how --check says so
instead of install-and-pray).
"""
import argparse
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "runner"))

import install  # noqa: E402
from install import (  # noqa: E402
    aide_cron_text,
    aide_rules_text,
    chosen_collectors,
    collector_health_rows,
    install_collectors,
    osquery_config_text,
    osquery_flags_text,
    osquery_systemd_unit_text,
    requested_collectors,
)


def _args(**kw):
    base = {"collector": None, "no_collector": False,
            "wazuh_manager": None}
    base.update(kw)
    return argparse.Namespace(**base)


class ChosenCollectorsTest(unittest.TestCase):
    def test_default_is_osquery(self):
        self.assertEqual(chosen_collectors(_args(), None),
                         ["osquery"])

    def test_default_suppressed_on_pi_light(self):
        self.assertEqual(chosen_collectors(_args(), "pi-light"),
                         [])

    def test_explicit_wins_even_on_pi_light(self):
        args = _args(collector=["falco"])
        self.assertEqual(chosen_collectors(args, "pi-light"),
                         ["falco"])

    def test_no_collector_means_none(self):
        args = _args(no_collector=True, collector=["falco"])
        self.assertEqual(chosen_collectors(_args(), None),
                         ["osquery"])
        self.assertEqual(chosen_collectors(args, None), [])

    def test_explicit_dedups_and_keeps_order(self):
        args = _args(collector=["zeek", "aide", "zeek"])
        self.assertEqual(chosen_collectors(args, None),
                         ["zeek", "aide"])

    def test_requested_has_no_default(self):
        self.assertEqual(requested_collectors(_args()), [])
        self.assertEqual(
            requested_collectors(_args(collector=["sysmon"])),
            ["sysmon"])
        self.assertEqual(
            requested_collectors(_args(no_collector=True,
                                       collector=["sysmon"])), [])


class OsqueryPackTest(unittest.TestCase):
    def test_config_is_the_light_pack(self):
        cfg = json.loads(osquery_config_text())
        self.assertEqual(sorted(cfg["schedule"]),
                         ["hp_listening_ports", "hp_processes",
                          "hp_users"])
        for name, entry in cfg["schedule"].items():
            self.assertIn("query", entry)
            self.assertIn("interval", entry)
            # Removals are results too; osquery-feed files them.
            self.assertIs(entry["removed"], True)
        sched = cfg["schedule"]
        self.assertEqual(sched["hp_processes"]["interval"], 300)
        self.assertEqual(sched["hp_users"]["interval"], 3600)
        self.assertEqual(sched["hp_listening_ports"]["interval"], 300)
        self.assertIn("cmdline", sched["hp_processes"]["query"])
        self.assertIn("username", sched["hp_users"]["query"])
        self.assertIn("address", sched["hp_listening_ports"]["query"])
        self.assertIn("listening_ports",
                      cfg["schedule"]["hp_listening_ports"]["query"])
        self.assertIn("FROM processes",
                      cfg["schedule"]["hp_processes"]["query"])
        self.assertIn("FROM users",
                      cfg["schedule"]["hp_users"]["query"])

    def test_flags_carry_the_filesystem_logger(self):
        text = osquery_flags_text("/etc/osquery/osquery.conf",
                                  "/var/log/osquery",
                                  "/var/osquery/osquery.db",
                                  "/var/run/osqueryd.pidfile")
        self.assertIn("--logger_plugin=filesystem", text)
        self.assertIn("--logger_path=/var/log/osquery", text)
        self.assertIn("--pidfile=/var/run/osqueryd.pidfile", text)
        self.assertIn("--watchdog_level=1", text)
        self.assertIn("--config_path=/etc/osquery/osquery.conf",
                      text)

    def test_unit_points_at_the_flagfile(self):
        unit = osquery_systemd_unit_text("/opt/osquery/bin/osqueryd")
        self.assertIn("ExecStart=/opt/osquery/bin/osqueryd "
                      "--flagfile=/etc/osquery/osquery.flags", unit)
        self.assertIn("WantedBy=multi-user.target", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("RestartSec=10", unit)
        self.assertIn("After=network-online.target", unit)


class AidePackTest(unittest.TestCase):
    def test_rules_are_the_scoped_set(self):
        text = aide_rules_text()
        for d in ("/etc", "/bin", "/sbin", "/usr/bin", "/usr/sbin",
                  "/boot"):
            self.assertIn(f"{d} HP", text)
        # The vendor whole-tree default is the measured failure
        # this scope exists to avoid.
        self.assertNotIn("/home", text)
        self.assertNotIn("\n/ ", text)

    def test_cron_writes_the_feed_report_path(self):
        text = aide_cron_text()
        self.assertIn("aide --check", text)
        self.assertIn("/var/log/aide/aide.log", text)


def _facts(**over):
    facts = {"installed": {}, "service_active": {}, "running": {},
             "bpf_ok": None, "falco_device": False,
             "sysmon_telemetry_error": False, "aide_db": False,
             "wazuh_manager": False, "artifact_age_sec": {}}
    facts.update(over)
    return facts


def _states(rows):
    return {name: state for name, state, _ in rows}


class CollectorHealthRowsTest(unittest.TestCase):
    def test_empty_machine_is_all_absent(self):
        rows = collector_health_rows(_facts())
        self.assertEqual(len(rows), 8)
        self.assertEqual(set(_states(rows).values()), {"ABSENT"})

    def test_osquery_running_works(self):
        rows = collector_health_rows(_facts(
            installed={"osquery": True},
            service_active={"osquery": True},
            artifact_age_sec={"osquery": 42.0}))
        self.assertEqual(_states(rows)["osquery"], "WORKS")
        detail = {n: d for n, _, d in rows}["osquery"]
        self.assertIn("42s ago", detail)

    def test_osquery_installed_but_stopped(self):
        rows = collector_health_rows(_facts(
            installed={"osquery": True}))
        self.assertEqual(_states(rows)["osquery"],
                         "INSTALLED-BUT-CANNOT-RUN")

    def test_falco_bpf_denied_is_the_measured_failure(self):
        rows = collector_health_rows(_facts(
            installed={"falco": True},
            service_active={"falco": True}, bpf_ok=False))
        self.assertEqual(_states(rows)["falco"],
                         "INSTALLED-BUT-CANNOT-RUN")
        detail = {n: d for n, _, d in rows}["falco"]
        self.assertIn("kernel denied", detail)

    def test_falco_with_device_and_service_works(self):
        rows = collector_health_rows(_facts(
            installed={"falco": True},
            service_active={"falco": True}, bpf_ok=None,
            falco_device=True))
        self.assertEqual(_states(rows)["falco"], "WORKS")

    def test_sysmon_telemetry_error_names_bpf(self):
        rows = collector_health_rows(_facts(
            installed={"sysmon": True},
            service_active={"sysmon": True},
            sysmon_telemetry_error=True))
        self.assertEqual(_states(rows)["sysmon"],
                         "INSTALLED-BUT-CANNOT-RUN")
        detail = {n: d for n, _, d in rows}["sysmon"]
        self.assertIn("BPF", detail)

    def test_wazuh_without_manager_cannot_run(self):
        rows = collector_health_rows(_facts(
            installed={"wazuh": True},
            service_active={"wazuh": True}))
        self.assertEqual(_states(rows)["wazuh"],
                         "INSTALLED-BUT-CANNOT-RUN")
        detail = {n: d for n, _, d in rows}["wazuh"]
        self.assertIn("forwards to nothing", detail)

    def test_wazuh_with_manager_works(self):
        rows = collector_health_rows(_facts(
            installed={"wazuh": True},
            service_active={"wazuh": True}, wazuh_manager=True))
        self.assertEqual(_states(rows)["wazuh"], "WORKS")

    def test_aide_needs_its_database(self):
        rows = collector_health_rows(_facts(
            installed={"aide": True}))
        self.assertEqual(_states(rows)["aide"],
                         "INSTALLED-BUT-CANNOT-RUN")
        rows = collector_health_rows(_facts(
            installed={"aide": True}, aide_db=True))
        self.assertEqual(_states(rows)["aide"], "WORKS")

    def test_zeek_and_softflowd_are_owner_started(self):
        rows = collector_health_rows(_facts(
            installed={"zeek": True, "softflowd": True}))
        self.assertEqual(_states(rows)["zeek"],
                         "INSTALLED-BUT-CANNOT-RUN")
        detail = {n: d for n, _, d in rows}["zeek"]
        self.assertIn("230 MB", detail)
        self.assertIn("never a default", detail)
        rows = collector_health_rows(_facts(
            installed={"zeek": True, "softflowd": True},
            running={"zeek": True, "softflowd": True}))
        self.assertEqual(_states(rows)["zeek"], "WORKS")
        self.assertEqual(_states(rows)["softflowd"], "WORKS")


class CollectorHealthFactsTest(unittest.TestCase):
    def test_facts_gather_survives_a_which_that_raises(self):
        # Regression: the --check tests that patch sys.platform
        # to win32 on a POSIX interpreter make shutil.which
        # itself raise (shutil._winapi is None there). A health
        # probe answers falsely; it never raises.
        with mock.patch.object(
                install.shutil, "which",
                side_effect=AttributeError("no _winapi")):
            facts = install.collector_health_facts()
        self.assertEqual(set(facts["installed"]),
                         set(install.COLLECTOR_NAMES))
        self.assertFalse(any(facts["installed"].values()))


class InstallCollectorsDispatchTest(unittest.TestCase):
    def test_wazuh_without_manager_is_a_skip_not_an_install(self):
        with mock.patch.object(
                install, "_install_collector_linux") as fake:
            with redirect_stdout(io.StringIO()):
                lines = install_collectors(["wazuh"], _args())
        fake.assert_not_called()
        self.assertEqual(len(lines), 1)
        self.assertIn("skipped", lines[0])
        self.assertIn("--wazuh-manager", lines[0])

    def test_one_failure_is_a_line_not_an_abort(self):
        def fake(name, args):
            if name == "falco":
                raise RuntimeError("boom")
            return f"collector {name}: fine"

        with mock.patch.object(
                install, "_install_collector_linux", fake), \
                mock.patch.object(install.sys, "platform", "linux"):
            with redirect_stdout(io.StringIO()):
                lines = install_collectors(["falco", "aide"],
                                           _args())
        self.assertEqual(len(lines), 2)
        self.assertIn("install failed: boom", lines[0])
        self.assertIn("fine", lines[1])

    def test_help_lists_the_collector_family(self):
        import subprocess
        out = subprocess.run(
            [sys.executable, os.path.join(REPO, "runner",
                                          "install.py"), "--help"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0)
        for flag in ("--collector", "--no-collector",
                     "--wazuh-manager"):
            self.assertIn(flag, out.stdout)
        self.assertIn("collectors", out.stdout)


if __name__ == "__main__":
    unittest.main()
