"""
apps/payments/services/receipt_pdf.py

Build a professional A4 PDF receipt and return it as raw bytes.

Usage:
    from apps.payments.services.receipt_pdf import build_receipt_pdf
    pdf_bytes = build_receipt_pdf(receipt)

Requires: reportlab  (pip install reportlab)
"""

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable,
)

# ── Colour palette ─────────────────────────────────────────────────────────
_BRAND   = colors.HexColor("#1e40af")   # deep blue  — headings / banner
_ACCENT  = colors.HexColor("#2563eb")   # mid blue   — section labels
_SUCCESS = colors.HexColor("#16a34a")   # green      — amounts / verified stamp
_LIGHT   = colors.HexColor("#f1f5f9")   # slate-100  — row backgrounds
_BORDER  = colors.HexColor("#cbd5e1")   # slate-300  — rule lines
_TXT     = colors.HexColor("#0f172a")   # slate-900  — body text
_TXT2    = colors.HexColor("#475569")   # slate-600  — labels / sub-text
_WHITE   = colors.white

PAGE_W, PAGE_H = A4


# ── Paragraph styles ───────────────────────────────────────────────────────

def _S():
    return {
        "brand": ParagraphStyle(
            "brand", fontName="Helvetica-Bold", fontSize=22,
            textColor=_BRAND, leading=26, alignment=TA_LEFT,
        ),
        "tagline": ParagraphStyle(
            "tagline", fontName="Helvetica", fontSize=9,
            textColor=_TXT2, leading=13, alignment=TA_LEFT,
        ),
        "receipt_no": ParagraphStyle(
            "receipt_no", fontName="Helvetica-Bold", fontSize=12,
            textColor=_ACCENT, leading=15, alignment=TA_RIGHT,
        ),
        "receipt_sub": ParagraphStyle(
            "receipt_sub", fontName="Helvetica", fontSize=9,
            textColor=_TXT2, leading=12, alignment=TA_RIGHT,
        ),
        "banner": ParagraphStyle(
            "banner", fontName="Helvetica-Bold", fontSize=9,
            textColor=_WHITE, leading=12, alignment=TA_LEFT,
        ),
        "label": ParagraphStyle(
            "label", fontName="Helvetica", fontSize=9,
            textColor=_TXT2, leading=13,
        ),
        "value": ParagraphStyle(
            "value", fontName="Helvetica-Bold", fontSize=9,
            textColor=_TXT, leading=13,
        ),
        "amt_label": ParagraphStyle(
            "amt_label", fontName="Helvetica-Bold", fontSize=12,
            textColor=_TXT, leading=16,
        ),
        "amt_value": ParagraphStyle(
            "amt_value", fontName="Helvetica-Bold", fontSize=18,
            textColor=_SUCCESS, leading=22, alignment=TA_RIGHT,
        ),
        "verified": ParagraphStyle(
            "verified", fontName="Helvetica-Bold", fontSize=9,
            textColor=_SUCCESS, leading=12, alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=8,
            textColor=_TXT2, leading=12, alignment=TA_CENTER,
        ),
    }


# ── Public entry point ─────────────────────────────────────────────────────

