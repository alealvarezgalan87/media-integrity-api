"""Negative Keywords extractor — Phase 3B.

Extracts campaign-level negative keywords and shared negative keyword lists
to detect overlaps and insufficient Shopping coverage.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY_CAMPAIGN_NEGATIVES = """
SELECT
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type,
  campaign_criterion.keyword.text,
  campaign_criterion.keyword.match_type,
  campaign_criterion.negative
FROM campaign_criterion
WHERE campaign_criterion.type = 'KEYWORD'
  AND campaign_criterion.negative = true
  AND campaign.status != 'REMOVED'
"""

QUERY_SHARED_SETS = """
SELECT
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type,
  campaign_shared_set.shared_set,
  campaign_shared_set.status,
  shared_set.name,
  shared_set.type,
  shared_set.member_count
FROM campaign_shared_set
WHERE shared_set.type = 'NEGATIVE_KEYWORDS'
  AND campaign_shared_set.status = 'ENABLED'
  AND campaign.status != 'REMOVED'
"""


class NegativeKeywordsExtractor(BaseConnector):
    """Extracts negative keyword data from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract negative keywords (campaign-level + shared lists)."""
        import time

        t0 = time.time()

        # Campaign-level negatives
        rows_camp = self._execute_query(QUERY_CAMPAIGN_NEGATIVES, self.customer_id)
        camp_negatives = self._parse_rows(rows_camp)

        # Shared sets
        rows_shared = self._execute_query(QUERY_SHARED_SETS, self.customer_id)
        shared_sets = self._parse_rows(rows_shared)

        data = {
            "campaign_negatives": camp_negatives,
            "shared_sets": shared_sets,
        }

        flat = camp_negatives + [{"_type": "shared_set", **s} for s in shared_sets]
        self._save_raw_json(flat, "google_ads_negative_keywords.json", self.output_dir)
        self.log_extraction(len(flat), time.time() - t0)
        return [data]
