"""GA4 attribution extractor — Sprint 4.

Limited: Only DDA model summary via API. Full paths require BigQuery.
"""

import structlog
from typing import Any

from engine.connectors.ga4 import run_ga4_report

logger = structlog.get_logger(__name__)


class GA4AttributionExtractor:
    """Extracts attribution data from GA4 Data API v1."""

    def __init__(self, credentials: dict, property_id: str):
        self.credentials = credentials
        self.property_id = property_id

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract attribution model summary from GA4.

        Note: Full attribution paths require BigQuery.
        API only provides DDA summary by channel group.
        """
        rows = run_ga4_report(
            credentials=self.credentials,
            property_id=self.property_id,
            start_date=start_date,
            end_date=end_date,
            dimensions=["sessionDefaultChannelGroup"],
            metrics=["conversions", "totalRevenue"],
        )

        logger.info("ga4_attribution_extracted", rows=len(rows))
        return rows
