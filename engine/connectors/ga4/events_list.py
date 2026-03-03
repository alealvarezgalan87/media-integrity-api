"""GA4 Events List extractor — Phase 3G.

Queries GA4 Data API to get the list of tracked event names and their counts,
to detect missing mid-funnel events.
"""

import structlog
from typing import Any

from engine.connectors.ga4 import run_ga4_report

logger = structlog.get_logger(__name__)


class GA4EventsListExtractor:
    """Extracts the list of tracked events from a GA4 property."""

    def __init__(self, credentials: dict, property_id: str):
        self.credentials = credentials
        self.property_id = property_id

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Query GA4 for event names and counts in the date range."""
        rows = run_ga4_report(
            credentials=self.credentials,
            property_id=self.property_id,
            start_date=start_date,
            end_date=end_date,
            dimensions=["eventName"],
            metrics=["eventCount", "totalUsers"],
        )

        logger.info("ga4_events_list_extracted", total_events=len(rows))
        return rows
