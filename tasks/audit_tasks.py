"""
Celery task for running the full audit pipeline.
Saves results into normalized Django ORM tables.
"""

import dataclasses
import json

from celery import shared_task
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils import timezone

from core.models import Audit, AuditDomainScore, AuditRedFlag, RedFlagRule, Report


def _make_serializable(obj):
    """Recursively convert dataclass instances and other non-serializable objects."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(i) for i in obj]
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return {k: _make_serializable(v) for k, v in obj.__dict__.items()}
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def run_audit_task(self, run_id: str):
    """Execute the full audit pipeline as a background task."""
    audit = Audit.objects.get(run_id=run_id)
    audit.status = Audit.Status.RUNNING
    audit.started_at = timezone.now()
    audit.save(update_fields=["status", "started_at"])

    try:
        from engine.orchestrator.audit_runner import run_audit

        org = audit.organization
        credentials = None
        demo_key = None

        login_customer_id = None

        if audit.source == "live":
            try:
                creds = org.google_credentials
                credentials = {
                    "developer_token": creds.developer_token,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "refresh_token": creds.refresh_token,
                }
                login_customer_id = creds.mcc_id or None
            except Exception:
                raise ValueError("No Google Ads credentials configured for this organization.")
        else:
            demo_key = audit.full_result.get("demo_key", "demo-moderate")

        result = run_audit(
            account_id=audit.account_id_raw,
            start_date=str(audit.date_range_start),
            end_date=str(audit.date_range_end),
            demo_key=demo_key,
            credentials=credentials,
            login_customer_id=login_customer_id,
        )

        scorecard = result.get("_scorecard") or {}
        scoring = result.get("_scoring_results") or {}
        scoring_summary = result.get("scoring", {})

        with transaction.atomic():
            # ── Update Audit composite fields ──────────────────────
            audit.composite_score = scoring_summary.get(
                "composite_score", scoring.get("composite_score")
            )
            audit.risk_band = scoring_summary.get("risk_band", "")
            audit.capital_implication = scoring_summary.get("capital_implication", "")
            audit.confidence = scoring_summary.get("confidence", "")
            audit.extraction_stats = _make_serializable(result.get("extraction_stats", {}))
            audit.full_result = _make_serializable(result)
            audit.status = Audit.Status.SUCCESS
            audit.completed_at = timezone.now()
            audit.duration_seconds = (
                audit.completed_at - audit.started_at
            ).total_seconds()

            # Update account_name from result if available
            if result.get("account", {}).get("name"):
                audit.account_name = result["account"]["name"]

            audit.save()

            # ── Save Domain Scores (5 rows) ────────────────────────
            domain_scores_data = scorecard.get("domain_scores", {})
            if isinstance(domain_scores_data, dict):
                for domain_key, ds in domain_scores_data.items():
                    if not isinstance(ds, dict):
                        continue
                    AuditDomainScore.objects.create(
                        audit=audit,
                        domain=domain_key,
                        value=ds.get("value", 0),
                        weight=ds.get("weight", 0),
                        weighted_contribution=ds.get("weighted_contribution", 0),
                        data_completeness=ds.get("data_completeness", 1.0),
                        key_findings=ds.get("key_findings", []),
                        sub_scores=ds.get("sub_scores", {}),
                    )

            # ── Save Red Flags (0-N rows) ──────────────────────────
            red_flags_data = scoring.get("red_flags", [])
            for rf in red_flags_data:
                rf_id = rf.id if hasattr(rf, "id") else rf.get("id", "")
                rule = RedFlagRule.objects.filter(id=rf_id).first()

                AuditRedFlag.objects.create(
                    audit=audit,
                    rule=rule,
                    rule_id_raw=rf_id,
                    severity=rf.severity if hasattr(rf, "severity") else rf.get("severity", "medium"),
                    domain=rf.domain if hasattr(rf, "domain") else rf.get("domain", ""),
                    title=rf.title if hasattr(rf, "title") else rf.get("title", ""),
                    description=rf.description if hasattr(rf, "description") else rf.get("description", ""),
                    recommendation=rf.recommendation if hasattr(rf, "recommendation") else rf.get("recommendation", ""),
                    evidence=rf.evidence if hasattr(rf, "evidence") else rf.get("evidence", {}),
                    triggered_by=rf.triggered_by if hasattr(rf, "triggered_by") else rf.get("triggered_by", ""),
                )

            # ── Save Reports (file outputs) ────────────────────────
            outputs = result.get("outputs", result.get("output_paths", {}))
            file_map = {
                "pdf_report": ("pdf", "report.pdf"),
                "html_report": ("html", "report.html"),
                "scorecard": ("json", "scorecard.json"),
                "evidence_pack": ("zip", "evidence_pack.zip"),
            }
            for output_key, (report_type, default_name) in file_map.items():
                file_path = outputs.get(output_key)
                if file_path:
                    _save_report_file(audit, report_type, file_path, default_name)

    except Exception as exc:
        audit.status = Audit.Status.FAILED
        audit.errors = [str(exc)]
        audit.completed_at = timezone.now()
        audit.save(update_fields=["status", "errors", "completed_at"])
        raise self.retry(exc=exc)


def _save_report_file(audit, report_type, file_path, default_name):
    """Save a generated file to the Report model."""
    import os

    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        report = Report(
            audit=audit,
            report_type=report_type,
            file_name=default_name,
            file_size=len(content),
        )
        report.file.save(default_name, ContentFile(content), save=True)
    except Exception:
        pass  # Non-critical — audit still succeeds without file storage
