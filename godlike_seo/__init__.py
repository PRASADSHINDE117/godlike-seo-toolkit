"""
Godlike SEO Engine 3.3
======================

An evidence-backed, production-grade Python SEO diagnostic suite featuring
deterministic URL normalization, root-cause issue clustering, transparent
mathematical scoring, internal PageRank modeling, and competitive SERP reverse-engineering.
"""

__version__ = "3.3.0"
__author__ = "Godlike SEO Team"

from godlike_seo.models import (
    PageData,
    CrawlResult,
    SEOIssue,
    IssueCluster,
    ScoreDeduction,
    SEOReport,
    SERPResult,
    CompetitorAnalysis,
    IssueSeverity,
    IssueConfidence,
    IssueCategory,
    CanonicalState,
    CheckStatus,
    CheckResult,
    CrawlStatus,
)
from godlike_seo.utils.url_normalizer import normalize_url, are_urls_equivalent

__all__ = [
    "PageData",
    "CrawlResult",
    "SEOIssue",
    "IssueCluster",
    "ScoreDeduction",
    "SEOReport",
    "SERPResult",
    "CompetitorAnalysis",
    "IssueSeverity",
    "IssueConfidence",
    "IssueCategory",
    "CanonicalState",
    "CheckStatus",
    "CheckResult",
    "CrawlStatus",
    "normalize_url",
    "are_urls_equivalent",
    "__version__",
]
