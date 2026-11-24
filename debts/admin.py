from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import Debt


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = (
        "description", "client", "original_amount", "total_paid",
        "outstanding_balance", "currency", "due_date", "status", "owner",
    )
    list_filter = ("status", "currency", "due_date")
    search_fields = ("description", "client__full_name", "invoice_number")
    readonly_fields = ("total_paid", "outstanding_balance")
    fieldsets = (
        ("Debt Details", {"fields": (
            "owner", "client", "description", "invoice_number",
            "original_amount", "currency", "due_date", "status", "reminder_enabled",
        )}),
        ("Payment Summary (Calculated Automatically)", {"fields": (
            "total_paid", "outstanding_balance",
        )}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(owner=request.user)

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if not request.user.is_superuser:
            fields.append("owner")
        return fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "client" and not request.user.is_superuser:
            kwargs["queryset"] = db_field.related_model.objects.filter(
                owner=request.user, is_archived=False
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.owner = request.user
        if obj.client.owner_id != obj.owner_id:
            raise ValidationError("The selected client must belong to the debt owner.")
        if obj.client.is_archived:
            raise ValidationError("Restore the client before assigning a debt.")
        if obj.original_amount < obj.total_paid:
            raise ValidationError("Original amount cannot be less than confirmed payments.")
        super().save_model(request, obj, form, change)
