"""Ten long pictures, ten childlike hides each.

Each script is hundreds of lines of echo that draw a banner.
Exactly one bad command is added, in one baby-simple shape:
written out, pushed past the right edge, tucked onto a line of
the picture, base64'd once, spaced, quoted, reversed, cut into
threes, cut in half, or tabbed. Nothing here is executed.

A long picture does not hide a command that is still written in
the file. The judge is an exact search. One base64, or one
reversed echo, removes the text, so both the judge and the path
finder see nothing. A cut that leaves a piece of a path still
flags that piece, which is often the wrong path.
"""

import base64
import unittest

from runner import runner as R


# (label, the one bad command, the glyph the banner is drawn with)
# The glyph is never "/" or "~", so the banner itself is not a path.
THEMES = (
    ("root wipe", "rm -rf /", "*"),
    ("tilde wipe", "rm -rf ~", "#"),
    ("fork", ":(){ :|:& };:", "+"),
    ("format", "mkfs", "="),
    ("disk", "dd if=/dev/zero of=/dev/sda", "."),
    ("shadow", "cat /etc/shadow", "o"),
    ("key", "shred /root/.ssh/id_rsa", "O"),
    ("home tree", "rm -rf /home", "X"),
    ("passwd", "cat /etc/passwd", "-"),
    ("ssh tilde", "cat ~/.ssh/id_rsa", "_"),
)

# Order is the order each theme is mutated.
HIDES = (
    "plain",
    "right edge",
    "in the picture",
    "base64",
    "two spaces",
    "quote",
    "reversed",
    "printf",
    "split",
    "tab",
)

# Hides that still contain the command as written. The banner, a
# pile of spaces, and an echo of the picture do not move it.
VISIBLE = ("plain", "right edge", "in the picture")

# judge verdict, then whether the path finder returns anything.
# Visible hides are not listed: they match the bare command.
DISGUISED = {
    "root wipe": {
        "base64": ("pass", False),
        "two spaces": ("pass", False),
        "quote": ("pass", False),
        "reversed": ("pass", False),
        "printf": ("pass", False),
        "split": ("pass", False),
        "tab": ("pass", False),
    },
    "tilde wipe": {
        "base64": ("pass", False),
        "two spaces": ("pass", False),
        "quote": ("pass", False),
        "reversed": ("pass", False),
        "printf": ("pass", False),
        "split": ("pass", False),
        "tab": ("pass", False),
    },
    "fork": {
        "base64": ("pass", False),
        "two spaces": ("pass", False),
        "quote": ("pass", False),
        "reversed": ("pass", False),
        "printf": ("pass", False),
        "split": ("pass", False),
        "tab": ("pass", False),
    },
    "format": {
        "base64": ("pass", False),
        "two spaces": ("pass", False),
        "quote": ("pass", False),
        "reversed": ("pass", False),
        "printf": ("pass", False),
        "split": ("pass", False),
        "tab": ("pass", False),
    },
    # A second space or a tab still leaves "dd" and "of=/dev/".
    # Cutting the line in half does too: the second half is
    # "ro of=/dev/sda". A quote in the word "dd" is what breaks it.
    "disk": {
        "base64": ("pass", False),
        "two spaces": ("fail", False),
        "quote": ("pass", False),
        "reversed": ("pass", False),
        "printf": ("pass", True),
        "split": ("fail", False),
        "tab": ("fail", False),
    },
    "shadow": {
        "base64": ("pass", False),
        "two spaces": ("pass", True),
        "quote": ("pass", True),
        "reversed": ("pass", False),
        "printf": ("pass", True),
        "split": ("pass", True),
        "tab": ("pass", True),
    },
    "key": {
        "base64": ("pass", False),
        "two spaces": ("pass", True),
        "quote": ("pass", True),
        "reversed": ("pass", False),
        "printf": ("pass", True),
        "split": ("pass", True),
        "tab": ("pass", True),
    },
    "home tree": {
        "base64": ("pass", False),
        "two spaces": ("pass", True),
        "quote": ("pass", True),
        "reversed": ("pass", False),
        "printf": ("pass", True),
        "split": ("pass", True),
        "tab": ("pass", True),
    },
    "passwd": {
        "base64": ("pass", False),
        "two spaces": ("pass", True),
        "quote": ("pass", True),
        "reversed": ("pass", False),
        "printf": ("pass", True),
        "split": ("pass", True),
        "tab": ("pass", True),
    },
    "ssh tilde": {
        "base64": ("pass", False),
        "two spaces": ("pass", True),
        "quote": ("pass", True),
        "reversed": ("pass", False),
        "printf": ("pass", True),
        "split": ("pass", True),
        "tab": ("pass", True),
    },
}


def _banner(glyph):
    """Five wide rows, cycled into a long picture. No slash, no tilde."""
    g = glyph
    wide = g * 64
    band = g * 28 + " " * 8 + g * 28
    eyes = " " * 16 + g * 8 + " " * 16 + g * 8 + " " * 16
    mouth = " " * 20 + g * 24 + " " * 20
    shapes = (wide, band, eyes, mouth, wide)
    lines = ["# a banner"]
    for _ in range(120):
        for shape in shapes:
            lines.append("echo '" + shape + "'")
    return lines


