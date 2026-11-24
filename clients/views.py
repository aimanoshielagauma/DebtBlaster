
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from debts.models import Debt
from .forms import ClientForm
from .models import Client


@login_required
def client_list(request):
    clients = Client.objects.filter(owner=request.user).prefetch_related("debts__payments")

    search = request.GET.get("q", "").strip()
    archived = request.GET.get("archived", "active")

    if search:
        clients = clients.filter(
            Q(full_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone__icontains=search)
        )

    if archived == "archived":
        clients = clients.filter(is_archived=True)
    elif archived == "all":
        pass
    else:
        clients = clients.filter(is_archived=False)

    for client in clients:
        totals = {}
        due_dates = []
        for debt in client.debts.all():
            if debt.owner_id != request.user.pk or debt.status == Debt.Status.CANCELLED:
                continue
            paid = sum(
                (payment.amount for payment in debt.payments.all() if payment.status == "confirmed"),
                Decimal("0.00"),
            )
            balance = max(Decimal("0.00"), debt.original_amount - paid)
            if balance > Decimal("0.00"):
                totals[debt.currency] = totals.get(debt.currency, Decimal("0.00")) + balance
                due_dates.append(debt.due_date)
        client.outstanding_by_currency = totals
        client.next_due_date = min(due_dates) if due_dates else None

    all_clients = Client.objects.filter(owner=request.user)
    all_debts = Debt.objects.filter(owner=request.user).exclude(status=Debt.Status.CANCELLED)
    outstanding_by_currency = {}
    for debt in all_debts:
        outstanding_by_currency[debt.currency] = outstanding_by_currency.get(debt.currency, Decimal("0.00")) + debt.outstanding_balance
    return render(
        request,
        "clients/client_list.html",
        {
            "clients": clients,
            "search": search,
            "archived": archived,
            "active_count": all_clients.filter(is_archived=False).count(),
            "open_count": all_debts.exclude(status=Debt.Status.PAID).count(),
            "overdue_count": all_debts.exclude(status=Debt.Status.PAID).filter(due_date__lt=timezone.localdate()).count(),
            "outstanding_by_currency": outstanding_by_currency,
        },
    )


@login_required
def client_create(request):
    if request.method == "POST":
        form = ClientForm(request.POST)

        if form.is_valid():
            client = form.save(commit=False)
            client.owner = request.user
            client.save()

            messages.success(request, "Client added successfully.")
            return redirect("client-detail", pk=client.pk)
    else:
        form = ClientForm()

    return render(
        request,
        "clients/client_form.html",
        {"form": form, "page_title": "Add client"},
    )


@login_required
def client_detail(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
        owner=request.user,
    )

    debts = Debt.objects.filter(
        client=client,
        owner=request.user,
    ).order_by("due_date", "id")

    outstanding_debts = debts.exclude(
        status=Debt.Status.CANCELLED
    )

    total_original = outstanding_debts.aggregate(
        total=Sum("original_amount")
    )["total"] or Decimal("0.00")

    total_outstanding = sum(
        (debt.outstanding_balance for debt in outstanding_debts),
        Decimal("0.00"),
    )

    return render(
        request,
        "clients/client_detail.html",
        {
            "client": client,
            "debts": debts,
            "total_original": total_original,
            "total_outstanding": total_outstanding,
        },
    )


@login_required
def client_edit(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)

        if form.is_valid():
            form.save()
            messages.success(request, "Client updated successfully.")
            return redirect("client-detail", pk=client.pk)
    else:
        form = ClientForm(instance=client)

    return render(
        request,
        "clients/client_form.html",
        {
            "form": form,
            "client": client,
            "page_title": "Edit client",
        },
    )


@login_required
@require_POST
def client_toggle_archive(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
        owner=request.user,
    )

    client.is_archived = not client.is_archived
    client.save(update_fields=["is_archived", "updated_at"])

    message = (
        "Client archived."
        if client.is_archived
        else "Client restored."
    )
    messages.success(request, message)

    return redirect("client-detail", pk=client.pk)
