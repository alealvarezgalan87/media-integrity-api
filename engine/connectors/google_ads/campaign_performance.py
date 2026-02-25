"""Campaign performance extractor — Sprint 1, Task 1.1.

Extracts daily metrics: impressions, clicks, cost, conversions, conversion_value, ROAS.
Uses SearchStream for efficiency.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.advertising_channel_type,
  campaign.advertising_channel_sub_type,
  campaign.bidding_strategy_type,
  campaign.campaign_budget,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.all_conversions,
  metrics.all_conversions_value,
  metrics.average_cpc,
  metrics.ctr,
  metrics.cost_per_conversion,
  metrics.value_per_conversion
FROM campaign
WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND campaign.status != 'REMOVED'
ORDER BY segments.date DESC
"""


class CampaignPerformanceExtractor(BaseConnector):
    """Extracts campaign performance data from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract campaign performance for the given date range."""
        import time

        t0 = time.time()
        query = QUERY.format(start_date=start_date, end_date=end_date)
        rows = self._execute_query(query, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_campaign_performance.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
