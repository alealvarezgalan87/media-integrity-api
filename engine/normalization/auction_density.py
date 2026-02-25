"""Normalize auction insights — Sprint 2, Task 2.4.

Schema: One row per campaign per competitor per date period.
Search + Shopping ONLY.
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def _flatten_auction_row(row: dict) -> dict:
    """Flatten a nested Google Ads auction insight row."""
    campaign = row.get("campaign", {})
    segments = row.get("segments", {})
    metrics = row.get("metrics", {})
    return {
        "campaign_id": campaign.get("id"),
        "campaign_name": campaign.get("name"),
        "date": segments.get("date"),
        "display_domain": row.get("auction_insight", {}).get("display_domain",
                          row.get("display_domain")),
        "impression_share": metrics.get("auction_insight_search_impression_share",
                           row.get("impression_share", 0.0)),
        "overlap_rate": metrics.get("auction_insight_search_overlap_rate",
                       row.get("overlap_rate", 0.0)),
        "position_above_rate": metrics.get("auction_insight_search_position_above_rate",
                              row.get("position_above_rate", 0.0)),
        "top_of_page_rate": metrics.get("auction_insight_search_top_of_page_rate",
                           row.get("top_of_page_rate", 0.0)),
        "absolute_top_of_page_rate": metrics.get("auction_insight_search_absolute_top_of_page_rate",
                                    row.get("absolute_top_of_page_rate", 0.0)),
        "outranking_share": metrics.get("auction_insight_search_outranking_share",
                           row.get("outranking_share", 0.0)),
    }


def build_auction_density(auction_data: list[dict]) -> pd.DataFrame:
    """Build the auction_density canonical table.

    Args:
        auction_data: Raw auction insights from Google Ads (Search/Shopping only).

    Returns:
        DataFrame with one row per campaign per competitor per date.
    """
    if not auction_data:
        logger.warning("No auction data provided, returning empty DataFrame")
        return pd.DataFrame()

    flat_rows = [_flatten_auction_row(r) for r in auction_data]
    df = pd.DataFrame(flat_rows)

    logger.info("Built auction_density", rows=len(df))
    return df


def compute_auction_metrics(df: pd.DataFrame) -> dict:
    """Compute aggregated metrics for the demand_capture domain (auction part).

    Args:
        df: The auction_density canonical DataFrame.

    Returns:
        dict with avg_outranking_share for scoring.
    """
    if df.empty:
        return {
            "avg_outranking_share": None,
        }

    own_rows = df[df["display_domain"] == "(You)"] if "display_domain" in df.columns else df

    if own_rows.empty:
        own_rows = df

    avg_outranking_share = own_rows["outranking_share"].mean() if "outranking_share" in own_rows.columns else 0.0

    return {
        "avg_outranking_share": round(float(avg_outranking_share), 4),
    }
