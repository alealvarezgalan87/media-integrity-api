"""Cross-reference Google Ads and GA4 attribution settings — Sprint 4, Task 4.7.

Schema: Cross-platform attribution comparison.
Phase 2 (Sprint 4+).
Flag mismatches between Google Ads and GA4 attribution models.
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def build_attribution_config(
    google_ads_conversions: list[dict],
    ga4_attribution: list[dict],
) -> pd.DataFrame:
    """Build the attribution_config canonical table.

    Args:
        google_ads_conversions: Conversion action config from Google Ads.
        ga4_attribution: Attribution data from GA4.

    Returns:
        DataFrame with cross-platform attribution comparison.
    """
    if not google_ads_conversions:
        logger.info("attribution_config_no_gads_data")
        return pd.DataFrame()

    # Build Google Ads side
    gads_rows = []
    for conv in google_ads_conversions:
        name = conv.get("name") or conv.get("conversion_action_name", "")
        model = conv.get("attribution_model") or conv.get("attribution_model_type", "UNKNOWN")
        conversions = float(conv.get("conversions", 0) or 0)
        gads_rows.append({
            "conversion_action": name,
            "google_ads_model": str(model),
            "google_ads_conversions": conversions,
        })

    df = pd.DataFrame(gads_rows)

    # Build GA4 side — GA4 uses Data-Driven Attribution (DDA) by default
    if ga4_attribution:
        ga4_total = sum(float(r.get("conversions", 0) or 0) for r in ga4_attribution)
        df["ga4_model"] = "DATA_DRIVEN"
        df["ga4_conversions"] = ga4_total / max(len(df), 1)
    else:
        df["ga4_model"] = None
        df["ga4_conversions"] = None

    # Calculate match and discrepancy
    df["model_match"] = df.apply(
        lambda r: r["google_ads_model"] == r["ga4_model"] if r["ga4_model"] else None,
        axis=1,
    )
    df["discrepancy_pct"] = df.apply(
        lambda r: (
            round(abs(float(r["ga4_conversions"] or 0) - r["google_ads_conversions"])
                  / max(r["google_ads_conversions"], 1) * 100, 2)
            if r["ga4_conversions"] is not None else None
        ),
        axis=1,
    )

    logger.info("attribution_config_built", rows=len(df))
    return df
