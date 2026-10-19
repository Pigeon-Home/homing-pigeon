"""Public surface for `import runner`.

The implementation lives in runner.runner. Tests and local_test import
these names from the package, so they have to be here.
"""
# Static import first: runner.runner loads runner.mailbox dynamically
# (_load_mod), which PyInstaller cannot trace. The installer binary is
# built from install.py with no --hidden-import list and reaches this
# package through `import runner`; without runner.mailbox bundled,
# connect_smtp/send_mail below are missing and `import runner` fails
# in the frozen installer (version "unknown", setup wizard skipped).
from runner import mailbox as _mailbox  # noqa: F401
from runner.runner import (  # noqa: F401
    ask_model,
    connect_smtp,
    ensure_inference_ready,
    inference_config,
    send_mail,
    sign_payload,
    update_llama_from_config,
    verify_body,
    _redact_patterns,
)
