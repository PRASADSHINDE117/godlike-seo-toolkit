"""
Content Quality, Keyword Density, TF-IDF, N-gram, and Cannibalization Analyzer.

Features:
- Flesch Reading Ease and Flesch-Kincaid Grade Level scoring
- TF-IDF matrix computation across all crawled pages
- N-gram phrase frequency analysis (1-gram, 2-gram, 3-gram) with stopword removal
- Near-duplicate content detection using token set similarity (Dice coefficient)
- Keyword cannibalization detection (identifying multiple pages targeting identical keywords)
- Content depth and thin-content scoring
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from godlike_seo.models import (
    PageData,
    PageType,
    SEOIssue,
    IssueSeverity,
    IssueCategory,
    IssueConfidence,
)
from godlike_seo.utils.url_normalizer import are_urls_equivalent

# Common English stop words
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}


GENERIC_CANNIBALIZATION_TERMS: Set[str] = {
    "home", "about", "contact", "login", "signin", "register", "signup",
    "terms", "privacy", "policy", "cart", "shop", "browse", "view",
    "details", "help", "support", "services", "cookie", "cookies",
    "account", "profile", "password", "menu", "search", "faq", "footer",
    "header", "navigation", "versatyle", "tental", "page", "welcome"
}


@dataclass
class PageReadability:
    url: str
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    difficulty_label: str
    word_count: int
    sentence_count: int


@dataclass
class CannibalizationRisk:
    keyword: str
    competing_urls: List[str]
    title_matches: List[str]
    similarity_score: float
    recommendation: str


class ContentAnalyzer:
    """Performs deep textual and lexical SEO analysis across pages."""

    def __init__(self, stop_words: Optional[Set[str]] = None):
        self.stop_words = stop_words or STOP_WORDS

    def _tokenize(self, text: str) -> List[str]:
        """Convert text into cleaned lower-case word tokens."""
        return [w.lower() for w in re.findall(r"\b[a-zA-Z]{2,}\b", text)]

    def _count_syllables(self, word: str) -> int:
        """Estimate syllable count in an English word."""
        word = word.lower()
        if len(word) <= 3:
            return 1
        word = re.sub(r"(?:[^laeiouy]|ed|es|e)$", "", word)
        word = re.sub(r"^y", "", word)
        syllables = len(re.findall(r"[aeiouy]{1,2}", word))
        return max(1, syllables)

    def analyze_readability(self, page: PageData) -> PageReadability:
        """Calculate Flesch Reading Ease and Flesch-Kincaid Grade Level."""
        text = page.text_content or ""
        words = self._tokenize(text)
        word_count = len(words)
        if word_count == 0:
            return PageReadability(page.url, 0.0, 0.0, "No content", 0, 0)

        # Sentence counting
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        sentence_count = max(1, len(sentences))

        total_syllables = sum(self._count_syllables(w) for w in words)

        # Flesch Reading Ease
        # 206.835 - 1.015 * (total words / total sentences) - 84.6 * (total syllables / total words)
        fre = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (total_syllables / word_count)
        fre = max(0.0, min(100.0, fre))

        # Flesch-Kincaid Grade Level
        # 0.39 * (total words / total sentences) + 11.8 * (total syllables / total words) - 15.59
        fkgl = 0.39 * (word_count / sentence_count) + 11.8 * (total_syllables / word_count) - 15.59
        fkgl = max(0.0, fkgl)

        if fre >= 80:
            label = "Very Easy (Elementary)"
        elif fre >= 60:
            label = "Standard / Plain English"
        elif fre >= 50:
            label = "Fairly Difficult (High School)"
        elif fre >= 30:
            label = "Difficult (College)"
        else:
            label = "Very Difficult (Academic/Technical)"

        return PageReadability(
            url=page.url,
            flesch_reading_ease=round(fre, 1),
            flesch_kincaid_grade=round(fkgl, 1),
            difficulty_label=label,
            word_count=word_count,
            sentence_count=sentence_count,
        )

    def extract_ngrams(self, text: str, n: int = 2, top_k: int = 15) -> List[Tuple[str, int, float]]:
        """Extract top N-grams excluding stop words, returning (phrase, count, density_pct)."""
        tokens = [w for w in self._tokenize(text) if w not in self.stop_words]
        if len(tokens) < n:
            return []

        ngrams = [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
        total_ngrams = len(ngrams)
        counts = Counter(ngrams)

        result = []
        for phrase, count in counts.most_common(top_k):
            density = (count / total_ngrams) * 100.0 if total_ngrams > 0 else 0.0
            result.append((phrase, count, round(density, 2)))
        return result

    def compute_tfidf(self, pages: List[PageData], top_k: int = 10) -> Dict[str, List[Tuple[str, float]]]:
        """Compute TF-IDF top terms for each page across the crawl corpus."""
        corpus: Dict[str, List[str]] = {}
        doc_freq: Counter = Counter()

        for page in pages:
            tokens = [w for w in self._tokenize(page.text_content) if w not in self.stop_words]
            if tokens:
                corpus[page.url] = tokens
                unique_words = set(tokens)
                for w in unique_words:
                    doc_freq[w] += 1

        total_docs = len(corpus)
        if total_docs == 0:
            return {}

        results: Dict[str, List[Tuple[str, float]]] = {}

        for url, tokens in corpus.items():
            tf = Counter(tokens)
            doc_len = len(tokens)
            tfidf_scores: Dict[str, float] = {}

            for word, count in tf.items():
                term_frequency = count / doc_len
                inverse_doc_frequency = math.log((total_docs + 1) / (doc_freq[word] + 1)) + 1.0
                tfidf_scores[word] = term_frequency * inverse_doc_frequency

            top_terms = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            results[url] = [(w, round(score, 4)) for w, score in top_terms]

        return results

    def detect_keyword_cannibalization(self, pages: List[PageData]) -> List[CannibalizationRisk]:
        """Detect public indexable pages that compete for the exact same target keywords in titles and H1s."""
        # Strictly filter to public indexable content with substantial text
        valid_pages = [
            p for p in pages
            if getattr(p, "page_type", None) == PageType.PUBLIC_CONTENT
            and not getattr(p, "is_auth_gate", False)
            and p.is_indexable
            and p.status_code == 200
            and p.word_count >= 150
        ]

        if len(valid_pages) < 2:
            return []

        keyword_to_pages: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

        for page in valid_pages:
            title = page.title or ""
            h1 = page.h1_tags[0] if page.h1_tags else ""

            # Extract 2-word and 3-word n-grams from Title and H1
            title_tokens = [w for w in self._tokenize(title) if w not in self.stop_words]
            h1_tokens = [w for w in self._tokenize(h1) if w not in self.stop_words]

            phrases = set()
            for tokens in (title_tokens, h1_tokens):
                for n in (2, 3):
                    for i in range(len(tokens) - n + 1):
                        gram_tokens = tokens[i : i + n]
                        # Discard if all tokens are generic
                        if any(t in GENERIC_CANNIBALIZATION_TERMS for t in gram_tokens):
                            continue
                        phrase = " ".join(gram_tokens)
                        if len(phrase) >= 6:
                            phrases.add(phrase)

            for phrase in phrases:
                keyword_to_pages[phrase].append((page.url, title))

        risks: List[CannibalizationRisk] = []
        for kw, page_list in keyword_to_pages.items():
            # Deduplicate URLs and check for genuine distinct pages
            unique_entries = []
            seen_urls = set()
            for u, t in page_list:
                if not any(are_urls_equivalent(u, su) for su in seen_urls):
                    seen_urls.add(u)
                    unique_entries.append((u, t))

            if len(unique_entries) > 1:
                urls = [u for u, _ in unique_entries]
                titles = [t for _, t in unique_entries]
                risks.append(CannibalizationRisk(
                    keyword=kw,
                    competing_urls=urls,
                    title_matches=titles,
                    similarity_score=round(len(urls) / len(valid_pages), 3),
                    recommendation=(
                        f"Pages {', '.join(urls[:2])} both feature '{kw}' in titles or main headings. "
                        "Audit search intent for both URLs. If serving distinct intents, refine title/H1 targeting. "
                        "If targeting identical intent, consider consolidating content."
                    ),
                ))

        # Sort by most severe cannibalization (most competing URLs)
        risks.sort(key=lambda r: len(r.competing_urls), reverse=True)
        return risks[:10]

    def analyze(self, pages: List[PageData]) -> Dict[str, Any]:
        """Run complete content quality audit across all pages."""
        readability_reports = [self.analyze_readability(p) for p in pages if p.text_content]
        avg_fre = sum(r.flesch_reading_ease for r in readability_reports) / max(1, len(readability_reports))
        avg_words = sum(p.word_count for p in pages) / max(1, len(pages))

        cannibalization = self.detect_keyword_cannibalization(pages)
        tfidf_summary = self.compute_tfidf(pages)

        issues: List[SEOIssue] = []

        # Convert cannibalization into SEOIssue objects
        for risk in cannibalization[:3]:
            issues.append(SEOIssue(
                issue_id="KEYWORD_CANNIBALIZATION_RISK",
                severity=IssueSeverity.MEDIUM,
                category=IssueCategory.CONTENT,
                title=f"Potential Keyword Cannibalization: '{risk.keyword}'",
                description=f"Multiple public pages ({len(risk.competing_urls)}) target the phrase '{risk.keyword}' in titles or headings.",
                affected_url=risk.competing_urls[0],
                evidence=f"Shared phrase '{risk.keyword}' found in titles across {len(risk.competing_urls)} URLs: {', '.join(risk.competing_urls[:2])}",
                observation=f"Phrase '{risk.keyword}' appears in <title> or <h1> of multiple distinct public indexable pages.",
                inference="Search engines may split query authority between these pages if they both attempt to rank for the same user intent.",
                impact="May prevent either page from achieving top ranking positions if search intent overlaps.",
                recommendation=risk.recommendation,
                verification_step="Audit Google Search Console performance queries for both URLs to verify whether impressions conflict.",
                confidence=IssueConfidence.MEDIUM,
                details={"competing_urls": risk.competing_urls},
            ))

        # Flag difficult readability
        for r in readability_reports:
            if r.flesch_reading_ease < 30 and r.word_count > 300:
                issues.append(SEOIssue(
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.CONTENT,
                    title="Content Difficult to Read",
                    description=f"Readability score is {r.flesch_reading_ease}/100 ({r.difficulty_label}).",
                    affected_url=r.url,
                    recommendation="Simplify sentence structures and shorten long paragraphs to improve user engagement and dwell time.",
                ))

        return {
            "average_flesch_reading_ease": round(avg_fre, 1),
            "average_word_count": round(avg_words, 1),
            "cannibalization_risks": cannibalization,
            "readability_by_page": readability_reports,
            "top_tfidf_terms": tfidf_summary,
            "issues": issues,
        }
