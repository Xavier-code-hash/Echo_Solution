from django.utils import timezone

def global_context(request):
    ctx = {"year": timezone.now().year, "site_name": "Echo_Solutions"}
    if not request.user.is_authenticated:
        return ctx
    from apps.messaging.models import Message, Notification
    ctx["unread_msgs"]   = Message.objects.filter(recipient=request.user, is_read=False).count()
    ctx["unread_notifs"] = Notification.objects.filter(
        user=request.user, channel="in_app", status="sent").count()
    return ctx
