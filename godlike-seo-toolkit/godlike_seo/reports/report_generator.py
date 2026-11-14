"""
SEO Report Generator 2.0.

Provides transparent, mathematically reproducible scoring with itemized
point deductions, issue clustering, and prioritized evidence-based recommendations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from godlike_seo.analyzers.content_analyzer import ContentAnalyzer
from godlike_seo.analyzers.issue_detector import SEOIssueDetector
from godlike_seo.analyzers.link_analyzer import LinkAnalyzer
from godlike_seo.analyzers.technical_analyzer import TechnicalAnalyzer
from godlike_seo.models import (
    CategoryScore,
    CompetitorAnalysis,
    CrawlResult,
    IssueCategory,
    IssueCluster,
    IssueSeverity,
    ScoreDeduction,
    SEOIssue,
    SEOReport,
    SERPAnalysis,
)

logger = logging.getLogger(__name__)

# Transparent mathematical penalty points per cluster severity
DEDUCTION_RATES = {
    IssueSeverity.CRITICAL: 15.0,
    IssueSeverity.HIGH: 8.0,
    IssueSeverity.MEDIUM: 3.0,
    IssueSeverity.LOW: 1.0,
    IssueSeverity.INFORMATIONAL: 0.0,
}


class ReportGenerator:
    """Combines crawl data, runs all audits, clusters findings, and computes transparent scores."""

    def __init__(self):
        self.issue_detector = SEOIssueDetector()
        self.content_analyzer = ContentAnalyzer()
        self.technical_analyzer = TechnicalAnalyzer()
        self.link_analyzer = LinkAnalyzer()

    def generate_report(
        self,
        crawl_result: CrawlResult,
        competitor_analyses: Optional[List[CompetitorAnalysis]] = None,
        serp_analyses: Optional[List[SERPAnalysis]] = None,
    ) -> SEOReport:
        pages = crawl_result.pages
        domain = crawl_result.domain or (urlparse(crawl_result.start_url).netloc if crawl_result.start_url else "")

        logger.info("Generating Evidence-Based SEO Report 3.0 for: %s (%d pages)", domain, len(pages))

        # 1. Run Link Analysis first to populate inlinks_count and internal PageRank
        link_audit = self.link_analyzer.analyze(pages)
        raw_issues: List[SEOIssue] = list(link_audit.get("issues", []))

        # Synchronize orphaned pages between crawler and link analyzer
        if link_audit.get("orphaned_pages") is not None:
            crawl_result.orphaned_pages = link_audit["orphaned_pages"]

        # 2. Run Issue Detector (Evidence-backed, using calibrated inlinks_count for 404 severity)
        raw_issues.extend(self.issue_detector.analyze(pages))

        # 3. Run Content Analysis
        content_audit = self.content_analyzer.analyze(pages)
        raw_issues.extend(content_audit.get("issues", []))

        # 4. Run Technical Analysis
        tech_audit = self.technical_analyzer.analyze(pages)
        raw_issues.extend(tech_audit.get("issues", []))

        # 5. Cluster identical issues across multiple URLs
        clusters: List[IssueCluster] = self.issue_detector.cluster_issues(raw_issues)

        # 6. Group clusters by category and compute reproducible scores
        cat_clusters: Dict[IssueCategory, List[IssueCluster]] = {}
        for c in clusters:
            cat_clusters.setdefault(c.category, []).append(c)

        all_deductions: List[ScoreDeduction] = []

        def build_category_score(
            cat_name: str,
            category: IssueCategory,
            total_tests: int,
            weight: float,
        ) -> CategoryScore:
            cat_list = cat_clusters.get(category, [])
            deductions: List[ScoreDeduction] = []
            score = 100.0

            for cluster in cat_list:
                pts = DEDUCTION_RATES.get(cluster.severity, 0.0)
                if pts > 0.0:
                    score -= pts
                    deduction = ScoreDeduction(
                        rule_title=cluster.title,
                        severity=cluster.severity,
                        points_deducted=pts,
                        reason=cluster.description,
                        affected_count=len(cluster.affected_urls),
                    )
                    deductions.append(deduction)
                    all_deductions.append(deduction)

            final_score = max(0.0, round(score, 1))
            tests_passed = max(0, total_tests - len(deductions))

            status = "PASSED"
            if final_score < 50:
                status = "FAILED"
            elif final_score < 75:
                status = "WARNING"
            elif final_score < 95:
                status = "GOOD"

            return CategoryScore(
                name=cat_name,
                score=final_score,
                weight=weight,
                tests_evaluated=total_tests,
                tests_passed=tests_passed,
                deductions=deductions,
                status=status,
            )

        category_scores: Dict[str, CategoryScore] = {
            "technical": build_category_score("Technical & Crawlability", IssueCategory.TECHNICAL, 10, 0.25),
            "on_page": build_category_score("On-Page & Metadata", IssueCategory.ON_PAGE, 8, 0.25),
            "content": build_category_score("Content & Topical Depth", IssueCategory.CONTENT, 6, 0.20),
            "internal_linking": build_category_score("Site Architecture & Links", IssueCategory.INTERNAL_LINKING, 6, 0.15),
            "mobile": build_category_score("Mobile & Responsive", IssueCategory.MOBILE, 4, 0.10),
            "security": build_category_score("Security & Standards", IssueCategory.SECURITY, 5, 0.05),
        }

        # Weighted Master Score
        overall_score = round(sum(cs.score * cs.weight for cs in category_scores.values()), 1)

        # 7. Actionable recommendations from clusters
        recommendations: List[str] = []
        for cluster in clusters:
            if cluster.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH):
                recs_text = f"[{cluster.severity.value.upper()}] {cluster.title}: {cluster.recommendation} (Affects {len(cluster.affected_urls)} pages)"
                if recs_text not in recommendations:
                    recommendations.append(recs_text)
            elif cluster.severity == IssueSeverity.MEDIUM and len(recommendations) < 10:
                recs_text = f"[MEDIUM] {cluster.title}: {cluster.recommendation} (Affects {len(cluster.affected_urls)} pages)"
                if recs_text not in recommendations:
                    recommendations.append(recs_text)

        summary_stats = {
            "total_pages_crawled": len(pages),
            "total_tests_evaluated": sum(cs.tests_evaluated for cs in category_scores.values()),
            "total_tests_passed": sum(cs.tests_passed for cs in category_scores.values()),
            "unique_issue_clusters": len(clusters),
            "total_raw_occurrences": len(raw_issues),
            "critical_clusters_count": len([c for c in clusters if c.severity == IssueSeverity.CRITICAL]),
            "high_clusters_count": len([c for c in clusters if c.severity == IssueSeverity.HIGH]),
            "medium_clusters_count": len([c for c in clusters if c.severity == IssueSeverity.MEDIUM]),
            "low_clusters_count": len([c for c in clusters if c.severity == IssueSeverity.LOW]),
            "info_clusters_count": len([c for c in clusters if c.severity == IssueSeverity.INFORMATIONAL]),
            "orphaned_pages_count": len(crawl_result.orphaned_pages),
            "average_response_time_ms": tech_audit.get("average_response_time_ms", 0),
            "average_word_count": content_audit.get("average_word_count", 0),
        }

        comp_analyses = competitor_analyses or []
        first_comp = comp_analyses[0] if comp_analyses else None

        return SEOReport(
            url=crawl_result.start_url,
            domain=domain,
            overall_score=overall_score,
            category_scores=category_scores,
            all_deductions=all_deductions,
            issue_clusters=clusters,
            raw_issues=raw_issues,
            recommendations=recommendations,
            summary_stats=summary_stats,
            crawl_result=crawl_result,
            competitor_analyses=comp_analyses,
            competitor_analysis=first_comp,
            serp_analyses=serp_analyses or [],
        )
