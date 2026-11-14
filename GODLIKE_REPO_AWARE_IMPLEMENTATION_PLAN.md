# GODLIKE SEO TOOLKIT — REPOSITORY-AWARE IMPLEMENTATION PLAN

**Document type:** Execution brief for an AI coding agent  
**Prepared:** 15 November 2026  
**Repository:** https://github.com/PRASADSHINDE117/godlike-seo-toolkit  
**Target branch:** `main` (create a feature branch before edits)  
**Priority:** Correctness and safety first; rendering and AI assistance later  
**Status:** Based on inspection of the public repository files. The agent must clone the exact current commit and run the test suite before changing code. This document is not a claim that tests have been run locally.

---

## 0. Mission

Improve the existing Godlike SEO toolkit in-place. Do not replace it with a new crawler or rewrite the project around a new framework.

The toolkit already has a useful Python foundation: an asynchronous `aiohttp` crawler, BeautifulSoup extraction, page-intent classification, deterministic issue detection, a link analyzer, an audit/report generator, Excel/HTML/Markdown/JSON exports, a CLI, Playwright-based login support and an agent skill definition.

The job is to make those components produce trustworthy, traceable results. Do not add checks simply to increase the advertised check count. Fix the existing correctness gaps, build regression tests from the real failures, and only then add an AI adjudication layer.

### Non-negotiable engineering rules

1. Deterministic facts come from code and captured evidence, not an LLM: response status, response headers, HTML elements, canonical directives, URL normalization, link counts, redirects, timings and graph calculations.
2. Every issue must link to its evidence, affected URLs, page classification, rule ID and rule version.
3. Do not treat an unexecuted or unavailable test as passed.
4. Missing canonical, short content, title length and multiple H1s must not be presented as guaranteed ranking penalties.
5. Do not crawl through robots restrictions, CAPTCHA, authentication or bot protection by bypassing them.
6. Do not submit credentials or cookies to an unapproved origin.
7. AI may evaluate interpretation and write explanations; it may not invent technical facts or overwrite deterministic measurements.
8. Preserve the existing Python architecture unless a measured technical constraint requires a change.

## 1. Repository map and current baseline

The inspected repository describes this layout:

```text
godlike-seo-toolkit/
├── godlike_seo/
│   ├── analyzers/
│   │   ├── content_analyzer.py
│   │   ├── issue_detector.py
│   │   ├── link_analyzer.py
│   │   ├── page_classifier.py
│   │   └── technical_analyzer.py
│   ├── reports/
│   │   ├── excel_report.py
│   │   ├── html_report.py
│   │   ├── markdown_report.py
│   │   └── report_generator.py
│   ├── serp/
│   ├── utils/url_normalizer.py
│   ├── auth.py
│   ├── cli.py
│   ├── crawler.py
│   ├── models.py
│   └── setup.py
├── skills/godlike-seo/
│   ├── SEO.md
│   └── SKILL.md
├── tests/test_audit_engine.py
├── HANDOFF.md
├── LICENSE
├── README.md
├── SEO.md
└── requirements.txt
```

### Existing strengths to retain

- Async HTTP fetching via `aiohttp` rather than a heavyweight browser for every URL.
- Page classification before applying content checks.
- Separate observation and inference fields on issue records.
- Normalized URL comparison and issue clustering.
- Link analysis with inbound/outbound link and PageRank calculations.
- Structured `PageData`, issue and report models.
- Multi-format report generation.
- A CLI and importable Python API.
- Playwright already exists for authenticated login workflows.

### First action required from the coding agent

1. Clone the repository and record the exact commit SHA, branch and dirty status.
2. Run `python -m unittest discover -s tests -t .` from the repository root.
3. Run a clean dependency installation in a fresh environment.
4. Generate baseline reports for the checked-in fixtures and one controlled local test site.
5. Save test output and baseline JSON before code changes.
6. Do not use a live production site as the first regression fixture.

The GitHub `HANDOFF.md` reports 12 passing tests. The agent must verify the current branch rather than assume the handoff remains accurate.

---

## 2. Confirmed repository-specific defects to address

These are not generic suggestions. They are based on the current public source files inspected for this repository. Re-check each against the exact cloned commit before editing.

### P0 — TLS certificate verification is disabled by default

**File:** `godlike_seo/crawler.py`  
**Relevant code:** `CrawlerConfig.verify_ssl` defaults to `False`; the value is passed to `aiohttp.TCPConnector(ssl=...)` and to `session.get(..., ssl=...)`.

**Why this matters:** In aiohttp, `ssl=False` disables certificate verification. A normal audit therefore makes HTTPS requests without the default certificate validation. The separate technical analyzer's TLS checks do not make the crawler's own HTTP connection safe.

**Required fix:**

- Change the default to certificate verification enabled.
- Keep an insecure override only as an explicit advanced diagnostic option, disabled by default, with a strong warning in CLI and report metadata.
- Do not use the insecure override to make invalid websites appear healthy.
- Add tests proving the default connector verifies certificates and explicit override behaviour is opt-in.

**Acceptance:** A default crawl rejects an invalid/untrusted TLS certificate; an explicit diagnostic override is clearly marked in the audit metadata.

### P0 — `render_js` is declared but no rendering path uses it

