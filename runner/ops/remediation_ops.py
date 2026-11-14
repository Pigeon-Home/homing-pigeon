"""Remediation and job helpers.

Extracted from runner.py.
"""
import json
import os
import signal
import sys


try:
    from runner.ops.live import _runner
except ImportError:  # running from inside runner/ as __main__
    from ops.live import _runner  # type: ignore


def _windows_confine(backend=None):
    """The Windows containment backend module, or None.

    `backend` is the tests' injection point. The real module is
    runner/guard/windows_confine.py, imported lazily by its
    role-folder name with the script-mode fallback, the way
    sibling modules import each other. None when it cannot be
    imported at all: callers read that as "cannot engage",
    which keeps every gate in its refuse direction.
    """
    if backend is not None:
        return backend
    try:
        from runner.guard import windows_confine
        return windows_confine
    except ImportError:
        pass
    try:
        from guard import windows_confine  # type: ignore
        return windows_confine
    except ImportError:
        return None

# The mark _confinement_spawn leaves on a Windows confined
# process: this process already sits in a Job Object. The
# confinement spawn assigns the process to its Job Object at
# creation (suspended, before it runs a line), and a process
# can sit in only one job hierarchy -- assigning it to a
# second, unrelated Job Object fails (AssignProcessToJobObject,
# error 5). job_user's Windows control is that same Job Object
# with the same memory ceiling, so _job_user_postspawn reads
# this mark as "the control is already applied" instead of
# assigning again. Identity is the test: only the spawn seam's
# own mark counts, never a look-alike value.
JOB_OBJECT_APPLIED = object()


def _freebsd_confine(backend=None):
    """The FreeBSD containment backend module, or None.

    The mirror of _windows_confine for runner/guard/
    freebsd_confine.py, imported lazily the same way. `backend`
    is the tests' injection point. None when it cannot be
    imported at all: callers read that as "cannot engage",
    which keeps every gate in its refuse direction.
    """
    if backend is not None:
        return backend
    try:
        from runner.guard import freebsd_confine
        return freebsd_confine
    except ImportError:
        pass
    try:
        from guard import freebsd_confine  # type: ignore
        return freebsd_confine
    except ImportError:
        return None


def _macos_confine(backend=None):
    """The macOS containment backend module, or None.

    The mirror of _freebsd_confine for runner/guard/
    macos_confine.py, imported lazily the same way. `backend`
    is the tests' injection point. None when it cannot be
    imported at all: callers read that as "cannot engage",
    which keeps every gate in its refuse direction.
    """
    if backend is not None:
        return backend
    try:
        from runner.guard import macos_confine
        return macos_confine
    except ImportError:
        pass
    try:
        from guard import macos_confine  # type: ignore
        return macos_confine
    except ImportError:
        return None

