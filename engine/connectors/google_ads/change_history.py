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
WHERE change_event.change_date_time BETWEEN '{start_datetime}' AND '{end_datetime}'
ORDER BY change_event.change_date_time DESC
LIMIT 10000
"""


class ChangeHistoryExtractor(BaseConnector):
    """Extracts change history from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract change history for the given date range (max 90 days lookback)."""
        import time

        t0 = time.time()
        start_datetime = f"{start_date}T00:00:00"
        end_datetime = f"{end_date}T23:59:59"
        query = QUERY.format(start_datetime=start_datetime, end_datetime=end_datetime)
        rows = self._execute_query(query, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_change_history.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
