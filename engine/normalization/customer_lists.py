"""Customer Lists normalization — Phase 3E.

Computes:
- customer_list_match_rate: average match rate across CRM-based lists
- days_since_customer_list_refresh: estimated from change_history
"""

import structlog

logger = structlog.get_logger(__name__)


def compute_customer_list_metrics(cl_data: list[dict], change_data: list[dict] | None = None) -> dict:
    """Analyze customer list health.

    Args:
        cl_data: Raw customer_lists extractor output.
        change_data: Optional change_history data for CRM upload events.

    Returns:
        Dict with days_since_customer_list_refresh, customer_list_match_rate.
    """
    defaults = {
        "days_since_customer_list_refresh": 0,
        "customer_list_match_rate": 1.0,
    }

    if not cl_data:
        return defaults

    crm_lists = []
    match_rates = []
    too_small = 0

    for row in cl_data:
        ul = row.get("user_list", row.get("userList", {}))
        if not isinstance(ul, dict):
            continue

        list_type = ul.get("type", "")
        if "CRM" in str(list_type).upper():
            crm_lists.append(ul)

            mr = ul.get("match_rate_percentage", ul.get("matchRatePercentage"))
            if mr is not None:
                match_rates.append(float(mr) / 100.0)

            size_search = int(ul.get("size_for_search", ul.get("sizeForSearch", 0)) or 0)
            size_display = int(ul.get("size_for_display", ul.get("sizeForDisplay", 0)) or 0)
            if size_search == 0 and size_display == 0:
                too_small += 1

    avg_match_rate = sum(match_rates) / len(match_rates) if match_rates else 1.0

    # Estimate days since refresh from change_history
    days_since_refresh = 0
    if change_data:
        from datetime import datetime, timezone
        latest_upload = None
        for row in change_data:
            change = row.get("change_event", row.get("changeEvent", {}))
            if not isinstance(change, dict):
                continue
            changed_resource = change.get("change_resource_type", change.get("changeResourceType", ""))
            if "USER_LIST" in str(changed_resource).upper():
                change_date = change.get("change_date_time", change.get("changeDateTime", ""))
                if change_date:
                    try:
                        dt = datetime.fromisoformat(str(change_date).replace("Z", "+00:00"))
                        if latest_upload is None or dt > latest_upload:
                            latest_upload = dt
                    except (ValueError, TypeError):
                        pass
        if latest_upload:
            days_since_refresh = (datetime.now(timezone.utc) - latest_upload).days
        else:
            days_since_refresh = 91

    result = {
        "days_since_customer_list_refresh": days_since_refresh,
        "customer_list_match_rate": round(avg_match_rate, 4),
    }

    logger.info(
        "customer_list_metrics",
        crm_lists=len(crm_lists),
        avg_match_rate=avg_match_rate,
        too_small=too_small,
        days_since_refresh=days_since_refresh,
    )
    return result
