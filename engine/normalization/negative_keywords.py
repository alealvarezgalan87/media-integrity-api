"""Negative Keywords normalization — Phase 3B.

Computes:
- negative_keyword_overlap_count: number of negative keywords that appear in 2+ campaigns
- shopping_negative_keyword_coverage: ratio of Shopping campaigns with adequate negatives
"""

import structlog
from collections import Counter

logger = structlog.get_logger(__name__)


def compute_negative_keyword_metrics(nk_data: list[dict]) -> dict:
    """Analyze negative keyword health.

    Args:
        nk_data: Raw negative_keywords extractor output (list with 1 dict
                 containing 'campaign_negatives' and 'shared_sets').

    Returns:
        Dict with negative_keyword_overlap_count, shopping_negative_keyword_coverage.
    """
    defaults = {
        "negative_keyword_overlap_count": 0,
        "shopping_negative_keyword_coverage": 1.0,
    }

    if not nk_data:
        return defaults

    # Unwrap the single-item list
    inner = nk_data[0] if isinstance(nk_data[0], dict) else {}
    camp_negatives = inner.get("campaign_negatives", [])
    shared_sets = inner.get("shared_sets", [])

    # ── Overlap detection ──
    keyword_campaigns = {}
    for row in camp_negatives:
        campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
        criterion = row.get("campaign_criterion", row.get("campaignCriterion", {}))
        if isinstance(criterion, dict):
            kw_info = criterion.get("keyword", {})
        else:
            kw_info = {}

        camp_id = campaign.get("id", campaign.get("resource_name", ""))
        kw_text = kw_info.get("text", "").lower().strip()

        if kw_text and camp_id:
            keyword_campaigns.setdefault(kw_text, set()).add(str(camp_id))

    overlap_count = sum(1 for kw, camps in keyword_campaigns.items() if len(camps) >= 2)

    # ── Shopping negative keyword coverage ──
    shopping_campaigns = set()
    shopping_with_negatives = set()

    for row in camp_negatives:
        campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
        channel = campaign.get("advertising_channel_type", "")
        camp_id = str(campaign.get("id", ""))
        if "SHOPPING" in str(channel).upper():
            shopping_campaigns.add(camp_id)
            shopping_with_negatives.add(camp_id)

    for row in shared_sets:
        campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
        channel = campaign.get("advertising_channel_type", "")
        camp_id = str(campaign.get("id", ""))
        if "SHOPPING" in str(channel).upper():
            shopping_campaigns.add(camp_id)
            shopping_with_negatives.add(camp_id)

    if shopping_campaigns:
        coverage = len(shopping_with_negatives) / len(shopping_campaigns)
    else:
        coverage = 1.0

    result = {
        "negative_keyword_overlap_count": overlap_count,
        "shopping_negative_keyword_coverage": round(coverage, 4),
    }

    logger.info(
        "negative_keyword_metrics",
        total_campaign_negatives=len(camp_negatives),
        shared_sets=len(shared_sets),
        overlap_count=overlap_count,
        shopping_coverage=coverage,
    )
    return result
