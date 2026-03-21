from django import forms
from apps.properties.models import Unit
W = {"class": "form-control"}

class LeaseForm(forms.Form):
    first_name  = forms.CharField(max_length=150, widget=forms.TextInput(attrs=W))
    last_name   = forms.CharField(max_length=150, widget=forms.TextInput(attrs=W))
    email       = forms.EmailField(widget=forms.EmailInput(attrs=W))
    phone       = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs=W))
    unit        = forms.ModelChoiceField(queryset=Unit.objects.none(), widget=forms.Select(attrs=W))
    start_date  = forms.DateField(widget=forms.DateInput(attrs={**W, "type": "date"}))
    end_date    = forms.DateField(widget=forms.DateInput(attrs={**W, "type": "date"}))
    monthly_rent= forms.DecimalField(max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs=W))
    deposit     = forms.DecimalField(max_digits=10, decimal_places=2, initial=0, widget=forms.NumberInput(attrs=W))
    rent_due_day= forms.IntegerField(min_value=1, max_value=28, initial=1, widget=forms.NumberInput(attrs=W))
    late_fee    = forms.DecimalField(max_digits=8, decimal_places=2, initial=0, widget=forms.NumberInput(attrs=W))

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner:
            from apps.properties.models import Property
            pids = Property.objects.filter(owner=owner).values_list("id", flat=True)
            self.fields["unit"].queryset = Unit.objects.filter(
                property__in=pids, status="available"
            ).select_related("property")
            self.fields["unit"].label_from_instance = lambda u: f"{u.property.name} — Unit #{u.unit_number} (KES {u.monthly_rent:,.0f}/mo)"

    def clean(self):
        cd = super().clean()
        s, e = cd.get("start_date"), cd.get("end_date")
        if s and e and e <= s:
            self.add_error("end_date", "End date must be after start date.")
        return cd
