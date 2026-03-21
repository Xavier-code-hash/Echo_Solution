from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from apps.tenants.models import Lease, TenantProfile
from apps.authentication.models import User
from apps.properties.models import Property, Unit


def _owner_unit_ids(user):
    pids = Property.objects.filter(owner=user).values_list("id", flat=True)
    return Unit.objects.filter(property__in=pids).values_list("id", flat=True)


@method_decorator(login_required, name="dispatch")
class TenantListView(View):
    def get(self, request):
        uids   = _owner_unit_ids(request.user)
        leases = Lease.objects.filter(unit__in=uids, status="active").select_related("tenant", "unit__property").order_by("tenant__first_name")
        return render(request, "tenants/list.html", {"leases": leases})


@method_decorator(login_required, name="dispatch")
class TenantDetailView(View):
    def get(self, request, pk):
        tenant = get_object_or_404(User, pk=pk)
        leases = Lease.objects.filter(tenant=tenant).select_related("unit__property").order_by("-start_date")
        from apps.payments.models import Invoice, Payment
        from apps.maintenance.models import MaintenanceRequest
        lids = leases.values_list("id", flat=True)
        invoices = Invoice.objects.filter(lease__in=lids).order_by("-invoice_date")[:10]
        maintenance = MaintenanceRequest.objects.filter(submitted_by=tenant).order_by("-created_at")[:8]
        return render(request, "tenants/detail.html", {
            "tenant": tenant, "leases": leases,
            "invoices": invoices, "maintenance": maintenance,
        })


@method_decorator(login_required, name="dispatch")
class TenantCreateView(View):
    def get(self, request):
        from apps.tenants.forms import LeaseForm
        uids = _owner_unit_ids(request.user)
        return render(request, "tenants/create.html", {
            "form": LeaseForm(owner=request.user),
        })

    def post(self, request):
        from apps.tenants.forms import LeaseForm
        form = LeaseForm(request.POST, owner=request.user)
        if form.is_valid():
            # Create or get user account for tenant
            email = form.cleaned_data["email"].lower()
            first = form.cleaned_data["first_name"]
            last  = form.cleaned_data["last_name"]
            phone = form.cleaned_data.get("phone", "")
            tenant, created = User.objects.get_or_create(email=email, defaults={
                "first_name": first, "last_name": last, "phone": phone, "role": "tenant",
            })
            if created:
                import secrets
                tenant.set_password(secrets.token_urlsafe(16))
                tenant.save()
            # Create the lease
            unit = form.cleaned_data["unit"]
            lease = Lease.objects.create(
                unit=unit, tenant=tenant,
                start_date=form.cleaned_data["start_date"],
                end_date=form.cleaned_data["end_date"],
                monthly_rent=form.cleaned_data["monthly_rent"],
                deposit=form.cleaned_data["deposit"],
                rent_due_day=form.cleaned_data.get("rent_due_day", 1),
                late_fee=form.cleaned_data.get("late_fee", 0),
                status="active",
            )
            unit.status = "occupied"
            unit.save(update_fields=["status"])
            messages.success(request, f"Tenant {tenant.get_full_name()} added and lease created.")
            return redirect("tenants:detail", pk=tenant.pk)
        return render(request, "tenants/create.html", {"form": form})


@method_decorator(login_required, name="dispatch")
class LeaseListView(View):
    def get(self, request):
        uids   = _owner_unit_ids(request.user)
        status = request.GET.get("status", "")
        qs     = Lease.objects.filter(unit__in=uids).select_related("tenant", "unit__property").order_by("-start_date")
        if status:
            qs = qs.filter(status=status)
        return render(request, "tenants/leases.html", {"leases": qs, "filter_status": status})


@method_decorator(login_required, name="dispatch")
class LeaseDetailView(View):
    def get(self, request, pk):
        uids  = _owner_unit_ids(request.user)
        lease = get_object_or_404(Lease, pk=pk, unit__in=uids)
        return render(request, "tenants/lease_detail.html", {"lease": lease})

    def post(self, request, pk):
        uids   = _owner_unit_ids(request.user)
        lease  = get_object_or_404(Lease, pk=pk, unit__in=uids)
        action = request.POST.get("action")
        if action == "terminate":
            lease.status = "terminated"
            lease.unit.status = "available"
            lease.unit.save(update_fields=["status"])
            lease.save(update_fields=["status", "updated_at"])
            messages.success(request, "Lease terminated.")
        elif action == "renew":
            from datetime import timedelta
            lease.end_date = lease.end_date.replace(year=lease.end_date.year + 1)
            lease.status = "active"
            lease.save(update_fields=["end_date", "status", "updated_at"])
            messages.success(request, "Lease renewed for 1 year.")
        return redirect("tenants:lease-detail", pk=pk)
