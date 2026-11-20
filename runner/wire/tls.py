#!/usr/bin/env python3
"""
One trust store for every outbound HTTPS call the runner makes.

The frozen build died on a clean Windows Server at the OAuth token
exchange: urllib could not verify Google's certificate, because the
one-file executable carried no CA bundle and the machine offered it
none it could read (CERTIFICATE_VERIFY_FAILED: unable to get local
issuer certificate). A development machine hides the flaw, because
a bundle is lying around there for other reasons. So the choice of
CA file is made here, once, in the open, and every urllib HTTPS
call site in the runner asks this module for its context instead
of taking the platform default and hoping.

The order is deliberate:

  1. SSL_CERT_FILE, when the operator sets it. The operator's word
     outranks the bundle: a private proxy CA lives exactly there,
     and the field workaround for the failure above was exactly
     this variable, pointed at a bundle by hand.
  2. certifi's bundled CA file, when certifi is importable. The
     freeze collects certifi's data, so the shipped executable
     carries the file inside itself and a clean machine is no
     longer a special case.
  3. The platform default context, when neither is available: a
     source run on a managed machine keeps the behaviour it had.

certifi is an optional import on purpose. The runner's dependency
set stays the standard library; the bundle is a build-time
passenger, found by path when present and missed quietly when not.
"""
import os
import ssl


def _certifi_cafile():
    """certifi's CA bundle path, or None when certifi is absent.

    Any failure to import it or to answer reads as absent: a broken
    optional passenger must not take the token exchange down with
    it. The platform default is the fallback then, as it was before
    this module existed.
    """
    try:
        import certifi
        path = certifi.where()
    except Exception:
        return None
    if isinstance(path, str) and path and os.path.isfile(path):
        return path
    return None


def cafile():
    """The CA file outbound HTTPS verifies against, or None.

    None means: let ssl build the platform default context. The
    operator's SSL_CERT_FILE wins over the bundled file, and a
    value the operator set is passed through untouched for ssl to
    judge, never silently replaced by the bundle.
    """
    env = os.environ.get("SSL_CERT_FILE") or ""
    if env:
        return env
    return _certifi_cafile()


def ssl_context() -> ssl.SSLContext:
    """The shared context for outbound HTTPS."""
    path = cafile()
    if path:
        return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()