def _finish_remediation(cfg, st, monitor, job, job_id, work,
                        base_dir, script_path, proc=None):
    """Close out a monitored job: acts, record, member.

    Called after the process has exited (or been killed). A
    mid-run act is already in the monitor's outcome; a tripwire
    the final scan turns up still earns quarantine, referral,
    and the page -- there is just nothing left to kill, so the
    recorded act is the quarantine. The same honesty applies to
    a mid-run kill order that lost the race with a job already
    exiting on its own (POSIX: the exit was not the SIGKILL):
    the act that landed is the quarantine. Returns the result
    member or None when nothing acted.
    """
    R = _runner()
    outcome = monitor.outcome
    try:
        monitor.final_scan()
    except Exception:
        pass
    mode = st["mode"]
    digest = _runner()._remediation.received_digest(job)
    envelope_note = getattr(monitor, "_envelope_note", "")
    for div in outcome.get("divergences") or []:
        _runner().vlog(f"remediation: job {job_id}: divergence "
             f"{_runner()._remediation.divergence_text(div)}")
    for rec in outcome.get("oracle") or []:
        decision = rec.get("decision")
        _runner()._remediation_audit(
            base_dir, cfg, st, job_id,
            "abstained" if decision == "abstain" else "spared",
            rec.get("divergence") or "", rec.get("reason") or "")
    if mode == "off":
        page_div = outcome.get("page")
        if page_div is not None:
            _runner()._remediation_event(base_dir, st, job_id, page_div,
                               "none", "none", "unavailable", "",
                               digest)
            _runner()._remediation_audit(base_dir, cfg, st, job_id,
                               "observed", page_div,
                               "mode off: recorded and paged only")
        return None
    acted = outcome.get("acted")
    post_tripwire = None
    if acted is None:
        for div in outcome.get("divergences") or []:
            if div.get("tripwire"):
                post_tripwire = div
                break
    if acted is None and post_tripwire is None:
        return None
    if acted is not None:
        authority = acted["authority"]
        div = acted["divergence"]
        _sigkill = getattr(signal, "SIGKILL", None)
        tree_killed = os.name == "nt" or (
            _sigkill is not None
            and proc is not None and proc.returncode is not None
            and proc.returncode == -_sigkill)
        act = "killed" if tree_killed else "quarantined"
    else:
        authority = "tripwire"
        div = post_tripwire
        act = "quarantined"
    R.log(f"job {job_id}: remediation {act} "
        f"({_runner()._remediation.divergence_text(div)}; "
        f"authority {authority})", "WARN")
    marker = {"job_id": job_id, "mode": mode, "authority": authority,
              "divergence": _runner()._remediation.divergence_text(div),
              "act": act, "received_digest": digest}
    qdir = _runner()._remediation.quarantine_job(base_dir, job_id, work, marker)
    refer = []
    if qdir:
        qwork = os.path.join(qdir, "work")
        for rel in outcome.get("suspects") or []:
            refer.append(os.path.join(qwork, rel))
        try:
            script_rel = os.path.relpath(script_path, work)
            refer.append(os.path.join(qwork, script_rel))
        except ValueError:
            pass
    else:
        for rel in outcome.get("suspects") or []:
            refer.append(os.path.join(work, rel))
        refer.append(script_path)
    av_verdict, av_detail = _runner()._remediation.av_referral(refer)
    member = _runner()._remediation.result_member(
        mode, authority, div, act, av_verdict, digest)
    _runner()._remediation.enforce_quarantine_bounds(base_dir, st)
    _runner()._remediation_audit(
        base_dir, cfg, st, job_id, "acted", div,
        f"act={act} authority={authority} av={av_verdict} "
        f"({av_detail})")
    _runner()._remediation_event(base_dir, st, job_id, div, act, authority,
                       av_verdict, qdir or "", digest, envelope_note)
    return member


def job_user_startup_problem(cfg, platform=None, face=None,
                             backend=None):
    """Why job_user on enforce cannot run here, or None when it can.

    The POSIX mechanism is a setuid demote in a preexec hook; on
    Windows there is no such hook. Windows containment is a Job
    Object assigned after the process starts (runner/guard/
    windows_confine.py), so on win32 the gate asks that backend
    whether it can engage: engageable, enforce may run and the
    assignment happens per job in _job_user_postspawn; not
    engageable, enforce changes what the box protects while
    doing nothing, which is Decision 1's refuse class -- the
    same one confinement's startup_problem guards. On POSIX the demote needs root and a resolvable configured
    user: a runner that is not root, or whose configured user
    cannot be resolved, would start and then run every job as
    the runner's own account under a mode that promises
    otherwise -- so both refuse at startup instead (Q132). A
    user that exists at startup and is removed later reaches
    the job-time path in _job_user_preexec, which records the
    fallback and refuses the job under enforce.
    platform defaults to sys.platform; tests pass it, and a fake
    face when they script the syscalls.
    """
    if platform is None:
        platform = sys.platform
    sec = _runner()._security
    if sec is None or sec.sec_mode(cfg, "job_user") != "enforce":
        return None
    if platform == "win32":
        backend = _windows_confine(backend)
        if backend is not None and getattr(
                backend, "IS_WINDOWS_BACKEND", False):
            # Only a real backend's probe is consulted. The stub
            # (any non-Windows host, including every simulated
            # win32 the suite constructs) answers below with the
            # refusal it has always given, deterministically.
            try:
                problem = backend.windows_startup_problem(cfg)
            except Exception as e:  # a backend that cannot answer
                problem = str(e)    # has not shown it can engage
            if problem is None:
                return None
            return "job_user cannot engage on win32: %s" % problem
        return ("job_user (a POSIX setuid demote) is POSIX-only; "
                "this machine is win32")
    secblock = cfg.get("security") if isinstance(cfg, dict) else None
    secblock = secblock if isinstance(secblock, dict) else {}
    ju = secblock.get("job_user")
    user = ju.get("user") if isinstance(ju, dict) else None
    if not user or not isinstance(user, str):
        return None
    face = face or _runner()._JobUserFace()
    if face.euid() != 0:
        return ("job_user demotes jobs with setuid, which needs "
                "root; the runner is not running as root, so the "
                "demote cannot be applied")
    try:
        face.getpwnam(user)
    except (ImportError, KeyError, ValueError) as e:
        return ("the configured job_user %r cannot be resolved "
                "on this machine (%s)" % (user, e))
    return None


