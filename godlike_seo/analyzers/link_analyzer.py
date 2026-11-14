"""
Link Graph and Internal PageRank Flow Analyzer.

Features:
- Internal PageRank algorithm (Power iteration with damping factor = 0.85)
- Orphaned page discovery (pages not reachable via internal navigation)
- Dead-end page detection (pages with no outgoing links)
- Crawl depth / Click depth analysis (pages > 3 clicks away from root)
- Anchor text distribution analysis (identifies generic anchors like "click here", "learn more")
- Internal equity flow and link distribution metrics
"""

from __future__ import annotations

import collections
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from godlike_seo.models import (
    PageData,
    PageType,
    SEOIssue,
    IssueSeverity,
    IssueCategory,
    IssueConfidence,
)
from godlike_seo.utils.url_normalizer import are_urls_equivalent

GENERIC_ANCHOR_TEXTS: Set[str] = {
    "click here", "here", "read more", "learn more", "more", "link",
    "page", "website", "this link", "continue", "view", "details", "check out"
}


@dataclass
class PageLinkStats:
    url: str
    inlinks_count: int = 0
    outlinks_count: int = 0
    pagerank_score: float = 0.0  # 0 to 100
    crawl_depth: int = 0
    is_orphaned: bool = False
    is_dead_end: bool = False
    inbound_anchors: List[str] = field(default_factory=list)


