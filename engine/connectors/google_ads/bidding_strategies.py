"""Bidding strategy extractor — Sprint 1, Task 1.8.

Extracts strategy type (tCPA, tROAS, maximize conversions, etc.),
target values, campaign assignment.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.bidding_strategy_type,
  campaign.bidding_strategy,
  bidding_strategy.id,
  bidding_strategy.name,
  bidding_strategy.type,
  bidding_strategy.target_cpa.target_cpa_micros,
  bidding_strategy.target_roas.target_roas,
  bidding_strategy.maximize_conversions.target_cpa_micros,
  bidding_strategy.maximize_conversion_value.target_roas
FROM campaign
WHERE campaign.status != 'REMOVED'
"""


class BiddingStrategiesExtractor(BaseConnector):
    """Extracts bidding strategy data from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract bidding strategy configuration."""
        import time

        t0 = time.time()
        rows = self._execute_query(QUERY, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_bidding_strategies.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