**File:** `godlike_seo/crawler.py`  
**Relevant code:** `CrawlerConfig.render_js` is declared, but inspection found no other use of this setting in that file. Playwright usage documented in `HANDOFF.md` and `auth.py` is for login/authentication, not a general source-vs-rendered SEO crawl.

**Why this matters:** A configuration option that appears to enable rendering but does nothing is misleading. JavaScript-heavy sites can return a minimal app shell to the HTTP crawler while the browser later renders the real title, content, links or canonical.

**Required fix:**

- Implement a separate optional Playwright renderer, enabled only for pages that need it; or remove the setting until it is implemented. Do not leave a nonfunctional flag.
- Keep HTTP-first crawling as the default.
- Render pages selectively when source HTML appears incomplete, metadata/links are missing, or the user requests browser rendering.
- Persist source DOM and rendered DOM as separate evidence snapshots.
- Compare title, description, robots, canonical, headings, visible text and discovered links between both views.
- Record render status, final URL, browser errors and failed first-party requests.
- Never submit forms or execute destructive actions during normal SEO rendering.

**Acceptance:** A fixture with content injected by JavaScript has a different source and rendered snapshot; rendered mode detects the visible content and links; non-render mode remains fast and deterministic.

### P0 — Canonical absence is incorrectly represented as self-canonical

**File:** `godlike_seo/crawler.py`  
**Relevant code:** `is_self_canonical` is initialised to `True`; it is only changed when a declared canonical points somewhere else. If no canonical tag exists, the code still describes the page as `self-canonical` in `indexability_reason`.

**Why this matters:** A missing canonical and an explicit self-referencing canonical are different observations. This produced a contradiction in the SharePal audit workbook: blank `Canonical URL` cells while the indexability reason said “self-canonical”.

**Required fix:** Replace the boolean-only representation with an explicit canonical state, at minimum:

- `missing`
- `self_referencing`
- `cross_url`
- `invalid`
- `multiple`
- `unparseable`

Retain the actual raw href, resolved href, normalized href and final page URL. Do not mark a missing canonical as a self-canonical. Do not automatically mark a page non-indexable merely because a canonical tag is absent. Treat canonical choice and indexability directives as separate fields.

**Acceptance:** Test absent, explicit self, relative self, cross-canonical, malformed href, multiple tags and redirected URL cases. The workbook and JSON must report the same state.

### P0 — Sitewide noindex rule counts every crawled URL and reports only one affected URL

**File:** `godlike_seo/analyzers/issue_detector.py`  
**Relevant code:** `_check_sitewide_noindex()` computes `len(noindex_pages) / len(pages)` over every crawled page and triggers at 70%. It then creates one issue whose `affected_url` is only `pages[0].url`, even though the description claims that dozens of pages are blocked.

**Why this matters:** Private app routes, login routes, utility URLs, redirects and error pages may be expected to be non-indexable. They should not inflate the denominator for public-site indexability. A cluster with one affected URL is also inconsistent with a 40-of-40 finding.

**Required fix:**

- Calculate coverage over eligible public HTML pages only (`PUBLIC_CONTENT`), and report excluded page counts by type.
- Keep authentication, user-app, system-utility, redirect and error pages visible as separate classifications, not as public-page indexation failures.
- Store the full affected URL list or a complete per-page evidence collection on the issue cluster.
- Include exact numerator, denominator and percentage: for example, `38 / 40 public HTML pages`.
- Make deployment intent explicit: `production`, `staging`, `development` or `unknown`. Do not infer this solely from a hostname or TLD.
- If the environment is `staging` and noindex is intentional, report an informational environment status rather than a production-critical SEO blocker.
- If environment is `unknown`, state the technical observation and require environment confirmation before asserting business impact.
- Keep per-page meta robots and X-Robots-Tag findings independently visible.

**Acceptance:** A site with 20 public pages and 20 private routes where only private routes are noindex must not trigger a public-sitewide blocker. A production fixture where all public pages are noindex must trigger a critical gate and list all blocked public pages. A staging fixture must be classified as intentional when the audit config says staging.

### P0 — Score and “tests passed” fields are not actual executed test results

**File:** `godlike_seo/reports/report_generator.py`  
**Relevant code:** Category test counts are hard-coded (`10, 8, 6, 6, 4, 5`). `tests_passed` is calculated as `total_tests - len(deductions)`, not from an execution ledger of checks that were actually run and passed.

**Why this matters:** A fixed denominator cannot reveal which checks ran, which were skipped, which could not be measured, and which returned inconclusive. A cluster can also represent many affected pages while consuming one deduction. The report can therefore look more certain and complete than the evidence supports.

**Required fix:**

- Introduce a `RuleResult`/`CheckResult` model with `rule_id`, `rule_version`, category, status (`pass`, `fail`, `skipped`, `inconclusive`, `not_applicable`), affected URL(s), evidence, reason and execution timestamp.
- Compute the executed denominator from actual rule results, not constants.
- Never count skipped, unsupported or failed-to-measure checks as passed.
- Separate detection coverage from issue severity and from score deductions.
- Display coverage per category and overall, including unavailable data.
- Add a confidence/coverage indicator beside the score.
- Keep cluster-level deductions if desired, but expose affected URL count and scope. Do not let high-impact blockers be hidden behind a high weighted average.
- Add a score gate: if the intended public pages are confirmed globally noindex in a production environment, status must read `INDEXATION BLOCKED` regardless of the numeric score.
- If there are zero eligible public/indexable pages to assess, orphan-page checks must be `not_applicable`, not a pass.

