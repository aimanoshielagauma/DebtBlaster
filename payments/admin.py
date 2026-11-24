
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Payment
from .services import record_payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "debt",
        "amount",
        "payment_date",
        "method",
        "status",
        "owner",
    )

    list_filter = ("status", "method", "payment_date")
    search_fields = (
        "debt__description",
        "debt__client__full_name",
        "reference",
    )

    readonly_fields = (
        "owner",
        "debt",
        "amount",
        "payment_date",
        "method",
        "reference",
        "notes",
        "status",
        "recorded_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if request.user.is_superuser:
            return queryset

        return queryset.filter(owner=request.user)

    actions = None
