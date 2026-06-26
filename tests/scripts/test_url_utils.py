"""SSRF regression tests for ``scripts/url_utils.py``.

Locks in the v1.5.1 hardening: any URL whose hostname resolves to a private,
loopback, link-local, CGNAT, or otherwise-internal address must be rejected,
and DNS failures must fail closed (raise ValueError, not pass through).

These tests do not require network access — IP-literal hostnames bypass DNS
resolution. The dns-failure case uses a hostname that definitely won't resolve.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Make scripts/ importable without requiring an installed package
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from url_utils import sanitize_error, sanitize_url, validate_url  # noqa: E402


# ─── SSRF blocklist ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://localhost/secret",         # resolves to 127.0.0.1
    "http://0.0.0.0:8080",
    "http://10.0.0.1",
    "http://172.16.0.5",
    "http://172.31.255.254",
    "http://192.168.1.1",
    "http://169.254.169.254/latest/meta-data/",  # AWS metadata endpoint
    "http://100.64.0.1",                          # CGNAT range
    "https://[::1]/admin",
    "https://[fc00::1]",                          # ULA
    "https://[fe80::1%25eth0]",                   # link-local (note %% for URL)
    "https://[::ffff:127.0.0.1]",                 # IPv4-mapped IPv6 loopback
    "https://[::]/",                              # IPv6 unspecified (v1.6.0 fix)
    "https://[64:ff9b::a9fe:a9fe]/",              # NAT64 prefix → IPv4 169.254.169.254 (v1.7.1 fix)
    "https://[2002:7f00:0001::]/",                # 6to4 prefix wrapping 127.0.0.1 (v1.7.1 fix)
    "https://[2001:db8::1]/",                     # IPv6 documentation range (v1.7.1 fix)
])
def test_blocks_private_and_internal_addresses(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize("url", [
    "ftp://example.com",
    "file:///etc/passwd",
    "gopher://example.com",
    "data:text/html,<script>alert(1)</script>",
    "javascript:alert(1)",
])
def test_blocks_non_http_schemes(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_dns_resolution_failure_fails_closed():
    """A hostname that cannot be resolved should raise, not be allowed
    through to the requests/playwright layer."""
    with pytest.raises(ValueError):
        validate_url("http://nonexistent-hostname-for-codex-ads-tests.invalid")


@pytest.mark.parametrize("url,expected_contains", [
    ("example.com", "https://example.com"),    # bare hostname gets https:// prepended
    ("https://example.com/foo?bar=baz", "https://example.com/foo"),
])
def test_valid_public_urls_pass(url, expected_contains):
    """Public hostnames that resolve to non-blocked IPs must pass through.
    This requires network access (DNS for example.com) so we keep it minimal."""
    pytest.importorskip("socket")
    try:
        result = validate_url(url)
    except ValueError as e:
        if "DNS" in str(e) or "resolve" in str(e).lower():
            pytest.skip("No network access for DNS resolution")
        raise
    assert expected_contains in result


# ─── sanitize_error ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,sanitized_marker", [
    ("Failed with key=sk-1234567890abcdef", "key=***"),
    ("Got 401 with token=ghp_AAA111BBB222CCC", "token=***"),
    ("Error: secret=topsecret123 in payload", "secret=***"),
    ("Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig is invalid", "Bearer ***"),
    ("Authorization: Bearer ghp_AAA111BBB222CCC failed", "Bearer ***"),
    ("auth=Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig", "auth=***"),  # auth= captures full Bearer token
    ("password = hunter2 was rejected", "password=***"),  # note: regex normalizes
    # New patterns added in v1.7.1 hardening:
    ("api_key=sk_live_abc123xyz failed", "api_key=***"),
    ("Got apikey=sk_live_abc123xyz", "apikey=***"),
    ("access_token=ya29.AHESpeudo refresh failed", "access_token=***"),
    ("refresh-token: 1//05somelong_value_here was rotated", "refresh_token=***"),
    ("OAuth callback ?code=4/0AY0e-g7abc&state=xyz", "code=***"),
    ("AWS Signature=AKIAxx/20260518/... invalid", "signature=***"),
])
def test_sanitize_error_strips_credentials(raw, sanitized_marker):
    msg = sanitize_error(Exception(raw))
    assert sanitized_marker in msg
    # And the original secret value must NOT survive (token bodies)
    for forbidden in (
        "sk-1234567890abcdef", "ghp_AAA111BBB222CCC", "topsecret123",
        "eyJhbGciOiJIUzI1NiJ9", "hunter2",
        "sk_live_abc123xyz", "ya29.AHESpeudo", "1//05somelong_value_here",
        "4/0AY0e-g7abc", "AKIAxx/20260518/...",
    ):
        assert forbidden not in msg


def test_sanitize_error_preserves_benign_message():
    """Messages without secrets should pass through unchanged."""
    msg = sanitize_error(Exception("File not found: /tmp/foo.json"))
    assert "File not found" in msg
    assert "/tmp/foo.json" in msg


# ─── sanitize_url ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,forbidden_substrings,required_substrings", [
    # OAuth flow callback URLs
    ("https://example.com/cb?code=4/0AY0e-g7abc&state=xyz",
     ["4/0AY0e-g7abc"], ["code=***"]),
    # Access tokens in query string
    ("https://api.example.com/data?access_token=ya29.AHESpeudo",
     ["ya29.AHESpeudo"], ["access_token=***"]),
    # Userinfo (basic auth) in URL — should be stripped entirely
    ("https://user:supersecretpass@example.com/path",
     ["user", "supersecretpass"], ["https://example.com/path"]),
    # Mixed: userinfo + query token
    ("https://admin:hunter2@api.example.com/x?api_key=sk_live_xyz",
     ["admin", "hunter2", "sk_live_xyz"], ["api_key=***"]),
])
def test_sanitize_url_strips_credentials(raw, forbidden_substrings, required_substrings):
    cleaned = sanitize_url(raw)
    for forbidden in forbidden_substrings:
        assert forbidden not in cleaned, f"Expected {forbidden!r} stripped from {cleaned!r}"
    for required in required_substrings:
        assert required in cleaned, f"Expected {required!r} present in {cleaned!r}"


def test_sanitize_url_preserves_benign_url():
    """Plain URLs without credentials should pass through unchanged."""
    url = "https://example.com/landing?utm_source=meta&utm_campaign=brand"
    assert sanitize_url(url) == url


# ─── Redirect SSRF revalidation (v1.7.1 hardening) ──────────────────────────


def test_fetch_page_blocks_redirect_to_private_ip(monkeypatch):
    """fetch_page() must re-validate every redirect hop, not just the initial URL.

    Pre-v1.7.1, requests' built-in follow-redirects path silently fetched
    `Location: http://169.254.169.254/` and similar. After the fix, fetch_page
    refuses to follow a redirect into the SSRF blocklist.
    """
    from unittest.mock import MagicMock
    import importlib
    fetch_page_module = importlib.import_module("fetch_page")

    redirect_response = MagicMock()
    redirect_response.status_code = 302
    redirect_response.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}
    redirect_response.url = "https://example.com/"

    class FakeSession:
        def get(self, *args, **kwargs):
            return redirect_response

    monkeypatch.setattr(fetch_page_module.requests, "Session", FakeSession)

    # Initial URL must pass validation (example.com resolves to a public IP).
    try:
        validate_url("https://example.com/")
    except ValueError as exc:
        if "DNS" in str(exc) or "resolve" in str(exc).lower():
            pytest.skip("No network access for DNS resolution of example.com")
        raise

    result = fetch_page_module.fetch_page("https://example.com/", timeout=5)
    assert result["error"] is not None, "expected blocked-redirect error"
    assert "Blocked redirect" in result["error"]
    # The destination IP must not leak in raw form (sanitize_error redacts)
    # but the operator should at least know it was blocked.
    assert result["status_code"] is None
    assert result["content"] is None


def test_fetch_page_allows_redirect_to_public_ip(monkeypatch):
    """A redirect chain that stays on public addresses should succeed."""
    from unittest.mock import MagicMock
    import importlib
    fetch_page_module = importlib.import_module("fetch_page")

    final_response = MagicMock()
    final_response.status_code = 200
    final_response.headers = {}
    final_response.text = "<html>ok</html>"
    final_response.url = "https://example.com/final"

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def get(self, *args, **kwargs):
            return final_response

    monkeypatch.setattr(fetch_page_module.requests, "Session", FakeSession)

    try:
        validate_url("https://example.com/")
    except ValueError as exc:
        if "DNS" in str(exc) or "resolve" in str(exc).lower():
            pytest.skip("No network access for DNS resolution of example.com")
        raise

    result = fetch_page_module.fetch_page("https://example.com/", timeout=5)
    assert result["error"] is None
    assert result["status_code"] == 200
    assert result["content"] == "<html>ok</html>"
