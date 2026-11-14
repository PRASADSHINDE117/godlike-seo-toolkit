"""
SQLite database manager for the Godlike SEO Toolkit.

Handles persistent storage of crawl results, historical snapshots, and
comparison data using aiosqlite for async I/O.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiosqlite

from godlike_seo.models import (
    CrawlResult,
    CrawlStatus,
    HeadingData,
    HreflangTag,
    ImageData,
    LinkData,
    OpenGraphData,
    PageData,
    RedirectHop,
    SEOIssue,
    StructuredDataItem,
    TwitterCardData,
    IssueSeverity,
    IssueCategory,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = "godlike_seo.db"
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Database Manager
# ---------------------------------------------------------------------------

class DatabaseManager:
    """Async SQLite manager for crawl data persistence.

    Usage::

        async with DatabaseManager("seo.db") as db:
            crawl_id = await db.save_crawl(crawl_result)
            result = await db.load_crawl(crawl_id)
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "DatabaseManager":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the database connection and ensure schema exists."""
        if self._conn is not None:
            return
        logger.info("Connecting to database: %s", self.db_path)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._create_schema()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed.")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() or use async with.")
        return self._conn

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def _create_schema(self) -> None:
        """Create all required tables if they do not exist."""
        await self.conn.executescript(_SCHEMA_SQL)
        await self.conn.commit()
        logger.debug("Database schema ensured (version %d).", SCHEMA_VERSION)

    # ------------------------------------------------------------------
    # Save crawl
    # ------------------------------------------------------------------

    async def save_crawl(self, result: CrawlResult) -> int:
        """Persist a full CrawlResult and return the crawl_id."""
        logger.info("Saving crawl for %s (%d pages)…", result.start_url, len(result.pages))

        cursor = await self.conn.execute(
            """
            INSERT INTO crawls (
                start_url, domain, total_pages, total_internal_links,
                total_external_links, total_images, crawl_duration_seconds,
                crawl_status, started_at, finished_at, sitemap_urls,
                orphaned_pages, errors, link_graph
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.start_url,
                result.domain,
                result.total_pages or len(result.pages),
                result.total_internal_links,
                result.total_external_links,
                result.total_images,
                result.crawl_duration_seconds,
                result.crawl_status.value,
                result.started_at,
                result.finished_at,
                json.dumps(result.sitemap_urls),
                json.dumps(result.orphaned_pages),
                json.dumps(result.errors),
                json.dumps(result.link_graph, default=str),
            ),
        )
        crawl_id = cursor.lastrowid
        assert crawl_id is not None

        # Batch-insert pages
        for page in result.pages:
            await self._save_page(crawl_id, page)

        await self.conn.commit()
        logger.info("Crawl saved with id=%d.", crawl_id)
        return crawl_id

    async def _save_page(self, crawl_id: int, page: PageData) -> int:
        """Insert a single PageData row."""
        cursor = await self.conn.execute(
            """
            INSERT INTO pages (
                crawl_id, url, final_url, status_code, content_type,
                content_length, response_time_ms, http_headers, redirect_chain,
                crawl_depth, crawled_at, title, meta_description, meta_robots,
                canonical_url, viewport_meta, language, headings,
                word_count, text_content, text_to_html_ratio,
                internal_links, external_links, images, structured_data,
                open_graph, twitter_card, hreflang_tags,
                is_indexable, is_self_canonical, found_in_sitemap,
                is_orphaned, error
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                crawl_id,
                page.url,
                page.final_url,
                page.status_code,
                page.content_type,
                page.content_length,
                page.response_time_ms,
                json.dumps(page.http_headers),
                json.dumps([{"url": h.url, "status_code": h.status_code} for h in page.redirect_chain]),
                page.crawl_depth,
                page.crawled_at,
                page.title,
                page.meta_description,
                page.meta_robots,
                page.canonical_url,
                page.viewport_meta,
                page.language,
                json.dumps([{"level": h.level, "text": h.text} for h in page.headings]),
                page.word_count,
                page.text_content[:50_000] if page.text_content else "",  # cap storage
                page.text_to_html_ratio,
                json.dumps([_link_to_dict(l) for l in page.internal_links]),
                json.dumps([_link_to_dict(l) for l in page.external_links]),
                json.dumps([_image_to_dict(i) for i in page.images]),
                json.dumps([{"format": s.format, "data": s.data, "raw": s.raw} for s in page.structured_data]),
                json.dumps(page.open_graph.raw_tags if page.open_graph else {}),
                json.dumps(page.twitter_card.raw_tags if page.twitter_card else {}),
                json.dumps([{"language": h.language, "url": h.url} for h in page.hreflang_tags]),
                page.is_indexable,
                page.is_self_canonical,
                page.found_in_sitemap,
                page.is_orphaned,
                page.error,
            ),
        )
        return cursor.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Load crawl
    # ------------------------------------------------------------------

    async def load_crawl(self, crawl_id: int) -> Optional[CrawlResult]:
        """Load a full CrawlResult by id."""
        cursor = await self.conn.execute(
            "SELECT * FROM crawls WHERE id = ?", (crawl_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        pages = await self._load_pages(crawl_id)
        return CrawlResult(
            pages=pages,
            start_url=row["start_url"],
            domain=row["domain"],
            total_pages=row["total_pages"],
            total_internal_links=row["total_internal_links"],
            total_external_links=row["total_external_links"],
            total_images=row["total_images"],
            crawl_duration_seconds=row["crawl_duration_seconds"],
            crawl_status=CrawlStatus(row["crawl_status"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            sitemap_urls=json.loads(row["sitemap_urls"]),
            orphaned_pages=json.loads(row["orphaned_pages"]),
            errors=json.loads(row["errors"]),
            link_graph=json.loads(row["link_graph"]),
        )

    async def _load_pages(self, crawl_id: int) -> List[PageData]:
        """Load all pages for a given crawl."""
        cursor = await self.conn.execute(
            "SELECT * FROM pages WHERE crawl_id = ? ORDER BY crawl_depth, url",
            (crawl_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_page(r) for r in rows]

    @staticmethod
    def _row_to_page(row: aiosqlite.Row) -> PageData:
        """Deserialise a database row into a PageData object."""
        headings_raw = json.loads(row["headings"]) if row["headings"] else []
        redirect_chain_raw = json.loads(row["redirect_chain"]) if row["redirect_chain"] else []
        internal_links_raw = json.loads(row["internal_links"]) if row["internal_links"] else []
        external_links_raw = json.loads(row["external_links"]) if row["external_links"] else []
        images_raw = json.loads(row["images"]) if row["images"] else []
        structured_data_raw = json.loads(row["structured_data"]) if row["structured_data"] else []
        hreflang_raw = json.loads(row["hreflang_tags"]) if row["hreflang_tags"] else []
        og_raw = json.loads(row["open_graph"]) if row["open_graph"] else {}
        tc_raw = json.loads(row["twitter_card"]) if row["twitter_card"] else {}

        return PageData(
            url=row["url"],
            final_url=row["final_url"] or "",
            status_code=row["status_code"],
            content_type=row["content_type"] or "",
            content_length=row["content_length"] or 0,
            response_time_ms=row["response_time_ms"] or 0.0,
            http_headers=json.loads(row["http_headers"]) if row["http_headers"] else {},
            redirect_chain=[RedirectHop(**h) for h in redirect_chain_raw],
            crawl_depth=row["crawl_depth"],
            crawled_at=row["crawled_at"] or "",
            title=row["title"] or "",
            meta_description=row["meta_description"] or "",
            meta_robots=row["meta_robots"] or "",
            canonical_url=row["canonical_url"],
            viewport_meta=row["viewport_meta"],
            language=row["language"],
            headings=[HeadingData(**h) for h in headings_raw],
            word_count=row["word_count"] or 0,
            text_content=row["text_content"] or "",
            text_to_html_ratio=row["text_to_html_ratio"] or 0.0,
            internal_links=[LinkData(**l) for l in internal_links_raw],
            external_links=[LinkData(**l) for l in external_links_raw],
            images=[ImageData(**i) for i in images_raw],
            structured_data=[StructuredDataItem(**s) for s in structured_data_raw],
            open_graph=OpenGraphData(raw_tags=og_raw) if og_raw else None,
            twitter_card=TwitterCardData(raw_tags=tc_raw) if tc_raw else None,
            hreflang_tags=[HreflangTag(**h) for h in hreflang_raw],
            is_indexable=bool(row["is_indexable"]),
            is_self_canonical=bool(row["is_self_canonical"]),
            found_in_sitemap=bool(row["found_in_sitemap"]),
            is_orphaned=bool(row["is_orphaned"]),
            error=row["error"],
        )

    # ------------------------------------------------------------------
    # Listing / history
    # ------------------------------------------------------------------

    async def list_crawls(
        self, domain: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return summary rows for recent crawls, optionally filtered by domain."""
        if domain:
            cursor = await self.conn.execute(
                "SELECT id, start_url, domain, total_pages, crawl_status, "
                "started_at, finished_at, crawl_duration_seconds "
                "FROM crawls WHERE domain = ? ORDER BY id DESC LIMIT ?",
                (domain, limit),
            )
        else:
            cursor = await self.conn.execute(
                "SELECT id, start_url, domain, total_pages, crawl_status, "
                "started_at, finished_at, crawl_duration_seconds "
                "FROM crawls ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_page(self, crawl_id: int, url: str) -> Optional[PageData]:
        """Load a single page from a crawl."""
        cursor = await self.conn.execute(
            "SELECT * FROM pages WHERE crawl_id = ? AND url = ?",
            (crawl_id, url),
        )
        row = await cursor.fetchone()
        return self._row_to_page(row) if row else None

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    async def save_issues(self, crawl_id: int, issues: List[SEOIssue]) -> None:
        """Persist a list of SEOIssue objects tied to a crawl."""
        for issue in issues:
            await self.conn.execute(
                """
                INSERT INTO issues (
                    crawl_id, severity, category, title, description,
                    affected_url, recommendation, details, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    crawl_id,
                    issue.severity.value,
                    issue.category.value,
                    issue.title,
                    issue.description,
                    issue.affected_url,
                    issue.recommendation,
                    json.dumps(issue.details),
                    issue.detected_at,
                ),
            )
        await self.conn.commit()
        logger.info("Saved %d issues for crawl %d.", len(issues), crawl_id)

    async def load_issues(self, crawl_id: int) -> List[SEOIssue]:
        """Load all issues for a given crawl."""
        cursor = await self.conn.execute(
            "SELECT * FROM issues WHERE crawl_id = ? ORDER BY severity, category",
            (crawl_id,),
        )
        rows = await cursor.fetchall()
        return [
            SEOIssue(
                severity=IssueSeverity(r["severity"]),
                category=IssueCategory(r["category"]),
                title=r["title"],
                description=r["description"],
                affected_url=r["affected_url"],
                recommendation=r["recommendation"],
                details=json.loads(r["details"]) if r["details"] else {},
                detected_at=r["detected_at"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Comparison helpers
    # ------------------------------------------------------------------

    async def compare_crawls(
        self, crawl_id_old: int, crawl_id_new: int
    ) -> Dict[str, Any]:
        """Return a diff summary between two crawls of the same domain.

        Keys returned:
          - added_urls, removed_urls
          - status_changes: list of {url, old_status, new_status}
          - title_changes: list of {url, old_title, new_title}
          - meta_desc_changes
          - old_summary, new_summary (total pages, duration, etc.)
        """
        old = await self.load_crawl(crawl_id_old)
        new = await self.load_crawl(crawl_id_new)
        if old is None or new is None:
            raise ValueError("One or both crawl IDs not found.")

        old_urls = {p.url for p in old.pages}
        new_urls = {p.url for p in new.pages}
        old_map = {p.url: p for p in old.pages}
        new_map = {p.url: p for p in new.pages}

        status_changes = []
        title_changes = []
        meta_desc_changes = []
        for url in old_urls & new_urls:
            op, np = old_map[url], new_map[url]
            if op.status_code != np.status_code:
                status_changes.append({"url": url, "old_status": op.status_code, "new_status": np.status_code})
            if op.title != np.title:
                title_changes.append({"url": url, "old_title": op.title, "new_title": np.title})
            if op.meta_description != np.meta_description:
                meta_desc_changes.append({"url": url, "old_desc": op.meta_description, "new_desc": np.meta_description})

        return {
            "added_urls": sorted(new_urls - old_urls),
            "removed_urls": sorted(old_urls - new_urls),
            "status_changes": status_changes,
            "title_changes": title_changes,
            "meta_desc_changes": meta_desc_changes,
            "old_summary": {
                "crawl_id": crawl_id_old,
                "total_pages": old.total_pages,
                "duration_s": old.crawl_duration_seconds,
            },
            "new_summary": {
                "crawl_id": crawl_id_new,
                "total_pages": new.total_pages,
                "duration_s": new.crawl_duration_seconds,
            },
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def delete_crawl(self, crawl_id: int) -> None:
        """Delete a crawl and all associated pages and issues."""
        await self.conn.execute("DELETE FROM issues WHERE crawl_id = ?", (crawl_id,))
        await self.conn.execute("DELETE FROM pages WHERE crawl_id = ?", (crawl_id,))
        await self.conn.execute("DELETE FROM crawls WHERE id = ?", (crawl_id,))
        await self.conn.commit()
        logger.info("Deleted crawl %d and associated data.", crawl_id)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _link_to_dict(link: LinkData) -> Dict[str, Any]:
    return {
        "href": link.href,
        "anchor_text": link.anchor_text,
        "is_internal": link.is_internal,
        "is_nofollow": link.is_nofollow,
        "is_ugc": link.is_ugc,
        "is_sponsored": link.is_sponsored,
        "rel_attributes": link.rel_attributes,
        "status_code": link.status_code,
    }


def _image_to_dict(img: ImageData) -> Dict[str, Any]:
    return {
        "src": img.src,
        "alt": img.alt,
        "width": img.width,
        "height": img.height,
        "is_lazy_loaded": img.is_lazy_loaded,
        "file_size": img.file_size,
    }


# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS crawls (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    start_url               TEXT    NOT NULL,
    domain                  TEXT    NOT NULL,
    total_pages             INTEGER DEFAULT 0,
    total_internal_links    INTEGER DEFAULT 0,
    total_external_links    INTEGER DEFAULT 0,
    total_images            INTEGER DEFAULT 0,
    crawl_duration_seconds  REAL    DEFAULT 0.0,
    crawl_status            TEXT    DEFAULT 'completed',
    started_at              TEXT,
    finished_at             TEXT,
    sitemap_urls            TEXT    DEFAULT '[]',
    orphaned_pages          TEXT    DEFAULT '[]',
    errors                  TEXT    DEFAULT '[]',
    link_graph              TEXT    DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS pages (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id          INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    url               TEXT    NOT NULL,
    final_url         TEXT    DEFAULT '',
    status_code       INTEGER DEFAULT 0,
    content_type      TEXT    DEFAULT '',
    content_length    INTEGER DEFAULT 0,
    response_time_ms  REAL    DEFAULT 0.0,
    http_headers      TEXT    DEFAULT '{}',
    redirect_chain    TEXT    DEFAULT '[]',
    crawl_depth       INTEGER DEFAULT 0,
    crawled_at        TEXT,
    title             TEXT    DEFAULT '',
    meta_description  TEXT    DEFAULT '',
    meta_robots       TEXT    DEFAULT '',
    canonical_url     TEXT,
    viewport_meta     TEXT,
    language          TEXT,
    headings          TEXT    DEFAULT '[]',
    word_count        INTEGER DEFAULT 0,
    text_content      TEXT    DEFAULT '',
    text_to_html_ratio REAL  DEFAULT 0.0,
    internal_links    TEXT    DEFAULT '[]',
    external_links    TEXT    DEFAULT '[]',
    images            TEXT    DEFAULT '[]',
    structured_data   TEXT    DEFAULT '[]',
    open_graph        TEXT    DEFAULT '{}',
    twitter_card      TEXT    DEFAULT '{}',
    hreflang_tags     TEXT    DEFAULT '[]',
    is_indexable      INTEGER DEFAULT 1,
    is_self_canonical INTEGER DEFAULT 1,
    found_in_sitemap  INTEGER DEFAULT 0,
    is_orphaned       INTEGER DEFAULT 0,
    error             TEXT
);

CREATE INDEX IF NOT EXISTS idx_pages_crawl   ON pages(crawl_id);
CREATE INDEX IF NOT EXISTS idx_pages_url     ON pages(crawl_id, url);
CREATE INDEX IF NOT EXISTS idx_crawls_domain ON crawls(domain);

CREATE TABLE IF NOT EXISTS issues (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_id        INTEGER NOT NULL REFERENCES crawls(id) ON DELETE CASCADE,
    severity        TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    description     TEXT    DEFAULT '',
    affected_url    TEXT    DEFAULT '',
    recommendation  TEXT    DEFAULT '',
    details         TEXT    DEFAULT '{}',
    detected_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_issues_crawl ON issues(crawl_id);
"""
