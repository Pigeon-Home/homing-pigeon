# Sysmon Feed fixtures — SYNTHETIC

Every fixture in this directory is **synthetic**: crafted by
hand from the vendor-documented Sysmon Event ID 1
(ProcessCreate) field layout, modeled on real Sysmon output
conventions. None of it is a captured sample.

That is not an apology, it is the honest state of the
evidence: Sysmon for Linux did not run in the measurement
environment (the host denied BPF program loading, so the
service installed and its config validated but telemetry
failed to start), and no Windows Sysmon export was captured
there either. See the extension README for the full caveat.

- `synthetic-linux-sysmon.log` — Sysmon for Linux shape:
  one event per syslog line, the event as XML text on the
  line. A process-from-temp event, a base64-token event, a
  benign event, an Event ID 3 event (parses to nothing),
  and a non-event line.
- `synthetic-windows-sysmon.txt` — Windows Sysmon exported
  as text: multi-line `Field: value` blocks separated by
  blank lines. A process-from-temp event, an
  `-EncodedCommand` event, and a benign event.
