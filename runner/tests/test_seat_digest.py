"""The seat digest (runner/tools/seat_digest.py): where a window of
each seat's work went, read from the history and the questions
file. The pure parts are pinned here on small fixtures: the commit
kinds, the numstat reader, the questions reader (a wrapped heading
read whole), who a question is addressed to, the residual chain,
the per-seat shares, and the hours a question waits for the other
seat's first commit."""
import importlib.util
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "seat_digest", os.path.join(REPO, "runner", "tools", "seat_digest.py"))
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)

LOG = (
    "@aaa1111\t1000\tMuse\tdesk: Q7 suppositions, recorded before the fix\n"
    "40\t0\tdocs/desk.md\n"
    "@bbb2222\t4600\tMuse\tQ7: the guard reads the second shape (option 1)\n"
    "300\t2\trunner/tests/test_guard.py\n"
    "20\t5\trunner/ops/guard.py\n"
    "@ccc3333\t400\tClaude\ttests: a leg of its own; Q7 asks the desk where it belongs\n"
    "-\t-\tassets/logo.png\n"
    "10\t1\trunner/tools/split.json\n"
    "@ddd4444\t200\tClaude\trelease: 1.2.3.4 — the record\n"
)

QUESTIONS = """# Questions

## Q9 (Muse, to the desk, 2026-11-12): the
Q8 guard's residual ledger shapes — a second
separator family

body

## Q8 (Muse, to the desk, 2026-11-11): the Q7 guard's residual polarity shapes — one more

body

## Q7 (Claude asks Muse, 2026-11-11): the sweeps outrun every wall; where should they run

body

## Q6 (Claude asks the owner, 2026-11-10): a token, so a tag can carry a workflow file

## Q5 (Muse, to the desk, 2026-11-01): an older matter
"""


class ReadersTest(unittest.TestCase):
    def test_the_kind_is_the_subjects_prefix(self):
        self.assertEqual(sd.kind("desk: Q7 suppositions"), "desk")
        self.assertEqual(sd.kind("Release: 1.2"), "release")
        self.assertEqual(sd.kind("Q168: the plain path spawns suspended"), "question fix")
        self.assertEqual(sd.kind("tests+docs: two things"), "tests+docs")
        self.assertEqual(sd.kind("Germany bank 65: 2,504 entries"), "other")
        self.assertEqual(sd.kind("Update README.md"), "other")

    def test_the_log_reader_takes_commits_and_numstat(self):
        commits = sd.parse_log(LOG)
        self.assertEqual([c["sha"] for c in commits], ["aaa1111", "bbb2222", "ccc3333", "ddd4444"])
        self.assertEqual(commits[1]["files"], [(300, 2, "runner/tests/test_guard.py"), (20, 5, "runner/ops/guard.py")])
        # a binary file's "-" counts for nothing
        self.assertEqual(commits[2]["files"][0], (0, 0, "assets/logo.png"))
        self.assertEqual(commits[3]["files"], [])
        self.assertEqual(commits[0]["at"], 1000)

    def test_a_wrapped_heading_is_read_whole(self):
        qs = sd.questions(QUESTIONS)
        self.assertEqual([q["q"] for q in qs], ["Q9", "Q8", "Q7", "Q6", "Q5"])
        self.assertEqual(qs[0]["date"], "2026-11-12")
        self.assertIn("Q8 guard's residual ledger shapes", qs[0]["title"])
        self.assertEqual(qs[2]["who"], "Claude asks Muse")

    def test_who_a_question_is_addressed_to(self):
        self.assertEqual(sd.addressed("Muse, to the desk"), ("Muse", "self"))
        self.assertEqual(sd.addressed("Claude asks Muse"), ("Claude", "seat"))
        self.assertEqual(sd.addressed("Claude asks the owner"), ("Claude", "owner"))
        self.assertEqual(sd.addressed("Claude, the desk, to the conductor"), ("Claude", "owner"))
        self.assertEqual(sd.addressed("Muse to Claude, the desk"), ("Muse", "seat"))
        # a seat that files for the desk it carries asks itself
        self.assertEqual(sd.addressed("Muse asks Muse"), ("Muse", "self"))
        self.assertEqual(sd.addressed("Muse asks Claude"), ("Muse", "seat"))
        # relayed from the owner is a seat's question, not one to him
        self.assertEqual(sd.addressed("Claude to Muse, from the owner"), ("Claude", "seat"))