**Acceptance:** Tests must prove that not-run checks do not count as passed; score inputs are reproducible; critical blockers trigger the status gate; score and coverage match in all formats.

### P0 — Link graph metrics need explicit edge semantics and complete reconciliation tests

**File:** `godlike_seo/analyzers/link_analyzer.py`  
**Relevant code:** the analyzer stores unique source-to-target targets in a set for PageRank, while also storing individual link occurrences in `outbound_internal_edges` and `inbound_details`. It populates page outlinks from `len(p.internal_links)` and inlinks from inbound details matched to the page URL.

**Why this matters:** These are different metrics. A crawl may contain multiple anchors from one source page to the same target; an edge may point to a target that was not crawled because of the page limit; and a link may point to a redirect URL while the page inventory stores the final URL. Summing unlike metrics can produce apparent contradictions or lost inlinks. Current tests validate the all-targets-crawled simple case, not these real-world cases.

**Required fix:**

- Build one canonical link-occurrence table with fields: source URL, raw href, resolved URL, normalized target URL, final target URL if known, target status if fetched, anchor text, link location, rel attributes and whether target is within the configured crawl scope.
- Maintain two clearly named graph metrics:
  - **link occurrences:** every actual `<a>` link instance;
  - **unique directed page edges:** one source-to-target relationship for PageRank/topology.
- Define counts explicitly in the workbook: `Internal link occurrences`, `Unique internal targets`, `Inbound occurrences to crawled pages`, and `Outbound occurrences from crawled pages`.
- Normalize graph source and target keys with the same URL policy used by the page inventory.
- Resolve redirect aliases so inbound links to a redirect can be attributed both to the original URL and final destination, without double counting.
- Preserve links to not-yet-crawled targets as `target_not_crawled`; do not silently discard them or pretend they belong to a crawled page.
- Derive JSON, XLSX and HTML graph values from the same graph object.
- Keep PageRank based on a documented unique-edge graph, and do not mix it with raw occurrence counts.

**Acceptance:** Cover duplicate anchors, target not crawled due to max-pages, redirects, query variants, encoded URLs, cross-subdomain boundaries, self-links and external links. Reconciliation equations must be defined for each metric and tested.

### P0 — Clean install may be missing the parser dependency

**Files:** `godlike_seo/crawler.py`, `requirements.txt`  
**Relevant code:** crawler constructs `BeautifulSoup(html, "lxml")`; `requirements.txt` lists `aiohttp`, `beautifulsoup4`, `openpyxl` and `playwright`, but does not list `lxml`.

**Required fix:** Add `lxml` as an explicit runtime dependency or implement and test a deliberate fallback parser. Document parser choice in output metadata. Run tests inside a clean environment with only declared dependencies installed.

**Acceptance:** A clean installation from the repository's documented command can crawl a local HTML fixture without `FeatureNotFound` or hidden system dependencies.

---

## 3. P1 — Crawler and URL correctness improvements

### 3.1 Stable crawler identity and robots.txt handling

**File:** `godlike_seo/crawler.py`

Current code selects user agents randomly and the fallback list includes a Googlebot user-agent string. The robots parser is checked with `_get_user_agent()` and the outgoing request obtains another `_get_user_agent()` value. With random selection, the identity checked against robots.txt can differ from the identity actually sent in the HTTP request.

Required changes:

- Use one stable, transparent Godlike user-agent per audit, and use exactly that same value for robots checks and outgoing requests.
- Do not impersonate Googlebot by default. Googlebot simulation, if ever supported, must be a clearly labelled separate diagnostic mode and must not be used to bypass access controls.
- Check the seed URL against robots policy before crawling it. The root seed is currently inserted directly into the queue.
- Record `blocked_by_robots` as a crawl coverage status, not as `noindex`.
- Read sitemap declarations from robots.txt as well as conventional sitemap paths.
- Make error handling for inaccessible or malformed robots.txt explicit and configurable; do not silently pretend full robots coverage was achieved.

### 3.2 Rate limiting and queue safety

Current code sleeps `rate_limit_delay` inside each worker. That is a per-worker delay, not a strict shared per-origin request-rate limiter.

Required changes:

- Implement a shared per-origin token bucket or equivalent scheduler.
- Respect crawl-delay when present where supported; make per-domain concurrency configurable.
- Add retry/backoff for transient 429, 503 and network failures, with a strict retry ceiling.
- Respect `Retry-After`.
- Enforce `max_pages` atomically so concurrent workers cannot overshoot the limit.
- Add crawl cancellation and predictable shutdown of workers/queues.
- Store crawl failures as page/attempt records rather than silently losing the URL.

### 3.3 URL normalisation must preserve path semantics

**File:** `godlike_seo/utils/url_normalizer.py`

Current path normalization calls `unquote_plus()` on path segments. In URL form encoding, `+` means a space in query values; in a URL path, a literal plus is a plus. Converting a literal `+` to a space can change the identity of a route.