def _job_user_preexec(cfg, base_dir, job_id, work, face=None,
                      backend=None):
    R = _runner()
    if _runner()._security is None:
        return None
    mode = _runner()._security.sec_mode(cfg, "job_user")
    if mode == "off":
        return None
    if os.name == "nt":
        # The demote cannot engage on Windows. What can engage is
        # the Job Object backend, and only after the process
        # starts -- so under enforce the refusal lives at startup
        # (job_user_startup_problem) and the application in
        # _job_user_postspawn; this hook's win32 job is the record
        # and, when the backend cannot engage, the job-time
        # backstop refusal for a config changed under a running
        # runner. The backend is consulted on a real Windows host
        # (sys.platform) or when a test injects one; a simulated
        # os.name alone keeps the long-standing behavior.
        engageable = False
        if backend is not None or sys.platform == "win32":
            mod = _windows_confine(backend)
            if mod is not None and (
                    backend is not None
                    or getattr(mod, "IS_WINDOWS_BACKEND", False)):
                try:
                    engageable = (
                        mod.windows_startup_problem(cfg) is None)
                except Exception:
                    engageable = False
        _runner()._security.bump_evaluated(base_dir, "job_user")
        try:
            _runner()._security.write_audit_entry(
                base_dir, "job_user",
                "would_contain" if engageable
                else "unsupported_platform",
                "windows_job_object" if engageable
                else "job_user_posix_only",
                job_id=str(job_id), cfg=cfg,
                mode=mode)
        except Exception:
            pass
        if mode == "enforce" and not engageable:
            raise _runner().JobRejected(
                "job_user is POSIX-only; job refused under "
                "security.modes.job_user=enforce")
        return None
    face = face or _runner()._JobUserFace()
    _runner()._security.bump_evaluated(base_dir, "job_user")
    sec = cfg.get("security")
    sec = sec if isinstance(sec, dict) else {}
    ju = sec.get("job_user") if isinstance(sec.get("job_user"), dict) else {}
    user = ju.get("user") if isinstance(ju, dict) else None
    if not user or not isinstance(user, str):
        return None

    def _audit(decision, reason, detail=""):
        try:
            _runner()._security.write_audit_entry(
                base_dir, "job_user", decision, reason,
                job_id=str(job_id), detail=str(detail), cfg=cfg,
                mode=mode)
        except Exception:
            pass

    if mode == "audit":
        _audit("would_run_as", "would_run_as_user", user)
        return None
    # enforce from here on: a demote that cannot happen refuses
    # the job. The fallback is recorded first, in the same shape
    # it always had, so the audit trail still names the step-down
    # that was refused.
    if face.euid() != 0:
        R.log(f"job {job_id}: job_user needs root; refusing the job "
            f"under enforce", "WARN")
        _audit("fallback", "job_user_needs_root")
        raise _runner().JobRejected(
            "job_user needs root; job refused under "
            "security.modes.job_user=enforce")
    try:
        pw = face.getpwnam(user)
    except (ImportError, KeyError) as e:
        R.log(f"job {job_id}: job_user {user!r} unavailable ({e}); "
            f"refusing the job under enforce", "WARN")
        _audit("fallback", "job_user_unavailable", str(e))
        raise _runner().JobRejected(
            f"job_user {user!r} unavailable ({e}); job refused under "
            "security.modes.job_user=enforce")
    # The job must own its workdir to read the script and write output.
    try:
        for root, dirs, files in face.walk(work):
            face.chown(root, pw.pw_uid, pw.pw_gid)
            for d in dirs:
                face.chown(os.path.join(root, d), pw.pw_uid, pw.pw_gid)
            for f in files:
                face.chown(os.path.join(root, f), pw.pw_uid, pw.pw_gid)
        # Traverse-only (+x, not +r) on the parent chain up to base_dir,
        # so the job user can reach its workdir without listing the
        # runner's state. Files there stay protected by their own mode.
        node = face.realpath(work)
        stop = face.realpath(base_dir)
        while True:
            node = face.dirname(node)
            try:
                st = face.stat(node)
            except OSError:
                break
            if not st.st_mode & 0o001:
                face.chmod(node, st.st_mode | 0o001)
            if node == stop or node == face.dirname(node):
                break
    except OSError as e:
        R.log(f"job {job_id}: cannot chown workdir to {user} ({e}); "
            f"refusing the job under enforce", "WARN")
        _audit("fallback", "job_user_chown_failed", str(e))
        raise _runner().JobRejected(
            f"cannot chown workdir to {user} ({e}); job refused "
            "under security.modes.job_user=enforce")
    _audit("run_as", "ran_as_user", user)

    def _demote():
        # After fork, before exec. Syscalls only.
        face.setgid(pw.pw_gid)
        try:
            face.initgroups(pw.pw_name, pw.pw_gid)
        except OSError:
            # Q18: never carry the runner's supplementary groups
            # into the job. Fall back to the user's primary group
            # alone; if even that fails, raise, and the job is
            # refused rather than run with the runner's groups.
            face.setgroups([pw.pw_gid])
        face.setuid(pw.pw_uid)
    return _demote


