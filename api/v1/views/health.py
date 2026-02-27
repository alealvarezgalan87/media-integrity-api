"""Health check endpoint."""

from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        responses={
            200: inline_serializer(
                name="HealthResponse",
                fields={
                    "status": serializers.CharField(),
                    "version": serializers.CharField(),
                    "timestamp": serializers.DateTimeField(),
                },
            ),
        },
    )
    def get(self, request):
        return Response({
            "status": "ok",
            "version": "1.0.0",
            "timestamp": timezone.now().isoformat(),
        })
