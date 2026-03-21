"""
Safaricom M-Pesa STK Push — Daraja API v1.
Docs: https://developer.safaricom.co.ke/Documentation
"""
import base64, logging, requests
from datetime import datetime
from django.conf import settings

log = logging.getLogger("apps.payments")
_SANDBOX = "https://sandbox.safaricom.co.ke"
_LIVE    = "https://api.safaricom.co.ke"

def _url(path=""):
    base = _SANDBOX if settings.MPESA_ENVIRONMENT == "sandbox" else _LIVE
    return base + path

def get_token() -> str:
    creds = base64.b64encode(
        f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}".encode()).decode()
    r = requests.get(_url("/oauth/v1/generate?grant_type=client_credentials"),
                     headers={"Authorization": f"Basic {creds}"}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]

def _password(ts: str) -> str:
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{ts}"
    return base64.b64encode(raw.encode()).decode()

def stk_push(phone: str, amount: float, ref: str, desc: str) -> dict:
    """
    Initiate STK push.
    phone: 254XXXXXXXXX (no leading +)
    """
    if not (settings.MPESA_CONSUMER_KEY and settings.MPESA_CONSUMER_SECRET and settings.MPESA_PASSKEY):
        return {"ok": False, "error": "M-Pesa not configured"}
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        token = get_token()
        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password":          _password(ts),
            "Timestamp":         ts,
            "TransactionType":   "CustomerPayBillOnline",
            "Amount":            int(amount),
            "PartyA":            phone,
            "PartyB":            settings.MPESA_SHORTCODE,
            "PhoneNumber":       phone,
            "CallBackURL":       settings.MPESA_CALLBACK_URL,
            "AccountReference":  str(ref)[:12],
            "TransactionDesc":   str(desc)[:13],
        }
        r = requests.post(_url("/mpesa/stkpush/v1/processrequest"), json=payload,
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        log.info("M-Pesa STK → %s, checkout=%s", phone, data.get("CheckoutRequestID"))
        return {"ok": True, "checkout_id": data.get("CheckoutRequestID"), "raw": data}
    except Exception as e:
        log.error("M-Pesa error: %s", e)
        return {"ok": False, "error": str(e)}

def parse_callback(data: dict) -> dict:
    """Parse Daraja callback body."""
    try:
        cb   = data["Body"]["stkCallback"]
        code = cb["ResultCode"]
        cid  = cb["CheckoutRequestID"]
        if code == 0:
            items = {i["Name"]: i["Value"] for i in cb["CallbackMetadata"]["Item"]}
            return {
                "ok":       True,
                "checkout_id": cid,
                "code":     0,
                "result_desc": cb.get("ResultDesc"),
                "receipt":  items.get("MpesaReceiptNumber"),
                "amount":   items.get("Amount"),
                "phone":    str(items.get("PhoneNumber")),
            }
        return {"ok": False, "checkout_id": cid, "code": code, "result_desc": cb.get("ResultDesc")}
    except (KeyError, TypeError) as e:
        log.error("M-Pesa callback parse error: %s", e)
        return {"ok": False, "error": "malformed callback"}
