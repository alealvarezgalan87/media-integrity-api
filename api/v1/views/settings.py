"""
Settings views — Google Ads config, Scoring config, Report options.
"""

from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.serializers import (
    GoogleAdsConfigSerializer,
    ReportOptionsSerializer,
    ScoringConfigSerializer,
)
from core.models import GoogleAdsAccount, GoogleAdsCredential, ReportConfig, ScoringConfig


class GoogleConfigView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: GoogleAdsConfigSerializer},
    )
    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({})

        try:
            creds = org.google_credentials
        except GoogleAdsCredential.DoesNotExist:
            return Response({
                "developer_token": "",
                "client_id": "",
                "client_secret": "",
                "refresh_token": "",
                "mcc_id": "",
                "api_version": "v23",
                "account_sync_interval_hours": 6,
            })

        return Response({
            "developer_token": self._mask(creds.developer_token),
            "client_id": creds.client_id,
            "client_secret": self._mask(creds.client_secret),
            "refresh_token": self._mask(creds.refresh_token),
            "mcc_id": creds.mcc_id,
            "api_version": creds.api_version,
            "account_sync_interval_hours": creds.account_sync_interval_hours,
        })

    @extend_schema(
        request=GoogleAdsConfigSerializer,
        responses={
            200: inline_serializer(
                name="GoogleConfigSaveResponse",
                fields={"status": serializers.CharField()},
            ),
        },
    )
    def post(self, request):
        org = request.user.organization
        if not org:
            return Response(
                {"error": "No organization assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GoogleAdsConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        creds, _ = GoogleAdsCredential.objects.get_or_create(organization=org)

        for field, value in data.items():
            if value and not str(value).startswith("****"):
                setattr(creds, field, value)
        creds.save()

        return Response({"status": "saved"})

    @staticmethod
    def _mask(value):
        if not value or len(value) < 8:
            return "****"
        return "****" + value[-4:]


class TestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="TestConnectionResponse",
                fields={
                    "connected": serializers.BooleanField(),
                    "message": serializers.CharField(),
                    "accounts": serializers.ListField(
                        child=inline_serializer(
                            name="GoogleAdsAccount",
                            fields={
                                "id": serializers.CharField(),
                                "name": serializers.CharField(),
                            },
                        ),
                        required=False,
                    ),
                },
            ),
        },
    )
    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({"connected": False, "message": "No organization."})

        try:
            creds = org.google_credentials
        except GoogleAdsCredential.DoesNotExist:
            return Response({
                "connected": False,
                "message": "No Google Ads credentials configured.",
            })

        if not creds.developer_token or not creds.client_id:
            return Response({
                "connected": False,
                "message": "Incomplete credentials. Please configure all fields.",
            })

        if not creds.refresh_token:
            return Response({
                "connected": False,
                "message": "No refresh token. Please connect your Google account first.",
            })

        if not creds.mcc_id:
            return Response({
                "connected": False,
                "message": "MCC ID is required. Please configure it in settings.",
            })

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
            accounts = manager.list_accessible_accounts()
            creds.is_verified = True
            creds.last_verified_at = timezone.now()
            creds.save(update_fields=["is_verified", "last_verified_at"])

            # Save accounts directly to DB
            now = timezone.now()
            remote_ids = set()
            for acc in accounts:
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
            GoogleAdsAccount.objects.filter(
                organization=org, is_active=True
            ).exclude(account_id__in=remote_ids).update(is_active=False)

            return Response({
                "connected": True,
                "message": f"Connected. Found {len(accounts)} accounts saved to database.",
                "accounts": [{"id": a["id"], "name": a["name"]} for a in accounts],
            })
        except ImportError:
            return Response({
                "connected": False,
                "message": "Engine not installed yet (Fase 2). Credentials saved.",
            })
        except Exception as e:
            return Response({
                "connected": False,
                "message": _friendly_connection_error(e),
            })


def _friendly_connection_error(exc: Exception) -> str:
    """Convert raw Google Ads / network exceptions into user-friendly messages."""
    raw = str(exc).lower()

    # SSL / network connectivity issues
    if "ssl" in raw or "eof" in raw or "connection" in raw and "pool" in raw:
        return "Could not reach Google servers. Please check your internet connection and try again."

    # Max retries / timeout
    if "max retries" in raw or "timed out" in raw or "timeout" in raw:
        return "Request to Google timed out. Please try again in a few moments."

    # Invalid OAuth credentials
    if "invalid_client" in raw:
        return "Invalid Client ID or Client Secret. Please verify your OAuth credentials."
    if "invalid_grant" in raw or "token has been expired or revoked" in raw:
        return "Refresh token is invalid or expired. Please reconnect your Google account."
    if "unauthorized" in raw or "401" in raw:
        return "Authentication failed. Please check your credentials and try again."

    # Google Ads API specific
    if "developer_token" in raw or "developer token" in raw:
        return "Invalid Developer Token. Please verify it in your Google Ads API Center."
    if "not_found" in raw and "customer" in raw:
        return "MCC account not found. Please verify the MCC ID is correct."
    if "permission_denied" in raw or "authorization_error" in raw:
        return "Access denied. Your Developer Token may not have the required permissions."
    if "customer_not_enabled" in raw:
        return "The MCC account is not enabled. Please check its status in Google Ads."

    # DNS resolution
    if "name or service not known" in raw or "getaddrinfo" in raw:
        return "DNS resolution failed. Please check your internet connection."

    # Fallback — truncate to avoid showing a wall of text
    short = str(exc)[:200]
    return f"Connection failed: {short}{'…' if len(str(exc)) > 200 else ''}"


