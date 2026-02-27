"""Change history extractor — Sprint 1, Task 1.6.

Last 90 days of changes: what changed, who changed it, old value, new value.
Critical for audit trail.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  change_event.change_date_time,
  change_event.change_resource_type,
  change_event.change_resource_name,
  change_event.client_type,
  change_event.user_email,
  change_event.old_resource,
  change_event.new_resource,
  change_event.resource_change_operation,
  change_event.changed_fields
FROM change_event
WHERE change_event.change_date_time BETWEEN '{start_date}' AND '{end_date}'
ORDER BY change_event.change_date_time DESC
LIMIT 10000
"""


class ChangeHistoryExtractor(BaseConnector):
    """Extracts change history from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract change history for the given date range (max 30 days lookback)."""
        import time
        from datetime import date, timedelta

        t0 = time.time()

        # Google Ads API limits change_event queries to last 30 days
        max_lookback = (date.today() - timedelta(days=30)).isoformat()
        if start_date < max_lookback:
            self.logger.info(
                "clamping_start_date",
                original=start_date,
                clamped=max_lookback,
                reason="change_event max 30-day lookback",
            )
            start_date = max_lookback

        query = QUERY.format(start_date=start_date, end_date=end_date)
        rows = self._execute_query(query, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_change_history.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
