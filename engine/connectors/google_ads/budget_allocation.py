"""Budget allocation extractor — Sprint 1, Task 1.2.

Extracts budget amount, delivery method, period, shared budget status.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY_BUDGETS = """
SELECT
  campaign_budget.id,
  campaign_budget.name,
  campaign_budget.amount_micros,
  campaign_budget.delivery_method,
  campaign_budget.period,
  campaign_budget.total_amount_micros,
  campaign_budget.status,
  campaign_budget.explicitly_shared,
  campaign_budget.reference_count
FROM campaign_budget
WHERE campaign_budget.status != 'REMOVED'
"""

QUERY_CAMPAIGN_BUDGETS = """
SELECT
  campaign.id,
  campaign.name,
  campaign.campaign_budget,
  campaign_budget.amount_micros,
  metrics.cost_micros,
  segments.date
FROM campaign
WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND campaign.status != 'REMOVED'
"""


class BudgetAllocationExtractor(BaseConnector):
    """Extracts budget allocation data from Google Ads API v23."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract budget allocation for the given date range."""
        import time

        t0 = time.time()
        budget_rows = self._execute_query(QUERY_BUDGETS, self.customer_id)
        budgets = self._parse_rows(budget_rows)

        campaign_query = QUERY_CAMPAIGN_BUDGETS.format(start_date=start_date, end_date=end_date)
        campaign_rows = self._execute_query(campaign_query, self.customer_id)
        campaign_budgets = self._parse_rows(campaign_rows)

        data = budgets + campaign_budgets
        self._save_raw_json(data, "google_ads_budget_allocation.json", self.output_dir)
        self.log_extraction(len(data), time.time() - t0)
        return data
