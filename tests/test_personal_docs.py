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
        self.assertNotIn("ignore", BANNER.lower())
        self.assertNotIn("--", BANNER)
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


class SwitchTest(unittest.TestCase):
    def test_the_switch_does_not_run_the_check(self):
        import argparse
        from runner.runner import log_startup
        import runner.runner as R
        args = argparse.Namespace(
            verbose=False, workers=None, poll_interval=None,
            max_output_bytes=None, timeout=None,
            dry_run=False, once=False, no_send=False,
            ignore_personal_documents=True)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    R._personal_docs, "warn_if_personal_documents",
                    side_effect=AssertionError("check ran")):
                log_startup({}, args, d)

    def test_without_the_switch_the_check_runs(self):
        import argparse
        from runner.runner import log_startup
        import runner.runner as R
        args = argparse.Namespace(
            verbose=False, workers=None, poll_interval=None,
            max_output_bytes=None, timeout=None,
            dry_run=False, once=False, no_send=False,
            ignore_personal_documents=False)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(
                    R._personal_docs, "warn_if_personal_documents",
                    return_value=False) as warn:
                log_startup({}, args, d)
        warn.assert_called_once_with()

    def test_install_bakes_the_switch_into_the_service(self):
        import types
        from runner import install
        baked = install._forwarded_args(types.SimpleNamespace(
            dry_run=False, no_send=False, pdb=False,
            allow_cleartext=False, verbose=True,
            poll_interval=None, max_output_bytes=None,
            timeout=None, workers=None,
            ignore_personal_documents=True))
        self.assertIn("--ignore-personal-documents", baked)
        quiet = install._forwarded_args(types.SimpleNamespace(
            dry_run=False, no_send=False, pdb=False,
            allow_cleartext=False, verbose=True,
            poll_interval=None, max_output_bytes=None,
            timeout=None, workers=None,
            ignore_personal_documents=False))
        self.assertNotIn("--ignore-personal-documents", quiet)


