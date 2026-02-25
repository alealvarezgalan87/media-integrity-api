"""
API Key authentication backend for DRF.
Authenticates requests using X-API-Key header.
"""

import hashlib

from django.utils import timezone
from rest_framework import authentication, exceptions


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate requests using an API key in the X-API-Key header."""

    keyword = "X-API-Key"

    def authenticate(self, request):
        api_key = request.META.get("HTTP_X_API_KEY")
        if not api_key:
            return None

        from core.models import ApiKey

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        try:
            key_obj = ApiKey.objects.select_related(
                "organization"
            ).get(key_hash=key_hash, is_active=True)
        except ApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key.")

        if key_obj.expires_at and key_obj.expires_at < timezone.now():
            raise exceptions.AuthenticationFailed("API key expired.")

        # Update last_used_at
        ApiKey.objects.filter(pk=key_obj.pk).update(last_used_at=timezone.now())

        # Return the first admin user of the organization, or create a system user
        user = key_obj.organization.users.filter(is_active=True).first()
        if not user:
            raise exceptions.AuthenticationFailed("No active users in organization.")

        return (user, key_obj)
