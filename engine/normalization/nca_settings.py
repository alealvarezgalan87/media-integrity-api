"""NCA Settings normalization — Phase 3F.

Detects if NCA bid adjustments are set and flags them for validation.
"""

import structlog

logger = structlog.get_logger(__name__)


def compute_nca_metrics(nca_data: list[dict]) -> dict:
    """Analyze NCA bid settings.

    Args:
        nca_data: Raw nca_settings extractor output.

    Returns:
        Dict with nca_bid_adjustment (float), nca_bid_validation (bool).
    """
    defaults = {
        "nca_bid_adjustment": 0,
        "nca_bid_validation": True,
    }

    if not nca_data:
        return defaults

    nca_bids = []
    for row in nca_data:
        campaign = row.get("campaign", {}) if isinstance(row.get("campaign"), dict) else {}
        nca = campaign.get(
            "customer_acquisition_goal_settings",
            campaign.get("customerAcquisitionGoalSettings", {})
        )
        if not isinstance(nca, dict):
            continue

        opt_mode = nca.get("optimization_mode", nca.get("optimizationMode", ""))
        value_settings = nca.get("value_settings", nca.get("valueSettings", {}))
        if isinstance(value_settings, dict):
            hlv = value_settings.get("high_lifetime_value", value_settings.get("highLifetimeValue", 0))
        else:
            hlv = 0

        if opt_mode and str(opt_mode).upper() not in ("", "TARGET_ALL_EQUALLY", "UNSPECIFIED"):
            nca_bids.append(float(hlv or 0))

    if nca_bids:
        max_bid = max(nca_bids)
        result = {
            "nca_bid_adjustment": max_bid,
            "nca_bid_validation": False,
        }
    else:
        result = defaults

    logger.info(
        "nca_metrics",
        campaigns_with_nca=len(nca_bids),
        max_bid=max(nca_bids) if nca_bids else 0,
    )
    return result
