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
    PageData,
    PageType,
    HeadingData,
    LinkData,
    ImageData,
    IssueSeverity,
    IssueCategory,
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

            # Check headers
            headers = [ws.cell(row=1, column=c).value for c in range(1, 18)]
            self.assertIn("Is Indexable", headers)
            self.assertIn("Indexability Reason", headers)
            self.assertIn("Internal Inlinks", headers)
            self.assertIn("Internal Outlinks", headers)
            self.assertIn("External Outlinks", headers)

            # Check rows
            row2_vals = [ws.cell(row=2, column=c).value for c in range(1, 18)]
            row3_vals = [ws.cell(row=3, column=c).value for c in range(1, 18)]

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


if __name__ == "__main__":
    unittest.main()
