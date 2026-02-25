"""
Session-based API key authentication.
Login: authenticate user/pass → create ephemeral API key → return raw key.
Logout: destroy the session API key.
"""

import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ApiKey

SESSION_TTL_HOURS = 24


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class SessionLoginView(APIView):
    """POST /api/v1/auth/login/ — returns a session API key."""

    permission_classes = [AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=ser.validated_data["username"],
            password=ser.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Generate ephemeral API key
        raw_key = f"sk-{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        prefix = raw_key[:8]

        # If user has no org, create a personal one
        org = user.organization
        if org is None:
            from core.models import Organization
            org, _ = Organization.objects.get_or_create(
                slug=f"personal-{user.pk}",
                defaults={"name": f"{user.username}'s workspace"},
            )
            user.organization = org
            user.save(update_fields=["organization"])

        api_key = ApiKey.objects.create(
            name=f"session-{user.username}",
            key_hash=key_hash,
            prefix=prefix,
            organization=org,
            created_by=user,
            is_active=True,
            scopes=["session"],
            expires_at=timezone.now() + timedelta(hours=SESSION_TTL_HOURS),
        )

        return Response({
            "api_key": raw_key,
            "user": {
                "username": user.username,
                "email": user.email,
                "role": getattr(user, "role", "user"),
            },
            "organization": {
                "name": org.name,
                "slug": org.slug,
            },
        })


class SessionLogoutView(APIView):
    """POST /api/v1/auth/logout/ — destroys the session API key."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # If authenticated via API key, delete it
        if hasattr(request, "auth") and isinstance(request.auth, ApiKey):
            request.auth.delete()
            return Response({"detail": "Session destroyed."})

        # If authenticated via JWT, destroy all session keys for user
        ApiKey.objects.filter(
            created_by=request.user,
            scopes__contains=["session"],
        ).delete()

        return Response({"detail": "All sessions destroyed."})


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/ — change the current user's password."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(ser.validated_data["current_password"]):
            return Response(
                {"current_password": ["Current password is incorrect."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(ser.validated_data["new_password"])
        user.save(update_fields=["password"])

        # Destroy all session keys — forces re-login with new password
        ApiKey.objects.filter(
            created_by=user,
            scopes__contains=["session"],
        ).delete()

        return Response({"detail": "Password changed. Please log in again."})
