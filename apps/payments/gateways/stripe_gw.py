"""Stripe gateway — Card payments."""
import logging
import stripe
from django.conf import settings

log = logging.getLogger("apps.payments")


def _client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_payment_intent(amount: float, invoice, currency: str = "KES") -> dict:
    """
    Create a Stripe PaymentIntent and a matching PENDING Payment row in the DB.

    The Payment row must exist before the client confirms, so the webhook and
    stripe_confirm view can find it by stripe_pi_id and settle the invoice.

    Returns {"ok": True, "client_secret": "...", "pi_id": "pi_..."}
         or {"ok": False, "error": "..."}
    """
    from apps.payments.models import Payment

    try:
        pi = _client().PaymentIntent.create(
            amount   = int(amount * 100),
            currency = currency.lower(),
            metadata = {
                "invoice_id":     str(invoice.pk),
                "invoice_number": invoice.invoice_number,
            },
            automatic_payment_methods={"enabled": True},
        )

        payment = Payment.objects.create(
            invoice      = invoice,
            tenant       = invoice.lease.tenant,
            amount       = amount,
            gateway      = Payment.Gateway.STRIPE,
            stripe_pi_id = pi.id,
            status       = Payment.Status.PENDING,
        )
        log.info("Stripe PI created: %s (payment pk=%s)", pi.id, payment.pk)
        return {"ok": True, "client_secret": pi.client_secret, "pi_id": pi.id}

    except stripe.error.StripeError as e:
        log.error("Stripe create_payment_intent: %s", e)
        return {"ok": False, "error": str(e)}


def verify_webhook(payload: bytes, sig: str):
    """Validate Stripe webhook signature. Raises StripeError on failure."""
    return _client().Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)


def on_payment_succeeded(pi_id: str) -> None:
    """
    Mark the Payment COMPLETED and settle the Invoice.
    Idempotent — safe to call from both the webhook and stripe_confirm view.
    Receipt issuance is handled inside _settle() in views.py.
    """
    from apps.payments.models import Payment

    try:
        payment = Payment.objects.get(stripe_pi_id=pi_id)
    except Payment.DoesNotExist:
        log.warning("on_payment_succeeded: PI %s not found in DB", pi_id)
        return

    if payment.status == Payment.Status.COMPLETED:
        log.info("PI %s already settled — skipping duplicate call", pi_id)
        return

    payment.status = Payment.Status.COMPLETED
    payment.save(update_fields=["status", "updated_at"])

    # Import here to avoid circular imports; _settle also issues the receipt
    from apps.payments.views import _settle
    _settle(payment)
    log.info("Stripe PI %s settled — invoice %s", pi_id, payment.invoice.invoice_number)