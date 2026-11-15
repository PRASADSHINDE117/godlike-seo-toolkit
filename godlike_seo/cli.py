"""
Godlike SEO Toolkit - Command Line Interface 2.0.

Provides CLI commands for AI Agents and Developers:
- Full asynchronous website crawling and SEO auditing with zero-false-positive engine
- User login automation via Playwright (form login, session cookie capture, auth state)
- Multiple developer export formats: Markdown (.md), Excel (.xlsx), HTML (.html), and JSON (.json)
- Minimalist, lightweight CLI mode (--quiet / --format json) for AI Agent tool calling
- SERP scraping and competitor benchmark comparison
- Long-tail keyword intent research
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import warnings
from typing import Optional

import click
import urllib3
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

from godlike_seo import __version__
from godlike_seo.auth import AuthConfig, AuthManager
from godlike_seo.crawler import CrawlerConfig, SEOCrawler
from godlike_seo.models import CrawlResult, SEOReport
from godlike_seo.reports.excel_report import ExcelReportGenerator
from godlike_seo.reports.html_report import HTMLReportGenerator
from godlike_seo.reports.markdown_report import MarkdownReportGenerator
from godlike_seo.reports.report_generator import ReportGenerator
from godlike_seo.serp.competitor_analyzer import CompetitorAnalyzer
from godlike_seo.serp.keyword_analyzer import KeywordAnalyzer
from godlike_seo.serp.serp_scraper import SERPScraper
from godlike_seo.decision_engine import KevDecisionEngine
from godlike_seo.integrations.search_console import GoogleSearchConsoleClient
from godlike_seo.integrations.pagespeed import PageSpeedInsightsClient

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(message)s")

DEFAULT_AUTH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user details", "user info.txt")


def _load_keyword_file(filepath: str) -> list[str]:
    """Read keyword queries from the toolkit's Keyword Plan workbook tab."""
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(filepath, read_only=True, data_only=True)
    except Exception as exc:
        raise click.ClickException(f"Could not read keyword workbook: {exc}") from exc
    try:
        if "Keyword Plan" not in workbook.sheetnames:
            raise click.ClickException("Keyword workbook must contain a 'Keyword Plan' sheet.")
        sheet = workbook["Keyword Plan"]
        header_row = None
        keyword_col = None
        for row_idx, row in enumerate(sheet.iter_rows(min_row=1, max_row=min(sheet.max_row or 50, 20), values_only=True), start=1):
            for col_idx, value in enumerate(row, start=1):
                if isinstance(value, str) and value.strip().casefold() == "target keyword / query":
                    header_row, keyword_col = row_idx, col_idx
                    break
            if keyword_col:
                break
        if not keyword_col or not header_row:
            raise click.ClickException("Could not find a 'Target keyword / query' column in the 'Keyword Plan' sheet.")
        queries = []
        for (value,) in sheet.iter_rows(
            min_row=header_row + 1,
            min_col=keyword_col,
            max_col=keyword_col,
            values_only=True,
        ):
            if isinstance(value, str) and value.strip():
                queries.append(value.strip())
        return queries
    finally:
        workbook.close()


@click.group()
@click.version_option(version=__version__, prog_name="godlike-seo")
def cli():
    """⚡ Godlike SEO Engine 3.3.2 - Minimalist, Evidence-Backed CLI for Developers & AI Agents."""
    pass


