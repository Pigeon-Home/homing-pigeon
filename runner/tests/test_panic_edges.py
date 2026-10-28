"""The panic word's failure arms: a damaged state, a bad word, a flag
that will not write, a sink that raises, and a process that will not
die. Each must leave the box stopped, or not armed, and never raise.

Agent-Stamp: 60000b3a-32a6-4847-996f-638cbcb6d854
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.guard import panic  # noqa: E402


class PanicEdgesTest(unittest.TestCase):
    def setUp(self):
        panic._reset_for_tests()
        self.addCleanup(panic._reset_for_tests)
        self.base = tempfile.mkdtemp(prefix="hp-panic-edges-")
        self.addCleanup(shutil.rmtree, self.base, True)

    def _state(self, record):
        with open(os.path.join(self.base, panic.STATE_FILE), "w") as fh:
            json.dump(record, fh)

    def test_a_subject_that_does_not_decode_is_read_as_it_stands(self):
        with mock.patch.object(panic.email.header, "decode_header",
                               side_effect=ValueError("bad")):
            self.assertEqual(panic._subject_text("  a   b "), "a b")

    def test_a_state_with_the_wrong_types_or_salt_is_not_armed(self):
        for record in ({"v": 1, "salt": 7, "sha384": "0" * 96},
                       {"v": 1, "salt": "zz" * 16, "sha384": "0" * 96},
                       {"v": 1, "salt": "00" * 8, "sha384": "0" * 96},
                       {"v": 1, "salt": "00" * 16, "sha384": "0" * 95}):
            with self.subTest(record=record):
                self._state(record)
                self.assertIsNone(panic.load(self.base))
                self.assertEqual(panic.state(self.base), "not armed")

    def test_arm_refuses_a_word_that_is_not_from_the_list(self):
        with self.assertRaises(ValueError):
            panic.arm(self.base, "not six words")
        self.assertIsNone(panic.load(self.base))

    def test_a_flag_that_will_not_write_still_stops_the_box(self):
        events = []
        with mock.patch.object(panic._atomicio, "write_json",
                               side_effect=OSError("read-only")):
            panic.fire(self.base, transport="email", event_sink=events.append)
        self.assertFalse(os.path.lexists(os.path.join(self.base, panic.FLAG_FILE)))
        self.assertTrue(panic._FIRED)
        self.assertEqual(events[0]["type"], "panic_fired")

    def test_a_sink_that_raises_does_not_undo_the_stop(self):
        def sink(_event):
            raise RuntimeError("sink down")
        panic.fire(self.base, transport="file", event_sink=sink)
        self.assertTrue(os.path.lexists(os.path.join(self.base, panic.FLAG_FILE)))

    def test_kill_without_a_hook_and_a_kill_that_raises(self):
        proc = mock.MagicMock()
        panic.kill(proc)
        proc.kill.assert_called_once_with()
        proc.kill.side_effect = ProcessLookupError()
        panic.kill(proc)  # must not raise
        panic.set_kill(mock.MagicMock(side_effect=OSError("gone")))
        panic.kill(proc)


if __name__ == "__main__":
    unittest.main()
