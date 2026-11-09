# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""Feature tiers: the inventory page names what the tree ships.

docs/steady/feature-tiers.md sorts the shipped features into
the supported core, the advanced tier, and the experimental
tier, each placement resting on evidence in the tree: a
config gate in runner/config.example.json, an "(optional)"
or "(opt-in)" marker in PROTOCOL.md, or a shipped /
design-notes label in the transports document. This test is
the consistency check between the page and that evidence:

- every folder in runner/transport_extensions/ has its row
  in the tier the page assigns it, and the count the page
  states is the count the tree has;
- the transports document's own shipped / built labels name
  exactly the transports the page places in tiers 1 and 2,
  and the sections with no shipped code are the ones the
  page names in tier 3;
- the features the README's Status paragraph claims — the
  agent, opinions, self-learning, remediation, five job
  transports, the example senses — each appear in the tier
  the page assigns them, with the splits (key management,
  learning, remediation, DTLS) landing in both of their
  tiers;
- the config defaults and PROTOCOL.md markers the page
  cites still read as the page says they read.

The pins are against the documents and the config the page
cites, never against a second copy of the page's table: if
a feature moves tiers, the page and this test's assignment
map move together, and the tree-derived checks (folders,
counts, labels, defaults) are what fail first.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAGE = os.path.join(ROOT, "docs", "steady", "feature-tiers.md")
README = os.path.join(ROOT, "README.md")
PROTOCOL = os.path.join(ROOT, "PROTOCOL.md")
CONFIG = os.path.join(ROOT, "runner", "config.example.json")
TRANSPORTS_DOC = os.path.join(
    ROOT, "docs", "infrastructure-documents", "extend", "transports.md")
TRANSPORT_DIR = os.path.join(ROOT, "runner", "transport_extensions")
EXTENSION_DIR = os.path.join(ROOT, "runner", "extensions")

TIER_HEADINGS = ["## Tier 1 — the supported core",
                 "## Tier 2 — advanced, supported",
                 "## Tier 3 — experimental and research"]

# The page's assignment of the shipped transports: folder ->
# (needle in a table row's first cell, tier).
TRANSPORT_TIERS = {"email": ("The email transport", 1),
                   "file": ("The file transport", 2),
                   "nats": ("The NATS transport", 2),
                   "dtls": ("The DTLS transport", 2),
                   "queues": ("The hosted queue transport", 2)}

# Transports the transports document describes but no folder
# ships, as the page's tier 3 row names them.
UNSHIPPED_TRANSPORTS = ["NATS JetStream", "MQTT", "Redis Streams",
                        "Postgres", "Cloudflare Durable Objects",
                        "Local socket"]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _tier_sections(text):
    """The page's text under each tier heading, in tier order."""
    out = []
    for i, heading in enumerate(TIER_HEADINGS):
        start = text.index(heading)
        nxt = text.find("\n## ", start + len(heading))
        out.append(text[start:] if nxt < 0 else text[start:nxt])
    return out


def _first_cells(section):
    """The first cell of every table row in a tier section."""
    cells = []
    for line in section.splitlines():
        if line.startswith("| ") and "---" not in line:
            cell = line.split("|")[1].strip()
            if cell and cell != "Feature":
                cells.append(cell)
    return cells


