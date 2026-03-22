import re


def normalize_msisdn(phone: str) -> str:
    """Normalize Kenyan phone numbers to 254XXXXXXXXX."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0") and len(digits) == 10:
        return "254" + digits[1:]
    if digits.startswith(("7", "1")) and len(digits) == 9:
        return "254" + digits
    if digits.startswith("254") and len(digits) == 12:
        return digits
    return ""