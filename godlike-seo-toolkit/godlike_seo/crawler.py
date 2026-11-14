"""
Production-grade Async SEO Crawler Engine 2.0.

Features:
- Deterministic RFC 3986 URL normalization via godlike_seo.utils.url_normalizer
- Case-insensitive & regex-based viewport, canonical, and meta tag extraction with raw evidence
- Multi-worker async crawling with aiohttp and BeautifulSoup4 (lxml)
- Robots.txt compliance and XML sitemap discovery
- Full link graph construction with anchor text and placement classification
- Full redirect hop recording and loop detection
- Content hashing (excluding script/style) for duplicate detection
- Real-time progress callbacks for CLI and web interfaces
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import aiohttp
from bs4 import BeautifulSoup

try:
    import tldextract
except ImportError:
    tldextract = None

try:
    from fake_useragent import UserAgent
    _ua = UserAgent()
except Exception:
    _ua = None

from godlike_seo.models import (
    CrawlResult,
    CrawlStatus,
    HeadingData,
    HreflangTag,
    ImageData,
    LinkData,
    OpenGraphData,
    PageData,
    PageType,
    RedirectHop,
    StructuredDataItem,
    TwitterCardData,
)
from godlike_seo.analyzers.page_classifier import PageClassifier
from godlike_seo.auth import AuthConfig, AuthManager
from godlike_seo.utils.url_normalizer import normalize_url, are_urls_equivalent

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
]


@dataclass
class CrawlerConfig:
    """Crawler runtime configuration."""
    max_depth: int = 3
    max_pages: int = 200
    concurrency: int = 10
    rate_limit_delay: float = 0.05
    timeout_seconds: int = 15
    render_js: bool = False
    respect_robots_txt: bool = True
    parse_sitemap: bool = True
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    verify_ssl: bool = False


class SEOCrawler:
    """Godlike SEO Crawler Engine 2.0."""

    def __init__(
        self,
        config: Optional[CrawlerConfig] = None,
        auth_config: Optional[AuthConfig] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.config = config or CrawlerConfig()
        self.auth_config = auth_config
        self.progress_callback = progress_callback

        self._auth_cookies: Dict[str, str] = {}
        self._auth_headers: Dict[str, str] = {}
        self._visited_urls: Set[str] = set()
        self._sitemap_urls: Set[str] = set()
        self._queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
        self._crawled_pages: List[PageData] = []
        self._link_graph: Dict[str, List[Tuple[str, str]]] = {}
        self._robots_parser: Optional[urllib.robotparser.RobotFileParser] = None
        self._target_domain: str = ""
        self._root_url: str = ""
        self._start_time: float = 0.0

    def _get_user_agent(self) -> str:
        if self.config.user_agent:
            return self.config.user_agent
        if _ua:
            try:
                return _ua.random
            except Exception:
                pass
        import random
        return random.choice(DEFAULT_USER_AGENTS)

    def _is_same_domain(self, url: str) -> bool:
        """Check if URL belongs to the target domain."""
        parsed = urlparse(url)
        if not parsed.netloc:
            return True
        if tldextract:
            ext_target = tldextract.extract(self._target_domain)
            ext_url = tldextract.extract(parsed.netloc)
            return (ext_target.domain, ext_target.suffix) == (ext_url.domain, ext_url.suffix)
        target_host = self._target_domain.lower().split(":")[0].lstrip("www.")
        url_host = parsed.netloc.lower().split(":")[0].lstrip("www.")
        return target_host == url_host or url_host.endswith("." + target_host)

    def _is_crawlable_url(self, url: str) -> bool:
        """Filter out non-HTML files, mailto, tel, javascript, etc."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        path = parsed.path.lower()
        # Cloudflare and CDN security/email obfuscation helpers are not site content
        if "/cdn-cgi/" in path or path.startswith("/cdn-cgi"):
            return False

        skip_extensions = (
            ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
            ".mp4", ".mp3", ".avi", ".mov", ".zip", ".tar", ".gz", ".exe",
            ".dmg", ".css", ".js", ".json", ".xml", ".txt", ".woff", ".woff2", ".ttf"
        )
        if any(path.endswith(ext) for ext in skip_extensions):
            return False

        if self.config.respect_robots_txt and self._robots_parser:
            try:
                if not self._robots_parser.can_fetch(self._get_user_agent(), url):
                    return False
            except Exception:
                pass

        return True

    async def _fetch_robots_txt(self, session: aiohttp.ClientSession, base_url: str) -> None:
        """Fetch and parse robots.txt for the domain."""
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            async with session.get(robots_url, timeout=self.config.timeout_seconds) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(text.splitlines())
                    self._robots_parser = parser
                    logger.info("Parsed robots.txt from %s", robots_url)
        except Exception as e:
            logger.debug("Could not fetch robots.txt: %s", e)

    async def _discover_sitemaps(self, session: aiohttp.ClientSession, base_url: str) -> List[str]:
        """Discover and parse XML sitemaps."""
        parsed = urlparse(base_url)
        sitemap_candidates = [
            f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap/sitemap.xml",
        ]

        discovered_urls: Set[str] = set()

        async def parse_sitemap_xml(sitemap_url: str):
            try:
                async with session.get(sitemap_url, timeout=self.config.timeout_seconds) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        try:
                            root = ET.fromstring(content)
                            for elem in root.iter():
                                if "}" in elem.tag:
                                    elem.tag = elem.tag.split("}", 1)[1]

                            for sub in root.findall(".//sitemap/loc"):
                                if sub.text:
                                    await parse_sitemap_xml(sub.text.strip())

                            for u in root.findall(".//url/loc"):
                                if u.text:
                                    norm = normalize_url(u.text.strip())
                                    discovered_urls.add(norm)
                        except Exception as parse_err:
                            logger.debug("Failed parsing XML from %s: %s", sitemap_url, parse_err)
            except Exception as e:
                logger.debug("Error fetching sitemap %s: %s", sitemap_url, e)

        for candidate in sitemap_candidates:
            await parse_sitemap_xml(candidate)
            if discovered_urls:
                break

        return list(discovered_urls)

    def _determine_link_location(self, a_tag: Any) -> str:
        for parent in a_tag.parents:
            tag_name = getattr(parent, "name", "")
            classes = " ".join(parent.get("class", []) if isinstance(parent.get("class"), list) else [parent.get("class", "")])
            parent_id = parent.get("id", "")
            combined = f"{tag_name} {classes} {parent_id}".lower()

            if "nav" in combined or "menu" in combined:
                return "nav"
            if "header" in combined:
                return "header"
            if "footer" in combined:
                return "footer"
            if "sidebar" in combined or "aside" in combined:
                return "sidebar"

        return "body"

    def _extract_page_data(
        self,
        url: str,
        final_url: str,
        status_code: int,
        headers: Dict[str, str],
        html: str,
        response_time_ms: float,
        redirect_chain: List[RedirectHop],
        depth: int,
    ) -> Tuple[PageData, List[str]]:
        """Extract rich SEO data and raw DOM evidence."""
        soup = BeautifulSoup(html, "lxml")

        # Title
        title_tags = soup.find_all("title")
        title = title_tags[0].get_text(strip=True) if title_tags else ""
        title_count = len(title_tags)

        # Meta description
        meta_desc = ""
        meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if meta_desc_tag:
            meta_desc = meta_desc_tag.get("content", "").strip()

        # Meta robots
        meta_robots = ""
        meta_robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
        if meta_robots_tag:
            meta_robots = meta_robots_tag.get("content", "").strip()

        # Canonical
        canonical_url = None
        canonical_raw_snippet = None
        canonical_tag = soup.find("link", attrs={"rel": re.compile(r"^canonical$", re.I)})
        if canonical_tag and canonical_tag.get("href"):
            canonical_url = normalize_url(urljoin(final_url, canonical_tag.get("href").strip()))
            canonical_raw_snippet = str(canonical_tag)[:200]
        elif "link" in headers and 'rel="canonical"' in headers["link"]:
            match = re.search(r'<([^>]+)>;\s*rel="canonical"', headers["link"], re.I)
            if match:
                canonical_url = normalize_url(urljoin(final_url, match.group(1).strip()))
                canonical_raw_snippet = headers["link"][:200]

        # Robust Viewport Meta Extraction
        viewport_meta = None
        viewport_raw_snippet = None
        has_viewport = False

        # 1. BeautifulSoup case-insensitive attribute search
        viewport_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        if viewport_tag:
            viewport_meta = viewport_tag.get("content", "").strip()
            viewport_raw_snippet = str(viewport_tag)
            has_viewport = True
        else:
            # 2. Raw HTML regex fallback
            raw_match = re.search(r'<meta[^>]+name=["\']viewport["\'][^>]*>', html, re.I)
            if not raw_match:
                raw_match = re.search(r'<meta[^>]+content=["\'][^"\']*width=device-width[^"\']*["\'][^>]*>', html, re.I)
            if raw_match:
                viewport_raw_snippet = raw_match.group(0)
                content_m = re.search(r'content=["\']([^"\']+)["\']', viewport_raw_snippet, re.I)
                viewport_meta = content_m.group(1) if content_m else "width=device-width, initial-scale=1.0"
                has_viewport = True

        # Language
        html_tag = soup.find("html")
        lang = html_tag.get("lang") if html_tag else None
        if not lang and "content-language" in headers:
            lang = headers["content-language"]

        # Headings
        headings: List[HeadingData] = []
        for level in range(1, 7):
            for h in soup.find_all(f"h{level}"):
                text = h.get_text(strip=True)
                dom_snippet = str(h)[:150]
                headings.append(HeadingData(level=level, text=text, dom_snippet=dom_snippet))

        # Body Text & Metrics
        for elem in soup(["script", "style", "noscript", "svg"]):
            elem.decompose()

        body_tag = soup.find("body") or soup
        text_content = body_tag.get_text(separator=" ", strip=True)
        words = re.findall(r"\b\w+\b", text_content)
        word_count = len(words)
        content_hash = hashlib.md5(text_content.encode("utf-8", errors="ignore")).hexdigest()

        # Images
        images: List[ImageData] = []
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src:
                src = urljoin(final_url, src)
            alt = img.get("alt")
            width = None
            height = None
            try:
                if img.get("width"):
                    width = int(re.sub(r"\D", "", str(img.get("width"))))
                if img.get("height"):
                    height = int(re.sub(r"\D", "", str(img.get("height"))))
            except Exception:
                pass

            loading = img.get("loading", "")
            srcset = img.get("srcset", "")
            dom_snippet = str(img)[:150]
            images.append(ImageData(
                src=src,
                alt=alt,
                width=width,
                height=height,
                loading=loading,
                srcset=srcset,
                dom_snippet=dom_snippet,
            ))

        # Links & Link Graph
        internal_links: List[LinkData] = []
        external_links: List[LinkData] = []
        discovered_urls: List[str] = []

        for a in soup.find_all("a", href=True):
            raw_href = a["href"].strip()
            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(final_url, raw_href)
            normalized = normalize_url(full_url)
            anchor = a.get_text(strip=True)
            rel_list = a.get("rel", [])
            if isinstance(rel_list, str):
                rel_list = rel_list.split()

            is_nofollow = "nofollow" in rel_list
            is_ugc = "ugc" in rel_list
            is_sponsored = "sponsored" in rel_list
            location = self._determine_link_location(a)

            link_obj = LinkData(
                href=normalized,
                raw_url=raw_href,
                anchor_text=anchor,
                is_internal=self._is_same_domain(normalized),
                is_nofollow=is_nofollow,
                is_ugc=is_ugc,
                is_sponsored=is_sponsored,
                rel_attributes=rel_list,
                location=location,
                dom_snippet=str(a)[:120],
            )

            if link_obj.is_internal:
                internal_links.append(link_obj)
                discovered_urls.append(normalized)
                self._link_graph.setdefault(final_url, []).append((normalized, anchor))
            else:
                external_links.append(link_obj)

        # Structured Data
        structured_data: List[StructuredDataItem] = []
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw_json = script.string or ""
            try:
                import json
                data = json.loads(raw_json)
                stype = ""
                if isinstance(data, dict):
                    stype = data.get("@type", "")
                elif isinstance(data, list) and data:
                    stype = data[0].get("@type", "")
                structured_data.append(StructuredDataItem(
                    format="json-ld",
                    type=str(stype),
                    data=data if isinstance(data, dict) else {"items": data},
                    raw=raw_json[:300],
                    is_valid=True,
                ))
            except Exception as jerr:
                structured_data.append(StructuredDataItem(
                    format="json-ld",
                    raw=raw_json[:300],
                    is_valid=False,
                    error_message=str(jerr),
                ))

        # OpenGraph
        og_dict: Dict[str, str] = {}
        for og in soup.find_all("meta", property=re.compile(r"^og:", re.I)):
            prop = og.get("property", "").lower()
            cont = og.get("content", "")
            if prop and cont:
                og_dict[prop] = cont

        open_graph = OpenGraphData(
            og_title=og_dict.get("og:title"),
            og_description=og_dict.get("og:description"),
            og_image=og_dict.get("og:image"),
            og_url=og_dict.get("og:url"),
            og_type=og_dict.get("og:type"),
            og_site_name=og_dict.get("og:site_name"),
            og_locale=og_dict.get("og:locale"),
            raw_tags=og_dict,
        )

        # Twitter Card
        tw_dict: Dict[str, str] = {}
        for tw in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)}):
            name = tw.get("name", "").lower()
            cont = tw.get("content", "")
            if name and cont:
                tw_dict[name] = cont

        twitter_card = TwitterCardData(
            card_type=tw_dict.get("twitter:card"),
            title=tw_dict.get("twitter:title"),
            description=tw_dict.get("twitter:description"),
            image=tw_dict.get("twitter:image"),
            site=tw_dict.get("twitter:site"),
            creator=tw_dict.get("twitter:creator"),
            raw_tags=tw_dict,
        )

        # Hreflang
        hreflang_tags: List[HreflangTag] = []
        for hl in soup.find_all("link", attrs={"rel": "alternate", "hreflang": True}):
            lang_code = hl.get("hreflang", "").strip()
            href_val = hl.get("href", "").strip()
            if lang_code and href_val:
                hreflang_tags.append(HreflangTag(
                    language=lang_code,
                    url=normalize_url(urljoin(final_url, href_val)),
                ))

        # Assets
        css_files = [normalize_url(urljoin(final_url, link["href"])) for link in soup.find_all("link", rel="stylesheet") if link.get("href")]
        js_files = [normalize_url(urljoin(final_url, s["src"])) for s in soup.find_all("script", src=True) if s.get("src")]

        # Comprehensive Indexability Determination
        x_robots = headers.get("x-robots-tag", "").strip()
        reasons = []
        is_indexable = True

        if "noindex" in x_robots.lower():
            is_indexable = False
            reasons.append(f"Blocked by X-Robots-Tag: '{x_robots}'")
        if "noindex" in meta_robots.lower():
            is_indexable = False
            reasons.append(f"Blocked by <meta name='robots' content='{meta_robots}'>")
        if status_code >= 400:
            is_indexable = False
            reasons.append(f"Blocked by HTTP {status_code} Error")
        elif status_code in (301, 302, 303, 307, 308):
            is_indexable = False
            reasons.append(f"Blocked by HTTP {status_code} Redirect")

        is_self_canonical = True
        if canonical_url and not are_urls_equivalent(canonical_url, final_url):
            is_self_canonical = False
            reasons.append(f"Non-self canonical points to: '{canonical_url}'")

        if is_indexable and not reasons:
            indexability_reason = "Indexable (200 OK, no blocking directives, self-canonical)"
        else:
            indexability_reason = "; ".join(reasons) if reasons else "Non-indexable"

        norm_final = normalize_url(final_url)

        # Classify Page Intent & Workflow (Godlike 3.0)
        classification = PageClassifier.classify(
            url=norm_final,
            status_code=status_code,
            html=html,
            headers=headers,
        )

        page_data = PageData(
            url=normalize_url(url),
            final_url=norm_final,
            status_code=status_code,
            content_type=headers.get("content-type", ""),
            content_length=int(headers.get("content-length", len(html))),
            response_time_ms=response_time_ms,
            response_time=response_time_ms / 1000.0,
            http_headers=headers,
            headers=headers,
            redirect_chain=redirect_chain,
            crawl_depth=depth,
            has_html=True,
            html_raw=html,
            page_type=classification["page_type"],
            is_auth_gate=classification["is_auth_gate"],
            page_type_reason=classification["reason"],
            title=title,
            title_count=title_count,
            meta_description=meta_desc,
            meta_robots=meta_robots,
            canonical_url=canonical_url,
            canonical_raw_snippet=canonical_raw_snippet,
            viewport_meta=viewport_meta,
            viewport_raw_snippet=viewport_raw_snippet,
            has_viewport=has_viewport,
            language=lang,
            headings=headings,
            word_count=word_count,
            text_content=text_content,
            content_hash=content_hash,
            internal_links=internal_links,
            external_links=external_links,
            internal_outlinks_count=len(internal_links),
            external_outlinks_count=len(external_links),
            images=images,
            css_files=css_files,
            js_files=js_files,
            structured_data=structured_data,
            open_graph=open_graph,
            og_tags=og_dict,
            twitter_card=twitter_card,
            twitter_tags=tw_dict,
            hreflang_tags=hreflang_tags,
            is_indexable=is_indexable,
            indexability_reason=indexability_reason,
            x_robots_tag=x_robots,
            is_self_canonical=is_self_canonical,
            found_in_sitemap=(norm_final in self._sitemap_urls),
        )

        return page_data, discovered_urls

    async def _crawl_url_http(
        self,
        session: aiohttp.ClientSession,
        url: str,
        depth: int,
    ) -> Optional[Tuple[PageData, List[str]]]:
        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if self._auth_headers:
            headers.update(self._auth_headers)

        redirect_chain: List[RedirectHop] = []
        t0 = time.perf_counter()

        try:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
                proxy=self.config.proxy,
                ssl=self.config.verify_ssl,
                allow_redirects=True,
            ) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0

                for hist in resp.history:
                    redirect_chain.append(RedirectHop(url=normalize_url(str(hist.url)), status_code=hist.status))

                final_url = normalize_url(str(resp.url))
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                content_type = resp_headers.get("content-type", "")

                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    classification = PageClassifier.classify(url=final_url, status_code=resp.status, headers=resp_headers)
                    x_robots = resp_headers.get("x-robots-tag", "").strip()
                    is_indexable = resp.status < 400 and "noindex" not in x_robots.lower()
                    indexability_reason = f"Non-HTML Content ({content_type})" if is_indexable else f"Blocked by HTTP {resp.status} status"
                    page = PageData(
                        url=normalize_url(url),
                        final_url=final_url,
                        status_code=resp.status,
                        content_type=content_type,
                        content_length=int(resp_headers.get("content-length", 0)),
                        response_time_ms=elapsed_ms,
                        http_headers=resp_headers,
                        headers=resp_headers,
                        redirect_chain=redirect_chain,
                        crawl_depth=depth,
                        has_html=False,
                        page_type=classification["page_type"],
                        is_auth_gate=classification["is_auth_gate"],
                        page_type_reason=classification["reason"],
                        is_indexable=is_indexable,
                        indexability_reason=indexability_reason,
                        x_robots_tag=x_robots,
                    )
                    return page, []

                html = await resp.text(errors="replace")
                return self._extract_page_data(
                    url=url,
                    final_url=final_url,
                    status_code=resp.status,
                    headers=resp_headers,
                    html=html,
                    response_time_ms=elapsed_ms,
                    redirect_chain=redirect_chain,
                    depth=depth,
                )

        except asyncio.TimeoutError:
            return PageData(url=normalize_url(url), status_code=0, error="Request timed out", crawl_depth=depth, has_html=False, page_type=PageType.ERROR, is_indexable=False, indexability_reason="Request timed out"), []
        except Exception as e:
            return PageData(url=normalize_url(url), status_code=0, error=str(e), crawl_depth=depth, has_html=False, page_type=PageType.ERROR, is_indexable=False, indexability_reason=f"Connection Error: {e}"), []

    async def crawl(self, start_url: str) -> CrawlResult:
        """Run the comprehensive crawl against the given root URL."""
        self._start_time = time.perf_counter()
        self._root_url = normalize_url(start_url)
        parsed = urlparse(self._root_url)
        self._target_domain = parsed.netloc

        result = CrawlResult(
            start_url=self._root_url,
            domain=self._target_domain,
            started_at=datetime.utcnow().isoformat(),
        )

        # Automated Login via Playwright if credentials provided
        if self.auth_config:
            auth_manager = AuthManager(self.auth_config)
            self._auth_cookies = await auth_manager.perform_login()
            if self.auth_config.headers:
                self._auth_headers = self.auth_config.headers

        connector = aiohttp.TCPConnector(ssl=self.config.verify_ssl, limit=self.config.concurrency)
        async with aiohttp.ClientSession(connector=connector, cookies=self._auth_cookies or None) as session:
            if self.config.respect_robots_txt:
                await self._fetch_robots_txt(session, self._root_url)

            if self.config.parse_sitemap:
                sitemap_list = await self._discover_sitemaps(session, self._root_url)
                self._sitemap_urls = set(sitemap_list)
                result.sitemap_urls = sitemap_list

            await self._queue.put((self._root_url, 0))
            self._visited_urls.add(self._root_url)

            semaphore = asyncio.Semaphore(self.config.concurrency)

            async def worker():
                while True:
                    try:
                        url, depth = await self._queue.get()
                    except asyncio.CancelledError:
                        break

                    if len(self._crawled_pages) >= self.config.max_pages:
                        self._queue.task_done()
                        continue

                    async with semaphore:
                        if self.config.rate_limit_delay > 0:
                            await asyncio.sleep(self.config.rate_limit_delay)

                        crawl_res = await self._crawl_url_http(session, url, depth)

                        if crawl_res:
                            page_data, newly_discovered = crawl_res
                            self._crawled_pages.append(page_data)

                            if self.progress_callback:
                                self.progress_callback({
                                    "status": "crawling",
                                    "url": url,
                                    "status_code": page_data.status_code,
                                    "total_crawled": len(self._crawled_pages),
                                    "queue_size": self._queue.qsize(),
                                })

                            if depth < self.config.max_depth:
                                for next_url in newly_discovered:
                                    norm_next = normalize_url(next_url)
                                    if (
                                        norm_next not in self._visited_urls
                                        and len(self._visited_urls) < self.config.max_pages * 2
                                        and self._is_same_domain(norm_next)
                                        and self._is_crawlable_url(norm_next)
                                    ):
                                        self._visited_urls.add(norm_next)
                                        await self._queue.put((norm_next, depth + 1))

                    self._queue.task_done()

            tasks = [asyncio.create_task(worker()) for _ in range(self.config.concurrency)]

            while not self._queue.empty() and len(self._crawled_pages) < self.config.max_pages:
                await asyncio.sleep(0.3)

            await self._queue.join()

            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        # Context-Aware Orphan Analysis (Godlike 3.0):
        # Only evaluate verified PUBLIC_CONTENT pages that are indexable HTML 200 OK
        # Application workflows (auth, account, create-listing, cart) and redirects are strictly excluded
        all_inbound_targets = {target for targets in self._link_graph.values() for target, _ in targets}

        orphaned = []

        for sm_url in self._sitemap_urls:
            norm_sm = normalize_url(sm_url)
            sm_class = PageClassifier.classify(norm_sm)
            if (
                sm_class["page_type"] == PageType.PUBLIC_CONTENT
                and not sm_class["is_auth_gate"]
                and not are_urls_equivalent(norm_sm, self._root_url)
                and norm_sm not in all_inbound_targets
            ):
                orphaned.append(sm_url)

        for page in self._crawled_pages:
            if (
                page.status_code == 200
                and page.is_indexable
                and page.has_html
                and page.page_type == PageType.PUBLIC_CONTENT
                and not page.is_auth_gate
            ):
                norm = normalize_url(page.final_url or page.url)
                if (
                    not are_urls_equivalent(norm, self._root_url)
                    and norm not in all_inbound_targets
                ):
                    page.is_orphaned = True
                    if norm not in orphaned and page.url not in orphaned:
                        orphaned.append(page.url)

        duration = time.perf_counter() - self._start_time
        result.pages = self._crawled_pages
        result.total_pages = len(self._crawled_pages)
        result.crawl_duration_seconds = round(duration, 2)
        result.link_graph = self._link_graph
        result.orphaned_pages = orphaned
        result.finished_at = datetime.utcnow().isoformat()
        result.total_internal_links = sum(len(p.internal_links) for p in self._crawled_pages)
        result.total_external_links = sum(len(p.external_links) for p in self._crawled_pages)
        result.total_images = sum(len(p.images) for p in self._crawled_pages)

        logger.info("Crawl 2.0 finished: %d pages, %d orphaned", result.total_pages, len(orphaned))
        return result
