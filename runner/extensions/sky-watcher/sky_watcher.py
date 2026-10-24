#!/usr/bin/env python3
"""Sky Watcher: a Homing Pigeon user extension (example sense).

Watches the International Space Station -- where it is right
now, from the wheretheiss.at position feed -- and turns its
passes over one observer into sensor alerts for the Oracle.
Most ISS passes are invisible (daylight, or the station in
Earth's shadow) or too low to bother with. A few each week are
the real thing: the station sunlit, the sky dark, the track
climbing to a bright point nearly overhead. This sense files
the difference:

- station_approaching    the station entered the approach
                         corridor around the observer (info;
                         fires for every pass, visible or not)
- visible_pass_starting  a sunlit pass over a dark sky begins
                         within the visible_lead_sec tunable,
                         culminating above the visible minimum
                         (medium)
- bright_pass            that pass culminates at or above the
                         bright threshold -- near zenith
                         (high; the wake-worthy one)

The machinery is deliberately boring, in the Lab Results
example's shape. fetch_position() is the only function that
touches the network; update() -- one position sample plus the
manifest plus last pass's state, out come alerts and the new
state -- is pure geometry and a small state machine, so the
whole decision surface is testable off-network. A pass walks
out -> approaching -> visible -> out, each stage files once
per pass, and the state resets when the station leaves the
corridor, so the next orbit starts fresh.

The geometry, in one paragraph. psi is the central angle
between the observer and the station's sub-point. Elevation
follows from psi and the altitude: atan2(cos(psi) - R/(R+h),
sin(psi)). Two successive sub-points define the orbit plane,
so the pass's culmination is estimated before it happens:
the minimum central angle is asin(|o . n|) for observer unit
vector o and plane normal n, and the lead time to the visible
window comes from the along-track angle still to travel at
the station's angular rate. Whether the observer's sky is
dark is a small solar calculation (the NOAA fractional-year
approximation, good to about a degree -- plenty against a
-6 degree threshold). Whether the station is sunlit is the
feed's own visibility field: "daylight" or "eclipsed".

The producer runs one sample per invocation; a timer (cron,
a systemd timer, the runner's own schedule) drives the
poll_interval_sec cadence, 60 seconds by default. A feed
outage is a quiet no-op: nothing files, the state is left
exactly as it was, and the next pass retries. No sample, no
signal -- this sense never invents a pass.

--samples FILE replays recorded feed responses instead of
the live feed: a JSON list of wheretheiss.at response objects
(or one object). The way to demo the sense, and the way the
tests drive it, on any machine.

Run on the same machine as the runner, it delivers locally:
--local-dir <runner base dir> signs each payload with this
sense's key (read from the environment variable named by
--secret-env) and drops it into the runner's local inbox, or
pushes it to the runner's loopback listener when --local-port
is given. Same envelope, same signature -- only the transport
differs (docs/extensions.md, "Local delivery"). Without
--local-dir it prints one alert payload per line, and signing
and delivery follow the standard senses flow.

Position data: wheretheiss.at (https://wheretheiss.at), the
free public ISS tracker; no API key. Poll it politely -- the
60-second default cadence is theirs to share.
"""
import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

EARTH_RADIUS_KM = 6371.0
FEED_URL = "https://api.wheretheiss.at/v1/satellites/25544"
# The station's orbital speed, for samples that omit velocity.
DEFAULT_VELOCITY_KMH = 27576.0
# A longer silence than this ends any pass in progress: the
# next sample starts a fresh one rather than resuming a track
# nobody has seen for a quarter of an orbit.
PASS_GAP_SEC = 900.0

_SIGNALS = ("station_approaching", "visible_pass_starting",
            "bright_pass")


def _num(value):
    return "%g" % value


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


# --- the geometry (pure) ---------------------------------------------

