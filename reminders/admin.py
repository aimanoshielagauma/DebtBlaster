from django.contrib import admin

from .models import ReminderSchedule, ReminderLog, ReminderEvent


@admin.register(ReminderSchedule)
class ReminderScheduleAdmin(admin.ModelAdmin):
    list_display = ("debt", "owner", "enabled", "frequency", "next_reminder_at", "stopped_at")
    list_filter = ("enabled", "frequency")

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("debt")
        return qs if request.user.is_superuser else qs.filter(owner=request.user)


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ("debt", "recipient_email", "scheduled_for", "status", "attempted_at")
    list_filter = ("status",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(schedule__owner=request.user)


@admin.register(ReminderEvent)
class ReminderEventAdmin(admin.ModelAdmin):
    list_display = ("debt", "event_type", "recipient_email", "scheduled_for", "status", "attempt_count")
    list_filter = ("status", "event_type")
    readonly_fields = (
        "schedule", "debt", "event_key", "event_type", "recipient_email",
        "scheduled_for", "next_attempt_at", "attempt_count", "status",
        "claimed_at", "claim_token", "sent_at", "last_error", "created_at", "updated_at",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(schedule__owner=request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)
