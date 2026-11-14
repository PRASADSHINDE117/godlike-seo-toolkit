"""
SERP Scraper – scrapes Google (with DuckDuckGo fallback) search results.

Features
--------
* Rotating user-agent strings and realistic browser headers
* Random delays (2-5 s) between requests to avoid blocks
* Optional proxy support
* Pagination for up to 100 results per query
* Extracts: organic results, featured snippets, "People Also Ask", related
  searches
* DuckDuckGo HTML API as a fallback when Google blocks
* Search-volume estimation via Google Suggest / Autocomplete API
* Persists results to the toolkit's SQLite database
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import quote_plus, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from godlike_seo.models import SERPResult, SERPAnalysis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NUM_RESULTS = 10
MAX_RESULTS_PER_PAGE = 10
MIN_DELAY = 2.0
MAX_DELAY = 5.0
REQUEST_TIMEOUT = 15

GOOGLE_SEARCH_URL = "https://www.google.com/search"
GOOGLE_SUGGEST_URL = "http://suggestqueries.google.com/complete/search"
DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"

# A realistic pool of desktop browser User-Agent strings (2024-2025 era).
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.9,fr;q=0.8",
    "en,en-US;q=0.9",
]


# ---------------------------------------------------------------------------
# Helper dataclasses for enriched SERP data
# ---------------------------------------------------------------------------

@dataclass
class SERPFeatures:
    """Extra SERP features beyond the 10 blue links."""
    featured_snippet: Optional[Dict[str, str]] = None  # {title, text, url}
    people_also_ask: List[str] = field(default_factory=list)
    related_searches: List[str] = field(default_factory=list)


@dataclass
class SERPPage:
    """Complete SERP data for a single keyword query."""
    keyword: str
    results: List[SERPResult] = field(default_factory=list)
    features: Optional[SERPFeatures] = None
    source: str = "google"  # "google" or "duckduckgo"
    total_results_estimated: int = 0
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class SERPScraper:
    """Scrapes search engine result pages and estimates search volumes.

    Parameters
    ----------
    proxy : str, optional
        HTTP/HTTPS proxy URL, e.g. ``"http://user:pass@proxy:8080"``.
    db_path : str, optional
        Path to the SQLite database for persisting results.
    num_results : int
        Number of results to fetch per keyword (1-100). Defaults to 10.
    language : str
        Google ``hl`` / language parameter. Defaults to ``"en"``.
    country : str
        Google ``gl`` / country parameter. Defaults to ``"us"``.
    delay_range : tuple[float, float]
        Min/max random delay between requests in seconds.
    progress_callback : callable, optional
        Called with ``(keyword_index, total_keywords, keyword)`` on each query.
    """

    def __init__(
        self,
        *,
        proxy: Optional[str] = None,
        db_path: Optional[str] = None,
        num_results: int = DEFAULT_NUM_RESULTS,
        language: str = "en",
        country: str = "us",
        delay_range: Tuple[float, float] = (MIN_DELAY, MAX_DELAY),
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> None:
        self.proxy = proxy
        self.db_path = db_path
        self.num_results = max(1, min(num_results, 100))
        self.language = language
        self.country = country
        self.delay_range = delay_range
        self.progress_callback = progress_callback

        self._session = requests.Session()
        if proxy:
            self._session.proxies = {"http": proxy, "https": proxy}

        self._db_conn = None
        if db_path:
            self._init_db()

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Initialise SQLite tables for SERP data."""
        import sqlite3

        self._db_conn = sqlite3.connect(self.db_path)
        cur = self._db_conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS serp_results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword     TEXT NOT NULL,
                position    INTEGER NOT NULL,
                url         TEXT NOT NULL,
                title       TEXT,
                snippet     TEXT,
                domain      TEXT,
                is_featured INTEGER DEFAULT 0,
                source      TEXT DEFAULT 'google',
                scraped_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS serp_features (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword          TEXT NOT NULL,
                featured_snippet TEXT,
                people_also_ask  TEXT,
                related_searches TEXT,
                source           TEXT DEFAULT 'google',
                scraped_at       TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS search_volume_estimates (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword  TEXT NOT NULL,
                score    REAL,
                rank     INTEGER,
                fetched_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_serp_keyword ON serp_results(keyword);
            CREATE INDEX IF NOT EXISTS idx_serp_features_kw ON serp_features(keyword);
            """
        )
        self._db_conn.commit()

    def _save_serp_page(self, page: SERPPage) -> None:
        """Persist a SERPPage to the database."""
        if self._db_conn is None:
            return
        cur = self._db_conn.cursor()
        for r in page.results:
            cur.execute(
                """INSERT INTO serp_results
                   (keyword, position, url, title, snippet, domain, is_featured, source, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    page.keyword,
                    r.position,
                    r.url,
                    r.title,
                    r.snippet,
                    r.domain,
                    1 if r.is_featured else 0,
                    page.source,
                    page.scraped_at,
                ),
            )
        if page.features:
            cur.execute(
                """INSERT INTO serp_features
                   (keyword, featured_snippet, people_also_ask, related_searches, source, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    page.keyword,
                    json.dumps(page.features.featured_snippet) if page.features.featured_snippet else None,
                    json.dumps(page.features.people_also_ask),
                    json.dumps(page.features.related_searches),
                    page.source,
                    page.scraped_at,
                ),
            )
        self._db_conn.commit()

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    def _random_headers(self) -> Dict[str, str]:
        """Build realistic browser request headers with a random UA."""
        ua = random.choice(USER_AGENTS)
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    def _delay(self) -> None:
        """Sleep for a random interval within the configured range."""
        sleep_time = random.uniform(*self.delay_range)
        logger.debug("Sleeping %.2f s between requests", sleep_time)
        time.sleep(sleep_time)

    def _get(self, url: str, params: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Perform a GET request; return the response text or *None* on failure."""
        try:
            resp = self._session.get(
                url,
                params=params,
                headers=self._random_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            logger.warning("Request to %s failed: %s", url, exc)
            return None

    # ------------------------------------------------------------------
    # Google parsing
    # ------------------------------------------------------------------

    def _parse_google_results(
        self, html: str, keyword: str, start_position: int = 1
    ) -> Tuple[List[SERPResult], SERPFeatures]:
        """Parse Google SERP HTML into structured data."""
        soup = BeautifulSoup(html, "lxml")
        results: List[SERPResult] = []
        features = SERPFeatures()

        # --- Featured snippet ---
        fs_block = soup.select_one("div.xpdopen, div.ifM9O, block-component[class*='featured']")
        if fs_block:
            fs_title_el = fs_block.select_one("h3, [role='heading']")
            fs_text_el = fs_block.select_one("span.hgKElc, div.LGOjhe, div[data-attrid]")
            fs_link_el = fs_block.select_one("a[href]")
            features.featured_snippet = {
                "title": fs_title_el.get_text(strip=True) if fs_title_el else "",
                "text": fs_text_el.get_text(strip=True) if fs_text_el else "",
                "url": fs_link_el["href"] if fs_link_el and fs_link_el.get("href") else "",
            }

        # --- People Also Ask ---
        paa_blocks = soup.select("div.related-question-pair, div[data-q], div.wQiwMc")
        for paa in paa_blocks:
            question_el = paa.select_one("[data-q], .CSkcDe, span")
            if question_el:
                q_text = question_el.get("data-q") or question_el.get_text(strip=True)
                if q_text and q_text not in features.people_also_ask:
                    features.people_also_ask.append(q_text)

        # --- Related searches ---
        related_blocks = soup.select("div.s75CSd a, div.k8XOCe a, a.k8XOCe, div#botstuff a")
        for rel in related_blocks:
            text = rel.get_text(strip=True)
            if text and len(text) > 2 and text not in features.related_searches:
                features.related_searches.append(text)

        # --- Organic results ---
        # Google wraps results in <div class="g"> or <div data-sokoban-container>
        result_blocks = soup.select("div.g, div.tF2Cxc, div[data-sokoban-container]")
        position = start_position

        seen_urls: set = set()
        for block in result_blocks:
            if position > start_position + MAX_RESULTS_PER_PAGE:
                break

            link_el = block.select_one("a[href]")
            if not link_el:
                continue

            href = link_el.get("href", "")
            # Filter out internal Google links
            if not href.startswith("http") or "google.com" in href:
                continue

            # Deduplicate
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title_el = block.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else ""

            snippet_el = block.select_one(
                "div.VwiC3b, span.aCOpRe, div[data-sncf], div.IsZvec"
            )
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            domain = urlparse(href).netloc.replace("www.", "")

            is_featured = False
            if features.featured_snippet and features.featured_snippet.get("url") == href:
                is_featured = True

            results.append(
                SERPResult(
                    position=position,
                    url=href,
                    title=title,
                    snippet=snippet,
                    domain=domain,
                    is_featured=is_featured,
                )
            )
            position += 1

        return results, features

    def _scrape_google(self, keyword: str) -> Optional[SERPPage]:
        """Scrape Google for *keyword* across one or more pages."""
        all_results: List[SERPResult] = []
        features: Optional[SERPFeatures] = None
        pages_needed = (self.num_results + MAX_RESULTS_PER_PAGE - 1) // MAX_RESULTS_PER_PAGE

        for page_idx in range(pages_needed):
            start = page_idx * MAX_RESULTS_PER_PAGE
            params: Dict[str, str] = {
                "q": keyword,
                "hl": self.language,
                "gl": self.country,
                "num": str(MAX_RESULTS_PER_PAGE),
            }
            if start > 0:
                params["start"] = str(start)

            html = self._get(GOOGLE_SEARCH_URL, params=params)
            if html is None:
                logger.warning("Google returned no HTML for '%s' (page %d)", keyword, page_idx)
                break

            # Detect blocking
            if "detected unusual traffic" in html.lower() or "captcha" in html.lower():
                logger.warning("Google CAPTCHA / block detected for '%s'", keyword)
                break

            page_results, page_features = self._parse_google_results(
                html, keyword, start_position=start + 1
            )
            all_results.extend(page_results)
            if page_idx == 0:
                features = page_features

            if len(page_results) == 0:
                break  # no more results

            if page_idx < pages_needed - 1:
                self._delay()

        if not all_results:
            return None

        return SERPPage(
            keyword=keyword,
            results=all_results[: self.num_results],
            features=features,
            source="google",
        )

    # ------------------------------------------------------------------
    # Bing fallback
    # ------------------------------------------------------------------

    def _scrape_bing(self, keyword: str) -> Optional[SERPPage]:
        """Scrape Bing search results as a reliable search engine provider."""
        logger.info("Falling back to Bing for '%s'", keyword)
        try:
            import base64
            url = f"https://www.bing.com/search?q={quote_plus(keyword)}&count={self.num_results}"
            resp = self._session.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            results: List[SERPResult] = []
            position = 1

            for item in soup.select("li.b_algo"):
                if position > self.num_results:
                    break
                a_tag = item.select_one("h2 a")
                if not a_tag:
                    continue

                raw_href = a_tag.get("href", "")
                actual_url = raw_href

                # Decode Bing tracking URL
                if "/ck/a?" in raw_href and "u=" in raw_href:
                    try:
                        import re
                        m = re.search(r"[?&]u=a1([a-zA-Z0-9_-]+)", raw_href)
                        if m:
                            b64_str = m.group(1) + "=="
                            actual_url = base64.urlsafe_b64decode(b64_str).decode("utf-8", errors="ignore")
                    except Exception:
                        actual_url = raw_href

                if not actual_url.startswith("http"):
                    continue

                title = a_tag.get_text(strip=True)
                snippet_el = item.select_one(".b_caption p, .b_algoDesc, p")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                domain = urlparse(actual_url).netloc.replace("www.", "")

                results.append(
                    SERPResult(
                        position=position,
                        url=actual_url,
                        title=title,
                        snippet=snippet,
                        domain=domain,
                    )
                )
                position += 1

            if not results:
                return None

            return SERPPage(keyword=keyword, results=results, source="bing")

        except Exception as e:
            logger.warning("Bing scrape error for '%s': %s", keyword, e)
            return None

    # ------------------------------------------------------------------
    # DuckDuckGo fallback
    # ------------------------------------------------------------------

    def _scrape_duckduckgo(self, keyword: str) -> Optional[SERPPage]:
        """Scrape DuckDuckGo HTML-only endpoint as a fallback."""
        logger.info("Falling back to DuckDuckGo for '%s'", keyword)
        try:
            resp = self._session.post(
                DUCKDUCKGO_HTML_URL,
                data={"q": keyword, "b": ""},
                headers=self._random_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("DuckDuckGo request failed: %s", exc)
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        results: List[SERPResult] = []
        links = soup.select("div.result, div.web-result")
        position = 1

        for block in links:
            if position > self.num_results:
                break
            link_el = block.select_one("a.result__a")
            if not link_el:
                continue
            href = link_el.get("href", "")
            # DuckDuckGo sometimes wraps URLs in a redirect
            if "uddg=" in href:
                from urllib.parse import parse_qs, urlparse as _up
                parsed = _up(href)
                qs = parse_qs(parsed.query)
                href = qs.get("uddg", [href])[0]

            if not href.startswith("http"):
                continue

            title = link_el.get_text(strip=True)
            snippet_el = block.select_one("a.result__snippet, div.result__snippet")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            domain = urlparse(href).netloc.replace("www.", "")

            results.append(
                SERPResult(
                    position=position,
                    url=href,
                    title=title,
                    snippet=snippet,
                    domain=domain,
                )
            )
            position += 1

        if not results:
            return None

        return SERPPage(
            keyword=keyword,
            results=results,
            source="duckduckgo",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(
        self,
        keywords: Union[List[str], str],
        num_results: Optional[int] = None,
    ) -> Any:
        """Scrape SERPs for a list of keywords or a single keyword.

        Tries Google first; on failure falls back to DuckDuckGo.
        """
        if num_results is not None:
            self.num_results = max(1, min(num_results, 100))

        is_single = isinstance(keywords, str)
        kw_list = [keywords] if is_single else keywords

        pages: List[SERPPage] = []
        total = len(kw_list)

        for idx, kw in enumerate(kw_list, start=1):
            kw = kw.strip()
            if not kw:
                continue

            if self.progress_callback:
                self.progress_callback(idx, total, kw)

            logger.info("Scraping SERP for '%s' (%d/%d)", kw, idx, total)

            page = self._scrape_google(kw)
            if page is None:
                page = self._scrape_duckduckgo(kw)
            if page is None:
                page = self._scrape_bing(kw)

            if page is not None:
                self._save_serp_page(page)
                pages.append(page)
                logger.info(
                    "Got %d results for '%s' via %s",
                    len(page.results),
                    kw,
                    page.source,
                )
            else:
                logger.warning("No results obtained for '%s'", kw)

            if idx < total:
                self._delay()

        if is_single:
            if pages:
                p = pages[0]
                return SERPAnalysis(
                    keyword=p.keyword,
                    results=p.results,
                    total_results=len(p.results),
                    search_engine=p.source,
                    people_also_ask=p.features.people_also_ask if p.features else [],
                    related_searches=p.features.related_searches if p.features else [],
                )
            return SERPAnalysis(keyword=str(keywords), results=[], total_results=0)

        return pages

    def scrape_single(self, keyword: str) -> Optional[SERPPage]:
        """Convenience: scrape a single keyword."""
        results = self.scrape([keyword])
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Search volume estimation via Google Suggest
    # ------------------------------------------------------------------

    def estimate_search_volume(
        self, keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """Estimate *relative* search volume using Google Autocomplete.

        Google returns suggestions in a rough popularity order.  We query
        each keyword and assign a normalised score (100 = first suggestion,
        lower = less popular).  This is **not** an absolute volume number
        but a useful relative ranking among a set of keywords.

        Returns
        -------
        list[dict]
            ``[{"keyword": str, "score": float, "rank": int, "suggestions": list[str]}, ...]``
        """
        volume_data: List[Dict[str, Any]] = []

        for kw in keywords:
            kw = kw.strip()
            if not kw:
                continue

            suggestions = self._get_google_suggestions(kw)
            # The keyword's rank within the suggestions list gives a rough
            # popularity proxy.  If it appears first it is very popular.
            kw_lower = kw.lower()
            rank = -1
            for i, s in enumerate(suggestions):
                if kw_lower in s.lower():
                    rank = i
                    break

            # Score: 100 if rank 0, decaying to 10 if rank 9, 0 if absent.
            if rank == -1:
                score = 0.0
            else:
                score = max(10.0, 100.0 - rank * 10.0)

            entry = {
                "keyword": kw,
                "score": score,
                "rank": rank if rank >= 0 else None,
                "suggestions": suggestions,
            }
            volume_data.append(entry)

            # Persist
            if self._db_conn:
                self._db_conn.execute(
                    """INSERT INTO search_volume_estimates
                       (keyword, score, rank, fetched_at) VALUES (?, ?, ?, ?)""",
                    (kw, score, rank if rank >= 0 else None, datetime.utcnow().isoformat()),
                )
                self._db_conn.commit()

            self._delay()

        return volume_data

    def _get_google_suggestions(self, keyword: str) -> List[str]:
        """Query Google Autocomplete and return suggestion strings."""
        params = {
            "client": "firefox",  # returns JSON
            "q": keyword,
            "hl": self.language,
        }
        text = self._get(GOOGLE_SUGGEST_URL, params=params)
        if not text:
            return []
        try:
            data = json.loads(text)
            if isinstance(data, list) and len(data) >= 2:
                return [s for s in data[1] if isinstance(s, str)]
        except (json.JSONDecodeError, IndexError):
            pass
        return []

    # ------------------------------------------------------------------
    # Result conversion helpers
    # ------------------------------------------------------------------

    def to_serp_analysis(self, page: SERPPage) -> SERPAnalysis:
        """Convert a SERPPage into the toolkit's ``SERPAnalysis`` model."""
        return SERPAnalysis(
            keyword=page.keyword,
            results=page.results,
            total_results=len(page.results),
            search_engine=page.source,
            language=self.language,
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release resources."""
        self._session.close()
        if self._db_conn:
            self._db_conn.close()

    def __enter__(self) -> "SERPScraper":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
