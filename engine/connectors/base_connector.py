"""Abstract base connector with shared auth, pagination, logging, and error handling."""

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any

import structlog
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.api_core.exceptions import (
    ResourceExhausted,
    Unauthenticated,
    PermissionDenied,
    InternalServerError,
    InvalidArgument,
)

logger = structlog.get_logger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 5


class BaseConnector(ABC):
    """Abstract base for all Google Ads data source connectors."""

    def __init__(
        self,
        credentials: dict,
        customer_id: str,
        login_customer_id: str | None = None,
        output_dir: str | None = None,
    ):
        self.credentials = credentials
        self.customer_id = customer_id.replace("-", "")
        self.login_customer_id = (
            login_customer_id.replace("-", "") if login_customer_id else None
        )
        self.output_dir = output_dir
        self.logger = logger.bind(
            connector=self.__class__.__name__,
            customer_id=self.customer_id,
        )
        self._client: GoogleAdsClient | None = None

    def _get_client(self) -> GoogleAdsClient:
        """Create or return cached GoogleAdsClient."""
        if self._client is not None:
            return self._client

        config = {
            "developer_token": self.credentials["developer_token"],
            "client_id": self.credentials["client_id"],
            "client_secret": self.credentials["client_secret"],
            "refresh_token": self.credentials["refresh_token"],
            "use_proto_plus": True,
        }
        if self.login_customer_id:
            config["login_customer_id"] = self.login_customer_id

        self._client = GoogleAdsClient.load_from_dict(config)
        return self._client

    def _execute_query(self, query: str, customer_id: str | None = None) -> list:
        """Execute a GAQL query with retry and error handling.

        Returns list of GoogleAdsRow objects.
        """
        cid = (customer_id or self.customer_id).replace("-", "")
        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        return self._retry_with_backoff(
            lambda: self._search_stream(ga_service, cid, query)
        )

    def _search_stream(self, ga_service, customer_id: str, query: str) -> list:
        """Execute SearchStream and collect all rows."""
        rows = []
        stream = ga_service.search_stream(customer_id=customer_id, query=query)
        for batch in stream:
            for row in batch.results:
                rows.append(row)
        return rows

    def _retry_with_backoff(self, func, max_retries: int = MAX_RETRIES):
        """Execute function with exponential backoff on retryable errors."""
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return func()
            except GoogleAdsException as ex:
                last_error = ex
                error_code = self._classify_google_ads_error(ex)
                if error_code in ("QUERY_ERROR", "PERMISSION_DENIED", "REQUEST_ERROR", "UNKNOWN"):
                    self.logger.error(
                        "google_ads_error",
                        error_code=error_code,
                        message=str(ex),
                    )
                    raise
                elif error_code == "RESOURCE_EXHAUSTED" and attempt < max_retries:
                    wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                    self.logger.warning(
                        "rate_limited_retrying",
                        attempt=attempt + 1,
                        wait_seconds=wait,
                    )
                    time.sleep(wait)
                    continue
                elif error_code == "UNAUTHENTICATED" and attempt == 0:
                    self.logger.warning("auth_failed_retrying")
                    self._client = None
                    time.sleep(1)
                    continue
                else:
                    self.logger.error(
                        "google_ads_error",
                        error_code=error_code,
                        message=str(ex),
                    )
                    raise
            except ResourceExhausted as ex:
                last_error = ex
                if attempt < max_retries:
                    wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                    self.logger.warning("rate_limited", wait_seconds=wait)
                    time.sleep(wait)
                    continue
                raise
            except (InternalServerError,) as ex:
                last_error = ex
                if attempt < max_retries:
                    wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                    self.logger.warning("server_error_retrying", wait_seconds=wait)
                    time.sleep(wait)
                    continue
                raise
            except Unauthenticated as ex:
                self.logger.error("authentication_failed", error=str(ex))
                raise
            except PermissionDenied as ex:
                self.logger.error("permission_denied", error=str(ex))
                raise
            except InvalidArgument as ex:
                self.logger.error("query_error", error=str(ex))
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("Retry loop exhausted without result")

    def _classify_google_ads_error(self, ex: GoogleAdsException) -> str:
        """Classify a GoogleAdsException into an error category.

        Proto-plus error_code is a oneof — hasattr always returns True for all
        fields, so we must check for non-zero (non-default) values instead.
        """
        NON_RETRYABLE = {"PERMISSION_DENIED", "QUERY_ERROR", "REQUEST_ERROR"}

        for error in ex.failure.errors:
            ec = error.error_code
            # Check each field for a non-default (non-zero) value
            try:
                if ec.quota_error and ec.quota_error != 0:
                    return "RESOURCE_EXHAUSTED"
            except (AttributeError, ValueError):
                pass
            try:
                if ec.authentication_error and ec.authentication_error != 0:
                    return "UNAUTHENTICATED"
            except (AttributeError, ValueError):
                pass
            try:
                if ec.authorization_error and ec.authorization_error != 0:
                    return "PERMISSION_DENIED"
            except (AttributeError, ValueError):
                pass
            try:
                if ec.query_error and ec.query_error != 0:
                    return "QUERY_ERROR"
            except (AttributeError, ValueError):
                pass
            try:
                if ec.request_error and ec.request_error != 0:
                    return "REQUEST_ERROR"
            except (AttributeError, ValueError):
                pass
            try:
                if ec.internal_error and ec.internal_error != 0:
                    return "INTERNAL"
            except (AttributeError, ValueError):
                pass
        return "UNKNOWN"

    def _parse_rows(self, rows: list) -> list[dict[str, Any]]:
        """Convert GoogleAdsRow proto objects to plain dictionaries."""
        parsed = []
        for row in rows:
            parsed.append(self._proto_to_dict(row))
        return parsed

    def _proto_to_dict(self, proto_obj) -> dict:
        """Recursively convert a proto-plus message to a dictionary."""
        from google.protobuf.json_format import MessageToDict
        try:
            if hasattr(proto_obj, '_pb'):
                return MessageToDict(proto_obj._pb, preserving_proto_field_name=True)
            elif hasattr(proto_obj, 'DESCRIPTOR'):
                return MessageToDict(proto_obj, preserving_proto_field_name=True)
            else:
                return dict(proto_obj)
        except Exception:
            return {"raw": str(proto_obj)}

    def _save_raw_json(self, data: list[dict], filename: str, output_dir: str | None = None) -> str | None:
        """Save raw extracted data as JSON file."""
        out = output_dir or self.output_dir
        if not out:
            return None
        raw_dir = os.path.join(out, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        path = os.path.join(raw_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        self.logger.info("raw_json_saved", path=path, rows=len(data))
        return path

    @abstractmethod
    def extract(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Extract raw data for the given date range."""
        ...

    def log_extraction(self, row_count: int, duration_seconds: float) -> dict:
        """Log extraction metadata."""
        manifest = {
            "connector": self.__class__.__name__,
            "customer_id": self.customer_id,
            "row_count": row_count,
            "duration_seconds": round(duration_seconds, 2),
            "status": "complete" if row_count > 0 else "empty",
        }
        self.logger.info("extraction_complete", **manifest)
        return manifest
