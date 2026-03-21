from django import forms
from apps.maintenance.models import MaintenanceRequest
W = {"class": "form-control"}

class MaintenanceForm(forms.ModelForm):
    class Meta:
        model  = MaintenanceRequest
        fields = ["unit","title","category","priority","description","image"]
        widgets = {
            "unit":        forms.Select(attrs=W),
            "title":       forms.TextInput(attrs={**W, "placeholder": "Brief description of the issue"}),
            "category":    forms.Select(attrs=W),
            "priority":    forms.Select(attrs=W),
            "description": forms.Textarea(attrs={**W, "rows":5, "placeholder": "Describe the issue in detail…"}),
            "image":       forms.FileInput(attrs={"class":"form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from apps.properties.models import Unit
            if user.is_owner_or_above:
                from apps.properties.models import Property
                pids = Property.objects.filter(owner=user).values_list("id", flat=True)
                qs   = Unit.objects.filter(property__in=pids).select_related("property")
            else:
                from apps.tenants.models import Lease
                uids = Lease.objects.filter(tenant=user, status="active").values_list("unit", flat=True)
                qs   = Unit.objects.filter(id__in=uids).select_related("property")
            self.fields["unit"].queryset = qs
            self.fields["unit"].label_from_instance = lambda u: f"{u.property.name} — Unit #{u.unit_number}"