def _job_user_postspawn(cfg, base_dir, job_id, proc, backend=None):
    """Apply Windows containment to a just-started job process.

    The POSIX demote rides Popen's preexec_fn, which Windows does
    not have; a Job Object can only be assigned once the process
    exists, so on win32 the enforce point for job_user is here,
    called by exec immediately after Popen. Returns a release
    callable the caller invokes once the process has exited (it
    closes the job handle, which ends the Job Object), or None
    when nothing was applied -- every mode but enforce, and every
    platform but win32, returns None and changes nothing.

    A job that came through a spawn seam (the confinement
    spawn, or the job_user spawn in _job_user_spawn) already
    carries the control, marked JOB_OBJECT_APPLIED, and is
    recorded below without a second assignment. This
    function's own assignment is for a process that came
    through neither seam.

    Under enforce a failure is a refusal, in the shape the POSIX
    path uses: the fallback is recorded, the just-started process
    is killed, and the job is rejected rather than run
    uncontained. The success record names only what was applied:
    decision "contained", reason the backend's own status string
    ("windows_job_object") -- no record claims a restricted token
    or any other control this backend does not implement.
    """
    if os.name != "nt":
        return None
    sec = _runner()._security
    if sec is None or sec.sec_mode(cfg, "job_user") != "enforce":
        return None
    backend = _windows_confine(backend)

    def _audit(decision, reason, detail=""):
        try:
            sec.write_audit_entry(
                base_dir, "job_user", decision, reason,
                job_id=str(job_id), detail=str(detail), cfg=cfg,
                mode="enforce")
        except Exception:
            pass

    if getattr(proc, "job_object_applied", None) is \
            JOB_OBJECT_APPLIED:
        # The confinement spawn already assigned this process
        # to a Job Object at creation -- the same control, with
        # the same memory ceiling, this postspawn would apply.
        # A second assignment cannot succeed (a process sits in
        # one job hierarchy; the hosted leg answered error 5 and
        # every default-posture job was refused), and none is
        # needed: the record names the control that IS applied,
        # and the confinement release owns the handle's close.
        _audit("contained",
               getattr(backend, "STATUS_JOB_OBJECT", None)
               or "windows_job_object")
        return None
    try:
        if backend is None:
            raise RuntimeError(
                "windows confinement backend is unavailable")
        status, job_handle = backend.apply_windows_containment(
            getattr(proc, "_handle", None))
    except Exception as e:
        _audit("fallback", "windows_containment_failed", e)
        try:
            proc.kill()
        except Exception:
            pass
        raise _runner().JobRejected(
            "job_user containment could not be applied on win32 "
            "(%s); job refused under "
            "security.modes.job_user=enforce" % (e,))
    _audit("contained", status)

    def _release():
        try:
            backend.close_job_handle(job_handle)
        except Exception:
            pass

    return _release


