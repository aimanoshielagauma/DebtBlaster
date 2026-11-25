
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from clients.models import Client
from .models import Debt


class DebtForm(forms.ModelForm):
    class Meta:
        model = Debt
        fields = [
            "client",
            "description",
            "invoice_number",
            "original_amount",
            "currency",
            "due_date",
            "reminder_enabled",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "original_amount": forms.NumberInput(
                attrs={"min": "0.01", "step": "0.01"}
            ),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

        self.fields["client"].queryset = Client.objects.none()

        if owner is not None:
            self.fields["client"].queryset = Client.objects.filter(
                owner=owner,
                is_archived=False,
            )

    def clean_description(self):
        description = self.cleaned_data["description"].strip()

        if not description:
            raise ValidationError("Enter a debt description.")

        return description

    def clean_invoice_number(self):
        return (self.cleaned_data.get("invoice_number") or "").strip()

    def clean_original_amount(self):
        amount = self.cleaned_data["original_amount"]

        if amount <= Decimal("0.00"):
            raise ValidationError(
                "The debt amount must be greater than zero."
            )

        if self.instance.pk and amount < self.instance.total_paid:
            raise ValidationError(
                "The original amount cannot be less than the confirmed "
                "payments already recorded."
            )

        return amount

    def clean_currency(self):
        currency = self.cleaned_data["currency"].strip().upper()

        if self.instance.pk:
            old_currency = self.instance.currency.upper()

            if (
                currency != old_currency
                and self.instance.payments.exists()
            ):
                raise ValidationError(
                    "You cannot change the currency after payments have "
                    "been recorded. Create a separate debt in the new currency."
                )

        return currency
