"""Brand/Non-brand campaign classifier.

Heurística para clasificar campaigns como brand, nonbrand o unknown
basándose en el nombre de la campaña y el nombre de la cuenta/brand.
"""

import re

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

BRAND_KEYWORDS = [
    "brand", "branded", "branding",
    "trademark", "tm",
]

NONBRAND_KEYWORDS = [
    "nonbrand", "non-brand", "non brand",
    "generic", "prospecting", "conquest",
    "discovery", "awareness",
    "dsa", "dynamic search",
]


def _classify_campaign(name: str, channel_type: str, brand_name: str) -> str:
    """Classify a single campaign as brand, nonbrand, unknown, or other.

    Args:
        name: Campaign name (lowercased for matching).
        channel_type: advertising_channel_type (SEARCH, SHOPPING, etc.).
        brand_name: Brand/account name for matching.

    Returns:
        One of: "brand", "nonbrand", "unknown", "other".
    """
    name_lower = name.lower()
    channel_lower = str(channel_type).upper()

    # Non-search campaigns → other (Shopping, PMax, Display, Video, etc.)
    if channel_lower not in ("SEARCH", "2"):
        return "other"

    # Check for nonbrand keywords first (more specific, e.g. "non-brand" contains "brand")
    for kw in NONBRAND_KEYWORDS:
        if kw in name_lower:
            return "nonbrand"

    # Check for brand name in campaign name
    if brand_name:
        brand_lower = brand_name.lower()
        # Strip common suffixes from brand names
        brand_clean = re.sub(r"[_\-\s]+(ad\s*account|de|us|uk|eu|ca|au).*$", "", brand_lower, flags=re.IGNORECASE).strip()
        if brand_clean and len(brand_clean) >= 3 and brand_clean in name_lower:
            return "brand"

    # Check for brand keywords
    for kw in BRAND_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", name_lower):
            return "brand"

    # Unclassified search campaign → unknown (treated as nonbrand for metrics)
    return "unknown"


def classify_brand_nonbrand(campaigns_df: pd.DataFrame, brand_name: str = "") -> dict:
    """Classify each campaign as brand, nonbrand, or unknown.

    Args:
        campaigns_df: DataFrame with campaign data (must have 'campaign_name' column).
        brand_name: The brand/account name for matching.

    Returns:
        Dict with:
        - brand_spend_pct: float (0-1)
        - nonbrand_search_impression_share: float (0-1)
        - nonbrand_abs_top_impression_share: float (0-1)
        - campaign_classifications: list of {campaign_name, classification}
    """
    defaults = {
        "brand_spend_pct": 0.0,
        "nonbrand_search_impression_share": 0.0,
        "nonbrand_abs_top_impression_share": 0.0,
    }

    if campaigns_df.empty or "campaign_name" not in campaigns_df.columns:
        return defaults

    channel_col = "advertising_channel_type" if "advertising_channel_type" in campaigns_df.columns else None

    # Classify each row
    campaigns_df = campaigns_df.copy()
    campaigns_df["_brand_class"] = campaigns_df.apply(
        lambda r: _classify_campaign(
            str(r.get("campaign_name", "")),
            str(r.get(channel_col, "SEARCH")) if channel_col else "SEARCH",
            brand_name,
        ),
        axis=1,
    )

    # Aggregate by campaign (since df may have daily rows)
    campaign_agg = campaigns_df.groupby("campaign_id").agg({
        "cost": "sum",
        "_brand_class": "first",
    }).reset_index() if "campaign_id" in campaigns_df.columns else campaigns_df

    total_spend = campaign_agg["cost"].sum() if "cost" in campaign_agg.columns else 0
    brand_spend = campaign_agg.loc[
        campaign_agg["_brand_class"] == "brand", "cost"
    ].sum() if "cost" in campaign_agg.columns else 0

    brand_spend_pct = round(float(brand_spend / total_spend), 4) if total_spend > 0 else 0.0

    # Nonbrand IS metrics (from search campaigns classified as nonbrand or unknown)
    nonbrand_mask = campaigns_df["_brand_class"].isin(["nonbrand", "unknown"])
    nonbrand_rows = campaigns_df[nonbrand_mask]

    nonbrand_search_impression_share = 0.0
    if not nonbrand_rows.empty and "search_impression_share" in nonbrand_rows.columns:
        vals = nonbrand_rows["search_impression_share"].dropna()
        nonbrand_search_impression_share = round(float(vals.mean()), 4) if len(vals) > 0 else 0.0

    nonbrand_abs_top_impression_share = 0.0
    if not nonbrand_rows.empty and "search_absolute_top_impression_share" in nonbrand_rows.columns:
        vals = nonbrand_rows["search_absolute_top_impression_share"].dropna()
        nonbrand_abs_top_impression_share = round(float(vals.mean()), 4) if len(vals) > 0 else 0.0

    classifications = campaigns_df[["campaign_name", "_brand_class"]].drop_duplicates()
    counts = classifications["_brand_class"].value_counts().to_dict()
    logger.info(
        "brand_classification_complete",
        brand=counts.get("brand", 0),
        nonbrand=counts.get("nonbrand", 0),
        unknown=counts.get("unknown", 0),
        other=counts.get("other", 0),
        brand_spend_pct=brand_spend_pct,
    )

    return {
        "brand_spend_pct": brand_spend_pct,
        "nonbrand_search_impression_share": nonbrand_search_impression_share,
        "nonbrand_abs_top_impression_share": nonbrand_abs_top_impression_share,
    }
