"""Shared HTTP helper (stdlib only) for arXiv API calls and PDF downloads."""

from __future__ import annotations

import ssl
import urllib.request

USER_AGENT = "literature-review-crew/0.1 (student project)"


def _ssl_context() -> ssl.SSLContext:
    # On some Windows Pythons the system store misses the arXiv chain
    # (CERTIFICATE_VERIFY_FAILED). certifi ships with chromadb/httpx: use it if present.
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CONTEXT = _ssl_context()


def http_get(url: str, timeout: float) -> bytes:
    """GET `url` and return the body. Raises urllib.error.URLError/HTTPError on failure."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read()
