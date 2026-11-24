
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from .forms import PaymentForm
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
