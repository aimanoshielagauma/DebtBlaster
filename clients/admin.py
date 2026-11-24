
from django.contrib import admin

from .models import Client
from .settings_models import BusinessSettings
from .audit_log import AuditLog


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "client_type",
        "owner",
        "is_archived",
    )

    search_fields = ("full_name", "email")
    list_filter = ("client_type", "is_archived")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if request.user.is_superuser:
            return queryset

        return queryset.filter(owner=request.user)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.owner = request.user

        super().save_model(request, obj, form, change)


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "business_name",
        "owner",
        "default_currency",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if request.user.is_superuser:
            return queryset

        return queryset.filter(owner=request.user)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.owner = request.user

        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "entity_type",
        "entity_id",
        "owner",
        "created_at",
    )

    readonly_fields = (
        "owner",
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "details",
        "created_at",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if request.user.is_superuser:
            return queryset

        return queryset.filter(owner=request.user)

    def has_add_permission(self, request):
        # Audit logs should be created by application services.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return (
            request.user.is_superuser
            and super().has_delete_permission(request, obj)
        )
