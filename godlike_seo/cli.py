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

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(message)s")

DEFAULT_AUTH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user details", "user info.txt")


@click.group()
@click.version_option(version="3.3.0", prog_name="godlike-seo")
def cli():
    """⚡ Godlike SEO Engine 3.3 - Minimalist, Evidence-Backed CLI for Developers & AI Agents."""
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
@click.option("--render-js", is_flag=True, default=False, help="Enable selective headless Playwright JS rendering.")
@click.option("--keyword", "-k", default=None, help="Target keyword to run competitive SERP benchmark against.")
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
    render_js: bool,
    keyword: Optional[str],
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
            f"[bold cyan]Godlike SEO Engine 3.1[/bold cyan]{auth_msg}\nTarget: [yellow]{url}[/yellow] | Max Pages: {max_pages} | Concurrency: {concurrency} | Env: {environment or 'auto'}",
            border_style="cyan"
        ))

    config = CrawlerConfig(
        max_pages=max_pages,
        max_depth=depth,
        concurrency=concurrency,
        environment=environment,
        render_js=render_js,
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
    comp_analyses = []
    if keyword:
        if not quiet:
            console.print(f"[cyan]Scraping SERP & Competitors for query: '[bold yellow]{keyword}[/bold yellow]'...[/cyan]")
        analyzer = CompetitorAnalyzer()
        comp = analyzer.analyze_for_keyword(target_keyword=keyword, your_url=url)
        comp_analyses.append(comp)

    report: SEOReport = report_gen.generate_report(crawl_result, competitor_analyses=comp_analyses, environment=environment)

    # CLI Terminal Display
    if not quiet and output_format != "json":
        score_color = "green" if report.overall_score >= 85 else ("yellow" if report.overall_score >= 65 else "red")
        stats = report.summary_stats or {}
        status_col = "green" if report.audit_status == "PASS" else ("cyan" if report.audit_status == "STAGING_PROTECTED" else "red")
        console.print()
        console.print(Panel.fit(
            f"Overall Health Score: [bold {score_color}]{report.overall_score:.0f}/100[/bold {score_color}] | Release Status: [bold {status_col}]{report.audit_status}[/] ({report.environment_intent.upper()})\n"
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
            "summary_stats": report.summary_stats,
            "category_scores": {k: {"name": cs.name, "score": cs.score, "tests_passed": cs.tests_passed, "tests_evaluated": cs.tests_evaluated, "deductions_count": len(cs.deductions)} for k, cs in report.category_scores.items()},
            "deductions": [{"rule": d.rule_title, "points": d.points_deducted, "reason": d.reason, "affected": d.affected_count} for d in report.all_deductions],
            "issue_clusters": [c.to_dict() for c in report.issue_clusters],
            "recommendations": report.recommendations,
            "orphaned_pages": crawl_result.orphaned_pages,
            "remediation_plan": report.remediation_plan.to_dict() if getattr(report, "remediation_plan", None) else None,
            "verifications": [v.to_dict() for v in getattr(report, "verifications", [])],
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
def serp(keyword: str, compare: Optional[str], results: int):
    """Scan Google/DuckDuckGo/Bing search results and benchmark top competitors."""
    console.print(Panel.fit(f"[bold cyan]SERP Intelligence[/bold cyan]\nQuery: [yellow]'{keyword}'[/yellow]", border_style="cyan"))

    scraper = SERPScraper()
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

        gap_color = "green" if comp_analysis.competitive_gap_score > 70 else "red"
        console.print(Panel.fit(
            f"Your URL Rank: #{comp_analysis.your_position or 'Unranked (>20)'}\n"
            f"Competitive Gap Score: [{gap_color}]{comp_analysis.competitive_gap_score}/100[/{gap_color}]",
            title="Competitor Benchmark",
        ))

        if comp_analysis.gaps:
            gap_table = Table(title="[bold yellow]Competitive Ranking Gaps[/bold yellow]")
            gap_table.add_column("Identified Deficit", style="red")
            gap_table.add_column("Recommended Fix to Outrank", style="green")
            for g, r in zip(comp_analysis.gaps, comp_analysis.recommendations):
                gap_table.add_row(g, r)
            console.print(gap_table)


@cli.command()
@click.argument("seed")
@click.option("--limit", "-l", default=30, help="Max keywords to discover.")
def keywords(seed: str, limit: int):
    """Expand seed keyword into questions, long-tail terms, and search intent groups."""
    console.print(Panel.fit(f"[bold cyan]Keyword Research & Intent Explorer[/bold cyan]\nSeed: [yellow]'{seed}'[/yellow]", border_style="cyan"))

    analyzer = KeywordAnalyzer()
    with console.status("[green]Querying Google autocomplete and clustering search intent..."):
        opps = analyzer.expand_keyword(seed, max_results=limit)

    table = Table(title=f"Discovered Keyword Opportunities for '{seed}'", show_header=True, header_style="bold magenta")
    table.add_column("Keyword", style="yellow")
    table.add_column("Search Intent", style="cyan")
    table.add_column("Recommended Content Type", style="white")

    for opp in opps:
        table.add_row(opp.keyword, opp.intent.value, opp.suggested_content_type)
    console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
