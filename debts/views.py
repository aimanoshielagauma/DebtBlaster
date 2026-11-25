
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from clients.models import Client
from payments.models import Payment
from reminders.scheduling import sync_debt_schedule
from .forms import DebtForm
from .models import Debt
from django.utils.timezone import localdate

@login_required
def debt_list(request):
    debts = Debt.objects.filter(
        owner=request.user
    ).select_related("client")

    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    due = request.GET.get("due", "")

    if search:
        debts = debts.filter(
            Q(description__icontains=search)
            | Q(invoice_number__icontains=search)
            | Q(client__full_name__icontains=search)
            | Q(client__email__icontains=search)
        )

    valid_statuses = {
        choice[0] for choice in Debt.Status.choices
    }

    if status in valid_statuses:
        debts = debts.filter(status=status)

    today = timezone.localdate()

    if due == "overdue":
        debts = debts.filter(
            due_date__lt=today
        ).exclude(
            status__in=[
                Debt.Status.PAID,
                Debt.Status.CANCELLED,
            ]
        )

    elif due == "upcoming":
        debts = debts.filter(
            due_date__gte=today
        ).exclude(
            status=Debt.Status.CANCELLED
        )

    return render(
        request,
        "debts/debt_list.html",
        {
            "debts": debts,
            "search": search,
            "status": status,
            "due": due,
            "status_choices": Debt.Status.choices,
        },
    )


@login_required
def debt_create(request):
    initial = {}

    client_id = request.GET.get("client")

    if client_id and client_id.isdigit():
        client = Client.objects.filter(
            pk=int(client_id),
            owner=request.user,
            is_archived=False,
        ).first()

        if client:
            initial["client"] = client

    if request.method == "POST":
        form = DebtForm(
            request.POST,
            owner=request.user,
        )

        if form.is_valid():
            debt = form.save(commit=False)
            debt.owner = request.user

            if debt.client.owner_id != request.user.pk:
                form.add_error(
                    "client",
                    "Select one of your own clients.",
                )

            elif debt.client.is_archived:
                form.add_error(
                    "client",
                    "Archived clients cannot receive new debts.",
                )

            else:
                debt.save()
                sync_debt_schedule(debt)

                messages.success(
                    request,
                    "Debt added successfully.",
                )

                return redirect("debt-detail", pk=debt.pk)

    else:
        form = DebtForm(
            owner=request.user,
            initial=initial,
        )

    return render(
        request,
        "debts/debt_form.html",
        {
            "form": form,
            "page_title": "Add debt",
        },
    )


@login_required
def debt_detail(request, pk):
    debt = get_object_or_404(
        Debt.objects.select_related("client"),
        pk=pk,
        owner=request.user,
    )

    payments = Payment.objects.filter(
        debt=debt,
        owner=request.user,
    ).order_by("-payment_date", "-id")

    return render(
        request,
        "debts/debt_detail.html",
        {
            "debt": debt,
            "payments": payments,
        },
    )


@login_required
def debt_edit(request, pk):
    debt = get_object_or_404(
        Debt,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        form = DebtForm(
            request.POST,
            instance=debt,
            owner=request.user,
        )

        if form.is_valid():
            updated_debt = form.save(commit=False)
            updated_debt.owner = request.user

            if updated_debt.client.owner_id != request.user.pk:
                form.add_error(
                    "client",
                    "Select one of your own clients.",
                )

            elif updated_debt.client.is_archived:
                form.add_error(
                    "client",
                    "Restore the client before assigning a debt to them.",
                )

            else:
                updated_debt.save()

                # Recalculate payment status.
                # A cancelled debt must remain cancelled.
                if updated_debt.status != Debt.Status.CANCELLED:
                    total_paid = updated_debt.total_paid

                    if total_paid >= updated_debt.original_amount:
                        updated_debt.status = Debt.Status.PAID

                    elif total_paid > 0:
                        updated_debt.status = Debt.Status.PARTIAL

                    else:
                        updated_debt.status = Debt.Status.UNPAID

                    updated_debt.save(
                        update_fields=["status", "updated_at"]
                    )

                # Synchronize reminder scheduling after saving.
                sync_debt_schedule(updated_debt)

                messages.success(
                    request,
                    "Debt updated successfully.",
                )

                return redirect(
                    "debt-detail",
                    pk=updated_debt.pk,
                )

    else:
        form = DebtForm(
            instance=debt,
            owner=request.user,
        )

    return render(
        request,
        "debts/debt_form.html",
        {
            "form": form,
            "debt": debt,
            "page_title": "Edit debt",
        },
    )

@login_required
def debt_aging_report(request):
    today = timezone.localdate()

    buckets = [
        {"key": "not_overdue", "label": "Not overdue"},
        {"key": "days_1_30", "label": "1–30 days overdue"},
        {"key": "days_31_60", "label": "31–60 days overdue"},
        {"key": "days_61_90", "label": "61–90 days overdue"},
        {"key": "days_90_plus", "label": "90+ days overdue"},
    ]

    report = defaultdict(
        lambda: {
            bucket["key"]: Decimal("0.00")
            for bucket in buckets
        }
    )
    counts = defaultdict(
        lambda: {
            bucket["key"]: 0
            for bucket in buckets
        }
    )
    debt_rows = []

    debts = (
        Debt.objects
        .filter(owner=request.user)
        .exclude(
            status__in=[
                Debt.Status.PAID,
                Debt.Status.CANCELLED,
            ]
        )
        .select_related("client")
        .prefetch_related("payments")
        .order_by("due_date", "id")
    )

    for debt in debts:
        balance = Decimal(str(debt.outstanding_balance))

        # Ignore debts with no remaining balance, even if their status
        # has not yet been recalculated.
        if balance <= Decimal("0.00"):
            continue

        days_overdue = (today - debt.due_date).days

        if days_overdue <= 0:
            bucket_key = "not_overdue"
        elif days_overdue <= 30:
            bucket_key = "days_1_30"
        elif days_overdue <= 60:
            bucket_key = "days_31_60"
        elif days_overdue <= 90:
            bucket_key = "days_61_90"
        else:
            bucket_key = "days_90_plus"

        currency = debt.currency
        report[currency][bucket_key] += balance
        counts[currency][bucket_key] += 1

        debt_rows.append({
            "debt": debt,
            "balance": balance,
            "days_overdue": max(days_overdue, 0),
            "bucket_key": bucket_key,
        })

    currencies = sorted(set(report.keys()))

    currency_reports = []
    for currency in currencies:
        bucket_rows = []
        total = Decimal("0.00")

        for bucket in buckets:
            key = bucket["key"]
            amount = report[currency][key]
            total += amount

            bucket_rows.append({
                "key": key,
                "label": bucket["label"],
                "amount": amount,
                "count": counts[currency][key],
            })

        currency_reports.append({
            "currency": currency,
            "buckets": bucket_rows,
            "total": total,
        })

    return render(
        request,
        "debts/debt_aging_report.html",
        {
            "currency_reports": currency_reports,
            "debt_rows": debt_rows,
            "today": today,
            "has_debts": bool(debt_rows),
        },
    )
