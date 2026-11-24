
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from clients.models import Client
from payments.models import Payment
from .forms import DebtForm
from .models import Debt


@login_required
def debt_list(request):
    debts = Debt.objects.filter(owner=request.user).select_related("client")

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

    valid_statuses = {choice[0] for choice in Debt.Status.choices}
    if status in valid_statuses:
        debts = debts.filter(status=status)

    today = timezone.localdate()

    if due == "overdue":
        debts = debts.filter(
            due_date__lt=today,
        ).exclude(
            status__in=[Debt.Status.PAID, Debt.Status.CANCELLED]
        )
    elif due == "upcoming":
        debts = debts.filter(
            due_date__gte=today,
        ).exclude(status=Debt.Status.CANCELLED)

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
        form = DebtForm(request.POST, owner=request.user)

        if form.is_valid():
            debt = form.save(commit=False)
            debt.owner = request.user

            if debt.client.owner_id != request.user.pk:
                form.add_error("client", "Select one of your own clients.")
            elif debt.client.is_archived:
                form.add_error("client", "Archived clients cannot receive new debts.")
            else:
                debt.save()
                from reminders.scheduling import sync_debt_schedule
                sync_debt_schedule(debt)
                messages.success(request, "Debt added successfully.")
                return redirect("debt-detail", pk=debt.pk)
    else:
        form = DebtForm(owner=request.user, initial=initial)

    return render(
        request,
        "debts/debt_form.html",
        {"form": form, "page_title": "Add debt"},
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
                form.add_error("client", "Select one of your own clients.")
            elif updated_debt.client.is_archived:
                form.add_error(
                    "client",
                    "Restore the client before assigning a debt to them.",
                )
            else:
                updated_debt.save()
                from reminders.scheduling import sync_debt_schedule
                sync_debt_schedule(updated_debt)
                messages.success(request, "Debt updated successfully.")
                return redirect("debt-detail", pk=debt.pk)
    else:
        form = DebtForm(instance=debt, owner=request.user)

    return render(
        request,
        "debts/debt_form.html",
        {
            "form": form,
            "debt": debt,
            "page_title": "Edit debt",
        },
    )