class LinkAnalyzer:
    """Computes internal graph topology, PageRank, and link health."""

    def __init__(self, damping_factor: float = 0.85, max_iterations: int = 40):
        self.damping_factor = damping_factor
        self.max_iterations = max_iterations

    def calculate_pagerank(
        self,
        nodes: Set[str],
        adj_list: Dict[str, Set[str]],
    ) -> Dict[str, float]:
        """Compute internal PageRank scores scaled 0-100 using power iteration."""
        N = len(nodes)
        if N == 0:
            return {}

        initial_val = 1.0 / N
        ranks: Dict[str, float] = {node: initial_val for node in nodes}

        # Inverse graph (target -> set of sources)
        in_nodes: Dict[str, Set[str]] = collections.defaultdict(set)
        out_counts: Dict[str, int] = {}

        for src, targets in adj_list.items():
            out_counts[src] = len(targets)
            for tgt in targets:
                if tgt in nodes:
                    in_nodes[tgt].add(src)

        for _ in range(self.max_iterations):
            new_ranks: Dict[str, float] = {}
            dangling_sum = sum(ranks[node] for node in nodes if out_counts.get(node, 0) == 0)

            for node in nodes:
                rank_sum = sum(
                    ranks[src] / out_counts[src]
                    for src in in_nodes.get(node, set())
                    if out_counts.get(src, 0) > 0
                )
                new_ranks[node] = (
                    (1.0 - self.damping_factor) / N
                    + self.damping_factor * (rank_sum + dangling_sum / N)
                )

            # Check convergence
            diff = sum(abs(new_ranks[n] - ranks[n]) for n in nodes)
            ranks = new_ranks
            if diff < 1e-6:
                break

        # Log-scale to 0 - 100
        max_r = max(ranks.values()) if ranks else 1.0
        min_r = min(ranks.values()) if ranks else 0.0
        range_r = max_r - min_r or 1.0

        scaled: Dict[str, float] = {}
        for node, val in ranks.items():
            # Normalized logarithm
            normalized = (val - min_r) / range_r
            score = round(10.0 + 90.0 * (math.sqrt(normalized)), 1)
            scaled[node] = score

        return scaled

    def analyze(self, pages: List[PageData]) -> Dict[str, Any]:
        """Perform full link graph and internal PageRank analysis."""
        nodes: Set[str] = {p.final_url or p.url for p in pages}
        adj_list: Dict[str, Set[str]] = collections.defaultdict(set)
        inbound_anchors: Dict[str, List[str]] = collections.defaultdict(list)
        inbound_details: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
        outbound_internal_edges: Dict[str, List[Tuple[str, str, str]]] = collections.defaultdict(list)

        generic_anchor_issues: List[Tuple[str, str, str]] = []  # (source, target, anchor)

        for p in pages:
            src = p.final_url or p.url
            for link in p.internal_links:
                tgt = link.href or link.url
                if tgt:
                    adj_list[src].add(tgt)
                    anchor = (link.anchor_text or link.anchor or "").strip()
                    loc = getattr(link, "location", "body")
                    outbound_internal_edges[src].append((tgt, anchor, loc))
                    inbound_anchors[tgt].append(anchor)
                    inbound_details[tgt].append({
                        "source": src,
                        "anchor": anchor,
                        "location": loc,
                    })
                    if anchor.lower() in GENERIC_ANCHOR_TEXTS:
                        generic_anchor_issues.append((src, tgt, anchor))

        pagerank_scores = self.calculate_pagerank(nodes, adj_list)

        page_stats: Dict[str, PageLinkStats] = {}
        orphaned_pages: List[str] = []
        dead_ends: List[str] = []
        deep_pages: List[str] = []

        root_url = pages[0].final_url or pages[0].url if pages else ""

        for p in pages:
            url = p.final_url or p.url
            in_internal_count = len(inbound_details.get(url, []))
            out_internal_count = len(p.internal_links)
            out_unique_targets = len(adj_list.get(url, set()))

            p.inlinks_count = in_internal_count
            p.internal_inlinks_count = in_internal_count
            p.internal_outlinks_count = out_internal_count
            p.external_outlinks_count = len(p.external_links)
            p.inbound_link_details = inbound_details.get(url, [])

            pr = pagerank_scores.get(url, 10.0)

            # Context-Aware Orphan Analysis:
            # Strictly an indexable PUBLIC_CONTENT document (status 200, not auth gate)
            # that receives 0 internal inlinks and is not the root homepage.
            is_orphan = (
                in_internal_count == 0
                and not are_urls_equivalent(url, root_url)
                and p.status_code == 200
                and p.is_indexable
                and getattr(p, "page_type", None) == PageType.PUBLIC_CONTENT
                and not getattr(p, "is_auth_gate", False)
            )

            # Dead-end check: Only for public content pages that have actual content
            is_dead = (
                out_internal_count == 0
                and p.status_code == 200
                and getattr(p, "page_type", None) == PageType.PUBLIC_CONTENT
                and not getattr(p, "is_auth_gate", False)
                and p.word_count >= 100
            )

            if is_orphan:
                orphaned_pages.append(url)
            if is_dead:
                dead_ends.append(url)
            if p.crawl_depth >= 4 and getattr(p, "page_type", None) == PageType.PUBLIC_CONTENT:
                deep_pages.append(url)

            page_stats[url] = PageLinkStats(
                url=url,
                inlinks_count=in_internal_count,
                outlinks_count=out_internal_count,
                pagerank_score=pr,
                crawl_depth=p.crawl_depth,
                is_orphaned=is_orphan,
                is_dead_end=is_dead,
                inbound_anchors=inbound_anchors.get(url, [])[:10],
            )

        issues: List[SEOIssue] = []

        # Flag verified orphaned public pages
        for orphan in orphaned_pages:
            issues.append(SEOIssue(
                issue_id="ORPHANED_PAGE_DETECTED",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.INTERNAL_LINKING,
                title="Orphaned Indexable Page (0 Inlinks)",
                description="Public indexable page receives 0 internal links from site navigation.",
                affected_url=orphan,
                evidence="Internal link graph analyzed: inlinks = 0.",
                observation="Page was discovered via sitemap or direct URL, but has zero inbound internal links from site navigation.",
                inference="Search engines rely on internal links to discover and assign PageRank authority to public content pages.",
                impact="Pages isolated from site architecture fail to receive PageRank and rarely rank for target queries.",
                recommendation="Link to this page contextually from relevant category pages, parent hubs, or related blog articles.",
                verification_step="Inspect internal links and verify at least one navigation link points to this page.",
                confidence=IssueConfidence.HIGH,
            ))

        # Flag dead ends
        for dead in dead_ends[:5]:
            issues.append(SEOIssue(
                issue_id="DEAD_END_PAGE",
                severity=IssueSeverity.LOW,
                category=IssueCategory.INTERNAL_LINKING,
                title="Dead-End Content Page (0 Outlinks)",
                description="Public content page has no outbound internal links.",
                affected_url=dead,
                evidence="Internal link graph analyzed: outlinks = 0.",
                observation="Document contains no <a> tags pointing to internal pages on the same domain.",
                inference="Users and bots reaching this page must use browser back navigation or exit the site.",
                impact="Traps PageRank equity and increases exit rates.",
                recommendation="Add contextual links to related content or a clear conversion call-to-action.",
                verification_step="Verify at least one internal link exists in the page body or footer.",
                confidence=IssueConfidence.HIGH,
            ))

        # Flag deep pages
        for deep in deep_pages[:5]:
            issues.append(SEOIssue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.INTERNAL_LINKING,
                title=f"Excessive Click Depth ({page_stats[deep].crawl_depth} clicks from home)",
                description="Important content buried deep in site hierarchy receives less Google crawl frequency.",
                affected_url=deep,
                recommendation="Flatten architecture. Bring important pages within 2-3 clicks from the homepage using breadcrumbs or category hubs.",
            ))

        # Generic anchor text issues
        if generic_anchor_issues:
            sample = generic_anchor_issues[0]
            issues.append(SEOIssue(
                severity=IssueSeverity.INFO,
                category=IssueCategory.INTERNAL_LINKING,
                title=f"Non-descriptive internal anchor text ({len(generic_anchor_issues)} found)",
                description=f"Using generic anchors like '{sample[2]}' provides zero keyword context to search crawlers.",
                affected_url=sample[0],
                recommendation="Replace generic anchor texts ('click here', 'read more') with descriptive keywords reflecting the destination page topic.",
            ))

        return {
            "page_stats": page_stats,
            "orphaned_pages": orphaned_pages,
            "dead_end_pages": dead_ends,
            "deep_pages": deep_pages,
            "generic_anchors_count": len(generic_anchor_issues),
            "top_pagerank_pages": sorted(
                page_stats.values(), key=lambda s: s.pagerank_score, reverse=True
            )[:10],
            "issues": issues,
        }