def _vec(lat_deg, lon_deg):
    """Unit vector for a point on the sphere."""
    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    return (math.cos(phi) * math.cos(lam),
            math.cos(phi) * math.sin(lam),
            math.sin(phi))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _clamp(x, lo=-1.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def central_angle_rad(lat1, lon1, lat2, lon2):
    """The angle at Earth's center between two surface points."""
    a = _vec(lat1, lon1)
    b = _vec(lat2, lon2)
    cx = a[1] * b[2] - a[2] * b[1]
    cy = a[2] * b[0] - a[0] * b[2]
    cz = a[0] * b[1] - a[1] * b[0]
    cross = math.sqrt(cx * cx + cy * cy + cz * cz)
    return math.atan2(cross, _clamp(_dot(a, b)))


def elevation_deg(psi_rad, alt_km):
    """Elevation of the station above the observer's horizon.

    psi is the central angle to the sub-point; the station sits
    at radius R + alt. At psi = 0 the station is overhead (90);
    elevation reaches 0 where cos(psi) = R / (R + alt).
    """
    k = EARTH_RADIUS_KM / (EARTH_RADIUS_KM + alt_km)
    return math.degrees(math.atan2(math.cos(psi_rad) - k,
                                   math.sin(psi_rad)))


def psi_for_elevation_deg(el_deg, alt_km):
    """The central angle at which the station stands at el_deg.

    Inverts elevation_deg in closed form: with t = tan(el),
    t*sin(psi) - cos(psi) = -k becomes M*sin(psi - a) = -k for
    M = sqrt(t^2 + 1) and a = atan2(1, t).
    """
    t = math.tan(math.radians(el_deg))
    m = math.sqrt(t * t + 1.0)
    alpha = math.atan2(1.0, t)
    k = EARTH_RADIUS_KM / (EARTH_RADIUS_KM + alt_km)
    return alpha - math.asin(_clamp(k / m))


def station_geometry(obs_lat, obs_lon, s_lat, s_lon, alt_km):
    """(central angle rad, elevation deg, ground distance km)."""
    psi = central_angle_rad(obs_lat, obs_lon, s_lat, s_lon)
    return psi, elevation_deg(psi, alt_km), EARTH_RADIUS_KM * psi


def culmination_estimate_deg(prev, sample, obs_lat, obs_lon):
    """Estimate the pass's culmination elevation, or None.

    prev and sample are two position samples (dicts with lat /
    lon / alt_km). Their sub-points and Earth's center define
    the orbit plane; the closest the track comes to the
    observer is asin(|o . n|), turned into an elevation at the
    current altitude. One sample alone says nothing about the
    track, so it returns None.
    """
    if not isinstance(prev, dict):
        return None
    p1 = _vec(prev["lat"], prev["lon"])
    p2 = _vec(sample["lat"], sample["lon"])
    nx = p1[1] * p2[2] - p1[2] * p2[1]
    ny = p1[2] * p2[0] - p1[0] * p2[2]
    nz = p1[0] * p2[1] - p1[1] * p2[0]
    norm = math.sqrt(nx * nx + ny * ny + nz * nz)
    if norm < 1e-12:
        return None  # the same point twice: no track yet
    o = _vec(obs_lat, obs_lon)
    psi_min = math.asin(_clamp(abs(_dot(o, (nx / norm, ny / norm,
                                             nz / norm)))))
    return elevation_deg(psi_min, sample["alt_km"])


def sun_elevation_deg(lat_deg, lon_deg, ts):
    """The sun's elevation at a place and epoch time (NOAA approx).

    The fractional-year series for the equation of time and
    the solar declination, then the hour angle. Accurate to
    about a degree -- this gates "is the sky dark", not an
    eclipse prediction.
    """
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    jan1 = datetime(dt.year, 1, 1, tzinfo=timezone.utc)
    day = (dt - jan1).days + 1
    hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    gamma = 2.0 * math.pi / 365.0 * (day - 1 + (hour - 12.0) / 24.0)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(gamma)
                       - 0.032077 * math.sin(gamma)
                       - 0.014615 * math.cos(2 * gamma)
                       - 0.040849 * math.sin(2 * gamma))
    decl = (0.006918 - 0.399912 * math.cos(gamma)
            + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma)
            + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma)
            + 0.00148 * math.sin(3 * gamma))
    tst = (hour * 60.0 + eqtime + 4.0 * lon_deg) % 1440.0
    ha = tst / 4.0 - 180.0
    if ha < -180.0:
        ha += 360.0
    phi = math.radians(lat_deg)
    cos_zen = (math.sin(phi) * math.sin(decl)
               + math.cos(phi) * math.cos(decl)
               * math.cos(math.radians(ha)))
    return 90.0 - math.degrees(math.acos(_clamp(cos_zen)))


# --- the feed (the only network code) ---------------------------------

