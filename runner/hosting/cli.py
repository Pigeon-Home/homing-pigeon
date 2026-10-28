#!/usr/bin/env python3
# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""homing-pigeon-host: put a runner on a machine the tenant pays for.

    homing-pigeon-host up --provider fly --token-env FLY_API_TOKEN \\
        --tenant alice --region iad --version <release> --blob @blob.json
    homing-pigeon-host up --provider fly --token-env FLY_API_TOKEN \\
        --tenant alice --region iad --version <release> \\
        --queue https://hp.example.workers.dev/t/alice
    homing-pigeon-host status
    homing-pigeon-host redeploy fly:e784... --version <release> --token-env FLY_API_TOKEN
    homing-pigeon-host rotate fly:e784... --token-env FLY_API_TOKEN
    homing-pigeon-host destroy fly:e784...
    homing-pigeon-host dispatch --target macos-ephemeral --tenant alice \\
        --token-env GITHUB_TOKEN --repo pigeon-home/hosted-runners \\
        --version <release> --blob-ref QUEUE_URL_ALICE

The provider token is read from the environment variable named by
--token-env and never written anywhere. The blob is the tenant's
one-blob config (shared secret, transport block, runner id,
workspace root); `rotate` mints a new shared secret, recreates the
machine with it, and prints the new secret once. The inventory is a
JSON file (default ~/.homing-pigeon/hosting.json) that enforces one
resident machine per tenant per provider.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets as _secrets
import sys

try:
    from runner.hosting import base, bootstrap, inventory as _inv
    from runner.hosting.httpdoor import UrllibHttp
    from runner.hosting import digitalocean, fly, github_actions, hetzner
    from runner.ops.install import read_config_blob
except ImportError:  # script mode: python3 runner/hosting/cli.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    from hosting import base, bootstrap, inventory as _inv  # type: ignore
    from hosting.httpdoor import UrllibHttp  # type: ignore
    from hosting import digitalocean, fly, github_actions, hetzner  # type: ignore
    from ops.install import read_config_blob  # type: ignore

PROVIDERS = {"fly": fly.FlyMachines, "hetzner": hetzner.HetznerCloud,
             "digitalocean": digitalocean.DigitalOcean}
DEFAULT_SIZE = {"fly": "shared-cpu-1x", "hetzner": "cx23",
                "digitalocean": "s-1vcpu-512mb-10gb"}


def _token(name):
    if not name:
        raise SystemExit("error: --token-env NAME is required (the token "
                         "is read from that variable, never from argv)")
    tok = os.environ.get(name)
    if not tok:
        raise SystemExit(f"error: environment variable {name} is empty")
    return tok


def _inventory(path):
    return _inv.Inventory(os.path.expanduser(
        path or "~/.homing-pigeon/hosting.json"))


def _provider(name, token, http=None, app=None):
    cls = PROVIDERS.get(name)
    if cls is None:
        raise SystemExit(f"error: unknown provider {name!r} "
                         f"(known: {', '.join(sorted(PROVIDERS))})")
    http = http or UrllibHttp()
    if name == "fly":
        return cls(http, token, app=app)
    return cls(http, token)


def _split_key(key):
    prov, _, mid = str(key).partition(":")
    if not prov or not mid:
        raise SystemExit("error: machine keys look like provider:id")
    return prov, mid


