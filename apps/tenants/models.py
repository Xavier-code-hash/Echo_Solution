import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class TenantProfile(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user      = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_profile")
    id_number = models.CharField(max_length=50, blank=True)
    dob       = models.DateField(null=True, blank=True)
    employer  = models.CharField(max_length=200, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    emergency_name = models.CharField(max_length=200, blank=True)
    emergency_phone = models.CharField(max_length=30, blank=True)
    emergency_relation = models.CharField(max_length=100, blank=True)
    notes     = models.TextField(blank=True)

    def __str__(self):
        return f"Profile: {self.user.get_full_name()}"


class Lease(models.Model):
    class Status(models.TextChoices):
        PENDING    = "pending",    "Pending"
        ACTIVE     = "active",     "Active"
        EXPIRED    = "expired",    "Expired"
        TERMINATED = "terminated", "Terminated"

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit         = models.ForeignKey("properties.Unit", on_delete=models.PROTECT, related_name="leases")
    tenant       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leases")
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    start_date   = models.DateField()
    end_date     = models.DateField()
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deposit_paid = models.BooleanField(default=False)
    rent_due_day = models.PositiveSmallIntegerField(default=1)
    late_fee     = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    grace_days   = models.PositiveSmallIntegerField(default=5)
    document     = models.FileField(upload_to="leases/", blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.tenant.get_full_name()} @ {self.unit}"

    @property
    def days_remaining(self):
        return (self.end_date - timezone.now().date()).days

    @property
    def is_expiring_soon(self):
        return 0 <= self.days_remaining <= 60
