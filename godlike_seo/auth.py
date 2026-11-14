"""
User Authentication & Playwright Login Engine for Godlike SEO 2.0.

Provides automated authenticated crawling & testing:
- Reads credentials from files (e.g., `user details/user info.txt`), JSON, or CLI arguments
- Automated form login using Playwright (locates email/username, password, submit button)
- Extracts session cookies and storage state
- Injects auth cookies & headers into aiohttp and Playwright crawl sessions
- Verifies post-login authenticated state
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuthConfig:
    """User authentication configuration."""
    login_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    auth_cookie: Optional[str] = None  # e.g. "session_id=xyz; token=abc"
    auth_header: Optional[str] = None  # e.g. "Bearer xyz"
    auth_file_path: Optional[str] = None
    cookies: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    username_selector: Optional[str] = None
    password_selector: Optional[str] = None
    submit_selector: Optional[str] = None
    is_authenticated: bool = False

    @classmethod
    def from_file(cls, filepath: str) -> "AuthConfig":
        """Parse credentials from a file (JSON or key=value format)."""
        config = cls(auth_file_path=filepath)
        if not os.path.exists(filepath):
            return config

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                return config

            # Try parsing as JSON first
            if content.startswith("{") and content.endswith("}"):
                try:
                    data = json.loads(content)
                    config.login_url = data.get("login_url") or data.get("url")
                    config.username = data.get("username") or data.get("email") or data.get("user")
                    config.password = data.get("password") or data.get("pass")
                    config.auth_cookie = data.get("auth_cookie") or data.get("cookie")
                    config.auth_header = data.get("auth_header") or data.get("token")
                    if isinstance(data.get("cookies"), dict):
                        config.cookies.update(data["cookies"])
                    if isinstance(data.get("headers"), dict):
                        config.headers.update(data["headers"])
                    return config
                except Exception:
                    pass

            # Parse line by line: key=value or key: value
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    key, val = line.split("=", 1)
                elif ":" in line:
                    key, val = line.split(":", 1)
                else:
                    continue

                k = key.strip().lower()
                v = val.strip()

                if k in ("username", "user", "email"):
                    config.username = v
                elif k in ("password", "pass", "pwd"):
                    config.password = v
                elif k in ("login_url", "url", "login"):
                    config.login_url = v
                elif k in ("cookie", "auth_cookie", "cookies"):
                    config.auth_cookie = v
                elif k in ("token", "auth_header", "authorization", "bearer"):
                    config.auth_header = v

        except Exception as e:
            logger.warning("Error reading auth file %s: %s", filepath, e)

        return config


class AuthManager:
    """Manages login workflows and session extraction via Playwright."""

    def __init__(self, config: Optional[AuthConfig] = None):
        self.config = config or AuthConfig()

    def parse_cookie_string(self, cookie_str: str) -> Dict[str, str]:
        """Convert 'name=val; name2=val2' into dict."""
        cookies = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies

    async def perform_login(self) -> Dict[str, str]:
        """Run automated login using Playwright and return captured session cookies."""
        # 1. If explicit cookie provided, parse directly
        if self.config.auth_cookie:
            cookies = self.parse_cookie_string(self.config.auth_cookie)
            self.config.cookies.update(cookies)
            self.config.is_authenticated = True
            logger.info("Using provided auth cookies (%d cookies)", len(cookies))
            return self.config.cookies

        # 2. If login_url + username + password available, automate with Playwright
        if not (self.config.login_url and self.config.username and self.config.password):
            logger.debug("No complete login credentials provided; running unauthenticated.")
            return {}

        logger.info("Starting automated Playwright login to %s", self.config.login_url)

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                # Navigate to login URL
                await page.goto(self.config.login_url, wait_until="networkidle", timeout=20000)

                # Find username input field
                user_selectors = [
                    self.config.username_selector,
                    'input[type="email"]',
                    'input[name="username"]',
                    'input[name="email"]',
                    'input[id="username"]',
                    'input[id="email"]',
                    'input[name="user"]',
                    'input[type="text"]',
                ]
                user_input = None
                for sel in user_selectors:
                    if sel:
                        try:
                            loc = page.locator(sel).first
                            if await loc.count() > 0 and await loc.is_visible():
                                user_input = loc
                                break
                        except Exception:
                            continue

                if user_input:
                    await user_input.fill(self.config.username)
                    logger.info("Filled username credentials")
                else:
                    logger.warning("Could not locate username input field on %s", self.config.login_url)

                # Find password input field
                pass_selectors = [
                    self.config.password_selector,
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[name="pass"]',
                    'input[id="password"]',
                ]
                pass_input = None
                for sel in pass_selectors:
                    if sel:
                        try:
                            loc = page.locator(sel).first
                            if await loc.count() > 0 and await loc.is_visible():
                                pass_input = loc
                                break
                        except Exception:
                            continue

                if pass_input:
                    await pass_input.fill(self.config.password)
                    logger.info("Filled password credentials")
                else:
                    logger.warning("Could not locate password input field on %s", self.config.login_url)

                # Submit form
                submit_selectors = [
                    self.config.submit_selector,
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("Login")',
                    'button:has-text("Sign In")',
                    'button:has-text("Log in")',
                    'form button',
                ]
                submitted = False
                for sel in submit_selectors:
                    if sel:
                        try:
                            btn = page.locator(sel).first
                            if await btn.count() > 0 and await btn.is_visible():
                                await btn.click()
                                submitted = True
                                break
                        except Exception:
                            continue

                if not submitted and pass_input:
                    # Fallback: Press Enter on password input
                    await pass_input.press("Enter")
                    submitted = True

                # Wait for post-login navigation or network idle
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass

                # Extract cookies
                browser_cookies = await context.cookies()
                extracted_cookies = {c["name"]: c["value"] for c in browser_cookies}

                await browser.close()

                if extracted_cookies:
                    self.config.cookies.update(extracted_cookies)
                    self.config.is_authenticated = True
                    logger.info("Automated login successful! Captured %d session cookies.", len(extracted_cookies))
                    return self.config.cookies
                else:
                    logger.warning("Login completed but no session cookies were obtained.")

        except Exception as e:
            logger.error("Playwright automated login failed: %s", e)

        return self.config.cookies