def _apply_queue(blob, args):
    """--queue URL: the hosted queue as the runner's transport, so a
    runner and its pipe arrive in one command with no hand-written
    blob. The runner token comes from --queue-token-env (never argv)
    and is written into the blob, which the machine keeps 0600 beside
    the shared secret: a system service has no environment of its own
    to read a token_env from. Returns True when the queue was set."""
    url = getattr(args, "queue", None)
    if not url:
        return False
    url = url.strip().rstrip("/")
    if not url.startswith("https://") or "/t/" not in url:
        raise SystemExit("error: --queue is the tenant's queue base, "
                         "https://<worker>/t/<tenant>")
    name = getattr(args, "queue_token_env", None) or "HP_RUNNER_TOKEN"
    tok = os.environ.get(name)
    if not tok:
        raise SystemExit(f"error: --queue needs the runner token in "
                         f"environment variable {name}")
    transports = blob.get("transports")
    transports = list(transports) if isinstance(transports, list) else []
    if "queues" not in transports:
        transports.append("queues")
    blob["transports"] = transports
    block = blob.get("transport_queues")
    block = dict(block) if isinstance(block, dict) else {}
    block["url"] = url
    block["token"] = tok
    block.pop("token_env", None)
    blob["transport_queues"] = block
    blob.setdefault("workspace_root", "/data/work")
    return True


def cmd_up(args, http=None, sleep=None):
    token = _token(args.token_env)
    blob = read_config_blob(args.blob)
    queued = _apply_queue(blob, args)
    secret_env = getattr(args, "secret_env", None)
    if secret_env:
        value = os.environ.get(secret_env)
        if not value:
            raise SystemExit(f"error: environment variable {secret_env} "
                             f"is empty")
        blob["shared_secret"] = value
    if "shared_secret" not in blob:
        blob["shared_secret"] = _secrets.token_hex(32)
        print("blob: no shared_secret given; one was generated (see below)")
        if queued:
            print("queue: set the same value as the Worker's HMAC_SECRET "
                  "(wrangler secret put HMAC_SECRET), or the Worker "
                  "refuses every job this runner would accept")
    blob.setdefault("runner_id", f"{args.tenant}-{_secrets.token_hex(4)}")
    spec = base.MachineSpec(args.tenant, args.region,
                            args.size or DEFAULT_SIZE.get(args.provider),
                            args.version, blob, profile=args.profile,
                            image=args.image)
    inv = _inventory(args.inventory)
    if inv.resident_for(args.tenant, args.provider):
        raise SystemExit(f"error: tenant {args.tenant!r} already has a "
                         f"resident machine on {args.provider}; use "
                         f"redeploy or destroy")
    provider = _provider(args.provider, token, http=http)
    machine = provider.create(spec)
    rec = inv.place(machine, args.tenant)
    inv.save()
    if not args.no_wait:
        kw = {"sleep": sleep} if sleep else {}
        machine = provider.wait_running(machine.id, timeout=args.wait, **kw)
        inv.update(machine)
        inv.save()
    shown = {"machine": _inv.Inventory.key(machine.provider, machine.id),
             "state": machine.state, "region": machine.region,
             "ip": machine.ip, "tenant": rec["tenant"],
             "shared_secret": blob["shared_secret"]}
    if queued:
        shown["queue"] = blob["transport_queues"]["url"]
    print(json.dumps(shown, indent=2))
    return 0


def cmd_status(args, http=None):
    inv = _inventory(args.inventory)
    rows = sorted(inv.machines.values(),
                  key=lambda r: (r.get("tenant") or "", r.get("id") or ""))
    if not rows:
        print("no machines")
        return 0
    for r in rows:
        print(f"{r['provider']}:{r['id']}  tenant={r.get('tenant')}  "
              f"state={r.get('state')}  version={r.get('version')}  "
              f"region={r.get('region')}  ip={r.get('ip') or '-'}  "
              f"seen={r.get('last_seen')}")
    if inv.dispatches:
        print(f"{len(inv.dispatches)} ephemeral dispatch(es) recorded")
    return 0


def cmd_destroy(args, http=None):
    prov, mid = _split_key(args.machine)
    token = _token(args.token_env)
    inv = _inventory(args.inventory)
    rec = inv.machines.get(_inv.Inventory.key(prov, mid))
    provider = _provider(prov, token, http=http,
                         app=(rec or {}).get("raw_app") or
                         (f"hp-{rec['tenant']}" if rec and prov == "fly"
                          else None))
    provider.destroy(mid)
    inv.forget(prov, mid)
    inv.save()
    print(f"destroyed {prov}:{mid}")
    return 0


