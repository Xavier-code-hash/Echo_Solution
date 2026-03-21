import uuid
from django.db import models
from django.conf import settings


class MaintenanceRequest(models.Model):
    class Priority(models.TextChoices):
        LOW       = "low",       "Low"
        MEDIUM    = "medium",    "Medium"
        HIGH      = "high",      "High"
        EMERGENCY = "emergency", "Emergency"

    class Status(models.TextChoices):
        OPEN        = "open",        "Open"
        ASSIGNED    = "assigned",    "Assigned"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED    = "resolved",    "Resolved"
        CLOSED      = "closed",      "Closed"

    class Category(models.TextChoices):
        PLUMBING   = "plumbing",   "Plumbing"
        ELECTRICAL = "electrical", "Electrical"
        HVAC       = "hvac",       "HVAC / AC"
        STRUCTURAL = "structural", "Structural"
        APPLIANCE  = "appliance",  "Appliance"
        SECURITY   = "security",   "Security"
        CLEANING   = "cleaning",   "Cleaning"
        OTHER      = "other",      "Other"

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit         = models.ForeignKey("properties.Unit", on_delete=models.CASCADE, related_name="maintenance")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="submitted_requests")
    assigned_to  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_requests")
    title        = models.CharField(max_length=200)
    description  = models.TextField()
    category     = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    priority     = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    image        = models.ImageField(upload_to="maintenance/", blank=True, null=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    resolution   = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    resolved_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.priority}] {self.title}"
