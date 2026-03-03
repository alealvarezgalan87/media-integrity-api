"""GA4 property discovery via Analytics Admin API.

Handles:
- Listing accessible GA4 properties
- Verifying property access
- Getting property details

Mirror of mcc_manager.py but for Google Analytics 4.
"""

import structlog
from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from google.analytics.admin_v1beta.types import ListPropertiesRequest
from google.analytics.admin_v1alpha import (
    AnalyticsAdminServiceClient as AlphaAdminClient,
)
from google.oauth2.credentials import Credentials

logger = structlog.get_logger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"


class GA4ScopeError(Exception):
    """Raised when OAuth2 token lacks GA4 scopes."""

    pass


class GA4Manager:
    """Manages GA4 property discovery via Analytics Admin API."""

    def __init__(self, credentials: dict):
        """
        Args:
            credentials: dict with client_id, client_secret, refresh_token.
        """
        self.credentials = credentials
        self._client = self._build_client()
        self._alpha_client = None

    def _build_client(self) -> AnalyticsAdminServiceClient:
        """Create Analytics Admin client from OAuth2 credentials."""
        creds = Credentials(
            token=None,
            refresh_token=self.credentials["refresh_token"],
            token_uri=TOKEN_URI,
            client_id=self.credentials["client_id"],
            client_secret=self.credentials["client_secret"],
        )
        return AnalyticsAdminServiceClient(credentials=creds)

    def list_properties(self) -> list[dict]:
        """List all GA4 properties accessible to the authenticated user.

        Returns:
            List of dicts with property_id, display_name, timezone,
            currency, industry_category, service_level.
        """
        properties = []
        try:
            for account_summary in self._client.list_account_summaries():
                account_name = account_summary.account
                if not account_name:
                    continue

                try:
                    request = ListPropertiesRequest(
                        filter=f"parent:{account_name}"
                    )
                    for prop in self._client.list_properties(request):
                        industry = ""
                        if prop.industry_category:
                            industry = (
                                prop.industry_category.name
                                if hasattr(prop.industry_category, "name")
                                else str(prop.industry_category)
                            )

                        service = ""
                        if prop.service_level:
                            service = (
                                prop.service_level.name
                                if hasattr(prop.service_level, "name")
                                else str(prop.service_level)
                            )

                        properties.append({
                            "property_id": prop.name.split("/")[-1],
                            "display_name": prop.display_name,
                            "timezone": prop.time_zone or "",
                            "currency": prop.currency_code or "",
                            "industry_category": industry,
                            "service_level": service,
                        })
                except Exception as e:
                    logger.warning(
                        "list_properties_for_account_failed",
                        account=account_name,
                        error=str(e),
                    )

            logger.info("ga4_properties_listed", count=len(properties))
            return properties

        except Exception as e:
            error_msg = str(e)
            if "SERVICE_DISABLED" in error_msg or "has not been used in project" in error_msg:
                logger.error("ga4_api_not_enabled", error=error_msg)
                raise GA4ScopeError(
                    "Google Analytics Admin API is not enabled in your "
                    "Google Cloud project. Enable it at: "
                    "https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com"
                ) from e
            if "403" in error_msg or "PERMISSION_DENIED" in error_msg:
                logger.error("ga4_scope_missing", error=error_msg)
                raise GA4ScopeError(
                    "Refresh token lacks analytics.readonly scope. "
                    "Please re-authorize."
                ) from e
            logger.error("ga4_list_properties_failed", error=error_msg)
            raise

    def _get_alpha_client(self) -> AlphaAdminClient:
        """Lazy-build v1alpha client (needed for BigQuery links)."""
        if self._alpha_client is None:
            creds = Credentials(
                token=None,
                refresh_token=self.credentials["refresh_token"],
                token_uri=TOKEN_URI,
                client_id=self.credentials["client_id"],
                client_secret=self.credentials["client_secret"],
            )
            self._alpha_client = AlphaAdminClient(credentials=creds)
        return self._alpha_client

    def get_bigquery_links(self, property_id: str) -> dict | None:
        """Check if a GA4 property has BigQuery export configured.

        Uses the v1alpha Admin API (list_big_query_links).

        Args:
            property_id: The numeric GA4 property ID (e.g. "327204471").

        Returns:
            Dict with bq_project_id, bq_dataset_id, daily_export, streaming_export
            if BQ is linked, or None if no BQ link exists.
        """
        try:
            alpha = self._get_alpha_client()
            links = list(alpha.list_big_query_links(
                parent=f"properties/{property_id}"
            ))
            if not links:
                return None

            link = links[0]
            # link.project is like "projects/417769516199"
            project_id = link.project.replace("projects/", "") if link.project else ""
            # dataset follows convention: analytics_<property_id>
            dataset_id = f"analytics_{property_id}"

            logger.info(
                "bq_link_found",
                property_id=property_id,
                bq_project=project_id,
                daily=link.daily_export_enabled,
                streaming=link.streaming_export_enabled,
            )
            return {
                "bq_project_id": project_id,
                "bq_dataset_id": dataset_id,
                "bq_dataset_location": link.dataset_location or "",
                "daily_export_enabled": link.daily_export_enabled,
                "streaming_export_enabled": link.streaming_export_enabled,
            }
        except Exception as e:
            logger.warning(
                "bq_link_check_failed",
                property_id=property_id,
                error=str(e),
            )
            return None

    def verify_access(self, property_id: str) -> bool:
        """Verify access to a specific GA4 property.

        Args:
            property_id: The numeric GA4 property ID (e.g. "345678901").

        Returns:
            True if accessible, False otherwise.
        """
        try:
            self._client.get_property(name=f"properties/{property_id}")
            logger.info("ga4_access_verified", property_id=property_id)
            return True
        except Exception as e:
            logger.warning(
                "ga4_access_denied", property_id=property_id, error=str(e)
            )
            return False

    def get_property_info(self, property_id: str) -> dict | None:
        """Get detailed info for a specific GA4 property.

        Args:
            property_id: The numeric GA4 property ID.

        Returns:
            Dict with property details, or None if not accessible.
        """
        try:
            prop = self._client.get_property(name=f"properties/{property_id}")

            industry = ""
            if prop.industry_category:
                industry = (
                    prop.industry_category.name
                    if hasattr(prop.industry_category, "name")
                    else str(prop.industry_category)
                )

            service = ""
            if prop.service_level:
                service = (
                    prop.service_level.name
                    if hasattr(prop.service_level, "name")
                    else str(prop.service_level)
                )

            return {
                "property_id": prop.name.split("/")[-1],
                "display_name": prop.display_name,
                "timezone": prop.time_zone or "",
                "currency": prop.currency_code or "",
                "industry_category": industry,
                "service_level": service,
            }
        except Exception as e:
            logger.error(
                "ga4_get_property_failed", property_id=property_id, error=str(e)
            )
            return None
