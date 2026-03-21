from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import ProtectedError
from apps.properties.models import Property, Unit
from apps.properties.forms import PropertyForm, UnitForm


@method_decorator(login_required, name="dispatch")
class PropertyListView(View):
    def get(self, request):
        props = Property.objects.filter(owner=request.user).prefetch_related("units")
        return render(request, "properties/list.html", {"properties": props})


@method_decorator(login_required, name="dispatch")
class PropertyCreateView(View):
    def get(self, request):
        return render(request, "properties/form.html", {"form": PropertyForm(), "title": "Add Property"})

    def post(self, request):
        form = PropertyForm(request.POST, request.FILES)
        if form.is_valid():
            prop = form.save(commit=False)
            prop.owner = request.user
            prop.save()
            messages.success(request, f"Property '{prop.name}' created successfully.")
            return redirect("properties:detail", pk=prop.pk)
        return render(request, "properties/form.html", {"form": form, "title": "Add Property"})


@method_decorator(login_required, name="dispatch")
class PropertyDetailView(View):
    def get(self, request, pk):
        prop  = get_object_or_404(Property, pk=pk, owner=request.user)
        units = prop.units.all().order_by("floor", "unit_number")
        unit_form = UnitForm()
        return render(request, "properties/detail.html", {
            "property": prop, "units": units, "unit_form": unit_form
        })


@method_decorator(login_required, name="dispatch")
class PropertyEditView(View):
    def get(self, request, pk):
        prop = get_object_or_404(Property, pk=pk, owner=request.user)
        return render(request, "properties/form.html", {
            "form": PropertyForm(instance=prop), "title": "Edit Property", "property": prop
        })

    def post(self, request, pk):
        prop = get_object_or_404(Property, pk=pk, owner=request.user)
        form = PropertyForm(request.POST, request.FILES, instance=prop)
        if form.is_valid():
            form.save()
            messages.success(request, "Property updated.")
            return redirect("properties:detail", pk=prop.pk)
        return render(request, "properties/form.html", {"form": form, "title": "Edit Property"})


@method_decorator(login_required, name="dispatch")
class PropertyDeleteView(View):
    def post(self, request, pk):
        prop = get_object_or_404(Property, pk=pk, owner=request.user)
        name = prop.name
        try:
            prop.delete()
            messages.success(request, f"Property '{name}' deleted.")
        except ProtectedError as e:
            blocking = ", ".join(str(obj) for obj in e.protected_objects)
            messages.error(
                request,
                f"Cannot delete '{name}' — it still has protected records: {blocking}. "
                "Remove them first."
            )
        return redirect("properties:list")


@method_decorator(login_required, name="dispatch")
class UnitCreateView(View):
    def post(self, request, prop_pk):
        prop = get_object_or_404(Property, pk=prop_pk, owner=request.user)
        form = UnitForm(request.POST)
        if form.is_valid():
            unit = form.save(commit=False)
            unit.property = prop
            unit.save()
            messages.success(request, f"Unit {unit.unit_number} added.")
        else:
            for field, errs in form.errors.items():
                messages.error(request, f"{field}: {errs[0]}")
        return redirect("properties:detail", pk=prop.pk)


@method_decorator(login_required, name="dispatch")
class UnitEditView(View):
    def get(self, request, prop_pk, unit_pk):
        prop = get_object_or_404(Property, pk=prop_pk, owner=request.user)
        unit = get_object_or_404(Unit, pk=unit_pk, property=prop)
        return render(request, "properties/unit_form.html", {
            "form": UnitForm(instance=unit), "property": prop, "unit": unit
        })

    def post(self, request, prop_pk, unit_pk):
        prop = get_object_or_404(Property, pk=prop_pk, owner=request.user)
        unit = get_object_or_404(Unit, pk=unit_pk, property=prop)
        form = UnitForm(request.POST, instance=unit)
        if form.is_valid():
            form.save()
            messages.success(request, f"Unit {unit.unit_number} updated.")
            return redirect("properties:detail", pk=prop.pk)
        return render(request, "properties/unit_form.html", {
            "form": form, "property": prop, "unit": unit
        })


@method_decorator(login_required, name="dispatch")
class UnitDeleteView(View):
    def post(self, request, prop_pk, unit_pk):
        prop = get_object_or_404(Property, pk=prop_pk, owner=request.user)
        unit = get_object_or_404(Unit, pk=unit_pk, property=prop)
        num  = unit.unit_number
        try:
            unit.delete()
            messages.success(request, f"Unit {num} deleted.")
        except ProtectedError as e:
            blocking = ", ".join(str(obj) for obj in e.protected_objects)
            messages.error(
                request,
                f"Cannot delete Unit {num} — it has active lease(s): {blocking}. "
                "Terminate or reassign the lease(s) first."
            )
        return redirect("properties:detail", pk=prop.pk)