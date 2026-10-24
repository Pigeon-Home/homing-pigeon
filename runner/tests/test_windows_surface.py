"""Pins for the simulated Windows surface (runner/tools/windows_surface.py).

build-windows is the one CI job a local Linux gate cannot
rehearse, and 3.8.9 died there on POSIX assumptions a POSIX gate
could not see. The surface tool makes that class of failure
happen locally; these tests are its proof of work and its
regression net:

- the surface applies and restores exactly (identity, absent
  attributes, windll fakes), and restoring is total;
- the dispatch points the 3.8.9 failure actually touched --
  the remediation samplers and the memory total -- take the
  Windows route under the surface, with the POSIX-only
  attributes genuinely absent;
- a representative platform-sensitive test class
  (RemediationProbeEdges, the class the d2da8e6 fix lives in)
  passes wholesale under the applied surface;
- privilege and daemon-kwargs branches keyed on os.name behave
  as their Windows sides promise.

The wholesale suite run under the surface is a tool, not a
test: runner/tools/run_tests_windows_sim.py. These pins are the
bounded in-suite sample.
"""
import ctypes
import importlib.util
import os
import sys
import unittest
from unittest import mock


def _load_surface():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "runner", "tools", "windows_surface.py")
    spec = importlib.util.spec_from_file_location(
        "hp_windows_surface", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


surface = _load_surface()


class SurfaceMechanicsTest(unittest.TestCase):
    def test_apply_and_restore_is_total(self):
        before = (os.name, sys.platform, hasattr(os, "sysconf"),
                  hasattr(ctypes, "windll"))
        restore = surface.apply_surface()
        try:
            self.assertEqual(os.name, "nt")
            self.assertEqual(sys.platform, "win32")
            self.assertFalse(hasattr(os, "sysconf"))
            self.assertFalse(hasattr(os, "getloadavg"))
            self.assertFalse(hasattr(os, "fork"))
            import platform
            self.assertEqual(platform.system(), "Windows")
            self.assertEqual(platform.machine(), "AMD64")
        finally:
            restore()
        after = (os.name, sys.platform, hasattr(os, "sysconf"),
                 hasattr(ctypes, "windll"))
        self.assertEqual(before, after)

    def test_description_names_the_absent_set(self):
        desc = surface.surface_description()
        for attr in ("sysconf", "getloadavg", "fork"):
            self.assertIn(attr, desc["absent_os_attributes"])
        self.assertEqual(desc["identity"]["os.name"], "nt")
        self.assertTrue(desc["not_simulated"])

    def test_windll_fake_answers_neutrally(self):
        restore = surface.apply_surface()
        try:
            self.assertEqual(
                ctypes.windll.shell32.IsUserAnAdmin(), 0)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self.assertEqual(kernel32.GlobalMemoryStatusEx(None), 0)
            fn = ctypes.windll.kernel32.CreateToolhelp32Snapshot
            fn.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
            self.assertEqual(fn(0, 0), 0)
        finally:
            restore()

    def test_an_existing_windll_is_overlaid_then_restored(self):
        # The 3.10.1 build-windows failure: the host already has
        # windll (an elevated runner, IsUserAnAdmin -> 1). The
        # surface must still answer 0 while applied, and must
        # put that host object back afterwards.
        class _HostShell:
            def IsUserAnAdmin(self):
                return 1

        class _HostLoader:
            shell32 = _HostShell()

        class _HostKernel:
            def GlobalMemoryStatusEx(self, *_args, **_kwargs):
                return 1

        def _host_factory(*_args, **_kwargs):
            return _HostKernel()

        had_windll = hasattr(ctypes, "windll")
        had_windll_obj = getattr(ctypes, "windll", None)
        had_win = hasattr(ctypes, "WinDLL")
        had_win_obj = getattr(ctypes, "WinDLL", None)
        host_loader = _HostLoader()
        ctypes.windll = host_loader
        ctypes.WinDLL = _host_factory
        try:
            restore = surface.apply_surface()
            try:
                self.assertEqual(
                    ctypes.windll.shell32.IsUserAnAdmin(), 0)
                self.assertEqual(
                    ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(None),
                    0)
            finally:
                restore()
            self.assertIs(ctypes.windll, host_loader)
            self.assertEqual(
                ctypes.windll.shell32.IsUserAnAdmin(), 1)
            self.assertEqual(
                ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(None), 1)
        finally:
            if had_windll:
                ctypes.windll = had_windll_obj
            else:
                del ctypes.windll
            if had_win:
                ctypes.WinDLL = had_win_obj
            else:
                del ctypes.WinDLL

    def test_double_apply_keeps_the_first_restore_in_charge(self):
        # Compare against the value captured BEFORE applying --
        # on a real Windows host (or under the sim harness, which
        # has a layer applied already) that value IS "nt", and a
        # correct restore returns to it, not away from it.
        before = os.name
        restore = surface.apply_surface()
        noop = surface.apply_surface()
        noop()
        self.assertEqual(os.name, "nt")  # still applied
        restore()
        self.assertEqual(os.name, before)


class WindowsDispatchPinsTest(unittest.TestCase):
    """The d2da8e6 dispatch points, exercised under the surface
    with the POSIX attributes genuinely deleted."""

    def test_total_memory_takes_the_windows_route(self):
        from runner import remediation
        restore = surface.apply_surface()
        try:
            with mock.patch.object(
                    remediation, "_win_total_memory",
                    return_value=8 * 1024 ** 3) as win:
                self.assertEqual(
                    remediation.total_memory_bytes(), 8 * 1024 ** 3)
                win.assert_called_once()
            with mock.patch.object(
                    remediation, "_win_total_memory",
                    return_value=None):
                self.assertIsNone(remediation.total_memory_bytes())
        finally:
            restore()

    def test_sysconf_fallback_swallows_attribute_error(self):
        # The exact 3.8.9 shape: a platform that is neither the
        # Linux /proc route nor nt reaches the sysconf fallback;
        # where sysconf does not exist the AttributeError is the
        # documented "no route" answer, not a crash.
        from runner import remediation
        # sysconf may already be absent (the sim harness deletes
        # it for the whole process); the pin then starts from the
        # environment it is actually testing and restores only
        # what it took.
        saved = getattr(os, "sysconf", None)
        if saved is not None:
            del os.sysconf
        try:
            with mock.patch.object(sys, "platform", "darwin"), \
                    mock.patch.object(os, "name", "posix"):
                self.assertIsNone(remediation.total_memory_bytes())
        finally:
            if saved is not None:
                os.sysconf = saved

    def test_privilege_check_takes_the_windows_branch(self):
        from runner import posture
        restore = surface.apply_surface()
        try:
            results = []
            with mock.patch.dict(os.environ, {"USERNAME": "DRU"}):
                posture._check_privileges(results)
            self.assertEqual(len(results), 1)
            self.assertIn("DRU", results[0][2])
        finally:
            restore()

    def test_daemon_kwargs_for_windows_have_no_start_new_session(self):
        from runner.runner import daemon_popen_kwargs
        win = daemon_popen_kwargs(True)
        self.assertNotIn("start_new_session", win)
        posix = daemon_popen_kwargs(False)
        self.assertTrue(posix.get("start_new_session"))


class RepresentativeSampleTest(unittest.TestCase):
    """A platform-sensitive class, wholesale, under the surface.

    If a future change reintroduces a POSIX assumption in these
    paths, this fails here -- on a Linux box, before CI.
    """

    def test_remediation_probe_edges_pass_under_the_surface(self):
        from runner.tests.test_coverage_inner import RemediationProbeEdges
        suite = unittest.TestLoader().loadTestsFromTestCase(
            RemediationProbeEdges)
        self.assertGreater(suite.countTestCases(), 5)
        restore = surface.apply_surface()
        try:
            result = unittest.TestResult()
            suite.run(result)
        finally:
            restore()
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])


if __name__ == "__main__":
    unittest.main()
