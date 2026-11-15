"""
Data models for the Godlike SEO Toolkit 2.0.

Defines all core dataclasses used throughout the toolkit for representing
crawled page data, evidence-backed SEO issues, issue clusters, SERP results,
competitor analysis, and reproducible scoring models.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IssueSeverity(str, Enum):
    """Calibrated severity classification."""
    CRITICAL = "critical"      # Directly blocks crawl, indexation, or causes 4xx/5xx/security errors
    HIGH = "high"              # Substantially degrades search visibility (missing title, canonical conflict)
    MEDIUM = "medium"          # Measurable ranking/UX defect (missing meta description, uncompressed assets, CLS)
    WARNING = "medium"         # Backward-compatible alias for MEDIUM
    LOW = "low"                # Minor on-page refinement (heading hierarchy, alt text length)
    INFORMATIONAL = "info"     # Opportunities & suggestions (Schema rich snippet opportunities, social tags)
    INFO = "info"              # Backward-compatible alias for INFORMATIONAL


class PageType(str, Enum):
    """Classification of page intent and technical workflow."""
    PUBLIC_CONTENT = "public_content"    # Indexable public marketing, blog, doc, product content
    USER_APP_ROUTE = "user_app_route"    # Private application workflows (/wishlist, /my-bookings, /cart)
    AUTHENTICATION = "authentication"    # Login, signup, password reset, soft auth walls
    SYSTEM_UTILITY = "system_utility"    # API endpoints, dynamic RSS feeds, search parameters
    REDIRECT = "redirect"                # 3xx redirect destinations
    ERROR = "error"                      # 4xx / 5xx error responses


class IssueConfidence(str, Enum):
    """Confidence level of the detection."""
    HIGH = "high"              # Deterministic check (e.g. HTTP status 404, missing title, SSL expiration)
    MEDIUM = "medium"          # High-probability heuristic (e.g. content uniqueness, heading flow)
    LOW = "low"                # Advisory suggestion


class IssueCategory(str, Enum):
    """Clear, standardized category taxonomy."""
    TECHNICAL = "technical"
    INDEXABILITY = "indexability"
    ON_PAGE = "on_page"
    CONTENT = "content"
    INTERNAL_LINKING = "internal_linking"
    PERFORMANCE = "performance"
    MOBILE = "mobile"
    SECURITY = "security"
    STRUCTURED_DATA = "structured_data"
    INTERNATIONAL = "international"
    SOCIAL = "social"


class CanonicalState(str, Enum):
    """Explicit taxonomy of canonical URL declarations."""
    MISSING = "missing"                      # No <link rel="canonical"> tag or HTTP Link header found
    SELF_REFERENCING = "self_referencing"    # Declares exact match to requested / normalized final URL
    CROSS_URL = "cross_url"                  # Declares different internal or external URL
    RELATIVE = "relative"                    # Declares relative path instead of absolute URL
    MULTIPLE = "multiple"                    # Multiple conflicting canonical directives declared
    INVALID = "invalid"                      # Malformed URL or non-HTTP scheme


class CheckStatus(str, Enum):
    """Audit rule execution ledger status."""
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"
    INCONCLUSIVE = "inconclusive"


# ---------------------------------------------------------------------------
# Base dict-compatible dataclass helper
# ---------------------------------------------------------------------------

class DictCompatible:
    """Provides dict-like .get(), ['key'], and .to_dict() serialization for dataclass models."""

    def get(self, key: str, default: Any = None) -> Any:
        val = getattr(self, key, None)
        if val is not None:
            return val
        aliases = getattr(self, "_aliases", {})
        if key in aliases:
            return getattr(self, aliases[key], default)
        return default

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None and not hasattr(self, key):
            raise KeyError(key)
        return val

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) or key in getattr(self, "_aliases", {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass fields, nested models, and enums into a JSON-serializable dictionary."""
        res: Dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            if isinstance(v, Enum):
                res[k] = v.value
            elif hasattr(v, "to_dict"):
                res[k] = v.to_dict()
            elif isinstance(v, list):
                res[k] = [
                    item.to_dict() if hasattr(item, "to_dict")
                    else (item.value if isinstance(item, Enum) else item)
                    for item in v
                ]
            elif isinstance(v, dict):
                res[k] = {
                    dk: dv.to_dict() if hasattr(dv, "to_dict")
                    else (dv.value if isinstance(dv, Enum) else dv)
                    for dk, dv in v.items()
                }
            else:
                res[k] = v
        return res


