"""GA4 traffic acquisition extractor — Sprint 4, Task 4.3.

Extracts sessionSource, sessionMedium, sessionCampaignName x sessions,
engaged sessions, conversions.
"""

import structlog
from typing import Any

from engine.connectors.ga4 import run_ga4_report

logger = structlog.get_logger(__name__)


class GA4TrafficAcquisitionExtractor:
    """Extracts traffic acquisition data from GA4 Data API v1."""

    def __init__(self, credentials: dict, property_id: str):
        self.credentials = credentials
        self.property_id = property_id

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract traffic acquisition using GA4 runReport.

        Dimensions: sessionSource, sessionMedium, sessionCampaignName, date
        Metrics: sessions, engagedSessions, engagementRate, conversions,
                 totalRevenue, bounceRate
        """
        rows = run_ga4_report(
            credentials=self.credentials,
            property_id=self.property_id,
            start_date=start_date,
            end_date=end_date,
            dimensions=["sessionSource", "sessionMedium", "sessionCampaignName", "date"],
            metrics=[
                "sessions", "engagedSessions", "engagementRate",
                "conversions", "totalRevenue", "bounceRate",
            ],
        )

        logger.info("ga4_traffic_acquisition_extracted", rows=len(rows))
        return rows
