"""GA4 Data API v1 connectors."""

import structlog
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2.credentials import Credentials

logger = structlog.get_logger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"


def build_ga4_data_client(credentials: dict) -> BetaAnalyticsDataClient:
    """Build a BetaAnalyticsDataClient from OAuth2 credentials dict."""
    creds = Credentials(
        token=None,
        refresh_token=credentials["refresh_token"],
        token_uri=TOKEN_URI,
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
    )
    return BetaAnalyticsDataClient(credentials=creds)


def parse_report_response(response) -> list[dict]:
    """Parse a GA4 RunReportResponse into a list of dicts."""
    rows = []
    dim_headers = [h.name for h in response.dimension_headers]
    met_headers = [h.name for h in response.metric_headers]

    for row in response.rows:
        d = {}
        for i, dim in enumerate(row.dimension_values):
            d[dim_headers[i]] = dim.value
        for i, met in enumerate(row.metric_values):
            d[met_headers[i]] = met.value
        rows.append(d)
    return rows


def run_ga4_report(
    credentials: dict,
    property_id: str,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    metrics: list[str],
) -> list[dict]:
    """Run a GA4 report and return parsed rows.

    Args:
        credentials: dict with client_id, client_secret, refresh_token.
        property_id: GA4 property ID (e.g. "345678901").
        start_date: YYYY-MM-DD.
        end_date: YYYY-MM-DD.
        dimensions: List of dimension names.
        metrics: List of metric names.

    Returns:
        List of dicts with dimension and metric values.
    """
    client = build_ga4_data_client(credentials)

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        limit=100000,
    )

    response = client.run_report(request)
    rows = parse_report_response(response)

    logger.info(
        "ga4_report_complete",
        property_id=property_id,
        dimensions=dimensions,
        metrics=metrics,
        row_count=len(rows),
    )
    return rows
