import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify


# ═══════════════════════════════════════════════════════════════════════════════
# TENANT & AUTH
# ═══════════════════════════════════════════════════════════════════════════════


class Organization(models.Model):
    """Tenant — cada empresa es una organización."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Usuario extendido con organización y rol."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        USER = "user", "User"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)

    google_ads_accounts = models.ManyToManyField(
        "GoogleAdsAccount",
        blank=True,
        related_name="users",
    )

    class Meta:
        db_table = "auth_user"


class ApiKey(models.Model):
    """API Keys por organización — para integraciones de terceros."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="api_keys"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    name = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=128, unique=True)
    prefix = models.CharField(max_length=8)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"


# ═══════════════════════════════════════════════════════════════════════════════
# BILLING (placeholder — se activa post-MVP)
# ═══════════════════════════════════════════════════════════════════════════════


class BillingPlan(models.Model):
    """Plan de suscripción por organización."""

    class Tier(models.TextChoices):
        STARTER = "starter", "Starter"
        PROFESSIONAL = "professional", "Professional"
        ENTERPRISE = "enterprise", "Enterprise"

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="billing"
    )
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.STARTER)
    max_audits_per_month = models.IntegerField(default=10)
    max_accounts = models.IntegerField(default=5)
    max_users = models.IntegerField(default=3)
    is_active = models.BooleanField(default=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization.name} — {self.get_tier_display()}"


# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE ADS ACCOUNTS & CREDENTIALS
# ═══════════════════════════════════════════════════════════════════════════════


class GoogleAdsCredential(models.Model):
    """Credenciales Google Ads por organización."""

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="google_credentials"
    )
    developer_token = models.CharField(max_length=200)
    client_id = models.CharField(max_length=200)
    client_secret = models.CharField(max_length=200)
    refresh_token = models.TextField()
    mcc_id = models.CharField(max_length=20, blank=True)
    api_version = models.CharField(max_length=10, default="v23")
    is_verified = models.BooleanField(default=False)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    account_sync_interval_hours = models.PositiveIntegerField(
        default=6,
        help_text="How often to sync accounts from Google Ads (in hours)",
    )
    oauth_scopes = models.TextField(
        blank=True,
        default="",
        help_text="Space-separated OAuth2 scopes granted by the current refresh token",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization.name} — MCC {self.mcc_id}"


class GoogleAdsAccount(models.Model):
    """Cuentas Google Ads descubiertas bajo un MCC."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="google_ads_accounts"
    )
    account_id = models.CharField(max_length=20)
    account_name = models.CharField(max_length=200)
    currency = models.CharField(max_length=10, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    ga4_property = models.ForeignKey(
        "GA4Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="google_ads_accounts",
    )

    class Meta:
        unique_together = ("organization", "account_id")

    def __str__(self):
        return f"{self.account_name} ({self.account_id})"


class GA4Property(models.Model):
    """Propiedades GA4 descubiertas vía Analytics Admin API."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="ga4_properties"
    )
    property_id = models.CharField(max_length=20)
    display_name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=10, blank=True)
    industry_category = models.CharField(max_length=100, blank=True)
    service_level = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    bq_project_id = models.CharField(max_length=100, blank=True)
    bq_dataset_id = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ("organization", "property_id")

    def __str__(self):
        return f"{self.display_name} ({self.property_id})"


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS & RULES
# ═══════════════════════════════════════════════════════════════════════════════


class ScoringConfig(models.Model):
    """Configuración de scoring por organización."""

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="scoring_config"
    )
    demand_capture_weight = models.FloatField(default=0.25)
    automation_exposure_weight = models.FloatField(default=0.20)
    measurement_integrity_weight = models.FloatField(default=0.25)
    capital_allocation_weight = models.FloatField(default=0.20)
    creative_velocity_weight = models.FloatField(default=0.10)

    company_name = models.CharField(max_length=200, default="")
    report_title = models.CharField(
        max_length=200, default="Media Operations Integrity Report"
    )
    footer_text = models.CharField(max_length=500, default="CONFIDENTIAL")
    page_size = models.CharField(max_length=10, default="A4")

    def weights_dict(self):
        return {
            "demand_capture_integrity": self.demand_capture_weight,
            "automation_exposure": self.automation_exposure_weight,
            "measurement_integrity": self.measurement_integrity_weight,
            "capital_allocation_discipline": self.capital_allocation_weight,
            "creative_velocity": self.creative_velocity_weight,
        }

    def __str__(self):
        return f"ScoringConfig — {self.organization.name}"


