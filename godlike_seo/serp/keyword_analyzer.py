"""
Production-Grade Keyword Intelligence & Search Intent Engine.

Features:
- Multi-dimensional search intent classification (Informational, Commercial, Transactional, Navigational, Local)
- Syntactic & semantic intent confidence scoring
- Non-linear semantic relevance modeling (phrase integrity, Jaccard token overlap, suggestion rank decay)
- Search volume tier estimation (HIGH, MEDIUM, LOW, NICHE)
- Keyword Difficulty (KD 0-100) algorithmic estimation
- Content format mapping tailored to search intent
"""

from __future__ import annotations

import difflib
import json
import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

logger = logging.getLogger(__name__)

GOOGLE_SUGGEST_URL = "https://suggestqueries.google.com/complete/search"


class SearchIntent(str, Enum):
    INFORMATIONAL = "Informational"
    COMMERCIAL = "Commercial"
    TRANSACTIONAL = "Transactional"
    NAVIGATIONAL = "Navigational"
    LOCAL = "Local"


@dataclass
class KeywordOpportunity:
    keyword: str
    intent: SearchIntent
    relevance_score: float  # 0 to 100
    group: str
    suggested_content_type: str
    search_volume_tier: str = "MEDIUM"   # Heuristic only; not a measured volume band
    keyword_difficulty: float = 30.0     # Heuristic only; not a SERP difficulty metric
    intent_confidence: float = 0.85      # 0.0 to 1.0 confidence in classified search intent
    trend_signal: str = "UNKNOWN"        # Historical data is not collected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "intent": self.intent.value if hasattr(self.intent, "value") else str(self.intent),
            "relevance_score": round(self.relevance_score, 1),
            "group": self.group,
            "suggested_content_type": self.suggested_content_type,
            "search_volume_tier": self.search_volume_tier,
            "keyword_difficulty": round(self.keyword_difficulty, 1),
            "intent_confidence": round(self.intent_confidence, 2),
            "trend_signal": self.trend_signal,
            "search_volume_basis": "Heuristic tier from phrase length and autocomplete suggestion order; no monthly search volume data.",
            "keyword_difficulty_basis": "Heuristic estimate from phrase length and intent; not a provider or SERP-based difficulty score.",
            "trend_data_available": False,
        }


