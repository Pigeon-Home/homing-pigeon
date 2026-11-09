# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""The personal-documents shelter: plan, apply, restore, the
config-mode gate, the marker the warning check honours, and the
manifest's fail-closed validation.

The shelter's discipline, from docs/steady/security/
personal-documents-shelter.md: nothing moves without the
operator's --apply, nothing is deleted, nothing is overwritten,
and the only record is a manifest inside the shelter folder on
the operator's own machine.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from runner.guard import security as S  # noqa: E402
from runner.oracle import personal_docs as PD  # noqa: E402
from runner.oracle import personal_docs_shelter as SH  # noqa: E402


def _write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class ShelterHome(unittest.TestCase):
    def setUp(self):
        # Realpath'd: production hands real paths (the plan's
        # sources are realpath'd roots), and on macOS a temp dir
        # sits behind /var -> /private/var, so an un-realpath'd
        # home would not match the manifest's "from" entries.
        self.home = os.path.realpath(tempfile.mkdtemp(prefix="hp-shelter-"))
        self.addCleanup(shutil.rmtree, self.home, True)
        for folder in ("Documents", "Desktop", "Downloads"):
            os.makedirs(os.path.join(self.home, folder))

    def put(self, rel, text="x"):
        # Normpath'd: callers pass rel with "/" separators, and
        # on Windows os.path.join keeps that "/" inside the
        # result, while production's collected paths carry the
        # platform separator throughout — an exact comparison
        # against a manifest entry would differ on that one
        # character. Normpath canonicalizes the separators.
        path = os.path.normpath(os.path.join(self.home, rel))
        _write(path, text)
        return path


class PlanTest(ShelterHome):
    def test_plan_finds_a_sensitive_file_and_ignores_clean_ones(self):
        self.put("Documents/tax return 2024.pdf")
        self.put("Documents/notes.txt")
        plan = SH.plan_shelter(self.home)
        self.assertEqual(1, len(plan))
        self.assertTrue(plan[0]["source"].endswith("tax return 2024.pdf"))
        self.assertEqual(os.path.join("Documents", "tax return 2024.pdf"),
                         plan[0]["dest"])

    def test_plan_takes_a_sensitive_folder_whole(self):
        self.put("Documents/Taxes 2024/return.pdf")
        self.put("Documents/Taxes 2024/receipts.pdf")
        plan = SH.plan_shelter(self.home)
        self.assertEqual(1, len(plan))
        self.assertTrue(plan[0]["source"].endswith("Taxes 2024"))

    def test_plan_covers_desktop_downloads_and_onedrive(self):
        self.put("Desktop/passport scan.pdf")
        self.put("Downloads/w2 form.pdf")
        self.put("OneDrive/Documents/mortgage.pdf")
        sources = [os.path.basename(p["source"])
                   for p in SH.plan_shelter(self.home)]
        self.assertEqual(
            ["mortgage.pdf", "passport scan.pdf", "w2 form.pdf"],
            sorted(sources))

    def test_plan_skips_symlinks(self):
        target = self.put("Documents/real.pdf")
        os.symlink(target, os.path.join(self.home, "Documents", "tax.pdf"))
        self.assertEqual([], SH.plan_shelter(self.home))

    def test_plan_skips_skip_dirs_and_dotfiles(self):
        self.put("Documents/node_modules/taxes/return.pdf")
        self.put("Documents/.taxes/return.pdf")
        self.assertEqual([], SH.plan_shelter(self.home))

    def test_plan_respects_the_depth_the_check_uses(self):
        self.put("Documents/a/b/tax.pdf")
        self.put("Documents/a/b/c/insurance.pdf")
        plan = SH.plan_shelter(self.home)
        self.assertEqual(1, len(plan))
        self.assertTrue(plan[0]["source"].endswith(
            os.path.join("a", "b", "tax.pdf")))

    def test_plan_never_replans_the_shelter_itself(self):
        sheltered = self.put(os.path.join(
            "Desktop", "Sheltered Documents", "Documents", "tax.pdf"))
        _write(os.path.join(self.home, "Desktop", "Sheltered Documents",
                            PD.SHELTER_MARKER_NAME),
               PD.SHELTER_MARKER_MAGIC + "\n")
        self.assertTrue(os.path.exists(sheltered))
        self.assertEqual([], SH.plan_shelter(self.home))

    def test_plan_on_a_missing_home_is_empty(self):
        self.assertEqual([], SH.plan_shelter(
            os.path.join(self.home, "nope")))

    def test_plan_bookend_and_unicode_names(self):
        for name in ("--tax.pdf", " tax .pdf", "t'ax-passport.pdf",
                     "tax\U0001F4A6.pdf", "tax\u200b.pdf",
                     "my-very-long-tax-document-name-for-2024.pdf"):
            self.put(os.path.join("Documents", name))
        plan = SH.plan_shelter(self.home)
        self.assertEqual(6, len(plan))


