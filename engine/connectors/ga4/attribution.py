"""GA4 attribution extractor — Sprint 4.

Limited: Only DDA model summary via API. Full paths require BigQuery.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector


class GA4AttributionExtractor(BaseConnector):
    """Extracts attribution data from GA4 Data API v1."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract attribution model summary from GA4.

        Note: Full attribution paths require BigQuery.
        API only provides DDA summary.
        """
        # TODO: Implement with google-analytics-data RunReportRequest
        raise NotImplementedError("Sprint 4")
