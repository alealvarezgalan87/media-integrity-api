"""GA4 Events normalization — Phase 3G.

Computes:
- tracked_funnel_events: count of standard ecommerce funnel events tracked
- missing_funnel_events: list of expected events not tracked
"""

import structlog

logger = structlog.get_logger(__name__)

MID_FUNNEL_EVENTS = {
    "add_to_cart",
    "begin_checkout",
    "view_item",
    "view_item_list",
    "sign_up",
    "generate_lead",
}


def compute_ga4_events_metrics(events_data: list[dict]) -> dict:
    """Analyze GA4 event tracking completeness.

    Args:
        events_data: Raw events_list extractor output (list of {eventName, eventCount}).

    Returns:
        Dict with tracked_funnel_events (int), missing_funnel_events (list[str]).
    """
    defaults = {
        "tracked_funnel_events": None,
        "missing_funnel_events": [],
    }

    if not events_data:
        return defaults

    tracked = set()
    for row in events_data:
        name = row.get("eventName", "")
        count = int(row.get("eventCount", 0) or 0)
        if name and count > 0:
            tracked.add(name.lower())

    tracked_mid_funnel = tracked & MID_FUNNEL_EVENTS
    missing = sorted(MID_FUNNEL_EVENTS - tracked)

    result = {
        "tracked_funnel_events": len(tracked_mid_funnel),
        "missing_funnel_events": missing,
    }

    logger.info(
        "ga4_events_metrics",
        total_events=len(tracked),
        mid_funnel_tracked=len(tracked_mid_funnel),
        missing=missing,
    )
    return result