@cli.command()
@click.argument("url")
@click.option("--max-pages", "-m", default=50, help="Maximum number of pages to crawl.")
@click.option("--depth", "-d", default=3, help="Maximum crawl depth.")
@click.option("--concurrency", "-c", default=10, help="Concurrent async crawler workers.")
@click.option("--format", "-f", "output_format", type=click.Choice(["all", "html", "md", "xlsx", "json"]), default="all", help="Report format (all, html, md, xlsx, json).")
@click.option("--output", "-o", default=None, help="Filepath to save report.")
@click.option("--output-dir", default=None, help="Directory to save generated reports.")
@click.option("--environment", "-e", type=click.Choice(["production", "staging", "development", "unknown"]), default=None, help="Target environment intent. When 'staging', sitewide noindex is treated as expected protection.")
@click.option("--verify-ssl/--insecure", "verify_ssl", default=True, show_default=True, help="Enforce SSL certificate verification (uses certifi bundles).")
@click.option("--render-js", is_flag=True, default=False, help="Enable selective headless Playwright JS rendering.")
@click.option("--keyword", "-k", multiple=True, help="Target keyword to benchmark; repeat for multiple terms.")
@click.option("--keyword-file", type=click.Path(exists=True, dir_okay=False, path_type=str), help="Read queries from the 'Keyword Plan' tab of the research workbook.")
@click.option("--keyword-limit", type=click.IntRange(1, 100), default=5, show_default=True, help="Maximum benchmark queries loaded from --keyword-file and --keyword.")
@click.option("--country", default="in", show_default=True, help="Two-letter search market code (for example, in or us).")
@click.option("--language", default="en", show_default=True, help="Search language code (for example, en).")
@click.option("--auth-file", default=None, help="Path to credentials file (e.g. 'user details/user info.txt').")
@click.option("--login-url", default=None, help="Login page URL to authenticate via Playwright before crawling.")
@click.option("--username", "-u", default=None, help="Login username/email.")
@click.option("--password", "-p", default=None, help="Login password.")
@click.option("--auth-cookie", default=None, help="Raw session cookie string (e.g. 'session=xyz; token=abc').")
@click.option("--quiet", "-q", is_flag=True, help="Minimalist agent output (suppresses terminal banners).")
def crawl(
    url: str,
    max_pages: int,
    depth: int,
    concurrency: int,
    output_format: str,
    output: Optional[str],
    output_dir: Optional[str],
    environment: Optional[str],
    verify_ssl: bool,
    render_js: bool,
    keyword: tuple[str, ...],
    keyword_file: Optional[str],
    keyword_limit: int,
    country: str,
    language: str,
    auth_file: Optional[str],
    login_url: Optional[str],
    username: Optional[str],
    password: Optional[str],
    auth_cookie: Optional[str],
    quiet: bool,
):
    """Crawl a website, detect evidence-backed issues, orphaned pages, and export MD/Excel/HTML/JSON reports."""
    # Setup AuthConfig
    auth_cfg = AuthConfig()
    target_auth_file = auth_file or (DEFAULT_AUTH_FILE if os.path.exists(DEFAULT_AUTH_FILE) else None)
    if target_auth_file and os.path.exists(target_auth_file):
        auth_cfg = AuthConfig.from_file(target_auth_file)

    if login_url:
        auth_cfg.login_url = login_url
    if username:
        auth_cfg.username = username
    if password:
        auth_cfg.password = password
    if auth_cookie:
        auth_cfg.auth_cookie = auth_cookie

    has_auth = bool(auth_cfg.auth_cookie or (auth_cfg.login_url and auth_cfg.username and auth_cfg.password))

    if not quiet:
        auth_msg = " [bold green](Authenticated via Playwright)[/]" if has_auth else ""
        console.print(Panel.fit(
            f"[bold cyan]Godlike SEO Engine {__version__}[/bold cyan]{auth_msg}\nTarget: [yellow]{url}[/yellow] | Max Pages: {max_pages} | Concurrency: {concurrency} | Env: {environment or 'auto'}",
            border_style="cyan"
        ))

    config = CrawlerConfig(
        max_pages=max_pages,
        max_depth=depth,
        concurrency=concurrency,
        environment=environment,
        render_js=render_js,
        verify_ssl=verify_ssl,
    )
    crawler = SEOCrawler(config=config, auth_config=auth_cfg if has_auth else None)

    if not quiet:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[green]Crawling {url}...", total=None)
            crawl_result: CrawlResult = asyncio.run(crawler.crawl(url))
            progress.update(task, description="[bold green]Crawl complete! Running diagnostic audits...")
    else:
        crawl_result: CrawlResult = asyncio.run(crawler.crawl(url))

    report_gen = ReportGenerator(environment=environment)
    query_list = list(keyword)
    if keyword_file:
        query_list.extend(_load_keyword_file(keyword_file))
    unique_queries = []
    seen_queries = set()
    for query in query_list:
        normalized_query = query.strip().casefold()
        if normalized_query and normalized_query not in seen_queries:
            seen_queries.add(normalized_query)
            unique_queries.append(query.strip())
    if len(unique_queries) > keyword_limit:
        if not quiet:
            console.print(f"[yellow]Limiting {len(unique_queries)} queries to the first {keyword_limit}.[/yellow]")
        unique_queries = unique_queries[:keyword_limit]

    comp_analyses = []
    if unique_queries:
        if not quiet:
            console.print(f"[cyan]Benchmarking {len(unique_queries)} keyword query(s) for {country}/{language}...[/cyan]")
        scraper = SERPScraper(country=country, language=language)
        analyzer = CompetitorAnalyzer(scraper=scraper)
        for query in unique_queries:
            if not quiet:
                console.print(f"[cyan]Scraping SERP & Competitors for query: '[bold yellow]{query}[/bold yellow]'...[/cyan]")
            comp_analyses.append(analyzer.analyze_for_keyword(target_keyword=query, your_url=url))

    report: SEOReport = report_gen.generate_report(crawl_result, competitor_analyses=comp_analyses, environment=environment)

    # CLI Terminal Display
    if not quiet and output_format != "json":
        score_color = "green" if report.overall_score >= 85 else ("yellow" if report.overall_score >= 65 else "red")
        stats = report.summary_stats or {}
        status_col = "green" if report.audit_status == "PASS" else ("cyan" if report.audit_status == "STAGING_PROTECTED" else "red")
        console.print()
        console.print(Panel.fit(
            f"Production SEO Readiness: [bold {score_color}]{report.overall_score:.0f}/100[/bold {score_color}] | Technical Diagnostics: {report.diagnostic_score:.0f}/100 | Release Status: [bold {status_col}]{report.audit_status}[/] ({report.environment_intent.upper()})\n"
            f"Pages Crawled: {len(crawl_result.pages)} | Unique Issue Clusters: [bold]{stats.get('unique_issue_clusters', 0)}[/bold] | Raw Occurrences: {stats.get('total_raw_occurrences', 0)}\n"
            f"Critical Blockers: [bold {'red' if stats.get('critical_clusters_count', 0) > 0 else 'green'}]{stats.get('critical_clusters_count', 0)}[/] | Orphaned Pages: {len(crawl_result.orphaned_pages)}",
            title="[bold]Diagnostic Summary[/bold]",
            border_style=score_color,
        ))
        if report.audit_status in ("INDEXATION_BLOCKED", "STAGING_PROTECTED"):
            msg_col = "red" if report.audit_status == "INDEXATION_BLOCKED" else "cyan"
            console.print(Panel(f"[{msg_col}]{report.status_message}[/]", border_style=msg_col))

        cat_table = Table(title="Category Evaluation & Scoring", show_header=True, header_style="bold magenta")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Score", justify="right")
        cat_table.add_column("Weight", justify="right")
        cat_table.add_column("Tests Passed", justify="right")
        cat_table.add_column("Deductions", justify="right")

        for cat_name, cs in report.category_scores.items():
            c_col = "green" if cs.score >= 85 else ("yellow" if cs.score >= 65 else "red")
            cat_table.add_row(
                cs.name,
                f"[{c_col}]{cs.score:.0f}/100[/{c_col}]",
                f"{int(cs.weight*100)}%",
                f"{cs.tests_passed}/{cs.tests_evaluated}",
                f"{len(cs.deductions)}",
            )
        console.print(cat_table)

        # Top Action Items
        rec_table = Table(title="⚡ Top Prioritized Developer Fixes", show_header=True, header_style="bold yellow")
        rec_table.add_column("Priority Action Item", style="white")
        for r in report.recommendations[:8]:
            rec_table.add_row(r)
        console.print(rec_table)

    # Determine Output Directory & Base Name
    safe_domain = report.domain.replace(".", "_") or "site"
    out_dir = output_dir or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)

    generated_files = []

    # 1. HTML Export
    if output_format in ("all", "html"):
        html_path = output if (output and output.endswith(".html")) else os.path.join(out_dir, f"seo_report_{safe_domain}.html")
        html_gen = HTMLReportGenerator()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_gen.render(report))
        generated_files.append(html_path)

    # 2. Markdown Export (Token-efficient for AI Agents & Devs)
    if output_format in ("all", "md"):
        md_path = output if (output and output.endswith(".md")) else os.path.join(out_dir, f"seo_report_{safe_domain}.md")
        md_gen = MarkdownReportGenerator()
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_gen.render(report))
        generated_files.append(md_path)

    # 3. Excel Export (.xlsx with multi-tabs)
    if output_format in ("all", "xlsx"):
        xlsx_path = output if (output and output.endswith(".xlsx")) else os.path.join(out_dir, f"seo_report_{safe_domain}.xlsx")
        xlsx_gen = ExcelReportGenerator()
        xlsx_gen.generate(report, xlsx_path)
        generated_files.append(xlsx_path)

    # 4. JSON Export (Machine-parseable for Agentic Pipelines)
    if output_format in ("all", "json"):
        json_path = output if (output and output.endswith(".json")) else os.path.join(out_dir, f"seo_report_{safe_domain}.json")
        json_payload = {
            "url": report.url,
            "domain": report.domain,
            "overall_score": report.overall_score,
            "diagnostic_score": report.diagnostic_score,
            "audit_status": report.audit_status,
            "status_message": report.status_message,
            "environment_intent": report.environment_intent,
            "summary_stats": report.summary_stats,
            "category_scores": {k: {"name": cs.name, "score": cs.score, "tests_passed": cs.tests_passed, "tests_evaluated": cs.tests_evaluated, "deductions_count": len(cs.deductions)} for k, cs in report.category_scores.items()},
            "deductions": [{"rule": d.rule_title, "points": d.points_deducted, "reason": d.reason, "affected": d.affected_count} for d in report.all_deductions],
            "check_ledger": [c.to_dict() for c in getattr(report, "check_ledger", [])],
            "issue_clusters": [c.to_dict() for c in report.issue_clusters],
            "recommendations": report.recommendations,
            "orphaned_pages": crawl_result.orphaned_pages,
            "remediation_plan": report.remediation_plan.to_dict() if getattr(report, "remediation_plan", None) else None,
            "verifications": [v.to_dict() for v in getattr(report, "verifications", [])],
            "competitor_analyses": [a.to_dict() for a in report.competitor_analyses],
            "serp_analyses": [a.to_dict() for a in report.serp_analyses],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_payload, f, indent=2)
        generated_files.append(json_path)

        if quiet and output_format == "json":
            print(json.dumps(json_payload, indent=2))
            return

    if not quiet:
        console.print("\n[bold green]✓ Generated Developer & AI Reports:[/bold green]")
        for gf in generated_files:
            console.print(f"  • [cyan]{os.path.abspath(gf)}[/cyan]")
        console.print()
    elif not (output_format == "json"):
        for gf in generated_files:
            print(os.path.abspath(gf))


