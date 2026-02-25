"""Normalize PMax campaigns by channel (v23 data) — Sprint 2, Task 2.3.

Schema: One row per PMax campaign per channel per day.
Only for dates >= June 1, 2025.
Derived fields: channel_cost_share, channel_conversion_share.
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

AUTOMATED_BIDDING_TYPES = {
    "MAXIMIZE_CONVERSIONS",
    "MAXIMIZE_CONVERSION_VALUE",
    "TARGET_CPA",
    "TARGET_ROAS",
    "TARGET_SPEND",
    "TARGET_IMPRESSION_SHARE",
}


def _safe_div(numerator, denominator, default=0.0):
    """Safe division that never raises ZeroDivisionError."""
    return numerator / denominator if denominator != 0 else default


def _flatten_pmax_row(row: dict) -> dict:
    """Flatten a nested Google Ads PMax breakdown row."""
    campaign = row.get("campaign", {})
    segments = row.get("segments", {})
    metrics = row.get("metrics", {})
    return {
        "campaign_id": campaign.get("id"),
        "campaign_name": campaign.get("name"),
        "date": segments.get("date"),
        "ad_network_type": segments.get("ad_network_type"),
        "impressions": metrics.get("impressions", 0),
        "clicks": metrics.get("clicks", 0),
        "cost_micros": metrics.get("cost_micros", 0),
        "conversions": metrics.get("conversions", 0.0),
        "conversions_value": metrics.get("conversions_value", 0.0),
        "all_conversions": metrics.get("all_conversions", 0.0),
        "all_conversions_value": metrics.get("all_conversions_value", 0.0),
    }


def _flatten_campaign_row(row: dict) -> dict:
    """Flatten a campaign row for total spend context."""
    campaign = row.get("campaign", {})
    segments = row.get("segments", {})
    metrics = row.get("metrics", {})
    return {
        "campaign_id": campaign.get("id"),
        "campaign_name": campaign.get("name"),
        "advertising_channel_type": campaign.get("advertising_channel_type"),
        "bidding_strategy_type": campaign.get("bidding_strategy_type"),
        "date": segments.get("date"),
        "cost_micros": metrics.get("cost_micros", 0),
    }


def build_pmax_breakdown(pmax_data: list[dict]) -> pd.DataFrame:
    """Build the pmax_breakdown canonical table.

    Args:
        pmax_data: Raw PMax channel breakdown from Google Ads API v23.

    Returns:
        DataFrame with one row per PMax campaign per channel per day.
    """
    if not pmax_data:
        logger.warning("No PMax data provided, returning empty DataFrame")
        return pd.DataFrame()

    flat_rows = [_flatten_pmax_row(r) for r in pmax_data]
    df = pd.DataFrame(flat_rows)

    df["cost"] = df["cost_micros"] / 1_000_000

    df["is_legacy_mixed"] = df["ad_network_type"] == "MIXED"

    total_cost_per_date = df.groupby("date")["cost"].transform("sum")
    df["channel_cost_share"] = df.apply(
        lambda r: _safe_div(r["cost"], total_cost_per_date.loc[r.name]), axis=1
    )

    total_conv_per_date = df.groupby("date")["conversions_value"].transform("sum")
    df["channel_conversion_share"] = df.apply(
        lambda r: _safe_div(r["conversions_value"], total_conv_per_date.loc[r.name]), axis=1
    )

    logger.info("Built pmax_breakdown", rows=len(df))
    return df


def compute_automation_metrics(df: pd.DataFrame, campaign_df: pd.DataFrame) -> dict:
    """Compute aggregated metrics for the automation_exposure domain.

    Args:
        df: The pmax_breakdown canonical DataFrame.
        campaign_df: The campaigns_daily DataFrame for total spend context.

    Returns:
        dict with automation_exposure scoring keys.
    """
    if campaign_df is None or campaign_df.empty:
        return {
            "pct_spend_automated": 0.0,
            "pct_spend_pmax": 0.0,
            "pmax_channel_concentration": 0.0,
            "bidding_strategy_diversity": 0,
        }

    total_spend = campaign_df["cost"].sum() if "cost" in campaign_df.columns else 0.0

    pmax_spend = 0.0
    if not df.empty and "cost" in df.columns:
        pmax_spend = df["cost"].sum()

    pct_spend_pmax = _safe_div(pmax_spend, total_spend)

    automated_spend = 0.0
    if "bidding_strategy_type" in campaign_df.columns and "cost" in campaign_df.columns:
        auto_mask = campaign_df["bidding_strategy_type"].isin(AUTOMATED_BIDDING_TYPES)
        automated_spend = campaign_df.loc[auto_mask, "cost"].sum()
    pct_spend_automated = _safe_div(automated_spend, total_spend)

    pmax_channel_concentration = 0.0
    if not df.empty and "cost" in df.columns:
        pmax_total = df["cost"].sum()
        if pmax_total > 0:
            channel_spend = df.groupby("ad_network_type")["cost"].sum()
            shares = channel_spend / pmax_total
            pmax_channel_concentration = float((shares ** 2).sum())

    bidding_strategy_diversity = 0
    if "bidding_strategy_type" in campaign_df.columns:
        bidding_strategy_diversity = int(campaign_df["bidding_strategy_type"].dropna().nunique())

    return {
        "pct_spend_automated": round(float(pct_spend_automated), 4),
        "pct_spend_pmax": round(float(pct_spend_pmax), 4),
        "pmax_channel_concentration": round(float(pmax_channel_concentration), 4),
        "bidding_strategy_diversity": bidding_strategy_diversity,
    }
