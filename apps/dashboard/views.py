from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render
from django.db.models import Sum
from django.utils import timezone


@method_decorator(login_required, name="dispatch")
class HomeView(View):
    def get(self, request):
        u   = request.user
        ctx = self._owner_ctx(u) if u.is_owner_or_above else self._tenant_ctx(u)
        return render(request, "dashboard/home.html", ctx)

    def _owner_ctx(self, u):
        from apps.properties.models import Property, Unit
        from apps.tenants.models import Lease
        from apps.payments.models import Invoice, Payment
        from apps.maintenance.models import MaintenanceRequest
        today  = timezone.now().date()
        props  = Property.objects.filter(owner=u)
        pids   = props.values_list("id", flat=True)
        units  = Unit.objects.filter(property__in=pids)
        uids   = units.values_list("id", flat=True)
        leases = Lease.objects.filter(unit__in=uids, status="active")
        lids   = leases.values_list("id", flat=True)
        income = Payment.objects.filter(
            invoice__lease__in=lids, status="completed",
            created_at__month=today.month, created_at__year=today.year,
        ).aggregate(t=Sum("amount"))["t"] or 0
        upcoming_invoices = Invoice.objects.filter(
            lease__in=lids,
            due_date__gte=today,
            due_date__lte=today + timezone.timedelta(days=7),
        ).exclude(status__in=["paid", "void"]).select_related("lease__tenant", "lease__unit__property").order_by("due_date")

        rent_reminders = [{
            "invoice": inv,
            "days": (inv.due_date - today).days,
        } for inv in upcoming_invoices]

        return {
            "is_owner": True,
            "total_props":     props.count(),
            "total_units":     units.count(),
            "occupied_units":  units.filter(status="occupied").count(),
            "active_leases":   leases.count(),
            "overdue_count":   Invoice.objects.filter(lease__in=lids, status="overdue").count(),
            "open_maintenance":MaintenanceRequest.objects.filter(
                unit__in=uids, status__in=["open","assigned","in_progress"]).count(),
            "monthly_income":  income,
            "rent_reminders":  rent_reminders,
            "expiring_leases": leases.filter(
                end_date__lte=today + timezone.timedelta(days=60)
            ).select_related("tenant","unit__property").order_by("end_date")[:6],
            "recent_maintenance": MaintenanceRequest.objects.filter(
                unit__in=uids, status__in=["open","assigned","in_progress"]
            ).select_related("unit__property","submitted_by").order_by("-created_at")[:6],
            "overdue_invoices": Invoice.objects.filter(
                lease__in=lids, status="overdue"
            ).select_related("lease__tenant").order_by("-due_date")[:5],
            "properties": props.prefetch_related("units")[:6],
        }

    def _tenant_ctx(self, u):
        from apps.tenants.models import Lease
        from apps.payments.models import Invoice
        from apps.maintenance.models import MaintenanceRequest
        leases = Lease.objects.filter(tenant=u, status="active").select_related("unit__property")
        lids   = leases.values_list("id", flat=True)
        return {
            "is_owner":       False,
            "my_leases":      leases,
            "my_invoices":    Invoice.objects.filter(lease__in=lids).order_by("-invoice_date")[:5],
            "my_maintenance": MaintenanceRequest.objects.filter(
                submitted_by=u).order_by("-created_at")[:5],
        }
