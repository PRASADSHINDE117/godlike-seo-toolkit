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


# Regex patterns identifying interactive user application workflows
APP_ROUTE_PATTERNS = re.compile(
    r"/(my-|user|account|profile|settings|dashboard|admin|portal|"
    r"bookings|orders|wishlist|create-|new-|edit-|manage-|cart|checkout|"
    r"billing|payment|inbox|messages|notifications)",
    re.I,
)

# Regex patterns identifying authentication entry points
AUTH_ROUTE_PATTERNS = re.compile(
    r"/(login|signin|sign-in|log-in|signup|sign-up|register|registration|"
    r"auth|authenticate|password|forgot-password|reset-password|logout)",
    re.I,
)

# Regex patterns identifying system utilities and dynamic feeds
UTILITY_PATTERNS = re.compile(
    r"/(api/|graphql|feed|rss|search\?|filter\?|export|download)",
    re.I,
)


class PageClassifier:
    """Classifies URLs and DOM responses to prevent false-positive audits on app routes."""

    @staticmethod
    def classify(
        url: str,
        status_code: int = 200,
        html: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Classify page and detect soft login gateways."""
        headers = headers or {}
        parsed = urlparse(url)
        path = parsed.path.lower()
        query = parsed.query.lower()
        full_path = f"{path}?{query}" if query else path

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
        if html:
            if PageClassifier._detect_login_form(html) and ("redirect=" in query or "next=" in query or "login" in html.lower()[:500]):
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
        """Detect whether HTML body is predominantly a user login form."""
        if not html:
            return False

        # Quick regex check for password inputs
        if re.search(r'<input[^>]+type=["\']password["\']', html, re.I):
            return True

        # Check for authentication markers
        auth_phrases = [
            "sign in to your account",
            "log in to your account",
            "please sign in",
            "enter your password",
            "login to continue",
        ]
        html_lower = html[:5000].lower()
        if any(phrase in html_lower for phrase in auth_phrases):
            return True

        return False
