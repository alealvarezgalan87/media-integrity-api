"""Normalize GA4 channel performance data — Sprint 4, Task 4.6.

Schema: One row per channel per day.
Phase 2 (Sprint 4+).
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def build_ga4_channel_performance(
    ga4_channel_data: list[dict],
    data_source: str = "GA4_API",
) -> pd.DataFrame:
    """Build the ga4_channel_performance canonical table.

    Args:
        ga4_channel_data: Raw GA4 channel revenue data.
        data_source: "GA4_API" or "BIGQUERY".

    Returns:
        DataFrame with one row per channel per day.
    """
    # TODO: Implement normalization
    # - Calculate revenue_per_session, conversion_rate
    # - Tag data_source
    raise NotImplementedError("Sprint 4 — Task 4.6")
