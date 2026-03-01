"""
Celery tasks for syncing Google Ads accounts from MCC to local DB.
"""

import structlog
from celery import shared_task
from django.utils import timezone

logger = structlog.get_logger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def sync_google_accounts(self, organization_id: str):
    """Sync Google Ads accounts from MCC into GoogleAdsAccount table."""
    from core.models import GoogleAdsAccount, GoogleAdsCredential, Organization

    try:
        org = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        logger.error("sync_accounts_org_not_found", organization_id=organization_id)
        return {"status": "error", "message": "Organization not found"}

    try:
        creds = org.google_credentials
    except GoogleAdsCredential.DoesNotExist:
        logger.warning("sync_accounts_no_credentials", org=org.name)
        return {"status": "skipped", "message": "No credentials configured"}

    if not all([creds.developer_token, creds.client_id, creds.client_secret, creds.refresh_token, creds.mcc_id]):
        logger.warning("sync_accounts_incomplete_credentials", org=org.name)
        return {"status": "skipped", "message": "Incomplete credentials"}

    try:
        from engine.auth.mcc_manager import MCCManager

        manager = MCCManager(
            credentials={
                "developer_token": creds.developer_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "refresh_token": creds.refresh_token,
            },
            mcc_customer_id=creds.mcc_id,
        )
        remote_accounts = manager.list_accessible_accounts()
    except Exception as exc:
        logger.error("sync_accounts_api_failed", org=org.name, error=str(exc))
        raise self.retry(exc=exc)

    now = timezone.now()
    remote_ids = set()

    for acc in remote_accounts:
        remote_ids.add(acc["id"])
        GoogleAdsAccount.objects.update_or_create(
            organization=org,
            account_id=acc["id"],
            defaults={
                "account_name": acc.get("name", ""),
                "currency": acc.get("currency", ""),
                "timezone": acc.get("timezone", ""),
                "is_active": True,
                "last_synced_at": now,
            },
        )

    # Deactivate accounts no longer in MCC
    deactivated = GoogleAdsAccount.objects.filter(
        organization=org, is_active=True
    ).exclude(account_id__in=remote_ids).update(is_active=False)

    logger.info(
        "sync_accounts_done",
        org=org.name,
        synced=len(remote_accounts),
        deactivated=deactivated,
    )

    return {
        "status": "ok",
        "synced": len(remote_accounts),
        "deactivated": deactivated,
    }


@shared_task
def sync_google_accounts_all():
    """Periodic task: sync accounts for all orgs with valid credentials.
    
    Respects each org's account_sync_interval_hours setting.
    """
    from datetime import timedelta

    from core.models import GoogleAdsAccount, GoogleAdsCredential

    creds_qs = GoogleAdsCredential.objects.filter(
        is_verified=True,
        developer_token__gt="",
        mcc_id__gt="",
    ).select_related("organization")

    now = timezone.now()
    count = 0
    for cred in creds_qs:
        interval = timedelta(hours=cred.account_sync_interval_hours or 6)

        # Check last sync time for this org
        last_sync = (
            GoogleAdsAccount.objects.filter(organization=cred.organization)
            .order_by("-last_synced_at")
            .values_list("last_synced_at", flat=True)
            .first()
        )

        if last_sync and (now - last_sync) < interval:
            logger.debug("sync_accounts_skipped", org=cred.organization.name, next_in=str(interval - (now - last_sync)))
            continue

        sync_google_accounts.delay(str(cred.organization_id))
        count += 1

    logger.info("sync_accounts_all_dispatched", organizations=count)
    return {"dispatched": count}
