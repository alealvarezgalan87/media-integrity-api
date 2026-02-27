# Media Integrity API — Documentación

**Media Structural Integrity Engine™** — Backend REST API

## Índice

| Documento | Descripción |
|-----------|-------------|
| [Arquitectura](./architecture.md) | Visión general del sistema, componentes y diagramas |
| [Modelo de Datos](./data-model.md) | Entidades, relaciones y diagrama ER |
| [Referencia API](./api-reference.md) | Endpoints, métodos, request/response |
| [Autenticación](./authentication.md) | Flujos de auth (Session API Key + JWT) |
| [Pipeline de Auditoría](./audit-pipeline.md) | Motor de análisis, scoring y reporting |
| [Despliegue y CI/CD](./deployment.md) | Docker, Railway, GitHub Actions |

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| **Framework** | Django 5.x + Django REST Framework |
| **Auth** | JWT (SimpleJWT) + API Key custom |
| **Task Queue** | Celery + Redis |
| **Base de datos** | PostgreSQL (prod) / SQLite (dev) |
| **Reporting** | WeasyPrint (PDF), Jinja2 (HTML), OpenPyXL (Excel) |
| **Google Ads** | google-ads SDK v23 |
| **API Docs** | drf-spectacular (OpenAPI 3 + Swagger UI) |
| **Deploy** | Docker + Railway |
| **CI/CD** | GitHub Actions |

## Estructura del Proyecto

```
media-integrity-api/
├── api/                    # Django REST Framework layer
│   ├── authentication.py   # API Key auth backend
│   └── v1/                 # API v1 (views, serializers, urls)
├── config/                 # Django settings & WSGI/ASGI
│   ├── settings/
│   │   ├── base.py         # Settings compartidos
│   │   └── development.py  # Settings de desarrollo
│   ├── celery.py           # Configuración Celery
│   └── urls.py             # URL root
├── core/                   # Modelos Django (13 tablas)
│   └── models.py
├── engine/                 # Motor de análisis (stateless)
│   ├── auth/               # MCC Manager (Google OAuth)
│   ├── connectors/         # Google Ads, GA4, BigQuery
│   ├── normalization/      # Normalización de datos
│   ├── orchestrator/       # Pipeline runner
│   ├── scoring/            # 5 dominios + red flags + composite
│   └── reporting/          # PDF, HTML, Excel, Evidence Pack
├── tasks/                  # Celery tasks
│   └── audit_tasks.py      # Task principal de auditoría
├── Dockerfile
├── docker-compose.yml
├── Procfile                # Railway/Heroku
├── pyproject.toml          # Dependencias
└── .github/workflows/ci.yml
```
