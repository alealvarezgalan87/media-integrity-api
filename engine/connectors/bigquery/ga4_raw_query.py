"""BigQuery GA4 raw query connector — Sprint 4, Task 4.5.

Queries analytics_{property_id}.events_* tables for unsampled data.
Solves GA4 API sampling issues for high-traffic properties.
"""

from typing import Any

from engine.connectors.base_connector import BaseConnector

QUERY_CHANNEL_REVENUE = """
SELECT
  traffic_source.source AS session_source,
  traffic_source.medium AS session_medium,
  traffic_source.name AS campaign_name,
  COUNT(DISTINCT user_pseudo_id) AS users,
  COUNT(*) AS events,
  COUNTIF(event_name = 'purchase') AS purchases,
  SUM(CASE WHEN event_name = 'purchase'
    THEN (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value')
    ELSE 0 END) AS revenue
FROM `{project}.analytics_{property_id}.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{start_YYYYMMDD}' AND '{end_YYYYMMDD}'
GROUP BY 1, 2, 3
ORDER BY revenue DESC
"""

QUERY_CONVERSION_LAG = """
SELECT
  user_pseudo_id,
  MIN(CASE WHEN event_name = 'session_start' THEN event_timestamp END) AS first_session,
  MIN(CASE WHEN event_name = 'purchase' THEN event_timestamp END) AS first_purchase,
  TIMESTAMP_DIFF(
    TIMESTAMP_MICROS(MIN(CASE WHEN event_name = 'purchase' THEN event_timestamp END)),
    TIMESTAMP_MICROS(MIN(CASE WHEN event_name = 'session_start' THEN event_timestamp END)),
    DAY
  ) AS days_to_convert
FROM `{project}.analytics_{property_id}.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{start_YYYYMMDD}' AND '{end_YYYYMMDD}'
GROUP BY user_pseudo_id
HAVING first_purchase IS NOT NULL
"""


class BigQueryGA4Connector(BaseConnector):
    """Queries BigQuery for unsampled GA4 data."""

    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract unsampled GA4 data from BigQuery.

        Requires client to have GA4 -> BigQuery export enabled.
        """
        # TODO: Implement with google-cloud-bigquery client
        raise NotImplementedError("Sprint 4 — Task 4.5")