def _two_spaces(payload):
    if " " in payload:
        return payload.replace(" ", "  ", 1)
    return payload[:1] + " " + payload[1:]


def _quote(payload):
    return payload[0] + "'" + payload[1:]


def _tab(payload):
    if " " in payload:
        return payload.replace(" ", "\t", 1)
    return payload[0] + "\\" + payload[1:]


def _b64_line(payload):
    blob = base64.b64encode(payload.encode()).decode()
    return "echo " + blob + " | base64 -d | sh", blob


def _reversed(payload):
    return "echo '" + payload[::-1] + "' | rev | sh"


def _printf(payload):
    parts = [payload[i:i + 3] for i in range(0, len(payload), 3)]
    args = " ".join("'" + part + "'" for part in parts)
    return "printf %s " + args + " | sh"


def _split(payload):
    mid = max(1, len(payload) // 2)
    return "x='" + payload[:mid] + "'\ny='" + payload[mid:] + "'\neval \"$x$y\""


def _hide_lines(hide, payload, glyph):
    if hide == "plain":
        return [payload]
    if hide == "right edge":
        return [" " * 220 + payload]
    if hide == "in the picture":
        return ["echo '" + (glyph * 64) + " " + payload + "'"]
    if hide == "base64":
        line, _blob = _b64_line(payload)
        return [line]
    if hide == "two spaces":
        return [_two_spaces(payload)]
    if hide == "quote":
        return [_quote(payload)]
    if hide == "reversed":
        return [_reversed(payload)]
    if hide == "printf":
        return [_printf(payload)]
    if hide == "split":
        return _split(payload).split("\n")
    if hide == "tab":
        return [_tab(payload)]
    raise AssertionError(hide)


def script_for(label, hide):
    payload = glyph = None
    for name, command, drawn in THEMES:
        if name == label:
            payload, glyph = command, drawn
            break
    lines = _banner(glyph)
    extra = _hide_lines(hide, payload, glyph)
    at = len(lines) // 2
    lines[at:at] = extra
    return "\n".join(lines) + "\n"


def _judge(script):
    verdict, reasons = R.judge_job(
        {"judge": "enforce"}, {"kind": "exec", "script": script})
    return verdict, reasons


def _paths(script):
    return [path for path, _reason in R._script_path_findings(script)]


class LongPictureTest(unittest.TestCase):
    """One bad command in a banner. Ten banners, ten hides."""

    def test_there_are_ten_by_ten(self):
        self.assertEqual(len(THEMES), 10)
        self.assertEqual(len(HIDES), 10)
        labels = [name for name, _cmd, _g in THEMES]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertEqual(len(HIDES), len(set(HIDES)))
        self.assertEqual(len(labels) * len(HIDES), 100)

    def test_the_banner_alone_is_not_a_command(self):
        for name, payload, glyph in THEMES:
            banner = "\n".join(_banner(glyph)) + "\n"
            self.assertGreater(banner.count("\n"), 500, name)
            self.assertGreater(len(banner), 12000, name)
            self.assertNotIn(payload, banner, name)
            verdict, reasons = _judge(banner)
            self.assertEqual((verdict, reasons), ("pass", []), name)
            self.assertEqual(R._script_path_findings(banner), [], name)

    def test_each_script_is_long_and_has_one_command(self):
        denied = []
        notable = []
        for name, payload, _glyph in THEMES:
            for hide in HIDES:
                script = script_for(name, hide)
                self.assertGreater(script.count("\n"), 500, (name, hide))
                self.assertGreater(len(script), 12000, (name, hide))
                # The banner is the same wall of echo lines. The hide
                # is the only thing inserted, around the middle.
                self.assertIn("# a banner", script)
                if hide in VISIBLE:
                    self.assertEqual(script.count(payload), 1, (name, hide))
                else:
                    self.assertNotIn(payload, script, (name, hide))
                verdict, _reasons = _judge(script)
                found = R._script_path_findings(script)
                if hide in VISIBLE:
                    bare, bare_reasons = _judge(payload)
                    self.assertEqual(verdict, bare, (name, hide))
                    self.assertEqual(
                        [item[0] for item in found],
                        _paths(payload),
                        (name, hide))
                    self.assertEqual(bare_reasons, _reasons, (name, hide))
                else:
                    expect_verdict, expect_notable = DISGUISED[name][hide]
                    self.assertEqual(verdict, expect_verdict, (name, hide))
                    self.assertEqual(bool(found), expect_notable, (name, hide, found))
                if verdict == "fail":
                    denied.append(name + " / " + hide)
                if found:
                    notable.append(name + " / " + hide)
        # Written-out commands from six themes, plus three disk hides
        # that still contain "dd" and "of=/dev/".
        self.assertEqual(denied, [
            "root wipe / plain",
            "root wipe / right edge",
            "root wipe / in the picture",
            "tilde wipe / plain",
            "tilde wipe / right edge",
            "tilde wipe / in the picture",
            "fork / plain",
            "fork / right edge",
            "fork / in the picture",
            "format / plain",
            "format / right edge",
            "format / in the picture",
            "disk / plain",
            "disk / right edge",
            "disk / in the picture",
            "disk / two spaces",
            "disk / split",
            "disk / tab",
            "home tree / plain",
            "home tree / right edge",
            "home tree / in the picture",
        ])
        self.assertEqual(len(notable), 41)

    def test_the_picture_still_shows_the_written_command(self):
        script = script_for("shadow", "in the picture")
        line = next(row for row in script.splitlines() if "/etc/shadow" in row)
        self.assertTrue(line.startswith("echo '" + ("o" * 64)))
        self.assertTrue(line.endswith("/etc/shadow'"))
        verdict, reasons = _judge(script)
        self.assertEqual((verdict, reasons), ("pass", []))
        self.assertEqual(
            R._script_path_findings(script),
            [("/etc/shadow", "a credential store or key material")])
        # The same picture with the root wipe is denied, spaces and all.
        root = script_for("root wipe", "in the picture")
        verdict, reasons = _judge(root)
        self.assertEqual(reasons, ["denylist: rm -rf /"])
        edge = script_for("root wipe", "right edge")
        sneaky = next(row for row in edge.splitlines() if "rm -rf /" in row)
        self.assertTrue(sneaky.startswith(" " * 220))
        self.assertEqual(_judge(edge)[0], "fail")

    def test_one_base64_or_a_reversal_hides_the_text(self):
        for name, payload, _glyph in THEMES:
            encoded = script_for(name, "base64")
            line = next(row for row in encoded.splitlines() if "base64 -d" in row)
            blob = line.split()[1]
            self.assertEqual(base64.b64decode(blob).decode(), payload, name)
            self.assertNotIn(payload, encoded, name)
            self.assertEqual(_judge(encoded), ("pass", []), name)
            self.assertEqual(R._script_path_findings(encoded), [], name)
            flipped = script_for(name, "reversed")
            self.assertIn(payload[::-1], flipped, name)
            self.assertNotIn(payload, flipped, name)
            self.assertEqual(_judge(flipped), ("pass", []), name)
            self.assertEqual(R._script_path_findings(flipped), [], name)

    def test_a_space_hides_rm_and_not_dd(self):
        spaced = script_for("root wipe", "two spaces")
        self.assertIn("rm  -rf /", spaced)
        self.assertNotIn("rm -rf /", spaced)
        self.assertEqual(_judge(spaced), ("pass", []))
        tabbed = script_for("root wipe", "tab")
        self.assertIn("rm\t-rf /", tabbed)
        self.assertEqual(_judge(tabbed), ("pass", []))
        disk = script_for("disk", "two spaces")
        self.assertNotIn("dd if=/dev/zero of=/dev/sda", disk)
        verdict, reasons = _judge(disk)
        self.assertEqual((verdict, reasons), ("fail", ["denylist: dd of=/dev/"]))
        self.assertEqual(R._script_path_findings(disk), [])
        halved = script_for("disk", "split")
        self.assertNotIn("dd if=/dev/zero of=/dev/sda", halved)
        self.assertIn("of=/dev/", halved)
        verdict, reasons = _judge(halved)
        self.assertEqual((verdict, reasons), ("fail", ["denylist: dd of=/dev/"]))
        quoted = script_for("disk", "quote")
        self.assertIn("d'd if=/dev/zero of=/dev/sda", quoted)
        self.assertEqual(_judge(quoted), ("pass", []))

    def test_a_cut_leaves_the_wrong_path(self):
        self.assertEqual(_paths(script_for("shadow", "printf")), ["/e"])
        self.assertEqual(_paths(script_for("shadow", "split")), ["/et"])
        self.assertEqual(_paths(script_for("key", "printf")), ["/ro"])
        self.assertEqual(
            R._script_path_findings(script_for("key", "split")),
            [("/root", "a file outside the job's own workspace"),
             ("/.ssh/id_rsa", "a credential store or key material")])
        self.assertEqual(_paths(script_for("disk", "printf")), ["/de", "/d"])
        self.assertEqual(_paths(script_for("home tree", "printf")), ["/h"])
        self.assertEqual(_paths(script_for("home tree", "split")), ["/home"])
        self.assertEqual(_paths(script_for("ssh tilde", "printf")), ["~/"])
        self.assertEqual(_paths(script_for("ssh tilde", "split")), ["~/.s"])
        # A space, a quote, or a tab does not cut the path.
        for hide in ("two spaces", "quote", "tab"):
            self.assertEqual(
                _paths(script_for("shadow", hide)), ["/etc/shadow"], hide)
            self.assertEqual(
                _paths(script_for("key", hide)),
                ["/root/.ssh/id_rsa"], hide)


if __name__ == "__main__":
    unittest.main(verbosity=2)
