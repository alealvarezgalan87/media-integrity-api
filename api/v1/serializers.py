"""
DRF Serializers for Media Integrity API v1.
"""

from rest_framework import serializers

from core.models import (
    ApiKey,
    Audit,
    AuditDomainScore,
    AuditRedFlag,
    GoogleAdsCredential,
    RedFlagRule,
    Report,
    ScoringConfig,
)


# ── Audit Results (normalized) ────────────────────────────────────


class AuditDomainScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditDomainScore
        fields = [
            "domain", "value", "weight", "weighted_contribution",
            "data_completeness", "key_findings", "sub_scores",
        ]


class AuditRedFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditRedFlag
        fields = [
            "rule_id_raw", "severity", "domain", "title",
            "description", "recommendation", "evidence", "triggered_by",
        ]


class ReportSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            "report_type", "file_name", "file_size",
            "generated_at", "version", "download_url",
        ]

    def get_download_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


# ── Audits ─────────────────────────────────────────────────────────


class AuditListSerializer(serializers.ModelSerializer):
    red_flags_count = serializers.SerializerMethodField()

    class Meta:
        model = Audit
        fields = [
            "run_id", "slug", "account_name", "account_id_raw", "source",
            "status", "composite_score", "risk_band", "capital_implication",
            "confidence", "red_flags_count",
            "date_range_start", "date_range_end", "created_at",
        ]

    def get_red_flags_count(self, obj):
        return obj.red_flags.count()


class AuditDetailSerializer(serializers.ModelSerializer):
    domain_scores = AuditDomainScoreSerializer(many=True, read_only=True)
    red_flags = AuditRedFlagSerializer(many=True, read_only=True)
    reports = ReportSerializer(many=True, read_only=True)
    red_flags_count = serializers.SerializerMethodField()
    ga4_summary = serializers.SerializerMethodField()
    confidence_summary = serializers.SerializerMethodField()

    class Meta:
        model = Audit
        exclude = ["full_result"]

    def get_red_flags_count(self, obj):
        return obj.red_flags.count()

    def get_ga4_summary(self, obj):
        """Extract GA4 summary from full_result for frontend display."""
        fr = obj.full_result or {}
        scorecard = fr.get("_scorecard", fr)
        tables = scorecard.get("tables", {})
        mi = tables.get("measurement_integrity", {})
        ca = tables.get("capital_allocation", {})
        es = obj.extraction_stats or {}

        ga4_source = es.get("ga4_source")
        if not ga4_source:
            ga4_raw = fr.get("_ga4_raw_data", scorecard.get("_ga4_raw_data", {}))
            ga4_source = ga4_raw.get("source") if ga4_raw else None

        if not ga4_source:
            return None

        return {
            "paid_revenue_share": ca.get("paid_revenue_share", 0) or 0,
            "ga4_ads_revenue_discrepancy": mi.get("ga4_ads_revenue_discrepancy", 0) or 0,
            "ga4_ads_conversion_discrepancy": mi.get("ga4_ads_conversion_discrepancy", 0) or 0,
            "ga4_source": ga4_source,
        }

    def get_confidence_summary(self, obj):
        """Extract confidence summary from full_result for frontend display."""
        fr = obj.full_result or {}
        scorecard = fr.get("_scorecard", fr)
        confidence_data = scorecard.get("_confidence")
        if not confidence_data:
            return None
        return {
            "overall": confidence_data.get("overall_confidence", "Unknown"),
            "completeness": confidence_data.get("overall_data_completeness", 0),
        }


class RunAuditSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=["demo", "live"])
    demo_key = serializers.CharField(required=False, default="demo-moderate")
    account_id = serializers.CharField(required=False)
    account_name = serializers.CharField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)

    def validate(self, data):
        if data["source"] == "live" and not data.get("account_id"):
            raise serializers.ValidationError(
                {"account_id": "Required for live audits."}
            )
        return data


# ── Settings & Rules ───────────────────────────────────────────────


class RedFlagRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedFlagRule
        fields = "__all__"
        read_only_fields = ["is_system", "organization"]


class ScoringConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoringConfig
        exclude = ["id", "organization"]

    def validate(self, data):
        weights = [
            data.get("demand_capture_weight", 0.25),
            data.get("automation_exposure_weight", 0.20),
            data.get("measurement_integrity_weight", 0.25),
            data.get("capital_allocation_weight", 0.20),
            data.get("creative_velocity_weight", 0.10),
        ]
        total = sum(weights)
        if abs(total - 1.0) > 0.01:
            raise serializers.ValidationError(
                f"Weights must sum to 1.0 (currently {total:.2f})."
            )
        return data


class GoogleAdsConfigSerializer(serializers.Serializer):
    developer_token = serializers.CharField(required=False, allow_blank=True)
    client_id = serializers.CharField(required=False, allow_blank=True)
    client_secret = serializers.CharField(required=False, allow_blank=True)
    refresh_token = serializers.CharField(required=False, allow_blank=True)
    mcc_id = serializers.CharField(required=False, allow_blank=True)
    api_version = serializers.CharField(required=False, default="v23")
    account_sync_interval_hours = serializers.IntegerField(required=False, min_value=1, max_value=168)


class ReportOptionsSerializer(serializers.Serializer):
    company_name = serializers.CharField(required=False, allow_blank=True)
    report_title = serializers.CharField(required=False, allow_blank=True)
    footer_text = serializers.CharField(required=False, allow_blank=True)
    page_size = serializers.ChoiceField(choices=["A4", "Letter"], required=False)


# ── API Keys ───────────────────────────────────────────────────────


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = [
            "id", "name", "prefix", "scopes", "is_active",
            "last_used_at", "expires_at", "created_at",
        ]
        read_only_fields = ["id", "prefix", "last_used_at", "created_at"]
