# Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026
"""runner/tools/release_gate.py: the release gate's mechanical half.

The gate's design stands in docs/infrastructure-documents/project/
release-gate.md: the conductor reads one checklist over one
finished candidate and signs before the tag is cut. These tests
hold the mechanical half to that design:

- the class registry, shut: every declared path family classifies
  as the design's table says, a path in two families asks for
  both classes, and paths outside the families ask for nothing;
- the two measured corrections: a commit with the release shape
  is machinery and is never classified (so the version carriers
  stop flagging key handling on every release), and a change
  confined to a figure slot's value is a figure refresh, not a
  class event, while any other changed line in the same file
  takes the file's normal classes;
- the checklist rendering: the ten items in the design's order,
  the classes touched declared on the machine line, the classes
  not touched asking nothing, and the protected-candidate form
  when commits stand beyond the candidate;
- the sign-off validator, failing closed: missing, duplicated,
  empty and unknown fields; a shortened version; a short SHA; a
  candidate form at war with its verdict form; a touched class
  with no reviewed line; a reviewed line for a class the range
  did not touch; and the valid records — standard, protected,
  and an honest not-signed — passing.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from runner.tools import release_gate as RG  # noqa: E402

SHA = "a" * 40
SHA_B = "b" * 40


def _record(touched=("protocol",), verdict="signed", form="standard",
            version="3.15.20.14", sha=SHA, conductor="The conductor",
            date="2026-11-09", reviewed=None, extra=""):
    if reviewed is None:
        reviewed = touched
    lines = [
        "# Release candidate record: %s" % version,
        "",
        "- Classes touched: %s" % (", ".join(touched) if touched else "none"),
        "",
        "## Sign-off",
        "",
        "- Version: %s" % version,
        "- Release commit: %s" % sha,
        "- Candidate: %s" % form,
        "- Conductor: %s" % conductor,
        "- Date: %s" % date,
        "- Verdict: %s" % verdict,
    ]
    for name in reviewed:
        lines.append("- Reviewed: %s" % name)
    if extra:
        lines.append(extra)
    return "\n".join(lines) + "\n"


class RegistryTest(unittest.TestCase):

    def test_protocol_paths(self):
        self.assertEqual(("protocol",), RG.classify_path("PROTOCOL.md"))
        self.assertEqual(("protocol",), RG.classify_path(
            "docs/ietf/draft-slutsky-homing-pigeon/source/x.md"))
        self.assertEqual(("protocol",), RG.classify_path(
            "runner/wire/verify.py"))
        self.assertEqual(("protocol",), RG.classify_path(
            "runner/wire/transports.py"))

    def test_signing_paths_ask_for_protocol_and_key_handling(self):
        self.assertEqual(("protocol", "key handling"),
                         RG.classify_path("runner/wire/jobcrypto.py"))
        self.assertEqual(("protocol", "key handling"),
                         RG.classify_path("runner/wire/mlkem.py"))

    def test_execution_paths(self):
        self.assertEqual(("execution",), RG.classify_path("runner/runner.py"))
        for name in ("exec.py", "main.py", "startup.py", "poll.py",
                     "handlers.py", "cli.py"):
            self.assertEqual(("execution",),
                             RG.classify_path("runner/ops/" + name), name)

    def test_key_handling_paths(self):
        self.assertEqual(("key handling",),
                         RG.classify_path("runner/ops/install.py"))
        self.assertEqual(("key handling",),
                         RG.classify_path("runner/guard/confval.py"))
        self.assertEqual(("key handling",),
                         RG.classify_path("runner/config.example.json"))
        self.assertEqual(("key handling",),
                         RG.classify_path("runner/cloud/send_job.py"))

    def test_confinement_paths(self):
        self.assertEqual(("confinement",),
                         RG.classify_path("runner/guard/sandbox.py"))
        self.assertEqual(("confinement",),
                         RG.classify_path("runner/guard/windows_confine.py"))
        self.assertEqual(("confinement",),
                         RG.classify_path("runner/guard/freebsd_confine.py"))
        self.assertEqual(("confinement",),
                         RG.classify_path("docs/steady/security/homing_pigeon.te"))
        self.assertEqual(("confinement",), RG.classify_path(
            "docs/steady/security/homing-pigeon.service"))

    def test_every_confinement_backend_asks_for_confinement(self):
        # One backend per platform family: the Linux sandbox and
        # the Windows and FreeBSD confinement backends are the
        # same kind of module, so a change to any one of them
        # asks for the confinement review (Packet 6, P6-S10).
        for path in ("runner/guard/sandbox.py",
                     "runner/guard/windows_confine.py",
                     "runner/guard/freebsd_confine.py"):
            self.assertEqual(("confinement",),
                             RG.classify_path(path), path)

    def test_posture_asks_for_confinement_and_job_user(self):
        self.assertEqual(("confinement", "job-user behavior"),
                         RG.classify_path("runner/ops/posture.py"))

    def test_job_user_name_rule(self):
        self.assertEqual(("job-user behavior",), RG.classify_path(
            ".github/workflows/job-user.yml"))
        self.assertEqual(("job-user behavior",), RG.classify_path(
            "runner/ops/job_user_gate.py"))

    def test_extension_loading_paths(self):
        self.assertEqual(("extension loading",), RG.classify_path(
            "runner/extensions/weather/__init__.py"))
        self.assertEqual(("extension loading",), RG.classify_path(
            "runner/transport_extensions/email/__main__.py"))
        self.assertEqual(("extension loading",),
                         RG.classify_path("runner/ops/extensions.py"))
        self.assertEqual(("extension loading",),
                         RG.classify_path("runner/ops/extsources.py"))
        self.assertEqual(("extension loading",),
                         RG.classify_path("runner/guard/extreview.py"))
        self.assertEqual(("extension loading",), RG.classify_path(
            "runner/tools/pin_extension_sources.py"))

    def test_disclosure_paths(self):
        self.assertEqual(("disclosure controls",),
                         RG.classify_path("runner/oracle/review.py"))
        self.assertEqual(("disclosure controls",),
                         RG.classify_path("runner/guard/security.py"))
        self.assertEqual(("disclosure controls",),
                         RG.classify_path("runner/ops/briefing.py"))
        self.assertEqual(("disclosure controls",),
                         RG.classify_path("runner/tools/disclosure.py"))

    def test_unclassified_paths_ask_for_nothing(self):
        for path in ("README.md",
                     "docs/steady/security/agent-state-files.md",
                     "docs/infrastructure-documents/project/statistics.md",
                     "runner/tests/test_release_gate.py",
                     "runner/ops/version4.py",
                     "assets/chart.svg"):
            self.assertEqual((), RG.classify_path(path), path)


class ReleaseSubjectTest(unittest.TestCase):

    def test_release_shape(self):
        self.assertTrue(RG.is_release_subject(
            "release: 3.15.20.13 — the agent's papers fenced"))
        self.assertFalse(RG.is_release_subject("docs: release the hounds"))
        self.assertFalse(RG.is_release_subject("Release: capital is not it"))
        self.assertFalse(RG.is_release_subject(""))


class SlotChangeTest(unittest.TestCase):

    LINE_OLD = "Figure: <!--hp-fig:tokens_exact-->100<!--/hp-fig--> tokens."
    LINE_NEW = "Figure: <!--hp-fig:tokens_exact-->200<!--/hp-fig--> tokens."

    def test_mask_slots_hides_values_keeps_names(self):
        self.assertEqual(
            "Figure: <!--hp-fig:tokens_exact--><!--/hp-fig--> tokens.",
            RG.mask_slots(self.LINE_OLD))

    def test_value_only_change_is_slot_only(self):
        self.assertTrue(RG.slot_only_change([self.LINE_OLD], [self.LINE_NEW]))

    def test_edit_outside_the_slot_is_not_slot_only(self):
        edited = "Total: <!--hp-fig:tokens_exact-->100<!--/hp-fig--> tokens."
        self.assertFalse(RG.slot_only_change([self.LINE_OLD], [edited]))

    def test_new_line_is_not_slot_only(self):
        self.assertFalse(RG.slot_only_change(
            [self.LINE_OLD], [self.LINE_NEW, "A brand new sentence."]))

    def test_dropped_line_is_not_slot_only(self):
        self.assertFalse(RG.slot_only_change([self.LINE_OLD, "x"], ["x"]))

    def test_no_change_is_slot_only(self):
        self.assertTrue(RG.slot_only_change([], []))


def _candidate(content=(), touched=(), deferred=(), version="3.15.20.14",
               base=SHA_B, head=SHA, tip=None):
    return {
        "version": version, "base": base, "head": head, "tip": tip,
        "content": list(content), "machinery": [],
        "deferred": list(deferred), "classes_touched": tuple(touched),
    }


def _entry(subject, paths=(), classes=(), refresh=(), sha=SHA):
    return {"sha": sha, "subject": subject, "paths": list(paths),
            "classes": tuple(classes), "refresh": list(refresh)}


class RenderTest(unittest.TestCase):

    def test_items_in_the_designs_order(self):
        text = RG.render_checklist(_candidate(
            content=[_entry("wire: tighten the verifier",
                            paths=["runner/wire/verify.py"],
                            classes=["protocol"])],
            touched=("protocol",)))
        positions = [text.index("**Candidate identity.**"),
                     text.index("**The range at a glance.**"),
                     text.index("**Builds and publication.**"),
                     text.index("**The stamp check.**"),
                     text.index("**The fresh measure.**"),
                     text.index("**The changelog.**"),
                     text.index("**Dark landings.**"),
                     text.index("**Class reviews.**"),
                     text.index("**The state of main.**"),
                     text.index("**The sign-off.**")]
        self.assertEqual(sorted(positions), positions)

    def test_identity_and_classes_declared(self):
        text = RG.render_checklist(_candidate(touched=("protocol",)))
        self.assertIn("Version 3.15.20.14", text)
        self.assertIn(SHA, text)
        self.assertIn("- Classes touched: protocol", text)
        self.assertIn("Not touched by this range, asking nothing:", text)
        self.assertIn("- Candidate: standard", text)
        self.assertIn("- Reviewed: protocol", text)

    def test_no_classes_touched_declares_none(self):
        text = RG.render_checklist(_candidate())
        self.assertIn("- Classes touched: none", text)
        self.assertNotIn("- Reviewed:", text)

    def test_refresh_path_is_marked_not_classed(self):
        text = RG.render_checklist(_candidate(content=[_entry(
            "docs: statistics refresh",
            paths=["PROTOCOL.md"], refresh=["PROTOCOL.md"])]))
        self.assertIn("PROTOCOL.md (figure refresh)", text)

    def test_protected_form_lists_deferred_commits(self):
        text = RG.render_checklist(_candidate(
            deferred=[_entry("oracle: widen the briefing",
                             paths=["runner/oracle/review.py"],
                             classes=["disclosure controls"])],
            tip=SHA_B))
        self.assertIn("protected candidate", text)
        self.assertIn("- Candidate: protected", text)
        self.assertIn("deferred: disclosure controls", text)


class ValidateTest(unittest.TestCase):

    def test_valid_standard_record(self):
        self.assertEqual([], RG.validate_signoff(_record()))

    def test_valid_protected_record(self):
        self.assertEqual([], RG.validate_signoff(_record(
            form="protected", verdict="signed (protected candidate)")))

    def test_valid_not_signed_record(self):
        self.assertEqual([], RG.validate_signoff(_record(
            verdict="not signed")))

    def test_no_classes_touched_needs_no_reviewed_lines(self):
        self.assertEqual([], RG.validate_signoff(_record(
            touched=(), reviewed=())))

    def test_missing_field_refused(self):
        text = _record().replace("- Conductor: The conductor\n", "")
        self.assertIn("missing field: Conductor", RG.validate_signoff(text))

    def test_empty_field_refused(self):
        problems = RG.validate_signoff(_record(conductor=""))
        self.assertIn("empty field: Conductor", problems)

    def test_duplicated_field_refused(self):
        text = _record(extra="- Date: 2026-11-10")
        self.assertIn("duplicated field: Date", RG.validate_signoff(text))

    def test_unknown_field_refused(self):
        text = _record(extra="- Witness: A bystander")
        self.assertIn("unknown field: Witness", RG.validate_signoff(text))

    def test_shortened_version_refused(self):
        problems = RG.validate_signoff(_record(version="3.15.20"))
        self.assertTrue(any("four-component" in p for p in problems),
                        problems)

    def test_short_sha_refused(self):
        problems = RG.validate_signoff(_record(sha="abc123"))
        self.assertTrue(any("full SHA" in p for p in problems), problems)

    def test_bad_date_refused(self):
        problems = RG.validate_signoff(_record(date="9-Nov-2026"))
        self.assertTrue(any("ISO date" in p for p in problems), problems)

    def test_unknown_verdict_refused(self):
        problems = RG.validate_signoff(_record(verdict="approved"))
        self.assertTrue(any("known verdict" in p for p in problems), problems)

    def test_protected_candidate_with_standard_verdict_refused(self):
        problems = RG.validate_signoff(_record(form="protected"))
        self.assertTrue(any("protected" in p for p in problems), problems)

    def test_standard_candidate_with_protected_verdict_refused(self):
        problems = RG.validate_signoff(_record(
            verdict="signed (protected candidate)"))
        self.assertTrue(any("standard" in p for p in problems), problems)

    def test_touched_class_without_reviewed_line_refused(self):
        problems = RG.validate_signoff(_record(
            touched=("protocol", "execution"), reviewed=("protocol",)))
        self.assertIn("touched class with no reviewed line: execution",
                      problems)

    def test_reviewed_line_for_untouched_class_refused(self):
        problems = RG.validate_signoff(_record(
            touched=("protocol",), reviewed=("protocol", "execution")))
        self.assertIn(
            "reviewed line for a class the range did not touch: execution",
            problems)

    def test_duplicated_reviewed_line_refused(self):
        problems = RG.validate_signoff(_record(
            reviewed=("protocol", "protocol")))
        self.assertIn("duplicated reviewed line", problems)

    def test_no_classes_declaration_refused(self):
        text = _record().replace("- Classes touched: protocol\n", "")
        problems = RG.validate_signoff(text)
        self.assertTrue(any("Classes touched" in p for p in problems),
                        problems)

    def test_caller_classes_override_the_declaration(self):
        text = _record(touched=("protocol",), reviewed=("protocol",))
        problems = RG.validate_signoff(
            text, classes_touched=("protocol", "execution"))
        self.assertIn("touched class with no reviewed line: execution",
                      problems)

    def test_no_signoff_block_refused(self):
        self.assertEqual(["no sign-off block found"],
                         RG.validate_signoff("# Just a title\n"))


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", repo, "-c", "user.name=Gate Test",
         "-c", "user.email=gate-test@localhost"] + list(args),
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _write(repo, rel, text):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _commit(repo, subject):
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", subject)
    out = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                         check=True, stdout=subprocess.PIPE,
                         universal_newlines=True)
    return out.stdout.strip()


class GitRangeTest(unittest.TestCase):

    def _repo(self):
        repo = tempfile.mkdtemp(prefix="release-gate-test-")
        self.addCleanup(lambda: __import__("shutil").rmtree(
            repo, ignore_errors=True))
        _git(repo, "init", "--quiet")
        _write(repo, "README.md", "# gate test fixture\n")
        base = _commit(repo, "fixture: the base")
        return repo, base

    def test_range_classification_end_to_end(self):
        repo, base = self._repo()
        _write(repo, "runner/wire/verify.py", "# verifier v1\n")
        _commit(repo, "wire: add the verifier")
        _write(repo, "runner/ops/install.py", "# installer v2\n")
        machinery = _commit(repo, "release: 0.0.0.0 — fixture release")
        _write(repo, "PROTOCOL.md",
               "# Protocol\n\nFigure: "
               "<!--hp-fig:tokens_exact-->100<!--/hp-fig--> tokens.\n")
        _commit(repo, "docs: the protocol manual arrives")
        _write(repo, "PROTOCOL.md",
               "# Protocol\n\nFigure: "
               "<!--hp-fig:tokens_exact-->200<!--/hp-fig--> tokens.\n")
        refresh = _commit(repo, "docs: statistics refresh — fixture")
        _write(repo, "PROTOCOL.md",
               "# Protocol, revised\n\nFigure: "
               "<!--hp-fig:tokens_exact-->200<!--/hp-fig--> tokens.\n")
        head = _commit(repo, "docs: a real protocol change")

        cand = RG.build_candidate(repo, base, head, "0.0.0.1")
        # The release-shaped commit is machinery, never classified:
        # install.py inside it flags nothing.
        self.assertEqual([machinery],
                         [sha for sha, _ in cand["machinery"]])
        self.assertEqual(("protocol",), cand["classes_touched"])
        by_subject = {e["subject"]: e for e in cand["content"]}
        self.assertEqual(("protocol",),
                         by_subject["wire: add the verifier"]["classes"])
        self.assertEqual(
            ["PROTOCOL.md"],
            by_subject["docs: statistics refresh — fixture"]["refresh"])
        self.assertEqual(
            (), by_subject["docs: statistics refresh — fixture"]["classes"])
        self.assertEqual(("protocol",),
                         by_subject["docs: a real protocol change"]["classes"])
        self.assertEqual(refresh,
                         by_subject["docs: statistics refresh — fixture"]
                         ["sha"])

    def test_range_read_survives_a_non_utf8_locale(self):
        # Regression: the git front door decoded git's UTF-8 output
        # with the locale encoding, so a non-ASCII subject came back
        # mangled under a Windows codepage (and the read crashed
        # under a C locale) — the end-to-end test above errored on
        # the Windows leg of the 3.15.20.15 builds. The read now
        # pins UTF-8; this holds it under a forced C locale.
        repo, base = self._repo()
        _write(repo, "runner/wire/verify.py", "# verifier v1\n")
        head = _commit(repo, "docs: statistics refresh — fixture")
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        snippet = (
            "import sys;"
            "from runner.tools import release_gate as RG;"
            "commits = RG.range_commits(sys.argv[1], sys.argv[2],"
            " sys.argv[3]);"
            "sys.stdout.write(ascii(commits[0][1]))")
        env = dict(os.environ, LC_ALL="C", PYTHONUTF8="0",
                   PYTHONCOERCECLOCALE="0", PYTHONPATH=root)
        out = subprocess.run(
            [sys.executable, "-c", snippet, repo, base, head],
            check=True, stdout=subprocess.PIPE,
            universal_newlines=True, env=env, cwd=root)
        self.assertEqual("'docs: statistics refresh \\u2014 fixture'",
                         out.stdout)

    def test_tip_beyond_the_candidate_is_deferred(self):
        repo, base = self._repo()
        _write(repo, "runner/wire/verify.py", "# verifier v1\n")
        head = _commit(repo, "wire: add the verifier")
        _write(repo, "runner/oracle/review.py", "# review v1\n")
        tip = _commit(repo, "oracle: widen the briefing")
        cand = RG.build_candidate(repo, base, head, "0.0.0.1", tip=tip)
        self.assertEqual(("protocol",), cand["classes_touched"])
        self.assertEqual(1, len(cand["deferred"]))
        self.assertEqual(("disclosure controls",),
                         cand["deferred"][0]["classes"])
        text = RG.render_checklist(cand)
        self.assertIn("- Candidate: protected", text)
        # The generated record, signed as protected, validates.
        filled = text.replace("- Conductor:\n",
                              "- Conductor: The conductor\n")
        filled = filled.replace("- Date:\n", "- Date: 2026-11-09\n")
        filled = filled.replace(
            "- Verdict:\n", "- Verdict: signed (protected candidate)\n")
        self.assertEqual([], RG.validate_signoff(filled))


if __name__ == "__main__":
    unittest.main()
