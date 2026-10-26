# Agent-Chat-Stamp: 50000c8e-1b3d-4f5a-9c7e-8d0b2a4c6e8f
"""The hosting control plane: put a configured runner somewhere, keep it
updated, never sit in the job path (docs/project/hosting.md).

Providers live behind one interface (`base.Provider`), talk through one
HTTP shim (`http`) so every call can be recorded and replayed in the
suite, and are driven by `cli`. Standard library only.
"""
