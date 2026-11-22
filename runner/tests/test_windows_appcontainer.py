# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The AppContainer control in the Windows confinement backend.

The Win32 spawn cannot execute on this host, so the proof here
rides the platform neutral half of runner/guard/windows_confine.py:
the container name's shape (with the bookend family around it),
the capabilities structure with its empty capability set, the
attribute list construction, the recorded grant set, the
AppContainer trial's four checks and each named failure, the
status string naming app_container only when the trial passes,
and the floor's behavior unchanged when it does not.
"""
import os
import string
import subprocess
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from runner.guard import windows_confine as WC


class FakeProc:
    def __init__(self, out=b"", err=b"", returncode=0,
                 timeout=False):
        self._out = out
        self._err = err
        self.returncode = returncode
        self._timeout = timeout
        self.closed = False
        self.killed = False

    def communicate(self, timeout=None):
        if self._timeout:
            raise subprocess.TimeoutExpired("trial", timeout)
        return self._out, self._err

    def kill(self):
        self.killed = True

    def close(self):
        self.closed = True


def _spawn_returning(proc, calls=None):
    def _spawn(argv, cwd=None, env=None):
        if calls is not None:
            calls.append((argv, cwd))
        return proc
    return _spawn


_ALL_OK = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-REFUSED\n"
           b"AC-OUTSIDE-WRITE-REFUSED\nAC-NETWORK-REFUSED\n"
           b"AC-TOKEN-APPCONTAINER\n")


class ContainerNameTests(unittest.TestCase):
    def test_fixed_name_is_valid(self):
        self.assertIsNone(
            WC.validate_app_container_name(WC.APP_CONTAINER_NAME))
        self.assertEqual(WC.APP_CONTAINER_NAME,
                         "pigeon-home.homing-pigeon.runner")

    def test_plain_shapes_are_valid(self):
        for name in ("a", "A1", "hp.runner", "hp_runner", "a" * 64,
                     "x" * 10 + "-" + "y" * 10):
            with self.subTest(name=name):
                self.assertIsNone(WC.validate_app_container_name(name))

    def test_empty_and_non_string_refused(self):
        for bad in ("", None, 7, b"hp", ["hp"]):
            with self.subTest(bad=bad):
                self.assertIsNotNone(WC.validate_app_container_name(bad))

    def test_too_long_refused(self):
        self.assertIsNotNone(
            WC.validate_app_container_name("a" * 65))
        self.assertIsNotNone(
            WC.validate_app_container_name("a" * 1000))

    def test_bookend_symbols_refused(self):
        # Every symbol on the keyboard, wrapped around a good
        # name at the front, the back, and both ends: only the
        # shape's own characters (dot, underscore, hyphen, in
        # their places) may survive, and a leading symbol never
        # does, because the name must start alphanumeric.
        base = "hp9"
        for ch in string.punctuation:
            for wrapped in (ch + base, base + ch, ch + base + ch):
                with self.subTest(wrapped=wrapped):
                    problem = WC.validate_app_container_name(wrapped)
                    if ch in "._-" and wrapped == base + ch:
                        self.assertIsNone(problem)
                    elif ch == "." and wrapped == ch + base:
                        self.assertIsNotNone(problem)
                    else:
                        self.assertIsNotNone(problem)

    def test_bookend_edge_characters_refused(self):
        base = "hp9"
        for ch in ("\x00", "\t", "\r", "\n", " ", "/", "\\", ":"):
            for wrapped in (ch + base, base + ch, ch + base + ch,
                            ch * 10 + base, base + ch * 10,
                            base[:1] + ch * 10 + base[1:]):
                with self.subTest(wrapped=repr(wrapped)):
                    self.assertIsNotNone(
                        WC.validate_app_container_name(wrapped))

    def test_symbol_only_and_whitespace_only_refused(self):
        for bad in ("-", ".", "_", "---", "...", "   ", "\t\n",
                    "!!!", "-hp", ".hp", "_hp"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(WC.validate_app_container_name(bad))

    def test_runs_of_ordinary_then_odd_refused(self):
        self.assertIsNotNone(WC.validate_app_container_name(
            "a" * 10 + ";"))
        self.assertIsNotNone(WC.validate_app_container_name(
            ";" * 10 + "a"))
        self.assertIsNotNone(WC.validate_app_container_name(
            "a" * 5 + ";" * 10 + "a" * 5))


class CapabilitiesTests(unittest.TestCase):
    def test_empty_capability_set(self):
        caps = WC.build_security_capabilities("S-1-15-2-123")
        self.assertEqual(caps["app_container_sid"], "S-1-15-2-123")
        self.assertEqual(caps["capabilities"], ())
        self.assertEqual(caps["capability_count"], 0)
        self.assertEqual(caps["reserved"], 0)

    def test_any_capability_is_an_error(self):
        for asked in (["internetClient"], ["S-1-15-3-1"],
                      ["internetClient", "picturesLibrary"]):
            with self.subTest(asked=asked):
                with self.assertRaises(ValueError):
                    WC.build_security_capabilities(
                        "S-1-15-2-123", capabilities=asked)

    def test_missing_sid_is_an_error(self):
        for bad in (None, ""):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    WC.build_security_capabilities(bad)

    def test_attribute_spec(self):
        caps = WC.build_security_capabilities("S-1-15-2-123")
        attr, payload = WC.proc_thread_attribute_spec(caps)
        self.assertEqual(
            attr, WC.PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES)
        self.assertEqual(attr, 0x00020009)
        self.assertIs(payload, caps)

    def test_attribute_spec_refuses_a_wide_capabilities_dict(self):
        wide = {"app_container_sid": "S-1-15-2-123",
                "capabilities": ("S-1-15-3-1",),
                "capability_count": 1, "reserved": 0}
        with self.assertRaises(ValueError):
            WC.proc_thread_attribute_spec(wide)
        with self.assertRaises(ValueError):
            WC.proc_thread_attribute_spec(None)
        with self.assertRaises(ValueError):
            WC.proc_thread_attribute_spec({})


class GrantSetTests(unittest.TestCase):
    def test_work_dir_full_and_reads_read_execute(self):
        grants = WC.app_container_grant_set(
            "/work", ["/ro/one", "/ro/two"])
        self.assertEqual(grants, [("/work", "read_write_execute"),
                                  ("/ro/one", "read_execute"),
                                  ("/ro/two", "read_execute")])

    def test_only_the_named_paths_are_granted(self):
        grants = WC.app_container_grant_set("/work")
        self.assertEqual(grants, [("/work", "read_write_execute")])
        self.assertNotIn("/etc", [p for p, _ in grants])
        self.assertNotIn("/", [p for p, _ in grants])

    def test_duplicates_collapse_in_order(self):
        grants = WC.app_container_grant_set(
            "/work", ["/ro", "/ro", "/work", "/other", "/ro"])
        self.assertEqual(grants, [("/work", "read_write_execute"),
                                  ("/ro", "read_execute"),
                                  ("/other", "read_execute")])

    def test_empty_work_dir_is_an_error(self):
        for bad in ("", None, 7):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    WC.app_container_grant_set(bad)

    def test_empty_read_path_is_an_error(self):
        with self.assertRaises(ValueError):
            WC.app_container_grant_set("/work", [""])
        with self.assertRaises(ValueError):
            WC.app_container_grant_set("/work", [None])


class TrialTests(unittest.TestCase):
    def test_all_four_checks_pass(self):
        proc = FakeProc(out=_ALL_OK)
        calls = []
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(proc, calls))
        self.assertIsNone(problem)
        self.assertTrue(proc.closed)
        argv, cwd = calls[0]
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(cwd, argv[3])

    def test_grant_gets_granted_paths_and_never_the_outside(self):
        seen = []

        def _grant(paths):
            seen.extend(paths)
            return None

        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=_ALL_OK)), grant=_grant)
        self.assertIsNone(problem)
        self.assertEqual(len(seen), 4)
        self.assertFalse(any("outside" in p for p in seen))

    def test_spawn_failure_is_named(self):
        def _spawn(argv, cwd=None, env=None):
            raise RuntimeError("CreateProcessW failed: 5")

        problem = WC.appcontainer_trial_problem(_spawn)
        self.assertIn("AppContainer trial spawn failed", problem)
        self.assertIn("CreateProcessW failed: 5", problem)

    def test_read_failure_is_named(self):
        proc = FakeProc(out=b"AC-READ-FAIL denied\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(proc))
        self.assertIn("could not read its granted staged file",
                      problem)

    def test_write_failure_is_named(self):
        proc = FakeProc(out=b"AC-READ-OK\nAC-WRITE-FAIL denied\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(proc))
        self.assertIn("could not write its work directory", problem)

    def test_outside_open_is_a_named_boundary_failure(self):
        out = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-OPEN\n"
               b"AC-OUTSIDE-WRITE-REFUSED\nAC-NETWORK-REFUSED\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("read outside its granted paths", problem)

    def test_outside_check_missing_is_named(self):
        out = b"AC-READ-OK\nAC-WRITE-OK\nAC-NETWORK-REFUSED\n"
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("outside the granted paths", problem)

    def test_network_open_is_a_named_boundary_failure(self):
        out = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-REFUSED\n"
               b"AC-OUTSIDE-WRITE-REFUSED\nAC-NETWORK-OPEN\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("reached the network", problem)

    def test_network_check_missing_is_named(self):
        out = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-REFUSED\n"
               b"AC-OUTSIDE-WRITE-REFUSED\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("network access being refused", problem)

    def test_timeout_is_named_and_kills(self):
        proc = FakeProc(timeout=True)
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(proc), timeout=3)
        self.assertIn("timed out after 3s", problem)
        self.assertTrue(proc.killed)

    def test_grant_problem_is_named(self):
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=_ALL_OK)),
            grant=lambda paths: "SetNamedSecurityInfoW failed: 5")
        self.assertIn("could not grant its staged tree", problem)
        self.assertIn("SetNamedSecurityInfoW failed: 5", problem)

    def test_grant_raising_is_named(self):
        def _grant(paths):
            raise OSError("no DACL")

        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=_ALL_OK)), grant=_grant)
        self.assertIn("could not grant its staged tree", problem)

    def test_outside_write_open_is_a_boundary_crossing(self):
        out = (b"AC-READ-OK\nAC-WRITE-OK\nAC-OUTSIDE-REFUSED\n"
               b"AC-OUTSIDE-WRITE-OPEN\nAC-NETWORK-REFUSED\n"
               b"AC-TOKEN-APPCONTAINER\n")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("wrote outside its granted paths", problem)
        self.assertTrue(WC.app_container_boundary_crossing(problem))

    def test_token_plain_is_named(self):
        out = _ALL_OK.replace(b"AC-TOKEN-APPCONTAINER",
                              b"AC-TOKEN-PLAIN")
        problem = WC.appcontainer_trial_problem(
            _spawn_returning(FakeProc(out=out)))
        self.assertIn("not an AppContainer token", problem)

    def test_trial_program_carries_the_four_checks(self):
        for marker in ("AC-READ-OK", "AC-WRITE-OK",
                       "AC-OUTSIDE-REFUSED", "AC-NETWORK-REFUSED",
                       "AC-OUTSIDE-OPEN", "AC-NETWORK-OPEN",
                       "AC-OUTSIDE-WRITE-REFUSED",
                       "AC-OUTSIDE-WRITE-OPEN",
                       "AC-TOKEN-APPCONTAINER"):
            self.assertIn(marker, WC._AC_TRIAL_PROGRAM)


class ProfileAndGateTests(unittest.TestCase):
    def test_profile_creation_outcomes(self):
        self.assertEqual(WC.profile_creation_outcome(0), "created")
        self.assertEqual(
            WC.profile_creation_outcome(0x800700B7), "exists")
        self.assertEqual(
            WC.profile_creation_outcome(-2147024713), "exists")
        self.assertEqual(
            WC.profile_creation_outcome(0x80070005), "failed")

    def test_missing_mechanism_falls_back_but_crossing_refuses(self):
        self.assertIsNone(WC.confinement_gate_problem(
            None, "AppContainer trial spawn failed: x"))
        self.assertIsNone(WC.confinement_gate_problem(None, None))
        crossing = ("AppContainer boundary crossing: an "
                    "AppContainer process read outside its "
                    "granted paths")
        self.assertEqual(
            WC.confinement_gate_problem(None, crossing), crossing)
        self.assertEqual(
            WC.confinement_gate_problem("floor failed", crossing),
            "floor failed")
        self.assertFalse(WC.app_container_boundary_crossing(
            "AppContainer trial spawn failed: x"))
        self.assertFalse(WC.app_container_boundary_crossing(None))


class StatusTests(unittest.TestCase):
    def test_floor_status_is_exact_and_unchanged(self):
        self.assertEqual(
            WC.STATUS_CONFINEMENT,
            "windows: job_object + restricted_token + "
            "low_integrity")
        self.assertEqual(WC.confinement_status(), WC.STATUS_CONFINEMENT)
        self.assertEqual(
            WC.confinement_status(False), WC.STATUS_CONFINEMENT)
        self.assertNotIn("app_container", WC.confinement_status())

    def test_extended_status_names_the_control(self):
        # The design's record string: the AppContainer spawn
        # replaces the restricted token, and low integrity is
        # not double named, so the proven string is its own
        # shape, not the floor string with a name appended.
        self.assertEqual(
            WC.confinement_status(True),
            "windows: job_object + appcontainer + no_network")
        self.assertEqual(
            WC.STATUS_APP_CONTAINER,
            "windows: job_object + appcontainer + no_network")
        self.assertEqual(
            WC.APP_CONTAINER_CONTROLS,
            ("job_object", "appcontainer", "no_network"))
        self.assertNotIn("restricted_token",
                         WC.confinement_status(True))
        self.assertNotIn("low_integrity",
                         WC.confinement_status(True))

    def test_status_follows_the_trial_verdict(self):
        self.assertEqual(
            WC.effective_confinement_status(None),
            WC.STATUS_APP_CONTAINER)
        for failure in ("an AppContainer process could not read "
                        "its granted staged file",
                        "AppContainer trial spawn failed: x"):
            with self.subTest(failure=failure):
                self.assertEqual(
                    WC.effective_confinement_status(failure),
                    WC.STATUS_CONFINEMENT)

    def test_floor_behavior_when_the_trial_fails(self):
        # The gate's floor probe on this host still answers the
        # Windows only problem (the stub backend), the floor
        # spawn still refuses off Windows, and no status the
        # floor path can produce names the new control.
        if not WC.IS_WINDOWS_BACKEND:
            self.assertEqual(
                WC.windows_confinement_problem(),
                "windows_confine is Windows-only")
            self.assertEqual(
                WC.windows_app_container_problem(),
                "windows_confine is Windows-only")
            with self.assertRaises(RuntimeError):
                WC.spawn_app_container_process(
                    ["x"], cwd="/work")
            with self.assertRaises(RuntimeError):
                WC.spawn_confined_process(["x"], cwd="/work")


if __name__ == "__main__":
    unittest.main()