def _job_user_spawn(cfg, base_dir, job_id, argv, cwd, env,
                    backend=None):
    """Spawn a job process under the Windows job_user control.

    Returns None when the seam does not apply -- every
    platform but win32 (read from sys.platform alone, the
    signal _confinement_spawn uses), and every job_user mode
    but enforce -- so the caller uses its ordinary spawn. On
    win32 at enforce it returns (proc, release): proc is the
    backend's suspended-spawn process (created suspended
    through the backend's own CreateProcessW, assigned to
    its Job Object, and only then resumed), marked
    JOB_OBJECT_APPLIED so _job_user_postspawn records the
    control instead of assigning a second time, and release
    closes its handles once the process has exited.

    This seam is what closes the Q168 race: the plain path
    used to spawn the child running through Popen and assign
    the Job Object afterwards, so a job that finished in
    milliseconds could have exited before the assignment
    reached it, and the postspawn refused a job whose output
    was already complete (AssignProcessToJobObject failed:
    5). A backend that cannot spawn refuses the job here,
    after the fallback record: under enforce a job never
    falls through to the running-then-assigned spawn this
    seam replaces. The success record is the postspawn's,
    naming only what was applied ("windows_job_object").
    """
    if sys.platform != "win32":
        return None
    sec = _runner()._security
    if sec is None or sec.sec_mode(cfg, "job_user") != "enforce":
        return None
    backend = _windows_confine(backend)

    def _audit(decision, reason, detail=""):
        try:
            sec.write_audit_entry(
                base_dir, "job_user", decision, reason,
                job_id=str(job_id), detail=str(detail), cfg=cfg,
                mode="enforce")
        except Exception:
            pass

    try:
        if backend is None:
            raise RuntimeError(
                "windows confinement backend is unavailable")
        spawn = getattr(backend, "spawn_job_object_process", None)
        if spawn is None:
            raise RuntimeError(
                "windows confinement backend has no suspended "
                "job-object spawn")
        proc = spawn(argv, cwd=cwd, env=env)
    except Exception as e:
        _audit("fallback", "windows_containment_failed", e)
        raise _runner().JobRejected(
            "job_user containment could not be applied on win32 "
            "(%s); job refused under "
            "security.modes.job_user=enforce" % (e,))
    try:
        # The spawn assigned the process to its Job Object at
        # creation; mark it so the job_user postspawn records
        # that control instead of assigning a second one (see
        # JOB_OBJECT_APPLIED above).
        proc.job_object_applied = JOB_OBJECT_APPLIED
    except Exception:
        pass

    def _release():
        try:
            proc.close()
        except Exception:
            pass

    return proc, _release


def confinement_startup_problem(cfg, platform=None, backend=None):
    """Why confinement on enforce cannot run here, or None.

    The win32 mirror of job_user_startup_problem. On Windows the
    confinement backend is runner/guard/windows_confine.py (Job
    Object + restricted token + low integrity -- see that
    module's docstring for what it does and does not provide), so
    on win32 the gate asks that backend's confinement probe
    whether it can engage. Only a REAL backend's probe is
    consulted: a simulated win32 (this host, the suite) answers
    the deterministic Linux-only refusal, exactly as job_user's
    gate does. The FreeBSD branch is the same shape against
    runner/guard/freebsd_confine.py (jail + no network + spawn
    resource limits), and the darwin branch against
    runner/guard/macos_confine.py (Seatbelt profile + no
    network + spawn resource limits). Off win32, FreeBSD and
    darwin this returns None and changes nothing: the bwrap
    gate in ops/main.py is the confinement gate there.
    """
    if platform is None:
        platform = sys.platform
    sec = _runner()._security
    if sec is None or sec.sec_mode(cfg, "confinement") != "enforce":
        return None
    if platform == "darwin":
        backend = _macos_confine(backend)
        if backend is not None and getattr(
                backend, "IS_MACOS_BACKEND", False):
            probe = getattr(backend, "macos_confinement_problem",
                            None)
            if probe is None:
                return ("confinement cannot engage on darwin: "
                        "the backend has no confinement probe")
            try:
                problem = probe(cfg)
            except Exception as e:  # a backend that cannot answer
                problem = str(e)    # has not shown it can engage
            if problem is None:
                return None
            return "confinement cannot engage on darwin: %s" % problem
        return ("confinement (bwrap) is Linux-only; "
                "this machine is %s" % platform)
    if platform.startswith("freebsd"):
        backend = _freebsd_confine(backend)
        if backend is not None and getattr(
                backend, "IS_FREEBSD_BACKEND", False):
            probe = getattr(backend, "freebsd_confinement_problem",
                            None)
            if probe is None:
                return ("confinement cannot engage on freebsd: "
                        "the backend has no confinement probe")
            try:
                problem = probe(cfg)
            except Exception as e:  # a backend that cannot answer
                problem = str(e)    # has not shown it can engage
            if problem is None:
                return None
            return "confinement cannot engage on freebsd: %s" % problem
        return ("confinement (bwrap) is Linux-only; "
                "this machine is %s" % platform)
    if platform != "win32":
        return None
    backend = _windows_confine(backend)
    if backend is not None and getattr(
            backend, "IS_WINDOWS_BACKEND", False):
        probe = getattr(backend, "windows_confinement_problem", None)
        if probe is None:
            return ("confinement cannot engage on win32: the "
                    "backend has no confinement probe")
        try:
            problem = probe(cfg)
        except Exception as e:  # a backend that cannot answer
            problem = str(e)    # has not shown it can engage
        if problem is None:
            return None
        return "confinement cannot engage on win32: %s" % problem
    return ("confinement (bwrap) is Linux-only; "
            "this machine is win32")


