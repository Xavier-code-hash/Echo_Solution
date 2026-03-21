"""
apps/payments/views.py

Receipt auto-generation happens for:
  - Physical cash  → immediately on form submission
  - Bank transfer  → immediately on form submission (owner verifies before submitting)
  - Stripe         → on stripe_confirm (client) and stripe_webhook (server)
  - M-Pesa         → on mpesa_callback from Safaricom
  - PayPal         → on paypal_success after order capture
"""
import json
import logging
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.payments.forms import InvoiceForm
from apps.payments.models import Invoice, MpesaCallbackLog, Payment, Receipt
from apps.payments.services.receipts import issue_receipt
from apps.payments.utils import normalize_msisdn

log = logging.getLogger("apps.payments")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _settle_invoice(invoice: Invoice) -> None:
    """Recalculate amount_paid and update invoice status after a completed payment."""
    from django.db.models import Sum
    paid = invoice.payments.filter(status="completed").aggregate(t=Sum("amount"))["t"] or 0
    invoice.amount_paid = paid
    if paid >= invoice.total_amount:
        invoice.status    = Invoice.Status.PAID
        invoice.paid_date = timezone.now().date()
    elif paid > 0:
        invoice.status = Invoice.Status.PARTIAL
    invoice.save(update_fields=["amount_paid", "status", "paid_date"])


def _issue_and_notify(payment: Payment) -> None:
    """Issue receipt and send email notification. Never raises — errors are logged only."""
    try:
        issue_receipt(payment)
    except Exception as exc:
        log.error("Receipt generation failed for payment %s: %s", payment.pk, exc)
    try:
        from apps.messaging.services import notify_payment_received
        notify_payment_received(payment)
    except Exception as exc:
        log.error("Payment notification failed for payment %s: %s", payment.pk, exc)


# ── Invoice views ─────────────────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class InvoiceListView(View):
    def get(self, request):
        u = request.user
        if u.is_owner_or_above:
            from apps.properties.models import Property, Unit
            from apps.tenants.models import Lease
            pids = Property.objects.filter(owner=u).values_list("id", flat=True)
            uids = Unit.objects.filter(property__in=pids).values_list("id", flat=True)
            lids = Lease.objects.filter(unit__in=uids).values_list("id", flat=True)
            qs   = Invoice.objects.filter(lease__in=lids).select_related(
                "lease__tenant", "lease__unit__property"
            )
        else:
            from apps.tenants.models import Lease
            lids = Lease.objects.filter(tenant=u).values_list("id", flat=True)
            qs   = Invoice.objects.filter(lease__in=lids).select_related(
                "lease__unit__property"
            )
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        return render(request, "payments/list.html", {"invoices": qs})


@method_decorator(login_required, name="dispatch")
class InvoiceCreateView(View):
    def get(self, request):
        if not request.user.is_owner_or_above:
            messages.error(request, "Permission denied.")
            return redirect("payments:list")
        lease_id = request.GET.get("lease")
        initial  = {}
        if lease_id:
            from apps.tenants.models import Lease
            try:
                lease = Lease.objects.get(pk=lease_id)
                initial = {
                    "lease": lease, "rent_amount": lease.monthly_rent,
                    "late_fee": lease.late_fee, "invoice_date": timezone.now().date(),
                    "due_date": timezone.now().date().replace(day=lease.rent_due_day),
                }
            except Exception:
                pass
        return render(request, "payments/form.html", {
            "form": InvoiceForm(initial=initial, owner=request.user)
        })

    def post(self, request):
        if not request.user.is_owner_or_above:
            messages.error(request, "Permission denied.")
            return redirect("payments:list")
        form = InvoiceForm(request.POST, owner=request.user)
        if form.is_valid():
            invoice        = form.save(commit=False)
            invoice.status = Invoice.Status.SENT
            invoice.save()
            messages.success(request, f"Invoice {invoice.invoice_number} created.")
            return redirect("payments:invoice-detail", pk=invoice.pk)
        return render(request, "payments/form.html", {"form": form})


@method_decorator(login_required, name="dispatch")
class InvoiceDetailView(View):
    def get(self, request, pk):
        invoice  = get_object_or_404(Invoice, pk=pk)
        payments = invoice.payments.select_related("tenant").order_by("-created_at")
        return render(request, "payments/invoice_detail.html", {
            "invoice": invoice, "payments": payments,
        })

    def post(self, request, pk):
        if not request.user.is_owner_or_above:
            messages.error(request, "Permission denied.")
            return redirect("payments:invoice-detail", pk=pk)
        invoice = get_object_or_404(Invoice, pk=pk)
        action  = request.POST.get("action")
        if action == "remind":
            from apps.messaging.services import notify_rent_due
            notify_rent_due(invoice.lease)
            messages.success(request, "Reminder sent to tenant.")
        elif action == "void":
            invoice.status = Invoice.Status.VOID
            invoice.save(update_fields=["status"])
            messages.success(request, f"Invoice {invoice.invoice_number} voided.")
        return redirect("payments:invoice-detail", pk=pk)


