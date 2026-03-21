"""
apps/messaging/services.py

Notification and email delivery layer.
Sends via Django's email backend (Brevo SMTP in production).
"""
import logging
from django.conf import settings
from django.utils import timezone

log = logging.getLogger("apps.messaging")


def send_email(
    to: str,
    subject: str,
    body: str,
    html: str = None,
    user=None,
    attachment_bytes: bytes = None,
    attachment_name: str = None,
    attachment_mime: str = "application/octet-stream",
) -> bool:
    """
    Send an email, optionally with a single file attachment.
    Records a Notification row if a user is provided.
    """
    ok = _django_email(to, subject, body, html, attachment_bytes, attachment_name, attachment_mime)

    if user:
        from apps.messaging.models import Notification
        Notification.objects.create(
            user=user,
            channel=Notification.Channel.EMAIL,
            subject=subject,
            body=body,
            status=Notification.Status.SENT if ok else Notification.Status.FAILED,
            sent_at=timezone.now() if ok else None,
        )

    return ok


def _django_email(
    to: str,
    subject: str,
    body: str,
    html: str = None,
    attachment_bytes: bytes = None,
    attachment_name: str = None,
    attachment_mime: str = "application/octet-stream",
) -> bool:
    """Low-level Django email sender with optional binary attachment."""
    try:
        from django.core.mail import EmailMultiAlternatives

        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )

        if html:
            msg.attach_alternative(html, "text/html")

        if attachment_bytes and attachment_name:
            msg.attach(attachment_name, attachment_bytes, attachment_mime)

        msg.send(fail_silently=False)
        log.info("Email sent → %s", to)
        return True

    except Exception as e:
        log.error("Email error: %s", e)
        return False


def notify_in_app(user, subject: str, body: str) -> None:
    from apps.messaging.models import Notification
    Notification.objects.create(
        user=user,
        channel=Notification.Channel.IN_APP,
        subject=subject,
        body=body,
        status=Notification.Status.SENT,
        sent_at=timezone.now(),
    )


def notify_rent_due(lease) -> None:
    t    = lease.tenant
    subj = f"Rent Due — {lease.unit.property.name} Unit {lease.unit.unit_number}"
    body = (
        f"Hi {t.get_short_name()},\n\n"
        f"Your rent of KES {lease.monthly_rent:,.0f} is due on day {lease.rent_due_day}.\n\n"
        f"Pay at: {settings.SITE_URL}/payments/"
    )
    send_email(t.email, subj, body, user=t)
    notify_in_app(t, subj, body)


def notify_payment_received(payment) -> None:
    t    = payment.tenant
    subj = f"Payment Confirmed — {payment.invoice.invoice_number}"
    body = (
        f"Hi {t.get_short_name()},\n\n"
        f"We received KES {payment.amount:,.0f} via {payment.get_gateway_display()}.\n"
        f"Ref: {payment.id}"
    )
    send_email(t.email, subj, body, user=t)
    notify_in_app(t, subj, body)


def notify_maintenance_update(req) -> None:
    if not req.submitted_by:
        return
    u    = req.submitted_by
    subj = f"Maintenance Update — {req.title}"
    body = (
        f"Hi {u.get_short_name()},\n\n"
        f"Your request '{req.title}' is now: {req.get_status_display()}."
    )
    send_email(u.email, subj, body, user=u)
    notify_in_app(u, subj, body)