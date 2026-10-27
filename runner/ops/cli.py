"""Argument parser for the runner CLI.

Extracted from runner.py to keep that file under the line budget.
"""
import argparse

try:
    from runner._version import __version__
except ImportError:  # running from inside runner/ as __main__
    try:
        from _version import __version__
    except ImportError:
        __version__ = "unknown"
try:
    from runner.wire import transports as _transports
except ImportError:
    try:
        from wire import transports as _transports  # type: ignore
    except ImportError:
        _transports = None


def _transports_arg(text):
    """argparse type for --transports: 'file,nats' -> ['file',
    'nats']. Names are transport EXTENSION names: shape is
    checked here, at startup; whether a name has a loadable
    extension is discovery's question at supervisor start (any
    valid drop-in manifest counts, registered or not)."""
    names = [p.strip() for p in str(text).split(",") if p.strip()]
    probe = {"transports": names}
    try:
        if _transports is not None:
            _transports.enabled_transports(probe)
        elif not names:
            raise ValueError("empty")
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None
    if not names:
        raise argparse.ArgumentTypeError("name at least one transport")
    return names




def build_parser():
    ap = argparse.ArgumentParser(
        description=(
            "Your cloud SI is smart, but it can't touch your "
            "computer. This is\n"
            "the agent that lives here: it polls a mailbox for "
            "signed jobs,\n"
            "runs them on this machine, and mails the results "
            "back.\n"
            "The signature is the only gate."),
        epilog=(
            "examples:\n"
            "  runner.py --config config.json\n"
            "      poll the mailbox and run signed jobs\n"
            "  runner.py --config config.json --once --dry-run -v\n"
            "      one cycle, narrated; verify only, change "
            "nothing\n"
            "  runner.py --oracle-mode deterministic "
            "--inspect board\n"
            "      read the board the Pi Light way: no model "
            "involved\n"
            "  runner.py --oracle\n"
            "      chat with the Oracle in your browser\n"
            "  runner.py --oracle-cli\n"
            "      the same chat, in this terminal\n"
            "\n"
            "config.json holds the durable settings. Every "
            "override above\n"
            "replaces one value for this process only and never "
            "rewrites\n"
            "the file; a flag beats a later config edit."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version",
                    version="%(prog)s " + __version__)
    g = ap.add_argument_group(
        "running",
        "The everyday switches. --no-send sits here on purpose,\n"
        "away from the other off-switches, so this page never\n"
        "reads as a turn-everything-off menu.")
    g.add_argument("--config", default="config.json", metavar="PATH",
                   help="config file to load (default: config.json)")
    g.add_argument("--once", action="store_true",
                   help="run a single poll cycle, then exit")
    g.add_argument("--drain", type=int, default=0, metavar="N",
                   help="with --once: keep polling until N jobs have "
                        "run, then exit (an ephemeral box's whole life; "
                        "0 = one cycle)")
    g.add_argument("--drain-seconds", type=int, default=0, metavar="T",
                   help="with --once: stop draining after T seconds "
                        "even if fewer jobs arrived (0 = no time cap)")
    g.add_argument("--dry-run", action="store_true",
                   help="verify signatures and print what would run; "
                        "execute nothing, send nothing, change nothing")
    g.add_argument("--no-send", action="store_true",
                   help="execute jobs but do not send result messages "
                        "(results go to the log only)")
    g.add_argument("--setup", action="store_true",
                   help="first-run setup in the browser: sign in, "
                        "set the shared secret, write config; then "
                        "start normally")
    g.add_argument("--pdb", action="store_true",
                   help="drop into pdb on unhandled exceptions")
    g = ap.add_argument_group(
        "this computer",
        "On startup the runner looks at file and folder names in\n"
        "your home Documents, Desktop, and Downloads. A legal,\n"
        "tax, or medical name prints a warning. The warning does\n"
        "not say how to turn that check off.")
    g.add_argument("--ignore-personal-documents", action="store_true",
                   help="skip that check and do not print the warning")
    g = ap.add_argument_group(
        "one-process overrides",
        "Each flag replaces one config value for this process\n"
        "only. config.json is never rewritten, and a flag beats\n"
        "a later config edit.")
    g.add_argument("--workers", type=int, default=None,
                   metavar="COUNT",
                   help="concurrent job executions (default: 1)")
    g.add_argument("--poll-interval", type=int, default=None,
                   metavar="SECONDS",
                   help="seconds between poll cycles (default: 20)")
    g.add_argument("--timeout", type=int, default=None,
                   metavar="SECONDS",
                   help="default per-job timeout in seconds "
                        "(default: 300)")
    g.add_argument("--max-output-bytes", type=int, default=None,
                   metavar="BYTES",
                   help="truncate stdout/stderr beyond this many "
                        "bytes (default: 100000)")
    g.add_argument("--max-job-age", type=int, default=None,
                   metavar="SECONDS",
                   help="reject jobs older than this many seconds "
                        "(default: 3600)")
    g.add_argument("--retention-days", type=int, default=None,
                   metavar="DAYS",
                   help="days to keep retained job outputs "
                        "(default: 7; 0 keeps them forever)")
    g.add_argument("--task-timeout", type=int, default=None,
                   metavar="SECONDS",
                   help="seconds before a claimed board task "
                        "returns to open (default: 86400)")
    g.add_argument("--max-query-budget", type=int, default=None,
                   metavar="COUNT",
                   help="most follow-up queries answered for one "
                        "job (default: 8)")
    g.add_argument("--max-queries-per-hour", type=int, default=None,
                   metavar="COUNT",
                   help="rate limit on follow-up queries "
                        "(default: 0 = no limit)")
    g.add_argument("--max-result-view",
                   choices=["full", "redacted", "summary", "attested"],
                   default=None, metavar="MODE",
                   help="narrowest result view the runner will "
                        "return (default: full)")
    g = ap.add_argument_group(
        "modes",
        "Feature modes for this process; the same values the\n"
        "config file takes.")
    g.add_argument("--judge", choices=["off", "advisory", "enforce"],
                   default=None, metavar="MODE",
                   help="pre-execution judge: advisory attaches "
                        "reasons and still runs the job; enforce "
                        "blocks denylisted jobs (default: off)")
    g.add_argument("--dag-mode",
                   choices=["off", "advisory", "enforce"],
                   default=None, metavar="MODE",
                   help="board dependencies: advisory hands a "
                        "task out with a warning; enforce withholds "
                        "it until its requires are done "
                        "(default: off)")
    g.add_argument("--oracle-mode",
                   choices=["llm", "deterministic"],
                   default=None, metavar="MODE",
                   help="Oracle mode: llm, or deterministic -- "
                        "the Pi Light mode, no model is called "
                        "(default: llm)")
    g.add_argument("--protocol-v2", action="store_true",
                   default=None,
                   help="before a job runs, send a version 2 "
                        "determination when the Oracle does not "
                        "expect a clean pass, and on a "
                        "deterministic Oracle ask the question "
                        "a local model would have been asked "
                        "(default: off)")
    g.add_argument("--answer-only", action="store_true",
                   default=None,
                   help="answer version 2 questions and do not "
                        "execute jobs; the laptop that thinks "
                        "for a Pi (default: off)")
    g.add_argument("--oracle-opinion", default=None, metavar="MODE",
                   choices=["off", "diagnose", "advise", "repair"],
                   help="Oracle opinion latitude for this process: "
                        "off, diagnose, advise, repair "
                        "(default: repair)")
    g.add_argument("--remediation-mode", default=None, metavar="MODE",
                   choices=["off", "deterministic", "oracle"],
                   help="remediation for this process: off (watch, "
                        "record, page), deterministic (tripwires "
                        "act), oracle (the model may also order a "
                        "kill) (default: deterministic)")
    g.add_argument("--require-review", action="store_true",
                   default=None,
                   help="completed board tasks wait in "
                        "pending_review until approved")
    g.add_argument("--no-require-review", action="store_false",
                   dest="require_review",
                   help="completed board tasks finish at once; "
                        "overrides --require-review")
    g.add_argument("--faster", action="store_true",
                   help="use qwen2.5:3b for this process, the "
                        "faster small model. The model in "
                        "config.json is left as it is.")
    g = ap.add_argument_group(
        "local signals",
        "Signed envelopes from this box's own senses.\n"
        "No mailbox involved.")
    g.add_argument("--local-signals", action="store_true",
                   default=None,
                   help="accept signed local signals from this "
                        "box's senses (default: on)")
    g.add_argument("--no-local-signals", action="store_false",
                   dest="local_signals",
                   help="refuse local signals; overrides "
                        "--local-signals")
    g.add_argument("--local-signal-port", type=int, default=None,
                   metavar="PORT",
                   help="loopback port for direct local signals "
                        "(default: 39271; 0 = no listener)")
    g.add_argument("--wake-cooldown", type=int, default=None,
                   metavar="SECONDS",
                   help="minimum seconds between Oracle wake "
                        "briefings (default: 900)")
    g = ap.add_argument_group(
        "logging",
        "One human-readable log. Verbose adds lines;\n"
        "it never changes the existing ones.")
    g.add_argument("-v", "--verbose", action="count", default=None,
                   help="narrate the decision points (poll, "
                        "ingest, wake gate, judge, board); repeat "
                        "for more (-vv). Overrides config "
                        "\"verbose\"")
    g.add_argument("--quiet", action="store_false", dest="verbose",
                   default=argparse.SUPPRESS,
                   help="startup block and job results only "
                        "(cap 50 lines/min); overrides -v and "
                        "config")
    g.add_argument("--log-max-bytes", type=int, default=None,
                   metavar="BYTES",
                   help="rotate runner.log at this size "
                        "(default: 33554432)")
    g.add_argument("--log-backups", type=int, default=None,
                   metavar="COUNT",
                   help="rotated runner.log files to keep "
                        "(default: 4)")
    g.add_argument("--oracle-log", action="store_true", default=None,
                   help="record full inference exchanges in "
                        "oracle.log")
    g.add_argument("--no-oracle-log", action="store_false",
                   dest="oracle_log",
                   help="do not write oracle.log; overrides "
                        "--oracle-log")
    g.add_argument("--oracle-log-max-bytes", type=int, default=None,
                   metavar="BYTES",
                   help="rotate oracle.log at this size "
                        "(default: 536870912)")
    g.add_argument("--oracle-log-backups", type=int, default=None,
                   metavar="COUNT",
                   help="rotated oracle.log files to keep "
                        "(default: 4)")
    g.add_argument("--transports", type=_transports_arg, default=None,
                   metavar="LIST",
                   help="job transports for this process, "
                        "comma-separated: " + ", ".join(
                            getattr(_transports, "FIRST_PARTY_TRANSPORTS",
                                    ("email",)) if _transports else ("email",))
                        + " (default: email)")
    g = ap.add_argument_group(
        "debug: cleartext",
        "Off unless you pass the flag. A cleartext job is still "
        "HMAC-SHA-384 signed with the shared secret. It is "
        "readable by every hop. There is no config key for this.")
    g.add_argument("--allow-cleartext", action="store_true",
                   help="accept an HMAC-signed job that is not "
                        "encrypted. Without this flag a cleartext "
                        "job is refused. The shared secret is "
                        "still required.")
    g = ap.add_argument_group(
        "the Oracle",
        "Talk to the Oracle instead of polling the mailbox.")
    g.add_argument("--oracle", action="store_true",
                   help="open a loopback chat with the Oracle in "
                        "your browser")
    g.add_argument("--oracle-cli", action="store_true",
                   help="chat with the Oracle in the terminal "
                        "(same chat, no browser)")
    g.add_argument("--oracle-port", type=int, default=11436,
                   metavar="PORT",
                   help="port for --oracle (default: 11436, "
                        "127.0.0.1 only)")
    g = ap.add_argument_group(
        "reports and harnesses",
        "Run one thing, print it, exit.\n"
        "None of these poll the mailbox.")
    g.add_argument("--inspect",
                   choices=["board", "budget", "job", "outbox", "redact",
                            "review", "sources"],
                   help="read local Oracle state and exit; "
                        "no mailbox")
    g.add_argument("--job-id", default=None, metavar="ID",
                   help="job id for --inspect job")
    g.add_argument("--fetch-sources", action="store_true",
                   help="fetch every extension's code and declared "
                        "upstream sources for the Oracle now, in the "
                        "foreground, retrying what failed; print "
                        "what happened and exit")
    g.add_argument("--run-variant", default=None, metavar="FILE",
                   help="run one locally supplied fuzz variant "
                        "job from FILE through validation and "
                        "confined execution, print its outcome "
                        "as JSON, and exit; no mailbox needed. "
                        "The job-fuzz sense's execution door: "
                        "variants are unsigned local artifacts "
                        "and are never admitted through the job "
                        "path")
    g.add_argument("--audit-report", action="store_true",
                   help="print a summary of the security audit "
                        "log and exit; no mailbox needed")
    g.add_argument("--remediation-release", default=None,
                   metavar="JOB_ID",
                   help="release a quarantined job's outputs "
                        "back out of quarantine (one recorded "
                        "act) and exit; no mailbox needed")
    g.add_argument("--since", default=None, metavar="WINDOW",
                   help="with --audit-report: only entries from "
                        "the last window, e.g. 14d or 48h "
                        "(default: 30d)")
    g.add_argument("--key", default=None, metavar="KEY_ID",
                   help="with --audit-report: only entries for "
                        "this key")
    g.add_argument("--feature", default=None, metavar="NAME",
                   help="with --audit-report: only entries for "
                        "this security feature")
    g.add_argument("--posture", action="store_true",
                   help="report the runner's security posture "
                        "and exit; no mailbox needed")
    g.add_argument("--diagnose", action="store_true",
                   help="run the diagnostic harness against this "
                        "config and exit (see "
                        "docs/use/local-si-test.md)")
    g.add_argument("--diagnose-timeout", type=int, default=None,
                   metavar="SECONDS",
                   help="with --diagnose: seconds to wait for "
                        "the round-trip result (default: 120)")
    g.add_argument("--local-test", action="store_true",
                   help="run the local SI test harness "
                        "(no mailbox needed)")
    g.add_argument("--browser", action="store_true",
                   help="with --local-test: chat via Open WebUI "
                        "instead of the terminal")
    return ap
