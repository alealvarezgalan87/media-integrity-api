"""New Customer Acquisition settings extractor — Phase 3F.

Extracts NCA goal settings from PMax and Shopping campaigns.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type,
  campaign.bidding_strategy_type,
  campaign.customer_acquisition_goal_settings.optimization_mode,
  campaign.customer_acquisition_goal_settings.value_settings.high_lifetime_value
FROM campaign
WHERE campaign.status = 'ENABLED'
  AND campaign.advertising_channel_type IN ('PERFORMANCE_MAX', 'SHOPPING')
"""


class NCASettingsExtractor(BaseConnector):
    """Extracts New Customer Acquisition settings from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        import time

        t0 = time.time()
        try:
            rows = self._execute_query(QUERY, self.customer_id)
            data = self._parse_rows(rows)
        except Exception as e:
            # NCA settings may not be available for all accounts
            self.logger.warning("nca_settings_query_failed", error=str(e))
            data = []
        self._save_raw_json(data, "google_ads_nca_settings.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
