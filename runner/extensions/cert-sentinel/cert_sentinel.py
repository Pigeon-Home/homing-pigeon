#!/usr/bin/env python3
"""Cert Sentinel: a Homing Pigeon user extension (example sense).

Watches certificates -- files on disk and, optionally, live TLS
endpoints -- for expiry and identity change, and files what it
finds as sensor alerts for the Oracle. It comes from PKI work:
the certificates a fleet trusts are quiet until they are not,
and the two ways they hurt are expiring unrenewed and being
replaced by something nobody expected. Each alert names one
of the signals declared in extension.json:

- cert_expiring  a certificate's remaining life fell to the
                 warn_days tunable (default 30) or below
- cert_critical  a certificate's remaining life fell to the
                 critical_days tunable (default 7) or below,
                 or it has already expired
- cert_changed   a known source now presents a different
                 serial, issuer, or subject -- the certificate
                 was reissued or swapped

The machinery is deliberately boring, in the Pi Health
example's shape. read_live() is the only function that touches
the platform; it returns one readings dict, and decide() --
readings plus manifest plus last pass's state, out come alerts
and the new state -- is pure, so the whole decision surface is
testable on any machine. Expiry is a band discipline: a
certificate files once when it enters the warn band and once
more when it enters the critical band, and stays quiet while
its band holds. A certificate seen for the first time files
its band alert if it is already in warn or critical (a
first-sight expired certificate is news, not a baseline),
but no cert_changed -- there is nothing it changed from.

Sources, all optional and capability-based -- a source that
cannot be read yields no record, which is never an error:

- cert files: the cert_files tunable names PEM files on disk,
  parsed with the standard library's certificate decoder
  (ssl._ssl._test_decode_cert); a missing or unparseable file
  is skipped silently.
- TLS targets: the tls_targets tunable names {"host", "port"}
  endpoints; each is probed with a real TLS handshake and the
  peer certificate is read back. No network, an unreachable
  host, or a failed handshake all simply yield no record.

Run on the same machine as the runner, it delivers locally:
--local-dir <runner base dir> signs each payload with this
sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extend/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.

--readings FILE reads a readings dict from a JSON file instead
of the platform: the way to try the sense (and test it)
against known certificates, on any box at all. A readings file
carries "now" (epoch seconds) and "certs", a list of records
{"source", "subject", "issuer", "serial", "not_after"} with
not_after as epoch seconds.
"""
import argparse
import json
import os
import socket
import ssl
import sys
import time


