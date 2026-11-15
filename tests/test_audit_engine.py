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
        self.assertEqual(rel_canon[0].severity, IssueSeverity.HIGH)

    # Scenario 7: Sitewide X-Robots-Tag noindex triggers CRITICAL issue
    def test_scenario_7_sitewide_noindex_critical(self):
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

    # Scenario 10: Image missing width/height attributes (CLS Risk)
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
        self.assertEqual(dim_issues[0].severity, IssueSeverity.LOW)
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


if __name__ == "__main__":
    unittest.main()
