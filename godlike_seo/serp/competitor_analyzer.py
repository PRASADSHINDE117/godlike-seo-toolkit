"""
Competitor Analysis and SERP Benchmark Engine.

Features:
- Discovers top-ranking competitors for a user-specified query
- Crawls and scrapes top competitor landing pages
- Performs head-to-head comparison on 12+ on-page SEO ranking factors
- Computes Competitive Gap Score (0-100)
- Generates tactical recommendations for outranking competitors to reach #1
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from godlike_seo.models import (
    CompetitorAnalysis,
    CompetitorMetrics,
    SERPAnalysis,
    SERPResult,
)
from godlike_seo.serp.serp_scraper import SERPScraper

logger = logging.getLogger(__name__)


class CompetitorAnalyzer:
    """Compares your page against top-ranking SERP competitors to give actionable advice."""

    def __init__(self, scraper: Optional[SERPScraper] = None):
        self.scraper = scraper or SERPScraper()

    @staticmethod
    def _host(url: str) -> str:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")

    def _scrape_page_metrics(self, url: str, target_keyword: str) -> CompetitorMetrics:
        """Fetch a single page and calculate key on-page ranking factors."""
        parsed = urlparse(url)
        domain = parsed.netloc

        metrics = CompetitorMetrics(domain=domain, url=url)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            try:
                import certifi
                verify_target = certifi.where()
            except Exception:
                verify_target = True

            t0 = time.perf_counter()
            resp = requests.get(url, headers=headers, timeout=10, verify=verify_target)
            metrics.response_time_ms = round((time.perf_counter() - t0) * 1000, 1)
            metrics.http_status_code = resp.status_code
            metrics.fetch_status = "fetched" if resp.status_code == 200 else "http_error"

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")

                # Title
                title_tag = soup.find("title")
                metrics.title = title_tag.get_text(strip=True) if title_tag else ""

                # Meta desc
                meta = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
                metrics.meta_description = meta.get("content", "").strip() if meta else ""

                # H1
                h1_tag = soup.find("h1")
                metrics.h1 = h1_tag.get_text(strip=True) if h1_tag else ""

                # Headings count
                headings = soup.find_all(re.compile(r"^h[1-6]$"))
                metrics.heading_count = len(headings)

                # Links
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if domain in href or href.startswith("/"):
                        metrics.total_internal_links += 1
                    else:
                        metrics.total_external_links += 1

                # Images
                metrics.total_images = len(soup.find_all("img"))

                # Schema
                metrics.has_structured_data = bool(soup.find("script", attrs={"type": "application/ld+json"}))

                # OG tags
                metrics.has_og_tags = bool(soup.find("meta", property=re.compile(r"^og:", re.I)))

                # Text content & Word count
                for tag in soup(["script", "style", "noscript", "svg"]):
                    tag.decompose()
                body_text = soup.get_text(separator=" ", strip=True)
                words = re.findall(r"\b\w+\b", body_text.lower())
                metrics.word_count = len(words)

                # Keyword analysis
                kw_lower = target_keyword.lower().strip()
                kw_tokens = kw_lower.split()

                metrics.keyword_in_title = kw_lower in metrics.title.lower()
                metrics.keyword_in_h1 = kw_lower in metrics.h1.lower()
                metrics.keyword_in_meta = kw_lower in metrics.meta_description.lower()

                # Keyword density
                if words and kw_lower:
                    kw_count = len(re.findall(re.escape(kw_lower), body_text.lower()))
                    metrics.keyword_density = round((kw_count * len(kw_tokens) / len(words)) * 100, 2)

                # Content depth proxy score (0-100)
                depth = min(100.0, (metrics.word_count / 20.0) + (metrics.heading_count * 2.0) + (10 if metrics.has_structured_data else 0))
                metrics.content_depth_score = round(depth, 1)

        except Exception as e:
            metrics.fetch_status = "failed"
            metrics.fetch_error = type(e).__name__
            logger.debug("Failed scraping competitor %s: %s", url, e)

        return metrics

    def analyze_for_keyword(
        self,
        target_keyword: str,
        your_url: str,
        max_competitors: int = 5,
    ) -> CompetitorAnalysis:
        """Find top search results for the keyword and compare against your URL."""
        logger.info("Scraping SERP for '%s' to benchmark against %s", target_keyword, your_url)
        serp_data: SERPAnalysis = self.scraper.scrape(target_keyword, num_results=max_competitors + 5)

        your_domain = self._host(your_url)

        # Determine your ranking position if already in SERP
        your_position = 0
        for item in serp_data.results:
            if self._host(item.url) == your_domain:
                your_position = item.position
                break

        # Scrape your page
        your_metrics = self._scrape_page_metrics(your_url, target_keyword)
        your_metrics.position = your_position

        # Scrape competitors
        competitors: List[CompetitorMetrics] = []
        for res in serp_data.results:
            if self._host(res.url) != your_domain and len(competitors) < max_competitors:
                comp = self._scrape_page_metrics(res.url, target_keyword)
                comp.position = res.position
                competitors.append(comp)

        # Gap analysis and recommendations
        gaps: List[str] = []
        recommendations: List[str] = []

        if not competitors or serp_data.search_engine == "unavailable":
            gaps.append(
                "SERP Scraping Blocked or Rate-Limited: Competitor comparison could not obtain organic search results. "
                "Search engines may have presented anti-bot challenges or HTTP 429 rate limits."
            )
            recommendations.append(
                "Configure a rotating proxy in CrawlerConfig or integrate Google Search Console API for official impressions and ranking positions."
            )
            return CompetitorAnalysis(
                keyword=target_keyword,
                your_url=your_url,
                your_position=your_position,
                your_metrics=your_metrics,
                competitors=[],
                gaps=gaps,
                recommendations=recommendations,
                competitive_gap_score=0.0,
                ranking_probability_pct=0.0,
                parity_status="INCONCLUSIVE",
                search_engine=serp_data.search_engine,
                search_language=serp_data.search_language,
                search_country=serp_data.search_country,
                serp_results=[],
            )

        avg_comp_words = sum(c.word_count for c in competitors) / max(1, len(competitors))
        avg_comp_headings = sum(c.heading_count for c in competitors) / max(1, len(competitors))
        schema_count = sum(1 for c in competitors if c.has_structured_data)
        n_comp = len(competitors)

        # 1. Word Count Comparison (Advisory Heuristic)
        if your_metrics.word_count < avg_comp_words * 0.75:
            gap = f"Content Length Observation (Advisory, n={n_comp}): Competitors average {avg_comp_words:.0f} words, while you have {your_metrics.word_count} words."
            gaps.append(gap)
            recommendations.append(
                f"Heuristic Structural Gap Observation (n={n_comp}): Competitor pages average {avg_comp_words:.0f} words vs your {your_metrics.word_count} words. "
                "Note: Word count is not a direct Google ranking factor; review whether competitors answer related sub-topics, FAQs, or intent facets that your page omits."
            )

        # 2. Keyword in Title
        if not your_metrics.keyword_in_title:
            gaps.append(f"Title Optimization Gap: Target keyword '{target_keyword}' missing from your <title> tag.")
            recommendations.append(
                f"Place '{target_keyword}' prominently at the beginning of your <title> tag for topical clarity."
            )

        # 3. Keyword in H1
        if not your_metrics.keyword_in_h1:
            gaps.append(f"H1 Header Gap: Target keyword '{target_keyword}' is missing from your H1 heading.")
            recommendations.append(
                f"Include '{target_keyword}' directly in your single main H1 heading to confirm page subject."
            )

        # 4. Heading structure
        if your_metrics.heading_count < avg_comp_headings * 0.6:
            gaps.append(f"Content Structure Observation (n={n_comp}): Competitors use {avg_comp_headings:.1f} subheadings (H2/H3) on average, vs {your_metrics.heading_count} on your page.")
            recommendations.append(
                "Consider breaking your content into organized sub-topics with descriptive H2 and H3 subheadings for scannability."
            )

        # 5. Schema markup
        if not your_metrics.has_structured_data and schema_count >= 2:
            gaps.append(f"Structured Data Gap ({schema_count}/{n_comp} competitors): Top competitors provide Schema.org JSON-LD structured data.")
            recommendations.append(
                "Add JSON-LD Schema (Article, FAQPage, or Product) to qualify for Google rich search results."
            )

        # 6. HTTP Request Latency / Round-Trip Time
        avg_speed = sum(c.response_time_ms for c in competitors) / max(1, len(competitors))
        if your_metrics.response_time_ms > avg_speed * 1.5 and your_metrics.response_time_ms > 1000:
            gaps.append(f"HTTP Latency Gap: Your page round-trip latency is {your_metrics.response_time_ms:.0f}ms vs competitors average {avg_speed:.0f}ms.")
            recommendations.append(
                "Improve server response time (TTFB/RTT) and enable edge caching to improve server latency relative to competitors."
            )

        # Multi-factor Weighted Parity Modeling:
        # 1. Content Depth (30%):
        score_content = min(30.0, (your_metrics.word_count / max(100.0, avg_comp_words)) * 30.0)
        # 2. Keyword Topical Alignment (25%):
        score_kw = (15.0 if your_metrics.keyword_in_title else 0.0) + (10.0 if your_metrics.keyword_in_h1 else 0.0)
        # 3. Structured Data Readiness (20%):
        score_schema = 20.0 if your_metrics.has_structured_data else (10.0 if schema_count == 0 else 0.0)
        # 4. Latency Parity (15%):
        score_speed = 15.0 if your_metrics.response_time_ms <= avg_speed else max(0.0, 15.0 - ((your_metrics.response_time_ms - avg_speed) / 100.0))
        # 5. Technical Baseline (10%):
        score_tech = (5.0 if your_metrics.has_https else 0.0) + (5.0 if your_metrics.has_og_tags else 0.0)

        parity_score = round(min(100.0, max(10.0, score_content + score_kw + score_schema + score_speed + score_tech)), 1)

        # Calibrated Ranking Probability (0-100%):
        if your_position in (1, 2, 3):
            base_prob = 85.0
        elif your_position <= 10 and your_position > 0:
            base_prob = 65.0
        elif your_position <= 20 and your_position > 0:
            base_prob = 40.0
        else:
            base_prob = 20.0

        # Adjust based on on-page parity delta from neutral baseline (70)
        parity_delta = (parity_score - 70.0) * 0.35
        ranking_prob = min(95.0, max(5.0, round(base_prob + parity_delta, 1)))

        parity_status = "HIGH_COMPETITIVE_PARITY" if parity_score >= 80 else ("MODERATE_PARITY" if parity_score >= 60 else "NEEDS_OPTIMIZATION")

        return CompetitorAnalysis(
            keyword=target_keyword,
            your_url=your_url,
            your_position=your_position,
            your_metrics=your_metrics,
            competitors=competitors,
            gaps=gaps,
            recommendations=recommendations,
            competitive_gap_score=parity_score,
            ranking_probability_pct=ranking_prob,
            parity_status=parity_status,
            search_engine=serp_data.search_engine,
            search_language=serp_data.search_language,
            search_country=serp_data.search_country,
            serp_results=serp_data.results,
            serp_retrieved_at=serp_data.retrieved_at,
        )
