"""Shopping structure normalization — Phase 3C.

Computes:
- shopping_campaign_product_overlap_pct: % of products targeted by 2+ Shopping campaigns
- shopping_rlsa_campaign_count: number of Shopping campaigns with RLSA audience lists
"""

import structlog

logger = structlog.get_logger(__name__)


def compute_shopping_structure_metrics(ss_data: list[dict]) -> dict:
    """Analyze Shopping campaign structure.

    Args:
        ss_data: Raw shopping_structure extractor output.

    Returns:
        Dict with shopping_campaign_product_overlap_pct, shopping_rlsa_campaign_count.
    """
    defaults = {
        "shopping_campaign_product_overlap_pct": 0.0,
        "shopping_rlsa_campaign_count": 0,
    }

    if not ss_data:
        return defaults

    inner = ss_data[0] if isinstance(ss_data[0], dict) else {}
    product_groups = inner.get("product_groups", [])
    campaign_audiences = inner.get("campaign_audiences", [])

    # ── Product overlap detection ──
    product_campaigns = {}
    for row in product_groups:
        campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
        criterion = row.get("ad_group_criterion", row.get("adGroupCriterion", {}))
        if isinstance(criterion, dict):
            lg = criterion.get("listing_group", criterion.get("listingGroup", {}))
            case_value = lg.get("case_value", lg.get("caseValue", {})) if isinstance(lg, dict) else {}
        else:
            case_value = {}

        camp_id = str(campaign.get("id", ""))
        if not camp_id:
            continue

        # Use product_item_id as the product identifier, fallback to brand+type
        pid = ""
        if isinstance(case_value, dict):
            item_id = case_value.get("product_item_id", case_value.get("productItemId", {}))
            brand = case_value.get("product_brand", case_value.get("productBrand", {}))
            ptype = case_value.get("product_type", case_value.get("productType", {}))

            if isinstance(item_id, dict) and item_id.get("value"):
                pid = f"item:{item_id['value']}"
            elif isinstance(brand, dict) and brand.get("value"):
                pid = f"brand:{brand['value']}"
            elif isinstance(ptype, dict) and ptype.get("value"):
                pid = f"type:{ptype['value']}"

        if pid:
            product_campaigns.setdefault(pid, set()).add(camp_id)

    total_products = len(product_campaigns)
    overlapping = sum(1 for p, camps in product_campaigns.items() if len(camps) >= 2)
    overlap_pct = overlapping / total_products if total_products > 0 else 0.0

    # ── RLSA detection ──
    shopping_with_rlsa = set()
    for row in campaign_audiences:
        campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
        channel = campaign.get("advertising_channel_type", "")
        camp_id = str(campaign.get("id", ""))

        if "SHOPPING" in str(channel).upper() and camp_id:
            shopping_with_rlsa.add(camp_id)

    result = {
        "shopping_campaign_product_overlap_pct": round(overlap_pct, 4),
        "shopping_rlsa_campaign_count": len(shopping_with_rlsa),
    }

    logger.info(
        "shopping_structure_metrics",
        total_products=total_products,
        overlapping_products=overlapping,
        overlap_pct=overlap_pct,
        shopping_rlsa_campaigns=len(shopping_with_rlsa),
    )
    return result
