import logging

import requests
from django.conf import settings

log = logging.getLogger("apps.payments")

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
LIVE_BASE    = "https://api-m.paypal.com"


def _base_url():
    return SANDBOX_BASE if settings.PAYPAL_ENVIRONMENT == "sandbox" else LIVE_BASE


def _access_token() -> str:
    resp = requests.post(
        f"{_base_url()}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_order(amount: float, invoice, return_url: str, cancel_url: str) -> str:
    token = _access_token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": "USD",
                "value": f"{amount:.2f}",
            },
            "description": f"Invoice {invoice.invoice_number}",
        }],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    resp = requests.post(
        f"{_base_url()}/v2/checkout/orders",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    approve_url = next(
        (link["href"] for link in data.get("links", []) if link["rel"] == "approve"),
        None,
    )
    if not approve_url:
        raise RuntimeError("PayPal did not return an approval URL")

    log.info("PayPal order created: %s", data.get("id"))
    return approve_url


def capture_order(order_id: str) -> dict:
    token = _access_token()
    resp  = requests.post(
        f"{_base_url()}/v2/checkout/orders/{order_id}/capture",
        headers={
            "Authorization":  f"Bearer {token}",
            "Content-Type":   "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    log.info("PayPal order captured: %s status=%s", order_id, data.get("status"))
    return data
