"""MCP tools for Media Integrity Engine.

Defines the tools that external systems (e.g. Growth Signal) can invoke
via the Model Context Protocol.

Tools:
- run_media_audit: Run a full audit for a Google Ads account
- get_audit_status: Check the status of a running audit
- get_scorecard: Retrieve the scorecard for a completed audit
"""

import structlog

logger = structlog.get_logger(__name__)


def run_media_audit_sync(
    account_id: str,
    date_start: str,
    date_end: str,
    organization_id: str | None = None,
) -> dict:
    """Run a media integrity audit synchronously via Celery.

    Dispatches the audit task and waits for completion.

    Args:
        account_id: Google Ads customer ID (e.g. "123-456-7890").
        date_start: Start date YYYY-MM-DD.
        date_end: End date YYYY-MM-DD.
        organization_id: Optional org UUID. Uses first org if not provided.

    Returns:
        Dict with composite_score, risk_band, capital_implication,
        red_flag_count, confidence, domain_scores.
    """
    import django
    django.setup()

    from core.models import Audit, Organization

    # Resolve organization
    if organization_id:
        org = Organization.objects.get(id=organization_id)
    else:
        org = Organization.objects.first()
        if not org:
            return {"error": "No organization found. Create one first."}

    # Clean account_id (remove dashes)
    clean_account_id = account_id.replace("-", "")

    # Create the audit via the task
    from tasks.audit_tasks import run_audit_task

    logger.info(
        "mcp_run_media_audit",
        account_id=clean_account_id,
        date_start=date_start,
        date_end=date_end,
        org=org.name,
    )

    # Dispatch task and wait for result (sync call with timeout)
    result = run_audit_task.apply(
        args=[],
        kwargs={
            "organization_id": str(org.id),
            "account_id": clean_account_id,
            "date_start": date_start,
            "date_end": date_end,
            "source": "mcp",
        },
    )

    # The task returns the run_id
    task_result = result.get(timeout=300)  # 5 min timeout

    if isinstance(task_result, dict) and "error" in task_result:
        return task_result

    run_id = task_result.get("run_id") if isinstance(task_result, dict) else str(task_result)

    # Fetch the completed audit
    return _build_scorecard_response(run_id)


def get_audit_status_sync(run_id: str) -> dict:
    """Get the status of an audit by run_id.

    Args:
        run_id: The UUID of the audit.

    Returns:
        Dict with run_id, status, and result if completed.
    """
    import django
    django.setup()

    from core.models import Audit

    try:
        audit = Audit.objects.get(run_id=run_id)
    except Audit.DoesNotExist:
        return {"error": f"Audit {run_id} not found."}

    response = {
        "run_id": str(audit.run_id),
        "status": audit.status,
        "account_name": audit.account_name,
        "created_at": audit.created_at.isoformat(),
    }

    if audit.status == "success":
        response.update(_build_scorecard_response(str(audit.run_id)))

    return response


def get_scorecard_sync(run_id: str) -> dict:
    """Retrieve the scorecard for a completed audit.

    Args:
        run_id: The UUID of the audit.

    Returns:
        Dict with full scorecard data.
    """
    import django
    django.setup()

    return _build_scorecard_response(run_id)


def _build_scorecard_response(run_id: str) -> dict:
    """Build the standardized scorecard response for an audit."""
    from core.models import Audit, AuditDomainScore, AuditRedFlag

    try:
        audit = Audit.objects.get(run_id=run_id)
    except Audit.DoesNotExist:
        return {"error": f"Audit {run_id} not found."}

    if audit.status != "success":
        return {
            "run_id": str(audit.run_id),
            "status": audit.status,
            "message": f"Audit is {audit.status}, not yet complete.",
        }

    domain_scores = {}
    for ds in AuditDomainScore.objects.filter(audit=audit):
        domain_scores[ds.domain] = {
            "score": ds.value,
            "weight": ds.weight,
            "data_completeness": ds.data_completeness,
        }

    red_flags = AuditRedFlag.objects.filter(audit=audit)

    return {
        "run_id": str(audit.run_id),
        "status": "success",
        "account_name": audit.account_name,
        "date_range": f"{audit.date_range_start} to {audit.date_range_end}",
        "composite_score": audit.composite_score,
        "risk_band": audit.risk_band,
        "capital_implication": audit.capital_implication,
        "red_flag_count": red_flags.count(),
        "confidence": audit.confidence,
        "domain_scores": domain_scores,
        "red_flags_summary": [
            {
                "rule_id": rf.rule_id_raw,
                "severity": rf.severity,
                "title": rf.title,
            }
            for rf in red_flags
        ],
    }
