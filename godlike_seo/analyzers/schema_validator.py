"""
Production-Grade Schema.org Structured Data Validator.

Validates JSON-LD and microdata structured data against official Google Search Central
rich result specifications. Evaluates mandatory and recommended properties for:
- Product & Offer schemas
- Article, BlogPosting, NewsArticle schemas
- Organization & LocalBusiness schemas
- FAQPage schemas
- BreadcrumbList schemas
- JobPosting & Event schemas
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set

from godlike_seo.models import (
    IssueCategory,
    IssueConfidence,
    IssueSeverity,
    PageData,
    PageType,
    SEOIssue,
    StructuredDataItem,
)

logger = logging.getLogger(__name__)

# Official Google Search Central Rich Result Requirements
SCHEMA_SPECIFICATIONS: Dict[str, Dict[str, Any]] = {
    "Product": {
        "required": ["name"],
        "one_of_required": [["offers", "review", "aggregateRating"]],
        "recommended": ["image", "description", "brand", "sku"],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/product",
    },
    "Article": {
        "required": ["headline", "image", "datePublished", "author"],
        "one_of_required": [],
        "recommended": ["dateModified", "description", "publisher"],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/article",
    },
    "BlogPosting": {
        "required": ["headline", "image", "datePublished", "author"],
        "one_of_required": [],
        "recommended": ["dateModified", "description", "publisher"],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/article",
    },
    "NewsArticle": {
        "required": ["headline", "image", "datePublished", "author"],
        "one_of_required": [],
        "recommended": ["dateModified", "description", "publisher"],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/article",
    },
    "FAQPage": {
        "required": ["mainEntity"],
        "one_of_required": [],
        "recommended": [],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/faqpage",
    },
    "BreadcrumbList": {
        "required": ["itemListElement"],
        "one_of_required": [],
        "recommended": [],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/breadcrumb",
    },
    "LocalBusiness": {
        "required": ["name", "address"],
        "one_of_required": [],
        "recommended": ["telephone", "url", "openingHoursSpecification", "geo", "image"],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/local-business",
    },
    "Organization": {
        "required": ["name", "url"],
        "one_of_required": [],
        "recommended": ["logo", "sameAs", "contactPoint"],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/organization",
    },
    "JobPosting": {
        "required": ["title", "description", "datePosted", "hiringOrganization"],
        "one_of_required": [],
        "recommended": ["validThrough", "employmentType", "jobLocation", "baseSalary"],
        "docs_url": "https://developers.google.com/search/docs/appearance/structured-data/job-posting",
    },
}


class SchemaValidator:
    """Validates structured data items for semantic compliance and rich result eligibility."""

    def validate_page(self, page: PageData) -> List[SEOIssue]:
        """Validate all structured data items on a page."""
        issues: List[SEOIssue] = []
        structured_items = getattr(page, "structured_data", []) or []

        if not structured_items:
            return issues

        for item in structured_items:
            if not item.is_valid:
                issues.append(SEOIssue(
                    issue_id="INVALID_JSON_LD",
                    severity=IssueSeverity.HIGH,
                    category=IssueCategory.STRUCTURED_DATA,
                    title="JSON-LD Structured Data Syntax Error",
                    description=f"JSON-LD script block cannot be parsed: {item.error_message or 'Syntax error'}",
                    affected_url=page.url,
                    evidence=f"Syntax error: {item.error_message} in snippet: {item.raw[:120]}",
                    observation=f"JSON-LD parsing failed: {item.error_message}.",
                    inference="Search engines completely discard malformed JSON-LD scripts, preventing rich snippet qualification.",
                    impact="Search engines cannot read structured data on this page.",
                    recommendation="Fix JSON syntax errors (unescaped quotes, trailing commas, or encoding errors).",
                    verification_step="Test JSON payload in Google Rich Results Test to confirm 0 syntax errors.",
                    confidence=IssueConfidence.HIGH,
                ))
                continue

            data = item.data if isinstance(item.data, dict) else {}
            if not data:
                continue

            stype = str(data.get("@type", "")).strip()
            # Normalize schema type if prefixed (e.g. "schema:Product" -> "Product")
            if ":" in stype:
                stype = stype.split(":")[-1]

            spec = SCHEMA_SPECIFICATIONS.get(stype)
            if not spec:
                # Check case-insensitive match
                for key, val in SCHEMA_SPECIFICATIONS.items():
                    if key.lower() == stype.lower():
                        spec = val
                        stype = key
                        break

            if not spec:
                continue

            # 1. Check Mandatory Fields
            missing_mandatory = []
            for req in spec["required"]:
                val = data.get(req)
                if val is None or val == "" or (isinstance(val, list) and len(val) == 0):
                    missing_mandatory.append(req)

            # Check "one_of_required" (e.g. Product offers OR review OR aggregateRating)
            for group in spec.get("one_of_required", []):
                has_any = any(bool(data.get(prop)) for prop in group)
                if not has_any:
                    missing_mandatory.append(f"one of ({', '.join(group)})")

            if missing_mandatory:
                missing_str = ", ".join(missing_mandatory)
                issues.append(SEOIssue(
                    issue_id="SCHEMA_MISSING_REQUIRED_PROPERTY",
                    severity=IssueSeverity.HIGH,
                    category=IssueCategory.STRUCTURED_DATA,
                    title=f"Schema.org {stype} Missing Required Property ({missing_str})",
                    description=f"{stype} schema declared on page is missing required property: {missing_str}",
                    affected_url=page.url,
                    evidence=f"@type: '{stype}' missing mandatory: [{missing_str}]",
                    observation=f"Declared Schema.org {stype} markup omits required Google Rich Result property: {missing_str}.",
                    inference=f"According to Google Search Central, {stype} structured data missing required properties will not qualify for rich search snippets.",
                    impact=f"Disqualifies page from Google {stype} rich snippets in SERP results.",
                    recommendation=f"Add the required property '{missing_str}' to the {stype} JSON-LD block. See: {spec['docs_url']}",
                    verification_step="Inspect Google Rich Results Test to confirm all required properties are populated.",
                    confidence=IssueConfidence.HIGH,
                ))

            # 2. Type-Specific Semantic Validations
            if stype == "FAQPage":
                main_entity = data.get("mainEntity")
                if isinstance(main_entity, list):
                    invalid_q_count = 0
                    for q in main_entity:
                        if not isinstance(q, dict) or not q.get("name") or not q.get("acceptedAnswer"):
                            invalid_q_count += 1
                    if invalid_q_count > 0:
                        issues.append(SEOIssue(
                            issue_id="SCHEMA_INVALID_FAQ_STRUCTURE",
                            severity=IssueSeverity.MEDIUM,
                            category=IssueCategory.STRUCTURED_DATA,
                            title="FAQPage Schema Contains Incomplete Question/Answer Entities",
                            description=f"FAQPage mainEntity contains {invalid_q_count} item(s) without valid name or acceptedAnswer.",
                            affected_url=page.url,
                            evidence=f"FAQPage has {invalid_q_count} malformed Question item(s)",
                            observation="FAQPage questions do not follow required Question -> acceptedAnswer -> text schema hierarchy.",
                            inference="Google will reject invalid FAQ entities and may suppress rich FAQ snippet accordions.",
                            impact="FAQ rich accordion expansion will not appear in search results.",
                            recommendation="Ensure each Question item in mainEntity declares 'name' and an 'acceptedAnswer' with 'text'.",
                            verification_step="Validate in Rich Results Test tool.",
                            confidence=IssueConfidence.HIGH,
                        ))

            elif stype == "BreadcrumbList":
                items = data.get("itemListElement")
                if isinstance(items, list):
                    missing_pos = any(not isinstance(i, dict) or "position" not in i for i in items)
                    if missing_pos:
                        issues.append(SEOIssue(
                            issue_id="SCHEMA_INVALID_BREADCRUMB_STRUCTURE",
                            severity=IssueSeverity.MEDIUM,
                            category=IssueCategory.STRUCTURED_DATA,
                            title="BreadcrumbList Schema Missing Item Positions",
                            description="BreadcrumbList items must specify numerical 'position' order.",
                            affected_url=page.url,
                            evidence="itemListElement contains entries without 'position' attribute",
                            observation="Breadcrumb items do not declare explicit sequential position integers.",
                            inference="Google requires explicit 1-based numerical positions to render breadcrumb navigation paths in search results.",
                            impact="Breadcrumb path display in SERP will be disabled.",
                            recommendation="Add 'position: 1', 'position: 2', etc., to each breadcrumb ListItem.",
                            verification_step="Confirm breadcrumb items have sequential position integers.",
                            confidence=IssueConfidence.HIGH,
                        ))

            elif stype in ("Article", "BlogPosting", "NewsArticle"):
                author = data.get("author")
                if author:
                    # Author should be dict or list of dicts with name
                    author_valid = False
                    if isinstance(author, dict) and author.get("name"):
                        author_valid = True
                    elif isinstance(author, list) and any(isinstance(a, dict) and a.get("name") for a in author):
                        author_valid = True
                    elif isinstance(author, str) and author.strip():
                        author_valid = True  # String author is accepted by Schema.org though dict Person is preferred
                    if not author_valid:
                        issues.append(SEOIssue(
                            issue_id="SCHEMA_MISSING_AUTHOR_NAME",
                            severity=IssueSeverity.MEDIUM,
                            category=IssueCategory.STRUCTURED_DATA,
                            title=f"{stype} Author Entity Missing Name",
                            description=f"{stype} author entity lacks a 'name' property.",
                            affected_url=page.url,
                            evidence=f"Author: {author}",
                            observation="Author property in Article structured data is missing a valid 'name' attribute.",
                            inference="Google recommends explicit Person or Organization author entities for E-E-A-T transparency and Top Stories eligibility.",
                            impact="Harming author attribution and E-E-A-T signals.",
                            recommendation="Specify author as {'@type': 'Person', 'name': 'Author Name'}.",
                            verification_step="Verify author entity includes name and type in JSON-LD.",
                            confidence=IssueConfidence.HIGH,
                        ))

            # 3. Check Recommended Properties (Advisory)
            missing_recommended = [
                rec for rec in spec.get("recommended", [])
                if not data.get(rec)
            ]
            if missing_recommended and len(missing_recommended) >= 2:
                rec_str = ", ".join(missing_recommended[:3])
                issues.append(SEOIssue(
                    issue_id="SCHEMA_MISSING_RECOMMENDED_PROPERTY",
                    severity=IssueSeverity.LOW,
                    category=IssueCategory.STRUCTURED_DATA,
                    title=f"Schema.org {stype} Opportunity: Add Recommended Properties",
                    description=f"{stype} schema could be enhanced by adding recommended properties: {rec_str}",
                    affected_url=page.url,
                    evidence=f"{stype} missing recommended: [{rec_str}]",
                    observation=f"{stype} markup omits recommended properties: {rec_str}.",
                    inference="Providing recommended properties gives Google more structured context, increasing rich snippet display chances.",
                    impact="Advisory recommendation to enhance rich snippet visual prominence.",
                    recommendation=f"Add recommended properties ({rec_str}) to enhance snippet richness.",
                    verification_step="Confirm additional properties appear in structured data validator.",
                    confidence=IssueConfidence.MEDIUM,
                ))

        return issues
