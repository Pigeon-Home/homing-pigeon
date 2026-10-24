# Cert Sentinel — an example Homing Pigeon extension

A sense for people who run PKI. Point it at the certificate
files a machine depends on — and, optionally, at the live TLS
endpoints it talks to — and the Oracle learns when one is
running out of life and when one was replaced underneath
everyone: which certificates are inside their warning window,
which ones are critical or already expired, and which ones
came back from a renewal with a different identity than the
certificate they replaced.

Certificates are read from the `cert_files` tunable (PEM files
on disk, decoded with the standard library) and from the
`tls_targets` tunable (`{"host", "port"}` entries probed with
a real TLS handshake that reads the peer certificate back).
Both source kinds produce the same record, so a certificate
is watched the same way wherever it lives. Honest coverage:
file parsing and TLS probing rely on the standard library's
decoder, which covers PEM certificate files and TLS servers
that present a certificate during the handshake; it does not
watch certificate stores (the Windows or macOS keychains),
OCSP or CRL status, or chain-of-trust validation — expiry and
identity on the endpoints you name are what it sees.

The watcher files three declared signals:

| Signal | Fires when |
|--------|------------|
| `cert_expiring` | A certificate's remaining life falls to the `warn_days` tunable (default 30) or below — files once on entering the warn band (medium) |
| `cert_critical` | A certificate's remaining life falls to the `critical_days` tunable (default 7) or below, or it has already expired — files once on entering the critical band (high) |
| `cert_changed` | A known source presents a different serial, issuer, or subject than the certificate in state — it was reissued or swapped (info) |

Expiry is a band discipline: entering warn files once and
entering critical files once, and a certificate stays quiet
while its band holds. A certificate seen for the first time
files its band alert if it is already in warn or critical —
a first-sight expired certificate is news, not a baseline —
but never `cert_changed`. A renewed certificate files
`cert_changed` and its band is re-evaluated fresh, so a
renewal back to a long life goes quiet again. The pass's
state lives in `.cert-sentinel-state.json` next to the script.

Run one pass:

```bash
python3 cert_sentinel.py --local-dir ~/.homing-pigeon --key-id cert-key
# HOMING_PIGEON_SENSOR_SECRET holds the cert_sentinel sense's key
```

Or try it anywhere by feeding it a readings file instead of
live reads:

```bash
python3 cert_sentinel.py --readings readings.json
# one alert payload per line on stdout
```

A readings file is one JSON object with `now` as epoch
seconds and one record per certificate:

```json
{"now": 1792375113.0,
 "certs": [{"source": "/etc/ssl/site.pem", "subject": "CN=example.com",
            "issuer": "CN=Example CA", "serial": "0A1B",
            "not_after": 1794000000.0}]}
```

Alert payloads are unsigned sense alerts when printed;
signing and delivery follow the standard senses flow. The
full extension walkthrough — manifest fields, the versioning
contract, sensor binding, and how to turn this example into
your own package — is in
[docs/extensions.md](../../../docs/extensions.md).

## Light mode

For a Pi Light install this sense is already close to free:
certificates move slowly, so the default
`poll_interval_sec` is 86400 — one pass a day is the cadence
expiry deserves. The knobs that tune it further down are the
ones the code actually reads:

- `tls_targets`: leave it empty for files-only operation —
  zero network probes, zero handshakes, just the PEM files in
  `cert_files` decoded once a day.
- `cert_files` / `tls_targets`: keep the lists short — the
  handful of certificates this box actually depends on, not
  a scan of every endpoint it has ever met.
