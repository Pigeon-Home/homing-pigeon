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

    def test_cycle_3742_sysstat(self):
        self._run_cycle(3742, 'sysstat', 0)

    def test_cycle_3743_exit3(self):
        self._run_cycle(3743, 'exit3', 3)

    def test_cycle_3744_shadow(self):
        self._run_cycle(3744, 'shadow', 0)

    def test_cycle_3745_clock(self):
        self._run_cycle(3745, 'clock', 0)

    def test_cycle_3746_envmark(self):
        self._run_cycle(3746, 'envmark', 0)

    def test_cycle_3747_hostinfo(self):
        self._run_cycle(3747, 'hostinfo', 0)

    def test_cycle_3748_workdir(self):
        self._run_cycle(3748, 'workdir', 0)

    def test_cycle_3749_flagread(self):
        self._run_cycle(3749, 'flagread', 0)

    def test_cycle_3750_sysstat(self):
        self._run_cycle(3750, 'sysstat', 0)

    def test_cycle_3751_exit3(self):
        self._run_cycle(3751, 'exit3', 3)

    def test_cycle_3752_shadow(self):
        self._run_cycle(3752, 'shadow', 0)

    def test_cycle_3753_clock(self):
        self._run_cycle(3753, 'clock', 0)

    def test_cycle_3754_envmark(self):
        self._run_cycle(3754, 'envmark', 0)

    def test_cycle_3755_hostinfo(self):
        self._run_cycle(3755, 'hostinfo', 0)

    def test_cycle_3756_workdir(self):
        self._run_cycle(3756, 'workdir', 0)

    def test_cycle_3757_flagread(self):
        self._run_cycle(3757, 'flagread', 0)

    def test_cycle_3758_sysstat(self):
        self._run_cycle(3758, 'sysstat', 0)

    def test_cycle_3759_exit3(self):
        self._run_cycle(3759, 'exit3', 3)

    def test_cycle_3760_shadow(self):
        self._run_cycle(3760, 'shadow', 0)

    def test_cycle_3761_clock(self):
        self._run_cycle(3761, 'clock', 0)

    def test_cycle_3762_envmark(self):
        self._run_cycle(3762, 'envmark', 0)

    def test_cycle_3763_hostinfo(self):
        self._run_cycle(3763, 'hostinfo', 0)

    def test_cycle_3764_workdir(self):
        self._run_cycle(3764, 'workdir', 0)

    def test_cycle_3765_flagread(self):
        self._run_cycle(3765, 'flagread', 0)

    def test_cycle_3766_sysstat(self):
        self._run_cycle(3766, 'sysstat', 0)

    def test_cycle_3767_exit3(self):
        self._run_cycle(3767, 'exit3', 3)

    def test_cycle_3768_shadow(self):
        self._run_cycle(3768, 'shadow', 0)

    def test_cycle_3769_clock(self):
        self._run_cycle(3769, 'clock', 0)

    def test_cycle_3770_envmark(self):
        self._run_cycle(3770, 'envmark', 0)

    def test_cycle_3771_hostinfo(self):
        self._run_cycle(3771, 'hostinfo', 0)

    def test_cycle_3772_workdir(self):
        self._run_cycle(3772, 'workdir', 0)

    def test_cycle_3773_flagread(self):
        self._run_cycle(3773, 'flagread', 0)

    def test_cycle_3774_sysstat(self):
        self._run_cycle(3774, 'sysstat', 0)

    def test_cycle_3775_exit3(self):
        self._run_cycle(3775, 'exit3', 3)

    def test_cycle_3776_shadow(self):
        self._run_cycle(3776, 'shadow', 0)

    def test_cycle_3777_clock(self):
        self._run_cycle(3777, 'clock', 0)

    def test_cycle_3778_envmark(self):
        self._run_cycle(3778, 'envmark', 0)

    def test_cycle_3779_hostinfo(self):
        self._run_cycle(3779, 'hostinfo', 0)

    def test_cycle_3780_workdir(self):
        self._run_cycle(3780, 'workdir', 0)

    def test_cycle_3781_flagread(self):
        self._run_cycle(3781, 'flagread', 0)

    def test_cycle_3782_sysstat(self):
        self._run_cycle(3782, 'sysstat', 0)

    def test_cycle_3783_exit3(self):
        self._run_cycle(3783, 'exit3', 3)

    def test_cycle_3784_shadow(self):
        self._run_cycle(3784, 'shadow', 0)

    def test_cycle_3785_clock(self):
        self._run_cycle(3785, 'clock', 0)

    def test_cycle_3786_envmark(self):
        self._run_cycle(3786, 'envmark', 0)

    def test_cycle_3787_hostinfo(self):
        self._run_cycle(3787, 'hostinfo', 0)

    def test_cycle_3788_workdir(self):
        self._run_cycle(3788, 'workdir', 0)

    def test_cycle_3789_flagread(self):
        self._run_cycle(3789, 'flagread', 0)

    def test_cycle_3790_sysstat(self):
        self._run_cycle(3790, 'sysstat', 0)

    def test_cycle_3791_exit3(self):
        self._run_cycle(3791, 'exit3', 3)

    def test_cycle_3792_shadow(self):
        self._run_cycle(3792, 'shadow', 0)

    def test_cycle_3793_clock(self):
        self._run_cycle(3793, 'clock', 0)

    def test_cycle_3794_envmark(self):
        self._run_cycle(3794, 'envmark', 0)

    def test_cycle_3795_hostinfo(self):
        self._run_cycle(3795, 'hostinfo', 0)

    def test_cycle_3796_workdir(self):
        self._run_cycle(3796, 'workdir', 0)

    def test_cycle_3797_flagread(self):
        self._run_cycle(3797, 'flagread', 0)

    def test_cycle_3798_sysstat(self):
        self._run_cycle(3798, 'sysstat', 0)

    def test_cycle_3799_exit3(self):
        self._run_cycle(3799, 'exit3', 3)

    def test_cycle_3800_shadow(self):
        self._run_cycle(3800, 'shadow', 0)

    def test_cycle_3801_clock(self):
        self._run_cycle(3801, 'clock', 0)

    def test_cycle_3802_envmark(self):
        self._run_cycle(3802, 'envmark', 0)

    def test_cycle_3803_hostinfo(self):
        self._run_cycle(3803, 'hostinfo', 0)

    def test_cycle_3804_workdir(self):
        self._run_cycle(3804, 'workdir', 0)

    def test_cycle_3805_flagread(self):
        self._run_cycle(3805, 'flagread', 0)

    def test_cycle_3806_sysstat(self):
        self._run_cycle(3806, 'sysstat', 0)

    def test_cycle_3807_exit3(self):
        self._run_cycle(3807, 'exit3', 3)

    def test_cycle_3808_shadow(self):
        self._run_cycle(3808, 'shadow', 0)

    def test_cycle_3809_clock(self):
        self._run_cycle(3809, 'clock', 0)

    def test_cycle_3810_envmark(self):
        self._run_cycle(3810, 'envmark', 0)

    def test_cycle_3811_hostinfo(self):
        self._run_cycle(3811, 'hostinfo', 0)

    def test_cycle_3812_workdir(self):
        self._run_cycle(3812, 'workdir', 0)

    def test_cycle_3813_flagread(self):
        self._run_cycle(3813, 'flagread', 0)

    def test_cycle_3814_sysstat(self):
        self._run_cycle(3814, 'sysstat', 0)

    def test_cycle_3815_exit3(self):
        self._run_cycle(3815, 'exit3', 3)

    def test_cycle_3816_shadow(self):
        self._run_cycle(3816, 'shadow', 0)

    def test_cycle_3817_clock(self):
        self._run_cycle(3817, 'clock', 0)

    def test_cycle_3818_envmark(self):
        self._run_cycle(3818, 'envmark', 0)

    def test_cycle_3819_hostinfo(self):
        self._run_cycle(3819, 'hostinfo', 0)

    def test_cycle_3820_workdir(self):
        self._run_cycle(3820, 'workdir', 0)

    def test_cycle_3821_flagread(self):
        self._run_cycle(3821, 'flagread', 0)

    def test_cycle_3822_sysstat(self):
        self._run_cycle(3822, 'sysstat', 0)

    def test_cycle_3823_exit3(self):
        self._run_cycle(3823, 'exit3', 3)

    def test_cycle_3824_shadow(self):
        self._run_cycle(3824, 'shadow', 0)

    def test_cycle_3825_clock(self):
        self._run_cycle(3825, 'clock', 0)

    def test_cycle_3826_envmark(self):
        self._run_cycle(3826, 'envmark', 0)

    def test_cycle_3827_hostinfo(self):
        self._run_cycle(3827, 'hostinfo', 0)

    def test_cycle_3828_workdir(self):
        self._run_cycle(3828, 'workdir', 0)

    def test_cycle_3829_flagread(self):
        self._run_cycle(3829, 'flagread', 0)

    def test_cycle_3830_sysstat(self):
        self._run_cycle(3830, 'sysstat', 0)

    def test_cycle_3831_exit3(self):
        self._run_cycle(3831, 'exit3', 3)

    def test_cycle_3832_shadow(self):
        self._run_cycle(3832, 'shadow', 0)

    def test_cycle_3833_clock(self):
        self._run_cycle(3833, 'clock', 0)

    def test_cycle_3834_envmark(self):
        self._run_cycle(3834, 'envmark', 0)

    def test_cycle_3835_hostinfo(self):
        self._run_cycle(3835, 'hostinfo', 0)

    def test_cycle_3836_workdir(self):
        self._run_cycle(3836, 'workdir', 0)

    def test_cycle_3837_flagread(self):
        self._run_cycle(3837, 'flagread', 0)

    def test_cycle_3838_sysstat(self):
        self._run_cycle(3838, 'sysstat', 0)

    def test_cycle_3839_exit3(self):
        self._run_cycle(3839, 'exit3', 3)

    def test_cycle_3840_shadow(self):
        self._run_cycle(3840, 'shadow', 0)

    def test_cycle_3841_clock(self):
        self._run_cycle(3841, 'clock', 0)

    def test_cycle_3842_envmark(self):
        self._run_cycle(3842, 'envmark', 0)

    def test_cycle_3843_hostinfo(self):
        self._run_cycle(3843, 'hostinfo', 0)

    def test_cycle_3844_workdir(self):
        self._run_cycle(3844, 'workdir', 0)

    def test_cycle_3845_flagread(self):
        self._run_cycle(3845, 'flagread', 0)

    def test_cycle_3846_sysstat(self):
        self._run_cycle(3846, 'sysstat', 0)

    def test_cycle_3847_exit3(self):
        self._run_cycle(3847, 'exit3', 3)

    def test_cycle_3848_shadow(self):
        self._run_cycle(3848, 'shadow', 0)

    def test_cycle_3849_clock(self):
        self._run_cycle(3849, 'clock', 0)

    def test_cycle_3850_envmark(self):
        self._run_cycle(3850, 'envmark', 0)

    def test_cycle_3851_hostinfo(self):
        self._run_cycle(3851, 'hostinfo', 0)

    def test_cycle_3852_workdir(self):
        self._run_cycle(3852, 'workdir', 0)

    def test_cycle_3853_flagread(self):
        self._run_cycle(3853, 'flagread', 0)

    def test_cycle_3854_sysstat(self):
        self._run_cycle(3854, 'sysstat', 0)

    def test_cycle_3855_exit3(self):
        self._run_cycle(3855, 'exit3', 3)

    def test_cycle_3856_shadow(self):
        self._run_cycle(3856, 'shadow', 0)

    def test_cycle_3857_clock(self):
        self._run_cycle(3857, 'clock', 0)

    def test_cycle_3858_envmark(self):
        self._run_cycle(3858, 'envmark', 0)

    def test_cycle_3859_hostinfo(self):
        self._run_cycle(3859, 'hostinfo', 0)

    def test_cycle_3860_workdir(self):
        self._run_cycle(3860, 'workdir', 0)

    def test_cycle_3861_flagread(self):
        self._run_cycle(3861, 'flagread', 0)

    def test_cycle_3862_sysstat(self):
        self._run_cycle(3862, 'sysstat', 0)

    def test_cycle_3863_exit3(self):
        self._run_cycle(3863, 'exit3', 3)

    def test_cycle_3864_shadow(self):
        self._run_cycle(3864, 'shadow', 0)

    def test_cycle_3865_clock(self):
        self._run_cycle(3865, 'clock', 0)

    def test_cycle_3866_envmark(self):
        self._run_cycle(3866, 'envmark', 0)

    def test_cycle_3867_hostinfo(self):
        self._run_cycle(3867, 'hostinfo', 0)

    def test_cycle_3868_workdir(self):
        self._run_cycle(3868, 'workdir', 0)

    def test_cycle_3869_flagread(self):
        self._run_cycle(3869, 'flagread', 0)

    def test_cycle_3870_sysstat(self):
        self._run_cycle(3870, 'sysstat', 0)

    def test_cycle_3871_exit3(self):
        self._run_cycle(3871, 'exit3', 3)

    def test_cycle_3872_shadow(self):
        self._run_cycle(3872, 'shadow', 0)

    def test_cycle_3873_clock(self):
        self._run_cycle(3873, 'clock', 0)

    def test_cycle_3874_envmark(self):
        self._run_cycle(3874, 'envmark', 0)

    def test_cycle_3875_hostinfo(self):
        self._run_cycle(3875, 'hostinfo', 0)

    def test_cycle_3876_workdir(self):
        self._run_cycle(3876, 'workdir', 0)

    def test_cycle_3877_flagread(self):
        self._run_cycle(3877, 'flagread', 0)

    def test_cycle_3878_sysstat(self):
        self._run_cycle(3878, 'sysstat', 0)

    def test_cycle_3879_exit3(self):
        self._run_cycle(3879, 'exit3', 3)

    def test_cycle_3880_shadow(self):
        self._run_cycle(3880, 'shadow', 0)

    def test_cycle_3881_clock(self):
        self._run_cycle(3881, 'clock', 0)

    def test_cycle_3882_envmark(self):
        self._run_cycle(3882, 'envmark', 0)

    def test_cycle_3883_hostinfo(self):
        self._run_cycle(3883, 'hostinfo', 0)

    def test_cycle_3884_workdir(self):
        self._run_cycle(3884, 'workdir', 0)

    def test_cycle_3885_flagread(self):
        self._run_cycle(3885, 'flagread', 0)

    def test_cycle_3886_sysstat(self):
        self._run_cycle(3886, 'sysstat', 0)

    def test_cycle_3887_exit3(self):
        self._run_cycle(3887, 'exit3', 3)

    def test_cycle_3888_shadow(self):
        self._run_cycle(3888, 'shadow', 0)

    def test_cycle_3889_clock(self):
        self._run_cycle(3889, 'clock', 0)

    def test_cycle_3890_envmark(self):
        self._run_cycle(3890, 'envmark', 0)

    def test_cycle_3891_hostinfo(self):
        self._run_cycle(3891, 'hostinfo', 0)

    def test_cycle_3892_workdir(self):
        self._run_cycle(3892, 'workdir', 0)

    def test_cycle_3893_flagread(self):
        self._run_cycle(3893, 'flagread', 0)

    def test_cycle_3894_sysstat(self):
        self._run_cycle(3894, 'sysstat', 0)

    def test_cycle_3895_exit3(self):
        self._run_cycle(3895, 'exit3', 3)

    def test_cycle_3896_shadow(self):
        self._run_cycle(3896, 'shadow', 0)

    def test_cycle_3897_clock(self):
        self._run_cycle(3897, 'clock', 0)

    def test_cycle_3898_envmark(self):
        self._run_cycle(3898, 'envmark', 0)

    def test_cycle_3899_hostinfo(self):
        self._run_cycle(3899, 'hostinfo', 0)

    def test_cycle_3900_workdir(self):
        self._run_cycle(3900, 'workdir', 0)

    def test_cycle_3901_flagread(self):
        self._run_cycle(3901, 'flagread', 0)

    def test_cycle_3902_sysstat(self):
        self._run_cycle(3902, 'sysstat', 0)

    def test_cycle_3903_exit3(self):
        self._run_cycle(3903, 'exit3', 3)

    def test_cycle_3904_shadow(self):
        self._run_cycle(3904, 'shadow', 0)

    def test_cycle_3905_clock(self):
        self._run_cycle(3905, 'clock', 0)

    def test_cycle_3906_envmark(self):
        self._run_cycle(3906, 'envmark', 0)

    def test_cycle_3907_hostinfo(self):
        self._run_cycle(3907, 'hostinfo', 0)

    def test_cycle_3908_workdir(self):
        self._run_cycle(3908, 'workdir', 0)

    def test_cycle_3909_flagread(self):
        self._run_cycle(3909, 'flagread', 0)

    def test_cycle_3910_sysstat(self):
        self._run_cycle(3910, 'sysstat', 0)

    def test_cycle_3911_exit3(self):
        self._run_cycle(3911, 'exit3', 3)

    def test_cycle_3912_shadow(self):
        self._run_cycle(3912, 'shadow', 0)

    def test_cycle_3913_clock(self):
        self._run_cycle(3913, 'clock', 0)

    def test_cycle_3914_envmark(self):
        self._run_cycle(3914, 'envmark', 0)

    def test_cycle_3915_hostinfo(self):
        self._run_cycle(3915, 'hostinfo', 0)

    def test_cycle_3916_workdir(self):
        self._run_cycle(3916, 'workdir', 0)

    def test_cycle_3917_flagread(self):
        self._run_cycle(3917, 'flagread', 0)

    def test_cycle_3918_sysstat(self):
        self._run_cycle(3918, 'sysstat', 0)

    def test_cycle_3919_exit3(self):
        self._run_cycle(3919, 'exit3', 3)

    def test_cycle_3920_shadow(self):
        self._run_cycle(3920, 'shadow', 0)

    def test_cycle_3921_clock(self):
        self._run_cycle(3921, 'clock', 0)

    def test_cycle_3922_envmark(self):
        self._run_cycle(3922, 'envmark', 0)

    def test_cycle_3923_hostinfo(self):
        self._run_cycle(3923, 'hostinfo', 0)

    def test_cycle_3924_workdir(self):
        self._run_cycle(3924, 'workdir', 0)

    def test_cycle_3925_flagread(self):
        self._run_cycle(3925, 'flagread', 0)

    def test_cycle_3926_sysstat(self):
        self._run_cycle(3926, 'sysstat', 0)

    def test_cycle_3927_exit3(self):
        self._run_cycle(3927, 'exit3', 3)

    def test_cycle_3928_shadow(self):
        self._run_cycle(3928, 'shadow', 0)

    def test_cycle_3929_clock(self):
        self._run_cycle(3929, 'clock', 0)

    def test_cycle_3930_envmark(self):
        self._run_cycle(3930, 'envmark', 0)

    def test_cycle_3931_hostinfo(self):
        self._run_cycle(3931, 'hostinfo', 0)

    def test_cycle_3932_workdir(self):
        self._run_cycle(3932, 'workdir', 0)

    def test_cycle_3933_flagread(self):
        self._run_cycle(3933, 'flagread', 0)

    def test_cycle_3934_sysstat(self):
        self._run_cycle(3934, 'sysstat', 0)

    def test_cycle_3935_exit3(self):
        self._run_cycle(3935, 'exit3', 3)

    def test_cycle_3936_shadow(self):
        self._run_cycle(3936, 'shadow', 0)

    def test_cycle_3937_clock(self):
        self._run_cycle(3937, 'clock', 0)

    def test_cycle_3938_envmark(self):
        self._run_cycle(3938, 'envmark', 0)

    def test_cycle_3939_hostinfo(self):
        self._run_cycle(3939, 'hostinfo', 0)

    def test_cycle_3940_workdir(self):
        self._run_cycle(3940, 'workdir', 0)

    def test_cycle_3941_flagread(self):
        self._run_cycle(3941, 'flagread', 0)

    def test_cycle_3942_sysstat(self):
        self._run_cycle(3942, 'sysstat', 0)

    def test_cycle_3943_exit3(self):
        self._run_cycle(3943, 'exit3', 3)

    def test_cycle_3944_shadow(self):
        self._run_cycle(3944, 'shadow', 0)

    def test_cycle_3945_clock(self):
        self._run_cycle(3945, 'clock', 0)

    def test_cycle_3946_envmark(self):
        self._run_cycle(3946, 'envmark', 0)

    def test_cycle_3947_hostinfo(self):
        self._run_cycle(3947, 'hostinfo', 0)

    def test_cycle_3948_workdir(self):
        self._run_cycle(3948, 'workdir', 0)

    def test_cycle_3949_flagread(self):
        self._run_cycle(3949, 'flagread', 0)

    def test_cycle_3950_sysstat(self):
        self._run_cycle(3950, 'sysstat', 0)

    def test_cycle_3951_exit3(self):
        self._run_cycle(3951, 'exit3', 3)

    def test_cycle_3952_shadow(self):
        self._run_cycle(3952, 'shadow', 0)

    def test_cycle_3953_clock(self):
        self._run_cycle(3953, 'clock', 0)

    def test_cycle_3954_envmark(self):
        self._run_cycle(3954, 'envmark', 0)

    def test_cycle_3955_hostinfo(self):
        self._run_cycle(3955, 'hostinfo', 0)

    def test_cycle_3956_workdir(self):
        self._run_cycle(3956, 'workdir', 0)

    def test_cycle_3957_flagread(self):
        self._run_cycle(3957, 'flagread', 0)

    def test_cycle_3958_sysstat(self):
        self._run_cycle(3958, 'sysstat', 0)

    def test_cycle_3959_exit3(self):
        self._run_cycle(3959, 'exit3', 3)

    def test_cycle_3960_shadow(self):
        self._run_cycle(3960, 'shadow', 0)

    def test_cycle_3961_clock(self):
        self._run_cycle(3961, 'clock', 0)

    def test_cycle_3962_envmark(self):
        self._run_cycle(3962, 'envmark', 0)

    def test_cycle_3963_hostinfo(self):
        self._run_cycle(3963, 'hostinfo', 0)

    def test_cycle_3964_workdir(self):
        self._run_cycle(3964, 'workdir', 0)

    def test_cycle_3965_flagread(self):
        self._run_cycle(3965, 'flagread', 0)

    def test_cycle_3966_sysstat(self):
        self._run_cycle(3966, 'sysstat', 0)

    def test_cycle_3967_exit3(self):
        self._run_cycle(3967, 'exit3', 3)

    def test_cycle_3968_shadow(self):
        self._run_cycle(3968, 'shadow', 0)

    def test_cycle_3969_clock(self):
        self._run_cycle(3969, 'clock', 0)

    def test_cycle_3970_envmark(self):
        self._run_cycle(3970, 'envmark', 0)

    def test_cycle_3971_hostinfo(self):
        self._run_cycle(3971, 'hostinfo', 0)

    def test_cycle_3972_workdir(self):
        self._run_cycle(3972, 'workdir', 0)

    def test_cycle_3973_flagread(self):
        self._run_cycle(3973, 'flagread', 0)

    def test_cycle_3974_sysstat(self):
        self._run_cycle(3974, 'sysstat', 0)

    def test_cycle_3975_exit3(self):
        self._run_cycle(3975, 'exit3', 3)

    def test_cycle_3976_shadow(self):
        self._run_cycle(3976, 'shadow', 0)

    def test_cycle_3977_clock(self):
        self._run_cycle(3977, 'clock', 0)

    def test_cycle_3978_envmark(self):
        self._run_cycle(3978, 'envmark', 0)

    def test_cycle_3979_hostinfo(self):
        self._run_cycle(3979, 'hostinfo', 0)

    def test_cycle_3980_workdir(self):
        self._run_cycle(3980, 'workdir', 0)

    def test_cycle_3981_flagread(self):
        self._run_cycle(3981, 'flagread', 0)

    def test_cycle_3982_sysstat(self):
        self._run_cycle(3982, 'sysstat', 0)

    def test_cycle_3983_exit3(self):
        self._run_cycle(3983, 'exit3', 3)

    def test_cycle_3984_shadow(self):
        self._run_cycle(3984, 'shadow', 0)

    def test_cycle_3985_clock(self):
        self._run_cycle(3985, 'clock', 0)

    def test_cycle_3986_envmark(self):
        self._run_cycle(3986, 'envmark', 0)

    def test_cycle_3987_hostinfo(self):
        self._run_cycle(3987, 'hostinfo', 0)

    def test_cycle_3988_workdir(self):
        self._run_cycle(3988, 'workdir', 0)

    def test_cycle_3989_flagread(self):
        self._run_cycle(3989, 'flagread', 0)

    def test_cycle_3990_sysstat(self):
        self._run_cycle(3990, 'sysstat', 0)

    def test_cycle_3991_exit3(self):
        self._run_cycle(3991, 'exit3', 3)

    def test_cycle_3992_shadow(self):
        self._run_cycle(3992, 'shadow', 0)

    def test_cycle_3993_clock(self):
        self._run_cycle(3993, 'clock', 0)

    def test_cycle_3994_envmark(self):
        self._run_cycle(3994, 'envmark', 0)

    def test_cycle_3995_hostinfo(self):
        self._run_cycle(3995, 'hostinfo', 0)

    def test_cycle_3996_workdir(self):
        self._run_cycle(3996, 'workdir', 0)

    def test_cycle_3997_flagread(self):
        self._run_cycle(3997, 'flagread', 0)

    def test_cycle_3998_sysstat(self):
        self._run_cycle(3998, 'sysstat', 0)

    def test_cycle_3999_exit3(self):
        self._run_cycle(3999, 'exit3', 3)

    def test_cycle_4000_shadow(self):
        self._run_cycle(4000, 'shadow', 0)

    def test_cycle_4001_clock(self):
        self._run_cycle(4001, 'clock', 0)

    def test_cycle_4002_envmark(self):
        self._run_cycle(4002, 'envmark', 0)

    def test_cycle_4003_hostinfo(self):
        self._run_cycle(4003, 'hostinfo', 0)

    def test_cycle_4004_workdir(self):
        self._run_cycle(4004, 'workdir', 0)

    def test_cycle_4005_flagread(self):
        self._run_cycle(4005, 'flagread', 0)

    def test_cycle_4006_sysstat(self):
        self._run_cycle(4006, 'sysstat', 0)

    def test_cycle_4007_exit3(self):
        self._run_cycle(4007, 'exit3', 3)

    def test_cycle_4008_shadow(self):
        self._run_cycle(4008, 'shadow', 0)

    def test_cycle_4009_clock(self):
        self._run_cycle(4009, 'clock', 0)

    def test_cycle_4010_envmark(self):
        self._run_cycle(4010, 'envmark', 0)

    def test_cycle_4011_hostinfo(self):
        self._run_cycle(4011, 'hostinfo', 0)

    def test_cycle_4012_workdir(self):
        self._run_cycle(4012, 'workdir', 0)

    def test_cycle_4013_flagread(self):
        self._run_cycle(4013, 'flagread', 0)

    def test_cycle_4014_sysstat(self):
        self._run_cycle(4014, 'sysstat', 0)

    def test_cycle_4015_exit3(self):
        self._run_cycle(4015, 'exit3', 3)

    def test_cycle_4016_shadow(self):
        self._run_cycle(4016, 'shadow', 0)

    def test_cycle_4017_clock(self):
        self._run_cycle(4017, 'clock', 0)

    def test_cycle_4018_envmark(self):
        self._run_cycle(4018, 'envmark', 0)

    def test_cycle_4019_hostinfo(self):
        self._run_cycle(4019, 'hostinfo', 0)

    def test_cycle_4020_workdir(self):
        self._run_cycle(4020, 'workdir', 0)

    def test_cycle_4021_flagread(self):
        self._run_cycle(4021, 'flagread', 0)

    def test_cycle_4022_sysstat(self):
        self._run_cycle(4022, 'sysstat', 0)

    def test_cycle_4023_exit3(self):
        self._run_cycle(4023, 'exit3', 3)

    def test_cycle_4024_shadow(self):
        self._run_cycle(4024, 'shadow', 0)

    def test_cycle_4025_clock(self):
        self._run_cycle(4025, 'clock', 0)

    def test_cycle_4026_envmark(self):
        self._run_cycle(4026, 'envmark', 0)

    def test_cycle_4027_hostinfo(self):
        self._run_cycle(4027, 'hostinfo', 0)

    def test_cycle_4028_workdir(self):
        self._run_cycle(4028, 'workdir', 0)

    def test_cycle_4029_flagread(self):
        self._run_cycle(4029, 'flagread', 0)

    def test_cycle_4030_sysstat(self):
        self._run_cycle(4030, 'sysstat', 0)

    def test_cycle_4031_exit3(self):
        self._run_cycle(4031, 'exit3', 3)

    def test_cycle_4032_shadow(self):
        self._run_cycle(4032, 'shadow', 0)

    def test_cycle_4033_clock(self):
        self._run_cycle(4033, 'clock', 0)

    def test_cycle_4034_envmark(self):
        self._run_cycle(4034, 'envmark', 0)

    def test_cycle_4035_hostinfo(self):
        self._run_cycle(4035, 'hostinfo', 0)

    def test_cycle_4036_workdir(self):
        self._run_cycle(4036, 'workdir', 0)

    def test_cycle_4037_flagread(self):
        self._run_cycle(4037, 'flagread', 0)

    def test_cycle_4038_sysstat(self):
        self._run_cycle(4038, 'sysstat', 0)

    def test_cycle_4039_exit3(self):
        self._run_cycle(4039, 'exit3', 3)

    def test_cycle_4040_shadow(self):
        self._run_cycle(4040, 'shadow', 0)

    def test_cycle_4041_clock(self):
        self._run_cycle(4041, 'clock', 0)

    def test_cycle_4042_envmark(self):
        self._run_cycle(4042, 'envmark', 0)

    def test_cycle_4043_hostinfo(self):
        self._run_cycle(4043, 'hostinfo', 0)

    def test_cycle_4044_workdir(self):
        self._run_cycle(4044, 'workdir', 0)

    def test_cycle_4045_flagread(self):
        self._run_cycle(4045, 'flagread', 0)

    def test_cycle_4046_sysstat(self):
        self._run_cycle(4046, 'sysstat', 0)

    def test_cycle_4047_exit3(self):
        self._run_cycle(4047, 'exit3', 3)

    def test_cycle_4048_shadow(self):
        self._run_cycle(4048, 'shadow', 0)

    def test_cycle_4049_clock(self):
        self._run_cycle(4049, 'clock', 0)

    def test_cycle_4050_envmark(self):
        self._run_cycle(4050, 'envmark', 0)

    def test_cycle_4051_hostinfo(self):
        self._run_cycle(4051, 'hostinfo', 0)

    def test_cycle_4052_workdir(self):
        self._run_cycle(4052, 'workdir', 0)

    def test_cycle_4053_flagread(self):
        self._run_cycle(4053, 'flagread', 0)

    def test_cycle_4054_sysstat(self):
        self._run_cycle(4054, 'sysstat', 0)

    def test_cycle_4055_exit3(self):
        self._run_cycle(4055, 'exit3', 3)

    def test_cycle_4056_shadow(self):
        self._run_cycle(4056, 'shadow', 0)

    def test_cycle_4057_clock(self):
        self._run_cycle(4057, 'clock', 0)

    def test_cycle_4058_envmark(self):
        self._run_cycle(4058, 'envmark', 0)

    def test_cycle_4059_hostinfo(self):
        self._run_cycle(4059, 'hostinfo', 0)

    def test_cycle_4060_workdir(self):
        self._run_cycle(4060, 'workdir', 0)

    def test_cycle_4061_flagread(self):
        self._run_cycle(4061, 'flagread', 0)

    def test_cycle_4062_sysstat(self):
        self._run_cycle(4062, 'sysstat', 0)

    def test_cycle_4063_exit3(self):
        self._run_cycle(4063, 'exit3', 3)

    def test_cycle_4064_shadow(self):
        self._run_cycle(4064, 'shadow', 0)

    def test_cycle_4065_clock(self):
        self._run_cycle(4065, 'clock', 0)

    def test_cycle_4066_envmark(self):
        self._run_cycle(4066, 'envmark', 0)

    def test_cycle_4067_hostinfo(self):
        self._run_cycle(4067, 'hostinfo', 0)

    def test_cycle_4068_workdir(self):
        self._run_cycle(4068, 'workdir', 0)

    def test_cycle_4069_flagread(self):
        self._run_cycle(4069, 'flagread', 0)

    def test_cycle_4070_sysstat(self):
        self._run_cycle(4070, 'sysstat', 0)

    def test_cycle_4071_exit3(self):
        self._run_cycle(4071, 'exit3', 3)

    def test_cycle_4072_shadow(self):
        self._run_cycle(4072, 'shadow', 0)

    def test_cycle_4073_clock(self):
        self._run_cycle(4073, 'clock', 0)

    def test_cycle_4074_envmark(self):
        self._run_cycle(4074, 'envmark', 0)

    def test_cycle_4075_hostinfo(self):
        self._run_cycle(4075, 'hostinfo', 0)

    def test_cycle_4076_workdir(self):
        self._run_cycle(4076, 'workdir', 0)

    def test_cycle_4077_flagread(self):
        self._run_cycle(4077, 'flagread', 0)

    def test_cycle_4078_sysstat(self):
        self._run_cycle(4078, 'sysstat', 0)

    def test_cycle_4079_exit3(self):
        self._run_cycle(4079, 'exit3', 3)

    def test_cycle_4080_shadow(self):
        self._run_cycle(4080, 'shadow', 0)

    def test_cycle_4081_clock(self):
        self._run_cycle(4081, 'clock', 0)

    def test_cycle_4082_envmark(self):
        self._run_cycle(4082, 'envmark', 0)

    def test_cycle_4083_hostinfo(self):
        self._run_cycle(4083, 'hostinfo', 0)

    def test_cycle_4084_workdir(self):
        self._run_cycle(4084, 'workdir', 0)

    def test_cycle_4085_flagread(self):
        self._run_cycle(4085, 'flagread', 0)

    def test_cycle_4086_sysstat(self):
        self._run_cycle(4086, 'sysstat', 0)

    def test_cycle_4087_exit3(self):
        self._run_cycle(4087, 'exit3', 3)

    def test_cycle_4088_shadow(self):
        self._run_cycle(4088, 'shadow', 0)

    def test_cycle_4089_clock(self):
        self._run_cycle(4089, 'clock', 0)

    def test_cycle_4090_envmark(self):
        self._run_cycle(4090, 'envmark', 0)

    def test_cycle_4091_hostinfo(self):
        self._run_cycle(4091, 'hostinfo', 0)

    def test_cycle_4092_workdir(self):
        self._run_cycle(4092, 'workdir', 0)

    def test_cycle_4093_flagread(self):
        self._run_cycle(4093, 'flagread', 0)

    def test_cycle_4094_sysstat(self):
        self._run_cycle(4094, 'sysstat', 0)

    def test_cycle_4095_exit3(self):
        self._run_cycle(4095, 'exit3', 3)

    def test_cycle_4096_shadow(self):
        self._run_cycle(4096, 'shadow', 0)

    def test_cycle_4097_clock(self):
        self._run_cycle(4097, 'clock', 0)

    def test_cycle_4098_envmark(self):
        self._run_cycle(4098, 'envmark', 0)

    def test_cycle_4099_hostinfo(self):
        self._run_cycle(4099, 'hostinfo', 0)

    def test_cycle_4100_workdir(self):
        self._run_cycle(4100, 'workdir', 0)

    def test_cycle_4101_flagread(self):
        self._run_cycle(4101, 'flagread', 0)

    def test_cycle_4102_sysstat(self):
        self._run_cycle(4102, 'sysstat', 0)

    def test_cycle_4103_exit3(self):
        self._run_cycle(4103, 'exit3', 3)

    def test_cycle_4104_shadow(self):
        self._run_cycle(4104, 'shadow', 0)

    def test_cycle_4105_clock(self):
        self._run_cycle(4105, 'clock', 0)

    def test_cycle_4106_envmark(self):
        self._run_cycle(4106, 'envmark', 0)

    def test_cycle_4107_hostinfo(self):
        self._run_cycle(4107, 'hostinfo', 0)

    def test_cycle_4108_workdir(self):
        self._run_cycle(4108, 'workdir', 0)

    def test_cycle_4109_flagread(self):
        self._run_cycle(4109, 'flagread', 0)

    def test_cycle_4110_sysstat(self):
        self._run_cycle(4110, 'sysstat', 0)


    def test_cycle_4111_exit3(self):
        self._run_cycle(4111, 'exit3', 3)

    def test_cycle_4112_shadow(self):
        self._run_cycle(4112, 'shadow', 0)

    def test_cycle_4113_clock(self):
        self._run_cycle(4113, 'clock', 0)

    def test_cycle_4114_envmark(self):
        self._run_cycle(4114, 'envmark', 0)

    def test_cycle_4115_hostinfo(self):
        self._run_cycle(4115, 'hostinfo', 0)

    def test_cycle_4116_workdir(self):
        self._run_cycle(4116, 'workdir', 0)

    def test_cycle_4117_flagread(self):
        self._run_cycle(4117, 'flagread', 0)

    def test_cycle_4118_sysstat(self):
        self._run_cycle(4118, 'sysstat', 0)

    def test_cycle_4119_exit3(self):
        self._run_cycle(4119, 'exit3', 3)

    def test_cycle_4120_shadow(self):
        self._run_cycle(4120, 'shadow', 0)

    def test_cycle_4121_clock(self):
        self._run_cycle(4121, 'clock', 0)

    def test_cycle_4122_envmark(self):
        self._run_cycle(4122, 'envmark', 0)

    def test_cycle_4123_hostinfo(self):
        self._run_cycle(4123, 'hostinfo', 0)

    def test_cycle_4124_workdir(self):
        self._run_cycle(4124, 'workdir', 0)

    def test_cycle_4125_flagread(self):
        self._run_cycle(4125, 'flagread', 0)

    def test_cycle_4126_sysstat(self):
        self._run_cycle(4126, 'sysstat', 0)

    def test_cycle_4127_exit3(self):
        self._run_cycle(4127, 'exit3', 3)

    def test_cycle_4128_shadow(self):
        self._run_cycle(4128, 'shadow', 0)

    def test_cycle_4129_clock(self):
        self._run_cycle(4129, 'clock', 0)

    def test_cycle_4130_envmark(self):
        self._run_cycle(4130, 'envmark', 0)

    def test_cycle_4131_hostinfo(self):
        self._run_cycle(4131, 'hostinfo', 0)

    def test_cycle_4132_workdir(self):
        self._run_cycle(4132, 'workdir', 0)

    def test_cycle_4133_flagread(self):
        self._run_cycle(4133, 'flagread', 0)

    def test_cycle_4134_sysstat(self):
        self._run_cycle(4134, 'sysstat', 0)

    def test_cycle_4135_exit3(self):
        self._run_cycle(4135, 'exit3', 3)

    def test_cycle_4136_shadow(self):
        self._run_cycle(4136, 'shadow', 0)

    def test_cycle_4137_clock(self):
        self._run_cycle(4137, 'clock', 0)

    def test_cycle_4138_envmark(self):
        self._run_cycle(4138, 'envmark', 0)

    def test_cycle_4139_hostinfo(self):
        self._run_cycle(4139, 'hostinfo', 0)

    def test_cycle_4140_workdir(self):
        self._run_cycle(4140, 'workdir', 0)

    def test_cycle_4141_flagread(self):
        self._run_cycle(4141, 'flagread', 0)

    def test_cycle_4142_sysstat(self):
        self._run_cycle(4142, 'sysstat', 0)

    def test_cycle_4143_exit3(self):
        self._run_cycle(4143, 'exit3', 3)

    def test_cycle_4144_shadow(self):
        self._run_cycle(4144, 'shadow', 0)

    def test_cycle_4145_clock(self):
        self._run_cycle(4145, 'clock', 0)

    def test_cycle_4146_envmark(self):
        self._run_cycle(4146, 'envmark', 0)

    def test_cycle_4147_hostinfo(self):
        self._run_cycle(4147, 'hostinfo', 0)

    def test_cycle_4148_workdir(self):
        self._run_cycle(4148, 'workdir', 0)

    def test_cycle_4149_flagread(self):
        self._run_cycle(4149, 'flagread', 0)

    def test_cycle_4150_sysstat(self):
        self._run_cycle(4150, 'sysstat', 0)

    def test_cycle_4151_exit3(self):
        self._run_cycle(4151, 'exit3', 3)

    def test_cycle_4152_shadow(self):
        self._run_cycle(4152, 'shadow', 0)

    def test_cycle_4153_clock(self):
        self._run_cycle(4153, 'clock', 0)

    def test_cycle_4154_envmark(self):
        self._run_cycle(4154, 'envmark', 0)

    def test_cycle_4155_hostinfo(self):
        self._run_cycle(4155, 'hostinfo', 0)

    def test_cycle_4156_workdir(self):
        self._run_cycle(4156, 'workdir', 0)

    def test_cycle_4157_flagread(self):
        self._run_cycle(4157, 'flagread', 0)

    def test_cycle_4158_sysstat(self):
        self._run_cycle(4158, 'sysstat', 0)

    def test_cycle_4159_exit3(self):
        self._run_cycle(4159, 'exit3', 3)

    def test_cycle_4160_shadow(self):
        self._run_cycle(4160, 'shadow', 0)

    def test_cycle_4161_clock(self):
        self._run_cycle(4161, 'clock', 0)

    def test_cycle_4162_envmark(self):
        self._run_cycle(4162, 'envmark', 0)

    def test_cycle_4163_hostinfo(self):
        self._run_cycle(4163, 'hostinfo', 0)

    def test_cycle_4164_workdir(self):
        self._run_cycle(4164, 'workdir', 0)

    def test_cycle_4165_flagread(self):
        self._run_cycle(4165, 'flagread', 0)

    def test_cycle_4166_sysstat(self):
        self._run_cycle(4166, 'sysstat', 0)

    def test_cycle_4167_exit3(self):
        self._run_cycle(4167, 'exit3', 3)

    def test_cycle_4168_shadow(self):
        self._run_cycle(4168, 'shadow', 0)

    def test_cycle_4169_clock(self):
        self._run_cycle(4169, 'clock', 0)

    def test_cycle_4170_envmark(self):
        self._run_cycle(4170, 'envmark', 0)

    def test_cycle_4171_hostinfo(self):
        self._run_cycle(4171, 'hostinfo', 0)

    def test_cycle_4172_workdir(self):
        self._run_cycle(4172, 'workdir', 0)

    def test_cycle_4173_flagread(self):
        self._run_cycle(4173, 'flagread', 0)

    def test_cycle_4174_sysstat(self):
        self._run_cycle(4174, 'sysstat', 0)

    def test_cycle_4175_exit3(self):
        self._run_cycle(4175, 'exit3', 3)

    def test_cycle_4176_shadow(self):
        self._run_cycle(4176, 'shadow', 0)

    def test_cycle_4177_clock(self):
        self._run_cycle(4177, 'clock', 0)

    def test_cycle_4178_envmark(self):
        self._run_cycle(4178, 'envmark', 0)

    def test_cycle_4179_hostinfo(self):
        self._run_cycle(4179, 'hostinfo', 0)

    def test_cycle_4180_workdir(self):
        self._run_cycle(4180, 'workdir', 0)

    def test_cycle_4181_flagread(self):
        self._run_cycle(4181, 'flagread', 0)

    def test_cycle_4182_sysstat(self):
        self._run_cycle(4182, 'sysstat', 0)

    def test_cycle_4183_exit3(self):
        self._run_cycle(4183, 'exit3', 3)

    def test_cycle_4184_shadow(self):
        self._run_cycle(4184, 'shadow', 0)

    def test_cycle_4185_clock(self):
        self._run_cycle(4185, 'clock', 0)

    def test_cycle_4186_envmark(self):
        self._run_cycle(4186, 'envmark', 0)

    def test_cycle_4187_hostinfo(self):
        self._run_cycle(4187, 'hostinfo', 0)

    def test_cycle_4188_workdir(self):
        self._run_cycle(4188, 'workdir', 0)

    def test_cycle_4189_flagread(self):
        self._run_cycle(4189, 'flagread', 0)

    def test_cycle_4190_sysstat(self):
        self._run_cycle(4190, 'sysstat', 0)

    def test_cycle_4191_exit3(self):
        self._run_cycle(4191, 'exit3', 3)

    def test_cycle_4192_shadow(self):
        self._run_cycle(4192, 'shadow', 0)

    def test_cycle_4193_clock(self):
        self._run_cycle(4193, 'clock', 0)

    def test_cycle_4194_envmark(self):
        self._run_cycle(4194, 'envmark', 0)

    def test_cycle_4195_hostinfo(self):
        self._run_cycle(4195, 'hostinfo', 0)

    def test_cycle_4196_workdir(self):
        self._run_cycle(4196, 'workdir', 0)

    def test_cycle_4197_flagread(self):
        self._run_cycle(4197, 'flagread', 0)

    def test_cycle_4198_sysstat(self):
        self._run_cycle(4198, 'sysstat', 0)

    def test_cycle_4199_exit3(self):
        self._run_cycle(4199, 'exit3', 3)

    def test_cycle_4200_shadow(self):
        self._run_cycle(4200, 'shadow', 0)

    def test_cycle_4201_clock(self):
        self._run_cycle(4201, 'clock', 0)

    def test_cycle_4202_envmark(self):
        self._run_cycle(4202, 'envmark', 0)

    def test_cycle_4203_hostinfo(self):
        self._run_cycle(4203, 'hostinfo', 0)

    def test_cycle_4204_workdir(self):
        self._run_cycle(4204, 'workdir', 0)

    def test_cycle_4205_flagread(self):
        self._run_cycle(4205, 'flagread', 0)

    def test_cycle_4206_sysstat(self):
        self._run_cycle(4206, 'sysstat', 0)

    def test_cycle_4207_exit3(self):
        self._run_cycle(4207, 'exit3', 3)

    def test_cycle_4208_shadow(self):
        self._run_cycle(4208, 'shadow', 0)

    def test_cycle_4209_clock(self):
        self._run_cycle(4209, 'clock', 0)

    def test_cycle_4210_envmark(self):
        self._run_cycle(4210, 'envmark', 0)

    def test_cycle_4211_hostinfo(self):
        self._run_cycle(4211, 'hostinfo', 0)

    def test_cycle_4212_workdir(self):
        self._run_cycle(4212, 'workdir', 0)

    def test_cycle_4213_flagread(self):
        self._run_cycle(4213, 'flagread', 0)

    def test_cycle_4214_sysstat(self):
        self._run_cycle(4214, 'sysstat', 0)

    def test_cycle_4215_exit3(self):
        self._run_cycle(4215, 'exit3', 3)

    def test_cycle_4216_shadow(self):
        self._run_cycle(4216, 'shadow', 0)

    def test_cycle_4217_clock(self):
        self._run_cycle(4217, 'clock', 0)

    def test_cycle_4218_envmark(self):
        self._run_cycle(4218, 'envmark', 0)

    def test_cycle_4219_hostinfo(self):
        self._run_cycle(4219, 'hostinfo', 0)

    def test_cycle_4220_workdir(self):
        self._run_cycle(4220, 'workdir', 0)

    def test_cycle_4221_flagread(self):
        self._run_cycle(4221, 'flagread', 0)

    def test_cycle_4222_sysstat(self):
        self._run_cycle(4222, 'sysstat', 0)

    def test_cycle_4223_exit3(self):
        self._run_cycle(4223, 'exit3', 3)

    def test_cycle_4224_shadow(self):
        self._run_cycle(4224, 'shadow', 0)

    def test_cycle_4225_clock(self):
        self._run_cycle(4225, 'clock', 0)

    def test_cycle_4226_envmark(self):
        self._run_cycle(4226, 'envmark', 0)

    def test_cycle_4227_hostinfo(self):
        self._run_cycle(4227, 'hostinfo', 0)

    def test_cycle_4228_workdir(self):
        self._run_cycle(4228, 'workdir', 0)

    def test_cycle_4229_flagread(self):
        self._run_cycle(4229, 'flagread', 0)

    def test_cycle_4230_sysstat(self):
        self._run_cycle(4230, 'sysstat', 0)

    def test_cycle_4231_exit3(self):
        self._run_cycle(4231, 'exit3', 3)

    def test_cycle_4232_shadow(self):
        self._run_cycle(4232, 'shadow', 0)

    def test_cycle_4233_clock(self):
        self._run_cycle(4233, 'clock', 0)

    def test_cycle_4234_envmark(self):
        self._run_cycle(4234, 'envmark', 0)

    def test_cycle_4235_hostinfo(self):
        self._run_cycle(4235, 'hostinfo', 0)

    def test_cycle_4236_workdir(self):
        self._run_cycle(4236, 'workdir', 0)

    def test_cycle_4237_flagread(self):
        self._run_cycle(4237, 'flagread', 0)

    def test_cycle_4238_sysstat(self):
        self._run_cycle(4238, 'sysstat', 0)

    def test_cycle_4239_exit3(self):
        self._run_cycle(4239, 'exit3', 3)

    def test_cycle_4240_shadow(self):
        self._run_cycle(4240, 'shadow', 0)

    def test_cycle_4241_clock(self):
        self._run_cycle(4241, 'clock', 0)

    def test_cycle_4242_envmark(self):
        self._run_cycle(4242, 'envmark', 0)

    def test_cycle_4243_hostinfo(self):
        self._run_cycle(4243, 'hostinfo', 0)

    def test_cycle_4244_workdir(self):
        self._run_cycle(4244, 'workdir', 0)

    def test_cycle_4245_flagread(self):
        self._run_cycle(4245, 'flagread', 0)

    def test_cycle_4246_sysstat(self):
        self._run_cycle(4246, 'sysstat', 0)

    def test_cycle_4247_exit3(self):
        self._run_cycle(4247, 'exit3', 3)

    def test_cycle_4248_shadow(self):
        self._run_cycle(4248, 'shadow', 0)

    def test_cycle_4249_clock(self):
        self._run_cycle(4249, 'clock', 0)

    def test_cycle_4250_envmark(self):
        self._run_cycle(4250, 'envmark', 0)

    def test_cycle_4251_hostinfo(self):
        self._run_cycle(4251, 'hostinfo', 0)

    def test_cycle_4252_workdir(self):
        self._run_cycle(4252, 'workdir', 0)

    def test_cycle_4253_flagread(self):
        self._run_cycle(4253, 'flagread', 0)

    def test_cycle_4254_sysstat(self):
        self._run_cycle(4254, 'sysstat', 0)

    def test_cycle_4255_exit3(self):
        self._run_cycle(4255, 'exit3', 3)

    def test_cycle_4256_shadow(self):
        self._run_cycle(4256, 'shadow', 0)

    def test_cycle_4257_clock(self):
        self._run_cycle(4257, 'clock', 0)

    def test_cycle_4258_envmark(self):
        self._run_cycle(4258, 'envmark', 0)

    def test_cycle_4259_hostinfo(self):
        self._run_cycle(4259, 'hostinfo', 0)

    def test_cycle_4260_workdir(self):
        self._run_cycle(4260, 'workdir', 0)

    def test_cycle_4261_flagread(self):
        self._run_cycle(4261, 'flagread', 0)

    def test_cycle_4262_sysstat(self):
        self._run_cycle(4262, 'sysstat', 0)

    def test_cycle_4263_exit3(self):
        self._run_cycle(4263, 'exit3', 3)

    def test_cycle_4264_shadow(self):
        self._run_cycle(4264, 'shadow', 0)

    def test_cycle_4265_clock(self):
        self._run_cycle(4265, 'clock', 0)

    def test_cycle_4266_envmark(self):
        self._run_cycle(4266, 'envmark', 0)

    def test_cycle_4267_hostinfo(self):
        self._run_cycle(4267, 'hostinfo', 0)

    def test_cycle_4268_workdir(self):
        self._run_cycle(4268, 'workdir', 0)

    def test_cycle_4269_flagread(self):
        self._run_cycle(4269, 'flagread', 0)

    def test_cycle_4270_sysstat(self):
        self._run_cycle(4270, 'sysstat', 0)

    def test_cycle_4271_exit3(self):
        self._run_cycle(4271, 'exit3', 3)

    def test_cycle_4272_shadow(self):
        self._run_cycle(4272, 'shadow', 0)

    def test_cycle_4273_clock(self):
        self._run_cycle(4273, 'clock', 0)

    def test_cycle_4274_envmark(self):
        self._run_cycle(4274, 'envmark', 0)

    def test_cycle_4275_hostinfo(self):
        self._run_cycle(4275, 'hostinfo', 0)

    def test_cycle_4276_workdir(self):
        self._run_cycle(4276, 'workdir', 0)

    def test_cycle_4277_flagread(self):
        self._run_cycle(4277, 'flagread', 0)

    def test_cycle_4278_sysstat(self):
        self._run_cycle(4278, 'sysstat', 0)

    def test_cycle_4279_exit3(self):
        self._run_cycle(4279, 'exit3', 3)

    def test_cycle_4280_shadow(self):
        self._run_cycle(4280, 'shadow', 0)

    def test_cycle_4281_clock(self):
        self._run_cycle(4281, 'clock', 0)

    def test_cycle_4282_envmark(self):
        self._run_cycle(4282, 'envmark', 0)

    def test_cycle_4283_hostinfo(self):
        self._run_cycle(4283, 'hostinfo', 0)

    def test_cycle_4284_workdir(self):
        self._run_cycle(4284, 'workdir', 0)

    def test_cycle_4285_flagread(self):
        self._run_cycle(4285, 'flagread', 0)

    def test_cycle_4286_sysstat(self):
        self._run_cycle(4286, 'sysstat', 0)

    def test_cycle_4287_exit3(self):
        self._run_cycle(4287, 'exit3', 3)

    def test_cycle_4288_shadow(self):
        self._run_cycle(4288, 'shadow', 0)

    def test_cycle_4289_clock(self):
        self._run_cycle(4289, 'clock', 0)

    def test_cycle_4290_envmark(self):
        self._run_cycle(4290, 'envmark', 0)

    def test_cycle_4291_hostinfo(self):
        self._run_cycle(4291, 'hostinfo', 0)

    def test_cycle_4292_workdir(self):
        self._run_cycle(4292, 'workdir', 0)

    def test_cycle_4293_flagread(self):
        self._run_cycle(4293, 'flagread', 0)

    def test_cycle_4294_sysstat(self):
        self._run_cycle(4294, 'sysstat', 0)

    def test_cycle_4295_exit3(self):
        self._run_cycle(4295, 'exit3', 3)

    def test_cycle_4296_shadow(self):
        self._run_cycle(4296, 'shadow', 0)

    def test_cycle_4297_clock(self):
        self._run_cycle(4297, 'clock', 0)

    def test_cycle_4298_envmark(self):
        self._run_cycle(4298, 'envmark', 0)

    def test_cycle_4299_hostinfo(self):
        self._run_cycle(4299, 'hostinfo', 0)

    def test_cycle_4300_workdir(self):
        self._run_cycle(4300, 'workdir', 0)

    def test_cycle_4301_flagread(self):
        self._run_cycle(4301, 'flagread', 0)

    def test_cycle_4302_sysstat(self):
        self._run_cycle(4302, 'sysstat', 0)

    def test_cycle_4303_exit3(self):
        self._run_cycle(4303, 'exit3', 3)

    def test_cycle_4304_shadow(self):
        self._run_cycle(4304, 'shadow', 0)

    def test_cycle_4305_clock(self):
        self._run_cycle(4305, 'clock', 0)

    def test_cycle_4306_envmark(self):
        self._run_cycle(4306, 'envmark', 0)

    def test_cycle_4307_hostinfo(self):
        self._run_cycle(4307, 'hostinfo', 0)

    def test_cycle_4308_workdir(self):
        self._run_cycle(4308, 'workdir', 0)

    def test_cycle_4309_flagread(self):
        self._run_cycle(4309, 'flagread', 0)

    def test_cycle_4310_sysstat(self):
        self._run_cycle(4310, 'sysstat', 0)

    def test_cycle_4311_exit3(self):
        self._run_cycle(4311, 'exit3', 3)

    def test_cycle_4312_shadow(self):
        self._run_cycle(4312, 'shadow', 0)

    def test_cycle_4313_clock(self):
        self._run_cycle(4313, 'clock', 0)

    def test_cycle_4314_envmark(self):
        self._run_cycle(4314, 'envmark', 0)

    def test_cycle_4315_hostinfo(self):
        self._run_cycle(4315, 'hostinfo', 0)

    def test_cycle_4316_workdir(self):
        self._run_cycle(4316, 'workdir', 0)

    def test_cycle_4317_flagread(self):
        self._run_cycle(4317, 'flagread', 0)

    def test_cycle_4318_sysstat(self):
        self._run_cycle(4318, 'sysstat', 0)

    def test_cycle_4319_exit3(self):
        self._run_cycle(4319, 'exit3', 3)

    def test_cycle_4320_shadow(self):
        self._run_cycle(4320, 'shadow', 0)

    def test_cycle_4321_clock(self):
        self._run_cycle(4321, 'clock', 0)

    def test_cycle_4322_envmark(self):
        self._run_cycle(4322, 'envmark', 0)

    def test_cycle_4323_hostinfo(self):
        self._run_cycle(4323, 'hostinfo', 0)

    def test_cycle_4324_workdir(self):
        self._run_cycle(4324, 'workdir', 0)

    def test_cycle_4325_flagread(self):
        self._run_cycle(4325, 'flagread', 0)

    def test_cycle_4326_sysstat(self):
        self._run_cycle(4326, 'sysstat', 0)

    def test_cycle_4327_exit3(self):
        self._run_cycle(4327, 'exit3', 3)

    def test_cycle_4328_shadow(self):
        self._run_cycle(4328, 'shadow', 0)

    def test_cycle_4329_clock(self):
        self._run_cycle(4329, 'clock', 0)

    def test_cycle_4330_envmark(self):
        self._run_cycle(4330, 'envmark', 0)

    def test_cycle_4331_hostinfo(self):
        self._run_cycle(4331, 'hostinfo', 0)

    def test_cycle_4332_workdir(self):
        self._run_cycle(4332, 'workdir', 0)

    def test_cycle_4333_flagread(self):
        self._run_cycle(4333, 'flagread', 0)

    def test_cycle_4334_sysstat(self):
        self._run_cycle(4334, 'sysstat', 0)

    def test_cycle_4335_exit3(self):
        self._run_cycle(4335, 'exit3', 3)

    def test_cycle_4336_shadow(self):
        self._run_cycle(4336, 'shadow', 0)

    def test_cycle_4337_clock(self):
        self._run_cycle(4337, 'clock', 0)

    def test_cycle_4338_envmark(self):
        self._run_cycle(4338, 'envmark', 0)

    def test_cycle_4339_hostinfo(self):
        self._run_cycle(4339, 'hostinfo', 0)

    def test_cycle_4340_workdir(self):
        self._run_cycle(4340, 'workdir', 0)

    def test_cycle_4341_flagread(self):
        self._run_cycle(4341, 'flagread', 0)

    def test_cycle_4342_sysstat(self):
        self._run_cycle(4342, 'sysstat', 0)

    def test_cycle_4343_exit3(self):
        self._run_cycle(4343, 'exit3', 3)

    def test_cycle_4344_shadow(self):
        self._run_cycle(4344, 'shadow', 0)

    def test_cycle_4345_clock(self):
        self._run_cycle(4345, 'clock', 0)

    def test_cycle_4346_envmark(self):
        self._run_cycle(4346, 'envmark', 0)

    def test_cycle_4347_hostinfo(self):
        self._run_cycle(4347, 'hostinfo', 0)

    def test_cycle_4348_workdir(self):
        self._run_cycle(4348, 'workdir', 0)

    def test_cycle_4349_flagread(self):
        self._run_cycle(4349, 'flagread', 0)

    def test_cycle_4350_sysstat(self):
        self._run_cycle(4350, 'sysstat', 0)

    def test_cycle_4351_exit3(self):
        self._run_cycle(4351, 'exit3', 3)

    def test_cycle_4352_shadow(self):
        self._run_cycle(4352, 'shadow', 0)

    def test_cycle_4353_clock(self):
        self._run_cycle(4353, 'clock', 0)

    def test_cycle_4354_envmark(self):
        self._run_cycle(4354, 'envmark', 0)

    def test_cycle_4355_hostinfo(self):
        self._run_cycle(4355, 'hostinfo', 0)

    def test_cycle_4356_workdir(self):
        self._run_cycle(4356, 'workdir', 0)

    def test_cycle_4357_flagread(self):
        self._run_cycle(4357, 'flagread', 0)

    def test_cycle_4358_sysstat(self):
        self._run_cycle(4358, 'sysstat', 0)

    def test_cycle_4359_exit3(self):
        self._run_cycle(4359, 'exit3', 3)

    def test_cycle_4360_shadow(self):
        self._run_cycle(4360, 'shadow', 0)

    def test_cycle_4361_clock(self):
        self._run_cycle(4361, 'clock', 0)

    def test_cycle_4362_envmark(self):
        self._run_cycle(4362, 'envmark', 0)

    def test_cycle_4363_hostinfo(self):
        self._run_cycle(4363, 'hostinfo', 0)

    def test_cycle_4364_workdir(self):
        self._run_cycle(4364, 'workdir', 0)

    def test_cycle_4365_flagread(self):
        self._run_cycle(4365, 'flagread', 0)

    def test_cycle_4366_sysstat(self):
        self._run_cycle(4366, 'sysstat', 0)

    def test_cycle_4367_exit3(self):
        self._run_cycle(4367, 'exit3', 3)

    def test_cycle_4368_shadow(self):
        self._run_cycle(4368, 'shadow', 0)

    def test_cycle_4369_clock(self):
        self._run_cycle(4369, 'clock', 0)

    def test_cycle_4370_envmark(self):
        self._run_cycle(4370, 'envmark', 0)

    def test_cycle_4371_hostinfo(self):
        self._run_cycle(4371, 'hostinfo', 0)

    def test_cycle_4372_workdir(self):
        self._run_cycle(4372, 'workdir', 0)

    def test_cycle_4373_flagread(self):
        self._run_cycle(4373, 'flagread', 0)

    def test_cycle_4374_sysstat(self):
        self._run_cycle(4374, 'sysstat', 0)

    def test_cycle_4375_exit3(self):
        self._run_cycle(4375, 'exit3', 3)

    def test_cycle_4376_shadow(self):
        self._run_cycle(4376, 'shadow', 0)

    def test_cycle_4377_clock(self):
        self._run_cycle(4377, 'clock', 0)

    def test_cycle_4378_envmark(self):
        self._run_cycle(4378, 'envmark', 0)

    def test_cycle_4379_hostinfo(self):
        self._run_cycle(4379, 'hostinfo', 0)

    def test_cycle_4380_workdir(self):
        self._run_cycle(4380, 'workdir', 0)

    def test_cycle_4381_flagread(self):
        self._run_cycle(4381, 'flagread', 0)

    def test_cycle_4382_sysstat(self):
        self._run_cycle(4382, 'sysstat', 0)

    def test_cycle_4383_exit3(self):
        self._run_cycle(4383, 'exit3', 3)

    def test_cycle_4384_shadow(self):
        self._run_cycle(4384, 'shadow', 0)

    def test_cycle_4385_clock(self):
        self._run_cycle(4385, 'clock', 0)

    def test_cycle_4386_envmark(self):
        self._run_cycle(4386, 'envmark', 0)

    def test_cycle_4387_hostinfo(self):
        self._run_cycle(4387, 'hostinfo', 0)

    def test_cycle_4388_workdir(self):
        self._run_cycle(4388, 'workdir', 0)

    def test_cycle_4389_flagread(self):
        self._run_cycle(4389, 'flagread', 0)

    def test_cycle_4390_sysstat(self):
        self._run_cycle(4390, 'sysstat', 0)

    def test_cycle_4391_exit3(self):
        self._run_cycle(4391, 'exit3', 3)

    def test_cycle_4392_shadow(self):
        self._run_cycle(4392, 'shadow', 0)

    def test_cycle_4393_clock(self):
        self._run_cycle(4393, 'clock', 0)

    def test_cycle_4394_envmark(self):
        self._run_cycle(4394, 'envmark', 0)

    def test_cycle_4395_hostinfo(self):
        self._run_cycle(4395, 'hostinfo', 0)

    def test_cycle_4396_workdir(self):
        self._run_cycle(4396, 'workdir', 0)

    def test_cycle_4397_flagread(self):
        self._run_cycle(4397, 'flagread', 0)

    def test_cycle_4398_sysstat(self):
        self._run_cycle(4398, 'sysstat', 0)

    def test_cycle_4399_exit3(self):
        self._run_cycle(4399, 'exit3', 3)

    def test_cycle_4400_shadow(self):
        self._run_cycle(4400, 'shadow', 0)

    def test_cycle_4401_clock(self):
        self._run_cycle(4401, 'clock', 0)

    def test_cycle_4402_envmark(self):
        self._run_cycle(4402, 'envmark', 0)

    def test_cycle_4403_hostinfo(self):
        self._run_cycle(4403, 'hostinfo', 0)

    def test_cycle_4404_workdir(self):
        self._run_cycle(4404, 'workdir', 0)

    def test_cycle_4405_flagread(self):
        self._run_cycle(4405, 'flagread', 0)

    def test_cycle_4406_sysstat(self):
        self._run_cycle(4406, 'sysstat', 0)

    def test_cycle_4407_exit3(self):
        self._run_cycle(4407, 'exit3', 3)

    def test_cycle_4408_shadow(self):
        self._run_cycle(4408, 'shadow', 0)

    def test_cycle_4409_clock(self):
        self._run_cycle(4409, 'clock', 0)

    def test_cycle_4410_envmark(self):
        self._run_cycle(4410, 'envmark', 0)

    def test_cycle_4411_hostinfo(self):
        self._run_cycle(4411, 'hostinfo', 0)

    def test_cycle_4412_workdir(self):
        self._run_cycle(4412, 'workdir', 0)

    def test_cycle_4413_flagread(self):
        self._run_cycle(4413, 'flagread', 0)

    def test_cycle_4414_sysstat(self):
        self._run_cycle(4414, 'sysstat', 0)

    def test_cycle_4415_exit3(self):
        self._run_cycle(4415, 'exit3', 3)

    def test_cycle_4416_shadow(self):
        self._run_cycle(4416, 'shadow', 0)

    def test_cycle_4417_clock(self):
        self._run_cycle(4417, 'clock', 0)

    def test_cycle_4418_envmark(self):
        self._run_cycle(4418, 'envmark', 0)

    def test_cycle_4419_hostinfo(self):
        self._run_cycle(4419, 'hostinfo', 0)

    def test_cycle_4420_workdir(self):
        self._run_cycle(4420, 'workdir', 0)

    def test_cycle_4421_flagread(self):
        self._run_cycle(4421, 'flagread', 0)

    def test_cycle_4422_sysstat(self):
        self._run_cycle(4422, 'sysstat', 0)

    def test_cycle_4423_exit3(self):
        self._run_cycle(4423, 'exit3', 3)

    def test_cycle_4424_shadow(self):
        self._run_cycle(4424, 'shadow', 0)

    def test_cycle_4425_clock(self):
        self._run_cycle(4425, 'clock', 0)

    def test_cycle_4426_envmark(self):
        self._run_cycle(4426, 'envmark', 0)

    def test_cycle_4427_hostinfo(self):
        self._run_cycle(4427, 'hostinfo', 0)

    def test_cycle_4428_workdir(self):
        self._run_cycle(4428, 'workdir', 0)

    def test_cycle_4429_flagread(self):
        self._run_cycle(4429, 'flagread', 0)

    def test_cycle_4430_sysstat(self):
        self._run_cycle(4430, 'sysstat', 0)

    def test_cycle_4431_exit3(self):
        self._run_cycle(4431, 'exit3', 3)

    def test_cycle_4432_shadow(self):
        self._run_cycle(4432, 'shadow', 0)

    def test_cycle_4433_clock(self):
        self._run_cycle(4433, 'clock', 0)

    def test_cycle_4434_envmark(self):
        self._run_cycle(4434, 'envmark', 0)

    def test_cycle_4435_hostinfo(self):
        self._run_cycle(4435, 'hostinfo', 0)

    def test_cycle_4436_workdir(self):
        self._run_cycle(4436, 'workdir', 0)

    def test_cycle_4437_flagread(self):
        self._run_cycle(4437, 'flagread', 0)

    def test_cycle_4438_sysstat(self):
        self._run_cycle(4438, 'sysstat', 0)

    def test_cycle_4439_exit3(self):
        self._run_cycle(4439, 'exit3', 3)

    def test_cycle_4440_shadow(self):
        self._run_cycle(4440, 'shadow', 0)

    def test_cycle_4441_clock(self):
        self._run_cycle(4441, 'clock', 0)

    def test_cycle_4442_envmark(self):
        self._run_cycle(4442, 'envmark', 0)

    def test_cycle_4443_hostinfo(self):
        self._run_cycle(4443, 'hostinfo', 0)

    def test_cycle_4444_workdir(self):
        self._run_cycle(4444, 'workdir', 0)

    def test_cycle_4445_flagread(self):
        self._run_cycle(4445, 'flagread', 0)

    def test_cycle_4446_sysstat(self):
        self._run_cycle(4446, 'sysstat', 0)

    def test_cycle_4447_exit3(self):
        self._run_cycle(4447, 'exit3', 3)

    def test_cycle_4448_shadow(self):
        self._run_cycle(4448, 'shadow', 0)

    def test_cycle_4449_clock(self):
        self._run_cycle(4449, 'clock', 0)

    def test_cycle_4450_envmark(self):
        self._run_cycle(4450, 'envmark', 0)

    def test_cycle_4451_hostinfo(self):
        self._run_cycle(4451, 'hostinfo', 0)

    def test_cycle_4452_workdir(self):
        self._run_cycle(4452, 'workdir', 0)

    def test_cycle_4453_flagread(self):
        self._run_cycle(4453, 'flagread', 0)

    def test_cycle_4454_sysstat(self):
        self._run_cycle(4454, 'sysstat', 0)

    def test_cycle_4455_exit3(self):
        self._run_cycle(4455, 'exit3', 3)

    def test_cycle_4456_shadow(self):
        self._run_cycle(4456, 'shadow', 0)

    def test_cycle_4457_clock(self):
        self._run_cycle(4457, 'clock', 0)

    def test_cycle_4458_envmark(self):
        self._run_cycle(4458, 'envmark', 0)

    def test_cycle_4459_hostinfo(self):
        self._run_cycle(4459, 'hostinfo', 0)

    def test_cycle_4460_workdir(self):
        self._run_cycle(4460, 'workdir', 0)

    def test_cycle_4461_flagread(self):
        self._run_cycle(4461, 'flagread', 0)

    def test_cycle_4462_sysstat(self):
        self._run_cycle(4462, 'sysstat', 0)

    def test_cycle_4463_exit3(self):
        self._run_cycle(4463, 'exit3', 3)

    def test_cycle_4464_shadow(self):
        self._run_cycle(4464, 'shadow', 0)

    def test_cycle_4465_clock(self):
        self._run_cycle(4465, 'clock', 0)

    def test_cycle_4466_envmark(self):
        self._run_cycle(4466, 'envmark', 0)

    def test_cycle_4467_hostinfo(self):
        self._run_cycle(4467, 'hostinfo', 0)

    def test_cycle_4468_workdir(self):
        self._run_cycle(4468, 'workdir', 0)

    def test_cycle_4469_flagread(self):
        self._run_cycle(4469, 'flagread', 0)

    def test_cycle_4470_sysstat(self):
        self._run_cycle(4470, 'sysstat', 0)

    def test_cycle_4471_exit3(self):
        self._run_cycle(4471, 'exit3', 3)

    def test_cycle_4472_shadow(self):
        self._run_cycle(4472, 'shadow', 0)

    def test_cycle_4473_clock(self):
        self._run_cycle(4473, 'clock', 0)

    def test_cycle_4474_envmark(self):
        self._run_cycle(4474, 'envmark', 0)

    def test_cycle_4475_hostinfo(self):
        self._run_cycle(4475, 'hostinfo', 0)

    def test_cycle_4476_workdir(self):
        self._run_cycle(4476, 'workdir', 0)

    def test_cycle_4477_flagread(self):
        self._run_cycle(4477, 'flagread', 0)

    def test_cycle_4478_sysstat(self):
        self._run_cycle(4478, 'sysstat', 0)

    def test_cycle_4479_exit3(self):
        self._run_cycle(4479, 'exit3', 3)

    def test_cycle_4480_shadow(self):
        self._run_cycle(4480, 'shadow', 0)

    def test_cycle_4481_clock(self):
        self._run_cycle(4481, 'clock', 0)

    def test_cycle_4482_envmark(self):
        self._run_cycle(4482, 'envmark', 0)

    def test_cycle_4483_hostinfo(self):
        self._run_cycle(4483, 'hostinfo', 0)

    def test_cycle_4484_workdir(self):
        self._run_cycle(4484, 'workdir', 0)

    def test_cycle_4485_flagread(self):
        self._run_cycle(4485, 'flagread', 0)

    def test_cycle_4486_sysstat(self):
        self._run_cycle(4486, 'sysstat', 0)

    def test_cycle_4487_exit3(self):
        self._run_cycle(4487, 'exit3', 3)

    def test_cycle_4488_shadow(self):
        self._run_cycle(4488, 'shadow', 0)

    def test_cycle_4489_clock(self):
        self._run_cycle(4489, 'clock', 0)

    def test_cycle_4490_envmark(self):
        self._run_cycle(4490, 'envmark', 0)

    def test_cycle_4491_hostinfo(self):
        self._run_cycle(4491, 'hostinfo', 0)

    def test_cycle_4492_workdir(self):
        self._run_cycle(4492, 'workdir', 0)

    def test_cycle_4493_flagread(self):
        self._run_cycle(4493, 'flagread', 0)

    def test_cycle_4494_sysstat(self):
        self._run_cycle(4494, 'sysstat', 0)

    def test_cycle_4495_exit3(self):
        self._run_cycle(4495, 'exit3', 3)

    def test_cycle_4496_shadow(self):
        self._run_cycle(4496, 'shadow', 0)

    def test_cycle_4497_clock(self):
        self._run_cycle(4497, 'clock', 0)

    def test_cycle_4498_envmark(self):
        self._run_cycle(4498, 'envmark', 0)

    def test_cycle_4499_hostinfo(self):
        self._run_cycle(4499, 'hostinfo', 0)

    def test_cycle_4500_workdir(self):
        self._run_cycle(4500, 'workdir', 0)

    def test_cycle_4501_flagread(self):
        self._run_cycle(4501, 'flagread', 0)

    def test_cycle_4502_sysstat(self):
        self._run_cycle(4502, 'sysstat', 0)

    def test_cycle_4503_exit3(self):
        self._run_cycle(4503, 'exit3', 3)

    def test_cycle_4504_shadow(self):
        self._run_cycle(4504, 'shadow', 0)

    def test_cycle_4505_clock(self):
        self._run_cycle(4505, 'clock', 0)

    def test_cycle_4506_envmark(self):
        self._run_cycle(4506, 'envmark', 0)

    def test_cycle_4507_hostinfo(self):
        self._run_cycle(4507, 'hostinfo', 0)

    def test_cycle_4508_workdir(self):
        self._run_cycle(4508, 'workdir', 0)

    def test_cycle_4509_flagread(self):
        self._run_cycle(4509, 'flagread', 0)

    def test_cycle_4510_sysstat(self):
        self._run_cycle(4510, 'sysstat', 0)

    def test_cycle_4511_exit3(self):
        self._run_cycle(4511, 'exit3', 3)

    def test_cycle_4512_shadow(self):
        self._run_cycle(4512, 'shadow', 0)

    def test_cycle_4513_clock(self):
        self._run_cycle(4513, 'clock', 0)

    def test_cycle_4514_envmark(self):
        self._run_cycle(4514, 'envmark', 0)

    def test_cycle_4515_hostinfo(self):
        self._run_cycle(4515, 'hostinfo', 0)

    def test_cycle_4516_workdir(self):
        self._run_cycle(4516, 'workdir', 0)

    def test_cycle_4517_flagread(self):
        self._run_cycle(4517, 'flagread', 0)

    def test_cycle_4518_sysstat(self):
        self._run_cycle(4518, 'sysstat', 0)

    def test_cycle_4519_exit3(self):
        self._run_cycle(4519, 'exit3', 3)

    def test_cycle_4520_shadow(self):
        self._run_cycle(4520, 'shadow', 0)

    def test_cycle_4521_clock(self):
        self._run_cycle(4521, 'clock', 0)

    def test_cycle_4522_envmark(self):
        self._run_cycle(4522, 'envmark', 0)

    def test_cycle_4523_hostinfo(self):
        self._run_cycle(4523, 'hostinfo', 0)

    def test_cycle_4524_workdir(self):
        self._run_cycle(4524, 'workdir', 0)

    def test_cycle_4525_flagread(self):
        self._run_cycle(4525, 'flagread', 0)

    def test_cycle_4526_sysstat(self):
        self._run_cycle(4526, 'sysstat', 0)

    def test_cycle_4527_exit3(self):
        self._run_cycle(4527, 'exit3', 3)

    def test_cycle_4528_shadow(self):
        self._run_cycle(4528, 'shadow', 0)

    def test_cycle_4529_clock(self):
        self._run_cycle(4529, 'clock', 0)

    def test_cycle_4530_envmark(self):
        self._run_cycle(4530, 'envmark', 0)

    def test_cycle_4531_hostinfo(self):
        self._run_cycle(4531, 'hostinfo', 0)

    def test_cycle_4532_workdir(self):
        self._run_cycle(4532, 'workdir', 0)

    def test_cycle_4533_flagread(self):
        self._run_cycle(4533, 'flagread', 0)

    def test_cycle_4534_sysstat(self):
        self._run_cycle(4534, 'sysstat', 0)

    def test_cycle_4535_exit3(self):
        self._run_cycle(4535, 'exit3', 3)

    def test_cycle_4536_shadow(self):
        self._run_cycle(4536, 'shadow', 0)

    def test_cycle_4537_clock(self):
        self._run_cycle(4537, 'clock', 0)

    def test_cycle_4538_envmark(self):
        self._run_cycle(4538, 'envmark', 0)

    def test_cycle_4539_hostinfo(self):
        self._run_cycle(4539, 'hostinfo', 0)

    def test_cycle_4540_workdir(self):
        self._run_cycle(4540, 'workdir', 0)

    def test_cycle_4541_flagread(self):
        self._run_cycle(4541, 'flagread', 0)

    def test_cycle_4542_sysstat(self):
        self._run_cycle(4542, 'sysstat', 0)

    def test_cycle_4543_exit3(self):
        self._run_cycle(4543, 'exit3', 3)

    def test_cycle_4544_shadow(self):
        self._run_cycle(4544, 'shadow', 0)

    def test_cycle_4545_clock(self):
        self._run_cycle(4545, 'clock', 0)

    def test_cycle_4546_envmark(self):
        self._run_cycle(4546, 'envmark', 0)

    def test_cycle_4547_hostinfo(self):
        self._run_cycle(4547, 'hostinfo', 0)

    def test_cycle_4548_workdir(self):
        self._run_cycle(4548, 'workdir', 0)

    def test_cycle_4549_flagread(self):
        self._run_cycle(4549, 'flagread', 0)

    def test_cycle_4550_sysstat(self):
        self._run_cycle(4550, 'sysstat', 0)

    def test_cycle_4551_exit3(self):
        self._run_cycle(4551, 'exit3', 3)

    def test_cycle_4552_shadow(self):
        self._run_cycle(4552, 'shadow', 0)

    def test_cycle_4553_clock(self):
        self._run_cycle(4553, 'clock', 0)

    def test_cycle_4554_envmark(self):
        self._run_cycle(4554, 'envmark', 0)

    def test_cycle_4555_hostinfo(self):
        self._run_cycle(4555, 'hostinfo', 0)

    def test_cycle_4556_workdir(self):
        self._run_cycle(4556, 'workdir', 0)

    def test_cycle_4557_flagread(self):
        self._run_cycle(4557, 'flagread', 0)

    def test_cycle_4558_sysstat(self):
        self._run_cycle(4558, 'sysstat', 0)

    def test_cycle_4559_exit3(self):
        self._run_cycle(4559, 'exit3', 3)

    def test_cycle_4560_shadow(self):
        self._run_cycle(4560, 'shadow', 0)

    def test_cycle_4561_clock(self):
        self._run_cycle(4561, 'clock', 0)

    def test_cycle_4562_envmark(self):
        self._run_cycle(4562, 'envmark', 0)

    def test_cycle_4563_hostinfo(self):
        self._run_cycle(4563, 'hostinfo', 0)

    def test_cycle_4564_workdir(self):
        self._run_cycle(4564, 'workdir', 0)

    def test_cycle_4565_flagread(self):
        self._run_cycle(4565, 'flagread', 0)

    def test_cycle_4566_sysstat(self):
        self._run_cycle(4566, 'sysstat', 0)

    def test_cycle_4567_exit3(self):
        self._run_cycle(4567, 'exit3', 3)

    def test_cycle_4568_shadow(self):
        self._run_cycle(4568, 'shadow', 0)

    def test_cycle_4569_clock(self):
        self._run_cycle(4569, 'clock', 0)

    def test_cycle_4570_envmark(self):
        self._run_cycle(4570, 'envmark', 0)

    def test_cycle_4571_hostinfo(self):
        self._run_cycle(4571, 'hostinfo', 0)

    def test_cycle_4572_workdir(self):
        self._run_cycle(4572, 'workdir', 0)

    def test_cycle_4573_flagread(self):
        self._run_cycle(4573, 'flagread', 0)

    def test_cycle_4574_sysstat(self):
        self._run_cycle(4574, 'sysstat', 0)

    def test_cycle_4575_exit3(self):
        self._run_cycle(4575, 'exit3', 3)

    def test_cycle_4576_shadow(self):
        self._run_cycle(4576, 'shadow', 0)

    def test_cycle_4577_clock(self):
        self._run_cycle(4577, 'clock', 0)

    def test_cycle_4578_envmark(self):
        self._run_cycle(4578, 'envmark', 0)

    def test_cycle_4579_hostinfo(self):
        self._run_cycle(4579, 'hostinfo', 0)

    def test_cycle_4580_workdir(self):
        self._run_cycle(4580, 'workdir', 0)

    def test_cycle_4581_flagread(self):
        self._run_cycle(4581, 'flagread', 0)

    def test_cycle_4582_sysstat(self):
        self._run_cycle(4582, 'sysstat', 0)

    def test_cycle_4583_exit3(self):
        self._run_cycle(4583, 'exit3', 3)

    def test_cycle_4584_shadow(self):
        self._run_cycle(4584, 'shadow', 0)

    def test_cycle_4585_clock(self):
        self._run_cycle(4585, 'clock', 0)

    def test_cycle_4586_envmark(self):
        self._run_cycle(4586, 'envmark', 0)

    def test_cycle_4587_hostinfo(self):
        self._run_cycle(4587, 'hostinfo', 0)

    def test_cycle_4588_workdir(self):
        self._run_cycle(4588, 'workdir', 0)

    def test_cycle_4589_flagread(self):
        self._run_cycle(4589, 'flagread', 0)

    def test_cycle_4590_sysstat(self):
        self._run_cycle(4590, 'sysstat', 0)

    def test_cycle_4591_exit3(self):
        self._run_cycle(4591, 'exit3', 3)

    def test_cycle_4592_shadow(self):
        self._run_cycle(4592, 'shadow', 0)

    def test_cycle_4593_clock(self):
        self._run_cycle(4593, 'clock', 0)

    def test_cycle_4594_envmark(self):
        self._run_cycle(4594, 'envmark', 0)

    def test_cycle_4595_hostinfo(self):
        self._run_cycle(4595, 'hostinfo', 0)

    def test_cycle_4596_workdir(self):
        self._run_cycle(4596, 'workdir', 0)

    def test_cycle_4597_flagread(self):
        self._run_cycle(4597, 'flagread', 0)

    def test_cycle_4598_sysstat(self):
        self._run_cycle(4598, 'sysstat', 0)

    def test_cycle_4599_exit3(self):
        self._run_cycle(4599, 'exit3', 3)

    def test_cycle_4600_shadow(self):
        self._run_cycle(4600, 'shadow', 0)

    def test_cycle_4601_clock(self):
        self._run_cycle(4601, 'clock', 0)

    def test_cycle_4602_envmark(self):
        self._run_cycle(4602, 'envmark', 0)

    def test_cycle_4603_hostinfo(self):
        self._run_cycle(4603, 'hostinfo', 0)

    def test_cycle_4604_workdir(self):
        self._run_cycle(4604, 'workdir', 0)

    def test_cycle_4605_flagread(self):
        self._run_cycle(4605, 'flagread', 0)

    def test_cycle_4606_sysstat(self):
        self._run_cycle(4606, 'sysstat', 0)

    def test_cycle_4607_exit3(self):
        self._run_cycle(4607, 'exit3', 3)

    def test_cycle_4608_shadow(self):
        self._run_cycle(4608, 'shadow', 0)

    def test_cycle_4609_clock(self):
        self._run_cycle(4609, 'clock', 0)

    def test_cycle_4610_envmark(self):
        self._run_cycle(4610, 'envmark', 0)

    def test_cycle_4611_hostinfo(self):
        self._run_cycle(4611, 'hostinfo', 0)

    def test_cycle_4612_workdir(self):
        self._run_cycle(4612, 'workdir', 0)

    def test_cycle_4613_flagread(self):
        self._run_cycle(4613, 'flagread', 0)

    def test_cycle_4614_sysstat(self):
        self._run_cycle(4614, 'sysstat', 0)

    def test_cycle_4615_exit3(self):
        self._run_cycle(4615, 'exit3', 3)

    def test_cycle_4616_shadow(self):
        self._run_cycle(4616, 'shadow', 0)

    def test_cycle_4617_clock(self):
        self._run_cycle(4617, 'clock', 0)

    def test_cycle_4618_envmark(self):
        self._run_cycle(4618, 'envmark', 0)

    def test_cycle_4619_hostinfo(self):
        self._run_cycle(4619, 'hostinfo', 0)

    def test_cycle_4620_workdir(self):
        self._run_cycle(4620, 'workdir', 0)

    def test_cycle_4621_flagread(self):
        self._run_cycle(4621, 'flagread', 0)

    def test_cycle_4622_sysstat(self):
        self._run_cycle(4622, 'sysstat', 0)

    def test_cycle_4623_exit3(self):
        self._run_cycle(4623, 'exit3', 3)

    def test_cycle_4624_shadow(self):
        self._run_cycle(4624, 'shadow', 0)

    def test_cycle_4625_clock(self):
        self._run_cycle(4625, 'clock', 0)

    def test_cycle_4626_envmark(self):
        self._run_cycle(4626, 'envmark', 0)

    def test_cycle_4627_hostinfo(self):
        self._run_cycle(4627, 'hostinfo', 0)

    def test_cycle_4628_workdir(self):
        self._run_cycle(4628, 'workdir', 0)

    def test_cycle_4629_flagread(self):
        self._run_cycle(4629, 'flagread', 0)

    def test_cycle_4630_sysstat(self):
        self._run_cycle(4630, 'sysstat', 0)

    def test_cycle_4631_exit3(self):
        self._run_cycle(4631, 'exit3', 3)

    def test_cycle_4632_shadow(self):
        self._run_cycle(4632, 'shadow', 0)

    def test_cycle_4633_clock(self):
        self._run_cycle(4633, 'clock', 0)

    def test_cycle_4634_envmark(self):
        self._run_cycle(4634, 'envmark', 0)

    def test_cycle_4635_hostinfo(self):
        self._run_cycle(4635, 'hostinfo', 0)

    def test_cycle_4636_workdir(self):
        self._run_cycle(4636, 'workdir', 0)

    def test_cycle_4637_flagread(self):
        self._run_cycle(4637, 'flagread', 0)

    def test_cycle_4638_sysstat(self):
        self._run_cycle(4638, 'sysstat', 0)

    def test_cycle_4639_exit3(self):
        self._run_cycle(4639, 'exit3', 3)

    def test_cycle_4640_shadow(self):
        self._run_cycle(4640, 'shadow', 0)

    def test_cycle_4641_clock(self):
        self._run_cycle(4641, 'clock', 0)

    def test_cycle_4642_envmark(self):
        self._run_cycle(4642, 'envmark', 0)

    def test_cycle_4643_hostinfo(self):
        self._run_cycle(4643, 'hostinfo', 0)

    def test_cycle_4644_workdir(self):
        self._run_cycle(4644, 'workdir', 0)

    def test_cycle_4645_flagread(self):
        self._run_cycle(4645, 'flagread', 0)

    def test_cycle_4646_sysstat(self):
        self._run_cycle(4646, 'sysstat', 0)

    def test_cycle_4647_exit3(self):
        self._run_cycle(4647, 'exit3', 3)

    def test_cycle_4648_shadow(self):
        self._run_cycle(4648, 'shadow', 0)

    def test_cycle_4649_clock(self):
        self._run_cycle(4649, 'clock', 0)

    def test_cycle_4650_envmark(self):
        self._run_cycle(4650, 'envmark', 0)

    def test_cycle_4651_hostinfo(self):
        self._run_cycle(4651, 'hostinfo', 0)

    def test_cycle_4652_workdir(self):
        self._run_cycle(4652, 'workdir', 0)

    def test_cycle_4653_flagread(self):
        self._run_cycle(4653, 'flagread', 0)

    def test_cycle_4654_sysstat(self):
        self._run_cycle(4654, 'sysstat', 0)

    def test_cycle_4655_exit3(self):
        self._run_cycle(4655, 'exit3', 3)

    def test_cycle_4656_shadow(self):
        self._run_cycle(4656, 'shadow', 0)

    def test_cycle_4657_clock(self):
        self._run_cycle(4657, 'clock', 0)

    def test_cycle_4658_envmark(self):
        self._run_cycle(4658, 'envmark', 0)

    def test_cycle_4659_hostinfo(self):
        self._run_cycle(4659, 'hostinfo', 0)

    def test_cycle_4660_workdir(self):
        self._run_cycle(4660, 'workdir', 0)

    def test_cycle_4661_flagread(self):
        self._run_cycle(4661, 'flagread', 0)

    def test_cycle_4662_sysstat(self):
        self._run_cycle(4662, 'sysstat', 0)

    def test_cycle_4663_exit3(self):
        self._run_cycle(4663, 'exit3', 3)

    def test_cycle_4664_shadow(self):
        self._run_cycle(4664, 'shadow', 0)

    def test_cycle_4665_clock(self):
        self._run_cycle(4665, 'clock', 0)

    def test_cycle_4666_envmark(self):
        self._run_cycle(4666, 'envmark', 0)

    def test_cycle_4667_hostinfo(self):
        self._run_cycle(4667, 'hostinfo', 0)

    def test_cycle_4668_workdir(self):
        self._run_cycle(4668, 'workdir', 0)

    def test_cycle_4669_flagread(self):
        self._run_cycle(4669, 'flagread', 0)

    def test_cycle_4670_sysstat(self):
        self._run_cycle(4670, 'sysstat', 0)

    def test_cycle_4671_exit3(self):
        self._run_cycle(4671, 'exit3', 3)

    def test_cycle_4672_shadow(self):
        self._run_cycle(4672, 'shadow', 0)

    def test_cycle_4673_clock(self):
        self._run_cycle(4673, 'clock', 0)

    def test_cycle_4674_envmark(self):
        self._run_cycle(4674, 'envmark', 0)

    def test_cycle_4675_hostinfo(self):
        self._run_cycle(4675, 'hostinfo', 0)

    def test_cycle_4676_workdir(self):
        self._run_cycle(4676, 'workdir', 0)

    def test_cycle_4677_flagread(self):
        self._run_cycle(4677, 'flagread', 0)

    def test_cycle_4678_sysstat(self):
        self._run_cycle(4678, 'sysstat', 0)

    def test_cycle_4679_exit3(self):
        self._run_cycle(4679, 'exit3', 3)

    def test_cycle_4680_shadow(self):
        self._run_cycle(4680, 'shadow', 0)

    def test_cycle_4681_clock(self):
        self._run_cycle(4681, 'clock', 0)

    def test_cycle_4682_envmark(self):
        self._run_cycle(4682, 'envmark', 0)

    def test_cycle_4683_hostinfo(self):
        self._run_cycle(4683, 'hostinfo', 0)

    def test_cycle_4684_workdir(self):
        self._run_cycle(4684, 'workdir', 0)

    def test_cycle_4685_flagread(self):
        self._run_cycle(4685, 'flagread', 0)

    def test_cycle_4686_sysstat(self):
        self._run_cycle(4686, 'sysstat', 0)

    def test_cycle_4687_exit3(self):
        self._run_cycle(4687, 'exit3', 3)

    def test_cycle_4688_shadow(self):
        self._run_cycle(4688, 'shadow', 0)

    def test_cycle_4689_clock(self):
        self._run_cycle(4689, 'clock', 0)

    def test_cycle_4690_envmark(self):
        self._run_cycle(4690, 'envmark', 0)

    def test_cycle_4691_hostinfo(self):
        self._run_cycle(4691, 'hostinfo', 0)

    def test_cycle_4692_workdir(self):
        self._run_cycle(4692, 'workdir', 0)

    def test_cycle_4693_flagread(self):
        self._run_cycle(4693, 'flagread', 0)

    def test_cycle_4694_sysstat(self):
        self._run_cycle(4694, 'sysstat', 0)

    def test_cycle_4695_exit3(self):
        self._run_cycle(4695, 'exit3', 3)

    def test_cycle_4696_shadow(self):
        self._run_cycle(4696, 'shadow', 0)

    def test_cycle_4697_clock(self):
        self._run_cycle(4697, 'clock', 0)

    def test_cycle_4698_envmark(self):
        self._run_cycle(4698, 'envmark', 0)

    def test_cycle_4699_hostinfo(self):
        self._run_cycle(4699, 'hostinfo', 0)

    def test_cycle_4700_workdir(self):
        self._run_cycle(4700, 'workdir', 0)

    def test_cycle_4701_flagread(self):
        self._run_cycle(4701, 'flagread', 0)

    def test_cycle_4702_sysstat(self):
        self._run_cycle(4702, 'sysstat', 0)

    def test_cycle_4703_exit3(self):
        self._run_cycle(4703, 'exit3', 3)

    def test_cycle_4704_shadow(self):
        self._run_cycle(4704, 'shadow', 0)

    def test_cycle_4705_clock(self):
        self._run_cycle(4705, 'clock', 0)

    def test_cycle_4706_envmark(self):
        self._run_cycle(4706, 'envmark', 0)

    def test_cycle_4707_hostinfo(self):
        self._run_cycle(4707, 'hostinfo', 0)

    def test_cycle_4708_workdir(self):
        self._run_cycle(4708, 'workdir', 0)

    def test_cycle_4709_flagread(self):
        self._run_cycle(4709, 'flagread', 0)

    def test_cycle_4710_sysstat(self):
        self._run_cycle(4710, 'sysstat', 0)

    def test_cycle_4711_exit3(self):
        self._run_cycle(4711, 'exit3', 3)

    def test_cycle_4712_shadow(self):
        self._run_cycle(4712, 'shadow', 0)

    def test_cycle_4713_clock(self):
        self._run_cycle(4713, 'clock', 0)

    def test_cycle_4714_envmark(self):
        self._run_cycle(4714, 'envmark', 0)

    def test_cycle_4715_hostinfo(self):
        self._run_cycle(4715, 'hostinfo', 0)

    def test_cycle_4716_workdir(self):
        self._run_cycle(4716, 'workdir', 0)

    def test_cycle_4717_flagread(self):
        self._run_cycle(4717, 'flagread', 0)

    def test_cycle_4718_sysstat(self):
        self._run_cycle(4718, 'sysstat', 0)

    def test_cycle_4719_exit3(self):
        self._run_cycle(4719, 'exit3', 3)

    def test_cycle_4720_shadow(self):
        self._run_cycle(4720, 'shadow', 0)

    def test_cycle_4721_clock(self):
        self._run_cycle(4721, 'clock', 0)

    def test_cycle_4722_envmark(self):
        self._run_cycle(4722, 'envmark', 0)

    def test_cycle_4723_hostinfo(self):
        self._run_cycle(4723, 'hostinfo', 0)

    def test_cycle_4724_workdir(self):
        self._run_cycle(4724, 'workdir', 0)

    def test_cycle_4725_flagread(self):
        self._run_cycle(4725, 'flagread', 0)

    def test_cycle_4726_sysstat(self):
        self._run_cycle(4726, 'sysstat', 0)

    def test_cycle_4727_exit3(self):
        self._run_cycle(4727, 'exit3', 3)

    def test_cycle_4728_shadow(self):
        self._run_cycle(4728, 'shadow', 0)

    def test_cycle_4729_clock(self):
        self._run_cycle(4729, 'clock', 0)

    def test_cycle_4730_envmark(self):
        self._run_cycle(4730, 'envmark', 0)

    def test_cycle_4731_hostinfo(self):
        self._run_cycle(4731, 'hostinfo', 0)

    def test_cycle_4732_workdir(self):
        self._run_cycle(4732, 'workdir', 0)

    def test_cycle_4733_flagread(self):
        self._run_cycle(4733, 'flagread', 0)

    def test_cycle_4734_sysstat(self):
        self._run_cycle(4734, 'sysstat', 0)

    def test_cycle_4735_exit3(self):
        self._run_cycle(4735, 'exit3', 3)

    def test_cycle_4736_shadow(self):
        self._run_cycle(4736, 'shadow', 0)

    def test_cycle_4737_clock(self):
        self._run_cycle(4737, 'clock', 0)

    def test_cycle_4738_envmark(self):
        self._run_cycle(4738, 'envmark', 0)

    def test_cycle_4739_hostinfo(self):
        self._run_cycle(4739, 'hostinfo', 0)

    def test_cycle_4740_workdir(self):
        self._run_cycle(4740, 'workdir', 0)

    def test_cycle_4741_flagread(self):
        self._run_cycle(4741, 'flagread', 0)

    def test_cycle_4742_sysstat(self):
        self._run_cycle(4742, 'sysstat', 0)

    def test_cycle_4743_exit3(self):
        self._run_cycle(4743, 'exit3', 3)

    def test_cycle_4744_shadow(self):
        self._run_cycle(4744, 'shadow', 0)

    def test_cycle_4745_clock(self):
        self._run_cycle(4745, 'clock', 0)

    def test_cycle_4746_envmark(self):
        self._run_cycle(4746, 'envmark', 0)

    def test_cycle_4747_hostinfo(self):
        self._run_cycle(4747, 'hostinfo', 0)

    def test_cycle_4748_workdir(self):
        self._run_cycle(4748, 'workdir', 0)

    def test_cycle_4749_flagread(self):
        self._run_cycle(4749, 'flagread', 0)

    def test_cycle_4750_sysstat(self):
        self._run_cycle(4750, 'sysstat', 0)

    def test_cycle_4751_exit3(self):
        self._run_cycle(4751, 'exit3', 3)

    def test_cycle_4752_shadow(self):
        self._run_cycle(4752, 'shadow', 0)

    def test_cycle_4753_clock(self):
        self._run_cycle(4753, 'clock', 0)

    def test_cycle_4754_envmark(self):
        self._run_cycle(4754, 'envmark', 0)

    def test_cycle_4755_hostinfo(self):
        self._run_cycle(4755, 'hostinfo', 0)

    def test_cycle_4756_workdir(self):
        self._run_cycle(4756, 'workdir', 0)

    def test_cycle_4757_flagread(self):
        self._run_cycle(4757, 'flagread', 0)

    def test_cycle_4758_sysstat(self):
        self._run_cycle(4758, 'sysstat', 0)

    def test_cycle_4759_exit3(self):
        self._run_cycle(4759, 'exit3', 3)

    def test_cycle_4760_shadow(self):
        self._run_cycle(4760, 'shadow', 0)

    def test_cycle_4761_clock(self):
        self._run_cycle(4761, 'clock', 0)

    def test_cycle_4762_envmark(self):
        self._run_cycle(4762, 'envmark', 0)

    def test_cycle_4763_hostinfo(self):
        self._run_cycle(4763, 'hostinfo', 0)

    def test_cycle_4764_workdir(self):
        self._run_cycle(4764, 'workdir', 0)

    def test_cycle_4765_flagread(self):
        self._run_cycle(4765, 'flagread', 0)

    def test_cycle_4766_sysstat(self):
        self._run_cycle(4766, 'sysstat', 0)

    def test_cycle_4767_exit3(self):
        self._run_cycle(4767, 'exit3', 3)

    def test_cycle_4768_shadow(self):
        self._run_cycle(4768, 'shadow', 0)

    def test_cycle_4769_clock(self):
        self._run_cycle(4769, 'clock', 0)

    def test_cycle_4770_envmark(self):
        self._run_cycle(4770, 'envmark', 0)

    def test_cycle_4771_hostinfo(self):
        self._run_cycle(4771, 'hostinfo', 0)

    def test_cycle_4772_workdir(self):
        self._run_cycle(4772, 'workdir', 0)

    def test_cycle_4773_flagread(self):
        self._run_cycle(4773, 'flagread', 0)

    def test_cycle_4774_sysstat(self):
        self._run_cycle(4774, 'sysstat', 0)

    def test_cycle_4775_exit3(self):
        self._run_cycle(4775, 'exit3', 3)

    def test_cycle_4776_shadow(self):
        self._run_cycle(4776, 'shadow', 0)

    def test_cycle_4777_clock(self):
        self._run_cycle(4777, 'clock', 0)

    def test_cycle_4778_envmark(self):
        self._run_cycle(4778, 'envmark', 0)

    def test_cycle_4779_hostinfo(self):
        self._run_cycle(4779, 'hostinfo', 0)

    def test_cycle_4780_workdir(self):
        self._run_cycle(4780, 'workdir', 0)

    def test_cycle_4781_flagread(self):
        self._run_cycle(4781, 'flagread', 0)

    def test_cycle_4782_sysstat(self):
        self._run_cycle(4782, 'sysstat', 0)

    def test_cycle_4783_exit3(self):
        self._run_cycle(4783, 'exit3', 3)

    def test_cycle_4784_shadow(self):
        self._run_cycle(4784, 'shadow', 0)

    def test_cycle_4785_clock(self):
        self._run_cycle(4785, 'clock', 0)

    def test_cycle_4786_envmark(self):
        self._run_cycle(4786, 'envmark', 0)

    def test_cycle_4787_hostinfo(self):
        self._run_cycle(4787, 'hostinfo', 0)

    def test_cycle_4788_workdir(self):
        self._run_cycle(4788, 'workdir', 0)

    def test_cycle_4789_flagread(self):
        self._run_cycle(4789, 'flagread', 0)

    def test_cycle_4790_sysstat(self):
        self._run_cycle(4790, 'sysstat', 0)

    def test_cycle_4791_exit3(self):
        self._run_cycle(4791, 'exit3', 3)

    def test_cycle_4792_shadow(self):
        self._run_cycle(4792, 'shadow', 0)

    def test_cycle_4793_clock(self):
        self._run_cycle(4793, 'clock', 0)

    def test_cycle_4794_envmark(self):
        self._run_cycle(4794, 'envmark', 0)

    def test_cycle_4795_hostinfo(self):
        self._run_cycle(4795, 'hostinfo', 0)

    def test_cycle_4796_workdir(self):
        self._run_cycle(4796, 'workdir', 0)

    def test_cycle_4797_flagread(self):
        self._run_cycle(4797, 'flagread', 0)

    def test_cycle_4798_sysstat(self):
        self._run_cycle(4798, 'sysstat', 0)

    def test_cycle_4799_exit3(self):
        self._run_cycle(4799, 'exit3', 3)

    def test_cycle_4800_shadow(self):
        self._run_cycle(4800, 'shadow', 0)

    def test_cycle_4801_clock(self):
        self._run_cycle(4801, 'clock', 0)

    def test_cycle_4802_envmark(self):
        self._run_cycle(4802, 'envmark', 0)

    def test_cycle_4803_hostinfo(self):
        self._run_cycle(4803, 'hostinfo', 0)

    def test_cycle_4804_workdir(self):
        self._run_cycle(4804, 'workdir', 0)

    def test_cycle_4805_flagread(self):
        self._run_cycle(4805, 'flagread', 0)

    def test_cycle_4806_sysstat(self):
        self._run_cycle(4806, 'sysstat', 0)

    def test_cycle_4807_exit3(self):
        self._run_cycle(4807, 'exit3', 3)

    def test_cycle_4808_shadow(self):
        self._run_cycle(4808, 'shadow', 0)

    def test_cycle_4809_clock(self):
        self._run_cycle(4809, 'clock', 0)

    def test_cycle_4810_envmark(self):
        self._run_cycle(4810, 'envmark', 0)

    def test_cycle_4811_hostinfo(self):
        self._run_cycle(4811, 'hostinfo', 0)

    def test_cycle_4812_workdir(self):
        self._run_cycle(4812, 'workdir', 0)

    def test_cycle_4813_flagread(self):
        self._run_cycle(4813, 'flagread', 0)

    def test_cycle_4814_sysstat(self):
        self._run_cycle(4814, 'sysstat', 0)

    def test_cycle_4815_exit3(self):
        self._run_cycle(4815, 'exit3', 3)

    def test_cycle_4816_shadow(self):
        self._run_cycle(4816, 'shadow', 0)

    def test_cycle_4817_clock(self):
        self._run_cycle(4817, 'clock', 0)

    def test_cycle_4818_envmark(self):
        self._run_cycle(4818, 'envmark', 0)

    def test_cycle_4819_hostinfo(self):
        self._run_cycle(4819, 'hostinfo', 0)

    def test_cycle_4820_workdir(self):
        self._run_cycle(4820, 'workdir', 0)

    def test_cycle_4821_flagread(self):
        self._run_cycle(4821, 'flagread', 0)

    def test_cycle_4822_sysstat(self):
        self._run_cycle(4822, 'sysstat', 0)

    def test_cycle_4823_exit3(self):
        self._run_cycle(4823, 'exit3', 3)

    def test_cycle_4824_shadow(self):
        self._run_cycle(4824, 'shadow', 0)

    def test_cycle_4825_clock(self):
        self._run_cycle(4825, 'clock', 0)

    def test_cycle_4826_envmark(self):
        self._run_cycle(4826, 'envmark', 0)

    def test_cycle_4827_hostinfo(self):
        self._run_cycle(4827, 'hostinfo', 0)

    def test_cycle_4828_workdir(self):
        self._run_cycle(4828, 'workdir', 0)

    def test_cycle_4829_flagread(self):
        self._run_cycle(4829, 'flagread', 0)

    def test_cycle_4830_sysstat(self):
        self._run_cycle(4830, 'sysstat', 0)

    def test_cycle_4831_exit3(self):
        self._run_cycle(4831, 'exit3', 3)

    def test_cycle_4832_shadow(self):
        self._run_cycle(4832, 'shadow', 0)

    def test_cycle_4833_clock(self):
        self._run_cycle(4833, 'clock', 0)

    def test_cycle_4834_envmark(self):
        self._run_cycle(4834, 'envmark', 0)

    def test_cycle_4835_hostinfo(self):
        self._run_cycle(4835, 'hostinfo', 0)

    def test_cycle_4836_workdir(self):
        self._run_cycle(4836, 'workdir', 0)

    def test_cycle_4837_flagread(self):
        self._run_cycle(4837, 'flagread', 0)

    def test_cycle_4838_sysstat(self):
        self._run_cycle(4838, 'sysstat', 0)

    def test_cycle_4839_exit3(self):
        self._run_cycle(4839, 'exit3', 3)

    def test_cycle_4840_shadow(self):
        self._run_cycle(4840, 'shadow', 0)

    def test_cycle_4841_clock(self):
        self._run_cycle(4841, 'clock', 0)

    def test_cycle_4842_envmark(self):
        self._run_cycle(4842, 'envmark', 0)

    def test_cycle_4843_hostinfo(self):
        self._run_cycle(4843, 'hostinfo', 0)

    def test_cycle_4844_workdir(self):
        self._run_cycle(4844, 'workdir', 0)

    def test_cycle_4845_flagread(self):
        self._run_cycle(4845, 'flagread', 0)

    def test_cycle_4846_sysstat(self):
        self._run_cycle(4846, 'sysstat', 0)

    def test_cycle_4847_exit3(self):
        self._run_cycle(4847, 'exit3', 3)

    def test_cycle_4848_shadow(self):
        self._run_cycle(4848, 'shadow', 0)

    def test_cycle_4849_clock(self):
        self._run_cycle(4849, 'clock', 0)

    def test_cycle_4850_envmark(self):
        self._run_cycle(4850, 'envmark', 0)

    def test_cycle_4851_hostinfo(self):
        self._run_cycle(4851, 'hostinfo', 0)

    def test_cycle_4852_workdir(self):
        self._run_cycle(4852, 'workdir', 0)

    def test_cycle_4853_flagread(self):
        self._run_cycle(4853, 'flagread', 0)

    def test_cycle_4854_sysstat(self):
        self._run_cycle(4854, 'sysstat', 0)

    def test_cycle_4855_exit3(self):
        self._run_cycle(4855, 'exit3', 3)

    def test_cycle_4856_shadow(self):
        self._run_cycle(4856, 'shadow', 0)

    def test_cycle_4857_clock(self):
        self._run_cycle(4857, 'clock', 0)

    def test_cycle_4858_envmark(self):
        self._run_cycle(4858, 'envmark', 0)

    def test_cycle_4859_hostinfo(self):
        self._run_cycle(4859, 'hostinfo', 0)

    def test_cycle_4860_workdir(self):
        self._run_cycle(4860, 'workdir', 0)

    def test_cycle_4861_flagread(self):
        self._run_cycle(4861, 'flagread', 0)

    def test_cycle_4862_sysstat(self):
        self._run_cycle(4862, 'sysstat', 0)

    def test_cycle_4863_exit3(self):
        self._run_cycle(4863, 'exit3', 3)

    def test_cycle_4864_shadow(self):
        self._run_cycle(4864, 'shadow', 0)

    def test_cycle_4865_clock(self):
        self._run_cycle(4865, 'clock', 0)

    def test_cycle_4866_envmark(self):
        self._run_cycle(4866, 'envmark', 0)

    def test_cycle_4867_hostinfo(self):
        self._run_cycle(4867, 'hostinfo', 0)

    def test_cycle_4868_workdir(self):
        self._run_cycle(4868, 'workdir', 0)

    def test_cycle_4869_flagread(self):
        self._run_cycle(4869, 'flagread', 0)

    def test_cycle_4870_sysstat(self):
        self._run_cycle(4870, 'sysstat', 0)

    def test_cycle_4871_exit3(self):
        self._run_cycle(4871, 'exit3', 3)

    def test_cycle_4872_shadow(self):
        self._run_cycle(4872, 'shadow', 0)

    def test_cycle_4873_clock(self):
        self._run_cycle(4873, 'clock', 0)

    def test_cycle_4874_envmark(self):
        self._run_cycle(4874, 'envmark', 0)

    def test_cycle_4875_hostinfo(self):
        self._run_cycle(4875, 'hostinfo', 0)

    def test_cycle_4876_workdir(self):
        self._run_cycle(4876, 'workdir', 0)

    def test_cycle_4877_flagread(self):
        self._run_cycle(4877, 'flagread', 0)

    def test_cycle_4878_sysstat(self):
        self._run_cycle(4878, 'sysstat', 0)

    def test_cycle_4879_exit3(self):
        self._run_cycle(4879, 'exit3', 3)

    def test_cycle_4880_shadow(self):
        self._run_cycle(4880, 'shadow', 0)

    def test_cycle_4881_clock(self):
        self._run_cycle(4881, 'clock', 0)

    def test_cycle_4882_envmark(self):
        self._run_cycle(4882, 'envmark', 0)

    def test_cycle_4883_hostinfo(self):
        self._run_cycle(4883, 'hostinfo', 0)

    def test_cycle_4884_workdir(self):
        self._run_cycle(4884, 'workdir', 0)

    def test_cycle_4885_flagread(self):
        self._run_cycle(4885, 'flagread', 0)

    def test_cycle_4886_sysstat(self):
        self._run_cycle(4886, 'sysstat', 0)

    def test_cycle_4887_exit3(self):
        self._run_cycle(4887, 'exit3', 3)

    def test_cycle_4888_shadow(self):
        self._run_cycle(4888, 'shadow', 0)

    def test_cycle_4889_clock(self):
        self._run_cycle(4889, 'clock', 0)

    def test_cycle_4890_envmark(self):
        self._run_cycle(4890, 'envmark', 0)

    def test_cycle_4891_hostinfo(self):
        self._run_cycle(4891, 'hostinfo', 0)

    def test_cycle_4892_workdir(self):
        self._run_cycle(4892, 'workdir', 0)

    def test_cycle_4893_flagread(self):
        self._run_cycle(4893, 'flagread', 0)

    def test_cycle_4894_sysstat(self):
        self._run_cycle(4894, 'sysstat', 0)

    def test_cycle_4895_exit3(self):
        self._run_cycle(4895, 'exit3', 3)

    def test_cycle_4896_shadow(self):
        self._run_cycle(4896, 'shadow', 0)

    def test_cycle_4897_clock(self):
        self._run_cycle(4897, 'clock', 0)

    def test_cycle_4898_envmark(self):
        self._run_cycle(4898, 'envmark', 0)

    def test_cycle_4899_hostinfo(self):
        self._run_cycle(4899, 'hostinfo', 0)

    def test_cycle_4900_workdir(self):
        self._run_cycle(4900, 'workdir', 0)

    def test_cycle_4901_flagread(self):
        self._run_cycle(4901, 'flagread', 0)

    def test_cycle_4902_sysstat(self):
        self._run_cycle(4902, 'sysstat', 0)

    def test_cycle_4903_exit3(self):
        self._run_cycle(4903, 'exit3', 3)

    def test_cycle_4904_shadow(self):
        self._run_cycle(4904, 'shadow', 0)

    def test_cycle_4905_clock(self):
        self._run_cycle(4905, 'clock', 0)

    def test_cycle_4906_envmark(self):
        self._run_cycle(4906, 'envmark', 0)

    def test_cycle_4907_hostinfo(self):
        self._run_cycle(4907, 'hostinfo', 0)

    def test_cycle_4908_workdir(self):
        self._run_cycle(4908, 'workdir', 0)

    def test_cycle_4909_flagread(self):
        self._run_cycle(4909, 'flagread', 0)

    def test_cycle_4910_sysstat(self):
        self._run_cycle(4910, 'sysstat', 0)

    def test_cycle_4911_exit3(self):
        self._run_cycle(4911, 'exit3', 3)

    def test_cycle_4912_shadow(self):
        self._run_cycle(4912, 'shadow', 0)

    def test_cycle_4913_clock(self):
        self._run_cycle(4913, 'clock', 0)

    def test_cycle_4914_envmark(self):
        self._run_cycle(4914, 'envmark', 0)

    def test_cycle_4915_hostinfo(self):
        self._run_cycle(4915, 'hostinfo', 0)

    def test_cycle_4916_workdir(self):
        self._run_cycle(4916, 'workdir', 0)

    def test_cycle_4917_flagread(self):
        self._run_cycle(4917, 'flagread', 0)

    def test_cycle_4918_sysstat(self):
        self._run_cycle(4918, 'sysstat', 0)

    def test_cycle_4919_exit3(self):
        self._run_cycle(4919, 'exit3', 3)

    def test_cycle_4920_shadow(self):
        self._run_cycle(4920, 'shadow', 0)

    def test_cycle_4921_clock(self):
        self._run_cycle(4921, 'clock', 0)

    def test_cycle_4922_envmark(self):
        self._run_cycle(4922, 'envmark', 0)

    def test_cycle_4923_hostinfo(self):
        self._run_cycle(4923, 'hostinfo', 0)

    def test_cycle_4924_workdir(self):
        self._run_cycle(4924, 'workdir', 0)

    def test_cycle_4925_flagread(self):
        self._run_cycle(4925, 'flagread', 0)

    def test_cycle_4926_sysstat(self):
        self._run_cycle(4926, 'sysstat', 0)

    def test_cycle_4927_exit3(self):
        self._run_cycle(4927, 'exit3', 3)

    def test_cycle_4928_shadow(self):
        self._run_cycle(4928, 'shadow', 0)

    def test_cycle_4929_clock(self):
        self._run_cycle(4929, 'clock', 0)

    def test_cycle_4930_envmark(self):
        self._run_cycle(4930, 'envmark', 0)

    def test_cycle_4931_hostinfo(self):
        self._run_cycle(4931, 'hostinfo', 0)

    def test_cycle_4932_workdir(self):
        self._run_cycle(4932, 'workdir', 0)

    def test_cycle_4933_flagread(self):
        self._run_cycle(4933, 'flagread', 0)

    def test_cycle_4934_sysstat(self):
        self._run_cycle(4934, 'sysstat', 0)

    def test_cycle_4935_exit3(self):
        self._run_cycle(4935, 'exit3', 3)

    def test_cycle_4936_shadow(self):
        self._run_cycle(4936, 'shadow', 0)

    def test_cycle_4937_clock(self):
        self._run_cycle(4937, 'clock', 0)


if __name__ == "__main__":
    unittest.main()
