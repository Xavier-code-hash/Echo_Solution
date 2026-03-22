from django import forms
from apps.payments.models import Invoice
from apps.tenants.models import Lease
W = {"class": "form-control"}

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["lease","rent_amount","late_fee","other_charges","discount","invoice_date","due_date","notes"]
        widgets = {
            "lease":         forms.Select(attrs=W),
            "rent_amount":   forms.NumberInput(attrs=W),
            "late_fee":      forms.NumberInput(attrs=W),
            "other_charges": forms.NumberInput(attrs=W),
            "discount":      forms.NumberInput(attrs=W),
            "invoice_date":  forms.DateInput(attrs={**W, "type": "date"}),
            "due_date":      forms.DateInput(attrs={**W, "type": "date"}),
            "notes":         forms.Textarea(attrs={**W, "rows": 3}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner:
            from apps.properties.models import Property, Unit
            pids = Property.objects.filter(owner=owner).values_list("id", flat=True)
            uids = Unit.objects.filter(property__in=pids).values_list("id", flat=True)
            self.fields["lease"].queryset = Lease.objects.filter(
                unit__in=uids, status="active"
            ).select_related("tenant", "unit__property")
            self.fields["lease"].label_from_instance = lambda l: f"{l.tenant.get_full_name()} — {l.unit.property.name} #{ l.unit.unit_number}"