"""GA4 paid vs organic revenue extractor — Sprint 4, Task 4.4.

Filters by channel group: Paid Search, Paid Social, Organic Search, Direct, etc.
"""

import structlog
from typing import Any

from engine.connectors.ga4 import run_ga4_report

logger = structlog.get_logger(__name__)

PAID_CHANNELS = {
    "Paid Search", "Paid Social", "Paid Shopping", "Paid Video", "Display",
    "Paid Other",
}
ORGANIC_CHANNELS = {
    "Organic Search", "Organic Social", "Organic Video", "Organic Shopping",
}


def _categorize_channel(channel_group: str) -> str:
    """Categorize a GA4 channel group into paid/organic/other."""
    if channel_group in PAID_CHANNELS:
        return "paid"
    if channel_group in ORGANIC_CHANNELS:
        return "organic"
    return "other"


class GA4PaidVsOrganicExtractor:
    """Extracts paid vs organic revenue breakdown from GA4 Data API v1."""

    def __init__(self, credentials: dict, property_id: str):
        self.credentials = credentials
        self.property_id = property_id

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract paid vs organic revenue using GA4 runReport.

        Dimensions: sessionDefaultChannelGroup
        Metrics: totalRevenue, transactions, sessions, conversions
        Then tag each row with paid/organic/other category.
        """
        rows = run_ga4_report(
            credentials=self.credentials,
            property_id=self.property_id,
            start_date=start_date,
            end_date=end_date,
            dimensions=["sessionDefaultChannelGroup"],
            metrics=["totalRevenue", "transactions", "sessions", "conversions"],
        )

        for row in rows:
            row["category"] = _categorize_channel(
                row.get("sessionDefaultChannelGroup", "")
            )

        logger.info("ga4_paid_vs_organic_extracted", rows=len(rows))
        return rows
