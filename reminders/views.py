
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from reminders.models import ReminderEvent


@login_required
def reminder_history(request):
    events = (
        ReminderEvent.objects
        .filter(debt__owner=request.user)
        .select_related("debt", "debt__client", "schedule")
        .order_by("-created_at", "-id")
    )

    status = request.GET.get("status", "").strip()
    valid_statuses = {
        value for value, label in ReminderEvent.Status.choices
    }

    if status in valid_statuses:
        events = events.filter(status=status)
    else:
        status = ""

    context = {
        "events": events,
        "selected_status": status,
        "status_choices": ReminderEvent.Status.choices,
    }

    return render(request, "reminders/history.html", context)