@cli.command()
@click.argument("login_url")
@click.option("--username", "-u", required=True, help="Login username/email.")
@click.option("--password", "-p", required=True, help="Login password.")
@click.option("--username-selector", default=None, help="CSS selector for username field.")
@click.option("--password-selector", default=None, help="CSS selector for password field.")
@click.option("--submit-selector", default=None, help="CSS selector for submit button.")
def test_login(login_url: str, username: str, password: str, username_selector: Optional[str], password_selector: Optional[str], submit_selector: Optional[str]):
    """Test automated Playwright authentication and display captured session cookies."""
    console.print(Panel.fit(f"[bold cyan]Testing Playwright Login[/bold cyan]\nURL: {login_url}\nUser: {username}", border_style="cyan"))

    auth_cfg = AuthConfig(
        login_url=login_url,
        username=username,
        password=password,
        username_selector=username_selector,
        password_selector=password_selector,
        submit_selector=submit_selector,
    )
    manager = AuthManager(auth_cfg)

    with console.status("[green]Launching headless browser and submitting login form..."):
        cookies = asyncio.run(manager.perform_login())

    if cookies:
        console.print(f"\n[bold green]✓ Successfully authenticated! Captured {len(cookies)} cookies:[/bold green]")
        for k, v in cookies.items():
            console.print(f"  • [yellow]{k}[/yellow]: {v[:40]}...")
    else:
        console.print("\n[bold red]✗ Authentication failed or no session cookies captured.[/bold red]")


