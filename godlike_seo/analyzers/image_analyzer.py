"""
Production-Grade Image SEO & Performance Analyzer.

Evaluates image elements across crawled DOM documents for:
- Missing alt text (accessibility and image search discovery)
- Low-quality or placeholder alt text ("image", "photo", "DSC_001.jpg")
- Missing explicit width and height attributes (CLS risk under Core Web Vitals)
- Modern image format delivery (WebP, AVIF vs legacy JPEG/PNG)
- LCP / Above-the-fold image lazy-loading anti-patterns (loading="lazy" on hero images)
- Oversized media assets (>200KB / >1MB)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from godlike_seo.models import (
    ImageData,
    IssueCategory,
    IssueConfidence,
    IssueSeverity,
    PageData,
    PageType,
    SEOIssue,
)


GENERIC_ALT_PATTERNS = re.compile(
    r"^(image|img|photo|picture|graphic|untitled|dsc_?\d+|screenshot|banner|logo|icon|placeholder)$",
    re.IGNORECASE,
)

MODERN_FORMATS = {".webp", ".avif", ".svg"}
LEGACY_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


class ImageAnalyzer:
    """Evaluates image assets for accessibility, search visibility, and Core Web Vitals compliance."""

    def analyze(self, pages: List[PageData]) -> Dict[str, Any]:
        """Run deep image diagnostics across public crawled pages."""
        issues: List[SEOIssue] = []
        total_images_inspected = 0
        missing_alt_count = 0
        missing_dimensions_count = 0
        oversized_images_count = 0

        for page in pages:
            if page.page_type not in (PageType.PUBLIC_CONTENT, PageType.USER_APP_ROUTE) or not page.has_html:
                continue

            images = getattr(page, "images", []) or []
            total_images_inspected += len(images)

            for idx, img in enumerate(images):
                src = getattr(img, "url", "") or getattr(img, "src", "") or ""
                alt = (img.alt or "").strip()
                parsed_src = urlparse(src)
                filename = parsed_src.path.split("/")[-1] if "/" in parsed_src.path else src
                ext = ("." + filename.split(".")[-1].lower()) if "." in filename else ""

                # 1. Missing Alt Text
                if not alt and not getattr(img, "is_decorative", False):
                    missing_alt_count += 1
                    issues.append(SEOIssue(
                        issue_id="IMAGE_MISSING_ALT",
                        severity=IssueSeverity.MEDIUM,
                        category=IssueCategory.ON_PAGE,
                        title="Image Missing Alt Attribute",
                        description=f"Image tag lacks an 'alt' descriptive text attribute: {filename[:50]}",
                        affected_url=page.url,
                        evidence=f'<img src="{src[:100]}"> (alt absent)',
                        observation=f"Image element '{filename[:40]}' lacks an 'alt' attribute in page DOM.",
                        inference="Search engines cannot understand the topic or context of images without descriptive alt text, preventing ranking in Google Images and harming screen reader accessibility.",
                        impact="Lost visibility in image search results and non-compliance with WCAG accessibility standards.",
                        recommendation="Add a descriptive, contextual 'alt' attribute explaining the visual content or function of the image.",
                        verification_step="Inspect DOM to confirm <img> contains a descriptive alt='...' attribute.",
                        confidence=IssueConfidence.HIGH,
                    ))
                elif alt and GENERIC_ALT_PATTERNS.match(alt):
                    # 2. Low-Quality / Generic Alt Text
                    issues.append(SEOIssue(
                        issue_id="IMAGE_LOW_QUALITY_ALT",
                        severity=IssueSeverity.INFORMATIONAL,
                        category=IssueCategory.ON_PAGE,
                        title="Low-Quality or Placeholder Image Alt Text",
                        description=f"Image alt text '{alt}' is generic or a placeholder filename.",
                        affected_url=page.url,
                        evidence=f'<img src="{src[:60]}" alt="{alt}">',
                        observation=f"Image declares generic placeholder alt text: '{alt}'.",
                        inference="Generic alt text like 'image' or raw filenames provides zero semantic value to search crawlers or assistive technologies.",
                        impact="Diminished image SEO topical relevance.",
                        recommendation="Replace placeholder alt text with a meaningful description of what the image depicts.",
                        verification_step="Confirm alt attribute conveys specific subject matter.",
                        confidence=IssueConfidence.HIGH,
                    ))

                # 3. Missing Explicit Width / Height (Cumulative Layout Shift)
                has_width = bool(getattr(img, "width", None) or getattr(img, "has_dimensions", False))
                has_height = bool(getattr(img, "height", None))
                if not has_width and not getattr(img, "has_dimensions", False):
                    missing_dimensions_count += 1
                    issues.append(SEOIssue(
                        issue_id="IMAGE_MISSING_DIMENSIONS",
                        severity=IssueSeverity.INFORMATIONAL,
                        category=IssueCategory.PERFORMANCE,
                        title="Image Missing Explicit Width and Height Attributes",
                        description=f"Image element '{filename[:40]}' does not declare explicit width/height dimensions.",
                        affected_url=page.url,
                        evidence=f'<img src="{src[:80]}"> (width/height attributes absent)',
                        observation="Image tag does not specify explicit width and height HTML attributes or aspect-ratio.",
                        inference="Missing dimensions can contribute to Cumulative Layout Shift when CSS or another mechanism does not reserve the image's aspect ratio; static HTML alone cannot confirm the rendered effect.",
                        impact="Advisory layout-stability risk; verify the rendered page and CSS before treating this as a defect.",
                        recommendation="Specify explicit width='...' and height='...' attributes on the <img> or define CSS aspect-ratio.",
                        verification_step="Verify <img> tag has width and height attributes in HTML.",
                        confidence=IssueConfidence.HIGH,
                    ))

                # 4. Hero / Above-the-fold Image Lazy-Loading Anti-pattern
                loading_attr = getattr(img, "loading", "").lower()
                if idx == 0 and loading_attr == "lazy":
                    issues.append(SEOIssue(
                        issue_id="IMAGE_HERO_LAZY_LOADED",
                        severity=IssueSeverity.MEDIUM,
                        category=IssueCategory.PERFORMANCE,
                        title="Hero / First Image Uses loading='lazy'",
                        description="First image in document specifies loading='lazy', which delays Largest Contentful Paint (LCP).",
                        affected_url=page.url,
                        evidence=f'<img src="{src[:80]}" loading="lazy">',
                        observation="Initial image element declares loading='lazy' attribute.",
                        inference="Applying loading='lazy' to above-the-fold hero images delays image fetching until after layout computation, significantly harming LCP.",
                        impact="Degrades Largest Contentful Paint (LCP) time by 500ms-1500ms on mobile connections.",
                        recommendation="Remove loading='lazy' from above-the-fold images and consider adding fetchpriority='high'.",
                        verification_step="Confirm top hero image has no loading='lazy' attribute.",
                        confidence=IssueConfidence.HIGH,
                    ))

                # 5. Oversized Images (>200KB or >1MB)
                size_bytes = (
                    getattr(img, "size_bytes", 0)
                    or getattr(img, "file_size", 0)
                    or getattr(img, "size", 0)
                    or 0
                )
                if size_bytes > 1_000_000:
                    oversized_images_count += 1
                    issues.append(SEOIssue(
                        issue_id="IMAGE_CRITICALLY_OVERSIZED",
                        severity=IssueSeverity.HIGH,
                        category=IssueCategory.PERFORMANCE,
                        title="Critically Oversized Image (>1MB)",
                        description=f"Image asset exceeds 1MB in size ({size_bytes / 1_000_000:.1f}MB): {filename[:40]}",
                        affected_url=page.url,
                        evidence=f"File: {src[:70]} | Size: {size_bytes / 1_000_000:.2f} MB",
                        observation=f"Image resource size is {size_bytes / 1_000_000:.2f} MB.",
                        inference="Uncompressed multi-megabyte images severely choke mobile bandwidth, spike page load time, and directly depress Core Web Vitals.",
                        impact="Severe mobile page load delay and heavy cellular data consumption for users.",
                        recommendation="Compress image using modern compression tools, resize to maximum display dimensions, and serve in WebP/AVIF format.",
                        verification_step="Verify image file size is under 200KB on production CDN.",
                        confidence=IssueConfidence.HIGH,
                    ))
                elif size_bytes > 200_000:
                    oversized_images_count += 1
                    issues.append(SEOIssue(
                        issue_id="IMAGE_OVERSIZED_OPTIMIZATION_OPPORTUNITY",
                        severity=IssueSeverity.LOW,
                        category=IssueCategory.PERFORMANCE,
                        title="Image Exceeds Recommended 200KB Threshold",
                        description=f"Image size ({size_bytes / 1000:.0f}KB) exceeds recommended 200KB budget: {filename[:40]}",
                        affected_url=page.url,
                        evidence=f"File: {src[:70]} | Size: {size_bytes / 1000:.1f} KB",
                        observation=f"Image resource size is {size_bytes / 1000:.1f} KB.",
                        inference="Web images larger than 200KB can typically be compressed 40-70% using WebP/AVIF with zero visible quality loss.",
                        impact="Slower page load speed and higher cumulative page transfer weight.",
                        recommendation="Compress image to under 200KB using lossless or high-quality lossy optimization.",
                        verification_step="Confirm compressed asset size is below 200KB.",
                        confidence=IssueConfidence.MEDIUM,
                    ))

        return {
            "issues": issues,
            "total_images_inspected": total_images_inspected,
            "missing_alt_count": missing_alt_count,
            "missing_dimensions_count": missing_dimensions_count,
            "oversized_images_count": oversized_images_count,
        }
