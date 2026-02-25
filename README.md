# Media Integrity API

**Media Structural Integrity Engine™** — Django REST API Backend

## Stack

- **Django 5.x** + **Django REST Framework**
- **Celery** + **Redis** (async audit pipeline)
- **PostgreSQL** (production) / **SQLite** (development)
- **JWT** + **API Key** authentication

## Quick Start (Local)

```bash
# 1. Install dependencies
pip install -e .

# 2. Run migrations
python manage.py migrate

# 3. Create superuser
python manage.py createsuperuser

# 4. Seed red flag rules
python manage.py seed_rules

# 5. Start server
python manage.py runserver 8000
```

Admin panel: http://localhost:8000/admin/

## Quick Start (Docker)

```bash
# Copy env file
cp .env.example .env

# Start all services
docker-compose up

# Run migrations (first time)
docker-compose exec api python manage.py migrate
docker-compose exec api python manage.py createsuperuser
docker-compose exec api python manage.py seed_rules
```

Services:
- **API**: http://localhost:8000
- **Admin**: http://localhost:8000/admin/
- **Flower** (Celery monitor): http://localhost:5555

## Environment Variables

See `.env.example` for all available variables.

## Data Model

13 tables organized around multi-tenant architecture:

- **Organization** — Tenant (company)
- **User** — Extended with organization + role
- **ApiKey** — Scoped API keys for integrations
- **BillingPlan** — Subscription tier (post-MVP)
- **GoogleAdsCredential** — Encrypted OAuth tokens
- **GoogleAdsAccount** — Discovered MCC accounts
- **ScoringConfig** — Weights + report branding
- **RedFlagRule** — Global or org-specific rules
- **Audit** — Core audit entity
- **AuditDomainScore** — Normalized scores (5 per audit)
- **AuditRedFlag** — Triggered flags per audit
- **Report** — Generated files (PDF, XLSX, ZIP, etc.)

## API

All endpoints under `/api/v1/`. Authentication via JWT (`Authorization: Bearer <token>`) or API Key (`X-API-Key: <key>`).