# ── Pay view ──────────────────────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class PayView(View):
    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        return render(request, "payments/pay.html", {
            "invoice":          invoice,
            "stripe_pk":        settings.STRIPE_PUBLISHABLE_KEY,
            "mpesa_configured": bool(settings.MPESA_CONSUMER_KEY),
            "paypal_client_id": settings.PAYPAL_CLIENT_ID,
            "today":            date.today().isoformat(),
        })

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        gateway = request.POST.get("gateway", "")
        handlers = {
            "stripe": self._stripe_init,
            "mpesa":  self._mpesa_push,
            "paypal": self._paypal_redirect,
            "cash":   self._cash_payment,
            "bank":   self._bank_payment,
        }
        handler = handlers.get(gateway)
        if not handler:
            messages.error(request, "Invalid payment method.")
            return redirect("payments:pay", pk=pk)
        return handler(request, invoice)

    # ── Stripe ────────────────────────────────────────────────────────────────

    def _stripe_init(self, request, invoice):
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            pi = stripe.PaymentIntent.create(
                amount=int(invoice.balance_due * 100),
                currency="kes",
                metadata={"invoice_id": str(invoice.pk)},
            )
            payment = Payment.objects.create(
                invoice=invoice, tenant=invoice.lease.tenant,
                amount=invoice.balance_due, gateway=Payment.Gateway.STRIPE,
                status=Payment.Status.PENDING, stripe_pi_id=pi.id,
            )
            log.info("Stripe PI created: %s (payment pk=%s)", pi.id, payment.pk)
            return JsonResponse({"ok": True, "client_secret": pi.client_secret})
        except Exception as exc:
            log.error("Stripe init error: %s", exc)
            return JsonResponse({"ok": False, "error": str(exc)})

    # ── M-Pesa ────────────────────────────────────────────────────────────────

    def _mpesa_push(self, request, invoice):
        phone = normalize_msisdn(request.POST.get("phone", ""))
        if not phone:
            messages.error(request, "Invalid phone number.")
            return redirect("payments:pay", pk=invoice.pk)
        payment = Payment.objects.create(
            invoice=invoice, tenant=invoice.lease.tenant,
            amount=invoice.balance_due, gateway=Payment.Gateway.MPESA,
            status=Payment.Status.PENDING, mpesa_phone=phone,
        )
        try:
            from apps.payments.services import mpesa as mpesa_svc
            checkout_id = mpesa_svc.stk_push(
                phone=phone, amount=int(invoice.balance_due),
                account_ref=invoice.invoice_number,
                description=f"Rent {invoice.invoice_number}",
            )
            payment.mpesa_checkout = checkout_id
            payment.save(update_fields=["mpesa_checkout"])
            log.info("M-Pesa STK → %s, checkout=%s", phone, checkout_id)
            messages.info(request, "M-Pesa prompt sent — enter your PIN to complete.")
        except Exception as exc:
            log.error("M-Pesa STK error: %s", exc)
            messages.error(request, f"M-Pesa error: {exc}")
        return redirect("payments:invoice-detail", pk=invoice.pk)

    # ── PayPal ────────────────────────────────────────────────────────────────

    def _paypal_redirect(self, request, invoice):
        try:
            from apps.payments.services import paypal as paypal_svc
            approve_url = paypal_svc.create_order(
                amount=float(invoice.balance_due), invoice=invoice,
                return_url=request.build_absolute_uri(
                    f"/payments/paypal/success/?invoice={invoice.pk}"
                ),
                cancel_url=request.build_absolute_uri(
                    f"/payments/paypal/cancel/?invoice={invoice.pk}"
                ),
            )
            return redirect(approve_url)
        except Exception as exc:
            log.error("PayPal order error: %s", exc)
            messages.error(request, f"PayPal error: {exc}")
            return redirect("payments:pay", pk=invoice.pk)

    # ── Physical cash ─────────────────────────────────────────────────────────

    def _cash_payment(self, request, invoice):
        """
        Owner confirms physical cash was handed over.
        Payment is marked COMPLETED immediately and receipt issued on the spot.
        """
        reference   = request.POST.get("reference", "").strip()
        received_by = request.POST.get("received_by", "").strip()
        notes       = request.POST.get("notes", "").strip()

        ref_parts = []
        if reference:   ref_parts.append(f"Ref: {reference}")
        if received_by: ref_parts.append(f"Received by: {received_by}")
        if notes:       ref_parts.append(notes)
        full_reference = " | ".join(ref_parts) if ref_parts else "Physical cash"

        payment = Payment.objects.create(
            invoice=invoice,
            tenant=invoice.lease.tenant,
            amount=invoice.balance_due,
            gateway=Payment.Gateway.CASH,
            status=Payment.Status.COMPLETED,
            reference=full_reference,
        )
        _settle_invoice(invoice)
        _issue_and_notify(payment)

        log.info(
            "Cash payment recorded — invoice %s, KES %s",
            invoice.invoice_number, payment.amount,
        )
        messages.success(
            request,
            f"Cash payment of KES {payment.amount:,.0f} recorded. "
            "Receipt generated and emailed to the tenant."
        )
        return redirect("payments:invoice-detail", pk=invoice.pk)

    # ── Bank transfer ─────────────────────────────────────────────────────────

    def _bank_payment(self, request, invoice):
        """
        Owner enters bank transfer confirmation details (or scans QR from slip).
        Receipt is issued immediately — owner is responsible for verifying the
        transfer before submitting this form.
        """
        bank_name   = request.POST.get("bank_name", "").strip()
        bank_branch = request.POST.get("bank_branch", "").strip()
        bank_code   = request.POST.get("bank_code", "").strip()
        bank_date   = request.POST.get("bank_date", "").strip()
        bank_sender = request.POST.get("bank_sender", "").strip()
        bank_amount = request.POST.get("bank_amount", "").strip()
        notes       = request.POST.get("notes", "").strip()

        if not bank_name or not bank_code:
            messages.error(request, "Bank name and transaction code are required.")
            return redirect("payments:pay", pk=invoice.pk)

        # Build a structured reference that will appear on the receipt PDF
        ref_parts = [bank_name]
        if bank_branch: ref_parts.append(f"({bank_branch})")
        ref_parts.append(f"| Code: {bank_code}")
        if bank_date:   ref_parts.append(f"| Date: {bank_date}")
        if bank_sender: ref_parts.append(f"| From: {bank_sender}")
        if notes:       ref_parts.append(f"| {notes}")
        full_reference = " ".join(ref_parts)

        try:
            amount = abs(float(bank_amount)) if bank_amount else float(invoice.balance_due)
        except ValueError:
            amount = float(invoice.balance_due)

        payment = Payment.objects.create(
            invoice=invoice,
            tenant=invoice.lease.tenant,
            amount=amount,
            gateway=Payment.Gateway.BANK,
            status=Payment.Status.COMPLETED,
            reference=full_reference,
        )
        _settle_invoice(invoice)
        _issue_and_notify(payment)

        log.info(
            "Bank payment recorded — invoice %s, KES %s, code: %s",
            invoice.invoice_number, payment.amount, bank_code,
        )
        messages.success(
            request,
            f"Bank transfer of KES {payment.amount:,.0f} recorded "
            f"(Code: {bank_code}). Receipt generated and emailed to the tenant."
        )
        return redirect("payments:invoice-detail", pk=invoice.pk)


