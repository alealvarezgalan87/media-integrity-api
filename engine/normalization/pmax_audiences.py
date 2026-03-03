"""PMax audience signals normalization — Phase 3D.

Detects whether PMax campaigns have a proper prospecting vs retargeting split
by analyzing audience signals in asset groups.
"""

import structlog

logger = structlog.get_logger(__name__)

RETARGETING_TYPES = {"REMARKETING", "CUSTOMER_LIST", "USER_LIST"}
PROSPECTING_TYPES = {"CUSTOM_AUDIENCE", "IN_MARKET", "AFFINITY", "CUSTOM_INTENT"}


def compute_pmax_audience_metrics(pmax_aud_data: list[dict]) -> dict:
    """Analyze PMax audience signal separation.

    Returns:
        Dict with pmax_prospecting_campaign_count, pmax_retargeting_campaign_count.
    """
    defaults = {
        "pmax_prospecting_campaign_count": 0,
        "pmax_retargeting_campaign_count": 0,
    }

    if not pmax_aud_data:
        return defaults

    inner = pmax_aud_data[0] if isinstance(pmax_aud_data[0], dict) else {}
    signals = inner.get("asset_group_signals", [])
    asset_groups = inner.get("asset_groups", [])
    pmax_audiences = inner.get("pmax_audiences", [])

    prospecting_campaigns = set()
    retargeting_campaigns = set()

    if signals:
        for row in signals:
            campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
            camp_id = str(campaign.get("id", ""))
            signal = row.get("asset_group_signal", row.get("assetGroupSignal", {}))
            audience = signal.get("audience", {}) if isinstance(signal, dict) else {}
            segments = audience.get("audience_segments", audience.get("audienceSegments", []))

            if not camp_id:
                continue

            for seg in (segments if isinstance(segments, list) else []):
                seg_type = ""
                if isinstance(seg, dict):
                    for key in ("type", "audience_segment_type", "audienceSegmentType"):
                        if key in seg:
                            seg_type = str(seg[key]).upper()
                            break

                if any(rt in seg_type for rt in RETARGETING_TYPES):
                    retargeting_campaigns.add(camp_id)
                elif any(pt in seg_type for pt in PROSPECTING_TYPES):
                    prospecting_campaigns.add(camp_id)
    else:
        # Fallback: if a PMax campaign has USER_LIST criteria → retargeting
        pmax_camp_ids = set()
        for row in asset_groups:
            campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
            pmax_camp_ids.add(str(campaign.get("id", "")))

        camps_with_audiences = set()
        for row in pmax_audiences:
            campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
            camps_with_audiences.add(str(campaign.get("id", "")))

        retargeting_campaigns = camps_with_audiences & pmax_camp_ids
        prospecting_campaigns = pmax_camp_ids - retargeting_campaigns

    result = {
        "pmax_prospecting_campaign_count": len(prospecting_campaigns),
        "pmax_retargeting_campaign_count": len(retargeting_campaigns),
    }

    logger.info(
        "pmax_audience_metrics",
        prospecting=len(prospecting_campaigns),
        retargeting=len(retargeting_campaigns),
    )
    return result
