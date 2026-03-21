import uuid
from django.db import models
from django.conf import settings


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT   = "draft",   "Draft"
        SENT    = "sent",    "Sent"
        PAID    = "paid",    "Paid"
        PARTIAL = "partial", "Partial"
        OVERDUE = "overdue", "Overdue"
        VOID    = "void",    "Void"

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    lease          = models.ForeignKey("tenants.Lease", on_delete=models.PROTECT, related_name="invoices")
    status         = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    rent_amount    = models.DecimalField(max_digits=10, decimal_places=2)
    late_fee       = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    other_charges  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    discount       = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    invoice_date   = models.DateField()
    due_date       = models.DateField()
    paid_date      = models.DateField(null=True, blank=True)
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date"]

    def save(self, *args, **kwargs):
        self.total_amount = self.rent_amount + self.late_fee + self.other_charges - self.discount
        if not self.invoice_number:
            last = Invoice.objects.order_by("-created_at").first()
            n    = (int(last.invoice_number.split("-")[1]) + 1) if last else 1
            self.invoice_number = f"INV-{n:06d}"
        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    def __str__(self):
        return self.invoice_number


class Payment(models.Model):
    class Gateway(models.TextChoices):
        STRIPE = "stripe", "Card (Stripe)"
        MPESA  = "mpesa",  "M-Pesa"
        PAYPAL = "paypal", "PayPal"
        CASH   = "cash",   "Cash"
        BANK   = "bank",   "Bank Transfer"

    class Status(models.TextChoices):
        PENDING   = "pending",   "Pending"
        COMPLETED = "completed", "Completed"
        FAILED    = "failed",    "Failed"
        REFUNDED  = "refunded",  "Refunded"

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice        = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    tenant         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    amount         = models.DecimalField(max_digits=10, decimal_places=2)
    gateway        = models.CharField(max_length=10, choices=Gateway.choices)
    status         = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    stripe_pi_id   = models.CharField(max_length=255, blank=True)
    mpesa_ref      = models.CharField(max_length=100, blank=True)
    mpesa_checkout = models.CharField(max_length=100, blank=True)
    mpesa_phone    = models.CharField(max_length=15, blank=True)
    paypal_order   = models.CharField(max_length=100, blank=True)
    reference      = models.CharField(max_length=100, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.gateway} {self.amount} [{self.status}]"


class MpesaCallbackLog(models.Model):
    checkout_id = models.CharField(max_length=100, blank=True)
    invoice     = models.ForeignKey(Invoice, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="mpesa_logs")
    payment     = models.ForeignKey(Payment, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="mpesa_logs")
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)
    raw         = models.JSONField()
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"M-Pesa Callback {self.checkout_id or '-'} ({self.result_code})"


class Receipt(models.Model):
    """
    Immutable payment receipt — one per completed Payment.

    The OneToOneField on `payment` is the DB-level duplicate guard: a second
    INSERT for the same payment raises IntegrityError, caught by issue_receipt()
    which then returns the already-existing receipt instead of crashing.

    receipt_number  RCP-000001, RCP-000002 …  Sequential, never reused.
    gateway_ref     The external proof-of-payment reference (M-Pesa receipt /
                    Stripe PI ID / PayPal order ID / cash note).
    """

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=30, unique=True, editable=False)

    payment  = models.OneToOneField(
        Payment, on_delete=models.PROTECT, related_name="receipt"
    )
    invoice  = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name="receipts"
    )
    tenant   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="receipts"
    )

    amount      = models.DecimalField(max_digits=10, decimal_places=2)
    gateway     = models.CharField(max_length=10)
    gateway_ref = models.CharField(max_length=255, blank=True)
    issued_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.receipt_number

    @property
    def gateway_display(self):
        return {
            "stripe": "Card (Stripe)",
            "mpesa":  "M-Pesa",
            "paypal": "PayPal",
            "cash":   "Cash",
            "bank":   "Bank Transfer",
        }.get(self.gateway, self.gateway.title())