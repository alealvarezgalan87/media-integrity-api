"""
Settings views — Google Ads config, Scoring config, Report options.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.serializers import (
    GoogleAdsConfigSerializer,
    ReportOptionsSerializer,
    ScoringConfigSerializer,
)
from core.models import GoogleAdsCredential, ScoringConfig


class GoogleConfigView(APIView):
    permission_classes = [IsAuthenticated]

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
            })

        return Response({
            "developer_token": self._mask(creds.developer_token),
            "client_id": creds.client_id,
            "client_secret": self._mask(creds.client_secret),
            "refresh_token": self._mask(creds.refresh_token),
            "mcc_id": creds.mcc_id,
            "api_version": creds.api_version,
        })

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
            if value:
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

        # Attempt real connection via MCC manager (will be available in Fase 2)
        try:
            from engine.auth.mcc_manager import MCCManager
            manager = MCCManager({
                "developer_token": creds.developer_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "refresh_token": creds.refresh_token,
            })
            accounts = manager.list_accounts(creds.mcc_id)
            creds.is_verified = True
            creds.save(update_fields=["is_verified", "last_verified_at"])
            return Response({
                "connected": True,
                "message": f"Connected. Found {len(accounts)} accounts.",
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
                "message": f"Connection failed: {str(e)}",
            })


class ScoringConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({})

        config, _ = ScoringConfig.objects.get_or_create(organization=org)
        serializer = ScoringConfigSerializer(config)
        return Response(serializer.data)

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

    def get(self, request):
        org = request.user.organization
        if not org:
            return Response({})

        config, _ = ScoringConfig.objects.get_or_create(organization=org)
        return Response({
            "company_name": config.company_name,
            "report_title": config.report_title,
            "footer_text": config.footer_text,
            "page_size": config.page_size,
        })

    def post(self, request):
        org = request.user.organization
        if not org:
            return Response(
                {"error": "No organization assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReportOptionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        config, _ = ScoringConfig.objects.get_or_create(organization=org)
        for field, value in data.items():
            if value is not None:
                setattr(config, field, value)
        config.save()
        return Response({"status": "saved"})
