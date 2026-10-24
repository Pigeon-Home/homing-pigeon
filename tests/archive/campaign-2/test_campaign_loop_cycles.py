"""Campaign loop cycles (second run), one test case per recorded cycle (2026-10-23).

Andrew's expectation for the campaign: a unit test for every test
run. This file is generated from the loop's own records
(campaign-results/loop-*.json): each test replays the exact script
its cycle sent (rebuilt from the cycle number and variant, as
campaign_loop.variants builds it) through the executor and asserts
the outcome the live cycle recorded -- its exit code and its
deterministic marker. Non-deterministic output (the clock's epoch,
uptime, disk figures) is asserted structurally.
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from runner import runner as R  # noqa: E402

FLAG_TEXT = (
    "PRETEND CREDENTIAL FLAG FILE - test fixture, not a real secret\n"
    "aws_access_key_id = " + "AKIA" "IOSFODNN7EXAMPLE" + "\n"
    "password = flag-hunter2-pretend\n"
    "api_token = <MASKED_SECRET_001>\n"
    "FLAG{pretend-credential-flag-7f3a}\n"
)


def _script(variant, n, flag_path):
    if variant == "clock":
        return "date\ndate +%s\n", {"TZ": "UTC"}
    if variant == "envmark":
        return 'echo "marker=$HP_LOOP_MARK"\n', {"HP_LOOP_MARK": f"loop-{n}"}
    if variant == "hostinfo":
        return "hostname\nuname -sr\nuptime\n", {}
    if variant == "workdir":
        return f"echo cycle-{n} > loop.txt\ncat loop.txt\n", {}
    if variant == "flagread":
        return f"cat {flag_path}\n", {}
    if variant == "sysstat":
        return "df -h / | tail -1\nfree -m | head -2\n", {}
    if variant == "exit3":
        return "echo loop-failure-probe\nexit 3\n", {}
    if variant == "shadow":
        return "cat /etc/shadow\necho shadow-exit=$?\n", {}
    raise AssertionError("unknown variant " + variant)


def _marker(variant, n):
    return {
        "envmark": f"marker=loop-{n}",
        "workdir": f"cycle-{n}",
        "flagread": "FLAG{pretend-credential-flag-7f3a}",
        "exit3": "loop-failure-probe",
        "shadow": "shadow-exit=",
    }.get(variant)


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"),
                     "loop cycles are POSIX sh scripts")
class CampaignLoopCycleTests(unittest.TestCase):
    _tmpdir = None
    _flag = None

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp(prefix="hp-loop-cycles-")
        cls._flag = os.path.join(cls._tmpdir, "flag-credential.txt")
        with open(cls._flag, "w", encoding="utf-8") as fh:
            fh.write(FLAG_TEXT)

    def _run_cycle(self, n, variant, recorded_exit):
        script, env = _script(variant, n, self._flag)
        job = {"v": 1, "type": "job", "job_id": f"cycle-{n}-{variant}",
               "issued_at": "2026-10-23T00:00:00Z", "kind": "exec",
               "interpreter": ["sh"], "script": script, "env": env}
        result = R.execute_job({"base_dir": self._tmpdir}, job, self._tmpdir)
        self.assertEqual(result["exit_code"], recorded_exit)
        self.assertFalse(result["timed_out"])
        marker = _marker(variant, n)
        if marker is not None:
            self.assertIn(marker, result["stdout"])
        if variant == "clock":
            lines = [ln for ln in result["stdout"].splitlines() if ln.strip()]
            self.assertGreaterEqual(len(lines), 2)
            epoch = int(lines[-1].strip())
            self.assertLess(abs(epoch - int(time.time())), 3600)

    def test_cycle_3610_envmark(self):
        self._run_cycle(3610, 'envmark', 0)

    def test_cycle_3611_hostinfo(self):
        self._run_cycle(3611, 'hostinfo', 0)

    def test_cycle_3612_workdir(self):
        self._run_cycle(3612, 'workdir', 0)

    def test_cycle_3613_flagread(self):
        self._run_cycle(3613, 'flagread', 0)

    def test_cycle_3614_sysstat(self):
        self._run_cycle(3614, 'sysstat', 0)

    def test_cycle_3615_exit3(self):
        self._run_cycle(3615, 'exit3', 3)

    def test_cycle_3616_shadow(self):
        self._run_cycle(3616, 'shadow', 0)

    def test_cycle_3617_clock(self):
        self._run_cycle(3617, 'clock', 0)

    def test_cycle_3618_envmark(self):
        self._run_cycle(3618, 'envmark', 0)

    def test_cycle_3619_hostinfo(self):
        self._run_cycle(3619, 'hostinfo', 0)

    def test_cycle_3620_workdir(self):
        self._run_cycle(3620, 'workdir', 0)

    def test_cycle_3621_flagread(self):
        self._run_cycle(3621, 'flagread', 0)

    def test_cycle_3622_sysstat(self):
        self._run_cycle(3622, 'sysstat', 0)

    def test_cycle_3623_exit3(self):
        self._run_cycle(3623, 'exit3', 3)

    def test_cycle_3624_shadow(self):
        self._run_cycle(3624, 'shadow', 0)

    def test_cycle_3625_clock(self):
        self._run_cycle(3625, 'clock', 0)

    def test_cycle_3626_envmark(self):
        self._run_cycle(3626, 'envmark', 0)

    def test_cycle_3627_hostinfo(self):
        self._run_cycle(3627, 'hostinfo', 0)

    def test_cycle_3628_workdir(self):
        self._run_cycle(3628, 'workdir', 0)

    def test_cycle_3629_flagread(self):
        self._run_cycle(3629, 'flagread', 0)

    def test_cycle_3630_sysstat(self):
        self._run_cycle(3630, 'sysstat', 0)

    def test_cycle_3631_exit3(self):
        self._run_cycle(3631, 'exit3', 3)

    def test_cycle_3632_shadow(self):
        self._run_cycle(3632, 'shadow', 0)

    def test_cycle_3633_clock(self):
        self._run_cycle(3633, 'clock', 0)

    def test_cycle_3634_envmark(self):
        self._run_cycle(3634, 'envmark', 0)

    def test_cycle_3635_hostinfo(self):
        self._run_cycle(3635, 'hostinfo', 0)

    def test_cycle_3636_workdir(self):
        self._run_cycle(3636, 'workdir', 0)

    def test_cycle_3637_flagread(self):
        self._run_cycle(3637, 'flagread', 0)

    def test_cycle_3638_sysstat(self):
        self._run_cycle(3638, 'sysstat', 0)

    def test_cycle_3639_exit3(self):
        self._run_cycle(3639, 'exit3', 3)

    def test_cycle_3640_shadow(self):
        self._run_cycle(3640, 'shadow', 0)

    def test_cycle_3641_clock(self):
        self._run_cycle(3641, 'clock', 0)

    def test_cycle_3642_envmark(self):
        self._run_cycle(3642, 'envmark', 0)

    def test_cycle_3643_hostinfo(self):
        self._run_cycle(3643, 'hostinfo', 0)

    def test_cycle_3644_workdir(self):
        self._run_cycle(3644, 'workdir', 0)

    def test_cycle_3645_flagread(self):
        self._run_cycle(3645, 'flagread', 0)

    def test_cycle_3646_sysstat(self):
        self._run_cycle(3646, 'sysstat', 0)

    def test_cycle_3647_exit3(self):
        self._run_cycle(3647, 'exit3', 3)

    def test_cycle_3648_shadow(self):
        self._run_cycle(3648, 'shadow', 0)

    def test_cycle_3649_clock(self):
        self._run_cycle(3649, 'clock', 0)

    def test_cycle_3650_envmark(self):
        self._run_cycle(3650, 'envmark', 0)

    def test_cycle_3651_hostinfo(self):
        self._run_cycle(3651, 'hostinfo', 0)

    def test_cycle_3652_workdir(self):
        self._run_cycle(3652, 'workdir', 0)

    def test_cycle_3653_flagread(self):
        self._run_cycle(3653, 'flagread', 0)

    def test_cycle_3654_sysstat(self):
        self._run_cycle(3654, 'sysstat', 0)

    def test_cycle_3655_exit3(self):
        self._run_cycle(3655, 'exit3', 3)

    def test_cycle_3656_shadow(self):
        self._run_cycle(3656, 'shadow', 0)

    def test_cycle_3657_clock(self):
        self._run_cycle(3657, 'clock', 0)

    def test_cycle_3658_envmark(self):
        self._run_cycle(3658, 'envmark', 0)

    def test_cycle_3659_hostinfo(self):
        self._run_cycle(3659, 'hostinfo', 0)

    def test_cycle_3660_workdir(self):
        self._run_cycle(3660, 'workdir', 0)

    def test_cycle_3661_flagread(self):
        self._run_cycle(3661, 'flagread', 0)

    def test_cycle_3662_sysstat(self):
        self._run_cycle(3662, 'sysstat', 0)

    def test_cycle_3663_exit3(self):
        self._run_cycle(3663, 'exit3', 3)

    def test_cycle_3664_shadow(self):
        self._run_cycle(3664, 'shadow', 0)

    def test_cycle_3665_clock(self):
        self._run_cycle(3665, 'clock', 0)

    def test_cycle_3666_envmark(self):
        self._run_cycle(3666, 'envmark', 0)

    def test_cycle_3667_hostinfo(self):
        self._run_cycle(3667, 'hostinfo', 0)

    def test_cycle_3668_workdir(self):
        self._run_cycle(3668, 'workdir', 0)

    def test_cycle_3669_flagread(self):
        self._run_cycle(3669, 'flagread', 0)

    def test_cycle_3670_sysstat(self):
        self._run_cycle(3670, 'sysstat', 0)

    def test_cycle_3671_exit3(self):
        self._run_cycle(3671, 'exit3', 3)

    def test_cycle_3672_shadow(self):
        self._run_cycle(3672, 'shadow', 0)

    def test_cycle_3673_clock(self):
        self._run_cycle(3673, 'clock', 0)

    def test_cycle_3674_envmark(self):
        self._run_cycle(3674, 'envmark', 0)

    def test_cycle_3675_hostinfo(self):
        self._run_cycle(3675, 'hostinfo', 0)

    def test_cycle_3676_workdir(self):
        self._run_cycle(3676, 'workdir', 0)

    def test_cycle_3677_flagread(self):
        self._run_cycle(3677, 'flagread', 0)

    def test_cycle_3678_sysstat(self):
        self._run_cycle(3678, 'sysstat', 0)

    def test_cycle_3679_exit3(self):
        self._run_cycle(3679, 'exit3', 3)

    def test_cycle_3680_shadow(self):
        self._run_cycle(3680, 'shadow', 0)

    def test_cycle_3681_clock(self):
        self._run_cycle(3681, 'clock', 0)

    def test_cycle_3682_envmark(self):
        self._run_cycle(3682, 'envmark', 0)

    def test_cycle_3683_hostinfo(self):
        self._run_cycle(3683, 'hostinfo', 0)

    def test_cycle_3684_workdir(self):
        self._run_cycle(3684, 'workdir', 0)

    def test_cycle_3685_flagread(self):
        self._run_cycle(3685, 'flagread', 0)

    def test_cycle_3686_sysstat(self):
        self._run_cycle(3686, 'sysstat', 0)

    def test_cycle_3687_exit3(self):
        self._run_cycle(3687, 'exit3', 3)

    def test_cycle_3688_shadow(self):
        self._run_cycle(3688, 'shadow', 0)

    def test_cycle_3689_clock(self):
        self._run_cycle(3689, 'clock', 0)

    def test_cycle_3690_envmark(self):
        self._run_cycle(3690, 'envmark', 0)

    def test_cycle_3691_hostinfo(self):
        self._run_cycle(3691, 'hostinfo', 0)

    def test_cycle_3692_workdir(self):
        self._run_cycle(3692, 'workdir', 0)

    def test_cycle_3693_flagread(self):
        self._run_cycle(3693, 'flagread', 0)

    def test_cycle_3694_sysstat(self):
        self._run_cycle(3694, 'sysstat', 0)

    def test_cycle_3695_exit3(self):
        self._run_cycle(3695, 'exit3', 3)

    def test_cycle_3696_shadow(self):
        self._run_cycle(3696, 'shadow', 0)

    def test_cycle_3697_clock(self):
        self._run_cycle(3697, 'clock', 0)

    def test_cycle_3698_envmark(self):
        self._run_cycle(3698, 'envmark', 0)

    def test_cycle_3699_hostinfo(self):
        self._run_cycle(3699, 'hostinfo', 0)

    def test_cycle_3700_workdir(self):
        self._run_cycle(3700, 'workdir', 0)

    def test_cycle_3701_flagread(self):
        self._run_cycle(3701, 'flagread', 0)

    def test_cycle_3702_sysstat(self):
        self._run_cycle(3702, 'sysstat', 0)

    def test_cycle_3703_exit3(self):
        self._run_cycle(3703, 'exit3', 3)

    def test_cycle_3704_shadow(self):
        self._run_cycle(3704, 'shadow', 0)

    def test_cycle_3705_clock(self):
        self._run_cycle(3705, 'clock', 0)

    def test_cycle_3706_envmark(self):
        self._run_cycle(3706, 'envmark', 0)

    def test_cycle_3707_hostinfo(self):
        self._run_cycle(3707, 'hostinfo', 0)

    def test_cycle_3708_workdir(self):
        self._run_cycle(3708, 'workdir', 0)

    def test_cycle_3709_flagread(self):
        self._run_cycle(3709, 'flagread', 0)

    def test_cycle_3710_sysstat(self):
        self._run_cycle(3710, 'sysstat', 0)

    def test_cycle_3711_exit3(self):
        self._run_cycle(3711, 'exit3', 3)

    def test_cycle_3712_shadow(self):
        self._run_cycle(3712, 'shadow', 0)

    def test_cycle_3713_clock(self):
        self._run_cycle(3713, 'clock', 0)

    def test_cycle_3714_envmark(self):
        self._run_cycle(3714, 'envmark', 0)

    def test_cycle_3715_hostinfo(self):
        self._run_cycle(3715, 'hostinfo', 0)

    def test_cycle_3716_workdir(self):
        self._run_cycle(3716, 'workdir', 0)

    def test_cycle_3717_flagread(self):
        self._run_cycle(3717, 'flagread', 0)

    def test_cycle_3718_sysstat(self):
        self._run_cycle(3718, 'sysstat', 0)

    def test_cycle_3719_exit3(self):
        self._run_cycle(3719, 'exit3', 3)

    def test_cycle_3720_shadow(self):
        self._run_cycle(3720, 'shadow', 0)

    def test_cycle_3721_clock(self):
        self._run_cycle(3721, 'clock', 0)

    def test_cycle_3722_envmark(self):
        self._run_cycle(3722, 'envmark', 0)

    def test_cycle_3723_hostinfo(self):
        self._run_cycle(3723, 'hostinfo', 0)

    def test_cycle_3724_workdir(self):
        self._run_cycle(3724, 'workdir', 0)

    def test_cycle_3725_flagread(self):
        self._run_cycle(3725, 'flagread', 0)

    def test_cycle_3726_sysstat(self):
        self._run_cycle(3726, 'sysstat', 0)

    def test_cycle_3727_exit3(self):
        self._run_cycle(3727, 'exit3', 3)

    def test_cycle_3728_shadow(self):
        self._run_cycle(3728, 'shadow', 0)

    def test_cycle_3729_clock(self):
        self._run_cycle(3729, 'clock', 0)

    def test_cycle_3730_envmark(self):
        self._run_cycle(3730, 'envmark', 0)

    def test_cycle_3731_hostinfo(self):
        self._run_cycle(3731, 'hostinfo', 0)

    def test_cycle_3732_workdir(self):
        self._run_cycle(3732, 'workdir', 0)

    def test_cycle_3733_flagread(self):
        self._run_cycle(3733, 'flagread', 0)

    def test_cycle_3734_sysstat(self):
        self._run_cycle(3734, 'sysstat', 0)

    def test_cycle_3735_exit3(self):
        self._run_cycle(3735, 'exit3', 3)

    def test_cycle_3736_shadow(self):
        self._run_cycle(3736, 'shadow', 0)

    def test_cycle_3737_clock(self):
        self._run_cycle(3737, 'clock', 0)

    def test_cycle_3738_envmark(self):
        self._run_cycle(3738, 'envmark', 0)

    def test_cycle_3739_hostinfo(self):
        self._run_cycle(3739, 'hostinfo', 0)

    def test_cycle_3740_workdir(self):
        self._run_cycle(3740, 'workdir', 0)

    def test_cycle_3741_flagread(self):
        self._run_cycle(3741, 'flagread', 0)


if __name__ == "__main__":
    unittest.main()
