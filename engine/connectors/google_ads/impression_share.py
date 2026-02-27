"""Impression share extractor — Sprint 1, Task 1.3.

Extracts search_impression_share, top_impression_percentage,
absolute_top_impression_percentage, budget_lost_IS, rank_lost_IS.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type,
  segments.date,
  metrics.search_impression_share,
  metrics.search_top_impression_share,
  metrics.search_absolute_top_impression_share,
  metrics.search_budget_lost_impression_share,
  metrics.search_rank_lost_impression_share,
  metrics.content_impression_share,
  metrics.content_budget_lost_impression_share,
  metrics.content_rank_lost_impression_share
FROM campaign
WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND campaign.status != 'REMOVED'
  AND campaign.advertising_channel_type IN ('SEARCH', 'SHOPPING', 'PERFORMANCE_MAX')
"""


class ImpressionShareExtractor(BaseConnector):
    """Extracts impression share metrics from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract impression share data for the given date range."""
        import time

        t0 = time.time()
        query = QUERY.format(start_date=start_date, end_date=end_date)
        rows = self._execute_query(query, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_impression_share.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
