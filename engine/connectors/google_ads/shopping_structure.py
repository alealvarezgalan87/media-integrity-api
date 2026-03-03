"""Shopping campaign structure extractor — Phase 3C.

Extracts product group targeting and audience lists from Shopping campaigns
to detect product overlap and missing RLSA.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY_SHOPPING_PRODUCT_GROUPS = """
SELECT
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type,
  ad_group.id,
  ad_group.name,
  ad_group_criterion.listing_group.type,
  ad_group_criterion.listing_group.case_value.product_brand.value,
  ad_group_criterion.listing_group.case_value.product_type.value,
  ad_group_criterion.listing_group.case_value.product_item_id.value,
  ad_group_criterion.listing_group.case_value.product_category.category_id,
  ad_group_criterion.status
FROM ad_group_criterion
WHERE campaign.advertising_channel_type = 'SHOPPING'
  AND ad_group_criterion.type = 'LISTING_GROUP'
  AND campaign.status != 'REMOVED'
  AND ad_group.status != 'REMOVED'
"""

QUERY_CAMPAIGN_AUDIENCES = """
SELECT
  campaign.id,
  campaign.name,
  campaign.advertising_channel_type,
  campaign_criterion.type,
  campaign_criterion.user_list.user_list
FROM campaign_criterion
WHERE campaign_criterion.type = 'USER_LIST'
  AND campaign.status != 'REMOVED'
  AND campaign.advertising_channel_type IN ('SHOPPING', 'SEARCH', 'PERFORMANCE_MAX')
"""


class ShoppingStructureExtractor(BaseConnector):
    """Extracts Shopping campaign structure from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        import time

        t0 = time.time()

        # Product groups
        try:
            rows_pg = self._execute_query(QUERY_SHOPPING_PRODUCT_GROUPS, self.customer_id)
            product_groups = self._parse_rows(rows_pg)
        except Exception as e:
            self.logger.warning("shopping_product_groups_query_failed", error=str(e))
            product_groups = []

        # Audience targets
        try:
            rows_aud = self._execute_query(QUERY_CAMPAIGN_AUDIENCES, self.customer_id)
            audiences = self._parse_rows(rows_aud)
        except Exception as e:
            self.logger.warning("campaign_audiences_query_failed", error=str(e))
            audiences = []

        data = {
            "product_groups": product_groups,
            "campaign_audiences": audiences,
        }

        flat = product_groups + [{"_type": "audience", **a} for a in audiences]
        self._save_raw_json(flat, "google_ads_shopping_structure.json", self.output_dir)
        self.log_extraction(len(flat), time.time() - t0)
        return [data]
