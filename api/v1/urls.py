"""
API v1 URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from api.v1.views.audits import AuditViewSet
from api.v1.views.health import HealthView
from api.v1.views.red_flags import RedFlagRuleViewSet
from api.v1.views.settings import (
    GoogleConfigView,
    ReportConfigView,
    ScoringConfigView,
    TestConnectionView,
)

router = DefaultRouter()
router.register(r"audits", AuditViewSet, basename="audit")
router.register(r"red-flags", RedFlagRuleViewSet, basename="red-flag")

urlpatterns = [
    path("", include(router.urls)),

    # JWT auth
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Settings
    path("settings/google/", GoogleConfigView.as_view(), name="settings-google"),
    path("settings/google/test/", TestConnectionView.as_view(), name="settings-google-test"),
    path("settings/scoring/", ScoringConfigView.as_view(), name="settings-scoring"),
    path("settings/report/", ReportConfigView.as_view(), name="settings-report"),

    # Health
    path("health/", HealthView.as_view(), name="health"),
]
