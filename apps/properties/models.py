import uuid
from django.db import models
from django.conf import settings


class Property(models.Model):
    class Type(models.TextChoices):
        APARTMENT  = "apartment",  "Apartment Complex"
        HOUSE      = "house",      "House / Villa"
        COMMERCIAL = "commercial", "Commercial"
        MIXED      = "mixed",      "Mixed Use"
        LAND       = "land",       "Land / Plot"

    class Status(models.TextChoices):
        ACTIVE      = "active",      "Active"
        INACTIVE    = "inactive",    "Inactive"
        MAINTENANCE = "maintenance", "Under Maintenance"

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="properties")
    name         = models.CharField(max_length=200)
    type         = models.CharField(max_length=20, choices=Type.choices, default=Type.APARTMENT)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    description  = models.TextField(blank=True)
    cover_image  = models.ImageField(upload_to="properties/covers/", blank=True, null=True)
    address      = models.CharField(max_length=255)
    city         = models.CharField(max_length=100)
    county       = models.CharField(max_length=100, blank=True)
    country      = models.CharField(max_length=100, default="Kenya")
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    year_built   = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Properties"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def total_units(self):
        return self.units.count()

    @property
    def occupied_units(self):
        return self.units.filter(status=Unit.Status.OCCUPIED).count()

    @property
    def occupancy_rate(self):
        t = self.total_units
        return round(self.occupied_units / t * 100, 1) if t else 0

    @property
    def monthly_revenue(self):
        from django.db.models import Sum
        return self.units.filter(status=Unit.Status.OCCUPIED).aggregate(
            r=Sum("monthly_rent"))["r"] or 0


class Unit(models.Model):
    class Status(models.TextChoices):
        AVAILABLE   = "available",    "Available"
        OCCUPIED    = "occupied",     "Occupied"
        MAINTENANCE = "maintenance",  "Under Maintenance"
        RESERVED    = "reserved",     "Reserved"

    class BedType(models.TextChoices):
        STUDIO  = "studio",  "Studio"
        ONE     = "1bed",    "1 Bedroom"
        TWO     = "2bed",    "2 Bedrooms"
        THREE   = "3bed",    "3 Bedrooms"
        FOUR    = "4bed",    "4+ Bedrooms"
        PENT    = "pent",    "Penthouse"
        COMM    = "comm",    "Commercial"

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property     = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units")
    unit_number  = models.CharField(max_length=20)
    type         = models.CharField(max_length=10, choices=BedType.choices, default=BedType.ONE)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    floor        = models.PositiveSmallIntegerField(default=1)
    bedrooms     = models.PositiveSmallIntegerField(default=1)
    bathrooms    = models.DecimalField(max_digits=3, decimal_places=1, default=1)
    area_sqft    = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amenities    = models.JSONField(default=list, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("property", "unit_number")]
        ordering = ["property", "floor", "unit_number"]

    def __str__(self):
        return f"{self.property.name} — Unit {self.unit_number}"
