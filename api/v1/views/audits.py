"""
Audit ViewSet — CRUD, run, status, download.
"""

from datetime import date

from django.http import FileResponse, HttpResponse
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
        if user.is_superuser or getattr(user, "role", "") == "admin":
            if user.organization:
                return Audit.objects.filter(organization=user.organization)
            return Audit.objects.all()
        return Audit.objects.filter(created_by=user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AuditDetailSerializer
        if self.action == "run":
            return RunAuditSerializer
        return AuditListSerializer

    def get_object(self):
        """Support lookup by slug in addition to UUID (run_id)."""
        from django.http import Http404

        pk = self.kwargs.get("pk", "")
        queryset = self.get_queryset()
        try:
            import uuid as _uuid
            _uuid.UUID(pk)
            obj = queryset.get(run_id=pk)
        except (ValueError, Audit.DoesNotExist):
            try:
                obj = queryset.get(slug=pk)
            except Audit.DoesNotExist:
                raise Http404
        self.check_object_permissions(self.request, obj)
        return obj

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
            account_name = data.get("account_name", "")
            if not account_name:
                # Try to find the real name from GoogleAdsAccount
                from core.models import GoogleAdsAccount
                gads_account = GoogleAdsAccount.objects.filter(
                    organization=org, account_id=account_id_raw
                ).first()
                account_name = (
                    f"{gads_account.account_name} ({account_id_raw})"
                    if gads_account else f"Account {account_id_raw}"
                )

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
            {"status": "accepted", "run_id": str(audit.run_id), "slug": audit.slug},
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
        """Download a report file by type. XLSX is generated on-the-fly."""
        audit = self.get_object()

        # XLSX — generate on-the-fly from ORM data
        if file_type == "xlsx":
            return self._generate_xlsx(audit)

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

    def _generate_xlsx(self, audit):
        """Build Excel evaluation report from audit ORM data."""
        from engine.reporting.excel_export import generate_audit_excel

        domain_scores = {}
        for ds in audit.domain_scores.all():
            domain_scores[ds.domain] = {
                "value": ds.value,
                "weight": ds.weight,
                "weighted_contribution": ds.weighted_contribution,
                "data_completeness": ds.data_completeness,
                "key_findings": ds.key_findings or [],
                "sub_scores": ds.sub_scores or {},
            }

        red_flags = list(
            audit.red_flags.all().values(
                "rule_id_raw", "severity", "domain",
                "title", "description", "recommendation",
            )
        )
        for rf in red_flags:
            rf["id"] = rf.pop("rule_id_raw", "")

        audit_data = {
            "run_id": str(audit.run_id),
            "account_id": audit.account_id_raw,
            "account_name": audit.account_name,
            "date_range": {
                "start": str(audit.date_range_start),
                "end": str(audit.date_range_end),
            },
            "scoring": {
                "composite_score": audit.composite_score,
                "risk_band": audit.risk_band,
                "capital_implication": audit.capital_implication,
                "confidence": audit.confidence,
                "red_flags_count": audit.red_flags.count(),
            },
            "domain_scores": domain_scores,
            "red_flags": red_flags,
            "execution": {
                "source": audit.source,
                "duration_seconds": audit.duration_seconds,
                "timestamp": str(audit.created_at) if audit.created_at else "",
            },
            "raw_data": audit.full_result.get("_raw_data", {}),
            "ga4_raw_data": audit.full_result.get("_ga4_raw_data", {}),
        }

        excel_bytes = generate_audit_excel(audit_data)
        safe_name = audit.account_name.replace(" ", "_").replace("/", "_")
        filename = f"MIE_Evaluation_{safe_name}_{str(audit.run_id)[:8]}.xlsx"

        return HttpResponse(
            excel_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def perform_destroy(self, instance):
        """Delete audit and all related data (cascade)."""
        instance.delete()
