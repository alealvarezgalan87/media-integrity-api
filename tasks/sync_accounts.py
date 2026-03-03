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


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def sync_ga4_properties(self, organization_id: str):
    """Sync GA4 properties from Analytics Admin API into GA4Property table."""
    from core.models import GA4Property, GoogleAdsCredential, Organization

    try:
        org = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        logger.error("sync_ga4_org_not_found", organization_id=organization_id)
        return {"status": "error", "message": "Organization not found"}

    try:
        creds = org.google_credentials
    except GoogleAdsCredential.DoesNotExist:
        logger.warning("sync_ga4_no_credentials", org=org.name)
        return {"status": "skipped", "message": "No credentials configured"}

    if not all([creds.client_id, creds.client_secret, creds.refresh_token]):
        logger.warning("sync_ga4_incomplete_credentials", org=org.name)
        return {"status": "skipped", "message": "Incomplete credentials"}

    if "analytics.readonly" not in (creds.oauth_scopes or ""):
        logger.warning("sync_ga4_no_scope", org=org.name)
        return {"status": "skipped", "message": "GA4 scope not authorized"}

    try:
        from engine.auth.ga4_manager import GA4Manager

        manager = GA4Manager(credentials={
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
        })
        remote_properties = manager.list_properties()
    except Exception as exc:
        logger.error("sync_ga4_api_failed", org=org.name, error=str(exc))
        raise self.retry(exc=exc)

    now = timezone.now()
    remote_ids = set()

    bq_detected = 0
    for prop in remote_properties:
        remote_ids.add(prop["property_id"])
        defaults = {
            "display_name": prop.get("display_name", ""),
            "timezone": prop.get("timezone", ""),
            "currency": prop.get("currency", ""),
            "industry_category": prop.get("industry_category", ""),
            "service_level": prop.get("service_level", ""),
            "is_active": True,
            "last_synced_at": now,
        }

        # Auto-detect BigQuery export links
        bq_info = manager.get_bigquery_links(prop["property_id"])
        if bq_info:
            defaults["bq_project_id"] = bq_info["bq_project_id"]
            defaults["bq_dataset_id"] = bq_info["bq_dataset_id"]
            bq_detected += 1

        GA4Property.objects.update_or_create(
            organization=org,
            property_id=prop["property_id"],
            defaults=defaults,
        )

    # Deactivate properties no longer accessible
    deactivated = GA4Property.objects.filter(
        organization=org, is_active=True
    ).exclude(property_id__in=remote_ids).update(is_active=False)

    logger.info(
        "sync_ga4_done",
        org=org.name,
        synced=len(remote_properties),
        deactivated=deactivated,
        bq_detected=bq_detected,
    )

    return {
        "status": "ok",
        "synced": len(remote_properties),
        "deactivated": deactivated,
        "bq_detected": bq_detected,
    }
