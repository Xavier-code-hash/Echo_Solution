import json
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render
from django.db.models import Sum, Count
from django.db.models.functions import ExtractMonth
from django.utils import timezone


@method_decorator(login_required, name="dispatch")
class OverviewView(View):
    def get(self, request):
        from apps.properties.models import Property, Unit
        from apps.tenants.models import Lease
        from apps.payments.models import Invoice, Payment
        from apps.maintenance.models import MaintenanceRequest

        u = request.user

        if not u.is_owner_or_above:
            leases   = Lease.objects.filter(tenant=u)
            lids     = leases.values_list("id", flat=True)
            invoices = Invoice.objects.filter(lease__in=lids)
            return render(request, "reports/overview.html", {
                "monthly_revenue": 0, "yearly_revenue": 0,
                "outstanding": invoices.filter(
                    status__in=["sent", "partial", "overdue"]
                ).aggregate(t=Sum("total_amount"))["t"] or 0,
                "total_invoices": invoices.count(),
                "paid_invoices":  invoices.filter(status="paid").count(),
                "collection_rate": 0,
                "gateway_breakdown": [], "max_gateway_total": 1,
                "invoice_status_breakdown": [],
                "recent_payments": [],
                "properties": [],
                "est_maintenance": 0, "actual_maintenance": 0,
                "monthly_chart_data": json.dumps([0] * 12),
            })

        today = timezone.now().date()
        props = Property.objects.filter(owner=u)
        pids  = props.values_list("id", flat=True)
        uids  = Unit.objects.filter(property__in=pids).values_list("id", flat=True)
        lids  = Lease.objects.filter(unit__in=uids).values_list("id", flat=True)

        invoices = Invoice.objects.filter(lease__in=lids)
        payments = Payment.objects.filter(invoice__lease__in=lids, status="completed")

        monthly_revenue = payments.filter(
            created_at__year=today.year, created_at__month=today.month
        ).aggregate(t=Sum("amount"))["t"] or 0

        yearly_revenue = payments.filter(
            created_at__year=today.year
        ).aggregate(t=Sum("amount"))["t"] or 0

        outstanding = invoices.filter(
            status__in=["sent", "partial", "overdue"]
        ).aggregate(t=Sum("total_amount"))["t"] or 0

        total_invoices  = invoices.count()
        paid_invoices   = invoices.filter(status="paid").count()
        collection_rate = round(paid_invoices / total_invoices * 100) if total_invoices else 0

        gateway_breakdown = list(
            payments.values("gateway").annotate(total=Sum("amount")).order_by("-total")
        )
        max_gateway_total = max((g["total"] for g in gateway_breakdown), default=1)

        invoice_status_breakdown = list(
            invoices.values("status").annotate(count=Count("id")).order_by("-count")
        )

        maint = MaintenanceRequest.objects.filter(unit__in=uids)
        est_maintenance    = maint.aggregate(t=Sum("estimated_cost"))["t"] or 0
        actual_maintenance = maint.aggregate(t=Sum("actual_cost"))["t"] or 0

        recent_payments = payments.select_related(
            "tenant", "invoice"
        ).order_by("-created_at")[:15]

        # Build 12-element list of monthly revenue totals for the bar chart
        monthly_data = [0.0] * 12
        monthly_qs = (
            payments
            .filter(created_at__year=today.year)
            .annotate(month=ExtractMonth("created_at"))
            .values("month")
            .annotate(t=Sum("amount"))
        )
        for row in monthly_qs:
            monthly_data[row["month"] - 1] = float(row["t"])

        return render(request, "reports/overview.html", {
            "monthly_revenue":  monthly_revenue,
            "yearly_revenue":   yearly_revenue,
            "outstanding":      outstanding,
            "total_invoices":   total_invoices,
            "paid_invoices":    paid_invoices,
            "collection_rate":  collection_rate,
            "gateway_breakdown":          gateway_breakdown,
            "max_gateway_total":          max_gateway_total,
            "invoice_status_breakdown":   invoice_status_breakdown,
            "est_maintenance":    est_maintenance,
            "actual_maintenance": actual_maintenance,
            "recent_payments":    recent_payments,
            "properties":         props.prefetch_related("units"),
            "monthly_chart_data": json.dumps(monthly_data),
        })