def build_receipt_pdf(receipt) -> bytes:
    """Return a PDF receipt as raw bytes for the given Receipt instance."""
    buf = BytesIO()
    S   = _S()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=14 * mm,  bottomMargin=14 * mm,
    )
    W = PAGE_W - 36 * mm     # usable width
    story = []

    # ── 1. Header ─────────────────────────────────────────────────────────
    hdr = Table(
        [[Paragraph("Echo Solutions", S["brand"]),
          _right_block(receipt, S)]],
        colWidths=[W * 0.55, W * 0.45],
    )
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [hdr,
              Paragraph("Property Management", S["tagline"]),
              Spacer(1, 4 * mm),
              HRFlowable(width="100%", thickness=2, color=_BRAND, spaceAfter=4 * mm)]

    # ── 2. "PAYMENT RECEIPT" banner ────────────────────────────────────────
    story += [_banner("PAYMENT RECEIPT", W, S),
              Spacer(1, 5 * mm)]

    # ── 3. Prominent amount ────────────────────────────────────────────────
    amt = Table(
        [[Paragraph("Amount Paid", S["amt_label"]),
          Paragraph(f"KES {receipt.amount:,.2f}", S["amt_value"])]],
        colWidths=[W * 0.5, W * 0.5],
    )
    amt.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story += [amt, Spacer(1, 5 * mm)]

    # ── 4. Two-column detail grid ──────────────────────────────────────────
    inv    = receipt.invoice
    tenant = receipt.tenant

    left = [
        ("Tenant",   tenant.get_full_name()),
        ("Email",    tenant.email),
        ("Unit",     f"{inv.lease.unit.property.name} #{inv.lease.unit.unit_number}"),
        ("Invoice",  inv.invoice_number),
        ("Period",   f"{inv.invoice_date.strftime('%d %b %Y')} – {inv.due_date.strftime('%d %b %Y')}"),
    ]
    right = [
        ("Receipt No.",   receipt.receipt_number),
        ("Date Issued",   receipt.issued_at.strftime("%d %b %Y %H:%M")),
        ("Payment Via",   receipt.gateway_display),
        ("Reference",     receipt.gateway_ref or "—"),
        ("Invoice Total", f"KES {inv.total_amount:,.2f}"),
    ]

    details = Table(
        [[_kv_table(left, W), _kv_table(right, W)]],
        colWidths=[W * 0.50, W * 0.50],
    )
    details.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBEFORE",   (1, 0), (1, -1), 0.75, _BORDER),
        ("LEFTPADDING",  (1, 0), (1, -1), 10),
    ]))
    story += [details, Spacer(1, 5 * mm)]

    # ── 5. Invoice breakdown ───────────────────────────────────────────────
    story += [_banner("Invoice Breakdown", W, S, color=_ACCENT),
              Spacer(1, 2 * mm)]

    rows  = [[Paragraph("Description", S["label"]),
              Paragraph("Amount (KES)", S["label"])]]
    rows += [["Rent", f"{inv.rent_amount:,.2f}"]]
    if inv.late_fee:
        rows += [["Late Fee",      f"{inv.late_fee:,.2f}"]]
    if inv.other_charges:
        rows += [["Other Charges", f"{inv.other_charges:,.2f}"]]
    if inv.discount:
        rows += [["Discount",      f"({inv.discount:,.2f})"]]

    rows += [
        ["Total",       f"{inv.total_amount:,.2f}"],
        ["Amount Paid", f"{inv.amount_paid:,.2f}"],
        ["Balance Due", f"{inv.balance_due:,.2f}"],
    ]
    n = len(rows)
    balance = inv.balance_due
    bk = Table(rows, colWidths=[W * 0.65, W * 0.35])
    bk.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, 0),   "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1),  9),
        ("BACKGROUND",    (0, 0), (-1, 0),   _LIGHT),
        ("ALIGN",         (1, 0), (1, -1),   "RIGHT"),
        ("TOPPADDING",    (0, 0), (-1, -1),  4),
        ("BOTTOMPADDING", (0, 0), (-1, -1),  4),
        ("LEFTPADDING",   (0, 0), (-1, -1),  8),
        ("RIGHTPADDING",  (0, 0), (-1, -1),  8),
        ("LINEBELOW",     (0, 0), (-1, -1),  0.5, _BORDER),
        # Total row
        ("FONTNAME",      (0, n - 3), (-1, n - 3), "Helvetica-Bold"),
        ("BACKGROUND",    (0, n - 3), (-1, n - 3), colors.HexColor("#e0f2fe")),
        # Amount Paid row
        ("FONTNAME",      (0, n - 2), (-1, n - 2), "Helvetica-Bold"),
        # Balance Due row — green if zero, red if outstanding
        ("FONTNAME",      (0, n - 1), (-1, n - 1), "Helvetica-Bold"),
        ("BACKGROUND",    (0, n - 1), (-1, n - 1),
            colors.HexColor("#dcfce7") if balance <= 0 else colors.HexColor("#fee2e2")),
        ("TEXTCOLOR",     (0, n - 1), (-1, n - 1),
            _SUCCESS if balance <= 0 else colors.HexColor("#b91c1c")),
    ]))
    story += [bk, Spacer(1, 6 * mm)]

    # ── 6. Verified stamp ─────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=1, color=_BORDER, spaceAfter=4 * mm),
        Paragraph(
            f"✓  Payment verified and recorded on "
            f"{receipt.issued_at.strftime('%d %B %Y at %H:%M')}",
            S["verified"],
        ),
        Spacer(1, 3 * mm),
    ]

    # ── 7. Footer ─────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=3 * mm),
        Paragraph(
            "This is an official receipt issued by Echo Solutions Property Management. "
            "Please retain for your records.<br/>"
            f"<b>{receipt.receipt_number}</b> &nbsp;|&nbsp; "
            f"Invoice {inv.invoice_number} &nbsp;|&nbsp; "
            "Generated automatically upon payment confirmation.",
            S["footer"],
        ),
    ]

    doc.build(story)
    return buf.getvalue()


# ── Helpers ────────────────────────────────────────────────────────────────

def _right_block(receipt, S):
    tbl = Table(
        [[Paragraph(receipt.receipt_number, S["receipt_no"])],
         [Paragraph(f"Issued: {receipt.issued_at.strftime('%d %b %Y')}", S["receipt_sub"])]],
        colWidths=["100%"],
    )
    tbl.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return tbl


def _banner(text, width, S, color=None):
    tbl = Table([[Paragraph(text, S["banner"])]], colWidths=[width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), color or _BRAND),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    return tbl


def _kv_table(rows, full_width):
    S = _S()
    data = [[Paragraph(k, S["label"]), Paragraph(v, S["value"])] for k, v in rows]
    col_w = full_width / 2
    t = Table(data, colWidths=[col_w * 0.42, col_w * 0.55])
    t.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.5, _BORDER),
    ]))
    return t