"""
Professional Multi-Tab Excel Report Generator using openpyxl.

Creates structured .xlsx workbooks with:
- Tab 1: Executive Summary & Category Deductions
- Tab 2: Actionable Issue Clusters
- Tab 3: All Evaluated Pages & Metrics
- Tab 4: Orphaned Pages Audit
- Tab 5: Internal Link Graph & Anchor Text
- Tab 6: SERP Competitor Rankings & Page Metadata (when keyword analysis is requested)
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from godlike_seo.models import IssueSeverity, SEOReport


class ExcelReportGenerator:
    """Generates multi-sheet Excel audit workbooks."""

    def __init__(self):
        # Color palette
        self.header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        self.sub_header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        self.header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        self.title_font = Font(name="Calibri", size=14, bold=True, color="0F172A")
        self.bold_font = Font(name="Calibri", size=11, bold=True)
        self.regular_font = Font(name="Calibri", size=10)

        # Severity fills
        self.crit_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        self.high_fill = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")
        self.med_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
        self.low_fill = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
        self.info_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")

        thin = Side(border_style="thin", color="CBD5E1")
        self.border = Border(top=thin, left=thin, right=thin, bottom=thin)

    def _apply_table_styling(self, ws, start_row: int, max_cols: int):
        """Autofit columns and set alignments."""
        for col in range(1, max_cols + 1):
            col_letter = get_column_letter(col)
            max_len = 0
            for row in range(start_row, ws.max_row + 1):
                val = ws.cell(row=row, column=col).value
                if val:
                    max_len = max(max_len, len(str(val)))
            ws.column_dimensions[col_letter].width = min(50, max(max_len + 3, 12))

    def generate(self, report: SEOReport, filepath: str) -> None:
        """Build and save the Excel workbook."""
        wb = openpyxl.Workbook()
        ws_summary = wb.active
        ws_summary.title = "Summary & Health"

        stats = report.summary_stats or {}

        # ---------------------------------------------------------------
        # TAB 1: Summary & Health
        # ---------------------------------------------------------------
        ws_summary["A1"] = "⚡ GODLIKE SEO ENGINE 3.3.1 - AUDIT REPORT"
        ws_summary["A1"].font = self.title_font
        ws_summary["A2"] = f"Target: {report.url} | Domain: {report.domain} | Generated: {report.generated_at[:19]} UTC"
        ws_summary["A2"].font = Font(name="Calibri", size=10, italic=True, color="64748B")

        if report.audit_status == "PASS":
            status_color = "16A34A"
        elif report.audit_status == "STAGING_PROTECTED":
            status_color = "2563EB"
        elif report.audit_status in ("NEEDS_REVIEW", "INSUFFICIENT_COVERAGE", "INDEXATION_WARNING", "INCONCLUSIVE"):
            status_color = "D97706"
        else:
            status_color = "DC2626"

        ws_summary["A3"] = f"Release Status: {report.audit_status} | Environment: {report.environment_intent.upper()}"
        ws_summary["A3"].font = Font(name="Calibri", size=11, bold=True, color=status_color)
        ws_summary["A4"] = f"Verdict: {report.status_message}"
        ws_summary["A4"].font = Font(name="Calibri", size=10, italic=True, color="475569")

        # Key Metrics Block
        metrics = [
            ("Overall SEO Health Score", f"{report.overall_score:.0f}/100"),
            ("Audit Release Status", report.audit_status),
            ("Environment Intent", report.environment_intent.upper()),
            ("Pages Crawled", stats.get("total_pages_crawled", len(report.crawl_result.pages) if report.crawl_result else 0)),
            ("Crawl Coverage", f"{stats.get('crawl_coverage_pct', 100.0):.1f}%"),
            ("Unique Issue Clusters", stats.get("unique_issue_clusters", len(report.issue_clusters))),
            ("Raw Issue Occurrences", stats.get("total_raw_occurrences", len(report.raw_issues))),
            ("Critical Blockers", stats.get("critical_clusters_count", len(report.critical_clusters))),
            ("Orphaned Indexable Pages", stats.get("orphaned_pages_count", len(report.crawl_result.orphaned_pages) if report.crawl_result else 0)),
            ("Avg HTTP Latency / RTT", f"{stats.get('average_latency_rtt_ms') or stats.get('average_response_time_ms', 0):.0f} ms"),
        ]
        ws_summary["A5"] = "Core Performance Metric"
        ws_summary["B5"] = "Measured Value"
        ws_summary["A5"].font = self.header_font
        ws_summary["B5"].font = self.header_font
        ws_summary["A5"].fill = self.header_fill
        ws_summary["B5"].fill = self.header_fill

        for idx, (m_name, m_val) in enumerate(metrics, start=6):
            ws_summary.cell(row=idx, column=1, value=m_name).font = self.bold_font
            c = ws_summary.cell(row=idx, column=2, value=m_val)
            c.font = self.bold_font
            c.alignment = Alignment(horizontal="right")
            ws_summary.cell(row=idx, column=1).border = self.border
            c.border = self.border

        # Category Breakdown Table
        cat_start = len(metrics) + 8
        ws_summary.cell(row=cat_start, column=1, value="Category").fill = self.header_fill
        ws_summary.cell(row=cat_start, column=2, value="Score").fill = self.header_fill
        ws_summary.cell(row=cat_start, column=3, value="Weight").fill = self.header_fill
        ws_summary.cell(row=cat_start, column=4, value="Tests Passed").fill = self.header_fill
        ws_summary.cell(row=cat_start, column=5, value="Deductions Count").fill = self.header_fill
        for c in range(1, 6):
            ws_summary.cell(row=cat_start, column=c).font = self.header_font

        for idx, (k, cs) in enumerate(report.category_scores.items(), start=cat_start + 1):
            ws_summary.cell(row=idx, column=1, value=cs.name).font = self.bold_font
            ws_summary.cell(row=idx, column=2, value=f"{cs.score:.0f}/100").font = self.bold_font
            ws_summary.cell(row=idx, column=3, value=f"{int(cs.weight*100)}%")
            ws_summary.cell(row=idx, column=4, value=f"{cs.tests_passed}/{cs.tests_evaluated}")
            ws_summary.cell(row=idx, column=5, value=len(cs.deductions))
            for c in range(1, 6):
                ws_summary.cell(row=idx, column=c).border = self.border

        self._apply_table_styling(ws_summary, 5, 5)

        # ---------------------------------------------------------------
        # TAB 2: Issue Clusters
        # ---------------------------------------------------------------
        ws_issues = wb.create_sheet(title="Actionable Issue Clusters")
        headers_issues = [
            "Severity", "Category", "Issue ID", "Title",
            "Technical Observation", "SEO Inference & Risk",
            "Occurrences", "Affected URLs Count", "Impact Summary",
            "Recommended Developer Fix", "Verification Step", "Sample Evidence"
        ]
        for c_idx, h in enumerate(headers_issues, start=1):
            cell = ws_issues.cell(row=1, column=c_idx, value=h)
            cell.font = self.header_font
            cell.fill = self.header_fill

        for r_idx, cl in enumerate(report.issue_clusters, start=2):
            sev_str = cl.severity.value.upper()
            obs_str = getattr(cl, "observation", "") or cl.description
            inf_str = getattr(cl, "inference", "") or cl.impact
            ws_issues.cell(row=r_idx, column=1, value=sev_str).font = self.bold_font
            ws_issues.cell(row=r_idx, column=2, value=cl.category.value.title())
            ws_issues.cell(row=r_idx, column=3, value=cl.issue_id)
            ws_issues.cell(row=r_idx, column=4, value=cl.title).font = self.bold_font
            ws_issues.cell(row=r_idx, column=5, value=obs_str)
            ws_issues.cell(row=r_idx, column=6, value=inf_str)
            ws_issues.cell(row=r_idx, column=7, value=cl.occurrences_count)
            ws_issues.cell(row=r_idx, column=8, value=len(cl.affected_urls))
            ws_issues.cell(row=r_idx, column=9, value=cl.impact)
            ws_issues.cell(row=r_idx, column=10, value=cl.recommendation).font = Font(name="Calibri", size=10, color="0369A1")
            ws_issues.cell(row=r_idx, column=11, value=cl.verification_step)

            if cl.sample_evidence:
                ev_items = []
                for item in cl.sample_evidence[:3]:
                    line = f"{item.get('url')}: {item.get('evidence')}"
                    sources = item.get("source_pages", [])
                    if sources:
                        line += f" (Sources: {', '.join(sources[:2])})"
                    ev_items.append(line)
                sample_ev = " | ".join(ev_items)
            else:
                sample_ev = ""
            ws_issues.cell(row=r_idx, column=12, value=sample_ev)

            # Color severity column
            if cl.severity == IssueSeverity.CRITICAL:
                ws_issues.cell(row=r_idx, column=1).fill = self.crit_fill
            elif cl.severity == IssueSeverity.HIGH:
                ws_issues.cell(row=r_idx, column=1).fill = self.high_fill
            elif cl.severity == IssueSeverity.MEDIUM:
                ws_issues.cell(row=r_idx, column=1).fill = self.med_fill
            elif cl.severity == IssueSeverity.LOW:
                ws_issues.cell(row=r_idx, column=1).fill = self.low_fill
            else:
                ws_issues.cell(row=r_idx, column=1).fill = self.info_fill

            for c in range(1, 13):
                ws_issues.cell(row=r_idx, column=c).border = self.border

        self._apply_table_styling(ws_issues, 1, 12)

        # ---------------------------------------------------------------
        # TAB 3: All Evaluated Pages
        # ---------------------------------------------------------------
        ws_pages = wb.create_sheet(title="All Evaluated Pages")
        headers_pages = [
            "Requested URL", "Final Resolved URL", "Redirect Chain", "Status", "Technical Classification", "Content Type",
            "Is Indexable", "Indexability Reason", "Canonical State", "Canonical URL", "Internal Inlinks", "Internal Outlinks",
            "External Outlinks", "HTTP Latency / RTT (ms)", "Word Count", "H1 Count", "Title", "Meta Description", "Has Viewport",
            "Images Count", "Structured Data Count", "OG URL"
        ]
        for c_idx, h in enumerate(headers_pages, start=1):
            cell = ws_pages.cell(row=1, column=c_idx, value=h)
            cell.font = self.header_font
            cell.fill = self.header_fill

        if report.crawl_result:
            for r_idx, page in enumerate(report.crawl_result.pages, start=2):
                pt = getattr(page, "page_type", None)
                pt_val = pt.value if hasattr(pt, "value") else str(pt or "public_content")
                in_inlinks = getattr(page, "internal_inlinks_count", getattr(page, "inlinks_count", 0))
                in_outlinks = getattr(page, "internal_outlinks_count", len(page.internal_links))
                ex_outlinks = getattr(page, "external_outlinks_count", len(page.external_links))
                canon_state = getattr(page, "canonical_state", None)
                canon_state_val = canon_state.value if hasattr(canon_state, "value") else str(canon_state or "missing")
                schema_cnt = len(getattr(page, "structured_data", []))
                og_url_val = (page.open_graph.og_url if page.open_graph else "") or (page.og_tags.get("og:url", "") if page.og_tags else "")
                chain_parts = []
                for hop in (page.redirect_chain or []):
                    if hasattr(hop, "url"):
                        chain_parts.append(f"{hop.url} ({hop.status_code})")
                    elif isinstance(hop, dict) and "url" in hop:
                        chain_parts.append(f"{hop['url']} ({hop.get('status_code', 301)})")
                    else:
                        chain_parts.append(str(hop))
                chain_str = " -> ".join(chain_parts) if chain_parts else "Direct (200)"

                ws_pages.cell(row=r_idx, column=1, value=page.url)
                ws_pages.cell(row=r_idx, column=2, value=page.final_url or page.url)
                ws_pages.cell(row=r_idx, column=3, value=chain_str)
                ws_pages.cell(row=r_idx, column=4, value=page.status_code)
                ws_pages.cell(row=r_idx, column=5, value=pt_val.replace('_', ' ').upper())
                ws_pages.cell(row=r_idx, column=6, value=page.content_type)
                ws_pages.cell(row=r_idx, column=7, value="Yes" if page.is_indexable else "No")
                ws_pages.cell(row=r_idx, column=8, value=page.indexability_reason or ("Indexable" if page.is_indexable else "Non-indexable"))
                ws_pages.cell(row=r_idx, column=9, value=canon_state_val)
                ws_pages.cell(row=r_idx, column=10, value=page.canonical_url or "")
                ws_pages.cell(row=r_idx, column=11, value=in_inlinks)
                ws_pages.cell(row=r_idx, column=12, value=in_outlinks)
                ws_pages.cell(row=r_idx, column=13, value=ex_outlinks)
                ws_pages.cell(row=r_idx, column=14, value=round(page.response_time_ms, 1))
                ws_pages.cell(row=r_idx, column=15, value=page.word_count)
                ws_pages.cell(row=r_idx, column=16, value=len(page.h1_tags))
                ws_pages.cell(row=r_idx, column=17, value=page.title)
                ws_pages.cell(row=r_idx, column=18, value=page.meta_description)
                ws_pages.cell(row=r_idx, column=19, value="Yes" if page.has_viewport else "No")
                ws_pages.cell(row=r_idx, column=20, value=len(page.images))
                ws_pages.cell(row=r_idx, column=21, value=schema_cnt)
                ws_pages.cell(row=r_idx, column=22, value=og_url_val)

                for c in range(1, 23):
                    ws_pages.cell(row=r_idx, column=c).border = self.border

        self._apply_table_styling(ws_pages, 1, 22)

        # ---------------------------------------------------------------
        # TAB 4: Orphaned Pages
        # ---------------------------------------------------------------
        ws_orphans = wb.create_sheet(title="Orphaned Pages")
        ws_orphans.cell(row=1, column=1, value="Orphaned URL").font = self.header_font
        ws_orphans.cell(row=1, column=2, value="Internal Inlinks").font = self.header_font
        ws_orphans.cell(row=1, column=3, value="Context & Architectural Fix").font = self.header_font
        ws_orphans.cell(row=1, column=1).fill = self.header_fill
        ws_orphans.cell(row=1, column=2).fill = self.header_fill
        ws_orphans.cell(row=1, column=3).fill = self.header_fill

        orphans = report.crawl_result.orphaned_pages if report.crawl_result else []
        for r_idx, orp in enumerate(orphans, start=2):
            ws_orphans.cell(row=r_idx, column=1, value=orp)
            ws_orphans.cell(row=r_idx, column=2, value=0)
            ws_orphans.cell(row=r_idx, column=3, value="Indexable page in sitemap isolated from navigation. Link from category or main content hubs.")
            for c in range(1, 4):
                ws_orphans.cell(row=r_idx, column=c).border = self.border

        self._apply_table_styling(ws_orphans, 1, 3)

        # ---------------------------------------------------------------
        # TAB 5: Internal Link Graph
        # ---------------------------------------------------------------
        ws_links = wb.create_sheet(title="Internal Link Graph")
        headers_links = ["Source (Requested URL)", "Source (Final Resolved URL)", "Target URL", "Anchor Text", "Link Location"]
        for c_idx, h in enumerate(headers_links, start=1):
            cell = ws_links.cell(row=1, column=c_idx, value=h)
            cell.font = self.header_font
            cell.fill = self.header_fill

        row_counter = 2
        if report.crawl_result and report.crawl_result.pages:
            seen_edges = set()
            for p in report.crawl_result.pages:
                req_src = p.url
                res_src = p.final_url or p.url
                for link in p.internal_links:
                    tgt = (link.href or link.url or "").strip()
                    if not tgt:
                        continue
                    anchor = (link.anchor_text or link.anchor or "").strip()
                    loc = getattr(link, "location", "body")
                    edge_key = (req_src, res_src, tgt, anchor, loc)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        ws_links.cell(row=row_counter, column=1, value=req_src)
                        ws_links.cell(row=row_counter, column=2, value=res_src)
                        ws_links.cell(row=row_counter, column=3, value=tgt)
                        ws_links.cell(row=row_counter, column=4, value=anchor)
                        ws_links.cell(row=row_counter, column=5, value=loc)
                        for c in range(1, 6):
                            ws_links.cell(row=row_counter, column=c).border = self.border
                        row_counter += 1

        self._apply_table_styling(ws_links, 1, 5)

        # ---------------------------------------------------------------
        # TAB 6: Search Results & Competitor Page Metadata
        # ---------------------------------------------------------------
        competitor_analyses = report.competitor_analyses or (
            [report.competitor_analysis] if report.competitor_analysis else []
        )
        if competitor_analyses:
            ws_serp = wb.create_sheet(title="SERP Competitors")
            ws_serp["A1"] = "SERP Results & Competitor Page Metadata"
            ws_serp["A1"].font = self.title_font
            ws_serp["A2"] = (
                "Positions are the captured order from the named search provider for the requested market/language. "
                "They are a point-in-time snapshot, not a stable or personalized Google ranking guarantee. "
                "Blank metadata means the page fetch did not return that field; check Fetch Status."
            )
            ws_serp["A2"].alignment = Alignment(wrap_text=True, vertical="top")
            ws_serp.merge_cells("A2:S2")
            headers_serp = [
                "Keyword", "Search Provider", "Country Target", "Language", "Captured At (UTC)",
                "Observed Position", "Target / Competitor", "Domain", "Ranking URL",
                "SERP Result Title", "Fetched <title>", "Meta Description", "H1", "SERP Snippet",
                "Fetch Status", "HTTP Status", "Word Count", "Heading Count", "Structured Data",
            ]
            for c_idx, header in enumerate(headers_serp, start=1):
                cell = ws_serp.cell(row=4, column=c_idx, value=header)
                cell.font = self.header_font
                cell.fill = self.header_fill

            row_idx = 5
            for analysis in competitor_analyses:
                metrics_by_url = {
                    (metric.url or "").rstrip("/").casefold(): metric
                    for metric in analysis.competitors
                }
                target_metrics = analysis.your_metrics
                if target_metrics and target_metrics.url:
                    metrics_by_url[target_metrics.url.rstrip("/").casefold()] = target_metrics

                observed_target = False
                results = getattr(analysis, "serp_results", []) or []
                for result in results:
                    key = (result.url or "").rstrip("/").casefold()
                    metric = metrics_by_url.get(key)
                    result_host = urlparse(result.url).netloc.lower().removeprefix("www.")
                    is_target = result_host == urlparse(analysis.your_url).netloc.lower().removeprefix("www.")
                    observed_target = observed_target or is_target
                    values = [
                        analysis.keyword,
                        analysis.search_engine,
                        analysis.search_country,
                        analysis.search_language,
                        analysis.serp_retrieved_at or analysis.analysed_at,
                        result.position,
                        "Target site" if is_target else "Competitor",
                        result.domain or result_host,
                        result.url,
                        result.title,
                        metric.title if metric else "",
                        metric.meta_description if metric else "",
                        metric.h1 if metric else "",
                        result.snippet,
                        metric.fetch_status if metric else "not fetched",
                        metric.http_status_code if metric else None,
                        metric.word_count if metric else None,
                        metric.heading_count if metric else None,
                        "Yes" if metric and metric.has_structured_data else ("No" if metric and metric.fetch_status == "fetched" else ""),
                    ]
                    for c_idx, value in enumerate(values, start=1):
                        cell = ws_serp.cell(row=row_idx, column=c_idx, value=value)
                        cell.border = self.border
                        cell.alignment = Alignment(vertical="top", wrap_text=True)
                    row_idx += 1

                if target_metrics and not observed_target:
                    values = [
                        analysis.keyword,
                        analysis.search_engine,
                        analysis.search_country,
                        analysis.search_language,
                        analysis.serp_retrieved_at or analysis.analysed_at,
                        "Not in captured results",
                        "Target site",
                        target_metrics.domain,
                        target_metrics.url or analysis.your_url,
                        "",
                        target_metrics.title,
                        target_metrics.meta_description,
                        target_metrics.h1,
                        "",
                        target_metrics.fetch_status,
                        target_metrics.http_status_code,
                        target_metrics.word_count,
                        target_metrics.heading_count,
                        "Yes" if target_metrics.has_structured_data else ("No" if target_metrics.fetch_status == "fetched" else ""),
                    ]
                    for c_idx, value in enumerate(values, start=1):
                        cell = ws_serp.cell(row=row_idx, column=c_idx, value=value)
                        cell.border = self.border
                        cell.alignment = Alignment(vertical="top", wrap_text=True)
                    row_idx += 1

            for col_idx, width in enumerate([30, 18, 14, 12, 24, 18, 18, 28, 52, 48, 48, 55, 40, 55, 18, 14, 14, 16, 18], start=1):
                ws_serp.column_dimensions[get_column_letter(col_idx)].width = width
            ws_serp.freeze_panes = "A5"
            ws_serp.auto_filter.ref = f"A4:S{max(4, row_idx - 1)}"
            ws_serp.row_dimensions[2].height = 34

        # ---------------------------------------------------------------
        # TAB 7: AI Agent Remediation Tasks
        # ---------------------------------------------------------------
        plan = getattr(report, "remediation_plan", None)
        if plan and getattr(plan, "tasks", None):
            ws_tasks = wb.create_sheet(title="Agent Remediation Tasks")
            headers_tasks = [
                "Task ID", "Priority", "Title", "Target Component", "Affected Pages",
                "Sample URL", "Problem Statement", "Code Patch Solution", "Playwright Verification Test", "Git Commit Proposal"
            ]
            for c_idx, h in enumerate(headers_tasks, start=1):
                cell = ws_tasks.cell(row=1, column=c_idx, value=h)
                cell.font = self.header_font
                cell.fill = self.header_fill

            for r_idx, task in enumerate(plan.tasks, start=2):
                ws_tasks.cell(row=r_idx, column=1, value=task.task_id)
                ws_tasks.cell(row=r_idx, column=2, value=task.priority)
                ws_tasks.cell(row=r_idx, column=3, value=task.title)
                ws_tasks.cell(row=r_idx, column=4, value=task.target_component)
                ws_tasks.cell(row=r_idx, column=5, value=task.affected_urls_count)
                ws_tasks.cell(row=r_idx, column=6, value=task.sample_url)
                ws_tasks.cell(row=r_idx, column=7, value=task.problem_statement)
                ws_tasks.cell(row=r_idx, column=8, value=task.code_diff_solution)
                ws_tasks.cell(row=r_idx, column=9, value=task.playwright_test_code)
                ws_tasks.cell(row=r_idx, column=10, value=task.git_commit_proposal)

                # Color priority
                if task.priority == "P0":
                    ws_tasks.cell(row=r_idx, column=2).fill = self.crit_fill
                elif task.priority == "P1":
                    ws_tasks.cell(row=r_idx, column=2).fill = self.high_fill
                elif task.priority == "P2":
                    ws_tasks.cell(row=r_idx, column=2).fill = self.med_fill
                else:
                    ws_tasks.cell(row=r_idx, column=2).fill = self.low_fill

                for c in range(1, 11):
                    ws_tasks.cell(row=r_idx, column=c).border = self.border

            self._apply_table_styling(ws_tasks, 1, 10)

        # ---------------------------------------------------------------
        # TAB 8: Deterministic Check Execution Ledger
        # ---------------------------------------------------------------
        ledger = getattr(report, "check_ledger", [])
        if ledger:
            ws_ledger = wb.create_sheet(title="Check Ledger")
            headers_ledger = ["Rule ID", "Category", "Rule Title", "Status", "Affected Count", "Execution Evidence & Scope"]
            for c_idx, h in enumerate(headers_ledger, start=1):
                cell = ws_ledger.cell(row=1, column=c_idx, value=h)
                cell.font = self.header_font
                cell.fill = self.header_fill

            for r_idx, cr in enumerate(ledger, start=2):
                st = cr.status.value.upper() if hasattr(cr.status, "value") else str(cr.status).upper()
                cat_str = cr.category.value.replace("_", " ").title() if hasattr(cr.category, "value") else str(cr.category).title()

                ws_ledger.cell(row=r_idx, column=1, value=cr.rule_id).font = self.bold_font
                ws_ledger.cell(row=r_idx, column=2, value=cat_str)
                ws_ledger.cell(row=r_idx, column=3, value=cr.title)
                status_cell = ws_ledger.cell(row=r_idx, column=4, value=st)
                status_cell.font = self.bold_font
                ws_ledger.cell(row=r_idx, column=5, value=cr.affected_count)
                ws_ledger.cell(row=r_idx, column=6, value=cr.evidence)

                if st == "PASS":
                    status_cell.fill = self.low_fill
                elif st == "FAIL":
                    status_cell.fill = self.crit_fill
                elif st == "SKIPPED":
                    status_cell.fill = self.med_fill
                elif st == "NOT_APPLICABLE":
                    status_cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

                for c in range(1, 7):
                    ws_ledger.cell(row=r_idx, column=c).border = self.border

            self._apply_table_styling(ws_ledger, 1, 6)

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        try:
            wb.save(filepath)
        except PermissionError:
            import time
            alt_path = Path(filepath).with_name(f"{Path(filepath).stem}_{int(time.time())}.xlsx")
            wb.save(alt_path)
