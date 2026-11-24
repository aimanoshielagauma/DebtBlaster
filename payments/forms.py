
from django import forms
from django.core.exceptions import ValidationError

from debts.models import Debt
from .models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = (
            "debt",
            "amount",
            "payment_date",
            "method",
            "reference",
            "notes",
        )
        widgets = {
            "payment_date": forms.DateInput(
                attrs={"type": "date"}
            ),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

        if owner is not None:
            self.fields["debt"].queryset = Debt.objects.filter(
                owner=owner,
            ).exclude(status__in=[Debt.Status.CANCELLED, Debt.Status.PAID])

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise ValidationError(
                "Payment amount must be greater than zero."
            )

        return amount

    def clean_reference(self):
        return (self.cleaned_data.get("reference") or "").strip()
