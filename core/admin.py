from django.contrib import admin

from core.models import (
    ApiKey,
    Audit,
    AuditDomainScore,
    AuditRedFlag,
    BillingPlan,
    GA4Property,
    GoogleAdsAccount,
    GoogleAdsCredential,
    Organization,
    RedFlagRule,
    Report,
    ScoringConfig,
    User,
)


# ── Inlines (nested inside Audit detail) ─────────────────────────


class AuditDomainScoreInline(admin.TabularInline):
    model = AuditDomainScore
    extra = 0
    readonly_fields = ["domain", "value", "weight", "weighted_contribution", "data_completeness"]
    can_delete = False


class AuditRedFlagInline(admin.TabularInline):
    model = AuditRedFlag
    extra = 0
    readonly_fields = ["rule_id_raw", "severity", "domain", "title"]
    can_delete = False


class ReportInline(admin.TabularInline):
    model = Report
    extra = 0
    readonly_fields = ["report_type", "file_name", "file_size", "generated_at", "version"]
    can_delete = False


# ── Tenant & Auth ─────────────────────────────────────────────────


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["username", "email", "organization", "role", "is_active"]
    list_filter = ["role", "organization", "is_active"]
    search_fields = ["username", "email"]
    filter_horizontal = ["google_ads_accounts"]


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "prefix", "organization", "is_active", "last_used_at", "expires_at"]
    list_filter = ["is_active", "organization"]
    readonly_fields = ["key_hash", "prefix", "last_used_at"]


@admin.register(BillingPlan)
class BillingPlanAdmin(admin.ModelAdmin):
    list_display = ["organization", "tier", "max_audits_per_month", "max_accounts", "is_active"]
    list_filter = ["tier", "is_active"]


# ── Google Ads ────────────────────────────────────────────────────


@admin.register(GoogleAdsCredential)
class GoogleAdsCredentialAdmin(admin.ModelAdmin):
    list_display = ["organization", "mcc_id", "api_version", "is_verified", "last_verified_at"]
    readonly_fields = ["client_secret", "refresh_token"]


@admin.register(GoogleAdsAccount)
class GoogleAdsAccountAdmin(admin.ModelAdmin):
    list_display = ["account_name", "account_id", "organization", "currency", "ga4_property", "is_active"]
    list_filter = ["is_active", "organization", "currency"]
    search_fields = ["account_name", "account_id"]


@admin.register(GA4Property)
class GA4PropertyAdmin(admin.ModelAdmin):
    list_display = ["display_name", "property_id", "organization", "timezone", "currency", "is_active", "last_synced_at"]
    list_filter = ["organization", "is_active"]
    search_fields = ["display_name", "property_id"]
    readonly_fields = ["id", "last_synced_at"]


# ── Settings & Rules ─────────────────────────────────────────────


@admin.register(ScoringConfig)
class ScoringConfigAdmin(admin.ModelAdmin):
    list_display = ["organization", "company_name", "page_size"]


@admin.register(RedFlagRule)
class RedFlagRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "severity", "domain", "enabled", "is_system", "organization"]
    list_filter = ["severity", "domain", "enabled", "is_system", "organization"]
    list_editable = ["enabled"]
    search_fields = ["id", "title"]


# ── Audits (with inlines) ────────────────────────────────────────


@admin.register(Audit)
class AuditAdmin(admin.ModelAdmin):
    list_display = [
        "run_id", "account_name", "organization", "status",
        "composite_score", "risk_band", "capital_implication", "created_at",
    ]
    list_filter = ["status", "risk_band", "capital_implication", "source", "organization"]
    search_fields = ["account_name", "account_id_raw"]
    readonly_fields = ["run_id", "full_result", "extraction_stats", "errors"]
    date_hierarchy = "created_at"
    inlines = [AuditDomainScoreInline, AuditRedFlagInline, ReportInline]


# ── Standalone views of normalized tables (for analytics) ────────


@admin.register(AuditDomainScore)
class AuditDomainScoreAdmin(admin.ModelAdmin):
    list_display = ["audit", "domain", "value", "weight", "weighted_contribution"]
    list_filter = ["domain"]


@admin.register(AuditRedFlag)
class AuditRedFlagAdmin(admin.ModelAdmin):
    list_display = ["audit", "rule_id_raw", "severity", "domain", "title"]
    list_filter = ["severity", "domain"]
    search_fields = ["rule_id_raw", "title"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["audit", "report_type", "file_name", "file_size", "version", "generated_at"]
    list_filter = ["report_type"]