class ReportConfig(models.Model):
    """Configuración de reporte por usuario."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="report_config"
    )
    company_name = models.CharField(max_length=200, default="")
    report_title = models.CharField(
        max_length=200, default="Media Operations Integrity Report"
    )
    footer_text = models.CharField(max_length=500, default="CONFIDENTIAL")
    page_size = models.CharField(max_length=10, default="A4")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ReportConfig — {self.user.username}"


class RedFlagRule(models.Model):
    """Reglas de red flags — globales o por organización."""

    id = models.CharField(max_length=50, primary_key=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="red_flag_rules",
        null=True,
        blank=True,
    )
    severity = models.CharField(max_length=20, default="medium")
    domain = models.CharField(max_length=50)
    condition = models.CharField(max_length=300)
    title = models.CharField(max_length=200)
    description = models.TextField()
    recommendation = models.TextField()
    enabled = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.id} — {self.title}"


# ═══════════════════════════════════════════════════════════════════════════════
# AUDITS (core entity)
# ═══════════════════════════════════════════════════════════════════════════════


class Audit(models.Model):
    """Auditoría ejecutada — entidad central."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    run_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="audits"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    account = models.ForeignKey(
        GoogleAdsAccount, on_delete=models.SET_NULL, null=True, blank=True
    )
    account_id_raw = models.CharField(max_length=20)
    account_name = models.CharField(max_length=200)
    date_range_start = models.DateField()
    date_range_end = models.DateField()
    source = models.CharField(max_length=20, default="demo")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    composite_score = models.IntegerField(null=True)
    risk_band = models.CharField(max_length=50, blank=True)
    capital_implication = models.CharField(max_length=20, blank=True)
    confidence = models.CharField(max_length=20, blank=True)

    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    duration_seconds = models.FloatField(null=True)
    extraction_stats = models.JSONField(default=dict)
    errors = models.JSONField(default=list)

    full_result = models.JSONField(default=dict)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account_name} — {self.created_at:%Y-%m-%d}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self) -> str:
        date_str = str(self.date_range_start) if self.date_range_start else "draft"
        base = slugify(f"{self.account_name}-{date_str}")
        if not base:
            base = "audit"
        base = base[:100]
        candidate = base
        counter = 1
        while Audit.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT RESULTS (normalized — one row per domain / per flag)
# ═══════════════════════════════════════════════════════════════════════════════


class AuditDomainScore(models.Model):
    """Score de un dominio para una auditoría específica."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    audit = models.ForeignKey(
        Audit, on_delete=models.CASCADE, related_name="domain_scores"
    )

    class Domain(models.TextChoices):
        DEMAND_CAPTURE = "demand_capture_integrity", "Demand Capture"
        AUTOMATION = "automation_exposure", "Automation Exposure"
        MEASUREMENT = "measurement_integrity", "Measurement Integrity"
        CAPITAL = "capital_allocation_discipline", "Capital Allocation"
        CREATIVE = "creative_velocity", "Creative Velocity"

    domain = models.CharField(max_length=50, choices=Domain.choices)
    value = models.IntegerField()
    weight = models.FloatField()
    weighted_contribution = models.FloatField()
    data_completeness = models.FloatField(default=1.0)
    key_findings = models.JSONField(default=list)
    sub_scores = models.JSONField(default=dict)

    class Meta:
        unique_together = ("audit", "domain")
        ordering = ["domain"]

    def __str__(self):
        return f"{self.audit.account_name} — {self.get_domain_display()}: {self.value}"


class AuditRedFlag(models.Model):
    """Red flag disparado en una auditoría específica."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    audit = models.ForeignKey(
        Audit, on_delete=models.CASCADE, related_name="red_flags"
    )
    rule = models.ForeignKey(
        RedFlagRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_instances",
    )
    rule_id_raw = models.CharField(max_length=50)
    severity = models.CharField(max_length=20)
    domain = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    description = models.TextField()
    recommendation = models.TextField()
    evidence = models.JSONField(default=dict)
    triggered_by = models.CharField(max_length=300)

    class Meta:
        ordering = ["-severity", "domain"]

    def __str__(self):
        return f"{self.rule_id_raw} — {self.title}"


# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS & EVIDENCE (files as first-class entities)
# ═══════════════════════════════════════════════════════════════════════════════


class Report(models.Model):
    """Archivo de reporte generado para una auditoría."""

    class ReportType(models.TextChoices):
        PDF = "pdf", "PDF Report"
        HTML = "html", "HTML Report"
        EXCEL = "xlsx", "Excel Report"
        JSON = "json", "Scorecard JSON"
        EVIDENCE = "zip", "Evidence Pack"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    audit = models.ForeignKey(
        Audit, on_delete=models.CASCADE, related_name="reports"
    )
    report_type = models.CharField(max_length=10, choices=ReportType.choices)
    file = models.FileField(upload_to="reports/%Y/%m/")
    file_size = models.IntegerField(default=0)
    file_name = models.CharField(max_length=200)
    generated_at = models.DateTimeField(auto_now_add=True)
    version = models.IntegerField(default=1)

    class Meta:
        unique_together = ("audit", "report_type", "version")
        ordering = ["report_type", "-version"]

    def __str__(self):
        return f"{self.file_name} (v{self.version})"
