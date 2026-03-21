from django import forms
from django.core.exceptions import ValidationError
from apps.landing.models import CallbackRequest
from apps.payments.utils import normalize_msisdn


SUBJECT_CHOICES = [
    ("Sales Enquiry", "Sales Enquiry"),
    ("Technical Support", "Technical Support"),
    ("Billing", "Billing"),
    ("Partnership", "Partnership"),
    ("Other", "Other"),
]


class CallbackRequestForm(forms.ModelForm):
    class Meta:
        model = CallbackRequest
        fields = ["full_name", "phone", "email", "preferred_time", "message"]

    def clean_phone(self):
        phone = normalize_msisdn(self.cleaned_data.get("phone", ""))
        if not phone:
            raise ValidationError("Enter a valid phone number.")
        return phone


class ContactMessageForm(forms.Form):
    first_name = forms.CharField(max_length=50)
    last_name  = forms.CharField(max_length=50)
    email      = forms.EmailField()
    subject    = forms.ChoiceField(choices=SUBJECT_CHOICES)
    message    = forms.CharField(max_length=2000)
