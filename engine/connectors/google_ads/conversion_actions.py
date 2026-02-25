"""Conversion actions config extractor — Sprint 1, Task 1.4.

Extracts all conversion actions: name, type, category, counting_type,
attribution_model, lookback_window.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  conversion_action.id,
  conversion_action.name,
  conversion_action.type,
  conversion_action.category,
  conversion_action.status,
  conversion_action.counting_type,
  conversion_action.attribution_model_settings.attribution_model,
  conversion_action.attribution_model_settings.data_driven_model_status,
  conversion_action.value_settings.default_value,
  conversion_action.value_settings.always_use_default_value,
  conversion_action.click_through_lookback_window_days,
  conversion_action.view_through_lookback_window_days,
  conversion_action.include_in_conversions_metric
FROM conversion_action
WHERE conversion_action.status != 'REMOVED'
"""


class ConversionActionsExtractor(BaseConnector):
    """Extracts conversion action configuration from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract conversion action config."""
        import time

        t0 = time.time()
        rows = self._execute_query(QUERY, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_conversion_actions.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
