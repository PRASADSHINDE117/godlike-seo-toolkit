"""
Google Search Console (GSC) Production API Integration.

Fetches and analyzes verified search performance metrics directly from Google:
- Clicks, Impressions, CTR, and Average Ranking Positions
- Striking Distance Opportunities (Keywords ranking at positions 8-20 ripe for page 1 wins)
- Underperforming High-Impression / Low-CTR Queries (Title/Snippet rewrite opportunities)
- Internal Keyword Cannibalization Detection
- Demo/Mock fallback for offline testing and onboarding without credentials
"""

from __future__ import annotations

import collections
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)

GSC_API_BASE = "https://www.googleapis.com/webmasters/v3/sites"


@dataclass
class GSCQueryPerformance:
    query: str
    page: str
    clicks: int
    impressions: int
    ctr: float          # Percentage, e.g. 3.4%
    position: float     # Average ranking position, e.g. 8.2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "page": self.page,
            "clicks": self.clicks,
            "impressions": self.impressions,
            "ctr": round(self.ctr, 2),
            "position": round(self.position, 1),
        }


@dataclass
class GSCReport:
    site_url: str
    start_date: str
    end_date: str
    total_clicks: int = 0
    total_impressions: int = 0
    average_ctr: float = 0.0
    average_position: float = 0.0
    queries: List[GSCQueryPerformance] = field(default_factory=list)
    striking_distance: List[GSCQueryPerformance] = field(default_factory=list)
    low_ctr_opportunities: List[GSCQueryPerformance] = field(default_factory=list)
    cannibalization_warnings: List[Dict[str, Any]] = field(default_factory=list)
    is_mock: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_url": self.site_url,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_clicks": self.total_clicks,
            "total_impressions": self.total_impressions,
            "average_ctr": round(self.average_ctr, 2),
            "average_position": round(self.average_position, 1),
            "queries_count": len(self.queries),
            "striking_distance_count": len(self.striking_distance),
            "low_ctr_opportunities_count": len(self.low_ctr_opportunities),
            "is_mock": self.is_mock,
        }


