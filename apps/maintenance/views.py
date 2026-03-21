from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from apps.maintenance.models import MaintenanceRequest


def _qs_for_user(user):
    if user.is_owner_or_above:
        from apps.properties.models import Property, Unit
        pids = Property.objects.filter(owner=user).values_list("id", flat=True)
        uids = Unit.objects.filter(property__in=pids).values_list("id", flat=True)
        return MaintenanceRequest.objects.filter(unit__in=uids)
    return MaintenanceRequest.objects.filter(submitted_by=user)


@method_decorator(login_required, name="dispatch")
class RequestListView(View):
    def get(self, request):
        qs = _qs_for_user(request.user).select_related("unit__property", "submitted_by")
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return render(request, "maintenance/list.html", {"requests": qs})


@method_decorator(login_required, name="dispatch")
class RequestDetailView(View):
    def get(self, request, pk):
        req = get_object_or_404(MaintenanceRequest, pk=pk)
        return render(request, "maintenance/detail.html", {"req": req})

    def post(self, request, pk):
        req = get_object_or_404(MaintenanceRequest, pk=pk)
        if not request.user.is_owner_or_above:
            messages.error(request, "Permission denied.")
            return redirect("maintenance:detail", pk=pk)
        new_status  = request.POST.get("status")
        resolution  = request.POST.get("resolution", "").strip()
        actual_cost = request.POST.get("actual_cost", "").strip()
        if new_status:
            req.status = new_status
            if new_status == "resolved" and not req.resolved_at:
                req.resolved_at = timezone.now()
        if resolution:
            req.resolution = resolution
        if actual_cost:
            try:
                req.actual_cost = float(actual_cost)
            except ValueError:
                pass
        req.save()
        from apps.messaging.services import notify_maintenance_update
        notify_maintenance_update(req)
        messages.success(request, f"Request updated — {req.get_status_display()}.")
        return redirect("maintenance:detail", pk=pk)


@method_decorator(login_required, name="dispatch")
class RequestCreateView(View):
    def get(self, request):
        from apps.maintenance.forms import MaintenanceForm
        return render(request, "maintenance/form.html", {"form": MaintenanceForm(user=request.user)})

    def post(self, request):
        from apps.maintenance.forms import MaintenanceForm
        form = MaintenanceForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            req = form.save(commit=False)
            req.submitted_by = request.user
            req.save()
            messages.success(request, "Maintenance request submitted successfully.")
            return redirect("maintenance:detail", pk=req.pk)
        return render(request, "maintenance/form.html", {"form": form})
