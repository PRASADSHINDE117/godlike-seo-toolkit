"""
External Production API Integrations for Google Search Console and PageSpeed Insights.
"""

from godlike_seo.integrations.search_console import GoogleSearchConsoleClient, GSCQueryPerformance
from godlike_seo.integrations.pagespeed import PageSpeedInsightsClient, CoreWebVitalsAssessment

__all__ = [
    "GoogleSearchConsoleClient",
    "GSCQueryPerformance",
    "PageSpeedInsightsClient",
    "CoreWebVitalsAssessment",
]
