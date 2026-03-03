"""GA4 channel revenue extractor — Sprint 4, Task 4.2.

Extracts sessionDefaultChannelGroup x totalRevenue, transactions, purchaseRevenue.
"""

import structlog
from typing import Any

from engine.connectors.ga4 import run_ga4_report

logger = structlog.get_logger(__name__)


class GA4ChannelRevenueExtractor:
    """Extracts channel revenue data from GA4 Data API v1."""

    def __init__(self, credentials: dict, property_id: str):
        self.credentials = credentials
        self.property_id = property_id

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract channel revenue using GA4 runReport.

        Dimensions: sessionDefaultChannelGroup, date
        Metrics: totalRevenue, transactions, purchaseRevenue, sessions,
                 engagedSessions, totalUsers, conversions
        """
        rows = run_ga4_report(
            credentials=self.credentials,
            property_id=self.property_id,
            start_date=start_date,
            end_date=end_date,
            dimensions=["sessionDefaultChannelGroup", "date"],
            metrics=[
                "totalRevenue", "transactions", "purchaseRevenue",
                "sessions", "engagedSessions", "totalUsers", "conversions",
            ],
        )

        logger.info("ga4_channel_revenue_extracted", rows=len(rows))
        return rows
