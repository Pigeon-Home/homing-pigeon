#!/usr/bin/env python3
"""homing-pigeon-host: put a runner on a machine the tenant pays for.

    homing-pigeon-host up --provider fly --token-env FLY_API_TOKEN \\
        --tenant alice --region iad --version <release> --blob @blob.json
    homing-pigeon-host status
    homing-pigeon-host redeploy fly:e784... --version <release>
    homing-pigeon-host rotate fly:e784...
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


def cmd_up(args, http=None, sleep=None):
    token = _token(args.token_env)
    blob = read_config_blob(args.blob)
    if "shared_secret" not in blob:
        blob["shared_secret"] = _secrets.token_hex(32)
        print("blob: no shared_secret given; one was generated (see below)")
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
    print(json.dumps({"machine": _inv.Inventory.key(machine.provider,
                                                     machine.id),
                      "state": machine.state, "region": machine.region,
                      "ip": machine.ip, "tenant": rec["tenant"],
                      "shared_secret": blob["shared_secret"]}, indent=2))
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
    common(up)

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
