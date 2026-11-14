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
            t0 = time.perf_counter()
            resp = requests.get(url, headers=headers, timeout=10, verify=False)
            metrics.response_time_ms = round((time.perf_counter() - t0) * 1000, 1)

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

        your_domain = urlparse(your_url).netloc

        # Determine your ranking position if already in SERP
        your_position = 0
        for item in serp_data.results:
            if your_domain in item.url or your_url.rstrip("/") in item.url:
                your_position = item.position
                break

        # Scrape your page
        your_metrics = self._scrape_page_metrics(your_url, target_keyword)
        your_metrics.position = your_position

        # Scrape competitors
        competitors: List[CompetitorMetrics] = []
        for res in serp_data.results:
            if your_domain not in res.url and len(competitors) < max_competitors:
                comp = self._scrape_page_metrics(res.url, target_keyword)
                comp.position = res.position
                competitors.append(comp)

        # Gap analysis and recommendations
        gaps: List[str] = []
        recommendations: List[str] = []

        if competitors:
            avg_comp_words = sum(c.word_count for c in competitors) / len(competitors)
            avg_comp_headings = sum(c.heading_count for c in competitors) / len(competitors)
            schema_count = sum(1 for c in competitors if c.has_structured_data)

            # 1. Word Count Comparison
            if your_metrics.word_count < avg_comp_words * 0.75:
                gap = f"Content Length Gap: Competitors average {avg_comp_words:.0f} words, while you have {your_metrics.word_count} words."
                gaps.append(gap)
                recommendations.append(
                    f"Expand content by at least {int(avg_comp_words - your_metrics.word_count)} words. "
                    "Google rewards comprehensive topical authority for this query."
                )

            # 2. Keyword in Title
            if not your_metrics.keyword_in_title:
                gaps.append(f"Title Optimization Gap: Target keyword '{target_keyword}' missing from your <title> tag.")
                recommendations.append(
                    f"Place '{target_keyword}' prominently at the beginning of your <title> tag."
                )

            # 3. Keyword in H1
            if not your_metrics.keyword_in_h1:
                gaps.append(f"H1 Header Gap: Target keyword '{target_keyword}' is missing from your H1 heading.")
                recommendations.append(
                    f"Include '{target_keyword}' directly in your single main H1 heading."
                )

            # 4. Heading structure
            if your_metrics.heading_count < avg_comp_headings * 0.6:
                gaps.append(f"Content Structure Gap: Competitors use {avg_comp_headings:.1f} subheadings (H2/H3), you have {your_metrics.heading_count}.")
                recommendations.append(
                    "Break your content into organized sub-topics with clear H2 and H3 subheadings."
                )

            # 5. Schema markup
            if not your_metrics.has_structured_data and schema_count >= 2:
                gaps.append("Structured Data Gap: Competitors use Schema.org JSON-LD structured data for rich snippets.")
                recommendations.append(
                    "Add JSON-LD Schema (Article, FAQPage, or Product) to qualify for Google rich search results."
                )

            # 6. Page Speed / TTFB
            avg_speed = sum(c.response_time_ms for c in competitors) / len(competitors)
            if your_metrics.response_time_ms > avg_speed * 1.5 and your_metrics.response_time_ms > 1000:
                gaps.append(f"Page Speed Gap: Your page loads in {your_metrics.response_time_ms:.0f}ms vs competitors average {avg_speed:.0f}ms.")
                recommendations.append(
                    "Improve server response time and enable caching to match or beat competitor speeds."
                )

        # Compute competitive gap score (0-100; 100 = parity or better)
        gap_penalty = min(80.0, len(gaps) * 15.0)
        gap_score = round(100.0 - gap_penalty, 1)

        return CompetitorAnalysis(
            keyword=target_keyword,
            your_url=your_url,
            your_position=your_position,
            competitors=competitors,
            gaps=gaps,
            recommendations=recommendations,
            competitive_gap_score=gap_score,
        )
