"""
Godlike SEO Toolkit - Flask Web Application & REST API.

Provides an interactive web dashboard for:
- Initiating on-demand site crawls with live progress
- Inspecting visual SEO health scores, orphaned pages, and issues
- Running real-time SERP competitive comparisons
- Conducting Google autocomplete keyword research
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
import threading
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template_string, request, Response

from godlike_seo.crawler import CrawlerConfig, SEOCrawler
from godlike_seo.models import CrawlResult, SEOReport
from godlike_seo.reports.html_report import HTMLReportGenerator
from godlike_seo.reports.report_generator import ReportGenerator
from godlike_seo.serp.competitor_analyzer import CompetitorAnalyzer
from godlike_seo.serp.keyword_analyzer import KeywordAnalyzer
from godlike_seo.serp.serp_scraper import SERPScraper

app = Flask(__name__)

# In-memory store for active sessions
REPORTS_CACHE: Dict[str, SEOReport] = {}
CRAWL_STATUS: Dict[str, Dict[str, Any]] = {}

HTML_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Godlike SEO Toolkit - Control Center</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0B0F19;
            --surface: #151C2C;
            --surface-hover: #1E273D;
            --border: #242F48;
            --primary: #38BDF8;
            --accent: #6366F1;
            --text-main: #F1F5F9;
            --text-muted: #94A3B8;
            --success: #10B981;
            --warning: #F59E0B;
            --danger: #EF4444;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
        }
        .sidebar {
            width: 260px;
            background: var(--surface);
            border-right: 1px solid var(--border);
            padding: 30px 20px;
            display: flex;
            flex-direction: column;
        }
        .brand {
            font-size: 1.3rem;
            font-weight: 800;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 40px;
        }
        .brand span { color: var(--primary); }
        .nav-link {
            padding: 12px 16px;
            border-radius: 8px;
            color: var(--text-muted);
            text-decoration: none;
            margin-bottom: 8px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .nav-link.active, .nav-link:hover {
            background: var(--surface-hover);
            color: var(--primary);
        }
        .main-content {
            flex: 1;
            padding: 40px;
            overflow-y: auto;
        }
        .header {
            margin-bottom: 30px;
        }
        .header h1 { font-size: 2rem; font-weight: 800; }
        .header p { color: var(--text-muted); margin-top: 5px; }
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }
        .input-group {
            display: flex;
            gap: 12px;
            margin-top: 15px;
        }
        input, select {
            flex: 1;
            background: #0B0F19;
            border: 1px solid var(--border);
            padding: 12px 16px;
            border-radius: 8px;
            color: white;
            font-size: 1rem;
            font-family: inherit;
        }
        input:focus { outline: none; border-color: var(--primary); }
        button {
            background: linear-gradient(135deg, var(--accent) 0%, var(--primary) 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 700;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        button:hover { opacity: 0.9; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        #results-box { margin-top: 20px; }
        pre {
            background: #070A11;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: #38BDF8;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="brand">⚡ <span>Godlike</span>SEO</div>
        <div class="nav-link active" onclick="showTab('crawler')">🕷️ Deep Site Crawler</div>
        <div class="nav-link" onclick="showTab('serp')">🏆 SERP & Competitors</div>
        <div class="nav-link" onclick="showTab('keywords')">🎯 Keyword Explorer</div>
    </div>

    <div class="main-content">
        <!-- Crawler Tab -->
        <div id="tab-crawler" class="tab-content active">
            <div class="header">
                <h1>Full Website Crawler & SEO Audit</h1>
                <p>Detect 80+ critical ranking issues, find orphaned pages, and generate high-impact recommendations.</p>
            </div>
            <div class="card">
                <h3>Enter Website URL</h3>
                <div class="input-group">
                    <input type="url" id="crawl-url" placeholder="https://example.com" value="https://example.com" required>
                    <select id="crawl-env" style="max-width: 160px;">
                        <option value="">Env: Auto-Detect</option>
                        <option value="production">Production</option>
                        <option value="staging">Staging</option>
                        <option value="development">Development</option>
                    </select>
                    <input type="number" id="crawl-max" placeholder="Max Pages" value="20" style="max-width: 120px;">
                    <button onclick="startCrawl()">Run Full Audit</button>
                </div>
                <div id="crawl-progress" style="margin-top: 15px; display: none; color: var(--primary);">
                    Crawling & Analyzing... This may take a few seconds.
                </div>
            </div>
            <div id="crawl-results" class="card" style="display: none;">
                <h3>Audit Results</h3>
                <div id="crawl-summary"></div>
                <div style="margin-top: 15px;">
                    <a id="report-link" target="_blank" style="color: var(--primary); font-weight: bold; text-decoration: underline;">Open Full Interactive HTML Report →</a>
                </div>
            </div>
        </div>

        <!-- SERP Tab -->
        <div id="tab-serp" class="tab-content">
            <div class="header">
                <h1>SERP Intelligence & Competitor Comparison</h1>
                <p>Find the top 10 ranking websites on Google/DDG and discover exactly what gaps you need to close to rank #1.</p>
            </div>
            <div class="card">
                <h3>Benchmark Query</h3>
                <div class="input-group">
                    <input type="text" id="serp-keyword" placeholder="e.g. best seo tools 2026" value="best seo audit tool">
                    <input type="url" id="serp-target" placeholder="Your URL (e.g. https://example.com)" value="https://example.com">
                    <button onclick="runSerp()">Benchmark Competitors</button>
                </div>
            </div>
            <div id="serp-results" class="card" style="display: none;">
                <h3>Competitive Intelligence</h3>
                <pre id="serp-json"></pre>
            </div>
        </div>

        <!-- Keywords Tab -->
        <div id="tab-keywords" class="tab-content">
            <div class="header">
                <h1>Keyword Intent Explorer</h1>
                <p>Google autocomplete expansion and intent categorization (Informational, Commercial, Transactional).</p>
            </div>
            <div class="card">
                <h3>Seed Keyword</h3>
                <div class="input-group">
                    <input type="text" id="kw-seed" placeholder="e.g. technical seo" value="seo crawler">
                    <button onclick="runKeywords()">Discover Long-Tail Keywords</button>
                </div>
            </div>
            <div id="kw-results" class="card" style="display: none;">
                <h3>Opportunities</h3>
                <pre id="kw-json"></pre>
            </div>
        </div>
    </div>

    <script>
        function showTab(name) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + name).classList.add('active');
            event.target.classList.add('active');
        }

        async function startCrawl() {
            const url = document.getElementById('crawl-url').value;
            const maxPages = document.getElementById('crawl-max').value;
            const env = document.getElementById('crawl-env').value;
            document.getElementById('crawl-progress').style.display = 'block';
            document.getElementById('crawl-results').style.display = 'none';

            try {
                const res = await fetch('/api/crawl', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url, max_pages: parseInt(maxPages), environment: env || null})
                });
                const data = await res.json();
                document.getElementById('crawl-progress').style.display = 'none';
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }
                document.getElementById('crawl-results').style.display = 'block';

                let statusBadgeCol = '#10B981';
                if ((data.audit_status || '').includes('BLOCKED')) statusBadgeCol = '#EF4444';
                else if (['NEEDS_REVIEW', 'INSUFFICIENT_COVERAGE', 'INDEXATION_WARNING'].includes(data.audit_status)) statusBadgeCol = '#F59E0B';
                else if (data.audit_status === 'STAGING_PROTECTED') statusBadgeCol = '#60A5FA';

                document.getElementById('crawl-summary').innerHTML = `
                    <div style="display: flex; gap: 15px; align-items: center; margin: 12px 0;">
                        <span style="font-size: 1.6rem; font-weight: 800; color: ${data.overall_score >= 85 ? '#10B981' : (data.overall_score >= 65 ? '#F59E0B' : '#EF4444')};">${data.overall_score}/100</span>
                        <span style="background: rgba(255,255,255,0.08); border: 1px solid ${statusBadgeCol}; color: ${statusBadgeCol}; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.85rem;">${data.audit_status}</span>
                    </div>
                    <p style="color: #94A3B8; font-size: 0.9rem; margin-bottom: 8px;">${data.status_message}</p>
                    <p style="font-size: 0.88rem; color: #CBD5E1;"><strong>Pages Crawled:</strong> ${data.summary_stats.total_pages_crawled} | <strong>Coverage:</strong> ${data.summary_stats.crawl_coverage_pct || 100}% | <strong>Orphaned:</strong> ${data.summary_stats.orphaned_pages_count} | <strong>Critical Issues:</strong> ${data.summary_stats.critical_issues_count}</p>
                `;
                document.getElementById('report-link').href = '/report/' + data.domain;
            } catch(e) {
                alert('Crawl error: ' + e);
                document.getElementById('crawl-progress').style.display = 'none';
            }
        }

        async function runSerp() {
            const kw = document.getElementById('serp-keyword').value;
            const target = document.getElementById('serp-target').value;
            const res = await fetch('/api/serp', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({keyword: kw, target_url: target})
            });
            const data = await res.json();
            document.getElementById('serp-results').style.display = 'block';
            document.getElementById('serp-json').textContent = JSON.stringify(data, null, 2);
        }

        async function runKeywords() {
            const seed = document.getElementById('kw-seed').value;
            const res = await fetch('/api/keywords', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({seed: seed})
            });
            const data = await res.json();
            document.getElementById('kw-results').style.display = 'block';
            document.getElementById('kw-json').textContent = JSON.stringify(data, null, 2);
        }
    </script>
</body>
</html>
"""


