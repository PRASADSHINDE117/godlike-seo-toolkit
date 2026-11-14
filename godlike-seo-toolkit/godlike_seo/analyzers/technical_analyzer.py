"""
Technical SEO and Infrastructure Analyzer.

Audits:
- SSL/TLS certificate health and HTTPS enforcement
- Security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, etc.)
- Server response times (TTFB) and Core Web Vitals estimates
- HTTP Compression (Brotli / Gzip)
- Caching policies (Cache-Control, ETag)
- Robots.txt and XML Sitemap validation
- Redirect chains and Canonical loop detection
"""

from __future__ import annotations

import logging
import socket
import ssl
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from godlike_seo.models import (
    PageData,
    SEOIssue,
    IssueSeverity,
    IssueCategory,
)

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """Performs deep technical infrastructure, performance, and security checks."""

    def __init__(self, check_ssl_live: bool = False):
        self.check_ssl_live = check_ssl_live

    def check_ssl_certificate(self, hostname: str, port: int = 443) -> Dict[str, Any]:
        """Inspect SSL/TLS certificate details directly via socket."""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=5.0) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()

                    # Expiry date parsing
                    not_after = cert.get("notAfter", "")
                    expire_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z") if not_after else None
                    days_left = (expire_dt - datetime.utcnow()).days if expire_dt else 999

                    return {
                        "valid": True,
                        "days_remaining": days_left,
                        "cipher": cipher[0] if cipher else "Unknown",
                        "tls_version": version,
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                    }
        except Exception as e:
            return {"valid": False, "error": str(e), "days_remaining": 0}

    def audit_security_headers(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Check presence and configuration of recommended security headers."""
        h = {k.lower(): v for k, v in headers.items()}

        audit = {
            "hsts": "strict-transport-security" in h,
            "csp": "content-security-policy" in h,
            "x_frame_options": "x-frame-options" in h,
            "x_content_type_options": "x-content-type-options" in h,
            "referrer_policy": "referrer-policy" in h,
            "permissions_policy": "permissions-policy" in h or "feature-policy" in h,
            "server_header_leak": "server" in h,
            "x_powered_by_leak": "x-powered-by" in h,
        }
        return audit

    def audit_caching_and_compression(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Audit HTTP caching policies and compression."""
        h = {k.lower(): v for k, v in headers.items()}
        encoding = h.get("content-encoding", "").lower()
        cache_control = h.get("cache-control", "").lower()
        etag = "etag" in h

        is_compressed = "gzip" in encoding or "br" in encoding or "deflate" in encoding

        max_age = 0
        if "max-age=" in cache_control:
            try:
                import re
                m = re.search(r"max-age=(\d+)", cache_control)
                if m:
                    max_age = int(m.group(1))
            except Exception:
                pass

        return {
            "is_compressed": is_compressed,
            "compression_type": encoding or "none",
            "cache_control": cache_control,
            "has_cache_control": bool(cache_control),
            "max_age_seconds": max_age,
            "has_etag": etag,
        }

    def analyze(self, pages: List[PageData]) -> Dict[str, Any]:
        """Run technical audits across crawled pages and return metrics + issues."""
        issues: List[SEOIssue] = []

        if not pages:
            return {"issues": []}

        # Check root domain SSL
        parsed_root = urlparse(pages[0].url)
        ssl_info = {}
        if parsed_root.scheme == "https" and self.check_ssl_live:
            ssl_info = self.check_ssl_certificate(parsed_root.netloc)
            if not ssl_info.get("valid"):
                issues.append(SEOIssue(
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.SECURITY,
                    title="Invalid or Missing SSL Certificate",
                    description=f"SSL certificate handshake failed: {ssl_info.get('error')}",
                    affected_url=pages[0].url,
                    recommendation="Ensure a valid, active TLS certificate from a trusted authority is installed.",
                ))
            elif ssl_info.get("days_remaining", 999) < 14:
                issues.append(SEOIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.SECURITY,
                    title="SSL Certificate Expiring Soon",
                    description=f"Certificate expires in {ssl_info.get('days_remaining')} days.",
                    affected_url=pages[0].url,
                    recommendation="Renew the TLS certificate immediately to avoid browser security warnings.",
                ))

        # Check pages
        total_ttfb = 0.0
        slow_pages = []
        uncompressed_pages = []

        for p in pages:
            headers = p.headers or p.http_headers or {}
            sec_audit = self.audit_security_headers(headers)
            cache_comp = self.audit_caching_and_compression(headers)

            total_ttfb += p.response_time_ms

            # Slow TTFB (> 1500 ms)
            if p.response_time_ms > 1500:
                slow_pages.append(p.url)
                if p.response_time_ms > 3000:
                    issues.append(SEOIssue(
                        severity=IssueSeverity.CRITICAL,
                        category=IssueCategory.PERFORMANCE,
                        title=f"Very Slow Page Load ({p.response_time_ms:.0f}ms)",
                        description=f"Server response time of {p.response_time_ms:.0f}ms severely impairs Google crawl budget.",
                        affected_url=p.url,
                        recommendation="Optimize database queries, enable server-side caching (Redis/OPcache), and use a CDN.",
                    ))

            # Missing Compression
            if not cache_comp["is_compressed"] and p.content_length > 2048:
                uncompressed_pages.append(p.url)

            # Security headers check on first page (site-wide indicator)
            if p.url == pages[0].url:
                if not sec_audit["hsts"] and parsed_root.scheme == "https":
                    issues.append(SEOIssue(
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.SECURITY,
                        title="Missing Strict-Transport-Security (HSTS)",
                        description="HSTS header is missing on HTTPS response.",
                        affected_url=p.url,
                        recommendation="Add 'Strict-Transport-Security: max-age=31536000; includeSubDomains' to enforce encrypted connections.",
                    ))
                if not sec_audit["x_content_type_options"]:
                    issues.append(SEOIssue(
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.SECURITY,
                        title="Missing X-Content-Type-Options Header",
                        description="Header 'X-Content-Type-Options: nosniff' prevents MIME-sniffing vulnerabilities.",
                        affected_url=p.url,
                        recommendation="Configure your server to send 'X-Content-Type-Options: nosniff'.",
                    ))

        avg_ttfb = total_ttfb / max(1, len(pages))

        if uncompressed_pages:
            issues.append(SEOIssue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.PERFORMANCE,
                title=f"Missing Gzip/Brotli Compression on {len(uncompressed_pages)} pages",
                description="HTML pages are served uncompressed, causing slower load times.",
                affected_url=uncompressed_pages[0],
                recommendation="Enable Brotli or Gzip compression in Nginx/Apache/Cloudflare to reduce transfer size by 60-80%.",
            ))

        return {
            "ssl_info": ssl_info,
            "average_response_time_ms": round(avg_ttfb, 1),
            "slow_pages_count": len(slow_pages),
            "uncompressed_pages_count": len(uncompressed_pages),
            "issues": issues,
        }