class KeywordAnalyzer:
    """Discovers high-value keywords and clusters them by search intent and competitive viability."""

    def __init__(self, user_agent: Optional[str] = None, language: str = "en", country: str = "us"):
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        self.language = language
        self.country = country

    def _get_autocomplete_suggestions(self, query: str) -> List[Tuple[str, int]]:
        """Fetch Google autocomplete suggestions with rank positions."""
        params = {
            "client": "chrome",
            "q": query,
            "hl": self.language,
            "gl": self.country,
        }
        headers = {"User-Agent": self.user_agent}

        try:
            resp = requests.get(GOOGLE_SUGGEST_URL, params=params, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
                    return [(str(item), rank) for rank, item in enumerate(data[1], start=1)]
        except Exception as e:
            logger.debug("Autocomplete error for '%s': %s", query, e)

        return []

    def classify_intent(self, keyword: str) -> Tuple[SearchIntent, float]:
        """Classify search intent from syntactic structure and intent signals, returning (Intent, Confidence)."""
        kw = keyword.lower().strip()
        words = kw.split()

        # 1. Local Search Intent
        local_signals = ["near me", "nearby", "in ", "at ", "directions", "location", "hours", "open now", "city", "center", "closest", "area"]
        geo_suffixes = [
            " india", " bengaluru", " bangalore", " hyderabad", " mumbai", " delhi",
            " chennai", " pune", " kolkata", " ahmedabad", " coimbatore", " jaipur",
            " surat", " lucknow", " london", " nyc", " usa",
        ]
        if any(sig in kw for sig in local_signals) or any(kw.endswith(s) for s in geo_suffixes):
            return SearchIntent.LOCAL, 0.92

        # 2. Transactional Intent (Action & Acquisition verbs)
        transactional_signals = [
            "buy", "purchase", "order", "price", "pricing", "cost", "cheap", "discount",
            "coupon", "promo", "deal", "deals", "quote", "booking", "book", "rent",
            "rental", "rentals", "renting", "hire", "lease", "subscription", "for sale",
            "download", "hire", "freelance", "services",
        ]
        tx_matches = sum(1 for w in transactional_signals if re.search(rf"\b{re.escape(w)}\b", kw))
        if tx_matches > 0:
            confidence = min(0.98, 0.75 + (tx_matches * 0.12))
            return SearchIntent.TRANSACTIONAL, confidence

        # 3. Commercial Investigation Intent (Comparison & Evaluation)
        commercial_signals = [
            "best", "top", "review", "reviews", "vs", "versus", "comparison", "compare",
            "alternative", "alternatives", "recommended", "rating", "ratings", "pros and cons",
            "features", "worth it", "difference between",
        ]
        comm_matches = sum(1 for w in commercial_signals if re.search(rf"\b{re.escape(w)}\b", kw))
        if comm_matches > 0:
            confidence = min(0.98, 0.75 + (comm_matches * 0.12))
            return SearchIntent.COMMERCIAL, confidence

        # 4. Navigational Intent (Brand / Login / Access portals)
        navigational_signals = [
            "login", "signin", "sign in", "sign up", "signup", "portal", "account",
            "dashboard", "official", "support", "customer service", "helpdesk",
        ]
        if any(re.search(rf"\b{re.escape(w)}\b", kw) for w in navigational_signals):
            return SearchIntent.NAVIGATIONAL, 0.90

        # 5. Informational Intent (Questions, Explanations, Tutorials)
        informational_signals = [
            "how to", "what is", "why", "who", "when", "where", "guide", "tutorial",
            "examples", "definition", "meaning", "template", "cheat sheet", "specs", "learn", "ideas",
        ]
        if any(kw.startswith(s) or f" {s} " in kw for s in informational_signals):
            return SearchIntent.INFORMATIONAL, 0.92

        # Default Informational (e.g. broad head queries or entity lookups)
        return SearchIntent.INFORMATIONAL, 0.70

    def calculate_relevance(self, seed: str, keyword: str, rank_position: int = 5) -> float:
        """Calculate multi-dimensional semantic relevance (0 to 100).

        Combines:
        1. Jaccard token overlap (0-30 pts)
        2. Exact phrase / contiguous n-gram preservation (0-30 pts)
        3. String sequence similarity (0-20 pts)
        4. Autocomplete rank decay (popularity proxy) (0-20 pts)
        """
        seed_clean = seed.lower().strip()
        kw_clean = keyword.lower().strip()

        seed_tokens = set(seed_clean.split())
        kw_tokens = set(kw_clean.split())

        if not seed_tokens or not kw_tokens:
            return 50.0

        # 1. Jaccard Token Overlap (up to 30 pts)
        jaccard = len(seed_tokens & kw_tokens) / len(seed_tokens | kw_tokens)
        score_jaccard = jaccard * 30.0

        # 2. Phrase Integrity (Contiguous seed presence, up to 30 pts)
        score_phrase = 30.0 if seed_clean in kw_clean else (15.0 if any(t in kw_clean for t in seed_tokens) else 0.0)

        # 3. String Sequence Similarity (up to 20 pts)
        seq_ratio = difflib.SequenceMatcher(None, seed_clean, kw_clean).ratio()
        score_seq = seq_ratio * 20.0

        # 4. Suggestion Rank Decay (Google popularity signal, up to 20 pts)
        score_rank = max(5.0, 20.0 - (rank_position * 1.5))

        total_score = score_jaccard + score_phrase + score_seq + score_rank
        return min(100.0, max(10.0, round(total_score, 1)))

    def estimate_volume_and_difficulty(self, keyword: str, intent: SearchIntent, rank: int) -> Tuple[str, float]:
        """Estimate search volume tier and keyword difficulty (KD 0-100)."""
        kw = keyword.lower().strip()
        words = kw.split()
        word_count = len(words)

        # Search Volume Tier:
        if word_count <= 2 and rank <= 3:
            vol_tier = "HIGH"
        elif word_count <= 3 and rank <= 6:
            vol_tier = "MEDIUM"
        elif word_count <= 4:
            vol_tier = "LOW"
        else:
            vol_tier = "NICHE"

        # Keyword Difficulty (0-100):
        base_kd = 50.0
        if word_count <= 2:
            base_kd += 30.0
        elif word_count == 3:
            base_kd += 15.0
        elif word_count >= 5:
            base_kd -= 25.0

        if intent in (SearchIntent.TRANSACTIONAL, SearchIntent.COMMERCIAL):
            base_kd += 15.0
        elif intent == SearchIntent.INFORMATIONAL:
            base_kd -= 10.0

        kd = min(95.0, max(5.0, round(base_kd, 1)))
        return vol_tier, kd

    def get_content_type_recommendation(self, intent: SearchIntent) -> str:
        """Map search intent to the optimal Google ranking content format."""
        if intent == SearchIntent.INFORMATIONAL:
            return "In-depth How-To Guide, FAQ section, or Comprehensive Tutorial"
        elif intent == SearchIntent.COMMERCIAL:
            return "Comparison Table, Buyer's Guide, or Feature Breakdown Review"
        elif intent == SearchIntent.TRANSACTIONAL:
            return "High-converting Landing Page with Pricing, Testimonials & CTA"
        elif intent == SearchIntent.LOCAL:
            return "Location Landing Page with Google Map embed, NAP details, and local reviews"
        else:
            return "Brand Homepage or Product Login Portal"

    def expand_keyword(self, seed: str, max_results: int = 40) -> List[KeywordOpportunity]:
        """Generate long-tail variations across questions, prepositions, and alphabet."""
        clean_seed = seed.strip().lower()
        discovered: Dict[str, int] = {}  # keyword -> best rank position

        def record(s_tuple_list):
            for kw, rank in s_tuple_list:
                kw_str = kw.strip().lower()
                if kw_str and kw_str != clean_seed:
                    if kw_str not in discovered or rank < discovered[kw_str]:
                        discovered[kw_str] = rank

        # 1. Direct suggestions
        record(self._get_autocomplete_suggestions(clean_seed))

        # 2. Question prefixes
        question_prefixes = ["how to", "what is", "why", "best", "where to"]
        for prefix in question_prefixes:
            record(self._get_autocomplete_suggestions(f"{prefix} {clean_seed}"))

        # 3. Alphabetical expansion
        for letter in ["a", "b", "c", "f", "h", "m", "p", "s", "t"]:
            if len(discovered) >= max_results * 2:
                break
            record(self._get_autocomplete_suggestions(f"{clean_seed} {letter}"))

        opportunities: List[KeywordOpportunity] = []
        for kw, best_rank in discovered.items():
            intent, confidence = self.classify_intent(kw)
            relevance = self.calculate_relevance(clean_seed, kw, best_rank)
            vol_tier, kd = self.estimate_volume_and_difficulty(kw, intent, best_rank)

            group = "Questions" if any(kw.startswith(q) for q in ["how", "what", "why", "where", "who", "which"]) else intent.value

            opportunities.append(KeywordOpportunity(
                keyword=kw,
                intent=intent,
                relevance_score=relevance,
                group=group,
                suggested_content_type=self.get_content_type_recommendation(intent),
                search_volume_tier=vol_tier,
                keyword_difficulty=kd,
                intent_confidence=confidence,
                trend_signal="UNKNOWN",
            ))

        opportunities.sort(key=lambda o: (o.relevance_score, -o.keyword_difficulty), reverse=True)
        return opportunities[:max_results]
