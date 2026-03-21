import uuid
from django.db import models
from django.conf import settings


class Message(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="sent_messages")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inbox")
    subject   = models.CharField(max_length=255)
    body      = models.TextField()
    is_read   = models.BooleanField(default=False)
    read_at   = models.DateTimeField(null=True, blank=True)
    parent    = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject


class Notification(models.Model):
    class Channel(models.TextChoices):
        EMAIL  = "email",  "Email"
        SMS    = "sms",    "SMS"
        IN_APP = "in_app", "In-App"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT    = "sent",    "Sent"
        FAILED  = "failed",  "Failed"

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    channel    = models.CharField(max_length=10, choices=Channel.choices)
    subject    = models.CharField(max_length=255, blank=True)
    body       = models.TextField()
    status     = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