class ApplyRestoreTest(ShelterHome):
    def test_apply_moves_marks_and_records(self):
        src = self.put("Documents/tax return 2024.pdf", "papers")
        result = SH.apply_shelter(self.home)
        self.assertEqual([], result["errors"])
        self.assertEqual(1, len(result["moved"]))
        self.assertFalse(os.path.exists(src))
        dest = result["moved"][0]["to"]
        with open(dest, encoding="utf-8") as fh:
            self.assertEqual("papers", fh.read())
        root = SH.shelter_root(self.home)
        self.assertTrue(PD.is_shelter_dir(root))
        entries = SH.load_manifest(self.home)
        self.assertEqual([{"from": src, "to": dest}], entries)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits only")
    def test_shelter_folder_is_operator_only(self):
        self.put("Documents/tax.pdf")
        SH.apply_shelter(self.home)
        mode = os.stat(SH.shelter_root(self.home)).st_mode & 0o777
        self.assertEqual(0o700, mode)

    def test_after_apply_the_warning_check_is_quiet(self):
        self.put("Documents/tax return 2024.pdf")
        self.assertTrue(PD.personal_documents_present(self.home))
        SH.apply_shelter(self.home)
        self.assertFalse(PD.personal_documents_present(self.home))

    def test_apply_is_repeatable_and_never_clobbers_the_manifest(self):
        self.put("Documents/tax.pdf")
        SH.apply_shelter(self.home)
        self.put("Downloads/passport.pdf")
        result = SH.apply_shelter(self.home)
        self.assertEqual(1, len(result["moved"]))
        self.assertEqual(2, len(SH.load_manifest(self.home)))

    def test_apply_never_overwrites_a_name_already_in_the_shelter(self):
        root = SH.shelter_root(self.home)
        taken = os.path.join(root, "Documents", "tax.pdf")
        _write(taken, "already here")
        self.put("Documents/tax.pdf", "new papers")
        result = SH.apply_shelter(self.home)
        dest = result["moved"][0]["to"]
        self.assertTrue(dest.endswith("tax (2).pdf"))
        with open(taken, encoding="utf-8") as fh:
            self.assertEqual("already here", fh.read())
        with open(dest, encoding="utf-8") as fh:
            self.assertEqual("new papers", fh.read())

    def test_same_name_in_two_watched_folders_stays_distinct(self):
        self.put("Documents/tax.pdf", "one")
        self.put("Downloads/tax.pdf", "two")
        result = SH.apply_shelter(self.home)
        self.assertEqual(2, len(result["moved"]))
        dests = sorted(r["to"] for r in result["moved"])
        self.assertNotEqual(dests[0], dests[1])
        for record in result["moved"]:
            with open(record["to"], encoding="utf-8") as fh:
                self.assertIn(fh.read(), ("one", "two"))

    def test_apply_collects_a_vanished_source_and_moves_the_rest(self):
        gone = self.put("Documents/tax.pdf")
        self.put("Documents/passport.pdf")
        plan = SH.plan_shelter(self.home)
        os.unlink(gone)
        result = SH.apply_shelter(self.home, plan)
        self.assertEqual(1, len(result["moved"]))
        self.assertEqual(1, len(result["errors"]))
        self.assertEqual(1, len(SH.load_manifest(self.home)))

    def test_apply_refuses_over_a_corrupt_existing_manifest(self):
        root = SH.shelter_root(self.home)
        _write(os.path.join(root, SH.MANIFEST_NAME), "not json")
        src = self.put("Documents/tax.pdf")
        with self.assertRaises(SH.ShelterError):
            SH.apply_shelter(self.home)
        self.assertTrue(os.path.exists(src))

    def test_restore_puts_everything_back(self):
        src = self.put("Documents/tax return 2024.pdf", "papers")
        SH.apply_shelter(self.home)
        result = SH.restore_shelter(self.home)
        self.assertEqual([], result["errors"])
        self.assertEqual(1, len(result["restored"]))
        with open(src, encoding="utf-8") as fh:
            self.assertEqual("papers", fh.read())
        self.assertEqual([], SH.load_manifest(self.home))
        self.assertFalse(os.path.exists(os.path.join(
            SH.shelter_root(self.home), SH.MANIFEST_NAME)))

    def test_restore_never_overwrites_an_occupied_place(self):
        src = self.put("Documents/tax.pdf", "sheltered")
        SH.apply_shelter(self.home)
        _write(src, "new occupant")
        result = SH.restore_shelter(self.home)
        self.assertEqual(0, len(result["restored"]))
        self.assertEqual(1, len(result["errors"]))
        with open(src, encoding="utf-8") as fh:
            self.assertEqual("new occupant", fh.read())
        self.assertEqual(1, len(SH.load_manifest(self.home)))

    def test_restore_reports_a_missing_sheltered_item(self):
        self.put("Documents/tax.pdf")
        record = SH.apply_shelter(self.home)["moved"][0]
        os.unlink(record["to"])
        result = SH.restore_shelter(self.home)
        self.assertEqual(1, len(result["errors"]))
        self.assertEqual(1, len(SH.load_manifest(self.home)))

    def test_round_trip_with_a_bookend_name(self):
        name = "-- w2 --.pdf"
        src = self.put(os.path.join("Documents", name), "papers")
        SH.apply_shelter(self.home)
        self.assertFalse(os.path.exists(src))
        SH.restore_shelter(self.home)
        self.assertTrue(os.path.exists(src))