Required changes:

- Use percent-decoding appropriate for URI paths; do not apply form-query `+` semantics to path segments.
- Keep query parsing separate from path parsing.
- Do not strip parameters that define real content, category or location pages. Keep the existing tracking-parameter list configurable and auditable.
- Preserve the original URL beside the normalized URL and record the normalization steps.
- Test literal `+`, `%2B`, `%20`, Unicode, reserved characters, encoded dot segments, duplicate slashes, trailing slashes, default ports, fragments, blank query values and repeated query keys.
- Do not assume that sorting query parameters is always safe for application semantics; use a configurable normalization policy and preserve raw query order when required.

### 3.4 Page classification should use segment-aware matching and evidence

**File:** `godlike_seo/analyzers/page_classifier.py`

Current app/auth patterns are broad substring regular expressions (for example `account`, `user`, `new-`, `edit-`, `auth`, `password`). A legitimate public route can contain one of these strings without being a private workflow.

Required changes:

- Match path segments and explicit route patterns, not arbitrary substrings.
- Support site-specific route overrides and allowlists.
- Use HTML evidence (login form, password input, authenticated shell, account controls) to strengthen classification.
- Keep classification confidence and reason, not just a category.
- Add a `REVIEW_REQUIRED`/`UNKNOWN` outcome for ambiguous pages; do not force every page into public or private.
- Re-evaluate the classification after browser rendering if the static response is an app shell.
- Include examples such as `/user-guide/`, `/accounting/`, `/new-arrivals/`, `/editors-picks/`, `/authentic-stories/` as public route regression fixtures.

### 3.5 Canonical and robots directive completeness

- Parse `meta name="robots"`, bot-specific meta names (for example Googlebot where relevant), and all X-Robots-Tag response header values.
- Parse directive tokens rather than relying only on substring checks.
- Detect multiple canonical tags, malformed canonical URLs, cross-origin canonicals and canonical chains.
- Keep robots.txt crawl blocking separate from noindex directives. A page blocked by robots.txt has not been inspected for its meta robots directive.
- Distinguish “candidate for indexing” from “Google-selected canonical”; Godlike cannot know Google's selected canonical without Search Console URL Inspection data.
- Do not describe absence of canonical as an indexability failure on every clean unique URL.
- A query parameter is not automatically disposable. `?category=...`, `?city=...` or equivalent parameters may define distinct landing pages.

### 3.6 Performance labels must describe what was measured

**File:** `godlike_seo/crawler.py` and report output

Current crawler timing uses `time.perf_counter()` around the `aiohttp` request and records elapsed time after the response is received, including connection establishment and any automatic redirect chain. This is useful HTTP request latency, but it is not the same as browser navigation TTFB or Core Web Vitals.

Required changes:

- Rename the raw field to something explicit such as `http_request_to_response_headers_ms`.
- Record redirect count, connection reuse/warm state if known, sample count and measurement method.
- Use repeated controlled measurements for performance benchmarking; report median and percentile rather than one average only.
- Never infer LCP, INP or CLS from this value.
- Integrate PageSpeed Insights/CrUX data separately and label lab vs field data.

### 3.7 Crawler security for hosted/service deployments

If Godlike is exposed as a web service or accepts untrusted URLs from users, add an outbound-request security layer:

- Allow only HTTP/HTTPS.
- Block loopback, private, link-local, multicast, reserved and cloud metadata IPv4/IPv6 ranges.
- Validate DNS answers and redirect targets to reduce SSRF and DNS-rebinding risk.
- Re-check every redirect hop and enforce an allowed-host policy.
- Never forward auth headers, bearer tokens or cookies to another origin.
- Set response body and decompressed-body limits, redirect limits and total wall-clock limits.
- Never fetch `file:`, `ftp:`, `data:` or internal service protocols.
- Keep this protection mandatory for hosted deployments; document any deliberate local-only mode.

---

## 4. P1 — SEO rule calibration: remove unsupported certainty

**Primary file:** `godlike_seo/analyzers/issue_detector.py`

### 4.1 Content word count

Current `THIN_CONTENT` rule flags every public page under 150 words as medium severity. Google does not publish a preferred word count or universal minimum for ranking.

Required change:

- Remove the fixed 150-word minimum as a ranking-quality rule.
- Retain word count as an observation/diagnostic metric.
- Evaluate page purpose, content type, user intent and whether key information is present.
- Do not penalize short contact, product, utility or transactional pages just for being short.
- Any future AI content assessment must cite the visible page text and state its limitations.

### 4.2 H1 rules

Current rule flags multiple H1s and claims they dilute topical focus and confuse screen readers. Missing H1 currently receives HIGH severity and a recommendation to add a single H1.

Required change:

- Keep extraction of headings and outline.
- Do not automatically treat multiple H1s as an SEO ranking penalty.
- Evaluate logical heading hierarchy, empty headings, skipped levels, duplicated headings and clarity of the primary page heading.
- Missing primary heading may be a content/semantic clarity recommendation, not a universal critical technical blocker.
- Separate accessibility conformance from SEO findings; do not claim a screen-reader defect solely from the number of H1 elements.

