"""
Google OAuth2 flow for obtaining a refresh token automatically.

Flow:
1. Frontend calls GET /api/v1/settings/google/oauth/authorize/
   → Backend builds Google consent URL → returns it as JSON
2. Frontend opens that URL (popup or redirect)
3. User authorizes → Google redirects to GET /api/v1/settings/google/oauth/callback/?code=xxx&state=xxx
4. Backend exchanges code for refresh_token → saves to GoogleAdsCredential
5. Backend redirects to frontend with ?oauth=success or ?oauth=error
"""

import hashlib
import secrets
from urllib.parse import urlencode

import requests as http_requests
from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import GoogleAdsCredential

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = " ".join([
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/bigquery.readonly",
])

# In-memory state store (for production, use cache/redis/db)
_oauth_states = {}


class GoogleOAuthAuthorizeView(APIView):
    """GET /api/v1/settings/google/oauth/authorize/ — returns the Google consent URL."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="OAuthAuthorizeResponse",
                fields={
                    "authorize_url": serializers.URLField(),
                },
            ),
            400: inline_serializer(
                name="OAuthAuthorizeError",
                fields={"error": serializers.CharField()},
            ),
        },
    )
    def get(self, request):
        org = request.user.organization
        if not org:
            return Response(
                {"error": "No organization assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Need client_id and client_secret saved first
        try:
            creds = org.google_credentials
        except GoogleAdsCredential.DoesNotExist:
            return Response(
                {"error": "Save Client ID and Client Secret first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not creds.client_id or not creds.client_secret:
            return Response(
                {"error": "Client ID and Client Secret are required before connecting."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate CSRF state token
        state = secrets.token_urlsafe(32)
        _oauth_states[state] = {
            "org_id": str(org.id),
            "user_id": str(request.user.id),
        }

        # Build the callback URL — points to our backend
        callback_url = request.build_absolute_uri("/api/v1/settings/google/oauth/callback/")

        params = {
            "client_id": creds.client_id,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }

        authorize_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

        return Response({"authorize_url": authorize_url})


class GoogleOAuthCallbackView(APIView):
    """
    GET /api/v1/settings/google/oauth/callback/?code=xxx&state=xxx
    Google redirects here after user authorizes.
    Exchanges code for refresh_token, saves it, redirects to frontend.
    """

    permission_classes = []
    authentication_classes = []

    @extend_schema(exclude=True)
    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        redirect_base = f"{frontend_url}/settings/google"

        # User denied access
        if error:
            return self._redirect(redirect_base, "error", f"Google authorization denied: {error}")

        if not code or not state:
            return self._redirect(redirect_base, "error", "Missing code or state parameter.")

        # Validate state
        state_data = _oauth_states.pop(state, None)
        if not state_data:
            return self._redirect(redirect_base, "error", "Invalid or expired state. Please try again.")

        org_id = state_data["org_id"]

        try:
            creds = GoogleAdsCredential.objects.get(organization_id=org_id)
        except GoogleAdsCredential.DoesNotExist:
            return self._redirect(redirect_base, "error", "Google credentials not found.")

        # Build callback URL (must match exactly what was used in authorize)
        callback_url = request.build_absolute_uri("/api/v1/settings/google/oauth/callback/")

        # Exchange code for tokens
        try:
            token_response = http_requests.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "redirect_uri": callback_url,
                    "grant_type": "authorization_code",
                },
                timeout=30,
            )
            token_data = token_response.json()

            if "error" in token_data:
                return self._redirect(
                    redirect_base, "error",
                    f"Token exchange failed: {token_data.get('error_description', token_data['error'])}"
                )

            refresh_token = token_data.get("refresh_token")
            if not refresh_token:
                return self._redirect(redirect_base, "error", "No refresh token received. Try disconnecting and reconnecting.")

            # Save the refresh token and scopes
            creds.refresh_token = refresh_token
            creds.oauth_scopes = SCOPES
            creds.save(update_fields=["refresh_token", "oauth_scopes", "updated_at"])

            return self._redirect(redirect_base, "success", "Google account connected successfully.")

        except http_requests.RequestException as e:
            return self._redirect(redirect_base, "error", f"Failed to exchange token: {str(e)}")

    @staticmethod
    def _redirect(base_url, status, message):
        from django.http import HttpResponseRedirect
        from urllib.parse import quote
        return HttpResponseRedirect(f"{base_url}?oauth={status}&message={quote(message)}")


class GoogleOAuthStatusView(APIView):
    """GET /api/v1/settings/google/oauth/status/ — check if refresh token exists."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="OAuthStatusResponse",
                fields={
                    "connected": serializers.BooleanField(),
                    "has_refresh_token": serializers.BooleanField(),
                    "has_ga4_scope": serializers.BooleanField(),
                    "has_bq_scope": serializers.BooleanField(),
                },
            ),
        },
    )
    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({"connected": False, "has_refresh_token": False})

        try:
            creds = org.google_credentials
            has_token = bool(creds.refresh_token and len(creds.refresh_token) > 5)
            scopes = creds.oauth_scopes or ""
            has_ga4 = "analytics.readonly" in scopes
            has_bq = "bigquery.readonly" in scopes
            return Response({
                "connected": has_token,
                "has_refresh_token": has_token,
                "has_ga4_scope": has_ga4,
                "has_bq_scope": has_bq,
            })
        except GoogleAdsCredential.DoesNotExist:
            return Response({"connected": False, "has_refresh_token": False, "has_ga4_scope": False, "has_bq_scope": False})
