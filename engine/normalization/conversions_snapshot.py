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

    # ── Conversion source variance ──────────────────────────────
    conv_source_metrics = _calc_conversion_source_metrics(df)

    # ── Enhanced Conversions detection ────────────────────────────
    enhanced_conversions_enabled = _detect_enhanced_conversions(df)

    return {
        "attribution_model_count": attribution_model_count,
        "dda_adoption_rate": round(float(dda_adoption_rate), 4),
        "lookback_window_consistency": bool(lookback_window_consistency),
        "conversion_action_count": conversion_action_count,
        "ga4_ads_revenue_discrepancy": None,
        # Phase 2 metrics
        "conversion_source_count": conv_source_metrics["conversion_source_count"],
        "conversion_source_variance": conv_source_metrics["conversion_source_variance"],
        "enhanced_conversions_enabled": enhanced_conversions_enabled,
    }


def _calc_conversion_source_metrics(df: pd.DataFrame) -> dict:
    """Calculate conversion source count and variance."""
    if df.empty or "type" not in df.columns:
        return {"conversion_source_count": 0, "conversion_source_variance": 0.0}

    sources = df["type"].dropna().tolist()
    unique_sources = set(sources)

    source_counts: dict[str, int] = {}
    for s in sources:
        source_counts[s] = source_counts.get(s, 0) + 1

    values = list(source_counts.values())
    if len(values) <= 1:
        variance = 0.0
    else:
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        # Normalize to 0-1 range
        variance = min(variance / (mean ** 2) if mean > 0 else 0, 1.0)

    return {
        "conversion_source_count": len(unique_sources),
        "conversion_source_variance": round(variance, 3),
    }


def _detect_enhanced_conversions(df: pd.DataFrame) -> bool | None:
    """Detect if any conversion action has Enhanced Conversions enabled.

    Returns True if enabled, False if not, None if data not available.
    The enhanced_conversions_opt_in_status field may not be available
    in all Google Ads API versions.
    """
    ec_col = "enhanced_conversions_opt_in_status"
    if ec_col not in df.columns:
        # Field not available in extractor — return None (data insufficient)
        return None
    enabled = df[ec_col].astype(str).str.contains("ENABLED", case=False, na=False)
    return bool(enabled.any())
