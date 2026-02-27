"""Asset performance extractor — Sprint 1, Task 1.7.

Extracts asset type, performance_label, policy_summary for PMax and responsive ads.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  asset_group.id,
  asset_group.name,
  asset_group.campaign,
  asset_group_asset.asset,
  asset_group_asset.field_type,
  asset_group_asset.status,
  asset.id,
  asset.name,
  asset.type,
  asset.final_urls
FROM asset_group_asset
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND asset_group.status != 'REMOVED'
"""


class AssetPerformanceExtractor(BaseConnector):
    """Extracts asset performance data from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract asset performance data."""
        import time

        t0 = time.time()
        rows = self._execute_query(QUERY, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_asset_performance.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
