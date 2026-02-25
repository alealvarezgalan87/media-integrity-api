"""GA4 traffic acquisition extractor — Sprint 4, Task 4.3.

Extracts sessionSource, sessionMedium, sessionCampaignName x sessions,
engaged sessions, conversions.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector


class GA4TrafficAcquisitionExtractor(BaseConnector):
    """Extracts traffic acquisition data from GA4 Data API v1."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract traffic acquisition using GA4 runReport.

        Dimensions: sessionSource, sessionMedium, sessionCampaignName, date
        Metrics: sessions, engagedSessions, engagementRate, conversions,
                 totalRevenue, bounceRate
        """
        # TODO: Implement with google-analytics-data RunReportRequest
        raise NotImplementedError("Sprint 4 — Task 4.3")
