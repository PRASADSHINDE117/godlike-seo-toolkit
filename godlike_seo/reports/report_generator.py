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
from godlike_seo.decision_engine import KevDecisionEngine, AgentRemediationPlanner
from godlike_seo.models import (
    CanonicalState,
    CategoryScore,
    CheckResult,
    CheckStatus,
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


RULE_CATALOG = [
    # Technical & Crawlability
    {
        "rule_id": "TECH-001",
        "category": IssueCategory.TECHNICAL,
        "title": "HTTP Status & Crawlability",
        "description": "Verifies that all crawled URLs return clean 200 OK responses without 4xx client or 5xx server errors.",
        "issue_ids": {"HTTP_404_INTERNAL_LINKED", "HTTP_404_RESOURCE", "HTTP_500_SERVER_ERROR", "CONNECTION_ERROR"},
    },
    {
        "rule_id": "TECH-002",
        "category": IssueCategory.TECHNICAL,
        "title": "Search Indexation Directives",
        "description": "Validates that production public pages do not serve blocking 'noindex' directives via HTTP headers or HTML meta tags.",
        "issue_ids": {"SITEWIDE_INDEXATION_BLOCK"},
    },
    {
        "rule_id": "TECH-003",
        "category": IssueCategory.TECHNICAL,
        "title": "Canonical Directive Consistency",
        "description": "Ensures all indexable pages declare absolute, valid canonical URLs without conflicting tags or parameter drops.",
        "issue_ids": {"MISSING_CANONICAL_WITH_QUERY", "RELATIVE_CANONICAL_URL", "CONFLICTING_CANONICAL_TAGS", "CANONICAL_POINTS_TO_4XX"},
    },
    {
        "rule_id": "TECH-004",
        "category": IssueCategory.TECHNICAL,
        "title": "Route Segment & Placeholder Slugs",
        "description": "Detects unpopulated frontend variables or broken URL segments such as '/undefined/', '/null/', or empty slugs.",
        "issue_ids": {"MALFORMED_LOCATION_URL"},
    },
    {
        "rule_id": "TECH-005",
        "category": IssueCategory.TECHNICAL,
        "title": "Redirect Chains & Loops",
        "description": "Confirms internal links point directly to destination URLs without unnecessary 301/302 hops or infinite loops.",
        "issue_ids": {"REDIRECT_CHAIN", "REDIRECT_LOOP"},
    },
    {
        "rule_id": "TECH-006",
        "category": IssueCategory.TECHNICAL,
        "title": "XML Sitemap Discovery & Coverage",
        "description": "Verifies that an accessible XML sitemap is present and references public indexable pages.",
        "issue_ids": {"MISSING_SITEMAP", "SITEMAP_INDEXABILITY_MISMATCH"},
    },
    {
        "rule_id": "TECH-007",
        "category": IssueCategory.TECHNICAL,
        "title": "Robots.txt Directives & Accessibility",
        "description": "Checks that robots.txt exists, parses valid directives, and avoids disallowing critical public assets.",
        "issue_ids": {"ROBOTS_TXT_MISSING", "ROBOTS_DISALLOW_CRITICAL"},
    },
    {
        "rule_id": "TECH-008",
        "category": IssueCategory.TECHNICAL,
        "title": "Server Response Latency",
        "description": "Monitors Time to First Byte (TTFB) and ensures server response times remain under 1000ms.",
        "issue_ids": {"SLOW_RESPONSE_TIME"},
    },
    {
        "rule_id": "TECH-009",
        "category": IssueCategory.TECHNICAL,
        "title": "Search Snippet Previews & Robots Directives",
        "description": "Verifies that pages do not serve nosnippet or max-snippet:0 blocking search engine preview snippets.",
        "issue_ids": {"SEARCH_SNIPPET_BLOCKED"},
    },

    # On-Page & Metadata
    {
        "rule_id": "ONPAGE-001",
        "category": IssueCategory.ON_PAGE,
        "title": "Title Tag Presence & Length",
        "description": "Checks that every public page has a descriptive <title> tag between 10 and 65 characters.",
        "issue_ids": {"MISSING_TITLE_TAG", "TITLE_TOO_LONG", "TITLE_TOO_SHORT"},
    },
    {
        "rule_id": "ONPAGE-002",
        "category": IssueCategory.ON_PAGE,
        "title": "Title Tag Uniqueness",
        "description": "Verifies that distinct public URLs do not share identical <title> tags across the site.",
        "issue_ids": {"DUPLICATE_TITLE_TAG"},
    },
    {
        "rule_id": "ONPAGE-003",
        "category": IssueCategory.ON_PAGE,
        "title": "Meta Description Presence & Cardinality",
        "description": "Ensures pages declare exactly one concise meta description tag (70-160 chars) without duplicates.",
        "issue_ids": {"MISSING_META_DESCRIPTION", "META_DESCRIPTION_TOO_LONG", "MULTIPLE_META_DESCRIPTIONS"},
    },
    {
        "rule_id": "ONPAGE-004",
        "category": IssueCategory.ON_PAGE,
        "title": "Main H1 Heading Presence",
        "description": "Checks that every public content page declares a main <h1> heading clearly defining the page subject.",
        "issue_ids": {"MISSING_H1_TAG"},
    },
    {
        "rule_id": "ONPAGE-005",
        "category": IssueCategory.ON_PAGE,
        "title": "Heading Hierarchy & Multiplicity",
        "description": "Audits heading hierarchy to ensure logical outline without conflicting heading structures.",
        "issue_ids": {"MULTIPLE_H1_TAGS"},
    },
    {
        "rule_id": "ONPAGE-006",
        "category": IssueCategory.ON_PAGE,
        "title": "Image Alt Text Accessibility",
        "description": "Verifies that <img> elements include descriptive alt attributes for accessibility and Google Images.",
        "issue_ids": {"IMAGE_MISSING_ALT"},
    },
    {
        "rule_id": "ONPAGE-007",
        "category": IssueCategory.ON_PAGE,
        "title": "HTML Language & Encoding",
        "description": "Ensures the <html> element declares a valid lang attribute for internationalization and screen readers.",
        "issue_ids": {"MISSING_HTML_LANG"},
    },

    # Social & Open Graph
    {
        "rule_id": "SOC-001",
        "category": IssueCategory.SOCIAL,
        "title": "Open Graph & Social Metadata Consistency",
        "description": "Validates Open Graph tags, ensuring og:url is well-formed, matches canonical URL, and provides rich social previews.",
        "issue_ids": {"MALFORMED_OG_URL", "OG_URL_CANONICAL_MISMATCH", "MISSING_OG_TITLE", "MISSING_OPEN_GRAPH", "MISSING_TWITTER_CARD"},
    },

    # Content & Topical Depth
    {
        "rule_id": "CONTENT-001",
        "category": IssueCategory.CONTENT,
        "title": "Substantive Body Text Depth",
        "description": "Evaluates body copy length to ensure documents contain substantive indexable text.",
        "issue_ids": {"VERY_THIN_CONTENT", "THIN_CONTENT"},
    },
    {
        "rule_id": "CONTENT-002",
        "category": IssueCategory.CONTENT,
        "title": "Content Uniqueness Across URLs",
        "description": "Checks body content hashes to detect 100% duplicate page text across distinct public URLs.",
        "issue_ids": {"DUPLICATE_PAGE_CONTENT"},
    },
    {
        "rule_id": "CONTENT-003",
        "category": IssueCategory.CONTENT,
        "title": "Staging & Test Data Leakage",
        "description": "Scans public documents for mock listings, lorem ipsum placeholders, or staging notices.",
        "issue_ids": {"PUBLIC_STAGING_TEST_CONTENT"},
    },
    {
        "rule_id": "CONTENT-004",
        "category": IssueCategory.CONTENT,
        "title": "Topical Context & Substance",
        "description": "Audits pages for introductory summaries, FAQs, or sufficient contextual copy to fulfill search intent.",
        "issue_ids": {"CONTENT_DEPTH_OPPORTUNITY"},
    },
    {
        "rule_id": "CONTENT-005",
        "category": IssueCategory.CONTENT,
        "title": "Topical Keyword Overlap & Intent Differentiation",
        "description": "Audits pages for overlapping target phrases in titles/headings, advising GSC query performance verification before consolidating URLs.",
        "issue_ids": {"TOPICAL_KEYWORD_OVERLAP", "KEYWORD_CANNIBALIZATION_RISK"},
    },

    # Site Architecture & Links
    {
        "rule_id": "LINK-001",
        "category": IssueCategory.INTERNAL_LINKING,
        "title": "Orphaned Public Indexable Pages",
        "description": "Audits internal link graph to ensure all indexable public pages receive at least one internal navigation link.",
        "issue_ids": {"ORPHANED_PAGE_DETECTED"},
    },
    {
        "rule_id": "LINK-002",
        "category": IssueCategory.INTERNAL_LINKING,
        "title": "Dead-End Content Pages",
        "description": "Checks for public content documents with 0 outbound internal links that trap PageRank equity.",
        "issue_ids": {"DEAD_END_PAGE"},
    },
    {
        "rule_id": "LINK-003",
        "category": IssueCategory.INTERNAL_LINKING,
        "title": "Click Depth & Architecture Hierarchy",
        "description": "Verifies that core public content is reachable within 3 clicks from the root homepage.",
        "issue_ids": {"EXCESSIVE_CLICK_DEPTH"},
    },
    {
        "rule_id": "LINK-004",
        "category": IssueCategory.INTERNAL_LINKING,
        "title": "Internal Link Nofollow Directives",
        "description": "Ensures internal navigation does not waste PageRank by applying rel='nofollow' to internal links.",
        "issue_ids": {"INTERNAL_LINK_NOFOLLOW"},
    },
    {
        "rule_id": "LINK-005",
        "category": IssueCategory.INTERNAL_LINKING,
        "title": "Anchor Text Quality & Descriptive Links",
        "description": "Audits anchor texts for generic phrases ('click here', 'read more') that offer no keyword context.",
        "issue_ids": {"NON_DESCRIPTIVE_ANCHOR"},
    },

    # Mobile & Responsive
    {
        "rule_id": "MOB-001",
        "category": IssueCategory.MOBILE,
        "title": "Viewport Meta Tag Presence",
        "description": "Ensures HTML head contains a <meta name='viewport'> element for mobile browsers.",
        "issue_ids": {"MISSING_VIEWPORT_TAG"},
    },
    {
        "rule_id": "MOB-002",
        "category": IssueCategory.MOBILE,
        "title": "Responsive Device-Width Configuration",
        "description": "Confirms viewport is configured as 'width=device-width' rather than fixed pixel dimensions.",
        "issue_ids": {"FIXED_WIDTH_VIEWPORT"},
    },
    # Performance & Page Experience
    {
        "rule_id": "PERF-001",
        "category": IssueCategory.PERFORMANCE,
        "title": "Image Cumulative Layout Shift Prevention",
        "description": "Checks that <img> elements declare explicit width and height attributes or CSS aspect-ratio to reserve layout space.",
        "issue_ids": {"IMAGE_MISSING_DIMENSIONS"},
    },

    # Security & Standards
    {
        "rule_id": "SEC-001",
        "category": IssueCategory.SECURITY,
        "title": "HTTPS Protocol Enforcement",
        "description": "Validates that all site routes enforce HTTPS encryption and redirect HTTP requests cleanly.",
        "issue_ids": {"INSECURE_HTTP_PROTOCOL"},
    },
    {
        "rule_id": "SEC-002",
        "category": IssueCategory.SECURITY,
        "title": "TLS Certificate Verification",
        "description": "Verifies that the server presents a trusted, valid TLS certificate without chain errors.",
        "issue_ids": {"INVALID_SSL_CERTIFICATE"},
    },
    {
        "rule_id": "SEC-003",
        "category": IssueCategory.SECURITY,
        "title": "Mixed Content Detection",
        "description": "Ensures secure HTTPS pages do not load insecure HTTP stylesheets, scripts, or media assets.",
        "issue_ids": {"MIXED_CONTENT"},
    },
    {
        "rule_id": "SEC-004",
        "category": IssueCategory.SECURITY,
        "title": "Defensive Security Headers",
        "description": "Evaluates presence of modern security headers (HSTS, Content-Security-Policy, X-Frame-Options).",
        "issue_ids": {"MISSING_HSTS_HEADER"},
    },

    # Structured Data
    {
        "rule_id": "SCHEMA-001",
        "category": IssueCategory.STRUCTURED_DATA,
        "title": "Schema.org Rich Snippet Opportunity",
        "description": "Identifies opportunities to add Schema.org JSON-LD to qualify for Google rich search results.",
        "issue_ids": {"OPPORTUNITY_SCHEMA_MARKUP"},
    },
    {
        "rule_id": "SCHEMA-002",
        "category": IssueCategory.STRUCTURED_DATA,
        "title": "JSON-LD Syntax & Parsing Validity",
        "description": "Validates that declared JSON-LD script blocks are free of syntax errors and unescaped characters.",
        "issue_ids": {"INVALID_JSON_LD"},
    },
]


class ReportGenerator:
    """Combines crawl data, runs all audits, clusters findings, and computes transparent scores."""

    def __init__(self, environment: Optional[str] = None):
        self.environment = environment
        self.issue_detector = SEOIssueDetector(environment=environment)
        self.content_analyzer = ContentAnalyzer()
        self.technical_analyzer = TechnicalAnalyzer()
        self.link_analyzer = LinkAnalyzer()

    def generate_report(
        self,
        crawl_result: CrawlResult,
        competitor_analyses: Optional[List[CompetitorAnalysis]] = None,
        serp_analyses: Optional[List[SERPAnalysis]] = None,
        environment: Optional[str] = None,
    ) -> SEOReport:
        pages = crawl_result.pages
        domain = crawl_result.domain or (urlparse(crawl_result.start_url).netloc if crawl_result.start_url else "")

        # Resolve environment intent
        env_intent = environment or getattr(crawl_result, "environment", None) or self.environment or "unknown"
        if env_intent == "unknown" or not env_intent:
            if any(k in domain.lower() for k in ("staging", "dev.", "test.", "demo.", "uat.", "localhost")):
                env_intent = "staging"
            else:
                # Inspect response headers and cookies from initial pages for candidate / staging markers
                for p in pages[:5]:
                    h_str = " ".join(f"{k}:{v}" for k, v in p.headers.items()).lower()
                    if any(term in h_str for term in ("candidate", "staging", "development", "preview", "tental_staging")):
                        env_intent = "staging"
                        break
                if env_intent == "unknown" or not env_intent:
                    env_intent = "production"

        # Update detector environment if needed
        self.issue_detector.environment = env_intent

        logger.info("Generating Evidence-Based SEO Report 3.1 for: %s (%d pages, env: %s)", domain, len(pages), env_intent)

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

        # 6. Build Deterministic Rule Execution Ledger
        cluster_map: Dict[str, IssueCluster] = {c.issue_id: c for c in clusters}
        ledger: List[CheckResult] = []

        eligible_indexable_count = link_audit.get("eligible_indexable_count", 0)

        for rule in RULE_CATALOG:
            r_id = rule["rule_id"]
            cat = rule["category"]
            r_title = rule["title"]
            r_desc = rule["description"]
            matched_clusters = [cluster_map[iid] for iid in rule["issue_ids"] if iid in cluster_map]

            if matched_clusters:
                primary = matched_clusters[0]
                total_aff = list(dict.fromkeys([u for mc in matched_clusters for u in mc.affected_urls]))
                ledger.append(CheckResult(
                    rule_id=r_id,
                    rule_version="3.1",
                    category=cat,
                    status=CheckStatus.FAIL,
                    title=r_title,
                    description=primary.description,
                    evidence=primary.observation,
                    affected_count=len(total_aff),
                    affected_urls=total_aff,
                ))
            else:
                # Special applicability conditions
                if r_id == "LINK-001" and eligible_indexable_count == 0:
                    ledger.append(CheckResult(
                        rule_id=r_id,
                        rule_version="3.1",
                        category=cat,
                        status=CheckStatus.NOT_APPLICABLE,
                        title=r_title,
                        description="Not applicable: 0 indexable public content pages exist in crawl scope (e.g. sitewide noindex active).",
                        evidence="Orphan check skipped because no public indexable pages were crawlable.",
                        affected_count=0,
                        affected_urls=[],
                    ))
                else:
                    ledger.append(CheckResult(
                        rule_id=r_id,
                        rule_version="3.1",
                        category=cat,
                        status=CheckStatus.PASS,
                        title=r_title,
                        description=r_desc,
                        evidence="Verified without defects across crawled document set.",
                        affected_count=0,
                        affected_urls=[],
                    ))

        # 7. Group clusters by category and compute reproducible scores
        cat_clusters: Dict[IssueCategory, List[IssueCluster]] = {}
        for c in clusters:
            effective_cat = c.category
            if effective_cat == IssueCategory.INDEXABILITY:
                effective_cat = IssueCategory.TECHNICAL
            elif effective_cat == IssueCategory.INTERNATIONAL:
                effective_cat = IssueCategory.ON_PAGE
            cat_clusters.setdefault(effective_cat, []).append(c)

        all_deductions: List[ScoreDeduction] = []

        def build_category_score(
            cat_name: str,
            category: IssueCategory,
            weight: float,
        ) -> CategoryScore:
            cat_list = cat_clusters.get(category, [])
            cat_results = [r for r in ledger if r.category == category]
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
            tests_eval = len([r for r in cat_results if r.status in (CheckStatus.PASS, CheckStatus.FAIL)])
            tests_pass = len([r for r in cat_results if r.status == CheckStatus.PASS])
            tests_skip = len([r for r in cat_results if r.status == CheckStatus.SKIPPED])
            tests_na = len([r for r in cat_results if r.status == CheckStatus.NOT_APPLICABLE])

            status = "PASSED"
            if tests_eval == 0 and tests_na > 0:
                status = "NOT_APPLICABLE"
            elif final_score < 50:
                status = "FAILED"
            elif final_score < 75:
                status = "WARNING"
            elif final_score < 95:
                status = "GOOD"

            return CategoryScore(
                name=cat_name,
                score=final_score,
                weight=weight,
                tests_evaluated=tests_eval,
                tests_passed=tests_pass,
                tests_skipped=tests_skip,
                tests_not_applicable=tests_na,
                deductions=deductions,
                check_results=cat_results,
                status=status,
            )

        category_scores: Dict[str, CategoryScore] = {
            "technical": build_category_score("Technical & Crawlability", IssueCategory.TECHNICAL, 0.15),
            "on_page": build_category_score("On-Page & Metadata", IssueCategory.ON_PAGE, 0.15),
            "social": build_category_score("Social & Open Graph", IssueCategory.SOCIAL, 0.15),
            "content": build_category_score("Content & Topical Depth", IssueCategory.CONTENT, 0.15),
            "internal_linking": build_category_score("Site Architecture & Links", IssueCategory.INTERNAL_LINKING, 0.15),
            "performance": build_category_score("Performance & Experience", IssueCategory.PERFORMANCE, 0.10),
            "structured_data": build_category_score("Structured Data & Schema", IssueCategory.STRUCTURED_DATA, 0.05),
            "mobile": build_category_score("Mobile & Responsive", IssueCategory.MOBILE, 0.05),
            "security": build_category_score("Security & Standards", IssueCategory.SECURITY, 0.05),
        }

        # Weighted Master Score
        raw_score = sum(cs.score * cs.weight for cs in category_scores.values())
        overall_score = round(raw_score, 1)

        # Release Gate Evaluation & Score Gating
        has_sitewide_noindex = any(c.issue_id == "SITEWIDE_INDEXATION_BLOCK" for c in clusters)
        has_staging_noindex = any(c.issue_id == "STAGING_ENVIRONMENT_NOINDEX_ACTIVE" for c in clusters)
        critical_clusters = [c for c in clusters if c.severity == IssueSeverity.CRITICAL]
        high_clusters = [c for c in clusters if c.severity == IssueSeverity.HIGH]

        if has_sitewide_noindex and env_intent != "staging":
            audit_status = "INDEXATION_BLOCKED"
            status_message = (
                "CRITICAL RELEASE BLOCKER: Sitewide 'noindex' directive detected across public pages on production host. "
                "Search engines cannot index this website. SEO Master Score capped at 0/100 (Indexation Blocked)."
            )
            overall_score = 0.0
        elif has_staging_noindex or (has_sitewide_noindex and env_intent == "staging"):
            audit_status = "STAGING_PROTECTED"
            status_message = (
                "STAGING HOST: Sitewide 'noindex' directive is active, appropriately protecting staging inventory "
                "from search engine indexing."
            )
        elif len(critical_clusters) > 0:
            audit_status = "CRITICAL_BLOCKED"
            crit_names = ", ".join(c.title for c in critical_clusters[:2])
            status_message = f"CRITICAL DEFECTS DETECTED: {len(critical_clusters)} critical blocker(s) identified ({crit_names}). Release blocked."
            overall_score = min(overall_score, 49.0)
        elif len(high_clusters) > 0:
            audit_status = "NEEDS_REVIEW"
            high_names = ", ".join(c.title for c in high_clusters[:2])
            status_message = f"HIGH SEVERITY ISSUES: {len(high_clusters)} high-priority defect(s) require developer remediation ({high_names}). Release gated."
            overall_score = min(overall_score, 84.9)
        elif overall_score < 70:
            audit_status = "NEEDS_REVIEW"
            status_message = f"Audit score ({overall_score}/100) is below acceptable release threshold (70/100)."
        else:
            audit_status = "PASS"
            status_message = "All core technical, on-page, and social release criteria satisfied. Zero critical and zero high defects detected."

        # 8. Actionable recommendations from clusters
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

        # 8.5 Model Decision Verification & AI Agent Remediation Planning
        decision_engine = KevDecisionEngine()
        verifications = decision_engine.verify_all_clusters(clusters)
        planner = AgentRemediationPlanner()
        remediation_plan = planner.generate_plan(domain, clusters, verifications)

        summary_stats = {
            "total_pages_crawled": len(pages),
            "total_tests_evaluated": sum(cs.tests_evaluated for cs in category_scores.values()),
            "total_tests_passed": sum(cs.tests_passed for cs in category_scores.values()),
            "total_tests_not_applicable": sum(cs.tests_not_applicable for cs in category_scores.values()),
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
            "audit_status": audit_status,
            "environment_intent": env_intent,
        }

        comp_analyses = competitor_analyses or []
        first_comp = comp_analyses[0] if comp_analyses else None

        return SEOReport(
            url=crawl_result.start_url,
            domain=domain,
            overall_score=overall_score,
            category_scores=category_scores,
            all_deductions=all_deductions,
            audit_status=audit_status,
            status_message=status_message,
            environment_intent=env_intent,
            check_ledger=ledger,
            issue_clusters=clusters,
            raw_issues=raw_issues,
            recommendations=recommendations,
            summary_stats=summary_stats,
            crawl_result=crawl_result,
            competitor_analyses=comp_analyses,
            competitor_analysis=first_comp,
            serp_analyses=serp_analyses or [],
            remediation_plan=remediation_plan,
            verifications=verifications,
        )