class GoogleSearchConsoleClient:
    """Client for Google Search Console Search Analytics API."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        credentials_file: Optional[str] = None,
        enable_demo_mode: bool = True,
    ):
        self.access_token = access_token or os.environ.get("GSC_ACCESS_TOKEN")
        self.credentials_file = credentials_file or os.environ.get("GSC_CREDENTIALS_JSON") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        self.enable_demo_mode = enable_demo_mode

    def _get_auth_header(self) -> Optional[Dict[str, str]]:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return None

    def fetch_search_analytics(
        self,
        site_url: str,
        days: int = 28,
        row_limit: int = 100,
    ) -> GSCReport:
        """Fetch real Search Analytics from GSC API or generate calibrated demo data."""
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        auth_headers = self._get_auth_header()

        # If live credentials available, execute live HTTP request
        if auth_headers:
            try:
                encoded_site = quote_plus(site_url)
                endpoint = f"{GSC_API_BASE}/{encoded_site}/searchAnalytics/query"
                payload = {
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": ["query", "page"],
                    "rowLimit": row_limit,
                }
                resp = requests.post(endpoint, headers=auth_headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("rows", [])
                    return self._process_rows(site_url, start_date, end_date, rows, is_mock=False)
                else:
                    logger.warning("GSC API responded with status %d: %s", resp.status_code, resp.text)
            except Exception as e:
                logger.warning("Failed communicating with GSC API: %s", e)

        # Fallback to demo/mock data if no credentials or request failed
        if self.enable_demo_mode:
            return self._generate_mock_report(site_url, start_date, end_date)

        return GSCReport(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            is_mock=False,
        )

    def _process_rows(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        rows: List[Dict[str, Any]],
        is_mock: bool = False,
    ) -> GSCReport:
        queries: List[GSCQueryPerformance] = []
        total_clicks = 0
        total_impressions = 0
        sum_position = 0.0

        query_to_pages: Dict[str, List[str]] = collections.defaultdict(list)

        for r in rows:
            keys = r.get("keys", ["", ""])
            q_text = keys[0] if len(keys) > 0 else ""
            p_url = keys[1] if len(keys) > 1 else site_url
            clicks = int(r.get("clicks", 0))
            impressions = int(r.get("impressions", 0))
            ctr = float(r.get("ctr", 0.0)) * 100.0
            pos = float(r.get("position", 0.0))

            perf = GSCQueryPerformance(
                query=q_text,
                page=p_url,
                clicks=clicks,
                impressions=impressions,
                ctr=ctr,
                position=pos,
            )
            queries.append(perf)
            total_clicks += clicks
            total_impressions += impressions
            sum_position += pos
            query_to_pages[q_text].append(p_url)

        n = len(queries)
        avg_ctr = (total_clicks / max(1, total_impressions)) * 100.0
        avg_pos = sum_position / max(1, n)

        # Striking Distance: Ranked positions 8 to 20 with solid impressions
        striking = [q for q in queries if 7.5 <= q.position <= 20.0 and q.impressions >= 50]
        striking.sort(key=lambda q: (q.impressions, -q.position), reverse=True)

        # Low CTR Opportunities: Ranking top 5 with CTR < 3%
        low_ctr = [q for q in queries if q.position <= 5.0 and q.ctr < 3.0 and q.impressions >= 100]
        low_ctr.sort(key=lambda q: q.impressions, reverse=True)

        # Cannibalization Detection: 1 query split across multiple landing pages
        cannibalization = []
        for q_name, p_list in query_to_pages.items():
            if len(set(p_list)) > 1:
                cannibalization.append({
                    "query": q_name,
                    "competing_pages": list(set(p_list)),
                })

        return GSCReport(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            total_clicks=total_clicks,
            total_impressions=total_impressions,
            average_ctr=avg_ctr,
            average_position=avg_pos,
            queries=queries,
            striking_distance=striking,
            low_ctr_opportunities=low_ctr,
            cannibalization_warnings=cannibalization,
            is_mock=is_mock,
        )

    def _generate_mock_report(self, site_url: str, start_date: str, end_date: str) -> GSCReport:
        """Provide realistic Search Console performance metrics for testing and demonstration."""
        from urllib.parse import urlparse
        domain = urlparse(site_url).netloc or "example.com"
        clean_name = domain.split(".")[0]

        mock_rows = [
            # Top 3 High performers
            {"keys": [f"{clean_name} reviews", f"https://{domain}/reviews"], "clicks": 420, "impressions": 3100, "ctr": 0.135, "position": 1.8},
            {"keys": [f"{clean_name} pricing", f"https://{domain}/pricing"], "clicks": 280, "impressions": 2400, "ctr": 0.116, "position": 2.3},
            # Low CTR Opportunity: Position 3.4 with 5200 impressions but only 1.2% CTR
            {"keys": [f"best {clean_name} alternatives", f"https://{domain}/comparison"], "clicks": 62, "impressions": 5200, "ctr": 0.012, "position": 3.4},
            # Striking Distance: Position 8.6 with 3800 impressions (ripe for page 1 jump)
            {"keys": [f"{clean_name} tutorial guide", f"https://{domain}/docs"], "clicks": 45, "impressions": 3800, "ctr": 0.011, "position": 8.6},
            {"keys": [f"how to setup {clean_name}", f"https://{domain}/setup"], "clicks": 38, "impressions": 2900, "ctr": 0.013, "position": 9.4},
            {"keys": [f"{clean_name} api documentation", f"https://{domain}/api"], "clicks": 30, "impressions": 2100, "ctr": 0.014, "position": 11.2},
            # Cannibalization: 2 pages competing for same query
            {"keys": [f"{clean_name} login portal", f"https://{domain}/login"], "clicks": 180, "impressions": 1200, "ctr": 0.150, "position": 1.1},
            {"keys": [f"{clean_name} login portal", f"https://{domain}/account"], "clicks": 25, "impressions": 800, "ctr": 0.031, "position": 4.5},
        ]
        return self._process_rows(site_url, start_date, end_date, mock_rows, is_mock=True)
