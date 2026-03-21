"""
apps/payments/services/receipts.py

Single entry point: issue_receipt(payment)

Guarantees
----------
* Exactly one receipt per completed Payment (OneToOneField + IntegrityError guard)
* Re-entrant / idempotent — safe to call from webhook AND client-side confirm
* Sends a receipt email to the tenant with the PDF attached
* Never raises — all errors are logged so a receipt failure never breaks
  the payment confirmation flow
"""

import logging
from django.db import IntegrityError, transaction

log = logging.getLogger("apps.payments")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def issue_receipt(payment) -> "Receipt":   # noqa: F821
    """
    Create a Receipt for *payment* (must be COMPLETED), persist it, send the
    receipt email, and return the Receipt instance.

    If a receipt already exists for this payment (duplicate call / race) the
    existing receipt is returned silently.

    Raises ValueError if payment.status != "completed".
    """
    from apps.payments.models import Receipt

    if payment.status != "completed":
        raise ValueError(
            f"Cannot issue receipt for payment {payment.pk} "
            f"with status '{payment.status}' — must be COMPLETED."
        )

    # Fast-path: receipt already exists (idempotent re-call)
    try:
        existing = payment.receipt
        log.debug("issue_receipt: receipt %s already exists, returning.", existing.receipt_number)
        return existing
    except Receipt.DoesNotExist:
        pass

    try:
        with transaction.atomic():
            receipt = Receipt(
                payment     = payment,
                invoice     = payment.invoice,
                tenant      = payment.tenant,
                amount      = payment.amount,
                gateway     = payment.gateway,
                gateway_ref = _gateway_ref(payment),
            )
            # Save first so we have a stable PK, then assign the sequential number
            receipt.save()
            receipt.receipt_number = _next_receipt_number(receipt)
            receipt.save(update_fields=["receipt_number"])

        log.info(
            "Receipt %s issued — payment %s, invoice %s, KES %s via %s",
            receipt.receipt_number, payment.pk,
            payment.invoice.invoice_number, payment.amount, payment.gateway,
        )

    except IntegrityError:
        # Race condition: another thread created the receipt first
        log.warning("Duplicate receipt attempt for payment %s — returning existing.", payment.pk)
        return payment.receipt

    # Send email (non-fatal — a mail failure must never roll back the receipt)
    try:
        _send_receipt_email(receipt)
    except Exception as exc:
        log.error("Receipt email failed for %s: %s", receipt.receipt_number, exc)

    return receipt


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _next_receipt_number(receipt) -> str:
    """
    Generate the next RCP-XXXXXX number.
    Runs inside the same atomic() block so the count is consistent.
    Falls back to the receipt's own PK suffix on any parse error.
    """
    from apps.payments.models import Receipt as R
    last = (
        R.objects
        .exclude(pk=receipt.pk)          # exclude the row we just saved
        .exclude(receipt_number="")
        .order_by("-issued_at")
        .values_list("receipt_number", flat=True)
        .first()
    )
    if last:
        try:
            seq = int(last.split("-")[1]) + 1
        except (IndexError, ValueError):
            seq = 1
    else:
        seq = 1
    return f"RCP-{seq:06d}"


def _gateway_ref(payment) -> str:
    """Return the most meaningful external reference for the gateway."""
    if payment.gateway == "mpesa":
        return payment.mpesa_ref or payment.mpesa_checkout or ""
    if payment.gateway == "stripe":
        return payment.stripe_pi_id or ""
    if payment.gateway == "paypal":
        return payment.paypal_order or ""
    return payment.reference or ""


def _send_receipt_email(receipt) -> None:
    """
    Email the PDF receipt to the tenant.
    Uses apps.messaging.services.send_email which already handles
    Brevo SMTP from your .env settings.
    """
    from apps.messaging.services import send_email
    from apps.payments.services.receipt_pdf import build_receipt_pdf

    tenant  = receipt.tenant
    invoice = receipt.invoice
    pdf     = build_receipt_pdf(receipt)

    subject = f"Payment Receipt {receipt.receipt_number} — {invoice.invoice_number}"
    body = (
        f"Hi {tenant.get_short_name()},\n\n"
        f"Thank you for your payment of KES {receipt.amount:,.2f} "
        f"for invoice {invoice.invoice_number}.\n\n"
        f"Receipt number : {receipt.receipt_number}\n"
        f"Payment method : {receipt.gateway_display}\n"
        f"Reference      : {receipt.gateway_ref or '—'}\n"
        f"Date           : {receipt.issued_at.strftime('%d %B %Y %H:%M')}\n\n"
        f"Your PDF receipt is attached to this email.\n\n"
        f"Echo Solutions Property Management"
    )

    send_email(
        to       = tenant.email,
        subject  = subject,
        body     = body,
        user     = tenant,
        attachment_bytes = pdf,
        attachment_name  = f"receipt_{receipt.receipt_number}.pdf",
        attachment_mime  = "application/pdf",
    )

    log.info("Receipt email sent to %s for %s", tenant.email, receipt.receipt_number)