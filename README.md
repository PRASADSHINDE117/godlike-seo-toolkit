---
name: seo-toolkit
description: Complete guide for AI Agents to execute Godlike SEO audits, deep async site crawling, SERP scraping, competitor reverse-engineering, search intent keyword research, authenticated Playwright testing, and multi-format reporting (Markdown, Excel, HTML, JSON).
argument-hint: "[crawl|serp|keywords|test-login] [options]"
version: 3.0.0
---

# ⚡ Godlike SEO Engine 3.0: Agent Skills & Capability Guide

The **Godlike SEO Toolkit** is a production-grade, evidence-based SEO audit engine, deep asynchronous web crawler, SERP competitor scraper, and search intent research toolkit. It is built specifically for **autonomous AI agents, developers, and CI/CD pipelines**, prioritizing **diagnostic precision, zero false positives, and reproducible mathematical scoring**.

---

## 🧭 Core Architecture & Agent Philosophy

Most traditional SEO crawlers produce noisy false alarms by naively applying static content rules to private application workflows. Godlike 3.0 solves this through three core principles that agents must understand:

1. **Intent-Aware Page Classification (`PageClassifier`)**:
   Before running any audits, every URL and HTTP response is classified into one of six categories:
   - `PUBLIC_CONTENT`: Marketing, blog, category, product, and documentation pages. Full on-page SEO evaluations apply.
   - `USER_APP_ROUTE`: Interactive user application workflows (`/wishlist`, `/my-bookings`, `/create-listing`, `/cart`, `/checkout`, `/account`). Protected from false-positive duplicate content and cannibalization flags.
   - `AUTHENTICATION`: Login, register, signup, password reset, and soft login gates (pages returning 200 OK with password fields or auth forms to unauthenticated crawlers).
   - `SYSTEM_UTILITY`: Internal API feeds, search query feeds, pagination endpoints.
   - `REDIRECT`: 3xx HTTP redirect responses.
   - `ERROR`: 4xx / 5xx HTTP error responses.

2. **Strict Separation of Observation from Inference**:
   Every diagnostic issue separates factual measurement from contextual risk:
   - **Technical Observation**: The objective, measurable fact (e.g. *"Server returned HTTP 404 for URL linked from 27 internal pages"* or *"Document does not declare a `<link rel='canonical'>` tag"*).
   - **SEO Inference & Risk**: The nuanced ranking implication (e.g. *"Breaks user navigation paths and wastes crawler budget"* vs *"On clean unique URLs, Google defaults to indexing the request URL; canonical tag is a defensive safeguard"*).

3. **Transparent, Itemized Mathematical Scoring**:
   Scores begin at `100.0` points per category and are reduced by calibrated deductions per **unique root-cause issue cluster** (not raw occurrence counts):
   - **Critical Blocker (`-15.0 pts`)**: Directly blocks crawling or indexation (HTTP 5xx crashes, invalid SSL).
   - **High Risk (`-8.0 pts`)**: Significantly degrades visibility (duplicate titles across public pages, broken internal links).
   - **Medium Risk (`-3.0 pts`)**: Measurable ranking/UX defect (thin content, parameterized URL missing canonical).
   - **Low Risk (`-1.0 pts`)**: Minor refinement (title too long/short, image missing explicit dimensions / CLS risk).
   - **Informational (`0.0 pts`)**: Growth opportunities (Schema.org rich snippet opportunity, defensive self-referencing canonicals).

---

## 🛠️ Complete Tool & Capability Inventory

The toolkit is accessible via CLI (`python -m godlike_seo`) or directly via Python SDK (`import godlike_seo`).

### 1. Asynchronous Site Crawler (`godlike_seo.crawler`)
- **Deterministic URL Normalization**: RFC 3986 normalization strips tracking parameters (`utm_*`, `fbclid`, `gclid`), unifies encoded characters (`%20` and `+`), standardizes trailing slashes, and eliminates default ports.
- **Dual-Pass Extraction**: Case-insensitive DOM parsing + regex fallback captures `<meta name="viewport">`, `<link rel="canonical">`, `<title>`, `<meta name="description">`, and OpenGraph/Twitter cards even in malformed HTML.
- **Link Graph & Internal PageRank**: Full directed link graph with anchor text placement (nav, body, footer) and internal equity distribution (Power Iteration, damping = 0.85).
- **Context-Aware Orphan Detection**: Compares discovered URLs against sitemap.xml while strictly filtering out private application routes and login gates.
- **Robots.txt & Sitemap Discovery**: Parses `robots.txt` directives, detects sitemap declarations, and traverses XML sitemap indices.
- **Redirect Tracing**: Traces complete multi-hop redirect chains and detects infinite loops.

