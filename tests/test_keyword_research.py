"""Keyword research and SERP workbook integration tests."""

import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook as OpenpyxlWorkbook
from openpyxl import load_workbook

from godlike_seo.models import (
    CompetitorMetrics,
    SERPAnalysis,
    SERPResult,
    SEOReport,
)
from godlike_seo.reports.excel_report import ExcelReportGenerator
from godlike_seo.serp.competitor_analyzer import CompetitorAnalyzer
from godlike_seo.serp.keyword_analyzer import KeywordAnalyzer, SearchIntent
from godlike_seo.cli import _load_keyword_file


class FakeScraper:
    def scrape(self, keyword, num_results=None):
        return SERPAnalysis(
            keyword=keyword,
            search_engine="google",
            search_language="en",
            search_country="in",
            results=[
                SERPResult(
                    position=1,
                    url="https://example.com.attacker.test/page",
                    title="Unrelated domain result",
                    snippet="Wrongly similar domain.",
                    domain="example.com.attacker.test",
                ),
                SERPResult(
                    position=2,
                    url="https://example.com",
                    title="Target result title",
                    snippet="Target result snippet.",
                    domain="example.com",
                ),
            ],
        )


class KeywordResearchTests(unittest.TestCase):
    def test_rental_phrasing_is_transactional(self):
        analyzer = KeywordAnalyzer()
        expected = {
            "camera rental Bengaluru": SearchIntent.LOCAL,
            "DSLR camera on rent India": SearchIntent.LOCAL,
            "renting power tools": SearchIntent.TRANSACTIONAL,
            "tent rentals near me": SearchIntent.LOCAL,
        }
        for phrase, intent in expected.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(analyzer.classify_intent(phrase)[0], intent)

    def test_competitor_analysis_preserves_market_and_matches_exact_host(self):
        analyzer = CompetitorAnalyzer(scraper=FakeScraper())
        metrics = {
            "https://example.com.attacker.test/page": CompetitorMetrics(
                domain="example.com.attacker.test", url="https://example.com.attacker.test/page",
                position=1, fetch_status="fetched", title="Attacker title", h1="Attacker H1",
            ),
            "https://www.example.com/": CompetitorMetrics(
                domain="example.com", url="https://www.example.com/",
                position=2, fetch_status="fetched", title="Camera rental", h1="Cameras for rent",
            ),
            "https://example.com": CompetitorMetrics(
                domain="example.com", url="https://example.com",
                fetch_status="fetched", title="Home page", h1="Home",
            ),
        }
        with patch.object(analyzer, "_scrape_page_metrics", side_effect=lambda url, query: metrics[url]):
            analysis = analyzer.analyze_for_keyword("camera rental", "https://example.com", max_competitors=5)

        self.assertEqual(analysis.your_position, 2)
        self.assertEqual(analysis.position_label, "#2")
        self.assertEqual(analysis.search_country, "in")
        self.assertEqual(analysis.search_language, "en")
        self.assertEqual(analysis.search_engine, "google")
        self.assertEqual(len(analysis.competitors), 1)
        self.assertEqual(analysis.competitors[0].domain, "example.com.attacker.test")
        self.assertEqual(analysis.your_metrics.h1, "Home")

    def test_excel_export_includes_ranks_and_competitor_tags(self):
        analyzer = CompetitorAnalyzer(scraper=FakeScraper())
        metrics = {
            "https://example.com.attacker.test/page": CompetitorMetrics(
                domain="example.com.attacker.test", url="https://example.com.attacker.test/page",
                position=1, fetch_status="fetched", http_status_code=200,
                title="Attacker title", meta_description="Competitor description", h1="Attacker H1",
                word_count=80, heading_count=3,
            ),
            "https://www.example.com/": CompetitorMetrics(
                domain="example.com", url="https://www.example.com/",
                position=2, fetch_status="fetched", http_status_code=200,
                title="Camera rental", meta_description="Target description", h1="Cameras for rent",
                word_count=120, heading_count=5,
            ),
            "https://example.com": CompetitorMetrics(
                domain="example.com", url="https://example.com",
                fetch_status="fetched", http_status_code=200, title="Home page", h1="Home",
            ),
        }
        with patch.object(analyzer, "_scrape_page_metrics", side_effect=lambda url, query: metrics[url]):
            analysis = analyzer.analyze_for_keyword("camera rental", "https://example.com", max_competitors=5)

        report = SEOReport(
            url="https://example.com",
            domain="example.com",
            competitor_analyses=[analysis],
            competitor_analysis=analysis,
        )
        filepath = Path(__file__).parents[1] / "reports" / "_test_keyword_report.xlsx"
        try:
            ExcelReportGenerator().generate(report, filepath)
            workbook = load_workbook(filepath, read_only=True, data_only=True)
            self.assertIn("SERP Competitors", workbook.sheetnames)
            sheet = workbook["SERP Competitors"]
            headers = [cell.value for cell in sheet[4]]
            header_col = {name: idx + 1 for idx, name in enumerate(headers)}
            rows = list(sheet.iter_rows(min_row=5, values_only=True))
            self.assertEqual(rows[0][header_col["Observed Position"] - 1], 1)
            self.assertEqual(rows[0][header_col["Fetched <title>"] - 1], "Attacker title")
            self.assertEqual(rows[0][header_col["Meta Description"] - 1], "Competitor description")
            self.assertEqual(rows[0][header_col["H1"] - 1], "Attacker H1")
            self.assertEqual(rows[1][header_col["Target / Competitor"] - 1], "Target site")
            self.assertEqual(rows[1][header_col["Observed Position"] - 1], 2)
            workbook.close()
        finally:
            filepath.unlink(missing_ok=True)

    def test_keyword_file_reads_keyword_plan_header(self):
        filepath = Path(__file__).parents[1] / "reports" / "_test_keyword_plan.xlsx"
        try:
            workbook = OpenpyxlWorkbook()
            sheet = workbook.active
            sheet.title = "Keyword Plan"
            sheet["A1"] = "Research plan"
            sheet["C4"] = "Target keyword / query"
            sheet["C5"] = "camera rental Bengaluru"
            sheet["C6"] = "DSLR camera on rent India"
            workbook.save(filepath)
            workbook.close()

            self.assertEqual(
                _load_keyword_file(str(filepath)),
                ["camera rental Bengaluru", "DSLR camera on rent India"],
            )
        finally:
            filepath.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