class FeatureTiersPageTest(unittest.TestCase):

    def test_page_names_three_tiers_in_order(self):
        text = _read(PAGE)
        positions = [text.index(h) for h in TIER_HEADINGS]
        self.assertEqual(positions, sorted(positions))

    def test_readme_points_at_the_page(self):
        self.assertIn("docs/steady/feature-tiers.md", _read(README))

    def test_every_row_sits_in_exactly_one_tier(self):
        sections = _tier_sections(_read(PAGE))
        cells = [c for s in sections for c in _first_cells(s)]
        self.assertEqual(len(cells), len(set(cells)),
                         "a feature row appears in more than one tier")

    def test_every_shipped_transport_has_its_row_in_its_tier(self):
        sections = _tier_sections(_read(PAGE))
        cells = [_first_cells(s) for s in sections]
        folders = sorted(d for d in os.listdir(TRANSPORT_DIR)
                         if os.path.isdir(os.path.join(TRANSPORT_DIR, d))
                         and d != "__pycache__")
        self.assertEqual(sorted(TRANSPORT_TIERS), folders,
                         "a shipped transport folder the page's "
                         "assignment does not name, or the reverse")
        for folder, (needle, tier) in TRANSPORT_TIERS.items():
            self.assertTrue(
                any(needle in c for c in cells[tier - 1]),
                f"{folder}: no row naming {needle!r} in tier {tier}")
            for other in (1, 2, 3):
                if other != tier:
                    self.assertFalse(
                        any(needle in c for c in cells[other - 1]),
                        f"{folder}: its row also appears in tier {other}")

    def test_the_counts_the_page_states_are_the_tree_s_counts(self):
        # Prose wraps; the counts are checked on the page's
        # text with its whitespace flattened.
        text = " ".join(_read(PAGE).split())
        folders = [d for d in os.listdir(TRANSPORT_DIR)
                   if os.path.isdir(os.path.join(TRANSPORT_DIR, d))
                   and d != "__pycache__"]
        self.assertIn(f"{len(folders)} shipped transport folders", text)
        senses = [d for d in os.listdir(EXTENSION_DIR)
                  if os.path.isdir(os.path.join(EXTENSION_DIR, d))]
        self.assertIn(f"{len(senses)} folders in `runner/extensions/`", text)

    def test_transports_doc_labels_match_the_page_s_tiers(self):
        shipped = []
        for line in _read(TRANSPORTS_DOC).splitlines():
            m = re.match(r"^## (.+?) — (.*)$", line)
            if m and ("shipped" in m.group(2) or "(built)" in m.group(2)):
                shipped.append(m.group(1).split()[0].lower())
        self.assertEqual(["dtls", "file", "nats", "queues"], sorted(shipped))
        sections = _tier_sections(_read(PAGE))
        placed = " ".join(c for s in sections[:2] for c in _first_cells(s)).lower()
        for name in shipped:
            self.assertIn(name.rstrip("s") if name == "queues" else name,
                          placed)

    def test_unshipped_transports_are_named_in_tier_3(self):
        tier3 = _tier_sections(_read(PAGE))[2]
        for name in UNSHIPPED_TRANSPORTS:
            self.assertIn(name, tier3)

    def test_readme_status_features_are_tiered(self):
        sections = _tier_sections(_read(PAGE))
        cells = [_first_cells(s) for s in sections]

        def placed(needle, tier):
            return any(needle in c for c in cells[tier - 1])

        # The agent, and the core the README's shape rests on.
        for needle in ("The runner", "Job verification",
                       "Per-job encryption", "The audit log",
                       "Confinement", "The separate job user",
                       "Simple result handling"):
            self.assertTrue(placed(needle, 1), f"{needle}: not in tier 1")
        # Opinions and the senses, in the advanced tier.
        self.assertTrue(placed("tier-1 opinions", 2))
        self.assertTrue(placed("Senses:", 2))
        # Five job transports across tiers 1 and 2 — no more, no fewer.
        rows = [c for s in cells[:2] for c in s if "transport" in c.lower()]
        self.assertEqual(5, len(rows))

    def test_split_features_land_in_both_of_their_tiers(self):
        sections = _tier_sections(_read(PAGE))
        cells = [_first_cells(s) for s in sections]

        def placed(needle, tier):
            return any(needle in c for c in cells[tier - 1])

        # Key management: the base form in the core, the marked
        # opt-in parts in the advanced tier.
        self.assertTrue(placed("Key management in its base form", 1))
        self.assertTrue(placed("Per-key policies", 2))
        self.assertTrue(placed("The key directory", 2))
        # Learning: verified facts advanced, model candidates
        # experimental.
        self.assertTrue(placed("verified facts", 2))
        self.assertTrue(placed("Model-distilled learning candidates", 3))
        # Remediation: the deterministic reflex advanced, the
        # model-driven one experimental.
        self.assertTrue(placed("Deterministic remediation", 2))
        self.assertTrue(placed("Model-driven remediation", 3))
        # DTLS: the shipped binding advanced, its hybrid group
        # experimental.
        self.assertTrue(placed("The DTLS transport", 2))
        self.assertTrue(placed("The DTLS hybrid group", 3))


class FeatureTiersEvidenceTest(unittest.TestCase):
    """The defaults and markers the page cites, read at the source."""

    def test_config_defaults_the_page_cites(self):
        cfg = json.loads(_read(CONFIG))
        self.assertEqual(["email"], cfg["transports"])
        modes = cfg["security"]["modes"]
        self.assertEqual("enforce", modes["confinement"])
        self.assertEqual("enforce", modes["job_user"])
        self.assertEqual("full", cfg["max_result_view"])
        self.assertEqual("repair", cfg["oracle_opinion_mode"])
        self.assertEqual("deterministic", cfg["remediation_mode"])
        self.assertEqual("enforce", cfg["extension_review"])
        self.assertIs(True, cfg["oracle_learning"])
        self.assertIs(False, cfg["oracle_learning_model"])
        self.assertIs(False, cfg["oracle_opinion_model"])
        self.assertEqual("", cfg["inference"]["endpoint"])
        self.assertIs(False, cfg["dri"]["enabled"])

    def test_protocol_markers_the_page_cites(self):
        lines = _read(PROTOCOL).splitlines()
        self.assertIn("### 9.3 Pre-execution judgment (optional)", lines)
        self.assertIn("### 14.1 Per-key policies (opt-in)", lines)
        self.assertIn("### 14.4 The key directory (opt-in)", lines)
        for head in ("### 14.2", "### 14.3"):
            line = next(l for l in lines if l.startswith(head))
            self.assertNotIn("(opt-in)", line)
            self.assertNotIn("(optional)", line)

    def test_v2_gate_the_page_cites(self):
        src = _read(os.path.join(ROOT, "runner", "wire", "protocol_v2.py"))
        self.assertIn('cfg.get("protocol_v2") is True', src)
        wire = os.listdir(os.path.join(ROOT, "runner", "wire"))
        self.assertIn("protocol_v2.py", wire)
        self.assertNotIn("protocol_v3.py", wire)


if __name__ == "__main__":
    unittest.main()
