"""BigQuery GA4 raw query connector — Sprint 4, Task 4.5.

Queries analytics_{property_id}.events_* tables for unsampled data.
Solves GA4 API sampling issues for high-traffic properties.
"""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── SQL Templates ──────────────────────────────────────────────────────

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
WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
GROUP BY 1, 2, 3
ORDER BY revenue DESC
"""

QUERY_TRAFFIC_ACQUISITION = """
SELECT
  traffic_source.source AS session_source,
  traffic_source.medium AS session_medium,
  COUNT(DISTINCT user_pseudo_id) AS total_users,
  COUNTIF(event_name = 'session_start') AS sessions
FROM `{project}.analytics_{property_id}.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
GROUP BY 1, 2
ORDER BY sessions DESC
"""

QUERY_PAID_VS_ORGANIC = """
SELECT
  CASE
    WHEN traffic_source.medium IN ('cpc', 'ppc', 'cpm', 'cpv', 'cpa', 'cpp')
      THEN 'paid'
    ELSE 'organic'
  END AS category,
  COUNT(DISTINCT user_pseudo_id) AS users,
  COUNTIF(event_name = 'purchase') AS conversions,
  SUM(CASE WHEN event_name = 'purchase'
    THEN (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value')
    ELSE 0 END) AS totalRevenue
FROM `{project}.analytics_{property_id}.events_*`
WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
GROUP BY 1
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
WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
GROUP BY user_pseudo_id
HAVING first_purchase IS NOT NULL
"""


class BigQueryGA4Connector:
    """Queries BigQuery for unsampled GA4 data.

    Uses the user's OAuth2 credentials to query their BigQuery project
    where GA4 exports event data to analytics_{property_id}.events_* tables.
    """

    def __init__(
        self,
        credentials: dict,
        bq_project_id: str,
        property_id: str,
    ):
        self.bq_project_id = bq_project_id
        self.property_id = property_id
        self._credentials = credentials
        self._client = None

    def _get_access_token(self) -> str:
        """Get a valid OAuth2 access token for BigQuery API calls."""
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials(
            token=None,
            refresh_token=self._credentials["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._credentials["client_id"],
            client_secret=self._credentials["client_secret"],
        )
        creds.refresh(Request())
        return creds.token

    def extract(self, start_date: str, end_date: str) -> dict[str, Any]:
        """Extract unsampled GA4 data from BigQuery.

        Args:
            start_date: YYYY-MM-DD format.
            end_date: YYYY-MM-DD format.

        Returns:
            Dict with channel_revenue, traffic_acquisition, paid_vs_organic,
            conversion_lag, and source="bigquery".
        """
        start_fmt = start_date.replace("-", "")
        end_fmt = end_date.replace("-", "")

        logger.info(
            "bq_extract_start",
            project=self.bq_project_id,
            property_id=self.property_id,
            date_range=f"{start_date} to {end_date}",
        )

        result = {"source": "bigquery"}

        result["channel_revenue"] = self._run_query(
            "channel_revenue", QUERY_CHANNEL_REVENUE, start_fmt, end_fmt
        )
        result["traffic_acquisition"] = self._run_query(
            "traffic_acquisition", QUERY_TRAFFIC_ACQUISITION, start_fmt, end_fmt
        )
        result["paid_vs_organic"] = self._run_query(
            "paid_vs_organic", QUERY_PAID_VS_ORGANIC, start_fmt, end_fmt
        )
        result["conversion_lag"] = self._run_query(
            "conversion_lag", QUERY_CONVERSION_LAG, start_fmt, end_fmt
        )

        logger.info(
            "bq_extract_complete",
            channels=len(result["channel_revenue"]),
            traffic=len(result["traffic_acquisition"]),
            paid_organic=len(result["paid_vs_organic"]),
            conv_lag=len(result["conversion_lag"]),
        )

        return result

    def _run_query(
        self, name: str, template: str, start_fmt: str, end_fmt: str
    ) -> list[dict]:
        """Execute a single BQ query via REST API with error isolation.

        Uses the BigQuery REST API directly instead of the client library
        to avoid scope validation issues in the google-cloud-bigquery SDK.
        """
        import json
        import urllib.request
        import urllib.error

        try:
            sql = template.format(
                project=self.bq_project_id,
                property_id=self.property_id,
                start=start_fmt,
                end=end_fmt,
            )

            token = self._get_access_token()
            url = (
                f"https://bigquery.googleapis.com/bigquery/v2"
                f"/projects/{self.bq_project_id}/queries"
            )
            body = json.dumps({
                "query": sql,
                "useLegacySql": False,
                "timeoutMs": 120000,
                "maxResults": 10000,
            }).encode()

            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=130) as resp:
                result = json.loads(resp.read())

            if not result.get("jobComplete"):
                logger.warning("bq_query_incomplete", query=name)
                return []

            schema = result.get("schema", {}).get("fields", [])
            field_names = [f["name"] for f in schema]
            rows = result.get("rows", [])

            data = []
            for row in rows:
                values = row.get("f", [])
                record = {}
                for i, field in enumerate(field_names):
                    raw_val = values[i]["v"] if i < len(values) else None
                    record[field] = self._cast_value(raw_val, schema[i])
                data.append(record)

            logger.info("bq_query_complete", query=name, rows=len(data))
            return data

        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            logger.warning("bq_query_failed", query=name, error=f"HTTP {e.code}: {body}")
            return []
        except Exception as e:
            logger.warning("bq_query_failed", query=name, error=str(e))
            return []

    @staticmethod
    def _cast_value(raw, field_schema: dict):
        """Cast a BigQuery REST API value to the appropriate Python type."""
        if raw is None:
            return None
        ftype = field_schema.get("type", "STRING")
        try:
            if ftype in ("INTEGER", "INT64"):
                return int(raw)
            elif ftype in ("FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"):
                return float(raw)
            elif ftype == "BOOLEAN":
                return raw.lower() in ("true", "1")
            else:
                return raw
        except (ValueError, TypeError):
            return raw