def _confinement_spawn(cfg, base_dir, job_id, argv, cwd, env,
                       backend=None):
    """Spawn a job process under platform confinement, or None.

    Returns None when the seam does not apply -- every platform
    but win32, FreeBSD and darwin, and every confinement mode
    but enforce -- so the caller uses its ordinary spawn. On
    win32 at enforce it returns (proc, release): proc is the
    Windows backend's confined process (the Popen subset exec
    drives), and release closes its handles once the process
    has exited.
    On FreeBSD at enforce the same shape comes from the FreeBSD
    backend (runner/guard/freebsd_confine.py): the jail is
    created first and the job started inside it via jexec, and
    release tears the jail down. The config rides to the spawn
    (the work mount, the read-only binds, the backend's own
    settings), and a read-only mount the backend adds for the
    job's interpreter is written into the record's detail, as
    the Linux sandbox's bind is. When the job_user seam is at
    enforce with a user named, that user is handed to the
    FreeBSD spawn, which applies it at the jail door (jexec -u)
    -- the Popen preexec demote cannot ride a spawn that
    replaces Popen, the same reason the Windows creation-time
    token exists. On darwin at enforce the same shape comes
    from the macOS backend (runner/guard/macos_confine.py):
    sandbox-exec applies the per-job Seatbelt profile to the
    launcher shim, which sets the spawn limits (and drops to
    the handed-over user, at the spawn door, the same reason)
    before it execs the job. A backend that cannot engage
    refuses the job here, after the fallback record: under
    enforce a job never falls through to an unconfined spawn.
    The success record names exactly the controls applied, in
    the backend's own status string ("windows: job_object +
    restricted_token + low_integrity" / "freebsd: jail +
    no_network + spawn_resource_limits", with the further
    controls a FreeBSD job's jail carried named between them /
    "macos: seatbelt_profile + no_network +
    spawn_resource_limits").
    """
    # The platform is sys.platform alone, the signal every
    # confinement gate beside this seam uses (_confinement_argv,
    # confinement_startup_problem). Deriving Windows from
    # os.name while darwin came from sys.platform let the two
    # disagree: on a darwin host a windows simulation that
    # patched os.name satisfied both branches at once, the
    # darwin branch won, and the windows backend was called
    # with the macOS branch's user argument (the test-macos
    # failures recorded in docs/steady/security/macos.md,
    # supposition S3). On a real host the signals always
    # agreed, so real-host behaviour is unchanged.
    is_windows = sys.platform == "win32"
    is_freebsd = sys.platform.startswith("freebsd")
    is_darwin = sys.platform == "darwin"
    if not is_windows and not is_freebsd and not is_darwin:
        return None
    sec = _runner()._security
    if sec is None or sec.sec_mode(cfg, "confinement") != "enforce":
        return None
    if is_darwin:
        backend = _macos_confine(backend)

        def _audit_mac(decision, reason, detail=""):
            try:
                sec.write_audit_entry(
                    base_dir, "confinement", decision, reason,
                    job_id=str(job_id), detail=str(detail), cfg=cfg,
                    mode="enforce")
            except Exception:
                pass

        user = None
        if sec.sec_mode(cfg, "job_user") == "enforce":
            secblock = cfg.get("security") \
                if isinstance(cfg, dict) else None
            secblock = secblock if isinstance(secblock, dict) else {}
            ju = secblock.get("job_user")
            ju = ju if isinstance(ju, dict) else {}
            if isinstance(ju.get("user"), str) and ju.get("user"):
                user = ju["user"]
        try:
            if backend is None:
                raise RuntimeError(
                    "macos confinement backend is unavailable")
            spawn = getattr(backend, "spawn_confined_process", None)
            if spawn is None:
                raise RuntimeError(
                    "macos confinement backend has no confined spawn")
            proc = spawn(argv, cwd=cwd, env=env, user=user)
        except Exception as e:
            _audit_mac("fallback", "macos_confinement_failed", e)
            raise _runner().JobRejected(
                "confinement could not be applied on darwin "
                "(%s); job refused under "
                "security.modes.confinement=enforce" % (e,))
        status = getattr(proc, "confinement_status", None) \
            or getattr(backend, "STATUS_CONFINEMENT", None) \
            or "macos: seatbelt_profile + no_network + spawn_resource_limits"
        _audit_mac("confined", status)

        def _release_mac():
            try:
                proc.close()
            except Exception:
                pass

        return proc, _release_mac
    if is_freebsd:
        backend = _freebsd_confine(backend)

        def _audit_fbsd(decision, reason, detail=""):
            try:
                sec.write_audit_entry(
                    base_dir, "confinement", decision, reason,
                    job_id=str(job_id), detail=str(detail), cfg=cfg,
                    mode="enforce")
            except Exception:
                pass

        user = None
        if sec.sec_mode(cfg, "job_user") == "enforce":
            secblock = cfg.get("security") \
                if isinstance(cfg, dict) else None
            secblock = secblock if isinstance(secblock, dict) else {}
            ju = secblock.get("job_user")
            ju = ju if isinstance(ju, dict) else {}
            if isinstance(ju.get("user"), str) and ju.get("user"):
                user = ju["user"]
        try:
            if backend is None:
                raise RuntimeError(
                    "freebsd confinement backend is unavailable")
            spawn = getattr(backend, "spawn_confined_process", None)
            if spawn is None:
                raise RuntimeError(
                    "freebsd confinement backend has no confined spawn")
            # The config rides to the spawn: the jail's work
            # mount, the operator's read-only binds and the
            # backend's own settings are read from it there.
            proc = spawn(argv, cwd=cwd, env=env, user=user, cfg=cfg)
        except Exception as e:
            _audit_fbsd("fallback", "freebsd_confinement_failed", e)
            raise _runner().JobRejected(
                "confinement could not be applied on freebsd "
                "(%s); job refused under "
                "security.modes.confinement=enforce" % (e,))
        # The record names the controls this job's jail carried:
        # the process object's own string, which says more than
        # the floor only where a control was applied.
        status = getattr(proc, "confinement_status", None) \
            or getattr(backend, "STATUS_CONFINEMENT", None) \
            or "freebsd: jail + no_network + spawn_resource_limits"
        notes = getattr(proc, "confinement_notes", None) or []
        _audit_fbsd("confined", status, "; ".join(notes))

        def _release_fbsd():
            try:
                proc.close()
            except Exception:
                pass

        return proc, _release_fbsd
    backend = _windows_confine(backend)

    def _audit(decision, reason, detail=""):
        try:
            sec.write_audit_entry(
                base_dir, "confinement", decision, reason,
                job_id=str(job_id), detail=str(detail), cfg=cfg,
                mode="enforce")
        except Exception:
            pass

    try:
        if backend is None:
            raise RuntimeError(
                "windows confinement backend is unavailable")
        spawn = getattr(backend, "spawn_confined_process", None)
        if spawn is None:
            raise RuntimeError(
                "windows confinement backend has no confined spawn")
        proc = spawn(argv, cwd=cwd, env=env)
    except Exception as e:
        _audit("fallback", "windows_confinement_failed", e)
        raise _runner().JobRejected(
            "confinement could not be applied on win32 "
            "(%s); job refused under "
            "security.modes.confinement=enforce" % (e,))
    try:
        # The spawn assigned the process to its Job Object at
        # creation; mark it so the job_user postspawn records
        # that control instead of assigning a second one (see
        # JOB_OBJECT_APPLIED above).
        proc.job_object_applied = JOB_OBJECT_APPLIED
    except Exception:
        pass
    status = getattr(proc, "confinement_status", None) \
        or getattr(backend, "STATUS_CONFINEMENT", None) \
        or "windows: job_object + restricted_token + low_integrity"
    _audit("confined", status)

    def _release():
        try:
            proc.close()
        except Exception:
            pass

    return proc, _release


