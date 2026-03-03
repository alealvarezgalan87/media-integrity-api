"""Normalize GA4 channel performance data — Sprint 4, Task 4.6.

Schema: One row per channel per day.
Phase 2 (Sprint 4+).
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

NUMERIC_COLS = [
    "totalRevenue", "transactions", "purchaseRevenue",
    "sessions", "engagedSessions", "totalUsers", "conversions",
]


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
    if not ga4_channel_data:
        logger.info("ga4_channel_performance_empty")
        return pd.DataFrame()

    df = pd.DataFrame(ga4_channel_data)

    # Cast numeric columns (GA4 API returns strings)
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Rename to snake_case
    rename_map = {
        "sessionDefaultChannelGroup": "channel_group",
        "totalRevenue": "revenue",
        "purchaseRevenue": "purchase_revenue",
        "engagedSessions": "engaged_sessions",
        "totalUsers": "users",
    }
    df = df.rename(columns=rename_map)

    # Calculate derived metrics
    df["revenue_per_session"] = df.apply(
        lambda r: round(r["revenue"] / r["sessions"], 4) if r["sessions"] > 0 else 0,
        axis=1,
    )
    df["conversion_rate"] = df.apply(
        lambda r: round(r["conversions"] / r["sessions"], 4) if r["sessions"] > 0 else 0,
        axis=1,
    )

    df["data_source"] = data_source

    logger.info("ga4_channel_performance_built", rows=len(df))
    return df
