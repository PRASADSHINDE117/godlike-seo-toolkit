"""
Evidence-Backed Developer SEO Audit Report Generator 2.0.

Produces a standalone, evidence-rich HTML audit dashboard with:
- Transparent mathematical scoring & deduction breakdowns
- Issue clustering (unique problems vs affected URLs vs raw occurrences)
- Full evidence cards with DOM code snippets, impact, confidence, fix, and verification steps
- Accurate server response time / TTFB profiling
- Contextual orphaned page analysis
- Side-by-side competitive SERP benchmarks
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

from godlike_seo.models import IssueSeverity, SEOReport


class HTMLReportGenerator:
    """Generates a professional, evidence-backed developer SEO audit report."""

    @staticmethod
    def _get_score_color(score: float) -> str:
        if score >= 85:
            return "#10B981"  # Emerald Green
        elif score >= 65:
            return "#F59E0B"  # Amber
        else:
            return "#EF4444"  # Red

    @staticmethod
    def _get_severity_badge(severity: IssueSeverity) -> str:
        s = severity.value.lower()
        if s == "critical":
            return '<span class="badge badge-critical">CRITICAL</span>'
        elif s == "high":
            return '<span class="badge badge-high">HIGH</span>'
        elif s == "medium":
            return '<span class="badge badge-medium">MEDIUM</span>'
        elif s == "low":
            return '<span class="badge badge-low">LOW</span>'
        else:
            return '<span class="badge badge-info">OPPORTUNITY</span>'

    def render(self, report: SEOReport) -> str:
        score = report.overall_score
        score_color = self._get_score_color(score)

        radius = 70
        circumference = 2 * 3.14159 * radius
        dashoffset = circumference - (circumference * score / 100.0)

        stats = report.summary_stats or {}
        pages_count = stats.get("total_pages_crawled", len(report.crawl_result.pages) if report.crawl_result else 0)
        orphans_count = stats.get("orphaned_pages_count", len(report.crawl_result.orphaned_pages) if report.crawl_result else 0)
        unique_clusters = stats.get("unique_issue_clusters", len(report.issue_clusters))
        raw_occurrences = stats.get("total_raw_occurrences", len(report.raw_issues))
        critical_clusters = stats.get("critical_clusters_count", 0)
        avg_latency = stats.get("average_latency_rtt_ms") or stats.get("average_response_time_ms", 0)
        coverage_pct = stats.get("crawl_coverage_pct", 100.0)

        crawl_config = report.crawl_result
        crawl_time = crawl_config.started_at[:19].replace("T", " ") if crawl_config else report.generated_at[:19].replace("T", " ")
        js_status = "Enabled" if (crawl_config and crawl_config.js_rendering_enabled) else "HTTP (Static DOM)"

        status_banner_html = ""
        if report.audit_status in ("INDEXATION_BLOCKED", "CRITICAL_BLOCKED"):
            status_banner_html = f"""
            <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; border-radius: 8px; padding: 14px 20px; margin-bottom: 20px; color: #FCA5A5; font-size: 0.92rem;">
                <strong style="color: #EF4444;">🚨 CRITICAL RELEASE BLOCKER:</strong> {html.escape(report.status_message)}
            </div>
            """
        elif report.audit_status == "STAGING_PROTECTED":
            status_banner_html = f"""
            <div style="background: rgba(59, 130, 246, 0.15); border: 1px solid #3B82F6; border-radius: 8px; padding: 14px 20px; margin-bottom: 20px; color: #93C5FD; font-size: 0.92rem;">
                <strong style="color: #60A5FA;">🛡️ STAGING ENVIRONMENT:</strong> {html.escape(report.status_message)}
            </div>
            """
        elif report.audit_status == "INSUFFICIENT_COVERAGE":
            status_banner_html = f"""
            <div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 14px 20px; margin-bottom: 20px; color: #FDE68A; font-size: 0.92rem;">
                <strong style="color: #F59E0B;">⚠️ INSUFFICIENT CRAWL COVERAGE:</strong> {html.escape(report.status_message)}
            </div>
            """
        elif report.audit_status == "INDEXATION_WARNING":
            status_banner_html = f"""
            <div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 14px 20px; margin-bottom: 20px; color: #FDE68A; font-size: 0.92rem;">
                <strong style="color: #F59E0B;">⚠️ ENVIRONMENT UNCONFIRMED / INDEXATION WARNING:</strong> {html.escape(report.status_message)}
            </div>
            """
        elif report.audit_status == "NEEDS_REVIEW":
            status_banner_html = f"""
            <div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 14px 20px; margin-bottom: 20px; color: #FDE68A; font-size: 0.92rem;">
                <strong style="color: #F59E0B;">⚠️ AUDIT REQUIRES ATTENTION (GATED):</strong> {html.escape(report.status_message)}
            </div>
            """
        elif report.audit_status == "INCONCLUSIVE":
            status_banner_html = f"""
            <div style="background: rgba(148, 163, 184, 0.15); border: 1px solid #94A3B8; border-radius: 8px; padding: 14px 20px; margin-bottom: 20px; color: #CBD5E1; font-size: 0.92rem;">
                <strong style="color: #94A3B8;">ℹ️ AUDIT INCONCLUSIVE:</strong> {html.escape(report.status_message)}
            </div>
            """
        elif report.audit_status == "PASS":
            status_banner_html = f"""
            <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 8px; padding: 14px 20px; margin-bottom: 20px; color: #A7F3D0; font-size: 0.92rem;">
                <strong style="color: #10B981;">✓ RELEASE AUDIT PASSED:</strong> {html.escape(report.status_message)}
            </div>
            """

        # Category Score Bars & Deductions
        cat_bars_html = ""
        scoring_breakdown_html = ""

        # Deterministic Check Execution Ledger Rows
        ledger_rows_html = ""
        for item in getattr(report, "check_ledger", []):
            st = item.status.value.lower() if hasattr(item.status, "value") else str(item.status).lower()
            if st == "pass":
                badge = '<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid #10B981;">PASS</span>'
            elif st == "fail":
                badge = '<span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #EF4444; border: 1px solid #EF4444;">FAIL</span>'
            elif st == "skipped":
                badge = '<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #F59E0B; border: 1px solid #F59E0B;">SKIPPED</span>'
            elif st == "not_applicable":
                badge = '<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: #94A3B8; border: 1px solid #94A3B8;">NOT APPLICABLE</span>'
            else:
                badge = f'<span class="badge">{html.escape(st.upper())}</span>'

            cat_str = item.category.value.replace("_", " ").title() if hasattr(item.category, "value") else str(item.category).title()
            aff_str = f" <small style='color: #EF4444;'>({item.affected_count} affected)</small>" if item.affected_count > 0 else ""

            ledger_rows_html += f"""
            <tr>
                <td><code>{html.escape(item.rule_id)}</code></td>
                <td><span style="color: #94A3B8; font-size: 0.8rem;">{html.escape(cat_str)}</span></td>
                <td><strong>{html.escape(item.title)}</strong></td>
                <td>{badge}</td>
                <td><span style="font-size: 0.85rem; color: #CBD5E1;">{html.escape(item.evidence)}{aff_str}</span></td>
            </tr>
            """

        for key, cs in report.category_scores.items():
            col = self._get_score_color(cs.score)
            status_badge = f'<span class="badge" style="background: rgba(255,255,255,0.08); color: {col};">{cs.status}</span>'
            cat_bars_html += f"""
            <div class="cat-score-row">
                <div class="cat-name"><strong>{html.escape(cs.name)}</strong> ({int(cs.weight*100)}%)</div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: {cs.score}%; background-color: {col};"></div>
                </div>
                <div class="cat-val" style="color: {col}; font-weight: bold;">{cs.score:.0f}/100</div>
                <div style="margin-left: 10px;">{status_badge}</div>
            </div>
            """

            # Itemized deductions
            if cs.deductions:
                scoring_breakdown_html += f"<h4>{html.escape(cs.name)} ({len(cs.deductions)} deductions)</h4><ul>"
                for d in cs.deductions:
                    scoring_breakdown_html += f"""
                    <li>
                        <span class="deduction-tag">-{d.points_deducted:.0f} pts</span>
                        <strong>{html.escape(d.rule_title)}</strong>: {html.escape(d.reason)}
                        <span class="affected-tag">Affects {d.affected_count} page(s)</span>
                    </li>
                    """
                scoring_breakdown_html += "</ul>"
            else:
                scoring_breakdown_html += f"<h4>{html.escape(cs.name)}</h4><p style='color: #10B981; font-size: 0.9rem;'>✓ All {cs.tests_evaluated} evaluated checks passed without deductions.</p>"

        # Clustered Evidence Cards
        evidence_cards_html = ""
        for cluster in report.issue_clusters:
            sev_badge = self._get_severity_badge(cluster.severity)
            cat_label = cluster.category.value.replace("_", " ").title()

            # Affected URLs formatted
            affected_urls_html = "".join(f"<li><code>{html.escape(u)}</code></li>" for u in cluster.affected_urls[:5])
            if len(cluster.affected_urls) > 5:
                affected_urls_html += f"<li><em>... and {len(cluster.affected_urls) - 5} more page(s)</em></li>"

            # Sample Evidence
            evidence_snippet = ""
            if cluster.sample_evidence:
                evidence_lines = []
                for item in cluster.sample_evidence[:4]:
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

            observation_text = getattr(cluster, "observation", "") or cluster.description
            inference_text = getattr(cluster, "inference", "") or cluster.impact

            evidence_cards_html += f"""
            <div class="finding-card">
                <div class="finding-header">
                    <div>
                        <span class="cat-tag">{html.escape(cat_label)}</span>
                        <h3>{html.escape(cluster.title)}</h3>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <span class="badge" style="background: #1E293B; color: #38BDF8;">Source: {html.escape(getattr(cluster, "finding_source", "raw_html"))}</span>
                        <span class="badge" style="background: #1E293B; color: #94A3B8;">Confidence: {cluster.confidence.value.upper()}</span>
                        {sev_badge}
                    </div>
                </div>

                <div class="finding-meta">
                    <strong>Cluster Occurrences:</strong> {cluster.occurrences_count} instance(s) across <strong>{len(cluster.affected_urls)} unique page(s)</strong>
                </div>

                <!-- Observation vs Inference Grid -->
                <div class="finding-grid">
                    <div class="finding-field" style="border-left: 3px solid #38BDF8;">
                        <div class="field-label" style="color: #38BDF8;">📋 Measurable Technical Observation</div>
                        <p style="font-weight: 500;">{html.escape(observation_text)}</p>
                    </div>

                    <div class="finding-field" style="border-left: 3px solid #A855F7;">
                        <div class="field-label" style="color: #A855F7;">🧠 Contextual SEO Inference & Risk</div>
                        <p>{html.escape(inference_text)}</p>
                    </div>
                </div>

                <div class="finding-grid" style="margin-top: 15px;">
                    <div class="finding-field">
                        <div class="field-label">🔍 Evidence Inspected</div>
                        <pre><code>{html.escape(evidence_snippet or 'Evaluated against document tree; attribute or tag is absent.')}</code></pre>
                    </div>

                    <div class="finding-field">
                        <div class="field-label">⚠️ Ranking & Crawl Consequence</div>
                        <p>{html.escape(cluster.impact)}</p>
                    </div>
                </div>

                <div class="finding-grid" style="margin-top: 15px;">
                    <div class="finding-field">
                        <div class="field-label">🛠️ Recommended Developer Fix</div>
                        <p style="color: #0284C7; font-weight: 600;">{html.escape(cluster.recommendation)}</p>
                    </div>

                    <div class="finding-field">
                        <div class="field-label">✓ Verification Step</div>
                        <p style="color: #059669;">{html.escape(cluster.verification_step)}</p>
                    </div>
                </div>

                <details class="affected-details" style="margin-top: 12px;">
                    <summary style="cursor: pointer; color: #64748B; font-size: 0.88rem; font-weight: 600;">View Affected URLs ({len(cluster.affected_urls)})</summary>
                    <ul style="margin-top: 8px; padding-left: 20px; font-size: 0.85rem; color: #475569;">
                        {affected_urls_html}
                    </ul>
                </details>
            </div>
            """

        # Orphaned Pages Table
        crawled_pages = report.crawl_result.pages if report.crawl_result else []
        eligible_indexable = [p for p in crawled_pages if p.is_indexable and p.status_code == 200]
        orphaned_list = report.crawl_result.orphaned_pages if report.crawl_result else []
        orphans_html = ""
        if not eligible_indexable:
            orphans_html = "<tr><td colspan='3' style='text-align: center; color: #94A3B8;'>⚪ Orphan analysis NOT APPLICABLE: 0 public pages are indexable (sitewide noindex active).</td></tr>"
        elif orphaned_list:
            for orphan in orphaned_list:
                orphans_html += f"""
                <tr>
                    <td><code>{html.escape(orphan)}</code></td>
                    <td><span class="badge badge-critical">0 Inlinks</span></td>
                    <td>Indexable page present in sitemap but isolated from internal site navigation. If intentional (e.g. ad landing page), ensure canonical or noindex is configured. If important, link from relevant category or contextual content.</td>
                </tr>
                """
        else:
            orphans_html = "<tr><td colspan='3' style='text-align: center; color: #10B981;'>✓ No orphaned indexable pages detected. All crawled URLs are linked in site navigation.</td></tr>"

        # Crawled Pages Inventory Table
        inventory_html = ""
        for p in crawled_pages:
            pt = getattr(p, "page_type", None)
            pt_val = pt.value if hasattr(pt, "value") else str(pt or "public_content")

            badge_color = "#10B981"
            if "app_route" in pt_val:
                badge_color = "#38BDF8"
            elif "auth" in pt_val:
                badge_color = "#A855F7"
            elif "utility" in pt_val:
                badge_color = "#94A3B8"
            elif "error" in pt_val or p.status_code >= 400:
                badge_color = "#EF4444"
            elif "redirect" in pt_val or p.status_code in (301, 302, 307, 308):
                badge_color = "#F59E0B"

            status_color = "#10B981" if p.status_code == 200 else ("#EF4444" if p.status_code >= 400 else "#F59E0B")
            in_inlinks = getattr(p, "internal_inlinks_count", getattr(p, "inlinks_count", 0))
            in_outlinks = getattr(p, "internal_outlinks_count", len(p.internal_links))
            idx_reason = getattr(p, "indexability_reason", "")
            if p.is_indexable:
                indexable_html = '<span style="color: #10B981; font-weight: 600;">Yes</span>'
            else:
                short_reason = (idx_reason[:26] + "...") if len(idx_reason) > 26 else (idx_reason or "No")
                indexable_html = f'<span style="color: #EF4444; font-weight: 600;" title="{html.escape(idx_reason)}">No <small style="color: #94A3B8; font-weight: normal;">({html.escape(short_reason)})</small></span>'
            title_disp = p.title[:45] + ('...' if len(p.title) > 45 else '') if p.title else 'None'

            inventory_html += f"""
            <tr>
                <td><code>{html.escape(p.url)}</code></td>
                <td><span style="color: {status_color}; font-weight: bold;">{p.status_code}</span></td>
                <td><span class="badge" style="background: rgba(30,41,59,0.9); color: {badge_color}; border: 1px solid {badge_color}; font-size: 0.72rem;">{pt_val.replace('_', ' ').upper()}</span></td>
                <td>{indexable_html}</td>
                <td>{in_inlinks}</td>
                <td>{in_outlinks}</td>
                <td>{p.word_count} words</td>
                <td>{html.escape(title_disp)}</td>
            </tr>
            """

        # Competitor Comparisons
        comp_html = ""
        all_comps = report.competitor_analyses or ([report.competitor_analysis] if report.competitor_analysis else [])
        for comp_analysis in all_comps:
            target_metrics = comp_analysis.your_metrics
            comp_html += f"""
            <div class="competitor-block">
                <h3>Query Benchmark: "{html.escape(comp_analysis.keyword)}"</h3>
                <p><strong>Your captured position:</strong> {html.escape(comp_analysis.position_label)} | <strong>Search:</strong> {html.escape(comp_analysis.search_engine)} ({html.escape(comp_analysis.search_country)}/{html.escape(comp_analysis.search_language)}) at {html.escape(comp_analysis.serp_retrieved_at or comp_analysis.analysed_at)} | <strong>Heuristic Gap Indicator:</strong> {comp_analysis.competitive_gap_score}/100 (not a rank forecast)</p>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Domain / URL</th>
                            <th>Word Count</th>
                            <th>H1 Header</th>
                            <th>Schema</th>
                            <th>Speed (HTTP RTT)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr class="target-row">
                            <td><strong>YOU ({html.escape(comp_analysis.position_label)})</strong></td>
                            <td><code>{html.escape(comp_analysis.your_url)}</code></td>
                            <td>{target_metrics.word_count if target_metrics else 'n/a'}</td>
                            <td>{html.escape(target_metrics.h1) if target_metrics and target_metrics.h1 else 'None'}</td>
                            <td>{'Yes' if target_metrics and target_metrics.has_structured_data else 'No data' if not target_metrics or target_metrics.fetch_status != 'fetched' else 'No'}</td>
                            <td>{f'{target_metrics.response_time_ms:.0f}ms' if target_metrics else 'n/a'}</td>
                        </tr>
            """
            for c in comp_analysis.competitors:
                comp_html += f"""
                        <tr>
                            <td>#{c.position}</td>
                            <td><code>{html.escape(c.domain)}</code></td>
                            <td>{c.word_count} words</td>
                            <td>{html.escape(c.h1[:40] + ('...' if len(c.h1) > 40 else '')) if c.h1 else 'None'}</td>
                            <td>{'Yes' if c.has_structured_data else 'No'}</td>
                            <td>{c.response_time_ms:.0f}ms</td>
                        </tr>
                """
            comp_html += """
                    </tbody>
                </table>
            """
            if comp_analysis.gaps:
                comp_html += "<div class='gap-box'><h4>Competitive Gaps to Surpass Competitors:</h4><ul>"
                for g in comp_analysis.gaps:
                    comp_html += f"<li>{html.escape(g)}</li>"
                comp_html += "</ul></div>"
            comp_html += "</div>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evidence-Based SEO Audit - {html.escape(report.domain)}</title>
    <style>
        :root {{
            --bg: #0F172A;
            --surface: #1E293B;
            --surface-hover: #334155;
            --border: #334155;
            --primary: #38BDF8;
            --accent: #6366F1;
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            line-height: 1.5;
            padding: 30px 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            border: 1px solid var(--border);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{ font-size: 1.8rem; font-weight: 800; }}
        .header p {{ color: var(--text-muted); margin-top: 5px; }}
        .config-bar {{
            background: rgba(0,0,0,0.25);
            border: 1px solid var(--border);
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            display: flex;
            gap: 20px;
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        .config-bar strong {{ color: var(--text-main); }}
        .grid-2 {{
            display: grid;
            grid-template-columns: 320px 1fr;
            gap: 25px;
            margin-bottom: 25px;
        }}
        .card {{
            background: var(--surface);
            border-radius: 12px;
            padding: 25px;
            border: 1px solid var(--border);
        }}
        .score-card {{
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .svg-dial {{ transform: rotate(-90deg); margin: 15px 0; }}
        .dial-bg {{ fill: none; stroke: #334155; stroke-width: 12; }}
        .dial-progress {{
            fill: none;
            stroke-width: 12;
            stroke-linecap: round;
            stroke-dasharray: {circumference:.1f};
            stroke-dashoffset: {dashoffset:.1f};
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 25px;
        }}
        .stat-box {{
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 18px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-val {{ font-size: 1.8rem; font-weight: 800; }}
        .stat-label {{ font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; margin-top: 4px; }}
        .cat-score-row {{ display: flex; align-items: center; margin-bottom: 12px; font-size: 0.92rem; }}
        .cat-name {{ width: 220px; color: var(--text-main); }}
        .progress-bar-bg {{
            flex: 1;
            height: 8px;
            background: #334155;
            border-radius: 4px;
            overflow: hidden;
            margin: 0 15px;
        }}
        .progress-bar-fill {{ height: 100%; border-radius: 4px; }}
        .cat-val {{ width: 65px; text-align: right; }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 700;
        }}
        .badge-critical {{ background: #7F1D1D; color: #FCA5A5; }}
        .badge-high {{ background: #991B1B; color: #FECACA; }}
        .badge-medium {{ background: #78350F; color: #FDE68A; }}
        .badge-low {{ background: #1E3A8A; color: #BFDBFE; }}
        .badge-info {{ background: #064E3B; color: #A7F3D0; }}
        .cat-tag {{
            font-size: 0.75rem;
            text-transform: uppercase;
            color: var(--primary);
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .finding-card {{
            background: #1E293B;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 18px;
        }}
        .finding-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }}
        .finding-header h3 {{ font-size: 1.15rem; font-weight: 700; color: #F8FAFC; margin-top: 2px; }}
        .finding-meta {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 15px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }}
        .finding-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
        .finding-field {{ background: rgba(0,0,0,0.2); padding: 12px; border-radius: 6px; font-size: 0.88rem; }}
        .field-label {{ font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 5px; }}
        pre {{
            background: #0B0F19;
            padding: 8px 12px;
            border-radius: 4px;
            overflow-x: auto;
            color: #38BDF8;
            font-family: monospace;
            font-size: 0.82rem;
            margin-top: 5px;
        }}
        .deduction-tag {{
            background: rgba(239,68,68,0.2);
            color: #EF4444;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.8rem;
            margin-right: 6px;
        }}
        .affected-tag {{
            background: rgba(255,255,255,0.08);
            color: var(--text-muted);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.78rem;
            margin-left: 6px;
        }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; margin-top: 15px; }}
        .data-table th, .data-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }}
        .data-table th {{ background: #0B0F19; color: var(--text-muted); }}
        .target-row {{ background: rgba(56, 189, 248, 0.1) !important; font-weight: bold; }}
        .gap-box {{ background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); padding: 15px; border-radius: 8px; margin-top: 15px; }}
        .gap-box h4 {{ color: #F59E0B; margin-bottom: 8px; }}
        .gap-box ul {{ padding-left: 20px; color: #FDE68A; }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div>
                <h1>⚡ Evidence-Based SEO Diagnostic Engine</h1>
                <p>Diagnostic evaluation for <strong>{html.escape(report.url)}</strong></p>
            </div>
            <div>
                <span class="badge" style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; padding: 6px 14px; font-size: 0.82rem;">EVIDENCE ENGINE 3.3.1</span>
            </div>
        </header>

        {status_banner_html}

        <!-- Crawl Configuration Metadata -->
        <div class="config-bar">
            <div><strong>Crawl Scope:</strong> {pages_count} Pages Evaluated ({coverage_pct:.0f}% Coverage)</div>
            <div><strong>Rendering:</strong> {js_status}</div>
            <div><strong>Timestamp:</strong> {crawl_time} UTC</div>
            <div><strong>Engine Confidence:</strong> High (Deterministic DOM Validation)</div>
        </div>

        <!-- Issue Aggregation Summary -->
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-val">{unique_clusters}</div>
                <div class="stat-label">Unique Issue Clusters</div>
            </div>
            <div class="stat-box">
                <div class="stat-val" style="color: {'#EF4444' if critical_clusters > 0 else '#10B981'};">{critical_clusters}</div>
                <div class="stat-label">Critical Blockers</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{raw_occurrences}</div>
                <div class="stat-label">Raw Occurrences</div>
            </div>
            <div class="stat-box">
                <div class="stat-val">{avg_latency:.0f} ms</div>
                <div class="stat-label">Avg HTTP RTT (Client Proxy)</div>
            </div>
        </div>

        <!-- Scores & Methodology -->
        <div class="grid-2">
            <div class="card score-card">
                <h3 style="margin-bottom: 8px;">Production SEO Readiness</h3>
                <div style="margin-bottom: 12px;">
                    <span class="badge" style="background: {'rgba(239, 68, 68, 0.2)' if ('BLOCKED' in report.audit_status or 'FAIL' in report.audit_status) else ('rgba(245, 158, 11, 0.2)' if report.audit_status in ('NEEDS_REVIEW', 'INSUFFICIENT_COVERAGE', 'INDEXATION_WARNING') else ('rgba(59, 130, 246, 0.2)' if report.audit_status == 'STAGING_PROTECTED' else ('rgba(148, 163, 184, 0.2)' if report.audit_status == 'INCONCLUSIVE' else 'rgba(16, 185, 129, 0.2)')))}; color: {'#EF4444' if ('BLOCKED' in report.audit_status or 'FAIL' in report.audit_status) else ('#F59E0B' if report.audit_status in ('NEEDS_REVIEW', 'INSUFFICIENT_COVERAGE', 'INDEXATION_WARNING') else ('#60A5FA' if report.audit_status == 'STAGING_PROTECTED' else ('#94A3B8' if report.audit_status == 'INCONCLUSIVE' else '#10B981')))}; padding: 5px 12px; font-weight: bold; font-size: 0.82rem;">{report.audit_status}</span>
                </div>
                <svg width="180" height="180" class="svg-dial">
                    <circle cx="90" cy="90" r="{radius}" class="dial-bg"></circle>
                    <circle cx="90" cy="90" r="{radius}" class="dial-progress" stroke="{score_color}"></circle>
                </svg>
                <div style="font-size: 2.8rem; font-weight: 800; color: {score_color}; margin-top: -125px; margin-bottom: 45px;">
                    {score:.0f}
                </div>
                <p style="color: var(--text-muted); font-size: 0.85rem; padding: 0 10px;">
                    Release readiness accounts for indexability and critical release gates. Technical diagnostics score reflects {stats.get('total_tests_evaluated', 39)} weighted technical, on-page, and architectural checks.
                </p>
                <p style="color: var(--text-muted); font-size: 0.85rem; padding: 0 10px;">Technical diagnostics score: <strong>{report.diagnostic_score:.0f}/100</strong></p>
            </div>

            <div class="card">
                <h3 style="margin-bottom: 15px;">Category Breakdown & Evaluation</h3>
                {cat_bars_html}
            </div>
        </div>

        <!-- Transparent Deductions Log -->
        <div class="card" style="margin-bottom: 25px;">
            <h3>📐 Transparent Scoring Methodology (Itemized Deductions)</h3>
            <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 15px;">
                Each score begins at 100. Deductions are strictly applied per unique issue cluster: Critical (-15), High (-8), Medium (-3), Low (-1). Informational suggestions carry 0 penalty.
            </p>
            <div style="font-size: 0.88rem; line-height: 1.8;">
                {scoring_breakdown_html}
            </div>
        </div>

        <!-- Deterministic Check Execution Ledger -->
        <div class="card" style="margin-bottom: 25px;">
            <h3>📋 Deterministic Check Execution Ledger ({len(getattr(report, "check_ledger", []))} Rules)</h3>
            <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 15px;">
                Verified execution ledger of all diagnostic rules. Distinguishes executed passes from skipped prerequisites and non-applicable audits.
            </p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width: 100px;">Rule ID</th>
                        <th style="width: 130px;">Category</th>
                        <th style="width: 220px;">Rule Title</th>
                        <th style="width: 130px;">Status</th>
                        <th>Execution Evidence & Scope</th>
                    </tr>
                </thead>
                <tbody>
                    {ledger_rows_html}
                </tbody>
            </table>
        </div>

        <!-- Evidence-Based Finding Cards -->
        <div class="card" style="margin-bottom: 25px;">
            <h3>🔬 Evidence-Based Audit Findings ({len(report.issue_clusters)} Issue Clusters)</h3>
            <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 20px;">
                Every finding presents the exact DOM element inspected, the expected SEO consequence, the developer fix, and re-crawl verification steps.
            </p>
            {evidence_cards_html}
        </div>

        <!-- Orphaned Pages -->
        <div class="card" style="margin-bottom: 25px;">
            <h3>🔍 Contextual Orphaned Page Audit</h3>
            <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 15px;">
                Orphaned pages are indexable HTML documents present in the sitemap that receive zero internal links from site navigation. Application workflows (like auth or account creation) are filtered out.
            </p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Orphaned URL</th>
                        <th>Inbound Links</th>
                        <th>Context & Architectural Assessment</th>
                    </tr>
                </thead>
                <tbody>
                    {orphans_html}
                </tbody>
            </table>
        </div>

        <!-- Evaluated Page Inventory & Classification -->
        <div class="card" style="margin-bottom: 25px;">
            <h3>📑 Evaluated Page Inventory & Classification</h3>
            <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 15px;">
                Full inventory of crawled URLs with technical classifications. Public content pages undergo full on-page SEO evaluations, while private app routes and authentication gateways are protected from false-positive duplicate content deductions.
            </p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Evaluated URL</th>
                        <th>Status</th>
                        <th>Technical Intent</th>
                        <th>Indexable?</th>
                        <th>Inlinks</th>
                        <th>Outlinks</th>
                        <th>Word Count</th>
                        <th>Title Tag</th>
                    </tr>
                </thead>
                <tbody>
                    {inventory_html}
                </tbody>
            </table>
        </div>

        <!-- Competitor Benchmark -->
        {f'<div class="card" style="margin-bottom: 25px;"><h3>🏆 SERP Intelligence & Competitor Reverse-Engineering</h3>{comp_html}</div>' if comp_html else ''}
    </div>
</body>
</html>
"""