class WarningEdgesTest(unittest.TestCase):
    """Names and folders the ordinary scan does not produce."""

    def test_a_phrase_trips(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(home, "Downloads", "bank-statement.pdf"))
            self.assertTrue(personal_documents_present(home))
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "Documents", "health_records"))
            self.assertTrue(personal_documents_present(home))

    def test_a_trailing_mark_does_not_hide_a_token(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(home, "Desktop", "tax-"))
            self.assertTrue(personal_documents_present(home))

    def test_node_modules_and_a_dotfile_are_not_papers(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(
                home, "Documents", "node_modules", "diagnosis.pdf"))
            _touch(os.path.join(home, "Documents", ".diagnosis.pdf"))
            self.assertFalse(personal_documents_present(home))

    def test_a_plain_folder_of_a_form_still_trips(self):
        with tempfile.TemporaryDirectory() as home:
            _touch(os.path.join(home, "Documents", "2024", "1040.pdf"))
            self.assertTrue(personal_documents_present(home))

    def test_xdg_junk_is_ignored(self):
        with tempfile.TemporaryDirectory() as home:
            papers = os.path.join(home, "papers")
            _touch(os.path.join(papers, "diagnosis.pdf"))
            cfg = os.path.join(home, ".config")
            os.makedirs(cfg)
            path = os.path.join(cfg, "user-dirs.dirs")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n# comment\nnot a pair\n")
                fh.write('XDG_MUSIC_DIR="$HOME/papers"\n')
                fh.write("XDG_DOWNLOAD_DIR=papers\n")
                fh.write('XDG_DOCUMENTS_DIR="$HOME/papers"\n')
            self.assertTrue(personal_documents_present(home))
            os.remove(os.path.join(papers, "diagnosis.pdf"))
            os.remove(path)
            os.symlink(os.path.join(home, "missing-dirs"), path)
            self.assertFalse(personal_documents_present(home))
            os.remove(path)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x" * 17000)
            _touch(os.path.join(papers, "diagnosis.pdf"))
            self.assertFalse(personal_documents_present(home))

    def test_the_same_folder_is_not_walked_twice(self):
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, ".config"))
            with open(os.path.join(home, ".config", "user-dirs.dirs"),
                      "w", encoding="utf-8") as fh:
                fh.write('XDG_DOCUMENTS_DIR="$HOME/Documents"\n')
            _touch(os.path.join(home, "Documents", "notes.txt"))
            self.assertFalse(personal_documents_present(home))

    def test_two_thousand_notes_stop_the_scan(self):
        with tempfile.TemporaryDirectory() as home:
            desk = os.path.join(home, "Documents")
            os.makedirs(desk)
            for i in range(2001):
                _touch(os.path.join(desk, "note%04d.txt" % i))
            self.assertFalse(personal_documents_present(home))

    def test_an_unreadable_folder_is_quiet(self):
        real_scan = os.scandir

        def deny_documents(path):
            if os.path.basename(os.path.normpath(path)) == "Documents":
                raise OSError("denied")
            return real_scan(path)

        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "Documents"))
            with mock.patch("runner.personal_docs.os.scandir", deny_documents):
                self.assertFalse(personal_documents_present(home))

        def deny_home(path):
            raise OSError("denied")

        with tempfile.TemporaryDirectory() as home:
            with mock.patch("runner.personal_docs.os.scandir", deny_home):
                self.assertFalse(personal_documents_present(home))

    def test_a_crash_in_the_check_prints_nothing(self):
        buf = io.StringIO()
        with mock.patch(
                "runner.personal_docs.personal_documents_present",
                side_effect=RuntimeError("disk")):
            self.assertFalse(warn_if_personal_documents(
                "/tmp", stream=buf))
        self.assertEqual(buf.getvalue(), "")

    def test_a_path_realpath_cannot_resolve_is_not_papers(self):
        with tempfile.TemporaryDirectory() as home:
            papers = os.path.join(home, "papers")
            _touch(os.path.join(papers, "diagnosis.pdf"))
            os.makedirs(os.path.join(home, ".config"))
            with open(os.path.join(home, ".config", "user-dirs.dirs"),
                      "w", encoding="utf-8") as fh:
                fh.write('XDG_DOCUMENTS_DIR="%s"\n' % papers)
            real = os.path.realpath
            def boom(path):
                if path == papers:
                    raise OSError("gone")
                return real(path)
            with mock.patch("runner.personal_docs.os.path.realpath", boom):
                self.assertFalse(personal_documents_present(home))

    def test_a_symlink_inside_documents_is_not_a_paper(self):
        with tempfile.TemporaryDirectory() as home, \
                tempfile.TemporaryDirectory() as outside:
            _touch(os.path.join(outside, "diagnosis.pdf"))
            os.makedirs(os.path.join(home, "Documents"))
            os.symlink(os.path.join(outside, "diagnosis.pdf"),
                       os.path.join(home, "Documents", "diagnosis.pdf"))
            self.assertFalse(personal_documents_present(home))

    def test_an_xdg_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as home, \
                tempfile.TemporaryDirectory() as outside:
            _touch(os.path.join(outside, "diagnosis.pdf"))
            link = os.path.join(home, "linked-papers")
            os.symlink(outside, link)
            os.makedirs(os.path.join(home, ".config"))
            with open(os.path.join(home, ".config", "user-dirs.dirs"),
                      "w", encoding="utf-8") as fh:
                fh.write('XDG_DOCUMENTS_DIR="%s"\n' % link)
            self.assertFalse(personal_documents_present(home))

    def test_two_thousand_names_in_the_home_stop_the_scan(self):
        with tempfile.TemporaryDirectory() as home:
            for i in range(2001):
                _touch(os.path.join(home, "page%04d.txt" % i))
            self.assertFalse(personal_documents_present(home))


if __name__ == "__main__":
    unittest.main()