### 2. Evidence-Based Issue Detector (`godlike_seo.analyzers.issue_detector`)
- Evaluates 80+ technical ranking factors with concrete DOM/Header code snippets.
- **Inlink-Calibrated 404s**: Broken links linked internally (`inlinks > 0`) are categorized as `HIGH` priority; unlinked 404s (`inlinks == 0`) are categorized as `MEDIUM` (sitemap ghost / external backlink).
- **True Duplicate Detection**: SHA-256 content hashing excluding scripts/styles, evaluated strictly across `PUBLIC_CONTENT` pages.
- **Root-Cause Clustering**: Consolidates repetitive site-wide issues (e.g. 50 images missing dimensions across 10 pages) into a single actionable cluster with sample evidence.

### 3. Deep Content & Lexical Analyzer (`godlike_seo.analyzers.content_analyzer`)
- **Readability Scoring**: Computes Flesch Reading Ease and Flesch-Kincaid Grade Level.
- **Corpus-Wide TF-IDF**: Extracts top characteristic topical terms per page across all crawled documents.
- **N-gram Extraction**: 1-gram, 2-gram, and 3-gram phrase frequency analysis with English stopword removal.
- **Non-Destructive Cannibalization**: Flags genuine keyword conflict only on substantial public content (`word_count >= 150`), providing intent differentiation advice rather than destructive 301 redirects.

### 4. Technical Infrastructure & Security (`godlike_seo.analyzers.technical_analyzer`)
- **SSL/TLS Validation**: Socket-level certificate handshake, expiration countdown, cipher suite, and TLS version.
- **Security Headers**: HSTS, Content-Security-Policy (CSP), X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
- **Server TTFB & Compression**: Measures Time-to-First-Byte and audits Brotli / Gzip compression and Cache-Control headers.

### 5. SERP Intelligence & Competitor Reverse-Engineering (`godlike_seo.serp`)
- **Multi-Engine Search**: Scrapes Google organic search with automatic fallback to Bing and DuckDuckGo (including base64 redirect resolution).
- **Competitor Benchmarking**: Fetches and analyzes top-ranking competitor URLs (word count, H1 tag, Schema markup, TTFB, keyword placement).
- **Competitive Gap Analysis**: Calculates a 0-100 Parity Score and itemizes specific deficits required to outrank competitors for any keyword.