### 4.3 Title and meta-description character thresholds

Current constants are `TITLE_MIN_CHARS = 10`, `TITLE_MAX_CHARS = 65`, `META_DESC_MIN_CHARS = 70`, `META_DESC_MAX_CHARS = 160`.

Required change:

- Keep character counts as observations, not hard Google rules.
- Evaluate duplicate title/description, missing content, clarity, page intent, pixel-width preview and truncation risk.
- Phrase recommendations as guidance, not an enforced maximum.
- Reduce severity of minor length-only warnings and remove deductions where evidence shows no meaningful issue.
- Do not say Google will definitely truncate a title/description at a specific character count.

### 4.4 Duplicate titles and content

- Continue to detect actual duplicates among eligible public content pages.
- Label duplicate titles as a metadata/template issue, not automatic keyword cannibalization.
- Duplicate title severity should consider page type and whether pages have different intent.
- Content hash is a useful deterministic starting point but can miss near-duplicates and falsely group pages with dynamic text. Keep exact-duplicate detection separate from near-duplicate similarity.
- Before recommending a 301, verify the pages have the same intent and that the destination is the intended canonical target.

### 4.5 Keyword cannibalization

- Do not infer cannibalization from shared title/H1 phrases alone.
- Label phrase overlap as `potential_keyword_overlap` until Search Console data or ranking observations show multiple URLs competing for the same query and intent.
- Use Google Search Console query-to-page data (with user authorization) for stronger cannibalization diagnosis.
- Do not prescribe redirects solely from phrase overlap.

### 4.6 Staging and placeholder content

The current staging detector catches explicit markers such as `[Staging]`, staging delivery practice, no-real-fulfilment, dummy listings and Lorem Ipsum. Keep this check, but change its impact language.

- Confirmed observation: staging/test markers are visible on a public page.
- Valid user-impact inference: potential visitor confusion and reduced transaction trust.
- Do not claim a guaranteed “E-E-A-T demotion” or a quantified algorithmic penalty without evidence.
- Add more route-aware placeholder detection and record the exact matching phrase and context.
- If a host is configured as staging, report environment hygiene separately from production SEO score.

### 4.7 Structured data

- Do not recommend Product, FAQPage, Article or Organization markup indiscriminately on every URL.
- Determine eligibility from page type and actual visible content.
- Validate JSON-LD syntax and required/recommended properties separately.
- Label schema presence as eligibility/implementation information, not a guaranteed ranking boost or rich result.

---

## 5. P1 — Packaging, release metadata and documentation consistency

The inspected root listing, handoff, skill manifest and setup metadata do not agree on version/licensing/package details.

Observed discrepancies to reconcile:

- `HANDOFF.md` says Engine 3.1.0.
- README/SKILL metadata says version 3.0.0.
- Several Python module docstrings still describe components as version 2.0.
- `godlike_seo/setup.py` says package version 1.0.0.
- The repository has a GPL-3.0 license, while the setup metadata classifies the package as MIT.
- `setup.py` points to a different GitHub project URL rather than this repository.
- The inspected root listing does not show a root-level `pyproject.toml` or `setup.py`; the setup file shown is nested inside the Python package.

Required changes:

1. Establish one source of version truth (prefer root `pyproject.toml` with a single package version).
2. Make README, SKILL.md, HANDOFF.md, CLI `--version`, report metadata and Python package metadata use that version.
3. Align license declaration/classifiers with the actual LICENSE file. Do not change the license without maintainer approval.
4. Replace stale package URLs/contact details with valid project information or remove placeholders.
5. Add a clean build/install smoke test from the repository root.
6. Pin or constrain dependencies sufficiently for reproducible releases; test current and minimum supported versions.
7. Document optional Playwright browser installation separately from the base HTTP crawler.

---

## 6. P1 — Report and workbook integrity

**Files:** `godlike_seo/reports/report_generator.py`, `excel_report.py`, `html_report.py`, `markdown_report.py`, `models.py`

Required changes:

- All formats must consume the same immutable normalized `SEOReport` / `AuditResult` object.
- Include a `run_id`, UTC timestamp, tool version, code revision, crawl configuration, user-agent, environment intent, rendering mode and ruleset version.
- Report exact page totals by page type and HTTP status.
- Show URLs discovered, fetched, skipped by robots, skipped by scope, failed, redirected and rendered.
- Show rule execution status, not only issue counts.
- Show canonical state and indexability reason as separate columns.
- Show page inlinks/outlinks under explicitly defined occurrence/unique-edge semantics.
- Show complete affected URL counts and sample evidence without substituting a sample URL for the full affected set.
- Keep the HTML score and score ring synchronized with JSON numeric values (do not round differently unless the display says so).
- Add a machine-readable export schema version.
- Add tests that reload the generated XLSX and compare values to JSON, Markdown and HTML, not just check that a workbook exists.
- Prevent empty or incomplete data from displaying as a perfect 100/100 category score.

Suggested report statuses:

- `BLOCKED`: a confirmed production blocker affects the relevant scope.
- `NEEDS_REVIEW`: evidence or environment intent is ambiguous.
- `PASS`: checks executed and no failure found.
- `PARTIAL`: some checks could not execute or only part of the site was crawled.
- `NOT_APPLICABLE`: the check does not apply to this environment/page type.

