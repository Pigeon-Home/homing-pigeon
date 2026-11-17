# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The README diagram's version 3 label reads "DTLS (v3)".

Q202, filed at the conductor's direction: the green version 3
label in the diagram at the top of README.md carried the words
"via email", and the conductor asked for those two words to be
removed from the picture only, so the label reads "DTLS (v3)"
and nothing else in the picture changes. The label stands in
two files that must stay in agreement: the wide picture
README.md displays, and the full picture the displayed one
links to. Every other use of the longer name in the tree, in
PROTOCOL.md, in the drafts and in the guides, stands exactly
as it is; this test holds the picture only.

This test pins the label in both copies, pins that the two
copies agree, and pins that both files still parse as XML,
so a redraw that restores the old words, edits only one copy,
or breaks the markup fails here.
"""

import os
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PICTURES = [
    "assets/how-it-fits-together-wide.svg",
    "assets/how-it-fits-together.svg",
]
NEW_LABEL = "DTLS (v3)"
OLD_LABEL = "DTLS via email (v3)"


def picture_text(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class ReadmeDiagramLabelTest(unittest.TestCase):

    def test_each_picture_carries_the_short_label_once(self):
        for rel in PICTURES:
            with self.subTest(picture=rel):
                self.assertEqual(1, picture_text(rel).count(NEW_LABEL))

    def test_no_picture_carries_the_old_label(self):
        for rel in PICTURES:
            with self.subTest(picture=rel):
                self.assertNotIn(OLD_LABEL, picture_text(rel))
                self.assertNotIn("DTLS via email", picture_text(rel))

    def test_the_two_pictures_agree_on_the_label(self):
        labels = []
        for rel in PICTURES:
            text = picture_text(rel)
            labels.append(text.count(NEW_LABEL))
        self.assertEqual(labels[0], labels[1])

    def test_each_picture_still_parses_as_xml(self):
        for rel in PICTURES:
            with self.subTest(picture=rel):
                root = ET.parse(os.path.join(ROOT, rel)).getroot()
                self.assertTrue(root.tag.endswith("svg"))

    def test_readme_still_displays_the_wide_picture(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn("assets/how-it-fits-together-wide.svg", readme)
        self.assertIn("assets/how-it-fits-together.svg", readme)


if __name__ == "__main__":
    unittest.main()