def cmd_redeploy(args, http=None, sleep=None, new_secret=None):
    """Recreate the machine with a new version and/or blob. The old
    machine is destroyed only after the new one is running, so the
    tenant's result stream has one short gap, not a hole."""
    prov, mid = _split_key(args.machine)
    token = _token(args.token_env)
    inv = _inventory(args.inventory)
    rec = inv.machines.get(_inv.Inventory.key(prov, mid))
    if rec is None:
        raise SystemExit(f"error: {args.machine} is not in the inventory")
    blob = read_config_blob(args.blob) if args.blob else {}
    _apply_queue(blob, args)
    if new_secret:
        blob["shared_secret"] = new_secret
    if "shared_secret" not in blob:
        raise SystemExit("error: redeploy needs the tenant's blob "
                         "(--blob) carrying shared_secret, or rotate")
    version = args.version or rec.get("version")
    spec = base.MachineSpec(rec["tenant"], rec.get("region"),
                            args.size or DEFAULT_SIZE.get(prov), version,
                            blob, profile=args.profile, image=args.image,
                            name=f"hp-{rec['tenant']}-{_secrets.token_hex(2)}")
    provider = _provider(prov, token, http=http,
                         app=f"hp-{rec['tenant']}" if prov == "fly" else None)
    inv.forget(prov, mid)  # make room: one resident per tenant
    fresh = provider.create(spec)
    inv.place(fresh, rec["tenant"])
    inv.save()
    kw = {"sleep": sleep} if sleep else {}
    fresh = provider.wait_running(fresh.id, timeout=args.wait, **kw)
    inv.update(fresh)
    provider.destroy(mid)
    inv.save()
    print(json.dumps({"machine": _inv.Inventory.key(fresh.provider, fresh.id),
                      "replaced": f"{prov}:{mid}", "version": version,
                      "state": fresh.state, "ip": fresh.ip}, indent=2))
    return 0


def cmd_rotate(args, http=None, sleep=None):
    new = _secrets.token_hex(32)
    rc = cmd_redeploy(args, http=http, sleep=sleep, new_secret=new)
    if rc == 0:
        print(json.dumps({"new_shared_secret": new,
                          "note": "hand this to the tenant's SI once; "
                                  "it is not stored here"}, indent=2))
    return rc


def cmd_dispatch(args, http=None, sleep=None):
    token = _token(args.token_env)
    owner, _, repo = (args.repo or "").partition("/")
    if not owner or not repo:
        raise SystemExit("error: --repo owner/name is required")
    gh = github_actions.GitHubActions(http or UrllibHttp(), token, owner,
                                      repo, workflow=args.workflow,
                                      ref=args.ref)
    d = gh.dispatch(args.target, args.tenant, args.version, args.blob_ref,
                    drain_jobs=args.drain, drain_seconds=args.drain_seconds,
                    ticket=getattr(args, "ticket", None))
    inv = _inventory(args.inventory)
    if not args.no_wait:
        kw = {"sleep": sleep} if sleep else {}
        gh.wait(d, timeout=args.wait, **kw)
    inv.record_dispatch(d, args.tenant)
    inv.save()
    print(json.dumps(d.to_record(), indent=2))
    return 0


