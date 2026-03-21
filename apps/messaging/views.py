from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages as django_msgs
from django.utils import timezone
from apps.messaging.models import Message
from apps.authentication.models import User


@method_decorator(login_required, name="dispatch")
class InboxView(View):
    def get(self, request):
        msgs = Message.objects.filter(recipient=request.user).select_related("sender").order_by("-created_at")
        return render(request, "messaging/inbox.html", {"messages_list": msgs})


@method_decorator(login_required, name="dispatch")
class MessageDetailView(View):
    def get(self, request, pk):
        message = get_object_or_404(Message, pk=pk, recipient=request.user)
        if not message.is_read:
            message.is_read = True
            message.read_at = timezone.now()
            message.save(update_fields=["is_read", "read_at"])
        return render(request, "messaging/message_detail.html", {"message": message})


@method_decorator(login_required, name="dispatch")
class ComposeView(View):
    def get(self, request):
        to_id = request.GET.get("to")
        recipient = None
        if to_id:
            try:
                recipient = User.objects.get(pk=to_id)
            except Exception:
                pass
        if request.user.is_owner_or_above:
            from apps.properties.models import Property, Unit
            from apps.tenants.models import Lease
            pids = Property.objects.filter(owner=request.user).values_list("id", flat=True)
            uids = Unit.objects.filter(property__in=pids).values_list("id", flat=True)
            tids = Lease.objects.filter(unit__in=uids, status="active").values_list("tenant", flat=True)
            recipients = User.objects.filter(id__in=tids).order_by("first_name")
        else:
            from apps.tenants.models import Lease
            leases = Lease.objects.filter(tenant=request.user, status="active").select_related("unit__property__owner")
            owner_ids = [l.unit.property.owner_id for l in leases]
            recipients = User.objects.filter(id__in=owner_ids)
        return render(request, "messaging/compose.html", {
            "to_id": to_id, "recipient": recipient, "recipients": recipients,
        })

    def post(self, request):
        to_id = request.POST.get("to")
        subj  = request.POST.get("subject", "").strip()
        body  = request.POST.get("body", "").strip()
        if not subj or not body:
            django_msgs.error(request, "Subject and message body are required.")
            return redirect("messaging:compose")
        try:
            recipient = User.objects.get(pk=to_id)
            Message.objects.create(sender=request.user, recipient=recipient, subject=subj, body=body)
            django_msgs.success(request, f"Message sent to {recipient.get_full_name()}.")
        except Exception:
            django_msgs.error(request, "Could not send message. Recipient not found.")
        return redirect("messaging:inbox")