### 6. Search Intent Keyword Explorer (`godlike_seo.serp.keyword_analyzer`)
- **Google Autocomplete Expansion**: Queries Google Autocomplete across questions (*who, what, where, how*), commercial comparisons (*best, vs, top*), and alphabetical suffixes.
- **Intent Categorization**: Categorizes phrases into `Informational`, `Commercial`, `Transactional`, or `Navigational`.
- **Content Type Mapping**: Recommends the optimal content format (Buyer's Guide, FAQ, In-depth Tutorial, or High-Converting Landing Page).

### 7. Playwright Headless Authentication (`godlike_seo.auth`)
- **Automated Login**: Locates email/username, password fields, and submit buttons using Playwright.
- **Credentials Support**: Reads credentials from key-value text files (`user details/user info.txt`), JSON files, CLI arguments, or raw cookies.
- **Cookie Injection**: Extracts session cookies and injects them directly into `aiohttp` crawl sessions to audit pages behind login walls.

### 8. Multi-Format Report Engine (`godlike_seo.reports`)
- **Markdown (`.md`)**: Token-efficient, dense, and structured for LLM context windows, AI agent reasoning, and GitHub issues.
- **Excel (`.xlsx`)**: Multi-tab workbook (`Summary & Health`, `Actionable Issue Clusters`, `All Evaluated Pages` with Technical Intent Classification, `Orphaned Pages`, `Internal Link Graph`).
- **Interactive HTML (`.html`)**: Standalone zero-dependency SVG dashboard with observation-inference cards and page inventory.
- **JSON (`.json`)**: Machine-readable JSON payload for pipeline streaming.

---

## 💻 CLI Commands & Syntax for AI Agents

All commands are executed via terminal using `python -m godlike_seo`.

### Command 1: `crawl`
Crawls a website, identifies issues, and generates multi-format reports.

```bash
python -m godlike_seo crawl <URL> [OPTIONS]
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--max-pages` | `-m` | Maximum pages to crawl | `200` |
| `--depth` | `-d` | Maximum click depth from start URL | `3` |
| `--concurrency` | `-c` | Number of concurrent async workers | `10` |
| `--format` | `-f` | Report format: `all`, `md`, `xlsx`, `html`, `json` | `all` |
| `--output` | `-o` | Specific destination file path | Auto |
| `--output-dir` | | Directory to store generated reports | Current Dir |
| `--keyword` | `-k` | Target search query to benchmark ranking against | `None` |
| `--auth-file` | | Path to credentials file (e.g. `user details/user info.txt`) | Auto-detect |
| `--login-url` | | URL of the login form | `None` |
| `--username` | `-u` | Login username or email | `None` |
| `--password` | `-p` | Login password | `None` |
| `--auth-cookie`| | Raw cookie string (`session=xyz; token=abc`) | `None` |
| `--quiet` | `-q` | Agent mode: Suppresses terminal banners, outputs filepaths or JSON | `False` |

#### Agent Quick Examples:
```bash
# 1. Full Audit with Markdown + Excel + HTML outputs
python -m godlike_seo crawl https://example.com --format all --output-dir "reports"

# 2. Quiet JSON Stream for Automated Pipelines
python -m godlike_seo crawl https://example.com --format json --quiet

# 3. Authenticated Crawl Behind Login Wall
python -m godlike_seo crawl https://example.com --auth-file "user details/user info.txt"

# 4. Crawl + Competitive Gap Analysis for a Target Search Query
python -m godlike_seo crawl https://example.com -k "camping tent rental" --format md
```

---

### Command 2: `serp`
Scans live search results for any query, reverse-engineers top ranking URLs, and benchmarks your page against them.

```bash
python -m godlike_seo serp "<KEYWORD>" [OPTIONS]
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--compare` | `-c` | Your page URL to benchmark against top ranking results | `None` |
| `--results` | `-n` | Number of search results to retrieve | `10` |

#### Agent Quick Example:
```bash
python -m godlike_seo serp "camera rental mumbai" --compare "https://example.com/cameras"
```

**Output provided to Agent:**
- Organic rankings #1 to #10 (domains, URLs, title tags, snippets).
- Comparative parity metrics: Word count, H1 heading, Schema usage, TTFB latency.
- Itemized competitive gap checklist (e.g. *"Target keyword missing from H1"*, *"Competitors average 1,500 words vs your 600 words"*).

---

### Command 3: `keywords`
Expands a seed topic into Google Autocomplete variations, long-tail terms, questions, and intent categories.

```bash
python -m godlike_seo keywords "<SEED_KEYWORD>" [OPTIONS]
```

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--limit` | `-n` | Maximum keyword suggestions to return | `30` |

#### Agent Quick Example:
```bash
python -m godlike_seo keywords "tent rental" --limit 20
```

**Output provided to Agent:**
- Discovered long-tail phrases and question queries.
- Classified search intent: `Commercial`, `Informational`, `Transactional`, `Navigational`.
- Recommended content format: Comparison Table, Buyer's Guide, FAQ section, or Conversion Landing Page.

---

### Command 4: `test-login`
Verifies automated authentication credentials using Playwright headless browser before running large crawls.

```bash
python -m godlike_seo test-login <LOGIN_URL> [OPTIONS]
```

| Option | Flag | Description |
| :--- | :--- | :--- |
| `--auth-file` | Path to credentials file (e.g. `user details/user info.txt`) |
| `--username`, `-u` | Login username/email |
| `--password`, `-p` | Login password |

---

## 🐍 Programmatic Python SDK for AI Agent Scripts

AI agents can import `godlike_seo` directly within Python scripts or workflows without spawning shell processes:

```python
import asyncio
from godlike_seo.crawler import SEOCrawler, CrawlerConfig
from godlike_seo.reports import ReportGenerator
from godlike_seo.serp import CompetitorAnalyzer, KeywordAnalyzer

async def audit_site(target_url: str, target_keyword: str):
    # 1. Configure and run deep crawler
    config = CrawlerConfig(max_pages=50, max_depth=3, concurrency=10)
    crawler = SEOCrawler(config=config)
    crawl_result = await crawler.crawl(target_url)

    # 2. Competitor reverse-engineering
    comp_analyzer = CompetitorAnalyzer()
    comp_analysis = comp_analyzer.analyze_for_keyword(target_keyword, target_url)

    # 3. Generate structured mathematical report
    report_gen = ReportGenerator()
    report = report_gen.generate_report(crawl_result, competitor_analyses=[comp_analysis])

    # 4. Access structured data
    print(f"Health Score: {report.overall_score}/100")
    for cluster in report.issue_clusters:
        print(f"[{cluster.severity.value}] {cluster.title}: {cluster.recommendation}")
        print(f"  Observation: {cluster.observation}")
        print(f"  SEO Inference: {cluster.inference}")

    return report

# Run
asyncio.run(audit_site("https://example.com", "best tent rental"))
```

---

## 📊 How Agents Should Parse & Act on Outputs

### 1. Parsing the Markdown Report (`.md`)
The generated `.md` report is optimized for LLMs. Agents should follow this parsing strategy:
- **Executive Overview**: Check `Overall Health Score` and `Critical Blockers`.
- **Category Breakdown & Deductions**: Identify which categories lost points and review the itemized deductions table.
- **Evidence-Based Findings**:
  - Read `Technical Observation` for the verified code condition.
  - Read `SEO Inference & Risk` for the search engine consequence.
  - Read `Recommended Fix` and `Verification Step` to generate code patches.
- **Evaluated Page Inventory**: Check `Technical Intent` column (`public_content`, `user_app_route`, `authentication`) to understand how each route was categorized.

### 2. Parsing the Multi-Tab Excel Report (`.xlsx`)
- **Tab 1 (`Summary & Health`)**: High-level KPIs, category scores, and weights.
- **Tab 2 (`Actionable Issue Clusters`)**: Complete table with `Severity`, `Title`, `Technical Observation`, `SEO Inference`, `Recommended Fix`, and `Sample Evidence`.
- **Tab 3 (`All Evaluated Pages`)**: Granular per-URL telemetry (HTTP status, Technical Classification, TTFB, Word Count, Inlinks, Outlinks, Canonical).
- **Tab 4 (`Orphaned Pages`)**: Isolated indexable URLs needing navigation links.
- **Tab 5 (`Internal Link Graph`)**: Source -> Target internal link mapping.

### 3. Parsing the JSON Payload (`.json`)
```json
{
  "url": "https://example.com",
  "overall_score": 96.0,
  "summary_stats": {
    "total_pages_crawled": 34,
    "unique_issue_clusters": 7,
    "critical_clusters_count": 0,
    "orphaned_pages_count": 0
  },
  "issue_clusters": [
    {
      "issue_id": "HTTP_404_INTERNAL_LINKED",
      "severity": "high",
      "category": "technical",
      "title": "Broken Internal Link (HTTP 404 Not Found)",
      "observation": "Server returned HTTP status 404 for actively linked URL.",
      "inference": "Breaks user navigation and wastes crawl budget.",
      "affected_urls": ["https://example.com/privacy"],
      "recommendation": "Update or remove internal links pointing to this URL."
    }
  ]
}
```

---

## 📋 Agent Action Checklist for Common Issues

When an agent is tasked with fixing issues detected by Godlike SEO 3.0, follow this standard procedure:

| Detected Issue ID | Agent Remediation Workflow |
| :--- | :--- |
| `HTTP_404_INTERNAL_LINKED` | Grep codebase for the broken URL string across templates/components (`href="/broken"`). Replace with active route or implement a 301 redirect in web server config (`nginx.conf` or framework routes). |
| `DUPLICATE_TITLE_TAG` | Open page templates/metadata configs. Ensure dynamic or distinct `<title>` strings reflecting the specific page content (e.g. append `Category Name \| Brand`). |
| `IMAGE_MISSING_DIMENSIONS` | Inspect template `<img>` tags. Add explicit `width` and `height` attributes matching natural image aspect ratio, or apply CSS `aspect-ratio: auto;` to prevent layout shifts (CLS). |
| `MISSING_CANONICAL_WITH_QUERY` | In page `<head>`, dynamically render `<link rel="canonical" href="<clean_base_url>">` stripping query parameters. |
| `KEYWORD_CANNIBALIZATION_RISK` | Audit search intent of the competing URLs. If they serve different intents, differentiate the primary H1 and Title keywords. If intents are identical, consolidate content to the strongest URL. |
| `OPPORTUNITY_SCHEMA_MARKUP` | Generate JSON-LD script block (`<script type="application/ld+json">`) with appropriate Schema.org type (`Organization`, `Product`, `Article`, `FAQPage`) and insert into `<head>`. |
| `ORPHANED_PAGE_DETECTED` | Add an internal anchor link from a relevant category hub, parent section, or blog post so search bots can traverse to this public page naturally. |

---

## 🔒 Authenticated Crawling Credentials Format

When crawling behind authentication, place user credentials in `user details/user info.txt` using either key-value or JSON syntax:

**Key-Value Format:**
```ini
login_url = https://example.com/login
username = user@example.com
password = SecretPassword123
```

**JSON Format:**
```json
{
  "login_url": "https://example.com/login",
  "username": "user@example.com",
  "password": "SecretPassword123"
}
```

The crawler will automatically detect this file, trigger headless Playwright authentication, extract session state, and crawl protected pages.
