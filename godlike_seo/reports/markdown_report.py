"""
Agentic AI & Developer Markdown Report Generator.

Generates structured, token-efficient GitHub-Flavored Markdown reports
tailored for AI agent reasoning, developer task management, and CI/CD pipelines.
"""

from __future__ import annotations

from typing import List
from godlike_seo.models import IssueSeverity, SEOReport


class MarkdownReportGenerator:
    """Renders evidence-backed, token-efficient Markdown reports."""

    def render(self, report: SEOReport) -> str:
        stats = report.summary_stats or {}
        pages_crawled = stats.get("total_pages_crawled", len(report.crawl_result.pages) if report.crawl_result else 0)
        orphans_count = stats.get("orphaned_pages_count", len(report.crawl_result.orphaned_pages) if report.crawl_result else 0)
        clusters_count = stats.get("unique_issue_clusters", len(report.issue_clusters))
        raw_occurrences = stats.get("total_raw_occurrences", len(report.raw_issues))
        critical_count = stats.get("critical_clusters_count", len(report.critical_clusters))
        avg_ttfb = stats.get("average_response_time_ms", 0)

        lines: List[str] = []

        # 1. Header
        lines.append(f"# ⚡ SEO & Technical Audit Report: `{report.domain}`")
        lines.append(f"**Target URL:** `{report.url}` | **Evaluated At:** `{report.generated_at[:19]} UTC`\n")

        # 2. Executive Metrics
        lines.append("## 📊 Executive Overview")
        lines.append(f"- **Overall Health Score:** `{report.overall_score:.0f}/100`")
        lines.append(f"- **Evaluated Pages:** `{pages_crawled}`")
        lines.append(f"- **Unique Issue Clusters:** `{clusters_count}` ({raw_occurrences} total raw occurrences)")
        lines.append(f"- **Critical Blockers:** `{critical_count}`")
        lines.append(f"- **Orphaned Indexable Pages:** `{orphans_count}`")
        lines.append(f"- **Avg Server Response Time (TTFB):** `{avg_ttfb:.0f} ms`\n")

        # 3. Category Breakdown & Transparent Deductions
        lines.append("## 📐 Category Breakdown & Scoring Methodology")
        lines.append("| Category | Score | Weight | Tests Passed | Deductions |")
        lines.append("| :--- | :---: | :---: | :---: | :---: |")

        for key, cs in report.category_scores.items():
            lines.append(f"| **{cs.name}** | `{cs.score:.0f}/100` | {int(cs.weight*100)}% | {cs.tests_passed}/{cs.tests_evaluated} | {len(cs.deductions)} |")

        lines.append("")
        if report.all_deductions:
            lines.append("### Itemized Point Deductions")
            for d in report.all_deductions:
                lines.append(f"- **[-{d.points_deducted:.0f} pts]** `{d.rule_title}`: {d.reason} *(Affects {d.affected_count} page(s))*")
            lines.append("")

        # 4. Action Plan for Developers
        lines.append("## 🚀 Prioritized Developer Action Plan")
        for i, rec in enumerate(report.recommendations[:10], start=1):
            lines.append(f"{i}. {rec}")
        lines.append("")

        # 5. Evidence-Backed Findings (Issue Clusters)
        lines.append(f"## 🔬 Evidence-Based Technical Findings ({len(report.issue_clusters)} Clusters)\n")

        for cluster in report.issue_clusters:
            sev_tag = cluster.severity.value.upper()
            cat_tag = cluster.category.value.replace("_", " ").title()
            urls_preview = ", ".join(f"`{u}`" for u in cluster.affected_urls[:3])
            if len(cluster.affected_urls) > 3:
                urls_preview += f" *(and {len(cluster.affected_urls) - 3} more)*"

            evidence_snippet = ""
            if cluster.sample_evidence:
                evidence_lines = []
                for item in cluster.sample_evidence[:3]:
                    url_str = item.get("url", "")
                    ev_str = item.get("evidence", "")
                    sources = item.get("source_pages", [])
                    anchor = item.get("anchor_text", "")
                    if len(cluster.sample_evidence) > 1:
                        line = f"- {url_str} => {ev_str}"
                    else:
                        line = ev_str
                    if sources:
                        line += f"\n  (Sources: {', '.join(sources[:2])})"
                    if anchor:
                        line += f"\n  (Anchor: '{anchor}')"
                    evidence_lines.append(line)
                evidence_snippet = "\n".join(evidence_lines)

            obs_text = getattr(cluster, "observation", "") or cluster.description
            inf_text = getattr(cluster, "inference", "") or cluster.impact

            lines.append(f"### [{sev_tag}] {cluster.title}")
            lines.append(f"- **Category:** `{cat_tag}` | **Confidence:** `{cluster.confidence.value.upper()}`")
            lines.append(f"- **Occurrences:** `{cluster.occurrences_count}` instance(s) across {len(cluster.affected_urls)} page(s)")
            lines.append(f"- **Technical Observation:** {obs_text}")
            lines.append(f"- **SEO Inference & Risk:** {inf_text}")
            lines.append(f"- **Affected URLs:** {urls_preview}")
            lines.append(f"- **Impact:** {cluster.impact}")
            if evidence_snippet:
                lines.append(f"- **Evidence Inspected:**\n  ```html\n  {evidence_snippet}\n  ```")
            lines.append(f"- **Recommended Fix:** {cluster.recommendation}")
            lines.append(f"- **Verification Step:** {cluster.verification_step}\n")

        # 6. Orphaned Pages
        orphaned_list = report.crawl_result.orphaned_pages if report.crawl_result else []
        lines.append("## 🔍 Contextual Orphaned Page Audit")
        if orphaned_list:
            lines.append("| Orphaned URL | Inlinks | Architectural Assessment |")
            lines.append("| :--- | :---: | :--- |")
            for orp in orphaned_list:
                lines.append(f"| `{orp}` | 0 | Found in sitemap but isolated from internal navigation. Link from category or content hubs. |")
        else:
            lines.append("✓ **No orphaned pages detected.** All indexable pages are linked in site navigation.\n")
        lines.append("")

        # 7. Page Inventory & Classification
        crawled_pages = report.crawl_result.pages if report.crawl_result else []
        if crawled_pages:
            lines.append("## 📑 Evaluated Page Inventory & Intent Classification")
            lines.append("| URL | Status | Technical Intent | Indexable? | Inlinks | Outlinks | Words | Title |")
            lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
            for p in crawled_pages:
                pt = getattr(p, "page_type", None)
                pt_val = pt.value if hasattr(pt, "value") else str(pt or "public_content")
                in_inlinks = getattr(p, "internal_inlinks_count", getattr(p, "inlinks_count", 0))
                in_outlinks = getattr(p, "internal_outlinks_count", len(p.internal_links))
                idx_str = "Yes" if p.is_indexable else f"No ({getattr(p, 'indexability_reason', '')[:20]}...)" if getattr(p, 'indexability_reason', '') else "No"
                title_clean = (p.title or "None").replace("|", "-")[:45]
                lines.append(f"| `{p.url}` | `{p.status_code}` | `{pt_val}` | {idx_str} | {in_inlinks} | {in_outlinks} | {p.word_count} | {title_clean} |")
            lines.append("")

        # 7. SERP & Competitor Intelligence (if present)
        all_comps = report.competitor_analyses or ([report.competitor_analysis] if report.competitor_analysis else [])
        if all_comps:
            lines.append("## 🏆 SERP Intelligence & Competitor Reverse-Engineering")
            for comp in all_comps:
                lines.append(f"### Benchmark Query: \"{comp.keyword}\"")
                lines.append(f"- **Your Position:** `#{comp.your_position or 'Unranked (>20)'}`")
                lines.append(f"- **Competitive Parity Score:** `{comp.competitive_gap_score}/100`")
                lines.append("\n| Rank | Domain | Word Count | H1 Heading | Schema | Speed (TTFB) |")
                lines.append("| :---: | :--- | :---: | :--- | :---: | :---: |")
                lines.append(f"| **YOU (#{comp.your_position or 'N/A'})** | `{comp.your_url}` | {stats.get('average_word_count', 0)} | Target Page | {'Yes' if stats.get('has_schema') else 'No'} | {avg_ttfb:.0f}ms |")
                for c in comp.competitors:
                    h1_clean = c.h1[:35] + ("..." if len(c.h1) > 35 else "") if c.h1 else "None"
                    lines.append(f"| #{c.position} | `{c.domain}` | {c.word_count} | {h1_clean} | {'Yes' if c.has_structured_data else 'No'} | {c.response_time_ms:.0f}ms |")

                if comp.gaps:
                    lines.append("\n**Competitive Ranking Gaps to Close:**")
                    for g in comp.gaps:
                        lines.append(f"- {g}")
            lines.append("")

        return "\n".join(lines)