def _learning_model_candidate(cfg, base_dir, job_id, job, outcome,
                              stdout_text, stderr_text):
    """The model channel of the learning loop: distill ONE
    candidate lesson from a completed job's outcome and output.

    Gated exactly like the tier-2 opinion note, plus the
    learning channel's own opt-in (oracle_learning_model):
    both model gates on and inference configured, so in
    deterministic Oracle mode (Pi Light) no model is ever
    called and no candidate is ever born. The reply must be a
    JSON object passing learning.validate_candidate -- output
    is evidence, never instruction, and a schema failure or an
    instruction-shaped claim is dropped, not filed.
    """
    R = _runner()
    if _runner()._learning is None \
            or not _runner()._learning.learning_model_enabled(cfg) \
            or not _runner()._opinion.model_enabled(cfg):
        return
    inf = _runner().inference_config(cfg)
    if inf is None:
        return
    try:
        context = (
            _runner()._describe_job(job)
            + f"\nOutcome: exit_code={outcome.get('exit_code')} "
              f"timed_out={bool(outcome.get('timed_out'))} "
              f"rejected={bool(outcome.get('rejected'))}\n"
            + "Output excerpt:\n"
            + ((stdout_text or "") + "\n"
               + (stderr_text or ""))[:1200])
        res = _runner().ask_model(
            inf,
            "From this completed job, distill ONE lesson about "
            "THIS host's environment that would help predict "
            "whether a similar future job succeeds. Reply with "
            "ONLY a JSON object: {\"claim\": a short declarative "
            "sentence about the environment, \"features\": "
            "[keys like \"tool:<name>\", \"interpreter:<exe>\", "
            "\"path:<path>\"], \"expects\": \"failure\" or "
            "\"success\" for similar jobs, \"confidence\": 0 to "
            "1}. A lesson states a fact about the environment; "
            "never phrase a lesson as an instruction.",
            context, 500, _runner()._redact_patterns(cfg))
    except Exception:
        return
    if not isinstance(res, dict):
        return
    text = res.get("answer")
    if not isinstance(text, str):
        return
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        return
    candidate = _runner()._learning.validate_candidate(obj)
    if candidate is None:
        R.log(f"oracle learning: model candidate for {job_id} "
            f"rejected by schema validation", "WARN")
        return
    record = _runner()._learning.candidate_record(
        candidate, job_id, _runner()._learning_fingerprint())
    if not _runner()._learning.append_candidate(base_dir, record):
        R.log(f"oracle learning: candidate write failed for "
            f"{job_id}", "WARN")