def _write_private(path, text):
    """Create `path` 0600 with `text`; refuse to overwrite a file."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)


def queue_tenant_record(si_token, runner_token, secret, jobs_per_hour,
                        bytes_per_day):
    """The TENANTS KV record the Worker reads for one tenant: the two
    bearer tokens as SHA-256 hex, the shared secret for the HMAC gate,
    and the quota."""
    import hashlib
    return {"si_token_sha256": hashlib.sha256(si_token.encode()).hexdigest(),
            "runner_token_sha256":
                hashlib.sha256(runner_token.encode()).hexdigest(),
            "hmac_secret": secret,
            "quota": {"jobs_per_hour": jobs_per_hour,
                      "bytes_per_day": bytes_per_day}}


def cmd_queue_tenant(args):
    """Mint one hosted-queue tenant: an SI token, a runner token and
    (unless --secret-env names one) a shared secret. Nothing secret is
    printed or put on a command line: the three go to <dir>/<tenant>.env
    and the Worker's KV record to <dir>/<tenant>.kv.json, both 0600 and
    never overwritten. Stdout is the next commands."""
    import re
    slug = args.tenant
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", slug or ""):
        raise SystemExit("error: --tenant is 1 to 64 of A-Z a-z 0-9 . _ - "
                         "(the Worker's slug rule), starting alphanumeric")
    if args.jobs_per_hour < 1 or args.bytes_per_day < 1:
        raise SystemExit("error: the quota must allow at least one job "
                         "and one byte")
    secret = None
    if args.secret_env:
        secret = os.environ.get(args.secret_env)
        if not secret:
            raise SystemExit(f"error: environment variable "
                             f"{args.secret_env} is empty")
    secret = secret or _secrets.token_hex(32)
    si, runner = _secrets.token_urlsafe(32), _secrets.token_urlsafe(32)
    folder = os.path.expanduser(args.dir)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    env_path = os.path.join(folder, f"{slug}.env")
    kv_path = os.path.join(folder, f"{slug}.kv.json")
    for p in (env_path, kv_path):
        if os.path.exists(p):
            raise SystemExit(f"error: {p} exists; a tenant is minted once "
                             f"(move it away to mint again)")
    record = queue_tenant_record(si, runner, secret, args.jobs_per_hour,
                                 args.bytes_per_day)
    _write_private(kv_path, json.dumps(record, indent=2) + "\n")
    _write_private(env_path,
                   f"# hosted queue tenant {slug}: keep this file private\n"
                   f"HP_SI_TOKEN={si}\nHP_RUNNER_TOKEN={runner}\n"
                   f"HP_SECRET={secret}\n")
    base = (args.worker or "https://<worker>").rstrip("/")
    print(json.dumps({"tenant": slug, "queue": f"{base}/t/{slug}",
                      "secrets_file": env_path, "kv_record_file": kv_path},
                     indent=2))
    print(f"""
Next:
  wrangler kv key put --binding TENANTS {slug} --path {kv_path}
  set -a; . {env_path}; set +a
  homing-pigeon-host up --provider fly --token-env FLY_API_TOKEN \\
      --tenant {slug} --region iad --version <release> \\
      --queue {base}/t/{slug} --secret-env HP_SECRET
