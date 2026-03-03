"""PMax Audience Signals extractor — Phase 3D.

Extracts audience signals from PMax asset groups to detect
prospecting vs retargeting split.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  campaign.id,
  campaign.name,
  asset_group.id,
  asset_group.name,
  asset_group_signal.audience.audience_segments
FROM asset_group_signal
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND campaign.status != 'REMOVED'
"""

QUERY_FALLBACK_ASSET_GROUPS = """
SELECT
  campaign.id,
  campaign.name,
  asset_group.id,
  asset_group.name,
  asset_group.status
FROM asset_group
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND campaign.status != 'REMOVED'
  AND asset_group.status = 'ENABLED'
"""

QUERY_PMAX_AUDIENCES = """
SELECT
  campaign.id,
  campaign.name,
  campaign_criterion.type,
  campaign_criterion.user_list.user_list
FROM campaign_criterion
WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
  AND campaign_criterion.type = 'USER_LIST'
  AND campaign.status != 'REMOVED'
"""


class PMaxAudienceSignalsExtractor(BaseConnector):
    """Extracts PMax audience signals from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        import time

        t0 = time.time()

        # Try primary query first
        signals = []
        try:
            rows = self._execute_query(QUERY, self.customer_id)
            signals = self._parse_rows(rows)
        except Exception as e:
            self.logger.warning("asset_group_signal_query_failed", error=str(e))

        # Fallback: get asset groups and campaign-level audience targets
        asset_groups = []
        pmax_audiences = []
        if not signals:
            try:
                rows_ag = self._execute_query(QUERY_FALLBACK_ASSET_GROUPS, self.customer_id)
                asset_groups = self._parse_rows(rows_ag)
            except Exception as e:
                self.logger.warning("asset_groups_query_failed", error=str(e))

            try:
                rows_aud = self._execute_query(QUERY_PMAX_AUDIENCES, self.customer_id)
                pmax_audiences = self._parse_rows(rows_aud)
            except Exception as e:
                self.logger.warning("pmax_audiences_query_failed", error=str(e))

        data = {
            "asset_group_signals": signals,
            "asset_groups": asset_groups,
            "pmax_audiences": pmax_audiences,
        }

        flat = signals + asset_groups + pmax_audiences
        self._save_raw_json(flat, "google_ads_pmax_audience_signals.json", self.output_dir)
        self.log_extraction(len(flat), time.time() - t0)
        return [data]
