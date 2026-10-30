# Agent-Stamp: 80000aeb-9c1f-49ad-aeee-fa0855092587
"""Q121: one subject grammar for every reader, the Worker's.

The runner's transports and the hosted queue's Worker read a message's
kind and id from the same subject line. They used to spell the
separator as ``\\s`` in two languages whose ``\\s`` differ, and a
subject separated by an information-separator control routed on one
side and not the other. Now the separator is one explicit class
(runner/wire/subject.py), every Python reader builds from it, and this
file holds them to it -- against the Worker itself when node is here.
"""

import json
import os
import re
import shutil
import subprocess
import unittest

from runner.wire import subject as S
from runner.wire import transports as TR
from runner.wire import protocol_v2 as V2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKER = os.path.join(ROOT, "runner", "cloud", "queues-worker", "src", "edge_subject_stdio.mjs")

# The separators the two languages used to disagree on, and a few
# they agreed on, each as the gap before the kind word.
GAPS = {
    " ": "bm-1", "\t": "bm-2", "\n": "bm-3",
    "\x1c": None, "\x1d": None, "\x1e": None, "\x1f": None, "\x85": None,
    "\xa0": "bm-4", " ": "bm-5", "　": "bm-6", "﻿": "bm-7",
}


class SubjectGrammarTest(unittest.TestCase):

    def test_the_separator_is_the_worker_s_whitespace(self):
        for gap, want in GAPS.items():
            subj = "[HOMING-PIGEON]%sresult %s" % (gap, want or "bm-x")
            m = S.RESULT_ID_RE.search(subj)
            self.assertEqual(want, m.group(1) if m else None, repr(gap))
            subj = "[HOMING-PIGEON]%sjob %s" % (gap, want or "bm-x")
            m = S.JOB_ID_RE.search(subj)
            self.assertEqual(want, m.group(1) if m else None, repr(gap))

    def test_a_control_character_is_part_of_the_id(self):
        m = S.JOB_ID_RE.search("[HOMING-PIGEON] job id\x1ftail")
        self.assertEqual("id\x1ftail", m.group(1))

    def test_every_reader_builds_from_the_one_grammar(self):
        self.assertIs(TR._JOB_ID_RE, S.JOB_ID_RE)
        self.assertIs(TR._RESULT_ID_RE, S.RESULT_ID_RE)
        self.assertIn(S.SPACE_CLASS, V2._KIND.pattern)
        self.assertNotIn("\\s", V2._KIND.pattern)
        for ext in ("file", "dtls", "queues", "nats"):
            mod = __import__("runner.transport_extensions.%s.__main__" % ext,
                             fromlist=["_JOB_ID_RE"])
            self.assertIs(mod._JOB_ID_RE, S.JOB_ID_RE, ext)

    def test_no_production_file_spells_the_subject_pattern_itself(self):
        # The copy that diverged was the eighth; a ninth must not grow.
        offenders = []
        for folder, _dirs, files in os.walk(os.path.join(ROOT, "runner")):
            if os.sep + "tests" in folder:
                continue
            for name in files:
                if not name.endswith(".py") or name == "subject.py":
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as fh:
                    if re.search(r"HOMING-PIGEON\\\]\(\?:\\s\+\\S\+\)", fh.read()):
                        offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual([], offenders)

    @unittest.skipUnless(shutil.which("node"), "the gate differential needs node")
    def test_the_worker_reads_the_same_ids(self):
        cases = []
        for gap in GAPS:
            cases.append("[HOMING-PIGEON]%sresult bm-x" % gap)
            cases.append("[HOMING-PIGEON]%sjob bm-y" % gap)
        cases += ["[HOMING-PIGEON] job id\x1ftail", "Re: [HOMING-PIGEON] TEST job z",
                  "[HOMING-PIGEON] qresult q", "[HOMING-PIGEON]", "nothing"]
        stdin = "".join(json.dumps({"subject": c}) + "\n" for c in cases)
        out = subprocess.run(["node", WORKER], input=stdin, capture_output=True,
                             text=True, timeout=60, check=True).stdout
        answers = [json.loads(line) for line in out.splitlines() if line]
        self.assertEqual(len(cases), len(answers))
        for subj, got in zip(cases, answers):
            pj = S.JOB_ID_RE.search(subj)
            pr = S.RESULT_ID_RE.search(subj)
            self.assertEqual(got["job"], pj.group(1) if pj else None, repr(subj))
            self.assertEqual(got["result"], pr.group(1) if pr else None, repr(subj))


if __name__ == "__main__":
    unittest.main()
