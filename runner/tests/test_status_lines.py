# Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c
"""Project telephone-pole: the status file and the words file hold
their shape (docs/project/telephone-pole.md).

docs/seats/status.txt is one line per seat, replaced, never appended:

    SEAT STAMP @COMMIT open:Qn,Qn|- closed:Qn,Qn|- on:WORD

A line that does not parse fails here, so the shorthand cannot drift
into a second dialect without a red build. The staleness check is the
point of the file: a question a seat lists as open that says **Done:**
in its first line fails, and so does a question number that does not
exist. docs/project/telephone-pole-words.md admits a word only with two
seats named.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
STATUS = os.path.join(ROOT, "docs", "seats", "status.txt")
WORDS = os.path.join(ROOT, "docs", "project", "telephone-pole-words.md")
QUESTIONS = os.path.join(ROOT, "docs", "seats", "questions.md")

_QLIST = r"(?:-|Q\d+(?:,Q\d+)*)"
LINE = re.compile(
    r"^(?P<seat>[a-z][a-z0-9-]{0,23}) "
    r"(?P<stamp>[0-9a-f]{8}|00000000-muse|grok) "
    r"@(?P<commit>[0-9a-f]{7,40}) "
    r"open:(?P<open>" + _QLIST + r") "
    r"closed:(?P<closed>" + _QLIST + r") "
    r"on:(?P<on>[a-z0-9][a-z0-9._-]{0,39})$")


def parse_status(text):
    """[(lineno, match)] for the seat lines; ValueError naming the first
    line that is neither a comment, blank, nor the shape."""
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        m = LINE.match(line)
        if m is None:
            raise ValueError(f"status.txt:{n}: not the shape: {line!r}")
        rows.append((n, m))
    return rows


def qnums(field):
    return [] if field == "-" else [int(q[1:]) for q in field.split(",")]


def question_heads(text):
    """{n: the entry's text up to its first prose} for every Q entry;
    later entries with a reused number keep the first (newest)."""
    heads = {}
    parts = re.split(r"\n(?=## Q\d+ )", text)
    for part in parts[1:]:
        n = int(re.match(r"## Q(\d+) ", part).group(1))
        heads.setdefault(n, part[:800])
    return heads


def is_done(head):
    """True when the entry says **Done:** before its body begins."""
    body = re.sub(r"^## [^\n]*\n", "", head)
    body = re.sub(r"<!--[^>]*-->", "", body).lstrip()
    return body.startswith("**Done:**")


def check(status_text, questions_text):
    """Every problem the status file has against the questions."""
    problems = []
    try:
        rows = parse_status(status_text)
    except ValueError as e:
        return [str(e)]
    heads = question_heads(questions_text)
    seats = {}
    for n, m in rows:
        seat = m.group("seat")
        if seat in seats:
            problems.append(f"status.txt:{n}: a second line for {seat} "
                            f"(line {seats[seat]}); replace, never add")
        seats.setdefault(seat, n)
        opened, closed = qnums(m.group("open")), qnums(m.group("closed"))
        for q in set(opened) & set(closed):
            problems.append(f"status.txt:{n}: Q{q} is both open and closed")
        for q in opened + closed:
            if q not in heads:
                problems.append(f"status.txt:{n}: Q{q} is not in "
                                "questions.md")
        for q in opened:
            if q in heads and is_done(heads[q]):
                problems.append(f"status.txt:{n}: {seat} lists Q{q} open "
                                "but it says Done; the line is stale")
    return problems


def word_problems(text):
    problems = []
    section = text.split("\n## Words", 1)
    if len(section) != 2:
        return ["telephone-pole-words.md has no Words section"]
    entries = re.split(r"\n(?=### )", section[1])
    for entry in entries[1:]:
        word = entry.splitlines()[0][4:].strip()
        m = re.search(r"^Seats: (.+)$", entry, re.M)
        seats = [s.strip() for s in m.group(1).split(",")] if m else []
        if len(set(s for s in seats if s)) < 2:
            problems.append(f"word {word!r} names fewer than two seats")
    return problems


class StatusFileTest(unittest.TestCase):
    def test_the_status_file_holds_its_shape_and_is_current(self):
        with open(STATUS, encoding="utf-8") as fh:
            status = fh.read()
        with open(QUESTIONS, encoding="utf-8") as fh:
            questions = fh.read()
        self.assertEqual(check(status, questions), [])

    def test_the_words_file_admits_a_word_only_with_two_seats(self):
        with open(WORDS, encoding="utf-8") as fh:
            self.assertEqual(word_problems(fh.read()), [])


QS = """# Questions

## Q2 (x): two

<!-- Agent-Stamp: 90000998-709f-46f5-b2bc-2c3c5cf8dc6c -->

**Done:** landed in `abc1234`.

Body.

## Q1 (x): one

Body.
"""


class CheckerTest(unittest.TestCase):
    """The checker on made-up files, so a red names a real fault."""

    def test_a_good_file(self):
        self.assertEqual(check(
            "# c\n\nreview 90000998 @abc1234 open:Q1 closed:Q2 on:x\n"
            "muse 00000000-muse @abc1234 open:- closed:- on:grow-25\n", QS),
            [])

    def test_a_line_that_is_not_the_shape(self):
        for line in ("review 90000998 open:- closed:- on:x",
                     "review 90000998 @abc1234 open:Q1, closed:- on:x",
                     "review 90000998 @abc1234 open:- closed:- on:two words",
                     "Review 90000998 @abc1234 open:- closed:- on:x",
                     "review 90000998 @abc1234 open:- closed:- on:x extra"):
            self.assertTrue(check(line + "\n", QS), line)

    def test_an_open_question_that_is_done_is_stale(self):
        problems = check("desk 40000e00 @abc1234 open:Q2 closed:- on:x\n",
                         QS)
        self.assertTrue(any("stale" in p for p in problems), problems)

    def test_a_question_that_does_not_exist(self):
        problems = check("desk 40000e00 @abc1234 open:Q9 closed:- on:x\n",
                         QS)
        self.assertTrue(any("Q9 is not" in p for p in problems), problems)

    def test_one_line_per_seat(self):
        problems = check("desk 40000e00 @abc1234 open:- closed:- on:a\n"
                         "desk 40000e00 @def5678 open:- closed:- on:b\n", QS)
        self.assertTrue(any("second line" in p for p in problems))

    def test_both_open_and_closed(self):
        problems = check("desk 40000e00 @abc1234 open:Q1 closed:Q1 on:a\n",
                         QS)
        self.assertTrue(any("both open and closed" in p for p in problems))

    def test_a_word_needs_two_seats(self):
        ok = "# W\n\n## Words\n\n### done\n\nSeats: desk, muse\n\nmeaning\n"
        one = "# W\n\n## Words\n\n### done\n\nSeats: desk\n\nmeaning\n"
        none = "# W\n\n## Words\n\n### done\n\nmeaning\n"
        self.assertEqual(word_problems(ok), [])
        self.assertTrue(word_problems(one))
        self.assertTrue(word_problems(none))
        self.assertTrue(word_problems("# no section\n"))


if __name__ == "__main__":
    unittest.main()
