"""
URL Normalization Engine for Godlike SEO 2.0.

Provides deterministic, RFC 3986-compliant URL normalization:
- Lowercase scheme and netloc
- Default port stripping (80, 443)
- Path normalization (resolves . and .., removes duplicate slashes)
- Trailing slash normalization with domain-level root handling
- Percent-encoding normalization (decodes unreserved characters, unifies %20 and +)
- Query parameter normalization (alphabetical sorting, tracking parameter stripping)
- Fragment stripping
"""

from __future__ import annotations

import posixpath
import re
from urllib.parse import parse_qsl, quote, unquote_plus, urlencode, urlparse, urlunparse

# Common tracking parameters to strip for SEO equivalence
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "gclsrc", "dclid", "zanpid", "msclkid",
    "mc_cid", "mc_eid", "_ga", "_gl", "_hsenc", "_hsmi",
}


def normalize_url(
    url: str,
    strip_tracking: bool = True,
    trailing_slash: str = "keep",  # "keep", "always", "never"
) -> str:
    """Deterministically normalize a URL for accurate comparison and deduplication."""
    if not url:
        return ""

    raw = url.strip()
    if not raw.startswith(("http://", "https://")):
        return raw

    try:
        parsed = urlparse(raw)
    except Exception:
        return raw

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Strip default ports
    if ":" in netloc:
        host, port = netloc.split(":", 1)
        if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
            netloc = host

    # Normalize path
    path = parsed.path or "/"

    # Normalize duplicate slashes: // -> /
    path = re.sub(r"/{2,}", "/", path)

    # Resolve . and ..
    if path != "/":
        segments = path.split("/")
        resolved = []
        for seg in segments:
            if seg in ("", "."):
                continue
            elif seg == "..":
                if resolved:
                    resolved.pop()
            else:
                # Normalize percent-encoding in path
                decoded_seg = unquote_plus(seg)
                resolved.append(quote(decoded_seg, safe="-._~:@!$&'()*+,;="))

        path = "/" + "/".join(resolved)
        if raw.endswith("/") and not path.endswith("/"):
            path += "/"

    # Handle trailing slash rule on subpaths
    if path == "":
        path = "/"
    elif path != "/":
        if trailing_slash == "never" and path.endswith("/"):
            path = path.rstrip("/")
        elif trailing_slash == "always" and not path.endswith("/") and not posixpath.splitext(path)[1]:
            path += "/"

    # Normalize query string
    query_str = ""
    if parsed.query:
        params = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_params = []
        for k, v in params:
            k_lower = k.lower()
            if strip_tracking and k_lower in TRACKING_PARAMS:
                continue
            # Normalize percent encoding in key and value
            norm_k = unquote_plus(k).strip()
            norm_v = unquote_plus(v).strip()
            filtered_params.append((norm_k, norm_v))

        # Sort parameters deterministically
        filtered_params.sort(key=lambda x: (x[0], x[1]))
        if filtered_params:
            query_str = urlencode(filtered_params)

    # Reconstruct normalized URL (fragment always stripped for SEO equivalence)
    return urlunparse((scheme, netloc, path, "", query_str, ""))


def are_urls_equivalent(url1: str, url2: str) -> bool:
    """Return True if two URLs represent the exact same HTTP resource."""
    if url1 == url2:
        return True
    return normalize_url(url1) == normalize_url(url2)