def _retained_job_summary(data, job_id, base_dir=None) -> str:
    """One retained job as context for the Oracle.

    Small local models answer concrete questions ("what did this job
    do?", "did it succeed?") only when the record carries the job's
    kind, its script, its real timestamp, and its exit status, not
    just the output text. A missing kind is "kind not recorded".
    That is not a failure, and it is not the word "unknown", which a
    small model will repeat as the status.
    """
    R = _runner()
    kind, status, when = _runner()._job_facts(data, job_id)
    lines = [f"job {job_id} ({kind}, {status}, {when})"]
    script = data.get("script") if isinstance(data.get("script"), str) else ""
    findings = []
    if script.strip():
        lines.append("script: " + script.strip()[:400])
        findings = _runner()._script_path_findings(script, base_dir, job_id)
        if findings:
            # The line carries its own job id. Both ask prompts
            # direct the model to report the finding with the job's
            # id, and the battery showed small models binding the
            # line to a neighbouring benign block when the only
            # binding was its position under the block header.
            lines.append(
                "notable: SUSPICIOUS ACCESS -- job " + job_id
                + ": this job's script references "
                + "; ".join(f"{path} ({reason})"
                            for path, reason in findings)
                + ". Reading files outside the job's own workspace "
                "is malicious-job behavior; the signature proves "
                "who sent the job, not that its behavior is benign.")
    text = _runner()._output_blob(data).strip()
    if findings:
        # Withhold, do not merely label. The Flag321 field tests
        # showed both small models handing a flagged job's raw
        # output back on request ("The value stored in flag.txt
        # is: 321") despite ASK_SYSTEM's no-reveal line, and the
        # 3B volunteering it unprompted: a pattern-based secret
        # scan cannot catch an arbitrary short value, and a value
        # that is not in the context cannot be repeated. The
        # retained record on disk is unchanged; only the Oracle's
        # summary withholds it, the same shape as an attested
        # result (attestations and a digest, not the output).
        digest = data.get("digest") if isinstance(
            data.get("digest"), str) else ""
        lines.append(
            "output: (withheld -- job " + job_id + " carries a "
            "notable finding, so its output may contain the material it "
            "accessed and is not shown to the Oracle"
            + (f"; {len(text)} chars, digest {digest[:16]}"
               if text else "; output was empty")
            + ")")
    else:
        if len(text) > 800:
            text = text[:800] + "\n..."
        lines.append("output:\n" + text if text else "output: (empty)")
    scan = data.get("artifact_scan")
    if isinstance(scan, list) and scan:
        lines.append("artifact scan:\n" + "\n".join(
            str(item)[:200] for item in scan[:20]))
    return "\n".join(lines)


