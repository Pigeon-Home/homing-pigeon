"""The hosting control plane: put a configured runner somewhere, keep it
updated, never sit in the job path (docs/project/hosting.md).

Providers live behind one interface (`base.Provider`), talk through one
HTTP shim (`http`) so every call can be recorded and replayed in the
suite, and are driven by `cli`. Standard library only.
"""
