"""Normalize conversion actions with config + recent performance — Sprint 2, Task 2.2.

Schema: One row per conversion action.
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def _flatten_conversion_row(row: dict) -> dict:
    """Flatten a nested Google Ads conversion action row."""
    ca = row.get("conversion_action", row)
    attr_settings = ca.get("attribution_model_settings", {})
    value_settings = ca.get("value_settings", {})
    return {
        "conversion_action_id": ca.get("id"),
        "name": ca.get("name"),
        "type": ca.get("type"),
        "category": ca.get("category"),
        "status": ca.get("status"),
        "counting_type": ca.get("counting_type"),
        "attribution_model": attr_settings.get("attribution_model", ca.get("attribution_model")),
        "data_driven_model_status": attr_settings.get("data_driven_model_status", ca.get("data_driven_model_status")),
        "default_value": value_settings.get("default_value", ca.get("default_value")),
        "always_use_default_value": value_settings.get("always_use_default_value", ca.get("always_use_default_value")),
        "click_through_lookback_window_days": ca.get("click_through_lookback_window_days"),
        "view_through_lookback_window_days": ca.get("view_through_lookback_window_days"),
        "include_in_conversions_metric": ca.get("include_in_conversions_metric"),
    }


def build_conversions_snapshot(conversion_actions_data: list[dict]) -> pd.DataFrame:
    """Build the conversions_snapshot canonical table.

    Args:
        conversion_actions_data: Raw conversion action config from Google Ads.

    Returns:
        DataFrame with one row per conversion action.
    """
    if not conversion_actions_data:
        logger.warning("No conversion actions data provided, returning empty DataFrame")
        return pd.DataFrame()

    flat_rows = [_flatten_conversion_row(r) for r in conversion_actions_data]
    df = pd.DataFrame(flat_rows)

    logger.info("Built conversions_snapshot", rows=len(df))
    return df


def compute_measurement_metrics(df: pd.DataFrame) -> dict:
    """Compute aggregated metrics for the measurement_integrity domain.

    Args:
        df: The conversions_snapshot canonical DataFrame.

    Returns:
        dict with measurement_integrity scoring keys.
    """
    if df.empty:
        return {
            "attribution_model_count": 0,
            "dda_adoption_rate": 0.0,
            "lookback_window_consistency": True,
            "conversion_action_count": 0,
            "ga4_ads_revenue_discrepancy": None,
        }

    conversion_action_count = len(df)

    attr_col = "attribution_model"
    if attr_col in df.columns:
        unique_models = df[attr_col].dropna().nunique()
        attribution_model_count = int(unique_models)

        dda_mask = df[attr_col].str.contains("DATA_DRIVEN", case=False, na=False)
        dda_count = dda_mask.sum()
        dda_adoption_rate = dda_count / conversion_action_count if conversion_action_count > 0 else 0.0
    else:
        attribution_model_count = 0
        dda_adoption_rate = 0.0

    lb_col = "click_through_lookback_window_days"
    if lb_col in df.columns:
        lb_values = df[lb_col].dropna()
        lookback_window_consistency = lb_values.nunique() <= 1 if len(lb_values) > 0 else True
    else:
        lookback_window_consistency = True

    return {
        "attribution_model_count": attribution_model_count,
        "dda_adoption_rate": round(float(dda_adoption_rate), 4),
        "lookback_window_consistency": bool(lookback_window_consistency),
        "conversion_action_count": conversion_action_count,
        "ga4_ads_revenue_discrepancy": None,
    }
