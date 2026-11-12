# Changelog

## 3.16.20.8

- Windows probe timeouts reduced to 3s to prevent 20-minute hangs on wevtutil.
- macos_confine.py path helper for Windows realpath rewrite is in ae10d41; current main has a placeholder that needs restore.
- Shrink guard is live to catch truncated pushes.