class DigestTest(unittest.TestCase):
    def setUp(self):
        self.commits = sd.parse_log(LOG)
        self.qs = sd.questions(QUESTIONS)

    def test_the_chain_follows_each_residual_to_the_question_before(self):
        self.assertEqual(sd.longest_chain(self.qs), (3, "Q7", "Q9"))
        self.assertEqual(sd.longest_chain([q for q in self.qs if q["q"] in ("Q7", "Q6")]), (0, "", ""))

    def test_the_shares_are_of_the_seats_own_lines(self):
        d = sd.digest(self.commits, self.qs, "2026-11-10", "2026-11-12", top=2)
        muse = d["seats"]["Muse"]
        self.assertEqual((muse["commits"], muse["added"], muse["deleted"]), (2, 360, 7))
        self.assertEqual(muse["top"], [("runner/tests/test_guard.py", 300, 83.3), ("docs/desk.md", 40, 11.1)])
        self.assertEqual(dict(muse["kinds"]), {"desk": 1, "question fix": 1})
        self.assertEqual(d["seats"]["Claude"]["commits"], 2)
        # the window's questions, by day: Q5 is outside it
        self.assertEqual(d["filed"], 4)
        self.assertEqual(d["addressed"], [("Claude -> owner", 1), ("Claude -> seat", 1), ("Muse -> self", 2)])
        self.assertEqual(d["chain"], (3, "Q7", "Q9"))

    def test_a_question_waits_for_the_other_seats_first_commit(self):
        rows = sd.answer_hours(self.commits, self.qs, "2026-11-10", "2026-11-12")
        # Q7: Claude named it at 400, Muse first at 1000 -- 600 s
        self.assertEqual(rows, [("Q7", "Claude", "Muse", 0.2)])
        alone = [c for c in self.commits if c["author"] == "Claude"]
        self.assertEqual(sd.answer_hours(alone, self.qs, "2026-11-10", "2026-11-12"),
                         [("Q7", "Claude", None, None)])

    def test_a_question_is_filed_when_its_heading_lands(self):
        # Q9 and Q8 landed inside the window; Q7's heading names a
        # day inside it but landed after the window closed, and Q5's
        # landed inside it under an older day. The count follows the
        # landings, so a re-run on a later day reads the same.
        patch = ("@@@5000\n@@ -45,0 +46,3 @@ Rules:\n+## Q9 (Muse, to the desk, 2026-11-12): the\n+body\n"
                 "@@@4000\n@@ -45,0 +46 @@\n+## Q8 (Muse, to the desk, 2026-11-11): the Q7 guard's residual\n"
                 "-## Q4 (old heading reworded)\n+## Q5 (Muse, to the desk, 2026-11-01): an older matter\n"
                 "@@@4500\n+## Q8 (Muse, to the desk, 2026-11-11): the Q7 guard's residual\n")
        filed = sd.filed_in(patch)
        self.assertEqual(filed, {"Q9": 5000, "Q8": 4000, "Q5": 4000})
        d = sd.digest(self.commits, self.qs, "2026-11-10", "2026-11-12", top=2, filed=filed)
        self.assertEqual(d["filed"], 3)
        self.assertEqual(d["addressed"], [("Muse -> self", 3)])
        # Q7 is outside the landings, so its wait is not this window's
        self.assertEqual(sd.answer_hours(self.commits, self.qs, "2026-11-10", "2026-11-12", filed=filed), [])
        self.assertEqual(sd.filed_in(""), {})

    def test_the_report_reads_in_lines(self):
        d = sd.digest(self.commits, self.qs, "2026-11-10", "2026-11-12", top=2)
        rows = sd.answer_hours(self.commits, self.qs, "2026-11-10", "2026-11-12")
        text = sd.render(d, rows, "2026-11-10T00:00:00Z", "2026-11-13T00:00:00Z")
        self.assertIn("Muse: 2 commits, 360 lines added, 7 deleted", text)
        self.assertIn(" 83.3%        300  runner/tests/test_guard.py", text)
        self.assertIn("questions filed in the window: 4 (Claude -> owner 1, Claude -> seat 1, Muse -> self 2)", text)
        self.assertIn("longest chain of residual questions: 3, Q7 .. Q9", text)
        self.assertIn("Q7: named first by Claude; first named by Muse 0.2 hours later", text)


if __name__ == "__main__":
    unittest.main()