The SI holds HP_SI_TOKEN and HP_SECRET; the runner gets HP_RUNNER_TOKEN
through --queue. Delete {kv_path} once the KV put has run.""")
    return 0


def build_parser():
    ap = argparse.ArgumentParser(
        prog="homing-pigeon-host",
        description="Put a Homing Pigeon runner on a machine the tenant "
                    "pays for; redeploy, rotate, destroy; dispatch "
                    "ephemeral runs.")
    ap.add_argument("--inventory", default=None, metavar="PATH",
                    help="inventory file (default ~/.homing-pigeon/hosting.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, token=True):
        if token:
            p.add_argument("--token-env", required=True, metavar="NAME",
                           help="environment variable holding the provider token")
        p.add_argument("--wait", type=int, default=300, metavar="SECONDS",
                       help="how long to wait for running (default 300)")
        p.add_argument("--no-wait", action="store_true",
                       help="return as soon as the request is accepted")

    def queue_args(p):
        p.add_argument("--queue", default=None, metavar="URL",
                       help="the hosted queue as the transport: the "
                            "tenant's base, https://<worker>/t/<tenant>")
        p.add_argument("--queue-token-env", default=None, metavar="NAME",
                       help="environment variable holding the runner "
                            "token for --queue (default HP_RUNNER_TOKEN)")

    up = sub.add_parser("up", help="provision one resident runner")
    up.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    up.add_argument("--tenant", required=True)
    up.add_argument("--region", required=True,
                    help="fly: iad, hetzner: nbg1, digitalocean: nyc3, ...")
    up.add_argument("--version", required=True, help="release to pin, e.g. the version in pyproject.toml")
    up.add_argument("--blob", default=None, metavar="JSON|@FILE|env:NAME",
                    help="the one-blob config (--config-json shape)")
    up.add_argument("--size", default=None)
    up.add_argument("--image", default=None, help="container image (fly)")
    up.add_argument("--profile", default="hosted")
    up.add_argument("--secret-env", default=None, metavar="NAME",
                    help="environment variable holding the shared secret "
                         "to use (with --queue: the Worker's HMAC_SECRET)")
    queue_args(up)
    common(up)

    qt = sub.add_parser("queue-tenant",
                        help="mint a hosted-queue tenant: tokens, secret, "
                             "KV record")
    qt.add_argument("--tenant", required=True)
    qt.add_argument("--dir", default="~/.homing-pigeon/tenants",
                    help="where the 0600 secrets and KV record files go")
    qt.add_argument("--worker", default=None, metavar="URL",
                    help="the Worker's base URL, for the printed commands")
    qt.add_argument("--secret-env", default=None, metavar="NAME",
                    help="environment variable holding an existing shared "
                         "secret (default: a new one)")
    qt.add_argument("--jobs-per-hour", type=int, default=600)
    qt.add_argument("--bytes-per-day", type=int, default=256 * 1024 * 1024)

    st = sub.add_parser("status", help="list the inventory")

    for name, fn_help in (("redeploy", "recreate with a new version or blob"),
                          ("rotate", "mint a new shared secret and recreate")):
        p = sub.add_parser(name, help=fn_help)
        p.add_argument("machine", help="provider:id")
        p.add_argument("--version", default=None)
        p.add_argument("--blob", default=None, metavar="JSON|@FILE|env:NAME")
        p.add_argument("--size", default=None)
        p.add_argument("--image", default=None)
        p.add_argument("--profile", default="hosted")
        queue_args(p)
        common(p)

    de = sub.add_parser("destroy", help="destroy a machine and forget it")
    de.add_argument("machine", help="provider:id")
    de.add_argument("--token-env", required=True, metavar="NAME")

    di = sub.add_parser("dispatch", help="one ephemeral run on GitHub Actions")
    di.add_argument("--target", required=True,
                    choices=sorted(github_actions.RUNNER_LABELS))
    di.add_argument("--tenant", required=True)
    di.add_argument("--version", required=True)
    di.add_argument("--repo", required=True, help="owner/name of the workflow repo")
    di.add_argument("--workflow", default="hp-ephemeral.yml")
    di.add_argument("--ref", default="main")
    di.add_argument("--blob-ref", required=True,
                    help="the secret name or queue URL the workflow reads the blob from")
    di.add_argument("--ticket", default=None,
                    help="run ticket (default: a fresh one); the workflow's "
                         "run-name must be 'hp <ticket>'")
    di.add_argument("--drain", type=int, default=1)
    di.add_argument("--drain-seconds", type=int, default=900)
    common(di)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "up":
            return cmd_up(args)
        if args.cmd == "queue-tenant":
            return cmd_queue_tenant(args)
        if args.cmd == "status":
            return cmd_status(args)
        if args.cmd == "destroy":
            return cmd_destroy(args)
        if args.cmd == "redeploy":
            return cmd_redeploy(args)
        if args.cmd == "rotate":
            return cmd_rotate(args)
        if args.cmd == "dispatch":
            return cmd_dispatch(args)
    except base.AuthError as e:
        print(f"auth: {e}", file=sys.stderr)
        return 3
    except base.RateLimited as e:
        print(f"rate limited: {e} (retry after {e.retry_after})", file=sys.stderr)
        return 4
    except base.ProviderError as e:
        print(f"provider: {e}", file=sys.stderr)
        return 5
    except _inv.IsolationError as e:
        print(f"isolation: {e}", file=sys.stderr)
        return 6
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
