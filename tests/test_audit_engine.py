"""
Unit Test Suite for Godlike SEO Audit Engine 3.0.

Tests 10 controlled scenarios verifying:
1. Genuine 404 with internal inlink -> flagged as HIGH broken link with source & anchor.
2. Cloudflare /cdn-cgi/l/email-protection -> ignored / not flagged as 404.
3. Private login route (/my-bookings) -> classified as auth gate / app route, excluded from duplicate content.
4. Duplicate public content -> flagged as HIGH duplicate content.
5. Duplicate legal page titles -> flagged as DUPLICATE_TITLE_TAG (template defect, not cannibalization).
6. Relative canonical tag -> flagged as HIGH canonical issue.
7. Sitewide and page X-Robots-Tag noindex -> flagged as CRITICAL indexation block with explicit reasons.
8. Public staging listing ([Staging], no real fulfilment) -> flagged as PUBLIC_STAGING_TEST_CONTENT.
9. Orphaned public page -> flagged as ORPHANED_PAGE_DETECTED.
10. Image missing width/height -> flagged as IMAGE_MISSING_DIMENSIONS (LOW CLS risk).
"""

import os
import unittest
from godlike_seo.models import (
    CanonicalState,
    CheckResult,
    CheckStatus,
    PageData,
    PageType,
    HeadingData,
    LinkData,
    ImageData,
    IssueSeverity,
    IssueCategory,
    IssueCluster,
    CrawlResult,
)
from godlike_seo.analyzers.issue_detector import SEOIssueDetector
from godlike_seo.analyzers.link_analyzer import LinkAnalyzer
from godlike_seo.reports.report_generator import ReportGenerator


