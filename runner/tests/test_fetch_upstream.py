# Agent-Stamp: a0000997-a43e-44ba-9a26-80b8150fd8a7
"""runner/tools/fetch_upstream.py: the pinned upstream files beside an
extension, fetched, checked and bumped.

test_upstream_pins holds the manifest rules and the shipped pins. The
rest of the tool never ran: the fetch, the drift check that --check
gates on, the ref resolution behind --bump, and main. A local git
repository stands in for the upstream (no network): the real fetch
carries exactly the listed paths with their digests and replaces
upstream/ whole; every way the tree can drift from its pin is named;
a peeled tag beats the tag beats the branch; and main checks, fetches,
bumps, refuses, and holds the budget over a throwaway extensions
folder.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from runner.tools import fetch_upstream as FU  # noqa: E402

PATHS = ["etc/schema.json", "LICENSE"]
REPO = "https://github.com/example/feed"


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@example.test",
                    "-c", "user.name=t", "-c", "commit.gpgsign=false"]
                   + list(args), cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
class _Upstream(unittest.TestCase):
    """A local repository standing in for the upstream project."""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="hp-upstream-test-")
        self.addCleanup(shutil.rmtree, self.td, True)
        self.src = os.path.join(self.td, "src")
        os.makedirs(os.path.join(self.src, "etc"))
        _git(self.src, "init", "-q")
        for rel, text in (("etc/schema.json", '{"event": 1}\n'),
                          ("LICENSE", "a license\n"),
                          ("not-carried.txt", "x" * 4000)):
            with open(os.path.join(self.src, *rel.split("/")), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        _git(self.src, "add", "-A")
        _git(self.src, "commit", "-q", "-m", "one")
        _git(self.src, "config", "uploadpack.allowFilter", "true")
        _git(self.src, "config", "uploadpack.allowAnySHA1InWant", "true")
        self.sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.src,
                                  capture_output=True, text=True,
                                  check=True).stdout.strip()
        self.ext = os.path.join(self.td, "extensions", "feed")
        os.makedirs(self.ext)

    def block(self, **over):
        b = {"repo": self.src, "ref": "main", "pin": self.sha,
             "paths": list(PATHS), "license": "MIT"}
        b.update(over)
        return b

    def fetch(self, **over):
        log = []
        return FU.fetch(self.ext, self.block(**over), log=log.append), log


class FetchTest(_Upstream):
    def test_only_the_listed_paths_with_their_digests(self):
        pin, log = self.fetch()
        up = os.path.join(self.ext, FU.UPSTREAM_DIR)
        self.assertEqual(sorted(os.listdir(up)), ["LICENSE", "PIN.json", "etc"])
        self.assertEqual(sorted(pin["files"]), sorted(PATHS))
        self.assertEqual(pin["files"]["LICENSE"]["sha384"],
                         FU._sha384(os.path.join(up, "LICENSE")))
        self.assertEqual(pin["bytes"], 13 + 10)
        self.assertEqual((pin["pin"], pin["license"]), (self.sha, "MIT"))
        with open(os.path.join(up, FU.PIN_FILE), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), pin)
        self.assertEqual(log, ["  fetched 2 file(s), 23 bytes, from %s@%s"
                               % (self.src, self.sha[:12])])
        self.assertEqual(FU.current_state(self.ext, self.block()), (True, []))

    def test_the_bytes_are_upstream_s_whatever_autocrlf_says(self):
        # A Windows box with core.autocrlf on: the checkout still lands
        # the LF bytes the pin's digests were taken over.
        home = os.path.join(self.td, "home")
        os.makedirs(home)
        cfg = os.path.join(home, ".gitconfig")
        with open(cfg, "w", encoding="utf-8") as fh:
            fh.write("[core]\n\tautocrlf = true\n\teol = crlf\n")
        with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": cfg,
                                          "HOME": home}):
            pin, _log = self.fetch()
        up = os.path.join(self.ext, FU.UPSTREAM_DIR)
        with open(os.path.join(up, "LICENSE"), "rb") as fh:
            self.assertEqual(fh.read(), b"a license\n")
        self.assertEqual(pin["bytes"], 13 + 10)

    def test_a_refetch_leaves_nothing_stale(self):
        self.fetch()
        stale = os.path.join(self.ext, FU.UPSTREAM_DIR, "stale.txt")
        open(stale, "w").close()
        self.fetch(paths=["LICENSE"])
        self.assertFalse(os.path.exists(stale))
        self.assertFalse(os.path.exists(os.path.join(
            self.ext, FU.UPSTREAM_DIR, "etc")))

    def test_a_listed_path_that_is_not_a_file_upstream_is_refused(self):
        with self.assertRaises(FU.UpstreamError) as cm:
            self.fetch(paths=["etc"])
        self.assertIn("etc is not a file", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.ext,
                                                     FU.UPSTREAM_DIR)))

    def test_a_pin_that_is_not_upstream_is_a_git_error(self):
        with self.assertRaises(FU.UpstreamError) as cm:
            self.fetch(pin="0" * 40)
        self.assertIn("git -C", str(cm.exception))
        self.assertIn("failed (", str(cm.exception))


class DriftTest(_Upstream):
    def setUp(self):
        super().setUp()
        self.fetch()
        self.up = os.path.join(self.ext, FU.UPSTREAM_DIR)

    def _reasons(self, **over):
        ok, reasons = FU.current_state(self.ext, self.block(**over))
        self.assertFalse(ok)
        return reasons

    def test_no_pin_file(self):
        os.remove(os.path.join(self.up, FU.PIN_FILE))
        self.assertEqual(self._reasons(), ["no upstream/PIN.json"])

    def test_another_repo_or_pin(self):
        self.assertEqual(self._reasons(repo=REPO),
                         ["PIN.json repo differs from manifest"])
        self.assertEqual(self._reasons(pin="a" * 40),
                         ["PIN.json pin %s != manifest pin aaaaaaaaaaaa"
                          % self.sha[:12]])

    def test_a_missing_changed_or_unlisted_file(self):
        os.remove(os.path.join(self.up, "LICENSE"))
        with open(os.path.join(self.up, "etc", "schema.json"), "a",
                  encoding="utf-8") as fh:
            fh.write("edited\n")
        open(os.path.join(self.up, "etc", "extra.json"), "w").close()
        self.assertEqual(sorted(self._reasons()), [
            "digest mismatch etc/schema.json", "missing LICENSE",
            "unlisted file(s) under upstream/: etc/extra.json"])

    def test_a_path_list_that_moved(self):
        self.assertIn("PIN.json file list differs from manifest paths",
                      self._reasons(paths=["LICENSE"]))


class ResolveRefTest(unittest.TestCase):
    def _resolve(self, listing, ref="v1"):
        with mock.patch.object(FU, "_git", return_value=listing) as git:
            return FU.resolve_ref(REPO, ref), git

    def test_a_peeled_tag_beats_the_tag_beats_the_branch(self):
        rows = ("a" * 40 + "\trefs/heads/v1\n" + "b" * 40 + "\trefs/tags/v1\n"
                + "c" * 40 + "\trefs/tags/v1^{}\n")
        got, git = self._resolve(rows)
        self.assertEqual(got, "c" * 40)
        self.assertEqual(git.call_args[0][0],
                         ["ls-remote", REPO, "refs/heads/v1", "refs/tags/v1",
                          "refs/tags/v1^{}"])
        self.assertEqual(self._resolve(rows.split("\n", 2)[0] + "\n"
                                       + rows.split("\n")[1])[0], "b" * 40)
        self.assertEqual(self._resolve("a" * 40 + "\trefs/heads/v1\n")[0],
                         "a" * 40)

    def test_an_unknown_ref_is_named(self):
        with self.assertRaises(FU.UpstreamError) as cm:
            self._resolve("")
        self.assertEqual(str(cm.exception), "%s: ref 'v1' not found" % REPO)


class MainTest(_Upstream):
    def setUp(self):
        super().setUp()
        self.root = os.path.dirname(self.ext)
        self.real_fetch = FU.fetch

    def _manifest(self, folder, upstream):
        d = os.path.join(self.root, folder)
        os.makedirs(d, exist_ok=True)
        data = {"name": folder, "kind": "sense"}
        if upstream is not None:
            data["upstream"] = upstream
        path = os.path.join(d, FU.MANIFEST_FILE)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def _main(self, *argv, budget=FU.UPSTREAM_BUDGET_BYTES, resolve=None):
        out, err = io.StringIO(), io.StringIO()

        def fetch_local(ext_dir, block, log=print):
            # Fetched from the local stand-in, recorded as the GitHub
            # repo the manifest names, as a real fetch would record it.
            pin = self.real_fetch(ext_dir, dict(block, repo=self.src), log)
            pin["repo"] = block["repo"]
            with open(os.path.join(ext_dir, FU.UPSTREAM_DIR, FU.PIN_FILE),
                      "w", encoding="utf-8") as fh:
                json.dump(pin, fh)
            return pin

        patches = [mock.patch.object(FU, "fetch", fetch_local),
                   mock.patch.object(FU, "UPSTREAM_BUDGET_BYTES", budget)]
        if resolve is not None:
            patches.append(mock.patch.object(FU, "resolve_ref", resolve))
        with contextlib.ExitStack() as st:
            for p in patches:
                st.enter_context(p)
            st.enter_context(contextlib.redirect_stdout(out))
            st.enter_context(contextlib.redirect_stderr(err))
            rc = FU.main(["--extensions-dir", self.root] + list(argv))
        return rc, out.getvalue(), err.getvalue()

    def _good(self, **over):
        b = {"repo": REPO, "ref": "main", "pin": self.sha, "paths": PATHS,
             "license": "MIT"}
        b.update(over)
        return b

    def test_check_fetches_nothing_and_names_the_gap(self):
        self._manifest("feed", self._good())
        rc, out, err = self._main("--check")
        self.assertEqual(rc, 1)
        self.assertIn("PROBLEM: feed: no upstream/PIN.json", err)
        self.assertFalse(os.path.exists(os.path.join(self.ext,
                                                     FU.UPSTREAM_DIR)))
        self.assertIn("upstream total: 0 bytes of", out)

    def test_a_fetch_then_a_clean_check(self):
        self._manifest("feed", self._good())
        rc, out, _err = self._main()
        self.assertEqual(rc, 0)
        self.assertIn("feed: fetching (no upstream/PIN.json)", out)
        self.assertIn("1 extension(s) fetched", out)
        rc, out, err = self._main("--check")
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("feed: up to date at %s" % self.sha[:12], out)

    def test_bump_rewrites_the_pin_when_the_ref_moved(self):
        path = self._manifest("feed", self._good(pin="a" * 40))
        rc, out, _err = self._main("--bump",
                                   resolve=lambda repo, ref: self.sha)
        self.assertEqual(rc, 0)
        self.assertIn("feed: main moved aaaaaaaaaaaa -> %s" % self.sha[:12],
                      out)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["upstream"]["pin"], self.sha)

    def test_bump_names_a_ref_it_cannot_resolve(self):
        self._manifest("feed", self._good())

        def gone(repo, ref):
            raise FU.UpstreamError("%s: ref %r not found" % (repo, ref))
        rc, _out, err = self._main("--bump", resolve=gone)
        self.assertEqual(rc, 1)
        self.assertIn("PROBLEM: feed: %s: ref 'main' not found" % REPO, err)

    def test_the_folders_main_refuses_or_skips(self):
        self._manifest("feed", {"repo": REPO})
        self._manifest("plain", None)
        os.makedirs(os.path.join(self.root, "orphan", FU.UPSTREAM_DIR))
        self._manifest("orphan", None)
        self._manifest("other", self._good(pin="0" * 40))
        os.makedirs(os.path.join(self.root, "no-manifest"))
        rc, out, err = self._main("--only", "feed", "--only", "orphan",
                                  "--only", "plain", "--only", "no-manifest")
        self.assertEqual(rc, 1)
        self.assertIn("PROBLEM: feed/extension.json: upstream: missing ref",
                      err)
        self.assertIn("PROBLEM: orphan: upstream/ exists but the manifest "
                      "names no upstream", err)
        self.assertNotIn("other", out + err)

    def test_a_fetch_that_fails_is_a_problem(self):
        self._manifest("feed", self._good(pin="0" * 40))
        rc, _out, err = self._main()
        self.assertEqual(rc, 1)
        self.assertIn("PROBLEM: feed: git -C", err)

    def test_the_budget_holds_every_upstream_together(self):
        self._manifest("feed", self._good())
        self._main()
        rc, out, err = self._main("--check", budget=10)
        self.assertEqual(rc, 1)
        self.assertIn("upstream budget exceeded: ", err)
        self.assertIn("largest: feed=", err)

    def test_check_and_bump_are_exclusive(self):
        with self.assertRaises(SystemExit) as cm, \
                contextlib.redirect_stderr(io.StringIO()):
            FU.main(["--check", "--bump"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