Do not make “zero critical findings” look like a clean bill of health when crawl coverage is low or critical categories were not evaluated.

---

## 7. Browser rendering plan — keep the existing stack

Do not migrate to Scrapy or Crawlee just to add browser rendering. Keep `aiohttp` for the high-volume HTTP pass and integrate Playwright for selected URLs.

### Two-pass flow

```text
Audit config
  -> URL discovery (seed, robots, sitemaps, internal links)
  -> aiohttp HTTP pass
  -> BeautifulSoup extraction
  -> page classification and rule checks
  -> render-needed selector
      -> Playwright render only selected pages
      -> rendered DOM extraction
      -> source/rendered diff
  -> normalized records and link graph
  -> deterministic analysis
  -> optional AI adjudication
  -> scoring gate and exports
```

### Render-needed signals

- Initial HTML contains little meaningful body content or only an app shell.
- Rendered metadata or primary content appears absent in source HTML.
- Source page has no links but browser-rendered navigation likely exists.
- Canonical, robots or structured data is injected by JavaScript.
- A user explicitly asks for rendered crawl.

### Browser evidence

Capture only what is useful:

- final URL and response status;
- rendered title, meta robots, canonical, hreflang and headings;
- visible text and internal links;
- console errors and failed first-party network requests;
- browser screenshot/trace for sampled failures or difficult diagnoses.

Do not take screenshots of every page by default. Do not let analytics/long-polling make `networkidle` the only readiness condition. Use explicit selectors and timeouts.

---

## 8. AI model strategy — optional second-opinion layer

The model is not the crawler. Do not run inference on every URL or every raw HTML page. Run it only on compact, normalized issue packets after deterministic analysis.

### Recommended starting options

| Role | Model to benchmark | Use | Caveat |
|---|---|---|---|
| Small general-purpose local reviewer | Google Gemma 4 E2B | Short evidence classification, explanations and constrained tool/JSON workflows | Verify local runtime, quantization, RAM/VRAM and structured-output reliability |
| Stronger general-purpose local reviewer | Qwen3.5-4B | Context-sensitive issue review, root-cause hypotheses and grounded recommendation drafting | Heavier than E2B; benchmark on the deployment machine |
| Specialist typed decision model | Kev-4B | Yes/no, multiple-choice and ordered-score decisions over one evidence state | Not a crawler and not a prose generator; validated context is 8,192 tokens; not validated specifically on SEO |

Do not install all models in production. First test a single general model, then compare Kev on the same labelled evidence set. If the machine cannot run a model efficiently, keep the deterministic engine and offer a remote provider only as an explicit user-configured option.

### Model provider interface

Add a provider abstraction so Godlike is not coupled to one runtime:

```python
class IssueAdjudicator(Protocol):
    async def adjudicate(self, evidence_packet: dict) -> dict:
        ...
```

Provide adapters only when needed (for example, local Transformers/Ollama-compatible serving or a self-hosted HTTP endpoint). Do not hard-code API keys or model URLs.

### AI evidence packet

For each issue, provide:

- issue ID and rule version;
- observation text;
- raw evidence (minimal necessary snippet/header/response data);
- affected URL and page type;
- requested vs final URL;
- status, canonical state, robots state and relevant inlink data;
- site environment intent (`production`, `staging`, `unknown`);
- existing severity and confidence;
- relevant source-vs-rendered comparison, where available.

### AI output contract

Require a strict JSON schema with:

- `evidence_supported`: true/false/insufficient;
- `classification`: confirmed, likely, informational, false_positive, needs_human_review;
- `severity_assessment`: critical/high/medium/low/info/unknown;
- `severity_rationale`;
- `context_missing`;
- `recommendation_validity`;
- `unsupported_claims`;
- `suggested_wording`;
- `model_confidence` and model/version identifier.

The AI must not silently change the raw observation, HTTP status, canonical href, page counts or graph metrics. It may recommend a revised interpretation for a human/rule maintainer.

### Kev-specific use

Kev-4B is a decision model. Use its `noul`, `choice` and `score` task types to answer independent questions such as:

- Does the supplied evidence prove this technical observation?
- Does the observation justify the current severity in this page/environment context?
- Is the proposed fix supported by the actual page evidence?
- Is there enough evidence to conclude keyword cannibalization?

Do not ask Kev to generate a full SEO report. Pair it with a general model only if the benchmark demonstrates a measurable benefit.

### Human review thresholds

Do not copy public model confidence values directly into production. Calibrate thresholds using labelled Godlike examples. Start with all AI recommendations advisory-only. A high-confidence model result may sort the review queue, but deterministic critical findings still need hard evidence and environment context.

---

## 9. Regression benchmark dataset — mandatory before release

Build a checked-in fixture suite. Do not use a live website as the only test corpus.

### Required fixture groups

