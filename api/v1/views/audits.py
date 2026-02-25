"""
Audit ViewSet — CRUD, run, status, download.
"""

from datetime import date

from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.serializers import (
    AuditDetailSerializer,
    AuditListSerializer,
    RunAuditSerializer,
)
from core.models import Audit, Report


class AuditViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Audit.objects.all()
        if user.organization:
            return Audit.objects.filter(organization=user.organization)
        return Audit.objects.none()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AuditDetailSerializer
        if self.action == "run":
            return RunAuditSerializer
        return AuditListSerializer

    @action(detail=False, methods=["post"])
    def run(self, request):
        """Launch an audit. Returns 202 with run_id for polling."""
        serializer = RunAuditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        org = request.user.organization

        # Build audit fields
        if data["source"] == "demo":
            demo_key = data.get("demo_key", "demo-moderate")
            account_name = {
                "demo-moderate": "Demo Account (Moderate)",
                "demo-critical": "Demo Account (Critical)",
                "demo-excellent": "Demo Account (Excellent)",
            }.get(demo_key, f"Demo ({demo_key})")
            account_id_raw = "000-000-0000"
        else:
            account_id_raw = data.get("account_id", "")
            account_name = f"Account {account_id_raw}"

        today = date.today()

        audit = Audit.objects.create(
            organization=org,
            created_by=request.user,
            account_id_raw=account_id_raw,
            account_name=account_name,
            date_range_start=data.get("start_date", today.replace(day=1)),
            date_range_end=data.get("end_date", today),
            source=data["source"],
            status=Audit.Status.PENDING,
            full_result={"demo_key": data.get("demo_key", "")},
        )

        # Dispatch Celery task (will be connected in Fase 2)
        try:
            from tasks.audit_tasks import run_audit_task
            run_audit_task.delay(str(audit.run_id))
        except ImportError:
            # Celery not configured yet — mark as pending
            pass

        return Response(
            {"status": "accepted", "run_id": str(audit.run_id)},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """Poll audit status."""
        audit = self.get_object()
        response = {
            "status": audit.status,
            "composite_score": audit.composite_score,
        }
        if audit.started_at and audit.status == Audit.Status.RUNNING:
            from django.utils import timezone
            elapsed = (timezone.now() - audit.started_at).total_seconds()
            response["progress"] = min(int(elapsed / 30 * 100), 95)
        elif audit.status == Audit.Status.SUCCESS:
            response["progress"] = 100
        elif audit.status == Audit.Status.FAILED:
            response["progress"] = 0
            response["errors"] = audit.errors
        else:
            response["progress"] = 0
        return Response(response)

    @action(
        detail=True,
        methods=["get"],
        url_path="download/(?P<file_type>[a-z]+)",
    )
    def download(self, request, pk=None, file_type=None):
        """Download a report file by type."""
        audit = self.get_object()

        report = (
            Report.objects.filter(audit=audit, report_type=file_type)
            .order_by("-version")
            .first()
        )

        if not report or not report.file:
            return Response(
                {"error": f"No {file_type} report available."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            report.file.open("rb"),
            as_attachment=True,
            filename=report.file_name,
        )

    def perform_destroy(self, instance):
        """Delete audit and all related data (cascade)."""
        instance.delete()
