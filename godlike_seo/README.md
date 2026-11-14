# ⚡ Godlike SEO Engine 2.0

> Evidence-backed, developer-grade SEO & web testing diagnostic engine built for **Software Engineers**, **Technical SEO Auditors**, and **Autonomous AI Agents**.

---

## 🌟 What's New in 2.0

- **Zero False-Positive Guarding**: On-page SEO checks strictly run on validated 200 OK indexable HTML documents. Viewport meta tags, canonicals, and headings are extracted using dual-pass DOM & regex parsers.
- **Deterministic RFC 3986 URL Normalization**: Automatically normalizes trailing slashes (`/` vs no-slash), percent encodings (`%20` vs `+`), and strips tracking parameters (`utm_*`, `fbclid`). No more fake duplicate-content warnings.
- **Root-Cause Issue Clustering**: Aggregates hundreds of repetitive raw notices into **unique root-cause problem clusters** with impact assessments, confidence ratings, and sample DOM evidence.
- **Transparent Mathematical Scoring**: Category scores are calculated from itemized point deductions with clear pass/fail criteria (no opaque decorative numbers).
- **Automated User Login (Playwright)**: Full support for authenticated crawling behind login walls using Playwright headless browser form submission or session cookies.
- **Multi-Format Developer & AI Exports**:
  - 📊 **Excel (`.xlsx`)**: Multi-tab formatted workbooks (Summary, Issue Clusters, All Evaluated Pages, Orphaned Pages, Internal Link Graph).
  - 📝 **Markdown (`.md`)**: Token-efficient, structured reports optimized for LLMs, Agentic AIs (Claude, GPT, Gemini), and GitHub PR summaries.
  - 🌐 **Interactive HTML (`.html`)**: Standalone SVG audit dashboard.
  - 🤖 **Structured JSON (`.json`)**: Machine-parseable output for programmatic pipelines.

---

## 🚀 CLI Quick Start

### 1. Full Multi-Format Audit (HTML, MD, Excel, JSON)
```bash
# Run crawl and generate all 4 report formats in one command:
python -m godlike_seo crawl https://yourwebsite.com --max-pages 50 --format all --output-dir ./reports
```

### 2. Export Specifically for Agentic AIs (`.md` or `.json`)
```bash
# Generate a token-optimized Markdown report for AI agent ingestion:
python -m godlike_seo crawl https://yourwebsite.com --format md --output audit.md

# Emit raw machine-parseable JSON directly to stdout for piping:
python -m godlike_seo crawl https://yourwebsite.com --format json --quiet
```

### 3. Professional Multi-Tab Excel Workbook (`.xlsx`)
```bash
# Export spreadsheet with Summary, Clusters, Evaluated Pages, and Link Graph:
python -m godlike_seo crawl https://yourwebsite.com --format xlsx --output audit.xlsx
```

### 4. Authenticated Crawling Behind User Login Walls
You can authenticate via credentials file, CLI flags, or raw session cookies:

```bash
# Option A: Automatic authentication using credentials file ('user details/user info.txt'):
python -m godlike_seo crawl https://yourwebsite.com --auth-file "user details/user info.txt"

# Option B: Automated Playwright form login:
python -m godlike_seo crawl https://yourwebsite.com \
  --login-url https://yourwebsite.com/login \
  --username "admin@example.com" \
  --password "SecretPassword123"

# Option C: Direct session cookie injection:
python -m godlike_seo crawl https://yourwebsite.com --auth-cookie "session_id=abc123xyz; token=eyJ..."

# Test your Playwright login credentials and inspect captured cookies:
python -m godlike_seo test-login https://yourwebsite.com/login -u "admin@example.com" -p "SecretPassword123"
```

#### Credentials File Format (`user details/user info.txt`)
Supports either key-value pairs or JSON:
```ini
login_url=https://yourwebsite.com/login
username=admin@example.com
password=SecretPassword123
```
Or JSON:
```json
{
  "login_url": "https://yourwebsite.com/login",
  "username": "admin@example.com",
  "password": "SecretPassword123"
}
```

### 5. SERP Intelligence & Competitor Benchmarking
```bash
# Benchmark your page against top 10 Google/Bing rankings for a search query:
python -m godlike_seo serp "custom leather boots" --compare https://yourwebsite.com/boots
```

### 6. Search Intent Keyword Research
```bash
# Expand seed keywords into Informational, Commercial, and Transactional clusters:
python -m godlike_seo keywords "seo audit tool" --limit 25
```

---

## 🏛️ Project Structure

```
godlike_seo/
├── __init__.py               # Exports and version 2.0.0
├── __main__.py               # Module execution entry point
├── cli.py                    # Developer & AI Agent CLI interface
├── crawler.py                # Asynchronous multi-worker crawler with Playwright auth
├── auth.py                   # Automated Playwright login & session cookie extractor
├── database.py               # SQLite storage with aiosqlite
├── models.py                 # Evidence-backed dataclasses (SEOIssue, IssueCluster, etc.)
├── utils/
│   ├── __init__.py
│   └── url_normalizer.py     # RFC 3986 deterministic URL normalization
├── analyzers/
│   ├── issue_detector.py     # Root-cause issue clustering & evidence validation
│   ├── content_analyzer.py   # Readability (Flesch), TF-IDF, Cannibalization
│   ├── technical_analyzer.py # SSL/TLS, Security Headers, TTFB profiling
│   └── link_analyzer.py      # Internal PageRank (0-100), Orphaned Pages, Click Depth
├── serp/
│   ├── serp_scraper.py       # Google, DuckDuckGo & Bing SERP scraper
│   ├── competitor_analyzer.py# On-page ranking factor reverse-engineering
│   └── keyword_analyzer.py   # Autocomplete expansion & intent clustering
└── reports/
    ├── report_generator.py   # Transparent scoring & itemized deductions
    ├── html_report.py        # Standalone SVG dashboard generator
    ├── markdown_report.py    # Agentic AI & Developer Markdown generator
    └── excel_report.py       # Multi-tab openpyxl spreadsheet generator
```
