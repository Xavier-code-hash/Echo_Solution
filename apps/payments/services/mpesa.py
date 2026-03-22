import base64
import logging
from datetime import datetime

import requests
from django.conf import settings

log = logging.getLogger("apps.payments")

SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
LIVE_BASE    = "https://api.safaricom.co.ke"


def _base_url():
    return SANDBOX_BASE if settings.MPESA_ENVIRONMENT == "sandbox" else LIVE_BASE


def _access_token() -> str:
    url  = f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    resp = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _password_and_timestamp():
    ts       = datetime.now().strftime("%Y%m%d%H%M%S")
    raw      = settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + ts
    password = base64.b64encode(raw.encode()).decode()
    return password, ts


def stk_push(phone: str, amount: int, account_ref: str, description: str) -> str:
    token    = _access_token()
    password, ts = _password_and_timestamp()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password":          password,
        "Timestamp":         ts,
        "TransactionType":   "CustomerPayBillOnline",
        "Amount":            amount,
        "PartyA":            phone,
        "PartyB":            settings.MPESA_SHORTCODE,
        "PhoneNumber":       phone,
        "CallBackURL":       settings.MPESA_CALLBACK_URL,
        "AccountReference":  account_ref,
        "TransactionDesc":   description,
    }

    resp = requests.post(
        f"{_base_url()}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("ResponseCode") != "0":
        raise RuntimeError(data.get("ResponseDescription", "STK push failed"))

    log.info("M-Pesa STK push sent to %s, CheckoutRequestID=%s", phone, data["CheckoutRequestID"])
    return data["CheckoutRequestID"]