@cli.command()
@click.argument("keyword")
@click.option("--compare", "-c", default=None, help="Your website URL to benchmark against top ranking results.")
@click.option("--results", "-n", default=10, help="Number of search results to scrape.")
@click.option("--country", default="in", show_default=True, help="Two-letter search market code (for example, in or us).")
@click.option("--language", default="en", show_default=True, help="Search language code (for example, en).")
def serp(keyword: str, compare: Optional[str], results: int, country: str, language: str):
    """Scan Google/DuckDuckGo/Bing search results and benchmark top competitors."""
    console.print(Panel.fit(f"[bold cyan]SERP Intelligence[/bold cyan]\nQuery: [yellow]'{keyword}'[/yellow]", border_style="cyan"))

    scraper = SERPScraper(country=country, language=language)
    with console.status("[green]Scraping search engine results..."):
        serp_data = scraper.scrape(keyword, num_results=results)

    table = Table(title=f"Search Results for '{keyword}'", show_header=True, header_style="bold green")
    table.add_column("Rank", justify="center", style="bold")
    table.add_column("Domain / URL", style="cyan")
    table.add_column("Snippet", style="white")

    for item in serp_data.results:
        table.add_row(f"#{item.position}", item.url, item.snippet[:90] + ("..." if len(item.snippet) > 90 else ""))
    console.print(table)

    if compare:
        console.print(f"\n[cyan]Benchmarking [yellow]{compare}[/yellow] against top ranking competitors...[/cyan]")
        analyzer = CompetitorAnalyzer(scraper=scraper)
        with console.status("[green]Scraping competitors and computing ranking gaps..."):
            comp_analysis = analyzer.analyze_for_keyword(keyword, your_url=compare)

        gap_color = "green" if comp_analysis.competitive_gap_score >= 75 else ("yellow" if comp_analysis.competitive_gap_score >= 50 else "red")
        prob_color = "green" if comp_analysis.ranking_probability_pct >= 70 else ("yellow" if comp_analysis.ranking_probability_pct >= 40 else "red")
        console.print(Panel.fit(
            f"Your URL Position: {comp_analysis.position_label}\n"
            f"Competitive Parity Score: [{gap_color}]{comp_analysis.competitive_gap_score}/100[/{gap_color}] ({comp_analysis.parity_status})\n"
            f"Estimated Ranking Probability: [{prob_color}]{comp_analysis.ranking_probability_pct:.1f}%[/{prob_color}]",
            title="Competitor Benchmark",
            border_style="cyan",
        ))

        if comp_analysis.gaps:
            gap_table = Table(title="[bold yellow]Competitive Ranking Gaps & Actionable Fixes[/bold yellow]")
            gap_table.add_column("Identified Deficit", style="red")
            gap_table.add_column("Recommended Fix to Outrank", style="green")
            for g, r in zip(comp_analysis.gaps, comp_analysis.recommendations):
                gap_table.add_row(g, r)
            console.print(gap_table)


