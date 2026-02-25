"""MCC (Manager Account) hierarchy management.

Handles:
- Listing accessible client accounts under MCC
- Verifying account access
- Managing login_customer_id header
"""

import structlog
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

logger = structlog.get_logger(__name__)


def _format_customer_id(raw_id: str) -> str:
    """Format a numeric customer ID as xxx-xxx-xxxx."""
    raw = str(raw_id).replace("-", "")
    if len(raw) == 10:
        return f"{raw[:3]}-{raw[3:6]}-{raw[6:]}"
    return raw


class MCCManager:
    """Manages Google Ads MCC hierarchy for multi-client access."""

    def __init__(self, credentials: dict, mcc_customer_id: str):
        self.credentials = credentials
        self.mcc_customer_id = mcc_customer_id.replace("-", "")
        self._client = self._build_client()

    def _build_client(self) -> GoogleAdsClient:
        """Create GoogleAdsClient from credentials dict."""
        config = {
            "developer_token": self.credentials["developer_token"],
            "client_id": self.credentials["client_id"],
            "client_secret": self.credentials["client_secret"],
            "refresh_token": self.credentials["refresh_token"],
            "login_customer_id": self.mcc_customer_id,
            "use_proto_plus": True,
        }
        return GoogleAdsClient.load_from_dict(config)

    def list_accessible_accounts(self) -> list[dict]:
        """List all client accounts accessible under this MCC."""
        query = """
            SELECT
                customer_client.id,
                customer_client.descriptive_name,
                customer_client.currency_code,
                customer_client.time_zone,
                customer_client.manager,
                customer_client.status
            FROM customer_client
            WHERE customer_client.manager = false
        """
        try:
            ga_service = self._client.get_service("GoogleAdsService")
            stream = ga_service.search_stream(
                customer_id=self.mcc_customer_id, query=query
            )
            accounts = []
            for batch in stream:
                for row in batch.results:
                    cc = row.customer_client
                    accounts.append({
                        "id": _format_customer_id(str(cc.id)),
                        "name": cc.descriptive_name,
                        "currency": cc.currency_code,
                        "timezone": cc.time_zone,
                        "status": cc.status.name if hasattr(cc.status, "name") else str(cc.status),
                    })
            logger.info("accounts_listed", count=len(accounts))
            return accounts
        except GoogleAdsException as e:
            logger.error("list_accounts_failed", error=str(e))
            raise
        except Exception as e:
            logger.error("list_accounts_failed", error=str(e))
            raise

    def verify_access(self, account_id: str) -> bool:
        """Verify that the MCC has access to a specific client account."""
        clean_id = account_id.replace("-", "")
        query = "SELECT customer.id FROM customer"
        try:
            ga_service = self._client.get_service("GoogleAdsService")
            stream = ga_service.search_stream(
                customer_id=clean_id, query=query
            )
            for batch in stream:
                if batch.results:
                    logger.info("access_verified", account_id=account_id)
                    return True
            return True
        except (GoogleAdsException, Exception) as e:
            logger.warning("access_denied", account_id=account_id, error=str(e))
            return False

    def get_account_info(self, account_id: str) -> dict | None:
        """Get detailed info for a specific account."""
        clean_id = account_id.replace("-", "")
        query = """
            SELECT
                customer.id,
                customer.descriptive_name,
                customer.currency_code,
                customer.time_zone
            FROM customer
        """
        try:
            ga_service = self._client.get_service("GoogleAdsService")
            stream = ga_service.search_stream(
                customer_id=clean_id, query=query
            )
            for batch in stream:
                for row in batch.results:
                    c = row.customer
                    return {
                        "id": _format_customer_id(str(c.id)),
                        "name": c.descriptive_name,
                        "currency": c.currency_code,
                        "timezone": c.time_zone,
                    }
            return None
        except GoogleAdsException as e:
            logger.error("get_account_info_failed", account_id=account_id, error=str(e))
            return None
        except Exception as e:
            logger.error("get_account_info_failed", account_id=account_id, error=str(e))
            return None
