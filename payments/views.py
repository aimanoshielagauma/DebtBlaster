from collections import defaultdict
from decimal import Decimal

from clients.models import Client
from debts.models import Debt
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import PaymentForm
from .models import Payment
from .services import record_payment


@login_required
def create_payment(request):
    if request.method == "POST":
        form = PaymentForm(request.POST, owner=request.user)

        if form.is_valid():
            data = form.cleaned_data

            try:
                record_payment(
                    debt_id=data["debt"].pk,
                    owner=request.user,
                    recorded_by=request.user,
                    amount=data["amount"],
                    payment_date=data["payment_date"],
                    method=data["method"],
                    reference=data["reference"],
                    notes=data["notes"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    "Payment recorded successfully.",
                )
                return redirect("debt-detail", pk=data["debt"].pk)
    else:
        form = PaymentForm(owner=request.user)

    return render(
        request,
        "payments/create_payment.html",
        {"form": form},
    )


@login_required
def monthly_collections(request):
    current_month = timezone.localdate().replace(day=1)
    month_value = request.GET.get(
        "month",
        current_month.strftime("%Y-%m"),
    )

    try:
        selected_month = datetime.strptime(
            month_value,
            "%Y-%m",
        ).date().replace(day=1)
    except (ValueError, TypeError):
        selected_month = current_month
        month_value = current_month.strftime("%Y-%m")
        messages.warning(
            request,
            "Invalid month selected. Showing the current month instead.",
        )

    payments = Payment.objects.filter(
        owner=request.user,
        status=Payment.Status.CONFIRMED,
        payment_date__year=selected_month.year,
        payment_date__month=selected_month.month,
    ).select_related(
        "debt",
        "debt__client",
    ).order_by(
        "-payment_date",
        "-id",
    )

    currency_totals = payments.values(
        "debt__currency",
    ).annotate(
        total=Sum("amount"),
        payment_count=Count("id"),
    ).order_by(
        "debt__currency",
    )

    return render(
        request,
        "payments/monthly_collections.html",
        {
            "payments": payments,
            "currency_totals": currency_totals,
            "selected_month": selected_month,
            "month_value": month_value,
        },
    )

@login_required
def client_payment_behaviour(request):
    clients = Client.objects.filter(
        owner=request.user,
    ).order_by("full_name")

    debts = Debt.objects.filter(
        owner=request.user,
    ).exclude(
        status=Debt.Status.CANCELLED,
    ).select_related(
        "client",
    ).prefetch_related(
        "payments",
    ).order_by(
        "client__full_name",
        "currency",
    )

    report = {}

    for debt in debts:
        currency = debt.currency.upper()
        key = (debt.client_id, currency)

        if key not in report:
            report[key] = {
                "client": debt.client,
                "currency": currency,
                "total_original": Decimal("0.00"),
                "total_paid": Decimal("0.00"),
                "total_outstanding": Decimal("0.00"),
                "unpaid_debts": 0,
                "partial_debts": 0,
                "paid_debts": 0,
                "payments_on_or_before_due": 0,
                "payments_after_due": 0,
                "confirmed_payment_count": 0,
            }

        row = report[key]
        row["total_original"] += debt.original_amount
        row["total_outstanding"] += debt.outstanding_balance

        if debt.status == Debt.Status.PAID:
            row["paid_debts"] += 1
        elif debt.status == Debt.Status.PARTIAL:
            row["partial_debts"] += 1
        elif debt.status == Debt.Status.UNPAID:
            row["unpaid_debts"] += 1

        for payment in debt.payments.all():
            if (
                payment.owner_id != request.user.pk
                or payment.status != Payment.Status.CONFIRMED
            ):
                continue

            row["total_paid"] += payment.amount
            row["confirmed_payment_count"] += 1

            if debt.due_date:
                if payment.payment_date <= debt.due_date:
                    row["payments_on_or_before_due"] += 1
                else:
                    row["payments_after_due"] += 1

    report_rows = sorted(
        report.values(),
        key=lambda row: (
            row["client"].full_name.lower(),
            row["currency"],
        ),
    )

    return render(
        request,
        "payments/client_payment_behaviour.html",
        {
            "report_rows": report_rows,
            "client_count": clients.count(),
        },
    )