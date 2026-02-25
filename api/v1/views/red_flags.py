"""
RedFlagRule ViewSet — CRUD with org scoping and system rule protection.
"""

from django.db import models
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.serializers import RedFlagRuleSerializer
from core.models import RedFlagRule


class RedFlagRuleViewSet(viewsets.ModelViewSet):
    serializer_class = RedFlagRuleSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return RedFlagRule.objects.all()
        if user.organization:
            return RedFlagRule.objects.filter(
                models.Q(organization=None) | models.Q(organization=user.organization)
            )
        return RedFlagRule.objects.filter(organization=None)

    def perform_create(self, serializer):
        org = self.request.user.organization
        serializer.save(organization=org, is_system=False)

    def perform_update(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system:
            return Response(
                {"error": "System rules cannot be deleted."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
