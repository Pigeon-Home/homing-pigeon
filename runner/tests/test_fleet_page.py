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
import sys
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


class FleetSshReadingTest(unittest.TestCase):
    """Q176: every machine line carries its SSH reading.

    The reading is dated 2026-11-13 and worded so it reaches
    no machine (the shape test above keeps the word for the
    other kind of login off the page). A machine that could
    not be read carries that plainly instead of a guess.
    """

    def test_every_machine_line_carries_an_ssh_reading(self):
        rows = _rows(_read(), MACHINES)
        for name in MACHINES:
            line = " ".join(rows[name])
            self.assertIn("SSH:", line, name)
            self.assertIn("2026-11-13", line, name)

    def test_the_key_only_reading_stands_where_it_was_read(self):
        rows = _rows(_read(), MACHINES)
        self.assertIn("by key only", " ".join(rows["The FreeBSD node"]))

    def test_the_not_key_only_reading_says_so_and_waits(self):
        rows = _rows(_read(), MACHINES)
        germany = " ".join(rows["Germany"])
        self.assertIn("not by key only", germany)
        self.assertIn("conductor", germany.lower())

    def test_unread_machines_say_not_read_not_a_posture(self):
        rows = _rows(_read(), MACHINES)
        for name in ("San Francisco", "Nuremberg"):
            line = " ".join(rows[name])
            self.assertIn("not read", line, name)
            self.assertIn("not guessed", line, name)

    def test_the_machine_with_no_ssh_server_says_so(self):
        rows = _rows(_read(), MACHINES)
        self.assertIn("no SSH server", " ".join(rows["Menlo Park"]))


DOCS = os.path.join(REPO, "docs")
CHANGELOG = os.path.join(
    REPO, "docs", "infrastructure-documents", "changelog.md")
VERSION_PY = os.path.join(REPO, "runner", "_version.py")
_QUAD_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def _declared_version_lines():
    """The (major, minor) lines the tree itself declares.

    Derived, never written out (AGENTS.md rule 16): the
    changelog's release headings and the runtime version
    constant are the tree's own record of its version lines.
    """
    lines = set()
    with open(CHANGELOG, encoding="utf-8") as fh:
        for match in re.finditer(
                r"^## (\d+)\.(\d+)\.\d+\.\d+", fh.read(), re.M):
            lines.add((int(match.group(1)), int(match.group(2))))
    with open(VERSION_PY, encoding="utf-8") as fh:
        match = re.search(r'__version__ = "(\d+)\.(\d+)\.\d+\.\d+"',
                          fh.read())
    if match:
        lines.add((int(match.group(1)), int(match.group(2))))
    return lines


def _is_project_version(quad, lines):
    """True when a dotted quad is one of the project's own
    four-part version numbers: it parses under version4's
    strict shape (exactly 4 numeric components, no leading
    zeros) and its major.minor is a declared version line."""
    sys.path.insert(0, REPO)
    from runner.ops import version4
    try:
        parts = version4.parse(quad)
    except ValueError:
        return False
    return (parts[0], parts[1]) in lines


def _public_addresses_in(text, lines):
    """The public (global) addresses a page's text carries.

    A quad that is not a global address (loopback, private,
    documentation, reserved) reaches no machine and is
    allowed. A global quad is allowed only as a project
    version; anything else is a public address standing on
    a page, and is returned so the test can name the page.
    Known limit, stated: a real address shaped exactly like
    a version on a declared line would pass; the fleet's
    machines are on no such line, and rule 17's wording --
    named by place, never by address -- is the first guard.
    """
    import ipaddress
    found = []
    for match in _QUAD_RE.finditer(text):
        quad = match.group(0)
        try:
            address = ipaddress.ip_address(quad)
        except ValueError:
            continue
        if not address.is_global:
            continue
        if _is_project_version(quad, lines):
            continue
        found.append(quad)
    return found


class DocsPublicAddressTest(unittest.TestCase):
    """Q176 ask 3: the fleet page's test family reaches the
    reports -- a page under `docs/` that carries a public
    address is named by a test.

    Pages are the markdown pages under `docs/` (the reports,
    the rig dossiers, the forum's markdown and the archive
    included). What the scan allows is stated in
    `_public_addresses_in`: non-global quads, and the
    project's own four-part version numbers, which are
    dotted quads too.
    """

    def test_no_docs_page_carries_a_public_address(self):
        lines = _declared_version_lines()
        offenders = []
        for root, _dirs, files in os.walk(DOCS):
            for name in sorted(files):
                if not name.endswith(".md"):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8",
                          errors="replace") as fh:
                    found = _public_addresses_in(fh.read(), lines)
                if found:
                    offenders.append(
                        "%s (%s)" % (
                            os.path.relpath(path, REPO),
                            ", ".join(sorted(set(found)))))
        self.assertEqual([], offenders)

    def test_the_scan_names_a_planted_public_address(self):
        lines = _declared_version_lines()
        text = "the rig stands at 203.0.113.9 in the report\n"
        # 203.0.113.0/24 is the documentation range: not
        # global, so the stand-in for a planted address is a
        # plainly global quad shaped like none of the fleet's.
        text = text.replace("203.0.113.9", "198.51.100.23")
        self.assertEqual([], _public_addresses_in(text, lines),
                         "documentation range must be allowed")
        text = text.replace("198.51.100.23", "45.79.10.20")
        self.assertEqual(["45.79.10.20"],
                         _public_addresses_in(text, lines))

    def test_the_scan_allows_versions_and_non_global_quads(self):
        lines = _declared_version_lines()
        for quad in ("3.16.25.5", "3.15.18.7", "127.0.0.1",
                     "10.0.0.5", "192.0.2.1", "0.0.0.0"):
            self.assertEqual(
                [], _public_addresses_in("x %s y" % quad, lines),
                quad)

    def test_the_scan_rejects_version_shaped_non_versions(self):
        lines = _declared_version_lines()
        # A quad on no declared version line is an address,
        # however version-shaped it looks.
        for quad in ("3.17.25.5", "2.28.30.118"):
            self.assertEqual(
                [quad], _public_addresses_in("x %s y" % quad, lines),
                quad)
        # A leading-zero quad is not a version under
        # version4's strict shape (and not a valid address
        # spelling either): the version check itself refuses it.
        self.assertFalse(_is_project_version("03.16.25.5", lines))
        self.assertTrue(_is_project_version("3.16.25.5", lines))
        self.assertFalse(_is_project_version("3.17.25.5", lines))

    def test_bookended_addresses_are_still_named(self):
        lines = _declared_version_lines()
        for text in ("--45.79.10.20--", ";45.79.10.20;",
                     "\"45.79.10.20\"", "(45.79.10.20)"):
            self.assertEqual(["45.79.10.20"],
                             _public_addresses_in(text, lines),
                             text)


if __name__ == "__main__":
    unittest.main()
