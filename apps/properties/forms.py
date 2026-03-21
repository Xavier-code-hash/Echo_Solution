from django import forms
from apps.properties.models import Property, Unit
W = {"class": "form-control"}

class PropertyForm(forms.ModelForm):
    class Meta:
        model  = Property
        fields = ["name","type","status","address","city","county","country","description","cover_image","purchase_price","year_built"]
        widgets = {
            "name":           forms.TextInput(attrs={**W, "placeholder": "e.g. Westlands Heights"}),
            "type":           forms.Select(attrs=W),
            "status":         forms.Select(attrs=W),
            "address":        forms.TextInput(attrs={**W, "placeholder": "Street address"}),
            "city":           forms.TextInput(attrs={**W, "placeholder": "e.g. Nairobi"}),
            "county":         forms.TextInput(attrs={**W, "placeholder": "e.g. Nairobi County"}),
            "country":        forms.TextInput(attrs=W),
            "description":    forms.Textarea(attrs={**W, "rows": 3, "placeholder": "Brief description…"}),
            "cover_image":    forms.FileInput(attrs={"class": "form-control"}),
            "purchase_price": forms.NumberInput(attrs={**W, "placeholder": "0"}),
            "year_built":     forms.NumberInput(attrs={**W, "placeholder": "2020"}),
        }

class UnitForm(forms.ModelForm):
    class Meta:
        model  = Unit
        fields = ["unit_number","type","status","floor","bedrooms","bathrooms","area_sqft","monthly_rent","deposit"]
        widgets = {
            "unit_number":  forms.TextInput(attrs={**W, "placeholder": "e.g. A1, 101"}),
            "type":         forms.Select(attrs=W),
            "status":       forms.Select(attrs=W),
            "floor":        forms.NumberInput(attrs=W),
            "bedrooms":     forms.NumberInput(attrs=W),
            "bathrooms":    forms.NumberInput(attrs=W),
            "area_sqft":    forms.NumberInput(attrs=W),
            "monthly_rent": forms.NumberInput(attrs={**W, "placeholder": "0"}),
            "deposit":      forms.NumberInput(attrs={**W, "placeholder": "0"}),
        }
