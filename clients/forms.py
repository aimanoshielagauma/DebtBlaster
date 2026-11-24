
from django import forms

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "client_type",
            "full_name",
            "email",
            "phone",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()

        if not full_name:
            raise forms.ValidationError("Enter the client's name.")

        return full_name

    def clean_email(self):
        return self.cleaned_data["email"].strip()
