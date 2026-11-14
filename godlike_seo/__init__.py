"""
Godlike SEO Engine 2.0
======================

An evidence-backed, production-grade Python SEO diagnostic suite featuring
deterministic URL normalization, root-cause issue clustering, transparent
mathematical scoring, internal PageRank modeling, and competitive SERP reverse-engineering.
"""

__version__ = "2.0.0"
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
    "CrawlStatus",
    "normalize_url",
    "are_urls_equivalent",
    "__version__",
]