@cli.command()
@click.argument("seed")
@click.option("--limit", "-l", default=30, help="Max keywords to discover.")
@click.option("--country", default="in", show_default=True, help="Two-letter market code used for autocomplete suggestions.")
@click.option("--language", default="en", show_default=True, help="Language code used for autocomplete suggestions.")
def keywords(seed: str, limit: int, country: str, language: str):
    """Expand seed keyword into questions, long-tail terms, and search intent groups."""
    console.print(Panel.fit(f"[bold cyan]Keyword Research & Intent Explorer[/bold cyan]\nSeed: [yellow]'{seed}'[/yellow]", border_style="cyan"))

    analyzer = KeywordAnalyzer(country=country, language=language)
    with console.status("[green]Querying Google autocomplete and clustering search intent..."):
        opps = analyzer.expand_keyword(seed, max_results=limit)

    table = Table(title=f"Discovered Keyword Opportunities for '{seed}'", show_header=True, header_style="bold magenta")
    table.add_column("Keyword", style="yellow")
    table.add_column("Intent", style="cyan")
    table.add_column("Volume Tier*", justify="center", style="green")
    table.add_column("Difficulty*", justify="center", style="bold")
    table.add_column("Relevance*", justify="center", style="white")
    table.add_column("Intent Confidence", justify="right")
    table.add_column("Recommended Content Type", style="dim")

    for opp in opps:
        kd_style = "green" if opp.keyword_difficulty <= 35 else ("yellow" if opp.keyword_difficulty <= 65 else "red")
        table.add_row(
            opp.keyword,
            opp.intent.value,
            opp.search_volume_tier,
            f"[{kd_style}]{opp.keyword_difficulty:.0f}[/{kd_style}]",
            f"{opp.relevance_score:.0f}",
            f"{opp.intent_confidence:.0%}",
            opp.suggested_content_type,
        )
    console.print(table)
    console.print("[dim]* Relevance, volume tier, and difficulty are heuristic estimates; no monthly search-volume or live trend data is available.[/dim]")