@dataclass
class CheckResult(DictCompatible):
    """A single deterministic audit rule execution entry in the ledger."""
    rule_id: str
    rule_version: str = "3.1"
    category: IssueCategory = IssueCategory.TECHNICAL
    status: CheckStatus = CheckStatus.PASS
    title: str = ""
    description: str = ""
    evidence: str = ""
    affected_count: int = 0
    affected_urls: List[str] = field(default_factory=list)


class CrawlStatus(str, Enum):
    """Status of a crawl job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Image / Link / Heading / Structured Data models
# ---------------------------------------------------------------------------

@dataclass
class ImageData(DictCompatible):
    """Data extracted from an <img> element."""
    src: str
    alt: Optional[str] = ""
    width: Optional[int] = None
    height: Optional[int] = None
    is_lazy_loaded: bool = False
    loading: str = ""
    file_size: Optional[int] = None
    size: int = 0
    srcset: str = ""
    is_above_fold: bool = False
    is_decorative: bool = False
    dom_snippet: str = ""
    url: Optional[str] = None
    size_bytes: Optional[int] = None

    _aliases = {
        "content_length": "file_size",
        "has_srcset": "srcset",
        "url": "src",
        "size_bytes": "file_size",
    }

    def __post_init__(self):
        if self.url and not self.src:
            self.src = self.url
        elif self.src and not self.url:
            self.url = self.src
        if self.size_bytes and not self.file_size:
            self.file_size = self.size_bytes
        elif self.file_size and not self.size_bytes:
            self.size_bytes = self.file_size
        if self.file_size and not self.size:
            self.size = self.file_size
        elif self.size and not self.file_size:
            self.file_size = self.size
        if self.size and not self.size_bytes:
            self.size_bytes = self.size
        if self.loading == "lazy":
            self.is_lazy_loaded = True


@dataclass
class LinkData(DictCompatible):
    """Data extracted from an <a> element."""
    href: str
    url: str = ""
    anchor_text: str = ""
    anchor: str = ""
    is_internal: bool = True
    is_nofollow: bool = False
    nofollow: bool = False
    is_ugc: bool = False
    is_sponsored: bool = False
    rel_attributes: List[str] = field(default_factory=list)
    status_code: Optional[int] = None
    raw_url: str = ""
    location: str = "body"  # nav, header, footer, sidebar, body
    dom_snippet: str = ""

    def __post_init__(self):
        if not self.url and self.href:
            self.url = self.href
        elif not self.href and self.url:
            self.href = self.url
        if not self.raw_url:
            self.raw_url = self.href or self.url
        if not self.anchor and self.anchor_text:
            self.anchor = self.anchor_text
        elif not self.anchor_text and self.anchor:
            self.anchor_text = self.anchor
        if self.is_nofollow:
            self.nofollow = True
        elif self.nofollow:
            self.is_nofollow = True


@dataclass
class HeadingData(DictCompatible):
    """A single heading element (h1-h6)."""
    level: int  # 1-6
    text: str
    dom_snippet: str = ""


@dataclass
class StructuredDataItem(DictCompatible):
    """Structured data extracted from page."""
    format: str = "json-ld"
    type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    is_valid: bool = True
    error_message: Optional[str] = None


@dataclass
class OpenGraphData(DictCompatible):
    """Open Graph meta tags."""
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_url: Optional[str] = None
    og_type: Optional[str] = None
    og_site_name: Optional[str] = None
    og_locale: Optional[str] = None
    raw_tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class TwitterCardData(DictCompatible):
    """Twitter Card meta tags."""
    card_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    site: Optional[str] = None
    creator: Optional[str] = None
    raw_tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class HreflangTag(DictCompatible):
    """An hreflang alternate link."""
    language: str
    url: str
    lang: str = ""
    href: str = ""

    def __post_init__(self):
        if not self.lang and self.language:
            self.lang = self.language
        elif not self.language and self.lang:
            self.language = self.lang
        if not self.href and self.url:
            self.href = self.url
        elif not self.url and self.href:
            self.url = self.href


@dataclass
class RedirectHop(DictCompatible):
    """A single hop in a redirect chain."""
    url: str
    status_code: int


# ---------------------------------------------------------------------------
# PageData – Primary crawled page model
# ---------------------------------------------------------------------------

@dataclass
class PageData(DictCompatible):
    """All extracted SEO data for a single crawled page."""

    # Core request / response info
    url: str
    final_url: str = ""
    status_code: int = 0
    content_type: str = ""
    content_length: int = 0
    response_time_ms: float = 0.0
    response_time: float = 0.0  # seconds
    http_headers: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    redirect_chain: List[RedirectHop] = field(default_factory=list)
    crawl_depth: int = 0
    crawled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Raw response body & DOM presence
    has_html: bool = True
    html_raw: str = ""

    # <head> meta
    title: str = ""
    title_count: int = 1
    meta_description: str = ""
    meta_description_count: int = 1
    all_meta_descriptions: List[str] = field(default_factory=list)
    meta_robots: str = ""
    robots_meta: str = ""
    robots_directives: Dict[str, Any] = field(default_factory=dict)
    is_snippet_blocked: bool = False
    snippet_blocking_reason: Optional[str] = None
    canonical_url: Optional[str] = None
    canonical_raw_snippet: Optional[str] = None
    viewport_meta: Optional[str] = None
    viewport_raw_snippet: Optional[str] = None
    has_viewport: bool = False
    language: Optional[str] = None
    lang_attribute: Optional[str] = None

    # Headings
    headings: List[HeadingData] = field(default_factory=list)
    source_h1_tags: List[str] = field(default_factory=list)
    rendered_h1_tags: List[str] = field(default_factory=list)

    # Body text metrics
    word_count: int = 0
    text_content: str = ""
    content_hash: str = ""

    # Links
    internal_links: List[LinkData] = field(default_factory=list)
    external_links: List[LinkData] = field(default_factory=list)

    # Images
    images: List[ImageData] = field(default_factory=list)

    # Assets
    css_files: List[str] = field(default_factory=list)
    js_files: List[str] = field(default_factory=list)

    # Structured data
    structured_data: List[StructuredDataItem] = field(default_factory=list)

    # Social meta
    open_graph: Optional[OpenGraphData] = None
    og_tags: Dict[str, str] = field(default_factory=dict)
    twitter_card: Optional[TwitterCardData] = None
    twitter_tags: Dict[str, str] = field(default_factory=dict)

    # International
    hreflang_tags: List[HreflangTag] = field(default_factory=list)

    # Classification & Workflow Intent
    page_type: PageType = PageType.PUBLIC_CONTENT
    is_auth_gate: bool = False
    page_type_reason: str = ""
    inlinks_count: int = 0
    internal_inlinks_count: int = 0
    internal_outlinks_count: int = 0
    external_outlinks_count: int = 0
    inbound_link_details: List[Dict[str, Any]] = field(default_factory=list)

    # Indexability & Directives
    is_indexable: bool = True
    indexability_reason: str = "Indexable (200 OK, no blocking directives)"
    x_robots_tag: str = ""
    is_self_canonical: bool = False
    canonical_state: CanonicalState = CanonicalState.MISSING
    found_in_sitemap: bool = False
    is_orphaned: bool = False

    # Rendering & DOM snapshots
    rendered_dom: Optional[str] = None
    raw_source_html: Optional[str] = None
    render_status: str = "static_http"

    # Error info
    error: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.page_type, str):
            try:
                self.page_type = PageType(self.page_type)
            except ValueError:
                self.page_type = PageType.PUBLIC_CONTENT
        if not self.headers and self.http_headers:
            self.headers = self.http_headers
        elif not self.http_headers and self.headers:
            self.http_headers = self.headers

        if not self.robots_meta and self.meta_robots:
            self.robots_meta = self.meta_robots
        elif not self.meta_robots and self.robots_meta:
            self.meta_robots = self.robots_meta

        if not self.lang_attribute and self.language:
            self.lang_attribute = self.language
        elif not self.language and self.lang_attribute:
            self.language = self.lang_attribute

        if not self.response_time and self.response_time_ms:
            self.response_time = self.response_time_ms / 1000.0
        elif not self.response_time_ms and self.response_time:
            self.response_time_ms = self.response_time * 1000.0

        if not self.final_url:
            self.final_url = self.url

        if self.viewport_meta or self.viewport_raw_snippet:
            self.has_viewport = True

    @property
    def h1_tags(self) -> List[str]:
        return [h.text for h in self.headings if h.level == 1]

    @property
    def h2_tags(self) -> List[str]:
        return [h.text for h in self.headings if h.level == 2]

    @property
    def h3_tags(self) -> List[str]:
        return [h.text for h in self.headings if h.level == 3]

    @property
    def h4_tags(self) -> List[str]:
        return [h.text for h in self.headings if h.level == 4]

    @property
    def h5_tags(self) -> List[str]:
        return [h.text for h in self.headings if h.level == 5]

    @property
    def h6_tags(self) -> List[str]:
        return [h.text for h in self.headings if h.level == 6]

    @property
    def total_links(self) -> int:
        return len(self.internal_links) + len(self.external_links)

    @property
    def images_without_alt(self) -> List[ImageData]:
        return [img for img in self.images if not (img.alt or "").strip()]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        pt = getattr(self, "page_type", None)
        if hasattr(pt, "value"):
            d["page_type"] = pt.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ---------------------------------------------------------------------------
# CrawlResult
# ---------------------------------------------------------------------------

@dataclass
class CrawlResult(DictCompatible):
    """Collection of all crawled pages plus crawl-level metadata."""

    pages: List[PageData] = field(default_factory=list)
    start_url: str = ""
    domain: str = ""
    total_pages: int = 0
    total_internal_links: int = 0
    total_external_links: int = 0
    total_images: int = 0
    crawl_duration_seconds: float = 0.0
    crawl_status: CrawlStatus = CrawlStatus.COMPLETED
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None
    sitemap_urls: List[str] = field(default_factory=list)
    orphaned_pages: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    environment: Optional[str] = None
    pages_discovered_count: int = 0
    crawl_coverage_pct: float = 100.0
    robots_sitemaps: List[str] = field(default_factory=list)
    sitemaps_attempted: bool = False
    robots_attempted: bool = False

    # Link graph: source_url -> [(target_url, anchor_text)]
    link_graph: Dict[str, List[tuple]] = field(default_factory=dict)

    # Configuration metadata
    js_rendering_enabled: bool = False
    max_depth_reached: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        pt = getattr(self, "page_type", None)
        if hasattr(pt, "value"):
            d["page_type"] = pt.value
        return d


# ---------------------------------------------------------------------------
# SEOIssue & IssueCluster (Evidence-backed and clustered)
# ---------------------------------------------------------------------------

@dataclass
class SEOIssue(DictCompatible):
    """Evidence-backed SEO issue."""

    issue_id: str = "GENERIC_SEO_ISSUE"
    severity: IssueSeverity = IssueSeverity.MEDIUM
    category: IssueCategory = IssueCategory.TECHNICAL
    title: str = ""
    description: str = ""
    affected_url: str = ""
    affected_urls: List[str] = field(default_factory=list)
    evidence: str = ""
    observation: str = ""              # Concrete, objective, measurable fact
    inference: str = ""                # Contextual SEO risk/interpretation
    impact: str = ""
    recommendation: str = ""
    verification_step: str = ""
    confidence: IssueConfidence = IssueConfidence.HIGH
    url: str = ""                      # Alias for affected_url
    source_pages: List[str] = field(default_factory=list)
    anchor_text: str = ""
    link_type: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not self.affected_urls and self.affected_url:
            self.affected_urls = [self.affected_url]
        elif not self.affected_url and self.affected_urls:
            self.affected_url = self.affected_urls[0]

        if not self.affected_url and self.url:
            self.affected_url = self.url
        elif not self.url and self.affected_url:
            self.url = self.affected_url

        if not self.title and self.description:
            self.title = self.description[:70]
        elif not self.description and self.title:
            self.description = self.title

        if not self.observation:
            self.observation = self.description or self.title
        if not self.inference:
            self.inference = self.impact or "May affect search performance or crawling."

        if not self.issue_id or self.issue_id == "GENERIC_SEO_ISSUE":
            clean_title = re.sub(r"[^A-Za-z0-9]+", "_", self.title.strip().upper())
            self.issue_id = clean_title[:40] or "GENERIC_ISSUE"

        if not self.evidence:
            self.evidence = "Evaluated against document tree and response headers."
        if not self.impact:
            self.impact = self.inference
        if not self.verification_step:
            self.verification_step = "Re-crawl the affected URL and inspect the rendered DOM or response headers."

        if isinstance(self.severity, str):
            try:
                self.severity = IssueSeverity(self.severity.lower())
            except ValueError:
                self.severity = IssueSeverity.MEDIUM

        if isinstance(self.confidence, str):
            try:
                self.confidence = IssueConfidence(self.confidence.lower())
            except ValueError:
                self.confidence = IssueConfidence.HIGH

        if isinstance(self.category, str):
            try:
                self.category = IssueCategory(self.category.lower().replace(" ", "_"))
            except ValueError:
                self.category = IssueCategory.TECHNICAL

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["confidence"] = self.confidence.value
        d["category"] = self.category.value
        return d


@dataclass
class IssueCluster(DictCompatible):
    """An aggregated group of identical issues across multiple URLs."""

    issue_id: str
    title: str
    severity: IssueSeverity
    category: IssueCategory
    description: str
    impact: str
    recommendation: str
    verification_step: str
    confidence: IssueConfidence
    observation: str = ""
    inference: str = ""
    occurrences_count: int = 1
    affected_urls: List[str] = field(default_factory=list)
    sample_evidence: List[Dict[str, str]] = field(default_factory=list)  # [{"url": ..., "evidence": ...}]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["confidence"] = self.confidence.value
        d["category"] = self.category.value
        return d


# ---------------------------------------------------------------------------
# SERP & Competitor models
# ---------------------------------------------------------------------------

@dataclass
class SERPResult(DictCompatible):
    """A search engine result entry."""
    position: int
    url: str
    title: str
    snippet: str = ""
    domain: str = ""
    keyword: str = ""
    is_featured: bool = False
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        pt = getattr(self, "page_type", None)
        if hasattr(pt, "value"):
            d["page_type"] = pt.value
        return d


@dataclass
class SERPAnalysis(DictCompatible):
    """Aggregated SERP analysis."""
    keyword: str
    results: List[SERPResult] = field(default_factory=list)
    total_results: int = 0
    search_engine: str = "google"
    search_language: str = "en"
    search_country: str = "us"
    people_also_ask: List[str] = field(default_factory=list)
    related_searches: List[str] = field(default_factory=list)
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CompetitorMetrics(DictCompatible):
    """Key metrics for a competitor."""
    domain: str
    url: str = ""
    position: int = 0
    fetch_status: str = "not_attempted"
    http_status_code: Optional[int] = None
    fetch_error: str = ""
    title: str = ""
    word_count: int = 0
    heading_count: int = 0
    h1: str = ""
    meta_description: str = ""
    response_time_ms: float = 0.0
    total_internal_links: int = 0
    total_external_links: int = 0
    total_images: int = 0
    has_structured_data: bool = False
    has_og_tags: bool = False
    has_https: bool = True
    content_depth_score: float = 0.0
    keyword_in_title: bool = False
    keyword_in_h1: bool = False
    keyword_in_meta: bool = False
    keyword_density: float = 0.0


@dataclass
class CompetitorAnalysis(DictCompatible):
    """Side-by-side competitive intelligence."""
    keyword: str
    your_url: str
    your_position: int = 0
    your_metrics: Optional[CompetitorMetrics] = None
    competitors: List[CompetitorMetrics] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    competitive_gap_score: float = 0.0
    ranking_probability_pct: float = 0.0
    parity_status: str = "EVALUATED"
    search_engine: str = "google"
    search_language: str = "en"
    search_country: str = "us"
    serp_results: List[SERPResult] = field(default_factory=list)
    serp_retrieved_at: str = ""
    analysed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def position_label(self) -> str:
        if self.your_position:
            return f"#{self.your_position}"
        if self.search_engine == "unavailable":
            return "Position unavailable"
        return f"Not found in captured top {len(self.serp_results)} {self.search_engine} results"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        pt = getattr(self, "page_type", None)
        if hasattr(pt, "value"):
            d["page_type"] = pt.value
        return d


# ---------------------------------------------------------------------------
# Scoring and Report Models
# ---------------------------------------------------------------------------

@dataclass
class ScoreDeduction(DictCompatible):
    """Itemized mathematical score deduction."""
    rule_title: str
    severity: IssueSeverity
    points_deducted: float
    reason: str
    affected_count: int


@dataclass
class CategoryScore(DictCompatible):
    """Mathematically reproducible category score."""
    name: str
    score: float                      # 0-100
    max_score: float = 100.0
    weight: float = 1.0
    tests_evaluated: int = 0
    tests_passed: int = 0
    tests_skipped: int = 0
    tests_not_applicable: int = 0
    deductions: List[ScoreDeduction] = field(default_factory=list)
    check_results: List[CheckResult] = field(default_factory=list)
    status: str = "PASSED"            # "PASSED", "WARNING", "FAILED", "NOT_TESTED", "NOT_APPLICABLE"


@dataclass
class SEOReport(DictCompatible):
    """Complete, evidence-backed SEO Audit Report 2.0."""

    url: str
    domain: str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Overall score 0-100 & calculation breakdown
    overall_score: float = 0.0
    category_scores: Dict[str, CategoryScore] = field(default_factory=dict)
    all_deductions: List[ScoreDeduction] = field(default_factory=list)

    # Release gate status and environment intent
    audit_status: str = "PASS"        # "PASS", "INDEXATION_BLOCKED", "STAGING_PROTECTED", "NEEDS_REVIEW", "PARTIAL"
    status_message: str = ""
    environment_intent: str = "unknown"  # "production", "staging", "development", "unknown"
    check_ledger: List[CheckResult] = field(default_factory=list)

    # Issue clustering
    issue_clusters: List[IssueCluster] = field(default_factory=list)
    raw_issues: List[SEOIssue] = field(default_factory=list)

    # Prioritized action plan
    recommendations: List[str] = field(default_factory=list)

    # AI Agent Remediation & Model Verification Layer (Kev-4B & Deterministic Engine)
    remediation_plan: Optional[Any] = None
    verifications: List[Any] = field(default_factory=list)
    summary_stats: Dict[str, Any] = field(default_factory=dict)

    # Raw data references
    crawl_result: Optional[CrawlResult] = None
    competitor_analyses: List[CompetitorAnalysis] = field(default_factory=list)
    competitor_analysis: Optional[CompetitorAnalysis] = None
    serp_analyses: List[SERPAnalysis] = field(default_factory=list)

    @property
    def critical_clusters(self) -> List[IssueCluster]:
        return [c for c in self.issue_clusters if c.severity == IssueSeverity.CRITICAL]

    @property
    def high_clusters(self) -> List[IssueCluster]:
        return [c for c in self.issue_clusters if c.severity == IssueSeverity.HIGH]

    @property
    def medium_clusters(self) -> List[IssueCluster]:
        return [c for c in self.issue_clusters if c.severity == IssueSeverity.MEDIUM]

    @property
    def low_clusters(self) -> List[IssueCluster]:
        return [c for c in self.issue_clusters if c.severity == IssueSeverity.LOW]

    @property
    def info_clusters(self) -> List[IssueCluster]:
        return [c for c in self.issue_clusters if c.severity == IssueSeverity.INFORMATIONAL]

    @property
    def all_issues(self) -> List[SEOIssue]:
        return self.raw_issues

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        pt = getattr(self, "page_type", None)
        if hasattr(pt, "value"):
            d["page_type"] = pt.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)
