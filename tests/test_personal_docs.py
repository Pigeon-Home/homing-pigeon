"""The personal-documents warning looks at names and nothing else."""

import io
import os
import tempfile
import unittest
from unittest import mock

from runner.personal_docs import (
    BANNER,
    personal_documents_present,
    warn_if_personal_documents,
)


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("body-that-must-not-leak")


class BannerTest(unittest.TestCase):
    def test_the_banner_is_a_fixed_box(self):
        lines = BANNER.splitlines()
        self.assertGreater(len(lines), 8)
        width = len(lines[0])
        self.assertTrue(set(lines[0]) == {"*"})
        self.assertTrue(all(len(line) == width for line in lines))
        self.assertIn("IMPORTANT DOCUMENTS", BANNER)
        self.assertIn("do NOT install", BANNER)
        self.assertIn("proficient system administrator", BANNER)
        self.assertNotIn("body-that-must-not-leak", BANNER)


class ScanTest(unittest.TestCase):
    def test_an_empty_home_is_quiet(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertFalse(personal_documents_present(home))

    def test_ordinary_notes_do_not_trip(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(home, "Documents", "notes.txt"))
            _touch(os.path.join(home, "Documents", "healthcheck.txt"))
            _touch(os.path.join(home, "Documents", "taxonomy.pdf"))
            self.assertFalse(personal_documents_present(home))

    def test_a_tax_file_two_levels_down_trips(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(
                home, "Documents", "Taxes", "2024-1040.pdf"))
            self.assertTrue(personal_documents_present(home))

    def test_deeper_than_the_cap_is_not_a_hit(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(
                home, "Documents", "a", "b", "c", "diagnosis.pdf"))
            self.assertFalse(personal_documents_present(home))

    def test_a_w2_with_a_hyphen_trips(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(home, "Desktop", "w-2.pdf"))
            self.assertTrue(personal_documents_present(home))

    def test_a_medical_folder_at_the_home_root_trips(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "Medical"))
            self.assertTrue(personal_documents_present(home))

    def test_onedrive_documents_count(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(
                home, "OneDrive - Personal", "Documents",
                "insurance.pdf"))
            self.assertTrue(personal_documents_present(home))

    def test_a_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as home, \
                tempfile.TemporaryDirectory() as outside:
            _touch(os.path.join(outside, "diagnosis.pdf"))
            os.symlink(outside, os.path.join(home, "Documents"))
            self.assertFalse(personal_documents_present(home))

    def test_xdg_inside_home_counts_and_outside_does_not(self):
        with tempfile.TemporaryDirectory() as home, \
                tempfile.TemporaryDirectory() as outside:
            papers = os.path.join(home, "papers")
            _touch(os.path.join(papers, "diagnosis.pdf"))
            os.makedirs(os.path.join(home, ".config"))
            with open(os.path.join(home, ".config", "user-dirs.dirs"),
                      "w", encoding="utf-8") as fh:
                fh.write('XDG_DOCUMENTS_DIR="$HOME/papers"\n')
            self.assertTrue(personal_documents_present(home))
            _touch(os.path.join(outside, "diagnosis.pdf"))
            with open(os.path.join(home, ".config", "user-dirs.dirs"),
                      "w", encoding="utf-8") as fh:
                fh.write('XDG_DOCUMENTS_DIR="%s"\n' % outside)
            os.remove(os.path.join(papers, "diagnosis.pdf"))
            self.assertFalse(personal_documents_present(home))

    def test_the_document_itself_is_never_opened(self):
        opened = []
        real_open = open

        def guard(file, *args, **kwargs):
            opened.append(os.path.basename(str(file)))
            return real_open(file, *args, **kwargs)

        with tempfile.TemporaryDirectory() as home:
            path = os.path.join(home, "Documents", "Taxes", "1040.pdf")
            _touch(path)
            with mock.patch("builtins.open", guard):
                self.assertTrue(personal_documents_present(home))
        self.assertNotIn("1040.pdf", opened)

    def test_the_banner_does_not_repeat_the_name(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(home, "Documents", "secret-diagnosis.pdf"))
            buf = io.StringIO()
            self.assertTrue(warn_if_personal_documents(home, stream=buf))
            text = buf.getvalue()
        self.assertIn("IMPORTANT DOCUMENTS", text)
        self.assertNotIn("secret-diagnosis", text)
        self.assertNotIn("body-that-must-not-leak", text)

    def test_a_miss_prints_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            buf = io.StringIO()
            self.assertFalse(warn_if_personal_documents(home, stream=buf))
            self.assertEqual(buf.getvalue(), "")

    def test_a_missing_home_does_not_raise(self):
        self.assertFalse(personal_documents_present(
            os.path.join(tempfile.gettempdir(), "hp-no-such-home")))
        self.assertFalse(personal_documents_present(""))
        self.assertFalse(personal_documents_present(None))


if __name__ == "__main__":
    unittest.main()
