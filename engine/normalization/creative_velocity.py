"""Normalize asset performance over time — Sprint 2, Task 2.5.

Schema: One row per asset per snapshot date.
Track performance_label changes across snapshots.
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

EXPECTED_FIELD_TYPES = {
    "HEADLINE", "LONG_HEADLINE", "DESCRIPTION", "MARKETING_IMAGE",
    "SQUARE_MARKETING_IMAGE", "PORTRAIT_MARKETING_IMAGE",
    "LOGO", "LANDSCAPE_LOGO", "YOUTUBE_VIDEO", "CALL_TO_ACTION_SELECTION",
    "BUSINESS_NAME",
}


def _flatten_asset_row(row: dict) -> dict:
    """Flatten a nested Google Ads asset performance row."""
    asset_group = row.get("asset_group", {})
    asset_group_asset = row.get("asset_group_asset", row.get("asset_group_asset", {}))
    asset = row.get("asset", {})
    policy = asset_group_asset.get("policy_summary", {})
    return {
        "asset_group_id": asset_group.get("id", row.get("asset_group_id")),
        "asset_group_name": asset_group.get("name", row.get("asset_group_name")),
        "campaign": asset_group.get("campaign", row.get("campaign")),
        "asset_id": asset.get("id", row.get("asset_id")),
        "asset_name": asset.get("name", row.get("asset_name")),
        "asset_type": asset.get("type", row.get("asset_type")),
        "field_type": asset_group_asset.get("field_type", row.get("field_type")),
        "performance_label": asset_group_asset.get("performance_label", row.get("performance_label")),
        "approval_status": policy.get("approval_status", row.get("approval_status")),
        "final_urls": asset.get("final_urls", row.get("final_urls")),
        "snapshot_date": row.get("snapshot_date", row.get("date")),
    }


def build_creative_velocity(asset_data: list[dict]) -> pd.DataFrame:
    """Build the creative_velocity canonical table.

    Args:
        asset_data: Raw asset performance from Google Ads.

    Returns:
        DataFrame with one row per asset per snapshot date.
    """
    if not asset_data:
        logger.warning("No asset data provided, returning empty DataFrame")
        return pd.DataFrame()

    flat_rows = [_flatten_asset_row(r) for r in asset_data]
    df = pd.DataFrame(flat_rows)

    logger.info("Built creative_velocity", rows=len(df))
    return df


def _safe_div(numerator, denominator, default=0.0):
    """Safe division that never raises ZeroDivisionError."""
    return numerator / denominator if denominator != 0 else default


def compute_creative_metrics(df: pd.DataFrame) -> dict:
    """Compute aggregated metrics for the creative_velocity domain.

    Args:
        df: The creative_velocity canonical DataFrame.

    Returns:
        dict with creative_velocity scoring keys.
    """
    if df.empty:
        return {
            "total_asset_count": 0,
            "asset_groups_count": 0,
            "pct_best_performing": 0.0,
            "pct_good_performing": 0.0,
            "pct_low_performing": 0.0,
            "pct_disapproved": 0.0,
            "format_diversity": 0,
            "data_completeness": 0.0,
        }

    total_asset_count = df["asset_id"].nunique() if "asset_id" in df.columns else len(df)

    asset_groups_count = 0
    if "asset_group_id" in df.columns:
        asset_groups_count = int(df["asset_group_id"].dropna().nunique())

    perf_col = "performance_label"
    total_rows = len(df)
    if perf_col in df.columns:
        perf_values = df[perf_col].fillna("UNSPECIFIED")
        pct_best_performing = _safe_div((perf_values == "BEST").sum(), total_rows)
        pct_good_performing = _safe_div((perf_values == "GOOD").sum(), total_rows)
        pct_low_performing = _safe_div((perf_values == "LOW").sum(), total_rows)
    else:
        pct_best_performing = 0.0
        pct_good_performing = 0.0
        pct_low_performing = 0.0

    approval_col = "approval_status"
    if approval_col in df.columns:
        pct_disapproved = _safe_div(
            (df[approval_col] == "DISAPPROVED").sum(), total_rows
        )
    else:
        pct_disapproved = 0.0

    format_diversity = 0
    if "field_type" in df.columns:
        format_diversity = int(df["field_type"].dropna().nunique())

    present_types = set(df["field_type"].dropna().unique()) if "field_type" in df.columns else set()
    data_completeness = _safe_div(len(present_types.intersection(EXPECTED_FIELD_TYPES)),
                                  len(EXPECTED_FIELD_TYPES)) if EXPECTED_FIELD_TYPES else 0.0

    return {
        "total_asset_count": int(total_asset_count),
        "asset_groups_count": asset_groups_count,
        "pct_best_performing": round(float(pct_best_performing), 4),
        "pct_good_performing": round(float(pct_good_performing), 4),
        "pct_low_performing": round(float(pct_low_performing), 4),
        "pct_disapproved": round(float(pct_disapproved), 4),
        "format_diversity": format_diversity,
        "data_completeness": round(float(data_completeness), 4),
    }
