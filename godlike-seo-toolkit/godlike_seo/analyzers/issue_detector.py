"""
Evidence-Backed SEO Issue Detector 2.0.

Features:
- Deterministic detection with concrete DOM & Header evidence
- Guarded analysis: On-page checks only run on indexable 200 OK HTML responses
- True URL normalization for duplicate content detection (avoids trailing-slash & encoding false alarms)
- Elimination of outdated SEO myths (no arbitrary 3% keyword density or 10% text-to-HTML rules)
- Calibrated severity levels (CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL)
- Confidence scoring (HIGH, MEDIUM, LOW)
- Actionable developer fixes with verification steps
- Root-cause issue clustering across multiple URLs
"""

from __future__ import annotations

import collections
import hashlib
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from godlike_seo.models import (
    IssueCategory,
    IssueCluster,
    IssueConfidence,
    IssueSeverity,
    PageData,
    PageType,
    SEOIssue,
)
from godlike_seo.utils.url_normalizer import are_urls_equivalent, normalize_url

logger = logging.getLogger(__name__)

# Calibrated title & meta thresholds
TITLE_MIN_CHARS = 10
TITLE_MAX_CHARS = 65
META_DESC_MIN_CHARS = 70
META_DESC_MAX_CHARS = 160


class SEOIssueDetector:
    """Professional, evidence-based SEO auditor."""

    def __init__(self, exclusion_patterns: Optional[List[str]] = None):
        self.exclusion_patterns = exclusion_patterns or []

    def _should_exclude(self, url: str) -> bool:
        if not self.exclusion_patterns:
            return False
        path = urlparse(url).path
        for pattern in self.exclusion_patterns:
            if pattern in path:
                return True
        return False

    def analyze(self, pages: List[PageData]) -> List[SEOIssue]:
        """Audit all crawled pages and return evidence-backed findings."""
        issues: List[SEOIssue] = []

        # Filter: Only analyze successfully fetched 200 OK HTML pages that are verified PUBLIC_CONTENT
        # User app routes, auth gates, utility URLs, and errors are excluded from on-page SEO evaluations
        html_200_public_pages = [
            p for p in pages
            if p.status_code == 200
            and p.has_html
            and getattr(p, "page_type", None) == PageType.PUBLIC_CONTENT
            and not getattr(p, "is_auth_gate", False)
            and not self._should_exclude(p.url)
        ]

        # General 200 OK HTML pages for universal checks (like mobile viewport)
        html_200_all_pages = [
            p for p in pages
            if p.status_code == 200 and p.has_html and not self._should_exclude(p.url)
        ]

        # Build cross-page lookups strictly on normalized URLs of PUBLIC content
        title_map: Dict[str, List[PageData]] = collections.defaultdict(list)
        desc_map: Dict[str, List[PageData]] = collections.defaultdict(list)
        h1_map: Dict[str, List[PageData]] = collections.defaultdict(list)
        content_hash_map: Dict[str, List[PageData]] = collections.defaultdict(list)

        for p in html_200_public_pages:
            norm_url = normalize_url(p.final_url or p.url)
            if p.title.strip():
                title_map[p.title.strip().lower()].append(p)
            if p.meta_description.strip():
                desc_map[p.meta_description.strip().lower()].append(p)
            if p.h1_tags:
                h1_map[p.h1_tags[0].strip().lower()].append(p)
            if p.content_hash:
                content_hash_map[p.content_hash].append(p)

        # 1. Sitewide Infrastructure & Directives checks
        issues.extend(self._check_sitewide_noindex(pages))

        # 2. HTTP & Status checks (runs on all responses)
        for page in pages:
            issues.extend(self._check_http_status(page))

        # 3. Viewport check (runs on all 200 OK HTML)
        for page in html_200_all_pages:
            issues.extend(self._check_mobile_viewport(page))

        # 4. On-Page, Content, Staging, Canonical, Schema, Links (strictly on PUBLIC content)
        for page in html_200_public_pages:
            issues.extend(self._check_staging_and_test_content(page))
            issues.extend(self._check_title(page, title_map))
            issues.extend(self._check_meta_description(page, desc_map))
            issues.extend(self._check_headings(page, h1_map))
            issues.extend(self._check_canonical(page))
            issues.extend(self._check_images(page))
            issues.extend(self._check_content_quality(page, content_hash_map))
            issues.extend(self._check_structured_data(page))
            issues.extend(self._check_links(page))

        return issues

    def cluster_issues(self, raw_issues: List[SEOIssue]) -> List[IssueCluster]:
        """Aggregate identical issues into root-cause clusters."""
        clusters: Dict[str, IssueCluster] = {}

        for issue in raw_issues:
            key = issue.issue_id
            evidence_entry = {
                "url": issue.affected_url,
                "evidence": issue.evidence,
            }
            if getattr(issue, "source_pages", None):
                evidence_entry["source_pages"] = issue.source_pages
            if getattr(issue, "anchor_text", None):
                evidence_entry["anchor_text"] = issue.anchor_text

            if key not in clusters:
                clusters[key] = IssueCluster(
                    issue_id=issue.issue_id,
                    title=issue.title,
                    severity=issue.severity,
                    category=issue.category,
                    description=issue.description,
                    observation=issue.observation,
                    inference=issue.inference,
                    impact=issue.impact,
                    recommendation=issue.recommendation,
                    verification_step=issue.verification_step,
                    confidence=issue.confidence,
                    occurrences_count=1,
                    affected_urls=[issue.affected_url],
                    sample_evidence=[evidence_entry],
                )
            else:
                cluster = clusters[key]
                cluster.occurrences_count += 1
                if issue.affected_url not in cluster.affected_urls:
                    cluster.affected_urls.append(issue.affected_url)
                if len(cluster.sample_evidence) < 5:
                    cluster.sample_evidence.append(evidence_entry)

        # Refine cluster observation when multiple distinct URLs are affected to prevent single-URL misattribution
        for cluster in clusters.values():
            if cluster.occurrences_count > 1:
                if cluster.issue_id == "HTTP_404_INTERNAL_LINKED":
                    cluster.observation = (
                        f"Found {len(cluster.affected_urls)} broken URLs returning HTTP 404 that are linked internally across the site. "
                        f"Inlink counts range from individual contextual links to site-wide header/footer navigation links. "
                        f"See individual URL evidence below for exact source pages and anchor text."
                    )
                elif cluster.issue_id == "DUPLICATE_TITLE_TAG":
                    cluster.observation = (
                        f"Found {len(cluster.affected_urls)} distinct pages sharing duplicate <title> tags. "
                        f"Indicates static/boilerplate page titles configured in shared CMS templates."
                    )
                elif cluster.issue_id == "DUPLICATE_PAGE_CONTENT":
                    cluster.observation = (
                        f"Found {len(cluster.affected_urls)} distinct public URLs sharing identical body content. "
                        f"Indicates un-canonicalized parameterized URLs or duplicated page variants."
                    )

        # Order clusters by severity
        sev_order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3,
            IssueSeverity.INFORMATIONAL: 4,
        }
        return sorted(clusters.values(), key=lambda c: (sev_order.get(c.severity, 99), -c.occurrences_count))

    # ------------------------------------------------------------------
    # 0. Domain & Infrastructure Indexability Directives
    # ------------------------------------------------------------------

    def _check_sitewide_noindex(self, pages: List[PageData]) -> List[SEOIssue]:
        """Detect domain-wide noindex directives (X-Robots-Tag / meta robots)."""
        issues = []
        if not pages:
            return issues

        noindex_pages = []
        for p in pages:
            xr = (getattr(p, "x_robots_tag", None) or (p.headers.get("x-robots-tag", "") if hasattr(p, "headers") and p.headers else "")).lower()
            mr = (getattr(p, "meta_robots", "") or "").lower()
            if "noindex" in xr or "noindex" in mr:
                directive = xr if "noindex" in xr else mr
                noindex_pages.append((p, directive))

        ratio = len(noindex_pages) / len(pages)
        if len(pages) >= 2 and (ratio >= 0.7 or len(noindex_pages) == len(pages)):
            sample_p, sample_directive = noindex_pages[0]
            root_url = pages[0].url
            issues.append(SEOIssue(
                issue_id="SITEWIDE_INDEXATION_BLOCK",
                severity=IssueSeverity.CRITICAL,
                category=IssueCategory.TECHNICAL,
                title="Domain-Wide Search Indexation Block (X-Robots-Tag / Robots Directives)",
                description=f"Server serves explicit 'noindex' directives across {len(noindex_pages)} of {len(pages)} crawled URLs ({int(ratio * 100)}% of site).",
                affected_url=root_url,
                evidence=f"Directives detected across {len(noindex_pages)} URLs. Example: {sample_p.url} serves '{sample_directive}'",
                observation=f"{len(noindex_pages)} of {len(pages)} crawled pages ({int(ratio * 100)}%) instruct search engines not to index content via HTTP header 'X-Robots-Tag' or HTML meta robots.",
                inference="Search engines (Googlebot, Bingbot) will honor these directives and purge the entire website from organic search indexes. Organic search traffic will be zero.",
                impact="Zero search engine indexation. The site cannot appear in any organic search results while this header/tag persists.",
                recommendation="If this is a staging/candidate environment, this configuration is intentional to protect testing environments. If this is PRODUCTION, immediately remove the 'X-Robots-Tag: noindex' header from your web server / CDN configuration.",
                verification_step="Run `curl -I https://domain/` in your terminal and verify the response headers do NOT contain 'X-Robots-Tag: noindex'.",
                confidence=IssueConfidence.HIGH,
            ))
        return issues

    # ------------------------------------------------------------------
    # 1. HTTP & Server Status
    # ------------------------------------------------------------------

    def _check_http_status(self, page: PageData) -> List[SEOIssue]:
        issues = []
        # Exclude Cloudflare email protection or internal worker endpoints
        if "/cdn-cgi/" in page.url:
            return issues

        if page.status_code == 404:
            inlinks = getattr(page, "inlinks_count", 0)
            inbound_details = getattr(page, "inbound_link_details", [])
            source_pages = [d["source"] for d in inbound_details if isinstance(d, dict) and "source" in d]
            anchor_texts = list(dict.fromkeys([d["anchor"] for d in inbound_details if isinstance(d, dict) and d.get("anchor")]))

            # Classify destination intent of the 404 URL
            path = urlparse(page.url).path.lower()
            if any(p in path for p in ("/owner", "/account", "/admin", "/dashboard", "/user", "/settings")):
                intent_type = "Protected User / Dashboard Route"
                intent_desc = f"Destination `{page.url}` is a user account or dashboard route returning 404."
            elif any(act in path for act in ("delete", "destroy", "remove", "action")):
                intent_type = "Destructive User / Action Endpoint"
                intent_desc = f"Destination `{page.url}` is a destructive user or mutation endpoint returning 404."
            elif path in ("/privacy", "/terms", "/about", "/contact", "/help", "/faq", "/support"):
                intent_type = "Suspected Typo / Stale Utility Route"
                intent_desc = f"Destination `{page.url}` appears to be a stale utility link or typo (e.g. linked as `/privacy` instead of `/privacy-policy`)."
            else:
                intent_type = "Resource Route"
                intent_desc = f"Destination `{page.url}` returns 404 Not Found."

            if inlinks > 0:
                evidence_parts = [f"HTTP/1.1 Status: 404 | Internal Inlinks: {inlinks}"]
                if source_pages:
                    evidence_parts.append(f"Linked from: {', '.join(source_pages[:2])}")
                if anchor_texts:
                    evidence_parts.append(f"Anchor: '{anchor_texts[0]}'")
                evidence_str = " | ".join(evidence_parts)

                obs_str = f"Server returned HTTP status 404 ({intent_type}). URL is actively linked internally from {inlinks} page(s)."
                if source_pages:
                    obs_str += f" Source pages include: {', '.join(source_pages[:3])}."
                if anchor_texts:
                    obs_str += f" Anchor text used: '{anchor_texts[0]}'."

                issues.append(SEOIssue(
                    issue_id="HTTP_404_INTERNAL_LINKED",
                    severity=IssueSeverity.HIGH,
                    category=IssueCategory.TECHNICAL,
                    title=f"Broken Internal Link: {intent_type} (HTTP 404)",
                    description=f"Server returned HTTP status 404 for actively linked URL: {page.url}",
                    affected_url=page.url,
                    evidence=evidence_str,
                    observation=obs_str,
                    inference=f"{intent_desc} Internal links lead users and crawlers to a dead end.",
                    impact="Breaks user navigation paths, creates dead ends, and wastes crawler budget.",
                    recommendation=f"Update or remove the broken internal links pointing to this URL (check {source_pages[0] if source_pages else 'site navigation'}), or configure a 301 redirect to an active equivalent page.",
                    verification_step="Request the URL with curl or browser and verify a 200 OK or 301 Moved Permanently status.",
                    confidence=IssueConfidence.HIGH,
                    source_pages=source_pages,
                    anchor_text=anchor_texts[0] if anchor_texts else "",
                ))
            else:
                issues.append(SEOIssue(
                    issue_id="HTTP_404_NOT_FOUND",
                    severity=IssueSeverity.MEDIUM,
                    category=IssueCategory.TECHNICAL,
                    title=f"Page Returns 404 Not Found (Unlinked: {intent_type})",
                    description=f"Server returned HTTP status 404 for {page.url}",
                    affected_url=page.url,
                    evidence="HTTP/1.1 Status: 404 | Internal Inlinks: 0",
                    observation=f"Server returned HTTP status 404 (Not Found). URL receives 0 internal links from site navigation.",
                    inference="URL is isolated from internal navigation. Likely an obsolete sitemap entry or broken external backlink.",
                    impact="If present in sitemap, it signals stale sitemap maintenance to Googlebot.",
                    recommendation="Remove the URL from sitemap.xml if present. If it receives external referral traffic, configure a 301 redirect.",
                    verification_step="Verify URL is removed from sitemap.xml or returns 410 Gone / 301 redirect.",
                    confidence=IssueConfidence.HIGH,
                ))
        elif page.status_code >= 500:
            issues.append(SEOIssue(
                issue_id="HTTP_5XX_SERVER_ERROR",
                severity=IssueSeverity.CRITICAL,
                category=IssueCategory.TECHNICAL,
                title=f"Server Error (HTTP {page.status_code})",
                description=f"Internal server error occurred when crawling {page.url}",
                affected_url=page.url,
                evidence=f"HTTP/1.1 Status: {page.status_code}",
                observation=f"Server returned HTTP status {page.status_code} server error.",
                inference="Server errors halt Googlebot indexing immediately and can cause domain-wide algorithmic demotion if widespread.",
                impact="Server errors halt Googlebot indexing and can trigger algorithmic ranking drops across the domain.",
                recommendation="Investigate web server and application logs to resolve the backend 5xx crash.",
                verification_step="Monitor server error logs and ensure consistent 200 OK responses under load.",
                confidence=IssueConfidence.HIGH,
            ))
        return issues

    # ------------------------------------------------------------------
    # 2. Mobile Viewport (Precision Engineered)
    # ------------------------------------------------------------------

    def _check_mobile_viewport(self, page: PageData) -> List[SEOIssue]:
        issues = []
        # Check both structured field and raw snippet
        if not page.has_viewport and not page.viewport_meta:
            issues.append(SEOIssue(
                issue_id="MISSING_VIEWPORT_TAG",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.MOBILE,
                title="Missing Viewport Meta Tag",
                description="The HTML <head> does not declare a responsive viewport meta tag.",
                affected_url=page.url,
                evidence="<head> element inspected; no <meta name=\"viewport\"> tag found.",
                impact="Google uses mobile-first indexing; pages without a viewport fail mobile-friendly audits and rank lower on smartphones.",
                recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1.0"> within the <head> section.',
                verification_step="View page source and verify <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"> is in <head>.",
                confidence=IssueConfidence.HIGH,
            ))
        else:
            meta_val = (page.viewport_meta or "").lower()
            if "width=" in meta_val and "device-width" not in meta_val:
                issues.append(SEOIssue(
                    issue_id="FIXED_WIDTH_VIEWPORT",
                    severity=IssueSeverity.MEDIUM,
                    category=IssueCategory.MOBILE,
                    title="Fixed-Width Viewport Configuration",
                    description=f"Viewport tag specifies a fixed pixel width instead of device-width: {page.viewport_meta}",
                    affected_url=page.url,
                    evidence=page.viewport_raw_snippet or f'content="{page.viewport_meta}"',
                    impact="Forces horizontal scrolling on smaller mobile viewports, harming user experience and Core Web Vitals.",
                    recommendation='Replace fixed width with "width=device-width, initial-scale=1.0".',
                    verification_step="Test page in Chrome DevTools mobile device emulation.",
                    confidence=IssueConfidence.HIGH,
                ))
        return issues

    # ------------------------------------------------------------------
    # 2.5 Staging, Dummy & Test Content Detector
    # ------------------------------------------------------------------

    def _check_staging_and_test_content(self, page: PageData) -> List[SEOIssue]:
        issues = []
        staging_patterns = [
            (r"\[staging\]|\(staging\)", "[Staging] marker"),
            (r"\bstaging\s+delivery\s+practice\b", "Staging delivery practice notice"),
            (r"\bno\s+real\s+fulfil{1,2}ment\b", "No real fulfilment disclaimer"),
            (r"\btest\s+listing\b|\btest\s+product\b|\bdummy\s+product\b", "Test / Dummy listing indicator"),
            (r"\blorem\s+ipsum\b", "Lorem Ipsum placeholder text"),
            (r"\bsample\s+item\s*-\s*do\s+not\s+buy\b", "Sample item placeholder notice"),
        ]

        text_to_search = f"{page.title} {' '.join(page.h1_tags)} {page.text_content[:4000]}"
        matched_indicators = []

        for pattern, label in staging_patterns:
            m = re.search(pattern, text_to_search, re.IGNORECASE)
            if m:
                matched_indicators.append(f"{label} ('{m.group(0)}')")

        if matched_indicators:
            sample = matched_indicators[0]
            issues.append(SEOIssue(
                issue_id="PUBLIC_STAGING_TEST_CONTENT",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.CONTENT,
                title="Staging / Mock Test Content Detected on Public Page",
                description=f"Public page contains test/mock placeholders or staging warnings: {sample}",
                affected_url=page.url,
                evidence="; ".join(matched_indicators),
                observation=f"Page content contains staging or placeholder artifacts: {'; '.join(matched_indicators)}.",
                inference="Demonstrates staging or dummy data leakage into crawlable routes. Users and search engines will perceive the website as incomplete, test-only, or untrustworthy, harming E-E-A-T quality evaluation.",
                impact="Severe E-E-A-T demotion by search quality algorithms and immediate loss of user transactional trust.",
                recommendation="Purge test and staging data from the production database or isolate staging environments with HTTP authentication and robots noindex.",
                verification_step="Inspect page text to ensure all placeholder and staging notices are replaced with authentic, production-ready product data.",
                confidence=IssueConfidence.HIGH,
            ))

        return issues

    # ------------------------------------------------------------------
    # 3. Title Tag
    # ------------------------------------------------------------------

    def _check_title(self, page: PageData, title_map: Dict[str, List[PageData]]) -> List[SEOIssue]:
        issues = []
        title = (page.title or "").strip()

        if not title:
            issues.append(SEOIssue(
                issue_id="MISSING_TITLE_TAG",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ON_PAGE,
                title="Missing <title> Tag",
                description="The page HTML does not have a <title> element.",
                affected_url=page.url,
                evidence="<head> inspected; <title> is absent or empty.",
                impact="Title is Google's primary on-page ranking signal and defines the snippet in search engine results pages.",
                recommendation="Add a descriptive, keyword-rich <title> tag between 10 and 65 characters.",
                verification_step="Inspect <title> in page source.",
                confidence=IssueConfidence.HIGH,
            ))
            return issues

        # Title length
        if len(title) > TITLE_MAX_CHARS:
            issues.append(SEOIssue(
                issue_id="TITLE_TOO_LONG",
                severity=IssueSeverity.LOW,
                category=IssueCategory.ON_PAGE,
                title=f"Title Tag Exceeds Display Limit ({len(title)} chars)",
                description=f"Title is {len(title)} characters long (recommended: {TITLE_MIN_CHARS}–{TITLE_MAX_CHARS}).",
                affected_url=page.url,
                evidence=f"<title>{title}</title>",
                impact="Google truncates desktop search titles exceeding ~600px width (approx. 60–65 characters) with an ellipsis (...), potentially cutting off secondary keywords.",
                recommendation=f"Shorten title to under {TITLE_MAX_CHARS} characters while keeping primary keywords near the beginning.",
                verification_step="Check SERP preview tool to ensure title renders without truncation.",
                confidence=IssueConfidence.HIGH,
            ))
        elif len(title) < TITLE_MIN_CHARS:
            issues.append(SEOIssue(
                issue_id="TITLE_TOO_SHORT",
                severity=IssueSeverity.LOW,
                category=IssueCategory.ON_PAGE,
                title=f"Title Tag Under-Optimized ({len(title)} chars)",
                description=f"Title has only {len(title)} characters (recommended minimum: {TITLE_MIN_CHARS}).",
                affected_url=page.url,
                evidence=f"<title>{title}</title>",
                impact="Short titles miss valuable topical keyword opportunities.",
                recommendation="Expand title to incorporate secondary keywords or brand qualifier.",
                verification_step="Verify expanded title in SERP preview.",
                confidence=IssueConfidence.HIGH,
            ))

        # Duplicate title across separate canonical pages
        norm_key = title.lower()
        matching_pages = [
            p for p in title_map.get(norm_key, [])
            if not are_urls_equivalent(p.final_url or p.url, page.final_url or page.url)
        ]
        if len(matching_pages) > 0:
            other_urls = [p.url for p in matching_pages[:3]]
            issues.append(SEOIssue(
                issue_id="DUPLICATE_TITLE_TAG",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ON_PAGE,
                title="Duplicate Title Tag Across Multiple Pages",
                description=f"Identical title '{title}' is shared across {len(matching_pages) + 1} distinct pages.",
                affected_url=page.url,
                evidence=f"Shared by: {', '.join(other_urls)}",
                observation=f"Page title '{title}' is identical to titles declared on {len(matching_pages)} other distinct public URLs.",
                inference="Duplicate titles represent a template metadata or CMS configuration defect across utility, category, or legal pages (not keyword cannibalization unless targeting competing commercial queries). It prevents search engines from distinguishing individual page intents in search snippets.",
                impact="Prevents search engines from presenting distinct snippets in search results; reduces CTR and topical clarity.",
                recommendation="Configure dynamic page titles in your template/CMS (e.g. append page name: 'Privacy Policy | Brand' vs 'Terms | Brand').",
                verification_step="Re-crawl and ensure title is uniquely descriptive across all pages.",
                confidence=IssueConfidence.HIGH,
            ))

        return issues

    # ------------------------------------------------------------------
    # 4. Meta Description
    # ------------------------------------------------------------------

    def _check_meta_description(self, page: PageData, desc_map: Dict[str, List[PageData]]) -> List[SEOIssue]:
        issues = []
        desc = (page.meta_description or "").strip()

        if not desc:
            issues.append(SEOIssue(
                issue_id="MISSING_META_DESCRIPTION",
                severity=IssueSeverity.MEDIUM,
                category=IssueCategory.ON_PAGE,
                title="Missing Meta Description",
                description="The page lacks a meta description tag.",
                affected_url=page.url,
                evidence="<head> inspected; <meta name=\"description\"> tag absent.",
                impact="Search engines generate an automated snippet from body text which may be disjointed or unappealing.",
                recommendation="Add a concise, compelling meta description between 70 and 160 characters summarizing the page.",
                verification_step="Verify <meta name=\"description\" content=\"...\"> is present in head.",
                confidence=IssueConfidence.HIGH,
            ))
            return issues

        if len(desc) > META_DESC_MAX_CHARS:
            issues.append(SEOIssue(
                issue_id="META_DESCRIPTION_TOO_LONG",
                severity=IssueSeverity.LOW,
                category=IssueCategory.ON_PAGE,
                title=f"Meta Description Too Long ({len(desc)} chars)",
                description=f"Meta description is {len(desc)} characters (recommended max: {META_DESC_MAX_CHARS}).",
                affected_url=page.url,
                evidence=f'<meta name="description" content="{desc[:120]}...">',
                impact="Google truncates descriptions exceeding ~960px on desktop and ~680px on mobile.",
                recommendation=f"Trim the description to under {META_DESC_MAX_CHARS} characters.",
                verification_step="Verify description renders fully in SERP snippet preview.",
                confidence=IssueConfidence.HIGH,
            ))

        return issues

    # ------------------------------------------------------------------
    # 5. Headings (H1 Hierarchy)
    # ------------------------------------------------------------------

    def _check_headings(self, page: PageData, h1_map: Dict[str, List[PageData]]) -> List[SEOIssue]:
        issues = []
        h1s = page.h1_tags

        if not h1s:
            issues.append(SEOIssue(
                issue_id="MISSING_H1_TAG",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ON_PAGE,
                title="Missing Main H1 Heading",
                description="No <h1> heading was found on this page.",
                affected_url=page.url,
                evidence="DOM tree inspected; <h1> element count is 0.",
                impact="H1 gives crawlers and assistive technologies the primary contextual topic of the page.",
                recommendation="Add a single <h1> heading clearly stating the main page subject.",
                verification_step="Inspect the rendered DOM to verify <h1> exists.",
                confidence=IssueConfidence.HIGH,
            ))
        elif len(h1s) > 1:
            issues.append(SEOIssue(
                issue_id="MULTIPLE_H1_TAGS",
                severity=IssueSeverity.LOW,
                category=IssueCategory.ON_PAGE,
                title=f"Multiple H1 Headings Found ({len(h1s)} tags)",
                description="The page contains more than one <h1> element.",
                affected_url=page.url,
                evidence=f"H1 tags: {', '.join(h1s[:3])}",
                impact="Multiple H1s dilute topical focus and can confuse heading hierarchy for screen readers.",
                recommendation="Keep one primary <h1> heading per page. Demote secondary headings to <h2>.",
                verification_step="Verify exactly one <h1> exists in DOM.",
                confidence=IssueConfidence.HIGH,
            ))

        return issues

    # ------------------------------------------------------------------
    # 6. Canonical Validation
    # ------------------------------------------------------------------

    def _check_canonical(self, page: PageData) -> List[SEOIssue]:
        issues = []
        if not page.canonical_url:
            has_query = bool(urlparse(page.url).query)
            if has_query:
                issues.append(SEOIssue(
                    issue_id="MISSING_CANONICAL_WITH_QUERY",
                    severity=IssueSeverity.MEDIUM,
                    category=IssueCategory.TECHNICAL,
                    title="Parameterized URL Missing Canonical Tag",
                    description="URL contains query parameters but lacks a canonical link directive.",
                    affected_url=page.url,
                    evidence=f"URL: {page.url} | <link rel=\"canonical\"> absent.",
                    observation=f"URL contains query string ('{urlparse(page.url).query[:40]}') and declares no canonical tag.",
                    inference="Search engines may crawl and index parameter variations separately, causing content duplication and crawl budget waste.",
                    impact="Search engines may index parameterized URLs as separate competing pages.",
                    recommendation="Add <link rel=\"canonical\" href=\"...\"> pointing to the clean canonical URL.",
                    verification_step="Inspect <head> to confirm canonical link points to the non-parameterized version.",
                    confidence=IssueConfidence.HIGH,
                ))
            else:
                issues.append(SEOIssue(
                    issue_id="MISSING_CANONICAL_TAG",
                    severity=IssueSeverity.INFORMATIONAL,
                    category=IssueCategory.TECHNICAL,
                    title="Defensive Best Practice: Missing Self-Referencing Canonical",
                    description="Clean URL does not declare a self-referencing canonical tag.",
                    affected_url=page.url,
                    evidence="<head> element inspected; rel=\"canonical\" absent.",
                    observation="Page HTML does not declare an explicit <link rel='canonical'> tag.",
                    inference="On unique clean URLs without parameters, Google defaults to canonicalizing to the requested URL. Adding a self-referencing tag is a defensive best practice against parameter pollution or external scrapers.",
                    impact="Defensive recommendation; absence alone does not harm indexation on unique clean URLs.",
                    recommendation="Add a self-referencing <link rel=\"canonical\" href=\"...\"> pointing to this exact URL.",
                    verification_step="Inspect <head> to confirm canonical tag is present and matches the URL.",
                    confidence=IssueConfidence.HIGH,
                ))
        else:
            # Check if canonical is an invalid URL or points to a 4xx
            canon = page.canonical_url
            if not canon.startswith(("http://", "https://")):
                issues.append(SEOIssue(
                    issue_id="RELATIVE_CANONICAL_URL",
                    severity=IssueSeverity.HIGH,
                    category=IssueCategory.TECHNICAL,
                    title="Relative Canonical URL Declared",
                    description=f"Canonical URL '{canon}' is relative instead of absolute.",
                    affected_url=page.url,
                    evidence=page.canonical_raw_snippet or f'href="{canon}"',
                    observation=f"Canonical link tag declares relative path '{canon}'.",
                    inference="Search engine crawlers may resolve relative canonicals incorrectly or disregard them entirely.",
                    impact="Search engine crawlers may resolve relative canonicals incorrectly, ignoring the directive.",
                    recommendation="Ensure the canonical tag contains the full absolute URL including scheme and domain.",
                    verification_step="Confirm canonical starts with https://.",
                    confidence=IssueConfidence.HIGH,
                ))
        return issues

    # ------------------------------------------------------------------
    # 7. Images (CLS & Alt Text)
    # ------------------------------------------------------------------

    def _check_images(self, page: PageData) -> List[SEOIssue]:
        issues = []
        for img in page.images:
            src = img.src or ""
            # Missing alt attribute
            if img.alt is None:
                issues.append(SEOIssue(
                    issue_id="IMAGE_MISSING_ALT",
                    severity=IssueSeverity.LOW,
                    category=IssueCategory.ON_PAGE,
                    title="Image Missing Alt Attribute",
                    description=f"Image {src[:60]} does not have an alt attribute.",
                    affected_url=page.url,
                    evidence=img.dom_snippet or f'<img src="{src}">',
                    observation=f"Image element has no alt attribute defined.",
                    inference="Assistive screen readers cannot announce image content; Google Images indexing is hindered.",
                    impact="Harms image accessibility (WCAG 2.1) and prevents Google Image search indexing.",
                    recommendation="Add a descriptive alt attribute, or alt=\"\" if purely decorative.",
                    verification_step="Inspect <img> tag in DOM.",
                    confidence=IssueConfidence.HIGH,
                ))

            # Missing width/height (CLS Risk)
            if not img.width or not img.height:
                issues.append(SEOIssue(
                    issue_id="IMAGE_MISSING_DIMENSIONS",
                    severity=IssueSeverity.LOW,
                    category=IssueCategory.PERFORMANCE,
                    title="Image Missing Explicit Width/Height Attributes",
                    description=f"Image {src[:60]} lacks explicit width and height dimensions.",
                    affected_url=page.url,
                    evidence=img.dom_snippet or f'<img src="{src}">',
                    observation=f"Image tag ('{src[:40]}') lacks explicit width and height HTML attributes.",
                    inference="Browser cannot allocate layout space prior to download, creating Cumulative Layout Shift (CLS) risk if not constrained via CSS aspect-ratio.",
                    impact="May trigger layout shifts during page loading, negatively affecting Core Web Vitals (CLS).",
                    recommendation="Add explicit width and height attributes (or CSS aspect-ratio) to reserve layout space.",
                    verification_step="Verify width and height attributes exist on <img> or CSS aspect-ratio is defined.",
                    confidence=IssueConfidence.HIGH,
                ))
        return issues

    # ------------------------------------------------------------------
    # 8. Content Quality & Uniqueness
    # ------------------------------------------------------------------

    def _check_content_quality(self, page: PageData, hash_map: Dict[str, List[PageData]]) -> List[SEOIssue]:
        issues = []

        # Thin content check: Only flag on public pages with < 150 words of actual body text
        if page.word_count < 150:
            issues.append(SEOIssue(
                issue_id="THIN_CONTENT",
                severity=IssueSeverity.MEDIUM,
                category=IssueCategory.CONTENT,
                title=f"Thin Body Content ({page.word_count} words)",
                description=f"The page body contains only {page.word_count} words of text.",
                affected_url=page.url,
                evidence=f"Extracted plain text length: {page.word_count} words.",
                observation=f"Extracted plain text length is {page.word_count} words (recommended minimum: 150 words).",
                inference="Pages with minimal substance struggle to demonstrate search intent fulfillment or achieve topical depth.",
                impact="Pages with minimal substance struggle to demonstrate search intent fulfillment or achieve topical depth.",
                recommendation="Enrich the page with helpful, authoritative explanations, specifications, or FAQs.",
                verification_step="Review content word count and depth.",
                confidence=IssueConfidence.MEDIUM,
            ))

        # True Duplicate Content check:
        # Strictly between PUBLIC_CONTENT pages, excluding auth gates and app routes
        if page.content_hash:
            dups = [
                p for p in hash_map.get(page.content_hash, [])
                if not are_urls_equivalent(p.final_url or p.url, page.final_url or page.url)
                and getattr(p, "page_type", None) == PageType.PUBLIC_CONTENT
                and not getattr(p, "is_auth_gate", False)
            ]
            if len(dups) > 0:
                other_urls = [p.url for p in dups[:2]]
                issues.append(SEOIssue(
                    issue_id="DUPLICATE_PAGE_CONTENT",
                    severity=IssueSeverity.HIGH,
                    category=IssueCategory.CONTENT,
                    title="Identical Duplicate Content Across Distinct Public URLs",
                    description=f"Public page text is 100% identical to {len(dups)} other distinct public URLs.",
                    affected_url=page.url,
                    evidence=f"Matches: {', '.join(other_urls)} (Hash: {page.content_hash[:8]})",
                    observation=f"HTML body text content hash ({page.content_hash[:8]}) is identical across {len(dups) + 1} distinct public indexable URLs.",
                    inference="Search engines will consolidate or filter these duplicates, diluting ranking equity across competing URLs.",
                    impact="Dilutes link equity and search authority across multiple competing URLs.",
                    recommendation="Consolidate duplicate URLs using 301 redirects or canonical tags pointing to the primary content URL.",
                    verification_step="Ensure only one canonical version of the content is indexable.",
                    confidence=IssueConfidence.HIGH,
                ))

        return issues

    # ------------------------------------------------------------------
    # 9. Structured Data (Reclassified as Opportunity)
    # ------------------------------------------------------------------

    def _check_structured_data(self, page: PageData) -> List[SEOIssue]:
        issues = []
        if not page.structured_data:
            # Informational opportunity only, NOT a warning or failure!
            issues.append(SEOIssue(
                issue_id="OPPORTUNITY_SCHEMA_MARKUP",
                severity=IssueSeverity.INFORMATIONAL,
                category=IssueCategory.STRUCTURED_DATA,
                title="Rich Snippet Opportunity: Schema Markup",
                description="Page has no Schema.org JSON-LD structured data.",
                affected_url=page.url,
                evidence="<script type=\"application/ld+json\"> not found.",
                impact="Structured data is not required to rank, but qualifies pages for Google rich search results (stars, pricing, FAQs).",
                recommendation="Consider adding relevant Schema (e.g. Article, Product, Organization, or FAQPage) to enhance SERP visibility.",
                verification_step="Test URL in Google Rich Results Test tool.",
                confidence=IssueConfidence.HIGH,
            ))
        else:
            for item in page.structured_data:
                if not item.is_valid:
                    issues.append(SEOIssue(
                        issue_id="INVALID_JSON_LD",
                        severity=IssueSeverity.MEDIUM,
                        category=IssueCategory.STRUCTURED_DATA,
                        title="Syntax Error in JSON-LD Structured Data",
                        description=f"JSON-LD block failed to parse: {item.error_message}",
                        affected_url=page.url,
                        evidence=item.raw[:150],
                        impact="Googlebot will discard broken structured data and fail to generate rich snippets.",
                        recommendation="Fix JSON formatting (trailing commas, unescaped quotes).",
                        verification_step="Validate markup with schema.org validator.",
                        confidence=IssueConfidence.HIGH,
                    ))
        return issues

    # ------------------------------------------------------------------
    # 10. Links & Nofollow
    # ------------------------------------------------------------------

    def _check_links(self, page: PageData) -> List[SEOIssue]:
        issues = []
        for link in page.internal_links:
            if link.is_nofollow:
                issues.append(SEOIssue(
                    issue_id="INTERNAL_LINK_NOFOLLOW",
                    severity=IssueSeverity.LOW,
                    category=IssueCategory.INTERNAL_LINKING,
                    title="Nofollow Attribute on Internal Link",
                    description=f"Internal link to {link.href[:60]} uses rel=\"nofollow\".",
                    affected_url=page.url,
                    evidence=link.dom_snippet or f'<a href="{link.href}" rel="nofollow">',
                    impact="Wastes PageRank equity by preventing link weight from flowing to internal pages.",
                    recommendation="Remove rel=\"nofollow\" from internal links.",
                    verification_step="Inspect anchor element in DOM.",
                    confidence=IssueConfidence.HIGH,
                ))
        return issues
