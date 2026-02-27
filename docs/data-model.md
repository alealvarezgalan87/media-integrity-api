# Modelo de Datos

## Diagrama Entidad-Relación

```mermaid
erDiagram
    Organization ||--o{ User : "tiene"
    Organization ||--o{ ApiKey : "tiene"
    Organization ||--o| BillingPlan : "tiene"
    Organization ||--o| GoogleAdsCredential : "tiene"
    Organization ||--o{ GoogleAdsAccount : "tiene"
    Organization ||--o| ScoringConfig : "tiene"
    Organization ||--o{ RedFlagRule : "tiene"
    Organization ||--o{ Audit : "tiene"

    User ||--o{ ApiKey : "crea"
    User ||--o{ Audit : "crea"
    User ||--o| ReportConfig : "tiene"

    Audit ||--o{ AuditDomainScore : "tiene"
    Audit ||--o{ AuditRedFlag : "tiene"
    Audit ||--o{ Report : "tiene"
    Audit }o--o| GoogleAdsAccount : "analiza"

    RedFlagRule ||--o{ AuditRedFlag : "dispara"

    Organization {
        UUID id PK
        string name
        string slug UK
        bool is_active
        datetime created_at
        datetime updated_at
    }

    User {
        UUID id PK
        UUID organization_id FK
        string username UK
        string email
        string role "admin | user"
        bool is_active
    }

    ApiKey {
        UUID id PK
        UUID organization_id FK
        UUID created_by FK
        string name
        string key_hash UK
        string prefix
        json scopes
        bool is_active
        datetime expires_at
        datetime last_used_at
    }

    BillingPlan {
        int id PK
        UUID organization_id FK
        string tier "starter | professional | enterprise"
        int max_audits_per_month
        int max_accounts
        int max_users
        string stripe_customer_id
        string stripe_subscription_id
    }

    GoogleAdsCredential {
        int id PK
        UUID organization_id FK
        string developer_token
        string client_id
        string client_secret
        text refresh_token
        string mcc_id
        string api_version
        bool is_verified
        datetime last_verified_at
    }

    GoogleAdsAccount {
        UUID id PK
        UUID organization_id FK
        string account_id
        string account_name
        string currency
        string timezone
        bool is_active
    }

    ScoringConfig {
        int id PK
        UUID organization_id FK
        float demand_capture_weight
        float automation_exposure_weight
        float measurement_integrity_weight
        float capital_allocation_weight
        float creative_velocity_weight
        string company_name
        string report_title
        string page_size
    }

    ReportConfig {
        int id PK
        UUID user_id FK
        string company_name
        string report_title
        string footer_text
        string page_size
    }

    RedFlagRule {
        string id PK
        UUID organization_id FK
        string severity
        string domain
        string condition
        string title
        text description
        text recommendation
        bool enabled
        int sort_order
        bool is_system
    }

    Audit {
        UUID run_id PK
        UUID organization_id FK
        UUID created_by FK
        UUID account_id FK
        string account_id_raw
        string account_name
        date date_range_start
        date date_range_end
        string source "demo | live"
        string status "pending | running | success | failed"
        int composite_score
        string risk_band
        string capital_implication
        string confidence
        json full_result
        json errors
    }

    AuditDomainScore {
        UUID id PK
        UUID audit_id FK
        string domain
        int value
        float weight
        float weighted_contribution
        float data_completeness
        json key_findings
        json sub_scores
    }

    AuditRedFlag {
        UUID id PK
        UUID audit_id FK
        string rule_id FK
        string rule_id_raw
        string severity
        string domain
        string title
        text description
        text recommendation
        json evidence
        string triggered_by
    }

    Report {
        UUID id PK
        UUID audit_id FK
        string report_type "pdf | html | xlsx | json | zip"
        file file
        int file_size
        string file_name
        int version
    }
```

## Descripción de Entidades

### Tenant & Auth

| Modelo | Tabla | Descripción |
|--------|-------|-------------|
| **Organization** | `core_organization` | Tenant principal. Cada empresa tiene su organización aislada. |
| **User** | `auth_user` | Extiende `AbstractUser`. Vinculado a una organización con rol `admin` o `user`. |
| **ApiKey** | `core_apikey` | Claves de API por organización. Soporta keys de sesión efímeras y keys permanentes. |

### Billing

| Modelo | Tabla | Descripción |
|--------|-------|-------------|
| **BillingPlan** | `core_billingplan` | Plan de suscripción (Starter/Professional/Enterprise). Placeholder post-MVP. Integración con Stripe. |

### Google Ads

| Modelo | Tabla | Descripción |
|--------|-------|-------------|
| **GoogleAdsCredential** | `core_googleadscredential` | Credenciales OAuth por organización (developer token, client ID/secret, refresh token, MCC ID). |
| **GoogleAdsAccount** | `core_googleadsaccount` | Cuentas descubiertas bajo un MCC. Unique constraint `(organization, account_id)`. |

### Settings & Rules

| Modelo | Tabla | Descripción |
|--------|-------|-------------|
| **ScoringConfig** | `core_scoringconfig` | Pesos de los 5 dominios + branding del reporte. Uno por organización. |
| **ReportConfig** | `core_reportconfig` | Configuración de reporte por usuario (nombre empresa, título, footer, tamaño página). |
| **RedFlagRule** | `core_redflagrule` | Reglas de red flags. Pueden ser globales (`organization=null`) o por organización. Las reglas de sistema (`is_system=true`) no se pueden eliminar. |

### Audits

| Modelo | Tabla | Descripción |
|--------|-------|-------------|
| **Audit** | `core_audit` | Entidad central. Una auditoría ejecutada con status, scores, y resultado completo en JSON. |
| **AuditDomainScore** | `core_auditdomainscore` | 5 filas por auditoría (una por dominio). Score, peso, contribución ponderada, sub-scores. |
| **AuditRedFlag** | `core_auditredflag` | 0-N red flags disparados en una auditoría. Vinculados a la regla original. |
| **Report** | `core_report` | Archivos generados (PDF, HTML, Excel, JSON scorecard, Evidence Pack ZIP). Versionados. |

## Dominios de Scoring

Cada auditoría produce 5 domain scores:

| Dominio | Clave | Peso Default |
|---------|-------|-------------|
| Demand Capture Integrity | `demand_capture_integrity` | 0.25 |
| Automation Exposure | `automation_exposure` | 0.20 |
| Measurement Integrity | `measurement_integrity` | 0.25 |
| Capital Allocation Discipline | `capital_allocation_discipline` | 0.20 |
| Creative Velocity | `creative_velocity` | 0.10 |

El **composite score** (0-100) es la suma ponderada de los 5 dominios.