@cli.command()
@click.argument("url")
@click.option("--output", "-o", default="remediation_plan.md", help="Filepath to save remediation runbook.")
@click.option("--max-pages", "-m", default=10, help="Max pages to crawl for remediation diagnosis.")
@click.option("--format", "-f", "output_format", type=click.Choice(["md", "json"]), default="md", help="Export format.")
def remediate(url: str, output: str, max_pages: int, output_format: str):
    """AI Remediation Agent: Analyze findings, propose code patches, and generate Playwright verification tests."""
    console.print(Panel.fit(f"[bold cyan]AI Remediation Agent Engine[/bold cyan]\nTarget: [yellow]{url}[/yellow]", border_style="cyan"))

    crawler = SEOCrawler(config=CrawlerConfig(max_pages=max_pages, max_depth=2, concurrency=5))
    with console.status("[green]Crawling and diagnosing issues..."):
        crawl_result = asyncio.run(crawler.crawl(url))

    report_gen = ReportGenerator()
    report = report_gen.generate_report(crawl_result)

    plan = getattr(report, "remediation_plan", None)
    if not plan or not plan.tasks:
        console.print("[green]✓ Zero critical or high-severity issues detected. No remediation required![/green]")
        return

    table = Table(title=f"AI Remediation Tasks for {report.domain}", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="bold")
    table.add_column("Priority", justify="center")
    table.add_column("Title", style="white")
    table.add_column("Component", style="yellow")
    table.add_column("Scope", justify="center")

    for task in plan.tasks:
        p_col = "red" if task.priority == "P0" else ("yellow" if task.priority == "P1" else "cyan")
        table.add_row(task.task_id, f"[{p_col}]{task.priority}[/{p_col}]", task.title, task.target_component, f"{task.affected_urls_count} pages")
    console.print(table)

    with open(output, "w", encoding="utf-8") as f:
        if output_format == "json":
            json.dump(plan.to_dict(), f, indent=2)
        else:
            f.write(plan.to_markdown())

    console.print(f"\n[green]✓ Exported remediation plan to:[/] [bold cyan]{output}[/bold cyan]")


@cli.command()
@click.argument("site_url")
@click.option("--days", "-d", default=28, help="Date range in days.")
@click.option("--limit", "-l", default=50, help="Max queries to retrieve.")
def gsc(site_url: str, days: int, limit: int):
    """Google Search Console: Fetch verified impressions, clicks, CTR, and striking distance queries."""
    console.print(Panel.fit(f"[bold cyan]Google Search Console Performance Intelligence[/bold cyan]\nSite: [yellow]{site_url}[/yellow] ({days} days)", border_style="cyan"))

    client = GoogleSearchConsoleClient(enable_demo_mode=True)
    with console.status("[green]Fetching Google Search Console performance data..."):
        gsc_report = client.fetch_search_analytics(site_url, days=days, row_limit=limit)

    summary_panel = (
        f"Mode: {'[yellow]Demo / Simulation (Configure GSC_ACCESS_TOKEN for live API)[/yellow]' if gsc_report.is_mock else '[green]Live Verified GSC API[/green]'}\n"
        f"Total Clicks: [bold green]{gsc_report.total_clicks:,}[/bold green] | "
        f"Total Impressions: [bold cyan]{gsc_report.total_impressions:,}[/bold cyan] | "
        f"Avg CTR: [bold yellow]{gsc_report.average_ctr:.2f}%[/bold yellow] | "
        f"Avg Position: [bold white]{gsc_report.average_position:.1f}[/bold white]"
    )
    console.print(Panel.fit(summary_panel, title="Search Performance Summary"))

    if gsc_report.striking_distance:
        table = Table(title="🎯 Striking Distance Queries (Positions 8-20 ripe for Page 1)", show_header=True, header_style="bold yellow")
        table.add_column("Query", style="yellow")
        table.add_column("Position", justify="center", style="bold")
        table.add_column("Impressions", justify="right", style="cyan")
        table.add_column("Clicks", justify="right", style="green")
        table.add_column("CTR", justify="right")
        for q in gsc_report.striking_distance[:10]:
            table.add_row(q.query, f"#{q.position:.1f}", f"{q.impressions:,}", f"{q.clicks:,}", f"{q.ctr:.2f}%")
        console.print(table)

    if gsc_report.low_ctr_opportunities:
        table = Table(title="⚠️ High Impression / Low CTR Opportunities (Rank 1-5 Snippet Rewrites)", show_header=True, header_style="bold red")
        table.add_column("Query", style="yellow")
        table.add_column("Position", justify="center", style="bold")
        table.add_column("Impressions", justify="right", style="cyan")
        table.add_column("CTR", justify="right", style="red")
        for q in gsc_report.low_ctr_opportunities[:5]:
            table.add_row(q.query, f"#{q.position:.1f}", f"{q.impressions:,}", f"{q.ctr:.2f}%")
        console.print(table)