# ── Stripe webhook ────────────────────────────────────────────────────────────

@csrf_exempt
def stripe_webhook(request):
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.META.get("HTTP_STRIPE_SIGNATURE", ""),
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception as exc:
        log.warning("Stripe webhook error: %s", exc)
        return HttpResponse(status=400)

    if event["type"] == "payment_intent.succeeded":
        pi_id = event["data"]["object"]["id"]
        try:
            payment = Payment.objects.get(stripe_pi_id=pi_id)
            if payment.status != Payment.Status.COMPLETED:
                payment.status = Payment.Status.COMPLETED
                payment.save(update_fields=["status"])
                _settle_invoice(payment.invoice)
                _issue_and_notify(payment)
                log.info("Stripe webhook settled invoice %s", payment.invoice.invoice_number)
        except Payment.DoesNotExist:
            log.warning("Stripe webhook: no payment for PI %s", pi_id)

    return HttpResponse(status=200)


# ── Stripe client-side confirm ────────────────────────────────────────────────

@login_required
def stripe_confirm(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"})
    pi_id = request.POST.get("pi_id", "")
    try:
        payment = Payment.objects.select_related("invoice").get(stripe_pi_id=pi_id)
        if payment.status != Payment.Status.COMPLETED:
            payment.status = Payment.Status.COMPLETED
            payment.save(update_fields=["status"])
            _settle_invoice(payment.invoice)
            _issue_and_notify(payment)
            log.info("Stripe PI %s settled — invoice %s", pi_id, payment.invoice.invoice_number)
        return JsonResponse({"ok": True})
    except Payment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Payment not found."})
    except Exception as exc:
        log.error("Stripe confirm error: %s", exc)
        return JsonResponse({"ok": False, "error": str(exc)})


# ── M-Pesa callback ───────────────────────────────────────────────────────────

@csrf_exempt
def mpesa_callback(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    try:
        body = json.loads(request.body)
    except Exception:
        return HttpResponse(status=400)

    stk   = body.get("Body", {}).get("stkCallback", {})
    co_id = stk.get("CheckoutRequestID", "")
    code  = stk.get("ResultCode")
    desc  = stk.get("ResultDesc", "")

    payment = invoice = None
    try:
        payment = Payment.objects.select_related("invoice").get(mpesa_checkout=co_id)
        invoice = payment.invoice
    except Payment.DoesNotExist:
        log.warning("M-Pesa callback: no payment for checkout %s", co_id)

    MpesaCallbackLog.objects.create(
        checkout_id=co_id, invoice=invoice, payment=payment,
        result_code=code, result_desc=desc, raw=body,
    )

    if code == 0 and payment:
        items = {
            item["Name"]: item.get("Value")
            for item in stk.get("CallbackMetadata", {}).get("Item", [])
        }
        mpesa_ref = str(items.get("MpesaReceiptNumber", ""))
        payment.status    = Payment.Status.COMPLETED
        payment.mpesa_ref = mpesa_ref
        payment.save(update_fields=["status", "mpesa_ref"])
        _settle_invoice(payment.invoice)
        _issue_and_notify(payment)
        log.info("M-Pesa settled invoice %s, ref %s", invoice.invoice_number, mpesa_ref)
    elif payment:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        log.info("M-Pesa failed: %s — %s", co_id, desc)

    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


# ── M-Pesa retry ─────────────────────────────────────────────────────────────

@login_required
def mpesa_retry(request, pk):
    if request.method != "POST":
        return redirect("payments:list")
    payment = get_object_or_404(Payment, pk=pk)
    try:
        from apps.payments.services import mpesa as mpesa_svc
        checkout_id = mpesa_svc.stk_push(
            phone=payment.mpesa_phone, amount=int(payment.amount),
            account_ref=payment.invoice.invoice_number,
            description=f"Rent {payment.invoice.invoice_number}",
        )
        payment.mpesa_checkout = checkout_id
        payment.status         = Payment.Status.PENDING
        payment.save(update_fields=["mpesa_checkout", "status"])
        messages.info(request, "M-Pesa prompt resent.")
    except Exception as exc:
        messages.error(request, f"Retry failed: {exc}")
    return redirect("payments:invoice-detail", pk=payment.invoice.pk)


# ── PayPal ────────────────────────────────────────────────────────────────────

@login_required
def paypal_success(request):
    invoice_pk = request.GET.get("invoice")
    token      = request.GET.get("token")
    invoice    = get_object_or_404(Invoice, pk=invoice_pk)
    try:
        from apps.payments.services import paypal as paypal_svc
        paypal_svc.capture_order(token)
        payment = Payment.objects.create(
            invoice=invoice, tenant=invoice.lease.tenant,
            amount=invoice.balance_due, gateway=Payment.Gateway.PAYPAL,
            status=Payment.Status.COMPLETED, paypal_order=token,
        )
        _settle_invoice(invoice)
        _issue_and_notify(payment)
        messages.success(request, "PayPal payment confirmed. Receipt emailed.")
    except Exception as exc:
        log.error("PayPal capture error: %s", exc)
        messages.error(request, f"PayPal capture failed: {exc}")
    return redirect("payments:invoice-detail", pk=invoice.pk)


@login_required
def paypal_cancel(request):
    messages.warning(request, "PayPal payment cancelled.")
    return redirect("payments:invoice-detail", pk=request.GET.get("invoice"))


# ── Receipts ──────────────────────────────────────────────────────────────────

@login_required
def receipt_list(request):
    u = request.user
    if u.is_owner_or_above:
        from apps.properties.models import Property, Unit
        from apps.tenants.models import Lease
        pids     = Property.objects.filter(owner=u).values_list("id", flat=True)
        uids     = Unit.objects.filter(property__in=pids).values_list("id", flat=True)
        lids     = Lease.objects.filter(unit__in=uids).values_list("id", flat=True)
        receipts = Receipt.objects.filter(
            invoice__lease__in=lids
        ).select_related("tenant", "invoice__lease__unit__property").order_by("-issued_at")
    else:
        receipts = Receipt.objects.filter(
            tenant=u
        ).select_related("invoice__lease__unit__property").order_by("-issued_at")
    return render(request, "payments/receipt_list.html", {"receipts": receipts})


@login_required
def receipt_download(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk)
    if receipt.tenant != request.user and not request.user.is_owner_or_above:
        messages.error(request, "Permission denied.")
        return redirect("payments:receipt-list")
    from apps.payments.services.receipt_pdf import build_receipt_pdf
    pdf = build_receipt_pdf(receipt)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="receipt_{receipt.receipt_number}.pdf"'
    )
    return response