def _is_number(value):
    """A finite int or float, never a bool.

    Infinity and NaN are floats, and an integer too large for a float
    is an int, but none of them is a usable tunable: inf once made a
    threshold that never trips (or always trips), and int(inf) is an
    OverflowError. Each reads as "not a number" so the documented
    default applies.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        f = float(value)
    except (OverflowError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))


# --- the live reads: the only platform-touching code -----------------

def _flatten_name(name):
    """Flatten a getpeercert()-style name to a readable string.

    The decoded subject/issuer is a tuple of RDNs, each a tuple
    of (key, value) pairs: ((("CN", "example.com"),), ...). The
    readable form joins every pair as "CN=example.com, O=...".
    """
    parts = []
    if isinstance(name, (tuple, list)):
        for rdn in name:
            if isinstance(rdn, (tuple, list)):
                for pair in rdn:
                    if isinstance(pair, (tuple, list)) and len(pair) == 2:
                        parts.append(f"{pair[0]}={pair[1]}")
    return ", ".join(parts)


def _record_from_decoded(source, decoded):
    """One readings record from a decoded certificate, or None."""
    if not isinstance(decoded, dict):
        return None
    not_after_text = decoded.get("notAfter")
    if not isinstance(not_after_text, str) or not not_after_text:
        return None
    try:
        not_after = ssl.cert_time_to_seconds(not_after_text)
    except (ValueError, OverflowError):
        return None
    serial = decoded.get("serialNumber")
    return {
        "source": str(source),
        "subject": _flatten_name(decoded.get("subject")),
        "issuer": _flatten_name(decoded.get("issuer")),
        "serial": str(serial) if serial is not None else "",
        "not_after": float(not_after),
    }


def _read_cert_file(path):
    """Decode one PEM certificate file, or None when unreadable."""
    decode = getattr(ssl._ssl, "_test_decode_cert", None)
    if decode is None:
        return None
    try:
        decoded = decode(path)
    except (AttributeError, ValueError, OSError):
        return None
    return _record_from_decoded(path, decoded)


def _read_tls_target(host, port):
    """Probe one live TLS endpoint and read its certificate.

    Every network or TLS failure is a normal capability case --
    no network is no data -- so all of them answer None.
    """
    try:
        port = int(port)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isinstance(host, str) or not host:
        return None
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=host) as conn:
                decoded = conn.getpeercert()
    except Exception:
        return None
    return _record_from_decoded(f"{host}:{port}", decoded)


def read_live(manifest):
    """One live snapshot of the watched certificates.

    Returns {"now": epoch float, "certs": [record, ...]}. A
    source that cannot be read contributes no record, never
    an exception.
    """
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    certs = []
    files = tunables.get("cert_files")
    if isinstance(files, list):
        for path in files:
            if not isinstance(path, str) or not path:
                continue
            rec = _read_cert_file(path)
            if rec is not None:
                certs.append(rec)
    targets = tunables.get("tls_targets")
    if isinstance(targets, list):
        for target in targets:
            if not isinstance(target, dict):
                continue
            rec = _read_tls_target(target.get("host"),
                                   target.get("port", 443))
            if rec is not None:
                certs.append(rec)
    return {"now": time.time(), "certs": certs}


# --- the decision: readings in, signals out (pure) --------------------

_BANDS = ("ok", "warn", "critical")


def _fresh_state():
    return {"seen": {}}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    seen = state.get("seen")
    if not isinstance(seen, dict):
        seen = {}
    clean = {}
    for source, rec in seen.items():
        if not isinstance(source, str) or not isinstance(rec, dict):
            continue
        band = rec.get("band")
        if band not in _BANDS:
            continue
        not_after = rec.get("not_after")
        if not _is_number(not_after):
            continue
        clean[source] = {
            "serial": rec.get("serial") if isinstance(
                rec.get("serial"), str) else "",
            "issuer": rec.get("issuer") if isinstance(
                rec.get("issuer"), str) else "",
            "subject": rec.get("subject") if isinstance(
                rec.get("subject"), str) else "",
            "not_after": float(not_after),
            "band": band,
        }
    return {"seen": clean}


def _tunable_days(tunables, key, default):
    value = tunables.get(key)
    return float(value) if _is_number(value) and value >= 0 else default


def decide(readings, manifest, state):
    """One pass: (readings, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the current time arrives as
    readings["now"] (epoch seconds). Band discipline: a
    certificate files cert_expiring on entering the warn band
    and cert_critical on entering the critical band, and is
    quiet while its band holds. A changed identity files
    cert_changed alongside any band alert the same pass
    produces, and its band is then re-evaluated fresh.
    """
    state = _clean_state(state)
    if not isinstance(readings, dict):
        readings = {}
    tunables = manifest.get("tunables") if isinstance(manifest, dict) else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "cert_sentinel"
    warn_days = _tunable_days(tunables, "warn_days", 30.0)
    critical_days = _tunable_days(tunables, "critical_days", 7.0)
    now = readings.get("now")
    now = float(now) if _is_number(now) else 0.0
    certs = readings.get("certs")
    if not isinstance(certs, list):
        certs = []

    records = []
    for cert in certs:
        if not isinstance(cert, dict):
            continue
        source = cert.get("source")
        not_after = cert.get("not_after")
        if not isinstance(source, str) or not source \
                or not _is_number(not_after):
            continue
        records.append({
            "source": source,
            "subject": cert.get("subject") if isinstance(
                cert.get("subject"), str) else "",
            "issuer": cert.get("issuer") if isinstance(
                cert.get("issuer"), str) else "",
            "serial": cert.get("serial") if isinstance(
                cert.get("serial"), str) else "",
            "not_after": float(not_after),
        })
    records.sort(key=lambda r: r["source"])

    seen = dict(state["seen"])
    alerts = []
    for rec in records:
        days_left = (rec["not_after"] - now) / 86400.0
        if days_left <= critical_days:
            band = "critical"
        elif days_left <= warn_days:
            band = "warn"
        else:
            band = "ok"
        detail = {
            "source": rec["source"],
            "subject": rec["subject"],
            "issuer": rec["issuer"],
            "serial": rec["serial"],
            "not_after": rec["not_after"],
            "days_left": round(days_left, 2),
        }
        previous = seen.get(rec["source"])
        changed = False
        if previous is not None and (
                previous["serial"] != rec["serial"]
                or previous["issuer"] != rec["issuer"]
                or previous["subject"] != rec["subject"]):
            changed = True
            alerts.append({
                "sensor": sensor, "signal": "cert_changed",
                "severity": "info",
                "title": f"certificate for {rec['source']} changed: "
                         f"serial {previous['serial'] or '?'} -> "
                         f"{rec['serial'] or '?'}",
                "detail": dict(
                    detail,
                    previous_serial=previous["serial"],
                    previous_issuer=previous["issuer"],
                    previous_subject=previous["subject"]),
            })
        # A changed certificate's band is re-evaluated fresh:
        # its previous band belonged to a different certificate.
        previous_band = None if changed else (
            previous["band"] if previous is not None else None)
        if band == "warn" and previous_band != "warn":
            alerts.append({
                "sensor": sensor, "signal": "cert_expiring",
                "severity": "medium",
                "title": f"certificate for {rec['source']} expires "
                         f"in {round(days_left, 1):g} days "
                         f"(warn at {warn_days:g} days)",
                "detail": dict(detail, warn_days=warn_days),
            })
        elif band == "critical" and previous_band != "critical":
            if days_left < 0:
                title = (f"certificate for {rec['source']} has "
                         f"expired ({round(-days_left, 1):g} days ago)")
            else:
                title = (f"certificate for {rec['source']} expires "
                         f"in {round(days_left, 1):g} days "
                         f"(critical at {critical_days:g} days)")
            alerts.append({
                "sensor": sensor, "signal": "cert_critical",
                "severity": "high",
                "title": title,
                "detail": dict(detail, critical_days=critical_days),
            })
        seen[rec["source"]] = {
            "serial": rec["serial"],
            "issuer": rec["issuer"],
            "subject": rec["subject"],
            "not_after": rec["not_after"],
            "band": band,
        }
    return alerts, {"seen": seen}


# --- delivery and the main loop, in the Lab Results shape -------------

def _deliver_local(alerts, args):
    """Sign and deliver each alert to a runner on this machine.

    Returns how many alerts were delivered, or None when local
    delivery is not set up (the reason is printed). Uses the
    runner's own producer helpers, so the envelope and signature
    are the contract's, not a re-implementation.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(
        os.path.join(here, "..", "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    try:
        from runner.ops import extensions as hp_extensions
    except ImportError as e:
        print(f"cert-sentinel: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"cert-sentinel: no signing secret in ${args.secret_env}; "
              f"set it to this sense's key secret", file=sys.stderr)
        return None
    delivered = 0
    for alert in alerts:
        payload = hp_extensions.build_sensor_alert(
            alert["sensor"], alert["severity"], alert["title"],
            key_id=args.key_id, signal=alert.get("signal"),
            detail=alert.get("detail"))
        try:
            if args.local_port:
                hp_extensions.send_local_signal(
                    payload, secret, port=args.local_port)
                where = f"127.0.0.1:{args.local_port}"
            else:
                where = hp_extensions.drop_local_signal(
                    args.local_dir, payload, secret)
        except (OSError, ValueError) as e:
            print(f"cert-sentinel: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"cert-sentinel: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Cert Sentinel extension watcher: read the "
                    "watched certificates once and file sensor "
                    "alert payloads for expiry and identity change.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".cert-sentinel-state.json"),
                    help="state file (default: .cert-sentinel-state.json "
                         "next to this script)")
    ap.add_argument("--readings", default=None,
                    help="read the readings dict from this JSON file "
                         "instead of the platform (trying the sense "
                         "against known readings, on any box)")
    ap.add_argument("--local-dir", default=None,
                    help="runner base dir: deliver alerts locally "
                         "(signed, into its local inbox) instead of "
                         "printing payloads")
    ap.add_argument("--local-port", type=int, default=None,
                    help="with --local-dir: push to the runner's "
                         "loopback listener on this port instead of "
                         "dropping files")
    ap.add_argument("--key-id", default="",
                    help="key id this sense signs as (its "
                         "sensors.<name>.key_id in the runner config)")
    ap.add_argument("--secret-env", default="HOMING_PIGEON_SENSOR_SECRET",
                    help="environment variable holding the signing "
                         "secret (default: HOMING_PIGEON_SENSOR_SECRET)")
    args = ap.parse_args(argv)
    try:
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"cert-sentinel: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    if args.readings:
        try:
            with open(args.readings, encoding="utf-8") as fh:
                readings = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"cert-sentinel: cannot read readings "
                  f"{args.readings}: {e}", file=sys.stderr)
            return 2
    else:
        readings = read_live(manifest)
    state = _fresh_state()
    try:
        with open(args.state, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    alerts, state = decide(readings, manifest, state)
    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so the
            # next pass reports these certificates again.
            print(f"cert-sentinel: {len(alerts) - delivered} of "
                  f"{len(alerts)} alert(s) not delivered; state not "
                  f"saved, will retry next pass", file=sys.stderr)
            return 2
    else:
        for alert in alerts:
            print(json.dumps(alert, sort_keys=True))
    try:
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh, sort_keys=True)
    except OSError as e:
        print(f"cert-sentinel: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