class MarkerTest(ShelterHome):
    def _shelter_with(self, marker_text):
        folder = os.path.join(self.home, "Desktop", "Sheltered Documents")
        _write(os.path.join(folder, "tax.pdf"))
        if marker_text is not None:
            _write(os.path.join(folder, PD.SHELTER_MARKER_NAME), marker_text)
        return folder

    def test_the_name_alone_does_not_make_a_shelter(self):
        self._shelter_with(None)
        self.assertTrue(PD.personal_documents_present(self.home))

    def test_a_wrong_marker_does_not_make_a_shelter(self):
        self._shelter_with("some other text\n")
        self.assertTrue(PD.personal_documents_present(self.home))

    def test_the_real_marker_takes_the_folder_out_of_scope(self):
        self._shelter_with(PD.SHELTER_MARKER_MAGIC + "\n")
        self.assertFalse(PD.personal_documents_present(self.home))

    def test_is_shelter_dir_on_a_missing_folder_is_false(self):
        self.assertFalse(PD.is_shelter_dir(
            os.path.join(self.home, "nope")))


class ManifestFuzzTest(ShelterHome):
    """The manifest is a text surface: restore trusts it to move
    files, so every malformed shape must fail closed and move
    nothing."""

    def _manifest(self, text):
        root = SH.shelter_root(self.home)
        _write(os.path.join(root, SH.MANIFEST_NAME), text)

    def _doc(self, entries, **over):
        data = {"format": SH.MANIFEST_FORMAT,
                "version": SH.MANIFEST_VERSION, "entries": entries}
        data.update(over)
        return json.dumps(data)

    def _entry(self, **over):
        root = SH.shelter_root(self.home)
        entry = {"from": os.path.join(self.home, "Documents", "tax.pdf"),
                 "to": os.path.join(root, "Documents", "tax.pdf")}
        entry.update(over)
        return entry

    def test_a_valid_manifest_loads(self):
        self._manifest(self._doc([self._entry()]))
        self.assertEqual(1, len(SH.load_manifest(self.home)))

    def test_malformed_manifests_fail_closed(self):
        root = SH.shelter_root(self.home)
        bad = [
            "",
            "not json",
            "[]",
            "{}",
            self._doc([], format="other-format"),
            self._doc([], version=2),
            self._doc({}),
            self._doc(["not a dict"]),
            self._doc([{"from": "/x"}]),
            self._doc([self._entry(extra="nope")]),
            self._doc([self._entry(**{"from": 42})]),
            self._doc([self._entry(to=root)]),
            self._doc([self._entry(
                to=os.path.join(root, "..", "escape.pdf"))]),
            self._doc([self._entry(**{
                "from": os.path.join(self.home, "..", "outside.pdf")})]),
            self._doc([self._entry(**{
                "from": os.path.join(self.home, "Documents", "ta\x00x.pdf")})]),
            self._doc([self._entry(), self._entry()]),
            json.dumps({"format": SH.MANIFEST_FORMAT,
                        "version": SH.MANIFEST_VERSION,
                        "entries": None}),
        ]
        for text in bad:
            with self.subTest(text=text[:40]):
                self._manifest(text)
                with self.assertRaises(SH.ShelterError):
                    SH.load_manifest(self.home)
                with self.assertRaises(SH.ShelterError):
                    SH.restore_shelter(self.home)

    def test_a_missing_manifest_is_an_empty_shelter(self):
        self.assertEqual([], SH.load_manifest(self.home))
        result = SH.restore_shelter(self.home)
        self.assertEqual({"restored": [], "errors": []}, result)


