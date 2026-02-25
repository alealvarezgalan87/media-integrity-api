"""PMax channel breakdown extractor — Sprint 1, Task 1.9.

NEW in Google Ads API v23. Returns channel-level data for PMax:
SEARCH, YOUTUBE_WATCH, DISPLAY, DISCOVER, GMAIL, MAPS, SEARCH_PARTNERS.

CRITICAL: Only for dates >= June 1, 2025. Earlier dates return MIXED.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  campaign.id,
  campaign.name,
  segments.date,
  segments.ad_network_type,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.all_conversions,
  metrics.all_conversions_value
FROM campaign
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND campaign.status != 'REMOVED'
"""


class PMaxBreakdownExtractor(BaseConnector):
    """Extracts PMax channel-level breakdown from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract PMax channel breakdown for the given date range.

        Note: Dates before June 1, 2025 will return MIXED instead of
        individual channel values.
        """
        import time

        t0 = time.time()
        query = QUERY.format(start_date=start_date, end_date=end_date)
        rows = self._execute_query(query, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_pmax_breakdown.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