1. **Static HTML basics:** valid H1, missing H1, multiple H1, empty title, duplicate title, long/short title, meta description, canonical variants.
2. **Example Domain:** confirm a real visible H1 is extracted. Reproduce the 14 November report's missing-H1 finding as a regression case and determine whether it was caused by the old code, response difference or parser bug.
3. **JavaScript rendering:** app shell with JS-injected title, H1, content, canonical and links.
4. **Indexability:** header noindex, meta noindex, bot-specific meta, mixed directives, robots.txt disallow, public pages vs private/authentication routes, production vs staging intent.
5. **Canonical:** absent, self, relative self, cross URL, malformed, multiple, canonical chain, query-driven category landing pages.
6. **URL routes:** `/undefined/`, `/null/`, empty slug, literal plus in path, `%2B`, `%20`, Unicode, path case, repeated query params, tracking params, category/city parameters.
7. **Links:** repeated anchor links, link to an uncrawled target, redirect alias, 404 with inlinks, orphan page, dead end, footer/nav/body links, external links.
8. **Page classification:** `/user-guide/`, `/accounting/`, `/new-arrivals/`, `/editors-picks/`, genuine `/account/`, `/login/`, a soft-login gate and an API endpoint.
9. **Performance labels:** redirects, cold/warm connection, timeout, retry, and repeated response samples. Verify that the output never labels HTTP request latency as CrUX TTFB or Core Web Vitals.
10. **Report consistency:** JSON/XLSX/HTML/Markdown must agree for every fixture.
11. **Security:** invalid TLS by default, allowed override, redirects to private IP, DNS rebinding simulation where practical, cross-origin credential redirection, body-size limit and unsupported schemes.
12. **Clean installation:** run using declared dependencies only.

### Real audit regression packs

Use the uploaded audits only as anonymized/approved fixtures, preserving sensitive information appropriately:

- `example.com`: H1 false-positive investigation, 25-word thin-content warning, no invented benchmark quality.
- `sharepal.in`: `/undefined/` route detection, category query semantics, canonical state mismatch, duplicate titles vs cannibalization, route/subdomain scope.
- `tental.versatyle.in`: noindex across the public pages vs private routes, staging marker visibility, actual affected URL count for sitewide finding, `/privacy` 404 context, source/rendered content differences.

For each fixture, keep expected labels with human reviewer notes. Never use the same pages to tune and claim final test precision; hold out a separate test split.

---

## 10. Implementation phases

### Phase 0 — Reproduce and map current behaviour

- Clone exact `main` commit.
- Run existing unit tests and clean install.
- Trace CLI -> crawler -> analyzers -> report generator -> all exporters.
- Save baseline reports and test logs.
- Deliver a short architecture map plus list of reproducible failures.

**Exit gate:** baseline is reproducible and exact code revision is recorded.

### Phase 1 — Security and request integrity (P0)

- Enable TLS verification by default.
- Stabilize user-agent identity and robots checking.
- Enforce seed URL robots policy.
- Add shared per-origin rate limiting and atomic page caps.
- Add SSRF/redirect checks for any hosted or untrusted-input deployment.
- Add response size/time/redirect limits.

**Exit gate:** security and crawler policy tests pass; no credentials leak on cross-origin redirects.

### Phase 2 — Extraction, URL normalization and indexability correctness (P0)

- Add lxml dependency or fallback.
- Fix path plus normalization.
- Add explicit canonical states.
- Improve robots/noindex parsing.
- Correct sitewide noindex denominator and affected URL collection.
- Add production/staging/unknown environment intent.
- Add boundary-aware page classification and review state.

**Exit gate:** indexability, canonical, URL and page-classification fixture suite passes.

### Phase 3 — Graph, report and score integrity (P0)

- Normalize directed link-occurrence data.
- Separate edge occurrences from unique graph edges.
- Reconcile redirect aliases and uncrawled targets.
- Implement per-rule execution ledger.
- Correct coverage and score gates.
- Make exports consume one report object and cross-validate all metrics.

**Exit gate:** graph equations and report export equality tests pass for all fixture types.

### Phase 4 — SEO rule calibration (P1)

- Remove hard 150-word ranking rule.
- Reframe H1/multiple-H1 checks.
- Replace fixed title/meta character limits with advisory display/quality guidance.
- Contextualize duplicate title and duplicate content severity.
- Downgrade keyword overlap to potential cannibalization until GSC/ranking evidence exists.
- Remove unsupported guaranteed E-E-A-T penalty language.
- Make structured data recommendations page-type and eligibility aware.

**Exit gate:** every rule has a documented signal, scope, severity rationale, evidence source and regression fixture.

### Phase 5 — Selective Playwright rendering (P1)

- Implement the actual rendering path or remove the inert `render_js` switch.
- Add source/rendered evidence records and diff output.
- Render only selected pages.
- Keep existing auth automation isolated from normal anonymous crawling.

**Exit gate:** JS fixtures pass; rendered crawl remains bounded and safe; standard HTTP crawl performance does not regress significantly.

### Phase 6 — Lightweight AI adjudication (P2)

- Add provider interface and versioned JSON schema.
- Benchmark Gemma 4 E2B and Qwen3.5-4B against the same issue packet dataset.
- Test Kev-4B for structured evidence/severity decisions as an optional specialist.
- Keep results advisory-only until precision and calibration are measured on held-out labels.
- Add `model_disabled` mode; deterministic audit must work identically without a model.

**Exit gate:** model use has measured benefit, stable structured output and safe abstention behaviour. Model failure must never break the crawl or report export.

### Phase 7 — Search and performance intelligence (P2)