class TestSEOAuditEngine(unittest.TestCase):
    def setUp(self):
        self.detector = SEOIssueDetector()
        self.link_analyzer = LinkAnalyzer()
        self.report_gen = ReportGenerator()

    # Scenario 1: Genuine 404 with internal link
    def test_scenario_1_genuine_404_with_inlink(self):
        page_404 = PageData(
            url="https://example.com/privacy",
            status_code=404,
            has_html=False,
            inlinks_count=5,
            inbound_link_details=[{
                "source": "https://example.com/",
                "anchor": "Privacy Policy",
                "location": "footer"
            }],
        )
        issues = self.detector._check_http_status(page_404)
        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual(issue.issue_id, "HTTP_404_INTERNAL_LINKED")
        self.assertEqual(issue.severity, IssueSeverity.HIGH)
        self.assertIn("https://example.com/", issue.source_pages)
        self.assertEqual(issue.anchor_text, "Privacy Policy")
        self.assertIn("Typo / Stale Utility Route", issue.title)

    # Scenario 2: Cloudflare /cdn-cgi/ email protection ignored
    def test_scenario_2_cloudflare_cdn_cgi_excluded(self):
        cf_page = PageData(
            url="https://example.com/cdn-cgi/l/email-protection",
            status_code=404,
            has_html=False,
            inlinks_count=10,
        )
        issues = self.detector._check_http_status(cf_page)
        self.assertEqual(len(issues), 0, "Cloudflare /cdn-cgi/ paths must be excluded from broken link issues")

    # Scenario 3: Private login/app route excluded from on-page duplicate content
    def test_scenario_3_private_app_route_no_false_positive_duplicate(self):
        auth_page = PageData(
            url="https://example.com/my-bookings",
            status_code=200,
            has_html=True,
            page_type=PageType.USER_APP_ROUTE,
            is_auth_gate=True,
            word_count=50,
            content_hash="abc123hash",
        )
        # analyze() should skip on-page content checks on non-PUBLIC_CONTENT
        issues = self.detector.analyze([auth_page])
        dup_issues = [i for i in issues if i.issue_id == "DUPLICATE_PAGE_CONTENT"]
        thin_issues = [i for i in issues if i.issue_id == "THIN_CONTENT"]
        self.assertEqual(len(dup_issues), 0)
        self.assertEqual(len(thin_issues), 0)

    # Scenario 4: Duplicate public content flagged
    def test_scenario_4_duplicate_public_content_flagged(self):
        p1 = PageData(
            url="https://example.com/item-a",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            word_count=300,
            content_hash="duplicate_hash_999",
            title="Item A Title",
            headings=[HeadingData(level=1, text="Item A Heading")],
            has_viewport=True,
        )
        p2 = PageData(
            url="https://example.com/item-b",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            word_count=300,
            content_hash="duplicate_hash_999",
            title="Item B Title",
            headings=[HeadingData(level=1, text="Item B Heading")],
            has_viewport=True,
        )
        issues = self.detector.analyze([p1, p2])
        dup_issues = [i for i in issues if i.issue_id == "DUPLICATE_PAGE_CONTENT"]
        self.assertTrue(len(dup_issues) >= 1)
        self.assertEqual(dup_issues[0].severity, IssueSeverity.HIGH)

    # Scenario 5: Duplicate title tags wording focuses on template defect, not cannibalization
    def test_scenario_5_duplicate_title_defect_wording(self):
        p1 = PageData(
            url="https://example.com/privacy",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Shared Site Title - Brand",
            headings=[HeadingData(level=1, text="Privacy")],
            word_count=200,
            has_viewport=True,
        )
        p2 = PageData(
            url="https://example.com/terms",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Shared Site Title - Brand",
            headings=[HeadingData(level=1, text="Terms")],
            word_count=200,
            has_viewport=True,
        )
        issues = self.detector.analyze([p1, p2])
        title_dups = [i for i in issues if i.issue_id == "DUPLICATE_TITLE_TAG"]
        self.assertTrue(len(title_dups) >= 1)
        # Verify wording points to template metadata defect, not keyword cannibalization
        self.assertIn("template metadata or CMS configuration defect", title_dups[0].inference)

    # Scenario 6: Relative canonical tag flagged
    def test_scenario_6_relative_canonical_flagged(self):
        page = PageData(
            url="https://example.com/blog/article",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Article Valid Title",
            headings=[HeadingData(level=1, text="Article Heading")],
            word_count=250,
            canonical_url="/blog/article",  # relative!
            has_viewport=True,
        )
        issues = self.detector.analyze([page])
        rel_canon = [i for i in issues if i.issue_id == "RELATIVE_CANONICAL_URL"]
        self.assertEqual(len(rel_canon), 1)
        self.assertEqual(rel_canon[0].severity, IssueSeverity.LOW)

    # Scenario 7: Sitewide X-Robots-Tag noindex triggers CRITICAL issue on production
    def test_scenario_7_sitewide_noindex_critical(self):
        self.detector.environment = "production"
        pages = [
            PageData(
                url=f"https://example.com/page-{i}",
                status_code=200,
                has_html=True,
                x_robots_tag="noindex, nofollow, noarchive",
                page_type=PageType.PUBLIC_CONTENT,
                title=f"Page {i} Title",
                headings=[HeadingData(level=1, text=f"Heading {i}")],
                word_count=200,
                has_viewport=True,
            )
            for i in range(5)
        ]
        issues = self.detector.analyze(pages)
        sitewide_blocks = [i for i in issues if i.issue_id == "SITEWIDE_INDEXATION_BLOCK"]
        self.assertEqual(len(sitewide_blocks), 1)
        self.assertEqual(sitewide_blocks[0].severity, IssueSeverity.CRITICAL)
        self.assertIn("Domain-Wide Search Indexation Block", sitewide_blocks[0].title)

    # Scenario 8: Staging / Test content detected on public page
    def test_scenario_8_public_staging_test_content(self):
        staging_page = PageData(
            url="https://example.com/item/123",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="[Staging] 4-Person Camping Tent",
            headings=[HeadingData(level=1, text="[Staging] Tent")],
            text_content="This is for staging delivery practice with no real fulfilment of items.",
            word_count=200,
            has_viewport=True,
        )
        issues = self.detector.analyze([staging_page])
        staging_issues = [i for i in issues if i.issue_id == "PUBLIC_STAGING_TEST_CONTENT"]
        self.assertEqual(len(staging_issues), 1)
        self.assertEqual(staging_issues[0].severity, IssueSeverity.HIGH)
        self.assertIn("staging delivery practice", staging_issues[0].evidence.lower())

    # Scenario 9: Orphaned public page detected by LinkAnalyzer
    def test_scenario_9_orphaned_public_page(self):
        home = PageData(
            url="https://example.com/",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            internal_links=[],  # no link to /orphan
            is_indexable=True,
            word_count=300,
        )
        orphan = PageData(
            url="https://example.com/hidden-guide",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            is_indexable=True,
            word_count=400,
            internal_links=[],
        )
        audit = self.link_analyzer.analyze([home, orphan])
        orphaned = audit.get("orphaned_pages", [])
        self.assertIn("https://example.com/hidden-guide", orphaned)
        orphan_issues = [i for i in audit.get("issues", []) if i.issue_id == "ORPHANED_PAGE_DETECTED"]
        self.assertEqual(len(orphan_issues), 1)
        self.assertEqual(orphan_issues[0].severity, IssueSeverity.HIGH)

    # Scenario 10: Image missing width/height attributes (Advisory CLS Check)
    def test_scenario_10_image_missing_dimensions(self):
        page = PageData(
            url="https://example.com/gallery",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Gallery of Camping Tents",
            headings=[HeadingData(level=1, text="Our Gear")],
            word_count=250,
            images=[
                ImageData(src="https://example.com/photo.jpg", alt="Tent in woods", width=None, height=None)
            ],
            has_viewport=True,
        )
        issues = self.detector.analyze([page])
        dim_issues = [i for i in issues if i.issue_id == "IMAGE_MISSING_DIMENSIONS"]
        self.assertEqual(len(dim_issues), 1)
        self.assertEqual(dim_issues[0].severity, IssueSeverity.INFORMATIONAL)
        self.assertEqual(dim_issues[0].category, IssueCategory.PERFORMANCE)

    # Scenario 11: Link Graph Mathematical Identity: Sum(Inlinks) == Sum(Outlinks) == Total Edges
    def test_scenario_11_link_graph_mathematical_identity(self):
        p1 = PageData(
            url="https://example.com/",
            status_code=200,
            has_html=True,
            internal_links=[
                LinkData(href="https://example.com/about", anchor_text="About"),
                LinkData(href="https://example.com/contact", anchor_text="Contact"),
            ],
        )
        p2 = PageData(
            url="https://example.com/about",
            status_code=200,
            has_html=True,
            internal_links=[
                LinkData(href="https://example.com/", anchor_text="Home"),
                LinkData(href="https://example.com/contact", anchor_text="Contact Us"),
            ],
        )
        p3 = PageData(
            url="https://example.com/contact",
            status_code=200,
            has_html=True,
            internal_links=[
                LinkData(href="https://example.com/", anchor_text="Home"),
            ],
        )
        pages = [p1, p2, p3]
        self.link_analyzer.analyze(pages)

        total_inlinks = sum(p.internal_inlinks_count for p in pages)
        total_outlinks = sum(p.internal_outlinks_count for p in pages)
        total_edges = sum(len(p.internal_links) for p in pages)

        self.assertEqual(total_inlinks, total_outlinks, "Sum of internal inlinks must equal sum of internal outlinks")
        self.assertEqual(total_inlinks, total_edges, "Sum of inlinks must equal total internal edges in link graph")
        self.assertEqual(total_inlinks, 5)

    # Scenario 12: Excel Export Consistency & Reason
    def test_scenario_12_excel_export_consistency(self):
        import openpyxl
        import tempfile
        import os
        from godlike_seo.reports.excel_report import ExcelReportGenerator

        p1 = PageData(
            url="https://example.com/",
            status_code=200,
            has_html=True,
            is_indexable=True,
            indexability_reason="Indexable (200 OK)",
            internal_links=[LinkData(href="https://example.com/about", anchor_text="About")],
            external_links=[LinkData(href="https://google.com", anchor_text="Google", is_internal=False)],
        )
        p2 = PageData(
            url="https://example.com/about",
            status_code=200,
            has_html=True,
            is_indexable=False,
            indexability_reason="Blocked by X-Robots-Tag: 'noindex'",
            internal_links=[LinkData(href="https://example.com/", anchor_text="Home")],
        )
        pages = [p1, p2]
        self.link_analyzer.analyze(pages)

        crawl_result = CrawlResult(start_url="https://example.com/", pages=pages)
        report = self.report_gen.generate_report(crawl_result)

        excel_gen = ExcelReportGenerator()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            excel_gen.generate(report, tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
            self.assertTrue(os.path.getsize(tmp_path) > 0)

            # Load generated workbook
            wb = openpyxl.load_workbook(tmp_path)
            self.assertIn("All Evaluated Pages", wb.sheetnames)
            ws = wb["All Evaluated Pages"]

            # Check headers (18 columns in 3.1)
            headers = [ws.cell(row=1, column=c).value for c in range(1, 19)]
            self.assertIn("Is Indexable", headers)
            self.assertIn("Indexability Reason", headers)
            self.assertIn("Canonical State", headers)
            self.assertIn("Internal Inlinks", headers)
            self.assertIn("Internal Outlinks", headers)
            self.assertIn("External Outlinks", headers)

            # Check rows
            row2_vals = [ws.cell(row=2, column=c).value for c in range(1, 19)]
            row3_vals = [ws.cell(row=3, column=c).value for c in range(1, 19)]

            # Row 2 (Home): Indexable: Yes, Internal Inlinks: 1, Internal Outlinks: 1, External Outlinks: 1
            idx_indexable = headers.index("Is Indexable")
            idx_reason = headers.index("Indexability Reason")
            idx_inlinks = headers.index("Internal Inlinks")
            idx_outlinks = headers.index("Internal Outlinks")
            idx_ext = headers.index("External Outlinks")

            self.assertEqual(row2_vals[idx_indexable], "Yes")
            self.assertEqual(row2_vals[idx_inlinks], 1)
            self.assertEqual(row2_vals[idx_outlinks], 1)
            self.assertEqual(row2_vals[idx_ext], 1)

            # Row 3 (About): Indexable: No with reason
            self.assertEqual(row3_vals[idx_indexable], "No")
            self.assertIn("Blocked by X-Robots-Tag", row3_vals[idx_reason])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Scenario 13: Canonical State Taxonomy & Missing Canonical Truthfulness
    def test_scenario_13_canonical_taxonomy_truthfulness(self):
        from godlike_seo.crawler import SEOCrawler, CrawlerConfig

        crawler = SEOCrawler(config=CrawlerConfig())

        # Subtest 1: Page with no canonical tag declared
        html_no_canon = "<html><head><title>No Canonical</title></head><body>Content</body></html>"
        page_no_canon, _ = crawler._extract_page_data(
            url="https://example.com/page",
            final_url="https://example.com/page",
            status_code=200,
            headers={},
            html=html_no_canon,
            response_time_ms=100.0,
            redirect_chain=[],
            depth=0,
        )
        self.assertEqual(page_no_canon.canonical_state, CanonicalState.MISSING)
        self.assertFalse(page_no_canon.is_self_canonical)
        self.assertIsNone(page_no_canon.canonical_url)
        self.assertIn("no canonical declared - Google defaults to URL", page_no_canon.indexability_reason)
        self.assertNotIn("self-canonical", page_no_canon.indexability_reason)

        # Subtest 2: Page with explicit self-referencing canonical
        html_self_canon = '<html><head><link rel="canonical" href="https://example.com/page"></head><body>Content</body></html>'
        page_self_canon, _ = crawler._extract_page_data(
            url="https://example.com/page",
            final_url="https://example.com/page",
            status_code=200,
            headers={},
            html=html_self_canon,
            response_time_ms=100.0,
            redirect_chain=[],
            depth=0,
        )
        self.assertEqual(page_self_canon.canonical_state, CanonicalState.SELF_REFERENCING)
        self.assertTrue(page_self_canon.is_self_canonical)
        self.assertEqual(page_self_canon.canonical_url, "https://example.com/page")

        # Subtest 3: Multiple conflicting canonical tags
        html_multi_canon = '<html><head><link rel="canonical" href="https://example.com/a"><link rel="canonical" href="https://example.com/b"></head><body>Content</body></html>'
        page_multi_canon, _ = crawler._extract_page_data(
            url="https://example.com/page",
            final_url="https://example.com/page",
            status_code=200,
            headers={},
            html=html_multi_canon,
            response_time_ms=100.0,
            redirect_chain=[],
            depth=0,
        )
        self.assertEqual(page_multi_canon.canonical_state, CanonicalState.MULTIPLE)

    # Scenario 14: Malformed location URL / route segment detector
    def test_scenario_14_malformed_location_route_detector(self):
        page_broken_route = PageData(
            url="https://tental.versatyle.in/rent/undefined",
            title="Rent in undefined - Tental",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
        )
        issues = self.detector._check_malformed_urls(page_broken_route)
        self.assertTrue(len(issues) >= 1)
        issue = issues[0]
        self.assertEqual(issue.issue_id, "MALFORMED_LOCATION_URL")
        self.assertEqual(issue.severity, IssueSeverity.HIGH)
        self.assertIn("undefined", issue.evidence)

    # Scenario 15: Staging environment intent with sitewide noindex
    def test_scenario_15_staging_environment_noindex_handling(self):
        pages = [
            PageData(
                url=f"https://tental.versatyle.in/page-{i}",
                status_code=200,
                has_html=True,
                page_type=PageType.PUBLIC_CONTENT,
                x_robots_tag="noindex, nofollow",
                is_indexable=False,
                word_count=200,
            )
            for i in range(5)
        ]
        crawl_result = CrawlResult(start_url="https://tental.versatyle.in/", pages=pages, environment="staging")
        report_gen = ReportGenerator(environment="staging")
        report = report_gen.generate_report(crawl_result, environment="staging")

        self.assertEqual(report.audit_status, "STAGING_PROTECTED")
        self.assertEqual(report.environment_intent, "staging")
        self.assertEqual(report.overall_score, 0.0)
        self.assertGreater(report.diagnostic_score, 0.0)
        self.assertIn("Production readiness is 0/100", report.status_message)
        # No 30-point deduction for staging protection
        noindex_deductions = [d for d in report.all_deductions if "noindex" in d.reason.lower() or "SITEWIDE" in d.rule_title]
        self.assertEqual(len(noindex_deductions), 0)

    # Scenario 16: Production environment intent with sitewide noindex
    def test_scenario_16_production_sitewide_noindex_release_blocker(self):
        pages = [
            PageData(
                url=f"https://production-app.com/page-{i}",
                status_code=200,
                has_html=True,
                page_type=PageType.PUBLIC_CONTENT,
                x_robots_tag="noindex",
                is_indexable=False,
                word_count=200,
            )
            for i in range(5)
        ]
        crawl_result = CrawlResult(start_url="https://production-app.com/", pages=pages, environment="production")
        report_gen = ReportGenerator(environment="production")
        report = report_gen.generate_report(crawl_result, environment="production")

        self.assertEqual(report.audit_status, "INDEXATION_BLOCKED")
        self.assertEqual(report.overall_score, 0.0)
        self.assertIn("CRITICAL RELEASE BLOCKER", report.status_message)

    # Scenario 17: Orphan check NOT_APPLICABLE when zero indexable pages exist
    def test_scenario_17_orphan_check_not_applicable_when_zero_indexable(self):
        pages = [
            PageData(
                url="https://example.com/",
                status_code=200,
                has_html=True,
                page_type=PageType.PUBLIC_CONTENT,
                is_indexable=False,  # Blocked by noindex
                word_count=300,
                internal_links=[LinkData(href="https://example.com/page-1")],
            ),
            PageData(
                url="https://example.com/page-1",
                status_code=200,
                has_html=True,
                page_type=PageType.PUBLIC_CONTENT,
                is_indexable=False,  # Blocked by noindex
                word_count=200,
            ),
        ]
        crawl_result = CrawlResult(start_url="https://example.com/", pages=pages)
        report = self.report_gen.generate_report(crawl_result)

        # Find LINK-001 in check ledger
        orphan_checks = [r for r in report.check_ledger if r.rule_id == "LINK-001"]
        self.assertEqual(len(orphan_checks), 1)
        self.assertEqual(orphan_checks[0].status, CheckStatus.NOT_APPLICABLE)

    # Scenario 18: Link graph alias resolution and edge reconciliation
    def test_scenario_18_link_graph_alias_resolution(self):
        home = PageData(
            url="https://example.com",
            final_url="https://example.com/",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            internal_links=[
                LinkData(href="https://example.com/support", anchor_text="Help Support"),
                LinkData(href="https://example.com/support/", anchor_text="Support Link"),
            ]
        )
        # /support redirects to /login
        support = PageData(
            url="https://example.com/support",
            final_url="https://example.com/login",
            status_code=302,
            has_html=False,
            page_type=PageType.AUTHENTICATION,
        )
        login = PageData(
            url="https://example.com/login",
            final_url="https://example.com/login",
            status_code=200,
            has_html=True,
            page_type=PageType.AUTHENTICATION,
        )
        link_audit = self.link_analyzer.analyze([home, support, login])
        # The login page node should resolve both inbound links
        login_stats = link_audit["page_stats"]["https://example.com/login"]
        self.assertEqual(login_stats.inlinks_count, 2)
        self.assertEqual(login_stats.unique_inlinks_count, 1)

    # Scenario 19: Calibrated rule penalties
    def test_scenario_19_calibrated_rules(self):
        # 1. Multiple H1 tags should be INFORMATIONAL
        p_multi_h1 = PageData(
            url="https://example.com/multi-h1",
            headings=[HeadingData(level=1, text="H1 One"), HeadingData(level=1, text="H1 Two")],
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
        )
        issues = self.detector._check_headings(p_multi_h1, {})
        multi_issue = [i for i in issues if i.issue_id == "MULTIPLE_H1_TAGS"]
        self.assertEqual(len(multi_issue), 1)
        self.assertEqual(multi_issue[0].severity, IssueSeverity.INFORMATIONAL)

        # 2. Missing H1 should be MEDIUM (not HIGH)
        p_no_h1 = PageData(
            url="https://example.com/no-h1",
            headings=[],
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
        )
        issues_no_h1 = self.detector._check_headings(p_no_h1, {})
        missing_h1 = [i for i in issues_no_h1 if i.issue_id == "MISSING_H1_TAG"]
        self.assertEqual(len(missing_h1), 1)
        self.assertEqual(missing_h1[0].severity, IssueSeverity.MEDIUM)

        # 3. Content with 100 words should be INFORMATIONAL opportunity (not penalized)
        p_thin = PageData(
            url="https://example.com/catalog",
            word_count=100,
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
        )
        content_issues = self.detector._check_content_quality(p_thin, {})
        opp_issue = [i for i in content_issues if i.issue_id == "CONTENT_DEPTH_OPPORTUNITY"]
        self.assertEqual(len(opp_issue), 1)
        self.assertEqual(opp_issue[0].severity, IssueSeverity.INFORMATIONAL)

    # Scenario 20: Malformed Open Graph URL (/undefined, /null) -> HIGH
    def test_scenario_20_malformed_og_url(self):
        page = PageData(
            url="https://example.com/",
            canonical_url="https://example.com/",
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
            og_tags={"og:url": "https://example.com/undefined", "og:title": "Example"},
        )
        issues = self.detector._check_open_graph(page)
        malformed_issues = [i for i in issues if i.issue_id == "MALFORMED_OG_URL"]
        self.assertEqual(len(malformed_issues), 1)
        self.assertEqual(malformed_issues[0].severity, IssueSeverity.HIGH)
        self.assertIn("undefined", malformed_issues[0].evidence)

    # Scenario 21: Open Graph URL vs Canonical mismatch -> MEDIUM
    def test_scenario_21_og_url_canonical_mismatch(self):
        page = PageData(
            url="https://example.com/blog/seo-guide",
            canonical_url="https://example.com/blog/seo-guide",
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
            og_tags={"og:url": "https://example.com/articles/seo-guide", "og:title": "SEO Guide"},
        )
        issues = self.detector._check_open_graph(page)
        mismatch_issues = [i for i in issues if i.issue_id == "OG_URL_CANONICAL_MISMATCH"]
        self.assertEqual(len(mismatch_issues), 1)
        self.assertEqual(mismatch_issues[0].severity, IssueSeverity.MEDIUM)

    # Scenario 22: Duplicate / Multiple Meta Descriptions -> MEDIUM
    def test_scenario_22_multiple_meta_descriptions(self):
        page = PageData(
            url="https://example.com/products",
            meta_description="First meta description tag text.",
            meta_description_count=2,
            all_meta_descriptions=["First meta description tag text.", "Second duplicate meta description."],
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
        )
        issues = self.detector._check_meta_description(page, {})
        multi_desc_issues = [i for i in issues if i.issue_id == "MULTIPLE_META_DESCRIPTIONS"]
        self.assertEqual(len(multi_desc_issues), 1)
        self.assertEqual(multi_desc_issues[0].severity, IssueSeverity.MEDIUM)
        self.assertIn("Count: 2", multi_desc_issues[0].evidence)

    # Scenario 23: Robots Snippet Directives (max-snippet:-1 allowed vs nosnippet blocked)
    def test_scenario_23_snippet_directives(self):
        # 1. Page with max-snippet:-1 is NOT blocked
        page_unrestricted = PageData(
            url="https://example.com/",
            meta_robots="index, follow, max-snippet:-1, max-image-preview:large",
            is_snippet_blocked=False,
            snippet_blocking_reason="Unrestricted snippet length allowed (max-snippet:-1)",
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
        )
        issues_ok = self.detector._check_robots_and_snippets(page_unrestricted)
        self.assertEqual(len(issues_ok), 0)

        # 2. Page with nosnippet IS blocked
        page_blocked = PageData(
            url="https://example.com/private",
            meta_robots="index, follow, nosnippet",
            is_snippet_blocked=True,
            snippet_blocking_reason="nosnippet directive present in meta robots or X-Robots-Tag",
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
        )
        issues_blocked = self.detector._check_robots_and_snippets(page_blocked)
        snippet_issues = [i for i in issues_blocked if i.issue_id == "SEARCH_SNIPPET_BLOCKED"]
        self.assertEqual(len(snippet_issues), 1)
        self.assertEqual(snippet_issues[0].severity, IssueSeverity.HIGH)

    # Scenario 24: Decorative / 1x1 spacer GIF exclusion from missing-alt
    def test_scenario_24_decorative_image_alt_exclusion(self):
        page = PageData(
            url="https://example.com/gallery",
            images=[
                # 1. Real content image missing alt -> should be flagged
                ImageData(src="https://example.com/hero.jpg", alt=None, width=800, height=600, is_decorative=False),
                # 2. Next.js 1x1 transparent spacer GIF -> must NOT be flagged
                ImageData(src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7", alt=None, is_decorative=True),
                # 3. 1x1 tracking pixel -> must NOT be flagged
                ImageData(src="https://example.com/pixel.gif", alt=None, width=1, height=1, is_decorative=True),
                # 4. ARIA presentation image -> must NOT be flagged
                ImageData(src="https://example.com/bg-pattern.svg", alt=None, dom_snippet='<img src="..." role="presentation">', is_decorative=True),
            ],
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
        )
        issues = self.detector._check_images(page)
        alt_issues = [i for i in issues if i.issue_id == "IMAGE_MISSING_ALT"]
        # Only the 1 real content image should be flagged
        self.assertEqual(len(alt_issues), 1)
        self.assertEqual(alt_issues[0].affected_url, "https://example.com/gallery")
        self.assertIn("hero.jpg", alt_issues[0].evidence)

    # Scenario 25: JSON-LD Structured Data extraction with @graph & multiple items
    def test_scenario_25_json_ld_graph_extraction(self):
        from godlike_seo.crawler import SEOCrawler
        crawler = SEOCrawler()
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@graph": [
                    {"@type": "Organization", "name": "Acme Corp", "url": "https://example.com"},
                    {"@type": "WebSite", "url": "https://example.com", "name": "Acme Portal"}
                ]
            }
            </script>
        </head>
        <body><h1>Hello</h1><p>Test content.</p></body>
        </html>
        """
        page, _ = crawler._extract_page_data(
            url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            headers={"content-type": "text/html"},
            html=html,
            response_time_ms=50.0,
            redirect_chain=[],
            depth=0,
        )
        # Should unpack both Organization and WebSite from @graph
        self.assertEqual(len(page.structured_data), 2)
        types = [s.type for s in page.structured_data]
        self.assertIn("Organization", types)
        self.assertIn("WebSite", types)

        # Structured data check should report no OPPORTUNITY_SCHEMA_MARKUP
        issues = self.detector._check_structured_data(page)
        opp_issues = [i for i in issues if i.issue_id == "OPPORTUNITY_SCHEMA_MARKUP"]
        self.assertEqual(len(opp_issues), 0)

    # Scenario 26: Kev Decision Engine verification & AI Agent Remediation Plan
    def test_scenario_26_decision_engine_and_remediation_planner(self):
        from godlike_seo.decision_engine import KevDecisionEngine, AgentRemediationPlanner
        cluster = IssueCluster(
            issue_id="MALFORMED_OG_URL",
            title="Malformed Open Graph URL Detected",
            severity=IssueSeverity.HIGH,
            category=IssueCategory.SOCIAL,
            description="og:url contains /undefined",
            observation="Open Graph URL declares https://example.com/undefined",
            inference="Breaks social sharing previews.",
            impact="Broken previews.",
            recommendation="Sanitize og:url.",
            verification_step="Check tag in head.",
            confidence="high",
            occurrences_count=1,
            affected_urls=["https://example.com/"],
            sample_evidence=[{"url": "https://example.com/", "evidence": '<meta property="og:url" content="https://example.com/undefined">'}]
        )
        engine = KevDecisionEngine()
        verif = engine.verify_cluster(cluster)
        self.assertTrue(verif.is_verified)
        self.assertFalse(verif.is_false_positive)
        self.assertGreaterEqual(verif.confidence, 0.9)
        self.assertEqual(verif.remediation_action, "code_patch")

        planner = AgentRemediationPlanner()
        plan = planner.generate_plan("example.com", [cluster], [verif])
        self.assertEqual(len(plan.tasks), 1)
        task = plan.tasks[0]
        self.assertEqual(task.priority, "P1")
        self.assertIn("og:url", task.git_commit_proposal)
        self.assertIn("test_og_url_valid", task.playwright_test_code)

    # Scenario 27: Calibrated Scoring Architecture & Release Gating (Scope-Aware Gating)
    def test_scenario_27_calibrated_scoring_and_release_gating(self):
        # Part A: Isolated social tag defect (MALFORMED_OG_URL) applies category deduction
        # without halting releases or falsely capping an otherwise healthy site.
        page = PageData(
            url="https://example.com/",
            canonical_url="https://example.com/",
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
            title="Valid Title For Testing Scoring Engine",
            headings=[HeadingData(level=1, text="Valid H1 Heading")],
            meta_description="Valid length meta description for testing the scoring system correctly.",
            word_count=500,
            has_viewport=True,
            og_tags={"og:url": "https://example.com/undefined", "og:title": "Example"},
        )
        crawl_result = CrawlResult(start_url="https://example.com/", pages=[page])
        report = self.report_gen.generate_report(crawl_result)

        # 1. Social category must exist and be deducted (-8 pts for MALFORMED_OG_URL)
        self.assertIn("social", report.category_scores)
        social_cs = report.category_scores["social"]
        self.assertEqual(social_cs.score, 92.0)
        self.assertEqual(len(social_cs.deductions), 1)
        self.assertEqual(social_cs.deductions[0].points_deducted, 8.0)

        # 2. Deduction must be recorded in itemized all_deductions list
        malformed_deductions = [d for d in report.all_deductions if "Open Graph" in d.rule_title or "og:url" in d.reason.lower()]
        self.assertEqual(len(malformed_deductions), 1)

        # 3. Isolated social advisory does NOT halt release: site passes with mathematical score reduction (~98.8)
        self.assertEqual(report.audit_status, "PASS")
        self.assertGreaterEqual(report.overall_score, 95.0)

        # Part B: Systemic indexation/integrity defect (CANONICAL_POINTS_TO_4XX) GATES release
        page_broken_canonical = PageData(
            url="https://example.com/broken-canonical",
            canonical_url="https://example.com/missing-404-target",
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
            title="Valid Title For Testing Scoring Engine",
            word_count=400,
            has_viewport=True,
        )
        page_404_target = PageData(
            url="https://example.com/missing-404-target",
            status_code=404,
            has_html=False,
            page_type=PageType.PUBLIC_CONTENT,
        )
        crawl_gated = CrawlResult(start_url="https://example.com/", pages=[page_broken_canonical, page_404_target])
        report_gated = self.report_gen.generate_report(crawl_gated)
        self.assertEqual(report_gated.audit_status, "NEEDS_REVIEW")
        self.assertIn("SYSTEMIC DEFECTS", report_gated.status_message)
        self.assertLessEqual(report_gated.overall_score, 84.9)

    # Scenario 28: Code Tutorial Readability Stripping (Exempts Technical Code from False Alarms)
    def test_scenario_28_code_tutorial_readability_stripping(self):
        from godlike_seo.analyzers.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()

        tutorial_text = (
            "In this tutorial we learn how to implement binary search in Python.\n"
            "Binary search runs in logarithmic time complexity O(log n).\n"
            "Here is the complete implementation with helper methods:\n"
            "def binary_search(arr, target):\n"
            "    left = 0\n"
            "    right = len(arr) - 1\n"
            "    while left <= right:\n"
            "        mid = left + (right - left) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            left = mid + 1\n"
            "        else:\n"
            "            right = mid - 1\n"
            "    return -1\n"
            "# Run the code snippet\n"
            "arr = [1, 3, 5, 7, 9, 11]\n"
            "print(binary_search(arr, 7))\n"
        )
        page = PageData(
            url="https://example.com/tutorials/binary-search",
            text_content=tutorial_text,
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
            title="Python Binary Search Tutorial",
            headings=[HeadingData(level=1, text="Binary Search Tutorial")],
            word_count=350,
        )
        result = analyzer.analyze([page])
        # Assert no false positive "Content Difficult to Read" issue on this technical tutorial
        diff_issues = [i for i in result.get("issues", []) if i.issue_id == "CONTENT_DIFFICULT_READABILITY"]
        self.assertEqual(len(diff_issues), 0)

    # Scenario 29: Heuristic Keyword Overlap (INFORMATIONAL, 0 penalty)
    def test_scenario_29_heuristic_keyword_overlap(self):
        from godlike_seo.analyzers.content_analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()

        p1 = PageData(
            url="https://example.com/machine-learning-basics",
            title="Complete Machine Learning Tutorial Guide",
            headings=[HeadingData(level=1, text="Machine Learning Tutorial")],
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
            word_count=300,
            text_content="Introduction to supervised and unsupervised machine learning algorithms.",
            is_indexable=True,
        )
        p2 = PageData(
            url="https://example.com/advanced-machine-learning",
            title="Advanced Machine Learning Tutorial Course",
            headings=[HeadingData(level=1, text="Machine Learning Tutorial")],
            has_html=True,
            status_code=200,
            page_type=PageType.PUBLIC_CONTENT,
            word_count=300,
            text_content="Deep neural networks and reinforcement machine learning architectures.",
            is_indexable=True,
        )
        result = analyzer.analyze([p1, p2])
        overlap_issues = [i for i in result.get("issues", []) if i.issue_id == "TOPICAL_KEYWORD_OVERLAP"]
        self.assertGreaterEqual(len(overlap_issues), 1)
        self.assertEqual(overlap_issues[0].severity, IssueSeverity.INFORMATIONAL)
        self.assertIn("Google Search Console", overlap_issues[0].observation)

    # Scenario 30: Empty/Failed Crawl yields INCONCLUSIVE, 0 score, and SKIPPED ledger
    def test_scenario_30_empty_crawl_truthful_scoring(self):
        failed_crawl = CrawlResult(
            start_url="https://unreachable-host.xyz/",
            domain="unreachable-host.xyz",
            pages=[],
            pages_discovered_count=0,
            crawl_coverage_pct=0.0,
        )
        report = self.report_gen.generate_report(failed_crawl)
        self.assertEqual(report.audit_status, "INCONCLUSIVE")
        self.assertEqual(report.overall_score, 0.0)
        self.assertIn("inconclusive", report.status_message.lower())
        # All checks must be SKIPPED, none should falsely PASS
        passed_checks = [c for c in report.check_ledger if c.status == CheckStatus.PASS]
        self.assertEqual(len(passed_checks), 0)
        skipped_checks = [c for c in report.check_ledger if c.status == CheckStatus.SKIPPED]
        self.assertGreaterEqual(len(skipped_checks), 25)

    # Scenario 31: Sitewide Noindex on Unconfirmed Host triggers INDEXATION_WARNING
    def test_scenario_31_unconfirmed_environment_noindex_warning(self):
        pages = [
            PageData(
                url=f"https://unconfirmed-custom-subdomain.org/p-{i}",
                status_code=200,
                has_html=True,
                page_type=PageType.PUBLIC_CONTENT,
                x_robots_tag="noindex, nofollow",
                is_indexable=False,
                word_count=200,
            )
            for i in range(5)
        ]
        crawl = CrawlResult(start_url="https://unconfirmed-custom-subdomain.org/", pages=pages, environment=None)
        report = self.report_gen.generate_report(crawl, environment=None)
        self.assertEqual(report.environment_intent, "unknown")
        self.assertEqual(report.audit_status, "INDEXATION_WARNING")
        self.assertLessEqual(report.overall_score, 49.0)
        self.assertIn("ENVIRONMENT UNCONFIRMED", report.status_message)

    # Scenario 32: Web App SSRF Defense
    def test_scenario_32_web_app_ssrf_protection(self):
        from godlike_seo.web.app import is_safe_target_url
        # Localhost & Loopback
        safe, _ = is_safe_target_url("http://localhost:8000")
        self.assertFalse(safe)
        safe, _ = is_safe_target_url("http://127.0.0.1:5000/admin")
        self.assertFalse(safe)
        # Private RFC 1918
        safe, _ = is_safe_target_url("http://192.168.1.1/router")
        self.assertFalse(safe)
        safe, _ = is_safe_target_url("http://10.0.0.5/internal")
        self.assertFalse(safe)
        # Cloud Metadata
        safe, _ = is_safe_target_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        safe, _ = is_safe_target_url("http://metadata.google.internal/computeMetadata/v1/")
        self.assertFalse(safe)
        # Invalid schemes
        safe, _ = is_safe_target_url("file:///etc/passwd")
        self.assertFalse(safe)
        safe, _ = is_safe_target_url("ftp://ftp.example.com")
        self.assertFalse(safe)

    # Scenario 33: Insufficient Crawl Coverage Release Gate
    def test_scenario_33_insufficient_crawl_coverage_release_gate(self):
        # 10 discovered URLs, but only 2 crawled (20% coverage) -> INSUFFICIENT_COVERAGE
        pages = [
            PageData(
                url=f"https://large-site.example.com/page-{i}",
                status_code=200,
                has_html=True,
                page_type=PageType.PUBLIC_CONTENT,
                title=f"Sample Page {i} Title",
                headings=[HeadingData(level=1, text=f"Heading {i}")],
                meta_description="Sample description that meets normal length requirements for the page.",
                word_count=400,
                has_viewport=True,
            )
            for i in range(2)
        ]
        crawl = CrawlResult(
            start_url="https://large-site.example.com/",
            pages=pages,
            pages_discovered_count=10,
            crawl_coverage_pct=20.0,
        )
        report = self.report_gen.generate_report(crawl)
        self.assertEqual(report.audit_status, "INSUFFICIENT_COVERAGE")
        self.assertIn("INSUFFICIENT CRAWL COVERAGE", report.status_message)

        # Unmatched rules in ledger must reflect sample qualification, not unqualified full site PASS
        sample_checks = [c for c in report.check_ledger if "Full site unverified" in c.evidence]
        self.assertGreaterEqual(len(sample_checks), 20)

    # Scenario 34: Precision Route Classification (Code Tutorials vs Auth/App Routes)
    def test_scenario_34_precision_route_classification(self):
        from godlike_seo.analyzers.page_classifier import PageClassifier
        classifier = PageClassifier()

        # Public educational and programming tutorial routes must NOT be misclassified as auth/app gates
        tutorial_urls = [
            "https://www.geeksforgeeks.org/register/in-c",
            "https://www.geeksforgeeks.org/password/hash",
            "https://example.com/tutorials/auth/oauth-guide",
            "https://example.com/payment-methods",
            "https://example.com/portal-docs",
            "https://example.com/billing-faq",
        ]
        for u in tutorial_urls:
            res = classifier.classify(u, 200, "<html><body><h1>Guide</h1></body></html>")
            self.assertEqual(res["page_type"], PageType.PUBLIC_CONTENT, f"URL {u} was incorrectly classified as {res['page_type']}")

        # Real auth and application transaction routes must be correctly classified
        auth_urls = [
            "https://example.com/login",
            "https://example.com/signup",
            "https://example.com/users/register",
            "https://example.com/accounts/login",
            "https://example.com/forgot-password",
        ]
        for u in auth_urls:
            res = classifier.classify(u, 200, "<html><body><h1>Sign In</h1></body></html>")
            self.assertEqual(res["page_type"], PageType.AUTHENTICATION, f"URL {u} was not classified as AUTHENTICATION")

        app_urls = [
            "https://example.com/checkout",
            "https://example.com/cart",
            "https://example.com/account/billing",
            "https://example.com/dashboard/manage",
        ]
        for u in app_urls:
            res = classifier.classify(u, 200, "<html><body><h1>App</h1></body></html>")
            self.assertEqual(res["page_type"], PageType.USER_APP_ROUTE, f"URL {u} was not classified as USER_APP_ROUTE")

    # Scenario 35: Prerequisite Check Ledger Truthfulness (SKIPPED and NOT_APPLICABLE)
    def test_scenario_35_prerequisite_check_ledger_truthfulness(self):
        # 1 single page crawled, robots and sitemaps not attempted
        page = PageData(
            url="https://solo-page.example.com/",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Solo Page Title",
            headings=[HeadingData(level=1, text="Solo Heading")],
            meta_description="A solo page meta description for evaluating ledger prerequisite truthfulness.",
            word_count=500,
            has_viewport=True,
        )
        crawl = CrawlResult(
            start_url="https://solo-page.example.com/",
            pages=[page],
            pages_discovered_count=1,
            crawl_coverage_pct=100.0,
            robots_attempted=False,
            sitemaps_attempted=False,
        )
        report = self.report_gen.generate_report(crawl)

        ledger_map = {c.rule_id: c for c in report.check_ledger}

        # Sitemap (TECH-006) and Robots (TECH-007) must be SKIPPED
        self.assertEqual(ledger_map["TECH-006"].status, CheckStatus.SKIPPED)
        self.assertEqual(ledger_map["TECH-007"].status, CheckStatus.SKIPPED)

        # Cross-page duplicate checks (CONTENT-002, ONPAGE-002) must be NOT_APPLICABLE with 1 page
        self.assertEqual(ledger_map["CONTENT-002"].status, CheckStatus.NOT_APPLICABLE)
        self.assertEqual(ledger_map["ONPAGE-002"].status, CheckStatus.NOT_APPLICABLE)

    # Scenario 36: Multi-Format Report Generation (HTML, Markdown, Excel Check Ledger & Statuses)
    def test_scenario_36_multi_format_report_check_ledger_and_status_rendering(self):
        import tempfile
        import openpyxl
        from godlike_seo.reports.html_report import HTMLReportGenerator
        from godlike_seo.reports.markdown_report import MarkdownReportGenerator
        from godlike_seo.reports.excel_report import ExcelReportGenerator

        page = PageData(
            url="https://multi-format.example.com/",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Multi Format Test",
            headings=[HeadingData(level=1, text="Heading")],
            meta_description="A descriptive sentence for validating multi format reporting engines.",
            word_count=450,
            has_viewport=True,
        )
        crawl = CrawlResult(
            start_url="https://multi-format.example.com/",
            pages=[page],
            pages_discovered_count=1,
            crawl_coverage_pct=100.0,
        )
        report = self.report_gen.generate_report(crawl)

        # 1. HTML Report validation
        html_gen = HTMLReportGenerator()
        html_out = html_gen.render(report)
        self.assertIn("EVIDENCE ENGINE 3.3.1", html_out)
        self.assertIn("Deterministic Check Execution Ledger", html_out)
        self.assertIn("TECH-001", html_out)
        self.assertIn("RELEASE AUDIT PASSED", html_out)

        # 2. Markdown Report validation
        md_gen = MarkdownReportGenerator()
        md_out = md_gen.render(report)
        self.assertIn("Deterministic Check Execution Ledger", md_out)
        self.assertIn("TECH-001", md_out)
        self.assertIn("> [!TIP]", md_out)

        # 3. Excel Report validation
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            excel_gen = ExcelReportGenerator()
            excel_gen.generate(report, tmp_path)
            wb = openpyxl.load_workbook(tmp_path)
            self.assertIn("Check Ledger", wb.sheetnames)
            ws_ledger = wb["Check Ledger"]
            self.assertEqual(ws_ledger["A1"].value, "Rule ID")
            self.assertEqual(ws_ledger["A2"].value, "TECH-001")
            self.assertEqual(ws_ledger["D2"].value, "PASS")
            # Verify verdict in Summary sheet
            ws_summary = wb["Summary & Health"]
            self.assertIn("Verdict:", str(ws_summary["A4"].value))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Scenario 37: Web Dashboard & API Endpoints Verification
    def test_scenario_37_web_dashboard_routes(self):
        from godlike_seo.web.app import app
        client = app.test_client()

        # 1. Dashboard home renders cleanly
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Deep Site Crawler", res.data)

        # 2. SSRF check on crawl endpoint correctly rejects private/loopback targets
        res = client.post("/api/crawl", json={"url": "http://127.0.0.1:8080"})
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"SSRF Protection", res.data)

        # 3. Keyword explorer API expands terms into structured objects
        res = client.post("/api/keywords", json={"seed": "seo"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)

    # Scenario 38: Dedicated Image SEO & Performance Diagnostics
    def test_scenario_38_image_analyzer_deep_diagnostics(self):
        from godlike_seo.analyzers.image_analyzer import ImageAnalyzer
        from godlike_seo.models import ImageData

        page = PageData(
            url="https://example.com/gallery",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            images=[
                # 0. Hero image with loading="lazy" (Anti-pattern)
                ImageData(url="https://example.com/hero.jpg", src="https://example.com/hero.jpg", alt="Hero Banner", loading="lazy", width=1200, height=600),
                # 1. Missing alt attribute
                ImageData(url="https://example.com/missing-alt.png", src="https://example.com/missing-alt.png", alt=None, width=400, height=300),
                # 2. Generic placeholder alt
                ImageData(url="https://example.com/generic.jpg", src="https://example.com/generic.jpg", alt="image", width=300, height=200),
                # 3. Missing dimensions (CLS risk)
                ImageData(url="https://example.com/no-dimensions.png", src="https://example.com/no-dimensions.png", alt="Valid Alt Text", width=0, height=0),
                # 4. Critically oversized image (>1MB)
                ImageData(url="https://example.com/huge.png", src="https://example.com/huge.png", alt="Huge Graphic", size_bytes=2_500_000, width=1920, height=1080),
            ]
        )
        analyzer = ImageAnalyzer()
        res = analyzer.analyze([page])
        issue_ids = [i.issue_id for i in res["issues"]]

        self.assertIn("IMAGE_HERO_LAZY_LOADED", issue_ids)
        self.assertIn("IMAGE_MISSING_ALT", issue_ids)
        self.assertIn("IMAGE_LOW_QUALITY_ALT", issue_ids)
        self.assertIn("IMAGE_MISSING_DIMENSIONS", issue_ids)
        self.assertIn("IMAGE_CRITICALLY_OVERSIZED", issue_ids)

    # Scenario 39: Deep Schema.org Validation against Google Rich Results Rules
    def test_scenario_39_schema_validator_google_rich_results(self):
        from godlike_seo.analyzers.schema_validator import SchemaValidator
        from godlike_seo.models import StructuredDataItem

        # 1. Product schema missing offers/review
        page_product = PageData(
            url="https://example.com/product/shoes",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            structured_data=[
                StructuredDataItem(
                    format="json-ld",
                    type="Product",
                    data={"@type": "Product", "name": "Running Shoes"},
                    is_valid=True,
                )
            ]
        )
        validator = SchemaValidator()
        issues_prod = validator.validate_page(page_product)
        self.assertTrue(any(i.issue_id == "SCHEMA_MISSING_REQUIRED_PROPERTY" for i in issues_prod))
        self.assertTrue(any("offers" in i.title for i in issues_prod))

        # 2. FAQPage schema with malformed Question structure
        page_faq = PageData(
            url="https://example.com/faq",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            structured_data=[
                StructuredDataItem(
                    format="json-ld",
                    type="FAQPage",
                    data={"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": "What is this?"}]},
                    is_valid=True,
                )
            ]
        )
        issues_faq = validator.validate_page(page_faq)
        self.assertTrue(any(i.issue_id == "SCHEMA_INVALID_FAQ_STRUCTURE" for i in issues_faq))

        # 3. Valid Article with author entity
        page_article = PageData(
            url="https://example.com/blog/seo-guide",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            structured_data=[
                StructuredDataItem(
                    format="json-ld",
                    type="Article",
                    data={
                        "@type": "Article",
                        "headline": "Complete SEO Guide",
                        "image": "https://example.com/img.jpg",
                        "datePublished": "2026-01-01",
                        "author": {"@type": "Person", "name": "Prasad Shinde"},
                    },
                    is_valid=True,
                )
            ]
        )
        issues_art = validator.validate_page(page_article)
        self.assertFalse(any(i.issue_id == "SCHEMA_MISSING_REQUIRED_PROPERTY" for i in issues_art))

    # Scenario 40: Multi-Dimensional Search Intent & Semantic Relevance
    def test_scenario_40_keyword_intelligence_and_intent(self):
        from godlike_seo.serp.keyword_analyzer import KeywordAnalyzer, SearchIntent

        analyzer = KeywordAnalyzer()

        # Intent classification check
        intent_tx, conf_tx = analyzer.classify_intent("buy sony camera online discount")
        self.assertEqual(intent_tx, SearchIntent.TRANSACTIONAL)
        self.assertGreaterEqual(conf_tx, 0.85)

        intent_comm, conf_comm = analyzer.classify_intent("best camera vs smartphone review 2026")
        self.assertEqual(intent_comm, SearchIntent.COMMERCIAL)
        self.assertGreaterEqual(conf_comm, 0.85)

        intent_loc, conf_loc = analyzer.classify_intent("camera rental near me in bangalore")
        self.assertEqual(intent_loc, SearchIntent.LOCAL)

        intent_info, conf_info = analyzer.classify_intent("how to configure aperture and shutter speed")
        self.assertEqual(intent_info, SearchIntent.INFORMATIONAL)

        # Relevance scoring check: contiguous phrase gets higher score than tangential query
        score_exact = analyzer.calculate_relevance("seo toolkit", "seo toolkit for python developers", rank_position=1)
        score_tangent = analyzer.calculate_relevance("seo toolkit", "random python library tutorial", rank_position=8)
        self.assertGreater(score_exact, score_tangent)

        # Volume tier & KD check
        vol, kd = analyzer.estimate_volume_and_difficulty("buy shoes", SearchIntent.TRANSACTIONAL, rank=1)
        self.assertEqual(vol, "HIGH")
        self.assertGreaterEqual(kd, 70.0)

    # Scenario 41: Competitor Parity & Calibrated Ranking Probability
    def test_scenario_41_competitor_parity_and_ranking_probability(self):
        from godlike_seo.serp.competitor_analyzer import CompetitorAnalyzer
        from godlike_seo.serp.serp_scraper import SERPAnalysis, SERPResult

        # Mock SERP scraper with pre-configured results
        class MockScraper:
            def scrape(self, keyword, num_results=10):
                return SERPAnalysis(
                    keyword=keyword,
                    results=[
                        SERPResult(position=1, url="https://comp1.com/guide", title="Best Guide", snippet="", domain="comp1.com", keyword=keyword),
                        SERPResult(position=2, url="https://comp2.com/guide", title="Top Guide", snippet="", domain="comp2.com", keyword=keyword),
                    ],
                    total_results=2,
                    search_engine="google",
                )

        analyzer = CompetitorAnalyzer(scraper=MockScraper())
        # Mock scrape page metrics to avoid live HTTP requests
        analyzer._scrape_page_metrics = lambda url, kw: None
        from godlike_seo.models import CompetitorMetrics
        mock_your = CompetitorMetrics(domain="mybrand.com", url="https://mybrand.com/guide", word_count=1200, heading_count=6, keyword_in_title=True, keyword_in_h1=True, has_structured_data=True, response_time_ms=250.0)
        mock_c1 = CompetitorMetrics(domain="comp1.com", url="https://comp1.com/guide", word_count=1000, heading_count=5, keyword_in_title=True, keyword_in_h1=True, has_structured_data=True, response_time_ms=300.0)
        analyzer._scrape_page_metrics = lambda u, kw: mock_your if "mybrand.com" in u else mock_c1

        analysis = analyzer.analyze_for_keyword("seo guide", your_url="https://mybrand.com/guide", max_competitors=1)
        self.assertGreaterEqual(analysis.competitive_gap_score, 80.0)
        self.assertGreaterEqual(analysis.ranking_probability_pct, 20.0)
        self.assertEqual(analysis.parity_status, "HIGH_COMPETITIVE_PARITY")

    # Scenario 42: Google Search Console Performance Intelligence
    def test_scenario_42_google_search_console_integration(self):
        from godlike_seo.integrations.search_console import GoogleSearchConsoleClient

        client = GoogleSearchConsoleClient(enable_demo_mode=True)
        report = client.fetch_search_analytics("https://mysite.example.com")

        self.assertGreater(report.total_impressions, 0)
        self.assertGreater(report.total_clicks, 0)
        # Striking distance opportunities must be identified
        self.assertGreater(len(report.striking_distance), 0)
        for q in report.striking_distance:
            self.assertGreaterEqual(q.position, 7.5)
            self.assertLessEqual(q.position, 20.0)

    # Scenario 43: Google PageSpeed Insights & Core Web Vitals
    def test_scenario_43_pagespeed_insights_and_crux_vitals(self):
        from godlike_seo.integrations.pagespeed import PageSpeedInsightsClient

        client = PageSpeedInsightsClient()
        cwv = client.run_audit("https://example.com")

        self.assertIn(cwv.overall_status, ("PASS", "NEEDS_IMPROVEMENT", "POOR"))
        self.assertGreater(cwv.performance_score, 0)
        self.assertIsNotNone(cwv.lcp.value)
        self.assertIsNotNone(cwv.cls.value)
        self.assertIsNotNone(cwv.inp.value)
        self.assertGreater(len(cwv.opportunities), 0)

    # Scenario 44: AI Remediation Plan & Markdown Runbook Export
    def test_scenario_44_ai_remediation_plan_export(self):
        from godlike_seo.decision_engine import RemediationPlan, RemediationTask

        plan = RemediationPlan(
            domain="example.com",
            generated_at="2026-11-15T00:00:00Z",
            total_tasks=1,
            tasks=[
                RemediationTask(
                    task_id="SEO-TASK-001",
                    issue_id="MALFORMED_OG_URL",
                    priority="P1",
                    title="Malformed Open Graph URL",
                    target_component="components/MetaHead.tsx",
                    affected_urls_count=1,
                    sample_url="https://example.com/p1",
                    problem_statement="og:url declares /undefined",
                    code_diff_solution="Replace undefined with page.canonicalUrl",
                    playwright_test_code="async def test_og(page): pass",
                    git_commit_proposal="fix(seo): correct og:url token",
                )
            ],
            agent_remediation_summary="1 task ready for AI automated patching.",
        )
        md = plan.to_markdown()
        self.assertIn("SEO-TASK-001", md)
        self.assertIn("components/MetaHead.tsx", md)
        self.assertIn("```diff", md)
        self.assertIn("```python", md)

    # Scenario 45: Healthy Indexable Site Ready for Search
    def test_scenario_45_healthy_indexable_site_ready_for_search(self):
        from godlike_seo.models import IndexabilityStatus, CanonicalState
        p1 = PageData(
            url="https://example.com/",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Authoritative Example Homepage",
            meta_description="Comprehensive guide to example architecture and technical implementations.",
            canonical_url="https://example.com/",
            canonical_state=CanonicalState.SELF_REFERENCING,
            headings=[HeadingData(level=1, text="Main Page Topic")],
            word_count=500,
            has_viewport=True,
            robots_txt_status="ALLOWED",
            http_headers={"strict-transport-security": "max-age=31536000"},
        )
        p2 = PageData(
            url="https://example.com/docs",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Complete Documentation Guide",
            meta_description="Detailed reference documentation for developers and operators.",
            canonical_url="https://example.com/docs",
            canonical_state=CanonicalState.SELF_REFERENCING,
            headings=[HeadingData(level=1, text="Documentation Outline")],
            word_count=600,
            has_viewport=True,
            robots_txt_status="ALLOWED",
            http_headers={"strict-transport-security": "max-age=31536000"},
        )
        p1.internal_links = [LinkData(href="https://example.com/docs", anchor_text="Documentation")]
        p2.internal_links = [LinkData(href="https://example.com/", anchor_text="Home")]

        crawl = CrawlResult(start_url="https://example.com/", domain="example.com", pages=[p1, p2], pages_discovered_count=2, crawl_coverage_pct=100.0)
        report = self.report_gen.generate_report(crawl, environment="production")

        self.assertEqual(report.audit_status, "PASS")
        self.assertEqual(report.overall_score, 100.0)
        self.assertEqual(len(report.all_deductions), 0)

    # Scenario 46: Robots.txt Disallow Interaction with Noindex (Requirement 1 & Regression)
    def test_scenario_46_robots_txt_disallow_stops_noindex_detection(self):
        page = PageData(
            url="https://example.com/disallowed-with-noindex",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            robots_txt_status="DISALLOWED",
            meta_robots="noindex, nofollow",
        )
        issues = self.detector._check_robots_and_snippets(page)
        issue_ids = [i.issue_id for i in issues]
        self.assertIn("ROBOTS_BLOCKS_NOINDEX_DETECTION", issue_ids)
        noindex_issue = next(i for i in issues if i.issue_id == "ROBOTS_BLOCKS_NOINDEX_DETECTION")
        self.assertIn("prevents search engines from crawling the page to read the", noindex_issue.inference)

    # Scenario 47: JavaScript Rendered vs Raw HTML Metadata (Requirement 2 & Regression)
    def test_scenario_47_javascript_rendered_vs_raw_html_metadata(self):
        page = PageData(
            url="https://example.com/spa-app",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            raw_title="",
            rendered_title="Client Rendered React Dashboard Title",
            title="Client Rendered React Dashboard Title",
            render_status="rendered_playwright",
            headings=[HeadingData(level=1, text="Dashboard")],
        )
        issues = self.detector._check_title(page, title_map={})
        issue_ids = [i.issue_id for i in issues]
        self.assertIn("TITLE_CLIENT_SIDE_RENDERED", issue_ids)
        self.assertNotIn("MISSING_TITLE_TAG", issue_ids)
        js_issue = next(i for i in issues if i.issue_id == "TITLE_CLIENT_SIDE_RENDERED")
        self.assertEqual(js_issue.finding_source, "both")

    # Scenario 48: Canonical Target End-to-End Validation (Requirement 3 & Regression)
    def test_scenario_48_canonical_target_end_to_end_validation(self):
        from godlike_seo.models import CanonicalState
        # Page A -> canonical to 404
        page_a = PageData(
            url="https://example.com/page-a",
            canonical_url="https://example.com/broken-target",
            canonical_state=CanonicalState.CROSS_URL,
            status_code=200,
            has_html=True,
        )
        # Page B -> canonical to 301 redirect
        page_b = PageData(
            url="https://example.com/page-b",
            canonical_url="https://example.com/redirect-target",
            canonical_state=CanonicalState.CROSS_URL,
            status_code=200,
            has_html=True,
        )
        # Page C -> canonical to noindexed page
        page_c = PageData(
            url="https://example.com/page-c",
            canonical_url="https://example.com/noindex-target",
            canonical_state=CanonicalState.CROSS_URL,
            status_code=200,
            has_html=True,
        )
        # Page D & E -> reciprocal canonical loop (D -> E and E -> D)
        page_d = PageData(
            url="https://example.com/loop-d",
            canonical_url="https://example.com/loop-e",
            canonical_state=CanonicalState.CROSS_URL,
            status_code=200,
            has_html=True,
        )
        page_e = PageData(
            url="https://example.com/loop-e",
            canonical_url="https://example.com/loop-d",
            canonical_state=CanonicalState.CROSS_URL,
            status_code=200,
            has_html=True,
        )
        # Targets
        target_404 = PageData(url="https://example.com/broken-target", status_code=404, has_html=False)
        target_301 = PageData(url="https://example.com/redirect-target", status_code=301, final_url="https://example.com/destination", has_html=False)
        target_noindex = PageData(url="https://example.com/noindex-target", status_code=200, meta_robots="noindex", has_html=True)

        pages_by_url = {
            "https://example.com/broken-target": target_404,
            "https://example.com/redirect-target": target_301,
            "https://example.com/noindex-target": target_noindex,
            "https://example.com/loop-d": page_d,
            "https://example.com/loop-e": page_e,
        }

        # Check A
        issues_a = self.detector._check_canonical(page_a, pages_by_url)
        self.assertIn("CANONICAL_POINTS_TO_4XX", [i.issue_id for i in issues_a])

        # Check B
        issues_b = self.detector._check_canonical(page_b, pages_by_url)
        self.assertIn("CANONICAL_POINTS_TO_REDIRECT", [i.issue_id for i in issues_b])

        # Check C
        issues_c = self.detector._check_canonical(page_c, pages_by_url)
        self.assertIn("CANONICAL_POINTS_TO_NOINDEX", [i.issue_id for i in issues_c])

        # Check D (Loop)
        issues_d = self.detector._check_canonical(page_d, pages_by_url)
        self.assertIn("CANONICAL_TARGET_LOOP", [i.issue_id for i in issues_d])

    # Scenario 49: Partial Crawl Inconclusive Ledger Checks (Requirement 4 & Regression)
    def test_scenario_49_partial_crawl_inconclusive_ledger_checks(self):
        from godlike_seo.models import CheckStatus
        pages = [
            PageData(
                url=f"https://example.com/page-{i}",
                status_code=200,
                has_html=True,
                page_type=PageType.PUBLIC_CONTENT,
                title=f"Sample Page {i}",
                headings=[HeadingData(level=1, text=f"Heading {i}")],
                meta_description="Sample description meeting normal length requirements for the page.",
                word_count=400,
                has_viewport=True,
            )
            for i in range(2)
        ]
        crawl = CrawlResult(
            start_url="https://example.com/",
            pages=pages,
            pages_discovered_count=50,
            crawl_coverage_pct=4.0,
        )
        report = self.report_gen.generate_report(crawl)
        self.assertEqual(report.audit_status, "INSUFFICIENT_COVERAGE")
        inconclusive_checks = [c for c in report.check_ledger if c.status == CheckStatus.INCONCLUSIVE]
        self.assertGreaterEqual(len(inconclusive_checks), 20)

    # Scenario 50: Temporary Server Error 503 Graceful Handling (Regression)
    def test_scenario_50_temporary_server_error_503_graceful_handling(self):
        page_503 = PageData(
            url="https://example.com/failing-endpoint",
            status_code=503,
            has_html=False,
            page_type=PageType.ERROR,
        )
        issues = self.detector._check_http_status(page_503)
        self.assertIn("HTTP_5XX_SERVER_ERROR", [i.issue_id for i in issues])

    # Scenario 51: Unknown Environment Strict Isolation (Requirement 4 & Regression)
    def test_scenario_51_unknown_environment_strict_isolation(self):
        # Host contains 'staging' substring, but environment is UNKNOWN and no headers exist
        pages = [
            PageData(
                url=f"https://staging.customer-app.com/page-{i}",
                status_code=200,
                has_html=True,
                page_type=PageType.PUBLIC_CONTENT,
                meta_robots="noindex",
                title=f"Page {i}",
                headings=[HeadingData(level=1, text=f"Heading {i}")],
            )
            for i in range(3)
        ]
        crawl = CrawlResult(
            start_url="https://staging.customer-app.com/",
            domain="staging.customer-app.com",
            pages=pages,
            pages_discovered_count=3,
            crawl_coverage_pct=100.0,
        )
        # With environment=None or "unknown"
        report = self.report_gen.generate_report(crawl, environment="unknown")
        # Must NOT infer staging from hostname alone; must alert with INDEXATION_WARNING
        self.assertEqual(report.audit_status, "INDEXATION_WARNING")
        self.assertEqual(report.environment_intent, "unknown")
        self.assertIn("ENVIRONMENT UNCONFIRMED", report.status_message)

    # Scenario 52: Schema Optional Property Zero Point Deduction (Requirement 9)
    def test_scenario_52_schema_optional_property_zero_penalty(self):
        from godlike_seo.analyzers.schema_validator import SchemaValidator
        from godlike_seo.models import StructuredDataItem
        page = PageData(
            url="https://example.com/product/valid-item",
            status_code=200,
            has_html=True,
            page_type=PageType.PUBLIC_CONTENT,
            title="Valid Product Item",
            meta_description="Valid product item description meeting standards.",
            headings=[HeadingData(level=1, text="Product Name")],
            structured_data=[
                StructuredDataItem(
                    format="json-ld",
                    type="Product",
                    data={
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "name": "Super Camera 4K",
                        "offers": {
                            "@type": "Offer",
                            "price": "99.00",
                            "priceCurrency": "USD",
                        },
                    },
                )
            ],
        )
        validator = SchemaValidator()
        issues = validator.validate_page(page)
        # Missing recommended brand, sku should be INFORMATIONAL, not causing score penalties
        self.assertTrue(all(i.severity == IssueSeverity.INFORMATIONAL for i in issues))


if __name__ == "__main__":
    unittest.main()
