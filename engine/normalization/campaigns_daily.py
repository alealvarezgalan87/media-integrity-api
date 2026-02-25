"""Normalize campaign performance into daily rows — Sprint 2, Task 2.1.

Schema: One row per campaign per day.
Derived fields: roas = conversion_value / cost, budget_utilization = cost / budget_amount.
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def _safe_div(numerator, denominator, default=0.0):
    """Safe division that never raises ZeroDivisionError."""
    return numerator / denominator if denominator != 0 else default


def _flatten_campaign_row(row: dict) -> dict:
    """Flatten a nested Google Ads campaign row into a flat dict."""
    campaign = row.get("campaign", {})
    segments = row.get("segments", {})
    metrics = row.get("metrics", {})
    return {
        "campaign_id": campaign.get("id"),
        "campaign_name": campaign.get("name"),
        "campaign_status": campaign.get("status"),
        "advertising_channel_type": campaign.get("advertising_channel_type"),
        "advertising_channel_sub_type": campaign.get("advertising_channel_sub_type"),
        "bidding_strategy_type": campaign.get("bidding_strategy_type"),
        "campaign_budget": campaign.get("campaign_budget"),
        "date": segments.get("date"),
        "impressions": metrics.get("impressions", 0),
        "clicks": metrics.get("clicks", 0),
        "cost_micros": metrics.get("cost_micros", 0),
        "conversions": metrics.get("conversions", 0.0),
        "conversions_value": metrics.get("conversions_value", 0.0),
        "all_conversions": metrics.get("all_conversions", 0.0),
        "all_conversions_value": metrics.get("all_conversions_value", 0.0),
        "average_cpc": metrics.get("average_cpc", 0),
        "ctr": metrics.get("ctr", 0.0),
    }


def _flatten_budget_row(row: dict) -> dict:
    """Flatten a nested Google Ads budget row."""
    campaign = row.get("campaign", {})
    budget = row.get("campaign_budget", {})
    segments = row.get("segments", {})
    metrics = row.get("metrics", {})
    return {
        "campaign_id": campaign.get("id"),
        "campaign_name": campaign.get("name"),
        "budget_amount_micros": budget.get("amount_micros", row.get("budget_amount_micros", 0)),
        "date": segments.get("date"),
        "budget_cost_micros": metrics.get("cost_micros", 0),
    }


def _flatten_impression_share_row(row: dict) -> dict:
    """Flatten a nested Google Ads impression share row."""
    campaign = row.get("campaign", {})
    segments = row.get("segments", {})
    metrics = row.get("metrics", {})
    return {
        "campaign_id": campaign.get("id"),
        "campaign_name": campaign.get("name"),
        "advertising_channel_type": campaign.get("advertising_channel_type"),
        "date": segments.get("date"),
        "search_impression_share": metrics.get("search_impression_share", 0.0),
        "search_top_impression_percentage": metrics.get("search_top_impression_percentage", 0.0),
        "search_absolute_top_impression_percentage": metrics.get("search_absolute_top_impression_percentage", 0.0),
        "search_budget_lost_impression_share": metrics.get("search_budget_lost_impression_share", 0.0),
        "search_rank_lost_impression_share": metrics.get("search_rank_lost_impression_share", 0.0),
        "content_impression_share": metrics.get("content_impression_share", 0.0),
        "content_budget_lost_impression_share": metrics.get("content_budget_lost_impression_share", 0.0),
        "content_rank_lost_impression_share": metrics.get("content_rank_lost_impression_share", 0.0),
    }


def build_campaigns_daily(
    campaign_data: list[dict],
    budget_data: list[dict],
    impression_share_data: list[dict],
) -> pd.DataFrame:
    """Build the campaigns_daily canonical table.

    Args:
        campaign_data: Raw campaign performance from Google Ads.
        budget_data: Raw budget allocation data.
        impression_share_data: Raw impression share metrics.

    Returns:
        DataFrame with one row per campaign per day.
    """
    if not campaign_data:
        logger.warning("No campaign data provided, returning empty DataFrame")
        return pd.DataFrame()

    flat_campaigns = [_flatten_campaign_row(r) for r in campaign_data]
    df = pd.DataFrame(flat_campaigns)

    df["cost"] = df["cost_micros"] / 1_000_000

    df["roas"] = df.apply(
        lambda r: _safe_div(r["conversions_value"], r["cost"]), axis=1
    )

    if budget_data:
        flat_budgets = [_flatten_budget_row(r) for r in budget_data]
        budget_df = pd.DataFrame(flat_budgets)
        if "budget_amount_micros" in budget_df.columns:
            budget_df["budget_amount"] = budget_df["budget_amount_micros"] / 1_000_000
            merge_cols = ["campaign_id", "date"]
            available_cols = [c for c in merge_cols if c in budget_df.columns and c in df.columns]
            if available_cols:
                budget_merge = budget_df[available_cols + ["budget_amount"]].drop_duplicates(subset=available_cols)  # type: ignore[arg-type]
                df = df.merge(budget_merge, on=available_cols, how="left")
                df["budget_amount"] = df["budget_amount"].fillna(0)
            else:
                df["budget_amount"] = 0
        else:
            df["budget_amount"] = 0
    else:
        df["budget_amount"] = 0

    df["budget_utilization"] = df.apply(
        lambda r: _safe_div(r["cost"], r["budget_amount"]), axis=1
    )

    if impression_share_data:
        flat_is = [_flatten_impression_share_row(r) for r in impression_share_data]
        is_df = pd.DataFrame(flat_is)
        is_cols = [
            "search_impression_share", "search_top_impression_percentage",
            "search_absolute_top_impression_percentage",
            "search_budget_lost_impression_share", "search_rank_lost_impression_share",
            "content_impression_share", "content_budget_lost_impression_share",
            "content_rank_lost_impression_share",
        ]
        merge_cols = ["campaign_id", "date"]
        available_merge = [c for c in merge_cols if c in is_df.columns and c in df.columns]
        if available_merge:
            keep_cols = available_merge + [c for c in is_cols if c in is_df.columns]
            is_merge = is_df[keep_cols].drop_duplicates(subset=available_merge)
            df = df.merge(is_merge, on=available_merge, how="left")
            for col in is_cols:
                if col in df.columns:
                    df[col] = df[col].fillna(0.0)

    logger.info("Built campaigns_daily", rows=len(df))
    return df


def compute_campaigns_metrics(df: pd.DataFrame) -> dict:
    """Compute aggregated metrics for demand_capture and capital_allocation domains.

    Args:
        df: The campaigns_daily canonical DataFrame.

    Returns:
        dict with keys for both demand_capture and capital_allocation scoring.
    """
    if df.empty:
        return {
            "avg_search_impression_share": 0.0,
            "avg_budget_lost_impression_share": 0.0,
            "avg_rank_lost_impression_share": 0.0,
            "avg_budget_utilization": 0.0,
            "spend_concentration_hhi": 0.0,
            "roas_variance_coefficient": 0.0,
            "zero_conversion_spend_pct": 0.0,
            "campaign_count": 0,
        }

    is_col = "search_impression_share"
    avg_search_impression_share = df[is_col].mean() if is_col in df.columns else 0.0

    bl_col = "search_budget_lost_impression_share"
    avg_budget_lost_impression_share = df[bl_col].mean() if bl_col in df.columns else 0.0

    rl_col = "search_rank_lost_impression_share"
    avg_rank_lost_impression_share = df[rl_col].mean() if rl_col in df.columns else 0.0

    avg_budget_utilization = df["budget_utilization"].mean() if "budget_utilization" in df.columns else 0.0

    total_spend = df["cost"].sum()
    campaign_spend = df.groupby("campaign_id")["cost"].sum()
    if total_spend > 0:
        shares = campaign_spend / total_spend
        spend_concentration_hhi = (shares ** 2).sum()
    else:
        spend_concentration_hhi = 0.0

    campaign_roas = df.groupby("campaign_id")["roas"].mean()
    roas_mean = campaign_roas.mean()
    roas_std = campaign_roas.std()
    roas_variance_coefficient = _safe_div(roas_std, roas_mean) if pd.notna(roas_std) and pd.notna(roas_mean) else 0.0

    campaign_conversions = df.groupby("campaign_id")["conversions"].sum()
    campaign_costs = df.groupby("campaign_id")["cost"].sum()
    zero_conv_campaigns = (campaign_conversions == 0) & (campaign_costs > 0)
    zero_conv_spend = campaign_costs[zero_conv_campaigns].sum()
    zero_conversion_spend_pct = _safe_div(zero_conv_spend, total_spend)

    campaign_count = df["campaign_id"].nunique()

    return {
        "avg_search_impression_share": round(float(avg_search_impression_share), 4),
        "avg_budget_lost_impression_share": round(float(avg_budget_lost_impression_share), 4),
        "avg_rank_lost_impression_share": round(float(avg_rank_lost_impression_share), 4),
        "avg_budget_utilization": round(float(avg_budget_utilization), 4),
        "spend_concentration_hhi": round(float(spend_concentration_hhi), 4),
        "roas_variance_coefficient": round(float(roas_variance_coefficient), 4),
        "zero_conversion_spend_pct": round(float(zero_conversion_spend_pct), 4),
        "campaign_count": int(campaign_count),
    }
