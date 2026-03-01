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
from api.v1.views.auth import ChangePasswordView, SessionLoginView, SessionLogoutView
from api.v1.views.health import HealthView
from api.v1.views.red_flags import RedFlagRuleViewSet
from api.v1.views.users import UserViewSet
from api.v1.views.google_oauth import (
    GoogleOAuthAuthorizeView,
    GoogleOAuthCallbackView,
    GoogleOAuthStatusView,
)
from api.v1.views.settings import (
    GoogleAccountDetailView,
    GoogleAccountsListView,
    GoogleAccountsSyncView,
    GoogleConfigView,
    ReportConfigView,
    ScoringConfigView,
    TestConnectionView,
)

router = DefaultRouter()
router.register(r"audits", AuditViewSet, basename="audit")
router.register(r"red-flags", RedFlagRuleViewSet, basename="red-flag")
router.register(r"users", UserViewSet, basename="user")

urlpatterns = [
    path("", include(router.urls)),

    # Session auth (API key per session)
    path("auth/login/", SessionLoginView.as_view(), name="session-login"),
    path("auth/logout/", SessionLogoutView.as_view(), name="session-logout"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),

    # JWT auth (alternative)
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Settings
    path("settings/google/", GoogleConfigView.as_view(), name="settings-google"),
    path("settings/google/test/", TestConnectionView.as_view(), name="settings-google-test"),
    path("settings/google/accounts/", GoogleAccountsListView.as_view(), name="settings-google-accounts"),
    path("settings/google/accounts/sync/", GoogleAccountsSyncView.as_view(), name="settings-google-accounts-sync"),
    path("settings/google/accounts/<str:account_id>/", GoogleAccountDetailView.as_view(), name="settings-google-account-detail"),
    path("settings/google/oauth/authorize/", GoogleOAuthAuthorizeView.as_view(), name="google-oauth-authorize"),
    path("settings/google/oauth/callback/", GoogleOAuthCallbackView.as_view(), name="google-oauth-callback"),
    path("settings/google/oauth/status/", GoogleOAuthStatusView.as_view(), name="google-oauth-status"),
    path("settings/scoring/", ScoringConfigView.as_view(), name="settings-scoring"),
    path("settings/report/", ReportConfigView.as_view(), name="settings-report"),

    # Health
    path("health/", HealthView.as_view(), name="health"),
]
