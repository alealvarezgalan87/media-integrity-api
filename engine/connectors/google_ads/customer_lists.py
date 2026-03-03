"""Customer Lists extractor — Phase 3E.

Extracts user list metadata to detect outdated or low-quality customer match lists.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  user_list.id,
  user_list.name,
  user_list.type,
  user_list.size_for_search,
  user_list.size_for_display,
  user_list.membership_status,
  user_list.match_rate_percentage,
  user_list.membership_life_span,
  user_list.size_range_for_search,
  user_list.size_range_for_display,
  user_list.eligible_for_search,
  user_list.eligible_for_display,
  user_list.resource_name
FROM user_list
WHERE user_list.type IN ('CRM_BASED', 'RULE_BASED', 'LOGICAL_USER_LIST')
  AND user_list.membership_status = 'OPEN'
"""


class CustomerListsExtractor(BaseConnector):
    """Extracts customer list metadata from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        import time

        t0 = time.time()
        rows = self._execute_query(QUERY, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_customer_lists.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