class ModeGateTest(ShelterHome):
    def _config(self, modes):
        path = os.path.join(self.home, "config.json")
        _write(path, json.dumps({"security": {"modes": modes}}))
        return path

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = SH.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_the_feature_is_a_known_security_feature(self):
        self.assertIn(SH.FEATURE, S.FEATURES)
        S.validate_security_config(
            {"security": {"modes": {SH.FEATURE: "audit"}}})
        self.assertEqual("enforce", S.sec_mode({}, SH.FEATURE))

    def test_off_refuses_and_moves_nothing(self):
        src = self.put("Documents/tax.pdf")
        cfg = self._config({SH.FEATURE: "off"})
        rc, _out, _err = self._run(
            ["--home", self.home, "--config", cfg, "--apply"])
        self.assertEqual(2, rc)
        self.assertTrue(os.path.exists(src))

    def test_audit_plans_even_when_apply_is_asked(self):
        src = self.put("Documents/tax.pdf")
        cfg = self._config({SH.FEATURE: "audit"})
        rc, out, _err = self._run(
            ["--home", self.home, "--config", cfg, "--apply"])
        self.assertEqual(0, rc)
        self.assertIn("plan only", out)
        self.assertTrue(os.path.exists(src))

    def test_enforce_with_apply_shelters(self):
        src = self.put("Documents/tax.pdf")
        cfg = self._config({SH.FEATURE: "enforce"})
        rc, _out, _err = self._run(
            ["--home", self.home, "--config", cfg, "--apply"])
        self.assertEqual(0, rc)
        self.assertFalse(os.path.exists(src))

    def test_no_config_defaults_to_the_house_default(self):
        src = self.put("Documents/tax.pdf")
        rc, _out, _err = self._run(["--home", self.home, "--apply"])
        self.assertEqual(0, rc)
        self.assertFalse(os.path.exists(src))

    def test_planning_is_the_default_and_prints_the_plan(self):
        src = self.put("Documents/tax.pdf")
        rc, out, _err = self._run(["--home", self.home])
        self.assertEqual(0, rc)
        self.assertIn("would shelter", out)
        self.assertTrue(os.path.exists(src))

    def test_restore_through_main(self):
        src = self.put("Documents/tax.pdf", "papers")
        self._run(["--home", self.home, "--apply"])
        rc, _out, _err = self._run(["--home", self.home, "--restore"])
        self.assertEqual(0, rc)
        self.assertTrue(os.path.exists(src))

    def test_a_bad_config_is_a_refusal_not_a_traceback(self):
        path = os.path.join(self.home, "config.json")
        _write(path, "{broken")
        rc, _out, _err = self._run(
            ["--home", self.home, "--config", path, "--apply"])
        self.assertEqual(2, rc)


if __name__ == "__main__":
    unittest.main()
