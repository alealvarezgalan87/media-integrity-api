"""OAuth2 consent flow for Google Ads and GA4.

Handles:
- Authorization URL generation
- Consent screen redirect
- Callback token exchange
- Refresh token storage
- MCC hierarchy support
"""

import structlog
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = structlog.get_logger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"


class OAuthFlow:
    """Manages OAuth2 authentication flow for Google APIs."""

    GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
    GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._flow = None

    def get_authorization_url(self, scopes: list[str] | None = None) -> str:
        """Generate the OAuth2 authorization URL for user consent."""
        scopes = scopes or [self.GOOGLE_ADS_SCOPE]
        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": TOKEN_URI,
            }
        }
        try:
            self._flow = Flow.from_client_config(
                client_config,
                scopes=scopes,
                redirect_uri=self.redirect_uri,
            )
            auth_url, _ = self._flow.authorization_url(
                access_type="offline",
                prompt="consent",
            )
            logger.info("authorization_url_generated", scopes=scopes)
            return auth_url
        except Exception as e:
            logger.error("authorization_url_failed", error=str(e))
            raise

    def exchange_code(self, authorization_code: str) -> dict:
        """Exchange authorization code for access + refresh tokens."""
        if self._flow is None:
            raise RuntimeError("Must call get_authorization_url before exchange_code")
        try:
            self._flow.fetch_token(code=authorization_code)
            creds = self._flow.credentials
            result = {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": getattr(creds, "token_uri", TOKEN_URI),
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
            }
            logger.info("token_exchange_successful")
            return result
        except Exception as e:
            logger.error("token_exchange_failed", error=str(e))
            raise

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        try:
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri=TOKEN_URI,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            creds.refresh(Request())
            result = {
                "access_token": creds.token,
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
            }
            logger.info("token_refresh_successful")
            return result
        except Exception as e:
            logger.error("token_refresh_failed", error=str(e))
            raise
