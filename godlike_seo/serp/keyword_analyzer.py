"""
Keyword Research, Autocomplete Expansion, and Intent Classification Engine.

Features:
- Google Autocomplete API expansion (seed keyword + [a-z], prepositions, questions)
- Search intent classification (Informational, Commercial, Transactional, Navigational)
- Long-tail keyword generation
- Topic grouping and keyword opportunity scoring
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import requests

logger = logging.getLogger(__name__)

GOOGLE_SUGGEST_URL = "http://suggestqueries.google.com/complete/search"


class SearchIntent(str, Enum):
    INFORMATIONAL = "Informational"
    COMMERCIAL = "Commercial"
    TRANSACTIONAL = "Transactional"
    NAVIGATIONAL = "Navigational"


@dataclass
class KeywordOpportunity:
    keyword: str
    intent: SearchIntent
    relevance_score: float  # 0 to 100
    group: str
    suggested_content_type: str


class KeywordAnalyzer:
    """Discovers high-value keywords and clusters them by search intent."""

    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def _get_autocomplete_suggestions(self, query: str) -> List[str]:
        """Fetch Google autocomplete suggestions."""
        params = {
            "client": "chrome",
            "q": query,
            "hl": "en",
        }
        headers = {"User-Agent": self.user_agent}

        try:
            resp = requests.get(GOOGLE_SUGGEST_URL, params=params, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
                    return [str(item) for item in data[1]]
        except Exception as e:
            logger.debug("Autocomplete error for '%s': %s", query, e)

        return []

    def classify_intent(self, keyword: str) -> SearchIntent:
        """Classify search intent from keyword phrasing."""
        kw = keyword.lower()

        # Transactional
        transactional_signals = ["buy", "purchase", "cheap", "price", "pricing", "discount", "coupon", "order", "shop", "deal", "hire", "service"]
        if any(re.search(rf"\b{re.escape(w)}\b", kw) for w in transactional_signals):
            return SearchIntent.TRANSACTIONAL

        # Commercial
        commercial_signals = ["best", "top", "review", "reviews", "vs", "versus", "comparison", "alternative", "alternatives", "recommended"]
        if any(re.search(rf"\b{re.escape(w)}\b", kw) for w in commercial_signals):
            return SearchIntent.COMMERCIAL

        # Navigational
        navigational_signals = ["login", "sign in", "portal", "website", "official", "app download"]
        if any(re.search(rf"\b{re.escape(w)}\b", kw) for w in navigational_signals):
            return SearchIntent.NAVIGATIONAL

        # Default Informational
        return SearchIntent.INFORMATIONAL

    def get_content_type_recommendation(self, intent: SearchIntent) -> str:
        """Map search intent to the optimal Google ranking content format."""
        if intent == SearchIntent.INFORMATIONAL:
            return "In-depth How-To Guide, FAQ section, or Comprehensive Tutorial"
        elif intent == SearchIntent.COMMERCIAL:
            return "Comparison Table, Buyer's Guide, or Feature Breakdown Review"
        elif intent == SearchIntent.TRANSACTIONAL:
            return "High-converting Landing Page with Pricing, Testimonials & CTA"
        else:
            return "Brand Homepage or Product Login Portal"

    def expand_keyword(self, seed: str, max_results: int = 40) -> List[KeywordOpportunity]:
        """Generate long-tail variations across questions, prepositions, and alphabet."""
        clean_seed = seed.strip().lower()
        discovered: Set[str] = set()
        opportunities: List[KeywordOpportunity] = []

        # 1. Direct suggestions
        for s in self._get_autocomplete_suggestions(clean_seed):
            discovered.add(s)

        # 2. Question prefixes
        question_prefixes = ["how to", "what is", "why", "best", "where to"]
        for prefix in question_prefixes:
            for s in self._get_autocomplete_suggestions(f"{prefix} {clean_seed}"):
                discovered.add(s)

        # 3. Alphabetical expansion (selected high-intent letters)
        for letter in ["a", "b", "c", "f", "h", "m", "p", "s", "t"]:
            if len(discovered) >= max_results:
                break
            for s in self._get_autocomplete_suggestions(f"{clean_seed} {letter}"):
                discovered.add(s)

        # Build list of opportunities
        for kw in discovered:
            if kw == clean_seed:
                continue

            intent = self.classify_intent(kw)
            # Relevance heuristic based on word overlap
            overlap = len(set(clean_seed.split()) & set(kw.split()))
            relevance = min(100.0, 50.0 + (overlap * 20.0))

            group = "Questions" if any(kw.startswith(q) for q in ["how", "what", "why", "where", "who"]) else intent.value

            opportunities.append(KeywordOpportunity(
                keyword=kw,
                intent=intent,
                relevance_score=relevance,
                group=group,
                suggested_content_type=self.get_content_type_recommendation(intent),
            ))

        # Sort by relevance
        opportunities.sort(key=lambda o: o.relevance_score, reverse=True)
        return opportunities[:max_results]
