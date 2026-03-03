"""Keyword Quality Score extractor — Phase 3A.

Extracts Quality Score components at keyword level for brand vs non-brand analysis.
Only extracts ENABLED keywords from ENABLED ad groups in SEARCH campaigns.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type,
  ad_group.id,
  ad_group.name,
  ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type,
  ad_group_criterion.quality_info.quality_score,
  ad_group_criterion.quality_info.creative_relevance_status,
  ad_group_criterion.quality_info.post_click_quality_score_status,
  ad_group_criterion.quality_info.search_predicted_ctr,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM keyword_view
WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND campaign.status = 'ENABLED'
  AND ad_group.status = 'ENABLED'
  AND ad_group_criterion.status = 'ENABLED'
  AND campaign.advertising_channel_type = 'SEARCH'
"""


class KeywordQualityScoreExtractor(BaseConnector):
    """Extracts keyword-level Quality Score data from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        import time

        t0 = time.time()
        query = QUERY.format(start_date=start_date, end_date=end_date)
        rows = self._execute_query(query, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_keyword_quality_score.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
