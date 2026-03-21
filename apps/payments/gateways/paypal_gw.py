"""
PayPal Orders API v2.
Docs: https://developer.paypal.com/docs/api/orders/v2/
"""
import logging, requests
from django.conf import settings

log = logging.getLogger("apps.payments")
_SANDBOX = "https://api-m.sandbox.paypal.com"
_LIVE    = "https://api-m.paypal.com"

def _url(path=""):
    base = _SANDBOX if settings.PAYPAL_ENVIRONMENT == "sandbox" else _LIVE
    return base + path

def get_token() -> str:
    r = requests.post(_url("/v1/oauth2/token"),
                      data={"grant_type": "client_credentials"},
                      auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
                      timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]

def create_order(amount: float, currency="USD", invoice_id="") -> dict:
    if not (settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET):
        return {"ok": False, "error": "PayPal not configured"}
    try:
        token = get_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{"amount": {"currency_code": currency.upper(), "value": f"{amount:.2f}"},
                                 "custom_id": str(invoice_id),
                                 "description": f"Echo_Solutions Rent — Inv {invoice_id}"}],
            "application_context": {
                "return_url": f"{settings.SITE_URL}/payments/paypal/success/",
                "cancel_url": f"{settings.SITE_URL}/payments/paypal/cancel/",
                "brand_name": "Echo_Solutions", "user_action": "PAY_NOW",
            },
        }
        r = requests.post(_url("/v2/checkout/orders"), json=payload,
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r.raise_for_status()
        d = r.json()
        approve = next((l["href"] for l in d["links"] if l["rel"] == "approve"), "")
        return {"ok": True, "order_id": d["id"], "approve_url": approve}
    except Exception as e:
        log.error("PayPal order: %s", e)
        return {"ok": False, "error": str(e)}

def capture_order(order_id: str) -> dict:
    try:
        token = get_token()
        r = requests.post(_url(f"/v2/checkout/orders/{order_id}/capture"),
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r.raise_for_status()
        d = r.json()
        cap = d["purchase_units"][0]["payments"]["captures"][0]
        return {"ok": d["status"] == "COMPLETED", "order_id": order_id,
                "capture_id": cap["id"], "amount": float(cap["amount"]["value"])}
    except Exception as e:
        log.error("PayPal capture: %s", e)
        return {"ok": False, "error": str(e)}
