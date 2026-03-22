import logging

import stripe
from django.conf import settings

log = logging.getLogger("apps.payments")


def _client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_payment_intent(amount_kes: float, invoice_id: str) -> stripe.PaymentIntent:
    client = _client()
    pi = client.PaymentIntent.create(
        amount=int(amount_kes * 100),
        currency="kes",
        metadata={"invoice_id": invoice_id},
    )
    log.info("Stripe PaymentIntent created: %s", pi.id)
    return pi


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
