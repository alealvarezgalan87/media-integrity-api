"""
User management ViewSet — list, create, update, delete users.
Only admins can manage users.
"""

from rest_framework import serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import GoogleAdsAccount, User


class GoogleAdsAccountBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleAdsAccount
        fields = ["id", "account_id", "account_name"]


class UserSerializer(serializers.ModelSerializer):
    google_ads_accounts = GoogleAdsAccountBriefSerializer(many=True, read_only=True)
    google_ads_account_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False,
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "role", "is_active", "date_joined", "last_login",
            "google_ads_accounts", "google_ads_account_ids",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]

    def update(self, instance, validated_data):
        account_ids = validated_data.pop("google_ads_account_ids", None)
        instance = super().update(instance, validated_data)
        if account_ids is not None:
            org = instance.organization
            accounts = GoogleAdsAccount.objects.filter(id__in=account_ids, organization=org)
            instance.google_ads_accounts.set(accounts)
        return instance


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    google_ads_account_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False,
    )

    class Meta:
        model = User
        fields = [
            "username", "email", "first_name", "last_name",
            "role", "password", "google_ads_account_ids",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        account_ids = validated_data.pop("google_ads_account_ids", [])
        validated_data.setdefault("role", "user")
        org = self.context["request"].user.organization
        user = User(**validated_data, organization=org)
        user.set_password(password)
        user.save()
        if account_ids:
            accounts = GoogleAdsAccount.objects.filter(id__in=account_ids, organization=org)
            user.google_ads_accounts.set(accounts)
        return user


class IsAdmin(IsAuthenticated):
    """Only allow admin users."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.user.role == "admin" or request.user.is_superuser


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateUserSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.all().order_by("-date_joined")
        if user.organization:
            return User.objects.filter(
                organization=user.organization
            ).order_by("-date_joined")
        return User.objects.none()

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise serializers.ValidationError("You cannot delete your own account.")
        instance.is_active = False
        instance.save(update_fields=["is_active"])