def sample_from_feed(data):
    """One wheretheiss.at response object -> a sample, or None.

    The sample is the producer's internal shape: lat / lon /
    alt_km / velocity_kmh / sunlit (True, False, or None when
    the feed does not say) / ts (epoch seconds). A response
    missing its position or its timestamp is unusable and
    answers None -- the caller treats it as no sample at all.
    """
    if not isinstance(data, dict):
        return None
    lat = data.get("latitude")
    lon = data.get("longitude")
    alt = data.get("altitude")
    ts = data.get("timestamp")
    if not (_is_number(lat) and _is_number(lon)
            and _is_number(alt) and _is_number(ts)):
        return None
    vel = data.get("velocity")
    vel = float(vel) if _is_number(vel) else DEFAULT_VELOCITY_KMH
    if data.get("units") == "miles":
        alt = float(alt) * 1.609344
        vel = vel * 1.609344
    vis = data.get("visibility")
    sunlit = (vis == "daylight") if isinstance(vis, str) else None
    return {"lat": float(lat), "lon": float(lon),
            "alt_km": float(alt), "velocity_kmh": vel,
            "sunlit": sunlit, "ts": float(ts)}


def fetch_position(url=FEED_URL):
    """The station's current position, as a sample (or None).

    Raises OSError / ValueError when the feed cannot be read;
    main() turns that into a quiet no-op.
    """
    req = urllib.request.Request(
        url, headers={"User-Agent": "homing-pigeon-sky-watcher/0.1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return sample_from_feed(data)


# --- the pass state machine (pure) -------------------------------------

def _fresh_state():
    return {"stage": "out", "pass_id": 0, "fired": [],
            "prev": None, "culmination_deg": None, "last_ts": None}


def _clean_sample(raw):
    if not isinstance(raw, dict):
        return None
    lat, lon = raw.get("lat"), raw.get("lon")
    alt, ts = raw.get("alt_km"), raw.get("ts")
    if not (_is_number(lat) and _is_number(lon)
            and _is_number(alt) and _is_number(ts)):
        return None
    if not (-90.0 <= lat <= 90.0) or alt <= 0:
        return None
    vel = raw.get("velocity_kmh")
    sunlit = raw.get("sunlit")
    return {"lat": float(lat), "lon": float(lon),
            "alt_km": float(alt),
            "velocity_kmh": float(vel) if _is_number(vel)
            else DEFAULT_VELOCITY_KMH,
            "sunlit": sunlit if isinstance(sunlit, bool) else None,
            "ts": float(ts)}


def _clean_state(state):
    if not isinstance(state, dict):
        return _fresh_state()
    stage = state.get("stage")
    if stage not in ("out", "approaching", "visible"):
        stage = "out"
    pass_id = state.get("pass_id")
    if not isinstance(pass_id, int) or isinstance(pass_id, bool) \
            or pass_id < 0:
        pass_id = 0
    fired = state.get("fired")
    if not isinstance(fired, list):
        fired = []
    fired = [s for s in fired if s in _SIGNALS]
    prev = _clean_sample(state.get("prev"))
    culm = state.get("culmination_deg")
    last_ts = state.get("last_ts")
    return {
        "stage": stage, "pass_id": pass_id, "fired": fired,
        "prev": prev,
        "culmination_deg": float(culm) if _is_number(culm) else None,
        "last_ts": float(last_ts) if _is_number(last_ts) else None,
    }


def _tunable(tunables, key, default):
    value = tunables.get(key)
    return float(value) if _is_number(value) else default


def _observer(tunables):
    lat = tunables.get("observer_lat")
    lon = tunables.get("observer_lon")
    if _is_number(lat) and _is_number(lon) \
            and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
        return float(lat), float(lon)
    return None


def _time_to_visible_sec(sample, psi, psi_min, visible_min_deg):
    """Seconds until the station enters the visible window.

    The window is elevation >= visible_min_deg. Along the
    track, the angle still to travel is the difference between
    the along-track angle to closest approach now and at
    window entry, paced at the station's angular rate. 0 when
    already inside; None when this pass never enters (its
    culmination is under the minimum) or has already left.
    """
    alt = sample["alt_km"]
    psi_vis = psi_for_elevation_deg(visible_min_deg, alt)
    if psi <= psi_vis:
        return 0.0
    if psi_min is None or psi_min >= psi_vis:
        return None

    def along(psi_x):
        ratio = _clamp(math.cos(psi_x) / math.cos(psi_min))
        return math.acos(ratio)

    omega = (sample["velocity_kmh"] / 3600.0) \
        / (EARTH_RADIUS_KM + alt)
    if omega <= 0:
        return None
    return (along(psi) - along(psi_vis)) / omega


def update(sample, manifest, state):
    """One sample: (sample, manifest, state) -> (alerts, new_state).

    Pure: no I/O, no clock -- the sample carries its own
    timestamp. Stages: out -> approaching (corridor entry
    files station_approaching) -> visible (the heads-up has
    fired) -> out again when the station leaves the corridor,
    resetting the pass so the next orbit starts fresh. The
    visible and bright signals share one evaluation: both need
    the station sunlit, the observer's sky dark, and a
    culmination estimate that clears their threshold, and both
    fire inside the lead time, never after the fact.
    """
    state = _clean_state(state)
    sample = _clean_sample(sample)
    if sample is None:
        return [], state
    tunables = manifest.get("tunables") if isinstance(manifest, dict) \
        else {}
    if not isinstance(tunables, dict):
        tunables = {}
    sensor = manifest.get("name") if isinstance(manifest, dict) else None
    if not isinstance(sensor, str) or not sensor:
        sensor = "sky_watcher"
    observer = _observer(tunables)
    if observer is None:
        return [], state  # nowhere to watch from; nothing to say
    obs_lat, obs_lon = observer
    radius = _tunable(tunables, "approach_radius_km", 5000.0)
    visible_min = _tunable(tunables, "visible_min_elevation_deg", 10.0)
    bright_min = _tunable(tunables, "bright_min_elevation_deg", 65.0)
    lead = _tunable(tunables, "visible_lead_sec", 600.0)
    dark_below = _tunable(tunables, "dark_sun_elevation_deg", -6.0)

    # A long silence abandons any pass in progress: the track
    # nobody saw is not resumed, it is replaced.
    if state["last_ts"] is not None \
            and sample["ts"] - state["last_ts"] > PASS_GAP_SEC:
        state = {"stage": "out", "pass_id": state["pass_id"],
                 "fired": [], "prev": None, "culmination_deg": None,
                 "last_ts": state["last_ts"]}

    psi, elev, dist = station_geometry(
        obs_lat, obs_lon, sample["lat"], sample["lon"],
        sample["alt_km"])
    alerts = []

    if state["stage"] == "out":
        if dist > radius:
            state["prev"] = sample
            state["last_ts"] = sample["ts"]
            return alerts, state
        state["pass_id"] += 1
        state["stage"] = "approaching"
        state["fired"] = []
        state["culmination_deg"] = None

    if dist > radius:
        # The station left the corridor: the pass is over.
        state["stage"] = "out"
        state["fired"] = []
        state["culmination_deg"] = None
        state["prev"] = None
        state["last_ts"] = sample["ts"]
        return alerts, state

    # In a pass. Refresh the culmination estimate from the
    # last two sub-points whenever a usable previous exists.
    prev = state["prev"]
    estimate = culmination_estimate_deg(prev, sample, obs_lat, obs_lon) \
        if prev is not None else None
    if estimate is not None:
        state["culmination_deg"] = estimate
    culm = state["culmination_deg"]

    if "station_approaching" not in state["fired"]:
        detail = {"ground_distance_km": int(round(dist)),
                  "elevation_deg": round(elev, 1),
                  "observer_lat": obs_lat, "observer_lon": obs_lon}
        title = "ISS entering the approach corridor"
        if culm is not None:
            detail["culmination_deg"] = round(culm, 1)
            title += f" -- culmination ~{_num(round(culm))} deg"
        alerts.append({"sensor": sensor,
                       "signal": "station_approaching",
                       "severity": "info", "title": title,
                       "detail": detail})
        state["fired"].append("station_approaching")

    dark = sun_elevation_deg(obs_lat, obs_lon, sample["ts"]) < dark_below
    if sample["sunlit"] is True and dark and culm is not None:
        psi_min = None
        if prev is not None:
            p1 = _vec(prev["lat"], prev["lon"])
            p2 = _vec(sample["lat"], sample["lon"])
            nx = p1[1] * p2[2] - p1[2] * p2[1]
            ny = p1[2] * p2[0] - p1[0] * p2[2]
            nz = p1[0] * p2[1] - p1[1] * p2[0]
            norm = math.sqrt(nx * nx + ny * ny + nz * nz)
            if norm >= 1e-12:
                psi_min = math.asin(_clamp(abs(_dot(
                    _vec(obs_lat, obs_lon),
                    (nx / norm, ny / norm, nz / norm)))))
        starts_in = _time_to_visible_sec(sample, psi, psi_min,
                                         visible_min)
        receding = prev is not None and psi > central_angle_rad(
            obs_lat, obs_lon, prev["lat"], prev["lon"])
        if receding and starts_in not in (0.0,):
            starts_in = None  # the window is behind this pass
        if starts_in is not None and starts_in <= lead:
            if "visible_pass_starting" not in state["fired"] \
                    and culm >= visible_min:
                if starts_in <= 30:
                    when = "starting now"
                else:
                    when = f"starting in ~{int(round(starts_in / 60.0))} min"
                alerts.append({
                    "sensor": sensor,
                    "signal": "visible_pass_starting",
                    "severity": "medium",
                    "title": f"visible ISS pass {when} -- culmination "
                             f"{_num(round(culm))} deg",
                    "detail": {"starts_in_sec": int(round(starts_in)),
                               "culmination_deg": round(culm, 1),
                               "elevation_deg": round(elev, 1)}})
                state["fired"].append("visible_pass_starting")
                state["stage"] = "visible"
            if "bright_pass" not in state["fired"] \
                    and culm >= bright_min:
                alerts.append({
                    "sensor": sensor, "signal": "bright_pass",
                    "severity": "high",
                    "title": f"bright ISS pass overhead -- culmination "
                             f"{_num(round(culm))} deg",
                    "detail": {"starts_in_sec": int(round(starts_in)),
                               "culmination_deg": round(culm, 1),
                               "elevation_deg": round(elev, 1)}})
                state["fired"].append("bright_pass")

    state["prev"] = sample
    state["last_ts"] = sample["ts"]
    return alerts, state


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
        print(f"sky-watcher: local delivery needs the homing-pigeon "
              f"repo importable ({e}); run me from a clone",
              file=sys.stderr)
        return None
    secret = os.environ.get(args.secret_env) or ""
    if not secret:
        print(f"sky-watcher: no signing secret in ${args.secret_env}; "
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
            print(f"sky-watcher: delivery failed for "
                  f"{alert.get('signal')}: {e}", file=sys.stderr)
            continue
        delivered += 1
        print(f"sky-watcher: filed {alert.get('signal')} via {where}",
              file=sys.stderr)
    return delivered


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Sky Watcher extension: take one ISS position "
                    "sample and file sensor alert payloads for the "
                    "pass it belongs to. Run on a one-minute timer.")
    ap.add_argument("--manifest", default=os.path.join(here, "extension.json"),
                    help="extension.json to read tunables from")
    ap.add_argument("--state", default=os.path.join(
                        here, ".sky-watcher-state.json"),
                    help="state file (default: .sky-watcher-state.json "
                         "next to this script)")
    ap.add_argument("--samples", default=None,
                    help="replay recorded feed responses from this "
                         "JSON file (one wheretheiss.at object, or a "
                         "list of them) instead of the live feed")
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
        print(f"sky-watcher: cannot read manifest {args.manifest}: {e}",
              file=sys.stderr)
        return 2
    tunables = manifest.get("tunables") if isinstance(manifest, dict) \
        else {}
    if not isinstance(tunables, dict):
        tunables = {}
    if _observer(tunables) is None:
        print("sky-watcher: no observer set -- put observer_lat and "
              "observer_lon in the manifest's tunables; nothing filed",
              file=sys.stderr)
        return 0

    if args.samples:
        try:
            with open(args.samples, encoding="utf-8") as fh:
                recorded = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"sky-watcher: cannot read samples "
                  f"{args.samples}: {e}", file=sys.stderr)
            return 2
        if isinstance(recorded, dict):
            recorded = [recorded]
        if not isinstance(recorded, list):
            print("sky-watcher: samples file must hold a feed object "
                  "or a list of them", file=sys.stderr)
            return 2
        samples = [s for s in (sample_from_feed(r) for r in recorded)
                   if s is not None]
    else:
        try:
            live = fetch_position()
        except (OSError, ValueError) as e:
            # A feed outage is a quiet no-op: no sample, no
            # signal, the state untouched for the next pass.
            print(f"sky-watcher: feed unreachable ({e}); nothing filed",
                  file=sys.stderr)
            return 0
        samples = [live] if live is not None else []

    state = _fresh_state()
    try:
        with open(args.state, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        pass
    alerts = []
    for sample in samples:
        fired, state = update(sample, manifest, state)
        alerts.extend(fired)

    if args.local_dir:
        delivered = _deliver_local(alerts, args)
        if delivered is None:
            return 2  # _deliver_local already said why
        if delivered != len(alerts):
            # A failed delivery leaves the state unwritten, so
            # the next pass reports this pass again.
            print(f"sky-watcher: {len(alerts) - delivered} of "
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
        print(f"sky-watcher: cannot write state {args.state}: {e}",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
