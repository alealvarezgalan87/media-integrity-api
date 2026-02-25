"""Auction insights extractor — Sprint 1, Task 1.5.

Search + Shopping ONLY. Not available for PMax, Display, Video.
Extracts impression share, overlap rate, position above rate, top of page rate per competitor.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY = """
SELECT
  campaign.id,
  campaign.name,
  segments.date,
  auction_insight.display_domain,
  metrics.auction_insight_search_impression_share,
  metrics.auction_insight_search_overlap_rate,
  metrics.auction_insight_search_position_above_rate,
  metrics.auction_insight_search_top_of_page_rate,
  metrics.auction_insight_search_absolute_top_of_page_rate,
  metrics.auction_insight_search_outranking_share
FROM campaign
WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND campaign.advertising_channel_type IN ('SEARCH', 'SHOPPING')
  AND campaign.status != 'REMOVED'
"""


class AuctionInsightsExtractor(BaseConnector):
    """Extracts auction insights from Google Ads API v23 (Search/Shopping only)."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract auction insights for the given date range."""
        import time

        t0 = time.time()
        query = QUERY.format(start_date=start_date, end_date=end_date)
        rows = self._execute_query(query, self.customer_id)
        data = self._parse_rows(rows)
        self._save_raw_json(data, "google_ads_auction_insights.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