class GoogleAccountsListView(APIView):
    """GET /api/v1/settings/google/accounts/ — list accounts from local DB cache."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="GoogleAccountsListResponse",
                fields={
                    "accounts": serializers.ListField(
                        child=inline_serializer(
                            name="GoogleAdsAccountItem",
                            fields={
                                "id": serializers.CharField(),
                                "name": serializers.CharField(),
                            },
                        ),
                    ),
                    "last_synced_at": serializers.DateTimeField(allow_null=True),
                    "sync_interval_hours": serializers.IntegerField(),
                },
            ),
        },
    )
    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({"accounts": [], "last_synced_at": None, "sync_interval_hours": 6})

        # Admins see all org accounts; regular users see only their assigned accounts
        qs = GoogleAdsAccount.objects.filter(organization=org, is_active=True)
        if request.user.role != "admin" and not request.user.is_superuser:
            qs = qs.filter(users=request.user)
        accounts = list(qs.order_by("account_name"))

        sync_interval = 6
        try:
            creds = org.google_credentials
            sync_interval = creds.account_sync_interval_hours
        except GoogleAdsCredential.DoesNotExist:
            creds = None

        # If DB is empty but we have verified credentials, fetch directly + trigger background sync
        if not accounts and creds and creds.is_verified:
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
                remote = manager.list_accessible_accounts()

                # Trigger background sync to persist into DB
                try:
                    from tasks.sync_accounts import sync_google_accounts
                    sync_google_accounts.delay(str(org.id))
                except Exception:
                    pass

                return Response({
                    "accounts": [{"id": a["id"], "name": a["name"]} for a in remote],
                    "last_synced_at": None,
                    "sync_interval_hours": sync_interval,
                })
            except Exception:
                pass  # Fall through to empty response

        last_synced = accounts[0].last_synced_at if accounts else None

        from core.models import Audit
        from django.db.models import Count

        # Get audit counts per account_id
        audit_counts = dict(
            Audit.objects.filter(organization=org)
            .values_list("account_id_raw")
            .annotate(count=Count("run_id"))
            .values_list("account_id_raw", "count")
        )

        return Response({
            "accounts": [
                {
                    "id": str(a.id),
                    "account_id": a.account_id,
                    "name": a.account_name,
                    "currency": a.currency,
                    "timezone": a.timezone,
                    "last_synced_at": a.last_synced_at,
                    "audit_count": audit_counts.get(a.account_id, 0),
                }
                for a in accounts
            ],
            "last_synced_at": last_synced,
            "sync_interval_hours": sync_interval,
        })


class GoogleAccountDetailView(APIView):
    """GET /api/v1/settings/google/accounts/<account_id>/ — account detail (read-only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, account_id):
        org = request.user.organization
        if not org:
            return Response({"error": "No organization."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            account = GoogleAdsAccount.objects.get(
                organization=org, account_id=account_id
            )
        except GoogleAdsAccount.DoesNotExist:
            return Response({"error": "Account not found."}, status=status.HTTP_404_NOT_FOUND)

        from core.models import Audit

        audits = Audit.objects.filter(
            organization=org, account_id_raw=account_id
        ).order_by("-created_at")[:20]

        return Response({
            "id": str(account.id),
            "account_id": account.account_id,
            "name": account.account_name,
            "currency": account.currency,
            "timezone": account.timezone,
            "is_active": account.is_active,
            "last_synced_at": account.last_synced_at,
            "recent_audits": [
                {
                    "run_id": str(a.run_id),
                    "status": a.status,
                    "composite_score": a.composite_score,
                    "risk_band": a.risk_band,
                    "source": a.source,
                    "date_range_start": str(a.date_range_start),
                    "date_range_end": str(a.date_range_end),
                    "created_at": a.created_at.isoformat(),
                }
                for a in audits
            ],
        })


class GoogleAccountsSyncView(APIView):
    """POST /api/v1/settings/google/accounts/sync/ — trigger manual account sync."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        org = request.user.organization
        if not org:
            return Response(
                {"error": "No organization assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from tasks.sync_accounts import sync_google_accounts
        sync_google_accounts.delay(str(org.id))

        return Response({"status": "sync_started"}, status=status.HTTP_202_ACCEPTED)


class ScoringConfigView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ScoringConfigSerializer})
    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({})

        config, _ = ScoringConfig.objects.get_or_create(organization=org)
        serializer = ScoringConfigSerializer(config)
        return Response(serializer.data)

    @extend_schema(
        request=ScoringConfigSerializer,
        responses={
            200: inline_serializer(
                name="ScoringConfigSaveResponse",
                fields={"status": serializers.CharField()},
            ),
        },
    )
    def post(self, request):
        org = request.user.organization
        if not org:
            return Response(
                {"error": "No organization assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config, _ = ScoringConfig.objects.get_or_create(organization=org)
        serializer = ScoringConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"status": "saved"})


class ReportConfigView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ReportOptionsSerializer})
    def get(self, request):
        config, _ = ReportConfig.objects.get_or_create(user=request.user)
        return Response({
            "company_name": config.company_name,
            "report_title": config.report_title,
            "footer_text": config.footer_text,
            "page_size": config.page_size,
        })

    @extend_schema(
        request=ReportOptionsSerializer,
        responses={
            200: inline_serializer(
                name="ReportConfigSaveResponse",
                fields={"status": serializers.CharField()},
            ),
        },
    )
    def post(self, request):
        serializer = ReportOptionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        config, _ = ReportConfig.objects.get_or_create(user=request.user)
        for field, value in data.items():
            if value is not None:
                setattr(config, field, value)
        config.save()
        return Response({"status": "saved"})
