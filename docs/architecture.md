# Arquitectura del Sistema

## Visión General

Media Integrity API es un backend multi-tenant que analiza cuentas de Google Ads y genera reportes de integridad estructural. El sistema evalúa 5 dominios de scoring, detecta red flags y produce reportes en múltiples formatos.

## Diagrama de Arquitectura General

```mermaid
graph TB
    subgraph Clients
        FE[Frontend React]
        EXT[Integraciones Externas]
    end

    subgraph API Layer
        DRF[Django REST Framework]
        AUTH[Auth Middleware<br/>JWT + API Key]
        SWAGGER[Swagger UI<br/>OpenAPI 3]
    end

    subgraph Task Queue
        CELERY[Celery Worker]
        REDIS[(Redis<br/>Broker)]
        FLOWER[Flower<br/>Monitor :5555]
    end

    subgraph Engine - Stateless
        ORCH[Orchestrator<br/>Pipeline Runner]
        CONN[Connectors<br/>Google Ads / GA4 / BQ]
        NORM[Normalization]
        SCORE[Scoring Engine<br/>5 Dominios]
        FLAGS[Red Flag Detector]
        REPORT[Report Generator<br/>PDF / HTML / Excel]
    end

    subgraph Storage
        DB[(PostgreSQL / SQLite)]
        FILES[Media Files<br/>Reports / Evidence]
    end

    subgraph External
        GADS[Google Ads API v23]
    end

    FE -->|HTTP + API Key| AUTH
    EXT -->|HTTP + JWT| AUTH
    AUTH --> DRF
    DRF --> SWAGGER
    DRF -->|Dispatch Task| REDIS
    REDIS --> CELERY
    CELERY --> ORCH
    ORCH --> CONN
    CONN --> GADS
    CONN --> NORM
    NORM --> SCORE
    SCORE --> FLAGS
    FLAGS --> REPORT
    CELERY -->|Save Results| DB
    REPORT --> FILES
    DRF --> DB
```

## Componentes Principales

### 1. API Layer (`api/`)

Capa REST construida con Django REST Framework. Maneja autenticación, serialización, permisos y routing.

- **Autenticación dual**: JWT (SimpleJWT) + API Key custom (`X-API-Key`)
- **OAuth2**: Flujo de autorización Google para obtener refresh token automáticamente (`/settings/google/oauth/`)
- **Permisos**: `IsAuthenticated` por defecto, `IsAdmin` para gestión de usuarios
- **Paginación**: PageNumberPagination (50 items/página)
- **Filtros**: DjangoFilterBackend + SearchFilter + OrderingFilter
- **Schema**: drf-spectacular genera OpenAPI 3 automáticamente

### 2. Core Models (`core/`)

13 modelos Django organizados en 5 grupos:

- **Tenant & Auth**: Organization, User, ApiKey
- **Billing**: BillingPlan (placeholder post-MVP)
- **Google Ads**: GoogleAdsCredential, GoogleAdsAccount
- **Settings**: ScoringConfig, ReportConfig, RedFlagRule
- **Audits**: Audit, AuditDomainScore, AuditRedFlag, Report

### 3. Engine (`engine/`)

Motor de análisis stateless — no depende de Django ORM. Procesamiento puro de datos.

```mermaid
graph LR
    subgraph engine/
        A[connectors/] --> B[normalization/]
        B --> C[scoring/]
        C --> D[reporting/]
        E[orchestrator/] -->|coordina| A
        E -->|coordina| B
        E -->|coordina| C
        E -->|coordina| D
    end
```

| Módulo | Responsabilidad |
|--------|----------------|
| `connectors/` | Extracción de datos (Google Ads, GA4, BigQuery) |
| `normalization/` | Normalización y limpieza de métricas |
| `scoring/` | Cálculo de scores por dominio + composite |
| `reporting/` | Generación de reportes (PDF, HTML, Excel, ZIP) |
| `orchestrator/` | Pipeline que coordina todo el flujo |

### 4. Task Queue (`tasks/`)

Celery ejecuta auditorías en background. El flujo:

1. API recibe `POST /api/v1/audits/run/`
2. Crea registro `Audit` con status `pending`
3. Despacha `run_audit_task` a Celery via Redis
4. Worker ejecuta pipeline completo del engine
5. Resultados se guardan en tablas normalizadas

### 5. Config (`config/`)

Configuración Django estándar con settings split:

- `settings/base.py` — Compartido (DRF, JWT, CORS, Celery)
- `settings/development.py` — SQLite, DEBUG=True
- `celery.py` — App Celery
- `urls.py` — Root URL conf

## Diagrama de Secuencia — Flujo de Auditoría

```mermaid
sequenceDiagram
    actor U as Usuario
    participant API as Django API
    participant DB as Database
    participant R as Redis
    participant W as Celery Worker
    participant E as Engine
    participant G as Google Ads

    U->>API: POST /api/v1/audits/run/
    API->>DB: Crear Audit (status=pending)
    API->>R: Dispatch run_audit_task
    API-->>U: 202 Accepted {run_id}

    R->>W: Dequeue task
    W->>DB: Update status=running
    W->>E: run_audit(account_id, dates)

    alt source=live
        E->>G: Fetch campaign data
        G-->>E: Raw metrics
    else source=demo
        E->>E: Load demo fixtures
    end

    E->>E: Normalize → Score → Red Flags
    E->>E: Generate Reports (PDF, HTML, Excel)
    E-->>W: Result dict

    W->>DB: Save AuditDomainScore (×5)
    W->>DB: Save AuditRedFlag (×N)
    W->>DB: Save Report files
    W->>DB: Update Audit (status=success)

    U->>API: GET /api/v1/audits/{id}/status/
    API->>DB: Query audit
    API-->>U: {status, progress, composite_score}
```

## Multi-Tenancy

El sistema implementa **tenant isolation** a nivel de organización:

```mermaid
graph TD
    ORG[Organization] --> USERS[Users]
    ORG --> KEYS[API Keys]
    ORG --> CREDS[Google Credentials]
    ORG --> ACCOUNTS[Google Ads Accounts]
    ORG --> AUDITS[Audits]
    ORG --> CONFIG[Scoring Config]
    ORG --> RULES[Red Flag Rules]
    ORG --> BILLING[Billing Plan]

    AUDITS --> SCORES[Domain Scores]
    AUDITS --> FLAGS[Red Flags]
    AUDITS --> REPORTS[Reports]
```

- Cada usuario pertenece a una organización
- Queries filtran por `organization` del usuario autenticado
- Superusers pueden ver todo
- Admins ven toda su organización
- Users regulares ven solo sus propios audits
