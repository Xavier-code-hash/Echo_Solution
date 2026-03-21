import uuid
from django.db import models


class CallbackRequest(models.Model):
    class Status(models.TextChoices):
        NEW       = "new", "New"
        CONTACTED = "contacted", "Contacted"
        CLOSED    = "closed", "Closed"

    class PreferredTime(models.TextChoices):
        ANYTIME   = "anytime", "Anytime"
        MORNING   = "morning", "Morning"
        AFTERNOON = "afternoon", "Afternoon"
        EVENING   = "evening", "Evening"

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name      = models.CharField(max_length=120)
    phone          = models.CharField(max_length=15)
    email          = models.EmailField(blank=True)
    preferred_time = models.CharField(max_length=20, choices=PreferredTime.choices,
                                      default=PreferredTime.ANYTIME)
    message        = models.TextField(blank=True)
    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at     = models.DateTimeField(auto_now_add=True)
    contacted_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"