def is_safe_target_url(url: str) -> Tuple[bool, str]:
    """Validate target URL to protect against SSRF (rejecting private, loopback, and cloud metadata targets)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported scheme '{parsed.scheme}'. Only http and https are permitted."
        
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid or missing hostname in target URL."

        # Disallow localhost/metadata names
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "metadata.google.internal", "instance-data"):
            return False, f"Target host '{hostname}' is not permitted (local or cloud metadata host)."

        # Resolve hostname to check IP safety
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_loopback:
                return False, f"Resolution to loopback IP {ip_str} is prohibited."
            if ip_obj.is_private:
                return False, f"Resolution to private RFC 1918 network IP {ip_str} is prohibited."
            if ip_obj.is_link_local:
                return False, f"Resolution to link-local IP {ip_str} is prohibited."
            if ip_obj.is_reserved or ip_obj.is_multicast:
                return False, f"Resolution to reserved IP {ip_str} is prohibited."

        return True, ""
    except Exception as e:
        return False, f"URL resolution/validation error: {e}"


@app.route("/")
def index():
    return render_template_string(HTML_DASHBOARD_TEMPLATE)


@app.route("/api/crawl", methods=["POST"])
def api_crawl():
    payload = request.get_json() or {}
    url = payload.get("url", "https://example.com").strip()
    max_pages = min(int(payload.get("max_pages", 20)), 200)
    environment = payload.get("environment")

    is_safe, err_msg = is_safe_target_url(url)
    if not is_safe:
        return jsonify({"error": f"SSRF Protection: {err_msg}"}), 400

    crawler = SEOCrawler(config=CrawlerConfig(max_pages=max_pages, max_depth=2, concurrency=5, environment=environment))
    crawl_result = asyncio.run(crawler.crawl(url))

    report_gen = ReportGenerator(environment=environment)
    report = report_gen.generate_report(crawl_result, environment=environment)

    REPORTS_CACHE[report.domain] = report

    return jsonify({
        "domain": report.domain,
        "overall_score": report.overall_score,
        "audit_status": report.audit_status,
        "status_message": report.status_message,
        "summary_stats": report.summary_stats,
        "recommendations": report.recommendations[:5],
    })


@app.route("/report/<domain>")
def view_report(domain: str):
    report = REPORTS_CACHE.get(domain)
    if not report:
        # Check if any report matches
        if REPORTS_CACHE:
            report = next(iter(REPORTS_CACHE.values()))
        else:
            return "No report found. Please run a crawl first.", 404

    html_gen = HTMLReportGenerator()
    return html_gen.render(report)


@app.route("/api/serp", methods=["POST"])
def api_serp():
    payload = request.get_json() or {}
    kw = payload.get("keyword", "")
    target = payload.get("target_url", "")

    analyzer = CompetitorAnalyzer()
    comp = analyzer.analyze_for_keyword(target_keyword=kw, your_url=target)

    return jsonify(comp.to_dict())


@app.route("/api/keywords", methods=["POST"])
def api_keywords():
    payload = request.get_json() or {}
    seed = payload.get("seed", "")

    analyzer = KeywordAnalyzer()
    opps = analyzer.expand_keyword(seed, max_results=25)

    return jsonify([{
        "keyword": o.keyword,
        "intent": o.intent.value,
        "relevance": o.relevance_score,
        "content_type": o.suggested_content_type,
    } for o in opps])


if __name__ == "__main__":
    app.run(port=5000)
