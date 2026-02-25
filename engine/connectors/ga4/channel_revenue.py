"""GA4 channel revenue extractor — Sprint 4, Task 4.2.

Extracts sessionDefaultChannelGroup x totalRevenue, transactions, purchaseRevenue.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector


class GA4ChannelRevenueExtractor(BaseConnector):
    """Extracts channel revenue data from GA4 Data API v1."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract channel revenue using GA4 runReport.

        Dimensions: sessionDefaultChannelGroup, date
        Metrics: totalRevenue, transactions, purchaseRevenue, sessions,
                 engagedSessions, totalUsers, conversions
        """
        # TODO: Implement with google-analytics-data RunReportRequest
        raise NotImplementedError("Sprint 4 — Task 4.2")
