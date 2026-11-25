
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from debts.models import Debt
from .forms import ClientForm
from .models import Client


@login_required
def client_list(request):
    clients = Client.objects.filter(owner=request.user)

    search_query = request.GET.get("q", "").strip()
    archive_filter = request.GET.get("archive", "active")

    if search_query:
        clients = clients.filter(
            Q(full_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
        )

    if archive_filter == "archived":
        clients = clients.filter(is_archived=True)
    elif archive_filter == "all":
        pass
    else:
        clients = clients.filter(is_archived=False)

    return render(
        request,
        "clients/client_list.html",
        {
            "clients": clients,
            "search_query": search_query,
            "archive_filter": archive_filter,
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
        {
            "form": form,
            "client": None,
        },
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
    ).exclude(
        status=Debt.Status.CANCELLED
    ).order_by("-created_at")

    original_by_currency = {}
    outstanding_by_currency = {}

    for debt in debts:
        currency = debt.currency.upper()

        original_by_currency[currency] = (
            original_by_currency.get(currency, Decimal("0.00"))
            + debt.original_amount
        )

        outstanding_by_currency[currency] = (
            outstanding_by_currency.get(currency, Decimal("0.00"))
            + debt.outstanding_balance
        )

    return render(
        request,
        "clients/client_detail.html",
        {
            "client": client,
            "debts": debts,
            "original_by_currency": original_by_currency,
            "outstanding_by_currency": outstanding_by_currency,
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

    if client.is_archived:
        messages.success(request, "Client archived successfully.")
    else:
        messages.success(request, "Client restored successfully.")

    return redirect("client-list")