- Add optional Google Search Console integration with explicit user authorization.
- Use query/page/impression/click data before making cannibalization claims.
- Integrate PageSpeed Insights and CrUX separately from crawler request timings.
- Store historical audits for trends only with explicit retention/privacy policy.

**Exit gate:** all external measurements identify source, timestamp, scope, metric definition and missing-data state.

---

## 11. Proposed release gates and metrics

These are proposed internal engineering targets, not industry-certified thresholds.

- Deterministic rule precision: target at least 95% on a held-out, human-labelled test set for rules advertised as confirmed findings.
- No P0 regression tests failing.
- Zero mismatches between exports for pages, issue clusters, affected URL counts, canonical state, inlinks/outlinks, execution status and score inputs.
- No missing-vs-self canonical contradiction.
- No noindex sitewide blocker based only on non-public routes.
- No model-generated fact may overwrite deterministic evidence.
- All not-run/not-applicable/inconclusive checks explicitly reported.
- All crawler requests must use verified TLS by default.
- No cross-origin auth credential forwarding.
- Report coverage and audit limitations must be visible before the overall score.

Track precision and recall per rule, not just as one overall model metric. A 95% global score can hide a failing critical rule.

---

## 12. Version, license and package cleanup

Before publishing another release:

1. Choose the real semantic version from one source of truth.
2. Correct the README, SKILL manifest, HANDOFF, module docstrings and CLI version together.
3. Ensure GPL-3.0 repository license and package metadata agree; maintainer approval required to change license.
4. Replace the stale `godlike-seo/godlike-seo` URL in package metadata with this repository or a real project site.
5. Move packaging metadata to the repository root (`pyproject.toml` preferred) so a clean `pip install .` or editable install works.
6. Include `lxml` if the crawler continues to require the `lxml` BeautifulSoup parser.
7. Pin tested dependency ranges and add CI on supported Python versions.
8. Add a GitHub Actions workflow for unit tests, linting, type checking and package build.
9. Never include credentials, cookies, auth files, reports from user sites or `.env` data in Git.

---

## 13. Exact instructions to the coding agent

You are acting as the senior engineer modifying the existing repository `PRASADSHINDE117/godlike-seo-toolkit`.

1. Inspect the exact current repository before editing. Do not assume this plan describes files that have changed since it was written.
2. Start by running the existing tests and a clean dependency install. Report failures before changing code.
3. Create a new feature branch. Do not commit directly to `main`.
4. Work phase by phase in the order above. Complete P0 before P1/P2. Do not jump to AI integration first.
5. Keep the current Python + aiohttp architecture. Add Playwright selectively; do not migrate to Scrapy/Crawlee unless you prove the current design cannot meet a measurable requirement.
6. For each code change, add a regression test that fails before the fix and passes after it.
7. Do not use a language model to decide facts that can be checked deterministically.
8. Do not lower severity, suppress findings or change scores merely to make the sample reports look better. Every change needs a reason and a regression test.
9. Do not run destructive actions against websites. All tests must use local fixtures or explicitly authorized targets.
10. Do not expose or log passwords, cookies, bearer tokens, private headers or browser storage state.
11. Update README, SKILL.md, HANDOFF.md and CLI help whenever behaviour changes.
12. Run all unit tests, integration tests, lint/type checks and package build at the end.
13. Generate before/after reports for the Example Domain, SharePal and Tental fixture packs. Explain exactly which previous findings changed and why.
14. Deliver a final implementation summary containing: files changed, root cause, test added, test result, performance impact, security impact, migration/config changes, known limitations and remaining tasks.
15. If an acceptance gate fails, do not claim the phase is complete. State the blocker and leave the next phase unimplemented.

### First execution task — do this before any model work

Implement and test these seven P0 fixes in order:

1. Enable TLS verification by default.
2. Add the missing `lxml` dependency or tested parser fallback.
3. Make canonical state explicit; missing is not self-referencing.
4. Correct sitewide noindex scope and capture the full affected public URL list.
5. Replace synthetic fixed test counts with a real per-rule execution ledger.
6. Rebuild link graph metrics with separate link-occurrence and unique-edge semantics.
7. Fix the inert `render_js` setting by implementing a selective Playwright renderer or removing the option until ready.

Do not start the model phase until all seven pass their acceptance tests.

---

## 14. External technical references

Use current official documentation when implementing and pin tested versions in the repository:

- Kev-4B model card: https://huggingface.co/jaredpalmer/kev-4b
- Qwen3.5-4B model card: https://huggingface.co/Qwen/Qwen3.5-4B
- Gemma 4 model card: https://ai.google.dev/gemma/docs/core/model_card_4
- Playwright documentation: https://playwright.dev/docs/intro
- aiohttp TLS documentation: https://docs.aiohttp.org/en/stable/client_advanced.html#ssl-control-for-tcp-sockets
- RFC 9309 Robots Exclusion Protocol: https://www.rfc-editor.org/rfc/rfc9309.html
- Google JavaScript SEO basics: https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
- Google canonicalization guidance: https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- Google Core Web Vitals: https://developers.google.com/search/docs/appearance/core-web-vitals
- Google Search Console API: https://developers.google.com/webmaster-tools

