import builtins, ctypes, importlib.util, os, sys, tempfile, types, unittest
from unittest import mock
M = mock.patch.object
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from runner import posture as P  # noqa: E402
def _load(allow):
    real = builtins.__import__
    def guarded(name, g=None, loc=None, fromlist=(), level=0):
        runner = name == "runner" and fromlist and "security" in fromlist
        bare = name == "security" and not allow
        if name == "runner.security" or runner or bare: raise ImportError("no")
        return real(name, g, loc, fromlist, level)
    spec = importlib.util.spec_from_file_location("pf_%s" % allow, P.__file__)
    mod = importlib.util.module_from_spec(spec)
    with mock.patch("builtins.__import__", guarded): spec.loader.exec_module(mod)
    return mod._security
class _Api:
    def __init__(self, mode, buf, addr, st):
        self.mode, self.buf, self.addr, self.st = mode, buf, addr, st
    def GetNamedSecurityInfoW(self, path, *a):
        a[4]._obj.value = 1; return 0
    def GetAclInformation(self, dacl, info, size, kind):
        if self.mode == "fail": return 0
        info._obj.AceCount = 0 if self.mode == "empty" else 6; return 1
    def CreateWellKnownSid(self, sid, domain, raw, size):
        if sid != 1: return 0
        raw[:4] = b"SID1"; size._obj.value = 4; return 1
    def GetAce(self, dacl, index, out):
        self.st["i"] = index
        if not index: return 0
        out._obj.value = None if index == 1 else self.addr
        if index < 2: return 1
        ctypes.memset(self.buf, 0, 32)
        ctypes.c_ubyte.from_address(self.addr).value = int(index == 2)
        if index >= 4: ctypes.c_uint32.from_address(self.addr + 4).value = 0x80000000
        return 1
    def EqualSid(self, cand, known): return self.st["i"] == 5
    def LocalFree(self, ptr): return 0

class PostureGapTest(unittest.TestCase):
    def test_gaps(self):
        if os.name == "nt":
            self.skipTest("geteuid is POSIX")
        bare = types.ModuleType("security")
        with mock.patch.dict(sys.modules, {"security": bare}):
            self.assertIs(_load(True), bare)
        self.assertIsNone(_load(False))
        rows, cp = [], P._check_privileges
        kp, ph = P._check_key_policies, P._looks_like_placeholder
        with M(P.os, "geteuid", side_effect=AttributeError): cp(rows)
        uid = M(P.os, "geteuid", return_value=5)
        with uid, mock.patch.dict(sys.modules, {"pwd": None}): cp(rows)
        user = types.SimpleNamespace(pw_name="ada")
        with uid, mock.patch("pwd.getpwuid", side_effect=KeyError): cp(rows)
        with uid, mock.patch("pwd.getpwuid", return_value=user): cp(rows)
        kp(None, rows)
        extra = {"": "a", "k": "b", "z": "c"}
        kp({"additional_secrets": extra, "key_policies": {"k": {}}}, rows)
        b = {"runner.install": None, "install": None}
        with mock.patch.dict(sys.modules, b): self.assertFalse(ph("x"))
        inst = types.ModuleType("install"); inst._looks_like_placeholder = lambda v: 1
        with mock.patch.dict(sys.modules, {"runner.install": None, "install": inst}):
            self.assertTrue(ph("ph"))
        bad = types.ModuleType("runner.install")
        bad._looks_like_placeholder = mock.Mock(side_effect=ValueError("x"))
        with mock.patch.dict(sys.modules, {"runner.install": bad}):
            self.assertFalse(P._looks_like_placeholder("x"))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.json"); open(path, "wb").close()
            ex = mock.patch.object(P.os.path, "exists", return_value=False)
            home = mock.patch.object(P.os.path, "expanduser", return_value="/no/unit")
            with ex, home:
                self.assertIn("not an object", P.build_posture([], path, d)[-1][2])
                cfg = {"shared_secret": "n"*40, "workspace_root": d, "security": "off",
                       "key_policies": {"k": {"a": 1}},
                       "additional_secrets": {"": "x", "k": "y", "z": "changeme"}}
                with M(P, "_security", None), M(P.os, "access", return_value=False):
                    res = P.build_posture(cfg, path, d)
        text = "\n".join(m for _, _, m in res)
        self.assertIn("cannot evaluate", text); self.assertIn("not writable", text)
        codes = [P.exit_code_for([(lv, "s", "m")]) for lv in ("OK", "WARN", "FAIL")]
        self.assertEqual(codes, [0, 1, 2])
        self.assertTrue(P.format_posture(res).startswith("Security posture"))
        buf = ctypes.create_string_buffer(32); st = {"i": -1}
        def run(mode):
            api = _Api(mode, buf, ctypes.addressof(buf), st)
            with mock.patch.object(ctypes, "WinDLL", lambda *a, **k: api, create=True):
                return P._windows_file_restricted("secret.txt")
        self.assertEqual((run("fail"), run("empty"), run("aces")), (None, True, False))