@cli.command()
@click.argument("url")
@click.option("--strategy", "-s", type=click.Choice(["mobile", "desktop"]), default="mobile", help="Analysis device viewport.")
def pagespeed(url: str, strategy: str):
    """Google PageSpeed Insights: Core Web Vitals (LCP, CLS, INP, TTFB) and performance diagnostics."""
    console.print(Panel.fit(f"[bold cyan]Google PageSpeed Insights & Core Web Vitals[/bold cyan]\nTarget: [yellow]{url}[/yellow] | Viewport: [bold]{strategy.upper()}[/bold]", border_style="cyan"))

    client = PageSpeedInsightsClient()
    with console.status(f"[green]Querying Google PageSpeed Insights ({strategy})..."):
        cwv = client.run_audit(url, strategy=strategy)

    status_col = "green" if cwv.overall_status == "PASS" else ("yellow" if cwv.overall_status == "NEEDS_IMPROVEMENT" else "red")
    console.print(Panel.fit(
        f"Lighthouse Score: [bold {status_col}]{cwv.performance_score:.0f}/100[/bold {status_col}]\n"
        f"Core Web Vitals Assessment: [bold {status_col}]{cwv.overall_status}[/bold {status_col}] "
        f"({'[green]Live CrUX Lab[/green]' if cwv.is_live_crux else '[yellow]Calibrated Heuristic[/yellow]'})\n\n"
        f"• Largest Contentful Paint (LCP): [{cwv.lcp.status.lower()}]{cwv.lcp.value:.2f}{cwv.lcp.unit}[/{cwv.lcp.status.lower()}] (Threshold: ≤2.5s)\n"
        f"• Cumulative Layout Shift (CLS): [{cwv.cls.status.lower()}]{cwv.cls.value:.3f}[/{cwv.cls.status.lower()}] (Threshold: ≤0.1)\n"
        f"• Interaction to Next Paint (INP): [{cwv.inp.status.lower()}]{cwv.inp.value:.0f}{cwv.inp.unit}[/{cwv.inp.status.lower()}] (Threshold: ≤200ms)\n"
        f"• First Contentful Paint (FCP): [{cwv.fcp.status.lower()}]{cwv.fcp.value:.2f}{cwv.fcp.unit}[/{cwv.fcp.status.lower()}] (Threshold: ≤1.8s)\n"
        f"• Time to First Byte (TTFB): [{cwv.ttfb.status.lower()}]{cwv.ttfb.value:.0f}{cwv.ttfb.unit}[/{cwv.ttfb.status.lower()}] (Threshold: ≤800ms)",
        title="Core Web Vitals Scorecard",
        border_style=status_col,
    ))

    if cwv.opportunities:
        table = Table(title="🚀 Top Performance Opportunities", show_header=True, header_style="bold yellow")
        table.add_column("Audit", style="bold")
        table.add_column("Opportunity", style="white")
        table.add_column("Est. Savings", justify="right", style="cyan")
        for opp in cwv.opportunities:
            table.add_row(opp.get("id", ""), opp.get("title", ""), f"{opp.get('estimated_savings_ms', 0):.0f} ms")
        console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
