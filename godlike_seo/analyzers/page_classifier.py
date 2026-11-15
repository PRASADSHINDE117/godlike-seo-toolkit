"""
Page and URL Classification Engine for Godlike SEO 3.0.

Accurately classifies URLs and page responses before running SEO audits:
- PUBLIC_CONTENT: Marketing, product, category, blog, and documentation pages
- USER_APP_ROUTE: Authenticated workflows (/my-bookings, /wishlist, /create-listing, /cart)
- AUTHENTICATION: Login, register, signup, password reset routes
- SYSTEM_UTILITY: Internal API, search feeds, pagination parameters
- REDIRECT: 3xx redirect destinations
- ERROR: 4xx / 5xx error responses
- Detects "Soft Login Gates" (200 OK pages returning login forms)
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup


class PageType(str, Enum):
    PUBLIC_CONTENT = "public_content"
    USER_APP_ROUTE = "user_app_route"
    AUTHENTICATION = "authentication"
    SYSTEM_UTILITY = "system_utility"
    REDIRECT = "redirect"
    ERROR = "error"


# Segment-aware regex patterns identifying interactive user application workflows
# Target explicitly private, authenticated workflows while protecting public marketing and informational pages
APP_ROUTE_PATTERNS = re.compile(
    r"/(?:my-[a-z0-9_-]+|create-listing|edit-listing|manage-listing|"
    r"wishlist|cart|checkout)(?:/|$|\?)|"
    r"/(?:account|profile|settings|dashboard|admin|portal)/(?:edit|manage|settings|preferences|billing|orders|bookings|inbox|notifications)(?:/|$|\?)",
    re.I,
)

# Segment-aware regex patterns identifying genuine authentication entry points
# Avoids treating programming/security articles (/register/, /password/, /auth/) as auth gates
AUTH_ROUTE_PATTERNS = re.compile(
    r"/(?:login|signin|sign-in|log-in|signup|sign-up|logout|signout|sign-out|"
    r"forgot-password|reset-password|change-password)(?:/|$|\?)|"
    r"/(?:users?|accounts?)/(?:login|signin|signup|sign_in|sign_up|register|password)(?:/|$|\?)",
    re.I,
)

# Segment-aware regex patterns identifying system utilities and dynamic feeds
UTILITY_PATTERNS = re.compile(
    r"/(?:api|graphql|feed|rss)(?:/|$|\?)|/(?:search|filter)(?:\?|$)",
    re.I,
)


class PageClassifier:
    """Classifies URLs and DOM responses with segment-aware precision and custom overrides."""

    @staticmethod
    def classify(
        url: str,
        status_code: int = 200,
        html: str = "",
        headers: Optional[Dict[str, str]] = None,
        route_overrides: Optional[Dict[str, PageType]] = None,
    ) -> Dict[str, Any]:
        """Classify page and detect soft login gateways with segment awareness."""
        headers = headers or {}
        parsed = urlparse(url)
        path = parsed.path.lower()
        query = parsed.query.lower()
        full_path = f"{path}?{query}" if query else path

        # 0. User / Project Explicit Route Overrides
        if route_overrides:
            for pattern, target_type in route_overrides.items():
                if pattern.lower() in full_path or pattern.lower() == path:
                    return {
                        "page_type": target_type,
                        "is_app_route": target_type in (PageType.USER_APP_ROUTE, PageType.AUTHENTICATION),
                        "is_auth_gate": target_type == PageType.AUTHENTICATION,
                        "reason": f"Explicit route override matched: '{pattern}'",
                    }

        # 1. HTTP Status checks
        if status_code in (301, 302, 303, 307, 308):
            return {
                "page_type": PageType.REDIRECT,
                "is_app_route": False,
                "is_auth_gate": False,
                "reason": f"HTTP {status_code} Redirect",
            }

        if status_code >= 400:
            return {
                "page_type": PageType.ERROR,
                "is_app_route": False,
                "is_auth_gate": False,
                "reason": f"HTTP {status_code} Error",
            }

        # 2. Check URL patterns for authentication routes
        if AUTH_ROUTE_PATTERNS.search(full_path):
            return {
                "page_type": PageType.AUTHENTICATION,
                "is_app_route": True,
                "is_auth_gate": True,
                "reason": "URL matches authentication pattern",
            }

        # 3. Check URL patterns for user application workflows
        if APP_ROUTE_PATTERNS.search(full_path):
            # Check if this app route is returning a soft login gate
            is_soft_login = False
            if html:
                is_soft_login = PageClassifier._detect_login_form(html)

            return {
                "page_type": PageType.AUTHENTICATION if is_soft_login else PageType.USER_APP_ROUTE,
                "is_app_route": True,
                "is_auth_gate": is_soft_login,
                "reason": "App workflow route (soft login gate)" if is_soft_login else "Private user application workflow",
            }

        # 4. Check for system utility
        if UTILITY_PATTERNS.search(full_path):
            return {
                "page_type": PageType.SYSTEM_UTILITY,
                "is_app_route": False,
                "is_auth_gate": False,
                "reason": "System utility or internal feed",
            }

        # 5. Inspect HTML for soft login gate on otherwise public-looking URL
        # Requires explicit auth interception redirect parameters (?redirect= or ?next= or ?return_to=)
        if html and ("redirect=" in query or "next=" in query or "return_to=" in query or "returnurl=" in query):
            if PageClassifier._detect_login_form(html):
                return {
                    "page_type": PageType.AUTHENTICATION,
                    "is_app_route": True,
                    "is_auth_gate": True,
                    "reason": "HTML contains unauthenticated login gate with redirect parameter",
                }

        # Default: Public indexable content
        return {
            "page_type": PageType.PUBLIC_CONTENT,
            "is_app_route": False,
            "is_auth_gate": False,
            "reason": "Publicly indexable website content",
        }

    @staticmethod
    def _detect_login_form(html: str) -> bool:
        """Detect whether HTML body is predominantly a user login form, ignoring code snippets."""
        if not html:
            return False

        # Strip code blocks and pre elements to prevent false positives on programming tutorials
        clean_html = re.sub(r'<(?:pre|code)[^>]*>.*?</(?:pre|code)>', '', html, flags=re.S | re.I)

        # Must have an actual <form> containing a password input
        form_match = re.search(r'<form[^>]*>.*?</form>', clean_html, re.S | re.I)
        if not form_match:
            return False

        form_content = form_match.group(0)
        has_password = bool(re.search(r'<input[^>]+type=["\']password["\']', form_content, re.I))
        if not has_password:
            return False

        # Check for authentication markers
        auth_phrases = [
            "sign in",
            "log in",
            "password",
            "remember me",
            "forgot password",
        ]
        form_lower = form_content.lower()
        return any(phrase in form_lower for phrase in auth_phrases)
