"""Keyword Quality Score normalization — Phase 3A.

Computes avg QS overall and avg QS for non-brand keywords,
using the brand classifier to split brand vs non-brand.
"""

import structlog
from engine.normalization.brand_classifier import _classify_campaign

logger = structlog.get_logger(__name__)


def compute_quality_score_metrics(qs_data: list[dict], brand_name: str = "") -> dict:
    """Compute avg quality score and non-brand avg quality score.

    Args:
        qs_data: Raw keyword_quality_score extractor output.
        brand_name: Account/brand name for classification.

    Returns:
        Dict with avg_quality_score, nonbrand_avg_quality_score.
    """
    defaults = {
        "avg_quality_score": None,
        "nonbrand_avg_quality_score": None,
    }

    if not qs_data:
        return defaults

    all_qs = []
    nonbrand_qs = []

    for row in qs_data:
        # Navigate nested proto structure
        campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
        criterion = row.get("ad_group_criterion", row.get("adGroupCriterion", {}))
        if isinstance(criterion, dict):
            qi = criterion.get("quality_info", criterion.get("qualityInfo", {}))
            kw = criterion.get("keyword", {})
        else:
            qi = {}
            kw = {}

        qs = qi.get("quality_score", qi.get("qualityScore"))
        if qs is None or qs == 0:
            continue

        qs = int(qs)
        all_qs.append(qs)

        # Classify campaign as brand/nonbrand
        camp_name = campaign.get("name", "")
        channel_type = campaign.get("advertising_channel_type", "SEARCH")
        classification = _classify_campaign(camp_name, channel_type, brand_name)

        if classification in ("nonbrand", "unknown"):
            nonbrand_qs.append(qs)

    result = {
        "avg_quality_score": round(sum(all_qs) / len(all_qs), 2) if all_qs else None,
        "nonbrand_avg_quality_score": round(sum(nonbrand_qs) / len(nonbrand_qs), 2) if nonbrand_qs else None,
    }

    logger.info(
        "quality_score_metrics",
        total_keywords=len(all_qs),
        nonbrand_keywords=len(nonbrand_qs),
        avg_qs=result["avg_quality_score"],
        nonbrand_avg_qs=result["nonbrand_avg_quality_score"],
    )
    return result
