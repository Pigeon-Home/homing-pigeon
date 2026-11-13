"""The fleet page: rule 17's lines, completed under Q173.

Settled 2026-11-12 (Q173). `docs/infrastructure-documents/
project/fleet.md` carries one line per machine the project
rents or runs and one per service with a bill, and AGENTS.md
rule 17 bars anything that reaches a machine from that page:
no address, hostname, key, token or account identifier. The
order of work (item 4) reaches the same page: a rented rig
idle since its last review carries its direction on its line
-- back to fuzzing, or give back, named a day ahead and
banked first.

The deterministic substrate pinned here is the page's shape,
not its figures: the corpus counts on the page are a dated
snapshot the holding seat refreshes, so no count is pinned.
What cannot rot silently is what this family checks: the
five machines are lined, in the page's order; no line
carries anything that reaches a machine; every machine line
states a stood-up day or states plainly that it is not on
the record; the two directions the Q173 completion settled
stand on the lines they belong to; the services are lined;
and the gap list the conductor must supply is present.

Q178 (2026-11-13) adds the month against the owner's $700
ceiling: the lines whose cost is on the record, summed on the
page, the lines whose cost is not named beside the sum, and
each unknown line stating whether the seat can read its month
itself. The pins below hold that statement: the section
stands, its sum recomputes from the figures on the lines
themselves, the three unknown lines are named beside it, and
each unknown line carries its cannot-read statement with the
day it was read.
"""
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
FLEET = os.path.join(
    REPO, "docs", "infrastructure-documents", "project",
    "fleet.md")

MACHINES = ["Germany", "Menlo Park", "San Francisco",
            "Nuremberg", "The FreeBSD node"]
SERVICES = ["The hosted queue", "Outside-model API access",
            "GitHub", "Hosting control-plane accounts"]


def _read():
    with open(FLEET, encoding="utf-8") as fh:
        return fh.read()


def _rows(text, names):
    rows = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0] in names:
            rows[cells[0]] = cells
    return rows


class FleetPageShapeTest(unittest.TestCase):
    def test_every_machine_is_lined_in_order(self):
        text = _read()
        rows = _rows(text, MACHINES)
        self.assertEqual(sorted(rows), sorted(MACHINES))
        positions = [text.index("| " + name + " |")
                     for name in MACHINES]
        self.assertEqual(positions, sorted(positions))

    def test_no_line_reaches_a_machine(self):
        text = _read()
        self.assertIsNone(
            re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
                      text),
            "an address-shaped string stands on the fleet page")
        for label in ("server id", "droplet id", "ipv4",
                      "hostname:", "api token", "password"):
            self.assertNotIn(label, text.lower())

    def test_every_machine_line_states_its_shape(self):
        rows = _rows(_read(), MACHINES)
        for name in MACHINES:
            cells = rows[name]
            self.assertGreaterEqual(len(cells), 8, name)
            for cell in cells[1:]:
                self.assertTrue(cell, name + " has an empty cell")
            stood_up = cells[4]
            self.assertTrue(
                re.match(r"^\d{4}-\d{2}-\d{2}$", stood_up)
                or "not on the record" in stood_up,
                name + " states neither a stood-up day nor "
                "the gap")

    def test_the_idle_rented_rig_carries_its_direction(self):
        rows = _rows(_read(), MACHINES)
        nuremberg = " ".join(rows["Nuremberg"])
        self.assertIn("give back", nuremberg.lower())
        self.assertIn("2026-10-31", nuremberg)
        self.assertIn("conductor", nuremberg.lower())

    def test_the_returned_rig_reads_back_to_fuzzing(self):
        rows = _rows(_read(), MACHINES)
        francisco = " ".join(rows["San Francisco"])
        self.assertIn("back to fuzzing", francisco.lower())
        self.assertNotIn("give back", francisco.lower()
                         .replace("not a give-back candidate", ""))

    def test_services_are_lined(self):
        rows = _rows(_read(), SERVICES)
        self.assertEqual(sorted(rows), sorted(SERVICES))
        queue = " ".join(rows["The hosted queue"])
        self.assertIn("free tier", queue.lower())

    def test_the_gap_list_stands(self):
        text = _read()
        self.assertIn("What the conductor must still supply",
                      text)
        self.assertIn("No give-back is executed", text)


KNOWN_LINES = MACHINES + SERVICES
UNKNOWN_LINES = ["Menlo Park", "Outside-model API access",
                 "GitHub"]


def _month_total_section(text):
    start = text.index("## The month against the ceiling")
    end = text.index("## The lines", start)
    return text[start:end]


def _first_dollars(cell):
    match = re.search(r"\$(\d+(?:\.\d+)?)", cell)
    return float(match.group(1)) if match else 0.0


class FleetMonthTotalTest(unittest.TestCase):
    def test_the_month_is_stated_against_the_ceiling(self):
        section = _month_total_section(_read())
        self.assertIn("$700", section)
        self.assertIn("about $52.97 a month", section)
        self.assertIn("ceiling", section.lower())
        self.assertIn("restated when a line changes", section)

    def test_the_stated_sum_recomputes_from_the_lines(self):
        text = _read()
        rows = _rows(text, KNOWN_LINES)
        known = [name for name in KNOWN_LINES
                 if name not in UNKNOWN_LINES]
        total = 0.0
        for name in known:
            cells = rows[name]
            month_cell = cells[3]
            total += _first_dollars(month_cell)
        self.assertAlmostEqual(total, 52.97, places=2)
        section = _month_total_section(text)
        stated = re.search(r"about \$(\d+\.\d+) a month", section)
        self.assertIsNotNone(stated)
        self.assertAlmostEqual(float(stated.group(1)), total,
                               places=2)

    def test_the_unknown_lines_are_named_beside_the_sum(self):
        section = _month_total_section(_read())
        for name in UNKNOWN_LINES:
            self.assertIn(name, section)
        self.assertIn("not a complete month", section)
        self.assertIn("does not pass the ceiling", section)

    def test_each_unknown_line_states_the_seat_cannot_read_it(
            self):
        rows = _rows(_read(), UNKNOWN_LINES)
        for name in UNKNOWN_LINES:
            line = " ".join(rows[name])
            self.assertIn("cannot read", line, name)
            self.assertIn("2026-11-13", line, name)
            self.assertIn("conductor", line.lower(), name)
            self.assertIn("to supply", line, name)

    def test_no_known_line_claims_it_cannot_be_read(self):
        rows = _rows(_read(), KNOWN_LINES)
        for name in KNOWN_LINES:
            if name in UNKNOWN_LINES:
                continue
            self.assertNotIn("cannot read",
                             " ".join(rows[name]), name)


if __name__ == "__main__":
    unittest.main()
